from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .workspace import Workspace, WorkspaceError


@dataclass(frozen=True)
class CommandResult:
    kind: str
    payload: Any
    as_json: bool


def run_command(args: argparse.Namespace) -> CommandResult:
    if args.command == "queue":
        from .read_models import queue_items

        workspace = Workspace.load(args.workspace)
        return CommandResult(
            "queue",
            {"workspace": workspace, "items": queue_items(workspace)},
            args.json,
        )

    if args.command == "state":
        from .models import to_plain
        from .read_models import active_parallel_work, coordination_warnings, queue_items

        workspace = Workspace.load(args.workspace)
        items = queue_items(workspace)
        return CommandResult(
            "state",
            {
                "workspace": workspace.name,
                "counts": _workspace_counts(workspace),
                "attention": _attention_counts(items),
                "top_attention": to_plain(items[0]) if items else None,
                "queue": to_plain(items),
                "active_parallel_work": active_parallel_work(workspace),
                "coordination_warnings": coordination_warnings(workspace),
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
                    "sources": len(workspace.sources),
                    "workbenches": len(workspace.workbenches),
                    "playbook_sources": len(workspace.playbook_sources),
                    "integrations": len(workspace.integrations),
                    "integration_plans": len(workspace.integration_plans),
                    "integration_outbox": len(workspace.integration_outbox),
                    "work_items": len(workspace.work_items),
                    "receipts": len(workspace.receipts),
                },
            },
            args.json,
        )

    if args.command == "detail":
        from .read_models import detail

        workspace = Workspace.load(args.workspace)
        return CommandResult("detail", detail(workspace, args.work_id), args.json)

    if args.command == "scope":
        from .scope import check_scope

        workspace = Workspace.load(args.workspace)
        payload = check_scope(workspace, args.work_id, args.changed, args.action)
        return CommandResult("scope", payload.to_dict(), args.json)

    if args.command == "integrations":
        from .integrations import list_integrations

        workspace = Workspace.load(args.workspace)
        return CommandResult("integrations", list_integrations(workspace), args.json)

    if args.command == "agent":
        from .agent_checks import build_agent_check
        from .agent_finish import build_agent_finish
        from .agent_next import build_agent_next, build_agent_next_all
        from .agent_packets import build_agent_brief

        workspace = Workspace.load(args.workspace)
        if args.agent_command == "next":
            if args.all:
                return CommandResult(
                    "agent-next-all",
                    build_agent_next_all(workspace, args.mode, args.limit),
                    args.json,
                )
            return CommandResult(
                "agent-next",
                build_agent_next(workspace, args.palari_id, args.mode, args.limit),
                args.json,
            )
        if args.agent_command in {"brief", "start"}:
            return CommandResult(
                "agent-brief",
                build_agent_brief(workspace, args.work_id, args.palari_id, args.mode),
                args.json,
            )
        if args.agent_command == "check":
            return CommandResult(
                "agent-check",
                build_agent_check(workspace, args.work_id, args.palari_id, args.mode),
                args.json,
            )
        if args.agent_command == "finish":
            return CommandResult(
                "agent-finish",
                build_agent_finish(workspace, args.work_id, args.palari_id, args.mode),
                args.json,
            )

    if args.command == "workspace":
        from .workspace_init import initialize_workspace

        if args.workspace_command == "init":
            return CommandResult(
                "workspace-init",
                initialize_workspace(args.path, args.name),
                args.json,
            )

    if args.command == "integration":
        from .integrations import (
            cancel_integration_outbox_item,
            check_integration,
            decide_integration_plan,
            enqueue_integration_plan,
            plan_integration,
            record_integration_plan,
        )

        workspace = Workspace.load(args.workspace)
        if args.integration_command == "check":
            return CommandResult(
                "integration-check",
                check_integration(workspace, args.integration_id),
                args.json,
            )
        if args.integration_command == "plan":
            if args.record:
                return CommandResult(
                    "integration-plan",
                    record_integration_plan(
                        args.workspace,
                        args.integration_id,
                        args.work_id,
                        args.event,
                        args.action,
                        actor=args.actor,
                        plan_id=args.plan_id,
                    ),
                    args.json,
                )
            return CommandResult(
                "integration-plan",
                plan_integration(
                    workspace,
                    args.integration_id,
                    args.work_id,
                    args.event,
                    args.action,
                ),
                args.json,
            )
        if args.integration_command == "enqueue":
            return CommandResult(
                "integration-enqueue",
                enqueue_integration_plan(
                    args.workspace,
                    args.plan_id,
                    args.human_id,
                ),
                args.json,
            )
        if args.integration_command == "outbox-cancel":
            return CommandResult(
                "integration-outbox-cancel",
                cancel_integration_outbox_item(
                    args.workspace,
                    args.outbox_id,
                    args.human_id,
                    reason=args.reason,
                ),
                args.json,
            )
        if args.integration_command in {"approve", "reject", "cancel"}:
            return CommandResult(
                "integration-plan-decision",
                decide_integration_plan(
                    args.workspace,
                    args.plan_id,
                    args.human_id,
                    args.integration_command,
                    reason=args.reason,
                ),
                args.json,
            )

    if args.command == "migrate":
        return CommandResult("migration", migrate_workspace(args.workspace, args.write), args.json)

    if args.command == "history":
        from .history import read_history

        return CommandResult("history", read_history(args.workspace, args.limit), args.json)

    if args.command == "dashboard":
        from .dashboard import generate_dashboard

        return CommandResult(
            "dashboard",
            generate_dashboard(args.workspace, args.out),
            args.json,
        )

    if args.command == "desktop-prototype":
        from .desktop_prototype import generate_desktop_prototype

        return CommandResult(
            "desktop-prototype",
            generate_desktop_prototype(args.out),
            args.json,
        )

    if args.command == "desktop-serve":
        from .desktop_server import serve_desktop_prototype

        return CommandResult(
            "desktop-serve",
            serve_desktop_prototype(
                args.out,
                host=args.host,
                port=args.port,
            ),
            False,
        )

    if args.command == "review" and args.object_command == "guide":
        from .review_guides import build_review_guide

        workspace = Workspace.load(args.workspace)
        return CommandResult(
            "review-guide",
            build_review_guide(workspace, args.work_id),
            args.json,
        )

    if args.command == "decision" and args.object_command == "guide":
        from .decision_guides import build_decision_guide

        workspace = Workspace.load(args.workspace)
        return CommandResult(
            "decision-guide",
            build_decision_guide(workspace, args.target_id),
            args.json,
        )

    if args.command in {
        "goal",
        "human",
        "palari",
        "source",
        "playbook-source",
        "decision",
        "work",
        "attempt",
        "evidence",
        "review",
        "human-decision",
        "receipt",
        "outcome",
    }:
        return CommandResult("mutation", run_authoring_command(args), args.json)

    if args.command == "lifecycle":
        return CommandResult("mutation", run_lifecycle_command(args), args.json)

    if args.command == "maintainer" and args.maintainer_command == "status":
        from .maintainer import status as maintainer_status

        payload = maintainer_status(Path(args.repo)).to_dict()
        return CommandResult("maintainer-status", payload, args.json)

    if args.command == "playbooks":
        from .playbooks import playbook_catalog, recommend_playbooks

        workspace = Workspace.load(args.workspace)
        if args.playbooks_command == "sources":
            return CommandResult("playbooks", playbook_catalog(workspace), args.json)
        if args.playbooks_command == "recommend":
            return CommandResult(
                "playbook-recommendations",
                recommend_playbooks(workspace, args.work_id),
                args.json,
            )

    raise WorkspaceError("unknown command")


def migrate_workspace(workspace_path: str, write: bool) -> dict[str, Any]:
    from .history import append_history_event
    from .store import load_store, migrate_data, write_store

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
    from .authoring import (
        complete_work,
        create_human_decision,
        create_record,
        update_human_decision,
        update_record,
    )

    command = f"{args.command} {args.object_command}"
    if args.object_command in {"create", "record"}:
        record = _record_from_args(args)
        if args.command == "human-decision":
            return create_human_decision(args.workspace, record, command=command)
        return create_record(args.workspace, args.command, record, command=command)
    if args.object_command == "update":
        updates = _parse_setters(args.set, args.list)
        _apply_known_args(args, updates, include_id=False)
        if args.command == "human-decision":
            return update_human_decision(args.workspace, args.id, updates, command=command)
        return update_record(args.workspace, args.command, args.id, updates, command=command)
    if args.command == "work" and args.object_command == "complete":
        return complete_work(args.workspace, args.work_id, args.status, command=command)
    raise WorkspaceError(f"unsupported authoring command: {args.command} {args.object_command}")


def run_lifecycle_command(args: argparse.Namespace) -> Any:
    from .authoring import complete_work, create_human_decision, create_record

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
    record = _parse_setters(args.set, args.list)
    _apply_known_args(args, record, include_id=True)
    return {key: value for key, value in record.items() if value not in (None, "")}


def _parse_setters(setters: list[str], lists: list[str]) -> dict[str, Any]:
    from .authoring import parse_setters

    return parse_setters(setters, lists)


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
        "sources": len(workspace.sources),
        "workbenches": len(workspace.workbenches),
        "playbook_sources": len(workspace.playbook_sources),
        "integrations": len(workspace.integrations),
        "integration_plans": len(workspace.integration_plans),
        "integration_outbox": len(workspace.integration_outbox),
        "decisions": len(workspace.decisions),
        "work_items": len(workspace.work_items),
        "attempts": len(workspace.attempts),
        "evidence_runs": len(workspace.evidence_runs),
        "review_verdicts": len(workspace.review_verdicts),
        "human_decisions": len(workspace.human_decisions),
        "receipts": len(workspace.receipts),
        "outcomes": len(workspace.outcomes),
    }


def _attention_counts(items: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.attention] = counts.get(item.attention, 0) + 1
    return counts
