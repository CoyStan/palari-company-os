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

    if result.kind == "dashboard":
        print_dashboard(result.payload, result.as_json)
        return

    if result.kind == "desktop-prototype":
        print_desktop_prototype(result.payload, result.as_json)
        return

    if result.kind == "desktop-serve":
        print_desktop_serve(result.payload)
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

    if result.kind == "kilo":
        print_kilo(result.payload, result.as_json)
        return

    if result.kind == "playbooks":
        print_playbooks(result.payload, result.as_json)
        return

    if result.kind == "playbook-recommendations":
        print_playbook_recommendations(result.payload, result.as_json)
        return

    raise ValueError(f"unknown command result kind: {result.kind}")


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def print_validate(payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    print(f"Workspace valid: {payload['workspace']}")
    print(
        f"Records: {counts['goals']} goals, {counts['palaris']} Palaris, "
        f"{counts['humans']} humans, {counts.get('sources', 0)} sources, "
        f"{counts.get('playbook_sources', 0)} playbook sources, "
        f"{counts['work_items']} work items, {counts.get('receipts', 0)} receipts"
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


def print_dashboard(result: Any, as_json: bool) -> None:
    payload = {
        "workspace": result.workspace,
        "output_dir": result.output_dir,
        "index_path": result.index_path,
        "assets": result.assets,
    }
    if as_json:
        print_json(payload)
        return
    print(f"Dashboard generated: {result.index_path}")
    print(f"Workspace: {result.workspace}")
    for asset in result.assets:
        print(f"Asset: {asset}")


def print_desktop_prototype(result: Any, as_json: bool) -> None:
    payload = {
        "title": result.title,
        "output_dir": result.output_dir,
        "index_path": result.index_path,
        "assets": result.assets,
    }
    if as_json:
        print_json(payload)
        return
    print(f"Desktop prototype generated: {result.index_path}")
    print(f"Title: {result.title}")
    for asset in result.assets:
        print(f"Asset: {asset}")


def print_desktop_serve(payload: dict[str, Any]) -> None:
    print(f"Desktop server stopped: {payload['url']}")
    print(f"Prototype files: {payload['output_dir']}")
    print(f"Kilo execute enabled: {_yes_no(payload['kilo_execute_enabled'])}")


def print_kilo(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    if "work_id" not in payload:
        print("Kilo Code")
        print(f"Available: {_yes_no(payload['available'])}")
        print(f"Source: {payload['source']}")
        if payload.get("command"):
            print(f"Command: {_shell_join(payload['command'])}")
        if payload.get("version"):
            print(f"Version: {payload['version']}")
        if payload.get("note"):
            print(f"Note: {payload['note']}")
        return

    mode = "executed" if payload["execute"] else "preview"
    print(f"Kilo {mode}: {payload['work_id']}")
    print(f"Workspace: {payload['workspace']}")
    print(f"Available: {_yes_no(payload['available'])} ({payload['command_source']})")
    print(f"CWD: {payload['cwd']}")
    print("Command:")
    print(f"  {_shell_join(payload['command'])}")
    print("")
    print("Prompt:")
    print(payload["prompt"])
    if not payload["execute"]:
        print("")
        print("Not executed. Add --execute to call Kilo Code.")
    if "returncode" in payload:
        print("")
        print(f"Return code: {payload['returncode']}")
        if payload.get("stdout"):
            print("stdout:")
            print(payload["stdout"].rstrip())
        if payload.get("stderr"):
            print("stderr:")
            print(payload["stderr"].rstrip())


def print_playbooks(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Playbook sources: {payload['workspace']}")
    if not payload["sources"]:
        print("No playbook sources configured.")
        return
    for source in payload["sources"]:
        enabled = "enabled" if source.get("enabled", True) else "disabled"
        print(f"{source['id']}: {source['label']} [{enabled}]")
        print(f"  uri: {source.get('uri', '')}")
        if source.get("ref"):
            print(f"  ref: {source['ref']}")
        if source.get("license"):
            print(f"  license: {source['license']}")
    if payload["playbooks"]:
        print("")
        if payload.get("core_defaults"):
            print("Core default playbooks")
            for playbook in payload["core_defaults"]:
                print(f"  {playbook['id']}: {playbook['label']}")
            print("")
        print("Available playbooks")
        for playbook in payload["playbooks"]:
            marker = " [core default]" if playbook.get("core_default") else ""
            print(f"  {playbook['id']}: {playbook['label']}{marker}")
            if playbook.get("description"):
                print(f"    {playbook['description']}")
            if playbook.get("uri"):
                print(f"    {playbook['uri']}")


def print_playbook_recommendations(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Playbook recommendations for {payload['work_item']}: {payload['title']}")
    if not payload["recommended"]:
        print("No playbook recommendations.")
        print(f"Next: {payload['next_action']}")
        return
    for item in payload["recommended"]:
        if item.get("selected_by_user"):
            prefix = "pinned"
        elif item.get("core_default"):
            prefix = "default"
        else:
            prefix = "suggested"
        print(f"{item['id']} [{prefix}]")
        print(f"  {item['reason']}")
    if payload.get("operating_guidance"):
        print("")
        print("Operating guidance")
        print("Use this as guidance; the work item's scope and authority remain the source of truth.")
        for item in payload["operating_guidance"]:
            print(f"- {item['label']}: {item['guidance']}")
    print(f"Next: {payload['next_action']}")


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
            f"| receipt: {item.receipt_state} | approval: {item.approval_progress}"
        )
        print(f"  integration: {item.integration_state}")
        if item.learning_signal:
            print(f"  learning: {item.learning_signal}")
        if item.playbook_recommendations:
            print(f"  playbooks: {', '.join(item.playbook_recommendations)}")
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
    if work.get("allowed_sources"):
        print(f"  sources: {', '.join(work['allowed_sources'])}")
    if work.get("allowed_actions"):
        print(f"  actions: {', '.join(work['allowed_actions'])}")
    if work.get("output_targets"):
        print(f"  outputs: {', '.join(work['output_targets'])}")
    if work["forbidden_actions"]:
        print(f"  forbidden: {', '.join(work['forbidden_actions'])}")
    if payload.get("playbooks", {}).get("recommended"):
        print("  playbooks:")
        for item in payload["playbooks"]["recommended"]:
            print(f"    {item['id']}: {item['reason']}")
    print("")
    _print_section("Attempt", payload["attempt"])
    if payload.get("sources"):
        print("Sources")
        for source in payload["sources"]:
            print(f"  {source['id']}: {source['label']} [{source.get('access_mode', '')}]")
        print("")
    _print_section("Receipt", payload.get("receipt"))
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


def _shell_join(argv: list[str]) -> str:
    return " ".join(_quote_arg(arg) for arg in argv)


def _quote_arg(arg: str) -> str:
    if not arg:
        return "''"
    safe = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-=.,/:@%"
    if all(char in safe for char in arg):
        return arg
    return "'" + arg.replace("'", "'\"'\"'") + "'"
