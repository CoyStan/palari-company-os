"""Claude Code enforcement adapter.

This module turns the agent packet write boundary into structural enforcement
for Claude Code sessions instead of a voluntary contract:

- ``PreToolUse`` denies ``Write``/``Edit``/``NotebookEdit`` calls that target
  files outside the active claim's write boundary before the write happens,
  and asks a human when a Bash command looks like it writes outside it.
- ``Stop`` blocks Claude from finishing a turn while ``git status`` shows
  changes outside the boundary, so shell writes cannot slip through silently.
- ``SessionStart`` injects the active packet contract into Claude's context.

Hook handlers read only the persisted claim and packet files under
``.palari/`` that ``palari agent start`` wrote, so they enforce the exact
contract the agent started under and never load or mutate the workspace.
Handlers must never crash the Claude Code tool flow: every entry point
catches errors and degrades to "no decision".
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

from .agent_file_changes import git_repo_root, inspect_file_changes
from .agent_runtime import load_active_claim_contexts
from .path_policy import canonical_path_allowed
from .store import workspace_file_path

HOOK_EVENTS = ("pre-tool-use", "stop", "session-start")
FILE_WRITE_TOOLS = {"Write": "file_path", "Edit": "file_path", "NotebookEdit": "notebook_path"}
PRE_TOOL_USE_MATCHER = "Write|Edit|NotebookEdit|Bash"
HOOK_COMMAND_MARKER = "claude hook"
HOOK_TIMEOUT_SECONDS = 20
_REDIRECT_NO_TARGET = "\x00"
BASH_WRITE_COMMANDS = {
    "cp",
    "dd",
    "install",
    "ln",
    "mkdir",
    "mv",
    "rm",
    "rmdir",
    "tee",
    "touch",
    "truncate",
}


def run_hook(
    event: str,
    workspace_path: Path | str,
    *,
    strict: bool = False,
    stdin: Any = None,
) -> dict[str, Any]:
    """Read one Claude Code hook payload from stdin and return the decision.

    Never raises: a broken payload or missing workspace degrades to an empty
    decision so a Palari problem cannot lock up an unrelated Claude session.
    """
    try:
        raw = (stdin if stdin is not None else sys.stdin).read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        return handle_hook_event(event, payload, workspace_path, strict=strict)
    except Exception as exc:  # noqa: BLE001 - hooks must fail open, never block the session
        return {"systemMessage": f"palari claude hook {event} error: {exc}"}


def handle_hook_event(
    event: str,
    payload: dict[str, Any],
    workspace_path: Path | str,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    state = load_active_claim_contexts(
        workspace_path,
        pin_palari=os.environ.get("PALARI_AS", ""),
        pin_work=os.environ.get("PALARI_WORK_ID", ""),
    )
    contexts = state["contexts"]
    if event == "pre-tool-use":
        return _pre_tool_use(
            payload, contexts, state["errors"], workspace_path, strict=strict
        )
    if event == "stop":
        return _stop(payload, contexts, state["errors"], workspace_path)
    if event == "session-start":
        return _session_start(contexts, state["errors"], workspace_path)
    return {}


def active_claim_contexts(workspace_path: Path | str) -> list[dict[str, Any]]:
    """Return active claims with their persisted packets.

    Each entry has ``claim`` and ``packet`` keys. Expired leases are skipped.
    ``PALARI_AS`` / ``PALARI_WORK_ID`` environment variables narrow the set
    when one session among several must be pinned to a single claim.
    """
    return load_active_claim_contexts(
        workspace_path,
        pin_palari=os.environ.get("PALARI_AS", ""),
        pin_work=os.environ.get("PALARI_WORK_ID", ""),
    )["contexts"]


def bash_write_targets(command: str) -> list[str]:
    """Return path-like write targets a Bash command appears to touch.

    This is a conservative heuristic: it only inspects redirections and a
    short list of mutating commands, and its findings only ever produce an
    ``ask`` decision, never a silent ``deny`` or ``allow``.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    targets: list[str] = []
    expect_command = True
    expect_target = False
    active_write_command = ""
    sed_in_place = False
    sed_script_consumed = False
    for token in tokens:
        if token in {"&&", "||", ";", "|"}:
            expect_command = True
            expect_target = False
            active_write_command = ""
            sed_in_place = False
            sed_script_consumed = False
            continue
        redirect = _redirect_target(token)
        if redirect is not None:
            if redirect == _REDIRECT_NO_TARGET:
                pass
            elif redirect:
                targets.append(redirect)
            else:
                expect_target = True
            continue
        if expect_target:
            targets.append(token)
            expect_target = False
            continue
        if expect_command:
            expect_command = False
            name = Path(token).name
            if name in BASH_WRITE_COMMANDS:
                active_write_command = name
            elif name == "sed":
                sed_in_place = False
                sed_script_consumed = False
                active_write_command = "sed"
            elif name == "git":
                active_write_command = "git"
            continue
        if active_write_command == "git":
            active_write_command = "git-sub" if token in {"rm", "mv"} else ""
            continue
        if active_write_command == "sed":
            if token in {"-i", "--in-place"} or token.startswith("-i"):
                sed_in_place = True
                continue
            if token.startswith("-"):
                continue
            if not sed_script_consumed:
                sed_script_consumed = True
                continue
            if sed_in_place and _looks_like_path(token):
                targets.append(token)
            continue
        if active_write_command and not token.startswith("-"):
            targets.append(token)
    return targets


def install_hooks(
    project_dir: Path | str,
    workspace_path: Path | str,
    *,
    settings_file: str = "",
    local: bool = False,
    strict: bool = False,
    remove: bool = False,
) -> dict[str, Any]:
    """Merge (or remove) Palari-managed hooks in Claude Code settings.

    Idempotent: Palari-managed entries are recognized by their command marker
    and replaced in place; hooks owned by other tools are preserved.
    """
    root = Path(project_dir).expanduser().resolve()
    target = _settings_path(root, settings_file, local)
    data = _read_json(target) if target.exists() else {}
    if data is None:
        return {
            "schema_version": "palari.claude_install.v1",
            "status": "error",
            "changed": False,
            "settings_file": str(target),
            "message": f"{target} exists but is not valid JSON; fix or remove it first.",
            "hooks": {},
        }

    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks

    managed = {} if remove else _managed_hooks(root, workspace_path, strict=strict)
    changed = False
    for event in ("PreToolUse", "Stop", "SessionStart"):
        entries = hooks.get(event)
        if not isinstance(entries, list):
            entries = []
        kept = [entry for entry in entries if not _is_managed_entry(entry)]
        if event in managed:
            kept.append(managed[event])
        if kept != entries:
            changed = True
        if kept:
            hooks[event] = kept
        elif event in hooks:
            del hooks[event]
            changed = True
    if not hooks:
        del data["hooks"]

    if changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    status = "removed" if remove else "installed"
    if not changed:
        status = "unchanged"
    return {
        "schema_version": "palari.claude_install.v1",
        "status": status,
        "changed": changed,
        "settings_file": str(target),
        "workspace": _workspace_argument(root, workspace_path),
        "strict": strict,
        "palari_on_path": shutil.which("palari") is not None
        or (root / "bin" / "palari").is_file(),
        "hooks": {event: entry["hooks"][0]["command"] for event, entry in managed.items()},
        "message": _install_message(status, target),
    }


def hooks_status(
    project_dir: Path | str,
    workspace_path: Path | str,
) -> dict[str, Any]:
    root = Path(project_dir).expanduser().resolve()
    files: list[dict[str, Any]] = []
    for candidate in (root / ".claude" / "settings.json", root / ".claude" / "settings.local.json"):
        data = _read_json(candidate) if candidate.exists() else None
        events: list[str] = []
        strict = False
        if isinstance(data, dict) and isinstance(data.get("hooks"), dict):
            for event, entries in data["hooks"].items():
                if isinstance(entries, list) and any(_is_managed_entry(e) for e in entries):
                    events.append(event)
                    strict = strict or any(
                        "--strict" in hook.get("command", "")
                        for entry in entries
                        if _is_managed_entry(entry)
                        for hook in entry.get("hooks", [])
                    )
        files.append(
            {
                "path": str(candidate),
                "exists": candidate.exists(),
                "palari_hook_events": sorted(events),
                "strict": strict,
            }
        )
    state = load_active_claim_contexts(
        workspace_path,
        pin_palari=os.environ.get("PALARI_AS", ""),
        pin_work=os.environ.get("PALARI_WORK_ID", ""),
    )
    contexts = state["contexts"]
    installed = any(item["palari_hook_events"] for item in files)
    return {
        "schema_version": "palari.claude_status.v1",
        "installed": installed,
        "settings_files": files,
        "palari_on_path": shutil.which("palari") is not None,
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
        "message": (
            "Palari hooks are installed for Claude Code."
            if installed
            else "No Palari hooks found. Run: palari claude install"
        ),
    }


def _pre_tool_use(
    payload: dict[str, Any],
    contexts: list[dict[str, Any]],
    context_errors: list[str],
    workspace_path: Path | str,
    *,
    strict: bool,
) -> dict[str, Any]:
    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    exact = tool_name in FILE_WRITE_TOOLS
    if exact:
        raw_targets = [str(tool_input.get(FILE_WRITE_TOOLS[tool_name], ""))]
    elif tool_name == "Bash":
        raw_targets = bash_write_targets(str(tool_input.get("command", "")))
    else:
        return {}
    raw_targets = [target for target in raw_targets if target]
    if not raw_targets:
        return {}

    if context_errors:
        return _decision(
            "deny" if exact else "ask",
            "Palari cannot verify the active claim context: " + "; ".join(context_errors),
        )

    execute = _execute_contexts(contexts)
    if not contexts:
        if strict:
            return _decision(
                "ask",
                "No active Palari claim covers this session. "
                "Run: palari agent next --json, then palari agent start WORK-ID "
                "--as PALARI-ID --mode execute --json before changing files.",
            )
        return {}
    if not execute:
        reason = (
            "Active Palari claims are review-mode (read-only); file changes are "
            "outside the packet contract. Start execute-mode work first: "
            "palari agent start WORK-ID --as PALARI-ID --mode execute --json"
        )
        return _decision("deny" if exact else "ask", reason)

    cwd = Path(str(payload.get("cwd") or "") or os.getcwd())
    root = _resolution_root(payload)
    unresolved: list[str] = []
    relative_targets: list[str] = []
    for target in raw_targets:
        relative = _relativize(target, root, cwd)
        if relative is None:
            unresolved.append(target)
        else:
            relative_targets.append(relative)
    if unresolved:
        return _decision(
            "deny" if exact else "ask",
            "This file change touches paths outside the repository "
            f"({', '.join(sorted(unresolved))}), which the Palari packet cannot vouch for.",
        )
    if root is None or not _workspace_belongs_to_repo(workspace_path, root):
        return _decision(
            "deny" if exact else "ask",
            "The active Palari workspace cannot be bound to this Git repository.",
        )

    covering = [
        context
        for context in execute
        if all(
            canonical_path_allowed(
                target, _packet_write_paths(context["packet"]), root=root
            )
            for target in relative_targets
        )
    ]
    if len(covering) != 1:
        if len(covering) > 1:
            reason = (
                "This file change is covered by multiple active execute claims. "
                "Set PALARI_WORK_ID/PALARI_AS or release the overlapping claim before writing."
            )
        else:
            reason = _boundary_reason(
                relative_targets, _allowed_write_paths(execute), execute, exact
            )
        return _decision("deny" if exact else "ask", reason)

    selected = covering[0]
    allowed = _packet_write_paths(selected["packet"])
    if exact:
        claim = selected["claim"]
        return _decision(
            "allow",
            f"Inside the Palari write boundary for {claim.get('work_item', '')} "
            f"(claimed by {claim.get('claimed_by', '')}).",
        )
    return {}


def _stop(
    payload: dict[str, Any],
    contexts: list[dict[str, Any]],
    context_errors: list[str],
    workspace_path: Path | str,
) -> dict[str, Any]:
    if payload.get("stop_hook_active"):
        return {}
    if context_errors:
        return {
            "decision": "block",
            "reason": "Palari cannot verify the active claim context: " + "; ".join(context_errors),
        }
    execute = _execute_contexts(contexts)
    if not contexts:
        return {}
    if execute and len(execute) != 1:
        return {
            "decision": "block",
            "reason": (
                "Multiple active execute claims are ambiguous. Set PALARI_WORK_ID/PALARI_AS "
                "or release overlapping claims before finishing."
            ),
        }
    cwd = str(payload.get("cwd") or "") or os.getcwd()
    root = git_repo_root(Path(cwd))
    if root is None or not _workspace_belongs_to_repo(workspace_path, root):
        return {
            "decision": "block",
            "reason": "Palari cannot bind this active claim and workspace to the current Git repository.",
        }
    if not execute:
        inspection = inspect_file_changes(
            {"allowed_paths": {"write": []}},
            git_diff=True,
            cwd=Path(cwd),
            git_baseline=contexts[0]["claim"].get("git_baseline"),
        )
        observation_errors = inspection.get("observation_errors", []) if inspection else []
        if observation_errors:
            return {
                "decision": "block",
                "reason": "Palari could not inspect the Git worktree: "
                + "; ".join(observation_errors),
            }
        changed = inspection.get("outside_write_boundary", []) if inspection else []
        changed = _without_palari_runtime(changed, workspace_path, Path(cwd))
        if changed:
            return {
                "decision": "block",
                "reason": (
                    "Active review-mode Palari claims are read-only; changed files: "
                    + ", ".join(changed)
                ),
            }
        return {}
    boundary_packet = {"allowed_paths": {"write": _packet_write_paths(execute[0]["packet"])}}
    inspection = inspect_file_changes(
        boundary_packet,
        git_diff=True,
        cwd=Path(cwd),
        git_baseline=execute[0]["claim"].get("git_baseline"),
    )
    observation_errors = inspection.get("observation_errors", []) if inspection else []
    if observation_errors:
        return {
            "decision": "block",
            "reason": "Palari could not inspect the Git worktree: " + "; ".join(observation_errors),
        }
    outside = inspection.get("outside_write_boundary", []) if inspection else []
    outside = _without_palari_runtime(outside, workspace_path, Path(cwd))
    if not outside:
        return {}
    claim = execute[0]["claim"]
    work_id = claim.get("work_item", "WORK-ID")
    palari_id = claim.get("claimed_by", "PALARI-ID")
    lines = [
        "Palari boundary check failed: the working tree has changes outside the "
        "active packet write boundary.",
        "outside boundary:",
        *[f"  - {path}" for path in outside],
        "allowed:",
        *[f"  - {path}" for path in _allowed_write_paths(execute)],
        "Before finishing: revert the out-of-boundary changes (or confirm they "
        "predate this session and tell the human), then run:",
        f"  palari agent check {work_id} --as {palari_id} --mode execute --git-diff --json",
        "If the boundary itself must grow, stop and hand off with:",
        f"  palari agent handoff {work_id} --as {palari_id} --json",
    ]
    return {"decision": "block", "reason": "\n".join(lines)}


def _session_start(
    contexts: list[dict[str, Any]],
    context_errors: list[str],
    workspace_path: Path | str,
) -> dict[str, Any]:
    workspace_dir = workspace_file_path(workspace_path).parent
    lines = [
        "<palari-contract>",
        f"This project is governed by Palari Company OS (workspace: {workspace_dir}).",
    ]
    if context_errors:
        lines.append("Invalid active claim context (writes must stop):")
        lines.extend(f"- {error}" for error in context_errors)
    if contexts:
        lines.append("Active claims:")
        for context in contexts:
            claim = context["claim"]
            work_id = claim.get("work_item", "")
            palari_id = claim.get("claimed_by", "")
            mode = claim.get("mode", "")
            lines.append(
                f"- {work_id} claimed by {palari_id} (mode {mode}, "
                f"lease expires {claim.get('lease_expires_at', '')})"
            )
            writes = _packet_write_paths(context["packet"])
            lines.append(
                "  allowed write paths: " + (", ".join(writes) if writes else "(none)")
            )
            lines.append(
                f"  check before done: palari agent check {work_id} --as {palari_id} "
                f"--mode {mode} --git-diff --json"
            )
        lines.append(
            "File writes outside these boundaries are blocked by PreToolUse and "
            "Stop hooks; do not try to work around them."
        )
    else:
        lines.extend(
            [
                "No work item is claimed yet. Before changing files, pick bounded "
                "work and claim it:",
                "  palari agent next --json",
                "  palari agent start WORK-ID --as PALARI-ID --mode execute --json",
                "Palari hooks enforce the claimed packet's write boundary during "
                "this session.",
            ]
        )
    lines.append("</palari-contract>")
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }


def _decision(decision: str, reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def _boundary_reason(
    outside: list[str],
    allowed: list[str],
    execute: list[dict[str, Any]],
    exact: bool,
) -> str:
    claim = execute[0]["claim"]
    work_id = claim.get("work_item", "WORK-ID")
    palari_id = claim.get("claimed_by", "PALARI-ID")
    verb = "is" if exact else "may be"
    lines = [
        f"*** BLOCKED: file change {verb} outside the Palari write boundary ***",
        *[f"changed: {path}" for path in sorted(outside)],
        *[f"allowed: {path}" for path in allowed],
        f"work: {work_id} (claimed by {palari_id})",
        "Next safe commands:",
        f"  palari agent doctor {work_id} --as {palari_id} --mode execute --json",
        f"  palari agent handoff {work_id} --as {palari_id} --json",
        "If the boundary must grow, a human updates the work item scope first.",
    ]
    return "\n".join(lines)


def _without_palari_runtime(
    outside: list[str],
    workspace_path: Path | str,
    cwd: Path,
) -> list[str]:
    """Drop the workspace's own .palari runtime state from boundary findings.

    ``agent start`` writes packets and claims under ``.palari/``; treating
    that bookkeeping as an out-of-boundary change would block every stop.
    """
    root = git_repo_root(cwd)
    if root is None:
        return outside
    runtime_dir = workspace_file_path(workspace_path).parent / ".palari"
    try:
        prefix = runtime_dir.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return outside
    return [path for path in outside if path != prefix and not path.startswith(f"{prefix}/")]


def _execute_contexts(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [context for context in contexts if context["claim"].get("mode") == "execute"]


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


def _resolution_root(payload: dict[str, Any]) -> Path | None:
    cwd = str(payload.get("cwd") or "") or os.getcwd()
    root = git_repo_root(Path(cwd))
    if root is not None:
        return root
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    return Path(project_dir) if project_dir else None


def _relativize(target: str, root: Path | None, cwd: Path) -> str | None:
    """Map a hook-reported path onto the repo-relative boundary namespace.

    Relative paths are anchored at the hook's cwd first, since boundary paths
    are repo-root relative. Returns None when the path cannot be tied to the
    repository, so callers can distinguish "outside the boundary" from
    "outside the repo".
    """
    candidate = Path(target.strip().replace("\\", "/"))
    if not candidate.is_absolute():
        candidate = cwd / candidate
    if root is None:
        return None
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def _redirect_target(token: str) -> str | None:
    """Return the redirect target embedded in a token.

    ``">"``-style operators with a separate target return ``""`` so the
    caller consumes the next token; fd duplications such as ``2>&1`` return
    the no-target sentinel; non-redirect tokens return ``None``.
    """
    stripped = token.lstrip("012&")
    if not stripped.startswith(">"):
        return None
    remainder = stripped.lstrip(">").lstrip("|")
    if remainder.startswith("&"):
        return _REDIRECT_NO_TARGET
    return remainder


def _looks_like_path(token: str) -> bool:
    return "/" in token or "." in Path(token).name


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _settings_path(root: Path, settings_file: str, local: bool) -> Path:
    if settings_file:
        return Path(settings_file).expanduser().resolve()
    name = "settings.local.json" if local else "settings.json"
    return root / ".claude" / name


def _managed_hooks(
    root: Path,
    workspace_path: Path | str,
    *,
    strict: bool,
) -> dict[str, dict[str, Any]]:
    executable = _palari_executable(root)
    workspace_argument = _workspace_argument(root, workspace_path)
    strict_suffix = " --strict" if strict else ""

    def command(event: str, suffix: str = "") -> dict[str, Any]:
        return {
            "type": "command",
            "command": (
                f'{executable} --workspace "{workspace_argument}" claude hook {event}{suffix}'
            ),
            "timeout": HOOK_TIMEOUT_SECONDS,
        }

    return {
        "PreToolUse": {
            "matcher": PRE_TOOL_USE_MATCHER,
            "hooks": [command("pre-tool-use", strict_suffix)],
        },
        "Stop": {"hooks": [command("stop")]},
        "SessionStart": {"hooks": [command("session-start")]},
    }


def _palari_executable(root: Path) -> str:
    """Prefer a project-local wrapper so hooks work without a pip install."""
    if (root / "bin" / "palari").is_file():
        return '"$CLAUDE_PROJECT_DIR/bin/palari"'
    return "palari"


def _workspace_argument(root: Path, workspace_path: Path | str) -> str:
    workspace_dir = workspace_file_path(workspace_path).parent
    try:
        relative = workspace_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(workspace_dir)
    if relative == ".":
        return "$CLAUDE_PROJECT_DIR"
    return f"$CLAUDE_PROJECT_DIR/{relative}"


def _is_managed_entry(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks", [])
    if not isinstance(hooks, list):
        return False
    return any(
        isinstance(hook, dict)
        and HOOK_COMMAND_MARKER in str(hook.get("command", ""))
        and "palari" in str(hook.get("command", ""))
        for hook in hooks
    )


def _install_message(status: str, target: Path) -> str:
    if status == "installed":
        return f"Palari hooks written to {target}. Claude Code loads them on the next session."
    if status == "removed":
        return f"Palari hooks removed from {target}."
    return f"{target} already matches the requested hook configuration."


def _workspace_belongs_to_repo(workspace_path: Path | str, root: Path) -> bool:
    try:
        workspace_file_path(workspace_path).parent.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True
