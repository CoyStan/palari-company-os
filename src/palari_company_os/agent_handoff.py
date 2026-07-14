from __future__ import annotations

from datetime import datetime, timezone
from shlex import quote
from typing import Any

from .agent_finish import build_agent_finish
from .decision_guides import build_decision_guide
from .read_models import detail
from .review_guides import build_review_guide
from .workspace import Workspace


def build_agent_handoff(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
) -> dict[str, Any]:
    finish = build_agent_finish(workspace, work_id, palari_id, mode)
    guidance_codes = {item.get("code", "") for item in finish.get("handoff_guidance", [])}
    has_linked_decision = _has_linked_decision(workspace, work_id)
    decision_requested = "DECISION_HANDOFF" in guidance_codes or (
        "HUMAN_APPROVAL_HANDOFF" in guidance_codes and has_linked_decision
    )
    human_approval_requested = (
        "HUMAN_APPROVAL_HANDOFF" in guidance_codes and not has_linked_decision
    )
    review_handoff = (
        _review_handoff(workspace, work_id) if "REVIEW_HANDOFF" in guidance_codes else None
    )
    decision_handoff = _decision_handoff(workspace, work_id) if decision_requested else None
    human_approval_handoff = (
        _human_approval_handoff(workspace, work_id) if human_approval_requested else None
    )
    human_action_commands = _human_action_commands(
        review_handoff,
        decision_handoff,
        human_approval_handoff,
    )
    return {
        "schema_version": "palari.agent_handoff.v1",
        "handoff_id": _handoff_id(work_id, palari_id, mode),
        "created_at": _timestamp(),
        "workspace": finish.get("workspace", workspace.name),
        "would_mutate": False,
        "mode": mode or "execute",
        "status": finish.get("status", "blocked"),
        "handoff_available": bool(review_handoff or decision_handoff or human_approval_handoff),
        "handoff_types": _handoff_types(review_handoff, decision_handoff, human_approval_handoff),
        "next_step_type": finish.get("next_step_type", "inspect"),
        "agent": finish.get("agent", {}),
        "work_item": finish.get("work_item", {}),
        "finish": _finish_summary(finish),
        "review_handoff": review_handoff,
        "decision_handoff": decision_handoff,
        "human_approval_handoff": human_approval_handoff,
        "next_allowed_commands": _agent_safe_commands(
            finish,
            review_handoff,
            decision_handoff,
            human_approval_handoff,
        ),
        "human_action_commands": human_action_commands,
        "human_action_boundary": _human_action_boundary(human_action_commands),
        "omitted_context": [
            {
                "kind": "workspace_records",
                "reason": "Agent handoff v1 includes finish guidance and compact human review or decision context only.",
                "counts": {
                    "work_items": len(workspace.work_items),
                    "decisions": len(workspace.decisions),
                    "review_verdicts": len(workspace.review_verdicts),
                    "human_decisions": len(workspace.human_decisions),
                },
            }
        ],
    }


def _review_handoff(workspace: Workspace, work_id: str) -> dict[str, Any]:
    guide = build_review_guide(workspace, work_id)
    return {
        "schema_version": guide["schema_version"],
        "guide_id": guide["guide_id"],
        "command": f"palari review guide {work_id} --json",
        "status": guide["status"],
        "attention": guide.get("attention", ""),
        "why": guide.get("why", ""),
        "next_action": guide.get("next_action", ""),
        "work_item": guide["work_item"],
        "evidence": _pick(
            guide.get("evidence", {}),
            ["present", "id", "status", "head_sha", "summary"],
        ),
        "attempt": _pick(
            guide.get("attempt", {}),
            ["present", "id", "actor", "status", "result"],
        ),
        "receipt": _pick(
            guide.get("receipt", {}),
            [
                "present",
                "id",
                "sources_used",
                "outputs_created",
                "external_writes",
                "not_done",
                "undo_refs",
            ],
        ),
        "review_focus": guide.get("review_focus", []),
        "reviewer_candidates": guide.get("reviewer_candidates", []),
        "review_record_commands": guide.get("review_record_commands", []),
        "suggested_verdicts": guide.get("suggested_verdicts", []),
    }


def _decision_handoff(workspace: Workspace, work_id: str) -> dict[str, Any]:
    guide = build_decision_guide(workspace, work_id)
    return {
        "schema_version": guide["schema_version"],
        "guide_id": guide["guide_id"],
        "command": f"palari decision guide {guide['decision']['id']} --json",
        "status": guide["status"],
        "attention": guide.get("attention", ""),
        "why": guide.get("why", ""),
        "next_action": guide.get("next_action", ""),
        "decision": _pick(
            guide["decision"],
            [
                "id",
                "question",
                "status",
                "options",
                "recommendation",
                "safe_default",
                "required_human",
                "result",
            ],
        ),
        "required_human": guide.get("required_human", {}),
        "linked_work": guide.get("linked_work", {}),
        "decision_focus": guide.get("decision_focus", []),
        "suggested_results": guide.get("suggested_results", []),
        "decision_update_commands": guide.get("decision_update_commands", []),
    }


def _has_linked_decision(workspace: Workspace, work_id: str) -> bool:
    return any(decision.linked_work == work_id for decision in workspace.decisions)


def _human_approval_handoff(workspace: Workspace, work_id: str) -> dict[str, Any]:
    payload = detail(workspace, work_id)
    work = payload["work_item"]
    evidence = payload.get("evidence") or {}
    review = payload.get("review") or {}
    attempt = payload.get("attempt") or {}
    required_capability = work.get("required_approval_capability", "")
    candidates = _approval_candidates(workspace, required_capability)
    reviewed_head = review.get("reviewed_head") or evidence.get("head_sha") or _attempt_head(attempt)
    return {
        "schema_version": "palari.human_approval_handoff.v1",
        "guide_id": f"HUMAN-APPROVAL-{_safe_id(work_id)}-V1",
        "command": f"palari detail {work_id} --json",
        "status": payload.get("attention", ""),
        "attention": payload.get("attention", ""),
        "why": payload.get("why", ""),
        "next_action": payload.get("next_action", ""),
        "approval_progress": payload.get("safety", {}).get("approval_progress", ""),
        "required_approval_count": work.get("required_approval_count", 0),
        "required_approval_capability": required_capability,
        "reviewed_head": reviewed_head,
        "work_item": _pick(
            work,
            [
                "id",
                "title",
                "risk",
                "status",
                "scope",
                "acceptance_target",
                "forbidden_actions",
            ],
        ),
        "evidence": _pick(evidence, ["id", "status", "head_sha", "summary"]),
        "review": _pick(review, ["id", "reviewer", "verdict", "reviewed_head", "residual_risks"]),
        "attempt": _pick(attempt, ["id", "actor", "status", "result"]),
        "approval_candidates": candidates,
        "approval_focus": _approval_focus(payload),
        "human_decision_record_commands": _human_decision_record_commands(
            work_id,
            candidates,
            reviewed_head,
            evidence.get("id", ""),
            review.get("id", ""),
        ),
    }


def _finish_summary(finish: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": finish["schema_version"],
        "finish_id": finish["finish_id"],
        "packet_id": finish.get("packet_id", ""),
        "packet_context_hash": finish.get("packet_context_hash", ""),
        "check_id": finish.get("check_id", ""),
        "status": finish["status"],
        "can_finish": finish["can_finish"],
        "handoff_ready": finish["handoff_ready"],
        "report_guidance": finish["report_guidance"],
        "handoff_guidance": finish.get("handoff_guidance", []),
        "missing_requirements": finish.get("missing_requirements", []),
        "completed_requirements": finish.get("completed_requirements", []),
        "blockers": finish.get("blockers", []),
    }


def _handoff_types(
    review_handoff: dict[str, Any] | None,
    decision_handoff: dict[str, Any] | None,
    human_approval_handoff: dict[str, Any] | None,
) -> list[str]:
    types: list[str] = []
    if review_handoff is not None:
        types.append("review")
    if decision_handoff is not None:
        types.append("decision")
    if human_approval_handoff is not None:
        types.append("human-approval")
    return types


def _agent_safe_commands(
    finish: dict[str, Any],
    review_handoff: dict[str, Any] | None,
    decision_handoff: dict[str, Any] | None,
    human_approval_handoff: dict[str, Any] | None,
) -> list[str]:
    commands: list[str] = []
    has_handoff = bool(review_handoff or decision_handoff or human_approval_handoff)
    if review_handoff is not None:
        _append_once(commands, review_handoff["command"])
    if decision_handoff is not None:
        _append_once(commands, decision_handoff["command"])
    if human_approval_handoff is not None:
        _append_once(commands, human_approval_handoff["command"])
    for command in finish.get("next_allowed_commands", []):
        if not has_handoff or _is_read_only_command(command):
            _append_once(commands, command)
    _append_once(commands, "palari validate --json")
    return commands


def _is_read_only_command(command: str) -> bool:
    return bool(
        command.startswith("palari detail ")
        or command.startswith("palari queue ")
        or command.startswith("palari validate ")
        or command.startswith("palari review guide ")
        or command.startswith("palari decision guide ")
    )


def _human_action_commands(
    review_handoff: dict[str, Any] | None,
    decision_handoff: dict[str, Any] | None,
    human_approval_handoff: dict[str, Any] | None,
) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    if review_handoff is not None:
        for item in review_handoff.get("review_record_commands", []):
            commands.append(
                {
                    "type": "review-record",
                    "actor": item.get("reviewer", ""),
                    "command": item.get("command", ""),
                }
            )
    if decision_handoff is not None:
        for item in decision_handoff.get("decision_update_commands", []):
            commands.append(
                {
                    "type": "decision-update",
                    "actor": decision_handoff.get("decision", {}).get("required_human", ""),
                    "result": item.get("result", ""),
                    "command": item.get("command", ""),
                }
            )
    if human_approval_handoff is not None:
        for item in human_approval_handoff.get("human_decision_record_commands", []):
            commands.append(
                {
                    "type": "human-approval-record",
                    "actor": item.get("human_id", ""),
                    "result": item.get("decision", ""),
                    "command": item.get("command", ""),
                }
            )
    return commands


def _human_action_boundary(human_action_commands: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "agent_may_execute": False,
        "agent_allowed_use": "Quote or summarize human-only commands for a human supervisor.",
        "human_only_command_fields": ["human_action_commands[].command"],
        "count": len(human_action_commands),
        "must_not": [
            "Do not run human action commands.",
            "Do not claim to be the required human actor.",
            "Do not convert a recommendation into human review, decision, or acceptance.",
        ],
    }


def _pick(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload}


def _approval_candidates(workspace: Workspace, required_capability: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for human in workspace.humans:
        if required_capability and required_capability not in human.approval_capabilities:
            continue
        candidates.append(
            {
                "id": human.id,
                "name": human.name,
                "role": human.role,
                "authority_level": human.authority_level,
                "approval_capabilities": human.approval_capabilities,
            }
        )
    return candidates


def _approval_focus(payload: dict[str, Any]) -> list[str]:
    focus = [
        "Inspect the work output, evidence, review verdict, and residual risks before approving.",
        "Do not approve if required proof is missing or stale.",
    ]
    safety = payload.get("safety", {})
    if safety.get("receipt_state") != "ready":
        focus.append(f"Receipt state is {safety.get('receipt_state', 'unknown')}; require a receipt if the completion contract asks for one.")
    work = payload.get("work_item", {})
    if work.get("forbidden_actions"):
        focus.append("Confirm approval does not authorize forbidden actions without new scoped work.")
    return focus


def _human_decision_record_commands(
    work_id: str,
    candidates: list[dict[str, Any]],
    reviewed_head: str,
    evidence_id: str,
    review_id: str,
) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    for candidate in candidates:
        human_id = candidate["id"]
        for decision, status, quorum in [
            ("accepted", "accepted", "met"),
            ("changes-requested", "changes-requested", "not-met"),
            ("blocked", "blocked", "not-met"),
        ]:
            commands.append(
                {
                    "human_id": human_id,
                    "decision": decision,
                    "command": _human_decision_record_command(
                        work_id,
                        human_id,
                        reviewed_head,
                        decision,
                        status,
                        quorum,
                        evidence_id,
                        review_id,
                    ),
                }
            )
    return commands


def _human_decision_record_command(
    work_id: str,
    human_id: str,
    reviewed_head: str,
    decision: str,
    status: str,
    quorum_status: str,
    evidence_id: str,
    review_id: str,
) -> str:
    record_id = f"HUMAN-DECISION-{_safe_id(work_id)}-{_safe_id(human_id)}-{_safe_id(decision)}"
    parts = [
        "palari",
        "human-decision",
        "record",
        record_id,
        "--work-item-id",
        work_id,
        "--human-id",
        human_id,
        "--reviewed-head",
        reviewed_head or "REVIEWED-HEAD",
        "--decision",
        decision,
        "--status",
        status,
        "--quorum-status",
        quorum_status,
    ]
    if evidence_id:
        parts.extend(["--evidence-reference", evidence_id])
    if review_id:
        parts.extend(["--review-reference", review_id])
    parts.append("--json")
    return " ".join(quote(part) for part in parts)


def _attempt_head(attempt: dict[str, Any]) -> str:
    if attempt.get("head_sha"):
        return str(attempt["head_sha"])
    commits = attempt.get("commits", [])
    return commits[-1] if commits else ""


def _append_once(commands: list[str], command: str) -> None:
    if command and command not in commands:
        commands.append(command)


def _handoff_id(work_id: str, palari_id: str, mode: str) -> str:
    return f"HANDOFF-{_safe_id(work_id)}-{_safe_id(palari_id)}-{_safe_id(mode).upper()}-V1"


def _safe_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
    return cleaned.strip("-") or "UNKNOWN"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
