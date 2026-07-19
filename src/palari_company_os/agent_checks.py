from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_file_changes import inspect_file_changes
from .agent_packets import build_agent_brief
from .agent_runtime import claim_check, read_claim
from .workspace import Workspace


def build_agent_check(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    *,
    changed_paths: list[str] | None = None,
    git_diff: bool = False,
    cwd: Path | str | None = None,
) -> dict[str, Any]:
    packet = build_agent_brief(
        workspace,
        work_id,
        palari_id,
        mode,
    )
    checks = _packet_boundary_checks(packet)
    if packet.get("status") == "ready":
        checks.append(_claim_owned_check(workspace, work_id, palari_id, mode, packet))
    claim = read_claim(workspace.path, work_id)
    file_changes = inspect_file_changes(
        packet,
        changed_paths=changed_paths,
        git_diff=git_diff,
        cwd=cwd,
        git_baseline=(claim or {}).get("git_baseline"),
    )
    if file_changes is not None:
        checks.extend(_file_change_checks(file_changes))
    if "completion_contract" in packet:
        checks.extend(_completion_checks(packet))

    ok = all(check["status"] != "fail" for check in checks)
    return {
        "schema_version": "palari.agent_check.v1",
        "check_id": _check_id(work_id, palari_id, mode),
        "created_at": _timestamp(),
        "ok": ok,
        "workspace": packet.get("workspace", workspace.name),
        "mode": mode or "execute",
        "agent": packet.get("agent", {}),
        "work_item": packet.get("work_item", {}),
        "packet_id": packet.get("packet_id", ""),
        "packet_context_hash": packet.get("context_hash", ""),
        "packet_status": packet.get("status", "blocked"),
        "documentation_state": packet.get("documentation_state", {}),
        "recommended_docs": packet.get("recommended_docs", []),
        "next_step_type": packet.get("state", {}).get("next_step_type", "inspect"),
        "blockers": packet.get("blockers", []),
        "checks": checks,
        "file_changes": file_changes,
        "next_allowed_commands": _next_commands(packet, checks, ok),
    }


def _packet_boundary_checks(packet: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = packet.get("blockers", [])
    blocker_codes = {blocker.get("code", "") for blocker in blockers}
    if packet.get("status") != "ready":
        return [
            _check(
                "PACKET_READY",
                "fail",
                "The agent packet is blocked; resolve packet blockers before claiming completion.",
                required=True,
                next_command=_first_command(packet),
            )
        ]

    return [
        _check("PACKET_READY", "pass", "The agent packet is ready.", required=True),
        _check(
            "PALARI_ALLOWED",
            "fail" if "PALARI_NOT_ASSIGNED" in blocker_codes else "pass",
            "The acting Palari is assigned to this work item or allowed by its workbench.",
            required=True,
        ),
        _check(
            "DEPENDENCIES_CLEAR",
            "fail" if "DEPENDENCY_NOT_TERMINAL" in blocker_codes else "pass",
            "Dependencies are terminal for this packet.",
            required=True,
        ),
        _check(
            "SOURCES_ALLOWED",
            "fail" if {"SOURCE_MISSING", "SOURCE_NOT_ALLOWED"} & blocker_codes else "pass",
            "Declared sources are present and allowed for the acting Palari.",
            required=True,
        ),
        _external_write_check(packet),
        _check(
            "VALIDATE_WORKSPACE",
            "pass",
            "Workspace validation passed before this check was built.",
            required=True,
            next_command="palari validate --json",
        ),
    ]


def _completion_checks(packet: dict[str, Any]) -> list[dict[str, Any]]:
    contract = packet.get("completion_contract", {})
    proof = packet.get("proof_state", {})
    safety = packet.get("state", {}).get("safety", {})
    return [
        _proof_check(
            "RECEIPT_PRESENT",
            bool(contract.get("requires_receipt", False)),
            proof.get("receipt"),
            safety.get("receipt_state"),
            pass_states={"ready"},
            missing_message="A receipt is required before claiming this work is done.",
            next_command=_agent_advance_command(packet),
        ),
        _proof_check(
            "EVIDENCE_PRESENT",
            bool(contract.get("requires_evidence", False)),
            proof.get("evidence"),
            safety.get("evidence_state"),
            pass_states={"passed"},
            missing_message="Evidence is required before claiming this work is done.",
            next_command=_agent_advance_command(packet),
        ),
        _proof_check(
            "REVIEW_PRESENT",
            bool(contract.get("requires_review", False)),
            proof.get("review"),
            safety.get("review_state"),
            pass_states={"accept-ready"},
            missing_message="Review is required before claiming this work is done.",
            next_command=_agent_advance_command(packet),
        ),
        _human_decision_check(packet),
    ]


def _claim_owned_check(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str,
    packet: dict[str, Any],
) -> dict[str, Any]:
    result = claim_check(workspace.path, work_id, palari_id, mode or "execute", packet.get("context_hash", ""))
    return _check(
        "CLAIM_OWNED",
        result["status"],
        result["message"],
        required=True,
        next_command=result.get("next_command", ""),
    )


def _file_change_checks(file_changes: dict[str, Any]) -> list[dict[str, Any]]:
    outside = file_changes.get("outside_write_boundary", [])
    missing_outputs = file_changes.get("missing_required_outputs", [])
    unrecorded = file_changes.get("unrecorded_changed_files", [])
    checks = [
        _check(
            "FILE_CHANGES_WITHIN_WRITE_BOUNDARY",
            "fail" if outside else "pass",
            (
                "Observed file changes stay inside allowed write paths."
                if not outside
                else "Observed file changes outside allowed write paths: "
                f"{', '.join(outside)}."
            ),
            required=True,
        ),
        _check(
            "REQUIRED_OUTPUT_EXISTS",
            "fail" if missing_outputs else "pass",
            (
                "Required output targets exist or are not file-backed in this checkout."
                if not missing_outputs
                else "Required output targets are missing: "
                f"{', '.join(missing_outputs)}."
            ),
            required=True,
        ),
        _check(
            "FILE_CHANGES_RECORDED",
            "fail" if unrecorded else "pass",
            (
                "Observed file changes match attempt or receipt records."
                if not unrecorded
                else "Observed file changes are not recorded in the current attempt or receipt: "
                f"{', '.join(unrecorded)}."
            ),
            required=True,
        ),
    ]
    return checks


def _proof_check(
    code: str,
    required: bool,
    record: Any,
    state: str | None,
    *,
    pass_states: set[str],
    missing_message: str,
    next_command: str = "",
) -> dict[str, Any]:
    label = {
        "RECEIPT_PRESENT": "Receipt",
        "EVIDENCE_PRESENT": "Evidence",
        "REVIEW_PRESENT": "Review",
    }.get(code, code.replace("_", " ").title())
    if not required:
        return _check(
            code,
            "pass",
            f"{label} is not required for this work item.",
            required=False,
        )
    if record is not None and (not state or state in pass_states):
        return _check(code, "pass", f"{label} is present.", required=True)
    detail = f" Current state: {state}." if state else ""
    return _check(
        code,
        "fail",
        f"{missing_message}{detail}",
        required=True,
        next_command=next_command,
    )


def _human_decision_check(packet: dict[str, Any]) -> dict[str, Any]:
    contract = packet.get("completion_contract", {})
    if not contract.get("requires_human_decision", False):
        return _check(
            "HUMAN_DECISION_PRESENT",
            "pass",
            "Human decision is not required for this work item.",
            required=False,
        )
    proof = packet.get("proof_state", {})
    safety = packet.get("state", {}).get("safety", {})
    decision = proof.get("human_decision")
    if decision is not None and _approval_progress_met(safety.get("approval_progress", "")):
        return _check(
            "HUMAN_DECISION_PRESENT",
            "pass",
            "Human decision quorum is recorded.",
            required=True,
        )
    waiting_on = _human_decision_prerequisites(packet)
    if waiting_on:
        return _check(
            "HUMAN_DECISION_PRESENT",
            "fail",
            "Human decision waits for required proof before approval: "
            f"{', '.join(waiting_on)}.",
            required=True,
            next_command=_agent_advance_command(packet),
        )
    return _check(
        "HUMAN_DECISION_PRESENT",
        "fail",
        f"Human decision quorum is incomplete ({safety.get('approval_progress', 'unknown')}).",
        required=True,
        next_command=_agent_advance_command(packet),
    )


def _external_write_check(packet: dict[str, Any]) -> dict[str, Any]:
    contract = packet.get("completion_contract", {})
    integration = packet.get("proof_state", {}).get("integration", {})
    plans = integration.get("plans", [])
    outbox = integration.get("outbox", [])
    if not contract.get("external_writes_allowed", False):
        return _check(
            "NO_UNAPPROVED_EXTERNAL_WRITE",
            "pass",
            "No external write action is allowed for this work item.",
            required=True,
        )
    approved = any(plan.get("status") == "approved" for plan in plans)
    queued = any(item.get("status") == "queued" for item in outbox)
    if approved or queued:
        return _check(
            "NO_UNAPPROVED_EXTERNAL_WRITE",
            "pass",
            "External write boundary has an approved plan or queued outbox item.",
            required=True,
        )
    return _check(
        "NO_UNAPPROVED_EXTERNAL_WRITE",
        "fail",
        "External write action is allowed but no approved plan or queued outbox item is present.",
        required=True,
    )


def _next_commands(packet: dict[str, Any], checks: list[dict[str, Any]], ok: bool) -> list[str]:
    if ok:
        return _agent_check_commands(packet.get("next_allowed_commands", []), packet)
    commands: list[str] = []
    for check in checks:
        command = check.get("next_command", "")
        if (
            check.get("required")
            and check.get("status") == "fail"
            and command
        ):
            _append_agent_check_command(commands, command, packet)
    for command in (
        list(packet.get("next_allowed_commands", []))
        + packet_commands_from_checks(packet)
    ):
        _append_agent_check_command(commands, command, packet)
    _prioritize_review_handoff(commands, packet)
    return commands


def _agent_check_commands(commands: list[str], packet: dict[str, Any]) -> list[str]:
    normalized: list[str] = []
    for command in commands:
        _append_agent_check_command(normalized, command, packet)
    return normalized


def _append_agent_check_command(
    commands: list[str], command: str, packet: dict[str, Any]
) -> None:
    if not command:
        return
    normalized = _normalize_agent_check_command(command, packet)
    if normalized not in commands:
        commands.append(normalized)


def _normalize_agent_check_command(command: str, packet: dict[str, Any]) -> str:
    return (
        _agent_advance_command(packet)
        if _is_direct_proof_mutation(command)
        else command
    )


def _is_direct_proof_mutation(command: str) -> bool:
    stripped = command.strip()
    return any(
        stripped.startswith(prefix)
        for prefix in (
            "palari agent done ",
            "palari attempt closeout ",
            "palari attempt record ",
            "palari attempt update ",
            "palari evidence record ",
            "palari evidence update ",
            "palari human-decision record ",
            "palari receipt record ",
            "palari receipt update ",
        )
    )


def packet_commands_from_checks(packet: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    work_id = packet.get("work_item", {}).get("id", "WORK-ID")
    if packet.get("status") != "ready":
        commands.extend(packet.get("next_allowed_commands", []))
    else:
        commands.append(f"palari detail {work_id} --json")
        commands.append("palari validate --json")
    return commands


def _first_command(packet: dict[str, Any]) -> str:
    commands = packet.get("next_allowed_commands", [])
    return _normalize_agent_check_command(commands[0], packet) if commands else ""


def _prioritize_review_handoff(commands: list[str], packet: dict[str, Any]) -> None:
    blocker_codes = {blocker.get("code", "") for blocker in packet.get("blockers", [])}
    if not ({"REVIEW_REQUIRED", "RECEIPT_READY_REVIEW"} & blocker_codes):
        return
    work_id = packet.get("work_item", {}).get("id", "WORK-ID")
    palari_id = packet.get("agent", {}).get("id", "PALARI-ID")
    prioritized = [
        f"palari agent handoff {work_id} --as {palari_id} --json",
        f"palari review guide {work_id} --json",
    ]
    for command in reversed(prioritized):
        if command in commands:
            commands.remove(command)
        commands.insert(0, command)


def _agent_advance_command(packet: dict[str, Any]) -> str:
    work_id = packet.get("work_item", {}).get("id", "WORK-ID")
    palari_id = packet.get("agent", {}).get("id", "PALARI-ID")
    return f"palari agent advance {work_id} --as {palari_id} --json"


def _human_decision_prerequisites(packet: dict[str, Any]) -> list[str]:
    contract = packet.get("completion_contract", {})
    proof = packet.get("proof_state", {})
    safety = packet.get("state", {}).get("safety", {})
    waiting_on: list[str] = []
    if contract.get("requires_receipt", False) and not _proof_present(
        proof.get("receipt"),
        safety.get("receipt_state"),
        {"ready"},
    ):
        waiting_on.append("receipt")
    if contract.get("requires_evidence", False) and not _proof_present(
        proof.get("evidence"),
        safety.get("evidence_state"),
        {"passed"},
    ):
        waiting_on.append("evidence")
    if contract.get("requires_review", False) and not _proof_present(
        proof.get("review"),
        safety.get("review_state"),
        {"accept-ready"},
    ):
        waiting_on.append("review")
    return waiting_on


def _proof_present(record: Any, state: str | None, pass_states: set[str]) -> bool:
    return record is not None and (not state or state in pass_states)


def _approval_progress_met(progress: str) -> bool:
    try:
        current, required = progress.split("/", 1)
        return int(current) >= int(required)
    except (ValueError, TypeError):
        return False


def _check(
    code: str,
    status: str,
    message: str,
    *,
    required: bool,
    next_command: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "status": status,
        "required": required,
        "message": message,
    }
    if next_command:
        payload["next_command"] = next_command
    return payload


def _check_id(work_id: str, palari_id: str, mode: str) -> str:
    return f"CHECK-{_safe_id(work_id)}-{_safe_id(palari_id)}-{_safe_id(mode).upper()}-V1"


def _safe_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
    return cleaned.strip("-") or "UNKNOWN"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
