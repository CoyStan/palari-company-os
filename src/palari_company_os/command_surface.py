from __future__ import annotations

from pathlib import Path
from shlex import quote, split
from typing import Any

from .store import workspace_file_path


def palari_workspace_command(
    workspace_path: Path | str,
    *arguments: str,
) -> str:
    """Render one shell-safe Palari command bound to an exact workspace root."""

    data_path = workspace_file_path(workspace_path).resolve(strict=False)
    selector = data_path.parent if data_path.name == "workspace.json" else data_path
    tokens = ("palari", "--workspace", str(selector), *arguments)
    return " ".join(quote(token) for token in tokens)


def bind_palari_workspace_command(
    workspace_path: Path | str,
    command: str,
) -> str:
    """Bind one static emitted Palari command to the exact selected workspace."""

    try:
        tokens = split(command)
    except ValueError:
        return command
    if not tokens or tokens[0] != "palari":
        return command
    if len(tokens) >= 2 and (
        tokens[1] == "--workspace" or tokens[1].startswith("--workspace=")
    ):
        return command
    return palari_workspace_command(workspace_path, *tokens[1:])


def palari_command_parts(command: str) -> tuple[str, ...]:
    """Return Palari arguments after an optional global workspace selector."""

    try:
        tokens = split(command)
    except ValueError:
        return ()
    if not tokens or tokens[0] != "palari":
        return ()
    index = 1
    if index < len(tokens) and tokens[index] == "--workspace":
        if index + 1 >= len(tokens):
            return ()
        index += 2
    elif index < len(tokens) and tokens[index].startswith("--workspace="):
        if not tokens[index].split("=", 1)[1]:
            return ()
        index += 1
    return tuple(tokens[index:])


def bind_palari_command_payload(
    workspace_path: Path | str,
    value: Any,
    *,
    _command_context: bool = False,
) -> Any:
    """Bind command-bearing payload fields without rewriting prose."""

    if isinstance(value, str):
        if _command_context and palari_command_parts(value):
            return bind_palari_workspace_command(workspace_path, value)
        return value
    if isinstance(value, list):
        return [
            bind_palari_command_payload(
                workspace_path,
                item,
                _command_context=_command_context,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            bind_palari_command_payload(
                workspace_path,
                item,
                _command_context=_command_context,
            )
            for item in value
        )
    if not isinstance(value, dict):
        return value
    return {
        key: bind_palari_command_payload(
            workspace_path,
            item,
            _command_context=(
                _command_context
                or key == "command"
                or key == "commands"
                or key.endswith("_command")
                or key.endswith("_commands")
                or key == "next_safe_action"
            ),
        )
        for key, item in value.items()
    }
