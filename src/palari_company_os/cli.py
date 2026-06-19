from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .authoring import (
    create_human_decision,
    create_record,
    complete_work,
    parse_setters,
    update_human_decision,
    update_record,
)
from .maintainer import status as maintainer_status
from .models import to_plain
from .read_models import detail, queue_items
from .scope import check_scope
from .store import load_store, migrate_data, write_store
from .workspace import Workspace, WorkspaceError, default_workspace_path


def main(argv: list[str] | None = None) -> int:
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

    migrate_parser = subparsers.add_parser("migrate", help="Migrate a workspace to the current schema.")
    migrate_parser.add_argument("--write", action="store_true", help="Write migration result.")
    migrate_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    _add_goal_parser(subparsers)
    _add_human_parser(subparsers)
    _add_palari_parser(subparsers)
    _add_decision_parser(subparsers)
    _add_work_parser(subparsers)
    _add_attempt_parser(subparsers)
    _add_evidence_parser(subparsers)
    _add_review_parser(subparsers)
    _add_human_decision_parser(subparsers)
    _add_outcome_parser(subparsers)
    _add_lifecycle_parser(subparsers)

    maintainer_parser = subparsers.add_parser("maintainer", help="External maintainer tools.")
    maintainer_subparsers = maintainer_parser.add_subparsers(
        dest="maintainer_command", required=True
    )
    status_parser = maintainer_subparsers.add_parser("status", help="Show repo status.")
    status_parser.add_argument("--repo", default=".", help="Repo path to inspect.")
    status_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    args = parser.parse_args(argv)

    try:
        if args.command == "queue":
            workspace = Workspace.load(args.workspace)
            items = queue_items(workspace)
            if args.json:
                print_json({"workspace": workspace.name, "queue": to_plain(items)})
            else:
                print_queue(workspace, items)
            return 0

        if args.command == "state":
            workspace = Workspace.load(args.workspace)
            items = queue_items(workspace)
            payload = {
                "workspace": workspace.name,
                "counts": {
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
                },
                "attention": _attention_counts(items),
                "queue": to_plain(items),
            }
            if args.json:
                print_json(payload)
            else:
                print_state(payload)
            return 0

        if args.command == "validate":
            workspace = Workspace.load(args.workspace)
            payload = {
                "workspace": workspace.name,
                "valid": True,
                "counts": {
                    "goals": len(workspace.goals),
                    "palaris": len(workspace.palaris),
                    "humans": len(workspace.humans),
                    "work_items": len(workspace.work_items),
                },
            }
            if args.json:
                print_json(payload)
            else:
                print(f"Workspace valid: {workspace.name}")
                print(
                    f"Records: {len(workspace.goals)} goals, {len(workspace.palaris)} Palaris, "
                    f"{len(workspace.humans)} humans, {len(workspace.work_items)} work items"
                )
            return 0

        if args.command == "detail":
            workspace = Workspace.load(args.workspace)
            payload = detail(workspace, args.work_id)
            if args.json:
                print_json(payload)
            else:
                print_detail(payload)
            return 0

        if args.command == "scope":
            workspace = Workspace.load(args.workspace)
            payload = check_scope(workspace, args.work_id, args.changed, args.action)
            if args.json:
                print_json(payload.to_dict())
            else:
                print_scope(payload.to_dict())
            return 0

        if args.command == "migrate":
            store = load_store(args.workspace)
            migrated, changes = migrate_data(store.data)
            payload = {
                "workspace_file": str(store.data_path),
                "write": args.write,
                "changes": changes,
            }
            if args.write:
                store = type(store)(store.data_path, migrated)
                write_store(store)
            if args.json:
                print_json(payload)
            else:
                print_migration(payload)
            return 0

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
            result = handle_authoring(args)
            print_mutation(result, args.json)
            return 0

        if args.command == "lifecycle":
            result = handle_lifecycle(args)
            print_mutation(result, args.json)
            return 0

        if args.command == "maintainer" and args.maintainer_command == "status":
            payload = maintainer_status(Path(args.repo))
            if args.json:
                print_json(payload.to_dict())
            else:
                print_maintainer_status(payload.to_dict())
            return 0
    except (WorkspaceError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"palari: {exc}\n")

    parser.exit(2, "palari: unknown command\n")
    return 2


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def handle_authoring(args: argparse.Namespace) -> Any:
    if args.object_command in {"create", "record"}:
        record = _record_from_args(args)
        if args.command == "human-decision":
            return create_human_decision(args.workspace, record)
        return create_record(args.workspace, args.command, record)
    if args.object_command == "update":
        updates = parse_setters(args.set, args.list)
        _apply_known_args(args, updates, include_id=False)
        if args.command == "human-decision":
            return update_human_decision(args.workspace, args.id, updates)
        return update_record(args.workspace, args.command, args.id, updates)
    if args.command == "work" and args.object_command == "complete":
        return complete_work(args.workspace, args.work_id, args.status)
    raise WorkspaceError(f"unsupported authoring command: {args.command} {args.object_command}")


def handle_lifecycle(args: argparse.Namespace) -> Any:
    if args.lifecycle_command == "evidence":
        return create_record(args.workspace, "evidence", _record_from_args(args))
    if args.lifecycle_command == "review":
        return create_record(args.workspace, "review", _record_from_args(args))
    if args.lifecycle_command == "decide":
        return create_human_decision(args.workspace, _record_from_args(args))
    if args.lifecycle_command == "complete":
        return complete_work(args.workspace, args.work_id, args.status)
    if args.lifecycle_command == "outcome":
        return create_record(args.workspace, "outcome", _record_from_args(args))
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


def print_mutation(result: Any, as_json: bool) -> None:
    payload = {
        "action": result.action,
        "collection": result.collection,
        "record_id": result.record_id,
        "workspace": result.workspace,
    }
    if result.next_action:
        payload["next_action"] = result.next_action
    if as_json:
        print_json(payload)
    else:
        print(f"{result.action}: {result.collection}/{result.record_id}")
        if result.next_action:
            print(f"next: {result.next_action}")


def print_migration(payload: dict[str, Any]) -> None:
    print(f"Workspace migration: {payload['workspace_file']}")
    print(f"Write: {'yes' if payload['write'] else 'no'}")
    for change in payload["changes"]:
        print(f"  {change}")


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
    parser = subparsers.add_parser("lifecycle", help="Lifecycle aliases for evidence, review, decision, completion, and outcome.")
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


def print_queue(workspace: Workspace, items: list[Any]) -> None:
    print(f"Palari Company OS Queue: {workspace.name}")
    print("")
    for item in items:
        print(f"{item.id} [{item.intensity} / {item.risk}] {item.title}")
        print(f"  attention: {item.attention}")
        print(f"  goal: {item.goal_title}")
        print(f"  palari: {item.palari_name}")
        if item.owner:
            print(f"  owner: {item.owner}")
        print(f"  why: {item.why}")
        print(f"  safety: ai_safe={_yes_no(item.ai_safe_to_proceed)} human_wait={_yes_no(item.waiting_on_human)}")
        print(f"  evidence: {item.evidence_state} | review: {item.review_state} | approval: {item.approval_progress}")
        print(f"  integration: {item.integration_state}")
        if item.learning_signal:
            print(f"  learning: {item.learning_signal}")
        if item.intensity != item.recommended_intensity:
            print(f"  recommended intensity: {item.recommended_intensity} ({item.intensity_reason})")
        print(f"  next: {item.next_action}")
        print("")


def print_detail(payload: dict[str, Any]) -> None:
    work = payload["work_item"]
    goal = payload["goal"] or {}
    palari = payload["palari"] or {}
    print(f"{work['id']}: {work['title']}")
    print(f"Status: {work['status']} | Risk: {work['risk']} | Intensity: {work['intensity']}")
    print(f"Goal: {goal.get('title', work['goal'])}")
    print(f"Palari: {palari.get('name', work['palari'])}")
    print("")
    print(f"Attention: {payload['attention']}")
    print(f"Why: {payload['why']}")
    print(f"Next: {payload['next_action']}")
    print(f"Safety: {payload['safety']}")
    print("")
    print("Scope")
    print(f"  {work['scope']}")
    if work["allowed_resources"]:
        print(f"  allowed: {', '.join(work['allowed_resources'])}")
    if work["forbidden_actions"]:
        print(f"  forbidden: {', '.join(work['forbidden_actions'])}")
    print("")
    _print_section("Attempt", payload["attempt"])
    _print_section("Evidence", payload["evidence"])
    _print_section("Review", payload["review"])
    _print_section("Human Decision", payload["human_decision"])
    if payload["human_decisions"]:
        print("Human Decisions")
        for decision in payload["human_decisions"]:
            print(
                f"  {decision['id']} [{decision['status']}]: "
                f"{decision['human_id']} {decision['decision']}"
            )
        print("")
    if payload["linked_decisions"]:
        print("Linked Decisions")
        for decision in payload["linked_decisions"]:
            print(f"  {decision['id']} [{decision['status']}]: {decision['question']}")
        print("")
    _print_section("Outcome", payload["outcome"])


def print_maintainer_status(payload: dict[str, Any]) -> None:
    print("External Maintainer Status")
    print(f"Repo: {payload['repo']}")
    print(f"Branch: {payload['branch']}")
    print(f"Head: {payload['head']}")
    print(f"Upstream: {payload['upstream'] or '(none)'}")
    print(f"Divergence: {payload['divergence']}")
    print(f"PR readiness: {payload['pr_readiness']} - {payload['pr_readiness_reason']}")
    focused_tests = payload["focused_tests_run"]
    if focused_tests:
        print("Focused tests run:")
        for item in focused_tests:
            print(f"  {item}")
        print(f"Focused tests source: {payload['focused_tests_source']}")
    else:
        print(f"Focused tests run: unknown ({payload['focused_tests_source']})")
    dirty = payload["dirty_files"]
    if dirty:
        print("Dirty files:")
        for item in dirty:
            print(f"  {item}")
    else:
        print("Dirty files: none")


def print_state(payload: dict[str, Any]) -> None:
    print(f"Palari Company OS State: {payload['workspace']}")
    print("Counts")
    for key, value in payload["counts"].items():
        print(f"  {key}: {value}")
    print("Attention")
    for key, value in payload["attention"].items():
        print(f"  {key}: {value}")


def print_scope(payload: dict[str, Any]) -> None:
    print(f"Scope check for {payload['work_item_id']}: {'allowed' if payload['allowed'] else 'blocked'}")
    for violation in payload["violations"]:
        print(f"  violation: {violation}")
    for note in payload["notes"]:
        print(f"  note: {note}")


def _print_section(title: str, value: dict[str, Any] | None) -> None:
    if not value:
        print(f"{title}: none")
        print("")
        return
    print(title)
    for key, item in value.items():
        if isinstance(item, list):
            if item:
                print(f"  {key}: {', '.join(str(part) for part in item)}")
        elif item:
            print(f"  {key}: {item}")
    print("")


def _attention_counts(items: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.attention] = counts.get(item.attention, 0) + 1
    return counts


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
