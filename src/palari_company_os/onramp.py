"""Two-minute onramp for existing repositories.

``palari init`` creates a small but complete starter workspace (one human,
one Palari, one goal, one workbench, one repo source) in an existing project,
and ``palari work add`` creates an agent-startable work item from a title and
its write paths. Together with ``palari claude install`` they take a repo
from "never heard of Palari" to an enforced write boundary in three commands.

Everything here writes through the validated store, so an init or quick-add
that would produce an invalid workspace fails before touching disk.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from shlex import quote
from typing import Any

from .authoring import create_record, update_record
from .path_policy import validate_workspace_path
from .store import WorkspaceStore, load_store, write_store
from .validation import COLLECTION_FILE_KEYS
from .workspace import CURRENT_SCHEMA_VERSION, WorkspaceError

HUMAN_ID = "HUMAN-FOUNDER"
GOAL_ID = "GOAL-0001"
WORKBENCH_ID = "WORKBENCH-MAIN"
SOURCE_ID = "SOURCE-REPO"
_WORK_ID_RE = re.compile(r"^WORK-(\d+)$")


def initialize_starter_workspace(
    target: str | Path,
    *,
    name: str = "",
    palari_name: str = "Claude",
) -> dict[str, Any]:
    """Create a starter workspace ready for ``work add`` and ``agent start``."""
    directory = Path(target).expanduser().resolve()
    workspace_file = directory / "workspace.json"
    if workspace_file.exists():
        raise WorkspaceError(
            f"workspace file already exists: {workspace_file}; "
            "use the existing workspace or initialize a different directory"
        )
    workspace_name = name.strip() or directory.name or "workspace"
    palari_label = palari_name.strip() or "Claude"
    palari_id = _palari_id(palari_label)
    human_name = _git_user_name(directory) or "Founder"

    data: dict[str, Any] = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "name": workspace_name,
    }
    for key in COLLECTION_FILE_KEYS:
        data[key] = []
    data["humans"] = [
        {
            "id": HUMAN_ID,
            "name": human_name,
            "role": "Founder",
            "authority_level": "admin",
            "approval_capabilities": ["product", "merge"],
            "availability": "active",
        }
    ]
    data["palaris"] = [
        {
            "id": palari_id,
            "name": palari_label,
            "role": "AI coding partner",
            "scope": "Do bounded work items inside declared write boundaries.",
            "forbidden_actions": [
                "write outside approved work areas",
                "send external messages",
            ],
            "default_worker": (
                "claude-code" if palari_label.lower() == "claude" else palari_label.lower()
            ),
            "owner_human": HUMAN_ID,
            "linked_goals": [GOAL_ID],
        }
    ]
    data["goals"] = [
        {
            "id": GOAL_ID,
            "title": f"Ship {workspace_name} work safely with AI partners",
            "owner": HUMAN_ID,
            "status": "active",
            "priority": "high",
            "success_criteria": [
                "AI work stays inside declared write boundaries",
                "A human can see what was done and what needs review",
            ],
            "linked_palaris": [palari_id],
        }
    ]
    data["sources"] = [
        {
            "id": SOURCE_ID,
            "label": "Repository",
            "kind": "repo",
            "provider": "local",
            "uri": ".",
            "access_mode": "read",
            "selected": True,
            "owner_human": HUMAN_ID,
            "allowed_palaris": [],
            "data_class": "internal",
            "authority": "company_owned",
            "steward_human": HUMAN_ID,
        }
    ]
    data["workbenches"] = [
        {
            "id": WORKBENCH_ID,
            "label": "Main workbench",
            "summary": f"Default work area for {workspace_name}.",
            "goal_ids": [GOAL_ID],
            "palari_ids": [palari_id],
            "human_ids": [HUMAN_ID],
            "source_ids": [SOURCE_ID],
            "status": "active",
        }
    ]

    workspace = write_store(WorkspaceStore(data_path=workspace_file, data=data))
    workspace_arg = _workspace_cli_argument(directory)
    return {
        "schema_version": "palari.init.v1",
        "workspace": workspace.name,
        "workspace_file": str(workspace_file),
        "valid": True,
        "human": {"id": HUMAN_ID, "name": human_name},
        "palari": {"id": palari_id, "name": palari_label},
        "goal": GOAL_ID,
        "workbench": WORKBENCH_ID,
        "source": SOURCE_ID,
        "next_commands": [
            f'palari{workspace_arg} work add "First task" --write docs/notes.md',
            f"palari{workspace_arg} claude install",
            f"palari{workspace_arg} queue",
        ],
        "message": (
            f"Starter workspace '{workspace.name}' created. Add a bounded work "
            "item with: palari work add \"Title\" --write PATH"
        ),
    }


def quick_add_work(
    workspace_path: str | Path,
    title: str,
    *,
    write: list[str],
    read: list[str] | None = None,
    palari_id: str = "",
    goal_id: str = "",
    workbench_id: str = "",
    risk: str = "R1",
    intensity: str = "light",
    scope: str = "",
    acceptance_target: str = "",
    verify: list[str] | None = None,
    work_id: str = "",
    approvals: int = 0,
) -> dict[str, Any]:
    """Create one agent-startable work item from a title and its write paths."""
    clean_title = title.strip()
    if not clean_title:
        raise WorkspaceError("work title is required")
    write_paths = _normalized_paths(write, "--write")
    if not write_paths:
        raise WorkspaceError("at least one --write path is required to bound the work")
    read_paths = _normalized_paths(read or [], "--read")

    store = load_store(workspace_path)
    palari = _resolve_default(store.data, "palaris", palari_id, "--as")
    goal = _resolve_default(store.data, "goals", goal_id, "--goal")
    workbench = _resolve_optional_default(store.data, "workbenches", workbench_id, "--workbench")
    resolved_id = work_id.strip() or _next_work_id(store.data)

    allowed_sources: list[str] = []
    workbench_outputs_added: list[str] = []
    if workbench:
        bench = _find_record(store.data, "workbenches", workbench)
        allowed_sources = [str(item) for item in (bench or {}).get("source_ids", [])]
        # A work item's outputs must live inside its workbench boundary, so
        # declaring a new write path here also declares it on the workbench.
        existing_outputs = [str(item) for item in (bench or {}).get("output_target_ids", [])]
        workbench_outputs_added = [path for path in write_paths if path not in existing_outputs]
        if workbench_outputs_added:
            update_record(
                str(workspace_path),
                "workbench",
                workbench,
                {"output_target_ids": existing_outputs + workbench_outputs_added},
                command="work add",
            )

    resources: list[str] = []
    for path in read_paths + write_paths:
        if path not in resources:
            resources.append(path)

    record = {
        "id": resolved_id,
        "title": clean_title,
        "goal": goal,
        "palari": palari,
        "workbench_id": workbench,
        "risk": risk,
        "intensity": intensity,
        "status": "active",
        "scope": scope.strip() or f"Do exactly this: {clean_title}.",
        "allowed_resources": resources,
        "allowed_sources": allowed_sources,
        "output_targets": write_paths,
        "conflict_targets": write_paths,
        "parallel_policy": "independent",
        "forbidden_actions": ["write outside the declared write paths"],
        "acceptance_target": (
            acceptance_target.strip() or "Declared outputs exist and verification passes."
        ),
        "verification_expectations": list(verify or []),
        "required_approval_count": max(0, approvals),
    }
    create_record(str(workspace_path), "work", record, command="work add", actor=palari)

    return {
        "schema_version": "palari.work_add.v1",
        "workspace_file": str(store.data_path),
        "work_item": record,
        "workbench_outputs_added": workbench_outputs_added,
        "next_commands": [
            f"palari agent start {resolved_id} --as {palari} --mode execute --json",
            f"palari agent check {resolved_id} --as {palari} --mode execute --git-diff --json",
            "palari claude install",
        ],
        "message": (
            f"{resolved_id} created for {palari}: write boundary is "
            f"{', '.join(write_paths)}."
        ),
    }


def _palari_id(label: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", label.upper()).strip("-")
    return f"PALARI-{slug or 'PARTNER'}"


def _git_user_name(directory: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), "config", "user.name"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _workspace_cli_argument(directory: Path) -> str:
    if directory == Path.cwd():
        return ""
    return f" --workspace {quote(str(directory))}"


def _normalized_paths(paths: list[str], flag: str) -> list[str]:
    normalized: list[str] = []
    for path in paths:
        try:
            value = validate_workspace_path(path)
        except ValueError as exc:
            raise WorkspaceError(f"{flag} {path!r}: {exc}") from exc
        if value not in normalized:
            normalized.append(value)
    return normalized


def _resolve_default(data: dict[str, Any], collection: str, explicit: str, flag: str) -> str:
    if explicit.strip():
        return explicit.strip()
    ids = _collection_ids(data, collection)
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise WorkspaceError(
            f"workspace has no {collection}; run palari init or create one first"
        )
    raise WorkspaceError(
        f"workspace has {len(ids)} {collection} ({', '.join(ids)}); pass {flag} to pick one"
    )


def _resolve_optional_default(
    data: dict[str, Any],
    collection: str,
    explicit: str,
    flag: str,
) -> str:
    if explicit.strip():
        return explicit.strip()
    ids = _collection_ids(data, collection)
    if len(ids) == 1:
        return ids[0]
    if not ids:
        return ""
    raise WorkspaceError(
        f"workspace has {len(ids)} {collection} ({', '.join(ids)}); pass {flag} to pick one"
    )


def _collection_ids(data: dict[str, Any], collection: str) -> list[str]:
    records = data.get(collection, [])
    if not isinstance(records, list):
        return []
    return [str(item.get("id", "")) for item in records if isinstance(item, dict)]


def _find_record(data: dict[str, Any], collection: str, record_id: str) -> dict[str, Any] | None:
    for item in data.get(collection, []):
        if isinstance(item, dict) and item.get("id") == record_id:
            return item
    return None


def _next_work_id(data: dict[str, Any]) -> str:
    highest = 0
    for record_id in _collection_ids(data, "work_items"):
        match = _WORK_ID_RE.match(record_id)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"WORK-{highest + 1:04d}"
