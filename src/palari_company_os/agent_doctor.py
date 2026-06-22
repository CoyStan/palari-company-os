from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_loop import build_agent_loop
from .workspace import Workspace


def build_agent_doctor(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
) -> dict[str, Any]:
    """Explain why a work item is or is not safe for an agent right now."""

    loop = build_agent_loop(workspace, work_id, palari_id, mode)
    diagnosis = _diagnosis(loop)
    return {
        "schema_version": "palari.agent_doctor.v1",
        "doctor_id": _doctor_id(work_id, palari_id, mode),
        "created_at": _timestamp(),
        "workspace": loop.get("workspace", workspace.name),
        "would_mutate": False,
        "mode": mode or "execute",
        "status": diagnosis["status"],
        "agent_safe": diagnosis["agent_safe"],
        "human_handoff_required": diagnosis["human_handoff_required"],
        "summary": diagnosis["summary"],
        "agent": loop.get("agent", {}),
        "work_item": loop.get("work_item", {}),
        "next_step_type": loop.get("next_step_type", "inspect"),
        "loop_command": _loop_command(work_id, palari_id, mode),
        "checks": _doctor_checks(loop),
        "blockers": loop.get("blockers", []),
        "missing_requirements": loop.get("missing_requirements", []),
        "completed_requirements": loop.get("completed_requirements", []),
        "recommended_commands": _recommended_commands(loop),
        "next_allowed_commands": loop.get("next_allowed_commands", []),
        "human_action_boundary": loop.get("human_action_boundary"),
        "omitted_context": [
            {
                "kind": "detailed_payloads",
                "reason": "Agent doctor v1 explains the current loop status. Run agent loop or the stage commands for full payloads.",
            }
        ],
    }


def _diagnosis(loop: dict[str, Any]) -> dict[str, Any]:
    loop_status = str(loop.get("status", "inspect"))
    handoff_required = loop_status == "handoff-required" or bool(
        loop.get("human_action_boundary")
    )
    missing = loop.get("missing_requirements", [])
    blockers = loop.get("blockers", [])
    if loop_status == "ready-to-report":
        return {
            "status": "ready-to-report",
            "agent_safe": True,
            "human_handoff_required": False,
            "summary": "The agent loop checks pass. The agent may report completion with the check result.",
        }
    if handoff_required:
        return {
            "status": "human-handoff-required",
            "agent_safe": False,
            "human_handoff_required": True,
            "summary": "This work is waiting for human review or decision context. Use agent handoff; do not run human-only commands.",
        }
    if missing:
        labels = ", ".join(item.get("code", "") for item in missing if item.get("code"))
        return {
            "status": "missing-proof",
            "agent_safe": True,
            "human_handoff_required": False,
            "summary": f"The packet is usable, but required proof is missing: {labels}.",
        }
    if blockers:
        labels = ", ".join(item.get("code", "") for item in blockers if item.get("code"))
        return {
            "status": "blocked",
            "agent_safe": False,
            "human_handoff_required": False,
            "summary": f"The packet is blocked: {labels}.",
        }
    return {
        "status": loop_status,
        "agent_safe": False,
        "human_handoff_required": False,
        "summary": "Inspect the agent loop before proceeding.",
    }


def _doctor_checks(loop: dict[str, Any]) -> list[dict[str, Any]]:
    stages = {stage.get("name", ""): stage for stage in loop.get("stages", [])}
    checks = [
        _stage_check("PACKET", stages.get("brief")),
        _stage_check("CONTRACT", stages.get("check")),
        _stage_check("FINISH", stages.get("finish")),
    ]
    handoff = stages.get("handoff")
    if handoff:
        checks.append(_stage_check("HANDOFF", handoff))
    boundary = loop.get("human_action_boundary") or {}
    if boundary.get("agent_may_execute") is False:
        checks.append(
            {
                "code": "HUMAN_ACTION_BOUNDARY",
                "status": "warn",
                "message": "Human action commands may be quoted for a supervisor, but the agent must not run them.",
            }
        )
    return checks


def _stage_check(code: str, stage: dict[str, Any] | None) -> dict[str, Any]:
    if stage is None:
        return {
            "code": code,
            "status": "missing",
            "message": f"{code.lower()} stage is not present.",
        }
    status = "pass" if stage.get("ok") else "fail"
    if code == "HANDOFF" and stage.get("ok"):
        status = "warn"
    return {
        "code": code,
        "status": status,
        "message": stage.get("message", ""),
        "command": stage.get("command", ""),
    }


def _recommended_commands(loop: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for stage in loop.get("stages", []):
        if stage.get("name") == "handoff":
            _append_once(commands, stage.get("command", ""))
    for command in loop.get("next_allowed_commands", []):
        _append_once(commands, command)
    command_map = loop.get("commands", {})
    _append_once(commands, command_map.get("loop", ""))
    if not commands:
        _append_once(commands, command_map.get("next", ""))
    return commands


def _append_once(commands: list[str], command: str) -> None:
    if command and command not in commands:
        commands.append(command)


def _loop_command(work_id: str, palari_id: str, mode: str) -> str:
    return f"palari agent loop {work_id} --as {palari_id} --mode {mode} --json"


def _doctor_id(work_id: str, palari_id: str, mode: str) -> str:
    return f"DOCTOR-{_safe_id(work_id)}-{_safe_id(palari_id)}-{_safe_id(mode).upper()}-V1"


def _safe_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
    return cleaned.strip("-") or "UNKNOWN"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
