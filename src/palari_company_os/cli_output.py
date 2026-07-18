from __future__ import annotations

import json
from typing import Any

from .cli_output_agent import (
    print_agent_adopt,
    print_agent_brief,
    print_agent_check,
    print_agent_doctor,
    print_agent_advance,
    print_agent_finish,
    print_agent_handoff,
    print_agent_loop,
    print_agent_next,
    print_agent_next_all,
    print_agent_park,
    print_agent_release,
    print_agent_session_contract,
    print_agent_start,
)
from .cli_dispatch import CommandResult
from .cli_output_integrations import (
    print_integration_check,
    print_integration_enqueue,
    print_integration_outbox_cancel,
    print_integration_outbox_check,
    print_integration_plan,
    print_integration_plan_decision,
    print_integrations,
)
from .cli_output_utils import print_json, yes_no as _yes_no
from .models import to_plain
from .workspace import Workspace


INTENSITY_RANK = {"light": 0, "standard": 1, "high": 2}


def print_result(result: CommandResult) -> None:
    if result.kind == "demo":
        print_demo(result.payload, result.as_json)
        return

    if result.kind == "queue":
        workspace = result.payload["workspace"]
        items = result.payload["items"]
        if result.as_json:
            print_json({"workspace": workspace.name, "queue": to_plain(items)})
        else:
            print_queue(workspace, items)
        return

    if result.kind == "approval-inbox":
        if result.as_json:
            print_json(result.payload)
        else:
            print_approval_inbox(result.payload)
        return

    if result.kind == "approval-pack-decision":
        if result.as_json:
            print_json(result.payload)
        else:
            print_approval_pack_decision(result.payload)
        return

    if result.kind == "state":
        if result.as_json:
            print_json(result.payload)
        else:
            print_state(result.payload)
        return

    if result.kind == "data-map":
        if result.as_json:
            print_json(result.payload)
        else:
            print_data_map(result.payload)
        return

    if result.kind == "docs-check":
        print_docs_check(result.payload, result.as_json)
        return

    if result.kind == "docs-init":
        print_docs_init(result.payload, result.as_json)
        return

    if result.kind == "docs-map":
        print_docs_map(result.payload, result.as_json)
        return

    if result.kind == "proof":
        print_proof(result.payload, result.as_json)
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

    if result.kind == "integration-outbox-check":
        print_integration_outbox_check(result.payload, result.as_json)
        return

    if result.kind == "integration-outbox-cancel":
        print_integration_outbox_cancel(result.payload, result.as_json)
        return

    if result.kind == "agent-brief":
        print_agent_brief(result.payload, result.as_json)
        return

    if result.kind == "agent-adopt":
        print_agent_adopt(result.payload, result.as_json)
        return

    if result.kind == "agent-hook":
        print(json.dumps(result.payload))
        return

    if result.kind == "agent-start":
        print_agent_start(result.payload, result.as_json)
        return

    if result.kind == "agent-session-contract":
        print_agent_session_contract(result.payload, result.as_json)
        return

    if result.kind == "agent-release":
        print_agent_release(result.payload, result.as_json)
        return

    if result.kind == "agent-park":
        print_agent_park(result.payload, result.as_json)
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

    if result.kind == "agent-loop":
        print_agent_loop(result.payload, result.as_json)
        return

    if result.kind == "agent-doctor":
        print_agent_doctor(result.payload, result.as_json)
        return

    if result.kind == "agent-advance":
        print_agent_advance(result.payload, result.as_json)
        return

    if result.kind == "review-guide":
        print_review_guide(result.payload, result.as_json)
        return

    if result.kind == "decision-guide":
        print_decision_guide(result.payload, result.as_json)
        return

    if result.kind in {
        "capabilities",
        "capability-check",
        "capability-policy",
        "authority-profiles",
        "authority-check",
        "evidence-verify",
        "proposal-decision",
        "linear",
    }:
        if result.as_json:
            print_json(result.payload)
        else:
            print_governance_payload(result.payload)
        return

    if result.kind == "init":
        print_init(result.payload, result.as_json)
        return

    if result.kind == "work-add":
        print_work_add(result.payload, result.as_json)
        return

    if result.kind == "claude-hook":
        print(json.dumps(result.payload))
        return

    if result.kind == "claude-install":
        print_claude_install(result.payload, result.as_json)
        return

    if result.kind == "claude-status":
        print_claude_status(result.payload, result.as_json)
        return

    if result.kind == "git-install":
        if result.as_json:
            print_json(result.payload)
        else:
            print_git_install(result.payload)
        return

    if result.kind == "git-pre-commit":
        if result.as_json:
            print_json(result.payload)
        else:
            print_git_pre_commit(result.payload)
        return

    if result.kind == "git-status":
        if result.as_json:
            print_json(result.payload)
        else:
            print_git_status(result.payload)
        return

    if result.kind == "git-readiness":
        if result.as_json:
            print_json(result.payload)
        else:
            print_git_readiness(result.payload)
        return

    if result.kind == "mcp-server":
        return

    if result.kind == "history-journal":
        if result.as_json:
            print_json(result.payload)
        else:
            print_history_journal(result.payload)
        return

    if result.kind == "history-checkpoints":
        if result.as_json:
            print_json(result.payload)
        else:
            print_history_checkpoints(result.payload)
        return

    if result.kind == "history-restoration":
        if result.as_json:
            print_json(result.payload)
        else:
            print_history_restoration(result.payload)
        return

    if result.kind == "mission-control-serve":
        print_mission_control_serve(result.payload)
        return

    if result.kind == "demo-serve":
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

    if result.kind == "gate-profiles":
        print_gate_profiles(result.payload, result.as_json)
        return

    if result.kind == "gate-recommendations":
        print_gate_recommendations(result.payload, result.as_json)
        return

    raise ValueError(f"unknown command result kind: {result.kind}")


def print_validate(payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    print(f"Workspace valid: {payload['workspace']}")
    print(
        f"Records: {counts['goals']} goals, {counts['palaris']} Palaris, "
        f"{counts['humans']} humans, {counts.get('sources', 0)} sources, "
        f"{counts.get('workbenches', 0)} workbenches, "
        f"{counts.get('playbook_sources', 0)} playbook sources, "
        f"{counts.get('capabilities', 0)} capabilities, "
        f"{counts.get('authority_profiles', 0)} authority profiles, "
        f"{counts.get('integrations', 0)} integrations, "
        f"{counts.get('integration_plans', 0)} integration plans, "
        f"{counts.get('integration_outbox', 0)} outbox items, "
        f"{counts.get('proposals', 0)} proposals, "
        f"{counts['work_items']} work items, "
        f"{counts.get('acceptance_records', 0)} acceptance records, "
        f"{counts.get('receipts', 0)} receipts"
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


def print_governance_payload(payload: dict[str, Any]) -> None:
    schema = payload.get("schema_version", "palari.payload.v1")
    print(schema)
    if "workspace" in payload:
        print(f"Workspace: {payload['workspace']}")
    if "ok" in payload:
        print(f"OK: {_yes_no(bool(payload['ok']))}")
    if "next_action" in payload:
        print(f"Next: {payload['next_action']}")
    if "capabilities" in payload:
        print(f"Capabilities: {len(payload['capabilities'])}")
    if "allowed_capabilities" in payload:
        print(f"Allowed capabilities: {len(payload['allowed_capabilities'])}")
    if "profiles" in payload:
        print(f"Authority profiles: {len(payload['profiles'])}")
    if "blockers" in payload and payload["blockers"]:
        print("Blockers:")
        for blocker in payload["blockers"]:
            print(f"  - {blocker}")


def print_demo(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print("Palari demo: blocked file change in under two minutes")
    print(f"Demo workspace: {payload['workspace_dir']}")
    print()
    for index, step in enumerate(payload["steps"], start=1):
        print(f"== {index}. {step['title']} ==")
        if step.get("narration"):
            print(step["narration"])
        print(f"$ {step['command']}")
        stdout = step.get("display_stdout") or step.get("stdout", "")
        stdout = stdout.rstrip()
        if stdout:
            print(stdout)
        stderr = step.get("stderr", "").rstrip()
        if stderr:
            print(stderr)
        if step.get("block_marker"):
            print()
            print(step["block_marker"])
            print(f"Offending path: {step['offending_path']}")
            print(f"Allowed write paths: {', '.join(step['allowed_write_paths'])}")
        if step.get("pass_marker"):
            print()
            print(step["pass_marker"])
        if not payload["no_pause"] and index != len(payload["steps"]):
            try:
                input("\nPress Enter for the next act...")
            except EOFError:
                pass
        print()
    print("What just happened:")
    for sentence in payload["plain_summary"]:
        print(f"- {sentence}")
    print("Try next:")
    for command in payload["try_next_commands"]:
        print(f"  {command}")


def print_history_journal(payload: dict[str, Any]) -> None:
    print(f"Governance journal: {payload.get('status', 'unknown')}")
    print(f"Enabled: {_yes_no(bool(payload.get('enabled')))}")
    print(f"Verified: {_yes_no(bool(payload.get('ok')))}")
    if payload.get("journal_file"):
        print(f"Journal file: {payload['journal_file']}")
    for item in payload.get("errors", []):
        print(f"  error {item.get('code', '')}: {item.get('message', '')}")
        if item.get("next_action"):
            print(f"    next: {item['next_action']}")
    for item in payload.get("warnings", []):
        print(f"  warning {item.get('code', '')}: {item.get('message', '')}")


def print_history_checkpoints(payload: dict[str, Any]) -> None:
    print(f"Governed checkpoints: {payload['count']}")
    print(f"Current: {payload['current_checkpoint_digest']}")
    for item in payload["checkpoints"]:
        print(
            f"  {item['checkpoint_digest']} [{item['event_kind']}] "
            f"by {item['metadata']['actor']} via {item['metadata']['command']}"
        )
    print("Restoration appends history; it does not undo external effects.")


def print_history_restoration(payload: dict[str, Any]) -> None:
    print(f"Checkpoint restoration: {payload['status']}")
    print(f"Checkpoint: {payload['checkpoint_digest']}")
    print(f"Class: {payload['restoration_class']}")
    print(f"Idempotent replay: {_yes_no(bool(payload['idempotent']))}")
    if payload.get("message"):
        print(payload["message"])
    for effect in payload.get("external_effects_not_undone", []):
        print(f"  NOT UNDONE: {effect}")


def print_proof(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    action = payload.get("action", "verify")
    status = payload.get("status")
    if status is None and "verified" in payload:
        status = "verified" if payload["verified"] else "rejected"
    print(f"PCAW proof {action}: {status or 'unknown'}")
    if payload.get("proof_file"):
        print(f"Proof: {payload['proof_file']}")
    digest = payload.get("statement_digest")
    if isinstance(digest, dict):
        print(f"Statement: {digest.get('algorithm', '')}:{digest.get('value', '')}")
    elif digest:
        print(f"Statement: {digest}")
    if payload.get("claimed_state"):
        print(f"Claimed state: {payload['claimed_state']}")
    if payload.get("derived_lifecycle_state"):
        print(f"Derived state: {payload['derived_lifecycle_state']}")
    properties = payload.get("verified_properties", {})
    if properties:
        print("Verified properties:")
        if isinstance(properties, dict):
            for name, status in properties.items():
                print(f"  - {name}: {status}")
        else:
            for item in properties:
                print(f"  - {item.get('name', '')}: {item.get('status', '')}")
    for item in payload.get("errors", []):
        print(f"  error {item.get('code', '')}: {item.get('message', '')}")
        if item.get("next_action"):
            print(f"    next: {item['next_action']}")
    for item in payload.get("warnings", []):
        print(f"  warning {item.get('code', '')}: {item.get('message', '')}")
    for item in payload.get("security_limitations", []):
        print(f"  limitation: {item}")


def print_data_map(payload: dict[str, Any]) -> None:
    from .data_map import format_data_map

    for line in format_data_map(payload):
        print(line)


def print_docs_check(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    summary = payload["summary"]
    print(f"Docs check: {payload['status']} ({payload['repo']})")
    print(
        f"Checks: {summary['checks']} | warnings: {summary['warnings']} | "
        f"failures: {summary['failures']}"
    )
    for check in payload["checks"]:
        if check["status"] == "pass":
            continue
        path = f" [{check['path']}]" if check.get("path") else ""
        print(f"- {check['code']} [{check['status']}]{path}: {check['message']}")
    print(f"Next: {payload['next_action']}")


def print_docs_init(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Docs init: {payload['mode']} ({payload['repo']})")
    print(f"Would mutate: {_yes_no(payload['would_mutate'])}")
    for item in payload["files"]:
        print(f"- {item['path']} [{item['action']}]: {item['summary']}")
    if payload.get("created"):
        print(f"Created: {', '.join(payload['created'])}")
    if payload.get("overwritten"):
        print(f"Overwritten: {', '.join(payload['overwritten'])}")
    if payload.get("skipped_existing"):
        print(f"Skipped existing: {', '.join(payload['skipped_existing'])}")
    print(f"Next: {payload['next_action']}")


def print_docs_map(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    state = payload["documentation_state"]
    print(f"Docs map: {payload['repo']}")
    print(f"Documentation: {state['status']} - {state['message']}")
    print("Root entrypoints:")
    for item in payload["root_entrypoints"]:
        print(f"  - {item['path']}: {'present' if item['exists'] else 'missing'}")
    print("Canonical agent docs:")
    for item in payload["canonical_agent_docs"]:
        print(f"  - {item['path']}: {'present' if item['exists'] else 'missing'}")
    print("Major command groups:")
    print("  " + ", ".join(payload["major_command_groups"]))


def print_mission_control_serve(payload: dict[str, Any]) -> None:
    print(f"Mission Control stopped: {payload['url']}")
    print(f"Workspace file: {payload['workspace_file']}")


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


def print_gate_profiles(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Gate profiles: {payload['workspace']}")
    for profile in payload["profiles"]:
        print(f"{profile['id']}: {profile['label']}")
        print(f"  {profile['summary']}")
        print(f"  reviewer: {profile['reviewer_role']}")


def print_gate_recommendations(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    print(f"Gate recommendations for {work['id']}: {work['title']}")
    if payload["no_special_gate_required"]:
        print("No special gate required.")
        print(f"Next: {payload['next_action']}")
        return
    for gate in payload["recommended_gates"]:
        print(f"{gate['id']}: {gate['label']}")
        print(f"  reason: {gate['reason']}")
        contract = gate["review_contract"]
        print(f"  reviewer: {contract['reviewer_role']}")
        print("  blockers:")
        for item in contract["blocker_checklist"]:
            print(f"    - {item}")
        print(f"  accept-ready: {contract['accept_ready_standard']}")
    print(f"Next: {payload['next_action']}")


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
            identity_type = candidate.get("identity_type", "human")
            print(
                f"  - {candidate['id']} ({candidate['name']}, {identity_type}): "
                f"{candidate['reason']}"
            )
            if candidate.get("review_packet_command"):
                print(f"    packet: {candidate['review_packet_command']}")
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


def print_init(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Workspace created: {payload['workspace']}")
    print(f"File: {payload['workspace_file']}")
    print(
        f"Starter records: {payload['human']['id']} ({payload['human']['name']}), "
        f"{payload['palari']['id']} ({payload['palari']['name']}), "
        f"{payload['goal']}, {payload['workbench']}, {payload['source']}"
    )
    adoption = payload.get("adoption") or {}
    if adoption.get("status") != "not-requested":
        print(
            f"Host adoption: {adoption.get('host', '')} "
            f"[{adoption.get('status', 'unknown')}]"
        )
        if adoption.get("status") == "blocked":
            print(f"Why: {adoption.get('message', '')}")
        else:
            host = adoption.get("host_adapter") or {}
            if host.get("next_action"):
                print(f"Activation: {host['next_action']}")
    print("Next commands:")
    for command in payload["next_commands"]:
        print(f"  {command}")


def print_work_add(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    print(f"Work item created: {work['id']} {work['title']}")
    print(f"Palari: {work['palari']} | risk {work['risk']} | intensity {work['intensity']}")
    print("Write boundary:")
    for path in work["output_targets"]:
        print(f"  - {path}")
    reads = [path for path in work["allowed_resources"] if path not in work["output_targets"]]
    if reads:
        print("Extra read paths:")
        for path in reads:
            print(f"  - {path}")
    dependencies = work.get("dependency_ids", [])
    if dependencies:
        print("Explicit dependencies:")
        for dependency in dependencies:
            print(f"  - {dependency}")
    print("Next commands:")
    for command in payload["next_commands"]:
        print(f"  {command}")


def print_git_readiness(payload: dict[str, Any]) -> None:
    print(f"Git integration readiness: {payload['work_item']}")
    print(f"Status: {payload['status']} | ready: {_yes_no(payload['ready'])}")
    print(
        f"Candidate: {payload['candidate']['sha'] or 'missing'} | "
        f"target {payload['target']['ref']}: {payload['target']['sha']}"
    )
    print(f"Relationship: {payload['relationship']}")
    for blocker in payload.get("blockers", []):
        print(f"  - {blocker['code']}: {blocker['message']}")
        print(f"    next: {blocker['next_safe_action']}")


def print_claude_install(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Claude Code hooks: {payload['status']}")
    print(f"Settings file: {payload['settings_file']}")
    if payload.get("workspace"):
        print(f"Workspace: {payload['workspace']}")
    if payload.get("hooks"):
        print("Hooks:")
        for event, command in payload["hooks"].items():
            print(f"  {event}: {command}")
    if not payload.get("palari_on_path", True):
        print("Warning: palari is not on PATH; hooks will fail until it is installed.")
    print(payload["message"])


def print_claude_status(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Claude Code enforcement installed: {_yes_no(payload['installed'])}")
    for item in payload["settings_files"]:
        events = ", ".join(item["palari_hook_events"]) or "none"
        strict = " (strict)" if item["strict"] else ""
        print(f"  {item['path']}: {events}{strict}")
    if not payload.get("palari_on_path", True):
        print("Warning: palari is not on PATH; hooks will fail until it is installed.")
    claims = payload["active_claims"]
    if claims:
        print("Active claims:")
        for claim in claims:
            writes = ", ".join(claim["allowed_write_paths"]) or "(none)"
            print(
                f"  {claim['work_item']} by {claim['claimed_by']} "
                f"(mode {claim['mode']}, lease {claim['lease_expires_at']})"
            )
            print(f"    allowed writes: {writes}")
    else:
        print("Active claims: none")
    print(payload["message"])


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
    print("Ordinary loop: start -> advance -> review -> human decision -> verify")
    print("")
    for item in items:
        print(f"{item.id} [{item.intensity} / {item.risk}] {item.title}")
        print(f"  attention: {item.attention}")
        print(f"  step: {item.next_step_type}")
        print(f"  next: {item.next_action}")
        if item.next_commands:
            print(f"  command: {item.next_commands[0]}")
        if item.workbench_label:
            print(f"  workbench: {item.workbench_label}")
        print(f"  goal: {item.goal_title}")
        print(f"  palari: {item.palari_name}")
        if item.owner:
            print(f"  owner: {item.owner}")
        if item.external_provider and item.external_key:
            print(f"  external: {item.external_provider}:{item.external_key}")
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
            label = "intensity note"
            if INTENSITY_RANK.get(item.recommended_intensity, 0) > INTENSITY_RANK.get(
                item.intensity, 0
            ):
                label = "intensity concern"
            print(
                f"  {label}: heuristic suggests {item.recommended_intensity} "
                f"({item.intensity_reason})"
            )
        if item.agent_loop_command:
            print(f"  agent loop: {item.agent_loop_command}")
        if item.agent_handoff_command:
            print(f"  agent handoff: {item.agent_handoff_command}")
        if item.terminal_disposition:
            print(f"  retired: {item.terminal_disposition} ({item.terminal_reason})")
            if item.successor_work_item_id:
                print(f"  successor: {item.successor_work_item_id}")
        print("")


def print_approval_inbox(payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    print(f"Approval Inbox: {payload['workspace']}")
    primary = payload.get("primary_action", {})
    commands = list(primary.get("commands", []))
    if primary.get("available"):
        state = "decision-ready"
        owner = "qualified human"
        safe = "yes, for the exact eligible presentation"
        explanation = (
            f"{counts['eligible']} item(s) have current proof; "
            f"{counts['blocked'] + counts['stale'] + counts['non_batchable']} exception(s) stay parked."
        )
        next_action = commands[0] if len(commands) == 1 else "Use the exact commands in --json."
    elif not counts["items"]:
        state = "empty"
        owner = "none"
        safe = "yes"
        explanation = "No governed human decision is waiting."
        next_action = "palari agent next --json"
    else:
        resolutions = [
            item.get("resolution", {}) for item in payload.get("individual_items", [])
        ]
        owner = next(
            (str(item.get("owner")) for item in resolutions if item.get("owner") not in {None, "none"}),
            "agent or reviewer",
        )
        state = "blocked"
        safe = "no aggregate decision is available"
        explanation = str(primary.get("next_safe_action") or "Resolve the current exceptions.")
        next_action = next(
            (
                str(item.get("next_safe_action"))
                for item in payload.get("individual_items", [])
                if item.get("next_safe_action")
            ),
            "palari agent next --json",
        )
    print(f"State: {state}")
    print(f"Safe: {safe}")
    print(f"Owner: {owner}")
    print(
        f"Items: {counts['items']} in {counts['packs']} pack(s) | "
        f"eligible {counts['eligible']} | blocked {counts['blocked']} | "
        f"stale {counts['stale']} | non-batchable {counts['non_batchable']}"
    )
    print(f"Why: {explanation}")
    print(f"Next: {next_action}")
    print("Proof details: rerun with --json. Parked is not approved.")


def print_approval_pack_decision(payload: dict[str, Any]) -> None:
    print(f"Approval Pack decision: {payload['status']}")
    print(f"Pack: {payload['pack_digest']}")
    print(f"Presentation: {payload.get('presentation_digest', 'legacy-unbound')}")
    print(f"Idempotent replay: {_yes_no(bool(payload['idempotent']))}")
    if payload.get("approved"):
        print(f"Approved: {', '.join(payload['approved'])}")
    if payload.get("rejected"):
        print(f"Rejected: {', '.join(payload['rejected'])}")
    if payload.get("deferred"):
        print(f"Deferred: {', '.join(payload['deferred'])}")
    if payload.get("executed"):
        print(f"Executed locally: {', '.join(payload['executed'])}")
    if payload.get("parked"):
        print(f"Still parked: {', '.join(payload['parked'])}")
    convergence = payload.get("convergence", {})
    if convergence:
        print(
            "One-action convergence: "
            f"{len(convergence.get('terminalized', []))} terminalized; "
            f"{len(convergence.get('remaining_parked', []))} parked"
        )


def print_detail(payload: dict[str, Any]) -> None:
    work = payload["work_item"]
    goal = payload["goal"] or {}
    palari = payload["palari"] or {}
    workbench = payload.get("workbench") or {}
    print(f"{work['id']}: {work['title']}")
    print(f"Status: {work['status']} | Risk: {work['risk']} | Intensity: {work['intensity']}")
    if work.get("status") in {"superseded", "abandoned"}:
        print(
            f"Retired: {work['status']} | "
            f"Reason: {work.get('terminal_reason', '')}"
        )
        if work.get("successor_work_item_id"):
            print(f"Successor: {work['successor_work_item_id']}")
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
    if payload.get("agent_handoff_command"):
        print("Agent handoff:")
        print(f"  {payload['agent_handoff_command']}")
    approval = payload.get("approval_pack") or {}
    if approval.get("available"):
        item = approval.get("item") or {}
        print(
            f"Approval Pack: {approval.get('pack_id', '')} | "
            f"{item.get('state', 'unknown')} | {approval.get('pack_digest', '')}"
        )
    elif approval:
        print(f"Approval Pack unavailable: {approval.get('reason', 'unknown reason')}")
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
        if top.get("agent_loop_command"):
            print(f"  agent loop: {top['agent_loop_command']}")
        if top.get("agent_handoff_command"):
            print(f"  agent handoff: {top['agent_handoff_command']}")
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


def _present_label(record: dict[str, Any]) -> str:
    if not record.get("present"):
        return "missing"
    identifier = record.get("id", "present")
    return str(identifier)


def print_git_install(payload: dict[str, Any]) -> None:
    print(f"Palari git hook: {payload['status']}")
    print(f"Hook path: {payload.get('hook_path', '')}")
    print(payload.get("message", ""))


def print_git_pre_commit(payload: dict[str, Any]) -> None:
    status = payload.get("status", "")
    print(f"Palari pre-commit: {status}")
    print(payload.get("message", ""))
    if payload.get("outside"):
        print("Outside boundary:")
        for path in payload["outside"]:
            print(f"  - {path}")
    if payload.get("allowed"):
        print("Allowed:")
        for path in payload["allowed"]:
            print(f"  - {path}")


def print_git_status(payload: dict[str, Any]) -> None:
    print(f"Palari git hook installed: {_yes_no(payload.get('installed', False))}")
    if payload.get("hook_path"):
        print(f"Hook path: {payload['hook_path']}")
    if payload.get("git_root"):
        print(f"Git root: {payload['git_root']}")
    claims = payload.get("active_claims", [])
    if claims:
        print("Active claims:")
        for claim in claims:
            writes = ", ".join(claim["allowed_write_paths"]) or "(none)"
            print(
                f"  {claim['work_item']} by {claim['claimed_by']} "
                f"(mode {claim['mode']}, lease {claim['lease_expires_at']})"
            )
            print(f"    allowed writes: {writes}")
    else:
        print("Active claims: none")
    print(payload.get("message", ""))
