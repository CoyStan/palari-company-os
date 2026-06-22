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
    handoff_ready = not missing_proof and bool(set(blocker_codes) & HANDOFF_BLOCKERS)
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
        "handoff_guidance": _handoff_guidance(check),
        "next_allowed_commands": _next_commands(check),
        "report_guidance": _report_guidance(status),
    }


def _finish_status(
    can_finish: bool,
    handoff_ready: bool,
    missing_proof: list[dict[str, Any]],
    blocker_codes: list[str],
) -> str:
    if can_finish:
        return "ready-to-report"
    if missing_proof:
        return "missing-proof"
    if handoff_ready:
        return "handoff-ready"
    if blocker_codes:
        return "blocked"
    return "not-ready"


def _next_commands(check: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for item in check.get("checks", []):
        if item.get("required") and item.get("status") == "fail" and item.get("code") != "PACKET_READY":
            _append_once(commands, item.get("next_command", ""))
    for command in check.get("next_allowed_commands", []):
        _append_once(commands, command)
    blocker_codes = {blocker.get("code", "") for blocker in check.get("blockers", [])}
    work_id = check.get("work_item", {}).get("id", "WORK-ID")
    palari_id = check.get("agent", {}).get("id", "PALARI-ID")
    handoff_command = f"palari agent handoff {work_id} --as {palari_id} --json"
    review_command = f"palari review guide {work_id} --json"
    review_needed = "RECEIPT_READY_REVIEW" in blocker_codes or "REVIEW_REQUIRED" in blocker_codes
    if review_needed:
        _prioritize(commands, [handoff_command, review_command])
    _append_once(commands, "palari validate --json")
    return commands


def _handoff_guidance(check: dict[str, Any]) -> list[dict[str, str]]:
    guidance: list[dict[str, str]] = []
    blocker_codes = {blocker.get("code", "") for blocker in check.get("blockers", [])}
    work_id = check.get("work_item", {}).get("id", "WORK-ID")
    palari_id = check.get("agent", {}).get("id", "PALARI-ID")
    handoff_command = f"palari agent handoff {work_id} --as {palari_id} --json"
    if "RECEIPT_READY_REVIEW" in blocker_codes or "REVIEW_REQUIRED" in blocker_codes:
        guidance.append(
            {
                "code": "REVIEW_HANDOFF",
                "message": "Use agent handoff to inspect the receipt, evidence, and ready-to-edit review record commands.",
                "command": handoff_command,
                "guide_command": f"palari review guide {work_id} --json",
            }
        )
    if "HUMAN_DECISION_REQUIRED" in blocker_codes:
        guidance.append(
            {
                "code": "DECISION_HANDOFF",
                "message": "Use agent handoff for required human authority and suggested decision update commands.",
                "command": handoff_command,
                "guide_command": _first_decision_command(check),
            }
        )
    return guidance


def _first_decision_command(check: dict[str, Any]) -> str:
    for command in check.get("next_allowed_commands", []):
        if command.startswith("palari decision guide "):
            return command
    work_id = check.get("work_item", {}).get("id", "WORK-ID")
    return f"palari detail {work_id} --json"


def _append_once(commands: list[str], command: str) -> None:
    if command and command not in commands:
        commands.append(command)


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
    if check.get("next_command"):
        payload["next_command"] = check["next_command"]
    return payload


def _report_guidance(status: str) -> str:
    if status == "ready-to-report":
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
