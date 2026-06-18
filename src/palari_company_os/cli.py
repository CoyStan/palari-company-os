from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .maintainer import status as maintainer_status
from .models import to_plain
from .read_models import detail, queue_items
from .scope import check_scope
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
