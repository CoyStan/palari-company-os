from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator

from .workspace import Workspace, WorkspaceError


STALE_WORKSPACE_LOCK_SECONDS = 30.0
WORKSPACE_LOCK_ERROR = "workspace write is already in progress; retry shortly"


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


@dataclass(frozen=True)
class _WorkspaceLock:
    path: Path
    token: str


def workspace_file_path(path: Path | str) -> Path:
    workspace_path = Path(path).expanduser().resolve()
    if workspace_path.is_dir():
        return workspace_path / "workspace.json"
    return workspace_path


@contextmanager
def workspace_write_lock(path: Path | str) -> Iterator[Path]:
    data_path = workspace_file_path(path)
    lock = _acquire_workspace_lock(data_path)
    try:
        yield data_path
    finally:
        _release_workspace_lock(lock)


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


def write_store(
    store: WorkspaceStore,
    *,
    metadata: Any | None = None,
    event_kind: str = "mutation",
    crash_hook: Any | None = None,
) -> Workspace:
    if has_collection_files(store.data):
        raise WorkspaceError(
            "authoring writes are not supported for split workspaces yet; "
            "edit collection files directly or use a single-file workspace"
        )
    lock = _acquire_workspace_lock(store.data_path)
    try:
        _assert_workspace_file_unchanged(store)
        before_data = (
            _load_current_raw(store.data_path)
            if store.loaded_hash is not None
            else None
        )
        if before_data is not None:
            _assert_retired_work_immutable(before_data, store.data)
        workspace = validate_data(store.data_path, store.data)
        text = json.dumps(store.data, indent=2, sort_keys=False) + "\n"
        from .governance_journal import (
            JournalError,
            MutationMetadata,
            transact,
            utc_timestamp,
        )

        if metadata is None:
            from .mutation_context import current_mutation_identity

            command, actor, action = current_mutation_identity()
            metadata = MutationMetadata(
                command=command,
                actor=actor,
                action=action,
                timestamp=utc_timestamp(),
            )
        try:
            if store.loaded_hash is None:
                transact(
                    store.data_path,
                    before_data=None,
                    after_data=store.data,
                    metadata=metadata,
                    apply=lambda: _atomic_replace_text(store.data_path, text),
                    event_kind="checkpoint",
                    coverage="complete",
                    crash_hook=crash_hook,
                )
            else:
                transact(
                    store.data_path,
                    before_data=before_data,
                    after_data=store.data,
                    metadata=metadata,
                    apply=lambda: _atomic_replace_text(store.data_path, text),
                    event_kind=event_kind,
                    crash_hook=crash_hook,
                )
        except JournalError as exc:
            next_action = f"; next: {exc.next_action}" if exc.next_action else ""
            raise WorkspaceError(
                f"governance journal blocked workspace write [{exc.code}]: {exc.message}{next_action}"
            ) from exc
        return workspace
    finally:
        _release_workspace_lock(lock)


def has_collection_files(data: dict[str, Any]) -> bool:
    value = data.get("collection_files")
    return isinstance(value, dict) and any(value.values())


_WORK_LINKED_COLLECTIONS = {
    "proposals": "linked_work",
    "attempts": "work_item_id",
    "evidence_runs": "work_item_id",
    "review_verdicts": "work_item_id",
    "human_decisions": "work_item_id",
    "acceptance_records": "work_item_id",
    "receipts": "work_item_id",
    "decisions": "linked_work",
    "outcomes": "work_item_id",
    "integration_plans": "work_item_id",
    "integration_outbox": "work_item_id",
}


def _assert_retired_work_immutable(
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    """Make retirement a temporal boundary while preserving prior audit proof."""

    before_work = {
        str(record.get("id") or ""): record
        for record in before.get("work_items", [])
        if isinstance(record, dict)
    }
    after_work = {
        str(record.get("id") or ""): record
        for record in after.get("work_items", [])
        if isinstance(record, dict)
    }
    retired = {
        work_id: record
        for work_id, record in before_work.items()
        if record.get("status") in {"superseded", "abandoned"}
    }
    for work_id, record in retired.items():
        candidate = after_work.get(work_id)
        if candidate is None or not _same_json_value(record, candidate):
            raise WorkspaceError(
                f"retired work {work_id} is immutable; create successor work instead"
            )
    retiring: dict[str, dict[str, Any]] = {}
    for work_id, candidate in after_work.items():
        if candidate.get("status") not in {"superseded", "abandoned"}:
            continue
        record = before_work.get(work_id)
        if record is None or work_id in retired:
            continue
        if record.get("status") in {"completed", "closed", "done"}:
            raise WorkspaceError(
                f"successfully completed work {work_id} cannot be relabeled as "
                f"{candidate.get('status')}"
            )
        if not _same_json_value(
            _without_retirement_fields(record),
            _without_retirement_fields(candidate),
        ):
            raise WorkspaceError(
                f"retiring work {work_id} may change only status, terminal_reason, "
                "and successor_work_item_id"
            )
        retiring[work_id] = candidate
    newly_retired = {
        work_id: candidate
        for work_id, candidate in after_work.items()
        if work_id not in before_work
        and candidate.get("status") in {"superseded", "abandoned"}
    }
    protected = {**retired, **retiring, **newly_retired}
    if not protected:
        return
    retired_ids = set(protected)
    for collection, field in _WORK_LINKED_COLLECTIONS.items():
        before_records = _linked_records_by_work(
            before, collection, field, retired_ids
        )
        after_records = _linked_records_by_work(
            after, collection, field, retired_ids
        )
        for work_id in protected:
            if not _same_json_value(
                before_records.get(work_id, []),
                after_records.get(work_id, []),
            ):
                raise WorkspaceError(
                    f"retired work {work_id} is audit-only; {collection} cannot change"
                )


def _without_retirement_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"status", "terminal_reason", "successor_work_item_id"}
    }


def _linked_records_by_work(
    data: dict[str, Any],
    collection: str,
    field: str,
    work_ids: set[str],
) -> dict[str, list[dict[str, Any]]]:
    records = data.get(collection, [])
    if not isinstance(records, list):
        return {}
    linked = {work_id: [] for work_id in work_ids}
    for record in records:
        if not isinstance(record, dict):
            continue
        work_id = record.get(field)
        if work_id in linked:
            linked[work_id].append(record)
    return linked


def _same_json_value(left: Any, right: Any) -> bool:
    return json.dumps(
        left,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) == json.dumps(
        right,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _acquire_workspace_lock(data_path: Path) -> _WorkspaceLock:
    lock_path = _safe_workspace_lock_path(data_path)
    token = uuid.uuid4().hex
    try:
        descriptor = _create_workspace_lock(lock_path)
    except FileExistsError as exc:
        if not _workspace_lock_is_stale(lock_path):
            raise WorkspaceError(WORKSPACE_LOCK_ERROR) from exc
        _remove_workspace_lock(lock_path)
        try:
            descriptor = _create_workspace_lock(lock_path)
        except FileExistsError as retry_exc:
            raise WorkspaceError(WORKSPACE_LOCK_ERROR) from retry_exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"pid={os.getpid()}\ntoken={token}\n")
        handle.flush()
        os.fsync(handle.fileno())
    return _WorkspaceLock(path=lock_path, token=token)


def _create_workspace_lock(lock_path: Path) -> int:
    return os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)


def _remove_workspace_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise WorkspaceError(WORKSPACE_LOCK_ERROR) from exc


def _workspace_lock_is_stale(lock_path: Path) -> bool:
    try:
        lock_stat = lock_path.stat()
    except FileNotFoundError:
        return True

    pid = _workspace_lock_pid(lock_path)
    if pid is not None:
        return not _pid_is_alive(pid)
    return (time.time() - lock_stat.st_mtime) > STALE_WORKSPACE_LOCK_SECONDS


def _release_workspace_lock(lock: _WorkspaceLock) -> None:
    try:
        text = lock.path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except OSError as exc:
        raise WorkspaceError(WORKSPACE_LOCK_ERROR) from exc
    token = next(
        (line.removeprefix("token=").strip() for line in text.splitlines() if line.startswith("token=")),
        "",
    )
    if token != lock.token:
        raise WorkspaceError("workspace lock ownership changed during write; inspect before retry")
    _remove_workspace_lock(lock.path)


def _safe_workspace_lock_path(data_path: Path) -> Path:
    root = data_path.parent.resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkspaceError(WORKSPACE_LOCK_ERROR) from exc
    current = root
    for component in (".palari", "locks"):
        current = current / component
        try:
            if current.is_symlink():
                raise WorkspaceError(
                    f"workspace control path must not contain symlinks: {current.relative_to(root)}"
                )
            current.mkdir(mode=0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise WorkspaceError(WORKSPACE_LOCK_ERROR) from exc
        if current.is_symlink() or not current.is_dir():
            raise WorkspaceError(
                f"workspace control path must be a real directory: {current.relative_to(root)}"
            )
    return current / f"{data_path.name}.lock"


def _load_current_raw(data_path: Path) -> dict[str, Any]:
    try:
        value = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceError(f"workspace cannot be journaled safely: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkspaceError("workspace cannot be journaled safely: root is not an object")
    return value


def _atomic_replace_text(data_path: Path, text: str) -> None:
    data_path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=data_path.parent,
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, data_path)
        temp_name = ""
        directory = os.open(data_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def _workspace_lock_pid(lock_path: Path) -> int | None:
    try:
        text = lock_path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if not line.startswith("pid="):
            continue
        try:
            return int(line.removeprefix("pid=").strip())
        except ValueError:
            return None
    return None


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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
