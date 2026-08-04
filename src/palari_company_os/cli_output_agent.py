from __future__ import annotations

from typing import Any

from .command_surface import palari_command_parts, palari_workspace_command
from .cli_output_utils import (
    plain_detail_state,
    plain_message,
    plain_status,
    plain_step,
    plain_step_status,
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


def _is_read_only_handoff_command(command: str) -> bool:
    parts = palari_command_parts(command)
    if not parts:
        return False
    normalized = "palari " + " ".join(parts)
    return normalized.startswith(_READ_ONLY_HANDOFF_COMMAND_PREFIXES)


def print_agent_adopt(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    enforcement = payload.get("enforcement") or {}
    host = payload.get("host_adapter") or {}
    git_gate = payload.get("git_gate") or {}
    print(f"Agent adoption: {payload.get('host', 'unknown')}")
    print(f"Status: {payload.get('status', 'unknown')}")
    print(f"Contract: {payload.get('contract_file', '')}")
    print(f"Commit boundary: {git_gate.get('status', 'unknown')}")
    print(
        "Session boundary: "
        f"{enforcement.get('session_boundary', 'unknown')} "
        f"({enforcement.get('session_activation', 'unknown')})"
    )
    if host.get("next_action"):
        print(f"Activation: {plain_message(host['next_action'])}")
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
    commands = _agent_display_commands(payload)
    ready_to_start = payload.get("status") == "ready" and payload.get("mode") == "execute"
    start_command = _payload_command(
        payload,
        "agent",
        "start",
        str(work.get("id") or "WORK-ID"),
        "--as",
        str(agent.get("id") or "PALARI-ID"),
        "--mode",
        "execute",
        "--json",
    )
    if ready_to_start:
        if start_command in commands:
            commands.remove(start_command)
        commands.insert(0, start_command)
    display_step = "start-work" if ready_to_start else _agent_display_step(payload)
    context_command = _agent_context_command(
        payload, commands[0] if commands else ""
    )
    print(f"Task brief: {payload['packet_id']}")
    print(
        "Status: "
        f"{plain_status(payload['status'], next_step_type=display_step, next_command=context_command)}"
    )
    print(f"Mode: {payload['mode']}")
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Task: {work.get('id', '')} {work.get('title', '')}")
    print(f"Next step: {plain_step(display_step, next_command=context_command)}")
    instruction = str(payload.get("one_sentence_instruction") or "")
    if payload.get("status") != "ready":
        instruction = instruction.replace(
            "resolve the packet blockers first",
            "resolve the task brief blockers first",
        )
    print(f"Instruction: {instruction}")
    docs_state = payload.get("documentation_state") or {}
    if docs_state:
        print(
            f"Docs: {docs_state.get('status', 'unknown')} - "
            f"{plain_message(docs_state.get('message', ''))}"
        )
    recommended_docs = payload.get("recommended_docs") or []
    if recommended_docs:
        print("Recommended docs:")
        for item in recommended_docs:
            print(f"  - {item['path']}: {plain_message(item['why'])}")
    blockers = payload.get("blockers", [])
    if blockers:
        print("Blockers:")
        for blocker in blockers:
            print(f"  - {blocker['code']}: {plain_message(blocker['message'])}")
    if ready_to_start:
        print("Preview only: start the task before editing or running completion checks.")
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
        print(
            "Status: "
            f"{plain_status(payload.get('start', {}).get('status', payload.get('status', 'unknown')))}"
        )
        print(f"Safe: {_yes_no(entry.get('safe', False))}")
        print(f"Owner: {entry.get('owner', '')}")
        print(f"Why: {entry.get('explanation', '')}")
        print(
            "Next: "
            f"{plain_message(entry.get('next_command', '') or entry.get('next_action', ''))}"
        )
        return
    print_agent_brief(payload, False)
    start = payload.get("start") or {}
    print(f"Start: {plain_status(start.get('status', 'unknown'))}")
    if start.get("packet_path"):
        print(f"Task brief file: {start['packet_path']}")
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
        print(f"Task lock file: {start['claim_path']}")
    claim = start.get("claim") or {}
    if claim:
        print(f"Assigned to: {claim.get('claimed_by', '')}")
        print(f"Assignment expires: {claim.get('lease_expires_at', '')}")


def print_agent_session_contract(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    body = payload.get("contract") or {}
    binding = body.get("packet_binding") or {}
    identity = body.get("identity") or {}
    work = identity.get("work_item") or {}
    enforcement = body.get("enforcement") or {}
    print(f"Portable session rules: {payload.get('contract_id', '')}")
    print(f"Status: {plain_status(payload.get('status', 'blocked'))}")
    print(f"Digest: {payload.get('contract_digest', '')}")
    print(f"Task: {work.get('id', '')} {work.get('title', '')}")
    print(f"Task brief: {binding.get('packet_id', '')}")
    print("Grants permission: no (a matching active task lock is required)")
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
            print(f"  - {plain_message(item)}")


def print_agent_release(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Task released: {payload['work_item']}")
    print(f"Status: {plain_status(payload['status'])}")
    print(f"Released: {_yes_no(payload['released'])}")
    print(f"By: {payload['released_by']}")
    print(f"Task lock file: {payload['claim_path']}")
    print(f"Message: {plain_message(payload['message'])}")


def print_agent_park(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Task: {payload['work_item']} [Blocked]")
    print(f"Owner: {payload['parked_by']}")
    print(f"Reason: {payload['reason']}")
    print(f"Next: {payload['next_action']}")
    print(f"Task lock released: {_yes_no(payload['claim_released'])}")


def print_agent_next(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    agent = payload["agent"]
    print(f"Agent next: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Status: {plain_status(payload['status'])}")
    print(f"Mode: {payload.get('mode', 'execute')}")
    print("Flow: start -> check -> review -> approve -> verify")
    print(f"Ready: {payload['ready_count']} | Blocked/waiting: {payload['blocked_count']}")
    blockers = payload.get("blockers", [])
    if blockers:
        print("Blockers:")
        for blocker in blockers:
            print(f"  - {blocker['code']}: {plain_message(blocker['message'])}")
            if blocker.get("next_command"):
                print(f"    fix: {blocker['next_command']}")
    candidates = payload.get("candidates", [])
    if candidates:
        print("Candidates:")
        for candidate in candidates:
            marker = "Ready" if candidate["can_start"] else "Waiting"
            next_step, next_command = _candidate_display_action(
                candidate,
                agent_id=str(agent.get("id", "PALARI-ID")),
                mode=str(payload.get("mode", "execute")),
            )
            context_command = _candidate_decision_command(candidate) or next_command
            print(
                f"  - {candidate['work_item_id']} [{marker}] "
                f"{candidate['title']} "
                f"({plain_status(candidate['attention'], next_step_type=next_step, next_command=context_command)})"
            )
            print(f"    next: {next_command}")
            if candidate.get("doctor_command"):
                print(f"    doctor: {candidate['doctor_command']}")
            if candidate.get("loop_command"):
                print(f"    loop: {candidate['loop_command']}")
            if next_step:
                print(
                    "    next step: "
                    f"{plain_step(next_step, next_command=context_command)}"
                )
            if candidate.get("blocker_codes"):
                print(f"    blockers: {', '.join(candidate['blocker_codes'])}")
            if candidate.get("start_blocker_codes"):
                print(f"    start blockers: {', '.join(candidate['start_blocker_codes'])}")
            if candidate.get("handoff_guidance"):
                for item in candidate["handoff_guidance"]:
                    print(
                        f"    handoff: {item['code']} - "
                        f"{plain_message(item['message'])}"
                    )
                    if item.get("command"):
                        print(f"      command: {item['command']}")
    commands = list(payload.get("next_allowed_commands", []))
    if candidates:
        _, primary_command = _candidate_display_action(
            candidates[0],
            agent_id=str(agent.get("id", "PALARI-ID")),
            mode=str(payload.get("mode", "execute")),
        )
        if primary_command and primary_command not in commands:
            commands.insert(0, primary_command)
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_agent_next_all(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Agent next rollup: {payload['workspace']}")
    print(f"Status: {plain_status(payload['status'])}")
    print(f"Mode: {payload.get('mode', 'execute')}")
    print(f"Ready: {payload['ready_count']} | Blocked/waiting: {payload['blocked_count']}")
    top = payload.get("top_candidate")
    if top:
        agent = top.get("agent", {})
        candidate = top.get("candidate", {})
        marker = "Ready" if candidate.get("can_start") else "Waiting"
        next_step, next_command = _candidate_display_action(
            candidate,
            agent_id=str(agent.get("id", "PALARI-ID")),
            mode=str(payload.get("mode", "execute")),
        )
        context_command = _candidate_decision_command(candidate) or next_command
        print(
            f"Top: {candidate.get('work_item_id', '')} [{marker}] "
            f"via {agent.get('id', '')} - {candidate.get('title', '')}"
        )
        print(f"  next: {next_command}")
        if candidate.get("doctor_command"):
            print(f"  doctor: {candidate.get('doctor_command', '')}")
        if candidate.get("loop_command"):
            print(f"  loop: {candidate.get('loop_command', '')}")
        if next_step:
            print(
                "  next step: "
                f"{plain_step(next_step, next_command=context_command)}"
            )
    for agent_payload in payload.get("agents", []):
        agent = agent_payload["agent"]
        print(
            f"  - {agent.get('id', '')} ({agent.get('name', 'unknown')}): "
            f"{agent_payload['ready_count']} ready / {agent_payload['blocked_count']} waiting"
        )
        candidates = agent_payload.get("candidates", [])
        if candidates:
            first = candidates[0]
            first_step, first_command = _candidate_display_action(
                first,
                agent_id=str(agent.get("id", "PALARI-ID")),
                mode=str(payload.get("mode", "execute")),
            )
            first_context = _candidate_decision_command(first) or first_command
            print(f"    next: {first_command}")
            if first.get("doctor_command"):
                print(f"    doctor: {first['doctor_command']}")
            if first.get("loop_command"):
                print(f"    loop: {first['loop_command']}")
            if first_step:
                print(
                    "    next step: "
                    f"{plain_step(first_step, next_command=first_context)}"
                )
    commands = list(payload.get("next_allowed_commands", []))
    if top:
        top_agent = top.get("agent", {})
        top_candidate = top.get("candidate", {})
        _, primary_command = _candidate_display_action(
            top_candidate,
            agent_id=str(top_agent.get("id", "PALARI-ID")),
            mode=str(payload.get("mode", "execute")),
        )
        if primary_command and primary_command not in commands:
            commands.insert(0, primary_command)
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
    commands = _agent_display_commands(payload)
    next_command = commands[0] if commands else ""
    display_step = _agent_display_step(payload)
    context_command = _agent_context_command(payload, next_command)
    print(f"Task check: {payload['check_id']}")
    print(f"OK: {_yes_no(payload['ok'])}")
    print(f"Mode: {payload.get('mode', 'execute')}")
    print(f"Task brief: {payload['packet_id']} ({plain_status(payload['packet_status'])})")
    print(f"Next step: {plain_step(display_step, next_command=context_command)}")
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Task: {work.get('id', '')} {work.get('title', '')}")
    blockers = payload.get("blockers", [])
    if blockers:
        print("Task brief blockers:")
        for blocker in blockers:
            print(f"  - {blocker['code']}: {plain_message(blocker['message'])}")
    print("Checks:")
    for check in payload.get("checks", []):
        marker = check["status"]
        required = "required" if check.get("required") else "optional"
        print(
            f"  - {check['code']} [{marker}, {required}]: "
            f"{plain_message(check['message'])}"
        )
        if check.get("next_command") in commands:
            print(f"    next: {check['next_command']}")
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
    commands = _agent_display_commands(payload)
    next_command = commands[0] if commands else ""
    display_step = _agent_display_step(payload)
    decision_command = _decision_guide_command(payload)
    decision_pending = bool(decision_command) or _has_blocker(
        payload, "HUMAN_DECISION_REQUIRED"
    )
    context_command = _agent_context_command(payload, next_command)
    print(f"Task finish: {payload['finish_id']}")
    print(
        "Status: "
        f"{plain_status(payload['status'], next_step_type=display_step, next_command=context_command)}"
    )
    print(f"Can finish: {_yes_no(payload['can_finish'])}")
    if decision_pending:
        print("Ready for decision handoff: yes")
    else:
        print(f"Ready to hand off: {_yes_no(payload['handoff_ready'])}")
    print(
        "Next step: "
        f"{plain_step(display_step, next_command=context_command)}"
    )
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Task: {work.get('id', '')} {work.get('title', '')}")
    if payload.get("missing_requirements"):
        print("Missing requirements:")
        for item in payload["missing_requirements"]:
            print(f"  - {item['code']}: {plain_message(item['message'])}")
            if item.get("next_command") in commands:
                print(f"    next: {item['next_command']}")
    if payload.get("completed_requirements"):
        print("Completed requirements:")
        for item in payload["completed_requirements"]:
            print(f"  - {item['code']}: {plain_message(item['message'])}")
    if payload.get("blockers"):
        print("Blockers:")
        for blocker in payload["blockers"]:
            print(f"  - {blocker['code']}: {plain_message(blocker['message'])}")
    if payload.get("handoff_guidance"):
        print("Handoff guidance:")
        for item in payload["handoff_guidance"]:
            print(f"  - {item['code']}: {plain_message(item['message'])}")
            if item.get("command"):
                print(f"    command: {item['command']}")
    guidance = (
        "Bring the linked decision to the required human before continuing."
        if decision_pending
        else _display_report_guidance(payload, payload["report_guidance"])
    )
    print(f"Guidance: {guidance}")
    if commands:
        print("Next commands:")
        for command in commands:
            print(f"  {command}")


def print_agent_handoff(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    work = payload["work_item"]
    next_command = _handoff_next_action(payload)
    print(f"Handoff: {work.get('id', '')} {work.get('title', '')}")
    print(
        "Status: "
        f"{plain_status(payload.get('status', 'unknown'), next_step_type=payload.get('next_step_type'), next_command=next_command)}"
    )
    print("Safe: yes (the next action is read-only; no approval is recorded)")
    print(f"Owner: {_handoff_owner(payload)}")
    print(f"Why: {plain_message(_handoff_explanation(payload))}")
    print(f"Next: {next_command}")
    print("Verification details and alternatives: rerun with --json.")


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
        return "The task is complete; no further approval or work is required."
    for section, fallback in (
        (review, "The checked version is waiting for an independent review result."),
        (decision, "A linked decision is waiting for qualified human judgment."),
        (approval, "The current reviewed version is waiting for qualified human approval."),
    ):
        if section:
            return _one_line(section.get("why") or section.get("next_action") or fallback)
    finish = payload.get("finish") or {}
    for key in ("missing_requirements", "blockers"):
        items = finish.get(key) or []
        if items:
            return _one_line(items[0].get("message") or "The current checks are blocked.")
    return _one_line(
        finish.get("report_guidance")
        or "Inspect the current checks before taking another action."
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
        if _is_read_only_handoff_command(command):
            return command
    work_id = str(payload.get("work_item", {}).get("id") or "WORK-ID")
    return _payload_command(payload, "detail", work_id, "--json")


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
    commands = _agent_display_commands(payload)
    next_command = commands[0] if commands else ""
    display_step = _agent_display_step(payload)
    decision_command = _decision_guide_command(payload)
    context_command = _agent_context_command(payload, next_command)
    print(f"Task flow: {payload['loop_id']}")
    print(
        "Status: "
        f"{plain_status(payload['status'], next_step_type=display_step, next_command=context_command)}"
    )
    print(f"Mode: {payload.get('mode', 'execute')}")
    print(
        "Next step: "
        f"{plain_step(display_step, next_command=context_command)}"
    )
    print(f"Agent: {agent.get('id', '')} ({agent.get('name', 'unknown')})")
    print(f"Task: {work.get('id', '')} {work.get('title', '')}")
    print("Stages:")
    for stage in payload.get("stages", []):
        message = str(stage["message"])
        if stage.get("name") == "finish" and (
            decision_command or _has_blocker(payload, "HUMAN_DECISION_REQUIRED")
        ):
            message = "Bring the linked decision to the required human before continuing."
        elif (
            payload.get("mode") == "execute"
            and stage.get("name") == "finish"
            and "CLAIM_OWNED" in _failed_check_codes(payload)
        ):
            message = _start_work_guidance()
        elif (
            payload.get("mode") == "review"
            and stage.get("name") == "finish"
            and stage.get("status") in {"missing-proof", "blocked"}
        ):
            message = _review_wait_guidance()
        print(
            f"  - {stage['name']} [{plain_detail_state(stage['status'])}]: "
            f"{plain_message(message)}"
        )
        print(f"    command: {stage['command']}")
        failed = stage.get("failed_required_checks", [])
        if failed:
            print(f"    failed required checks: {', '.join(failed)}")
    boundary = payload.get("human_action_boundary", {})
    if boundary.get("agent_may_execute") is False:
        label = "Decision boundary" if decision_command else "Approval boundary"
        print(f"{label}: the agent may quote human commands, but must not run them.")
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
    resolution_value = payload.get("resolution_summary")
    resolution = resolution_value if isinstance(resolution_value, dict) else {}
    owner_by_class = {
        "human-authority": "human",
        "independent-review": "reviewer",
        "external-state": "external owner",
        "automatic-reconciliation": "system",
        "terminal": "none",
    }
    primary_class = resolution.get("primary_class")
    owner = payload.get("owner") or owner_by_class.get(
        primary_class if isinstance(primary_class, str) else "",
        "agent" if payload.get("agent_safe") else "operator",
    )
    commands = _agent_display_commands(payload)
    next_command = commands[0] if commands else ""
    display_step = _agent_display_step(payload)
    decision_command = _decision_guide_command(payload)
    context_command = _agent_context_command(payload, next_command)
    blockers = payload.get("blockers") or []
    visible_safe = bool(payload.get("agent_safe")) and not blockers
    print(f"Task status: {payload['doctor_id']}")
    print(
        "Status: "
        f"{plain_status(payload['status'], next_step_type=display_step, next_command=context_command)}"
    )
    print(f"Safe: {_yes_no(visible_safe)}")
    print(f"Owner: {owner}")
    print(f"Agent: {agent.get('id', '')}")
    print(f"Task: {work.get('id', '')} {work.get('title', '')}")
    if decision_command:
        summary = "This task is waiting for a human answer to a linked decision."
    elif blockers:
        codes = ", ".join(str(item.get("code") or "") for item in blockers)
        summary = f"The task brief is blocked: {codes}."
    else:
        summary = plain_message(payload["summary"])
    print(f"Summary: {summary}")
    print(f"Next: {next_command or 'No action; inspect --json for recorded checks.'}")
    print("Verification details: rerun with --json.")


def print_agent_advance(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Task advance: {payload['work_item']}")
    print(f"Status: {plain_status(payload['status'])}")
    print(f"Can advance: {_yes_no(payload.get('can_advance', False))}")
    if payload.get("message"):
        print(plain_message(payload["message"]))
    planned_steps = [] if payload.get("proof_steps") else payload.get("steps", [])
    for step in planned_steps:
        label = plain_step(step.get("step", ""))
        status = plain_step_status(step.get("status", ""))
        step_id = step.get("id", "")
        detail_str = f" {step_id}" if step_id else ""
        print(f"  {label}{detail_str}: {status}")
    for step in payload.get("proof_steps", []):
        label = plain_step(step.get("step", ""))
        status = plain_step_status(step.get("status", ""))
        step_id = step.get("id", "")
        detail_str = f" {step_id}" if step_id else ""
        print(f"  {label}{detail_str}: {status}")


def _candidate_display_action(
    candidate: dict[str, Any],
    *,
    agent_id: str,
    mode: str,
) -> tuple[str, str]:
    """Choose the first human-safe action without changing the JSON contract."""

    step = str(candidate.get("next_step_type") or "")
    command = str(candidate.get("next_command") or "")
    if _candidate_decision_command(candidate):
        guidance = candidate.get("handoff_guidance") or []
        handoff = next(
            (
                str(item.get("command") or "")
                for item in guidance
                if item.get("code") == "DECISION_HANDOFF"
            ),
            command,
        )
        return "human-decision", handoff
    claim = candidate.get("claim") or {}
    if (
        mode == "execute"
        and candidate.get("can_start")
        and not claim.get("active")
    ):
        work_id = str(candidate.get("work_item_id") or "WORK-ID")
        return (
            "start-work",
            _payload_command(
                candidate,
                "agent",
                "start",
                work_id,
                "--as",
                agent_id,
                "--mode",
                "execute",
                "--json",
            ),
        )
    return step, command


def _candidate_decision_command(candidate: dict[str, Any]) -> str:
    for item in candidate.get("handoff_guidance") or []:
        if item.get("code") == "DECISION_HANDOFF" and item.get("guide_command"):
            return str(item["guide_command"])
    for command in candidate.get("next_commands") or []:
        if palari_command_parts(str(command))[:2] == ("decision", "guide"):
            return str(command)
    return ""


def _decision_guide_command(payload: dict[str, Any]) -> str:
    decision = payload.get("decision_handoff") or {}
    if decision.get("command"):
        return str(decision["command"])
    for item in payload.get("handoff_guidance") or []:
        if item.get("code") == "DECISION_HANDOFF" and item.get("guide_command"):
            return str(item["guide_command"])
    for key in ("next_allowed_commands", "recommended_commands"):
        for command in payload.get(key) or []:
            if palari_command_parts(str(command))[:2] == ("decision", "guide"):
                return str(command)
    return ""


def _decision_handoff_command(payload: dict[str, Any]) -> str:
    for item in payload.get("handoff_guidance") or []:
        if item.get("code") == "DECISION_HANDOFF" and item.get("command"):
            return str(item["command"])
    next_action = payload.get("next_action") or {}
    command = str(next_action.get("command") or "")
    if palari_command_parts(command)[:2] == ("agent", "handoff"):
        return command
    for key in ("recommended_commands", "next_allowed_commands"):
        for value in payload.get(key) or []:
            command = str(value)
            if palari_command_parts(command)[:2] == ("agent", "handoff"):
                return command
    if _has_blocker(payload, "HUMAN_DECISION_REQUIRED"):
        work_id = str(payload.get("work_item", {}).get("id") or "WORK-ID")
        agent_id = str(payload.get("agent", {}).get("id") or "PALARI-ID")
        return _payload_command(
            payload,
            "agent",
            "handoff",
            work_id,
            "--as",
            agent_id,
            "--json",
        )
    return ""


def _failed_check_codes(payload: dict[str, Any]) -> set[str]:
    codes = {
        str(item.get("code") or "")
        for item in payload.get("missing_requirements") or []
    }
    codes.update(
        str(item.get("code") or "")
        for item in payload.get("checks") or []
        if item.get("required") and item.get("status") == "fail"
    )
    return codes


def _has_blocker(payload: dict[str, Any], code: str) -> bool:
    return any(item.get("code") == code for item in payload.get("blockers") or [])


def _agent_context_command(payload: dict[str, Any], fallback: str = "") -> str:
    guide = _decision_guide_command(payload)
    if guide:
        return guide
    if _has_blocker(payload, "HUMAN_DECISION_REQUIRED"):
        # This value is only a rendering hint for plain_step/plain_status. The
        # executable command remains the read-only agent handoff.
        return "palari decision guide"
    return fallback


def _agent_display_step(payload: dict[str, Any]) -> str:
    if _decision_guide_command(payload) or _has_blocker(
        payload, "HUMAN_DECISION_REQUIRED"
    ):
        return "human-decision"
    if payload.get("packet_status") not in {None, "ready"} or payload.get("blockers"):
        return "inspect"
    if payload.get("mode", "execute") == "execute" and "CLAIM_OWNED" in _failed_check_codes(payload):
        return "start-work"
    return str(payload.get("next_step_type") or "inspect")


def _agent_display_commands(payload: dict[str, Any]) -> list[str]:
    commands = [str(item) for item in payload.get("next_allowed_commands") or []]
    decision_guide = _decision_guide_command(payload)
    decision_handoff = _decision_handoff_command(payload)
    if decision_guide or decision_handoff:
        visible = [decision_handoff or decision_guide, decision_guide]
        visible.extend(
            command
            for command in commands
            if palari_command_parts(command)[:2] != ("agent", "advance")
        )
        return list(dict.fromkeys(command for command in visible if command))

    blocked = payload.get("packet_status") not in {None, "ready"} or bool(
        payload.get("blockers")
    )
    if blocked:
        return [
            command
            for command in commands
            if _is_read_only_handoff_command(command)
        ]

    if payload.get("mode", "execute") == "execute" and "CLAIM_OWNED" in _failed_check_codes(payload):
        start = next(
            (
                str(item.get("next_command") or "")
                for collection in (
                    payload.get("checks") or [],
                    payload.get("missing_requirements") or [],
                )
                for item in collection
                if item.get("code") == "CLAIM_OWNED"
                and palari_command_parts(
                    str(item.get("next_command") or "")
                )[:2]
                == ("agent", "start")
            ),
            "",
        )
        if start and start not in commands:
            commands.insert(0, start)
        elif start:
            commands.remove(start)
            commands.insert(0, start)
    return commands


def _payload_command(payload: dict[str, Any], *arguments: str) -> str:
    workspace_file = str(payload.get("workspace_file") or "")
    if workspace_file:
        return palari_workspace_command(workspace_file, *arguments)
    return " ".join(("palari", *arguments))


def _display_report_guidance(payload: dict[str, Any], guidance: Any) -> str:
    if (
        payload.get("mode") == "execute"
        and "CLAIM_OWNED" in _failed_check_codes(payload)
    ):
        return _start_work_guidance()
    if payload.get("mode") == "review" and payload.get("status") in {
        "missing-proof",
        "blocked",
    }:
        return _review_wait_guidance()
    return plain_message(guidance)


def _review_wait_guidance() -> str:
    return (
        "Return this task to its builder and wait for current checks before reviewing."
    )


def _start_work_guidance() -> str:
    return "Start or continue this task before running its checks."
