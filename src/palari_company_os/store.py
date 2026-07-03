from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .workspace import CURRENT_SCHEMA_VERSION, Workspace, WorkspaceError


@dataclass(frozen=True)
class WorkspaceStore:
    data_path: Path
    data: dict[str, Any]
    loaded_hash: str | None = None

    def with_data(self, data: dict[str, Any]) -> "WorkspaceStore":
        return WorkspaceStore(
            data_path=self.data_path,
            data=data,
            loaded_hash=self.loaded_hash,
        )


def workspace_file_path(path: Path | str) -> Path:
    workspace_path = Path(path).expanduser().resolve()
    if workspace_path.is_dir():
        return workspace_path / "workspace.json"
    return workspace_path


def load_store(path: Path | str) -> WorkspaceStore:
    data_path = workspace_file_path(path)
    if not data_path.exists():
        raise WorkspaceError(f"workspace file not found: {data_path}")
    try:
        text = data_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"invalid workspace JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkspaceError("workspace root must be a JSON object")
    return WorkspaceStore(data_path=data_path, data=data, loaded_hash=_hash_text(text))


def validate_data(data_path: Path, data: dict[str, Any]) -> Workspace:
    return Workspace.from_raw(data, data_path.parent)


def write_store(store: WorkspaceStore) -> Workspace:
    if has_collection_files(store.data):
        raise WorkspaceError(
            "authoring writes are not supported for split workspaces yet; "
            "edit collection files directly or use a single-file workspace"
        )
    lock_path = _acquire_workspace_lock(store.data_path)
    try:
        _assert_workspace_file_unchanged(store)
        workspace = validate_data(store.data_path, store.data)
        text = json.dumps(store.data, indent=2, sort_keys=False) + "\n"
        store.data_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=store.data_path.parent,
            delete=False,
        ) as handle:
            handle.write(text)
            temp_name = handle.name
        os.replace(temp_name, store.data_path)
        return workspace
    finally:
        lock_path.unlink(missing_ok=True)


def has_collection_files(data: dict[str, Any]) -> bool:
    value = data.get("collection_files")
    return isinstance(value, dict) and any(value.values())


def _acquire_workspace_lock(data_path: Path) -> Path:
    lock_path = data_path.parent / ".palari" / "locks" / f"{data_path.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise WorkspaceError("workspace write is already in progress; retry shortly") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"pid={os.getpid()}\n")
    return lock_path


def _assert_workspace_file_unchanged(store: WorkspaceStore) -> None:
    if store.loaded_hash is None:
        if store.data_path.exists():
            raise WorkspaceError("workspace file appeared before write; retry command")
        return
    if not store.data_path.exists():
        raise WorkspaceError("workspace file was removed before write; retry command")
    current_hash = _hash_text(store.data_path.read_text(encoding="utf-8"))
    if current_hash != store.loaded_hash:
        raise WorkspaceError("workspace changed since it was loaded; retry command")


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def migrate_data(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    migrated = dict(data)
    changes: list[str] = []
    if "schema_version" not in migrated:
        migrated["schema_version"] = CURRENT_SCHEMA_VERSION
        changes.append("Added schema_version: 1.")
    elif migrated["schema_version"] == CURRENT_SCHEMA_VERSION:
        changes.append("Workspace already uses schema_version: 1.")
    elif migrated["schema_version"] == 0:
        migrated["schema_version"] = CURRENT_SCHEMA_VERSION
        changes.append("Upgraded schema_version from 0 to 1.")
    else:
        raise WorkspaceError(
            f"cannot migrate schema_version {migrated['schema_version']!r}; "
            f"supported target is {CURRENT_SCHEMA_VERSION}"
        )
    _ensure_collections(migrated, changes)
    return migrated, changes


def _ensure_collections(data: dict[str, Any], changes: list[str]) -> None:
    for key in (
        "goals",
        "humans",
        "palaris",
        "sources",
        "work_items",
        "attempts",
        "evidence_runs",
        "review_verdicts",
        "human_decisions",
        "receipts",
        "decisions",
        "outcomes",
    ):
        if key not in data:
            data[key] = []
            changes.append(f"Added missing collection: {key}.")
