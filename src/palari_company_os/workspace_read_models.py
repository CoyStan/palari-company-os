from __future__ import annotations

from typing import Any, Iterable

from .approval_packs import build_approval_inbox
from .errors import WorkspaceError
from .store import load_store
from .workspace import Workspace


def approval_inbox(
    workspace: Workspace,
    *,
    selected_work_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Compile the product-facing Approval Inbox from committed workspace truth."""

    store = load_store(workspace.path)
    return build_approval_inbox(
        workspace,
        store.data,
        selected_work_ids=selected_work_ids,
    )


def approval_detail(workspace: Workspace, work_id: str) -> dict[str, Any]:
    """Return one concise item-level approval view without weakening queue availability."""

    try:
        inbox = approval_inbox(workspace, selected_work_ids=(work_id,))
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
