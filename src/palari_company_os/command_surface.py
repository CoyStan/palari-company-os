from __future__ import annotations

from pathlib import Path
from shlex import quote

from .store import workspace_file_path


def palari_workspace_command(
    workspace_path: Path | str,
    *arguments: str,
) -> str:
    """Render one shell-safe Palari command bound to an exact workspace root."""

    root = workspace_file_path(workspace_path).parent.resolve(strict=False)
    tokens = ("palari", "--workspace", str(root), *arguments)
    return " ".join(quote(token) for token in tokens)
