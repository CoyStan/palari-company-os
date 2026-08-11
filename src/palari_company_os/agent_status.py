from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_operation import AgentOperation, ensure_agent_operation
from .command_surface import bind_palari_command_payload
from .workspace import Workspace


def build_agent_status(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    *,
    operation: AgentOperation | None = None,
) -> dict[str, Any]:
    """Return the canonical read-only projection of current agent state."""

    operation_state = ensure_agent_operation(
        workspace,
        work_id,
        palari_id,
        mode,
        operation=operation,
    )
    brief = operation_state.brief()
    check = operation_state.check()
    directive = bind_palari_command_payload(
        workspace.data_path,
        operation_state.directive(),
    )
    return {
        "schema_version": "palari.agent_status.v1",
        "created_at": _timestamp(),
        "workspace": brief.get("workspace", workspace.name),
        "workspace_file": str(workspace.data_path),
        "would_mutate": False,
        "mode": mode or "execute",
        "agent": brief.get("agent", {}),
        "work_item": brief.get("work_item", {}),
        "status": directive.get("status", "blocked"),
        "owner": directive.get("owner", "agent"),
        "agent_may_execute": bool(directive.get("agent_may_execute", False)),
        "next_step_type": directive.get(
            "next_step_type",
            check.get("next_step_type", "inspect"),
        ),
        "next_action": directive.get("next_action", {}),
        "review_boundary": bool(directive.get("review_boundary", False)),
        "human_boundary": bool(directive.get("human_boundary", False)),
        "task_brief": {
            "packet_id": brief.get("packet_id", ""),
            "context_hash": brief.get("context_hash", ""),
            "status": brief.get("status", "blocked"),
            "instruction": brief.get("one_sentence_instruction", ""),
        },
        "task_limits": _task_limits(brief),
        "check": {
            "check_id": check.get("check_id", ""),
            "ok": bool(check.get("ok", False)),
            "requirements": list(check.get("checks", [])),
        },
        "stages": _stages(brief, check, directive),
        "blockers": list(directive.get("blockers", brief.get("blockers", []))),
        "resolution": directive.get("resolution_summary", {}),
        "missing_requirements": list(directive.get("missing_requirements", [])),
        "completed_requirements": list(directive.get("completed_requirements", [])),
        "automatic_transitions": list(directive.get("automatic_transitions", [])),
        "next_allowed_commands": list(directive.get("next_allowed_commands", [])),
    }


def _task_limits(brief: dict[str, Any]) -> dict[str, Any]:
    return {
        "allowed_paths": brief.get("allowed_paths", {"read": [], "write": []}),
        "allowed_resources": list(brief.get("allowed_resources", [])),
        "allowed_sources": list(brief.get("allowed_sources", [])),
        "allowed_capabilities": list(brief.get("allowed_capabilities", [])),
        "forbidden_actions": list(brief.get("forbidden_actions", [])),
        "stop_conditions": list(brief.get("stop_conditions", [])),
        "dependencies": list(brief.get("dependencies", [])),
        "completion_contract": brief.get("completion_contract", {}),
    }


def _stages(
    brief: dict[str, Any],
    check: dict[str, Any],
    directive: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "name": "brief",
            "status": brief.get("status", "blocked"),
            "ok": brief.get("status") == "ready",
        },
        {
            "name": "check",
            "status": "pass" if check.get("ok") else "fail",
            "ok": bool(check.get("ok", False)),
        },
        {
            "name": "next",
            "status": directive.get("status", "blocked"),
            "owner": directive.get("owner", "agent"),
            "agent_may_execute": bool(directive.get("agent_may_execute", False)),
        },
    ]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
