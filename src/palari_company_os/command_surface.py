from __future__ import annotations

from pathlib import Path
from shlex import quote

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
