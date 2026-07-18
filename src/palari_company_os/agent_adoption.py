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
import shutil
import sys
from pathlib import Path
from typing import Any, TextIO

from .agent_file_changes import git_repo_root
from .git_hooks import install_git_hook
from .store import workspace_file_path
from .workspace import Workspace, WorkspaceError


AGENTS_START = "<!-- palari:agent-contract:start -->"
AGENTS_END = "<!-- palari:agent-contract:end -->"
CODEX_MARKER = "agent adopt --host codex --hook-event"
HOOK_TIMEOUT_SECONDS = 20
SUPPORTED_HOSTS = ("claude", "codex", "cursor", "devin", "glm", "generic")


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
    workspace = Workspace.load(workspace_path)
    if not _workspace_inside_project(workspace_path, root):
        raise WorkspaceError(
            "agent adoption requires the Palari workspace to be inside the project"
        )
    _assert_palari_executable(root)
    actor = _resolve_palari(workspace, palari_id)

    agents_path = root / "AGENTS.md"
    _assert_local_target(root, agents_path)
    agents_before = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    agents_after = _merge_agents_contract(agents_before, actor)

    codex_plan: tuple[Path, dict[str, Any], dict[str, Any]] | None = None
    if selected_host == "codex":
        codex_plan = _prepare_codex_hooks(root, workspace_path)
    elif selected_host == "claude":
        _preflight_claude_settings(root)

    # Install the cross-host structural gate first.  It refuses unmanaged
    # pre-commit hooks instead of overwriting them.
    git_result = install_git_hook(root, workspace_path)
    if git_result.get("status") == "error":
        raise WorkspaceError(str(git_result.get("message", "Git hook installation failed")))

    changed_files: list[str] = []
    if agents_after != agents_before:
        agents_path.write_text(agents_after, encoding="utf-8")
        changed_files.append(_relative(agents_path, root))

    host_result: dict[str, Any]
    if selected_host == "claude":
        from .claude_hooks import install_hooks

        host_result = install_hooks(root, workspace_path)
        if host_result.get("status") == "error":
            raise WorkspaceError(str(host_result.get("message", "Claude hook installation failed")))
        settings_file = str(host_result.get("settings_file", ""))
        if host_result.get("changed") and settings_file:
            changed_files.append(_relative(Path(settings_file), root))
    elif selected_host == "codex":
        assert codex_plan is not None
        target, before, after = codex_plan
        changed = after != before
        if changed:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
            changed_files.append(_relative(target, root))
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
            "command": _mcp_command(root, workspace_path),
            "authority": "agent-loop-only; no human acceptance or external-write authority",
        },
        "next_commands": [
            f"palari agent start --next --as {actor} --json",
            f"palari agent next --as {actor} --json",
        ],
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
) -> dict[str, Any]:
    """Run one internal host hook and return the host-native decision JSON."""
    selected = host.strip().lower()
    if selected != "codex":
        return {"systemMessage": f"Unsupported Palari agent hook host: {selected}"}
    try:
        raw = (stdin if stdin is not None else sys.stdin).read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise ValueError("hook input must be a JSON object")
        return _handle_codex_hook(event, payload, workspace_path)
    except Exception as exc:  # noqa: BLE001 - security hook emits a native fail-closed result
        reason = f"Palari could not verify the Codex hook input: {exc}"
        if event == "pre-tool-use":
            return _codex_deny(reason)
        if event == "stop":
            return {"decision": "block", "reason": reason}
        return {"systemMessage": reason}


def _handle_codex_hook(
    event: str,
    payload: dict[str, Any],
    workspace_path: Path | str,
) -> dict[str, Any]:
    from .claude_hooks import handle_hook_event

    if event in {"session-start", "stop"}:
        return handle_hook_event(event, payload, workspace_path)
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
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    target = root / ".codex" / "hooks.json"
    _assert_local_target(root, target)
    if target.exists():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkspaceError(f"{target} is not valid JSON: {exc}") from exc
        if not isinstance(loaded, dict):
            raise WorkspaceError(f"{target} must contain a JSON object")
        before = loaded
    else:
        before = {}
    after = json.loads(json.dumps(before))
    hooks = after.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise WorkspaceError(f"{target} hooks must be a JSON object")
    managed = _codex_managed_hooks(root, workspace_path)
    for event in ("SessionStart", "PreToolUse", "Stop"):
        entries = hooks.get(event, [])
        if not isinstance(entries, list):
            raise WorkspaceError(f"{target} hooks.{event} must be a JSON array")
        hooks[event] = [entry for entry in entries if not _is_codex_managed(entry)] + [
            managed[event]
        ]
    after.setdefault("description", "Project-local agent lifecycle hooks.")
    return target, before, after


def _preflight_claude_settings(root: Path) -> None:
    target = root / ".claude" / "settings.json"
    _assert_local_target(root, target)
    if not target.exists():
        return
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceError(f"{target} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkspaceError(f"{target} must contain a JSON object")
    hooks = data.get("hooks")
    if hooks is None:
        return
    if not isinstance(hooks, dict):
        raise WorkspaceError(f"{target} hooks must be a JSON object")
    for event in ("PreToolUse", "Stop", "SessionStart"):
        if event in hooks and not isinstance(hooks[event], list):
            raise WorkspaceError(f"{target} hooks.{event} must be a JSON array")


def _codex_managed_hooks(
    root: Path,
    workspace_path: Path | str,
) -> dict[str, dict[str, Any]]:
    executable = _host_executable(root)
    workspace_arg = _host_workspace_argument(root, workspace_path)

    def command(event: str) -> dict[str, Any]:
        return {
            "type": "command",
            "command": (
                f'{executable} --workspace "{workspace_arg}" '
                f"agent adopt --host codex --hook-event {event}"
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
            "matcher": "^(Bash|apply_patch|Edit|Write)$",
            "hooks": [command("pre-tool-use")],
        },
        "Stop": {"hooks": [command("stop")]},
    }


def _is_codex_managed(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks", [])
    return isinstance(hooks, list) and any(
        isinstance(hook, dict) and CODEX_MARKER in str(hook.get("command", ""))
        for hook in hooks
    )


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
    prefix = existing.rstrip()
    return (prefix + "\n\n" if prefix else "") + block + "\n"


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


def _host_executable(root: Path) -> str:
    if (root / "bin" / "palari").is_file():
        return '"$(git rev-parse --show-toplevel)/bin/palari"'
    return "palari"


def _host_workspace_argument(root: Path, workspace_path: Path | str) -> str:
    workspace_dir = workspace_file_path(workspace_path).parent.resolve()
    relative = workspace_dir.relative_to(root.resolve()).as_posix()
    suffix = "" if relative == "." else f"/{relative}"
    return f"$(git rev-parse --show-toplevel){suffix}"


def _mcp_command(root: Path, workspace_path: Path | str) -> str:
    executable = "./bin/palari" if (root / "bin" / "palari").is_file() else "palari"
    workspace_dir = workspace_file_path(workspace_path).parent.resolve()
    relative = workspace_dir.relative_to(root.resolve()).as_posix()
    workspace_arg = "." if relative == "." else relative
    return f"{executable} --workspace {workspace_arg} mcp serve"


def _workspace_inside_project(workspace_path: Path | str, root: Path) -> bool:
    try:
        workspace_file_path(workspace_path).parent.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _assert_local_target(root: Path, target: Path) -> None:
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError(f"adoption target is outside the project: {target}") from exc
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise WorkspaceError(f"adoption target uses a symlink: {cursor}")
    if target.exists() and not target.is_file():
        raise WorkspaceError(f"adoption target is not a regular file: {target}")


def _assert_palari_executable(root: Path) -> None:
    local = root / "bin" / "palari"
    if local.exists():
        if local.is_file() and os.access(local, os.X_OK):
            return
        raise WorkspaceError(f"project-local Palari wrapper is not executable: {local}")
    if shutil.which("palari") is None:
        raise WorkspaceError(
            "Palari is not on PATH and this project has no executable bin/palari wrapper"
        )


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
