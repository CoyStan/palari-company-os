from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_operation import AgentOperation, ensure_agent_operation
from .command_surface import bind_palari_workspace_command
from .workspace import Workspace


def build_agent_finish(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    *,
    operation: AgentOperation | None = None,
) -> dict[str, Any]:
    operation_state = ensure_agent_operation(
        workspace,
        work_id,
        palari_id,
        mode,
        operation=operation,
    )
    check = operation_state.check()
    directive = operation_state.directive()
    next_action = _bind_command_fields(
        workspace,
        directive["next_action"],
        {"command"},
    )
    automatic_transitions = _bind_command_fields(
        workspace,
        directive["automatic_transitions"],
        {"next_safe_action"},
    )
    missing_requirements = _bind_command_fields(
        workspace,
        directive["missing_requirements"],
        {"next_command"},
    )
    completed_requirements = _bind_command_fields(
        workspace,
        directive["completed_requirements"],
        {"next_command"},
    )
    blockers = _bind_command_fields(
        workspace,
        directive["blockers"],
        {"next_command", "next_safe_action"},
    )
    handoff_guidance = _bind_command_fields(
        workspace,
        directive["handoff_guidance"],
        {"command", "guide_command"},
    )
    return {
        "schema_version": "palari.agent_finish.v1",
        "finish_id": _finish_id(work_id, palari_id, mode),
        "created_at": _timestamp(),
        "workspace": check.get("workspace", workspace.name),
        "workspace_file": str(workspace.data_path),
        "mode": mode or "execute",
        "agent": check.get("agent", {}),
        "work_item": check.get("work_item", {}),
        "status": directive["status"],
        "owner": directive["owner"],
        "agent_may_execute": directive["agent_may_execute"],
        "next_action": next_action,
        "automatic_transitions": automatic_transitions,
        "review_boundary": directive["review_boundary"],
        "human_boundary": directive["human_boundary"],
        "can_finish": directive["can_finish"],
        "handoff_ready": directive["handoff_ready"],
        "would_mutate": False,
        "packet_id": check.get("packet_id", ""),
        "packet_context_hash": check.get("packet_context_hash", ""),
        "check_id": check.get("check_id", ""),
        "next_step_type": directive["next_step_type"],
        "missing_requirements": missing_requirements,
        "completed_requirements": completed_requirements,
        "blockers": blockers,
        "resolution_summary": directive["resolution_summary"],
        "handoff_guidance": handoff_guidance,
        "next_allowed_commands": [
            bind_palari_workspace_command(workspace.data_path, str(command))
            for command in directive["next_allowed_commands"]
        ],
        "report_guidance": directive["report_guidance"],
    }


def _bind_command_fields(
    workspace: Workspace,
    value: Any,
    field_names: set[str],
) -> Any:
    if isinstance(value, list):
        return [
            _bind_command_fields(workspace, item, field_names)
            for item in value
        ]
    if not isinstance(value, dict):
        return value
    payload: dict[str, Any] = {}
    for key, item in value.items():
        if key in field_names and isinstance(item, str):
            payload[key] = bind_palari_workspace_command(
                workspace.data_path,
                item,
            )
        else:
            payload[key] = _bind_command_fields(
                workspace,
                item,
                field_names,
            )
    return payload


def _finish_id(work_id: str, palari_id: str, mode: str) -> str:
    return f"FINISH-{_safe_id(work_id)}-{_safe_id(palari_id)}-{_safe_id(mode).upper()}-V1"


def _safe_id(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-" for char in value
    )
    return cleaned.strip("-") or "UNKNOWN"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
