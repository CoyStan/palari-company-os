from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_directive import enrich_blockers, resolution_summary
from .agent_finish import build_agent_finish
from .agent_handoff import build_agent_handoff
from .agent_operation import AgentOperation, ensure_agent_operation
from .governance_journal import JournalVerificationContext
from .workspace import Workspace


def build_agent_loop(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    *,
    journal_context: JournalVerificationContext | None = None,
    operation: AgentOperation | None = None,
) -> dict[str, Any]:
    """Return a compact read-only view of the agent operating loop."""

    operation_state = ensure_agent_operation(
        workspace,
        work_id,
        palari_id,
        mode,
        journal_context=journal_context,
        operation=operation,
    )
    brief = operation_state.brief()
    check = operation_state.check()
    finish = build_agent_finish(
        workspace,
        work_id,
        palari_id,
        mode,
        journal_context=operation_state.journal_context,
        operation=operation_state,
    )
    handoff = (
        build_agent_handoff(
            workspace,
            work_id,
            palari_id,
            mode,
            journal_context=operation_state.journal_context,
            operation=operation_state,
        )
        if _should_include_handoff(finish)
        else None
    )
    stages = [
        _brief_stage(work_id, palari_id, mode, brief),
        _check_stage(work_id, palari_id, mode, check),
        _finish_stage(work_id, palari_id, mode, finish),
    ]
    if handoff:
        stages.append(_handoff_stage(work_id, palari_id, mode, handoff))

    terminal = finish.get("next_step_type") == "closed"
    combined_blockers = enrich_blockers(
        _dedupe_dicts(
            list(brief.get("blockers", [])) + list(check.get("blockers", []))
        )
    )
    if terminal:
        stages = [_terminal_stage(work_id)]
    payload: dict[str, Any] = {
        "schema_version": "palari.agent_loop.v1",
        "loop_id": _loop_id(work_id, palari_id, mode),
        "created_at": _timestamp(),
        "workspace": workspace.name,
        "would_mutate": False,
        "mode": mode or "execute",
        "status": _loop_status(check, finish, handoff),
        "owner": finish.get("owner", "agent"),
        "agent_may_execute": finish.get("agent_may_execute", False),
        "next_action": finish.get("next_action", {}),
        "automatic_transitions": finish.get("automatic_transitions", []),
        "review_boundary": finish.get("review_boundary", False),
        "human_boundary": finish.get("human_boundary", False),
        "next_step_type": finish.get("next_step_type", check.get("next_step_type", "inspect")),
        "agent": brief.get("agent", {}),
        "work_item": brief.get("work_item", {}),
        "packet_id": brief.get("packet_id", ""),
        "packet_context_hash": brief.get("context_hash", ""),
        "check_id": check.get("check_id", ""),
        "finish_id": finish.get("finish_id", ""),
        "commands": _commands(work_id, palari_id, mode, include_handoff=bool(handoff)),
        "stages": stages,
        "blockers": [] if terminal else combined_blockers,
        "resolution_summary": resolution_summary(combined_blockers, terminal=terminal),
        "missing_requirements": finish.get("missing_requirements", []),
        "completed_requirements": finish.get("completed_requirements", []),
        "next_allowed_commands": _next_allowed_commands(finish, handoff),
        "omitted_context": [
            {
                "kind": "detailed_payloads",
                "reason": "Agent loop v1 summarizes brief, check, finish, and handoff. Run the stage commands for full payloads.",
            }
        ],
    }
    if handoff:
        payload["handoff_id"] = handoff.get("handoff_id", "")
        payload["handoff_types"] = handoff.get("handoff_types", [])
        payload["human_action_boundary"] = handoff.get("human_action_boundary", {})
    return payload


def _terminal_stage(work_id: str) -> dict[str, Any]:
    return {
        "name": "terminal",
        "command": f"palari detail {work_id} --json",
        "status": "closed",
        "ok": True,
        "message": "Work is terminal; inspect its immutable records when needed.",
    }


def _brief_stage(
    work_id: str,
    palari_id: str,
    mode: str,
    brief: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": "brief",
        "command": f"palari agent brief {work_id} --as {palari_id} --mode {mode} --json",
        "status": brief.get("status", "blocked"),
        "ok": brief.get("status") == "ready",
        "message": _brief_message(brief),
    }


def _check_stage(
    work_id: str,
    palari_id: str,
    mode: str,
    check: dict[str, Any],
) -> dict[str, Any]:
    failed = [
        item.get("code", "")
        for item in check.get("checks", [])
        if item.get("required") and item.get("status") == "fail"
    ]
    return {
        "name": "check",
        "command": f"palari agent check {work_id} --as {palari_id} --mode {mode} --json",
        "status": "pass" if check.get("ok") else "fail",
        "ok": bool(check.get("ok")),
        "message": "Packet contract is satisfied." if check.get("ok") else "Required checks are still failing.",
        "failed_required_checks": failed,
    }


def _finish_stage(
    work_id: str,
    palari_id: str,
    mode: str,
    finish: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": "finish",
        "command": f"palari agent finish {work_id} --as {palari_id} --mode {mode} --json",
        "status": finish.get("status", "blocked"),
        "ok": bool(finish.get("can_finish")),
        "handoff_ready": bool(finish.get("handoff_ready")),
        "message": finish.get("report_guidance", ""),
    }


def _handoff_stage(
    work_id: str,
    palari_id: str,
    mode: str,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": "handoff",
        "command": f"palari agent handoff {work_id} --as {palari_id} --mode {mode} --json",
        "status": "available" if handoff.get("handoff_available") else "not-available",
        "ok": bool(handoff.get("handoff_available")),
        "message": "Human handoff context is available."
        if handoff.get("handoff_available")
        else "No human handoff context is available.",
        "handoff_types": handoff.get("handoff_types", []),
    }


def _brief_message(brief: dict[str, Any]) -> str:
    if brief.get("status") == "ready":
        return brief.get("one_sentence_instruction", "Packet is ready.")
    blockers = brief.get("blockers", [])
    if blockers:
        codes = ", ".join(item.get("code", "") for item in blockers if item.get("code"))
        return f"Packet is blocked: {codes}."
    return "Packet is not ready."


def _should_include_handoff(finish: dict[str, Any]) -> bool:
    return bool(finish.get("handoff_guidance"))


def _loop_status(
    check: dict[str, Any],
    finish: dict[str, Any],
    handoff: dict[str, Any] | None,
) -> str:
    if finish.get("next_step_type") == "closed":
        return "closed"
    if finish.get("can_finish"):
        return "ready-to-report"
    if handoff and handoff.get("handoff_available"):
        return "handoff-required"
    if finish.get("status"):
        return str(finish["status"])
    if not check.get("ok"):
        return "check-failed"
    return "inspect"


def _commands(
    work_id: str,
    palari_id: str,
    mode: str,
    *,
    include_handoff: bool,
) -> dict[str, str]:
    commands = {
        "next": f"palari agent next --as {palari_id} --mode {mode} --json",
        "brief": f"palari agent brief {work_id} --as {palari_id} --mode {mode} --json",
        "check": f"palari agent check {work_id} --as {palari_id} --mode {mode} --json",
        "finish": f"palari agent finish {work_id} --as {palari_id} --mode {mode} --json",
        "loop": f"palari agent loop {work_id} --as {palari_id} --mode {mode} --json",
    }
    if include_handoff:
        commands["handoff"] = (
            f"palari agent handoff {work_id} --as {palari_id} --mode {mode} --json"
        )
    return commands


def _next_allowed_commands(
    finish: dict[str, Any],
    handoff: dict[str, Any] | None,
) -> list[str]:
    if handoff and handoff.get("next_allowed_commands"):
        return list(handoff["next_allowed_commands"])
    return list(finish.get("next_allowed_commands", []))


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = (str(item.get("code", "")), str(item.get("message", "")))
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _loop_id(work_id: str, palari_id: str, mode: str) -> str:
    return f"LOOP-{work_id}-{palari_id}-{mode.upper()}-V1"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
