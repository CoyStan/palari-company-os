from __future__ import annotations

from .models import Human, Integration, WorkItem


SUPPORTED_INTEGRATION_ACTIONS = {"notify", "comment", "create_issue", "update_issue"}

MODE_ACTIONS = {
    "notify": {"notify"},
    "read": set(),
    "write": {"comment", "create_issue", "update_issue"},
    "read_write": {"notify", "comment", "create_issue", "update_issue"},
    "webhook": set(),
    "dry_run": SUPPORTED_INTEGRATION_ACTIONS,
}


def supported_actions_for_mode(mode: str) -> set[str]:
    return set(MODE_ACTIONS.get(mode, set()))


def human_can_decide_integration_plan(
    human: Human,
    work: WorkItem,
    integration: Integration,
) -> bool:
    """Return whether one human may authorize this exact external-action plan."""

    if human.authority_level == "admin":
        return True
    if work.required_approval_capability:
        return work.required_approval_capability in human.approval_capabilities
    if integration.owner_human == human.id and integration.risk_level in {"low", "standard"}:
        return True
    if integration.risk_level in {"high", "critical"}:
        return bool({"policy", "deploy", "security"} & set(human.approval_capabilities))
    return bool(
        {"operations", "product", "policy", "merge", "deploy"}
        & set(human.approval_capabilities)
    )
