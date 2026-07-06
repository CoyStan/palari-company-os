from __future__ import annotations

import argparse
from typing import Any

from .workspace import default_workspace_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="palari", description="Palari Company OS CLI")
    parser.add_argument(
        "--workspace",
        default=str(default_workspace_path()),
        help="Workspace directory or workspace.json file.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser(
        "demo",
        help="Run the two-minute blocked-write demo in a throwaway workspace.",
    )
    demo_parser.add_argument(
        "--dir",
        dest="demo_dir",
        help="Empty directory to use for the demo workspace. Defaults to a temp directory.",
    )
    demo_parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Do not wait between demo acts.",
    )
    demo_parser.add_argument(
        "--serve",
        action="store_true",
        help="Prepare the demo workspace and open it in live Mission Control.",
    )
    demo_parser.add_argument("--host", default="127.0.0.1", help="Host to bind with --serve.")
    demo_parser.add_argument("--port", type=int, default=0, help="Port to bind with --serve.")
    demo_parser.add_argument("--json", action="store_true", help="Emit JSON transcript.")

    queue_parser = subparsers.add_parser("queue", help="Show work needing attention.")
    queue_parser.add_argument(
        "--include-closed",
        action="store_true",
        help="Include completed/closed work items in the queue output.",
    )
    queue_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    state_parser = subparsers.add_parser("state", help="Show compact operator state.")
    state_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    data_parser = subparsers.add_parser("data", help="Inspect workspace data boundaries.")
    data_nested = data_parser.add_subparsers(dest="data_command", required=True)
    data_map_parser = data_nested.add_parser(
        "map",
        help="Show where workspace data, sources, integrations, memory, and history live.",
    )
    data_map_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    _add_docs_parser(subparsers)

    validate_parser = subparsers.add_parser("validate", help="Validate the workspace.")
    validate_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    detail_parser = subparsers.add_parser("detail", help="Show one work item.")
    detail_parser.add_argument("work_id")
    detail_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    scope_parser = subparsers.add_parser("scope", help="Check declared work scope.")
    scope_parser.add_argument("work_id")
    scope_parser.add_argument(
        "--changed",
        action="append",
        default=[],
        metavar="PATH",
        help="Changed path to check. Repeat for multiple paths.",
    )
    scope_parser.add_argument(
        "--action",
        action="append",
        default=[],
        metavar="ACTION",
        help="Action to check against forbidden actions. Repeat for multiple actions.",
    )
    scope_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    integrations_parser = subparsers.add_parser(
        "integrations",
        help="List declared dry-run integrations.",
    )
    integrations_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    _add_integration_parser(subparsers)
    _add_agent_parser(subparsers)
    _add_workspace_parser(subparsers)
    _add_mcp_parser(subparsers)

    migrate_parser = subparsers.add_parser(
        "migrate", help="Migrate a workspace to the current schema."
    )
    migrate_parser.add_argument("--write", action="store_true", help="Write migration result.")
    migrate_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    history_parser = subparsers.add_parser("history", help="Show recent workspace history events.")
    history_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of recent events to show. Use 0 for none.",
    )
    history_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Generate a read-only static dashboard.",
    )
    dashboard_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for generated dashboard files.",
    )
    dashboard_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    desktop_prototype_parser = subparsers.add_parser(
        "desktop-prototype",
        help="Generate a static Palari Desktop shell prototype with demo data.",
    )
    desktop_prototype_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for generated prototype files.",
    )
    desktop_prototype_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    desktop_serve_parser = subparsers.add_parser(
        "desktop-serve",
        help="Serve the static Palari Desktop prototype locally.",
    )
    desktop_serve_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for generated prototype files.",
    )
    desktop_serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    desktop_serve_parser.add_argument("--port", type=int, default=0, help="Port to bind.")

    serve_parser = subparsers.add_parser(
        "serve",
        help="Serve live local Mission Control for one human operator.",
    )
    serve_parser.add_argument("--as", dest="human_id", required=True, help="Acting human id.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve_parser.add_argument("--port", type=int, default=0, help="Port to bind.")

    _add_goal_parser(subparsers)
    _add_human_parser(subparsers)
    _add_palari_parser(subparsers)
    _add_source_parser(subparsers)
    _add_playbook_source_parser(subparsers)
    _add_decision_parser(subparsers)
    _add_work_parser(subparsers)
    _add_attempt_parser(subparsers)
    _add_evidence_parser(subparsers)
    _add_review_parser(subparsers)
    _add_human_decision_parser(subparsers)
    _add_receipt_parser(subparsers)
    _add_outcome_parser(subparsers)
    _add_lifecycle_parser(subparsers)
    _add_maintainer_parser(subparsers)
    _add_playbooks_parser(subparsers)
    _add_gate_parser(subparsers)

    return parser


def _add_agent_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("agent", help="Compile bounded packets for AI agents.")
    nested = parser.add_subparsers(dest="agent_command", required=True)
    next_parser = nested.add_parser(
        "next",
        help="Show the next safe work candidates for one Palari or all Palaris.",
    )
    next_scope = next_parser.add_mutually_exclusive_group()
    next_scope.add_argument("--as", dest="palari_id", help="Acting Palari id.")
    next_scope.add_argument("--all", action="store_true", help="Show a rollup for all Palaris.")
    next_parser.add_argument("--mode", default="execute", help="Packet mode.")
    next_parser.add_argument("--limit", type=int, default=5, help="Maximum candidates to show.")
    next_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    brief = nested.add_parser(
        "brief",
        help="Compile a read-only agent packet for one work item.",
    )
    brief.add_argument("work_id")
    brief.add_argument("--as", dest="palari_id", required=True, help="Acting Palari id.")
    brief.add_argument("--mode", default="execute", help="Packet mode.")
    brief.add_argument("--json", action="store_true", help="Emit JSON.")
    start = nested.add_parser(
        "start",
        help="Persist the agent packet and claim one ready work item.",
    )
    start.add_argument("work_id")
    start.add_argument("--as", dest="palari_id", required=True, help="Acting Palari id.")
    start.add_argument("--mode", default="execute", help="Packet mode.")
    start.add_argument(
        "--lease-minutes",
        type=int,
        default=30,
        help="Claim lease length in minutes.",
    )
    start.add_argument("--json", action="store_true", help="Emit JSON.")
    release = nested.add_parser(
        "release",
        help="Release this Palari's local claim for one work item.",
    )
    release.add_argument("work_id")
    release.add_argument("--as", dest="palari_id", required=True, help="Acting Palari id.")
    release.add_argument("--json", action="store_true", help="Emit JSON.")
    check = nested.add_parser(
        "check",
        help="Check whether one work item currently satisfies its agent packet contract.",
    )
    check.add_argument("work_id")
    check.add_argument("--as", dest="palari_id", required=True, help="Acting Palari id.")
    check.add_argument("--mode", default="execute", help="Packet mode.")
    check.add_argument(
        "--changed",
        action="append",
        default=[],
        metavar="PATH",
        help="Observed changed path to compare with packet write boundaries. Repeatable.",
    )
    check.add_argument(
        "--git-diff",
        action="store_true",
        help="Inspect current git status against packet write boundaries.",
    )
    check.add_argument("--json", action="store_true", help="Emit JSON.")
    finish = nested.add_parser(
        "finish",
        help="Check whether one work item is ready for an agent completion report.",
    )
    finish.add_argument("work_id")
    finish.add_argument("--as", dest="palari_id", required=True, help="Acting Palari id.")
    finish.add_argument("--mode", default="execute", help="Packet mode.")
    finish.add_argument("--json", action="store_true", help="Emit JSON.")
    handoff = nested.add_parser(
        "handoff",
        help="Compile a read-only human handoff packet for one work item.",
    )
    handoff.add_argument("work_id")
    handoff.add_argument("--as", dest="palari_id", required=True, help="Acting Palari id.")
    handoff.add_argument("--mode", default="execute", help="Packet mode.")
    handoff.add_argument("--json", action="store_true", help="Emit JSON.")
    loop = nested.add_parser(
        "loop",
        help="Summarize the read-only agent next, brief, check, finish, and handoff loop.",
    )
    loop.add_argument("work_id")
    loop.add_argument("--as", dest="palari_id", required=True, help="Acting Palari id.")
    loop.add_argument("--mode", default="execute", help="Packet mode.")
    loop.add_argument("--json", action="store_true", help="Emit JSON.")
    doctor = nested.add_parser(
        "doctor",
        help="Explain why one work item is or is not safe for an agent right now.",
    )
    doctor.add_argument("work_id")
    doctor.add_argument("--as", dest="palari_id", required=True, help="Acting Palari id.")
    doctor.add_argument("--mode", default="execute", help="Packet mode.")
    doctor.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_docs_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "docs",
        help="Inspect and bootstrap agent-ready repository documentation.",
    )
    nested = parser.add_subparsers(dest="docs_command", required=True)

    check = nested.add_parser("check", help="Check agent-ready repo documentation freshness.")
    check.add_argument("--repo", default=".", help="Repository path to inspect.")
    check.add_argument("--json", action="store_true", help="Emit JSON.")

    init = nested.add_parser("init", help="Propose or create starter agent-ready repo docs.")
    init.add_argument("--repo", default=".", help="Repository path to inspect.")
    init.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the proposed starter docs without writing files.",
    )
    init.add_argument("--write", action="store_true", help="Create missing starter docs.")
    init.add_argument(
        "--overwrite",
        action="store_true",
        help="With --write, replace existing starter docs.",
    )
    init.add_argument("--json", action="store_true", help="Emit JSON.")

    docs_map = nested.add_parser("map", help="Show the agent-ready documentation map.")
    docs_map.add_argument("--repo", default=".", help="Repository path to inspect.")
    docs_map.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_workspace_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("workspace", help="Initialize or inspect workspaces.")
    nested = parser.add_subparsers(dest="workspace_command", required=True)
    init = nested.add_parser("init", help="Create a blank valid workspace.json.")
    init.add_argument("path", help="Workspace directory or workspace.json path to create.")
    init.add_argument("--name", required=True, help="Human-facing workspace name.")
    init.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_mcp_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("mcp", help="Serve Palari tools through MCP.")
    nested = parser.add_subparsers(dest="mcp_command", required=True)
    serve = nested.add_parser(
        "serve",
        help="Run a read-only stdio MCP server for Palari agent tools.",
    )
    serve.add_argument(
        "--repo",
        default=".",
        help="Repository path for docs tools.",
    )


def _add_integration_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("integration", help="Check or plan one integration.")
    nested = parser.add_subparsers(dest="integration_command", required=True)

    check = nested.add_parser("check", help="Check one declared integration.")
    check.add_argument("integration_id")
    check.add_argument("--json", action="store_true", help="Emit JSON.")

    plan = nested.add_parser("plan", help="Preview a dry-run integration payload.")
    plan.add_argument("integration_id")
    plan.add_argument("--work", dest="work_id", required=True, help="Work item id.")
    plan.add_argument("--event", required=True, help="Integration event to preview.")
    plan.add_argument("--action", required=True, help="Integration action to preview.")
    plan.add_argument("--record", action="store_true", help="Record the dry-run plan.")
    plan.add_argument("--id", dest="plan_id", default="", help="Optional integration plan id.")
    plan.add_argument("--actor", default="", help="Actor to attribute when recording.")
    plan.add_argument("--json", action="store_true", help="Emit JSON.")

    approve = nested.add_parser("approve", help="Approve a recorded dry-run integration plan.")
    approve.add_argument("plan_id")
    approve.add_argument("--by", dest="human_id", required=True, help="Approving human id.")
    approve.add_argument("--reason", default="", help="Optional approval note.")
    approve.add_argument("--json", action="store_true", help="Emit JSON.")

    reject = nested.add_parser("reject", help="Reject a recorded dry-run integration plan.")
    reject.add_argument("plan_id")
    reject.add_argument("--by", dest="human_id", required=True, help="Rejecting human id.")
    reject.add_argument("--reason", required=True, help="Reason for rejection.")
    reject.add_argument("--json", action="store_true", help="Emit JSON.")

    cancel = nested.add_parser("cancel", help="Cancel a recorded dry-run integration plan.")
    cancel.add_argument("plan_id")
    cancel.add_argument("--by", dest="human_id", required=True, help="Canceling human id.")
    cancel.add_argument("--reason", required=True, help="Reason for cancellation.")
    cancel.add_argument("--json", action="store_true", help="Emit JSON.")

    enqueue = nested.add_parser("enqueue", help="Queue an approved plan for future execution.")
    enqueue.add_argument("plan_id")
    enqueue.add_argument("--by", dest="human_id", required=True, help="Enqueuing human id.")
    enqueue.add_argument("--json", action="store_true", help="Emit JSON.")

    outbox_check = nested.add_parser(
        "outbox-check",
        help="Preflight a queued integration outbox item without executing it.",
    )
    outbox_check.add_argument("outbox_id")
    outbox_check.add_argument("--json", action="store_true", help="Emit JSON.")

    outbox_cancel = nested.add_parser(
        "outbox-cancel",
        help="Cancel a queued integration outbox item.",
    )
    outbox_cancel.add_argument("outbox_id")
    outbox_cancel.add_argument("--by", dest="human_id", required=True, help="Canceling human id.")
    outbox_cancel.add_argument("--reason", required=True, help="Reason for cancellation.")
    outbox_cancel.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_common_mutation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="Set a scalar field. Repeat for multiple fields.",
    )
    parser.add_argument(
        "--list",
        action="append",
        default=[],
        metavar="FIELD=A,B",
        help="Set a comma-separated list field. Repeat for multiple fields.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_create_update(
    subparsers: Any,
    name: str,
    help_text: str,
    create_fields: list[tuple[str, dict[str, Any]]],
) -> tuple[Any, argparse.ArgumentParser, argparse.ArgumentParser]:
    parser = subparsers.add_parser(name, help=help_text)
    nested = parser.add_subparsers(dest="object_command", required=True)
    create = nested.add_parser("create", help=f"Create a {name} record.")
    create.add_argument("id")
    for field_name, kwargs in create_fields:
        create.add_argument(f"--{field_name.replace('_', '-')}", dest=field_name, **kwargs)
    _add_common_mutation_args(create)
    update = nested.add_parser("update", help=f"Update a {name} record.")
    update.add_argument("id")
    for field_name, kwargs in create_fields:
        update.add_argument(
            f"--{field_name.replace('_', '-')}",
            dest=field_name,
            required=False,
            default=None,
            help=kwargs.get("help"),
        )
    _add_common_mutation_args(update)
    return nested, create, update


def _add_goal_parser(subparsers: Any) -> None:
    _add_create_update(
        subparsers,
        "goal",
        "Create or update goals.",
        [
            ("title", {"required": True, "help": "Goal title."}),
            ("owner", {"default": "", "help": "Owning human id."}),
            ("status", {"default": "active", "help": "Goal status."}),
            ("priority", {"default": "normal", "help": "Goal priority."}),
        ],
    )


def _add_human_parser(subparsers: Any) -> None:
    _add_create_update(
        subparsers,
        "human",
        "Create or update humans.",
        [
            ("name", {"required": True, "help": "Human name."}),
            ("role", {"default": "", "help": "Human role."}),
            ("authority_level", {"default": "standard", "help": "Authority level."}),
            ("availability", {"default": "", "help": "Availability signal."}),
            ("capacity_signal", {"default": "", "help": "Capacity signal."}),
        ],
    )


def _add_palari_parser(subparsers: Any) -> None:
    _add_create_update(
        subparsers,
        "palari",
        "Create or update Palaris.",
        [
            ("name", {"required": True, "help": "Palari name."}),
            ("role", {"required": True, "help": "Palari role."}),
            ("scope", {"default": "", "help": "Palari scope."}),
            ("owner_human", {"default": "", "help": "Owner human id."}),
            ("default_worker", {"default": "", "help": "Default model or worker route."}),
        ],
    )


def _add_source_parser(subparsers: Any) -> None:
    _add_create_update(
        subparsers,
        "source",
        "Create or update selected sources.",
        [
            ("label", {"required": True, "help": "Human-facing source label."}),
            ("kind", {"default": "", "help": "Source kind, such as note or file."}),
            ("provider", {"default": "", "help": "Source provider."}),
            ("uri", {"default": "", "help": "Source URI."}),
            ("external_id", {"default": "", "help": "Provider-specific source id."}),
            ("access_mode", {"default": "", "help": "Read/write access mode."}),
            ("owner_human", {"default": "", "help": "Owner human id."}),
            (
                "data_class",
                {"default": "", "help": "Data class: public/internal/confidential/restricted."},
            ),
            ("authority", {"default": "", "help": "Source authority, such as user_owned."}),
            ("steward_human", {"default": "", "help": "Human steward responsible for this source."}),
            ("freshness_sla", {"default": "", "help": "Freshness expectation, such as weekly."}),
            ("last_seen_revision", {"default": "", "help": "Last seen revision."}),
            ("last_read_at", {"default": "", "help": "Last read timestamp."}),
        ],
    )


def _add_playbook_source_parser(subparsers: Any) -> None:
    _add_create_update(
        subparsers,
        "playbook-source",
        "Create or update external playbook sources.",
        [
            ("label", {"required": True, "help": "Human-facing playbook source label."}),
            ("provider", {"default": "", "help": "Source provider, such as github."}),
            ("uri", {"default": "", "help": "Source URI."}),
            ("ref", {"default": "", "help": "Pinned branch, tag, or commit."}),
            ("license", {"default": "", "help": "License label."}),
            ("install_hint", {"default": "", "help": "Review or use hint."}),
        ],
    )


def _add_decision_parser(subparsers: Any) -> None:
    nested, _create, _update = _add_create_update(
        subparsers,
        "decision",
        "Guide, create, or update decisions.",
        [
            ("question", {"required": True, "help": "Decision question."}),
            ("status", {"default": "open", "help": "Decision status."}),
            ("context", {"default": "", "help": "Decision context."}),
            ("recommendation", {"default": "", "help": "Recommendation."}),
            ("safe_default", {"default": "", "help": "Safe default."}),
            ("required_human", {"default": "", "help": "Required human id."}),
            ("required_role", {"default": "", "help": "Required role."}),
            ("due_date", {"default": "", "help": "Due date."}),
            ("linked_goal", {"default": "", "help": "Linked goal id."}),
            ("linked_work", {"default": "", "help": "Linked work id."}),
            ("linked_palari", {"default": "", "help": "Linked Palari id."}),
        ],
    )
    guide = nested.add_parser("guide", help="Build a read-only decision guide.")
    guide.add_argument("target_id", help="Decision id, or a work item id linked to a decision.")
    guide.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_work_parser(subparsers: Any) -> None:
    nested, create, update = _add_create_update(
        subparsers,
        "work",
        "Create, update, or complete work items.",
        [
            ("title", {"required": True, "help": "Work title."}),
            ("goal", {"required": True, "help": "Goal id."}),
            ("palari", {"required": True, "help": "Palari id."}),
            ("risk", {"default": "R1", "help": "Risk level."}),
            ("intensity", {"default": "light", "help": "Operating intensity."}),
            ("status", {"default": "proposed", "help": "Work status."}),
            ("scope", {"default": "", "help": "Work scope."}),
            ("acceptance_target", {"default": "", "help": "Acceptance target."}),
            ("current_attempt", {"default": "", "help": "Current attempt id."}),
            (
                "required_approval_capability",
                {"default": "", "help": "Required approval capability."},
            ),
        ],
    )
    create.add_argument(
        "--required-approval-count",
        dest="required_approval_count",
        type=int,
        default=1,
        help="Required approval count.",
    )
    update.add_argument(
        "--required-approval-count",
        dest="required_approval_count",
        type=int,
        default=None,
        help="Required approval count.",
    )
    complete = nested.add_parser("complete", help="Complete a ready work item.")
    complete.add_argument("work_id")
    complete.add_argument("--status", default="completed", help="Terminal status to write.")
    complete.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_attempt_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("attempt", help="Record or update attempts.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    record = nested.add_parser("record", help="Record an attempt.")
    record.add_argument("id")
    record.add_argument("--work-item-id", required=True, help="Work item id.")
    record.add_argument("--actor", required=True, help="Actor id.")
    record.add_argument("--status", default="active", help="Attempt status.")
    record.add_argument("--branch", default="", help="Branch name.")
    record.add_argument("--workspace-path", default="", help="Workspace path.")
    record.add_argument("--model-or-worker", default="", help="Model or worker.")
    record.add_argument("--started-at", default="", help="Started timestamp.")
    record.add_argument("--cleanliness", default="", help="Cleanliness state.")
    record.add_argument("--result", default="", help="Attempt result.")
    _add_common_mutation_args(record)
    update = nested.add_parser("update", help="Update an attempt.")
    update.add_argument("id")
    _add_common_mutation_args(update)


def _add_evidence_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("evidence", help="Record or update evidence runs.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    record = nested.add_parser("record", help="Record evidence.")
    record.add_argument("id")
    record.add_argument("--work-item-id", required=True, help="Work item id.")
    record.add_argument("--attempt-id", required=True, help="Attempt id.")
    record.add_argument("--head-sha", required=True, help="Head sha or reference.")
    record.add_argument("--status", required=True, choices=["passed", "failed", "skipped"])
    record.add_argument("--base-ref", default="", help="Base ref.")
    record.add_argument("--summary", default="", help="Evidence summary.")
    record.add_argument("--freshness", default="fresh", help="Freshness state.")
    record.add_argument("--timestamp", default="", help="Timestamp.")
    _add_common_mutation_args(record)
    update = nested.add_parser("update", help="Update evidence.")
    update.add_argument("id")
    _add_common_mutation_args(update)


def _add_review_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("review", help="Guide, record, or update review verdicts.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    guide = nested.add_parser("guide", help="Build a read-only review guide for one work item.")
    guide.add_argument("work_id")
    guide.add_argument("--json", action="store_true", help="Emit JSON.")
    record = nested.add_parser("record", help="Record a review verdict.")
    record.add_argument("id")
    record.add_argument("--work-item-id", required=True, help="Work item id.")
    record.add_argument("--reviewed-head", required=True, help="Reviewed head.")
    record.add_argument("--reviewer", required=True, help="Reviewer id or role.")
    record.add_argument(
        "--verdict",
        required=True,
        choices=["accept-ready", "changes-requested", "needs-human-decision", "blocked"],
    )
    record.add_argument("--timestamp", default="", help="Timestamp.")
    _add_common_mutation_args(record)
    update = nested.add_parser("update", help="Update review.")
    update.add_argument("id")
    _add_common_mutation_args(update)


def _add_human_decision_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("human-decision", help="Record or update human decisions.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    record = nested.add_parser("record", help="Record a human decision or acceptance.")
    record.add_argument("id")
    record.add_argument("--work-item-id", required=True, help="Work item id.")
    record.add_argument("--human-id", required=True, help="Human id.")
    record.add_argument("--reviewed-head", required=True, help="Reviewed head.")
    record.add_argument("--decision", required=True, help="Decision value.")
    record.add_argument("--status", default="recorded", help="Decision status.")
    record.add_argument("--acceptance-mode", default="human", help="Acceptance mode.")
    record.add_argument("--quorum-status", default="", help="Quorum status.")
    record.add_argument("--evidence-reference", default="", help="Evidence id.")
    record.add_argument("--review-reference", default="", help="Review id.")
    record.add_argument("--timestamp", default="", help="Timestamp.")
    _add_common_mutation_args(record)
    update = nested.add_parser("update", help="Update human decision.")
    update.add_argument("id")
    _add_common_mutation_args(update)


def _add_receipt_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("receipt", help="Record or update human-facing receipts.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    record = nested.add_parser("record", help="Record a receipt.")
    record.add_argument("id")
    record.add_argument("--work-item-id", required=True, help="Work item id.")
    record.add_argument("--attempt-id", required=True, help="Attempt id.")
    record.add_argument("--actor", required=True, help="Receipt actor.")
    record.add_argument("--timestamp", default="", help="Timestamp.")
    _add_common_mutation_args(record)
    update = nested.add_parser("update", help="Update a receipt.")
    update.add_argument("id")
    _add_common_mutation_args(update)


def _add_outcome_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("outcome", help="Record or update outcomes.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    record = nested.add_parser("record", help="Record an outcome.")
    record.add_argument("id")
    record.add_argument("--work-item-id", required=True, help="Work item id.")
    record.add_argument("--summary", required=True, help="Outcome summary.")
    record.add_argument("--status", default="captured", help="Outcome status.")
    record.add_argument("--what-happened", default="", help="What happened.")
    record.add_argument("--what-changed", default="", help="What changed.")
    record.add_argument("--timestamp", default="", help="Timestamp.")
    _add_common_mutation_args(record)
    update = nested.add_parser("update", help="Update outcome.")
    update.add_argument("id")
    _add_common_mutation_args(update)


def _add_playbooks_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "playbooks",
        help="Inspect external playbook sources and work-item recommendations.",
    )
    nested = parser.add_subparsers(dest="playbooks_command", required=True)
    sources = nested.add_parser("sources", help="List configured playbook sources.")
    sources.add_argument("--json", action="store_true", help="Emit JSON.")
    recommend = nested.add_parser("recommend", help="Recommend playbooks for one work item.")
    recommend.add_argument("work_id")
    recommend.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_gate_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "gate",
        help="Inspect built-in review gate profiles and work-item gate recommendations.",
    )
    nested = parser.add_subparsers(dest="gate_command", required=True)
    profiles = nested.add_parser("profiles", help="List built-in review gate profiles.")
    profiles.add_argument("--json", action="store_true", help="Emit JSON.")
    recommend = nested.add_parser("recommend", help="Recommend review gates for one work item.")
    recommend.add_argument("work_id")
    recommend.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_lifecycle_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "lifecycle", help="Lifecycle aliases for evidence, review, decision, completion, and outcome."
    )
    nested = parser.add_subparsers(dest="lifecycle_command", required=True)
    evidence = nested.add_parser("evidence", help="Record lifecycle evidence.")
    evidence.add_argument("id")
    evidence.add_argument("--work-item-id", required=True)
    evidence.add_argument("--attempt-id", required=True)
    evidence.add_argument("--head-sha", required=True)
    evidence.add_argument("--status", required=True, choices=["passed", "failed", "skipped"])
    evidence.add_argument("--summary", default="")
    evidence.add_argument("--timestamp", default="")
    _add_common_mutation_args(evidence)
    review = nested.add_parser("review", help="Record lifecycle review.")
    review.add_argument("id")
    review.add_argument("--work-item-id", required=True)
    review.add_argument("--reviewed-head", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument(
        "--verdict",
        required=True,
        choices=["accept-ready", "changes-requested", "needs-human-decision", "blocked"],
    )
    review.add_argument("--timestamp", default="")
    _add_common_mutation_args(review)
    decide = nested.add_parser("decide", help="Record lifecycle human decision.")
    decide.add_argument("id")
    decide.add_argument("--work-item-id", required=True)
    decide.add_argument("--human-id", required=True)
    decide.add_argument("--reviewed-head", required=True)
    decide.add_argument("--decision", required=True)
    decide.add_argument("--status", default="recorded")
    decide.add_argument("--acceptance-mode", default="human")
    decide.add_argument("--quorum-status", default="")
    decide.add_argument("--evidence-reference", default="")
    decide.add_argument("--review-reference", default="")
    decide.add_argument("--timestamp", default="")
    _add_common_mutation_args(decide)
    complete = nested.add_parser("complete", help="Complete lifecycle work.")
    complete.add_argument("work_id")
    complete.add_argument("--status", default="completed")
    complete.add_argument("--json", action="store_true")
    outcome = nested.add_parser("outcome", help="Record lifecycle outcome.")
    outcome.add_argument("id")
    outcome.add_argument("--work-item-id", required=True)
    outcome.add_argument("--summary", required=True)
    outcome.add_argument("--status", default="captured")
    outcome.add_argument("--what-happened", default="")
    outcome.add_argument("--what-changed", default="")
    outcome.add_argument("--timestamp", default="")
    _add_common_mutation_args(outcome)


def _add_maintainer_parser(subparsers: Any) -> None:
    maintainer_parser = subparsers.add_parser("maintainer", help="External maintainer tools.")
    maintainer_subparsers = maintainer_parser.add_subparsers(
        dest="maintainer_command", required=True
    )
    status_parser = maintainer_subparsers.add_parser("status", help="Show repo status.")
    status_parser.add_argument("--repo", default=".", help="Repo path to inspect.")
    status_parser.add_argument("--json", action="store_true", help="Emit JSON.")
