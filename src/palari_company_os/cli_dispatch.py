from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .authoring import (
    complete_work,
    create_human_decision,
    create_record,
    parse_setters,
    update_human_decision,
    update_record,
)
from .history import append_history_event, read_history
from .maintainer import status as maintainer_status
from .models import to_plain
from .read_models import detail, queue_items
from .scope import check_scope
from .store import load_store, migrate_data, write_store
from .workspace import Workspace, WorkspaceError


@dataclass(frozen=True)
class CommandResult:
    kind: str
    payload: Any
    as_json: bool


def run_command(args: argparse.Namespace) -> CommandResult:
    if args.command == "queue":
        workspace = Workspace.load(args.workspace)
        return CommandResult(
            "queue",
            {"workspace": workspace, "items": queue_items(workspace)},
            args.json,
        )

    if args.command == "state":
        workspace = Workspace.load(args.workspace)
        items = queue_items(workspace)
        return CommandResult(
            "state",
            {
                "workspace": workspace.name,
                "counts": _workspace_counts(workspace),
                "attention": _attention_counts(items),
                "queue": to_plain(items),
            },
            args.json,
        )

    if args.command == "validate":
        workspace = Workspace.load(args.workspace)
        return CommandResult(
            "validate",
            {
                "workspace": workspace.name,
                "valid": True,
                "counts": {
                    "goals": len(workspace.goals),
                    "palaris": len(workspace.palaris),
                    "humans": len(workspace.humans),
                    "work_items": len(workspace.work_items),
                },
            },
            args.json,
        )

    if args.command == "detail":
        workspace = Workspace.load(args.workspace)
        return CommandResult("detail", detail(workspace, args.work_id), args.json)

    if args.command == "scope":
        workspace = Workspace.load(args.workspace)
        payload = check_scope(workspace, args.work_id, args.changed, args.action)
        return CommandResult("scope", payload.to_dict(), args.json)

    if args.command == "migrate":
        return CommandResult("migration", migrate_workspace(args.workspace, args.write), args.json)

    if args.command == "history":
        return CommandResult("history", read_history(args.workspace, args.limit), args.json)

    if args.command in {
        "goal",
        "human",
        "palari",
        "decision",
        "work",
        "attempt",
        "evidence",
        "review",
        "human-decision",
        "outcome",
    }:
        return CommandResult("mutation", run_authoring_command(args), args.json)

    if args.command == "lifecycle":
        return CommandResult("mutation", run_lifecycle_command(args), args.json)

    if args.command == "maintainer" and args.maintainer_command == "status":
        payload = maintainer_status(Path(args.repo)).to_dict()
        return CommandResult("maintainer-status", payload, args.json)

    raise WorkspaceError("unknown command")


def migrate_workspace(workspace_path: str, write: bool) -> dict[str, Any]:
    store = load_store(workspace_path)
    before = deepcopy(store.data)
    migrated, changes = migrate_data(store.data)
    payload = {
        "workspace_file": str(store.data_path),
        "write": write,
        "changes": changes,
    }
    if write:
        store = type(store)(store.data_path, migrated)
        workspace = write_store(store)
        append_history_event(
            store.data_path,
            schema_version=workspace.schema_version,
            command="migrate --write",
            action="migrated",
            object_type="workspace",
            object_collection="workspace",
            object_id=workspace.name,
            before=before,
            after=migrated,
        )
    return payload


def run_authoring_command(args: argparse.Namespace) -> Any:
    command = f"{args.command} {args.object_command}"
    if args.object_command in {"create", "record"}:
        record = _record_from_args(args)
        if args.command == "human-decision":
            return create_human_decision(args.workspace, record, command=command)
        return create_record(args.workspace, args.command, record, command=command)
    if args.object_command == "update":
        updates = parse_setters(args.set, args.list)
        _apply_known_args(args, updates, include_id=False)
        if args.command == "human-decision":
            return update_human_decision(args.workspace, args.id, updates, command=command)
        return update_record(args.workspace, args.command, args.id, updates, command=command)
    if args.command == "work" and args.object_command == "complete":
        return complete_work(args.workspace, args.work_id, args.status, command=command)
    raise WorkspaceError(f"unsupported authoring command: {args.command} {args.object_command}")


def run_lifecycle_command(args: argparse.Namespace) -> Any:
    command = f"lifecycle {args.lifecycle_command}"
    if args.lifecycle_command == "evidence":
        return create_record(args.workspace, "evidence", _record_from_args(args), command=command)
    if args.lifecycle_command == "review":
        return create_record(args.workspace, "review", _record_from_args(args), command=command)
    if args.lifecycle_command == "decide":
        return create_human_decision(args.workspace, _record_from_args(args), command=command)
    if args.lifecycle_command == "complete":
        return complete_work(args.workspace, args.work_id, args.status, command=command)
    if args.lifecycle_command == "outcome":
        return create_record(args.workspace, "outcome", _record_from_args(args), command=command)
    raise WorkspaceError(f"unsupported lifecycle command: {args.lifecycle_command}")


def _record_from_args(args: argparse.Namespace) -> dict[str, Any]:
    record = parse_setters(args.set, args.list)
    _apply_known_args(args, record, include_id=True)
    return {key: value for key, value in record.items() if value not in (None, "")}


def _apply_known_args(args: argparse.Namespace, record: dict[str, Any], include_id: bool) -> None:
    for key, value in vars(args).items():
        if key in {
            "command",
            "object_command",
            "lifecycle_command",
            "workspace",
            "json",
            "set",
            "list",
        }:
            continue
        if key == "id" and not include_id:
            continue
        if value in (None, "", []):
            continue
        record[key] = value


def _workspace_counts(workspace: Workspace) -> dict[str, int]:
    return {
        "goals": len(workspace.goals),
        "palaris": len(workspace.palaris),
        "humans": len(workspace.humans),
        "decisions": len(workspace.decisions),
        "work_items": len(workspace.work_items),
        "attempts": len(workspace.attempts),
        "evidence_runs": len(workspace.evidence_runs),
        "review_verdicts": len(workspace.review_verdicts),
        "human_decisions": len(workspace.human_decisions),
        "outcomes": len(workspace.outcomes),
    }


def _attention_counts(items: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.attention] = counts.get(item.attention, 0) + 1
    return counts
