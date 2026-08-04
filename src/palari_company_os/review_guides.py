from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .authority_plan import build_authority_plan
from .command_surface import palari_workspace_command
from .governance_binding import current_review_binding
from .pcaw_canonical import canonical_sha256
from .read_models import detail
from .workspace import Workspace


SUGGESTED_VERDICTS = (
    "accept-ready",
    "changes-requested",
    "needs-human-decision",
    "blocked",
)


def build_review_guide(workspace: Workspace, work_id: str) -> dict[str, Any]:
    payload = detail(workspace, work_id)
    work = payload["work_item"]
    evidence = payload.get("evidence")
    attempt = payload.get("attempt")
    receipt = payload.get("receipt")
    review_focus = _review_focus(payload)
    authority_plan = build_authority_plan(
        workspace,
        work_id,
        builder_id=str((attempt or {}).get("actor", "")),
    )
    reviewer_candidates = _reviewer_candidates(
        workspace,
        work,
        work_id,
        evidence,
        authority_plan,
    )
    rejected_reviewer_candidates = _rejected_reviewer_candidates(
        workspace,
        authority_plan,
    )
    review_binding, review_binding_errors = current_review_binding(
        workspace,
        work_id,
        require_output_coverage=True,
    )
    review_record_commands = _review_record_commands(
        workspace,
        work_id,
        evidence,
        reviewer_candidates,
        review_binding,
        review_binding_errors,
    )
    commands_by_reviewer: dict[str, list[dict[str, Any]]] = {}
    for command in review_record_commands:
        commands_by_reviewer.setdefault(str(command["reviewer"]), []).append(command)
    for candidate in reviewer_candidates:
        candidate["review_record_commands"] = commands_by_reviewer.get(
            str(candidate["id"]),
            [],
        )
    return {
        "schema_version": "palari.review_guide.v2",
        "guide_id": f"REVIEW-GUIDE-{work_id}-V2",
        "created_at": _timestamp(),
        "workspace": workspace.name,
        "would_mutate": False,
        "status": _status(payload, authority_plan),
        "work_item": {
            "id": work["id"],
            "title": work["title"],
            "risk": work["risk"],
            "status": work["status"],
            "scope": work.get("scope", ""),
            "acceptance_target": work.get("acceptance_target", ""),
        },
        "workbench": payload.get("workbench"),
        "palari": _compact_ref(payload.get("palari"), ["id", "name", "role"]),
        "attention": payload.get("attention", ""),
        "why": payload.get("why", ""),
        "next_action": payload.get("next_action", ""),
        "evidence": _evidence_summary(evidence),
        "attempt": _attempt_summary(attempt),
        "receipt": _receipt_summary(receipt),
        "review_focus": review_focus,
        "authority_plan": authority_plan,
        "reviewer_candidates": reviewer_candidates,
        "rejected_reviewer_candidates": rejected_reviewer_candidates,
        "review_binding": review_binding,
        "review_binding_errors": review_binding_errors,
        "review_record_commands": review_record_commands,
        "suggested_verdicts": list(SUGGESTED_VERDICTS),
        "review_record_command_template": (
            _review_record_command_template(workspace, work_id, evidence)
            if reviewer_candidates
            else ""
        ),
        "review_record_command_template_executable": False,
        "next_commands": _next_commands(workspace, work_id),
        "omitted_context": [
            {
                "kind": "workspace_records",
                "reason": "Review guide v2 includes only records directly related to the selected work item.",
                "counts": {
                    "work_items": len(workspace.work_items),
                    "palaris": len(workspace.palaris),
                    "sources": len(workspace.sources),
                    "workbenches": len(workspace.workbenches),
                },
            }
        ],
    }


def palari_reviewer_candidate(
    workspace: Workspace, work_id: str, palari_id: str
) -> dict[str, Any] | None:
    """Return one eligible advisory Palari reviewer, if declared and bounded."""

    guide = build_review_guide(workspace, work_id)
    return next(
        (
            candidate
            for candidate in guide["reviewer_candidates"]
            if candidate["identity_type"] == "palari" and candidate["id"] == palari_id
        ),
        None,
    )


def _status(payload: dict[str, Any], authority_plan: dict[str, Any]) -> str:
    review_state = payload.get("safety", {}).get("review_state", "")
    if review_state == "stale":
        return "stale-review"
    if payload.get("evidence") is None:
        return "missing-evidence"
    if payload.get("review") is not None:
        return "has-review"
    if payload.get("attention") == "needs-review":
        if authority_plan["requires_review"] and not authority_plan["viable"]:
            return "authority-plan-blocked"
        return "review-needed"
    return "inspect"


def _evidence_summary(evidence: dict[str, Any] | None) -> dict[str, Any]:
    if evidence is None:
        return {"present": False}
    return {
        "present": True,
        "id": evidence.get("id", ""),
        "status": evidence.get("status", ""),
        "head_sha": evidence.get("head_sha", ""),
        "summary": evidence.get("summary", ""),
        "commands": evidence.get("commands", []),
        "artifacts": evidence.get("artifacts", []),
    }


def _attempt_summary(attempt: dict[str, Any] | None) -> dict[str, Any]:
    if attempt is None:
        return {"present": False}
    return {
        "present": True,
        "id": attempt.get("id", ""),
        "actor": attempt.get("actor", ""),
        "status": attempt.get("status", ""),
        "commits": attempt.get("commits", []),
        "changed_files": attempt.get("changed_files", []),
        "result": attempt.get("result", ""),
    }


def _receipt_summary(receipt: dict[str, Any] | None) -> dict[str, Any]:
    if receipt is None:
        return {"present": False}
    return {
        "present": True,
        "id": receipt.get("id", ""),
        "sources_used": receipt.get("sources_used", []),
        "actions_taken": receipt.get("actions_taken", []),
        "outputs_created": receipt.get("outputs_created", []),
        "external_writes": receipt.get("external_writes", []),
        "not_done": receipt.get("not_done", []),
        "undo_refs": receipt.get("undo_refs", []),
    }


def _review_focus(payload: dict[str, Any]) -> list[str]:
    focus = [
        "Compare the attempt result and changed files against the work scope and acceptance target.",
    ]
    focus.append("Confirm evidence commands and artifacts are enough for the stated risk.")
    if payload.get("receipt") is None:
        focus.append(
            "Receipt is missing; confirm whether the work state intentionally relies on evidence and review instead."
        )
    else:
        focus.append(
            "Confirm the receipt honestly states sources used, outputs created, external writes, not-done items, and undo refs."
        )
    focus.append("Confirm forbidden actions were not performed.")
    if payload.get("work_item", {}).get("risk") in {"R3", "R4", "R5"}:
        focus.append("Check the higher-risk boundary before any human decision or integration.")
    receipt = payload.get("receipt") or {}
    if receipt.get("external_writes"):
        focus.append("Inspect every external write claim and require explicit human authority.")
    if payload.get("review") is not None:
        focus.append("A review already exists; verify whether it still matches the latest evidence head.")
    return focus


def _reviewer_candidates(
    workspace: Workspace,
    work: dict[str, Any],
    work_id: str,
    evidence: dict[str, Any] | None,
    authority_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    required_capability = str(work.get("required_approval_capability", ""))
    for option in authority_plan["viable_reviewers"]:
        reviewer_id = str(option["id"])
        if option["identity_type"] == "palari":
            palari = workspace.palari(reviewer_id)
            if palari is None:
                continue
            candidates.append(
                {
                    "id": palari.id,
                    "name": palari.name,
                    "role": palari.role,
                    "identity_type": "palari",
                    "authority_level": "review-only",
                    "approval_capabilities": [],
                    "agent_may_execute": True,
                    "reason": (
                        "Distinct Palari linked to the goal and allowed sources; "
                        f"{option['message']} Its verdict is advisory and cannot "
                        "satisfy human quorum."
                    ),
                    "review_packet_command": (
                        palari_workspace_command(
                            workspace.data_path,
                            "agent",
                            "start",
                            work_id,
                            "--as",
                            palari.id,
                            "--mode",
                            "review",
                            "--json",
                        )
                    ),
                    "review_record_command_template": _review_record_command_template(
                        workspace,
                        work_id,
                        evidence,
                        reviewer_id=palari.id,
                    ),
                    "review_record_command_template_executable": False,
                }
            )
            continue
        human = workspace.human(reviewer_id)
        if human is None:
            continue
        capabilities = list(human.approval_capabilities)
        reason = _reviewer_reason(
            human.authority_level,
            capabilities,
            required_capability,
        )
        candidates.append(
            {
                "id": human.id,
                "name": human.name,
                "role": human.role,
                "identity_type": "human",
                "authority_level": human.authority_level,
                "approval_capabilities": capabilities,
                "agent_may_execute": False,
                "reason": f"{reason} {option['message']}",
                "review_record_command_template": _review_record_command_template(
                    workspace,
                    work_id,
                    evidence,
                    reviewer_id=human.id,
                ),
                "review_record_command_template_executable": False,
            }
        )
    return sorted(candidates, key=_reviewer_sort_key)


def _rejected_reviewer_candidates(
    workspace: Workspace,
    authority_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    rejected: list[dict[str, Any]] = []
    for option in authority_plan["rejected_reviewers"]:
        reviewer_id = str(option["id"])
        identity = (
            workspace.palari(reviewer_id)
            if option["identity_type"] == "palari"
            else workspace.human(reviewer_id)
        )
        rejected.append(
            {
                "id": reviewer_id,
                "name": getattr(identity, "name", ""),
                "role": getattr(identity, "role", ""),
                "identity_type": option["identity_type"],
                "agent_may_execute": False,
                "code": option["code"],
                "reason": option["message"],
                "smallest_correction": option["smallest_correction"],
            }
        )
    return rejected


def _reviewer_reason(
    authority_level: str, capabilities: list[str], required_capability: str
) -> str:
    if "technical-review" in capabilities:
        return "Has technical-review capability for independent inspection."
    if required_capability and required_capability in capabilities:
        return (
            f"Has {required_capability} approval capability; review is still separate from acceptance."
        )
    if authority_level == "admin":
        return "Has admin authority in this workbench; review remains advisory until a decision is recorded."
    return "Assigned to this workbench."


def _reviewer_sort_key(candidate: dict[str, Any]) -> tuple[int, str]:
    capabilities = set(candidate["approval_capabilities"])
    score = 0
    if candidate.get("identity_type") == "palari":
        score -= 10
    if "technical-review" in capabilities:
        score -= 3
    if candidate["authority_level"] == "admin":
        score -= 1
    return (score, candidate["id"])


def _review_record_command_template(
    workspace: Workspace,
    work_id: str,
    evidence: dict[str, Any] | None,
    reviewer_id: str = "REVIEWER-ID",
) -> str:
    reviewed_head = str(evidence.get("head_sha", "HEAD")) if evidence is not None else "HEAD"
    return palari_workspace_command(
        workspace.data_path,
        "review",
        "record",
        "REVIEW-ID",
        "--work-item-id",
        work_id,
        "--reviewed-head",
        reviewed_head,
        "--reviewer",
        reviewer_id,
        "--binding-digest",
        "BINDING-DIGEST",
        "--verdict",
        "VERDICT",
        "--json",
    )


def _review_record_commands(
    workspace: Workspace,
    work_id: str,
    evidence: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    binding: dict[str, str],
    binding_errors: list[str],
) -> list[dict[str, Any]]:
    if evidence is None or binding_errors or not binding:
        return []
    reviewed_head = str(evidence.get("head_sha") or "")
    if not reviewed_head:
        return []
    binding_digest = canonical_sha256(binding)
    commands: list[dict[str, Any]] = []
    for candidate in candidates:
        reviewer_id = str(candidate["id"])
        for verdict in SUGGESTED_VERDICTS:
            review_id = _concrete_review_id(
                work_id,
                reviewer_id,
                verdict,
                reviewed_head,
                binding_digest,
            )
            commands.append(
                {
                    "reviewer": reviewer_id,
                    "identity_type": str(candidate["identity_type"]),
                    "agent_may_execute": bool(candidate["agent_may_execute"]),
                    "verdict": verdict,
                    "review_id": review_id,
                    "review_binding_digest": binding_digest,
                    "executable": True,
                    "command": palari_workspace_command(
                        workspace.data_path,
                        "review",
                        "record",
                        review_id,
                        "--work-item-id",
                        work_id,
                        "--reviewed-head",
                        reviewed_head,
                        "--reviewer",
                        reviewer_id,
                        "--binding-digest",
                        binding_digest,
                        "--verdict",
                        verdict,
                        "--json",
                    ),
                }
            )
    return commands


def _concrete_review_id(
    work_id: str,
    reviewer_id: str,
    verdict: str,
    reviewed_head: str,
    binding_digest: str,
) -> str:
    digest = canonical_sha256(
        {
            "schema_version": "palari.review-command-binding.v1",
            "work_item_id": work_id,
            "reviewer_id": reviewer_id,
            "verdict": verdict,
            "reviewed_head": reviewed_head,
            "review_binding_digest": binding_digest,
        }
    )
    return f"REVIEW-{digest.removeprefix('sha256:')[:24].upper()}"


def _next_commands(workspace: Workspace, work_id: str) -> list[str]:
    return [
        palari_workspace_command(
            workspace.data_path,
            "detail",
            work_id,
            "--json",
        ),
        palari_workspace_command(
            workspace.data_path,
            "validate",
            "--json",
        ),
    ]


def _compact_ref(record: dict[str, Any] | None, keys: list[str]) -> dict[str, Any]:
    if not record:
        return {}
    return {key: record.get(key, "") for key in keys}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
