from __future__ import annotations

from typing import Any


HANDOFF_BLOCKERS = {
    "RECEIPT_READY_REVIEW",
    "HUMAN_DECISION_REQUIRED",
    "INTEGRATION_BOUNDARY",
}

TERMINAL_BLOCKERS = {"WORK_CLOSED"}
REVIEW_BLOCKERS = {
    "RECEIPT_READY_REVIEW",
    "REVIEW_REQUIRED",
    "REVIEW_MISSING",
    "REVIEW_NOT_READY",
    "REVIEW_STALE",
    "REVIEW_PROOF_STALE",
}
HUMAN_BLOCKERS = {
    "HUMAN_DECISION_REQUIRED",
    "INTEGRATION_BOUNDARY",
    "OPEN_DECISIONS",
    "HUMAN_LACKS_CAPABILITY",
    "HUMAN_MISSING",
}
EXTERNAL_BLOCKERS = {
    "EXTERNAL_STATE_REQUIRED",
    "INTEGRATION_CONFLICT",
    "SOURCE_UNAVAILABLE",
}
AUTOMATIC_BLOCKERS = {
    "ACCEPTANCE_RECORD_MISSING",
    "ACCEPTANCE_PROJECTION_PENDING",
    "TERMINALIZATION_PENDING",
}


def compile_agent_directive(
    check: dict[str, Any],
    *,
    linked_decision_command: str | None = None,
) -> dict[str, Any]:
    """Purely derive the next safe action from one already-built check.

    The compiler has no workspace, filesystem, clock, or mutation access. That
    keeps every aggregate agent view on one deterministic interpretation of
    the current packet/check pair while preserving review and human authority
    as hard stop boundaries.
    """

    failed_required = [
        item
        for item in check.get("checks", [])
        if item.get("required") and item.get("status") == "fail"
    ]
    missing_proof = [
        item for item in failed_required if item.get("code") != "PACKET_READY"
    ]
    blocker_codes = [
        str(blocker.get("code", "")) for blocker in check.get("blockers", [])
    ]
    handoff_guidance = _handoff_guidance(check, linked_decision_command)
    human_approval_ready = (
        "HUMAN_DECISION_REQUIRED" in blocker_codes
        and linked_decision_command is None
        and human_approval_prerequisites_met(check)
    )
    blockers = enrich_blockers(check.get("blockers", []))
    convergence_ready = bool(
        not missing_proof
        and blockers
        and all(
            blocker.get("resolution", {}).get("automatic")
            for blocker in blockers
        )
    )
    handoff_ready = (
        human_approval_ready
        or (not missing_proof and bool(set(blocker_codes) & HANDOFF_BLOCKERS))
    ) and not convergence_ready
    check_next_step_type = str(check.get("next_step_type", "inspect"))
    terminal = check_next_step_type == "closed"
    next_step_type = (
        "automatic-reconciliation"
        if convergence_ready and not terminal
        else check_next_step_type
    )
    can_finish = bool(check.get("ok", False) or terminal)
    status = _finish_status(
        can_finish,
        handoff_ready,
        missing_proof,
        blocker_codes,
        terminal=terminal,
        convergence_ready=convergence_ready,
    )
    next_commands = _next_commands(check)
    summary = resolution_summary(blockers, terminal=terminal)
    next_action = _primary_action(
        status=status,
        terminal=terminal,
        convergence_ready=convergence_ready,
        handoff_guidance=handoff_guidance,
        blockers=blockers,
        next_commands=next_commands,
        resolution=summary,
    )
    return {
        "status": status,
        "owner": next_action["owner"],
        "agent_may_execute": next_action["agent_may_execute"],
        "next_action": next_action,
        "automatic_transitions": [
            {
                "code": str(blocker.get("code") or ""),
                "next_safe_action": str(
                    blocker.get("resolution", {}).get("next_safe_action") or ""
                ),
            }
            for blocker in blockers
            if convergence_ready
            and not terminal
            and blocker.get("resolution", {}).get("automatic")
        ],
        "review_boundary": any(
            code in REVIEW_BLOCKERS or code.startswith("REVIEW_")
            for code in blocker_codes
        ),
        "human_boundary": any(
            code in HUMAN_BLOCKERS or code.startswith(("HUMAN_", "APPROVAL_"))
            for code in blocker_codes
        ),
        "can_finish": can_finish,
        "handoff_ready": handoff_ready,
        "next_step_type": next_step_type,
        "missing_requirements": [_requirement(item) for item in missing_proof],
        "completed_requirements": [
            _requirement(item)
            for item in check.get("checks", [])
            if item.get("required") and item.get("status") == "pass"
        ],
        "blockers": [] if terminal else blockers,
        "resolution_summary": summary,
        "handoff_guidance": handoff_guidance,
        "next_allowed_commands": next_commands,
        "report_guidance": _report_guidance(
            status,
            str(check.get("mode") or "execute"),
        ),
    }


def _primary_action(
    *,
    status: str,
    terminal: bool,
    convergence_ready: bool,
    handoff_guidance: list[dict[str, str]],
    blockers: list[dict[str, Any]],
    next_commands: list[str],
    resolution: dict[str, Any],
) -> dict[str, Any]:
    owner_by_class = {
        "human-authority": "human",
        "independent-review": "reviewer",
        "external-state": "external",
        "automatic-reconciliation": "system",
        "terminal": "none",
    }
    owner = owner_by_class.get(str(resolution.get("primary_class") or ""), "agent")
    command = ""
    message = "Follow the first current safe command."
    if terminal:
        message = "No action is required; inspect the terminal record."
    elif status == "ready-to-report":
        message = "Report completion with the current check result."
    elif convergence_ready:
        command = next(
            (item for item in next_commands if item.startswith("palari agent advance ")),
            next(iter(next_commands), ""),
        )
        message = "Run the deterministic convergence action."
    elif handoff_guidance:
        command = str(handoff_guidance[0].get("command") or "")
        message = str(handoff_guidance[0].get("message") or "Hand off current proof.")
    else:
        command = next(iter(next_commands), "")
        if blockers:
            message = str(
                blockers[0].get("resolution", {}).get("next_safe_action")
                or blockers[0].get("message")
                or message
            )
    return {
        "type": "none" if terminal else status,
        "owner": owner,
        "agent_may_execute": bool(command) and not _is_human_action_command(command),
        "command": command,
        "message": message,
    }


def human_approval_prerequisites_met(check: dict[str, Any]) -> bool:
    """Return whether receipt, evidence, and review proof permits approval."""

    prerequisite_codes = {"RECEIPT_PRESENT", "EVIDENCE_PRESENT", "REVIEW_PRESENT"}
    checks = {item.get("code", ""): item for item in check.get("checks", [])}
    return all(
        checks.get(code, {}).get("required") is True
        and checks.get(code, {}).get("status") == "pass"
        for code in prerequisite_codes
    )


def review_prerequisites_met(check: dict[str, Any]) -> bool:
    """Return whether receipt and evidence are ready for independent review."""

    checks = {item.get("code", ""): item for item in check.get("checks", [])}
    receipt = checks.get("RECEIPT_PRESENT", {})
    evidence = checks.get("EVIDENCE_PRESENT", {})
    return (
        receipt.get("status") == "pass"
        and (not evidence.get("required") or evidence.get("status") == "pass")
    )


def enrich_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach stable ownership semantics without changing blocker authority."""

    enriched: list[dict[str, Any]] = []
    for blocker in blockers:
        payload = dict(blocker)
        payload["resolution"] = classify_resolution(
            str(blocker.get("code") or ""),
            str(blocker.get("next_command") or ""),
            str(blocker.get("message") or ""),
        )
        enriched.append(payload)
    return enriched


def classify_resolution(
    code: str,
    next_command: str = "",
    message: str = "",
) -> dict[str, Any]:
    """Classify who can safely resolve a state; never claim it was resolved."""

    if code == "INTEGRATION_BOUNDARY" and message.startswith(
        "Human decision is recorded"
    ):
        resolution_class, owner, automatic = (
            "automatic-reconciliation",
            "system",
            True,
        )
        action = next_command or (
            "Run deterministic agent advance to terminalize current proof."
        )
    elif code in TERMINAL_BLOCKERS:
        resolution_class, owner, automatic = "terminal", "none", True
        action = "Inspect the terminal record; no remediation is required."
    elif code in REVIEW_BLOCKERS or code.startswith("REVIEW_"):
        resolution_class, owner, automatic = "independent-review", "reviewer", False
        action = next_command or "Route the exact proof to an independent reviewer."
    elif code in HUMAN_BLOCKERS or code.startswith(("HUMAN_", "APPROVAL_")):
        resolution_class, owner, automatic = "human-authority", "human", False
        action = next_command or "Present the exact current decision to a qualified human."
    elif code in EXTERNAL_BLOCKERS or code.startswith(("EXTERNAL_", "PROVIDER_")):
        resolution_class, owner, automatic = "external-state", "external", False
        action = next_command or "Wait for or repair the declared external state."
    elif code in AUTOMATIC_BLOCKERS or code.startswith(("EVIDENCE_", "RECEIPT_")):
        resolution_class, owner, automatic = (
            "automatic-reconciliation",
            "system",
            True,
        )
        action = next_command or "Run deterministic agent reconciliation."
    else:
        resolution_class, owner, automatic = "agent-action", "agent", False
        action = next_command or "Follow the packet's next safe agent action."
    return {
        "class": resolution_class,
        "owner": owner,
        "automatic": automatic,
        "next_safe_action": action,
    }


def resolution_summary(
    blockers: list[dict[str, Any]],
    *,
    terminal: bool = False,
) -> dict[str, Any]:
    if terminal:
        return {
            "state": "terminal",
            "primary_class": "terminal",
            "human_attention_required": False,
            "counts": {"terminal": 1},
        }
    counts: dict[str, int] = {}
    for blocker in blockers:
        resolution = blocker.get("resolution") or classify_resolution(
            str(blocker.get("code") or "")
        )
        key = str(resolution["class"])
        counts[key] = counts.get(key, 0) + 1
    priority = (
        "human-authority",
        "independent-review",
        "external-state",
        "agent-action",
        "automatic-reconciliation",
    )
    primary = next((item for item in priority if counts.get(item)), "none")
    return {
        "state": "waiting" if counts else "clear",
        "primary_class": primary,
        "human_attention_required": bool(counts.get("human-authority")),
        "counts": counts,
    }


def _finish_status(
    can_finish: bool,
    handoff_ready: bool,
    missing_proof: list[dict[str, Any]],
    blocker_codes: list[str],
    *,
    terminal: bool = False,
    convergence_ready: bool = False,
) -> str:
    if terminal:
        return "closed"
    if convergence_ready:
        return "converge-ready"
    if can_finish:
        return "ready-to-report"
    if handoff_ready:
        return "handoff-ready"
    if missing_proof:
        return "missing-proof"
    if blocker_codes:
        return "blocked"
    return "not-ready"


def _next_commands(check: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for item in check.get("checks", []):
        if (
            item.get("required")
            and item.get("status") == "fail"
            and item.get("code") not in {"PACKET_READY", "HUMAN_DECISION_PRESENT"}
        ):
            _append_once(commands, str(item.get("next_command", "")))
    for command in check.get("next_allowed_commands", []):
        if not _is_human_action_command(command):
            _append_once(commands, command)
    blocker_codes = {blocker.get("code", "") for blocker in check.get("blockers", [])}
    work_id = check.get("work_item", {}).get("id", "WORK-ID")
    palari_id = check.get("agent", {}).get("id", "PALARI-ID")
    handoff_command = f"palari agent handoff {work_id} --as {palari_id} --json"
    review_command = f"palari review guide {work_id} --json"
    review_needed = (
        "RECEIPT_READY_REVIEW" in blocker_codes or "REVIEW_REQUIRED" in blocker_codes
    ) and review_prerequisites_met(check)
    if review_needed:
        _prioritize(commands, [handoff_command, review_command])
    automatic_reconciliation = bool(blocker_codes & AUTOMATIC_BLOCKERS) or any(
        blocker.get("code") == "INTEGRATION_BOUNDARY"
        and str(blocker.get("message") or "").startswith(
            "Human decision is recorded"
        )
        for blocker in check.get("blockers", [])
    )
    if automatic_reconciliation:
        _prioritize(
            commands,
            [f"palari agent advance {work_id} --as {palari_id} --json"],
        )
    _append_once(commands, "palari validate --json")
    return commands


def _handoff_guidance(
    check: dict[str, Any],
    linked_decision_command: str | None = None,
) -> list[dict[str, str]]:
    guidance: list[dict[str, str]] = []
    blocker_codes = {blocker.get("code", "") for blocker in check.get("blockers", [])}
    work_id = check.get("work_item", {}).get("id", "WORK-ID")
    palari_id = check.get("agent", {}).get("id", "PALARI-ID")
    handoff_command = f"palari agent handoff {work_id} --as {palari_id} --json"
    if (
        "RECEIPT_READY_REVIEW" in blocker_codes or "REVIEW_REQUIRED" in blocker_codes
    ) and review_prerequisites_met(check):
        guidance.append(
            {
                "code": "REVIEW_HANDOFF",
                "message": "Use agent handoff to inspect the receipt, evidence, and ready-to-edit review record commands.",
                "command": handoff_command,
                "guide_command": f"palari review guide {work_id} --json",
            }
        )
    if "HUMAN_DECISION_REQUIRED" in blocker_codes:
        decision_command = linked_decision_command or _first_decision_command(check)
        if linked_decision_command or decision_command.startswith("palari decision guide "):
            code = "DECISION_HANDOFF"
            message = "Use agent handoff for required human authority and suggested decision update commands."
        elif human_approval_prerequisites_met(check):
            code = "HUMAN_APPROVAL_HANDOFF"
            message = (
                "Use agent handoff. It exposes one exact Approval Pack action when "
                "the workspace has valid journal continuity and otherwise stays "
                "blocked without manufacturing human authority."
            )
        else:
            return guidance
        guidance.append(
            {
                "code": code,
                "message": message,
                "command": handoff_command,
                "guide_command": decision_command,
            }
        )
    return guidance


def _first_decision_command(check: dict[str, Any]) -> str:
    for command in check.get("next_allowed_commands", []):
        if command.startswith("palari decision guide "):
            return command
    work_id = check.get("work_item", {}).get("id", "WORK-ID")
    return f"palari detail {work_id} --json"


def _is_human_action_command(command: str) -> bool:
    return command.startswith(
        (
            "palari human-decision record ",
            "palari work accept ",
            "palari review record ",
            "palari decision update ",
        )
    )


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
    if check.get("next_command") and check.get("code") != "HUMAN_DECISION_PRESENT":
        payload["next_command"] = check["next_command"]
    return payload


def _report_guidance(status: str, mode: str) -> str:
    if status == "closed":
        return "Work is already terminal. Report the recorded outcome; no remediation is required."
    if status == "converge-ready":
        return (
            "Human authority is already current. Run deterministic agent advance "
            "to derive acceptance and terminalize the exact proof."
        )
    if status == "ready-to-report":
        if (mode or "execute") == "review":
            return (
                "Review packet checks pass. Report a review recommendation with evidence, "
                "but do not record a human review or claim the work item is complete unless "
                "explicitly authorized."
            )
        return "All required checks pass. Report completion and include the check result."
    if status == "handoff-ready":
        return "Do not continue execution. Hand off the completed proof to a human reviewer or approver."
    if status == "missing-proof":
        return "Do not claim completion yet. Record or refresh the missing trust records first."
    if status == "blocked":
        return "Do not claim completion. Resolve the packet blockers or ask a human to decide."
    return "Do not claim completion yet. Inspect the check result and next allowed commands."


def _append_once(commands: list[str], command: str) -> None:
    if command and command not in commands:
        commands.append(command)
