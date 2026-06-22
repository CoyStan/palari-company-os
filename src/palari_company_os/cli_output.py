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

    if result.kind == "integration-outbox-cancel":
        print_integration_outbox_cancel(result.payload, result.as_json)
        return

    if result.kind == "agent-brief":
        print_agent_brief(result.payload, result.as_json)
        return

    if result.kind == "agent-next":
        print_agent_next(result.payload, result.as_json)
        return

    if result.kind == "agent-next-all":
        print_agent_next_all(result.payload, result.as_json)
        return

    if result.kind == "agent-check":
        print_agent_check(result.payload, result.as_json)
        return

    if result.kind == "agent-finish":
        print_agent_finish(result.payload, result.as_json)
        return

    if result.kind == "agent-handoff":
        print_agent_handoff(result.payload, result.as_json)
        return

    if result.kind == "review-guide":
        print_review_guide(result.payload, result.as_json)
        return

    if result.kind == "decision-guide":
        print_decision_guide(result.payload, result.as_json)
        return

    if result.kind == "workspace-init":
        print_workspace_init(result.payload, result.as_json)
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


def print_workspace_init(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Workspace initialized: {payload['workspace']}")
    print(f"File: {payload['workspace_file']}")
    print("Next commands:")
    for command in payload["next_commands"]:
        print(f"  {command}")


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


def print_integration_outbox_cancel(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    item = payload["integration_outbox_item"]
    human = payload["human"]
    print(f"Integration outbox canceled: {item['id']}")
    print(f"Plan: {item['plan_id']} | Work: {item['work_item_id']}")
    print(f"By: {human['id']} ({human['name']})")
    print(f"Reason: {item['cancel_reason']}")
    print(f"Provider call: {_yes_no(payload['would_call_provider'])}")
    print(f"Next: {payload['next_action']}")


def print_agent_brief(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    agent = payload["agent"]
    print(f"Agent packet: {payload['packet_id']}")
    print(f"Status: {payload['status']}")
    print(f"Mode: {payload['mode']}")
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Work: {work.get('id', '')} {work.get('title', '')}")
    print(f"Instruction: {payload.get('one_sentence_instruction', '')}")
    blockers = payload.get("blockers", [])
    if blockers:
        print("Blockers:")
        for blocker in blockers:
            print(f"  - {blocker['code']}: {blocker['message']}")
    commands = payload.get("next_allowed_commands", [])
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_agent_next(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    agent = payload["agent"]
    print(f"Agent next: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Status: {payload['status']}")
    print(f"Ready: {payload['ready_count']} | Blocked/waiting: {payload['blocked_count']}")
    blockers = payload.get("blockers", [])
    if blockers:
        print("Blockers:")
        for blocker in blockers:
            print(f"  - {blocker['code']}: {blocker['message']}")
    candidates = payload.get("candidates", [])
    if candidates:
        print("Candidates:")
        for candidate in candidates:
            marker = "ready" if candidate["can_start"] else "waiting"
            print(
                f"  - {candidate['work_item_id']} [{marker}] "
                f"{candidate['title']} ({candidate['attention']})"
            )
            print(f"    next: {candidate['next_command']}")
            if candidate.get("next_step_type"):
                print(f"    step: {candidate['next_step_type']}")
            if candidate.get("blocker_codes"):
                print(f"    blockers: {', '.join(candidate['blocker_codes'])}")
            if candidate.get("start_blocker_codes"):
                print(f"    start blockers: {', '.join(candidate['start_blocker_codes'])}")
            if candidate.get("handoff_guidance"):
                for item in candidate["handoff_guidance"]:
                    print(f"    handoff: {item['code']} - {item['message']}")
                    if item.get("command"):
                        print(f"      command: {item['command']}")
    commands = payload.get("next_allowed_commands", [])
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_agent_next_all(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Agent next rollup: {payload['workspace']}")
    print(f"Status: {payload['status']}")
    print(f"Ready: {payload['ready_count']} | Blocked/waiting: {payload['blocked_count']}")
    top = payload.get("top_candidate")
    if top:
        agent = top.get("agent", {})
        candidate = top.get("candidate", {})
        marker = "ready" if candidate.get("can_start") else "waiting"
        print(
            f"Top: {candidate.get('work_item_id', '')} [{marker}] "
            f"via {agent.get('id', '')} - {candidate.get('title', '')}"
        )
        print(f"  next: {candidate.get('next_command', '')}")
        if candidate.get("next_step_type"):
            print(f"  step: {candidate.get('next_step_type', '')}")
    for agent_payload in payload.get("agents", []):
        agent = agent_payload["agent"]
        print(
            f"  - {agent.get('id', '')} ({agent.get('name', 'unknown')}): "
            f"{agent_payload['ready_count']} ready / {agent_payload['blocked_count']} waiting"
        )
        candidates = agent_payload.get("candidates", [])
        if candidates:
            first = candidates[0]
            print(f"    next: {first['next_command']}")
            if first.get("next_step_type"):
                print(f"    step: {first['next_step_type']}")
    commands = payload.get("next_allowed_commands", [])
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_agent_check(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    agent = payload["agent"]
    print(f"Agent check: {payload['check_id']}")
    print(f"OK: {_yes_no(payload['ok'])}")
    print(f"Packet: {payload['packet_id']} ({payload['packet_status']})")
    print(f"Step: {payload.get('next_step_type', 'inspect')}")
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Work: {work.get('id', '')} {work.get('title', '')}")
    blockers = payload.get("blockers", [])
    if blockers:
        print("Packet blockers:")
        for blocker in blockers:
            print(f"  - {blocker['code']}: {blocker['message']}")
    print("Checks:")
    for check in payload.get("checks", []):
        marker = check["status"]
        required = "required" if check.get("required") else "optional"
        print(f"  - {check['code']} [{marker}, {required}]: {check['message']}")
        if check.get("next_command"):
            print(f"    next: {check['next_command']}")
    commands = payload.get("next_allowed_commands", [])
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_agent_finish(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    agent = payload["agent"]
    print(f"Agent finish: {payload['finish_id']}")
    print(f"Status: {payload['status']}")
    print(f"Can finish: {_yes_no(payload['can_finish'])}")
    print(f"Handoff ready: {_yes_no(payload['handoff_ready'])}")
    print(f"Step: {payload.get('next_step_type', 'inspect')}")
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Work: {work.get('id', '')} {work.get('title', '')}")
    if payload.get("missing_requirements"):
        print("Missing requirements:")
        for item in payload["missing_requirements"]:
            print(f"  - {item['code']}: {item['message']}")
            if item.get("next_command"):
                print(f"    next: {item['next_command']}")
    if payload.get("completed_requirements"):
        print("Completed requirements:")
        for item in payload["completed_requirements"]:
            print(f"  - {item['code']}: {item['message']}")
    if payload.get("blockers"):
        print("Blockers:")
        for blocker in payload["blockers"]:
            print(f"  - {blocker['code']}: {blocker['message']}")
    if payload.get("handoff_guidance"):
        print("Handoff guidance:")
        for item in payload["handoff_guidance"]:
            print(f"  - {item['code']}: {item['message']}")
            if item.get("command"):
                print(f"    command: {item['command']}")
    print(f"Guidance: {payload['report_guidance']}")
    commands = payload.get("next_allowed_commands", [])
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_agent_handoff(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    agent = payload["agent"]
    print(f"Agent handoff: {payload['handoff_id']}")
    print(f"Status: {payload['status']} | Handoff: {_yes_no(payload['handoff_available'])}")
    print(f"Step: {payload.get('next_step_type', 'inspect')}")
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Work: {work.get('id', '')} {work.get('title', '')}")
    finish = payload["finish"]
    print(f"Finish guidance: {finish['report_guidance']}")
    if finish.get("handoff_guidance"):
        print("Handoff guidance:")
        for item in finish["handoff_guidance"]:
            print(f"  - {item['code']}: {item['message']}")
            if item.get("command"):
                print(f"    command: {item['command']}")
    review = payload.get("review_handoff")
    if review:
        print("Review handoff:")
        print(f"  status: {review['status']}")
        print(f"  command: {review['command']}")
        candidates = review.get("reviewer_candidates", [])
        if candidates:
            print("  reviewer candidates:")
            for candidate in candidates:
                print(f"    - {candidate['id']} ({candidate['name']})")
        record_commands = review.get("review_record_commands", [])
        if record_commands:
            print("  review record commands:")
            for item in record_commands:
                print(f"    - {item['reviewer']}: {item['command']}")
    decision = payload.get("decision_handoff")
    if decision:
        print("Decision handoff:")
        print(f"  status: {decision['status']}")
        print(f"  command: {decision['command']}")
        print(f"  decision: {decision['decision']['id']} {decision['decision']['question']}")
        commands_for_results = decision.get("decision_update_commands", [])
        if commands_for_results:
            print("  suggested update commands:")
            for item in commands_for_results:
                print(f"    - {item['result']}: {item['command']}")
    commands = payload.get("next_allowed_commands", [])
    if commands:
        print("Next agent-safe commands:")
        for command in commands:
            print(f"  {command}")
    human_commands = payload.get("human_action_commands", [])
    if human_commands:
        print("Human action commands:")
        for item in human_commands:
            detail = f" ({item.get('result', item.get('actor', ''))})"
            print(f"  - {item['type']}{detail}: {item['command']}")


def print_review_guide(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    evidence = payload["evidence"]
    attempt = payload["attempt"]
    receipt = payload["receipt"]
    print(f"Review guide: {payload['guide_id']}")
    print(f"Status: {payload['status']} | Would mutate: {_yes_no(payload['would_mutate'])}")
    print(f"Work: {work['id']} {work['title']} ({work['risk']})")
    print(f"Attention: {payload['attention']}")
    print(f"Why: {payload['why']}")
    print(f"Evidence: {_present_label(evidence)}")
    if evidence.get("present"):
        print(f"  head: {evidence.get('head_sha', '')} | status: {evidence.get('status', '')}")
    print(f"Attempt: {_present_label(attempt)}")
    if attempt.get("present") and attempt.get("changed_files"):
        print("  changed:")
        for path in attempt["changed_files"]:
            print(f"    - {path}")
    print(f"Receipt: {_present_label(receipt)}")
    if receipt.get("present") and receipt.get("not_done"):
        print("  not done:")
        for item in receipt["not_done"]:
            print(f"    - {item}")
    print("Review focus:")
    for item in payload["review_focus"]:
        print(f"  - {item}")
    candidates = payload.get("reviewer_candidates", [])
    if candidates:
        print("Reviewer candidates:")
        for candidate in candidates:
            print(f"  - {candidate['id']} ({candidate['name']}): {candidate['reason']}")
            if candidate.get("review_record_command"):
                print(f"    record: {candidate['review_record_command']}")
    print("Suggested verdicts:")
    print(f"  {', '.join(payload['suggested_verdicts'])}")
    print("Record template:")
    print(f"  {payload['review_record_command_template']}")
    commands = payload.get("next_commands", [])
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_decision_guide(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    decision = payload["decision"]
    linked_work = payload["linked_work"]
    print(f"Decision guide: {payload['guide_id']}")
    print(f"Status: {payload['status']} | Would mutate: {_yes_no(payload['would_mutate'])}")
    print(f"Decision: {decision['id']} {decision['question']}")
    if linked_work:
        print(f"Linked work: {linked_work['id']} {linked_work['title']} ({linked_work['risk']})")
    if decision.get("safe_default"):
        print(f"Safe default: {decision['safe_default']}")
    if decision.get("recommendation"):
        print(f"Recommendation: {decision['recommendation']}")
    if decision.get("options"):
        print("Options:")
        for option in decision["options"]:
            print(f"  - {option}")
    if decision.get("tradeoffs"):
        print("Tradeoffs:")
        for tradeoff in decision["tradeoffs"]:
            print(f"  - {tradeoff}")
    print("Decision focus:")
    for item in payload["decision_focus"]:
        print(f"  - {item}")
    print("Suggested results:")
    print(f"  {', '.join(payload['suggested_results'])}")
    commands_for_results = payload.get("decision_update_commands", [])
    if commands_for_results:
        print("Suggested update commands:")
        for item in commands_for_results:
            print(f"  - {item['result']}: {item['command']}")
    print("Update template:")
    print(f"  {payload['decision_update_command_template']}")
    commands = payload.get("next_commands", [])
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


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
        print(f"  step: {item.next_step_type}")
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
        if item.next_commands:
            print(f"  command: {item.next_commands[0]}")
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
    print(f"Step: {payload['next_step_type']}")
    print(f"Next: {payload['next_action']}")
    if payload.get("next_commands"):
        print("Next commands:")
        for command in payload["next_commands"]:
            print(f"  {command}")
    print(f"Safety: {payload['safety']}")
    if payload.get("agent_commands"):
        print("Agent commands:")
        for label, command in payload["agent_commands"].items():
            print(f"  {label}: {command}")
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
    top = payload.get("top_attention")
    if top:
        print("Top attention")
        print(f"  {top['id']}: {top['title']} ({top['attention']})")
        if top.get("next_step_type"):
            print(f"  step: {top['next_step_type']}")
        print(f"  why: {top['why']}")
        commands = top.get("next_commands") or []
        if commands:
            print(f"  command: {commands[0]}")
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


def _present_label(record: dict[str, Any]) -> str:
    if not record.get("present"):
        return "missing"
    identifier = record.get("id", "present")
    return str(identifier)
