from __future__ import annotations


PROVIDER_ACTIONS = {
    "slack": {"notify"},
    "github": {"notify", "comment", "create_issue"},
    "jira": {"notify", "comment", "create_issue", "update_issue"},
    "email": {"notify"},
}
