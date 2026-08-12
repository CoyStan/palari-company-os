from __future__ import annotations

import json
import re
from typing import Any

from .command_surface import palari_command_parts


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


_PLAIN_STATUS_LABELS = {
    "ready": "Ready",
    "ready-for-ai-work": "Ready",
    "proposed": "Ready",
    "under-review": "Needs review",
    "active": "In progress",
    "in-progress": "In progress",
    "started": "In progress",
    "claimed": "In progress",
    "needs-evidence": "In progress",
    "changes-requested": "In progress",
    "ready-to-integrate": "In progress",
    "ready-to-complete": "In progress",
    "automatic-reconciliation": "In progress",
    "converge-ready": "In progress",
    "ready-to-report": "In progress",
    "blocked": "Blocked",
    "parked": "Blocked",
    "paused": "Blocked",
    "failed": "Blocked",
    "rejected": "Blocked",
    "abandoned": "Complete",
    "check-failed": "Blocked",
    "missing-proof": "Blocked",
    "no-ready-work": "Blocked",
    "needs-review": "Needs review",
    "in-review": "Needs review",
    "review-required": "Needs review",
    "review-handoff": "Needs review",
    "needs-human-decision": "Needs approval",
    "needs-human": "Needs approval",
    "human-decision-required": "Needs approval",
    "human-handoff-required": "Needs approval",
    "decision-ready": "Needs approval",
    "empty": "Complete",
    "released": "Ready",
    "closed": "Complete",
    "complete": "Complete",
    "completed": "Complete",
    "done": "Complete",
    "accepted": "Complete",
    "approved": "Complete",
    "superseded": "Complete",
    "archived": "Complete",
}

_PLAIN_FIELD_LABELS = {
    "work_item": "Task",
    "work_items": "Tasks",
    "work_item_id": "Task id",
    "workbench": "Project",
    "workbenches": "Projects",
    "workbench_id": "Project id",
    "palari": "Agent",
    "palaris": "Agents",
    "allowed_palaris": "Allowed agents",
    "attempt": "Run",
    "attempts": "Runs",
    "attempt_id": "Run id",
    "attempt_hash": "Run hash",
    "receipt": "Run record",
    "receipts": "Run records",
    "receipt_reference": "Run-record id",
    "receipt_hash": "Run-record hash",
    "proof_hash": "Review-binding hash",
    "evidence": "Checks",
    "evidence_runs": "Check results",
    "evidence_reference": "Check-results id",
    "evidence_manifest_hash": "Check-results hash",
    "artifacts": "Outputs",
    "artifact_hashes": "Output hashes",
    "review_verdicts": "Review results",
    "verdict": "Review result",
    "human_decision": "Approval or rejection",
    "human_decisions": "Approvals and rejections",
    "acceptance_records": "Approval records",
    "acceptance_target": "Completion target",
    "work_contract_hash": "Task-rules hash",
    "acceptance_mode": "Approval mode",
    "quorum_status": "Required approvals",
    "authority_profiles": "Approval profiles",
    "authority_level": "Permission level",
    "outcome": "Result",
    "outcomes": "Results",
    "packet_id": "Task brief id",
    "packet_context_hash": "Task-brief hash",
    "context_packet": "Task brief",
    "claim_id": "Task lock id",
    "claim_expires_at": "Task lock expires",
    "scope": "Task limits",
}

_PLAIN_STEP_LABELS = {
    "start-work": "Start or continue task",
    "check-active-proof": "Run checks",
    "repair": "Repair task",
    "review-handoff": "Get independent review",
    "human-decision": "Get human approval",
    "human-approval": "Get human approval",
    "automatic-reconciliation": "Finish automatically",
    "closed": "Complete",
    "inspect": "Inspect details",
    "attempt-record": "Record run",
    "receipt-record": "Record run record",
    "evidence-record": "Record check results",
    "review-record": "Record review result",
    "human-decision-record": "Record approval or rejection",
    "acceptance-record": "Record final approval",
    "outcome-record": "Record result",
    "work-complete": "Complete task",
    "claim-release": "Release task lock",
    "proof-projection": "Refresh current checks",
    "proof-refresh": "Refresh current checks",
    "verify": "Run required check",
    "work-attempt-bind": "Tie run to task",
    "attempt-closeout": "Close run",
    "lifecycle-complete": "Complete task",
    "complete-work": "Complete task",
    "resume": "Resume task",
}

_PLAIN_STEP_STATUS_LABELS = {
    "create": "To do",
    "required": "To do",
    "update": "To update",
    "close-out": "To close",
    "created": "Done",
    "updated": "Done",
    "closed-out": "Done",
    "completed": "Done",
    "released": "Done",
    "already-current": "Already current",
    "already-completed": "Already complete",
    "not-needed": "Not needed",
}

_PLAIN_DETAIL_STATE_LABELS = {
    "not-started": "Not started",
    "waiting-on-evidence": "Waiting for checks",
    "has-review": "Previous review found",
    "missing-evidence": "Check results missing",
    "stale-review": "Previous review is stale",
    "review-needed": "Ready for review",
    "missing-proof": "Missing checks",
    "changes-requested": "Needs changes",
    "accept-ready": "Ready for approval",
    "authority-plan-blocked": "Approval plan blocked",
    "needs-human-decision": "Needs approval",
    "not-required": "Not required",
    "ready-to-record": "Ready to record",
    "pass": "Passed",
    "fail": "Failed",
    "available": "Available",
    "not-available": "Not available",
    "invalid": "Needs attention",
    "missing": "Missing",
    "stale": "Stale",
    "current": "Current",
    "passed": "Passed",
    "failed": "Failed",
    "not-ready": "Not ready",
    "blocked-by-decision": "Waiting for decision",
    "blocked-by-review": "Waiting for review",
    "ready": "Ready",
    "queued": "Queued",
    "sent": "Sent",
}

_PLAIN_MESSAGE_REPLACEMENTS = (
    (
        r"\bstart a bounded attempt using the declared scope and authority limits\b",
        "start a bounded run using the allowed files, sources, and actions",
    ),
    (
        r"\ban attempt exists without evidence; verify before making completion claims\b",
        "a run exists without check results; verify before reporting completion",
    ),
    (
        r"\bcompare the attempt result and changed files against the work scope and acceptance target\b",
        "compare the run result and changed files against the task limits and completion target",
    ),
    (
        r"\breceipt is missing; confirm whether the work state intentionally relies on evidence and review instead\b",
        "the run record is missing; stop and return the task to the builder before review",
    ),
    (
        r"\blatest recorded proof is not current: attempt\b",
        "latest checks are not current: run",
    ),
    (r"\bhas no receipt\b", "has no run record"),
    (
        r"\blatest evidence is stale for the current attempt head\b",
        "latest check results are stale for the current run version",
    ),
    (
        r"\bhas no current artifact binding version\b",
        "is not tied to the current output bytes",
    ),
    (
        r"\bhas no current output binding version\b",
        "is not tied to the current output bytes",
    ),
    (r"\blatest recorded proof is not current\b", "latest checks are not current"),
    (r"\blatest evidence is stale\b", "latest check results are stale"),
    (
        r"\bthere is an attempt but no evidence run for it\b",
        "there is a run but no check result for it",
    ),
    (
        r"\brefresh exact passing evidence for the current attempt and receipt\b",
        "refresh passing checks for the current run and run record",
    ),
    (
        r"\brefresh evidence before requesting review or human decision\b",
        "refresh checks before requesting review or approval",
    ),
    (r"\brefresh evidence and review\b", "refresh checks and review"),
    (
        r"\brepair the receipt and refresh evidence\b",
        "repair the run record and refresh checks",
    ),
    (
        r"\bhash the current output bytes and refresh evidence\b",
        "hash the current output bytes and refresh checks",
    ),
    (r"\brefresh evidence\b", "refresh checks"),
    (
        r"\brun the focused verification expected for this work item\b",
        "run the required checks for this task",
    ),
    (
        r"\bno execution attempt exists yet\b",
        "no run exists yet",
    ),
    (
        r"\bthe recorded current proof derives the terminal lifecycle state\b",
        "checks show this task is complete",
    ),
    (
        r"\brecorded current proof satisfies the lifecycle completion candidate\b",
        "current checks allow completion",
    ),
    (
        r"\breconcile the terminal lifecycle state from externally verified proof\b",
        "finish the task from the current checked records",
    ),
    (
        r"\breconcile the terminal lifecycle state\b",
        "finish the task from the current checked records",
    ),
    (
        r"\binspect the current kernel diagnostics and repair the blocked proof\b",
        "inspect the current blockers and repair the failed checks",
    ),
    (
        r"\binspect the task's current proof and authority plan before retrying\b",
        "inspect the task's current checks and approval plan before retrying",
    ),
    (
        r"\brecord a receipt for the declared current attempt\b",
        "record a run record for the current run",
    ),
    (
        r"\brecord a receipt for the current attempt\b",
        "record a run record for the current run",
    ),
    (
        r"\bthe current attempt has no evidence\b",
        "the current run has no check results",
    ),
    (
        r"\bwork inside the persisted packet, then converge deterministic proof\b",
        "work inside the saved task brief, then run checks to completion",
    ),
    (
        r"\bconcrete packet-bound review commands\b",
        "concrete task-brief review commands",
    ),
    (
        r"\bresolve the packet blockers first\b",
        "resolve the task brief blockers first",
    ),
    (
        r"\bpacket blockers\b",
        "task brief blockers",
    ),
    (
        r"\bpacket-bound executable verdict commands\b",
        "task-brief review-result commands",
    ),
    (
        r"\bhuman-only executable verdict commands\b",
        "human-only review-result commands",
    ),
    (
        r"\bpacket-bound\b",
        "task-brief",
    ),
    (
        r"\bavailable verdicts\b",
        "available review results",
    ),
    (
        r"\bno human approval quorum is required\b",
        "no human approval is required",
    ),
    (
        r"\bapproval quorum is incomplete\b",
        "required approvals are incomplete",
    ),
    (
        r"\btask authority plan\b",
        "task approval plan",
    ),
    (
        r"\bauthority plan\b",
        "approval plan",
    ),
    (
        r"\bjournal continuity\b",
        "tamper-evident history",
    ),
    (
        r"\bpersisted packet\b",
        "saved task brief",
    ),
    (
        r"\bconverge deterministic proof\b",
        "run checks to completion",
    ),
    (
        r"\breleased claim for\b",
        "released task lock for",
    ),
    (
        r"\bclaim lease has expired\b",
        "task lock has expired",
    ),
    (
        r"\brenew the claim\b",
        "renew the task lock",
    ),
    (
        r"\bno remediation is required\b",
        "no repair is required",
    ),
    (
        r"\brun deterministic agent reconciliation\b",
        "run automatic finish from current records",
    ),
    (
        r"\bcurrent exact evidence\b",
        "current check results",
    ),
    (
        r"\bcurrent evidence to inspect\b",
        "current check results to inspect",
    ),
    (
        r"\bevidence-first local completion\b",
        "checks-first local completion",
    ),
    (
        r"\bmanufacturing human authority\b",
        "creating a human approval",
    ),
    (r"\bwork scope and acceptance target\b", "task limits and completion target"),
    (r"\bscope and acceptance target\b", "task limits and completion target"),
    (r"\bbefore any human decision or integration\b", "before any approval or integration"),
    (r"\bdistinct Palari\b", "different agent"),
    (r"\bhuman quorum\b", "required human approvals"),
    (r"\ballowed write paths\b", "allowed files"),
    (r"\bpacket write boundary\b", "task brief's allowed files"),
    (r"\bwrite boundary\b", "allowed files"),
    (r"\bscope boundaries\b", "task limits"),
    (r"\bscope boundary\b", "task limit"),
    (
        r"\bdeclared scope and authority limits\b",
        "allowed files, sources, and actions",
    ),
    (r"\bdeclared scope\b", "declared task limits"),
    (r"\bwork scope\b", "task limits"),
    (r"\bscope expansion\b", "task-limit expansion"),
    (r"\bwithin scope\b", "within the task limits"),
    (r"\boutside scope\b", "outside the task limits"),
    (r"\ban execution attempt\b", "a run"),
    (r"\ban attempt\b", "a run"),
    (r"\ban evidence run\b", "a check result"),
    (r"\bevidence is\b", "check results are"),
    (r"\bevidence was\b", "check results were"),
    (r"\bevidence has\b", "check results have"),
    (r"\bevidence remains\b", "check results remain"),
    (r"\bactive execute claim\b", "active execution task lock"),
    (r"\bactive claim\b", "active task lock"),
    (r"\bowned execute claim\b", "owned execution task lock"),
    (r"\bexecute claim\b", "execution task lock"),
    (r"\bclaim file\b", "task-lock file"),
    (r"\bclaim baseline\b", "task-lock baseline"),
    (r"\bclaim epoch\b", "task-lock period"),
    (r"\bclaim owner\b", "task-lock owner"),
    (r"\bclaim belongs\b", "task lock belongs"),
    (r"\bclaim mode\b", "task-lock mode"),
    (r"\bclaim is\b", "task lock is"),
    (r"\bclaim does\b", "task lock does"),
    (r"\bclaim differs\b", "task lock differs"),
    (r"\bclaim state\b", "task-lock state"),
    (r"\bno claim exists\b", "no task lock exists"),
    (r"\bclaimed packet\b", "locked task brief"),
    (r"\bagent packets\b", "task briefs"),
    (r"\bagent packet\b", "task brief"),
    (r"\bexecute packet\b", "execution task brief"),
    (r"\bcurrent packet\b", "current task brief"),
    (r"\bwork items\b", "tasks"),
    (r"\bwork item\b", "task"),
    (r"\bworkbenches\b", "projects"),
    (r"\bworkbench\b", "project"),
    (r"\bproof attempts\b", "checked runs"),
    (r"\bproof attempt\b", "checked run"),
    (r"\bexecution attempts\b", "runs"),
    (r"\bexecution attempt\b", "run"),
    (r"\bevidence runs\b", "check results"),
    (r"\bevidence run\b", "check result"),
    (r"\bevidence commands and artifacts\b", "check commands and outputs"),
    (r"\bevidence commands\b", "check commands"),
    (r"\breceipt and evidence\b", "run record and check results"),
    (r"\bevidence and receipt\b", "check results and run record"),
    (r"\breceipt, evidence\b", "run record, check results"),
    (r"\bevidence, receipt\b", "check results, run record"),
    (r"\bcurrent receipt\b", "current run record"),
    (r"\bmissing receipt\b", "missing run record"),
    (r"\breceipt is missing\b", "run record is missing"),
    (r"\bconfirm the receipt honestly\b", "confirm the run record honestly"),
    (r"\breceipt is\b", "run record is"),
    (r"\breceipt has\b", "run record has"),
    (r"\bexact proof\b", "checked version"),
    (r"\bcurrent proof\b", "current checks"),
    (r"\blatest evidence head\b", "latest checked version"),
    (r"\bits verdict is advisory\b", "its review result is advisory"),
    (
        r"\breview is still separate from acceptance\b",
        "review is still separate from final approval",
    ),
    (
        r"\buse agent status for required human authority and suggested decision update commands\b",
        "use agent status to show the decision and safe choices to the required human",
    ),
    (r"\bcheckpoint listing\b", "restore-point listing"),
    (r"\bcheckpoint digest\b", "restore-point digest"),
    (r"\bhuman decisions\b", "approvals or rejections"),
    (r"\bhuman decision\b", "approval or rejection"),
    (r"\bhuman authority\b", "human approval"),
    (r"\bhuman acceptance\b", "human approval"),
    (r"\bfinal acceptance\b", "final approval"),
    (r"\bacceptance records\b", "approval records"),
    (r"\bacceptance record\b", "approval record"),
    (r"\bapproval quorum\b", "required approvals"),
    (r"\brecorded outcome\b", "recorded result"),
    (r"\boutcome records\b", "result records"),
    (r"\boutcome record\b", "result record"),
    (r"\bgovernance kernel\b", "rules and checks"),
    (r"\bgovernance lifecycle\b", "work process"),
    (r"\blifecycle state\b", "status"),
    (r"\bterminal state\b", "complete state"),
    (r"\bterminal record\b", "completed record"),
    (r"\bgovernance journal checkpoint\b", "tamper-evident history restore point"),
    (r"\bgovernance journal\b", "tamper-evident history"),
    (r"\bclaiming completion\b", "reporting completion"),
    (r"\bgoverned artifacts\b", "governed outputs"),
    (r"\bgoverned artifact\b", "governed output"),
    (r"\bartifact bindings\b", "output bindings"),
    (r"\bartifact binding\b", "output binding"),
    (r"\bartifact bytes\b", "output bytes"),
    (r"\breview verdicts\b", "review results"),
    (r"\breview verdict\b", "review result"),
    (r"\baccept-ready\b", "ready for approval"),
    (r"\bthe acting Palari\b", "the acting agent"),
    (r"\bassigned Palari\b", "assigned agent"),
    (r"\bdifferent Palari\b", "different agent"),
    (r"\bPalari reviewer\b", "agent reviewer"),
    (r"\bPalari not found\b", "agent not found"),
    (r"\bmissing Palari\b", "missing agent"),
)


def plain_status(
    value: Any,
    *,
    next_step_type: Any = "",
    next_command: Any = "",
) -> str:
    """Return one small operator status without changing stored status values."""

    step = str(next_step_type or "")
    if step == "review-handoff":
        return "Needs review"
    if step == "human-decision" and _is_decision_guide(next_command):
        return "Blocked"
    if step in {"human-decision", "human-approval"}:
        return "Needs approval"
    text = str(value or "unknown")
    return _PLAIN_STATUS_LABELS.get(text, text.replace("-", " ").capitalize())


def plain_field(value: Any) -> str:
    """Make internal snake-case labels readable in non-JSON output only."""

    text = str(value)
    if text in _PLAIN_FIELD_LABELS:
        return _PLAIN_FIELD_LABELS[text]
    return text.replace("_", " ").replace("-", " ").strip().capitalize()


def plain_step(value: Any, *, next_command: Any = "") -> str:
    """Describe a structured next-step code in ordinary non-JSON output."""

    text = str(value or "inspect")
    if text == "human-decision" and _is_decision_guide(next_command):
        return "Ask a human to decide"
    return _PLAIN_STEP_LABELS.get(text, text.replace("-", " ").capitalize())


def _is_decision_guide(value: Any) -> bool:
    return palari_command_parts(str(value or ""))[:2] == (
        "decision",
        "guide",
    )


def plain_step_status(value: Any) -> str:
    """Describe an internal reconciliation status in ordinary language."""

    text = str(value or "unknown")
    return _PLAIN_STEP_STATUS_LABELS.get(text, text.replace("-", " ").capitalize())


def plain_detail_state(value: Any) -> str:
    """Render one secondary record state without changing its stored value."""

    text = str(value or "unknown")
    return _PLAIN_DETAIL_STATE_LABELS.get(text, text.replace("-", " ").capitalize())


def plain_message(value: Any) -> str:
    """Translate human-facing prose while preserving commands and machine tokens."""

    text = str(value or "")
    if text.lstrip().startswith("palari ") or text.startswith("Answer decision:"):
        return text
    protected: dict[str, str] = {}

    def protect(match: re.Match[str]) -> str:
        key = f"\x00{len(protected)}\x00"
        protected[key] = match.group(0)
        return key

    rendered = re.sub(
        r"\bevidence (?=[A-Z][A-Z0-9_]*(?:-[A-Za-z0-9][A-Za-z0-9_.]*)+\b)",
        "check result ",
        text,
        flags=re.IGNORECASE,
    )
    rendered = re.sub(r"`[^`]*`", protect, rendered)
    rendered = re.sub(r"(?:\./bin/)?palari(?:\s+[^\n]*)", protect, rendered)
    rendered = re.sub(
        r"\b[A-Z][A-Z0-9_]*(?:-[A-Za-z0-9][A-Za-z0-9_.]*)+\b",
        protect,
        rendered,
    )
    rendered = re.sub(
        r"(?<!\w)(?:(?:\.{0,2}/)?(?:[\w.-]+/)+[\w.-]+|[\w-]+\.[A-Za-z0-9]{1,8})(?!\w)",
        protect,
        rendered,
    )
    for pattern, replacement in _PLAIN_MESSAGE_REPLACEMENTS:
        def substitute(match: re.Match[str], replacement: str = replacement) -> str:
            if match.group(0)[:1].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement

        rendered = re.sub(pattern, substitute, rendered, flags=re.IGNORECASE)
    for key, original in protected.items():
        rendered = rendered.replace(key, original)
    return rendered
