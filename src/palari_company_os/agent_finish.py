from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_directive import (
    AUTOMATIC_BLOCKERS,
    EXTERNAL_BLOCKERS,
    HANDOFF_BLOCKERS,
    HUMAN_BLOCKERS,
    REVIEW_BLOCKERS,
    TERMINAL_BLOCKERS,
    classify_resolution,
    enrich_blockers,
    human_approval_prerequisites_met,
    resolution_summary,
    review_prerequisites_met,
)
from .agent_operation import AgentOperation, ensure_agent_operation
from .governance_journal import JournalVerificationContext
from .workspace import Workspace


def build_agent_finish(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    *,
    journal_context: JournalVerificationContext | None = None,
    operation: AgentOperation | None = None,
) -> dict[str, Any]:
    operation_state = ensure_agent_operation(
        workspace,
        work_id,
        palari_id,
        mode,
        journal_context=journal_context,
        operation=operation,
    )
    check = operation_state.check()
    directive = operation_state.directive()
    return {
        "schema_version": "palari.agent_finish.v1",
        "finish_id": _finish_id(work_id, palari_id, mode),
        "created_at": _timestamp(),
        "workspace": check.get("workspace", workspace.name),
        "mode": mode or "execute",
        "agent": check.get("agent", {}),
        "work_item": check.get("work_item", {}),
        "status": directive["status"],
        "owner": directive["owner"],
        "agent_may_execute": directive["agent_may_execute"],
        "next_action": directive["next_action"],
        "automatic_transitions": directive["automatic_transitions"],
        "review_boundary": directive["review_boundary"],
        "human_boundary": directive["human_boundary"],
        "can_finish": directive["can_finish"],
        "handoff_ready": directive["handoff_ready"],
        "would_mutate": False,
        "packet_id": check.get("packet_id", ""),
        "packet_context_hash": check.get("packet_context_hash", ""),
        "check_id": check.get("check_id", ""),
        "next_step_type": directive["next_step_type"],
        "missing_requirements": directive["missing_requirements"],
        "completed_requirements": directive["completed_requirements"],
        "blockers": directive["blockers"],
        "resolution_summary": directive["resolution_summary"],
        "handoff_guidance": directive["handoff_guidance"],
        "next_allowed_commands": directive["next_allowed_commands"],
        "report_guidance": directive["report_guidance"],
    }


def _finish_id(work_id: str, palari_id: str, mode: str) -> str:
    return f"FINISH-{_safe_id(work_id)}-{_safe_id(palari_id)}-{_safe_id(mode).upper()}-V1"


def _safe_id(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-" for char in value
    )
    return cleaned.strip("-") or "UNKNOWN"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
