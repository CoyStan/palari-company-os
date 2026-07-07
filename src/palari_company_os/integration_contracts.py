from __future__ import annotations


PROVIDER_ACTIONS = {
    "slack": {"notify"},
    "github": {"notify", "comment", "create_issue"},
    "jira": {"notify", "comment", "create_issue", "update_issue"},
    "email": {"notify"},
    "linear": {"notify", "comment", "create_issue", "update_issue"},
}

MODE_ACTIONS = {
    "notify": {"notify"},
    "read": set(),
    "write": {"comment", "create_issue", "update_issue"},
    "read_write": {"notify", "comment", "create_issue", "update_issue"},
    "webhook": set(),
}


def supported_actions_for_mode(mode: str, provider: str) -> set[str]:
    if mode == "dry_run":
        return set(PROVIDER_ACTIONS.get(provider, set()))
    return set(MODE_ACTIONS.get(mode, set()))
