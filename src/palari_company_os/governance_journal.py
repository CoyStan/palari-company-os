"""Deterministic, replayable governance journal primitives.

`transact` deliberately does not create a second writer lock. Its caller must
hold the workspace store lock, and its `apply` callback must durably replace the
workspace before returning. The standalone checkpoint wrappers are intended to
be routed through that same serialization boundary by the CLI integration.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable


SCHEMA_VERSION = "palari.governance-journal.v1"
VERIFY_SCHEMA_VERSION = "palari.governance-journal.verify.v1"
JOURNAL_RELATIVE_PATH = ".palari/governance-journal.v1.jsonl"
HASH_PREFIX = "sha256:"
IJSON_INTEGER_MAX = 9_007_199_254_740_991

EVENT_KINDS = {"checkpoint", "mutation", "restoration"}
COVERAGE_MODES = {"complete", "from-checkpoint", "continuous", "continuity-break"}
RECORD_TYPES = {"prepare", "commit", "abort"}

PREPARE_FIELDS = {
    "schema_version",
    "sequence",
    "record_type",
    "transaction_id",
    "previous_record_digest",
    "event_kind",
    "coverage",
    "expected_before_workspace_digest",
    "before_workspace_digest",
    "after_workspace_digest",
    "logical_changes",
    "after_projection",
    "metadata",
    "record_digest",
}
COMMIT_FIELDS = {
    "schema_version",
    "sequence",
    "record_type",
    "transaction_id",
    "previous_record_digest",
    "prepared_record_digest",
    "after_workspace_digest",
    "record_digest",
}
ABORT_FIELDS = {
    "schema_version",
    "sequence",
    "record_type",
    "transaction_id",
    "previous_record_digest",
    "prepared_record_digest",
    "before_workspace_digest",
    "reason",
    "record_digest",
}
METADATA_FIELDS = {"command", "actor", "action", "timestamp", "objects", "reason"}
OBJECT_FIELDS = {"type", "collection", "id"}
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_MISSING = object()

CrashHook = Callable[[str], None]


class JournalError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: str = "$",
        next_action: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.next_action = next_action

    def as_dict(self, *, severity: str = "error") -> dict[str, str]:
        return {
            "code": self.code,
            "severity": severity,
            "path": self.path,
            "message": self.message,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class MutationMetadata:
    command: str
    actor: str
    action: str
    timestamp: str
    objects: tuple[dict[str, str], ...] = ()
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        metadata = {
            "command": self.command,
            "actor": self.actor,
            "action": self.action,
            "timestamp": self.timestamp,
            "objects": sorted(
                (dict(item) for item in self.objects),
                key=lambda item: (
                    str(item.get("type", "")),
                    str(item.get("collection", "")),
                    str(item.get("id", "")),
                ),
            ),
            "reason": self.reason,
        }
        _validate_metadata(metadata, "$.metadata")
        return metadata


@dataclass
class _JournalState:
    records: list[dict[str, Any]]
    replay_projection: dict[str, Any] | None
    replay_digest: str | None
    head_digest: str | None
    pending: dict[str, Any] | None
    committed: int
    aborted: int
    coverage: str
    continuity_breaks: list[int]


@dataclass
class JournalVerificationContext:
    """Reuse one exact journal verification inside a bounded read operation.

    The context is intentionally in-memory and caller-owned.  Reuse is allowed
    only while the workspace and journal bytes retain the exact SHA-256
    fingerprint observed by the prior verification.
    """

    _data_path: Path | None = None
    _fingerprint: tuple[str, str] | None = None
    _report: dict[str, Any] | None = None

    def verify(self, workspace_path: Path | str) -> dict[str, Any]:
        data_path = _workspace_data_path(workspace_path)
        fingerprint = _verification_fingerprint(data_path)
        if (
            self._data_path == data_path
            and self._fingerprint == fingerprint
            and self._report is not None
        ):
            return deepcopy(self._report)

        before = fingerprint
        report = verify_workspace_journal(workspace_path)
        after = _verification_fingerprint(data_path)
        if before != after:
            report = _operator_report(
                _error_report(
                    data_path,
                    JournalError(
                        "JOURNAL_CHANGED_DURING_VERIFICATION",
                        "workspace or journal bytes changed during verification",
                        next_action="Retry the read against one stable exact state.",
                    ),
                )
            )
        self._data_path = data_path
        self._fingerprint = after
        self._report = deepcopy(report)
        return report


def journal_file_path(data_path: Path | str) -> Path:
    workspace_file = Path(data_path).expanduser()
    if not workspace_file.is_absolute():
        workspace_file = (Path.cwd() / workspace_file).resolve(strict=False)
    root = workspace_file.parent.resolve(strict=False)
    return _safe_control_path(root, JOURNAL_RELATIVE_PATH)


def workspace_digest(data: dict[str, Any] | None) -> str | None:
    if data is None:
        return None
    return _stable_hash(data)


def logical_changes(
    before: dict[str, Any] | None,
    after: dict[str, Any],
) -> list[dict[str, Any]]:
    _validate_json_value(after, "$")
    if before is None:
        return []
    _validate_json_value(before, "$")
    changes: list[dict[str, Any]] = []
    _collect_changes(before, after, "", changes)
    return changes


def prepare_record(
    *,
    sequence: int,
    previous_record_digest: str | None,
    event_kind: str,
    coverage: str,
    expected_before_workspace_digest: str | None,
    before_workspace_digest: str | None,
    after_projection: dict[str, Any],
    metadata: MutationMetadata | dict[str, Any],
    before_projection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if event_kind not in EVENT_KINDS:
        raise JournalError("JOURNAL_INVALID_EVENT_KIND", f"unsupported event kind: {event_kind}")
    if coverage not in COVERAGE_MODES:
        raise JournalError("JOURNAL_INVALID_COVERAGE", f"unsupported coverage: {coverage}")
    metadata_dict = metadata.as_dict() if isinstance(metadata, MutationMetadata) else deepcopy(metadata)
    if isinstance(metadata_dict, dict) and isinstance(metadata_dict.get("objects"), list):
        metadata_dict["objects"] = _sorted_metadata_objects(metadata_dict["objects"])
    _validate_metadata(metadata_dict, "$.metadata")
    projection = deepcopy(after_projection)
    after_digest = workspace_digest(projection)
    record = {
        "schema_version": SCHEMA_VERSION,
        "sequence": sequence,
        "record_type": "prepare",
        "transaction_id": "",
        "previous_record_digest": previous_record_digest,
        "event_kind": event_kind,
        "coverage": coverage,
        "expected_before_workspace_digest": expected_before_workspace_digest,
        "before_workspace_digest": before_workspace_digest,
        "after_workspace_digest": after_digest,
        "logical_changes": logical_changes(before_projection, projection),
        "after_projection": projection,
        "metadata": metadata_dict,
        "record_digest": "",
    }
    record["transaction_id"] = _transaction_id(record)
    record["record_digest"] = record_digest(record)
    return record


def commit_record(
    prepared: dict[str, Any],
    *,
    sequence: int,
    previous_record_digest: str,
) -> dict[str, Any]:
    _validate_record_shape(prepared, -1)
    if prepared["record_type"] != "prepare":
        raise JournalError("JOURNAL_COMMIT_WITHOUT_PREPARE", "commit requires a prepare record")
    record = {
        "schema_version": SCHEMA_VERSION,
        "sequence": sequence,
        "record_type": "commit",
        "transaction_id": prepared["transaction_id"],
        "previous_record_digest": previous_record_digest,
        "prepared_record_digest": prepared["record_digest"],
        "after_workspace_digest": prepared["after_workspace_digest"],
        "record_digest": "",
    }
    record["record_digest"] = record_digest(record)
    return record


def abort_record(
    prepared: dict[str, Any],
    *,
    sequence: int,
    previous_record_digest: str,
    reason: str,
) -> dict[str, Any]:
    _validate_record_shape(prepared, -1)
    if prepared["record_type"] != "prepare":
        raise JournalError("JOURNAL_ABORT_WITHOUT_PREPARE", "abort requires a prepare record")
    if not reason.strip():
        raise JournalError("JOURNAL_ABORT_REASON_REQUIRED", "abort reason must not be empty")
    record = {
        "schema_version": SCHEMA_VERSION,
        "sequence": sequence,
        "record_type": "abort",
        "transaction_id": prepared["transaction_id"],
        "previous_record_digest": previous_record_digest,
        "prepared_record_digest": prepared["record_digest"],
        "before_workspace_digest": prepared["before_workspace_digest"],
        "reason": reason,
        "record_digest": "",
    }
    record["record_digest"] = record_digest(record)
    return record


def record_digest(record: dict[str, Any]) -> str:
    payload = {key: value for key, value in record.items() if key != "record_digest"}
    return _stable_hash(payload)


def append_record_fsync(
    data_path: Path | str,
    record: dict[str, Any],
    crash_hook: CrashHook | None = None,
) -> None:
    _validate_record_shape(record, -1)
    if record_digest(record) != record.get("record_digest"):
        raise JournalError(
            "JOURNAL_RECORD_DIGEST_MISMATCH",
            "record content does not match record_digest",
        )
    path = journal_file_path(data_path)
    _ensure_safe_parent(path, Path(data_path).expanduser().resolve(strict=False).parent)
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    existed = path.exists()
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise JournalError(
            "JOURNAL_APPEND_FAILED",
            f"cannot open governance journal safely: {exc}",
            next_action="Inspect the .palari path and retry without bypassing the journal.",
        ) from exc
    payload = _canonical_bytes(record) + b"\n"
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("journal append wrote no bytes")
            view = view[written:]
        _call_hook(crash_hook, f"after_{record['record_type']}_write")
        os.fsync(descriptor)
        _call_hook(crash_hook, f"after_{record['record_type']}_fsync")
        if not existed:
            _fsync_directory(path.parent)
            _call_hook(crash_hook, f"after_{record['record_type']}_directory_fsync")
    except OSError as exc:
        raise JournalError(
            "JOURNAL_APPEND_FAILED",
            f"cannot durably append governance journal record: {exc}",
            next_action="Run history verification and recover the visible pending transaction.",
        ) from exc
    finally:
        os.close(descriptor)


def verify_journal(
    data_path: Path | str,
    current_data: dict[str, Any] | None | object = _MISSING,
) -> dict[str, Any]:
    try:
        path = journal_file_path(data_path)
        if not path.exists():
            return _report_not_enabled(data_path)
        records = _read_records(data_path)
        state = _scan_records(records)
        current = _load_workspace_data(data_path) if current_data is _MISSING else current_data
        if current is not None and not isinstance(current, dict):
            raise JournalError("JOURNAL_WORKSPACE_INVALID", "current workspace must be an object")
        return _state_report(data_path, state, current)
    except JournalError as exc:
        return _error_report(data_path, exc)


def verify_workspace_journal(workspace_path: Path | str) -> dict[str, Any]:
    return _operator_report(verify_journal(_workspace_data_path(workspace_path)))


def committed_journal_states(data_path: Path | str) -> list[dict[str, Any]]:
    """Return verified committed projections as content-addressed checkpoints."""

    records = _read_records(data_path)
    state = _scan_records(records)
    if state.pending is not None:
        raise JournalError(
            "JOURNAL_PENDING_PREPARE",
            "cannot enumerate checkpoints while a transaction is pending",
            next_action="Recover the pending transaction first.",
        )
    prepared: dict[str, dict[str, Any]] = {}
    checkpoints: list[dict[str, Any]] = []
    for record in records:
        if record["record_type"] == "prepare":
            prepared[record["transaction_id"]] = record
            continue
        if record["record_type"] == "abort":
            prepared.pop(record["transaction_id"], None)
            continue
        source = prepared.pop(record["transaction_id"])
        checkpoints.append(
            {
                "checkpoint_digest": source["after_workspace_digest"],
                "transaction_id": source["transaction_id"],
                "prepare_sequence": source["sequence"],
                "commit_sequence": record["sequence"],
                "event_kind": source["event_kind"],
                "coverage": source["coverage"],
                "before_workspace_digest": source["before_workspace_digest"],
                "changed_paths": [item["path"] for item in source["logical_changes"]],
                "metadata": deepcopy(source["metadata"]),
                "projection": deepcopy(source["after_projection"]),
            }
        )
    return checkpoints


def journal_projection_for_digest(
    data_path: Path | str,
    checkpoint_digest: str,
) -> dict[str, Any] | None:
    matches = [
        item
        for item in committed_journal_states(data_path)
        if item["checkpoint_digest"] == checkpoint_digest
    ]
    return deepcopy(matches[-1]["projection"]) if matches else None


def pending_journal_prepare(data_path: Path | str) -> dict[str, Any] | None:
    """Return the exact verified pending prepare for safe command-level retry."""

    records = _read_records(data_path)
    if not records:
        return None
    state = _scan_records(records)
    return deepcopy(state.pending)


def pending_workspace_journal_context(
    workspace_path: Path | str,
) -> dict[str, Any] | None:
    """Return a verified pending prepare and its committed before projection.

    Command-level recovery must authenticate the pending mutation itself, not
    only the caller asking to recover it. Exposing the replayed before state
    lets the command prove that no unmentioned object shares the transaction.
    """

    data_path = _workspace_data_path(workspace_path)
    records = _read_records(data_path)
    if not records:
        return None
    state = _scan_records(records)
    if state.pending is None:
        return None
    return {
        "prepare": deepcopy(state.pending),
        "before_projection": deepcopy(state.replay_projection),
    }


def checkpoint_workspace_journal(
    workspace_path: Path | str,
    actor: str,
    acknowledge_break: bool = False,
    *,
    reason: str = "",
    timestamp: str | None = None,
) -> dict[str, Any]:
    data_path = _workspace_data_path(workspace_path)
    try:
        return _checkpoint_workspace_journal(
            workspace_path,
            actor,
            acknowledge_break,
            reason=reason,
            timestamp=timestamp,
        )
    except JournalError as exc:
        return _operator_report(_error_report(data_path, exc))


def _checkpoint_workspace_journal(
    workspace_path: Path | str,
    actor: str,
    acknowledge_break: bool = False,
    *,
    reason: str = "",
    timestamp: str | None = None,
) -> dict[str, Any]:
    data_path = _workspace_data_path(workspace_path)
    current_data = _load_workspace_data(data_path)
    if current_data is None:
        raise JournalError("JOURNAL_WORKSPACE_INVALID", "workspace file does not exist")
    journal_path = journal_file_path(data_path)
    coverage = "from-checkpoint"
    if journal_path.exists():
        records = _read_records(data_path)
        state = _scan_records(records)
        if state.pending is not None:
            raise JournalError(
                "JOURNAL_PENDING_PREPARE",
                "cannot checkpoint while a prepared transaction is pending",
                next_action="Recover the pending transaction first.",
            )
        current_digest = workspace_digest(current_data)
        if current_digest == state.replay_digest:
            return _operator_report(_state_report(data_path, state, current_data))
        if not acknowledge_break:
            raise JournalError(
                "JOURNAL_WORKSPACE_DIVERGENCE",
                "workspace differs from the committed journal projection",
                next_action="Restore it or explicitly acknowledge a continuity break.",
            )
        coverage = "continuity-break"
    metadata = MutationMetadata(
        command="history checkpoint",
        actor=actor,
        action="checkpointed",
        timestamp=timestamp or utc_timestamp(),
        reason=reason,
    )
    report = transact(
        data_path,
        before_data=current_data,
        after_data=current_data,
        metadata=metadata,
        apply=lambda: None,
        event_kind="checkpoint",
        coverage=coverage,
    )
    return _operator_report(report)


def recover_workspace_journal(
    workspace_path: Path | str,
    actor: str = "",
    *,
    action: str = "auto",
    reason: str = "",
) -> dict[str, Any]:
    data_path = _workspace_data_path(workspace_path)
    try:
        return _recover_workspace_journal(
            workspace_path,
            actor,
            action=action,
            reason=reason,
        )
    except JournalError as exc:
        return _operator_report(_error_report(data_path, exc))


def recover_workspace_journal_if_current(
    workspace_path: Path | str,
    actor: str,
    *,
    expected_status: str,
    expected_workspace_digest: str,
    expected_prepare_digest: str,
    expected_transaction_id: str,
    action: str = "auto",
    reason: str = "",
) -> dict[str, Any]:
    """Recover one authenticated pending transaction under the writer lock."""

    from .store import workspace_write_lock

    data_path = _workspace_data_path(workspace_path)
    try:
        with workspace_write_lock(workspace_path):
            current_data = _load_workspace_data(data_path)
            records = _read_records(data_path)
            state = _scan_records(records)
            prepared = state.pending
            if prepared is None:
                raise JournalError(
                    "JOURNAL_RECOVERY_STATE_CHANGED",
                    "the expected pending transaction is no longer present",
                )
            current_digest = workspace_digest(current_data)
            if current_digest == prepared["after_workspace_digest"]:
                current_status = "pending-commit"
            elif current_digest == prepared["before_workspace_digest"]:
                current_status = "pending-prepare"
            else:
                raise JournalError(
                    "JOURNAL_WORKSPACE_DIVERGENCE",
                    "workspace matches neither side of the pending journal transaction",
                )
            if (
                current_status != expected_status
                or current_digest != expected_workspace_digest
                or prepared.get("record_digest") != expected_prepare_digest
                or prepared.get("transaction_id") != expected_transaction_id
            ):
                raise JournalError(
                    "JOURNAL_RECOVERY_STATE_CHANGED",
                    "workspace or pending transaction changed after verification",
                    next_action="Re-run the command against the current exact state.",
                )
            del actor  # Terminal records retain the prepared actor attribution.
            return _operator_report(
                recover_pending(data_path, current_data, action=action, reason=reason)
            )
    except JournalError as exc:
        return _operator_report(_error_report(data_path, exc))


def _recover_workspace_journal(
    workspace_path: Path | str,
    actor: str = "",
    *,
    action: str = "auto",
    reason: str = "",
) -> dict[str, Any]:
    del actor  # Commit/abort records bind the prepared actor and need no new attribution.
    data_path = _workspace_data_path(workspace_path)
    current_data = _load_workspace_data(data_path)
    return _operator_report(
        recover_pending(data_path, current_data, action=action, reason=reason)
    )


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def recover_pending(
    data_path: Path | str,
    current_data: dict[str, Any] | None,
    *,
    action: str = "auto",
    reason: str = "",
    crash_hook: CrashHook | None = None,
) -> dict[str, Any]:
    if action not in {"auto", "abort"}:
        raise JournalError("JOURNAL_RECOVERY_ACTION_INVALID", f"unsupported recovery action: {action}")
    records = _read_records(data_path)
    state = _scan_records(records)
    if state.pending is None:
        return _state_report(data_path, state, current_data)

    prepared = state.pending
    current_digest = workspace_digest(current_data)
    if current_digest == prepared["after_workspace_digest"]:
        commit = commit_record(
            prepared,
            sequence=len(records),
            previous_record_digest=state.head_digest or "",
        )
        append_record_fsync(data_path, commit, crash_hook)
        return verify_journal(data_path, current_data)
    if current_digest == prepared["before_workspace_digest"]:
        if action == "auto":
            return _state_report(data_path, state, current_data)
        aborted = abort_record(
            prepared,
            sequence=len(records),
            previous_record_digest=state.head_digest or "",
            reason=reason,
        )
        append_record_fsync(data_path, aborted, crash_hook)
        return verify_journal(data_path, current_data)
    raise JournalError(
        "JOURNAL_WORKSPACE_DIVERGENCE",
        "workspace matches neither side of the pending journal transaction",
        next_action="Inspect the pending transaction; acknowledge a continuity break explicitly.",
    )


def transact(
    data_path: Path | str,
    *,
    before_data: dict[str, Any] | None,
    after_data: dict[str, Any],
    metadata: MutationMetadata,
    apply: Callable[[], None],
    event_kind: str = "mutation",
    coverage: str = "continuous",
    crash_hook: CrashHook | None = None,
) -> dict[str, Any]:
    records = _read_records(data_path) if journal_file_path(data_path).exists() else []
    state = _scan_records(records) if records else _empty_state()
    current_digest = workspace_digest(before_data)

    if state.pending is not None:
        pending = state.pending
        if current_digest == pending["after_workspace_digest"]:
            identity = _metadata_identity(metadata.as_dict())
            pending_identity = _metadata_identity(pending["metadata"])
            report = recover_pending(data_path, before_data, crash_hook=crash_hook)
            if workspace_digest(after_data) == current_digest and identity == pending_identity:
                return report
            records = _read_records(data_path)
            state = _scan_records(records)
        elif current_digest != pending["before_workspace_digest"]:
            raise JournalError(
                "JOURNAL_WORKSPACE_DIVERGENCE",
                "workspace matches neither side of the pending journal transaction",
                next_action="Inspect the pending transaction before another mutation.",
            )

    if not records and not (event_kind == "checkpoint" and coverage in {"complete", "from-checkpoint"}):
        raise JournalError(
            "JOURNAL_MISSING_CHECKPOINT",
            "a governance journal must begin with an explicit checkpoint",
            next_action="Create an initial history checkpoint before mutating this workspace.",
        )
    if records and state.pending is None:
        if coverage == "continuity-break":
            if event_kind != "checkpoint":
                raise JournalError(
                    "JOURNAL_INVALID_COVERAGE",
                    "a continuity break must be an explicit checkpoint",
                )
        elif current_digest != state.replay_digest:
            raise JournalError(
                "JOURNAL_WORKSPACE_DIVERGENCE",
                "workspace digest does not match the committed journal projection",
                next_action="Record an explicit continuity-break checkpoint or restore the workspace.",
            )

    expected_before = state.replay_digest
    recorded_before = current_digest
    if not records:
        expected_before = None
        recorded_before = None
    candidate_previous_digest = (
        state.pending["previous_record_digest"] if state.pending is not None else state.head_digest
    )
    prepared = prepare_record(
        sequence=len(records),
        previous_record_digest=candidate_previous_digest,
        event_kind=event_kind,
        coverage=coverage,
        expected_before_workspace_digest=expected_before,
        before_workspace_digest=recorded_before,
        after_projection=after_data,
        metadata=metadata,
        before_projection=state.replay_projection,
    )

    if state.pending is not None:
        if prepared["transaction_id"] != state.pending["transaction_id"]:
            raise JournalError(
                "JOURNAL_PENDING_DIFFERENT_MUTATION",
                "a different prepared mutation is already pending",
                next_action="Retry the prepared command or abort it through history recovery.",
            )
        prepared = state.pending
    else:
        _call_hook(crash_hook, "before_prepare_append")
        append_record_fsync(data_path, prepared, crash_hook)
        records.append(prepared)
    _call_hook(crash_hook, "before_apply")
    apply()
    _call_hook(crash_hook, "after_apply")
    commit = commit_record(
        prepared,
        sequence=len(records),
        previous_record_digest=prepared["record_digest"],
    )
    _call_hook(crash_hook, "before_commit_append")
    append_record_fsync(data_path, commit, crash_hook)
    return verify_journal(data_path, after_data)


def _scan_records(records: list[dict[str, Any]]) -> _JournalState:
    if not records:
        raise JournalError(
            "JOURNAL_MISSING_CHECKPOINT",
            "governance journal is empty and has no checkpoint",
            next_action="Create an explicit checkpoint.",
        )
    state = _empty_state()
    transaction_ids: set[str] = set()
    terminal_ids: set[str] = set()
    for index, record in enumerate(records):
        _validate_record_shape(record, index)
        if record["sequence"] != index:
            raise JournalError(
                "JOURNAL_SEQUENCE_GAP",
                f"journal sequence {record['sequence']} appears at position {index}",
                path=f"$[{index}].sequence",
            )
        if record["previous_record_digest"] != state.head_digest:
            raise JournalError(
                "JOURNAL_CHAIN_MISMATCH",
                "previous_record_digest does not match the prior record",
                path=f"$[{index}].previous_record_digest",
            )
        computed_digest = record_digest(record)
        if record["record_digest"] != computed_digest:
            raise JournalError(
                "JOURNAL_RECORD_DIGEST_MISMATCH",
                "journal record content does not match its digest",
                path=f"$[{index}].record_digest",
            )

        record_type = record["record_type"]
        if record_type == "prepare":
            if state.pending is not None:
                raise JournalError(
                    "JOURNAL_PENDING_PREPARE",
                    "another prepare appears before the prior transaction is terminal",
                    path=f"$[{index}]",
                )
            if record["transaction_id"] in transaction_ids:
                raise JournalError(
                    "JOURNAL_DUPLICATE_TRANSACTION",
                    "transaction_id is reused",
                    path=f"$[{index}].transaction_id",
                )
            transaction_ids.add(record["transaction_id"])
            _verify_prepare(record, state, index)
            state.pending = record
        elif record_type == "commit":
            if record["transaction_id"] in terminal_ids:
                raise JournalError(
                    "JOURNAL_DUPLICATE_TERMINAL",
                    "transaction has more than one terminal record",
                    path=f"$[{index}].transaction_id",
                )
            _verify_terminal(record, state.pending, index, commit=True)
            assert state.pending is not None
            state.replay_projection = deepcopy(state.pending["after_projection"])
            state.replay_digest = state.pending["after_workspace_digest"]
            if state.pending["coverage"] == "continuity-break":
                state.continuity_breaks.append(state.pending["sequence"])
            if not state.coverage:
                state.coverage = state.pending["coverage"]
            state.pending = None
            state.committed += 1
            terminal_ids.add(record["transaction_id"])
        else:
            if record["transaction_id"] in terminal_ids:
                raise JournalError(
                    "JOURNAL_DUPLICATE_TERMINAL",
                    "transaction has more than one terminal record",
                    path=f"$[{index}].transaction_id",
                )
            _verify_terminal(record, state.pending, index, commit=False)
            state.pending = None
            state.aborted += 1
            terminal_ids.add(record["transaction_id"])
        state.head_digest = record["record_digest"]
    state.records = records
    return state


def _verify_prepare(record: dict[str, Any], state: _JournalState, index: int) -> None:
    projection_digest = workspace_digest(record["after_projection"])
    if projection_digest != record["after_workspace_digest"]:
        raise JournalError(
            "JOURNAL_PROJECTION_DIGEST_MISMATCH",
            "after_projection does not match after_workspace_digest",
            path=f"$[{index}].after_workspace_digest",
        )
    expected_changes = logical_changes(state.replay_projection, record["after_projection"])
    if record["logical_changes"] != expected_changes:
        raise JournalError(
            "JOURNAL_LOGICAL_CHANGES_MISMATCH",
            "logical_changes do not describe the replayed projection change",
            path=f"$[{index}].logical_changes",
        )
    if record["transaction_id"] != _transaction_id(record):
        raise JournalError(
            "JOURNAL_TRANSACTION_DIGEST_MISMATCH",
            "transaction_id does not match deterministic transaction content",
            path=f"$[{index}].transaction_id",
        )

    if state.replay_projection is None:
        if index != 0 or record["event_kind"] != "checkpoint":
            raise JournalError(
                "JOURNAL_MISSING_CHECKPOINT",
                "the first journal transaction must be a checkpoint",
                path=f"$[{index}].event_kind",
            )
        if record["coverage"] not in {"complete", "from-checkpoint"}:
            raise JournalError(
                "JOURNAL_INVALID_COVERAGE",
                "initial checkpoint coverage must be complete or from-checkpoint",
                path=f"$[{index}].coverage",
            )
        if record["expected_before_workspace_digest"] is not None:
            raise JournalError(
                "JOURNAL_CHECKPOINT_BEFORE_INVALID",
                "initial checkpoint cannot claim an earlier journal digest",
                path=f"$[{index}].expected_before_workspace_digest",
            )
        if record["before_workspace_digest"] is not None:
            raise JournalError(
                "JOURNAL_CHECKPOINT_BEFORE_INVALID",
                "initial checkpoint cannot claim a before-workspace digest",
                path=f"$[{index}].before_workspace_digest",
            )
        return

    if record["expected_before_workspace_digest"] != state.replay_digest:
        raise JournalError(
            "JOURNAL_REPLAY_DIGEST_MISMATCH",
            "prepare expected digest does not match replayed workspace digest",
            path=f"$[{index}].expected_before_workspace_digest",
        )
    if record["coverage"] == "continuity-break":
        if record["event_kind"] != "checkpoint":
            raise JournalError(
                "JOURNAL_INVALID_COVERAGE",
                "continuity-break must be a checkpoint",
                path=f"$[{index}].event_kind",
            )
        if record["before_workspace_digest"] == state.replay_digest:
            raise JournalError(
                "JOURNAL_CONTINUITY_BREAK_UNNEEDED",
                "continuity-break checkpoint does not describe a divergence",
                path=f"$[{index}].before_workspace_digest",
            )
        if record["before_workspace_digest"] != record["after_workspace_digest"]:
            raise JournalError(
                "JOURNAL_CHECKPOINT_MUTATED_WORKSPACE",
                "continuity-break checkpoint must capture, not mutate, current state",
                path=f"$[{index}].after_workspace_digest",
            )
        return
    if record["coverage"] != "continuous":
        raise JournalError(
            "JOURNAL_INVALID_COVERAGE",
            "subsequent non-break transactions must use continuous coverage",
            path=f"$[{index}].coverage",
        )
    if record["before_workspace_digest"] != state.replay_digest:
        raise JournalError(
            "JOURNAL_REPLAY_DIGEST_MISMATCH",
            "prepare before digest does not match replayed workspace digest",
            path=f"$[{index}].before_workspace_digest",
        )


def _verify_terminal(
    record: dict[str, Any],
    pending: dict[str, Any] | None,
    index: int,
    *,
    commit: bool,
) -> None:
    if pending is None:
        code = "JOURNAL_COMMIT_WITHOUT_PREPARE" if commit else "JOURNAL_ABORT_WITHOUT_PREPARE"
        raise JournalError(code, "terminal record has no pending prepare", path=f"$[{index}]")
    if record["transaction_id"] != pending["transaction_id"]:
        raise JournalError(
            "JOURNAL_TERMINAL_MISMATCH",
            "terminal record transaction_id does not match its prepare",
            path=f"$[{index}].transaction_id",
        )
    if record["prepared_record_digest"] != pending["record_digest"]:
        raise JournalError(
            "JOURNAL_TERMINAL_MISMATCH",
            "terminal record does not bind the pending prepare digest",
            path=f"$[{index}].prepared_record_digest",
        )
    if commit and record["after_workspace_digest"] != pending["after_workspace_digest"]:
        raise JournalError(
            "JOURNAL_TERMINAL_MISMATCH",
            "commit after digest does not match the pending prepare",
            path=f"$[{index}].after_workspace_digest",
        )
    if not commit and record["before_workspace_digest"] != pending["before_workspace_digest"]:
        raise JournalError(
            "JOURNAL_TERMINAL_MISMATCH",
            "abort before digest does not match the pending prepare",
            path=f"$[{index}].before_workspace_digest",
        )


def _state_report(
    data_path: Path | str,
    state: _JournalState,
    current_data: dict[str, Any] | None,
) -> dict[str, Any]:
    current_digest = workspace_digest(current_data)
    diagnostics: list[dict[str, str]] = []
    status = "valid"
    chain_valid = True
    writable = state.pending is None
    pending_payload: dict[str, Any] | None = None

    if state.pending is not None:
        pending = state.pending
        pending_payload = {
            "transaction_id": pending["transaction_id"],
            "sequence": pending["sequence"],
            "before_workspace_digest": pending["before_workspace_digest"],
            "after_workspace_digest": pending["after_workspace_digest"],
            "workspace_position": "diverged",
        }
        if current_digest == pending["before_workspace_digest"]:
            code = "JOURNAL_PENDING_PREPARE"
            message = "prepared transaction has not changed the workspace"
            action = "Retry the same mutation or abort the pending transaction explicitly."
            pending_payload["workspace_position"] = "before"
            status = "pending-prepare"
        elif current_digest == pending["after_workspace_digest"]:
            code = "JOURNAL_PENDING_COMMIT"
            message = "workspace changed but its commit marker is missing"
            action = "Run journal recovery to append the exact commit marker."
            pending_payload["workspace_position"] = "after"
            status = "pending-commit"
        else:
            code = "JOURNAL_WORKSPACE_DIVERGENCE"
            message = "workspace matches neither side of the pending transaction"
            action = "Inspect the pending mutation and acknowledge any continuity break."
            status = "invalid"
        diagnostics.append(_diagnostic(code, message, action))
    elif current_digest != state.replay_digest:
        status = "invalid"
        writable = False
        diagnostics.append(
            _diagnostic(
                "JOURNAL_WORKSPACE_DIVERGENCE",
                "workspace digest does not match the committed journal projection",
                "Restore the committed projection or record an explicit continuity-break checkpoint.",
            )
        )

    if state.continuity_breaks:
        if status == "valid":
            status = "valid-with-continuity-break"
        diagnostics.append(
            _diagnostic(
                "JOURNAL_CONTINUITY_BREAK",
                "journal contains an acknowledged continuity break",
                "Treat history before the latest break as discontinuous.",
                severity="warning",
            )
        )

    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "status": status,
        "ok": status == "valid",
        "chain_valid": chain_valid,
        "writable": writable,
        "journal_file": JOURNAL_RELATIVE_PATH,
        "record_count": len(state.records),
        "committed_transactions": state.committed,
        "aborted_transactions": state.aborted,
        "head_record_digest": state.head_digest,
        "replay_workspace_digest": state.replay_digest,
        "current_workspace_digest": current_digest,
        "continuity": {
            "initial_coverage": state.coverage,
            "historical_continuity": not state.continuity_breaks,
            "break_sequences": state.continuity_breaks,
        },
        "pending": pending_payload,
        "diagnostics": diagnostics,
    }


def _read_records(data_path: Path | str) -> list[dict[str, Any]]:
    path = journal_file_path(data_path)
    if not path.exists():
        return []
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise JournalError("JOURNAL_READ_FAILED", f"cannot read governance journal: {exc}") from exc
    payload = b"".join(chunks)
    if payload and not payload.endswith(b"\n"):
        raise JournalError(
            "JOURNAL_TRUNCATED_RECORD",
            "governance journal does not end at a complete JSONL record",
            next_action="Do not edit the journal; recover only from the verified committed prefix.",
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise JournalError("JOURNAL_INVALID_UTF8", f"journal is not valid UTF-8: {exc}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line:
            raise JournalError(
                "JOURNAL_EMPTY_RECORD",
                "blank JSONL records are not allowed",
                path=f"$[{line_number - 1}]",
            )
        try:
            record = json.loads(
                line,
                object_pairs_hook=_strict_object,
                parse_float=_reject_float,
                parse_constant=_reject_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            code = "JOURNAL_DUPLICATE_KEY" if "duplicate key" in str(exc) else "JOURNAL_INVALID_JSON"
            raise JournalError(code, f"invalid journal JSON on line {line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise JournalError(
                "JOURNAL_INVALID_RECORD",
                f"journal line {line_number} must contain an object",
            )
        records.append(record)
    return records


def _validate_record_shape(record: dict[str, Any], index: int) -> None:
    path = "$" if index < 0 else f"$[{index}]"
    _validate_json_value(record, path)
    if record.get("schema_version") != SCHEMA_VERSION:
        raise JournalError(
            "JOURNAL_UNSUPPORTED_VERSION",
            f"unsupported journal schema: {record.get('schema_version')!r}",
            path=f"{path}.schema_version",
        )
    record_type = record.get("record_type")
    if record_type not in RECORD_TYPES:
        raise JournalError(
            "JOURNAL_INVALID_RECORD_TYPE",
            f"unsupported record type: {record_type!r}",
            path=f"{path}.record_type",
        )
    expected = {
        "prepare": PREPARE_FIELDS,
        "commit": COMMIT_FIELDS,
        "abort": ABORT_FIELDS,
    }[record_type]
    actual = set(record)
    if actual != expected:
        unknown = sorted(actual - expected)
        missing = sorted(expected - actual)
        detail = []
        if unknown:
            detail.append(f"unknown fields: {', '.join(unknown)}")
        if missing:
            detail.append(f"missing fields: {', '.join(missing)}")
        raise JournalError(
            "JOURNAL_RECORD_FIELDS_INVALID",
            "; ".join(detail),
            path=path,
        )
    if type(record["sequence"]) is not int or record["sequence"] < 0:
        raise JournalError(
            "JOURNAL_SEQUENCE_INVALID",
            "sequence must be a non-negative integer",
            path=f"{path}.sequence",
        )
    _validate_optional_digest(record["previous_record_digest"], f"{path}.previous_record_digest")
    _validate_digest(record["record_digest"], f"{path}.record_digest")
    _validate_digest(record["transaction_id"], f"{path}.transaction_id")
    if record_type == "prepare":
        if record["event_kind"] not in EVENT_KINDS:
            raise JournalError("JOURNAL_INVALID_EVENT_KIND", "invalid event_kind", path=path)
        if record["coverage"] not in COVERAGE_MODES:
            raise JournalError("JOURNAL_INVALID_COVERAGE", "invalid coverage", path=path)
        _validate_optional_digest(
            record["expected_before_workspace_digest"],
            f"{path}.expected_before_workspace_digest",
        )
        _validate_optional_digest(
            record["before_workspace_digest"], f"{path}.before_workspace_digest"
        )
        _validate_digest(record["after_workspace_digest"], f"{path}.after_workspace_digest")
        if not isinstance(record["after_projection"], dict):
            raise JournalError(
                "JOURNAL_PROJECTION_INVALID",
                "after_projection must be an object",
                path=f"{path}.after_projection",
            )
        if not isinstance(record["logical_changes"], list):
            raise JournalError(
                "JOURNAL_LOGICAL_CHANGES_INVALID",
                "logical_changes must be a list",
                path=f"{path}.logical_changes",
            )
        _validate_logical_changes(record["logical_changes"], f"{path}.logical_changes")
        _validate_metadata(record["metadata"], f"{path}.metadata")
    else:
        _validate_digest(record["prepared_record_digest"], f"{path}.prepared_record_digest")
        digest_field = "after_workspace_digest" if record_type == "commit" else "before_workspace_digest"
        _validate_optional_digest(record[digest_field], f"{path}.{digest_field}")
        if record_type == "commit":
            _validate_digest(record[digest_field], f"{path}.{digest_field}")
        if record_type == "abort" and (
            not isinstance(record["reason"], str) or not record["reason"].strip()
        ):
            raise JournalError("JOURNAL_ABORT_REASON_REQUIRED", "abort reason must not be empty")


def _validate_metadata(value: Any, path: str) -> None:
    if not isinstance(value, dict) or set(value) != METADATA_FIELDS:
        raise JournalError(
            "JOURNAL_METADATA_INVALID",
            "metadata must contain exactly command, actor, action, timestamp, objects, and reason",
            path=path,
        )
    for field in ("command", "actor", "action", "timestamp", "reason"):
        if not isinstance(value[field], str):
            raise JournalError(
                "JOURNAL_METADATA_INVALID",
                f"metadata {field} must be text",
                path=f"{path}.{field}",
            )
    if not value["command"] or not value["action"]:
        raise JournalError(
            "JOURNAL_METADATA_INVALID",
            "metadata command and action must not be empty",
            path=path,
        )
    if not _TIMESTAMP_RE.fullmatch(value["timestamp"]):
        raise JournalError(
            "JOURNAL_TIMESTAMP_INVALID",
            "metadata timestamp must be an unambiguous UTC RFC 3339 value",
            path=f"{path}.timestamp",
        )
    try:
        datetime.fromisoformat(value["timestamp"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise JournalError(
            "JOURNAL_TIMESTAMP_INVALID",
            "metadata timestamp is not a real calendar instant",
            path=f"{path}.timestamp",
        ) from exc
    objects = value["objects"]
    if not isinstance(objects, list):
        raise JournalError("JOURNAL_METADATA_INVALID", "metadata objects must be a list", path=path)
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(objects):
        if not isinstance(item, dict) or set(item) != OBJECT_FIELDS:
            raise JournalError(
                "JOURNAL_METADATA_INVALID",
                "metadata object must contain exactly type, collection, and id",
                path=f"{path}.objects[{index}]",
            )
        if not all(isinstance(item[field], str) for field in OBJECT_FIELDS):
            raise JournalError(
                "JOURNAL_METADATA_INVALID",
                "metadata object fields must be text",
                path=f"{path}.objects[{index}]",
            )
        identity = (item["type"], item["collection"], item["id"])
        if identity in seen:
            raise JournalError(
                "JOURNAL_METADATA_INVALID",
                "metadata objects must not contain duplicates",
                path=f"{path}.objects[{index}]",
            )
        seen.add(identity)
    if objects != _sorted_metadata_objects(objects):
        raise JournalError(
            "JOURNAL_METADATA_INVALID",
            "metadata objects must use canonical order",
            path=f"{path}.objects",
        )


def _validate_logical_changes(value: list[Any], path: str) -> None:
    seen_paths: set[str] = set()
    for index, change in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(change, dict) or set(change) != {"op", "path"}:
            raise JournalError(
                "JOURNAL_LOGICAL_CHANGES_INVALID",
                "logical change must contain exactly op and path",
                path=item_path,
            )
        if change["op"] not in {"add", "remove", "replace"}:
            raise JournalError(
                "JOURNAL_LOGICAL_CHANGES_INVALID",
                "logical change op is unsupported",
                path=f"{item_path}.op",
            )
        change_path = change["path"]
        if not isinstance(change_path, str) or (change_path and not change_path.startswith("/")):
            raise JournalError(
                "JOURNAL_LOGICAL_CHANGES_INVALID",
                "logical change path must be a JSON pointer",
                path=f"{item_path}.path",
            )
        if change_path in seen_paths:
            raise JournalError(
                "JOURNAL_LOGICAL_CHANGES_INVALID",
                "logical change paths must be unique",
                path=f"{item_path}.path",
            )
        seen_paths.add(change_path)


def _transaction_id(record: dict[str, Any]) -> str:
    metadata = _metadata_identity(record["metadata"])
    payload = {
        "schema_version": record["schema_version"],
        "previous_record_digest": record["previous_record_digest"],
        "event_kind": record["event_kind"],
        "coverage": record["coverage"],
        "expected_before_workspace_digest": record["expected_before_workspace_digest"],
        "before_workspace_digest": record["before_workspace_digest"],
        "after_workspace_digest": record["after_workspace_digest"],
        "logical_changes": record["logical_changes"],
        "metadata": metadata,
    }
    return _stable_hash(payload)


def _metadata_identity(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in metadata.items() if key != "timestamp"}


def _sorted_metadata_objects(objects: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        (dict(item) for item in objects),
        key=lambda item: (item["type"], item["collection"], item["id"]),
    )


def _collect_changes(before: Any, after: Any, path: str, output: list[dict[str, Any]]) -> None:
    if before == after:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child_path = f"{path}/{_json_pointer_escape(key)}"
            if key not in before:
                output.append({"op": "add", "path": child_path})
            elif key not in after:
                output.append({"op": "remove", "path": child_path})
            else:
                _collect_changes(before[key], after[key], child_path, output)
        return
    output.append({"op": "replace", "path": path})


def _json_pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _safe_control_path(root: Path, relative_path: str) -> Path:
    canonical_root = root.resolve(strict=False)
    parts = PurePosixPath(relative_path).parts
    candidate = canonical_root.joinpath(*parts)
    current = canonical_root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise JournalError(
                "JOURNAL_UNSAFE_PATH",
                f"governance journal path contains a symlink: {relative_path}",
                next_action="Replace the symlink with a real directory or file inside the workspace.",
            )
    try:
        candidate.resolve(strict=False).relative_to(canonical_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise JournalError(
            "JOURNAL_UNSAFE_PATH",
            f"governance journal path escapes the workspace: {relative_path}",
        ) from exc
    return candidate


def _ensure_safe_parent(path: Path, root: Path) -> None:
    _safe_control_path(root, JOURNAL_RELATIVE_PATH)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise JournalError("JOURNAL_UNSAFE_PATH", f"cannot create journal directory: {exc}") from exc
    checked = _safe_control_path(root, JOURNAL_RELATIVE_PATH)
    if checked != path:
        raise JournalError("JOURNAL_UNSAFE_PATH", "journal path changed during creation")


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise JournalError(
            "JOURNAL_APPEND_FAILED",
            f"cannot durably sync governance journal directory: {exc}",
        ) from exc


def _validate_json_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, bool)):
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise JournalError(
                    "JOURNAL_INVALID_UNICODE",
                    "JSON text contains an unpaired Unicode surrogate",
                    path=path,
                ) from exc
        return
    if type(value) is int:
        if not -IJSON_INTEGER_MAX <= value <= IJSON_INTEGER_MAX:
            raise JournalError(
                "JOURNAL_INTEGER_OUT_OF_RANGE",
                "integer is outside the interoperable JSON range",
                path=path,
            )
        return
    if isinstance(value, float):
        raise JournalError("JOURNAL_FLOAT_UNSUPPORTED", "floating-point JSON is unsupported", path=path)
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise JournalError("JOURNAL_INVALID_JSON", "JSON object keys must be text", path=path)
            _validate_json_value(key, path)
            _validate_json_value(item, f"{path}.{key}")
        return
    raise JournalError(
        "JOURNAL_INVALID_JSON",
        f"unsupported JSON value type: {type(value).__name__}",
        path=path,
    )


def _validate_digest(value: Any, path: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise JournalError("JOURNAL_DIGEST_INVALID", "expected a sha256 digest", path=path)


def _validate_optional_digest(value: Any, path: str) -> None:
    if value is not None:
        _validate_digest(value, path)


def _stable_hash(value: Any) -> str:
    return f"{HASH_PREFIX}{hashlib.sha256(_canonical_bytes(value)).hexdigest()}"


def _canonical_bytes(value: Any) -> bytes:
    _validate_json_value(value, "$")
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise ValueError(f"floating-point value is unsupported: {value}")


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite value is unsupported: {value}")


def _load_workspace_data(data_path: Path | str) -> dict[str, Any] | None:
    path = Path(data_path).expanduser().resolve(strict=False)
    if not path.exists():
        return None
    try:
        payload = path.read_text(encoding="utf-8")
        data = json.loads(
            payload,
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise JournalError("JOURNAL_WORKSPACE_INVALID", f"cannot read current workspace: {exc}") from exc
    if not isinstance(data, dict):
        raise JournalError("JOURNAL_WORKSPACE_INVALID", "current workspace must be an object")
    return data


def _workspace_data_path(workspace_path: Path | str) -> Path:
    path = Path(workspace_path).expanduser().resolve(strict=False)
    return path / "workspace.json" if path.is_dir() else path


def _verification_fingerprint(data_path: Path) -> tuple[str, str]:
    return (
        _file_sha256(data_path),
        _file_sha256(journal_file_path(data_path)),
    )


def _file_sha256(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"{HASH_PREFIX}{digest.hexdigest()}"


def _operator_report(report: dict[str, Any]) -> dict[str, Any]:
    result = dict(report)
    diagnostics = list(report.get("diagnostics") or [])
    result["enabled"] = report.get("status") != "not-enabled"
    result["errors"] = [item for item in diagnostics if item.get("severity") == "error"]
    result["warnings"] = [item for item in diagnostics if item.get("severity") == "warning"]
    return result


def _empty_state() -> _JournalState:
    return _JournalState([], None, None, None, None, 0, 0, "", [])


def _report_not_enabled(data_path: Path | str) -> dict[str, Any]:
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "status": "not-enabled",
        "ok": False,
        "chain_valid": False,
        "writable": True,
        "journal_file": JOURNAL_RELATIVE_PATH,
        "record_count": 0,
        "committed_transactions": 0,
        "aborted_transactions": 0,
        "head_record_digest": None,
        "replay_workspace_digest": None,
        "current_workspace_digest": None,
        "continuity": {
            "initial_coverage": "none",
            "historical_continuity": False,
            "break_sequences": [],
        },
        "pending": None,
        "diagnostics": [
            _diagnostic(
                "JOURNAL_NOT_ENABLED",
                "workspace has no governance journal checkpoint",
                "Create an explicit history checkpoint to begin continuity coverage.",
                severity="warning",
            )
        ],
    }


def _error_report(data_path: Path | str, error: JournalError) -> dict[str, Any]:
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "status": "invalid",
        "ok": False,
        "chain_valid": False,
        "writable": False,
        "journal_file": JOURNAL_RELATIVE_PATH,
        "record_count": 0,
        "committed_transactions": 0,
        "aborted_transactions": 0,
        "head_record_digest": None,
        "replay_workspace_digest": None,
        "current_workspace_digest": None,
        "continuity": {
            "initial_coverage": "unknown",
            "historical_continuity": False,
            "break_sequences": [],
        },
        "pending": None,
        "diagnostics": [error.as_dict()],
    }


def _diagnostic(
    code: str,
    message: str,
    next_action: str,
    *,
    severity: str = "error",
) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "path": "$",
        "message": message,
        "next_action": next_action,
    }


def _call_hook(hook: CrashHook | None, point: str) -> None:
    if hook is not None:
        hook(point)
