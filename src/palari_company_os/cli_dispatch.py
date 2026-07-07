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
    if args.command == "demo":
        from .demo import run_demo
        from .demo import serve_demo

        if args.serve:
            serve_demo(args.demo_dir, host=args.host, port=args.port)
            return CommandResult("demo-serve", {}, False)

        return CommandResult(
            "demo",
            run_demo(args.demo_dir, no_pause=args.no_pause or args.json),
            args.json,
        )

    if args.command == "queue":
        from .read_models import queue_items

        workspace = Workspace.load(args.workspace)
        items = queue_items(workspace)
        if not args.include_closed:
            items = [item for item in items if item.attention != "closed"]
        return CommandResult(
            "queue",
            {"workspace": workspace, "items": items},
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

    if args.command == "data" and args.data_command == "map":
        from .data_map import build_data_map

        workspace = Workspace.load(args.workspace)
        return CommandResult("data-map", build_data_map(workspace), args.json)

    if args.command == "docs":
        from .repo_docs import build_docs_map, check_docs, init_docs

        if args.docs_command == "check":
            return CommandResult("docs-check", check_docs(args.repo), args.json)
        if args.docs_command == "init":
            return CommandResult(
                "docs-init",
                init_docs(args.repo, write=args.write, overwrite=args.overwrite),
                args.json,
            )
        if args.docs_command == "map":
            return CommandResult("docs-map", build_docs_map(args.repo), args.json)

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
                    "capabilities": len(workspace.capabilities),
                    "authority_profiles": len(workspace.authority_profiles),
                    "integrations": len(workspace.integrations),
                    "integration_plans": len(workspace.integration_plans),
                    "integration_outbox": len(workspace.integration_outbox),
                    "proposals": len(workspace.proposals),
                    "work_items": len(workspace.work_items),
                    "acceptance_records": len(workspace.acceptance_records),
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
        from .agent_doctor import build_agent_doctor
        from .agent_finish import build_agent_finish
        from .agent_handoff import build_agent_handoff
        from .agent_loop import build_agent_loop
        from .agent_next import build_agent_next, build_agent_next_all
        from .agent_packets import build_agent_brief
        from .agent_runtime import release_agent, start_agent

        workspace = Workspace.load(args.workspace)
        if args.agent_command == "next":
            if args.all or not args.palari_id:
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
        if args.agent_command == "brief":
            return CommandResult(
                "agent-brief",
                build_agent_brief(workspace, args.work_id, args.palari_id, args.mode),
                args.json,
            )
        if args.agent_command == "start":
            return CommandResult(
                "agent-start",
                start_agent(
                    workspace,
                    args.workspace,
                    args.work_id,
                    args.palari_id,
                    args.mode,
                    lease_minutes=args.lease_minutes,
                ),
                args.json,
            )
        if args.agent_command == "release":
            return CommandResult(
                "agent-release",
                release_agent(workspace, args.workspace, args.work_id, args.palari_id),
                args.json,
            )
        if args.agent_command == "check":
            return CommandResult(
                "agent-check",
                build_agent_check(
                    workspace,
                    args.work_id,
                    args.palari_id,
                    args.mode,
                    changed_paths=args.changed,
                    git_diff=args.git_diff,
                    cwd=Path.cwd(),
                ),
                args.json,
            )
        if args.agent_command == "finish":
            return CommandResult(
                "agent-finish",
                build_agent_finish(workspace, args.work_id, args.palari_id, args.mode),
                args.json,
            )
        if args.agent_command == "handoff":
            return CommandResult(
                "agent-handoff",
                build_agent_handoff(workspace, args.work_id, args.palari_id, args.mode),
                args.json,
            )
        if args.agent_command == "loop":
            return CommandResult(
                "agent-loop",
                build_agent_loop(workspace, args.work_id, args.palari_id, args.mode),
                args.json,
            )
        if args.agent_command == "doctor":
            return CommandResult(
                "agent-doctor",
                build_agent_doctor(workspace, args.work_id, args.palari_id, args.mode),
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

    if args.command == "mcp" and args.mcp_command == "serve":
        from .mcp_server import serve_mcp

        serve_mcp(args.workspace, repo=args.repo)
        return CommandResult("mcp-server", {}, False)

    if args.command == "integration":
        from .integrations import (
            cancel_integration_outbox_item,
            check_integration_outbox,
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
        if args.integration_command == "outbox-check":
            return CommandResult(
                "integration-outbox-check",
                check_integration_outbox(workspace, args.outbox_id),
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

    if args.command == "linear":
        from .linear_adapter import (
            linear_block_template,
            linear_doctor,
            linear_import,
            linear_inspect_block,
            linear_issue,
            linear_linked,
            linear_post_gate,
            linear_send,
            linear_start,
            linear_status,
        )

        if args.linear_command == "doctor":
            return CommandResult("linear", linear_doctor(args.workspace), args.json)
        if args.linear_command == "linked":
            return CommandResult("linear", linear_linked(args.workspace), args.json)
        if args.linear_command == "issue":
            return CommandResult("linear", linear_issue(args.issue_key), args.json)
        if args.linear_command == "import":
            return CommandResult(
                "linear",
                linear_import(
                    args.workspace,
                    args.issue_key,
                    args.palari_id,
                    goal_id=args.goal_id,
                ),
                args.json,
            )
        if args.linear_command == "start":
            return CommandResult(
                "linear",
                linear_start(
                    args.workspace,
                    args.issue_key,
                    args.palari_id,
                    runner=args.runner,
                    mode=args.mode,
                    adopt_by=args.adopt_by,
                    goal_id=args.goal_id,
                    lease_minutes=args.lease_minutes,
                ),
                args.json,
            )
        if args.linear_command == "status":
            return CommandResult("linear", linear_status(args.workspace, args.issue_key), args.json)
        if args.linear_command == "block-template":
            return CommandResult(
                "linear",
                linear_block_template(
                    args.workspace,
                    args.palari_id,
                    args.goal_id,
                    risk=args.risk,
                    intensity=args.intensity,
                    scope=args.scope,
                    acceptance_target=args.acceptance_target,
                    parallel_policy=args.parallel_policy,
                    allowed_resources=args.allowed_resources,
                    allowed_sources=args.allowed_sources,
                    allowed_actions=args.allowed_actions,
                    output_targets=args.output_targets,
                    forbidden_actions=args.forbidden_actions,
                    verification_expectations=args.verification_expectations,
                    recommended_playbooks=args.recommended_playbooks,
                    conflict_targets=args.conflict_targets,
                ),
                args.json,
            )
        if args.linear_command == "inspect-block":
            return CommandResult(
                "linear",
                linear_inspect_block(args.workspace, args.issue_key, args.palari_id),
                args.json,
            )
        if args.linear_command == "post-gate":
            return CommandResult(
                "linear",
                linear_post_gate(
                    args.workspace,
                    args.issue_key,
                    event=args.event,
                    actor=args.actor,
                    record=args.record,
                ),
                args.json,
            )
        if args.linear_command == "send":
            return CommandResult(
                "linear",
                linear_send(
                    args.workspace,
                    args.outbox_id,
                    human_id=args.human_id,
                    confirm=args.confirm,
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

    if args.command == "serve":
        from .mission_control import serve_mission_control

        return CommandResult(
            "mission-control-serve",
            serve_mission_control(
                args.workspace,
                args.human_id,
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

    if args.command == "capability" and args.object_command in {
        "list",
        "check",
        "export-policy",
    }:
        from .capabilities import capability_catalog, capability_check, export_policy

        workspace = Workspace.load(args.workspace)
        if args.object_command == "list":
            return CommandResult("capabilities", capability_catalog(workspace), args.json)
        if args.object_command == "check":
            return CommandResult(
                "capability-check",
                capability_check(workspace, args.work_id, args.palari_id),
                args.json,
            )
        if args.object_command == "export-policy":
            return CommandResult(
                "capability-policy",
                export_policy(workspace, args.work_id, args.palari_id),
                args.json,
            )

    if args.command == "authority":
        from .authority import authority_check, authority_profiles

        workspace = Workspace.load(args.workspace)
        if args.authority_command == "profiles":
            return CommandResult("authority-profiles", authority_profiles(workspace), args.json)
        if args.authority_command == "check":
            return CommandResult(
                "authority-check",
                authority_check(workspace, args.work_id, args.profile),
                args.json,
            )

    if args.command == "evidence" and args.object_command == "verify":
        from .evidence_manifest import verify_evidence

        workspace = Workspace.load(args.workspace)
        return CommandResult("evidence-verify", verify_evidence(workspace, args.id), args.json)

    if args.command == "proposal" and args.object_command in {"adopt", "reject", "defer"}:
        from .proposals import adopt_proposal, decide_proposal

        if args.object_command == "adopt":
            return CommandResult(
                "proposal-decision",
                adopt_proposal(
                    args.workspace,
                    args.proposal_id,
                    args.work_id,
                    args.human_id,
                    reason=args.reason,
                ),
                args.json,
            )
        return CommandResult(
            "proposal-decision",
            decide_proposal(
                args.workspace,
                args.proposal_id,
                args.human_id,
                args.object_command,
                reason=args.reason,
            ),
            args.json,
        )

    if args.command == "work" and args.object_command == "expand-scope":
        from .proposals import request_scope_expansion

        return CommandResult(
            "proposal-decision",
            request_scope_expansion(
                args.workspace,
                args.work_id,
                args.decision_id,
                args.actor,
                read_paths=args.read,
                write_paths=args.write,
                actions=args.action,
                reason=args.reason,
            ),
            args.json,
        )

    if args.command in {
        "goal",
        "human",
        "palari",
        "source",
        "playbook-source",
        "capability",
        "authority-profile",
        "decision",
        "proposal",
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

        maintainer_payload = maintainer_status(Path(args.repo)).to_dict()
        return CommandResult("maintainer-status", maintainer_payload, args.json)

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

    if args.command == "gate":
        from .gate_profiles import gate_profile_catalog, recommend_gates

        workspace = Workspace.load(args.workspace)
        if args.gate_command == "profiles":
            return CommandResult("gate-profiles", gate_profile_catalog(workspace), args.json)
        if args.gate_command == "recommend":
            return CommandResult(
                "gate-recommendations",
                recommend_gates(workspace, args.work_id),
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
        store = store.with_data(migrated)
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
        accept_work,
        closeout_attempt,
        complete_work,
        create_human_decision,
        create_record,
        update_human_decision,
        update_record,
    )

    command = f"{args.command} {args.object_command}"
    if args.command == "work" and args.object_command == "accept":
        return accept_work(
            args.workspace,
            args.work_id,
            args.human_id,
            args.reviewed_head,
            decision_id=args.decision_id,
            acceptance_id=args.acceptance_id,
            reason=args.reason,
            authority_profile=args.authority_profile,
            command=command,
        )
    if args.command == "attempt" and args.object_command == "closeout":
        return closeout_attempt(
            args.workspace,
            args.id,
            status=args.status,
            head_sha=args.head_sha,
            cleanliness=args.cleanliness,
            changed_files=args.changed,
            output_targets=args.output_target,
            allow_missing_evidence=args.allow_missing_evidence,
            command=command,
        )
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
            "authority_command",
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
        "capabilities": len(workspace.capabilities),
        "authority_profiles": len(workspace.authority_profiles),
        "integrations": len(workspace.integrations),
        "integration_plans": len(workspace.integration_plans),
        "integration_outbox": len(workspace.integration_outbox),
        "decisions": len(workspace.decisions),
        "proposals": len(workspace.proposals),
        "work_items": len(workspace.work_items),
        "attempts": len(workspace.attempts),
        "evidence_runs": len(workspace.evidence_runs),
        "review_verdicts": len(workspace.review_verdicts),
        "human_decisions": len(workspace.human_decisions),
        "acceptance_records": len(workspace.acceptance_records),
        "receipts": len(workspace.receipts),
        "outcomes": len(workspace.outcomes),
    }


def _attention_counts(items: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.attention] = counts.get(item.attention, 0) + 1
    return counts
