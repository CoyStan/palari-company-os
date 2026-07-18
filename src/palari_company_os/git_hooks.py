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
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .agent_file_changes import git_repo_root
from .agent_runtime import load_active_claim_contexts
from .path_policy import canonical_path_allowed, validate_workspace_path
from .store import workspace_file_path

HOOK_MARKER = "palari git hook"
HOOK_TIMEOUT_SECONDS = 20

PRE_COMMIT_SCRIPT = """#!/bin/sh
# {marker}
# Palari pre-commit boundary enforcement
# Installed by: palari git install
# Remove by: palari git install --remove
exec {executable} --workspace {workspace_arg} git pre-commit
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
    state = load_active_claim_contexts(workspace_path)
    contexts = state["contexts"]
    execute = [c for c in contexts if c["claim"].get("mode") == "execute"]
    if state["errors"]:
        return {
            "schema_version": "palari.git_pre_commit.v1",
            "ok": False,
            "status": "invalid-claim",
            "message": "Commit blocked: active Palari claim context is invalid.",
            "staged": [],
            "outside": [],
            "allowed": [],
            "errors": state["errors"],
        }
    root = git_repo_root(Path(cwd or Path.cwd()))
    if root is None:
        return {
            "schema_version": "palari.git_pre_commit.v1",
            "ok": not contexts,
            "status": "no-git-repo",
            "message": (
                "Commit blocked: an active Palari claim cannot be bound to a Git repository."
                if contexts
                else "Not inside a Git repository; no active claim requires enforcement."
            ),
            "staged": [],
            "outside": [],
            "allowed": [],
            "errors": (["could not locate the Git repository for this commit"] if contexts else []),
        }
    if not contexts:
        return {
            "schema_version": "palari.git_pre_commit.v1",
            "ok": True,
            "status": "no-active-claim",
            "message": "No active Palari claim; skipping boundary check.",
            "staged": [],
            "outside": [],
            "allowed": [],
            "errors": [],
        }
    if not _workspace_belongs_to_repo(workspace_path, root):
        return {
            "schema_version": "palari.git_pre_commit.v1",
            "ok": False,
            "status": "workspace-repo-mismatch",
            "message": "Commit blocked: the Palari workspace is not inside this Git repository.",
            "staged": [],
            "outside": [],
            "allowed": [],
            "errors": [f"workspace {workspace_file_path(workspace_path).parent} is outside {root}"],
        }

    staged, staged_error = _staged_files_result(root)
    if staged_error:
        return {
            "schema_version": "palari.git_pre_commit.v1",
            "ok": False,
            "status": "git-observation-error",
            "message": "Commit blocked: Palari could not inspect the staged files.",
            "staged": [],
            "outside": [],
            "allowed": [],
            "errors": [staged_error],
        }

    if not execute:
        return {
            "schema_version": "palari.git_pre_commit.v1",
            "ok": not staged,
            "status": "read-only-claim" if staged else "pass",
            "message": (
                "Commit blocked: active review-mode Palari claims are read-only."
                if staged
                else "No staged files; active review-mode Palari claims remain read-only."
            ),
            "staged": staged,
            "outside": staged,
            "allowed": [],
            "errors": (["review-mode claims grant no commit authority"] if staged else []),
        }

    covering = [
        context
        for context in execute
        if all(
            canonical_path_allowed(path, _packet_write_paths(context["packet"]), root=root)
            for path in staged
        )
    ]
    if staged and len(covering) != 1:
        covered_by_any = [
            path
            for path in staged
            if any(
                canonical_path_allowed(path, _packet_write_paths(context["packet"]), root=root)
                for context in execute
            )
        ]
        outside = [path for path in staged if path not in covered_by_any]
        return {
            "schema_version": "palari.git_pre_commit.v1",
            "ok": False,
            "status": "ambiguous-claim" if not outside else "blocked",
            "staged": staged,
            "outside": outside,
            "allowed": [],
            "errors": [
                "staged files must be covered by exactly one active execute claim; "
                "release or pin overlapping work before committing"
            ],
            "message": "Commit blocked: staged files do not bind to exactly one active claim.",
        }

    selected = covering[0] if covering else execute[0]
    allowed = _packet_write_paths(selected["packet"])
    outside = [
        path for path in staged if not canonical_path_allowed(path, allowed, root=root)
    ]

    return {
        "schema_version": "palari.git_pre_commit.v1",
        "ok": len(outside) == 0,
        "status": "blocked" if outside else "pass",
        "staged": staged,
        "outside": outside,
        "allowed": allowed,
        "claim": selected["claim"].get("work_item", ""),
        "errors": [],
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

    hook_path, hook_error = _git_hook_path(git_root)
    if hook_path is None:
        return {
            "schema_version": "palari.git_install.v1",
            "status": "error",
            "changed": False,
            "message": f"Cannot locate Git hook directory: {hook_error}",
            "hook_path": "",
        }
    location_error = _git_hook_location_error(git_root, hook_path)
    if location_error:
        return {
            "schema_version": "palari.git_install.v1",
            "status": "error",
            "changed": False,
            "message": location_error,
            "hook_path": str(hook_path),
        }
    workspace_arg = shlex.quote(_workspace_argument(root, workspace_path))
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
    hook_path, hook_error = _git_hook_path(git_root) if git_root else (None, "")

    installed = False
    if hook_path and hook_path.exists():
        installed = _is_managed_hook(hook_path)

    state = load_active_claim_contexts(workspace_path)
    contexts = state["contexts"]
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
        "claim_errors": state["errors"],
        "hook_error": hook_error,
        "message": (
            "Palari pre-commit hook is installed."
            if installed
            else "No Palari pre-commit hook found. Run: palari git install"
        ),
    }


def active_claim_contexts(workspace_path: Path | str) -> list[dict[str, Any]]:
    """Return active claims with their persisted packets."""
    return load_active_claim_contexts(workspace_path)["contexts"]


def _staged_files(root: Path) -> list[str]:
    files, _error = _staged_files_result(root)
    return files


def _staged_files_result(root: Path) -> tuple[list[str], str]:
    try:
        result = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACMRTD", "-z"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"could not inspect staged files: {exc}"
    if result.returncode != 0:
        detail = os.fsdecode(result.stderr).strip() or f"git exited {result.returncode}"
        return [], f"could not inspect staged files: {detail}"
    files: list[str] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        value = os.fsdecode(raw)
        try:
            normalized = validate_workspace_path(value)
            if normalized != value:
                raise ValueError("path is not in canonical Git form")
        except ValueError as exc:
            return [], f"Git reported an unsafe staged path {value!r}: {exc}"
        if normalized not in files:
            files.append(normalized)
    return files, ""


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
        return shlex.quote(str(root / "bin" / "palari"))
    return "palari"


def _workspace_belongs_to_repo(workspace_path: Path | str, root: Path) -> bool:
    try:
        workspace_file_path(workspace_path).parent.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _git_hook_path(root: Path) -> tuple[Path | None, str]:
    try:
        configured = subprocess.run(
            ["git", "-C", str(root), "config", "--path", "--get", "core.hooksPath"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if configured.returncode == 0 and configured.stdout.strip():
            path = Path(configured.stdout.strip()).expanduser()
            if not path.is_absolute():
                path = root / path
            return path.resolve() / "pre-commit", ""
        resolved = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-path", "hooks/pre-commit"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if resolved.returncode != 0 or not resolved.stdout.strip():
        return None, resolved.stderr.strip() or "Git returned no hook path"
    path = Path(resolved.stdout.strip())
    if not path.is_absolute():
        path = root / path
    return path.resolve(), ""


def _git_hook_location_error(root: Path, hook_path: Path) -> str:
    """Reject process-global or unrelated hook targets before any write.

    A linked worktree legitimately shares the repository's common Git
    directory, so both the worktree root and that exact common directory are
    local. An arbitrary absolute ``core.hooksPath`` is not.
    """

    allowed_roots = [root.resolve()]
    try:
        common = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-common-dir"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Cannot verify Git hook locality: {exc}"
    if common.returncode != 0 or not common.stdout.strip():
        return common.stderr.strip() or "Cannot verify Git common directory"
    common_dir = Path(common.stdout.strip()).expanduser()
    if not common_dir.is_absolute():
        common_dir = root / common_dir
    allowed_roots.append(common_dir.resolve())
    resolved = hook_path.resolve()
    for allowed in allowed_roots:
        try:
            resolved.relative_to(allowed)
            return ""
        except ValueError:
            continue
    return (
        f"Refusing Git hook target outside this repository: {resolved}. "
        "Use a repository-local core.hooksPath or remove that configuration."
    )
