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


def approval_detail(
    workspace: Workspace,
    work_id: str,
    *,
    journal_context: JournalVerificationContext | None = None,
) -> dict[str, Any]:
    """Return one concise item-level approval view without weakening queue availability."""

    try:
        inbox = approval_inbox(
            workspace,
            selected_work_ids=(work_id,),
            journal_context=journal_context,
        )
    except WorkspaceError as exc:
        return {
            "available": False,
            "work_item_id": work_id,
            "reason": str(exc),
            "next_safe_action": "Repair or checkpoint journal continuity, then refresh detail.",
        }
    item = next(
        (candidate for candidate in inbox["individual_items"] if candidate["id"] == work_id),
        None,
    )
    pack = inbox["packs"][0] if inbox["packs"] else None
    return {
        "available": item is not None,
        "work_item_id": work_id,
        "pack_id": pack["pack_id"] if pack else "",
        "pack_digest": pack["pack_digest"] if pack else "",
        "item": item,
        "next_safe_action": (
            item["next_safe_action"] if item else "Refresh the Approval Inbox."
        ),
    }
