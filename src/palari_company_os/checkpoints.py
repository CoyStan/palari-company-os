from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable

from .errors import WorkspaceError
from .governance_journal import (
    JournalError,
    MutationMetadata,
    committed_journal_states,
    recover_pending,
    utc_timestamp,
    verify_journal,
    workspace_digest,
)
from .store import load_store, validate_data, write_store


CHECKPOINTS_SCHEMA_VERSION = "palari.checkpoints.v1"
RESTORATION_SCHEMA_VERSION = "palari.checkpoint-restoration.v1"
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def list_checkpoints(workspace_path: str) -> dict[str, Any]:
    store = load_store(workspace_path)
    report = verify_journal(store.data_path, store.data)
    if not report.get("chain_valid"):
        raise WorkspaceError("checkpoint listing requires a valid governance journal")
    try:
        states = committed_journal_states(store.data_path)
    except JournalError as exc:
        raise WorkspaceError(f"checkpoint listing failed [{exc.code}]: {exc.message}") from exc
    checkpoints = [
        {key: value for key, value in item.items() if key != "projection"}
        for item in states
    ]
    return {
        "schema_version": CHECKPOINTS_SCHEMA_VERSION,
        "workspace_file": str(store.data_path),
        "journal_head_digest": report.get("head_record_digest"),
        "current_checkpoint_digest": workspace_digest(store.data),
        "count": len(checkpoints),
        "checkpoints": checkpoints,
        "semantics": {
            "content_addressed": True,
            "append_only_history": True,
            "external_effects_undoable": False,
        },
    }


def restore_checkpoint(
    workspace_path: str,
    checkpoint_digest: str,
    *,
    actor: str,
    reason: str,
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if not _DIGEST_RE.fullmatch(checkpoint_digest):
        raise WorkspaceError("checkpoint digest must be a full sha256 digest")
    if not reason.strip():
        raise WorkspaceError("checkpoint restoration requires a non-empty reason")
    store = load_store(workspace_path)
    interrupted = verify_journal(store.data_path, store.data)
    if interrupted.get("pending"):
        recover_pending(
            store.data_path,
            store.data,
            action=(
                "abort"
                if interrupted["pending"].get("workspace_position") == "before"
                else "auto"
            ),
            reason="idempotent retry of interrupted checkpoint restoration",
        )
        store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    if workspace.human(actor) is None:
        raise WorkspaceError(
            f"checkpoint restoration actor must be a declared human: {actor}"
        )
    report = verify_journal(store.data_path, store.data)
    if not report.get("chain_valid") or report.get("pending"):
        raise WorkspaceError(
            "checkpoint restoration requires a valid journal with no pending transaction"
        )
    if report.get("replay_workspace_digest") != workspace_digest(store.data):
        raise WorkspaceError(
            "checkpoint restoration blocked because workspace diverges from the journal"
        )
    try:
        states = committed_journal_states(store.data_path)
    except JournalError as exc:
        raise WorkspaceError(f"checkpoint restoration failed [{exc.code}]: {exc.message}") from exc
    target_entry = next(
        (
            (index, item)
            for index, item in enumerate(states)
            if item["checkpoint_digest"] == checkpoint_digest
        ),
        None,
    )
    if target_entry is None:
        raise WorkspaceError("checkpoint digest is not present in the verified journal")
    target_index, target = target_entry
    projection = deepcopy(target["projection"])
    validate_data(store.data_path, projection)
    external_effects = _external_effects_since(
        projection,
        states[target_index + 1 :],
    )
    if external_effects:
        raise WorkspaceError(
            "checkpoint restoration blocked because external effects after the target "
            "cannot be undone locally: "
            + ", ".join(external_effects)
            + "; record any external compensation separately and create a new "
            "governed checkpoint instead"
        )
    if workspace_digest(store.data) == checkpoint_digest:
        return {
            "schema_version": RESTORATION_SCHEMA_VERSION,
            "status": "already-at-checkpoint",
            "idempotent": True,
            "checkpoint_digest": checkpoint_digest,
            "restoration_transition_digest": None,
            "restoration_class": "reversible-local",
            "external_effects_not_undone": [],
        }
    metadata = MutationMetadata(
        command=f"history --restore {checkpoint_digest}",
        actor=actor,
        action="restored-checkpoint",
        timestamp=utc_timestamp(),
        objects=(
            {
                "type": "workspace-checkpoint",
                "collection": "workspace",
                "id": checkpoint_digest,
            },
        ),
        reason=reason,
    )
    restored = write_store(
        store.with_data(projection),
        metadata=metadata,
        event_kind="restoration",
        crash_hook=crash_hook,
    )
    final_store = load_store(restored.path)
    final_report = verify_journal(final_store.data_path, final_store.data)
    if not final_report.get("chain_valid") or final_report.get("pending"):
        raise WorkspaceError("checkpoint restoration did not produce a committed journal state")
    return {
        "schema_version": RESTORATION_SCHEMA_VERSION,
        "status": "restored",
        "idempotent": False,
        "checkpoint_digest": checkpoint_digest,
        "current_checkpoint_digest": workspace_digest(final_store.data),
        "restoration_transition_digest": final_report.get("head_record_digest"),
        "restoration_class": "reversible-local",
        "external_effects_not_undone": [],
        "history_preserved": True,
        "message": "Local governed projection restored without rewriting prior history.",
    }


def _external_effects_after(
    target: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    effects: set[str] = set()
    target_receipts = {
        item.get("id"): set(item.get("external_writes", []))
        for item in target.get("receipts", [])
        if isinstance(item, dict)
    }
    for receipt in current.get("receipts", []):
        if not isinstance(receipt, dict):
            continue
        receipt_id = receipt.get("id")
        prior_writes = target_receipts.get(receipt_id, set())
        for value in set(receipt.get("external_writes", [])) - prior_writes:
            effects.add(f"receipt:{receipt.get('id', '')}:{value}")
    target_outbox = {
        item.get("id"): item.get("status")
        for item in target.get("integration_outbox", [])
        if isinstance(item, dict)
    }
    for item in current.get("integration_outbox", []):
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status in {"sent", "failed"} and target_outbox.get(item.get("id")) != status:
            effects.add(f"outbox:{item.get('id', '')}:{status}")
    return sorted(effects)


def _external_effects_since(
    target: dict[str, Any],
    later_states: list[dict[str, Any]],
) -> list[str]:
    """Return every external effect visible in any committed later projection."""

    effects: set[str] = set()
    for state in later_states:
        projection = state.get("projection")
        if isinstance(projection, dict):
            effects.update(_external_effects_after(target, projection))
    return sorted(effects)
