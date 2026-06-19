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

    queue_parser = subparsers.add_parser("queue", help="Show work needing attention.")
    queue_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    state_parser = subparsers.add_parser("state", help="Show compact operator state.")
    state_parser.add_argument("--json", action="store_true", help="Emit JSON.")

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

    _add_goal_parser(subparsers)
    _add_human_parser(subparsers)
    _add_palari_parser(subparsers)
    _add_source_parser(subparsers)
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

    return parser


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
            ("last_seen_revision", {"default": "", "help": "Last seen revision."}),
            ("last_read_at", {"default": "", "help": "Last read timestamp."}),
        ],
    )


def _add_decision_parser(subparsers: Any) -> None:
    _add_create_update(
        subparsers,
        "decision",
        "Create or update decisions.",
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
    parser = subparsers.add_parser("review", help="Record or update review verdicts.")
    nested = parser.add_subparsers(dest="object_command", required=True)
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
