from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .maintainer import status as maintainer_status
from .models import to_plain
from .read_models import detail, queue_items
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

    detail_parser = subparsers.add_parser("detail", help="Show one work item.")
    detail_parser.add_argument("work_id")
    detail_parser.add_argument("--json", action="store_true", help="Emit JSON.")

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

        if args.command == "detail":
            workspace = Workspace.load(args.workspace)
            payload = detail(workspace, args.work_id)
            if args.json:
                print_json(payload)
            else:
                print_detail(payload)
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

