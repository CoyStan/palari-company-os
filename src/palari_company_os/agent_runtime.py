from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from contextlib import ExitStack
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from shlex import quote
from typing import Any
from uuid import uuid4

from .agent_file_changes import capture_git_baseline
from .agent_packets import build_agent_brief
from .agent_session_contract import (
    compile_agent_session_contract,
    session_contract_error,
    session_contract_summary,
)
from .path_policy import resolve_workspace_path, validate_workspace_path
from .pcaw_canonical import CanonicalJSONError, canonical_sha256, strict_json_loads
from .store import workspace_file_path, workspace_write_lock
from .transition_checks import assert_transition_allowed
from .validation import COLLECTION_FILE_KEYS
from .workspace import Workspace, WorkspaceError


CLAIM_SCHEMA_VERSION = "palari.agent_claim.v2"
LEGACY_CLAIM_SCHEMA_VERSION = "palari.agent_claim.v1"
LEGACY_GIT_WITNESS_VERSION = "palari.git_claim_witness.v1"
GIT_WITNESS_VERSION = "palari.git_claim_witness.v2"
GIT_LEASE_VERSION = "palari.git_claim_lease.v2"
LEGACY_GIT_LEASE_VERSION = "palari.git_claim_lease.v1"
LEGACY_PROJECTION_SNAPSHOT_VERSION = "palari.governance_projection_snapshot.v1"
PROJECTION_SNAPSHOT_VERSION = "palari.governance_projection_snapshot.v2"
PRECLAIM_SCOPE_AUTHORITY_VERSION = "palari.preclaim_scope_authority.v1"
PRECLAIM_SCOPE_CATALOG_VERSION = "palari.preclaim_scope_catalog.v1"
PACKET_RUNTIME_STATE_FIELDS = {
    "blockers",
    "completion_contract",
    "context_hash",
    "created_at",
    "documentation_state",
    "next_allowed_commands",
    "omitted_context",
    "one_sentence_instruction",
    "proof_state",
    "state",
    "status",
}


class ClaimContentionError(WorkspaceError):
    """A bounded, retryable collision while acquiring one work claim."""

    code = "CLAIM_CONTENTION"

    def __init__(self, work_id: str, message: str) -> None:
        super().__init__(message)
        self.work_id = work_id


def start_agent(
    workspace: Workspace,
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    lease_minutes: int = 30,
    *,
    claim_start_head: str = "",
) -> dict[str, Any]:
    packet = build_agent_brief(workspace, work_id, palari_id, mode)
    if packet.get("status") != "ready":
        packet["start"] = {
            "status": "blocked",
            "would_mutate": False,
            "reason": "Agent start only persists packets and claims for ready packets.",
            "claim": None,
            "packet_path": "",
            "claim_path": "",
        }
        return packet
    assert_transition_allowed(
        workspace,
        "agent_start",
        work_id,
        actor=palari_id,
        context={"packet": packet, "mode": mode or "execute"},
    )

    data_path = workspace_file_path(workspace_path)
    now = _timestamp()
    expires = _timestamp_after(minutes=max(1, lease_minutes))
    claim_path = _claim_path(data_path, work_id)
    baseline_path = _baseline_path(data_path, work_id)
    workspace_locks = ExitStack()
    lock_path: Path | None = None
    acquired_lease: dict[str, str] | None = None
    try:
        lock_path = _acquire_claim_lock(data_path, work_id)
        workspace, packet = _current_start_packet(
            data_path,
            work_id,
            palari_id,
            mode or "execute",
            packet,
        )
        assert_transition_allowed(
            workspace,
            "agent_start",
            work_id,
            actor=palari_id,
            context={"packet": packet, "mode": mode or "execute"},
        )
        session_contract = compile_agent_session_contract(packet)
        packet_path = _packet_path(data_path, packet["packet_id"])
        contract_path = _session_contract_path(data_path, session_contract["contract_id"])
        existing = read_claim(workspace_path, work_id)
        active_existing = (
            existing if existing is not None and _claim_active(existing) else None
        )
        if existing and _claim_active(existing) and existing.get("claimed_by") != palari_id:
            raise ClaimContentionError(
                work_id,
                f"work {work_id} is already claimed by {existing.get('claimed_by', 'unknown')}"
            )
        if existing and _claim_active(existing):
            requested_mode = mode or "execute"
            if existing.get("mode") != requested_mode:
                raise WorkspaceError(
                    f"work {work_id} already has an active {existing.get('mode', 'unknown')} "
                    f"claim; release it before starting {requested_mode} mode"
                )
            try:
                existing_packet = _read_claim_packet(data_path, existing)
            except (ValueError, WorkspaceError) as exc:
                raise WorkspaceError(
                    f"work {work_id} active claim packet is invalid: {exc}"
                ) from exc
            packet_error = _validate_claim_packet(existing, existing_packet)
            if packet_error:
                raise WorkspaceError(
                    f"work {work_id} active claim packet is invalid: {packet_error}"
                )
            contract_error = _persisted_session_contract_error(
                data_path,
                existing,
                existing_packet,
            )
            if contract_error:
                raise WorkspaceError(
                    f"work {work_id} active claim session contract is invalid: "
                    f"{contract_error}"
                )
            if _packet_authority_hash(existing_packet) != _packet_authority_hash(packet):
                raise WorkspaceError(
                    f"work {work_id} has an active claim whose packet authority differs "
                    "from the current workspace; release it and route the scope change "
                    "through an authorized handoff before starting a new claim epoch"
                )

        persisted_baseline = _read_persisted_baseline(baseline_path, work_id)
        baseline_record: dict[str, Any] | None = None
        if persisted_baseline is None:
            git_baseline = capture_git_baseline(workspace.path)
            if claim_start_head:
                git_baseline = _baseline_at_claim_start(git_baseline, claim_start_head)
            if _complete_git_baseline(git_baseline):
                git_baseline = _capture_missing_work_scope_baseline(
                    data_path,
                    git_baseline,
                    packet,
                )
            baseline_record = {
                "schema_version": "palari.persisted_git_baseline.v1",
                "work_item": work_id,
                "captured_at": now,
                "git_baseline": git_baseline,
                "git_baseline_hash": _git_baseline_hash(git_baseline),
                "git_witness_version": "",
                "git_witness_ref": "",
            }
            git_witness_ref = ""
            git_witness_version = ""
        else:
            git_baseline = persisted_baseline["git_baseline"]
            git_witness_ref = str(persisted_baseline.get("git_witness_ref") or "")
            git_witness_version = str(
                persisted_baseline.get("git_witness_version") or ""
            )
            witness_error = _git_witness_error(work_id, persisted_baseline)
            if witness_error:
                raise WorkspaceError(
                    f"persisted Git baseline for {work_id}: {witness_error}"
                )

        scope_authority: dict[str, str] | None = None
        if _complete_git_baseline(git_baseline):
            scope_authority = _preclaim_scope_authority_binding(
                data_path, git_baseline, packet
            )
            if scope_authority["baseline_digest"] != scope_authority["current_digest"]:
                raise WorkspaceError(
                    "pre-claim scope authority differs from immutable baseline; "
                    "create a successor work item for the changed contract"
                )

        claim_session = str((active_existing or {}).get("claim_session") or uuid4().hex)
        projection_snapshot = (active_existing or {}).get("governance_projection_snapshot")
        projection_snapshot_captured = False
        if projection_snapshot is None and active_existing is None:
            projection_snapshot = _capture_governance_projection_snapshot(
                data_path,
                git_baseline,
                packet,
                scope_authority=scope_authority,
            )
            projection_snapshot_captured = isinstance(projection_snapshot, dict)
        projection_snapshot_digest = (
            _governance_projection_snapshot_digest(projection_snapshot)
            if isinstance(projection_snapshot, dict)
            else ""
        )
        _, current_packet = _current_start_packet(
            data_path,
            work_id,
            palari_id,
            mode or "execute",
            packet,
        )
        if current_packet.get("context_hash") != packet.get("context_hash"):
            raise WorkspaceError("workspace packet changed while claim was starting; retry safely")
        acquired_lease = _claim_git_lease(
            work_id,
            palari_id,
            mode or "execute",
            expires,
            claim_session,
            data_path,
            git_baseline,
            projection_snapshot_digest,
        )

        workspace_locks.enter_context(workspace_write_lock(data_path))
        (
            workspace,
            packet,
            session_contract,
            packet_path,
            contract_path,
            projection_snapshot,
        ) = _final_start_revalidation(
            data_path,
            work_id,
            palari_id,
            mode or "execute",
            packet,
            git_baseline,
            scope_authority=scope_authority,
            projection_snapshot=projection_snapshot,
            projection_snapshot_captured=projection_snapshot_captured,
            projection_snapshot_digest=projection_snapshot_digest,
        )
        if persisted_baseline is not None:
            witness_error = _git_witness_error(work_id, persisted_baseline)
            if witness_error:
                raise WorkspaceError(
                    f"persisted Git baseline for {work_id}: {witness_error}"
                )
        if projection_snapshot_captured:
            snapshot_head = str(projection_snapshot.get("session_start_head") or "")
            if _exact_git_head(str(git_baseline.get("git_root") or "")) != snapshot_head:
                raise WorkspaceError(
                    "Git HEAD changed while claim was starting; retry safely"
                )
            snapshot_error = governance_projection_snapshot_error(
                data_path,
                git_baseline,
                projection_snapshot,
                require_worktree_match=True,
            )
            if snapshot_error:
                raise WorkspaceError(
                    "governance projection changed while the claim was starting: "
                    + snapshot_error
                )

        if projection_snapshot is not None and not projection_snapshot_captured:
            snapshot_error = governance_projection_snapshot_error(
                data_path,
                git_baseline,
                projection_snapshot,
                require_worktree_match=True,
            )
            if snapshot_error:
                raise WorkspaceError(
                    "governance projection changed after claim start: " + snapshot_error
                )

        # A competing worktree must win the repository-shared lease before it
        # can create any durable local baseline or shared witness.  Capturing a
        # baseline is read-only; persistence happens only after the lease CAS.
        if baseline_record is not None:
            git_witness_ref = _create_git_witness(work_id, git_baseline)
            git_witness_version = _git_witness_version(
                git_baseline,
                git_witness_ref,
            )
            baseline_record["git_witness_version"] = git_witness_version
            baseline_record["git_witness_ref"] = git_witness_ref
            _write_json(baseline_path, baseline_record)

        claim = {
            "schema_version": CLAIM_SCHEMA_VERSION,
            "work_item": work_id,
            "claimed_by": palari_id,
            "mode": mode or "execute",
            "claimed_at": now,
            "lease_expires_at": expires,
            "packet_id": packet["packet_id"],
            "context_hash": packet["context_hash"],
            "workspace_file_hash": _file_hash(data_path),
            "packet_path": _runtime_relative(data_path, packet_path),
            "session_contract_path": _runtime_relative(data_path, contract_path),
            "session_contract_digest": session_contract["contract_digest"],
            "git_baseline": git_baseline,
            "git_baseline_hash": _git_baseline_hash(git_baseline),
            "git_baseline_path": _runtime_relative(data_path, baseline_path),
            "git_witness_version": git_witness_version,
            "git_witness_ref": git_witness_ref,
            "claim_session": claim_session,
            "governance_projection_snapshot": projection_snapshot,
            "governance_projection_snapshot_digest": projection_snapshot_digest,
        }
        if projection_snapshot is None:
            claim.pop("governance_projection_snapshot")
            claim.pop("governance_projection_snapshot_digest")
        claim.update(acquired_lease)

        _write_json(packet_path, packet)
        _write_json(contract_path, session_contract)
        _write_json(claim_path, claim)
    except Exception:
        if acquired_lease is not None:
            _release_git_lease(
                acquired_lease,
                strict=False,
                root=str(git_baseline.get("git_root") or ""),
            )
        raise
    finally:
        if lock_path is not None:
            lock_path.unlink(missing_ok=True)
        workspace_locks.close()
    packet["start"] = {
        "status": "claimed",
        "would_mutate": True,
        "claim": claim,
        "packet_path": _runtime_relative(data_path, packet_path),
        "session_contract_path": _runtime_relative(data_path, contract_path),
        "session_contract": session_contract_summary(session_contract),
        "claim_path": _runtime_relative(data_path, claim_path),
    }
    return packet


def start_next_agent(
    workspace: Workspace,
    workspace_path: Path | str,
    palari_id: str,
    mode: str = "execute",
    lease_minutes: int = 30,
) -> dict[str, Any]:
    """Select and claim the first deterministically safe queue item.

    Selection is a projection of the existing agent-next policy. It does not
    create a second eligibility rule or widen the packet compiled by
    ``start_agent``.
    """

    from .agent_next import build_agent_next

    next_payload = build_agent_next(
        workspace,
        palari_id,
        mode,
        limit=max(1, len(workspace.work_items)),
    )
    ready_candidates = [
        candidate
        for candidate in next_payload.get("candidates", [])
        if candidate.get("can_start")
    ]
    if not ready_candidates:
        return {
            "schema_version": "palari.agent_start_next.v1",
            "workspace": workspace.name,
            "status": "no-ready-work",
            "agent": next_payload.get("agent", {"id": palari_id}),
            "entry": _blocked_start_entry(next_payload),
            "start": {
                "status": "not-started",
                "would_mutate": False,
                "claim": None,
            },
            "next": next_payload,
        }

    contention: list[dict[str, str]] = []
    packet: dict[str, Any] | None = None
    selected: dict[str, Any] | None = None
    for candidate in ready_candidates:
        work_id = str(candidate["work_item_id"])
        try:
            current_workspace = Workspace.load(workspace_path)
            attempted = start_agent(
                current_workspace,
                workspace_path,
                work_id,
                palari_id,
                mode,
                lease_minutes=lease_minutes,
            )
        except WorkspaceError as exc:
            if not _claim_contention(exc, work_id):
                raise
            contention.append({"work_item_id": work_id, "message": str(exc)})
            continue
        if attempted.get("start", {}).get("status") != "claimed":
            contention.append(
                {
                    "work_item_id": work_id,
                    "message": "Candidate was no longer ready when its packet was refreshed.",
                }
            )
            continue
        packet = attempted
        selected = candidate
        break
    if packet is None or selected is None:
        primary = f"palari agent start --next --as {palari_id} --mode {mode} --json"
        return {
            "schema_version": "palari.agent_start_next.v1",
            "workspace": workspace.name,
            "status": "selection-contended",
            "agent": next_payload.get("agent", {"id": palari_id}),
            "entry": {
                "safe": False,
                "state": "contended",
                "owner": palari_id,
                "explanation": "Ready candidates changed or were claimed concurrently.",
                "next_action": primary,
                "next_command": primary,
                "contention": contention,
            },
            "start": {"status": "not-started", "would_mutate": False, "claim": None},
            "next": next_payload,
        }

    work_id = str(selected["work_item_id"])
    packet["entry"] = {
        "safe": packet.get("start", {}).get("status") == "claimed",
        "state": "active" if packet.get("start", {}).get("status") == "claimed" else "blocked",
        "owner": palari_id,
        "selected_work_item": work_id,
        "selection_rank": selected.get("queue_rank"),
        "explanation": packet.get("one_sentence_instruction", ""),
        "next_action": "Work inside the persisted packet, then converge deterministic proof.",
        "next_command": f"palari agent advance {work_id} --as {palari_id} --json",
        "skipped_contention": contention,
    }
    return packet


def _claim_contention(error: WorkspaceError, work_id: str) -> bool:
    return isinstance(error, ClaimContentionError) and error.work_id == work_id


def _blocked_start_entry(next_payload: dict[str, Any]) -> dict[str, Any]:
    """Project the first waiting candidate without inventing its owner."""

    candidates = next_payload.get("candidates", [])
    candidate = candidates[0] if candidates else None
    fallback_command = next(
        iter(next_payload.get("next_allowed_commands", [])),
        "",
    )
    if not isinstance(candidate, dict):
        missing_identity = next(
            (
                blocker
                for blocker in next_payload.get("blockers", [])
                if blocker.get("code") == "MISSING_PALARI"
            ),
            None,
        )
        if missing_identity is not None:
            command = "palari agent next --json"
            return {
                "safe": False,
                "state": "identity-required",
                "owner": "operator",
                "explanation": (
                    f"{missing_identity.get('message', 'Palari identity is not declared')}. "
                    "Choose an existing declared Palari; authority is never auto-assigned."
                ),
                "next_action": command,
                "next_command": command,
            }
        return {
            "safe": False,
            "state": "empty",
            "owner": "none",
            "explanation": "No visible work item is available to claim.",
            "next_action": fallback_command,
            "next_command": fallback_command,
        }
    primary_class = str(
        candidate.get("resolution_summary", {}).get("primary_class") or ""
    )
    owner = {
        "human-authority": "human",
        "independent-review": "reviewer",
        "external-state": "external",
        "automatic-reconciliation": "system",
        "terminal": "none",
    }.get(primary_class, "agent")
    command = str(candidate.get("next_command") or fallback_command)
    return {
        "safe": False,
        "state": str(candidate.get("next_step_type") or "blocked"),
        "owner": owner,
        "selected_work_item": str(candidate.get("work_item_id") or ""),
        "explanation": str(
            candidate.get("why")
            or candidate.get("next_action")
            or "No work item is currently safe to claim."
        ),
        "next_action": command,
        "next_command": command,
    }


def claim_baseline_head(workspace_path: Path | str, work_id: str) -> str:
    """Return a verified persistent claim-start commit for safe worktree migration."""

    data_path = workspace_file_path(workspace_path)
    persisted = _read_persisted_baseline(_baseline_path(data_path, work_id), work_id)
    if persisted is None:
        return ""
    witness_error = _git_witness_error(work_id, persisted)
    if witness_error:
        raise WorkspaceError(f"persisted Git baseline for {work_id}: {witness_error}")
    baseline = persisted["git_baseline"]
    return str(baseline.get("head_sha") or "")


def release_agent(
    workspace: Workspace,
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    *,
    _expected_claim: dict[str, Any] | None = None,
    _allow_missing_lease: bool = False,
    _after_lease_release: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    data_path = workspace_file_path(workspace_path)
    claim_path = _claim_path(data_path, work_id)
    lock_path = _acquire_claim_lock(data_path, work_id)
    try:
        claim = read_claim(workspace_path, work_id)
        if not claim:
            return {
                "schema_version": "palari.agent_release.v1",
                "released": False,
                "status": "not-claimed",
                "workspace": workspace.name,
                "work_item": work_id,
                "released_by": palari_id,
                "claim": None,
                "claim_path": _runtime_relative(data_path, claim_path),
                "message": f"No claim exists for {work_id}.",
            }
        if claim.get("claimed_by") != palari_id:
            raise WorkspaceError(
                f"work {work_id} is claimed by {claim.get('claimed_by', 'unknown')}, not {palari_id}"
            )
        if _expected_claim is not None:
            _assert_release_claim_unchanged(work_id, claim, _expected_claim)
        _release_git_lease(
            claim,
            strict=_claim_active(claim),
            allow_missing=_allow_missing_lease and _expected_claim is not None,
        )
        if _after_lease_release is not None:
            _after_lease_release(claim)

        # The local lock coordinates all compliant same-worktree claim writers.
        # Re-read once more so even an injected/manual replacement between the
        # shared lease CAS and unlink is preserved and diagnosed fail-closed.
        after_release = read_claim(workspace_path, work_id)
        if after_release is not None:
            _assert_release_claim_unchanged(work_id, after_release, claim)
            claim_path.unlink()
    finally:
        lock_path.unlink(missing_ok=True)
    return {
        "schema_version": "palari.agent_release.v1",
        "released": True,
        "status": "released",
        "workspace": workspace.name,
        "work_item": work_id,
        "released_by": palari_id,
        "claim": claim,
        "claim_path": _runtime_relative(data_path, claim_path),
        "message": f"Released claim for {work_id}.",
    }


def _assert_release_claim_unchanged(
    work_id: str,
    current: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    changed = [
        field
        for field in sorted(set(current) | set(expected))
        if (field in current) != (field in expected)
        or current.get(field) != expected.get(field)
    ]
    if changed:
        raise WorkspaceError(
            f"work {work_id} claim state changed ({', '.join(changed)}); "
            "refusing to release a replacement session"
        )


def claim_check(
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    mode: str,
    context_hash: str,
) -> dict[str, Any]:
    claim = read_claim(workspace_path, work_id)
    if not claim:
        return {
            "status": "fail",
            "message": "No active claim exists for this work item. Run agent start first.",
            "claim": None,
            "next_command": f"palari agent start {work_id} --as {palari_id} --mode {mode} --json",
        }
    claim_error = claim_integrity_error(workspace_path, work_id, claim)
    if claim_error:
        return {
            "status": "fail",
            "message": f"Active claim is invalid: {claim_error}. Restart the claim.",
            "claim": claim,
            "next_command": f"palari agent start {work_id} --as {palari_id} --mode {mode} --json",
        }
    if claim.get("claimed_by") != palari_id:
        return {
            "status": "fail",
            "message": f"Work is claimed by {claim.get('claimed_by', 'unknown')}, not {palari_id}.",
            "claim": claim,
            "next_command": f"palari agent release {work_id} --as {claim.get('claimed_by', 'PALARI-ID')} --json",
        }
    if claim.get("mode") != mode:
        return {
            "status": "fail",
            "message": f"Claim mode is {claim.get('mode', '')}, not {mode}.",
            "claim": claim,
            "next_command": f"palari agent start {work_id} --as {palari_id} --mode {mode} --json",
        }
    if not _claim_active(claim):
        return {
            "status": "fail",
            "message": "Claim lease has expired. Run agent start to renew the claim.",
            "claim": claim,
            "next_command": f"palari agent start {work_id} --as {palari_id} --mode {mode} --json",
        }
    if claim.get("context_hash") != context_hash:
        return {
            "status": "fail",
            "message": "Claim context hash differs from the current packet; restart before claiming completion.",
            "claim": claim,
            "next_command": f"palari agent start {work_id} --as {palari_id} --mode {mode} --json",
        }
    packet_error = _persisted_packet_error(workspace_file_path(workspace_path), claim)
    if packet_error:
        return {
            "status": "fail",
            "message": f"Active claim packet is invalid: {packet_error}. Restart the claim.",
            "claim": claim,
            "next_command": f"palari agent start {work_id} --as {palari_id} --mode {mode} --json",
        }
    return {
        "status": "pass",
        "message": "Active claim belongs to this Palari and matches the current packet.",
        "claim": claim,
        "next_command": "",
    }


def read_claim(workspace_path: Path | str, work_id: str) -> dict[str, Any] | None:
    path = _claim_path(workspace_file_path(workspace_path), work_id)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"invalid claim JSON for {work_id}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkspaceError(f"claim file for {work_id} must contain a JSON object")
    if value.get("work_item") != work_id:
        raise WorkspaceError(
            f"claim file for {work_id} identifies work item {value.get('work_item', '') or '(missing)'}"
        )
    return value


def read_claim_packet(
    workspace_path: Path | str,
    claim: dict[str, Any],
) -> dict[str, Any]:
    """Read and boundary-check the exact persisted packet named by a claim."""

    return _read_claim_packet(workspace_file_path(workspace_path), claim)


def claim_is_active(claim: dict[str, Any]) -> bool:
    """Return True while the claim lease has not expired."""
    return _claim_active(claim)


def claim_integrity_error(
    workspace_path: Path | str,
    work_id: str,
    claim: dict[str, Any],
    *,
    allow_released_lease: bool = False,
    allow_durable_parking_transition: bool = False,
) -> str:
    """Validate claim structure and its immutable persisted Git baseline."""

    if allow_durable_parking_transition and not allow_released_lease:
        return "durable parking recovery requires released-lease handling"

    error = _validate_active_claim(claim)
    if error:
        return error
    if claim.get("work_item") != work_id:
        return f"work_item is {claim.get('work_item', '') or '(missing)'}, not {work_id}"
    data_path = workspace_file_path(workspace_path)
    baseline_path = _baseline_path(data_path, work_id)
    expected_relative = _runtime_relative(data_path, baseline_path)
    if claim.get("git_baseline_path") != expected_relative:
        return "git_baseline_path does not identify the persisted baseline"
    try:
        persisted = _read_persisted_baseline(baseline_path, work_id)
    except WorkspaceError as exc:
        return str(exc)
    if persisted is None:
        return "persisted Git baseline is missing"
    if claim.get("git_baseline_hash") != persisted.get("git_baseline_hash"):
        return "claim Git baseline hash differs from the persisted baseline"
    if claim.get("git_baseline") != persisted.get("git_baseline"):
        return "claim Git baseline differs from the persisted baseline"
    if claim.get("git_witness_version") != persisted.get("git_witness_version"):
        return "claim Git witness version differs from the persisted baseline"
    if claim.get("git_witness_ref") != persisted.get("git_witness_ref"):
        return "claim Git witness ref differs from the persisted baseline"
    witness_error = _git_witness_error(work_id, persisted)
    if witness_error:
        return witness_error
    baseline = persisted["git_baseline"]
    if _complete_git_baseline(baseline):
        try:
            baseline_workspace = _scope_authority_workspace_from_git(
                data_path,
                baseline,
            )
            if baseline_workspace.work_item(work_id) is None:
                _scope_authority_catalog_digest(
                    baseline,
                    work_id,
                    str(claim["claimed_by"]),
                    str(claim["mode"]),
                )
        except WorkspaceError as exc:
            return str(exc)
    projection_snapshot = claim.get("governance_projection_snapshot")
    recovery_work_status = ""
    recovery_packet: dict[str, Any] | None = None
    if allow_durable_parking_transition and isinstance(projection_snapshot, dict):
        try:
            recovery_packet = _read_claim_packet(data_path, claim)
        except (ValueError, WorkspaceError) as exc:
            return str(exc)
        packet_error = _validate_claim_packet(claim, recovery_packet)
        if packet_error:
            return packet_error
        work_packet = recovery_packet.get("work_item")
        if not isinstance(work_packet, dict) or not isinstance(
            work_packet.get("status"), str
        ):
            return "packet work_item status is missing"
        recovery_work_status = str(work_packet["status"])
    if isinstance(projection_snapshot, dict):
        snapshot_error = governance_projection_snapshot_error(
            data_path,
            persisted["git_baseline"],
            projection_snapshot,
            require_worktree_match=False,
            parked_work_status_from=recovery_work_status,
        )
        if snapshot_error:
            return snapshot_error
    lease_error = _git_lease_error(claim, allow_missing=allow_released_lease)
    if lease_error:
        return lease_error
    packet = recovery_packet
    if packet is None:
        try:
            packet = _read_claim_packet(data_path, claim)
        except (ValueError, WorkspaceError) as exc:
            return str(exc)
    contract_error = _persisted_session_contract_error(data_path, claim, packet)
    if contract_error:
        return contract_error
    return ""


def git_lease_status(workspace_path: Path | str, work_id: str) -> dict[str, Any]:
    """Inspect the repository-shared active claim for one work item."""

    return git_lease_statuses(workspace_path, [work_id])[work_id]


def git_lease_statuses(
    workspace_path: Path | str,
    work_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Inspect shared claims in one Git ref scan, independent of queue size."""

    data_path = workspace_file_path(workspace_path)
    root = _git_output(str(data_path.parent), ["rev-parse", "--show-toplevel"])
    if not root:
        return {
            work_id: {
                "status": "unavailable",
                "active": False,
                "work_item": work_id,
                "message": (
                    "No Git repository is available for cross-worktree claim coordination."
                ),
            }
            for work_id in work_ids
        }
    listing_result = subprocess.run(
        [
            "git",
            "-C",
            root,
            "for-each-ref",
            "--format=%(refname)\t%(objectname)",
            "refs/palari/leases/",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if listing_result.returncode != 0:
        message = listing_result.stderr.strip() or "git for-each-ref failed"
        return {
            work_id: {
                "status": "invalid",
                "active": False,
                "work_item": work_id,
                "message": f"Cannot inspect cross-worktree claim refs: {message}",
            }
            for work_id in work_ids
        }
    listing = listing_result.stdout.strip()
    ref_oids: dict[str, str] = {}
    for line in listing.splitlines():
        if "\t" in line:
            ref, oid = line.split("\t", 1)
            ref_oids[ref] = oid
    current_fingerprint = _workspace_fingerprint(data_path)
    statuses: dict[str, dict[str, Any]] = {}
    for work_id in work_ids:
        lease_ref = _git_lease_ref(work_id)
        lease_oid = ref_oids.get(lease_ref, "")
        if not lease_oid:
            statuses[work_id] = {
                "status": "unclaimed",
                "active": False,
                "work_item": work_id,
                "lease_ref": lease_ref,
            }
            continue
        try:
            record = _read_git_lease(root, lease_ref, lease_oid, work_id)
        except WorkspaceError as exc:
            statuses[work_id] = {
                "status": "invalid",
                "active": False,
                "work_item": work_id,
                "lease_ref": lease_ref,
                "message": str(exc),
            }
            continue
        expires = _parse_timestamp(str(record.get("lease_expires_at") or ""))
        active = expires is not None and expires > datetime.now(timezone.utc)
        statuses[work_id] = {
            "status": "claimed" if active else "expired",
            "active": active,
            "work_item": work_id,
            "claimed_by": record["claimed_by"],
            "mode": record["mode"],
            "lease_expires_at": record["lease_expires_at"],
            "current_workspace": record["workspace_fingerprint"] == current_fingerprint,
            "lease_ref": lease_ref,
        }
    return statuses


def claims_dir(workspace_path: Path | str) -> Path:
    data_path = workspace_file_path(workspace_path)
    return _runtime_path(data_path, ".palari/claims")


def load_active_claim_contexts(
    workspace_path: Path | str,
    *,
    pin_palari: str = "",
    pin_work: str = "",
) -> dict[str, Any]:
    """Load active claims only when their persisted packet context is intact.

    Hook callers use ``errors`` as a fail-closed diagnostic. An invalid or
    mismatched active claim never contributes write authority.
    """

    contexts: list[dict[str, Any]] = []
    errors: list[str] = []
    data_path = workspace_file_path(workspace_path)
    if not data_path.is_file():
        return {"contexts": [], "errors": []}
    try:
        directory = claims_dir(workspace_path)
    except WorkspaceError as exc:
        return {"contexts": [], "errors": [str(exc)]}
    if not directory.is_dir():
        return {"contexts": [], "errors": []}

    workspace: Workspace | None = None
    workspace_error = ""
    try:
        workspace = Workspace.load(workspace_path)
    except WorkspaceError as exc:
        workspace_error = str(exc)

    for path in sorted(directory.glob("*.json")):
        try:
            relative_claim_path = path.relative_to(data_path.parent).as_posix()
            safe_claim_path = resolve_workspace_path(
                data_path.parent, relative_claim_path, require_exists=True
            )
            claim = _read_json_object(safe_claim_path, "claim")
        except (ValueError, WorkspaceError) as exc:
            errors.append(str(exc))
            continue
        if pin_palari and claim.get("claimed_by") != pin_palari:
            continue
        if pin_work and claim.get("work_item") != pin_work:
            continue
        work_id = str(claim.get("work_item") or "")
        structural_error = _validate_active_claim(claim)
        if structural_error:
            errors.append(f"invalid active claim {path.name}: {structural_error}")
            continue
        if not _claim_active(claim):
            continue
        error = claim_integrity_error(workspace_path, work_id, claim)
        if error:
            errors.append(f"invalid active claim {path.name}: {error}")
            continue
        try:
            packet_relative = validate_workspace_path(str(claim["packet_path"]))
            if not packet_relative.startswith(".palari/packets/"):
                raise ValueError("packet_path must be under .palari/packets")
            packet_path = resolve_workspace_path(
                data_path.parent, packet_relative, require_exists=True
            )
            packet = _read_json_object(packet_path, "packet")
        except (ValueError, WorkspaceError) as exc:
            errors.append(f"invalid active claim {path.name}: {exc}")
            continue
        packet_error = _validate_claim_packet(claim, packet)
        if packet_error:
            errors.append(f"invalid active claim {path.name}: {packet_error}")
            continue
        if claim.get("mode") == "execute":
            if workspace is None:
                errors.append(
                    f"invalid active claim {path.name}: current workspace cannot be loaded: "
                    f"{workspace_error}"
                )
                continue
            current_packet = build_agent_brief(
                workspace,
                str(claim.get("work_item") or ""),
                str(claim.get("claimed_by") or ""),
                "execute",
            )
            if current_packet.get("context_hash") != claim.get("context_hash"):
                errors.append(
                    f"invalid active claim {path.name}: persisted packet authority "
                    "differs from the current workspace packet"
                )
                continue
        contexts.append({"claim": claim, "packet": packet})
    return {"contexts": contexts, "errors": errors}


def _claim_active(claim: dict[str, Any]) -> bool:
    expires = _parse_timestamp(str(claim.get("lease_expires_at") or ""))
    return expires is not None and expires > datetime.now(timezone.utc)


def _packet_path(data_path: Path, packet_id: str) -> Path:
    return _runtime_path(data_path, f".palari/packets/{_safe_file_id(packet_id)}.json")


def _session_contract_path(data_path: Path, contract_id: str) -> Path:
    return _runtime_path(
        data_path,
        f".palari/packets/session-contracts/{_safe_file_id(contract_id)}.json",
    )


def _claim_path(data_path: Path, work_id: str) -> Path:
    return _runtime_path(data_path, f".palari/claims/{_safe_file_id(work_id)}.json")


def _claim_lock_path(data_path: Path, work_id: str) -> Path:
    return _runtime_path(data_path, f".palari/claims/{_safe_file_id(work_id)}.lock")


def _baseline_path(data_path: Path, work_id: str) -> Path:
    return _runtime_path(data_path, f".palari/claims/{_safe_file_id(work_id)}.baseline")


def _acquire_claim_lock(data_path: Path, work_id: str) -> Path:
    path = _claim_lock_path(data_path, work_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ClaimContentionError(
            work_id,
            f"work {work_id} claim is being updated; retry shortly",
        ) from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"{_timestamp()}\n")
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def _runtime_relative(data_path: Path, target: Path) -> str:
    try:
        return target.relative_to(data_path.parent).as_posix()
    except ValueError:
        return target.name


def _runtime_path(data_path: Path, relative: str) -> Path:
    try:
        return resolve_workspace_path(data_path.parent, relative)
    except ValueError as exc:
        raise WorkspaceError(f"unsafe Palari runtime path {relative}: {exc}") from exc


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise WorkspaceError(f"cannot read {label} file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"invalid {label} JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkspaceError(f"{label} file {path} must contain a JSON object")
    return value


def _read_persisted_baseline(path: Path, work_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    record = _read_json_object(path, "persisted Git baseline")
    if record.get("schema_version") != "palari.persisted_git_baseline.v1":
        raise WorkspaceError(f"persisted Git baseline for {work_id} has unsupported schema")
    if record.get("work_item") != work_id:
        raise WorkspaceError(f"persisted Git baseline for {work_id} identifies different work")
    baseline = record.get("git_baseline")
    if not isinstance(baseline, dict):
        raise WorkspaceError(f"persisted Git baseline for {work_id} is malformed")
    if record.get("git_baseline_hash") != _git_baseline_hash(baseline):
        raise WorkspaceError(f"persisted Git baseline for {work_id} does not match its hash")
    if baseline.get("head_sha"):
        if record.get("git_witness_version") not in {
            LEGACY_GIT_WITNESS_VERSION,
            GIT_WITNESS_VERSION,
        }:
            raise WorkspaceError(
                f"persisted Git baseline for {work_id} has no supported Git witness"
            )
        if record.get("git_witness_ref") != _git_witness_ref(work_id):
            raise WorkspaceError(
                f"persisted Git baseline for {work_id} has an invalid Git witness ref"
            )
        if (
            _scope_authority_catalog_hash(baseline, work_id)
            and record.get("git_witness_version") != GIT_WITNESS_VERSION
        ):
            raise WorkspaceError(
                f"persisted Git baseline for {work_id} has no catalog-bound Git witness"
            )
    return record


def _validate_active_claim(claim: dict[str, Any]) -> str:
    schema_version = claim.get("schema_version")
    if schema_version not in (CLAIM_SCHEMA_VERSION, LEGACY_CLAIM_SCHEMA_VERSION):
        return f"unsupported schema_version {claim.get('schema_version', '') or '(missing)'}"
    for field in ("work_item", "claimed_by", "mode", "packet_id", "context_hash", "packet_path"):
        if not isinstance(claim.get(field), str) or not claim[field]:
            return f"{field} is missing"
    if claim["mode"] not in {"execute", "review"}:
        return f"unsupported mode {claim['mode']}"
    if _parse_timestamp(str(claim.get("lease_expires_at") or "")) is None:
        return "lease_expires_at is missing or malformed"
    workspace_file_hash = claim.get("workspace_file_hash")
    if workspace_file_hash is not None and not _valid_sha256(workspace_file_hash):
        return "workspace_file_hash is malformed"
    projection_snapshot = claim.get("governance_projection_snapshot")
    projection_digest = claim.get("governance_projection_snapshot_digest")
    lease_version = claim.get("git_lease_version")
    if lease_version in (GIT_LEASE_VERSION, LEGACY_GIT_LEASE_VERSION):
        binding_error = _lease_snapshot_binding_error(claim)
        if binding_error:
            return binding_error
    elif projection_snapshot is not None or (projection_digest is not None and projection_digest != ""):
        return "governance projection snapshot requires a v2 Git claim lease"
    baseline = claim.get("git_baseline")
    if baseline is not None:
        if not isinstance(baseline, dict):
            return "git_baseline must be an object"
        declared_hash = claim.get("git_baseline_hash")
        if not isinstance(declared_hash, str) or declared_hash != _git_baseline_hash(baseline):
            return "git_baseline does not match git_baseline_hash"
    contract_path = claim.get("session_contract_path")
    contract_digest = claim.get("session_contract_digest")
    contract_required = schema_version == CLAIM_SCHEMA_VERSION
    if contract_required or contract_path is not None or contract_digest is not None:
        if not isinstance(contract_path, str) or not contract_path:
            return "session_contract_path is missing"
        try:
            normalized = validate_workspace_path(contract_path)
        except ValueError as exc:
            return f"session_contract_path is unsafe: {exc}"
        if normalized != contract_path or not contract_path.startswith(
            ".palari/packets/session-contracts/"
        ):
            return "session_contract_path must be under .palari/packets/session-contracts"
        if not _valid_sha256(contract_digest):
            return "session_contract_digest is missing or malformed"
    return ""


def _file_hash(path: Path) -> str:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise WorkspaceError(f"cannot hash workspace file for claim: {exc}") from exc
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _valid_sha256(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        return False
    return all(char in "0123456789abcdef" for char in value[7:])


def _validate_claim_packet(claim: dict[str, Any], packet: dict[str, Any]) -> str:
    if packet.get("packet_id") != claim.get("packet_id"):
        return "packet_id does not match the claim"
    if packet.get("context_hash") != claim.get("context_hash"):
        return "packet context_hash does not match the claim"
    if _packet_context_hash(packet) != claim.get("context_hash"):
        return "packet content does not match its context_hash"
    if packet.get("mode") != claim.get("mode"):
        return "packet mode does not match the claim"
    work_item = packet.get("work_item")
    if not isinstance(work_item, dict) or work_item.get("id") != claim.get("work_item"):
        return "packet work_item does not match the claim"
    agent = packet.get("agent")
    if not isinstance(agent, dict) or agent.get("id") != claim.get("claimed_by"):
        return "packet agent does not match the claim"
    if packet.get("status") != "ready":
        return f"packet status is {packet.get('status', '') or '(missing)'}, not ready"
    allowed_paths = packet.get("allowed_paths")
    if not isinstance(allowed_paths, dict):
        return "packet allowed_paths is missing"
    for mode in ("read", "write"):
        paths = allowed_paths.get(mode, [])
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            return f"packet allowed_paths.{mode} must be a list of paths"
        try:
            for item in paths:
                if validate_workspace_path(item) != item:
                    raise ValueError(f"path is not canonical: {item}")
        except ValueError as exc:
            return f"packet allowed_paths.{mode} contains an unsafe path: {exc}"
    return ""


def _persisted_packet_error(data_path: Path, claim: dict[str, Any]) -> str:
    try:
        packet = _read_claim_packet(data_path, claim)
    except (ValueError, WorkspaceError) as exc:
        return str(exc)
    packet_error = _validate_claim_packet(claim, packet)
    if packet_error:
        return packet_error
    return _persisted_session_contract_error(data_path, claim, packet)


def _read_claim_packet(data_path: Path, claim: dict[str, Any]) -> dict[str, Any]:
    packet_relative = validate_workspace_path(str(claim.get("packet_path") or ""))
    if not packet_relative.startswith(".palari/packets/"):
        raise WorkspaceError("packet_path must be under .palari/packets")
    packet_path = resolve_workspace_path(
        data_path.parent, packet_relative, require_exists=True
    )
    return _read_json_object(packet_path, "packet")


def _persisted_session_contract_error(
    data_path: Path,
    claim: dict[str, Any],
    packet: dict[str, Any],
) -> str:
    relative = claim.get("session_contract_path")
    digest = claim.get("session_contract_digest")
    if relative is None and digest is None:
        if claim.get("schema_version") == LEGACY_CLAIM_SCHEMA_VERSION:
            # Genuine v1 claims predate portable session-contract binding. A
            # successful restart upgrades them to v2 and takes the strict path.
            return ""
        return "session contract binding is missing from a v2 claim"
    try:
        normalized = validate_workspace_path(str(relative or ""))
    except ValueError as exc:
        return f"session contract path is unsafe: {exc}"
    if normalized != relative or not normalized.startswith(
        ".palari/packets/session-contracts/"
    ):
        return "session contract path must be under .palari/packets/session-contracts"
    try:
        path = resolve_workspace_path(data_path.parent, normalized, require_exists=True)
        value = strict_json_loads(path.read_bytes())
    except (OSError, ValueError, CanonicalJSONError) as exc:
        return f"cannot read strict session contract: {exc}"
    if not isinstance(value, dict):
        return "session contract must contain a JSON object"
    if value.get("contract_digest") != digest:
        return "session contract digest differs from the claim"
    error = session_contract_error(value, expected_packet=packet)
    if error:
        return f"session contract is invalid: {error}"
    expected_path = _runtime_relative(
        data_path,
        _session_contract_path(data_path, str(value.get("contract_id") or "")),
    )
    if normalized != expected_path:
        return "session contract path does not match contract_id"
    return ""


def _packet_context_hash(packet: dict[str, Any]) -> str:
    stable = {
        key: value for key, value in packet.items() if key not in {"created_at", "context_hash"}
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _packet_authority_hash(packet: dict[str, Any]) -> str:
    """Hash packet authority while excluding proof/read-model runtime state."""

    authority = {
        key: value for key, value in packet.items() if key not in PACKET_RUNTIME_STATE_FIELDS
    }
    encoded = json.dumps(authority, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _git_baseline_hash(baseline: dict[str, Any]) -> str:
    encoded = json.dumps(baseline, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _baseline_at_claim_start(
    captured: dict[str, Any], claim_start_head: str
) -> dict[str, Any]:
    root = str(captured.get("git_root") or "")
    current_head = str(captured.get("head_sha") or "")
    if not root or not current_head or not captured.get("observation_complete"):
        raise WorkspaceError(
            "cannot migrate a claim baseline without a complete Git worktree observation"
        )
    resolved = _git_output(root, ["rev-parse", "--verify", f"{claim_start_head}^{{commit}}"])
    if resolved != claim_start_head:
        raise WorkspaceError("persisted claim-start commit is unavailable in the isolated worktree")
    ancestor = subprocess.run(
        ["git", "-C", root, "merge-base", "--is-ancestor", claim_start_head, current_head],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if ancestor.returncode != 0:
        raise WorkspaceError(
            "isolated base must descend from the persisted claim-start commit"
        )
    migrated = dict(captured)
    migrated["head_sha"] = claim_start_head
    return migrated


def _git_witness_ref(work_id: str) -> str:
    safe = _safe_file_id(work_id).strip("-") or "work"
    digest = hashlib.sha256(work_id.encode("utf-8")).hexdigest()[:12]
    return f"refs/palari/claims/{safe}-{digest}"


def _capture_governance_projection_snapshot(
    data_path: Path,
    baseline: dict[str, Any],
    packet: dict[str, Any],
    *,
    scope_authority: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Bind the claim epoch to the exact local governance projection.

    The immutable Git baseline remains the proof origin.  This second snapshot
    only distinguishes already-committed Palari control-plane projection from
    product output; it never grants those paths to the packet.
    """

    root_text = str(baseline.get("git_root") or "")
    base_sha = str(baseline.get("head_sha") or "")
    session_head = _git_output(root_text, ["rev-parse", "HEAD"])
    if not root_text or not _exact_git_sha(base_sha) or not _exact_git_sha(session_head):
        return None
    root = Path(root_text).resolve()
    try:
        relative_data = data_path.resolve().relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise WorkspaceError(
            f"workspace projection escapes the claim Git repository: {exc}"
        ) from exc
    projection_paths = _governance_projection_paths(relative_data)
    if not _git_ancestor(root_text, base_sha, session_head):
        raise WorkspaceError(
            "claim session head does not descend from the immutable proof baseline"
        )
    touched = _git_range_paths(root_text, base_sha, session_head, projection_paths)
    if touched is None:
        raise WorkspaceError("cannot inspect governance projection commit history")
    if scope_authority is None:
        scope_authority = _preclaim_scope_authority_binding(
            data_path, baseline, packet
        )
    if scope_authority["baseline_digest"] != scope_authority["current_digest"]:
        raise WorkspaceError(
            "pre-claim scope authority differs from immutable baseline; "
            "create a successor work item for the changed contract"
        )
    if not touched:
        return None
    required = packet.get("required_output") or {}
    outputs = required.get("output_targets") or required.get("fallback_write_paths") or []
    if any(
        any(_runtime_path_matches(path, str(target)) for target in outputs if isinstance(target, str))
        for path in touched
    ):
        return None

    files: list[dict[str, str]] = []
    for path in projection_paths:
        payload = _git_blob_bytes(root_text, session_head, path)
        if payload is None:
            return None
        baseline_payload = _git_blob_bytes(root_text, base_sha, path)
        if baseline_payload is None:
            return None
        if (
            path in touched
            and path.endswith(("/.palari/history.jsonl", "/.palari/governance-journal.v1.jsonl"))
            and baseline_payload is not None
            and not payload.startswith(baseline_payload)
        ):
            raise WorkspaceError(
                f"governance projection path {path} is not an append-only extension of its baseline"
            )
        files.append(
            {
                "path": path,
                "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "classification": (
                    "legacy-audit-companion"
                    if path.endswith("/.palari/history.jsonl")
                    else "governance-projection"
                ),
            }
        )

    snapshot: dict[str, Any] = {
        "schema_version": PROJECTION_SNAPSHOT_VERSION,
        "base_sha": base_sha,
        "session_start_head": session_head,
        "changed_paths": sorted(touched),
        "files": files,
        "journal_verification": {},
        "scope_authority": scope_authority,
    }
    if touched:
        from .governance_journal import verify_workspace_journal

        report = verify_workspace_journal(data_path.parent)
        continuity = report.get("continuity") or {}
        if (
            not report.get("ok")
            or report.get("status") != "valid"
            or not report.get("chain_valid")
            or report.get("pending") is not None
            or report.get("current_workspace_digest")
            != report.get("replay_workspace_digest")
            or not continuity.get("historical_continuity")
            or continuity.get("break_sequences")
        ):
            raise WorkspaceError(
                "governance projection cannot be classified because journal continuity is not exact"
            )
        snapshot["journal_verification"] = {
            key: report.get(key)
            for key in (
                "status",
                "chain_valid",
                "head_record_digest",
                "current_workspace_digest",
                "replay_workspace_digest",
                "record_count",
                "committed_transactions",
            )
        }
    error = governance_projection_snapshot_error(
        data_path,
        baseline,
        snapshot,
        require_worktree_match=True,
    )
    if error:
        return None
    return snapshot


def governance_projection_snapshot_error(
    data_path: Path,
    baseline: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    require_worktree_match: bool,
    parked_work_status_from: str = "",
) -> str:
    """Return a fail-closed error for an invalid or stale claim snapshot."""

    if snapshot.get("schema_version") not in {
        LEGACY_PROJECTION_SNAPSHOT_VERSION,
        PROJECTION_SNAPSHOT_VERSION,
    }:
        return "governance projection snapshot has an unsupported schema"
    root_text = str(baseline.get("git_root") or "")
    base_sha = str(baseline.get("head_sha") or "")
    session_head = str(snapshot.get("session_start_head") or "")
    if snapshot.get("base_sha") != base_sha:
        return "governance projection snapshot uses a different proof baseline"
    if not root_text or not _exact_git_sha(base_sha) or not _exact_git_sha(session_head):
        return "governance projection snapshot has incomplete Git identity"
    if not _git_ancestor(root_text, base_sha, session_head):
        return "governance projection snapshot head is not a baseline descendant"
    try:
        root = Path(root_text).resolve()
        relative_data = data_path.resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        return "workspace projection escapes the claim Git repository"
    if snapshot.get("schema_version") == PROJECTION_SNAPSHOT_VERSION:
        authority_error = _governance_projection_scope_authority_error(
            data_path,
            baseline,
            snapshot,
            parked_work_status_from=parked_work_status_from,
        )
        if authority_error:
            return authority_error
    projection_paths = _governance_projection_paths(relative_data)
    files = snapshot.get("files")
    if not isinstance(files, list) or len(files) != len(projection_paths):
        return "governance projection snapshot file manifest is incomplete"
    manifest: dict[str, dict[str, Any]] = {}
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            return "governance projection snapshot file manifest is malformed"
        path = item["path"]
        if path in manifest or path not in projection_paths:
            return "governance projection snapshot file manifest has an unexpected path"
        digest = item.get("sha256")
        if not isinstance(digest, str) or not _valid_sha256(digest):
            return f"governance projection snapshot digest is malformed for {path}"
        manifest[path] = item
    if set(manifest) != set(projection_paths):
        return "governance projection snapshot file manifest does not match exact paths"
    touched = _git_range_paths(root_text, base_sha, session_head, projection_paths)
    declared = snapshot.get("changed_paths")
    if touched is None or not isinstance(declared, list) or sorted(declared) != sorted(touched):
        return "governance projection snapshot changed-path history is not exact"
    for path in projection_paths:
        payload = _git_blob_bytes(root_text, session_head, path)
        if payload is None:
            return f"governance projection snapshot Git blob is unreadable for {path}"
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        if manifest[path].get("sha256") != digest:
            return f"governance projection snapshot Git digest differs for {path}"
        if not require_worktree_match:
            continue
        try:
            lexical_candidate = root / path
            candidate = resolve_workspace_path(root, path, require_exists=True)
            if lexical_candidate.is_symlink() or not candidate.is_file():
                return f"governance projection worktree path is unsafe for {path}"
            current = candidate.read_bytes()
        except (OSError, ValueError) as exc:
            return f"cannot read governance projection worktree path {path}: {exc}"
        if hashlib.sha256(current).hexdigest() != digest.removeprefix("sha256:"):
            return f"governance projection changed after claim start: {path}"
    return ""


def _governance_projection_snapshot_digest(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _governance_projection_paths(relative_data: str) -> list[str]:
    parent = Path(relative_data).parent.as_posix()
    prefix = "" if parent == "." else parent + "/"
    return [
        relative_data,
        f"{prefix}.palari/history.jsonl",
        f"{prefix}.palari/governance-journal.v1.jsonl",
    ]


def _capture_missing_work_scope_baseline(
    data_path: Path,
    baseline: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    """Anchor a newly declared work contract that is not in Git yet."""

    work_id = _scope_authority_packet_identifier(packet, "work_item", "id")
    baseline_workspace = _scope_authority_workspace_from_git(data_path, baseline)
    if baseline_workspace.work_item(work_id) is not None:
        return baseline
    current_workspace = _scope_authority_workspace_from_current(data_path)
    if current_workspace.work_item(work_id) is None:
        raise WorkspaceError(
            f"pre-claim scope authority work is missing: {work_id}"
        )
    anchored = dict(baseline)
    anchored["scope_authority_catalog"] = _scope_authority_catalog(
        current_workspace,
        work_id,
    )
    return anchored


def _preclaim_scope_authority_binding(
    data_path: Path,
    baseline: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, str]:
    work_id = _scope_authority_packet_identifier(packet, "work_item", "id")
    palari_id = _scope_authority_packet_identifier(packet, "agent", "id")
    mode = packet.get("mode")
    if mode not in {"execute", "review"}:
        raise WorkspaceError("pre-claim scope authority packet mode is unsupported")
    return _scope_authority_binding_for(data_path, baseline, work_id, palari_id, mode)


def _governance_projection_scope_authority_error(
    data_path: Path,
    baseline: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    parked_work_status_from: str = "",
) -> str:
    binding = snapshot.get("scope_authority")
    if not isinstance(binding, dict):
        return "governance projection snapshot scope authority binding is missing"
    if binding.get("schema_version") != PRECLAIM_SCOPE_AUTHORITY_VERSION:
        return "governance projection snapshot scope authority binding has an unsupported schema"
    work_id = binding.get("work_item_id")
    palari_id = binding.get("palari_id")
    mode = binding.get("mode")
    baseline_digest = binding.get("baseline_digest")
    current_digest = binding.get("current_digest")
    if not isinstance(work_id, str) or not work_id:
        return "governance projection snapshot scope authority work item is missing"
    if not isinstance(palari_id, str) or not palari_id:
        return "governance projection snapshot scope authority Palari is missing"
    if mode not in {"execute", "review"}:
        return "governance projection snapshot scope authority mode is unsupported"
    if not isinstance(baseline_digest, str) or not _valid_sha256(baseline_digest):
        return "governance projection snapshot scope authority baseline digest is malformed"
    if not isinstance(current_digest, str) or not _valid_sha256(current_digest):
        return "governance projection snapshot scope authority current digest is malformed"
    try:
        actual = _scope_authority_binding_for(data_path, baseline, work_id, palari_id, mode)
    except WorkspaceError as exc:
        return f"cannot verify governance projection scope authority: {exc}"
    if actual["baseline_digest"] != baseline_digest:
        return "governance projection snapshot scope authority baseline digest differs"
    if actual["current_digest"] != current_digest:
        if not parked_work_status_from:
            return "governance projection snapshot scope authority current digest differs"
        try:
            current_workspace = _scope_authority_workspace_from_current(data_path)
            current_work = current_workspace.work_item(work_id)
            if current_work is None or current_work.status != "blocked":
                return "governance projection snapshot scope authority current digest differs"
            normalized_current_digest = _scope_authority_digest(
                current_workspace,
                work_id,
                palari_id,
                mode,
                work_status_override=parked_work_status_from,
            )
        except WorkspaceError as exc:
            return f"cannot verify parked governance projection scope authority: {exc}"
        if normalized_current_digest != current_digest:
            return "governance projection snapshot scope authority current digest differs"
    if baseline_digest != current_digest:
        return "pre-claim scope authority differs from immutable baseline; " \
            "create a successor work item for the changed contract"
    return ""


def _scope_authority_binding_for(
    data_path: Path,
    baseline: dict[str, Any],
    work_id: str,
    palari_id: str,
    mode: str,
) -> dict[str, str]:
    baseline_workspace = _scope_authority_workspace_from_git(data_path, baseline)
    current_workspace = _scope_authority_workspace_from_current(data_path)
    if baseline_workspace.work_item(work_id) is None:
        baseline_digest = _scope_authority_catalog_digest(
            baseline,
            work_id,
            palari_id,
            mode,
        )
    else:
        baseline_digest = _scope_authority_digest(
            baseline_workspace,
            work_id,
            palari_id,
            mode,
        )
    return {
        "schema_version": PRECLAIM_SCOPE_AUTHORITY_VERSION,
        "work_item_id": work_id,
        "palari_id": palari_id,
        "mode": mode,
        "baseline_digest": baseline_digest,
        "current_digest": _scope_authority_digest(
            current_workspace, work_id, palari_id, mode
        ),
    }


def _scope_authority_catalog(
    workspace: Workspace,
    work_id: str,
) -> dict[str, Any]:
    bindings = [
        {
            "palari_id": palari.id,
            "mode": mode,
            "digest": _scope_authority_digest(
                workspace,
                work_id,
                palari.id,
                mode,
            ),
        }
        for palari in sorted(workspace.palaris, key=lambda item: item.id)
        for mode in ("execute", "review")
    ]
    return {
        "schema_version": PRECLAIM_SCOPE_CATALOG_VERSION,
        "work_item_id": work_id,
        "bindings": bindings,
    }


def _scope_authority_catalog_digest(
    baseline: dict[str, Any],
    work_id: str,
    palari_id: str,
    mode: str,
) -> str:
    bindings = _scope_authority_catalog_bindings(baseline, work_id)
    for binding in bindings:
        if (binding["palari_id"], binding["mode"]) == (palari_id, mode):
            return str(binding["digest"])
    raise WorkspaceError(
        f"claim-start authority catalog has no {mode} binding for {palari_id}"
    )


def _scope_authority_catalog_hash(
    baseline: dict[str, Any],
    work_id: str,
) -> str:
    catalog = baseline.get("scope_authority_catalog")
    if catalog is None:
        return ""
    _scope_authority_catalog_bindings(baseline, work_id)
    try:
        return canonical_sha256(catalog)
    except CanonicalJSONError as exc:
        raise WorkspaceError(
            f"claim-start authority catalog cannot be canonicalized: {exc}"
        ) from exc


def _scope_authority_catalog_bindings(
    baseline: dict[str, Any],
    work_id: str,
) -> list[dict[str, str]]:
    catalog = baseline.get("scope_authority_catalog")
    if not isinstance(catalog, dict):
        raise WorkspaceError(
            f"immutable Git baseline predates work {work_id} and has no "
            "claim-start authority catalog"
        )
    if set(catalog) != {"schema_version", "work_item_id", "bindings"}:
        raise WorkspaceError("claim-start authority catalog has unexpected fields")
    if catalog.get("schema_version") != PRECLAIM_SCOPE_CATALOG_VERSION:
        raise WorkspaceError("claim-start authority catalog has an unsupported schema")
    if catalog.get("work_item_id") != work_id:
        raise WorkspaceError("claim-start authority catalog identifies different work")
    bindings = catalog.get("bindings")
    if not isinstance(bindings, list):
        raise WorkspaceError("claim-start authority catalog bindings are malformed")
    expected_order: list[tuple[str, str]] = []
    normalized: list[dict[str, str]] = []
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != {
            "palari_id",
            "mode",
            "digest",
        }:
            raise WorkspaceError("claim-start authority catalog binding is malformed")
        candidate = binding.get("palari_id")
        candidate_mode = binding.get("mode")
        digest = binding.get("digest")
        if not isinstance(candidate, str) or not candidate:
            raise WorkspaceError("claim-start authority catalog Palari is malformed")
        if candidate_mode not in {"execute", "review"}:
            raise WorkspaceError("claim-start authority catalog mode is malformed")
        if not isinstance(digest, str) or not _valid_sha256(digest):
            raise WorkspaceError("claim-start authority catalog digest is malformed")
        key = (candidate, candidate_mode)
        if key in expected_order:
            raise WorkspaceError("claim-start authority catalog binding is duplicated")
        expected_order.append(key)
        normalized.append(
            {
                "palari_id": candidate,
                "mode": candidate_mode,
                "digest": digest,
            }
        )
    if expected_order != sorted(expected_order):
        raise WorkspaceError("claim-start authority catalog bindings are not canonical")
    if not normalized:
        raise WorkspaceError("claim-start authority catalog has no bindings")
    return normalized


def _scope_authority_packet_identifier(
    packet: dict[str, Any], collection: str, field: str
) -> str:
    record = packet.get(collection)
    value = record.get(field) if isinstance(record, dict) else None
    if not isinstance(value, str) or not value:
        raise WorkspaceError(
            f"pre-claim scope authority packet {collection}.{field} is missing"
        )
    return value


def _scope_authority_workspace_from_current(data_path: Path) -> Workspace:
    workspace_root = data_path.parent
    if data_path.is_symlink():
        raise WorkspaceError(
            "workspace.json symlink is unsafe for pre-claim scope authority"
        )
    try:
        payload = data_path.read_bytes()
    except OSError as exc:
        raise WorkspaceError(
            f"cannot read current workspace for pre-claim scope authority: {exc}"
        ) from exc

    def read_collection(relative_path: str) -> bytes:
        try:
            candidate = resolve_workspace_path(
                workspace_root, relative_path, require_exists=True
            )
            if not candidate.is_file():
                raise ValueError("collection path is not a file")
            return candidate.read_bytes()
        except (OSError, ValueError) as exc:
            raise WorkspaceError(
                "cannot read current workspace collection for pre-claim scope authority: "
                f"{relative_path}: {exc}"
            ) from exc

    return _scope_authority_workspace_from_bytes(
        payload,
        data_path,
        read_collection,
        label="current",
    )


def _final_start_revalidation(
    data_path: Path,
    work_id: str,
    palari_id: str,
    mode: str,
    expected_packet: dict[str, Any],
    git_baseline: dict[str, Any],
    *,
    scope_authority: dict[str, str] | None,
    projection_snapshot: dict[str, Any] | None,
    projection_snapshot_captured: bool,
    projection_snapshot_digest: str,
) -> tuple[
    Workspace,
    dict[str, Any],
    dict[str, Any],
    Path,
    Path,
    dict[str, Any] | None,
]:
    """Recheck prepared claim state while the workspace mutation lock is held."""

    workspace, packet = _current_start_packet(
        data_path, work_id, palari_id, mode, expected_packet
    )
    assert_transition_allowed(
        workspace,
        "agent_start",
        work_id,
        actor=palari_id,
        context={"packet": packet, "mode": mode},
    )
    session_contract = compile_agent_session_contract(packet)
    packet_path = _packet_path(data_path, packet["packet_id"])
    contract_path = _session_contract_path(data_path, session_contract["contract_id"])


    final_scope_authority = scope_authority
    if _complete_git_baseline(git_baseline):
        final_scope_authority = _preclaim_scope_authority_binding(
            data_path, git_baseline, packet
        )
        if (
            final_scope_authority["baseline_digest"]
            != final_scope_authority["current_digest"]
        ):
            raise WorkspaceError(
                "pre-claim scope authority differs from immutable baseline; "
                "create a successor work item for the changed contract"
            )
        if scope_authority is None or final_scope_authority != scope_authority:
            raise WorkspaceError(
                "pre-claim scope authority changed while claim was starting; "
                "retry safely"
            )

    if projection_snapshot_captured:
        current_snapshot = _capture_governance_projection_snapshot(
            data_path,
            git_baseline,
            packet,
            scope_authority=final_scope_authority,
        )
        current_digest = (
            _governance_projection_snapshot_digest(current_snapshot)
            if isinstance(current_snapshot, dict)
            else ""
        )
        if current_digest != projection_snapshot_digest:
            raise WorkspaceError(
                "governance projection changed while claim was starting; retry safely"
            )
        projection_snapshot = current_snapshot

    return (
        workspace,
        packet,
        session_contract,
        packet_path,
        contract_path,
        projection_snapshot,
    )

def _current_start_packet(
    data_path: Path,
    work_id: str,
    palari_id: str,
    mode: str,
    expected_packet: dict[str, Any],
) -> tuple[Workspace, dict[str, Any]]:
    """Rebuild the exact current packet before a claim can gain a lease."""

    workspace = _scope_authority_workspace_from_current(data_path)
    packet = build_agent_brief(workspace, work_id, palari_id, mode)
    if packet.get("status") != "ready":
        raise WorkspaceError(
            "workspace packet changed while claim was starting and is no longer ready; "
            "retry safely"
        )
    if packet.get("context_hash") != expected_packet.get("context_hash"):
        raise WorkspaceError("workspace packet changed while claim was starting; retry safely")
    return workspace, packet


def _scope_authority_workspace_from_git(
    data_path: Path, baseline: dict[str, Any]
) -> Workspace:
    root_text = str(baseline.get("git_root") or "")
    base_sha = str(baseline.get("head_sha") or "")
    if not root_text or not _exact_git_sha(base_sha):
        raise WorkspaceError("immutable scope authority baseline has incomplete Git identity")
    try:
        root = Path(root_text).resolve()
        relative_data = data_path.resolve().relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise WorkspaceError(
            f"immutable scope authority workspace escapes the Git repository: {exc}"
        ) from exc
    payload = _git_blob_bytes(root_text, base_sha, relative_data)
    if payload is None:
        raise WorkspaceError(
            "immutable scope authority workspace Git blob is unreadable; "
            "next action: "
            + _missing_workspace_anchor_command(root, relative_data)
        )
    workspace_prefix = Path(relative_data).parent.as_posix()

    def read_collection(relative_path: str) -> bytes:
        try:
            normalized = validate_workspace_path(relative_path)
        except ValueError as exc:
            raise WorkspaceError(
                "immutable scope authority workspace collection path is unsafe: "
                f"{relative_path}: {exc}"
            ) from exc
        git_path = (
            normalized
            if workspace_prefix == "."
            else f"{workspace_prefix}/{normalized}"
        )
        collection_payload = _git_blob_bytes(root_text, base_sha, git_path)
        if collection_payload is None:
            raise WorkspaceError(
                "immutable scope authority workspace collection Git blob is unreadable: "
                + relative_path
            )
        return collection_payload

    return _scope_authority_workspace_from_bytes(
        payload,
        data_path,
        read_collection,
        label="immutable baseline",
    )


def _scope_authority_workspace_from_bytes(
    payload: bytes,
    data_path: Path,
    read_collection: Callable[[str], bytes],
    *,
    label: str,
) -> Workspace:
    try:
        raw = strict_json_loads(payload)
    except (CanonicalJSONError, TypeError) as exc:
        raise WorkspaceError(
            f"{label} workspace is not strict JSON for pre-claim scope authority: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise WorkspaceError(
            f"{label} workspace root is not an object for pre-claim scope authority"
        )
    expanded = _expand_scope_authority_collection_files(raw, read_collection, label)
    try:
        return Workspace.from_raw(expanded, data_path.parent)
    except WorkspaceError as exc:
        raise WorkspaceError(
            f"{label} workspace is invalid for pre-claim scope authority: {exc}"
        ) from exc


def _expand_scope_authority_collection_files(
    raw: dict[str, Any],
    read_collection: Callable[[str], bytes],
    label: str,
) -> dict[str, Any]:
    collection_files = raw.get("collection_files")
    if not collection_files:
        return raw
    if not isinstance(collection_files, dict):
        raise WorkspaceError(
            f"{label} workspace collection_files is invalid for pre-claim scope authority"
        )
    expanded = dict(raw)
    expanded["collection_files"] = {}
    for collection, paths in collection_files.items():
        if collection not in COLLECTION_FILE_KEYS:
            raise WorkspaceError(
                f"{label} workspace collection_files has unknown collection: {collection}"
            )
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            raise WorkspaceError(
                f"{label} workspace collection_files.{collection} is invalid"
            )
        records = raw.get(collection, [])
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise WorkspaceError(f"{label} workspace {collection} is invalid")
        combined = list(records)
        for relative_path in paths:
            try:
                normalized = validate_workspace_path(relative_path)
            except ValueError as exc:
                raise WorkspaceError(
                    f"{label} workspace collection path is unsafe: {relative_path}: {exc}"
                ) from exc
            try:
                included = strict_json_loads(read_collection(normalized))
            except (CanonicalJSONError, TypeError) as exc:
                raise WorkspaceError(
                    f"{label} workspace collection is not strict JSON: {relative_path}: {exc}"
                ) from exc
            if not isinstance(included, list) or not all(
                isinstance(item, dict) for item in included
            ):
                raise WorkspaceError(
                    f"{label} workspace collection is not a list of records: {relative_path}"
                )
            combined.extend(included)
        expanded[collection] = combined
    return expanded


def _scope_authority_digest(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str,
    *,
    work_status_override: str = "",
) -> str:
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"pre-claim scope authority work is missing: {work_id}")
    palari = workspace.palari(palari_id)
    if palari is None:
        raise WorkspaceError(f"pre-claim scope authority Palari is missing: {palari_id}")
    packet = build_agent_brief(workspace, work_id, palari_id, mode)
    agent = _scope_authority_mapping(packet.get("agent"), "agent")
    work_packet = _scope_authority_mapping(packet.get("work_item"), "work item")
    allowed_paths = _scope_authority_mapping(packet.get("allowed_paths"), "allowed paths")
    required_output = _scope_authority_mapping(
        packet.get("required_output"), "required output"
    )
    completion = _scope_authority_mapping(
        packet.get("completion_contract"), "completion contract"
    )
    policy = _scope_authority_mapping(
        packet.get("capability_policy"), "capability policy"
    )
    blockers = packet.get("blockers")
    if not isinstance(blockers, list) or not all(isinstance(item, dict) for item in blockers):
        raise WorkspaceError("pre-claim scope authority packet blockers are malformed")
    actor_eligible = not any(
        item.get("code") == "PALARI_NOT_ASSIGNED" for item in blockers
    )
    actor_authority = {
        "id": _scope_authority_text(agent.get("id"), "agent.id"),
        "name": _scope_authority_text(agent.get("name"), "agent.name"),
        "role": _scope_authority_text(agent.get("role"), "agent.role"),
        "scope": _scope_authority_text(agent.get("scope"), "agent.scope"),
        "mode": mode,
        "default_worker": _scope_authority_text(
            agent.get("default_worker"), "agent.default_worker"
        ),
        "standards": _scope_authority_strings(
            agent.get("standards", []), "agent.standards"
        ),
        "allowed_inputs": _scope_authority_strings(
            palari.allowed_inputs, "agent.allowed_inputs"
        ),
        "forbidden_inputs": _scope_authority_strings(
            palari.forbidden_inputs, "agent.forbidden_inputs"
        ),
        "forbidden_actions": _scope_authority_strings(
            agent.get("forbidden_actions", []), "agent.forbidden_actions"
        ),
        "memory_sources": _scope_authority_strings(
            palari.memory_sources, "agent.memory_sources"
        ),
        "owner_human": _scope_authority_text(
            palari.owner_human, "agent.owner_human"
        ),
    }
    if mode == "execute":
        actor_authority["assigned_or_workbench_allowed"] = actor_eligible
    else:
        actor_authority["review_goal_linked"] = (
            not work.goal or work.goal in palari.linked_goals
        )
    authority = {
        "schema_version": PRECLAIM_SCOPE_AUTHORITY_VERSION,
        "actor": actor_authority,
        "work_item": {
            "id": _scope_authority_text(work_packet.get("id"), "work_item.id"),
            "goal": _scope_authority_text(work.goal, "work_item.goal"),
            "status": _scope_authority_text(
                work_status_override or work.status,
                "work_item.status",
            ),
            "workbench_id": _scope_authority_text(
                work.workbench_id, "work_item.workbench_id"
            ),
            "parent_work_item_id": _scope_authority_text(
                work.parent_work_item_id, "work_item.parent_work_item_id"
            ),
            "dependency_ids": _scope_authority_strings(
                work.dependency_ids, "work_item.dependency_ids"
            ),
            "title": _scope_authority_text(work_packet.get("title", ""), "work_item.title"),
            "risk": _scope_authority_text(work_packet.get("risk", ""), "work_item.risk"),
            "intensity": _scope_authority_text(
                work_packet.get("intensity", ""), "work_item.intensity"
            ),
            "objective": _scope_authority_text(
                work_packet.get("objective", ""), "work_item.objective"
            ),
            "acceptance_target": _scope_authority_text(
                work_packet.get("acceptance_target", ""), "work_item.acceptance_target"
            ),
            "required_approval_count": work_packet.get("required_approval_count"),
            "required_approval_capability": _scope_authority_text(
                work_packet.get("required_approval_capability", ""),
                "work_item.required_approval_capability",
            ),
            "assigned_palari": work.palari,
            "allowed_actions": _scope_authority_strings(
                work.allowed_actions, "work_item.allowed_actions"
            ),
            "conflict_targets": _scope_authority_strings(
                work.conflict_targets, "work_item.conflict_targets"
            ),
            "parallel_policy": _scope_authority_text(
                work.parallel_policy, "work_item.parallel_policy"
            ),
        },
        "allowed_resources": _scope_authority_strings(
            packet.get("allowed_resources"), "allowed_resources"
        ),
        "allowed_paths": {
            "read": _scope_authority_strings(allowed_paths.get("read"), "allowed_paths.read"),
            "write": _scope_authority_strings(
                allowed_paths.get("write"), "allowed_paths.write"
            ),
        },
        "dependencies": _scope_authority_dependencies(packet.get("dependencies")),
        "allowed_sources": _scope_authority_sources(
            workspace,
            packet.get("allowed_sources"),
        ),
        "allowed_capabilities": _scope_authority_capabilities(
            packet.get("allowed_capabilities")
        ),
        "capability_policy": policy,
        "forbidden_actions": _scope_authority_strings(
            packet.get("forbidden_actions"), "forbidden_actions"
        ),
        "required_output": {
            "output_targets": _scope_authority_strings(
                required_output.get("output_targets", []), "required_output.output_targets"
            ),
            "fallback_write_paths": _scope_authority_strings(
                required_output.get("fallback_write_paths", []),
                "required_output.fallback_write_paths",
            ),
            "acceptance_target": _scope_authority_text(
                required_output.get("acceptance_target", ""),
                "required_output.acceptance_target",
            ),
            "verification_expectations": _scope_authority_strings(
                required_output.get("verification_expectations", []),
                "required_output.verification_expectations",
            ),
            "must_not": _scope_authority_strings(
                required_output.get("must_not", []), "required_output.must_not"
            ),
            "path_intents": _scope_authority_records(
                required_output.get("path_intents", []), "required_output.path_intents"
            ),
        },
        "completion_gates": {
            "requires_receipt": completion.get("requires_receipt"),
            "requires_review": completion.get("requires_review"),
            "requires_human_decision": completion.get("requires_human_decision"),
            "external_writes_allowed": completion.get("external_writes_allowed"),
            "external_write_actions": _scope_authority_strings(
                completion.get("external_write_actions", []),
                "completion_contract.external_write_actions",
            ),
        },
    }
    try:
        return canonical_sha256(authority)
    except CanonicalJSONError as exc:
        raise WorkspaceError(
            f"pre-claim scope authority cannot be canonicalized: {exc}"
        ) from exc


def _scope_authority_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkspaceError(f"pre-claim scope authority {label} is malformed")
    return value


def _scope_authority_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise WorkspaceError(f"pre-claim scope authority {label} is malformed")
    return value


def _scope_authority_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise WorkspaceError(f"pre-claim scope authority {label} is malformed")
    return sorted(set(value))


def _scope_authority_records(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise WorkspaceError(f"pre-claim scope authority {label} is malformed")
    try:
        return sorted((dict(item) for item in value), key=canonical_sha256)
    except CanonicalJSONError as exc:
        raise WorkspaceError(
            f"pre-claim scope authority {label} cannot be canonicalized: {exc}"
        ) from exc


def _scope_authority_dependencies(value: Any) -> list[dict[str, str]]:
    records = _scope_authority_records(value, "dependencies")
    normalized: list[dict[str, str]] = []
    for item in records:
        normalized.append(
            {
                "id": _scope_authority_text(item.get("id"), "dependencies[].id"),
                "status": _scope_authority_text(
                    item.get("status"), "dependencies[].status"
                ),
            }
        )
    return sorted(normalized, key=canonical_sha256)


def _scope_authority_sources(
    workspace: Workspace,
    value: Any,
) -> list[dict[str, Any]]:
    records = _scope_authority_records(value, "allowed_sources")
    fields = (
        "id",
        "kind",
        "provider",
        "access_mode",
        "selected",
        "owner_human",
        "allowed_palaris",
        "data_class",
        "authority",
        "steward_human",
        "freshness_sla",
        "redaction_required",
    )
    normalized = []
    for item in records:
        entry = {field: item.get(field) for field in fields}
        source_id = _scope_authority_text(entry.get("id"), "allowed_sources[].id")
        source = workspace.source(source_id)
        if source is None:
            raise WorkspaceError(
                f"pre-claim scope authority source is missing: {source_id}"
            )
        entry["uri"] = source.uri
        entry["external_id"] = source.external_id
        entry["allowed_palaris"] = _scope_authority_strings(
            entry["allowed_palaris"], "allowed_sources[].allowed_palaris"
        )
        normalized.append(entry)
    return sorted(normalized, key=canonical_sha256)


def _scope_authority_capabilities(value: Any) -> list[dict[str, Any]]:
    records = _scope_authority_records(value, "allowed_capabilities")
    fields = (
        "id",
        "kind",
        "provider",
        "status",
        "risk_level",
        "allowed_actions",
        "allowed_palaris",
        "source_ids",
        "policy_ref",
    )
    normalized = []
    for item in records:
        entry = {field: item.get(field) for field in fields}
        entry["allowed_actions"] = _scope_authority_strings(
            entry["allowed_actions"], "allowed_capabilities[].allowed_actions"
        )
        entry["allowed_palaris"] = _scope_authority_strings(
            entry["allowed_palaris"], "allowed_capabilities[].allowed_palaris"
        )
        entry["source_ids"] = _scope_authority_strings(
            entry["source_ids"], "allowed_capabilities[].source_ids"
        )
        normalized.append(entry)
    return sorted(normalized, key=canonical_sha256)


def _runtime_path_matches(path: str, target: str) -> bool:
    normalized_target = target.rstrip("/")
    return path == normalized_target or path.startswith(normalized_target + "/")


def _complete_git_baseline(baseline: dict[str, Any]) -> bool:
    return bool(baseline.get("git_root")) and _exact_git_sha(
        str(baseline.get("head_sha") or "")
    )


def _exact_git_sha(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def _exact_git_head(root: str) -> str:
    if not root:
        return ""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                root,
                "--no-replace-objects",
                "rev-parse",
                "--verify",
                "HEAD^{commit}",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    head = result.stdout.strip() if result.returncode == 0 else ""
    return head if _exact_git_sha(head) else ""


def _git_ancestor(root: str, base_sha: str, head_sha: str) -> bool:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                root,
                "--no-replace-objects",
                "merge-base",
                "--is-ancestor",
                base_sha,
                head_sha,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _git_range_paths(
    root: str,
    base_sha: str,
    head_sha: str,
    candidates: list[str],
) -> list[str] | None:
    if base_sha == head_sha:
        return []
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                root,
                "--no-replace-objects",
                "log",
                "--format=",
                "--name-only",
                "-z",
                "--no-renames",
                f"{base_sha}..{head_sha}",
                "--",
                *candidates,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    allowed = set(candidates)
    paths = {os.fsdecode(item) for item in result.stdout.split(b"\0") if item}
    return sorted(path for path in paths if path in allowed)


def _git_blob_bytes(root: str, revision: str, path: str) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", "-C", root, "--no-replace-objects", "show", f"{revision}:{path}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _missing_workspace_anchor_command(root: Path, relative_data: str) -> str:
    parent = Path(relative_data).parent.as_posix()
    prefix = "" if parent == "." else parent + "/"
    candidates = [
        relative_data,
        f"{prefix}.palari/history.jsonl",
        f"{prefix}.palari/governance-journal.v1.jsonl",
    ]
    paths = [
        path
        for path in candidates
        if not (root / path).is_symlink() and (root / path).is_file()
    ]
    rendered = " ".join(quote(path) for path in paths)
    git = (
        f"git -C {quote(str(root))} -c core.hooksPath=/dev/null "
        "-c commit.gpgSign=false"
    )
    message = quote("palari: anchor governance workspace")
    return (
        f"{git} add -f -- {rendered} && {git} commit --only "
        f"-m {message} -- {rendered}"
    )


def _create_git_witness(work_id: str, baseline: dict[str, Any]) -> str:
    root = str(baseline.get("git_root") or "")
    head = str(baseline.get("head_sha") or "")
    if not root or not head:
        return ""
    witness_ref = _git_witness_ref(work_id)
    catalog_hash = _scope_authority_catalog_hash(baseline, work_id)
    message = f"palari scope authority {catalog_hash}"
    existing = _git_output(root, ["rev-parse", "--verify", witness_ref])
    if existing:
        if existing != head:
            raise WorkspaceError(
                f"Git witness for {work_id} identifies {existing}, not claim head {head}"
            )
        error = _git_witness_history_error(
            root,
            witness_ref,
            head,
            authority_catalog_hash=catalog_hash,
        )
        if error:
            raise WorkspaceError(error)
        return witness_ref
    command = ["git", "-C", root, "update-ref", "--create-reflog"]
    if catalog_hash:
        command.extend(["-m", message])
    command.extend([witness_ref, head])
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise WorkspaceError(
            f"cannot create Git witness for {work_id}: "
            f"{result.stderr.strip() or 'git update-ref failed'}"
        )
    error = _git_witness_history_error(
        root,
        witness_ref,
        head,
        authority_catalog_hash=catalog_hash,
    )
    if error:
        raise WorkspaceError(error)
    return witness_ref


def _git_witness_version(baseline: dict[str, Any], witness_ref: str) -> str:
    if not witness_ref:
        return ""
    return (
        GIT_WITNESS_VERSION
        if baseline.get("scope_authority_catalog") is not None
        else LEGACY_GIT_WITNESS_VERSION
    )


def _git_witness_error(work_id: str, persisted: dict[str, Any]) -> str:
    baseline = persisted.get("git_baseline")
    if not isinstance(baseline, dict):
        return "persisted Git baseline is malformed"
    root = str(baseline.get("git_root") or "")
    head = str(baseline.get("head_sha") or "")
    if not head:
        return ""
    witness_ref = str(persisted.get("git_witness_ref") or "")
    if witness_ref != _git_witness_ref(work_id):
        return "persisted Git witness ref is invalid"
    current = _git_output(root, ["rev-parse", "--verify", witness_ref])
    if current != head:
        return "Git witness does not match the persisted claim-start head"
    version = persisted.get("git_witness_version")
    try:
        catalog_hash = _scope_authority_catalog_hash(baseline, work_id)
    except WorkspaceError as exc:
        return str(exc)
    if catalog_hash and version != GIT_WITNESS_VERSION:
        return "claim-start authority catalog requires a v2 Git witness"
    return _git_witness_history_error(
        root,
        witness_ref,
        head,
        authority_catalog_hash=catalog_hash,
    )


def _git_witness_history_error(
    root: str,
    witness_ref: str,
    head: str,
    *,
    authority_catalog_hash: str = "",
) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            root,
            "reflog",
            "show",
            "--format=%H%x09%gs",
            witness_ref,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    entries = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not entries:
        return "Git witness history is missing or unreadable"
    oldest_head, _, oldest_message = entries[-1].partition("\t")
    if oldest_head != head:
        return "Git witness history does not start at the persisted claim-start head"
    if (
        authority_catalog_hash
        and oldest_message != f"palari scope authority {authority_catalog_hash}"
    ):
        return "Git witness history does not bind the claim-start authority catalog"
    return ""


def _git_lease_ref(work_id: str) -> str:
    safe = _safe_file_id(work_id).strip("-")[:80] or "work"
    digest = hashlib.sha256(work_id.encode("utf-8")).hexdigest()[:12]
    return f"refs/palari/leases/{safe}-{digest}"


def _claim_git_lease(
    work_id: str,
    palari_id: str,
    mode: str,
    expires: str,
    session_id: str,
    data_path: Path,
    baseline: dict[str, Any],
    projection_snapshot_digest: str = "",
) -> dict[str, str]:
    root = str(baseline.get("git_root") or "")
    head = str(baseline.get("head_sha") or "")
    if not root or not head:
        return {}
    lease_ref = _git_lease_ref(work_id)
    foreign_claim = _foreign_registered_claim(root, data_path, work_id)
    if foreign_claim is not None:
        raise ClaimContentionError(
            work_id,
            f"work {work_id} is already claimed by {foreign_claim['claimed_by']} "
            f"in another Git worktree registered locally until "
            f"{foreign_claim['lease_expires_at']}"
        )
    record = {
        "schema_version": (
            GIT_LEASE_VERSION
            if projection_snapshot_digest
            else LEGACY_GIT_LEASE_VERSION
        ),
        "work_item": work_id,
        "claimed_by": palari_id,
        "mode": mode,
        "session_id": session_id,
        "workspace_fingerprint": _workspace_fingerprint(data_path),
        "lease_expires_at": expires,
    }
    if projection_snapshot_digest:
        record["governance_projection_snapshot_digest"] = projection_snapshot_digest
    lease_oid = ""
    for _ in range(4):
        current_oid = _git_output(root, ["rev-parse", "--verify", lease_ref])
        if current_oid:
            current = _read_git_lease(root, lease_ref, current_oid, work_id)
            current_expires = _parse_timestamp(str(current["lease_expires_at"]))
            current_active = (
                current_expires is not None
                and current_expires > datetime.now(timezone.utc)
            )
            if current_active and current["session_id"] != session_id:
                raise ClaimContentionError(
                    work_id,
                    f"work {work_id} is already claimed by {current['claimed_by']} "
                    f"in another Git worktree until {current['lease_expires_at']}"
                )
        if not lease_oid:
            lease_oid = _write_git_blob(root, record)
        expected_oid = current_oid or ("0" * len(lease_oid))
        result = subprocess.run(
            [
                "git",
                "-C",
                root,
                "update-ref",
                "--create-reflog",
                lease_ref,
                lease_oid,
                expected_oid,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            acquired = {
                "work_item": work_id,
                "claimed_by": palari_id,
                "mode": mode,
                "claim_session": session_id,
                "lease_expires_at": expires,
                "git_lease_version": record["schema_version"],
                "git_lease_ref": lease_ref,
                "git_lease_oid": lease_oid,
                "workspace_fingerprint": record["workspace_fingerprint"],
            }
            if projection_snapshot_digest:
                acquired["governance_projection_snapshot_digest"] = (
                    projection_snapshot_digest
                )
            return acquired
    raise ClaimContentionError(
        work_id,
        f"work {work_id} claim changed concurrently; retry safely",
    )


def _foreign_registered_claim(
    root: str,
    data_path: Path,
    work_id: str,
) -> dict[str, Any] | None:
    root_path = Path(root).resolve()
    try:
        relative_data = data_path.resolve().relative_to(root_path)
    except ValueError as exc:
        raise WorkspaceError("workspace is outside its reported Git worktree") from exc
    result = subprocess.run(
        ["git", "-C", root, "worktree", "list", "--porcelain"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise WorkspaceError(
            "cannot inspect registered Git worktrees before claiming work"
        )
    current_data = data_path.resolve()
    for line in result.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        worktree_root = Path(line.removeprefix("worktree ")).resolve()
        candidate_data = worktree_root / relative_data
        if candidate_data.resolve() == current_data:
            continue
        claim_path = (
            candidate_data.parent
            / ".palari"
            / "claims"
            / f"{_safe_file_id(work_id)}.json"
        )
        if not claim_path.exists():
            continue
        resolved_claim = claim_path.resolve()
        if not resolved_claim.is_relative_to(worktree_root) or claim_path.is_symlink():
            raise WorkspaceError(
                f"registered worktree claim path is unsafe for {work_id}"
            )
        claim = _read_json_object(resolved_claim, "registered worktree claim")
        if claim.get("work_item") != work_id:
            raise WorkspaceError(
                f"registered worktree claim file identifies different work than {work_id}"
            )
        structural_error = _validate_active_claim(claim)
        if structural_error:
            raise WorkspaceError(
                f"registered worktree claim for {work_id} is invalid: {structural_error}"
            )
        if _claim_active(claim):
            return claim
    return None


def _release_git_lease(
    claim: dict[str, Any],
    *,
    strict: bool,
    root: str = "",
    allow_missing: bool = False,
) -> None:
    lease_ref = str(claim.get("git_lease_ref") or "")
    lease_oid = str(claim.get("git_lease_oid") or "")
    if not lease_ref and not lease_oid:
        return
    baseline = claim.get("git_baseline")
    if not root and isinstance(baseline, dict):
        root = str(baseline.get("git_root") or "")
    if not root or not lease_ref or not lease_oid:
        if strict:
            raise WorkspaceError("active Git claim lease metadata is incomplete")
        return
    current_oid, ref_error = _git_ref_oid(root, lease_ref)
    if ref_error:
        if strict or allow_missing:
            raise WorkspaceError(ref_error)
        return
    if not current_oid and allow_missing:
        return
    if current_oid != lease_oid:
        if strict:
            raise WorkspaceError(
                "active Git claim lease changed; refusing to release another session"
            )
        return
    try:
        record = _read_git_lease(
            root,
            lease_ref,
            current_oid,
            str(claim.get("work_item") or ""),
        )
    except WorkspaceError:
        if strict:
            raise
        return
    if strict:
        binding_error = _lease_snapshot_binding_error(claim, record)
        if binding_error:
            raise WorkspaceError(
                "active Git claim lease belongs to a different session; refusing release: "
                + binding_error
            )
    expected = {
        "claimed_by": claim.get("claimed_by"),
        "mode": claim.get("mode"),
        "session_id": claim.get("claim_session"),
        "workspace_fingerprint": claim.get("workspace_fingerprint"),
        "lease_expires_at": claim.get("lease_expires_at"),
    }
    if any(record.get(field) != value for field, value in expected.items()):
        if strict:
            raise WorkspaceError(
                "active Git claim lease belongs to a different session; refusing release"
            )
        return
    result = subprocess.run(
        ["git", "-C", root, "update-ref", "-d", lease_ref, lease_oid],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0 and strict:
        raise WorkspaceError(
            f"cannot release Git claim lease: "
            f"{result.stderr.strip() or 'git update-ref failed'}"
        )


def _git_lease_error(
    claim: dict[str, Any],
    *,
    allow_missing: bool = False,
) -> str:
    fields = (
        "git_lease_version",
        "git_lease_ref",
        "git_lease_oid",
        "workspace_fingerprint",
    )
    values = [claim.get(field) for field in fields]
    if not any(values):
        return ""
    if not all(isinstance(value, str) and value for value in values):
        return "Git claim lease metadata is incomplete"
    if claim["git_lease_version"] not in {
        GIT_LEASE_VERSION,
        LEGACY_GIT_LEASE_VERSION,
    }:
        return "Git claim lease version is unsupported"
    work_id = str(claim.get("work_item") or "")
    if claim["git_lease_ref"] != _git_lease_ref(work_id):
        return "Git claim lease ref is invalid"
    baseline = claim.get("git_baseline")
    root = str(baseline.get("git_root") or "") if isinstance(baseline, dict) else ""
    if not root:
        return "Git claim lease has no repository root"
    current_oid, ref_error = _git_ref_oid(root, str(claim["git_lease_ref"]))
    if ref_error:
        return ref_error
    if not current_oid and allow_missing:
        return ""
    if current_oid != claim["git_lease_oid"]:
        return "Git claim lease does not match the active repository lease"
    try:
        record = _read_git_lease(root, claim["git_lease_ref"], current_oid, work_id)
    except WorkspaceError as exc:
        return str(exc)
    binding_error = _lease_snapshot_binding_error(claim, record)
    if binding_error:
        return binding_error
    expected = {
        "claimed_by": claim.get("claimed_by"),
        "mode": claim.get("mode"),
        "session_id": claim.get("claim_session"),
        "workspace_fingerprint": claim.get("workspace_fingerprint"),
        "lease_expires_at": claim.get("lease_expires_at"),
    }
    for field, value in expected.items():
        if (
            field == "mode"
            and record.get(field) == "execute"
            and value == "review"
        ):
            continue
        if record.get(field) != value:
            return f"Git claim lease {field} differs from the local claim"
    return ""


def _lease_snapshot_binding_error(
    claim: dict[str, Any],
    record: dict[str, str] | None = None,
) -> str:
    """Validate the versioned snapshot binding shared by a claim and lease."""

    claim_version = claim.get("git_lease_version")
    if claim_version not in (GIT_LEASE_VERSION, LEGACY_GIT_LEASE_VERSION):
        return "Git claim lease version is unsupported"
    if record is not None and record.get("schema_version") != claim_version:
        return "Git claim lease version differs from the local claim"

    snapshot = claim.get("governance_projection_snapshot")
    digest = claim.get("governance_projection_snapshot_digest")
    if claim_version == LEGACY_GIT_LEASE_VERSION:
        if snapshot is not None or (digest is not None and digest != ""):
            return "legacy Git claim lease cannot carry a governance projection snapshot"
        return ""

    if not isinstance(snapshot, dict):
        return "v2 Git claim lease requires a governance_projection_snapshot"
    if not isinstance(digest, str) or not _valid_sha256(digest):
        return "v2 Git claim lease requires a valid governance_projection_snapshot_digest"
    if _governance_projection_snapshot_digest(snapshot) != digest:
        return "governance projection snapshot does not match its digest"
    if record is not None and record.get("governance_projection_snapshot_digest") != digest:
        return "Git claim lease governance_projection_snapshot_digest differs from the local claim"
    return ""


def _write_git_blob(root: str, record: dict[str, str]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    result = subprocess.run(
        ["git", "-C", root, "hash-object", "-w", "--stdin"],
        input=encoded,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    oid = result.stdout.strip()
    if result.returncode != 0 or not re_fullmatch_git_oid(oid):
        raise WorkspaceError(
            f"cannot create Git claim lease object: "
            f"{result.stderr.strip() or 'git hash-object failed'}"
        )
    return oid


def _read_git_lease(
    root: str,
    lease_ref: str,
    lease_oid: str,
    work_id: str,
) -> dict[str, str]:
    if not re_fullmatch_git_oid(lease_oid):
        raise WorkspaceError(f"Git claim lease {lease_ref} has an invalid object id")
    result = subprocess.run(
        ["git", "-C", root, "cat-file", "blob", lease_oid],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise WorkspaceError(f"Git claim lease {lease_ref} is unreadable")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"Git claim lease {lease_ref} contains invalid JSON") from exc
    required = {
        "schema_version",
        "work_item",
        "claimed_by",
        "mode",
        "session_id",
        "workspace_fingerprint",
        "lease_expires_at",
    }
    if not isinstance(value, dict):
        raise WorkspaceError(f"Git claim lease {lease_ref} has an invalid contract")
    schema_version = value.get("schema_version")
    if schema_version == GIT_LEASE_VERSION:
        required.add("governance_projection_snapshot_digest")
    elif schema_version != LEGACY_GIT_LEASE_VERSION:
        raise WorkspaceError(f"Git claim lease {lease_ref} has an invalid contract")
    if set(value) != required:
        raise WorkspaceError(f"Git claim lease {lease_ref} has an invalid contract")
    if not all(isinstance(value[field], str) and value[field] for field in required):
        raise WorkspaceError(f"Git claim lease {lease_ref} has missing values")
    if value["work_item"] != work_id:
        raise WorkspaceError(f"Git claim lease {lease_ref} identifies different work")
    if value["mode"] not in {"execute", "review"}:
        raise WorkspaceError(f"Git claim lease {lease_ref} has an invalid mode")
    if _parse_timestamp(value["lease_expires_at"]) is None:
        raise WorkspaceError(f"Git claim lease {lease_ref} has an invalid expiry")
    return {field: value[field] for field in required}


def _workspace_fingerprint(data_path: Path) -> str:
    normalized = str(data_path.parent.resolve()).encode("utf-8")
    return f"sha256:{hashlib.sha256(normalized).hexdigest()}"


def re_fullmatch_git_oid(value: str) -> bool:
    return len(value) in {40, 64} and all(
        char in "0123456789abcdef" for char in value
    )


def _git_output(root: str, args: list[str]) -> str:
    if not root:
        return ""
    result = subprocess.run(
        ["git", "-C", root, *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_ref_oid(root: str, ref: str) -> tuple[str, str]:
    result = subprocess.run(
        ["git", "-C", root, "for-each-ref", "--format=%(objectname)", ref],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "git for-each-ref failed"
        return "", f"cannot inspect active Git claim lease: {detail}"
    values = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(values) > 1 or (values and not re_fullmatch_git_oid(values[0])):
        return "", "active Git claim lease ref produced an invalid object id"
    return (values[0] if values else ""), ""


def _safe_file_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _timestamp_after(*, minutes: int) -> str:
    value = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
