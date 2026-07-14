from __future__ import annotations

import json
import os
import tempfile
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from .path_policy import resolve_workspace_path, validate_workspace_path
from .validation import COLLECTION_FILE_KEYS, validate_raw_contract
from .workspace import CURRENT_SCHEMA_VERSION, Workspace, WorkspaceError


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
class _CollectionFileSnapshot:
    collection: str
    relative_path: str
    path: Path
    records: list[dict[str, Any]]
    loaded_hash: str


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


def migrate_store(
    store: WorkspaceStore,
    *,
    write: bool = False,
) -> tuple[dict[str, Any], list[str], Workspace | None]:
    """Migrate a loaded single-file or split workspace without losing placement.

    Ordinary authoring remains single-file only. Migration is the deliberately
    narrow exception: all split records are validated together, transformed,
    and written back to their original files before the root schema version is
    advanced. A partial write therefore leaves the v1 root in a retryable,
    fail-closed state.
    """

    source, snapshots = _migration_source(store)
    migrated, changes = migrate_data(source)
    if not write:
        return migrated, changes, None
    if not snapshots:
        workspace = write_store(store.with_data(migrated))
        return migrated, changes, workspace
    workspace = _write_split_migration(store, migrated, snapshots)
    return migrated, changes, workspace


def _acquire_workspace_lock(data_path: Path) -> Path:
    lock_path = data_path.parent / ".palari" / "locks" / f"{data_path.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
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
        handle.write(f"pid={os.getpid()}\n")
    return lock_path


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
    if pid is not None and not _pid_is_alive(pid):
        return True
    return (time.time() - lock_stat.st_mtime) > STALE_WORKSPACE_LOCK_SECONDS


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


def _migration_source(
    store: WorkspaceStore,
) -> tuple[dict[str, Any], list[_CollectionFileSnapshot]]:
    if not has_collection_files(store.data):
        return deepcopy(store.data), []

    validate_raw_contract(store.data)
    collection_files = store.data.get("collection_files")
    if not isinstance(collection_files, dict):
        raise WorkspaceError("workspace.collection_files must be an object")

    source = deepcopy(store.data)
    snapshots: list[_CollectionFileSnapshot] = []
    seen_paths: set[Path] = set()
    for collection, relative_paths in collection_files.items():
        if collection not in COLLECTION_FILE_KEYS:
            raise WorkspaceError(
                f"workspace.collection_files has unknown collection: {collection}"
            )
        if not isinstance(relative_paths, list) or not all(
            isinstance(item, str) for item in relative_paths
        ):
            raise WorkspaceError(
                f"workspace.collection_files.{collection} must be a list of paths"
            )
        records = source.setdefault(collection, [])
        if not isinstance(records, list):
            raise WorkspaceError(f"{collection} must be a list of objects")
        for relative_path in relative_paths:
            try:
                normalized = validate_workspace_path(relative_path)
                include_path = resolve_workspace_path(
                    store.data_path.parent,
                    normalized,
                    require_exists=True,
                )
            except ValueError as exc:
                raise WorkspaceError(
                    f"workspace.collection_files.{collection} path is unsafe: "
                    f"{relative_path}: {exc}"
                ) from exc
            if include_path in seen_paths:
                raise WorkspaceError(
                    f"workspace.collection_files includes the same file more than once: "
                    f"{relative_path}"
                )
            seen_paths.add(include_path)
            try:
                text = include_path.read_text(encoding="utf-8")
                included = json.loads(text)
            except OSError as exc:
                raise WorkspaceError(
                    f"cannot read workspace.collection_files.{collection} "
                    f"{relative_path}: {exc}"
                ) from exc
            except json.JSONDecodeError as exc:
                raise WorkspaceError(
                    f"invalid JSON in workspace.collection_files.{collection} "
                    f"{relative_path}: {exc}"
                ) from exc
            if not isinstance(included, list) or not all(
                isinstance(item, dict) for item in included
            ):
                raise WorkspaceError(
                    f"workspace.collection_files.{collection} {relative_path} "
                    "must contain a list of objects"
                )
            copied = deepcopy(included)
            records.extend(copied)
            snapshots.append(
                _CollectionFileSnapshot(
                    collection=collection,
                    relative_path=normalized,
                    path=include_path,
                    records=copied,
                    loaded_hash=_hash_text(text),
                )
            )
    return source, snapshots


def _write_split_migration(
    store: WorkspaceStore,
    migrated: dict[str, Any],
    snapshots: list[_CollectionFileSnapshot],
) -> Workspace:
    consolidated = deepcopy(migrated)
    consolidated["collection_files"] = {}
    validate_data(store.data_path, consolidated)

    migrated_by_collection: dict[str, dict[str, dict[str, Any]]] = {}
    included_ids: dict[str, set[str]] = {}
    for collection in COLLECTION_FILE_KEYS:
        records = migrated.get(collection, [])
        if not isinstance(records, list):
            raise WorkspaceError(f"{collection} must be a list of objects")
        migrated_by_collection[collection] = {
            str(record.get("id") or ""): record
            for record in records
            if isinstance(record, dict)
        }
        included_ids[collection] = set()

    file_payloads: list[tuple[_CollectionFileSnapshot, list[dict[str, Any]]]] = []
    for snapshot in snapshots:
        by_id = migrated_by_collection[snapshot.collection]
        output: list[dict[str, Any]] = []
        for record in snapshot.records:
            record_id = str(record.get("id") or "")
            migrated_record = by_id.get(record_id)
            if migrated_record is None:
                raise WorkspaceError(
                    f"migration lost {snapshot.collection} record {record_id or '(missing id)'}"
                )
            output.append(deepcopy(migrated_record))
            included_ids[snapshot.collection].add(record_id)
        file_payloads.append((snapshot, output))

    root_payload = deepcopy(migrated)
    root_payload["collection_files"] = deepcopy(store.data["collection_files"])
    for collection in COLLECTION_FILE_KEYS:
        root_payload[collection] = [
            deepcopy(record)
            for record in migrated.get(collection, [])
            if str(record.get("id") or "") not in included_ids[collection]
        ]

    lock_path = _acquire_workspace_lock(store.data_path)
    temp_paths: list[Path] = []
    try:
        _assert_workspace_file_unchanged(store)
        for snapshot, _ in file_payloads:
            try:
                current_path = resolve_workspace_path(
                    store.data_path.parent,
                    snapshot.relative_path,
                    require_exists=True,
                )
                if current_path != snapshot.path:
                    raise ValueError("resolved target changed")
                current_text = current_path.read_text(encoding="utf-8")
            except (OSError, ValueError) as exc:
                raise WorkspaceError(
                    f"collection file changed since it was loaded: "
                    f"{snapshot.relative_path}; retry command"
                ) from exc
            if _hash_text(current_text) != snapshot.loaded_hash:
                raise WorkspaceError(
                    f"collection file changed since it was loaded: "
                    f"{snapshot.relative_path}; retry command"
                )

        pending: list[tuple[Path, Path]] = []
        for snapshot, records in file_payloads:
            temp_path = _write_json_temp(snapshot.path, records)
            temp_paths.append(temp_path)
            pending.append((temp_path, snapshot.path))
        root_temp = _write_json_temp(store.data_path, root_payload)
        temp_paths.append(root_temp)
        for temp_path, target in pending:
            os.replace(temp_path, target)
            temp_paths.remove(temp_path)
        os.replace(root_temp, store.data_path)
        temp_paths.remove(root_temp)
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)
    return Workspace.load(store.data_path)


def _write_json_temp(target: Path, payload: object) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=target.parent,
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
        return Path(handle.name)


def migrate_data(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    migrated = deepcopy(data)
    changes: list[str] = []
    source_version = migrated.get("schema_version")
    if source_version is not None and type(source_version) is not int:
        raise WorkspaceError(
            f"cannot migrate schema_version {source_version!r}; "
            f"supported target is {CURRENT_SCHEMA_VERSION}"
        )
    if source_version not in {None, 0, 1, CURRENT_SCHEMA_VERSION}:
        raise WorkspaceError(
            f"cannot migrate schema_version {source_version!r}; "
            f"supported target is {CURRENT_SCHEMA_VERSION}"
        )
    _ensure_collections(migrated, changes)
    if source_version == CURRENT_SCHEMA_VERSION:
        changes.append(
            f"Workspace already uses schema_version: {CURRENT_SCHEMA_VERSION}."
        )
        return migrated, changes
    if source_version is None:
        changes.append("Added legacy schema_version: 1 before migration.")
    elif source_version == 0:
        changes.append("Upgraded schema_version from 0 to 1 before migration.")
    _migrate_v1_to_v2(migrated, changes)
    migrated["schema_version"] = CURRENT_SCHEMA_VERSION
    changes.append("Upgraded schema_version from 1 to 2.")
    return migrated, changes


def _migrate_v1_to_v2(data: dict[str, Any], changes: list[str]) -> None:
    """Invalidate legacy trust records that cannot prove exact artifact binding."""

    stale_review_ids: set[str] = set()
    stale_work_ids: set[str] = set()
    from .governance_binding import review_proof_hash

    for review in data.get("review_verdicts", []):
        if not isinstance(review, dict):
            continue
        if review.get("binding_version"):
            migrated_proof_hash = review_proof_hash(review)
            if review.get("proof_hash") != migrated_proof_hash:
                review["proof_hash"] = migrated_proof_hash
                changes.append(
                    f"Upgraded aggregate proof hash for bound review {review.get('id', '')}."
                )
        if review.get("verdict") != "accept-ready" or review.get("binding_version"):
            continue
        review["verdict"] = "blocked"
        risks = review.setdefault("residual_risks", [])
        note = "Migrated from schema v1: fresh exact-bound review required."
        if isinstance(risks, list) and note not in risks:
            risks.append(note)
        stale_review_ids.add(str(review.get("id") or ""))
        stale_work_ids.add(str(review.get("work_item_id") or ""))
    if stale_review_ids:
        changes.append(
            f"Blocked {len(stale_review_ids)} legacy accept-ready review(s) without exact binding."
        )

    reviews_by_id = {
        str(review.get("id") or ""): review
        for review in data.get("review_verdicts", [])
        if isinstance(review, dict)
    }
    blocked_decision_ids: set[str] = set()
    decision_timestamps: dict[tuple[str, str, str], set[str]] = {}
    for index, decision in enumerate(data.get("human_decisions", [])):
        if not isinstance(decision, dict):
            continue
        scope = (
            str(decision.get("work_item_id") or ""),
            str(decision.get("human_id") or ""),
            str(decision.get("reviewed_head") or ""),
        )
        timestamp = _unique_migration_timestamp(
            str(decision.get("timestamp") or ""),
            index,
            decision_timestamps.setdefault(scope, set()),
        )
        if timestamp != decision.get("timestamp"):
            decision["timestamp"] = timestamp
            changes.append(
                f"Normalized deterministic timestamp for human decision "
                f"{decision.get('id', index)}."
            )
        accepts = decision.get("decision") in {"accepted", "approved"} or decision.get(
            "status"
        ) in {"accepted", "approved"}
        if not accepts:
            continue
        review_reference = str(decision.get("review_reference") or "")
        review = reviews_by_id.get(review_reference)
        exact_match = bool(
            review
            and review.get("verdict") == "accept-ready"
            and review.get("binding_version")
            and decision.get("work_item_id") == review.get("work_item_id")
            and decision.get("reviewed_head") == review.get("reviewed_head")
            and decision.get("evidence_reference") == review.get("evidence_reference")
        )
        if exact_match:
            continue
        decision["decision"] = "blocked"
        decision["status"] = "blocked"
        decision["quorum_status"] = "not-met"
        blocked_decision_ids.add(str(decision.get("id") or ""))
        stale_work_ids.add(str(decision.get("work_item_id") or ""))
    if blocked_decision_ids:
        changes.append(
            f"Blocked {len(blocked_decision_ids)} human acceptance decision(s) tied to legacy reviews."
        )

    decisions_by_id = {
        str(decision.get("id") or ""): decision
        for decision in data.get("human_decisions", [])
        if isinstance(decision, dict)
    }
    latest_decision_by_scope: dict[tuple[str, str, str], dict[str, Any]] = {}
    for decision in decisions_by_id.values():
        scope = (
            str(decision.get("work_item_id") or ""),
            str(decision.get("human_id") or ""),
            str(decision.get("reviewed_head") or ""),
        )
        previous = latest_decision_by_scope.get(scope)
        if previous is None or _migration_record_order(decision) > _migration_record_order(
            previous
        ):
            latest_decision_by_scope[scope] = decision
    latest_review_by_work: dict[str, dict[str, Any]] = {}
    for review in reviews_by_id.values():
        work_id = str(review.get("work_item_id") or "")
        previous = latest_review_by_work.get(work_id)
        if previous is None or _migration_record_order(review) > _migration_record_order(
            previous
        ):
            latest_review_by_work[work_id] = review
    revoked_acceptance_ids: set[str] = set()
    for acceptance in data.get("acceptance_records", []):
        if not isinstance(acceptance, dict) or acceptance.get("status", "accepted") != "accepted":
            continue
        review = reviews_by_id.get(str(acceptance.get("review_reference") or ""))
        decision = decisions_by_id.get(str(acceptance.get("decision_id") or ""))
        exact_match = bool(
            review
            and decision
            and review.get("verdict") == "accept-ready"
            and review.get("binding_version")
            and decision.get("decision") in {"accepted", "approved"}
            and decision.get("status") in {"accepted", "approved"}
            and acceptance.get("work_item_id") == review.get("work_item_id")
            and acceptance.get("work_item_id") == decision.get("work_item_id")
            and acceptance.get("human_id") == decision.get("human_id")
            and acceptance.get("reviewed_head") == review.get("reviewed_head")
            and acceptance.get("reviewed_head") == decision.get("reviewed_head")
            and acceptance.get("evidence_reference") == review.get("evidence_reference")
            and acceptance.get("evidence_reference") == decision.get("evidence_reference")
            and acceptance.get("review_reference") == decision.get("review_reference")
            and acceptance.get("receipt_hash") == review.get("receipt_hash")
            and latest_decision_by_scope.get(
                (
                    str(decision.get("work_item_id") or ""),
                    str(decision.get("human_id") or ""),
                    str(decision.get("reviewed_head") or ""),
                )
            )
            is decision
            and latest_review_by_work.get(str(review.get("work_item_id") or "")) is review
        )
        if exact_match:
            continue
        acceptance["status"] = "revoked"
        acceptance["quorum_status"] = "not-met"
        revoked_acceptance_ids.add(str(acceptance.get("id") or ""))
        stale_work_ids.add(str(acceptance.get("work_item_id") or ""))
    if revoked_acceptance_ids:
        changes.append(
            f"Revoked {len(revoked_acceptance_ids)} acceptance record(s) tied to legacy reviews."
        )

    accepted_work_ids = {
        str(acceptance.get("work_item_id") or "")
        for acceptance in data.get("acceptance_records", [])
        if isinstance(acceptance, dict) and acceptance.get("status", "accepted") == "accepted"
    }
    reopened = 0
    for work in data.get("work_items", []):
        if not isinstance(work, dict):
            continue
        work_id = str(work.get("work_item_id") or work.get("id") or "")
        if work.get("status") not in {"completed", "closed", "done"}:
            continue
        if work.get("risk", "R1") in {"R1", "R2"} and work.get(
            "required_approval_count", 1
        ) == 0:
            continue
        if work_id not in stale_work_ids and work_id in accepted_work_ids:
            continue
        work["status"] = "in-review"
        reopened += 1
    if reopened:
        changes.append(
            f"Reopened {reopened} terminal work item(s) whose legacy review was invalidated."
        )


def _unique_migration_timestamp(value: str, index: int, used: set[str]) -> str:
    parsed: datetime | None = None
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None and parsed.utcoffset() is None:
            parsed = None
    if parsed is None:
        parsed = datetime.fromisoformat(
            f"1970-01-01T00:00:00.{index + 1:06d}+00:00"
        )
    else:
        parsed = parsed.astimezone(timezone.utc)
    candidate = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    while candidate in used:
        parsed += timedelta(microseconds=1)
        candidate = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    used.add(candidate)
    return candidate


def _migration_record_order(record: dict[str, Any]) -> tuple[datetime, str]:
    value = str(record.get("timestamp") or "")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        timestamp = datetime.min.replace(tzinfo=timezone.utc)
    if timestamp.utcoffset() is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return (timestamp, str(record.get("id") or ""))


def _ensure_collections(data: dict[str, Any], changes: list[str]) -> None:
    for key in (
        "goals",
        "humans",
        "palaris",
        "sources",
        "capabilities",
        "authority_profiles",
        "work_items",
        "proposals",
        "attempts",
        "evidence_runs",
        "review_verdicts",
        "human_decisions",
        "acceptance_records",
        "receipts",
        "decisions",
        "outcomes",
        "workbenches",
        "playbook_sources",
        "integrations",
        "integration_plans",
        "integration_outbox",
    ):
        if key not in data:
            data[key] = []
            changes.append(f"Added missing collection: {key}.")
