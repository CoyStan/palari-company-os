from __future__ import annotations

from pathlib import Path
from shlex import quote
from typing import Any

from .store import WorkspaceStore, write_store
from .validation import COLLECTION_FILE_KEYS
from .workspace import CURRENT_SCHEMA_VERSION, WorkspaceError


def initialize_workspace(target: str | Path, name: str) -> dict[str, Any]:
    workspace_file = _workspace_file_path(target)
    if workspace_file.exists():
        raise WorkspaceError(f"workspace file already exists: {workspace_file}")
    if workspace_file.parent.exists() and not workspace_file.parent.is_dir():
        raise WorkspaceError(f"workspace parent is not a directory: {workspace_file.parent}")

    workspace_name = name.strip()
    if not workspace_name:
        raise WorkspaceError("workspace name is required")

    data = _blank_workspace(workspace_name)
    workspace = write_store(WorkspaceStore(data_path=workspace_file, data=data))
    workspace_arg = quote(str(workspace_file))
    return {
        "workspace": workspace.name,
        "workspace_file": str(workspace_file),
        "valid": True,
        "counts": {
            "goals": len(workspace.goals),
            "palaris": len(workspace.palaris),
            "humans": len(workspace.humans),
            "sources": len(workspace.sources),
            "workbenches": len(workspace.workbenches),
            "work_items": len(workspace.work_items),
            "receipts": len(workspace.receipts),
        },
        "next_commands": [
            f"palari --workspace {workspace_arg} validate",
            f"palari --workspace {workspace_arg} human create HUMAN-FOUNDER --name 'Founder'",
            f"palari --workspace {workspace_arg} palari create PALARI-STEWARD "
            "--name Steward --role 'Workspace steward'",
            f"palari --workspace {workspace_arg} goal create GOAL-0001 --title 'First goal'",
        ],
    }


def _workspace_file_path(target: str | Path) -> Path:
    path = Path(target).expanduser()
    if path.suffix == ".json":
        return path.resolve()
    return (path / "workspace.json").resolve()


def _blank_workspace(name: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "name": name,
    }
    for key in COLLECTION_FILE_KEYS:
        data[key] = []
    return data
