"""Git pre-commit enforcement adapter.

This module turns the agent packet write boundary into structural enforcement
at git commit time, providing IDE-agnostic boundary checking that works in
any environment (Windsurf, Cursor, Devin, terminal, etc.).

- ``pre-commit`` checks staged files against active claim write boundaries
  and exits non-zero if any staged file is outside the boundary.
- ``install`` writes a pre-commit hook script into ``.git/hooks/pre-commit``
  that calls ``palari git pre-commit``.
- ``status`` reports whether hooks are installed and active claims.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .agent_file_changes import git_repo_root
from .agent_runtime import claim_is_active, claims_dir
from .path_policy import path_allowed
from .store import workspace_file_path

HOOK_MARKER = "palari git hook"
HOOK_TIMEOUT_SECONDS = 20

PRE_COMMIT_SCRIPT = """#!/bin/sh
# {marker}
# Palari pre-commit boundary enforcement
# Installed by: palari git install
# Remove by: palari git install --remove
exec {executable} --workspace "{workspace_arg}" git pre-commit
"""


def pre_commit(
    workspace_path: Path | str,
    *,
    cwd: Path | str | None = None,
) -> dict[str, Any]:
    """Check staged files against active claim write boundaries.

    Returns a dict with ``ok``, ``outside``, ``allowed``, and ``staged`` keys.
    Exits non-zero (via ``exit_code`` field) when staged files are outside
    the boundary, so the git commit is rejected.
    """
    root = git_repo_root(Path(cwd or Path.cwd()))
    if root is None:
        return {
            "schema_version": "palari.git_pre_commit.v1",
            "ok": True,
            "status": "no-git-repo",
            "message": "Not inside a git repository; skipping boundary check.",
            "staged": [],
            "outside": [],
            "allowed": [],
        }

    contexts = active_claim_contexts(workspace_path)
    execute = [c for c in contexts if c["claim"].get("mode") == "execute"]
    if not execute:
        return {
            "schema_version": "palari.git_pre_commit.v1",
            "ok": True,
            "status": "no-active-claim",
            "message": "No active execute-mode Palari claim; skipping boundary check.",
            "staged": [],
            "outside": [],
            "allowed": [],
        }

    staged = _staged_files(root)
    allowed = _allowed_write_paths(execute)
    outside = [path for path in staged if not path_allowed(path, allowed)]

    return {
        "schema_version": "palari.git_pre_commit.v1",
        "ok": len(outside) == 0,
        "status": "blocked" if outside else "pass",
        "staged": staged,
        "outside": outside,
        "allowed": allowed,
        "message": (
            f"Commit blocked: {len(outside)} staged file(s) outside the Palari "
            f"write boundary for active claim(s)."
            if outside
            else f"All {len(staged)} staged file(s) inside the Palari write boundary."
        ),
    }


def install_git_hook(
    project_dir: Path | str,
    workspace_path: Path | str,
    *,
    remove: bool = False,
) -> dict[str, Any]:
    """Install or remove the Palari pre-commit hook in ``.git/hooks/``.

    Idempotent: the Palari-managed hook is recognized by its marker comment
    and replaced in place.
    """
    root = Path(project_dir).expanduser().resolve()
    git_root = git_repo_root(root)
    if git_root is None:
        return {
            "schema_version": "palari.git_install.v1",
            "status": "error",
            "changed": False,
            "message": "Not inside a git repository; cannot install hooks.",
            "hook_path": "",
        }

    hook_path = git_root / ".git" / "hooks" / "pre-commit"
    workspace_arg = _workspace_argument(root, workspace_path)
    executable = _palari_executable(root)

    if remove:
        if hook_path.exists() and _is_managed_hook(hook_path):
            hook_path.unlink()
            return {
                "schema_version": "palari.git_install.v1",
                "status": "removed",
                "changed": True,
                "hook_path": str(hook_path),
                "message": f"Palari pre-commit hook removed from {hook_path}.",
            }
        return {
            "schema_version": "palari.git_install.v1",
            "status": "unchanged",
            "changed": False,
            "hook_path": str(hook_path),
            "message": f"No Palari-managed hook found at {hook_path}.",
        }

    script = PRE_COMMIT_SCRIPT.format(
        marker=HOOK_MARKER,
        workspace_arg=workspace_arg,
        executable=executable,
    )
    existing = hook_path.read_text(encoding="utf-8") if hook_path.exists() else ""
    if _is_managed_hook_str(existing):
        if existing.strip() == script.strip():
            return {
                "schema_version": "palari.git_install.v1",
                "status": "unchanged",
                "changed": False,
                "hook_path": str(hook_path),
                "message": f"Palari pre-commit hook already installed at {hook_path}.",
            }
        hook_path.write_text(script, encoding="utf-8")
        _make_executable(hook_path)
        return {
            "schema_version": "palari.git_install.v1",
            "status": "updated",
            "changed": True,
            "hook_path": str(hook_path),
            "message": f"Palari pre-commit hook updated at {hook_path}.",
        }

    if existing and not _is_managed_hook_str(existing):
        return {
            "schema_version": "palari.git_install.v1",
            "status": "error",
            "changed": False,
            "hook_path": str(hook_path),
            "message": (
                f"{hook_path} already exists and is not Palari-managed. "
                "Remove it manually or merge the Palari hook call into it."
            ),
        }

    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(script, encoding="utf-8")
    _make_executable(hook_path)
    return {
        "schema_version": "palari.git_install.v1",
        "status": "installed",
        "changed": True,
        "hook_path": str(hook_path),
        "message": f"Palari pre-commit hook installed at {hook_path}.",
    }


def git_hook_status(
    project_dir: Path | str,
    workspace_path: Path | str,
) -> dict[str, Any]:
    """Report whether the Palari pre-commit hook is installed and active claims."""
    root = Path(project_dir).expanduser().resolve()
    git_root = git_repo_root(root)
    hook_path = (git_root / ".git" / "hooks" / "pre-commit") if git_root else None

    installed = False
    if hook_path and hook_path.exists():
        installed = _is_managed_hook(hook_path)

    contexts = active_claim_contexts(workspace_path)
    return {
        "schema_version": "palari.git_status.v1",
        "installed": installed,
        "hook_path": str(hook_path) if hook_path else "",
        "git_root": str(git_root) if git_root else "",
        "active_claims": [
            {
                "work_item": context["claim"].get("work_item", ""),
                "claimed_by": context["claim"].get("claimed_by", ""),
                "mode": context["claim"].get("mode", ""),
                "lease_expires_at": context["claim"].get("lease_expires_at", ""),
                "allowed_write_paths": _packet_write_paths(context["packet"]),
            }
            for context in contexts
        ],
        "message": (
            "Palari pre-commit hook is installed."
            if installed
            else "No Palari pre-commit hook found. Run: palari git install"
        ),
    }


def active_claim_contexts(workspace_path: Path | str) -> list[dict[str, Any]]:
    """Return active claims with their persisted packets."""
    directory = claims_dir(workspace_path)
    if not directory.is_dir():
        return []
    contexts: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        claim = _read_json(path)
        if claim is None or not claim_is_active(claim):
            continue
        packet = _read_json(_packet_file(workspace_path, claim)) or {}
        contexts.append({"claim": claim, "packet": packet})
    return contexts


def _staged_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _allowed_write_paths(contexts: list[dict[str, Any]]) -> list[str]:
    allowed: list[str] = []
    for context in contexts:
        for path in _packet_write_paths(context["packet"]):
            if path not in allowed:
                allowed.append(path)
    return allowed


def _packet_write_paths(packet: dict[str, Any]) -> list[str]:
    paths = packet.get("allowed_paths", {})
    if not isinstance(paths, dict):
        return []
    write = paths.get("write", [])
    if not isinstance(write, list):
        return []
    return [str(path) for path in write if str(path)]


def _packet_file(workspace_path: Path | str, claim: dict[str, Any]) -> Path:
    workspace_dir = workspace_file_path(workspace_path).parent
    relative = str(claim.get("packet_path", ""))
    if relative:
        return workspace_dir / relative
    packet_id = str(claim.get("packet_id", ""))
    return workspace_dir / ".palari" / "packets" / f"{packet_id}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = __import__("json").loads(path.read_text(encoding="utf-8"))
    except (OSError, __import__("json").JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _is_managed_hook(hook_path: Path) -> bool:
    try:
        return _is_managed_hook_str(hook_path.read_text(encoding="utf-8"))
    except OSError:
        return False


def _is_managed_hook_str(content: str) -> bool:
    return HOOK_MARKER in content and "palari" in content


def _make_executable(path: Path) -> None:
    try:
        path.chmod(0o755)
    except OSError:
        pass


def _workspace_argument(root: Path, workspace_path: Path | str) -> str:
    workspace_dir = workspace_file_path(workspace_path).parent
    try:
        relative = workspace_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(workspace_dir)
    if relative == ".":
        return "."
    return relative


def _palari_executable(root: Path) -> str:
    """Prefer a project-local wrapper so hooks work without a pip install."""
    if (root / "bin" / "palari").is_file():
        return f'"{root / "bin" / "palari"}"'
    return "palari"
