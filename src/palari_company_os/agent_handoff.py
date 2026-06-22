from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_finish import build_agent_finish
from .decision_guides import build_decision_guide
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
    review_handoff = (
        _review_handoff(workspace, work_id) if "REVIEW_HANDOFF" in guidance_codes else None
    )
    decision_handoff = (
        _decision_handoff(workspace, work_id) if "DECISION_HANDOFF" in guidance_codes else None
    )
    return {
        "schema_version": "palari.agent_handoff.v1",
        "handoff_id": _handoff_id(work_id, palari_id, mode),
        "created_at": _timestamp(),
        "workspace": finish.get("workspace", workspace.name),
        "would_mutate": False,
        "mode": mode or "execute",
        "status": finish.get("status", "blocked"),
        "handoff_available": bool(review_handoff or decision_handoff),
        "handoff_types": _handoff_types(review_handoff, decision_handoff),
        "next_step_type": finish.get("next_step_type", "inspect"),
        "agent": finish.get("agent", {}),
        "work_item": finish.get("work_item", {}),
        "finish": _finish_summary(finish),
        "review_handoff": review_handoff,
        "decision_handoff": decision_handoff,
        "next_allowed_commands": _agent_safe_commands(finish, review_handoff, decision_handoff),
        "human_action_commands": _human_action_commands(review_handoff, decision_handoff),
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
) -> list[str]:
    types: list[str] = []
    if review_handoff is not None:
        types.append("review")
    if decision_handoff is not None:
        types.append("decision")
    return types


def _agent_safe_commands(
    finish: dict[str, Any],
    review_handoff: dict[str, Any] | None,
    decision_handoff: dict[str, Any] | None,
) -> list[str]:
    commands: list[str] = []
    if review_handoff is not None:
        _append_once(commands, review_handoff["command"])
    if decision_handoff is not None:
        _append_once(commands, decision_handoff["command"])
    for command in finish.get("next_allowed_commands", []):
        if _is_read_only_command(command):
            _append_once(commands, command)
    _append_once(commands, "palari validate --json")
    return commands


def _human_action_commands(
    review_handoff: dict[str, Any] | None,
    decision_handoff: dict[str, Any] | None,
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
    return commands


def _is_read_only_command(command: str) -> bool:
    return bool(
        command.startswith("palari detail ")
        or command.startswith("palari queue ")
        or command.startswith("palari validate ")
        or command.startswith("palari review guide ")
        or command.startswith("palari decision guide ")
    )


def _pick(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload}


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
