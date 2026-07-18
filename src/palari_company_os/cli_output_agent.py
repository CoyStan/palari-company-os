from __future__ import annotations

from typing import Any

from .cli_output_utils import (
    print_json,
    yes_no as _yes_no,
)


_READ_ONLY_HANDOFF_COMMAND_PREFIXES = (
    "palari agent brief ",
    "palari agent check ",
    "palari agent doctor ",
    "palari agent finish ",
    "palari agent handoff ",
    "palari agent loop ",
    "palari decision guide ",
    "palari detail ",
    "palari docs check",
    "palari evidence verify ",
    "palari history verify",
    "palari queue ",
    "palari review guide ",
    "palari scope ",
    "palari validate",
)


def print_agent_adopt(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    enforcement = payload.get("enforcement") or {}
    host = payload.get("host_adapter") or {}
    git_gate = payload.get("git_gate") or {}
    print(f"Agent adoption: {payload.get('host', 'generic')}")
    print(f"Status: {payload.get('status', 'unknown')}")
    print(f"Contract: {payload.get('contract_file', '')}")
    print(f"Commit boundary: {git_gate.get('status', 'unknown')}")
    print(
        "Session boundary: "
        f"{enforcement.get('session_boundary', 'advisory')} "
        f"({enforcement.get('session_activation', 'unknown')})"
    )
    if host.get("next_action"):
        print(f"Activation: {host['next_action']}")
    print(f"MCP: {(payload.get('mcp') or {}).get('command', '')}")
    commands = payload.get("next_commands") or []
    if commands:
        print(f"Next: {commands[0]}")


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
    entry = payload.get("entry") or {}
    if entry:
        selected = entry.get("selected_work_item", "none")
        print(f"Agent entry: {selected}")
        print(f"Status: {payload.get('start', {}).get('status', payload.get('status', 'unknown'))}")
        print(f"Safe: {_yes_no(entry.get('safe', False))}")
        print(f"Owner: {entry.get('owner', '')}")
        print(f"Why: {entry.get('explanation', '')}")
        print(f"Next: {entry.get('next_command', '') or entry.get('next_action', '')}")
        return
    print_agent_brief(payload, False)
    start = payload.get("start") or {}
    print(f"Start: {start.get('status', 'unknown')}")
    if start.get("packet_path"):
        print(f"Packet file: {start['packet_path']}")
    if start.get("session_contract_path"):
        print(f"Session contract: {start['session_contract_path']}")
        summary = start.get("session_contract") or {}
        print(f"Contract digest: {summary.get('contract_digest', '')}")
        print(
            "Enforcement: "
            f"{summary.get('enforcement_profile', 'unknown')} "
            f"(adapter: {summary.get('host_adapter', 'none')})"
        )
    if start.get("claim_path"):
        print(f"Claim file: {start['claim_path']}")
    claim = start.get("claim") or {}
    if claim:
        print(f"Claimed by: {claim.get('claimed_by', '')}")
        print(f"Lease expires: {claim.get('lease_expires_at', '')}")


def print_agent_session_contract(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    body = payload.get("contract") or {}
    binding = body.get("packet_binding") or {}
    identity = body.get("identity") or {}
    work = identity.get("work_item") or {}
    enforcement = body.get("enforcement") or {}
    print(f"Portable session contract: {payload.get('contract_id', '')}")
    print(f"Status: {payload.get('status', 'blocked')}")
    print(f"Digest: {payload.get('contract_digest', '')}")
    print(f"Work: {work.get('id', '')} {work.get('title', '')}")
    print(f"Packet: {binding.get('packet_id', '')}")
    print("Grants authority: no (an active matching claim is required)")
    print(
        "Enforcement: "
        f"{enforcement.get('profile', 'unknown')} "
        f"(adapter: {enforcement.get('adapter', 'none')})"
    )
    properties = enforcement.get("properties") or []
    if properties:
        print("Properties:")
        for item in properties:
            print(f"  - {item.get('id', '')} [{item.get('status', '')}]")
    limitations = body.get("security_limitations") or []
    if limitations:
        print("Security limitations:")
        for item in limitations:
            print(f"  - {item}")


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


def print_agent_park(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Work: {payload['work_item']} [blocked]")
    print(f"Owner: {payload['parked_by']}")
    print(f"Reason: {payload['reason']}")
    print(f"Next: {payload['next_action']}")
    print(f"Claim released: {_yes_no(payload['claim_released'])}")


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
    print(f"Agent handoff: {work.get('id', '')} {work.get('title', '')}")
    print(
        f"State: {payload.get('status', 'unknown')} / "
        f"{payload.get('next_step_type', 'inspect')}"
    )
    print("Safe: yes (next action is read-only; no authority is recorded)")
    print(f"Owner: {_handoff_owner(payload)}")
    print(f"Why: {_handoff_explanation(payload)}")
    print(f"Next: {_handoff_next_action(payload)}")
    print("Proof and alternatives: rerun with --json.")


def _handoff_owner(payload: dict[str, Any]) -> str:
    step = str(payload.get("next_step_type") or "")
    review = payload.get("review_handoff") or {}
    decision = payload.get("decision_handoff") or {}
    approval = payload.get("human_approval_handoff") or {}
    if review and (step == "review-handoff" or not (decision or approval)):
        return _eligible_owner(
            "independent reviewer",
            review.get("reviewer_candidates", []),
        )
    if decision:
        required = decision.get("required_human") or {}
        required_id = str(
            required.get("id")
            or decision.get("decision", {}).get("required_human")
            or ""
        )
        return f"qualified human {required_id}".rstrip()
    if approval:
        return _eligible_owner(
            "qualified human",
            approval.get("approval_candidates", []),
        )
    primary = str(payload.get("resolution_summary", {}).get("primary_class") or "")
    if payload.get("status") == "closed" or step == "closed" or primary == "terminal":
        return "none (terminal)"
    return {
        "human-authority": "qualified human",
        "independent-review": "independent reviewer",
        "external-state": "external owner",
        "automatic-reconciliation": (
            "system" if step == "automatic-reconciliation" else "agent"
        ),
        "agent-action": "agent",
    }.get(primary, "agent")


def _eligible_owner(label: str, candidates: list[dict[str, Any]]) -> str:
    ids = [str(item.get("id") or "") for item in candidates if item.get("id")]
    if not ids:
        return label
    if len(ids) == 1:
        return f"{label} {ids[0]}"
    if len(ids) <= 3:
        return f"{label} ({' or '.join(ids)})"
    return f"{label} ({len(ids)} eligible; inspect --json)"


def _handoff_explanation(payload: dict[str, Any]) -> str:
    review = payload.get("review_handoff") or {}
    decision = payload.get("decision_handoff") or {}
    approval = payload.get("human_approval_handoff") or {}
    if payload.get("status") == "closed" or payload.get("next_step_type") == "closed":
        return "Work is closed; no further authority or execution is required."
    for section, fallback in (
        (review, "Current proof is waiting for an independent verdict."),
        (decision, "A linked decision is waiting for qualified human judgment."),
        (approval, "Current reviewed proof is waiting for qualified human approval."),
    ):
        if section:
            return _one_line(section.get("why") or section.get("next_action") or fallback)
    finish = payload.get("finish") or {}
    for key in ("missing_requirements", "blockers"):
        items = finish.get(key) or []
        if items:
            return _one_line(items[0].get("message") or "Current proof is blocked.")
    return _one_line(
        finish.get("report_guidance")
        or "Inspect current proof before taking another action."
    )


def _handoff_next_action(payload: dict[str, Any]) -> str:
    step = str(payload.get("next_step_type") or "")
    review = payload.get("review_handoff") or {}
    decision = payload.get("decision_handoff") or {}
    approval = payload.get("human_approval_handoff") or {}
    if review and (step == "review-handoff" or not (decision or approval)):
        return _read_only_handoff_action(payload, str(review.get("command") or ""))
    if decision:
        return _read_only_handoff_action(payload, str(decision.get("command") or ""))
    if approval:
        return _read_only_handoff_action(payload, str(approval.get("command") or ""))
    return _read_only_handoff_action(payload)


def _read_only_handoff_action(
    payload: dict[str, Any],
    preferred: str = "",
) -> str:
    commands = [preferred, *payload.get("next_allowed_commands", [])]
    for value in commands:
        command = str(value or "")
        if command.startswith(_READ_ONLY_HANDOFF_COMMAND_PREFIXES):
            return command
    work_id = str(payload.get("work_item", {}).get("id") or "WORK-ID")
    return f"palari detail {work_id} --json"


def _one_line(value: Any, *, limit: int = 180) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


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
    resolution = payload.get("resolution_summary") or {}
    owner_by_class = {
        "human-authority": "human",
        "independent-review": "reviewer",
        "external-state": "external owner",
        "automatic-reconciliation": "system",
        "terminal": "none",
    }
    owner = payload.get("owner") or owner_by_class.get(
        resolution.get("primary_class"),
        "agent" if payload.get("agent_safe") else "operator",
    )
    next_action = payload.get("next_action") or {}
    next_command = str(next_action.get("command") or "") or next(
        iter(payload.get("recommended_commands", [])), ""
    )
    print(f"Agent doctor: {payload['doctor_id']}")
    print(f"State: {payload['status']} / {payload.get('next_step_type', 'inspect')}")
    print(f"Safe: {_yes_no(payload['agent_safe'])}")
    print(f"Owner: {owner}")
    print(f"Agent: {agent.get('id', '')}")
    print(f"Work: {work.get('id', '')} {work.get('title', '')}")
    print(f"Summary: {payload['summary']}")
    print(f"Next: {next_command or 'No action; inspect --json for recorded proof.'}")
    print("Proof details: rerun with --json.")


def print_agent_done(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    label = "Agent advance" if payload.get("schema_version") == "palari.agent_advance.v1" else "Agent done"
    print(f"{label}: {payload['work_item']}")
    print(f"Status: {payload['status']}")
    print(f"Can done: {_yes_no(payload.get('can_done', False))}")
    if payload.get("message"):
        print(payload["message"])
    for step in payload.get("steps", []):
        label = step.get("step", "")
        status = step.get("status", "")
        step_id = step.get("id", "")
        detail_str = f" {step_id}" if step_id else ""
        print(f"  {label}{detail_str}: {status}")
    for step in payload.get("proof_steps", []):
        label = step.get("step", "")
        status = step.get("status", "")
        step_id = step.get("id", "")
        detail_str = f" {step_id}" if step_id else ""
        print(f"  {label}{detail_str}: {status}")
