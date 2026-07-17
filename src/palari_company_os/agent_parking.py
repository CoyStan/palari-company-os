"""Durable, claim-bound parking for interrupted agent work.

Parking is deliberately smaller than proof closeout.  It records one blocked
attempt and binds the work item to that attempt in a single governance-journal
transaction, then releases the execute claim.  It never creates completion
proof or invokes convergence.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .agent_file_changes import capture_git_baseline, git_repo_root, inspect_file_changes
from .agent_packets import build_agent_brief
from .agent_runtime import (
    claim_check,
    claim_integrity_error,
    claim_is_active,
    read_claim,
    read_claim_packet,
    release_agent,
)
from .governance_journal import (
    JournalError,
    MutationMetadata,
    journal_file_path,
    pending_workspace_journal_context,
    utc_timestamp,
    verify_workspace_journal,
    workspace_digest,
)
from .path_policy import canonical_path_allowed, validate_workspace_path
from .store import WorkspaceStore, load_store, validate_data, workspace_file_path, write_store
from .workspace import Workspace, WorkspaceError


SCHEMA_VERSION = "palari.agent_parking.v1"
RESULT_SCHEMA_VERSION = "palari.agent_parking_record.v1"
_TERMINAL_WORK_STATUSES = {"completed", "closed", "done"}


def park_agent(
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    *,
    reason: str,
    next_action: str,
    _after_persist: Callable[[dict[str, Any]], None] | None = None,
    _after_lease_release: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Park owned execute work without manufacturing completion authority.

    ``_after_persist`` and ``_after_lease_release`` are narrow crash-injection
    seams used to prove retries around the durable write and lease/local-claim
    boundary. Production callers should leave them unset.
    """

    reason = _required_text(reason, "reason")
    next_action = _required_text(next_action, "next action")
    store = load_store(workspace_path)
    work_record = _record(store, "work_items", work_id)
    durable_attempt = _current_parking_attempt(store, work_record, work_id)
    claim, packet = _owned_claim(
        workspace_path,
        work_id,
        palari_id,
        allow_released_lease=durable_attempt is not None,
    )
    attempt_id = _parking_attempt_id(work_id, claim)
    existing = _optional_record(store, "attempts", attempt_id)
    if existing is None:
        existing = durable_attempt
    if existing is not None:
        return _resume_parked_release(
            store,
            work_record,
            existing,
            claim,
            packet,
            work_id,
            palari_id,
            reason,
            next_action,
            _after_lease_release,
        )

    if not claim_is_active(claim):
        raise WorkspaceError(
            f"cannot park {work_id}: its execute claim has expired; inspect the claim "
            "before starting a new claim epoch"
        )
    if str(work_record.get("status") or "") in _TERMINAL_WORK_STATUSES:
        raise WorkspaceError(
            f"cannot park terminal work {work_id} with status {work_record.get('status')}"
        )

    _ensure_journal(workspace_path, palari_id)
    # Checkpoint creation does not change workspace bytes, but reloading keeps
    # the following CAS and digest witness exact if another process raced it.
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    work_record = _record(store, "work_items", work_id)
    if _optional_record(store, "attempts", attempt_id) is not None:
        raise WorkspaceError(
            f"parking attempt {attempt_id} appeared during preparation; retry safely"
        )

    current_packet = build_agent_brief(workspace, work_id, palari_id, "execute")
    claim_result = claim_check(
        workspace_path,
        work_id,
        palari_id,
        "execute",
        str(current_packet.get("context_hash") or ""),
    )
    if claim_result.get("status") != "pass":
        raise WorkspaceError(
            f"cannot park {work_id}: {claim_result.get('message', 'claim does not match current work')}"
        )
    if current_packet.get("packet_id") != packet.get("packet_id"):
        raise WorkspaceError(
            f"cannot park {work_id}: the current packet differs from the claimed packet"
        )

    observation = _observe_repository(store.data_path, packet, claim)
    before_digest = str(workspace_digest(store.data) or "")
    parking_record = _parking_record(
        reason,
        next_action,
        packet,
        claim,
        observation,
        before_digest,
    )
    attempt_record = _blocked_attempt(
        attempt_id,
        work_id,
        palari_id,
        packet,
        claim,
        observation,
        parking_record,
    )

    _records(store, "attempts").append(attempt_record)
    work_record["status"] = "blocked"
    work_record["current_attempt"] = attempt_id
    # Validate the complete projection before the journal prepares it.  Paths
    # outside scope remain visible in result metadata, while changed_files only
    # contains paths the existing attempt schema is allowed to carry.
    validate_data(store.data_path, store.data)

    metadata = _parking_metadata(attempt_id, work_id, palari_id, reason)
    write_store(store, metadata=metadata)
    after_digest = str(workspace_digest(store.data) or "")
    persisted = _result_payload(
        workspace,
        work_id,
        palari_id,
        attempt_id,
        reason,
        next_action,
        observation,
        _parking_binding(packet, claim),
        before_digest,
        after_digest,
        resumed=False,
        claim_release=None,
    )
    current_observation = _normalize_retry_observation(
        _observe_repository(store.data_path, packet, claim),
        observation,
        store.data_path,
    )
    if current_observation != observation:
        raise WorkspaceError(
            f"work {work_id} was durably parked, but repository state changed during "
            "parking; the claim remains active for inspection"
        )
    if _after_persist is not None:
        _after_persist(persisted)

    parked_workspace = Workspace.load(workspace_path)
    release = release_agent(
        parked_workspace,
        workspace_path,
        work_id,
        palari_id,
        _expected_claim=claim,
        _after_lease_release=_after_lease_release,
    )
    _require_release(release, work_id)
    return _result_payload(
        parked_workspace,
        work_id,
        palari_id,
        attempt_id,
        reason,
        next_action,
        observation,
        _parking_binding(packet, claim),
        before_digest,
        after_digest,
        resumed=False,
        claim_release=release,
    )


def _resume_parked_release(
    store: WorkspaceStore,
    work_record: dict[str, Any],
    attempt: dict[str, Any],
    claim: dict[str, Any],
    packet: dict[str, Any],
    work_id: str,
    palari_id: str,
    reason: str,
    next_action: str,
    after_lease_release: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any]:
    """Finish release after an exact prior parking mutation."""

    if work_record.get("status") != "blocked" or work_record.get("current_attempt") != attempt.get(
        "id"
    ):
        raise WorkspaceError(
            f"cannot resume parking {work_id}: work does not identify the blocked parking attempt"
        )
    parking = _parking_result(attempt)
    expected_binding = _parking_binding(packet, claim)
    if parking.get("reason") != reason or parking.get("next_action") != next_action:
        raise WorkspaceError(
            f"cannot resume parking {work_id}: reason or next action differs from the durable record"
        )
    if parking.get("packet") != expected_binding:
        raise WorkspaceError(
            f"cannot resume parking {work_id}: claim state changed; "
            "the claimed packet binding differs from the durable record"
        )
    observation = _observe_repository(store.data_path, packet, claim)
    recorded_observation = parking.get("observation")
    if not isinstance(recorded_observation, dict):
        raise WorkspaceError(f"parking attempt {attempt.get('id')} has malformed observation metadata")
    observation = _normalize_retry_observation(
        observation,
        recorded_observation,
        store.data_path,
    )
    if observation != recorded_observation:
        raise WorkspaceError(
            f"cannot resume parking {work_id}: repository state changed after the durable parking record"
        )
    _assert_attempt_binding(attempt, work_id, palari_id, claim, parking, observation)

    metadata = _parking_metadata(str(attempt["id"]), work_id, palari_id, reason)
    _recover_matching_pending_journal(store, metadata)
    journal = _current_journal(store.data_path)
    current_digest = str(workspace_digest(store.data) or "")
    parked_workspace = validate_data(store.data_path, store.data)
    release = release_agent(
        parked_workspace,
        store.data_path,
        work_id,
        palari_id,
        _expected_claim=claim,
        _allow_missing_lease=True,
        _after_lease_release=after_lease_release,
    )
    _require_release(release, work_id)
    return _result_payload(
        parked_workspace,
        work_id,
        palari_id,
        str(attempt["id"]),
        reason,
        next_action,
        observation,
        expected_binding,
        str(parking.get("workspace_digest_before") or ""),
        current_digest,
        resumed=True,
        claim_release=release,
        journal=journal,
    )


def _owned_claim(
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    *,
    allow_released_lease: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    claim = read_claim(workspace_path, work_id)
    if claim is None:
        raise WorkspaceError(
            f"cannot park {work_id}: an owned execute claim is required; no claim exists"
        )
    error = claim_integrity_error(
        workspace_path,
        work_id,
        claim,
        allow_released_lease=allow_released_lease,
    )
    if error:
        if allow_released_lease:
            raise WorkspaceError(
                f"cannot resume parking {work_id}: claim state changed: {error}"
            )
        raise WorkspaceError(f"cannot park {work_id}: active claim is invalid: {error}")
    if claim.get("claimed_by") != palari_id:
        raise WorkspaceError(
            f"cannot park {work_id}: claim belongs to {claim.get('claimed_by', 'unknown')}, "
            f"not {palari_id}"
        )
    if claim.get("mode") != "execute":
        raise WorkspaceError(
            f"cannot park {work_id}: claim mode is {claim.get('mode', 'unknown')}, not execute"
        )
    packet = read_claim_packet(workspace_path, claim)
    return claim, packet


def _ensure_journal(workspace_path: Path | str, palari_id: str) -> None:
    data_path = workspace_file_path(workspace_path)
    if not journal_file_path(data_path).exists():
        raise WorkspaceError(
            "cannot park work without an activated governance journal; next action: "
            f"palari history --checkpoint --actor {palari_id} "
            "--reason 'Activate journal before parking legacy work' --json"
        )
    report = verify_workspace_journal(data_path)
    if not (
        report.get("chain_valid")
        and report.get("writable")
        and report.get("current_workspace_digest") == report.get("replay_workspace_digest")
    ):
        diagnostic = next(iter(report.get("errors") or report.get("diagnostics") or []), {})
        message = diagnostic.get("message") or report.get("status") or "journal is not writable"
        raise WorkspaceError(f"cannot park work without a current governance journal: {message}")


def _recover_matching_pending_journal(
    store: WorkspaceStore,
    metadata: MutationMetadata,
) -> None:
    try:
        pending = pending_workspace_journal_context(store.data_path)
    except JournalError as exc:
        raise WorkspaceError(f"cannot inspect pending parking journal transaction: {exc.message}") from exc
    if pending is None:
        return
    prepared = pending.get("prepare")
    if not isinstance(prepared, dict):
        raise WorkspaceError("pending parking journal context is malformed")
    expected_metadata = metadata.as_dict()
    actual_metadata = prepared.get("metadata")
    if not isinstance(actual_metadata, dict):
        raise WorkspaceError("pending parking journal metadata is malformed")
    expected_identity = {key: value for key, value in expected_metadata.items() if key != "timestamp"}
    actual_identity = {key: value for key, value in actual_metadata.items() if key != "timestamp"}
    if actual_identity != expected_identity:
        raise WorkspaceError("a different governance journal mutation is pending; inspect it first")
    if (
        prepared.get("after_projection") != store.data
        or prepared.get("after_workspace_digest") != workspace_digest(store.data)
    ):
        raise WorkspaceError("pending parking journal projection does not match the workspace")
    # write_store delegates to transact, which recognizes this exact prepared
    # mutation and appends only its missing commit marker.
    write_store(store, metadata=metadata)


def _current_journal(data_path: Path) -> dict[str, Any]:
    report = verify_workspace_journal(data_path)
    if not (
        report.get("chain_valid")
        and report.get("writable")
        and report.get("current_workspace_digest") == report.get("replay_workspace_digest")
    ):
        diagnostic = next(iter(report.get("errors") or report.get("diagnostics") or []), {})
        message = diagnostic.get("message") or report.get("status") or "journal is not current"
        raise WorkspaceError(f"cannot release parked claim: {message}")
    return {
        "journal_file": report.get("journal_file", ""),
        "record_count": report.get("record_count", 0),
        "head_record_digest": report.get("head_record_digest"),
        "workspace_digest": report.get("current_workspace_digest"),
    }


def _parking_record(
    reason: str,
    next_action: str,
    packet: dict[str, Any],
    claim: dict[str, Any],
    observation: dict[str, Any],
    before_digest: str,
) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "reason": reason,
        "next_action": next_action,
        "packet": _parking_binding(packet, claim),
        "workspace_digest_before": before_digest,
        "observation": observation,
        "authority_non_claims": [
            "no-receipt",
            "no-evidence",
            "no-review",
            "no-human-decision",
            "no-acceptance",
            "no-outcome",
            "no-convergence",
        ],
    }


def _parking_binding(packet: dict[str, Any], claim: dict[str, Any]) -> dict[str, str]:
    return {
        "packet_id": str(packet.get("packet_id") or ""),
        "packet_digest": _json_digest(packet),
        "context_hash": str(packet.get("context_hash") or ""),
        "packet_path": str(claim.get("packet_path") or ""),
        "session_contract_digest": str(claim.get("session_contract_digest") or ""),
        "claim_session": str(claim.get("claim_session") or ""),
        "claim_workspace_file_hash": str(claim.get("workspace_file_hash") or ""),
        "git_lease_version": str(claim.get("git_lease_version") or ""),
        "git_lease_ref": str(claim.get("git_lease_ref") or ""),
        "git_lease_oid": str(claim.get("git_lease_oid") or ""),
        "workspace_fingerprint": str(claim.get("workspace_fingerprint") or ""),
    }


def _blocked_attempt(
    attempt_id: str,
    work_id: str,
    palari_id: str,
    packet: dict[str, Any],
    claim: dict[str, Any],
    observation: dict[str, Any],
    parking_record: dict[str, Any],
) -> dict[str, Any]:
    allowed_paths = list(packet.get("allowed_paths", {}).get("write", []))
    head_sha = str(observation.get("head_sha") or "")
    base_sha = str(observation.get("base_sha") or "")
    record: dict[str, Any] = {
        "id": attempt_id,
        "work_item_id": work_id,
        "actor": palari_id,
        "status": "blocked",
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed_files": list(observation.get("inside_write_boundary") or []),
        "allowed_paths": allowed_paths,
        "claim_id": str(claim.get("claim_session") or claim.get("packet_id") or ""),
        "claim_expires_at": str(claim.get("lease_expires_at") or ""),
        "cleanliness": _cleanliness(observation),
        "result": _canonical_json(parking_record),
        "started_at": str(claim.get("claimed_at") or ""),
    }
    if head_sha and head_sha != base_sha:
        record["commits"] = [head_sha]
    return record


def _assert_attempt_binding(
    attempt: dict[str, Any],
    work_id: str,
    palari_id: str,
    claim: dict[str, Any],
    parking: dict[str, Any],
    observation: dict[str, Any],
) -> None:
    expected = {
        "work_item_id": work_id,
        "actor": palari_id,
        "status": "blocked",
        "base_sha": observation.get("base_sha", ""),
        "head_sha": observation.get("head_sha", ""),
        "changed_files": observation.get("inside_write_boundary", []),
        "claim_id": str(claim.get("claim_session") or claim.get("packet_id") or ""),
        "claim_expires_at": str(claim.get("lease_expires_at") or ""),
        "result": _canonical_json(parking),
    }
    for field, value in expected.items():
        if attempt.get(field) != value:
            raise WorkspaceError(
                f"cannot resume parking {work_id}: attempt field {field} differs from its binding"
            )


def _parking_result(attempt: dict[str, Any]) -> dict[str, Any]:
    raw = attempt.get("result")
    if not isinstance(raw, str) or not raw:
        raise WorkspaceError(f"parking attempt {attempt.get('id')} has no structured result")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"parking attempt {attempt.get('id')} result is invalid JSON") from exc
    if not isinstance(value, dict) or value.get("schema_version") != RESULT_SCHEMA_VERSION:
        raise WorkspaceError(f"parking attempt {attempt.get('id')} result has unsupported schema")
    if raw != _canonical_json(value):
        raise WorkspaceError(f"parking attempt {attempt.get('id')} result is not canonical")
    return value


def _observe_repository(
    data_path: Path,
    packet: dict[str, Any],
    claim: dict[str, Any],
) -> dict[str, Any]:
    root = git_repo_root(data_path.parent)
    baseline = claim.get("git_baseline")
    baseline = baseline if isinstance(baseline, dict) else {}
    base_sha = str(baseline.get("head_sha") or "")
    errors: list[str] = []
    if root is None:
        return {
            "observation_complete": False,
            "errors": ["Git repository root is unavailable."],
            "base_sha": base_sha,
            "head_sha": "",
            "committed_paths": [],
            "working_tree": {"modified": [], "untracked": [], "deleted": []},
            "all_changed_paths": [],
            "inside_write_boundary": [],
            "outside_write_boundary": [],
            "missing_required_outputs": [],
            "path_intent_mismatches": [],
            "ignored_control_paths": _control_projection_paths(data_path, None),
        }

    current = capture_git_baseline(root)
    head_sha = str(current.get("head_sha") or "")
    errors.extend(str(item) for item in current.get("observation_errors", []) if str(item))
    if current.get("head_observation_error"):
        errors.append(str(current["head_observation_error"]))
    baseline_root = str(baseline.get("git_root") or "")
    if baseline_root and Path(baseline_root).resolve() != root.resolve():
        errors.append("Claim Git baseline belongs to a different repository root.")

    committed_paths, committed_error = _committed_paths(root, base_sha, head_sha)
    if committed_error:
        errors.append(committed_error)
    inspection = inspect_file_changes(
        packet,
        git_diff=True,
        cwd=root,
        git_baseline=baseline,
    )
    if inspection is None:
        inspection = {}
        errors.append("Working-tree change inspection was unavailable.")
    errors.extend(str(item) for item in inspection.get("observation_errors", []) if str(item))

    ignored = _control_projection_paths(data_path, root)
    working = {
        "modified": _without_ignored(inspection.get("modified_files", []), ignored),
        "untracked": _without_ignored(inspection.get("untracked_files", []), ignored),
        "deleted": _without_ignored(inspection.get("deleted_files", []), ignored),
    }
    working_paths = sorted({path for values in working.values() for path in values})
    all_paths = sorted(set(committed_paths) | set(working_paths))
    allowed = list(packet.get("allowed_paths", {}).get("write", []))
    inside = [
        path
        for path in all_paths
        if canonical_path_allowed(path, allowed, root=root)
    ]
    outside = [path for path in all_paths if path not in inside]
    invalid = [
        str(path)
        for path in inspection.get("invalid_changed_paths", [])
        if str(path) not in outside
    ]
    outside.extend(invalid)
    observation_complete = bool(
        current.get("observation_complete")
        and inspection.get("observation_complete")
        and not errors
    )
    return {
        "observation_complete": observation_complete,
        "errors": sorted(dict.fromkeys(errors)),
        "base_sha": base_sha,
        "head_sha": head_sha,
        "committed_paths": committed_paths,
        "working_tree": working,
        "all_changed_paths": all_paths,
        "inside_write_boundary": sorted(inside),
        "outside_write_boundary": sorted(outside),
        "missing_required_outputs": sorted(
            str(item) for item in inspection.get("missing_required_outputs", [])
        ),
        "path_intent_mismatches": list(inspection.get("path_intent_mismatches", [])),
        "ignored_control_paths": ignored,
    }


def _committed_paths(root: Path, base_sha: str, head_sha: str) -> tuple[list[str], str]:
    if not base_sha or not head_sha:
        return [], "Claim baseline or current Git HEAD is unavailable."
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", base_sha, head_sha],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    if ancestor.returncode != 0:
        detail = ancestor.stderr.decode(errors="replace").strip()
        return [], detail or "Current Git HEAD does not descend from the claim baseline."
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
            f"{base_sha}..{head_sha}",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        return [], detail or "Could not inspect committed paths since the claim baseline."
    paths: list[str] = []
    for field in result.stdout.split(b"\0"):
        if not field:
            continue
        raw = field.decode(errors="surrogateescape")
        try:
            path = validate_workspace_path(raw)
        except ValueError as exc:
            return [], f"Git reported an unsafe committed path {raw!r}: {exc}"
        if path != raw:
            return [], f"Git reported a non-canonical committed path {raw!r}."
        paths.append(path)
    return sorted(dict.fromkeys(paths)), ""


def _normalize_retry_observation(
    current: dict[str, Any],
    recorded: dict[str, Any],
    data_path: Path,
) -> dict[str, Any]:
    """Remove only the workspace projection change created by parking itself."""

    normalized = json.loads(_canonical_json(current))
    root = git_repo_root(data_path.parent)
    if root is None:
        return normalized
    try:
        workspace_path = data_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return normalized
    recorded_working = recorded.get("working_tree")
    if not isinstance(recorded_working, dict):
        return normalized
    recorded_paths = {
        str(path)
        for values in recorded_working.values()
        if isinstance(values, list)
        for path in values
    }
    if workspace_path in recorded_paths:
        return normalized
    working = normalized.get("working_tree")
    if isinstance(working, dict):
        for key in ("modified", "untracked", "deleted"):
            values = working.get(key)
            if isinstance(values, list):
                working[key] = [path for path in values if path != workspace_path]
    committed = set(normalized.get("committed_paths") or [])
    working_paths = {
        path
        for values in (working or {}).values()
        if isinstance(values, list)
        for path in values
    }
    all_paths = sorted(committed | working_paths)
    normalized["all_changed_paths"] = all_paths
    for field in ("inside_write_boundary", "outside_write_boundary"):
        values = normalized.get(field)
        if isinstance(values, list):
            normalized[field] = [path for path in values if path != workspace_path]
    return normalized


def _control_projection_paths(data_path: Path, root: Path | None) -> list[str]:
    if root is None:
        return [
            ".palari/governance-journal.v1.jsonl",
            ".palari/history.jsonl",
            ".palari/claims/**",
            ".palari/locks/**",
            ".palari/packets/**",
            ".palari/verification/**",
        ]
    workspace_root = data_path.parent.resolve()
    try:
        prefix = workspace_root.relative_to(root.resolve()).as_posix()
    except ValueError:
        return []
    base = f"{prefix}/" if prefix != "." else ""
    return [
        f"{base}.palari/governance-journal.v1.jsonl",
        f"{base}.palari/history.jsonl",
        f"{base}.palari/claims/**",
        f"{base}.palari/locks/**",
        f"{base}.palari/packets/**",
        f"{base}.palari/verification/**",
    ]


def _without_ignored(values: Any, ignored: list[str]) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted(
        str(item)
        for item in values
        if str(item) and not _matches_ignored_control_path(str(item), ignored)
    )


def _matches_ignored_control_path(path: str, ignored: list[str]) -> bool:
    for pattern in ignored:
        if pattern.endswith("/**"):
            if path.startswith(pattern.removesuffix("**")):
                return True
        elif path == pattern:
            return True
    return False


def _parking_attempt_id(work_id: str, claim: dict[str, Any]) -> str:
    seed = "\0".join(
        (
            work_id,
            str(claim.get("claim_session") or claim.get("packet_id") or ""),
            str(claim.get("context_hash") or ""),
        )
    )
    suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24].upper()
    return f"ATTEMPT-PARK-{suffix}"


def _parking_metadata(
    attempt_id: str,
    work_id: str,
    palari_id: str,
    reason: str,
) -> MutationMetadata:
    return MutationMetadata(
        command="agent release",
        actor=palari_id,
        action="parked",
        timestamp=utc_timestamp(),
        objects=(
            {"type": "attempt", "collection": "attempts", "id": attempt_id},
            {"type": "work", "collection": "work_items", "id": work_id},
        ),
        reason=reason,
    )


def _result_payload(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    attempt_id: str,
    reason: str,
    next_action: str,
    observation: dict[str, Any],
    packet_binding: dict[str, str],
    before_digest: str,
    after_digest: str,
    *,
    resumed: bool,
    claim_release: dict[str, Any] | None,
    journal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "parked",
        "parked": True,
        "resumed": resumed,
        "workspace": workspace.name,
        "work_item": work_id,
        "parked_by": palari_id,
        "attempt_id": attempt_id,
        "reason": reason,
        "next_action": next_action,
        "packet_head_digest_changes": {
            "packet": packet_binding,
            "base_sha": observation.get("base_sha", ""),
            "head_sha": observation.get("head_sha", ""),
            "workspace_digest_before": before_digest,
            "workspace_digest_after": after_digest,
            "observation": observation,
        },
        "journal": journal or {
            "journal_file": ".palari/governance-journal.v1.jsonl",
            "workspace_digest": after_digest,
        },
        "claim_released": bool(claim_release and claim_release.get("released")),
        "claim_release": claim_release,
        "authority_created": {
            "receipt": False,
            "evidence": False,
            "review": False,
            "human_decision": False,
            "acceptance": False,
            "outcome": False,
            "convergence": False,
        },
        "message": (
            f"Work item {work_id} is durably parked as blocked; "
            "no completion or acceptance authority was created."
        ),
    }


def _cleanliness(observation: dict[str, Any]) -> str:
    if not observation.get("observation_complete"):
        return "unverified"
    working = observation.get("working_tree")
    if isinstance(working, dict) and any(working.get(key) for key in working):
        return "dirty"
    return "clean"


def _require_release(release: dict[str, Any], work_id: str) -> None:
    if not release.get("released"):
        raise WorkspaceError(
            f"work {work_id} was durably parked, but claim release could not be confirmed"
        )


def _record(store: WorkspaceStore, collection: str, record_id: str) -> dict[str, Any]:
    record = _optional_record(store, collection, record_id)
    if record is None:
        label = "work" if collection == "work_items" else collection.rstrip("s")
        raise WorkspaceError(f"{label} not found: {record_id}")
    return record


def _optional_record(
    store: WorkspaceStore,
    collection: str,
    record_id: str,
) -> dict[str, Any] | None:
    return next(
        (item for item in _records(store, collection) if item.get("id") == record_id),
        None,
    )


def _current_parking_attempt(
    store: WorkspaceStore,
    work_record: dict[str, Any],
    work_id: str,
) -> dict[str, Any] | None:
    attempt_id = str(work_record.get("current_attempt") or "")
    if not attempt_id.startswith("ATTEMPT-PARK-"):
        return None
    attempt = _optional_record(store, "attempts", attempt_id)
    if attempt is None:
        raise WorkspaceError(
            f"work {work_id} identifies missing parking attempt {attempt_id}"
        )
    if attempt.get("work_item_id") != work_id:
        raise WorkspaceError(
            f"work {work_id} identifies a parking attempt for different work"
        )
    _parking_result(attempt)
    return attempt


def _records(store: WorkspaceStore, collection: str) -> list[dict[str, Any]]:
    value = store.data.get(collection)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise WorkspaceError(f"{collection} must be an inline list of records for agent parking")
    return value


def _required_text(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise WorkspaceError(f"agent parking requires a non-empty {label}")
    return normalized


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_digest(value: Any) -> str:
    encoded = _canonical_json(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
