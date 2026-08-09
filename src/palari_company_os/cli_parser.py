from __future__ import annotations

import argparse
from typing import Any

from .agent_adoption import SUPPORTED_HOSTS
from .workspace import default_workspace_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="palari",
        description="Make AI work reviewable with clear limits, recorded checks, and human approval.",
        epilog=(
            "Ordinary journey: init -> work add -> agent start --next -> agent advance -> "
            "review -> approve -> proof verify.\n"
            "Additional expert and recovery commands remain available through direct --help."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument(
        "--workspace",
        default=str(default_workspace_path()),
        help="Workspace directory or workspace.json file.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

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
        "--journey",
        action="store_true",
        help=("Narrate the solo-maintainer R2 closeout: init through review and founder approval."),
    )
    demo_parser.add_argument(
        "--serve",
        action="store_true",
        help="Prepare the demo workspace and open it in live Mission Control.",
    )
    demo_parser.add_argument("--host", default="127.0.0.1", help="Host to bind with --serve.")
    demo_parser.add_argument("--port", type=int, default=0, help="Port to bind with --serve.")
    demo_parser.add_argument("--json", action="store_true", help="Emit JSON transcript.")

    init_parser = subparsers.add_parser(
        "init",
        help="Set up Palari in an existing repository.",
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository directory for workspace.json. Defaults to the current directory.",
    )
    init_parser.add_argument(
        "--name",
        default="",
        help="Workspace name. Defaults to the directory name.",
    )
    init_parser.add_argument(
        "--palari",
        default="Claude",
        help="Name for the starter agent. Defaults to Claude.",
    )
    init_parser.add_argument(
        "--host",
        choices=SUPPORTED_HOSTS,
        default="",
        help="Also install and anchor one tested local agent-host profile.",
    )
    init_parser.add_argument(
        "--strict-git",
        action="store_true",
        help=(
            "With --host cursor, also install the git pre-commit commit gate "
            "(opt-in; Cursor defaults to advisory-only)."
        ),
    )
    init_parser.add_argument(
        "--as",
        dest="palari_id",
        default="",
        help="Existing agent id for idempotent host setup.",
    )
    init_parser.add_argument(
        "--hook-event",
        choices=["pre-tool-use", "stop", "session-start"],
        default="",
        help=argparse.SUPPRESS,
    )
    init_parser.add_argument(
        "--strict",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    init_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    approve_parser = subparsers.add_parser(
        "approve",
        help="Approve one idea, or approve and complete one reviewed local task.",
    )
    approve_parser.add_argument("work_id", help="Idea or task id.")
    approve_parser.add_argument(
        "--as",
        dest="human_id",
        required=True,
        help="Acting human id.",
    )
    approve_parser.add_argument(
        "--reason",
        default="",
        help="Optional human rationale retained in governance history.",
    )
    approve_parser.add_argument(
        "--presented",
        default="",
        metavar="DIGEST",
        help=argparse.SUPPRESS,
    )
    approve_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    queue_parser = subparsers.add_parser("queue", help="Show tasks needing attention.")
    queue_parser.add_argument(
        "--include-closed",
        action="store_true",
        help="Include completed tasks in the queue output.",
    )
    queue_parser.add_argument(
        "--approval-inbox",
        action="store_true",
        help="Show deterministic Approval Packs instead of the ordinary queue.",
    )
    queue_parser.add_argument(
        "--select",
        action="append",
        default=[],
        metavar="WORK-ID",
        help="Narrow the Approval Inbox to specific tasks. Repeatable.",
    )
    queue_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    state_parser = subparsers.add_parser("state", help="Show compact workspace status.")
    state_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    _add_docs_parser(subparsers)
    _add_proof_parser(subparsers)

    validate_parser = subparsers.add_parser("validate", help="Check the workspace files.")
    validate_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    detail_parser = subparsers.add_parser("detail", help="Show one task.")
    detail_parser.add_argument("work_id")
    detail_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    scope_parser = subparsers.add_parser("scope", help="Check a task's allowed files and actions.")
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
    _add_linear_parser(subparsers)
    _add_agent_parser(subparsers)
    _add_claude_parser(subparsers)
    _add_git_parser(subparsers)
    _add_cursor_parser(subparsers)

    _add_mcp_parser(subparsers)

    history_parser = subparsers.add_parser(
        "history", help="Verify or manage replayable tamper-evident history."
    )
    history_mode = history_parser.add_mutually_exclusive_group()
    history_mode.add_argument(
        "--checkpoint",
        action="store_true",
        help="Create an explicit restore point in tamper-evident history.",
    )
    history_mode.add_argument(
        "--recover",
        action="store_true",
        help="Idempotently resolve a prepared history update when safe.",
    )
    history_parser.add_argument(
        "--acknowledge-break",
        action="store_true",
        help="With --checkpoint, preserve a visible history break after manual edits.",
    )
    history_parser.add_argument(
        "--actor",
        default="",
        help="Declared local actor for a restore-point or recovery record.",
    )
    history_parser.add_argument(
        "--reason",
        default="",
        help="Reason for creating or restoring a local restore point.",
    )
    history_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    serve_parser = subparsers.add_parser(
        "serve",
        help="Serve live local Mission Control for one human operator.",
    )
    serve_parser.add_argument("--as", dest="human_id", required=True, help="Acting human id.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve_parser.add_argument("--port", type=int, default=0, help="Port to bind.")

    _add_work_parser(subparsers)
    _add_reviewer_parser(subparsers)
    _add_decision_parser(subparsers)
    _add_review_parser(subparsers)
    _add_human_decision_parser(subparsers)

    _focus_default_help(subparsers)
    _disable_argument_abbreviations(parser)
    return parser


def _focus_default_help(subparsers: Any) -> None:
    """Keep expert commands parseable while making the ordinary journey obvious."""

    ordinary = (
        "init",
        "work",
        "agent",
        "approve",
        "queue",
        "detail",
        "proof",
        "validate",
        "docs",
    )
    actions = {action.dest: action for action in subparsers._choices_actions}
    subparsers._choices_actions = [actions[name] for name in ordinary]


def _disable_argument_abbreviations(parser: argparse.ArgumentParser) -> None:
    """Apply the root's fail-closed option grammar to every nested parser."""

    parser.allow_abbrev = False
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if not isinstance(choices, dict):
            continue
        for child in set(choices.values()):
            if isinstance(child, argparse.ArgumentParser):
                _disable_argument_abbreviations(child)


def _add_agent_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("agent", help="Give AI agents bounded task briefs.")
    nested = parser.add_subparsers(dest="agent_command", required=True, metavar="ACTION")
    home = nested.add_parser("home", help="See Goals, Team, Work, Checks, and Limits.")
    home.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    home.add_argument("--json", action="store_true", help="Emit JSON.")
    next_parser = nested.add_parser(
        "next",
        help="Show the next safe tasks for one agent or all agents.",
    )
    next_scope = next_parser.add_mutually_exclusive_group()
    next_scope.add_argument("--as", dest="palari_id", help="Acting agent id.")
    next_scope.add_argument("--all", action="store_true", help="Show a rollup for all agents.")
    next_parser.add_argument("--mode", default="execute", help="Session mode.")
    next_parser.add_argument("--limit", type=int, default=5, help="Maximum candidates to show.")
    next_parser.add_argument("--json", action="store_true", help="Emit JSON.")
    brief = nested.add_parser(
        "brief",
        help="Show a read-only task brief for one task.",
    )
    brief.add_argument("work_id")
    brief.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    brief.add_argument("--mode", default="execute", help="Session mode.")
    brief.add_argument(
        "--session-contract",
        action="store_true",
        help="Show the provider-neutral session rules instead of the task brief.",
    )
    brief.add_argument("--json", action="store_true", help="Emit JSON.")
    start = nested.add_parser(
        "start",
        help="Start a specific task or the next safe task.",
    )
    start.add_argument("work_id", nargs="?")
    start.add_argument(
        "--next",
        action="store_true",
        dest="start_next",
        help="Select and start the next safe task.",
    )
    start.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    start.add_argument("--mode", default="execute", help="Session mode.")
    start.add_argument(
        "--lease-minutes",
        type=int,
        default=30,
        help="Task-lock length in minutes.",
    )
    start.add_argument(
        "--isolate",
        action="store_true",
        help="Create or resume a dedicated local Git worktree before starting.",
    )
    start.add_argument(
        "--base-ref",
        default="HEAD",
        help="Committed Git ref used as the isolated worktree base.",
    )
    start.add_argument("--json", action="store_true", help="Emit JSON.")
    release = nested.add_parser(
        "release",
        help="Release this agent's local task lock.",
    )
    release.add_argument("work_id")
    release.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    release.add_argument(
        "--reason",
        default="",
        help="Save why the task stopped before releasing its lock.",
    )
    release.add_argument(
        "--next-action",
        default="",
        help="Exact safe action for resuming parked work; requires --reason.",
    )
    release.add_argument("--json", action="store_true", help="Emit JSON.")
    check = nested.add_parser(
        "check",
        help="Check whether one task follows its task brief.",
    )
    check.add_argument("work_id")
    check.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    check.add_argument("--mode", default="execute", help="Session mode.")
    check.add_argument(
        "--changed",
        action="append",
        default=[],
        metavar="PATH",
        help="Changed path to compare with the task's file limits. Repeatable.",
    )
    check.add_argument(
        "--git-diff",
        action="store_true",
        help="Check current Git changes against the task's file limits.",
    )
    check.add_argument("--json", action="store_true", help="Emit JSON.")
    finish = nested.add_parser(
        "finish",
        help="Check whether one task is ready for the agent's final report.",
    )
    finish.add_argument("work_id")
    finish.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    finish.add_argument("--mode", default="execute", help="Session mode.")
    finish.add_argument("--json", action="store_true", help="Emit JSON.")
    handoff = nested.add_parser(
        "handoff",
        help="Show the read-only handoff for one task.",
    )
    handoff.add_argument("work_id")
    handoff.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    handoff.add_argument("--mode", default="execute", help="Session mode.")
    handoff.add_argument("--json", action="store_true", help="Emit JSON.")
    loop = nested.add_parser(
        "loop",
        help="Summarize the task's start, checks, finish, and handoff steps.",
    )
    loop.add_argument("work_id")
    loop.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    loop.add_argument("--mode", default="execute", help="Session mode.")
    loop.add_argument("--json", action="store_true", help="Emit JSON.")
    doctor = nested.add_parser(
        "doctor",
        help="Explain why one task is ready, blocked, or waiting.",
    )
    doctor.add_argument("work_id")
    doctor.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    doctor.add_argument("--mode", default="execute", help="Session mode.")
    doctor.add_argument("--json", action="store_true", help="Emit JSON.")
    advance = nested.add_parser(
        "advance",
        help="Run required checks and stop at review, approval, or a concrete blocker.",
    )
    advance.add_argument("work_id")
    advance.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    advance.add_argument(
        "--dry-run",
        action="store_true",
        help="Return the exact plan without verification or mutation.",
    )
    advance.add_argument(
        "--refresh-verification",
        action="store_true",
        help="Ignore advisory cached records and rerun the required exact profiles.",
    )
    advance.add_argument("--json", action="store_true", help="Emit JSON.")

    actions = {action.dest: action for action in nested._choices_actions}
    nested._choices_actions = [
        actions[name] for name in ("home", "start", "advance", "release", "doctor")
    ]


def _add_claude_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "claude",
        help="Enforce task file limits inside Claude Code sessions.",
    )
    nested = parser.add_subparsers(dest="claude_command", required=True)

    install = nested.add_parser(
        "install",
        help="Write Palari-managed hooks into Claude Code settings.",
    )
    install.add_argument(
        "--project-dir",
        default="",
        help="Repository root that contains .claude/. Defaults to the current directory.",
    )
    install.add_argument(
        "--settings-file",
        default="",
        help="Explicit settings file to write instead of .claude/settings.json.",
    )
    install.add_argument(
        "--local",
        action="store_true",
        help="Write .claude/settings.local.json instead of the shared settings.json.",
    )
    install.add_argument(
        "--strict",
        action="store_true",
        help="Also ask a human before writes that no active task lock covers.",
    )
    install.add_argument(
        "--remove",
        action="store_true",
        help="Remove Palari-managed hooks instead of installing them.",
    )
    install.add_argument("--json", action="store_true", help="Emit JSON.")

    status = nested.add_parser(
        "status",
        help="Show installed Palari hooks and active task locks for Claude Code.",
    )
    status.add_argument(
        "--project-dir",
        default="",
        help="Repository root that contains .claude/. Defaults to the current directory.",
    )
    status.add_argument("--json", action="store_true", help="Emit JSON.")

    hook = nested.add_parser(
        "hook",
        help="Run one Claude Code hook event; reads the hook payload from stdin.",
    )
    hook.add_argument(
        "event",
        choices=["pre-tool-use", "stop", "session-start"],
        help="Hook event to evaluate.",
    )
    hook.add_argument(
        "--strict",
        action="store_true",
        help="Ask a human before writes that no active task lock covers.",
    )


def _add_git_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "git",
        help="Enforce task file limits at Git commit time (IDE-agnostic).",
    )
    nested = parser.add_subparsers(dest="git_command", required=True)

    install = nested.add_parser(
        "install",
        help="Install or remove the Palari pre-commit hook in .git/hooks/.",
    )
    install.add_argument(
        "--project-dir",
        default="",
        help="Repository root. Defaults to the current directory.",
    )
    install.add_argument(
        "--remove",
        action="store_true",
        help="Remove the Palari-managed pre-commit hook instead of installing it.",
    )
    install.add_argument("--json", action="store_true", help="Emit JSON.")

    pre_commit_cmd = nested.add_parser(
        "pre-commit",
        help="Check staged files against active task locks (run by the hook).",
    )
    pre_commit_cmd.add_argument("--json", action="store_true", help="Emit JSON.")

    status = nested.add_parser(
        "status",
        help="Show installed Palari Git hooks and active task locks.",
    )
    status.add_argument(
        "--project-dir",
        default="",
        help="Repository root. Defaults to the current directory.",
    )
    status.add_argument(
        "--work-id",
        default="",
        help="Assess this task against --target-ref instead of listing hooks.",
    )
    status.add_argument(
        "--target-ref",
        default="main",
        help="Local target revision used with --work-id. Defaults to main.",
    )
    status.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_cursor_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "cursor",
        help="Install Cursor advisory boundary rule (optional git commit gate).",
    )
    nested = parser.add_subparsers(dest="cursor_command", required=True)

    install = nested.add_parser(
        "install",
        help=(
            "Write the Palari boundary rule into .cursor/rules/ and, unless "
            "--no-git-hook, install the git pre-commit gate."
        ),
    )
    install.add_argument(
        "--project-dir",
        default="",
        help="Project root that contains .cursor/. Defaults to the current directory.",
    )
    install.add_argument(
        "--no-git-hook",
        action="store_true",
        help="Do not install the IDE-agnostic git pre-commit hook alongside the rule.",
    )
    install.add_argument(
        "--remove",
        action="store_true",
        help="Remove the Palari-managed Cursor rule (and git hook) instead of installing.",
    )
    install.add_argument("--json", action="store_true", help="Emit JSON.")

    status = nested.add_parser(
        "status",
        help="Show the installed Palari Cursor rule, git hook, and active claims.",
    )
    status.add_argument(
        "--project-dir",
        default="",
        help="Project root that contains .cursor/. Defaults to the current directory.",
    )
    status.add_argument("--json", action="store_true", help="Emit JSON.")


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


def _add_proof_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "proof",
        help="Export or independently verify Proof-Carrying AI Work statements.",
    )
    nested = parser.add_subparsers(dest="proof_command", required=True)

    export = nested.add_parser(
        "export",
        help="Export a deterministic PCAW v1 statement for one task.",
    )
    export.add_argument("work_id", help="Task id.")
    export.add_argument("--output", required=True, help="Proof statement output file.")
    export.add_argument("--json", action="store_true", help="Emit a structured export report.")

    verify = nested.add_parser(
        "verify",
        help="Verify a PCAW v1 statement without loading a Palari workspace.",
    )
    verify.add_argument("proof_file", help="PCAW statement JSON file.")
    verify.add_argument(
        "--subject-root",
        default="",
        help="Root for artifact subjects. Defaults to the proof file directory.",
    )
    verify.add_argument(
        "--statement-only",
        action="store_true",
        help="Verify governance consistency without reading artifact subjects.",
    )
    verify.add_argument("--json", action="store_true", help="Emit structured diagnostics.")


def _add_mcp_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("mcp", help="Serve Palari tools through MCP.")
    nested = parser.add_subparsers(dest="mcp_command", required=True)
    serve = nested.add_parser(
        "serve",
        help="Run a local stdio MCP server for Palari agent tools.",
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
    plan.add_argument("--work", dest="work_id", required=True, help="Task id.")
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


def _add_linear_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("linear", help="Use Linear as a governed work surface.")
    nested = parser.add_subparsers(dest="linear_command", required=True)

    doctor = nested.add_parser(
        "doctor",
        help="Check local Linear adapter readiness without calling Linear.",
    )
    doctor.add_argument("--json", action="store_true", help="Emit JSON.")

    connect = nested.add_parser(
        "connect",
        help="Verify Linear credentials and prepare the governed integration record.",
    )
    connect.add_argument(
        "--as",
        dest="actor",
        default="",
        help="Acting human or agent id. Defaults to the workspace admin.",
    )
    connect.add_argument("--json", action="store_true", help="Emit JSON.")

    issues = nested.add_parser(
        "issues",
        help="List open Linear issues for one team with local link state.",
    )
    issues.add_argument("--team", default="", help="Linear team key, e.g. ENG.")
    issues.add_argument("--limit", type=int, default=25, help="Maximum issues to list.")
    issues.add_argument("--json", action="store_true", help="Emit JSON.")

    sync = nested.add_parser(
        "sync",
        help="Pull one Linear issue and refresh linked local records.",
    )
    sync.add_argument("issue_key")
    sync.add_argument("--json", action="store_true", help="Emit JSON.")

    push = nested.add_parser(
        "push",
        help="Plan a checked Linear issue creation for a local task.",
    )
    push.add_argument("work_id")
    push.add_argument("--as", dest="actor", required=True, help="Acting agent or human id.")
    push.add_argument(
        "--team",
        default="",
        help="Linear team key. Defaults to the only visible team at send time.",
    )
    push.add_argument("--record", action="store_true", help="Record the approval plan.")
    push.add_argument("--json", action="store_true", help="Emit JSON.")

    linked = nested.add_parser(
        "linked",
        help="List all Palari proposals and tasks linked to Linear.",
    )
    linked.add_argument("--json", action="store_true", help="Emit JSON.")

    issue = nested.add_parser("issue", help="Fetch and normalize one Linear issue.")
    issue.add_argument("issue_key")
    issue.add_argument("--json", action="store_true", help="Emit JSON.")

    import_parser = nested.add_parser(
        "import",
        help="Create or update a Palari proposal linked to a Linear issue.",
    )
    import_parser.add_argument("issue_key")
    import_parser.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    import_parser.add_argument("--goal", dest="goal_id", default="", help="Fallback goal id.")
    import_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    start = nested.add_parser(
        "start",
        help="Start a Palari task linked to a Linear issue.",
    )
    start.add_argument("issue_key")
    start.add_argument(
        "--runner",
        choices=["codex", "claude-code"],
        default="codex",
        help="Runner label for task briefs. Palari does not launch the runner.",
    )
    start.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    start.add_argument("--mode", default="execute", help="Session mode.")
    start.add_argument("--adopt-by", dest="adopt_by", default="", help="Adopting human id.")
    start.add_argument("--goal", dest="goal_id", default="", help="Fallback goal id.")
    start.add_argument(
        "--lease-minutes",
        type=int,
        default=30,
        help="Task-lock length when work starts.",
    )
    start.add_argument("--json", action="store_true", help="Emit JSON.")

    status = nested.add_parser(
        "status",
        help="Map Palari task checks to a Linear-facing status.",
    )
    status.add_argument("issue_key")
    status.add_argument("--json", action="store_true", help="Emit JSON.")

    block_template = nested.add_parser(
        "block-template",
        help="Generate and validate a fenced Palari task block for Linear.",
    )
    block_template.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    block_template.add_argument("--goal", dest="goal_id", required=True, help="Goal id.")
    block_template.add_argument("--risk", required=True, help="Risk level, such as R1.")
    block_template.add_argument("--intensity", required=True, help="Operating intensity.")
    block_template.add_argument(
        "--scope",
        required=True,
        help="Task-limits text stored in the scope field.",
    )
    block_template.add_argument(
        "--acceptance-target",
        dest="acceptance_target",
        required=True,
        help="Completion target text.",
    )
    block_template.add_argument(
        "--parallel-policy",
        default="independent",
        choices=["independent", "coordinate", "exclusive"],
        help="Parallel work policy.",
    )
    block_template.add_argument(
        "--allowed-resource",
        dest="allowed_resources",
        action="append",
        default=[],
        help="Allowed file/resource path. Repeatable.",
    )
    block_template.add_argument(
        "--allowed-source",
        dest="allowed_sources",
        action="append",
        default=[],
        help="Allowed source id. Repeatable.",
    )
    block_template.add_argument(
        "--allowed-action",
        dest="allowed_actions",
        action="append",
        default=[],
        help="Allowed action. Repeatable.",
    )
    block_template.add_argument(
        "--output-target",
        dest="output_targets",
        action="append",
        default=[],
        help="Output target path. Repeatable.",
    )
    block_template.add_argument(
        "--forbidden-action",
        dest="forbidden_actions",
        action="append",
        default=[],
        help="Forbidden action. Repeatable.",
    )
    block_template.add_argument(
        "--verification",
        dest="verification_expectations",
        action="append",
        default=[],
        help="Expected verification command. Repeatable.",
    )
    block_template.add_argument(
        "--playbook",
        dest="recommended_playbooks",
        action="append",
        default=[],
        help="Recommended playbook id. Repeatable.",
    )
    block_template.add_argument(
        "--conflict-target",
        dest="conflict_targets",
        action="append",
        default=[],
        help="Conflicting task id. Repeatable.",
    )
    block_template.add_argument("--json", action="store_true", help="Emit JSON.")

    inspect_block = nested.add_parser(
        "inspect-block",
        help="Fetch a Linear issue and validate its fenced palari block.",
    )
    inspect_block.add_argument("issue_key")
    inspect_block.add_argument("--as", dest="palari_id", required=True, help="Acting agent id.")
    inspect_block.add_argument("--json", action="store_true", help="Emit JSON.")

    webhook = nested.add_parser(
        "webhook",
        help="Receive, verify, and inspect Linear webhook events.",
    )
    webhook_nested = webhook.add_subparsers(dest="webhook_command", required=True)
    webhook_serve = webhook_nested.add_parser(
        "serve",
        help="Run a local Linear webhook receiver for private dogfooding.",
    )
    webhook_serve.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    webhook_serve.add_argument("--port", type=int, default=0, help="Port to bind.")
    webhook_serve.add_argument("--json", action="store_true", help="Emit startup JSON.")

    webhook_verify = webhook_nested.add_parser(
        "verify",
        help="Verify a captured Linear webhook payload without mutating the workspace.",
    )
    webhook_verify.add_argument("--payload-file", required=True, help="Raw payload file.")
    webhook_verify.add_argument("--signature", required=True, help="Linear-Signature header.")
    webhook_verify.add_argument("--timestamp", required=True, help="Linear-Timestamp header.")
    webhook_verify.add_argument("--json", action="store_true", help="Emit JSON.")

    webhook_events = webhook_nested.add_parser(
        "events",
        help="List locally recorded Linear webhook events.",
    )
    webhook_events.add_argument("--limit", type=int, default=20, help="Number of events to show.")
    webhook_events.add_argument("--json", action="store_true", help="Emit JSON.")

    post_gate = nested.add_parser(
        "post-gate",
        help="Preview or record a Linear status comment plan.",
    )
    post_gate.add_argument("issue_key")
    post_gate.add_argument("--record", action="store_true", help="Record the approval plan.")
    post_gate.add_argument(
        "--event",
        required=True,
        choices=["work_blocked", "review_requested", "work_completed"],
        help="Palari event to post back to Linear.",
    )
    post_gate.add_argument("--actor", required=True, help="Acting agent or human id.")
    post_gate.add_argument(
        "--action",
        default="comment",
        choices=["comment", "update-issue"],
        help="Provider action to plan: comment (default) or update-issue.",
    )
    post_gate.add_argument(
        "--to-state",
        dest="to_state",
        default="",
        help="Explicit Linear workflow state name for update-issue plans.",
    )
    post_gate.add_argument("--json", action="store_true", help="Emit JSON.")

    send = nested.add_parser(
        "send",
        help="Send an approved queued Linear comment outbox item.",
    )
    send.add_argument("outbox_id")
    send.add_argument("--by", dest="human_id", required=True, help="Sending human id.")
    send.add_argument("--confirm", action="store_true", help="Confirm the live Linear write.")
    send.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_work_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("work", help="Add a bounded task.")
    nested = parser.add_subparsers(dest="object_command", required=True, metavar="ACTION")
    add = nested.add_parser(
        "add",
        help="Add one bounded task, or add an idea that needs human approval.",
    )
    add.add_argument("title")
    add.add_argument(
        "--idea",
        action="store_true",
        help="Store an authority-free idea instead of creating a task.",
    )
    for intent in ("create", "modify", "delete"):
        add.add_argument(
            f"--{intent}",
            action="append",
            default=[],
            help=f"Exact path that this task must {intent} (repeatable).",
        )
    add.add_argument(
        "--read",
        action="append",
        default=[],
        help="Additional read path (repeatable).",
    )
    add.add_argument(
        "--as",
        dest="palari_id",
        default="",
        help=("Acting agent id. Defaults to the project's sole execute-authorized agent."),
    )
    add.add_argument("--goal", default="", help="Goal id. Defaults to the only goal.")
    add.add_argument(
        "--workbench",
        default="",
        help="Project id. Defaults to the only project.",
    )
    add.add_argument("--risk", default="R1", help="Risk level.")
    add.add_argument("--intensity", default="light", help="Operating intensity.")
    add.add_argument("--scope", default="", help="One-sentence task limits.")
    add.add_argument("--acceptance", default="", help="Completion target.")
    add.add_argument(
        "--verify",
        action="append",
        default=[],
        help="Verification expectation (repeatable).",
    )
    add.add_argument(
        "--id",
        dest="work_id",
        default="",
        help="Explicit task or idea id. Defaults to a collision-resistant opaque id.",
    )
    add.add_argument(
        "--depends-on",
        dest="dependencies",
        action="append",
        default=[],
        metavar="WORK-ID",
        help="Prerequisite task id (repeatable).",
    )
    add.add_argument(
        "--parallel-policy",
        choices=("independent", "coordinate", "exclusive"),
        default="independent",
        help="Coordination policy for overlapping active tasks.",
    )
    add.add_argument("--approvals", type=int, default=0, help="Required approval count.")
    add.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_reviewer_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("reviewer", help="Add a review-only agent.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    add = nested.add_parser("add", help="Add an independent reviewer for one goal.")
    add.add_argument("id", help="Reviewer agent id.")
    add.add_argument("--name", default="Independent Reviewer", help="Reviewer name.")
    add.add_argument("--goal", required=True, help="Goal the reviewer may inspect.")
    add.add_argument("--owner", required=True, help="Responsible human id.")
    add.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_decision_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("decision", help="Inspect a required human decision.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    guide = nested.add_parser("guide", help="Build a read-only decision guide.")
    guide.add_argument("target_id", help="Decision id, or a task id linked to a decision.")
    guide.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_review_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("review", help="Guide or record independent review.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    guide = nested.add_parser("guide", help="Build a read-only review guide for one task.")
    guide.add_argument("work_id")
    guide.add_argument("--json", action="store_true", help="Emit JSON.")
    record = nested.add_parser("record", help="Record a review result.")
    record.add_argument("id")
    record.add_argument("--work-item-id", required=True, help="Task id.")
    record.add_argument("--reviewed-head", required=True, help="Reviewed head.")
    record.add_argument("--reviewer", required=True, help="Reviewer id or role.")
    record.add_argument(
        "--binding-digest",
        dest="review_binding_digest",
        default="",
        help="Machine-supplied digest from one exact Review Guide action.",
    )
    record.add_argument(
        "--verdict",
        required=True,
        choices=["accept-ready", "changes-requested", "needs-human-decision", "blocked"],
    )
    record.add_argument("--timestamp", default="", help="Timestamp.")
    record.add_argument("--json", action="store_true", help="Emit JSON.")


def _add_human_decision_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("human-decision", help="Apply an exact Approval Pack.")
    nested = parser.add_subparsers(dest="object_command", required=True)
    pack = nested.add_parser(
        "pack",
        help="Record one attributable human action over an exact Approval Pack.",
    )
    pack.add_argument("--pack-digest", required=True, help="Exact canonical pack digest.")
    pack.add_argument(
        "--presentation-digest",
        required=True,
        help="Exact canonical decision-presentation digest shown by the Approval Inbox.",
    )
    pack.add_argument("--human-id", required=True, help="Human recording the decision.")
    pack.add_argument(
        "--approve-eligible",
        action="store_true",
        help="Approve every currently eligible member in the exact pack.",
    )
    pack.add_argument("--approve", action="append", default=[], metavar="WORK-ID")
    pack.add_argument("--reject", action="append", default=[], metavar="WORK-ID")
    pack.add_argument("--defer", action="append", default=[], metavar="WORK-ID")
    pack.add_argument(
        "--pack-member",
        action="append",
        default=[],
        metavar="WORK-ID",
        help="Reproduce a narrowed pack selection. Repeat for every selected member.",
    )
    pack.add_argument("--reason", default="", help="Human rationale retained in the journal.")
    pack.add_argument("--json", action="store_true", help="Emit JSON.")
