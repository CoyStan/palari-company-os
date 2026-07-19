from __future__ import annotations

from typing import Any, Iterable

from .approval_packs import build_approval_inbox
from .errors import WorkspaceError
from .governance_journal import JournalVerificationContext
from .store import load_store
from .workspace import Workspace


def approval_inbox(
    workspace: Workspace,
    *,
    selected_work_ids: Iterable[str] = (),
    journal_context: JournalVerificationContext | None = None,
) -> dict[str, Any]:
    """Compile the product-facing Approval Inbox from committed workspace truth."""

    selected = tuple(selected_work_ids)
    retired_ids = {
        work.id
        for work in workspace.work_items
        if work.terminal_disposition
    }
    explicitly_retired = sorted(set(selected) & retired_ids)
    if explicitly_retired:
        raise WorkspaceError(
            f"retired work is audit-only and cannot enter the Approval Inbox: "
            f"{', '.join(explicitly_retired)}; inspect it with palari detail"
        )
    effective_selection = selected
    all_retired = False
    if retired_ids and not selected:
        effective_selection = tuple(
            work.id for work in workspace.work_items if work.id not in retired_ids
        )
        all_retired = not effective_selection

    store = load_store(workspace.path)
    payload = build_approval_inbox(
        workspace,
        store.data,
        selected_work_ids=effective_selection,
        journal_context=journal_context,
    )
    if all_retired:
        _empty_retired_inbox(payload)
    return payload


def _empty_retired_inbox(payload: dict[str, Any]) -> None:
    """Preserve the inbox schema when a workspace contains only retired work."""

    payload["individual_items"] = []
    payload["packs"] = []
    payload["approval_commands"] = []
    counts = payload.get("counts") or {}
    for key in ("items", "packs", "eligible", "blocked", "stale", "non_batchable"):
        counts[key] = 0
    payload["counts"] = counts
    primary = payload.get("primary_action") or {}
    primary.update(
        {
            "available": False,
            "count": 0,
            "commands": [],
            "next_safe_action": "No governed human decision is waiting.",
        }
    )
    payload["primary_action"] = primary
