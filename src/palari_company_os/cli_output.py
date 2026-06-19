from __future__ import annotations

import json
from typing import Any

from .cli_dispatch import CommandResult
from .models import to_plain
from .workspace import Workspace


def print_result(result: CommandResult) -> None:
    if result.kind == "queue":
        workspace = result.payload["workspace"]
        items = result.payload["items"]
        if result.as_json:
            print_json({"workspace": workspace.name, "queue": to_plain(items)})
        else:
            print_queue(workspace, items)
        return

    if result.kind == "state":
        if result.as_json:
            print_json(result.payload)
        else:
            print_state(result.payload)
        return

    if result.kind == "validate":
        if result.as_json:
            print_json(result.payload)
        else:
            print_validate(result.payload)
        return

    if result.kind == "detail":
        if result.as_json:
            print_json(result.payload)
        else:
            print_detail(result.payload)
        return

    if result.kind == "scope":
        if result.as_json:
            print_json(result.payload)
        else:
            print_scope(result.payload)
        return

    if result.kind == "migration":
        if result.as_json:
            print_json(result.payload)
        else:
            print_migration(result.payload)
        return

    if result.kind == "history":
        if result.as_json:
            print_json(result.payload)
        else:
            print_history(result.payload)
        return

    if result.kind == "mutation":
        print_mutation(result.payload, result.as_json)
        return

    if result.kind == "maintainer-status":
        if result.as_json:
            print_json(result.payload)
        else:
            print_maintainer_status(result.payload)
        return

    raise ValueError(f"unknown command result kind: {result.kind}")


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def print_validate(payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    print(f"Workspace valid: {payload['workspace']}")
    print(
        f"Records: {counts['goals']} goals, {counts['palaris']} Palaris, "
        f"{counts['humans']} humans, {counts['work_items']} work items"
    )


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


def print_history(payload: dict[str, Any]) -> None:
    print(f"Workspace history: {payload['workspace_file']}")
    print(f"History file: {payload['history_file']}")
    events = payload["events"]
    if not events:
        print("No history events recorded.")
        return
    for event in events:
        print(
            f"{event['timestamp']} {event['action']} "
            f"{event['object_type']}/{event['object_id']} by {event['actor']}"
        )
        print(f"  command: {event['command']}")
        changed_fields = event.get("changed_fields") or {}
        if changed_fields:
            print(f"  changed: {', '.join(sorted(changed_fields))}")


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
        print(
            f"  safety: ai_safe={_yes_no(item.ai_safe_to_proceed)} "
            f"human_wait={_yes_no(item.waiting_on_human)}"
        )
        print(
            f"  evidence: {item.evidence_state} | review: {item.review_state} "
            f"| approval: {item.approval_progress}"
        )
        print(f"  integration: {item.integration_state}")
        if item.learning_signal:
            print(f"  learning: {item.learning_signal}")
        if item.intensity != item.recommended_intensity:
            print(
                f"  recommended intensity: {item.recommended_intensity} "
                f"({item.intensity_reason})"
            )
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


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
