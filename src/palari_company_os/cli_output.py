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

    if result.kind == "integrations":
        print_integrations(result.payload, result.as_json)
        return

    if result.kind == "integration-check":
        print_integration_check(result.payload, result.as_json)
        return

    if result.kind == "integration-plan":
        print_integration_plan(result.payload, result.as_json)
        return

    if result.kind == "integration-plan-decision":
        print_integration_plan_decision(result.payload, result.as_json)
        return

    if result.kind == "integration-enqueue":
        print_integration_enqueue(result.payload, result.as_json)
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
        f"{counts.get('workbenches', 0)} workbenches, "
        f"{counts.get('playbook_sources', 0)} playbook sources, "
        f"{counts.get('integrations', 0)} integrations, "
        f"{counts.get('integration_plans', 0)} integration plans, "
        f"{counts.get('integration_outbox', 0)} outbox items, "
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


def print_integrations(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Integrations: {payload['workspace']}")
    if not payload["integrations"]:
        print("No integrations configured.")
        return
    for integration in payload["integrations"]:
        status = "enabled" if integration["enabled"] else "disabled"
        print(
            f"{integration['id']}: {integration['label']} "
            f"[{integration['provider']} / {status}]"
        )
        print(f"  mode: {integration['mode']} | risk: {integration['risk_level']}")
        print(f"  events: {', '.join(integration['allowed_events']) or 'none'}")
        print(f"  actions: {', '.join(integration['allowed_actions']) or 'none'}")


def print_integration_check(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    integration = payload["integration"]
    status = "enabled" if payload["enabled"] else "disabled"
    print(f"Integration check: {integration['id']} ({integration['provider']})")
    print(f"Status: {status} | Dry-run only: {_yes_no(payload['dry_run_only'])}")
    print(f"Plannable actions: {', '.join(payload['plannable_actions']) or 'none'}")
    if payload["blocked_actions"]:
        print(f"Blocked actions: {', '.join(payload['blocked_actions'])}")
    print("Secret: reference present" if payload["secret_ref_present"] else "Secret: none")
    for note in payload["notes"]:
        print(f"- {note}")


def print_integration_plan(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    integration = payload["integration"]
    work = payload["work_item"]
    print(f"Integration dry run: {integration['id']} -> {work['id']}")
    print(f"Event: {payload['event']} | Action: {payload['action']}")
    print(f"Provider call: {_yes_no(payload['would_call_provider'])}")
    print(f"Payload operation: {payload['payload_preview']['operation']}")
    if payload.get("recorded"):
        plan = payload.get("integration_plan") or {}
        print(f"Recorded plan: {plan.get('id', 'unknown')} ({plan.get('status', 'unknown')})")
        print("External write: planned only; no provider call was made.")
    else:
        print("Recorded plan: no (preview only)")
    print(f"Next: {payload['next_action']}")


def print_integration_plan_decision(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    plan = payload["integration_plan"]
    human = payload["human"]
    print(f"Integration plan {payload['decision']}: {plan['id']} -> {payload['status']}")
    print(f"By: {human['id']} ({human['name']})")
    print(f"Provider call: {_yes_no(payload['would_call_provider'])}")
    if plan.get("decision_reason"):
        print(f"Reason: {plan['decision_reason']}")
    print(f"Next: {payload['next_action']}")


def print_integration_enqueue(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    item = payload["integration_outbox_item"]
    human = payload["human"]
    print(f"Integration outbox queued: {item['id']}")
    print(f"Plan: {item['plan_id']} | Work: {item['work_item_id']}")
    print(f"By: {human['id']} ({human['name']})")
    print(f"Provider call: {_yes_no(payload['would_call_provider'])}")
    print(f"Next: {payload['next_action']}")


def print_queue(workspace: Workspace, items: list[Any]) -> None:
    print(f"Palari Company OS Queue: {workspace.name}")
    print("")
    for item in items:
        print(f"{item.id} [{item.intensity} / {item.risk}] {item.title}")
        print(f"  attention: {item.attention}")
        if item.workbench_label:
            print(f"  workbench: {item.workbench_label}")
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
        if item.active_attempts:
            attempts = ", ".join(attempt["attempt_id"] for attempt in item.active_attempts)
            print(f"  active attempts: {attempts}")
        for warning in item.coordination_warnings:
            print(f"  coordination: {warning}")
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
    workbench = payload.get("workbench") or {}
    print(f"{work['id']}: {work['title']}")
    print(f"Status: {work['status']} | Risk: {work['risk']} | Intensity: {work['intensity']}")
    if workbench:
        print(f"Workbench: {workbench.get('label', work['workbench_id'])}")
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
    if work.get("conflict_targets"):
        print(f"  conflict targets: {', '.join(work['conflict_targets'])}")
    if work.get("parallel_policy"):
        print(f"  parallel policy: {work['parallel_policy']}")
    if work["forbidden_actions"]:
        print(f"  forbidden: {', '.join(work['forbidden_actions'])}")
    if payload.get("playbooks", {}).get("recommended"):
        print("  playbooks:")
        for item in payload["playbooks"]["recommended"]:
            print(f"    {item['id']}: {item['reason']}")
    print("")
    if payload.get("parent_work_item"):
        parent = payload["parent_work_item"]
        print(f"Parent work item: {parent['id']} - {parent['title']}")
        print("")
    if payload.get("child_work_items"):
        print("Child Work Items")
        for child in payload["child_work_items"]:
            print(f"  {child['id']}: {child['title']} [{child['status']}]")
        print("")
    if payload.get("dependencies"):
        print("Dependencies")
        for dependency in payload["dependencies"]:
            print(f"  {dependency['id']}: {dependency['title']} [{dependency['status']}]")
        print("")
    if payload.get("active_parallel_attempts"):
        print("Active Parallel Attempts")
        for attempt in payload["active_parallel_attempts"]:
            print(
                f"  {attempt['attempt_id']}: {attempt['actor']} on "
                f"{attempt.get('branch', '') or attempt.get('workspace_path', '')}"
            )
        print("")
    if payload.get("coordination_warnings"):
        print("Coordination Warnings")
        for warning in payload["coordination_warnings"]:
            print(f"  {warning}")
        print("")
    _print_section("Attempt", payload["attempt"])
    if payload.get("sources"):
        print("Sources")
        for source in payload["sources"]:
            print(f"  {source['id']}: {source['label']} [{source.get('access_mode', '')}]")
        print("")
    if payload.get("integration_plans"):
        print("Integration Plans")
        for plan in payload["integration_plans"]:
            print(
                f"  {plan['id']} [{plan['status']}]: "
                f"{plan['integration_id']} {plan['event']} -> {plan['action']}"
            )
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
    if payload.get("active_parallel_work"):
        print("Active parallel work")
        for item in payload["active_parallel_work"]:
            print(f"  {item['work_item_id']} / {item['attempt_id']}: {item['actor']}")
    if payload.get("coordination_warnings"):
        print("Coordination warnings")
        for warning in payload["coordination_warnings"]:
            print(f"  {warning['message']}")


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
