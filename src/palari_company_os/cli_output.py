from __future__ import annotations

import json
from typing import Any

from .cli_output_agent import (
    print_agent_adopt,
    print_agent_brief,
    print_agent_advance,
    print_agent_home,
    print_agent_next,
    print_agent_next_all,
    print_agent_park,
    print_agent_release,
    print_agent_session_contract,
    print_agent_start,
    print_agent_status,
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
from .cli_output_utils import (
    plain_detail_state,
    plain_field,
    plain_message,
    plain_status,
    plain_step,
    print_json,
    yes_no as _yes_no,
)
from .models import to_plain
from .work_identity import replace_opaque_ids, short_opaque_id
from .workspace import Workspace


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

    if result.kind == "simple-approval":
        if result.as_json:
            print_json(result.payload)
        else:
            print_simple_approval(result.payload)
        return

    if result.kind == "state":
        if result.as_json:
            print_json(result.payload)
        else:
            print_state(result.payload)
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

    if result.kind == "agent-home":
        print_agent_home(result.payload, result.as_json)
        return

    if result.kind == "agent-next-all":
        print_agent_next_all(result.payload, result.as_json)
        return

    if result.kind == "agent-status":
        print_agent_status(result.payload, result.as_json)
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

    if result.kind == "linear":
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

    if result.kind in {"work-idea", "work-idea-accept"}:
        print_work_idea_accept(result.payload, result.as_json)
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

    if result.kind == "cursor-install":
        if result.as_json:
            print_json(result.payload)
        else:
            print_cursor_install(result.payload)
        return

    if result.kind == "cursor-status":
        if result.as_json:
            print_json(result.payload)
        else:
            print_cursor_status(result.payload)
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

    if result.kind == "mission-control-serve":
        print_mission_control_serve(result.payload)
        return

    if result.kind == "demo-serve":
        return

    if result.kind == "mutation":
        print_mutation(result.payload, result.as_json)
        return

    raise ValueError(f"unknown command result kind: {result.kind}")


def print_validate(payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    print(f"Workspace valid: {payload['workspace']}")
    print(
        f"Records: {_count(counts['goals'], 'goal')}, "
        f"{_count(counts['palaris'], 'agent')}, "
        f"{_count(counts['humans'], 'human')}, "
        f"{_count(counts.get('sources', 0), 'source')}, "
        f"{_count(counts.get('workbenches', 0), 'project')}, "
        f"{_count(counts.get('playbook_sources', 0), 'playbook source')}, "
        f"{_count(counts.get('capabilities', 0), 'capability', 'capabilities')}, "
        f"{_count(counts.get('authority_profiles', 0), 'approval profile')}, "
        f"{_count(counts.get('integrations', 0), 'integration')}, "
        f"{_count(counts.get('integration_plans', 0), 'integration plan')}, "
        f"{_count(counts.get('integration_outbox', 0), 'outbox item')}, "
        f"{_count(counts.get('proposals', 0), 'proposal')}, "
        f"{_count(counts['work_items'], 'task')}, "
        f"{_count(counts.get('acceptance_records', 0), 'approval record')}, "
        f"{_count(counts.get('receipts', 0), 'run record')}"
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
        print(f"{result.action}: {plain_field(result.collection)}/{result.record_id}")
        if result.next_action:
            print(f"Next: {plain_message(result.next_action)}")


def print_governance_payload(payload: dict[str, Any]) -> None:
    print(payload.get("schema_version", "palari.payload.v1"))
    for key, label in (
        ("workspace", "Workspace"),
        ("status", "Status"),
        ("next_action", "Next"),
    ):
        if payload.get(key) not in (None, ""):
            print(f"{label}: {plain_message(payload[key])}")
    if "ok" in payload:
        print(f"OK: {_yes_no(bool(payload['ok']))}")
    for blocker in payload.get("blockers", []):
        print(f"  blocker: {plain_message(blocker)}")


def print_demo(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    if payload.get("schema_version") == "palari.demo.journey.v1":
        print("Palari demo: solo-maintainer local closeout")
    else:
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
            print(f"Allowed files: {', '.join(step['allowed_write_paths'])}")
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
    print(f"Tamper-evident history: {payload.get('status', 'unknown')}")
    print(f"Enabled: {_yes_no(bool(payload.get('enabled')))}")
    print(f"Verified: {_yes_no(bool(payload.get('ok')))}")
    if payload.get("journal_file"):
        print(f"History file: {payload['journal_file']}")
    for item in payload.get("errors", []):
        print(
            f"  error {item.get('code', '')}: "
            f"{plain_message(item.get('message', ''))}"
        )
        if item.get("next_action"):
            print(f"    next: {plain_message(item['next_action'])}")
    for item in payload.get("warnings", []):
        print(
            f"  warning {item.get('code', '')}: "
            f"{plain_message(item.get('message', ''))}"
        )


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
        print(f"Claimed status: {payload['claimed_state']}")
    if payload.get("derived_lifecycle_state"):
        print(f"Verified status: {payload['derived_lifecycle_state']}")
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
    print(f"Next: {plain_message(payload['next_action'])}")


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
    print(f"Next: {plain_message(payload['next_action'])}")


def print_docs_map(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    state = payload["documentation_state"]
    print(f"Docs map: {payload['repo']}")
    print(f"Documentation: {state['status']} - {plain_message(state['message'])}")
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


def print_review_guide(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    evidence = payload["evidence"]
    attempt = payload["attempt"]
    receipt = payload["receipt"]
    print(f"Review guide: {payload['guide_id']}")
    print(
        f"Guide state: {plain_detail_state(payload['status'])} | "
        f"Would mutate: {_yes_no(payload['would_mutate'])}"
    )
    print(f"Task: {work['id']} {work['title']} ({work['risk']})")
    print(f"Task status: {plain_status(payload['attention'])}")
    print(f"Why: {plain_message(payload['why'])}")
    print(f"Checks: {_present_label(evidence)}")
    if evidence.get("present"):
        print(
            f"  version: {evidence.get('head_sha', '')} | "
            f"status: {plain_detail_state(evidence.get('status', ''))}"
        )
    print(f"Run: {_present_label(attempt)}")
    if attempt.get("present") and attempt.get("changed_files"):
        print("  changed:")
        for path in attempt["changed_files"]:
            print(f"    - {path}")
    print(f"Run record: {_present_label(receipt)}")
    if receipt.get("present") and receipt.get("not_done"):
        print("  not done:")
        for item in receipt["not_done"]:
            print(f"    - {item}")
    print("Review focus:")
    for item in payload["review_focus"]:
        print(f"  - {plain_message(item)}")
    candidates = payload.get("reviewer_candidates", [])
    if candidates:
        review_ready = payload.get("attention") == "needs-review"
        if review_ready:
            print("Reviewer candidates:")
        else:
            print("Potential reviewers after the task is ready:")
        for candidate in candidates:
            identity_type = candidate.get("identity_type", "human")
            if identity_type == "palari":
                identity_type = "agent"
            print(
                f"  - {candidate['id']} ({candidate['name']}, {identity_type}): "
                f"{plain_message(candidate['reason'])}"
            )
            if review_ready and candidate.get("review_packet_command"):
                print(f"    task brief: {candidate['review_packet_command']}")
            if review_ready:
                verdict_commands = [
                    command
                    for command in candidate.get("review_record_commands", [])
                    if command.get("executable") is True
                    and command.get("command")
                    and command.get("verdict")
                ]
                if verdict_commands:
                    label = plain_message(
                        "packet-bound executable verdict commands"
                        if candidate.get("agent_may_execute") is True
                        else "human-only executable verdict commands"
                    )
                    print(f"    {label}:")
                    for command in verdict_commands:
                        print(
                            f"      {command['verdict']}: "
                            f"{command['command']}"
                        )
    if payload.get("attention") == "needs-review":
        print(f"{plain_message('Available verdicts')}:")
        print(f"  {', '.join(payload['suggested_verdicts'])}")
        template = payload.get("review_record_command_template", "")
        if template:
            print("Non-executable reference template:")
            print(f"  {template}")
    else:
        print("Review recording is available after the required checks pass.")
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
    print(f"Workspace file: {payload['workspace_file']}")
    print(
        f"Starter records: {payload['human']['id']} ({payload['human']['name']}), "
        f"builder {payload['palari']['id']} ({payload['palari']['name']}), "
        f"reviewer {payload['reviewer']['id']} ({payload['reviewer']['name']}), "
        f"{payload['goal']}, {payload['workbench']}, {payload['source']}"
    )
    adoption = payload.get("adoption") or {}
    if adoption.get("status") != "not-requested":
        print(
            f"Host adoption: {adoption.get('host', '')} "
            f"[{adoption.get('status', 'unknown')}]"
        )
        if adoption.get("status") == "blocked":
            print(f"Why: {plain_message(adoption.get('message', ''))}")
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
    print(f"Task created: {work['id']} {work['title']}")
    print(f"Agent: {work['palari']} | risk {work['risk']} | intensity {work['intensity']}")
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


def print_work_idea_accept(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    if "idea" in payload:
        idea = payload["idea"]
        print(f"Idea added: {idea['id']} {idea['title']}")
        print("This idea grants no task authority.")
        print(f"Human next step: {payload['next_action']}")
        return
    work = payload["work_item"]
    print(f"Idea approved: {payload['idea_id']}")
    print(f"Task created: {work['id']} {work['title']}")
    print(f"Next: {payload['next_action']}")


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
        print("Active task locks:")
        for claim in claims:
            writes = ", ".join(claim["allowed_write_paths"]) or "(none)"
            print(
                f"  {claim['work_item']} by {claim['claimed_by']} "
                f"(mode {claim['mode']}, lease {claim['lease_expires_at']})"
            )
            print(f"    allowed writes: {writes}")
    else:
        print("Active task locks: none")
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
    commands = payload.get("next_commands", [])
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_queue(workspace: Workspace, items: list[Any]) -> None:
    print(f"Palari Tasks: {workspace.name}")
    print("Flow: start -> check -> review -> approve -> verify")
    print("")
    known_ids = _opaque_ids(workspace)
    for item in items:
        next_command = item.next_commands[0] if item.next_commands else ""
        display_id = short_opaque_id(item.id, known_ids)
        display_step, display_command, display_action = _execution_entry_action(
            next_step_type=item.next_step_type,
            next_command=next_command,
            next_action=item.next_action,
            work_id=display_id,
            palari_id=item.palari,
        )
        display_command = replace_opaque_ids(display_command, known_ids)
        print(f"{display_id} [{item.intensity} / {item.risk}] {item.title}")
        print(
            "  status: "
            f"{plain_status(item.attention, next_step_type=display_step, next_command=display_command)}"
        )
        print(
            f"  next step: {plain_step(display_step, next_command=display_command)}"
        )
        print(f"  next: {plain_message(display_action)}")
        if display_command:
            print(f"  command: {display_command}")
        if item.workbench_label:
            print(f"  project: {item.workbench_label}")
        print(f"  goal: {item.goal_title}")
        print(f"  agent: {item.palari_name}")
        if item.owner:
            print(f"  owner: {item.owner}")
        if item.external_provider and item.external_key:
            print(f"  external: {item.external_provider}:{item.external_key}")
        print(f"  why: {plain_message(item.why)}")
        print(
            f"  safety: agent can continue={_yes_no(item.ai_safe_to_proceed)} "
            f"| waiting for human={_yes_no(item.waiting_on_human)}"
        )
        print(
            f"  checks: {plain_detail_state(item.evidence_state)} | "
            f"review: {plain_detail_state(item.review_state)} "
            f"| run record: {plain_detail_state(item.receipt_state)} "
            f"| approvals: {item.approval_progress}"
        )
        print(f"  integration: {plain_detail_state(item.integration_state)}")
        if item.active_attempts:
            attempts = ", ".join(attempt["attempt_id"] for attempt in item.active_attempts)
            print(f"  active runs: {attempts}")
        for warning in item.coordination_warnings:
            print(f"  coordination: {warning}")
        if item.agent_status_command:
            print(f"  agent status: {replace_opaque_ids(item.agent_status_command, known_ids)}")
        if item.terminal_disposition:
            print(f"  retired: {item.terminal_disposition} ({item.terminal_reason})")
            if item.successor_work_item_id:
                print(
                    f"  successor: {short_opaque_id(item.successor_work_item_id, known_ids)}"
                )
        print("")


def print_approval_inbox(payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    print(f"Approval Inbox: {payload['workspace']}")
    known_ids = _payload_opaque_ids(payload)
    primary = payload.get("primary_action", {})
    commands = [
        replace_opaque_ids(str(command), known_ids)
        for command in list(primary.get("commands", []))
    ]
    if primary.get("available"):
        state = "decision-ready"
        owner = "qualified human"
        safe = "yes, for the exact eligible presentation"
        explanation = (
            f"{counts['eligible']} item(s) have current checks; "
            f"{counts['blocked'] + counts['stale'] + counts['non_batchable']} exception(s) stay parked."
        )
        next_action = commands[0] if len(commands) == 1 else "Use the exact commands in --json."
    elif not counts["items"]:
        state = "empty"
        owner = "none"
        safe = "yes"
        explanation = "No human approval is waiting."
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
                replace_opaque_ids(str(item.get("next_safe_action")), known_ids)
                for item in payload.get("individual_items", [])
                if item.get("next_safe_action")
            ),
            "palari agent next --json",
        )
    print(f"Status: {plain_status(state)}")
    print(f"Safe: {safe}")
    print(f"Owner: {owner}")
    print(
        f"Items: {counts['items']} in {counts['packs']} pack(s) | "
        f"eligible {counts['eligible']} | blocked {counts['blocked']} | "
        f"stale {counts['stale']} | non-batchable {counts['non_batchable']}"
    )
    print(f"Why: {plain_message(explanation)}")
    print(f"Next: {next_action}")
    print("Verification details: rerun with --json. Blocked tasks are not approved.")


def print_approval_pack_decision(payload: dict[str, Any]) -> None:
    print(f"Approval Pack decision: {payload['status']}")
    print(f"Pack: {payload['pack_digest']}")
    print(f"Presentation: {payload['presentation_digest']}")
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
            "Finished automatically: "
            f"{len(convergence.get('terminalized', []))} complete; "
            f"{len(convergence.get('remaining_parked', []))} still blocked"
        )


def print_simple_approval(payload: dict[str, Any]) -> None:
    work_id = str(payload.get("work_item") or "")
    print(
        f"Task {short_opaque_id(work_id, [work_id])}: {plain_status(payload['status'])}"
    )
    print(f"Approved by: {payload['human']}")
    print(f"Completed: {_yes_no(bool(payload['completed']))}")
    print(
        "External actions performed: "
        f"{_yes_no(bool(payload['performed_external_effects']))}"
    )
    if payload.get("idempotent"):
        print("This was a safe retry; no approval authority was duplicated.")


def print_detail(payload: dict[str, Any]) -> None:
    work = payload["work_item"]
    known_ids = _detail_opaque_ids(payload)
    display_id = short_opaque_id(str(work.get("id") or ""), known_ids)
    goal = payload["goal"] or {}
    palari = payload["palari"] or {}
    workbench = payload.get("workbench") or {}
    next_commands = [
        replace_opaque_ids(str(command), known_ids)
        for command in (payload.get("next_commands") or [])
    ]
    next_command = str(next_commands[0]) if next_commands else ""
    display_step, display_command, display_action = _execution_entry_action(
        next_step_type=str(payload.get("next_step_type") or "inspect"),
        next_command=next_command,
        next_action=str(payload.get("next_action") or ""),
        work_id=display_id,
        palari_id=str(work.get("palari") or ""),
    )
    display_command = replace_opaque_ids(display_command, known_ids)
    print(f"Task {display_id}: {work['title']}")
    print(
        "Status: "
        f"{plain_status(payload['attention'], next_step_type=display_step, next_command=display_command)} "
        f"| Risk: {work['risk']} | Intensity: {work['intensity']}"
    )
    if work.get("status") in {"superseded", "abandoned"}:
        print(
            f"Retired: {work['status']} | "
            f"Reason: {work.get('terminal_reason', '')}"
        )
        if work.get("successor_work_item_id"):
            print(f"Successor: {short_opaque_id(work['successor_work_item_id'], known_ids)}")
    if workbench:
        print(f"Project: {workbench.get('label', work['workbench_id'])}")
    print(f"Goal: {goal.get('title', work['goal'])}")
    print(f"Agent: {palari.get('name', work['palari'])}")
    print("")
    print(
        "Status detail: "
        f"{plain_status(payload['attention'], next_step_type=display_step, next_command=display_command)}"
    )
    print(f"Why: {plain_message(payload['why'])}")
    print(
        f"Next step: {plain_step(display_step, next_command=display_command)}"
    )
    print(f"Next: {plain_message(display_action)}")
    display_commands = list(next_commands)
    if display_command and display_command not in display_commands:
        display_commands.insert(0, display_command)
    if display_commands:
        print("Next commands:")
        for command in display_commands:
            print(f"  {command}")
    safety = payload["safety"]
    print(
        "Safety: "
        f"agent can continue={_yes_no(bool(safety.get('ai_safe_to_proceed')))} | "
        f"waiting for human={_yes_no(bool(safety.get('waiting_on_human')))}"
    )
    print(
        f"Checks: {plain_detail_state(safety.get('evidence_state', 'unknown'))} | "
        f"Review: {plain_detail_state(safety.get('review_state', 'unknown'))} | "
        f"Run record: {plain_detail_state(safety.get('receipt_state', 'unknown'))} | "
        f"Approvals: {safety.get('approval_progress', 'unknown')}"
    )
    if payload.get("agent_commands"):
        print("Agent commands:")
        for label, command in payload["agent_commands"].items():
            print(f"  {label}: {replace_opaque_ids(str(command), known_ids)}")
    print("")
    print("Task limits")
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
            print(f"    {item['id']}: {plain_message(item['reason'])}")
    print("")
    if payload.get("parent_work_item"):
        parent = payload["parent_work_item"]
        print(f"Parent task: {short_opaque_id(parent['id'], known_ids)} - {parent['title']}")
        print("")
    if payload.get("child_work_items"):
        print("Child Tasks")
        for child in payload["child_work_items"]:
            print(f"  {child['id']}: {child['title']} [{plain_status(child['status'])}]")
        print("")
    if payload.get("dependencies"):
        print("Dependencies")
        for dependency in payload["dependencies"]:
            print(
                f"  {dependency['id']}: {dependency['title']} "
                f"[{plain_status(dependency['status'])}]"
            )
        print("")
    if payload.get("active_parallel_attempts"):
        print("Active Parallel Runs")
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
    _print_section("Run", payload["attempt"])
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
    _print_section("Run Record", payload.get("receipt"))
    _print_section("Checks", payload["evidence"])
    _print_section("Review", payload["review"])
    _print_section("Approval or Rejection", payload["human_decision"])
    if payload["human_decisions"]:
        print("Approvals and Rejections")
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
    _print_section("Result", payload["outcome"])


def print_state(payload: dict[str, Any]) -> None:
    print(f"Palari workspace status: {payload['workspace']}")
    print("Counts")
    for key, value in payload["counts"].items():
        print(f"  {plain_field(key)}: {value}")
    print("Statuses")
    status_counts: dict[str, int] = {}
    queue = payload.get("queue") or []
    if queue:
        for item in queue:
            commands = item.get("next_commands") or []
            next_command = str(commands[0]) if commands else ""
            label = plain_status(
                str(item.get("attention") or ""),
                next_step_type=str(item.get("next_step_type") or ""),
                next_command=next_command,
            )
            status_counts[label] = status_counts.get(label, 0) + 1
    else:
        for key, value in payload["attention"].items():
            label = plain_status(key)
            status_counts[label] = status_counts.get(label, 0) + int(value)
    for key, value in status_counts.items():
        print(f"  {key}: {value}")
    top = payload.get("top_attention")
    if top:
        known_ids = [
            str(item.get("id") or "")
            for item in queue
            if item.get("id")
        ]
        if top.get("id"):
            known_ids.append(str(top["id"]))
        commands = [
            replace_opaque_ids(str(command), known_ids)
            for command in (top.get("next_commands") or [])
        ]
        next_command = str(commands[0]) if commands else ""
        display_id = short_opaque_id(str(top.get("id") or ""), known_ids)
        display_step, display_command, _ = _execution_entry_action(
            next_step_type=str(top.get("next_step_type") or "inspect"),
            next_command=next_command,
            next_action=str(top.get("next_action") or ""),
            work_id=display_id,
            palari_id=str(top.get("palari") or ""),
        )
        display_command = replace_opaque_ids(display_command, known_ids)
        print("Next task")
        print(
            f"  {display_id}: {top['title']} "
            f"({plain_status(top['attention'], next_step_type=display_step, next_command=display_command)})"
        )
        if display_step:
            print(
                "  next step: "
                f"{plain_step(display_step, next_command=display_command)}"
            )
        print(f"  why: {plain_message(top['why'])}")
        if top.get("agent_status_command"):
            print(
                "  agent status: "
                f"{replace_opaque_ids(str(top['agent_status_command']), known_ids)}"
            )
        if display_command:
            print(f"  command: {display_command}")
    if payload.get("active_parallel_work"):
        print("Active parallel work")
        for item in payload["active_parallel_work"]:
            print(
                f"  {short_opaque_id(str(item['work_item_id']), [str(item['work_item_id'])])} "
                f"/ {item['attempt_id']}: {item['actor']}"
            )
    if payload.get("coordination_warnings"):
        print("Coordination warnings")
        for warning in payload["coordination_warnings"]:
            print(f"  {plain_message(warning['message'])}")


def print_scope(payload: dict[str, Any]) -> None:
    work_id = str(payload.get("work_item_id") or "")
    print(
        f"Task limits for {short_opaque_id(work_id, [work_id])}: "
        f"{'allowed' if payload['allowed'] else 'blocked'}"
    )
    for violation in payload["violations"]:
        print(f"  violation: {violation}")
    for note in payload["notes"]:
        print(f"  note: {note}")


def _opaque_ids(workspace: Workspace) -> list[str]:
    ids = [item.id for item in workspace.work_items]
    ids.extend(item.id for item in workspace.proposals)
    return ids


def _payload_opaque_ids(payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in payload.get("individual_items") or []:
        item_id = str(item.get("id") or "")
        if item_id:
            ids.append(item_id)
    return ids


def _detail_opaque_ids(payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    work = payload.get("work_item") or {}
    if work.get("id"):
        ids.append(str(work["id"]))
    if work.get("successor_work_item_id"):
        ids.append(str(work["successor_work_item_id"]))
    parent = payload.get("parent_work_item") or {}
    if parent.get("id"):
        ids.append(str(parent["id"]))
    return ids


def _execution_entry_action(
    *,
    next_step_type: str,
    next_command: str,
    next_action: str,
    work_id: str,
    palari_id: str,
) -> tuple[str, str, str]:
    """Put the idempotent task-lock step before checks in human output."""

    if next_step_type == "check-active-proof" and work_id and palari_id:
        return (
            "start-work",
            f"palari agent start {work_id} --as {palari_id} --mode execute --json",
            "Start or resume the task before running its checks.",
        )
    return next_step_type, next_command, next_action


def _print_section(title: str, value: dict[str, Any] | None) -> None:
    if not value:
        print(f"{title}: none")
        print("")
        return
    print(title)
    for key, item in value.items():
        if isinstance(item, list):
            if item:
                print(f"  {plain_field(key)}: {', '.join(str(part) for part in item)}")
        elif item:
            print(f"  {plain_field(key)}: {item}")
    print("")


def _present_label(record: dict[str, Any]) -> str:
    if not record.get("present"):
        return "missing"
    identifier = record.get("id", "present")
    return str(identifier)


def _count(value: Any, singular: str, plural: str = "") -> str:
    count = int(value)
    label = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {label}"


def print_git_install(payload: dict[str, Any]) -> None:
    print(f"Palari git hook: {payload['status']}")
    print(f"Hook path: {payload.get('hook_path', '')}")
    print(plain_message(payload.get("message", "")))


def print_git_pre_commit(payload: dict[str, Any]) -> None:
    status = payload.get("status", "")
    print(f"Palari pre-commit: {status}")
    print(plain_message(payload.get("message", "")))
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
        print("Active task locks:")
        for claim in claims:
            writes = ", ".join(claim["allowed_write_paths"]) or "(none)"
            print(
                f"  {claim['work_item']} by {claim['claimed_by']} "
                f"(mode {claim['mode']}, lease {claim['lease_expires_at']})"
            )
            print(f"    allowed writes: {writes}")
    else:
        print("Active task locks: none")
    print(plain_message(payload.get("message", "")))


def print_cursor_install(payload: dict[str, Any]) -> None:
    print(f"Palari Cursor rule: {payload['status']}")
    print(f"Rule path: {payload.get('rule_path', '')}")
    git_hook = payload.get("git_hook")
    if git_hook is None:
        print("Git pre-commit hook: skipped (--no-git-hook)")
    else:
        print(f"Git pre-commit hook: {git_hook.get('status', '')}")
    print(plain_message(payload.get("message", "")))


def print_cursor_status(payload: dict[str, Any]) -> None:
    print(f"Palari Cursor rule installed: {_yes_no(payload.get('installed', False))}")
    if payload.get("rule_path"):
        print(f"Rule path: {payload['rule_path']}")
    print(f"Git pre-commit hook installed: {_yes_no(payload.get('git_hook_installed', False))}")
    claims = payload.get("active_claims", [])
    if claims:
        print("Active task locks:")
        for claim in claims:
            writes = ", ".join(claim["allowed_write_paths"]) or "(none)"
            print(
                f"  {claim['work_item']} by {claim['claimed_by']} "
                f"(mode {claim['mode']}, lease {claim['lease_expires_at']})"
            )
            print(f"    allowed writes: {writes}")
    else:
        print("Active task locks: none")
    print(plain_message(payload.get("message", "")))
