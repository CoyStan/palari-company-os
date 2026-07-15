from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .workspace import WorkspaceError


SCHEMA_VERSION = "palari.verification_attestation.v1"
HASH_PREFIX = "sha256:"
_FIELDS = {
    "schema_version",
    "attestation_id",
    "cache_key",
    "profile_id",
    "profile_digest",
    "argv",
    "head_sha",
    "base_sha",
    "changed_paths_digest",
    "cleanliness",
    "source_digest",
    "python",
    "platform",
    "status",
    "exit_code",
    "duration_ms",
    "stdout_digest",
    "stderr_digest",
    "created_at",
}


@dataclass(frozen=True)
class VerificationProfile:
    id: str
    argv: tuple[str, ...]
    timeout_seconds: int = 300

    @property
    def digest(self) -> str:
        return _digest(
            {
                "id": self.id,
                "argv": list(self.argv),
                "timeout_seconds": self.timeout_seconds,
            }
        )


@dataclass(frozen=True)
class VerificationContext:
    head_sha: str
    base_sha: str
    changed_paths: tuple[str, ...]
    cleanliness: str
    source_digest: str
    python: str
    platform: str


def default_context(
    *,
    head_sha: str,
    base_sha: str,
    changed_paths: list[str],
    cleanliness: str,
) -> VerificationContext:
    return VerificationContext(
        head_sha=head_sha,
        base_sha=base_sha,
        changed_paths=tuple(sorted(set(changed_paths))),
        cleanliness=cleanliness,
        source_digest=_digest({"git_head": head_sha}),
        python=_python_identity(),
        platform=_platform_identity(),
    )


def verification_profiles(
    risk: str,
    changed_paths: list[str],
    *,
    python_executable: str | None = None,
) -> tuple[VerificationProfile, ...]:
    """Return executable, shell-free profiles; work-item prose is never executed."""

    python = python_executable or sys.executable
    affected = VerificationProfile(
        "affected",
        (
            python,
            "scripts/verification_profiles.py",
            "affected",
            *tuple(sorted(set(changed_paths))),
        ),
    )
    if risk == "R1":
        return (affected,)
    return (
        VerificationProfile("complete", ("./scripts/verify.sh",), 600),
        VerificationProfile("install-smoke", ("./scripts/install_smoke.sh",), 300),
        VerificationProfile(
            "docs-check",
            ("./bin/palari", "docs", "check", "--json"),
            120,
        ),
    )


def cache_key(profile: VerificationProfile, context: VerificationContext) -> str:
    return _digest(
        {
            "schema_version": SCHEMA_VERSION,
            "profile_id": profile.id,
            "profile_digest": profile.digest,
            "head_sha": context.head_sha,
            "base_sha": context.base_sha,
            "changed_paths_digest": _digest(list(context.changed_paths)),
            "cleanliness": context.cleanliness,
            "source_digest": context.source_digest,
            "python": context.python,
            "platform": context.platform,
        }
    )


def run_or_reuse(
    workspace_path: Path | str,
    repo_root: Path | str,
    profile: VerificationProfile,
    context: VerificationContext,
    *,
    refresh: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> dict[str, Any]:
    if context.cleanliness not in {"clean", "pristine"}:
        raise WorkspaceError("verification requires an exactly clean committed worktree")
    if not context.head_sha or not context.base_sha:
        raise WorkspaceError("verification requires exact base and head commits")

    directory = _cache_directory(Path(workspace_path), create=True)
    key = cache_key(profile, context)
    path = directory / f"{key.removeprefix(HASH_PREFIX)}.json"
    cache_observed = False
    if path.exists() and not refresh:
        attestation = _read_attestation(path)
        errors = attestation_errors(attestation, profile, context)
        if errors:
            raise WorkspaceError(
                "cached verification attestation is invalid: " + "; ".join(errors)
            )
        if attestation["status"] != "passed":
            raise WorkspaceError("cached verification result is not passing; use --refresh-verification")
        # This file is an advisory performance/debugging record, not an
        # authority boundary. A process running as the same OS user can edit
        # it, so a cached pass must never create governed passing evidence.
        # Exact proof that has already been reconciled into the workspace is
        # reused by the advance projection before this function is called.
        cache_observed = True

    started = time.monotonic()
    try:
        result = runner(
            list(profile.argv),
            cwd=Path(repo_root),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=profile.timeout_seconds,
        )
        exit_code = int(result.returncode)
        stdout = bytes(result.stdout or b"")
        stderr = bytes(result.stderr or b"")
        status = "passed" if exit_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = bytes(exc.stdout or b"")
        stderr = bytes(exc.stderr or b"")
        status = "timeout"
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    attestation = {
        "schema_version": SCHEMA_VERSION,
        "attestation_id": f"VERIFY-{profile.id.upper()}-{key[-16:].upper()}",
        "cache_key": key,
        "profile_id": profile.id,
        "profile_digest": profile.digest,
        "argv": list(profile.argv),
        "head_sha": context.head_sha,
        "base_sha": context.base_sha,
        "changed_paths_digest": _digest(list(context.changed_paths)),
        "cleanliness": context.cleanliness,
        "source_digest": context.source_digest,
        "python": context.python,
        "platform": context.platform,
        "status": status,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "stdout_digest": _bytes_digest(stdout),
        "stderr_digest": _bytes_digest(stderr),
        "created_at": _timestamp(),
    }
    _write_attestation(path, attestation)
    return {
        "cache_hit": False,
        "cache_observed": cache_observed,
        "attestation": attestation,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }


def attestation_errors(
    attestation: dict[str, Any],
    profile: VerificationProfile,
    context: VerificationContext,
) -> list[str]:
    errors: list[str] = []
    unknown = sorted(set(attestation) - _FIELDS)
    missing = sorted(_FIELDS - set(attestation))
    if unknown:
        errors.append("unknown fields: " + ", ".join(unknown))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    expected = {
        "schema_version": SCHEMA_VERSION,
        "attestation_id": f"VERIFY-{profile.id.upper()}-{cache_key(profile, context)[-16:].upper()}",
        "cache_key": cache_key(profile, context),
        "profile_id": profile.id,
        "profile_digest": profile.digest,
        "argv": list(profile.argv),
        "head_sha": context.head_sha,
        "base_sha": context.base_sha,
        "changed_paths_digest": _digest(list(context.changed_paths)),
        "cleanliness": context.cleanliness,
        "source_digest": context.source_digest,
        "python": context.python,
        "platform": context.platform,
    }
    for field, value in expected.items():
        if attestation.get(field) != value:
            errors.append(f"{field} does not match the requested verification state")
    if attestation.get("status") not in {"passed", "failed", "timeout"}:
        errors.append("status is unsupported")
    exit_code = attestation.get("exit_code")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        errors.append("exit_code must be an integer")
    elif (attestation.get("status") == "passed") != (exit_code == 0):
        errors.append("status contradicts exit_code")
    if not isinstance(attestation.get("duration_ms"), int):
        errors.append("duration_ms must be an integer")
    elif attestation["duration_ms"] < 0:
        errors.append("duration_ms must not be negative")
    created_at = attestation.get("created_at")
    if not isinstance(created_at, str) or not created_at.endswith("Z"):
        errors.append("created_at must be an unambiguous UTC timestamp")
    else:
        try:
            datetime.fromisoformat(created_at.removesuffix("Z") + "+00:00")
        except ValueError:
            errors.append("created_at must be an unambiguous UTC timestamp")
    for field in ("cache_key", "profile_digest", "changed_paths_digest", "source_digest", "stdout_digest", "stderr_digest"):
        value = attestation.get(field)
        if not isinstance(value, str) or not _valid_digest(value):
            errors.append(f"{field} must be a sha256 digest")
    return errors


def _cache_directory(workspace_path: Path, *, create: bool) -> Path:
    root = workspace_path.resolve()
    directory = workspace_path / ".palari" / "verification"
    current = workspace_path
    for part in (".palari", "verification"):
        current = current / part
        if current.is_symlink():
            raise WorkspaceError(f"verification cache path is a symlink: {current}")
        if current.exists() and not current.is_dir():
            raise WorkspaceError(f"verification cache path is not a directory: {current}")
        if create and not current.exists():
            # Create one proven parent at a time. In particular, never call
            # mkdir(parents=True) through an unchecked .palari symlink.
            current.mkdir()
            if current.is_symlink():
                raise WorkspaceError(f"verification cache path is a symlink: {current}")
    try:
        directory.resolve().relative_to(root)
    except ValueError as exc:
        raise WorkspaceError("verification cache escapes the workspace") from exc
    return directory


def _read_attestation(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise WorkspaceError(f"verification attestation must not be a symlink: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise WorkspaceError(f"cannot read verification attestation {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkspaceError(f"verification attestation {path.name} must be an object")
    return data


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _write_attestation(path: Path, payload: dict[str, Any]) -> None:
    encoded = _canonical(payload) + b"\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".verification-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return _bytes_digest(_canonical(value))


def _bytes_digest(value: bytes) -> str:
    return HASH_PREFIX + hashlib.sha256(value).hexdigest()


def _valid_digest(value: str) -> bool:
    if not value.startswith(HASH_PREFIX) or len(value) != len(HASH_PREFIX) + 64:
        return False
    return all(char in "0123456789abcdef" for char in value[len(HASH_PREFIX) :])


def _python_identity() -> str:
    return f"{Path(sys.executable).resolve()}|{platform.python_implementation()}|{platform.python_version()}"


def _platform_identity() -> str:
    return f"{sys.platform}|{platform.machine()}|{platform.system()}-{platform.release()}"


def _tail(value: bytes, limit: int = 800) -> str:
    return value[-limit:].decode("utf-8", errors="replace")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
