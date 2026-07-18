"""One-action, provider-neutral adoption for local agent hosts.

Adoption installs only local, inspectable guardrails:

* a small managed contract in ``AGENTS.md``;
* the existing Git commit boundary gate for every host;
* a native session hook only for hosts whose protocol Palari implements.

It never writes user-global configuration, credentials, provider state, or
human authority.  Host profiles are deliberately explicit about which
properties are structural and which remain advisory.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO

from .agent_file_changes import git_repo_root
from .git_hooks import install_git_hook
from .store import workspace_file_path
from .workspace import Workspace, WorkspaceError


AGENTS_START = "<!-- palari:agent-contract:start -->"
AGENTS_END = "<!-- palari:agent-contract:end -->"
HOOK_TIMEOUT_SECONDS = 20
SUPPORTED_HOSTS = ("claude", "codex", "cursor", "devin", "glm", "generic")
PROJECT_WRAPPER = """#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"

exec python3 -S -m palari_company_os "$@"
"""


def adopt_agent_host(
    workspace_path: Path | str,
    *,
    project_dir: Path | str = ".",
    host: str = "generic",
    palari_id: str = "",
) -> dict[str, Any]:
    """Install the strongest honest local profile available for ``host``.

    The operation is idempotent.  Existing non-Palari instructions and hook
    entries are preserved.  A malformed managed block, invalid host JSON, or
    an unmanaged Git pre-commit hook blocks adoption before project
    instructions or host settings are changed.
    """
    selected_host = host.strip().lower()
    if selected_host not in SUPPORTED_HOSTS:
        raise WorkspaceError(
            "--host must be one of: " + ", ".join(SUPPORTED_HOSTS)
        )

    root = Path(project_dir).expanduser().resolve()
    repo_root = git_repo_root(root)
    if repo_root is None:
        raise WorkspaceError("agent adoption requires a Git repository")
    root = repo_root
    if not _workspace_inside_project(workspace_path, root):
        raise WorkspaceError(
            "agent adoption requires the Palari workspace to be inside the project"
        )
    workspace = Workspace.load(workspace_path)
    executable = _assert_palari_executable(root)
    actor = _resolve_palari(workspace, palari_id)

    agents_path = root / "AGENTS.md"
    _assert_local_target(root, agents_path)
    agents_existed = agents_path.exists()
    try:
        agents_before = agents_path.read_text(encoding="utf-8") if agents_existed else ""
    except (OSError, UnicodeError) as exc:
        raise WorkspaceError(f"{agents_path} cannot be inspected safely: {exc}") from exc
    agents_after = _merge_agents_contract(agents_before, actor)

    codex_plan: tuple[Path, dict[str, Any], dict[str, Any]] | None = None
    claude_plan: tuple[Path, dict[str, Any], dict[str, Any]] | None = None
    if selected_host == "codex":
        codex_plan = _prepare_codex_hooks(root, workspace_path, executable)
    elif selected_host == "claude":
        claude_plan = _prepare_claude_hooks(root, workspace_path, executable)

    host_plan = codex_plan or claude_plan
    host_target = host_plan[0] if host_plan else None
    host_existed = bool(host_target and host_target.exists())
    host_before_text = ""
    if host_target and host_existed:
        try:
            host_before_text = host_target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise WorkspaceError(f"{host_target} cannot be inspected safely: {exc}") from exc

    changed_files: list[str] = []
    try:
        if agents_after != agents_before:
            agents_path.write_text(agents_after, encoding="utf-8")
            changed_files.append(_relative(agents_path, root))
        if host_plan is not None:
            target, before, after = host_plan
            if after != before:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
                changed_files.append(_relative(target, root))

        # Install the cross-host structural gate last. If it refuses a foreign
        # or non-local target, restore the exact instruction/configuration bytes
        # instead of leaving a half-installed profile.
        git_result = install_git_hook(
            root,
            workspace_path,
            palari_executable=executable,
        )
        if git_result.get("status") == "error":
            raise WorkspaceError(
                str(git_result.get("message", "Git hook installation failed"))
            )
    except Exception as exc:  # noqa: BLE001 - restore exact pre-adoption state
        _restore_local_file(agents_path, existed=agents_existed, content=agents_before, root=root)
        if host_target is not None:
            _restore_local_file(
                host_target,
                existed=host_existed,
                content=host_before_text,
                root=root,
            )
        if isinstance(exc, WorkspaceError):
            raise
        raise WorkspaceError(f"agent adoption failed safely and was rolled back: {exc}") from exc

    host_result: dict[str, Any]
    if selected_host == "claude":
        assert claude_plan is not None
        target, before, after = claude_plan
        changed = after != before
        host_result = {
            "status": "installed" if changed else "unchanged",
            "changed": changed,
            "settings_file": str(target),
            "activation": "active",
            "next_action": "Start a new Claude Code session in this repository.",
        }
    elif selected_host == "codex":
        assert codex_plan is not None
        target, before, after = codex_plan
        changed = after != before
        host_result = {
            "status": "installed" if changed else "unchanged",
            "changed": changed,
            "settings_file": str(target),
            "activation": "review-project-hooks-in-codex",
            "next_action": "Open /hooks in Codex and trust the reviewed project hook definition.",
        }
    else:
        host_result = {
            "status": "portable",
            "changed": False,
            "activation": "no-proven-session-hook",
            "next_action": "Start the host in this repository; it must follow AGENTS.md.",
        }

    profile = _host_profile(selected_host)
    return {
        "schema_version": "palari.agent_adoption.v1",
        "status": "ready",
        "host": selected_host,
        "project": str(root),
        "executable": executable,
        "workspace": workspace.name,
        "palari_id": actor,
        "changed": bool(changed_files or git_result.get("changed")),
        "changed_files": sorted(changed_files),
        "contract_file": str(agents_path),
        "git_gate": git_result,
        "host_adapter": host_result,
        "enforcement": profile,
        "mcp": {
            "transport": "stdio",
            "command": _mcp_command(executable, workspace_path),
            "authority": "agent-loop-only; no human acceptance or external-write authority",
        },
        "next_commands": _agent_next_commands(executable, workspace_path, actor),
        "limitations": [
            "Git enforcement applies at commit time and is not a filesystem sandbox.",
            "Project-local host hooks may require the host user to review and trust them.",
            "Actor identifiers remain declared identities, not same-OS-user authentication.",
            "Adoption grants no review, acceptance, merge, push, deployment, provider, or external-write authority.",
        ],
    }


def run_agent_hook(
    host: str,
    event: str,
    workspace_path: Path | str,
    *,
    stdin: TextIO | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Run one internal host hook and return the host-native decision JSON."""
    selected = host.strip().lower()
    if selected not in {"claude", "codex"}:
        return {"systemMessage": f"Unsupported Palari agent hook host: {selected}"}
    try:
        raw = (stdin if stdin is not None else sys.stdin).read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise ValueError("hook input must be a JSON object")
        security_error = _hook_payload_security_error(payload)
        if event == "pre-tool-use" and security_error:
            return _codex_deny(security_error)
        with _allow_agent_advance():
            if selected == "claude":
                from .claude_hooks import handle_hook_event

                return handle_hook_event(
                    event,
                    payload,
                    workspace_path,
                    strict=strict,
                )
            return _handle_codex_hook(event, payload, workspace_path)
    except Exception as exc:  # noqa: BLE001 - security hook emits a native fail-closed result
        reason = f"Palari could not verify the Codex hook input: {exc}"
        if selected == "claude":
            return {}
        if event == "pre-tool-use":
            return _codex_deny(reason)
        if event == "stop":
            return {"continue": False, "stopReason": reason}
        return {"systemMessage": reason}


def _handle_codex_hook(
    event: str,
    payload: dict[str, Any],
    workspace_path: Path | str,
) -> dict[str, Any]:
    from .claude_hooks import handle_hook_event

    if event == "session-start":
        return handle_hook_event(event, payload, workspace_path)
    if event == "stop":
        decision = handle_hook_event(event, payload, workspace_path)
        if decision.get("decision") == "block":
            return {
                "continue": False,
                "stopReason": str(decision.get("reason", "Palari boundary check failed")),
            }
        return decision
    if event != "pre-tool-use":
        return {}

    tool_name = str(payload.get("tool_name", ""))
    if tool_name == "Bash":
        return _codex_compatible_decision(
            handle_hook_event("pre-tool-use", payload, workspace_path)
        )
    if tool_name != "apply_patch":
        return {}

    tool_input = payload.get("tool_input")
    command = str(tool_input.get("command", "")) if isinstance(tool_input, dict) else ""
    targets = _apply_patch_targets(command)
    if not targets:
        return _codex_deny(
            "Palari could not derive an exact file target from apply_patch; use a directly inspectable patch."
        )
    reasons: list[str] = []
    for target in targets:
        probe = dict(payload)
        probe["tool_name"] = "Write"
        probe["tool_input"] = {"file_path": target}
        decision = _codex_compatible_decision(
            handle_hook_event("pre-tool-use", probe, workspace_path)
        )
        specific = decision.get("hookSpecificOutput", {})
        if isinstance(specific, dict) and specific.get("permissionDecision") == "deny":
            reasons.append(str(specific.get("permissionDecisionReason", "blocked")))
    if reasons:
        return _codex_deny("; ".join(dict.fromkeys(reasons)))
    return {}


def _codex_compatible_decision(result: dict[str, Any]) -> dict[str, Any]:
    specific = result.get("hookSpecificOutput")
    if not isinstance(specific, dict):
        return result
    decision = str(specific.get("permissionDecision", ""))
    if decision != "ask":
        return result
    return _codex_deny(
        str(specific.get("permissionDecisionReason", "Palari requires human review"))
        + " Codex PreToolUse has no ask decision, so Palari denies this call safely."
    )


def _codex_deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


@contextmanager
def _allow_agent_advance() -> Any:
    """Classify convergence as the packet-bound agent mutation it already is.

    The legacy Claude adapter owns the common shell parser. Adoption routes
    both native adapters through this narrow compatibility layer until that
    expert module can be versioned independently. The entry is removed again
    after each hook call so no request-global authority is cached.
    """

    from . import claude_hooks

    command = ("agent", "advance")
    safe_present = command in claude_hooks.SAFE_AGENT_PALARI_COMMANDS
    mutating_present = command in claude_hooks.MUTATING_AGENT_PALARI_COMMANDS
    claude_hooks.SAFE_AGENT_PALARI_COMMANDS.add(command)
    claude_hooks.MUTATING_AGENT_PALARI_COMMANDS.add(command)
    try:
        yield
    finally:
        if not safe_present:
            claude_hooks.SAFE_AGENT_PALARI_COMMANDS.discard(command)
        if not mutating_present:
            claude_hooks.MUTATING_AGENT_PALARI_COMMANDS.discard(command)


def _apply_patch_targets(command: str) -> list[str]:
    targets: list[str] = []
    for line in command.splitlines():
        match = re.match(r"\*\*\* (?:Add|Update|Delete) File: (.+)$", line)
        if match:
            target = match.group(1).strip()
        else:
            moved = re.match(r"\*\*\* Move to: (.+)$", line)
            if not moved:
                continue
            target = moved.group(1).strip()
        if target and target not in targets:
            targets.append(target)
    return targets


def _prepare_codex_hooks(
    root: Path,
    workspace_path: Path | str,
    executable: str,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    target = root / ".codex" / "hooks.json"
    _assert_local_target(root, target)
    before = _read_host_json(target)
    after = json.loads(json.dumps(before))
    hooks = after.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise WorkspaceError(f"{target} hooks must be a JSON object")
    managed = _codex_managed_hooks(workspace_path, executable)
    for event in ("SessionStart", "PreToolUse", "Stop"):
        entries = hooks.get(event, [])
        if not isinstance(entries, list):
            raise WorkspaceError(f"{target} hooks.{event} must be a JSON array")
        hooks[event] = _without_managed_host_hooks(entries, "codex") + [managed[event]]
    after.setdefault("description", "Project-local agent lifecycle hooks.")
    return target, before, after


def _prepare_claude_hooks(
    root: Path,
    workspace_path: Path | str,
    executable: str,
    *,
    target: Path | None = None,
    strict: bool = False,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    target = target or root / ".claude" / "settings.json"
    _assert_local_target(root, target)
    before = _read_host_json(target)
    after = json.loads(json.dumps(before))
    hooks = after.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise WorkspaceError(f"{target} hooks must be a JSON object")
    managed = _claude_managed_hooks(workspace_path, executable, strict=strict)
    for event in ("PreToolUse", "Stop", "SessionStart"):
        entries = hooks.get(event, [])
        if not isinstance(entries, list):
            raise WorkspaceError(f"{target} hooks.{event} must be a JSON array")
        hooks[event] = _without_managed_host_hooks(entries, "claude") + [managed[event]]
    return target, before, after


def install_claude_host_hooks(
    project_dir: Path | str,
    workspace_path: Path | str,
    *,
    settings_file: str = "",
    local: bool = False,
    strict: bool = False,
    remove: bool = False,
) -> dict[str, Any]:
    """Install the compatible Claude surface through the hardened merger."""

    root = Path(project_dir).expanduser().resolve()
    repo_root = git_repo_root(root)
    if repo_root is None:
        raise WorkspaceError("Claude hook installation requires a Git repository")
    root = repo_root
    if not _workspace_inside_project(workspace_path, root):
        raise WorkspaceError("Claude hooks require the Palari workspace inside the project")
    executable = _assert_palari_executable(root)
    target = (
        Path(settings_file).expanduser().resolve()
        if settings_file
        else root / ".claude" / ("settings.local.json" if local else "settings.json")
    )
    target, before, after = _prepare_claude_hooks(
        root,
        workspace_path,
        executable,
        target=target,
        strict=strict,
    )
    if remove:
        hooks = after.get("hooks", {})
        if isinstance(hooks, dict):
            for event in ("PreToolUse", "Stop", "SessionStart"):
                entries = hooks.get(event, [])
                if isinstance(entries, list):
                    kept = _without_managed_host_hooks(entries, "claude")
                    if kept:
                        hooks[event] = kept
                    else:
                        hooks.pop(event, None)
            if not hooks:
                after.pop("hooks", None)
    changed = after != before
    if changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
    return {
        "schema_version": "palari.claude_install.v1",
        "status": "removed" if remove and changed else "installed" if changed else "unchanged",
        "changed": changed,
        "settings_file": str(target),
        "workspace": str(workspace_file_path(workspace_path).parent.resolve()),
        "strict": strict,
        "palari_on_path": True,
        "hooks": {},
        "message": (
            f"Palari hooks removed from {target}."
            if remove and changed
            else f"Palari hooks written to {target}. Claude Code loads them on the next session."
            if changed
            else f"Palari hooks already match {target}."
        ),
    }


def _read_host_json(target: Path) -> dict[str, Any]:
    if not target.exists():
        return {}
    try:
        loaded = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkspaceError(f"{target} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise WorkspaceError(f"{target} must contain a JSON object")
    return loaded


def _codex_managed_hooks(
    workspace_path: Path | str,
    executable: str,
) -> dict[str, dict[str, Any]]:
    def command(event: str) -> dict[str, Any]:
        return {
            "type": "command",
            "command": _host_hook_command(
                executable,
                workspace_path,
                host="codex",
                event=event,
            ),
            "timeout": HOOK_TIMEOUT_SECONDS,
            "statusMessage": "Checking Palari work boundary",
        }

    return {
        "SessionStart": {
            "matcher": "startup|resume|clear|compact",
            "hooks": [command("session-start")],
        },
        "PreToolUse": {
            "matcher": "^(Bash|apply_patch)$",
            "hooks": [command("pre-tool-use")],
        },
        "Stop": {"hooks": [command("stop")]},
    }


def _claude_managed_hooks(
    workspace_path: Path | str,
    executable: str,
    *,
    strict: bool,
) -> dict[str, dict[str, Any]]:
    def command(event: str) -> dict[str, Any]:
        return {
            "type": "command",
            "command": _claude_hook_command(
                executable,
                workspace_path,
                event=event,
                strict=strict and event == "pre-tool-use",
            ),
            "timeout": HOOK_TIMEOUT_SECONDS,
        }

    return {
        "PreToolUse": {
            "matcher": "Write|Edit|NotebookEdit|Bash",
            "hooks": [command("pre-tool-use")],
        },
        "Stop": {"hooks": [command("stop")]},
        "SessionStart": {"hooks": [command("session-start")]},
    }


def _without_managed_host_hooks(entries: list[Any], host: str) -> list[Any]:
    """Remove only Palari-owned hook calls, preserving co-located foreign hooks."""

    kept: list[Any] = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
            kept.append(entry)
            continue
        foreign_hooks = [
            hook for hook in entry["hooks"] if not _is_managed_host_hook(hook, host)
        ]
        if len(foreign_hooks) == len(entry["hooks"]):
            kept.append(entry)
            continue
        if foreign_hooks:
            preserved = json.loads(json.dumps(entry))
            preserved["hooks"] = foreign_hooks
            kept.append(preserved)
    return kept


def _is_managed_host_hook(hook: Any, host: str) -> bool:
    if not isinstance(hook, dict) or hook.get("type") != "command":
        return False
    command = str(hook.get("command", ""))
    try:
        tokens = _shell_command_tokens(command)
    except ValueError:
        return False
    if not tokens or any(_is_shell_control(token) for token in tokens):
        return False
    executable = tokens[0]
    if (
        not (
            _has_canonical_executable_word(command, executable)
            or _has_legacy_claude_executable_word(command, executable, host)
        )
        or Path(executable).name != "palari"
    ):
        return False
    arguments = tokens[1:]
    if arguments[:1] == ["--workspace"] and len(arguments) >= 2:
        arguments = arguments[2:]
    elif arguments and arguments[0].startswith("--workspace="):
        arguments = arguments[1:]

    events = {"pre-tool-use", "stop", "session-start"}
    if (
        len(arguments) == 6
        and arguments[0] == "init"
        and arguments[2:5] == ["--host", host, "--hook-event"]
        and arguments[5] in events
    ):
        return True
    if (
        len(arguments) == 5
        and arguments[:4] == ["agent", "adopt", "--host", host]
        and arguments[4].startswith("--hook-event=")
        and arguments[4].split("=", 1)[1] in events
    ):
        return True
    if (
        len(arguments) == 6
        and arguments[:5] == ["agent", "adopt", "--host", host, "--hook-event"]
        and arguments[5] in events
    ):
        return True
    if host != "claude" or arguments[:2] != ["claude", "hook"]:
        return False
    return (
        len(arguments) == 3 and arguments[2] in events
    ) or (
        len(arguments) == 4
        and arguments[2] == "pre-tool-use"
        and arguments[3] == "--strict"
    )


def _has_canonical_executable_word(command: str, executable: str) -> bool:
    """Accept only the static shell word emitted by :func:`shlex.join`."""

    expected = shlex.quote(executable)
    stripped = command.lstrip()
    return stripped == expected or stripped.startswith(expected + " ")


def _has_legacy_claude_executable_word(
    command: str,
    executable: str,
    host: str,
) -> bool:
    """Recognize the exact project-variable launcher emitted before v0.2."""

    expected = '"$CLAUDE_PROJECT_DIR/bin/palari"'
    stripped = command.lstrip()
    return (
        host == "claude"
        and executable == "$CLAUDE_PROJECT_DIR/bin/palari"
        and (stripped == expected or stripped.startswith(expected + " "))
    )


def _hook_payload_security_error(payload: dict[str, Any]) -> str:
    """Reject Palari commands whose CLI meaning is structurally ambiguous."""

    if str(payload.get("tool_name", "")) != "Bash":
        return ""
    tool_input = payload.get("tool_input")
    command = str(tool_input.get("command", "")) if isinstance(tool_input, dict) else ""
    try:
        tokens = _shell_command_tokens(command)
    except ValueError:
        return ""
    if not any(Path(token).name == "palari" for token in tokens):
        return ""
    declarations = sum(
        token == "--workspace" or token.startswith("--workspace=")
        for token in tokens
    )
    if declarations > 1:
        return (
            "Palari command has multiple --workspace declarations; the CLI uses the "
            "last value, so the hook denies this ambiguous command. Use exactly one "
            "workspace bound to the active packet."
        )
    return ""


def _shell_command_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _is_shell_control(token: str) -> bool:
    return bool(token) and all(character in ";&|" for character in token)


def _host_hook_command(
    executable: str,
    workspace_path: Path | str,
    *,
    host: str,
    event: str,
) -> str:
    workspace = str(workspace_file_path(workspace_path).parent.resolve())
    return shlex.join(
        [
            executable,
            "--workspace",
            workspace,
            "init",
            workspace,
            "--host",
            host,
            "--hook-event",
            event,
        ]
    )


def _claude_hook_command(
    executable: str,
    workspace_path: Path | str,
    *,
    event: str,
    strict: bool,
) -> str:
    workspace = str(workspace_file_path(workspace_path).parent.resolve())
    command = [executable, "--workspace", workspace, "claude", "hook", event]
    if strict:
        command.append("--strict")
    return shlex.join(command)


def _merge_agents_contract(existing: str, palari_id: str) -> str:
    start_count = existing.count(AGENTS_START)
    end_count = existing.count(AGENTS_END)
    if start_count != end_count or start_count > 1:
        raise WorkspaceError(
            "AGENTS.md has a malformed Palari managed block; repair the markers before adoption"
        )
    block = _agents_contract(palari_id)
    if start_count == 1:
        start = existing.index(AGENTS_START)
        end = existing.index(AGENTS_END, start) + len(AGENTS_END)
        return existing[:start] + block + existing[end:]
    if has_portable_agent_contract(existing):
        return existing
    prefix = existing.rstrip()
    return (prefix + "\n\n" if prefix else "") + block + "\n"


def has_portable_agent_contract(content: str) -> bool:
    """Return whether existing guidance already declares the core safe loop."""
    lowered = content.lower()
    return all(
        phrase in lowered
        for phrase in (
            "palari agent start --next",
            "palari agent advance",
            "human",
        )
    )


def _agents_contract(palari_id: str) -> str:
    return f"""{AGENTS_START}
## Palari governed work

Before changing files, claim one bounded work item:

```bash
palari agent start --next --as {palari_id} --json
```

Follow the returned packet. Stay inside its read/write paths, stop at every
human or external-write boundary, commit the bounded change, then run:

```bash
palari agent advance WORK-ID --as {palari_id} --json
```

Use `palari agent doctor WORK-ID --as {palari_id} --json` for one actionable
diagnosis. Never manufacture review, human acceptance, merge, push,
deployment, provider, credential, or external-write authority.
{AGENTS_END}"""


def _resolve_palari(workspace: Workspace, explicit: str) -> str:
    if explicit.strip():
        selected = explicit.strip()
        if workspace.palari(selected) is None:
            raise WorkspaceError(f"--as references unknown Palari {selected}")
        return selected
    ids = [item.id for item in workspace.palaris]
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise WorkspaceError("workspace has no Palari identity; run palari init first")
    raise WorkspaceError(
        f"workspace has {len(ids)} Palaris ({', '.join(ids)}); pass --as to choose one"
    )


def _host_profile(host: str) -> dict[str, Any]:
    session = "structural" if host in {"claude", "codex"} else "advisory"
    activation = "active"
    if host == "codex":
        activation = "requires-project-hook-trust"
    elif session == "advisory":
        activation = "unsupported-by-proven-host-adapter"
    return {
        "profile": f"palari.{host}.v1",
        "portable_contract": "declared",
        "commit_boundary": "structural",
        "session_boundary": session,
        "session_activation": activation,
        "human_authority": "palari-enforced",
        "external_write_authority": "palari-enforced",
    }


def _mcp_command(executable: str, workspace_path: Path | str) -> str:
    workspace = str(workspace_file_path(workspace_path).parent.resolve())
    return shlex.join([executable, "--workspace", workspace, "mcp", "serve"])


def _agent_next_commands(
    executable: str,
    workspace_path: Path | str,
    actor: str,
) -> list[str]:
    workspace = str(workspace_file_path(workspace_path).parent.resolve())
    base = [executable, "--workspace", workspace, "agent"]
    return [
        shlex.join([*base, "start", "--next", "--as", actor, "--json"]),
        shlex.join([*base, "next", "--as", actor, "--json"]),
    ]


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


def _assert_local_target(root: Path, target: Path) -> None:
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError(f"adoption target is outside the project: {target}") from exc
    cursor = root
    parts = relative.parts
    for index, part in enumerate(parts):
        cursor = cursor / part
        if cursor.is_symlink():
            raise WorkspaceError(f"adoption target uses a symlink: {cursor}")
        if index < len(parts) - 1 and cursor.exists() and not cursor.is_dir():
            raise WorkspaceError(
                f"adoption target parent is not a directory: {cursor}"
            )
    if target.exists() and not target.is_file():
        raise WorkspaceError(f"adoption target is not a regular file: {target}")


def _assert_palari_executable(root: Path) -> str:
    local = root / "bin" / "palari"
    if local.exists() or local.is_symlink():
        if local.is_symlink():
            raise WorkspaceError(
                f"project-local Palari wrapper must not be a symlink: {local}"
            )
        _assert_local_target(root, local)
        if not local.is_file() or not os.access(local, os.X_OK):
            raise WorkspaceError(f"project-local Palari wrapper is not executable: {local}")
        try:
            wrapper = local.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise WorkspaceError(f"project-local Palari wrapper is unreadable: {exc}") from exc
        wrapper_lines = tuple(
            line
            for line in wrapper.replace("\r\n", "\n").splitlines()
            if line.strip()
        )
        packaged_lines = tuple(line for line in PROJECT_WRAPPER.splitlines() if line.strip())
        if wrapper_lines != packaged_lines:
            raise WorkspaceError(
                "project-local bin/palari is not an inspectable Palari launcher; "
                "restore the packaged wrapper or remove it and install palari on PATH"
            )
        return str(local.resolve())
    current = _current_palari_executable()
    if current is not None:
        return str(current)
    installed = shutil.which("palari")
    if installed is None:
        raise WorkspaceError(
            "Palari is not on PATH and this project has no executable bin/palari wrapper"
        )
    return str(_validated_palari_invocation(Path(installed), source="PATH"))


def _current_palari_executable() -> Path | None:
    """Return the absolute entrypoint that is already running, when inspectable."""

    invoked = Path(sys.argv[0]).expanduser()
    if invoked.name != "palari" or not invoked.is_absolute():
        return None
    try:
        return _validated_palari_invocation(invoked, source="current entrypoint")
    except WorkspaceError:
        return None


def _validated_palari_invocation(invoked: Path, *, source: str) -> Path:
    invocation = invoked.expanduser()
    if not invocation.is_absolute():
        invocation = (Path.cwd() / invocation).absolute()
    if invocation.name != "palari":
        raise WorkspaceError(f"Palari {source} must be invoked through a path named palari")
    try:
        target = invocation.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceError(f"Palari {source} cannot be resolved safely: {exc}") from exc
    if not target.is_file() or not os.access(target, os.X_OK):
        raise WorkspaceError(
            f"Palari {source} is not a regular executable file: {invocation}"
        )
    return invocation


def _restore_local_file(
    path: Path,
    *,
    existed: bool,
    content: str,
    root: Path,
) -> None:
    try:
        if existed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return
        if path.exists() and path.is_file():
            path.unlink()
        parent = path.parent
        while parent != root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    except OSError as exc:
        raise WorkspaceError(f"could not restore {path} after adoption failure: {exc}") from exc


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
