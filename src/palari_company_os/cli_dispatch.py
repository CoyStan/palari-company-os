from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .work_identity import resolve_opaque_id
from .workspace import Workspace, WorkspaceError


@dataclass(frozen=True)
class CommandResult:
    kind: str
    payload: Any
    as_json: bool
    exit_code: int = 0


def run_command(args: argparse.Namespace) -> CommandResult:
    _canonicalize_work_refs(args)
    if args.command == "demo":
        from .demo import run_demo
        from .demo import run_solo_journey_demo
        from .demo import serve_demo

        if args.serve:
            serve_demo(args.demo_dir, host=args.host, port=args.port)
            return CommandResult("demo-serve", {}, False)

        if args.journey:
            return CommandResult(
                "demo",
                run_solo_journey_demo(
                    args.demo_dir,
                    no_pause=args.no_pause or args.json,
                ),
                args.json,
            )

        return CommandResult(
            "demo",
            run_demo(args.demo_dir, no_pause=args.no_pause or args.json),
            args.json,
        )

    if args.command == "approve":
        workspace = Workspace.load(args.workspace)
        if workspace.proposal(args.work_id) is not None:
            if args.presented:
                raise WorkspaceError("--presented is only valid for final task approval")
            from .proposals import adopt_proposal
            from .work_identity import generate_work_id

            work_id = generate_work_id(work.id for work in workspace.work_items)
            return CommandResult(
                "work-idea-accept",
                adopt_proposal(
                    args.workspace,
                    args.work_id,
                    work_id,
                    args.human_id,
                    reason=args.reason,
                ),
                args.json,
            )
        from .simple_approval import approve_work

        return CommandResult(
            "simple-approval",
            approve_work(
                args.workspace,
                args.work_id,
                args.human_id,
                reason=args.reason,
                presented_digest=args.presented,
            ),
            args.json,
        )

    if args.command == "queue":
        workspace = Workspace.load(args.workspace)
        if args.approval_inbox:
            from .workspace_read_models import approval_inbox

            return CommandResult(
                "approval-inbox",
                approval_inbox(workspace, selected_work_ids=args.select),
                args.json,
            )
        if args.select:
            raise WorkspaceError("--select requires --approval-inbox")
        from .read_models import queue_items

        items = queue_items(workspace)
        if not args.include_closed:
            items = [item for item in items if item.attention != "closed"]
        return CommandResult(
            "queue",
            {"workspace": workspace, "items": items},
            args.json,
        )

    if args.command == "inbox":
        from .workspace_read_models import approval_inbox

        workspace = Workspace.load(args.workspace)
        return CommandResult(
            "approval-inbox",
            approval_inbox(workspace, selected_work_ids=args.select),
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

    if args.command == "proof":
        if args.proof_command == "export":
            from .pcaw_export import export_pcaw_statement

            return CommandResult(
                "proof",
                export_pcaw_statement(args.workspace, args.work_id, args.output),
                args.json,
            )
        if args.proof_command == "verify":
            from .pcaw_protocol import verify_pcaw_file

            payload = verify_pcaw_file(
                args.proof_file,
                subject_root=args.subject_root,
                statement_only=args.statement_only,
            )
            error_codes = {
                str(item.get("code", ""))
                for item in payload.get("errors", [])
                if isinstance(item, dict)
            }
            exit_code = (
                0 if payload.get("verified") else 2 if "PROOF_UNREADABLE" in error_codes else 1
            )
            return CommandResult(
                "proof",
                payload,
                args.json,
                exit_code,
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
        scope_result = check_scope(workspace, args.work_id, args.changed, args.action)
        return CommandResult("scope", scope_result.to_dict(), args.json)

    if args.command == "integrations":
        from .integrations import list_integrations

        workspace = Workspace.load(args.workspace)
        return CommandResult("integrations", list_integrations(workspace), args.json)

    if args.command == "agent":
        from .agent_home import build_agent_home
        from .agent_next import build_agent_next, build_agent_next_all
        from .agent_packets import build_agent_brief
        from .agent_runtime import release_agent, start_agent, start_next_agent
        from .agent_status import build_agent_status

        agent_workspace: Workspace | None = None
        if args.agent_command == "advance":
            advance_workspace = Workspace.load(args.workspace)
            agent_workspace = advance_workspace
            advance_work = advance_workspace.work_item(args.work_id)
            if advance_work is not None and advance_work.terminal_disposition:
                return CommandResult(
                    "agent-advance",
                    {
                        "schema_version": "palari.agent_advance.v1",
                        "workspace": advance_workspace.name,
                        "work_item": args.work_id,
                        "status": "retired",
                        "can_advance": False,
                        "would_mutate": False,
                        "expected_state": "retired",
                        "stop_boundary": "terminal",
                        "message": (
                            f"Task {args.work_id} was "
                            f"{advance_work.terminal_disposition} and is audit-only: "
                            f"{advance_work.terminal_reason}"
                        ),
                        "steps": [],
                    },
                    args.json,
                )
        if args.agent_command == "advance" and args.dry_run:
            from .agent_advance import agent_advance_dry_run

            fast_plan = agent_advance_dry_run(
                args.workspace,
                args.work_id,
                args.palari_id,
            )
            if fast_plan is not None:
                return CommandResult("agent-advance", fast_plan, args.json)
        if args.agent_command == "release" and (args.reason or args.next_action):
            from .agent_parking import park_agent

            if not args.reason or not args.next_action:
                raise WorkspaceError(
                    "durable agent release requires both --reason and --next-action"
                )
            return CommandResult(
                "agent-park",
                park_agent(
                    args.workspace,
                    args.work_id,
                    args.palari_id,
                    reason=args.reason,
                    next_action=args.next_action,
                ),
                args.json,
            )
        if agent_workspace is None:
            agent_workspace = Workspace.load(args.workspace)
        if args.agent_command == "home":
            return CommandResult(
                "agent-home",
                build_agent_home(agent_workspace, args.palari_id),
                args.json,
            )
        if args.agent_command == "next":
            if args.all or not args.palari_id:
                return CommandResult(
                    "agent-next-all",
                    build_agent_next_all(agent_workspace, args.mode, args.limit),
                    args.json,
                )
            return CommandResult(
                "agent-next",
                build_agent_next(agent_workspace, args.palari_id, args.mode, args.limit),
                args.json,
            )
        if args.agent_command == "brief":
            packet = build_agent_brief(
                agent_workspace,
                args.work_id,
                args.palari_id,
                args.mode,
            )
            if args.session_contract:
                from .agent_session_contract import compile_agent_session_contract

                return CommandResult(
                    "agent-session-contract",
                    compile_agent_session_contract(packet),
                    args.json,
                )
            return CommandResult(
                "agent-brief",
                packet,
                args.json,
            )
        if args.agent_command == "start":
            if bool(args.start_next) == bool(args.work_id):
                raise WorkspaceError("agent start requires exactly one of WORK-ID or --next")
            if args.start_next:
                if args.isolate:
                    raise WorkspaceError(
                        "agent start --next does not infer an isolated branch; select an "
                        "explicit WORK-ID when --isolate is required"
                    )
                return CommandResult(
                    "agent-start",
                    start_next_agent(
                        agent_workspace,
                        args.workspace,
                        args.palari_id,
                        args.mode,
                        lease_minutes=args.lease_minutes,
                    ),
                    args.json,
                )
            if args.isolate:
                from .agent_isolation import start_isolated_agent

                return CommandResult(
                    "agent-start",
                    start_isolated_agent(
                        args.workspace,
                        args.work_id,
                        args.palari_id,
                        args.mode,
                        lease_minutes=args.lease_minutes,
                        base_ref=args.base_ref,
                    ),
                    args.json,
                )
            return CommandResult(
                "agent-start",
                start_agent(
                    agent_workspace,
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
                release_agent(agent_workspace, args.workspace, args.work_id, args.palari_id),
                args.json,
            )
        if args.agent_command == "status":
            return CommandResult(
                "agent-status",
                build_agent_status(agent_workspace, args.work_id, args.palari_id, args.mode),
                args.json,
            )
        if args.agent_command == "advance":
            from .agent_advance import agent_advance

            return CommandResult(
                "agent-advance",
                agent_advance(
                    agent_workspace,
                    args.workspace,
                    args.work_id,
                    args.palari_id,
                    dry_run=args.dry_run,
                    refresh_verification=args.refresh_verification,
                ),
                args.json,
            )

    if args.command == "claude":
        from .claude_hooks import hooks_status

        if args.claude_command == "hook":
            from .agent_adoption import run_agent_hook

            return CommandResult(
                "claude-hook",
                run_agent_hook(
                    "claude",
                    args.event,
                    args.workspace,
                    strict=args.strict,
                ),
                True,
            )
        if args.claude_command == "install":
            from .agent_adoption import install_claude_host_hooks

            return CommandResult(
                "claude-install",
                install_claude_host_hooks(
                    args.project_dir or Path.cwd(),
                    args.workspace,
                    settings_file=args.settings_file,
                    local=args.local,
                    strict=args.strict,
                    remove=args.remove,
                ),
                args.json,
            )
        if args.claude_command == "status":
            return CommandResult(
                "claude-status",
                hooks_status(args.project_dir or Path.cwd(), args.workspace),
                args.json,
            )

    if args.command == "git":
        from .git_hooks import git_hook_status, install_git_hook, pre_commit

        if args.git_command == "install":
            return CommandResult(
                "git-install",
                install_git_hook(
                    args.project_dir or Path.cwd(),
                    args.workspace,
                    remove=args.remove,
                ),
                args.json,
            )
        if args.git_command == "pre-commit":
            result = pre_commit(args.workspace, cwd=Path.cwd())
            if not result["ok"]:
                if args.json:
                    print(json.dumps(result, indent=2, sort_keys=True))
                else:
                    print(result.get("message", "Palari commit check failed."), file=sys.stderr)
                    for error in result.get("errors", []):
                        print(f"  error: {error}", file=sys.stderr)
                    for path in result.get("outside", []):
                        print(f"  outside: {path}", file=sys.stderr)
                sys.exit(1)
            return CommandResult("git-pre-commit", result, args.json)
        if args.git_command == "status":
            if args.work_id:
                from .agent_isolation import git_integration_readiness

                return CommandResult(
                    "git-readiness",
                    git_integration_readiness(
                        args.workspace,
                        args.work_id,
                        target_ref=args.target_ref,
                    ),
                    args.json,
                )
            return CommandResult(
                "git-status",
                git_hook_status(args.project_dir or Path.cwd(), args.workspace),
                args.json,
            )

    if args.command == "cursor":
        from .cursor_rules import cursor_rules_status, install_cursor_rules

        if args.cursor_command == "install":
            return CommandResult(
                "cursor-install",
                install_cursor_rules(
                    args.project_dir or Path.cwd(),
                    args.workspace,
                    git_hook=not args.no_git_hook,
                    remove=args.remove,
                ),
                args.json,
            )
        if args.cursor_command == "status":
            return CommandResult(
                "cursor-status",
                cursor_rules_status(args.project_dir or Path.cwd(), args.workspace),
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
            linear_connect,
            linear_doctor,
            linear_import,
            linear_inspect_block,
            linear_issue,
            linear_issues,
            linear_linked,
            linear_post_gate,
            linear_push,
            linear_send,
            linear_start,
            linear_status,
            linear_sync,
        )
        from .linear_webhook import (
            linear_webhook_events,
            linear_webhook_verify_file,
            serve_linear_webhook,
        )

        if args.linear_command == "doctor":
            return CommandResult("linear", linear_doctor(args.workspace), args.json)
        if args.linear_command == "connect":
            return CommandResult(
                "linear",
                linear_connect(args.workspace, actor=args.actor),
                args.json,
            )
        if args.linear_command == "issues":
            return CommandResult(
                "linear",
                linear_issues(args.workspace, team_key=args.team, limit=args.limit),
                args.json,
            )
        if args.linear_command == "sync":
            return CommandResult(
                "linear",
                linear_sync(args.workspace, args.issue_key),
                args.json,
            )
        if args.linear_command == "push":
            return CommandResult(
                "linear",
                linear_push(
                    args.workspace,
                    args.work_id,
                    actor=args.actor,
                    team_key=args.team,
                    record=args.record,
                ),
                args.json,
            )
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
        if args.linear_command == "webhook":
            if args.webhook_command == "serve":
                return CommandResult(
                    "linear",
                    serve_linear_webhook(
                        args.workspace,
                        host=args.host,
                        port=args.port,
                        as_json=args.json,
                    ),
                    False,
                )
            if args.webhook_command == "verify":
                return CommandResult(
                    "linear",
                    linear_webhook_verify_file(
                        args.payload_file,
                        signature=args.signature,
                        timestamp=args.timestamp,
                    ),
                    args.json,
                )
            if args.webhook_command == "events":
                return CommandResult(
                    "linear",
                    linear_webhook_events(args.workspace, limit=args.limit),
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
                    action=args.action.replace("-", "_"),
                    target_state=args.to_state,
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

    if args.command == "history":
        if not (args.checkpoint or args.recover) and (
            args.acknowledge_break or args.actor or args.reason
        ):
            raise WorkspaceError(
                "--actor, --reason, and --acknowledge-break require a journal mode"
            )
        from .governance_journal import (
            checkpoint_workspace_journal,
            recover_workspace_journal,
            verify_workspace_journal,
        )
        from .store import workspace_write_lock

        if args.checkpoint:
            with workspace_write_lock(args.workspace):
                payload = checkpoint_workspace_journal(
                    args.workspace,
                    actor=args.actor or "local-operator",
                    acknowledge_break=args.acknowledge_break,
                    reason=args.reason,
                )
        elif args.recover:
            with workspace_write_lock(args.workspace):
                payload = recover_workspace_journal(args.workspace, actor=args.actor)
        else:
            payload = verify_workspace_journal(args.workspace)
        return CommandResult(
            "history-journal",
            payload,
            args.json,
            0 if payload.get("ok") else 2,
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

    if args.command == "init":
        from .agent_adoption import adopt_agent_host, run_agent_hook
        from .onramp import initialize_starter_workspace
        from .store import workspace_file_path

        if args.hook_event:
            if not args.host:
                raise WorkspaceError("--hook-event requires --host")
            return CommandResult(
                "agent-hook",
                run_agent_hook(
                    args.host,
                    args.hook_event,
                    args.path,
                    strict=bool(getattr(args, "strict", False)),
                ),
                True,
            )

        strict_git = bool(getattr(args, "strict_git", False))
        no_git_hook = bool(getattr(args, "no_git_hook", False))
        if strict_git and args.host != "cursor":
            raise WorkspaceError("--strict-git is only valid with --host cursor")
        if no_git_hook and args.host != "cursor":
            raise WorkspaceError("--no-git-hook is only valid with --host cursor")
        if strict_git and no_git_hook:
            raise WorkspaceError("--strict-git and --no-git-hook cannot be combined")

        if workspace_file_path(args.path).exists() and args.host:
            return CommandResult(
                "agent-adopt",
                adopt_agent_host(
                    args.path,
                    project_dir=workspace_file_path(args.path).parent,
                    host=args.host,
                    palari_id=args.palari_id,
                    strict_git=strict_git,
                    no_git_hook=no_git_hook,
                ),
                args.json,
            )
        if args.palari_id:
            raise WorkspaceError("--as is only valid when adopting an existing workspace")

        return CommandResult(
            "init",
            initialize_starter_workspace(
                args.path,
                name=args.name,
                palari_name=args.palari,
                host=args.host,
                strict_git=strict_git,
                no_git_hook=no_git_hook,
            ),
            args.json,
        )

    if args.command == "do" or (args.command == "work" and args.object_command == "add"):
        from .onramp import quick_add_work

        return CommandResult(
            "work-idea" if args.idea else "work-add",
            quick_add_work(
                args.workspace,
                args.title,
                create=args.create,
                modify=args.modify,
                delete=args.delete,
                paths=args.paths,
                read=args.read,
                palari_id=args.palari_id,
                goal_id=args.goal,
                workbench_id=args.workbench,
                risk=args.risk,
                intensity=args.intensity,
                scope=args.scope,
                acceptance_target=args.acceptance,
                verify=args.verify,
                approvals=args.approvals,
                dependencies=args.dependencies,
                parallel_policy=args.parallel_policy,
                idea=args.idea,
            ),
            args.json,
        )

    if args.command == "reviewer" and args.object_command == "add":
        from .authoring import create_record

        return CommandResult(
            "mutation",
            create_record(
                args.workspace,
                "palari",
                {
                    "id": args.id,
                    "name": args.name,
                    "role": "Review-only AI partner",
                    "scope": "Independent review only",
                    "owner_human": args.owner,
                    "linked_goals": [args.goal],
                    "forbidden_actions": [
                        "build or modify task outputs",
                        "broaden task scope",
                        "send external messages",
                        "record human approval",
                    ],
                },
                command="reviewer add",
                actor=args.owner,
            ),
            args.json,
        )

    if args.command == "review" and args.object_command == "record":
        from .authoring import create_record

        record = {
            "id": args.id,
            "work_item_id": args.work_item_id,
            "reviewed_head": args.reviewed_head,
            "reviewer": args.reviewer,
            "review_binding_digest": args.review_binding_digest,
            "verdict": args.verdict,
        }
        if args.timestamp:
            record["timestamp"] = args.timestamp
        return CommandResult(
            "mutation",
            create_record(args.workspace, "review", record, command="review record"),
            args.json,
        )

    if args.command == "human-decision" and args.object_command == "pack":
        from .approval_packs import apply_pack_decision

        return CommandResult(
            "approval-pack-decision",
            apply_pack_decision(
                args.workspace,
                pack_digest=args.pack_digest,
                presentation_digest=args.presentation_digest,
                human_id=args.human_id,
                approve_eligible=args.approve_eligible,
                approve=args.approve,
                reject=args.reject,
                defer=args.defer,
                pack_members=args.pack_member,
                reason=args.reason,
            ),
            args.json,
        )

    raise WorkspaceError("unknown command")


def _canonicalize_work_refs(args: argparse.Namespace) -> None:
    """Resolve unique WORK-/IDEA- prefixes before command handlers see stored IDs."""

    list_fields = ("select", "approve", "reject", "defer", "pack_member")
    work_id = getattr(args, "work_id", None)
    lists = {name: list(getattr(args, name, None) or []) for name in list_fields}
    if not (isinstance(work_id, str) and work_id) and not any(lists.values()):
        return
    if getattr(args, "command", "") in {"demo", "init"}:
        return
    workspace_path = getattr(args, "workspace", None)
    if not workspace_path:
        return
    try:
        workspace = Workspace.load(workspace_path)
    except (OSError, WorkspaceError):
        return
    known = [item.id for item in workspace.work_items]
    known.extend(item.id for item in workspace.proposals)
    if isinstance(work_id, str) and work_id:
        args.work_id = resolve_opaque_id(work_id, known)
    for name, values in lists.items():
        if values:
            setattr(args, name, [resolve_opaque_id(item, known) for item in values])


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
