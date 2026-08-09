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

from .pcaw_canonical import IJSON_MAX_INTEGER


V2_SCHEMA_VERSION = "palari.governance-journal.v2"
VERIFY_SCHEMA_VERSION = "palari.governance-journal.verify.v1"
V2_JOURNAL_RELATIVE_PATH = ".palari/governance-journal.v2.jsonl"
HASH_PREFIX = "sha256:"

EVENT_KINDS = {"checkpoint", "mutation", "restoration"}
COVERAGE_MODES = {"complete", "from-checkpoint", "continuous", "continuity-break"}
RECORD_TYPES = {"prepare", "commit", "abort"}

V2_PREPARE_FIELDS = {
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
    "delta",
    "checkpoint_projection",
    "predecessor",
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
    record_count: int = 0
    journal_file: str = V2_JOURNAL_RELATIVE_PATH
    journal_schema_version: str = V2_SCHEMA_VERSION


@dataclass
class JournalVerificationContext:
    """Reuse one exact journal verification inside a bounded read operation.

    The context is intentionally in-memory and caller-owned. Reuse is allowed
    only while the workspace and journal retain the filesystem change witness
    observed by the prior exact verification.
    """

    _data_path: Path | None = None
    _witness: tuple[tuple[Any, ...], ...] | None = None
    _report: dict[str, Any] | None = None

    def verify(self, workspace_path: Path | str) -> dict[str, Any]:
        data_path = _workspace_data_path(workspace_path)
        witness = _verification_witness(data_path)
        if (
            self._data_path == data_path
            and self._witness == witness
            and self._report is not None
        ):
            return deepcopy(self._report)

        before = witness
        report = verify_workspace_journal(workspace_path)
        after = _verification_witness(data_path)
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
        self._witness = after
        self._report = deepcopy(report)
        return report


def journal_file_path(data_path: Path | str) -> Path:
    """Return the current journal path."""

    workspace_file = Path(data_path).expanduser()
    if not workspace_file.is_absolute():
        workspace_file = (Path.cwd() / workspace_file).resolve(strict=False)
    root = workspace_file.parent.resolve(strict=False)
    return _safe_control_path(root, V2_JOURNAL_RELATIVE_PATH)


def v2_journal_file_path(data_path: Path | str) -> Path:
    workspace_file = Path(data_path).expanduser()
    if not workspace_file.is_absolute():
        workspace_file = (Path.cwd() / workspace_file).resolve(strict=False)
    return _safe_control_path(
        workspace_file.parent.resolve(strict=False), V2_JOURNAL_RELATIVE_PATH
    )


def _journal_path_for_record(data_path: Path | str, record: dict[str, Any]) -> Path:
    if record.get("schema_version") != V2_SCHEMA_VERSION:
        raise JournalError(
            "JOURNAL_UNSUPPORTED_VERSION",
            "the governance journal accepts only the current schema",
        )
    return v2_journal_file_path(data_path)


def _journal_schema(path: Path) -> str | None:
    record = next(iter(_iter_records(path)), None)
    if record is None:
        return None
    value = record.get("schema_version")
    return value if isinstance(value, str) else None


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


def _prepare_v2_record(
    *,
    sequence: int,
    previous_record_digest: str | None,
    event_kind: str,
    coverage: str,
    expected_before_workspace_digest: str | None,
    before_workspace_digest: str | None,
    after_projection: dict[str, Any],
    metadata: MutationMetadata | dict[str, Any],
    before_projection: dict[str, Any] | None,
    predecessor: dict[str, Any] | None = None,
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
    checkpoint = event_kind == "checkpoint"
    delta = [] if checkpoint else _value_delta(before_projection, projection)
    if not checkpoint:
        if before_projection is None:
            raise JournalError(
                "JOURNAL_DELTA_BASE_MISSING",
                "a v2 mutation requires a replayable before projection",
            )
        replayed = _apply_value_delta(before_projection, delta, "$.delta")
        if workspace_digest(replayed) != workspace_digest(projection):
            raise JournalError(
                "JOURNAL_DELTA_INTERNAL_MISMATCH",
                "generated delta does not reconstruct the requested workspace projection",
            )
    record = {
        "schema_version": V2_SCHEMA_VERSION,
        "sequence": sequence,
        "record_type": "prepare",
        "transaction_id": "",
        "previous_record_digest": previous_record_digest,
        "event_kind": event_kind,
        "coverage": coverage,
        "expected_before_workspace_digest": expected_before_workspace_digest,
        "before_workspace_digest": before_workspace_digest,
        "after_workspace_digest": workspace_digest(projection),
        "delta": delta,
        "checkpoint_projection": projection if checkpoint else None,
        "predecessor": deepcopy(predecessor),
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
        "schema_version": prepared["schema_version"],
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
        "schema_version": prepared["schema_version"],
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
    if record.get("schema_version") != V2_SCHEMA_VERSION:
        raise JournalError(
            "JOURNAL_UNSUPPORTED_VERSION",
            "the governance journal accepts only the current schema",
        )
    _validate_record_shape(record, -1)
    if record_digest(record) != record.get("record_digest"):
        raise JournalError(
            "JOURNAL_RECORD_DIGEST_MISMATCH",
            "record content does not match record_digest",
        )
    root = Path(data_path).expanduser().resolve(strict=False).parent
    path = _journal_path_for_record(data_path, record)
    relative_path = str(path.relative_to(root))
    _ensure_safe_parent(path, root, relative_path)
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
        state = _scan_active_path(data_path, path)
        current = _load_workspace_data(data_path) if current_data is _MISSING else current_data
        if current is not None and not isinstance(current, dict):
            raise JournalError("JOURNAL_WORKSPACE_INVALID", "current workspace must be an object")
        return _state_report(data_path, state, current)
    except JournalError as exc:
        return _error_report(data_path, exc)


def verify_workspace_journal(workspace_path: Path | str) -> dict[str, Any]:
    return _operator_report(verify_journal(_workspace_data_path(workspace_path)))


def _active_state(data_path: Path | str) -> _JournalState:
    path = journal_file_path(data_path)
    if not path.exists():
        return _empty_state()
    return _scan_active_path(data_path, path)


def _scan_active_path(data_path: Path | str, path: Path) -> _JournalState:
    schema = _journal_schema(path)
    if schema not in {None, V2_SCHEMA_VERSION}:
        raise JournalError(
            "JOURNAL_PATH_SCHEMA_MISMATCH",
            "the journal path contains a record from another schema",
            path="$[0].schema_version",
        )
    return _scan_v2_records(data_path, path=path)


def committed_journal_states(data_path: Path | str) -> list[dict[str, Any]]:
    """Return verified committed projections as content-addressed checkpoints."""

    active = journal_file_path(data_path)
    state = _active_state(data_path)
    if state.pending is not None:
        raise JournalError(
            "JOURNAL_PENDING_PREPARE",
            "cannot enumerate checkpoints while a transaction is pending",
            next_action="Recover the pending transaction first.",
        )
    checkpoints: list[dict[str, Any]] = []
    prepared: dict[str, Any] | None = None
    projection: dict[str, Any] | None = None
    for record in _iter_records(active):
        if record["record_type"] == "prepare":
            prepared = record
            continue
        if record["record_type"] == "abort":
            prepared = None
            continue
        assert prepared is not None
        source = prepared
        projection = _v2_after_projection(projection, source, source["sequence"])
        checkpoints.append(
            {
                "checkpoint_digest": source["after_workspace_digest"],
                "transaction_id": source["transaction_id"],
                "prepare_sequence": source["sequence"],
                "commit_sequence": record["sequence"],
                "event_kind": source["event_kind"],
                "coverage": source["coverage"],
                "before_workspace_digest": source["before_workspace_digest"],
                "changed_paths": [item["path"] for item in source["delta"]],
                "metadata": deepcopy(source["metadata"]),
                "projection": deepcopy(projection),
            }
        )
        prepared = None
    return checkpoints


def pending_workspace_journal_context(
    workspace_path: Path | str,
) -> dict[str, Any] | None:
    """Return a verified pending prepare and its committed before projection.

    Command-level recovery must authenticate the pending mutation itself, not
    only the caller asking to recover it. Exposing the replayed before state
    lets the command prove that no unmentioned object shares the transaction.
    """

    data_path = _workspace_data_path(workspace_path)
    if not journal_file_path(data_path).exists():
        return None
    state = _active_state(data_path)
    if state.pending is None:
        return None
    prepared = deepcopy(state.pending)
    projected = _v2_after_projection(
        state.replay_projection, prepared, prepared["sequence"]
    )
    # These recovery-only fields are never appended or hashed.
    prepared["after_projection"] = projected
    prepared["logical_changes"] = logical_changes(state.replay_projection, projected)
    return {
        "prepare": prepared,
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
        state = _active_state(data_path)
        if state.pending is not None:
            raise JournalError(
                "JOURNAL_PENDING_PREPARE",
                "cannot checkpoint while a prepared transaction is pending",
                next_action="Recover the pending transaction first.",
            )
        current_digest = workspace_digest(current_data)
        if current_digest == state.replay_digest:
            return _operator_report(_state_report(data_path, state, current_data))
        if current_digest != state.replay_digest and not acknowledge_break:
            raise JournalError(
                "JOURNAL_WORKSPACE_DIVERGENCE",
                "workspace differs from the committed journal projection",
                next_action="Restore it or explicitly acknowledge a continuity break.",
            )
        if current_digest != state.replay_digest:
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
            state = _active_state(data_path)
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
    state = _active_state(data_path)
    if state.pending is None:
        return _state_report(data_path, state, current_data)

    prepared = state.pending
    current_digest = workspace_digest(current_data)
    if current_digest == prepared["after_workspace_digest"]:
        commit = commit_record(
            prepared,
            sequence=state.record_count,
            previous_record_digest=state.head_digest or "",
        )
        append_record_fsync(data_path, commit, crash_hook)
        return verify_journal(data_path, current_data)
    if current_digest == prepared["before_workspace_digest"]:
        if action == "auto":
            return _state_report(data_path, state, current_data)
        aborted = abort_record(
            prepared,
            sequence=state.record_count,
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
    prewrite_check: Callable[[], None] | None = None,
) -> dict[str, Any]:
    active_path = journal_file_path(data_path)
    state = _active_state(data_path) if active_path.exists() else _empty_state()
    current_digest = workspace_digest(before_data)

    if state.pending is not None:
        pending = state.pending
        if current_digest == pending["after_workspace_digest"]:
            identity = _metadata_identity(metadata.as_dict())
            pending_identity = _metadata_identity(pending["metadata"])
            report = recover_pending(data_path, before_data, crash_hook=crash_hook)
            if workspace_digest(after_data) == current_digest and identity == pending_identity:
                return report
            state = _active_state(data_path)
        elif current_digest != pending["before_workspace_digest"]:
            raise JournalError(
                "JOURNAL_WORKSPACE_DIVERGENCE",
                "workspace matches neither side of the pending journal transaction",
                next_action="Inspect the pending transaction before another mutation.",
            )

    has_records = state.record_count > 0
    initial_coverage_ok = coverage in {"complete", "from-checkpoint"}
    if not has_records and not (event_kind == "checkpoint" and initial_coverage_ok):
        raise JournalError(
            "JOURNAL_MISSING_CHECKPOINT",
            "a governance journal must begin with an explicit checkpoint",
            next_action="Create an initial history checkpoint before mutating this workspace.",
        )
    if has_records and state.pending is None:
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
    if state.pending is not None:
        expected_before = state.pending["expected_before_workspace_digest"]
        recorded_before = state.pending["before_workspace_digest"]
    if not has_records:
        expected_before = None
        recorded_before = None
    candidate_previous_digest = (
        state.pending["previous_record_digest"] if state.pending is not None else state.head_digest
    )
    prepare_kwargs: dict[str, Any] = {
        "sequence": state.record_count,
        "previous_record_digest": candidate_previous_digest,
        "event_kind": event_kind,
        "coverage": coverage,
        "expected_before_workspace_digest": expected_before,
        "before_workspace_digest": recorded_before,
        "after_projection": after_data,
        "metadata": metadata,
        "before_projection": state.replay_projection,
    }
    prepare_kwargs["predecessor"] = None
    prepared = _prepare_v2_record(**prepare_kwargs)

    pending_prepare = state.pending
    if pending_prepare is not None:
        if prepared["transaction_id"] != pending_prepare["transaction_id"]:
            raise JournalError(
                "JOURNAL_PENDING_DIFFERENT_MUTATION",
                "a different prepared mutation is already pending",
                next_action="Retry the prepared command or abort it through history recovery.",
            )
        prepared = pending_prepare
    else:
        _call_hook(crash_hook, "before_prepare_append")
        if prewrite_check is not None:
            prewrite_check()
        append_record_fsync(data_path, prepared, crash_hook)
        state.record_count += 1
    _call_hook(crash_hook, "before_apply")
    if prewrite_check is not None:
        try:
            prewrite_check()
        except Exception:
            aborted = abort_record(
                prepared,
                sequence=state.record_count,
                previous_record_digest=prepared["record_digest"],
                reason="final prewrite validation rejected the prepared mutation",
            )
            append_record_fsync(data_path, aborted)
            raise
    apply()
    _call_hook(crash_hook, "after_apply")
    commit = commit_record(
        prepared,
        sequence=state.record_count,
        previous_record_digest=prepared["record_digest"],
    )
    _call_hook(crash_hook, "before_commit_append")
    append_record_fsync(data_path, commit, crash_hook)
    return verify_journal(data_path, after_data)


def _scan_v2_records(data_path: Path | str, *, path: Path | None = None) -> _JournalState:
    path = path or v2_journal_file_path(data_path)
    state = _empty_state()
    state.journal_file = str(path.relative_to(_workspace_data_path(data_path).parent))
    state.journal_schema_version = V2_SCHEMA_VERSION
    found = False
    last_terminal_id = ""
    for index, record in enumerate(_iter_records(path)):
        found = True
        _validate_record_shape(record, index)
        if record["schema_version"] != V2_SCHEMA_VERSION:
            raise JournalError(
                "JOURNAL_UNSUPPORTED_VERSION",
                "v2 journal contains a record from another schema",
                path=f"$[{index}].schema_version",
            )
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
        if record["record_digest"] != record_digest(record):
            raise JournalError(
                "JOURNAL_RECORD_DIGEST_MISMATCH",
                "journal record content does not match its digest",
                path=f"$[{index}].record_digest",
            )

        if record["record_type"] == "prepare":
            if state.pending is not None:
                raise JournalError(
                    "JOURNAL_PENDING_PREPARE",
                    "another prepare appears before the prior transaction is terminal",
                    path=f"$[{index}]",
                )
            _verify_v2_prepare(record, state, index)
            state.pending = record
        elif record["record_type"] == "commit":
            if state.pending is None and record["transaction_id"] == last_terminal_id:
                raise JournalError(
                    "JOURNAL_DUPLICATE_TERMINAL",
                    "transaction has more than one terminal record",
                    path=f"$[{index}].transaction_id",
                )
            _verify_terminal(record, state.pending, index, commit=True)
            assert state.pending is not None
            state.replay_projection = _v2_after_projection(
                state.replay_projection, state.pending, index
            )
            state.replay_digest = state.pending["after_workspace_digest"]
            if state.pending["coverage"] == "continuity-break":
                state.continuity_breaks.append(state.pending["sequence"])
            if not state.coverage:
                state.coverage = state.pending["coverage"]
            state.pending = None
            state.committed += 1
            last_terminal_id = record["transaction_id"]
        else:
            if state.pending is None and record["transaction_id"] == last_terminal_id:
                raise JournalError(
                    "JOURNAL_DUPLICATE_TERMINAL",
                    "transaction has more than one terminal record",
                    path=f"$[{index}].transaction_id",
                )
            _verify_terminal(record, state.pending, index, commit=False)
            state.pending = None
            state.aborted += 1
            last_terminal_id = record["transaction_id"]
        state.head_digest = record["record_digest"]
        state.record_count = index + 1
    if not found:
        raise JournalError(
            "JOURNAL_MISSING_CHECKPOINT",
            "governance journal is empty and has no checkpoint",
            next_action="Create an explicit checkpoint.",
        )
    if state.committed == 0 and state.pending is None:
        raise JournalError(
            "JOURNAL_MISSING_CHECKPOINT",
            "v2 journal has no committed checkpoint",
            next_action="Restore the current journal checkpoint.",
        )
    return state


def _verify_v2_prepare(
    record: dict[str, Any],
    state: _JournalState,
    index: int,
) -> None:
    checkpoint = record["checkpoint_projection"]
    delta = record["delta"]
    predecessor = record["predecessor"]
    if predecessor is not None:
        raise JournalError(
            "JOURNAL_PREDECESSOR_UNSUPPORTED",
            "current journal records cannot declare a predecessor",
            path=f"$[{index}].predecessor",
        )
    if record["event_kind"] == "checkpoint":
        if not isinstance(checkpoint, dict) or delta != []:
            raise JournalError(
                "JOURNAL_CHECKPOINT_INVALID",
                "v2 checkpoint must contain one full projection and an empty delta",
                path=f"$[{index}]",
            )
        projected = checkpoint
    else:
        if checkpoint is not None:
            raise JournalError(
                "JOURNAL_DELTA_INVALID",
                "v2 mutation must use a delta",
                path=f"$[{index}]",
            )
        if state.replay_projection is None:
            raise JournalError(
                "JOURNAL_MISSING_CHECKPOINT",
                "v2 mutations require a committed checkpoint",
                path=f"$[{index}]",
            )
        projected = _apply_value_delta(state.replay_projection, delta, f"$[{index}].delta")
        if delta != _value_delta(state.replay_projection, projected):
            raise JournalError(
                "JOURNAL_DELTA_NONCANONICAL",
                "delta is not the deterministic minimal representation of the change",
                path=f"$[{index}].delta",
            )
    if workspace_digest(projected) != record["after_workspace_digest"]:
        raise JournalError(
            "JOURNAL_PROJECTION_DIGEST_MISMATCH",
            "checkpoint or delta result does not match after_workspace_digest",
            path=f"$[{index}].after_workspace_digest",
        )
    if record["transaction_id"] != _transaction_id(record):
        raise JournalError(
            "JOURNAL_TRANSACTION_DIGEST_MISMATCH",
            "transaction_id does not match deterministic transaction content",
            path=f"$[{index}].transaction_id",
        )

    if index == 0:
        if record["event_kind"] != "checkpoint":
            raise JournalError(
                "JOURNAL_MISSING_CHECKPOINT",
                "the first v2 transaction must be a checkpoint",
                path=f"$[{index}].event_kind",
            )
        if record["coverage"] not in {"complete", "from-checkpoint"}:
            raise JournalError(
                "JOURNAL_INVALID_COVERAGE",
                "a new v2 journal starts complete or from-checkpoint",
                path=f"$[{index}].coverage",
            )
        if record["expected_before_workspace_digest"] is not None:
            raise JournalError(
                "JOURNAL_CHECKPOINT_BEFORE_INVALID",
                "an initial checkpoint has no expected prior digest",
                path=f"$[{index}].expected_before_workspace_digest",
            )
        if record["before_workspace_digest"] is not None:
            raise JournalError(
                "JOURNAL_CHECKPOINT_BEFORE_INVALID",
                "an initial checkpoint has no before digest",
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
                path=f"$[{index}]",
            )
    elif record["coverage"] != "continuous" or record[
        "before_workspace_digest"
    ] != state.replay_digest:
        raise JournalError(
            "JOURNAL_REPLAY_DIGEST_MISMATCH",
            "continuous prepare must start at the replayed workspace digest",
            path=f"$[{index}].before_workspace_digest",
        )


def _v2_after_projection(
    before: dict[str, Any] | None,
    prepared: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    checkpoint = prepared["checkpoint_projection"]
    if checkpoint is not None:
        return deepcopy(checkpoint)
    if before is None:
        raise JournalError("JOURNAL_MISSING_CHECKPOINT", "delta has no checkpoint base")
    return _apply_value_delta(before, prepared["delta"], f"$[{index}].delta")


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
    if record["schema_version"] != pending["schema_version"]:
        raise JournalError(
            "JOURNAL_TERMINAL_MISMATCH",
            "terminal record schema does not match its prepare",
            path=f"$[{index}].schema_version",
        )
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
    all_breaks = list(state.continuity_breaks)
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

    if all_breaks:
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
        "journal_file": state.journal_file,
        "journal_schema_version": state.journal_schema_version,
        "record_count": state.record_count or len(state.records),
        "committed_transactions": state.committed,
        "aborted_transactions": state.aborted,
        "head_record_digest": state.head_digest,
        "replay_workspace_digest": state.replay_digest,
        "current_workspace_digest": current_digest,
        "continuity": {
            "initial_coverage": state.coverage,
            "historical_continuity": not state.continuity_breaks,
            "break_sequences": all_breaks,
        },
        "pending": pending_payload,
        "predecessor": None,
        "diagnostics": diagnostics,
    }


def _iter_records(path: Path) -> Iterable[dict[str, Any]]:
    """Yield strict JSONL records without retaining the journal payload."""

    if not path.exists():
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "r", encoding="utf-8", newline="") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.endswith("\n"):
                    raise JournalError(
                        "JOURNAL_TRUNCATED_RECORD",
                        "governance journal does not end at a complete JSONL record",
                        next_action=(
                            "Do not edit the journal; recover only from the verified "
                            "committed prefix."
                        ),
                    )
                payload = line[:-1]
                if not payload:
                    raise JournalError(
                        "JOURNAL_EMPTY_RECORD",
                        "blank JSONL records are not allowed",
                        path=f"$[{line_number - 1}]",
                    )
                try:
                    record = json.loads(
                        payload,
                        object_pairs_hook=_strict_object,
                        parse_float=_reject_float,
                        parse_constant=_reject_constant,
                    )
                except (json.JSONDecodeError, ValueError) as exc:
                    code = (
                        "JOURNAL_DUPLICATE_KEY"
                        if "duplicate key" in str(exc)
                        else "JOURNAL_INVALID_JSON"
                    )
                    raise JournalError(
                        code,
                        f"invalid journal JSON on line {line_number}: {exc}",
                    ) from exc
                if not isinstance(record, dict):
                    raise JournalError(
                        "JOURNAL_INVALID_RECORD",
                        f"journal line {line_number} must contain an object",
                    )
                yield record
    except UnicodeDecodeError as exc:
        raise JournalError("JOURNAL_INVALID_UTF8", f"journal is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise JournalError("JOURNAL_READ_FAILED", f"cannot read governance journal: {exc}") from exc


def _validate_record_shape(record: dict[str, Any], index: int) -> None:
    path = "$" if index < 0 else f"$[{index}]"
    schema_version = record.get("schema_version")
    if schema_version != V2_SCHEMA_VERSION:
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
        "prepare": V2_PREPARE_FIELDS,
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
        if not isinstance(record["delta"], list):
            raise JournalError(
                "JOURNAL_DELTA_INVALID",
                "delta must be a list",
                path=f"{path}.delta",
            )
        _validate_value_delta(record["delta"], f"{path}.delta")
        checkpoint = record["checkpoint_projection"]
        if checkpoint is not None and not isinstance(checkpoint, dict):
            raise JournalError(
                "JOURNAL_PROJECTION_INVALID",
                "checkpoint_projection must be an object or null",
                path=f"{path}.checkpoint_projection",
            )
        if record["predecessor"] is not None:
            raise JournalError(
                "JOURNAL_PREDECESSOR_UNSUPPORTED",
                "current journal records cannot declare a predecessor",
                path=f"{path}.predecessor",
            )
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


def _transaction_id(record: dict[str, Any]) -> str:
    metadata = _metadata_identity(record["metadata"])
    payload: dict[str, Any] = {
        "schema_version": record["schema_version"],
        "previous_record_digest": record["previous_record_digest"],
        "event_kind": record["event_kind"],
        "coverage": record["coverage"],
        "expected_before_workspace_digest": record["expected_before_workspace_digest"],
        "before_workspace_digest": record["before_workspace_digest"],
        "after_workspace_digest": record["after_workspace_digest"],
        "metadata": metadata,
    }
    payload.update(
        {
            "delta": record["delta"],
            "checkpoint_projection": record["checkpoint_projection"],
            "predecessor": record["predecessor"],
        }
    )
    return _stable_hash(payload)


def _metadata_identity(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in metadata.items() if key != "timestamp"}


def _sorted_metadata_objects(objects: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        (dict(item) for item in objects),
        key=lambda item: (item["type"], item["collection"], item["id"]),
    )


def _collect_changes(before: Any, after: Any, path: str, output: list[dict[str, Any]]) -> None:
    if _json_values_equal(before, after):
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


def _value_delta(
    before: dict[str, Any] | None,
    after: dict[str, Any],
) -> list[dict[str, Any]]:
    _validate_json_value(after, "$")
    if before is None:
        return []
    _validate_json_value(before, "$")
    output: list[dict[str, Any]] = []
    _collect_value_delta(before, after, "", output)
    output.sort(key=lambda change: change["path"])
    return output


def _collect_value_delta(
    before: Any,
    after: Any,
    path: str,
    output: list[dict[str, Any]],
) -> None:
    if _json_values_equal(before, after):
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after), key=_json_pointer_escape):
            child_path = f"{path}/{_json_pointer_escape(key)}"
            if key not in before:
                output.append({"op": "add", "path": child_path, "value": deepcopy(after[key])})
            elif key not in after:
                output.append({"op": "remove", "path": child_path})
            else:
                _collect_value_delta(before[key], after[key], child_path, output)
        return
    output.append({"op": "replace", "path": path, "value": deepcopy(after)})


def _json_values_equal(before: Any, after: Any) -> bool:
    """Compare JSON values without Python's bool/int equality aliasing."""

    if type(before) is not type(after):
        return False
    if isinstance(before, dict):
        return before.keys() == after.keys() and all(
            _json_values_equal(before[key], after[key]) for key in before
        )
    if isinstance(before, list):
        return len(before) == len(after) and all(
            _json_values_equal(left, right) for left, right in zip(before, after)
        )
    return bool(before == after)


def _validate_value_delta(value: list[Any], path: str) -> None:
    prior = ""
    seen: set[str] = set()
    for index, change in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(change, dict):
            raise JournalError("JOURNAL_DELTA_INVALID", "delta entry must be an object", path=item_path)
        op = change.get("op")
        expected = {"op", "path"} if op == "remove" else {"op", "path", "value"}
        if op not in {"add", "remove", "replace"} or set(change) != expected:
            raise JournalError(
                "JOURNAL_DELTA_INVALID",
                "delta entry fields must match add, remove, or replace",
                path=item_path,
            )
        pointer = change["path"]
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            raise JournalError(
                "JOURNAL_DELTA_INVALID",
                "delta path must be a non-root JSON pointer",
                path=f"{item_path}.path",
            )
        if pointer in seen or (prior and pointer <= prior):
            raise JournalError(
                "JOURNAL_DELTA_NONCANONICAL",
                "delta paths must be unique and lexicographically ordered",
                path=f"{item_path}.path",
            )
        prefix = ""
        for component in pointer.split("/")[1:-1]:
            prefix = f"{prefix}/{component}"
            if prefix in seen:
                raise JournalError(
                    "JOURNAL_DELTA_NONCANONICAL",
                    "delta paths must be prefix-disjoint",
                    path=f"{item_path}.path",
                )
        if "value" in change:
            _validate_json_value(change["value"], f"{item_path}.value")
        seen.add(pointer)
        prior = pointer


def _apply_value_delta(
    before: dict[str, Any],
    delta: list[dict[str, Any]],
    path: str,
) -> dict[str, Any]:
    _validate_value_delta(delta, path)
    result = deepcopy(before)
    for index, change in enumerate(delta):
        components = [_json_pointer_unescape(part, f"{path}[{index}].path") for part in change["path"].split("/")[1:]]
        parent: Any = result
        for component in components[:-1]:
            if not isinstance(parent, dict) or component not in parent:
                raise JournalError(
                    "JOURNAL_DELTA_APPLY_FAILED",
                    "delta parent path does not exist",
                    path=f"{path}[{index}].path",
                )
            parent = parent[component]
        if not isinstance(parent, dict):
            raise JournalError(
                "JOURNAL_DELTA_APPLY_FAILED",
                "delta parent must be an object",
                path=f"{path}[{index}].path",
            )
        key = components[-1]
        op = change["op"]
        exists = key in parent
        if (op == "add" and exists) or (op in {"remove", "replace"} and not exists):
            raise JournalError(
                "JOURNAL_DELTA_APPLY_FAILED",
                f"delta {op} precondition does not match replay state",
                path=f"{path}[{index}]",
            )
        if op == "remove":
            del parent[key]
        else:
            parent[key] = deepcopy(change["value"])
    return result


def _json_pointer_unescape(value: str, path: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "~":
            output.append(value[index])
            index += 1
            continue
        if index + 1 >= len(value) or value[index + 1] not in {"0", "1"}:
            raise JournalError(
                "JOURNAL_DELTA_INVALID",
                "delta JSON pointer contains an invalid escape",
                path=path,
            )
        output.append("~" if value[index + 1] == "0" else "/")
        index += 2
    return "".join(output)


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


def _ensure_safe_parent(path: Path, root: Path, relative_path: str) -> None:
    _safe_control_path(root, relative_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise JournalError("JOURNAL_UNSAFE_PATH", f"cannot create journal directory: {exc}") from exc
    checked = _safe_control_path(root, relative_path)
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
        if not -IJSON_MAX_INTEGER <= value <= IJSON_MAX_INTEGER:
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


def _verification_witness(
    data_path: Path,
) -> tuple[tuple[Any, ...], ...]:
    return (
        _file_witness(data_path),
        _file_witness(v2_journal_file_path(data_path)),
    )


def _file_witness(path: Path) -> tuple[Any, ...]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return ("missing",)
    return (
        "present",
        stat.st_dev,
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
    )


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
        "writable": False,
        "journal_file": V2_JOURNAL_RELATIVE_PATH,
        "journal_schema_version": V2_SCHEMA_VERSION,
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
        "predecessor": None,
        "diagnostics": [
            _diagnostic(
                "JOURNAL_NOT_ENABLED",
                "workspace has no governance journal checkpoint",
                "Create an explicit checkpoint to begin v2 continuity coverage.",
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
        "journal_file": V2_JOURNAL_RELATIVE_PATH,
        "journal_schema_version": V2_SCHEMA_VERSION,
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
        "predecessor": None,
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
