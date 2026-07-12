"""Cursor IDE integration adapter.

Cursor does not expose a pre-write "deny this edit" hook the way Claude Code
does, so this adapter pairs two complementary layers to make the packet write
boundary work in Cursor (and, by extension, any editor built on the same idea):

- An instructional project rule written to ``.cursor/rules/palari-boundary.mdc``
  that is always applied to the agent's context. It tells any Cursor agent how
  to discover and respect its current packet boundary.
- The IDE-agnostic git pre-commit hook (see :mod:`palari_company_os.git_hooks`)
  that *structurally* rejects a commit staging files outside the active claim's
  write boundary. This is installed by default so enforcement is real, not just
  advisory.

The rule file is intentionally static and durable: it points agents at
``palari agent`` commands and ``palari cursor status`` rather than embedding
volatile per-work-item paths that would go stale. Live boundaries are reported
by ``status``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .git_hooks import active_claim_contexts, git_hook_status, install_git_hook
from .store import workspace_file_path

RULE_MARKER = "palari cursor rule"
RULE_RELATIVE_PATH = ".cursor/rules/palari-boundary.mdc"

RULE_TEMPLATE = """---
description: Palari packet write boundary for AI agents working in this repo.
alwaysApply: true
---
<!-- {marker} -->
<!-- Installed by: palari cursor install -->
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
- Stop for every blocker, missing source, human decision, or external write.

Enforcement is not advisory: a Palari git pre-commit hook rejects any commit
that stages files outside the active claim's write boundary, regardless of
editor or model. Run `palari cursor status` to see the active claim and its
allowed write paths.
"""


def install_cursor_rules(
    project_dir: Path | str,
    workspace_path: Path | str,
    *,
    git_hook: bool = True,
    remove: bool = False,
) -> dict[str, Any]:
    """Install or remove the Palari Cursor project rule (and git hook backstop).

    Idempotent: the Palari-managed rule file is recognized by its marker comment
    and replaced in place. A non-Palari file at the same path is never
    overwritten. Unless ``git_hook`` is ``False``, the IDE-agnostic git
    pre-commit hook is installed/removed alongside the rule so the boundary is
    structurally enforced at commit time.
    """
    root = Path(project_dir).expanduser().resolve()
    rule_path = root / RULE_RELATIVE_PATH

    if remove:
        rule_status, changed = _remove_rule(rule_path)
    else:
        rule_status, changed = _write_rule(rule_path)

    # The Cursor rule is the primary artifact. If it could not be written (for
    # example, a hand-written file is already at that path), do not touch the
    # git hook so the command has no partial side effects.
    git_hook_result: dict[str, Any] | None = None
    if git_hook and rule_status != "error":
        git_hook_result = install_git_hook(root, workspace_path, remove=remove)

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
    rule_path = root / RULE_RELATIVE_PATH
    installed = _is_managed_rule(rule_path)
    git_status = git_hook_status(root, workspace_path)

    contexts = active_claim_contexts(workspace_path)
    return {
        "schema_version": "palari.cursor_status.v1",
        "installed": installed,
        "rule_path": str(rule_path),
        "git_hook_installed": bool(git_status.get("installed")),
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
            "Palari Cursor rule is installed."
            if installed
            else "No Palari Cursor rule found. Run: palari cursor install"
        ),
    }


def _write_rule(rule_path: Path) -> tuple[str, bool]:
    content = RULE_TEMPLATE.format(marker=RULE_MARKER)
    existing = rule_path.read_text(encoding="utf-8") if rule_path.exists() else ""
    if existing and not _is_managed_rule_str(existing):
        return "error", False
    if _is_managed_rule_str(existing):
        if existing.strip() == content.strip():
            return "unchanged", False
        rule_path.write_text(content, encoding="utf-8")
        return "updated", True
    rule_path.parent.mkdir(parents=True, exist_ok=True)
    rule_path.write_text(content, encoding="utf-8")
    return "installed", True


def _remove_rule(rule_path: Path) -> tuple[str, bool]:
    if rule_path.exists() and _is_managed_rule(rule_path):
        rule_path.unlink()
        return "removed", True
    return "unchanged", False


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
        return base + " Git pre-commit hook not installed: " + git_hook_result.get("message", "")
    return base + " Git pre-commit enforcement is active."


def _packet_write_paths(packet: dict[str, Any]) -> list[str]:
    paths = packet.get("allowed_paths", {})
    if not isinstance(paths, dict):
        return []
    write = paths.get("write", [])
    if not isinstance(write, list):
        return []
    return [str(path) for path in write if str(path)]


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
