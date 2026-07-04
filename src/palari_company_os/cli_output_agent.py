from __future__ import annotations

from typing import Any

from .cli_output_utils import (
    comma_or_none as _comma_or_none,
    print_json,
    print_limited_items as _print_limited_items,
    yes_no as _yes_no,
)


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
    docs_state = payload.get("documentation_state") or {}
    if docs_state:
        print(f"Docs: {docs_state.get('status', 'unknown')} - {docs_state.get('message', '')}")
    recommended_docs = payload.get("recommended_docs") or []
    if recommended_docs:
        print("Recommended docs:")
        for item in recommended_docs:
            print(f"  - {item['path']}: {item['why']}")
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


def print_agent_start(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print_agent_brief(payload, False)
    start = payload.get("start") or {}
    print(f"Start: {start.get('status', 'unknown')}")
    if start.get("packet_path"):
        print(f"Packet file: {start['packet_path']}")
    if start.get("claim_path"):
        print(f"Claim file: {start['claim_path']}")
    claim = start.get("claim") or {}
    if claim:
        print(f"Claimed by: {claim.get('claimed_by', '')}")
        print(f"Lease expires: {claim.get('lease_expires_at', '')}")


def print_agent_release(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Agent release: {payload['work_item']}")
    print(f"Status: {payload['status']}")
    print(f"Released: {_yes_no(payload['released'])}")
    print(f"By: {payload['released_by']}")
    print(f"Claim file: {payload['claim_path']}")
    print(f"Message: {payload['message']}")


def print_agent_next(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    agent = payload["agent"]
    print(f"Agent next: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Status: {payload['status']}")
    print(f"Mode: {payload.get('mode', 'execute')}")
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
            if candidate.get("doctor_command"):
                print(f"    doctor: {candidate['doctor_command']}")
            if candidate.get("loop_command"):
                print(f"    loop: {candidate['loop_command']}")
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
    print(f"Mode: {payload.get('mode', 'execute')}")
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
        if candidate.get("doctor_command"):
            print(f"  doctor: {candidate.get('doctor_command', '')}")
        if candidate.get("loop_command"):
            print(f"  loop: {candidate.get('loop_command', '')}")
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
            if first.get("doctor_command"):
                print(f"    doctor: {first['doctor_command']}")
            if first.get("loop_command"):
                print(f"    loop: {first['loop_command']}")
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
    print(f"Mode: {payload.get('mode', 'execute')}")
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
        focus = review.get("review_focus", [])
        if focus:
            print("  review focus:")
            for item in focus:
                print(f"    - {item}")
        receipt = review.get("receipt", {})
        if receipt.get("present"):
            print("  receipt:")
            outputs = receipt.get("outputs_created", [])
            if outputs:
                _print_limited_items("outputs", outputs, limit=8, indent="    ", item_indent="      ")
            print(f"    external writes: {_comma_or_none(receipt.get('external_writes', []))}")
            not_done = receipt.get("not_done", [])
            if not_done:
                _print_limited_items("not done", not_done, limit=8, indent="    ", item_indent="      ")
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
    approval = payload.get("human_approval_handoff")
    if approval:
        print("Human approval handoff:")
        print(f"  status: {approval['status']}")
        print(f"  command: {approval['command']}")
        print(f"  approval progress: {approval.get('approval_progress', '')}")
        print(f"  required approvals: {approval.get('required_approval_count', 0)}")
        if approval.get("required_approval_capability"):
            print(f"  required capability: {approval['required_approval_capability']}")
        focus = approval.get("approval_focus", [])
        if focus:
            print("  approval focus:")
            for item in focus:
                print(f"    - {item}")
        candidates = approval.get("approval_candidates", [])
        if candidates:
            print("  approval candidates:")
            for candidate in candidates:
                print(f"    - {candidate['id']} ({candidate['name']})")
        record_commands = approval.get("human_decision_record_commands", [])
        if record_commands:
            print("  human decision record commands:")
            for item in record_commands:
                print(f"    - {item['human_id']} {item['decision']}: {item['command']}")
    commands = payload.get("next_allowed_commands", [])
    if commands:
        print("Next agent-safe commands:")
        for command in commands:
            print(f"  {command}")
    human_commands = payload.get("human_action_commands", [])
    if human_commands:
        boundary = payload.get("human_action_boundary", {})
        if boundary.get("agent_may_execute") is False:
            print("Human action boundary: agent may quote these commands, but must not run them.")
        print("Human action commands:")
        for item in human_commands:
            detail = f" ({item.get('result', item.get('actor', ''))})"
            print(f"  - {item['type']}{detail}: {item['command']}")


def print_agent_loop(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    agent = payload["agent"]
    print(f"Agent loop: {payload['loop_id']}")
    print(f"Status: {payload['status']}")
    print(f"Mode: {payload.get('mode', 'execute')}")
    print(f"Step: {payload.get('next_step_type', 'inspect')}")
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Work: {work.get('id', '')} {work.get('title', '')}")
    print("Stages:")
    for stage in payload.get("stages", []):
        print(f"  - {stage['name']} [{stage['status']}]: {stage['message']}")
        print(f"    command: {stage['command']}")
        failed = stage.get("failed_required_checks", [])
        if failed:
            print(f"    failed required checks: {', '.join(failed)}")
    boundary = payload.get("human_action_boundary", {})
    if boundary.get("agent_may_execute") is False:
        print("Human action boundary: agent may quote human commands, but must not run them.")
    commands = payload.get("next_allowed_commands", [])
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_agent_doctor(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    agent = payload["agent"]
    print(f"Agent doctor: {payload['doctor_id']}")
    print(f"Status: {payload['status']}")
    print(f"Agent safe: {_yes_no(payload['agent_safe'])}")
    print(f"Human handoff required: {_yes_no(payload['human_handoff_required'])}")
    print(f"Mode: {payload.get('mode', 'execute')}")
    print(f"Step: {payload.get('next_step_type', 'inspect')}")
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Work: {work.get('id', '')} {work.get('title', '')}")
    print(f"Summary: {payload['summary']}")
    checks = payload.get("checks", [])
    if checks:
        print("Diagnosis:")
        for check in checks:
            print(f"  - {check['code']} [{check['status']}]: {check['message']}")
            if check.get("command"):
                print(f"    command: {check['command']}")
    if payload.get("missing_requirements"):
        print("Missing requirements:")
        for item in payload["missing_requirements"]:
            print(f"  - {item['code']}: {item['message']}")
    boundary = payload.get("human_action_boundary") or {}
    if boundary.get("agent_may_execute") is False:
        print("Human action boundary: agent may quote human commands, but must not run them.")
    commands = payload.get("recommended_commands", [])
    if commands:
        print("Recommended commands:")
        for command in commands:
            print(f"  {command}")


