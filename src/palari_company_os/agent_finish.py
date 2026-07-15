from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_checks import build_agent_check
from .workspace import Workspace


HANDOFF_BLOCKERS = {
    "RECEIPT_READY_REVIEW",
    "HUMAN_DECISION_REQUIRED",
    "INTEGRATION_BOUNDARY",
}


def build_agent_finish(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
) -> dict[str, Any]:
    check = build_agent_check(workspace, work_id, palari_id, mode)
    failed_required = [
        item
        for item in check.get("checks", [])
        if item.get("required") and item.get("status") == "fail"
    ]
    missing_proof = [
        item for item in failed_required if item.get("code") != "PACKET_READY"
    ]
    blocker_codes = [blocker.get("code", "") for blocker in check.get("blockers", [])]
    linked_decision_command = _linked_decision_command(workspace, work_id)
    handoff_guidance = _handoff_guidance(check, linked_decision_command)
    human_approval_ready = (
        "HUMAN_DECISION_REQUIRED" in blocker_codes
        and linked_decision_command is None
        and human_approval_prerequisites_met(check)
    )
    handoff_ready = (
        human_approval_ready
        or (not missing_proof and bool(set(blocker_codes) & HANDOFF_BLOCKERS))
    )
    can_finish = bool(check.get("ok", False))
    status = _finish_status(can_finish, handoff_ready, missing_proof, blocker_codes)
    return {
        "schema_version": "palari.agent_finish.v1",
        "finish_id": _finish_id(work_id, palari_id, mode),
        "created_at": _timestamp(),
        "workspace": check.get("workspace", workspace.name),
        "mode": mode or "execute",
        "agent": check.get("agent", {}),
        "work_item": check.get("work_item", {}),
        "status": status,
        "can_finish": can_finish,
        "handoff_ready": handoff_ready,
        "would_mutate": False,
        "packet_id": check.get("packet_id", ""),
        "packet_context_hash": check.get("packet_context_hash", ""),
        "check_id": check.get("check_id", ""),
        "next_step_type": check.get("next_step_type", "inspect"),
        "missing_requirements": [_requirement(item) for item in missing_proof],
        "completed_requirements": [
            _requirement(item)
            for item in check.get("checks", [])
            if item.get("required") and item.get("status") == "pass"
        ],
        "blockers": check.get("blockers", []),
        "handoff_guidance": handoff_guidance,
        "next_allowed_commands": _next_commands(check),
        "report_guidance": _report_guidance(status, mode),
    }


def _finish_status(
    can_finish: bool,
    handoff_ready: bool,
    missing_proof: list[dict[str, Any]],
    blocker_codes: list[str],
) -> str:
    if can_finish:
        return "ready-to-report"
    if handoff_ready:
        return "handoff-ready"
    if missing_proof:
        return "missing-proof"
    if blocker_codes:
        return "blocked"
    return "not-ready"


def _next_commands(check: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for item in check.get("checks", []):
        if (
            item.get("required")
            and item.get("status") == "fail"
            and item.get("code") not in {"PACKET_READY", "HUMAN_DECISION_PRESENT"}
        ):
            _append_once(commands, item.get("next_command", ""))
    for command in check.get("next_allowed_commands", []):
        if not _is_human_action_command(command):
            _append_once(commands, command)
    blocker_codes = {blocker.get("code", "") for blocker in check.get("blockers", [])}
    work_id = check.get("work_item", {}).get("id", "WORK-ID")
    palari_id = check.get("agent", {}).get("id", "PALARI-ID")
    handoff_command = f"palari agent handoff {work_id} --as {palari_id} --json"
    review_command = f"palari review guide {work_id} --json"
    review_needed = (
        "RECEIPT_READY_REVIEW" in blocker_codes or "REVIEW_REQUIRED" in blocker_codes
    ) and review_prerequisites_met(check)
    if review_needed:
        _prioritize(commands, [handoff_command, review_command])
    _append_once(commands, "palari validate --json")
    return commands


def _handoff_guidance(
    check: dict[str, Any],
    linked_decision_command: str | None = None,
) -> list[dict[str, str]]:
    guidance: list[dict[str, str]] = []
    blocker_codes = {blocker.get("code", "") for blocker in check.get("blockers", [])}
    work_id = check.get("work_item", {}).get("id", "WORK-ID")
    palari_id = check.get("agent", {}).get("id", "PALARI-ID")
    handoff_command = f"palari agent handoff {work_id} --as {palari_id} --json"
    if (
        "RECEIPT_READY_REVIEW" in blocker_codes or "REVIEW_REQUIRED" in blocker_codes
    ) and review_prerequisites_met(check):
        guidance.append(
            {
                "code": "REVIEW_HANDOFF",
                "message": "Use agent handoff to inspect the receipt, evidence, and ready-to-edit review record commands.",
                "command": handoff_command,
                "guide_command": f"palari review guide {work_id} --json",
            }
        )
    if "HUMAN_DECISION_REQUIRED" in blocker_codes:
        decision_command = linked_decision_command or _first_decision_command(check)
        if linked_decision_command or decision_command.startswith("palari decision guide "):
            code = "DECISION_HANDOFF"
            message = "Use agent handoff for required human authority and suggested decision update commands."
        elif human_approval_prerequisites_met(check):
            code = "HUMAN_APPROVAL_HANDOFF"
            message = "Use agent handoff for required work approval and human-only acceptance commands."
        else:
            return guidance
        guidance.append(
            {
                "code": code,
                "message": message,
                "command": handoff_command,
                "guide_command": decision_command,
            }
        )
    return guidance


def human_approval_prerequisites_met(check: dict[str, Any]) -> bool:
    """Return whether receipt, evidence, and review proof is ready for human approval."""

    prerequisite_codes = {"RECEIPT_PRESENT", "EVIDENCE_PRESENT", "REVIEW_PRESENT"}
    checks = {item.get("code", ""): item for item in check.get("checks", [])}
    return all(
        checks.get(code, {}).get("required") is True
        and checks.get(code, {}).get("status") == "pass"
        for code in prerequisite_codes
    )


def review_prerequisites_met(check: dict[str, Any]) -> bool:
    """Return whether receipt and evidence are ready for independent review."""

    checks = {item.get("code", ""): item for item in check.get("checks", [])}
    receipt = checks.get("RECEIPT_PRESENT", {})
    evidence = checks.get("EVIDENCE_PRESENT", {})
    return (
        receipt.get("status") == "pass"
        and (not evidence.get("required") or evidence.get("status") == "pass")
    )


def _linked_decision_command(workspace: Workspace, work_id: str) -> str | None:
    for decision in workspace.decisions:
        if decision.linked_work == work_id:
            return f"palari decision guide {decision.id} --json"
    return None


def _first_decision_command(check: dict[str, Any]) -> str:
    for command in check.get("next_allowed_commands", []):
        if command.startswith("palari decision guide "):
            return command
    work_id = check.get("work_item", {}).get("id", "WORK-ID")
    return f"palari detail {work_id} --json"


def _append_once(commands: list[str], command: str) -> None:
    if command and command not in commands:
        commands.append(command)


def _is_human_action_command(command: str) -> bool:
    return command.startswith(
        (
            "palari human-decision record ",
            "palari work accept ",
            "palari review record ",
            "palari decision update ",
        )
    )


def _prioritize(commands: list[str], prioritized: list[str]) -> None:
    for command in reversed([item for item in prioritized if item]):
        if command in commands:
            commands.remove(command)
        commands.insert(0, command)


def _requirement(check: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "code": check.get("code", ""),
        "message": check.get("message", ""),
    }
    if check.get("next_command") and check.get("code") != "HUMAN_DECISION_PRESENT":
        payload["next_command"] = check["next_command"]
    return payload


def _report_guidance(status: str, mode: str) -> str:
    if status == "ready-to-report":
        if (mode or "execute") == "review":
            return (
                "Review packet checks pass. Report a review recommendation with evidence, "
                "but do not record a human review or claim the work item is complete unless "
                "explicitly authorized."
            )
        return "All required checks pass. Report completion and include the check result."
    if status == "handoff-ready":
        return "Do not continue execution. Hand off the completed proof to a human reviewer or approver."
    if status == "missing-proof":
        return "Do not claim completion yet. Record or refresh the missing trust records first."
    if status == "blocked":
        return "Do not claim completion. Resolve the packet blockers or ask a human to decide."
    return "Do not claim completion yet. Inspect the check result and next allowed commands."


def _finish_id(work_id: str, palari_id: str, mode: str) -> str:
    return f"FINISH-{_safe_id(work_id)}-{_safe_id(palari_id)}-{_safe_id(mode).upper()}-V1"


def _safe_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
    return cleaned.strip("-") or "UNKNOWN"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
