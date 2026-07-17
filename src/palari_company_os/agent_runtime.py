from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
from .pcaw_canonical import CanonicalJSONError, strict_json_loads
from .store import workspace_file_path
from .transition_checks import assert_transition_allowed
from .workspace import Workspace, WorkspaceError


CLAIM_SCHEMA_VERSION = "palari.agent_claim.v2"
LEGACY_CLAIM_SCHEMA_VERSION = "palari.agent_claim.v1"
GIT_WITNESS_VERSION = "palari.git_claim_witness.v1"
GIT_LEASE_VERSION = "palari.git_claim_lease.v1"
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
    session_contract = compile_agent_session_contract(packet)
    now = _timestamp()
    expires = _timestamp_after(minutes=max(1, lease_minutes))
    packet_path = _packet_path(data_path, packet["packet_id"])
    contract_path = _session_contract_path(data_path, session_contract["contract_id"])
    claim_path = _claim_path(data_path, work_id)
    baseline_path = _baseline_path(data_path, work_id)
    lock_path = _acquire_claim_lock(data_path, work_id)
    acquired_lease: dict[str, str] | None = None
    try:
        existing = read_claim(workspace_path, work_id)
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
        else:
            git_baseline = persisted_baseline["git_baseline"]
            git_witness_ref = str(persisted_baseline.get("git_witness_ref") or "")

        claim_session = str((existing or {}).get("claim_session") or uuid4().hex)
        acquired_lease = _claim_git_lease(
            work_id,
            palari_id,
            mode or "execute",
            expires,
            claim_session,
            data_path,
            git_baseline,
        )

        # A competing worktree must win the repository-shared lease before it
        # can create any durable local baseline or shared witness.  Capturing a
        # baseline is read-only; persistence happens only after the lease CAS.
        if baseline_record is not None:
            git_witness_ref = _create_git_witness(work_id, git_baseline)
            baseline_record["git_witness_version"] = (
                GIT_WITNESS_VERSION if git_witness_ref else ""
            )
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
            "git_witness_version": GIT_WITNESS_VERSION if git_witness_ref else "",
            "git_witness_ref": git_witness_ref,
            "claim_session": claim_session,
        }
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
        lock_path.unlink(missing_ok=True)
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


_RELEASE_BINDING_FIELDS = (
    "schema_version",
    "work_item",
    "claimed_by",
    "mode",
    "claim_session",
    "packet_id",
    "packet_path",
    "context_hash",
    "session_contract_path",
    "session_contract_digest",
    "git_baseline_hash",
    "git_baseline_path",
    "git_witness_version",
    "git_witness_ref",
    "git_lease_version",
    "git_lease_ref",
    "git_lease_oid",
    "workspace_fingerprint",
    "lease_expires_at",
)


def _assert_release_claim_unchanged(
    work_id: str,
    current: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    changed = [
        field
        for field in _RELEASE_BINDING_FIELDS
        if current.get(field) != expected.get(field)
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
) -> str:
    """Validate claim structure and its immutable persisted Git baseline."""

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
    lease_error = _git_lease_error(claim, allow_missing=allow_released_lease)
    if lease_error:
        return lease_error
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
        if record.get("git_witness_version") != GIT_WITNESS_VERSION:
            raise WorkspaceError(
                f"persisted Git baseline for {work_id} has no supported Git witness"
            )
        if record.get("git_witness_ref") != _git_witness_ref(work_id):
            raise WorkspaceError(
                f"persisted Git baseline for {work_id} has an invalid Git witness ref"
            )
    return record


def _validate_active_claim(claim: dict[str, Any]) -> str:
    schema_version = claim.get("schema_version")
    if schema_version not in {CLAIM_SCHEMA_VERSION, LEGACY_CLAIM_SCHEMA_VERSION}:
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


def _create_git_witness(work_id: str, baseline: dict[str, Any]) -> str:
    root = str(baseline.get("git_root") or "")
    head = str(baseline.get("head_sha") or "")
    if not root or not head:
        return ""
    witness_ref = _git_witness_ref(work_id)
    existing = _git_output(root, ["rev-parse", "--verify", witness_ref])
    if existing:
        if existing != head:
            raise WorkspaceError(
                f"Git witness for {work_id} identifies {existing}, not claim head {head}"
            )
        error = _git_witness_history_error(root, witness_ref, head)
        if error:
            raise WorkspaceError(error)
        return witness_ref
    result = subprocess.run(
        ["git", "-C", root, "update-ref", "--create-reflog", witness_ref, head],
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
    error = _git_witness_history_error(root, witness_ref, head)
    if error:
        raise WorkspaceError(error)
    return witness_ref


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
    return _git_witness_history_error(root, witness_ref, head)


def _git_witness_history_error(root: str, witness_ref: str, head: str) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            root,
            "reflog",
            "show",
            "--format=%H",
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
    if entries[-1] != head:
        return "Git witness history does not start at the persisted claim-start head"
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
        "schema_version": GIT_LEASE_VERSION,
        "work_item": work_id,
        "claimed_by": palari_id,
        "mode": mode,
        "session_id": session_id,
        "workspace_fingerprint": _workspace_fingerprint(data_path),
        "lease_expires_at": expires,
    }
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
            return {
                "work_item": work_id,
                "claimed_by": palari_id,
                "mode": mode,
                "claim_session": session_id,
                "lease_expires_at": expires,
                "git_lease_version": GIT_LEASE_VERSION,
                "git_lease_ref": lease_ref,
                "git_lease_oid": lease_oid,
                "workspace_fingerprint": record["workspace_fingerprint"],
            }
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
    if claim["git_lease_version"] != GIT_LEASE_VERSION:
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
    if not isinstance(value, dict) or set(value) != required:
        raise WorkspaceError(f"Git claim lease {lease_ref} has an invalid contract")
    if not all(isinstance(value[field], str) and value[field] for field in required):
        raise WorkspaceError(f"Git claim lease {lease_ref} has missing values")
    if value["schema_version"] != GIT_LEASE_VERSION or value["work_item"] != work_id:
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
