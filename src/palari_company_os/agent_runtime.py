from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .agent_file_changes import capture_git_baseline
from .agent_packets import build_agent_brief
from .path_policy import resolve_workspace_path, validate_workspace_path
from .store import workspace_file_path
from .transition_checks import assert_transition_allowed
from .workspace import Workspace, WorkspaceError


CLAIM_SCHEMA_VERSION = "palari.agent_claim.v1"


def start_agent(
    workspace: Workspace,
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    lease_minutes: int = 30,
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
    git_baseline = capture_git_baseline(workspace.path)
    claim = {
        "schema_version": CLAIM_SCHEMA_VERSION,
        "work_item": work_id,
        "claimed_by": palari_id,
        "mode": mode or "execute",
        "claimed_at": now,
        "lease_expires_at": expires,
        "packet_id": packet["packet_id"],
        "context_hash": packet["context_hash"],
        "packet_path": _runtime_relative(data_path, _packet_path(data_path, packet["packet_id"])),
        "git_baseline": git_baseline,
        "git_baseline_hash": _git_baseline_hash(git_baseline),
    }

    packet_path = _packet_path(data_path, packet["packet_id"])
    claim_path = _claim_path(data_path, work_id)
    lock_path = _acquire_claim_lock(data_path, work_id)
    try:
        existing = read_claim(workspace_path, work_id)
        if existing and _claim_active(existing) and existing.get("claimed_by") != palari_id:
            raise WorkspaceError(
                f"work {work_id} is already claimed by {existing.get('claimed_by', 'unknown')}"
            )

        _write_json(packet_path, packet)
        _write_json(claim_path, claim)
    finally:
        lock_path.unlink(missing_ok=True)
    packet["start"] = {
        "status": "claimed",
        "would_mutate": True,
        "claim": claim,
        "packet_path": _runtime_relative(data_path, packet_path),
        "claim_path": _runtime_relative(data_path, claim_path),
    }
    return packet


def release_agent(
    workspace: Workspace,
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
) -> dict[str, Any]:
    data_path = workspace_file_path(workspace_path)
    claim_path = _claim_path(data_path, work_id)
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
    claim_path.unlink(missing_ok=True)
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
    claim_error = _validate_active_claim(claim)
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


def claim_is_active(claim: dict[str, Any]) -> bool:
    """Return True while the claim lease has not expired."""
    return _claim_active(claim)


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
        error = _validate_active_claim(claim)
        if error:
            errors.append(f"invalid active claim {path.name}: {error}")
            continue
        if not _claim_active(claim):
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
        contexts.append({"claim": claim, "packet": packet})
    return {"contexts": contexts, "errors": errors}


def _claim_active(claim: dict[str, Any]) -> bool:
    expires = _parse_timestamp(str(claim.get("lease_expires_at") or ""))
    return expires is not None and expires > datetime.now(timezone.utc)


def _packet_path(data_path: Path, packet_id: str) -> Path:
    return _runtime_path(data_path, f".palari/packets/{_safe_file_id(packet_id)}.json")


def _claim_path(data_path: Path, work_id: str) -> Path:
    return _runtime_path(data_path, f".palari/claims/{_safe_file_id(work_id)}.json")


def _claim_lock_path(data_path: Path, work_id: str) -> Path:
    return _runtime_path(data_path, f".palari/claims/{_safe_file_id(work_id)}.lock")


def _acquire_claim_lock(data_path: Path, work_id: str) -> Path:
    path = _claim_lock_path(data_path, work_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise WorkspaceError(f"work {work_id} claim is being updated; retry shortly") from exc
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


def _validate_active_claim(claim: dict[str, Any]) -> str:
    if claim.get("schema_version") != CLAIM_SCHEMA_VERSION:
        return f"unsupported schema_version {claim.get('schema_version', '') or '(missing)'}"
    for field in ("work_item", "claimed_by", "mode", "packet_id", "context_hash", "packet_path"):
        if not isinstance(claim.get(field), str) or not claim[field]:
            return f"{field} is missing"
    if claim["mode"] not in {"execute", "review"}:
        return f"unsupported mode {claim['mode']}"
    if _parse_timestamp(str(claim.get("lease_expires_at") or "")) is None:
        return "lease_expires_at is missing or malformed"
    baseline = claim.get("git_baseline")
    if baseline is not None:
        if not isinstance(baseline, dict):
            return "git_baseline must be an object"
        declared_hash = claim.get("git_baseline_hash")
        if not isinstance(declared_hash, str) or declared_hash != _git_baseline_hash(baseline):
            return "git_baseline does not match git_baseline_hash"
    return ""


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


def _packet_context_hash(packet: dict[str, Any]) -> str:
    stable = {
        key: value for key, value in packet.items() if key not in {"created_at", "context_hash"}
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _git_baseline_hash(baseline: dict[str, Any]) -> str:
    encoded = json.dumps(baseline, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


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
