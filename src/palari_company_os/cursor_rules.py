"""Cursor IDE integration adapter.

Cursor does not expose a pre-write "deny this edit" hook the way Claude Code
does, so this adapter pairs two complementary layers:

- An instructional project rule written to ``.cursor/rules/palari-boundary.mdc``
  that is always applied to the agent's context (advisory session boundary).
- The optional IDE-agnostic git pre-commit hook (see
  :mod:`palari_company_os.git_hooks`) that *structurally* rejects a commit
  staging files outside the active claim's write boundary.

``palari init --host cursor`` installs the advisory rule only. Structural
commit gating is opt-in via ``--strict-git``, ``palari cursor install`` (git
hook on by default), or ``palari git install``. With no active claim, commits
are allowed even when the hook is installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_file_changes import git_repo_root
from .git_hooks import git_hook_status, install_git_hook
from .store import workspace_file_path
from .workspace import WorkspaceError

RULE_MARKER = "palari cursor rule"
RULE_RELATIVE_PATH = ".cursor/rules/palari-boundary.mdc"

RULE_BODY = """---
description: Palari packet write boundary for AI agents working in this repo.
alwaysApply: true
---
<!-- {marker} -->
<!-- Installed by: palari cursor install / palari init --host cursor -->
<!-- Remove by: palari cursor install --remove -->

# Palari write-boundary contract

This project uses Palari Company OS to give AI agents an inspectable write
boundary. Before changing files, discover and respect your current boundary.

- Find safe work and read the packet:
  - `palari agent next --as PALARI-ID --json`
  - `palari agent brief WORK-ID --as PALARI-ID --mode execute --json`
- Claim the work before editing files:
  - `palari agent start WORK-ID --as PALARI-ID --mode execute --json`
- Only edit files inside the packet `allowed_paths.write`. Check your changes
  against the boundary before committing:
  - `palari agent check WORK-ID --as PALARI-ID --mode execute --git-diff --json`
- Autopilot until handoff: no `timeout`/`bash -c` wrappers; verify with
  `python3 -S -m unittest …` / `python3 -m ruff check …`; use bare
  `palari agent advance` then `palari agent handoff`. Humans approve in the
  inbox — not every shell step.
- Stop for every blocker, missing source, human decision, or external write.

{enforcement}

Recovery:

- Stuck claim blocking commits: `palari agent release WORK-ID --as PALARI-ID --json`
- Remove this rule (and optional git hook): `palari cursor install --remove`
- With no active claim, the git pre-commit gate allows commits.
- Live boundary: `palari cursor status`
"""

ENFORCEMENT_ADVISORY = """Session boundary is advisory: this project rule is always applied, but
Cursor cannot deny edits before they happen. Structural commit enforcement is
optional — run `palari cursor install` (or `palari git install`) to install the
git pre-commit hook."""

ENFORCEMENT_STRUCTURAL = """A Palari git pre-commit hook rejects any commit that stages files outside
the active claim's write boundary, regardless of editor or model. With no
active claim, commits are allowed."""


def install_cursor_rules(
    project_dir: Path | str,
    workspace_path: Path | str,
    *,
    git_hook: bool = True,
    remove: bool = False,
) -> dict[str, Any]:
    """Install or remove the Palari Cursor project rule (and optional git hook).

    Idempotent: the Palari-managed rule file is recognized by its marker comment
    and replaced in place. A non-Palari file at the same path is never
    overwritten. Unless ``git_hook`` is ``False``, the IDE-agnostic git
    pre-commit hook is installed/removed alongside the rule. When hook install
    is requested and fails after a rule write, the rule change is rolled back.
    """
    root = Path(project_dir).expanduser().resolve()
    repo_root = git_repo_root(root)
    if repo_root is not None:
        root = repo_root
    if not remove:
        _assert_safe_cursor_install(root, workspace_path)
    rule_path = root / RULE_RELATIVE_PATH
    _assert_local_rule_target(root, rule_path)

    if remove:
        rule_status, changed, before = _remove_rule(rule_path)
        git_hook_result: dict[str, Any] | None = None
        if git_hook and rule_status != "error":
            git_hook_result = install_git_hook(root, workspace_path, remove=True)
        return {
            "schema_version": "palari.cursor_install.v1",
            "status": rule_status,
            "changed": changed or bool(git_hook_result and git_hook_result.get("changed")),
            "rule_path": str(rule_path),
            "git_hook": git_hook_result,
            "workspace": _workspace_argument(root, workspace_path),
            "message": _install_message(rule_status, rule_path, git_hook_result),
        }

    plan = prepare_cursor_rule(rule_path, structural_commit=git_hook)
    if plan["status"] == "error":
        return {
            "schema_version": "palari.cursor_install.v1",
            "status": "error",
            "changed": False,
            "rule_path": str(rule_path),
            "git_hook": None,
            "workspace": _workspace_argument(root, workspace_path),
            "message": _install_message("error", rule_path, None),
        }

    rule_existed = bool(plan["before"])
    rule_before = plan["before"]
    rule_status = plan["status"]
    changed = plan["changed"]
    if changed:
        write_cursor_rule_bytes(rule_path, plan["after"])

    git_hook_result = None
    if git_hook:
        git_hook_result = install_git_hook(root, workspace_path, remove=False)
        if git_hook_result.get("status") == "error":
            _restore_rule(rule_path, existed=rule_existed, content=rule_before)
            return {
                "schema_version": "palari.cursor_install.v1",
                "status": "error",
                "changed": False,
                "rule_path": str(rule_path),
                "git_hook": git_hook_result,
                "workspace": _workspace_argument(root, workspace_path),
                "message": (
                    f"Cursor rule install rolled back: "
                    f"{git_hook_result.get('message', 'git hook installation failed')}"
                ),
            }

    return {
        "schema_version": "palari.cursor_install.v1",
        "status": rule_status,
        "changed": changed or bool(git_hook_result and git_hook_result.get("changed")),
        "rule_path": str(rule_path),
        "git_hook": git_hook_result,
        "workspace": _workspace_argument(root, workspace_path),
        "message": _install_message(rule_status, rule_path, git_hook_result),
    }


def cursor_rules_status(
    project_dir: Path | str,
    workspace_path: Path | str,
) -> dict[str, Any]:
    """Report whether the Cursor rule and git hook are installed, plus claims."""
    root = Path(project_dir).expanduser().resolve()
    repo_root = git_repo_root(root)
    if repo_root is not None:
        root = repo_root
    rule_path = root / RULE_RELATIVE_PATH
    installed = _is_managed_rule(rule_path)
    git_status = git_hook_status(root, workspace_path)

    return {
        "schema_version": "palari.cursor_status.v1",
        "installed": installed,
        "rule_path": str(rule_path),
        "git_hook_installed": bool(git_status.get("installed")),
        "active_claims": list(git_status.get("active_claims") or []),
        "message": (
            "Palari Cursor rule is installed."
            if installed
            else "No Palari Cursor rule found. Run: palari cursor install"
            " (or palari init --host cursor)"
        ),
    }


def prepare_cursor_rule(
    rule_path: Path,
    *,
    structural_commit: bool,
) -> dict[str, Any]:
    """Inspect and plan a Cursor rule write without mutating the filesystem."""
    content = rule_content(structural_commit=structural_commit)
    existing = rule_path.read_text(encoding="utf-8") if rule_path.exists() else ""
    if existing and not _is_managed_rule_str(existing):
        return {
            "status": "error",
            "changed": False,
            "before": existing,
            "after": existing,
        }
    if _is_managed_rule_str(existing):
        if existing.strip() == content.strip():
            return {
                "status": "unchanged",
                "changed": False,
                "before": existing,
                "after": existing,
            }
        return {
            "status": "updated",
            "changed": True,
            "before": existing,
            "after": content,
        }
    return {
        "status": "installed",
        "changed": True,
        "before": existing,
        "after": content,
    }


def write_cursor_rule_bytes(rule_path: Path, content: str) -> None:
    """Write managed Cursor rule bytes after locality checks."""
    rule_path.parent.mkdir(parents=True, exist_ok=True)
    rule_path.write_text(content, encoding="utf-8")


def rule_content(*, structural_commit: bool) -> str:
    enforcement = ENFORCEMENT_STRUCTURAL if structural_commit else ENFORCEMENT_ADVISORY
    return RULE_BODY.format(marker=RULE_MARKER, enforcement=enforcement)


def _remove_rule(rule_path: Path) -> tuple[str, bool, str]:
    existing = ""
    if rule_path.exists():
        try:
            existing = rule_path.read_text(encoding="utf-8")
        except OSError:
            existing = ""
    if rule_path.exists() and _is_managed_rule(rule_path):
        rule_path.unlink()
        return "removed", True, existing
    return "unchanged", False, existing


def _restore_rule(rule_path: Path, *, existed: bool, content: str) -> None:
    if existed:
        rule_path.parent.mkdir(parents=True, exist_ok=True)
        rule_path.write_text(content, encoding="utf-8")
        return
    if rule_path.exists():
        rule_path.unlink()


def _install_message(
    rule_status: str,
    rule_path: Path,
    git_hook_result: dict[str, Any] | None,
) -> str:
    if rule_status == "error":
        return (
            f"{rule_path} already exists and is not Palari-managed. "
            "Remove it manually or move it aside, then re-run."
        )
    if rule_status == "removed":
        base = f"Palari Cursor rule removed from {rule_path}."
    elif rule_status == "unchanged":
        base = f"Palari Cursor rule already up to date at {rule_path}."
    elif rule_status == "updated":
        base = f"Palari Cursor rule updated at {rule_path}."
    else:
        base = f"Palari Cursor rule installed at {rule_path}."

    if git_hook_result is None:
        return base + " Git pre-commit enforcement was skipped (--no-git-hook)."
    if git_hook_result.get("status") == "error":
        return base + " Git pre-commit hook not installed: " + git_hook_result.get(
            "message", ""
        )
    return base + " Git pre-commit enforcement is active."


def _assert_safe_cursor_install(root: Path, workspace_path: Path | str) -> None:
    if git_repo_root(root) is None:
        raise WorkspaceError("Cursor rule installation requires a Git repository")
    if not _workspace_inside_project(workspace_path, root):
        raise WorkspaceError(
            "Cursor rules require the Palari workspace to be inside the repository"
        )


def _assert_local_rule_target(root: Path, target: Path) -> None:
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError(f"Cursor rule target is outside the repository: {target}") from exc
    cursor = root
    for index, part in enumerate(relative.parts):
        cursor = cursor / part
        if cursor.is_symlink():
            raise WorkspaceError(f"Cursor rule target uses a symlink: {cursor}")
        if index < len(relative.parts) - 1 and cursor.exists() and not cursor.is_dir():
            raise WorkspaceError(
                f"Cursor rule target parent is not a directory: {cursor}"
            )
    if target.exists() and not target.is_file():
        raise WorkspaceError(f"Cursor rule target is not a regular file: {target}")


def _workspace_inside_project(workspace_path: Path | str, root: Path) -> bool:
    candidate = Path(workspace_path).expanduser()
    if candidate.is_dir():
        candidate = candidate / "workspace.json"
    if candidate.is_symlink():
        return False
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return resolved.is_file()


def _is_managed_rule(rule_path: Path) -> bool:
    try:
        return _is_managed_rule_str(rule_path.read_text(encoding="utf-8"))
    except OSError:
        return False


def _is_managed_rule_str(content: str) -> bool:
    return RULE_MARKER in content


def _workspace_argument(root: Path, workspace_path: Path | str) -> str:
    workspace_dir = workspace_file_path(workspace_path).parent
    try:
        relative = workspace_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(workspace_dir)
    return relative if relative != "." else "."
