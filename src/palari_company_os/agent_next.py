from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_finish import build_agent_finish
from .agent_packets import build_agent_brief
from .read_models import queue_items
from .workspace import Workspace


AGENT_STARTABLE_ATTENTIONS = {"ready-for-ai-work", "needs-evidence", "changes-requested"}
AGENT_REVIEWABLE_ATTENTIONS = {"needs-review", "receipt-ready"}


def build_agent_next(
    workspace: Workspace,
    palari_id: str,
    mode: str = "execute",
    limit: int = 5,
) -> dict[str, Any]:
    palari = workspace.palari(palari_id)
    if palari is None:
        return {
            "schema_version": "palari.agent_next.v1",
            "created_at": _timestamp(),
            "workspace": workspace.name,
            "status": "blocked",
            "agent": {"id": palari_id, "found": False},
            "mode": mode or "execute",
            "ready_count": 0,
            "blocked_count": 0,
            "candidates": [],
            "blockers": [
                {
                    "code": "MISSING_PALARI",
                    "message": f"Palari not found: {palari_id}",
                    "human_visible": True,
                }
            ],
            "next_allowed_commands": ["palari queue --json", "palari validate --json"],
            "omitted_context": [_omitted_context(workspace)],
        }

    candidates = _candidates(workspace, palari_id, mode or "execute")
    ordered = sorted(candidates, key=lambda item: (not item["can_start"], item["queue_rank"]))
    safe_limit = max(1, limit)
    selected = ordered[:safe_limit]
    ready_count = sum(1 for item in candidates if item["can_start"])
    blocked_count = len(candidates) - ready_count
    return {
        "schema_version": "palari.agent_next.v1",
        "created_at": _timestamp(),
        "workspace": workspace.name,
        "status": "ready" if ready_count else "no-ready-work",
        "agent": {
            "id": palari.id,
            "name": palari.name,
            "role": palari.role,
            "found": True,
        },
        "mode": mode or "execute",
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "candidates": selected,
        "blockers": [] if ready_count else _no_ready_blockers(candidates),
        "next_allowed_commands": _next_commands(selected, palari_id, mode or "execute"),
        "omitted_context": [_omitted_context(workspace)],
    }


def build_agent_next_all(workspace: Workspace, mode: str = "execute", limit: int = 5) -> dict[str, Any]:
    agents = [build_agent_next(workspace, palari.id, mode, limit) for palari in workspace.palaris]
    ready_count = sum(agent["ready_count"] for agent in agents)
    blocked_count = sum(agent["blocked_count"] for agent in agents)
    top_candidate = _all_top_candidate(agents)
    next_commands = _all_next_commands(agents, mode)
    return {
        "schema_version": "palari.agent_next_all.v1",
        "created_at": _timestamp(),
        "workspace": workspace.name,
        "status": "ready" if ready_count else "no-ready-work",
        "mode": mode or "execute",
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "top_candidate": top_candidate,
        "agents": agents,
        "next_allowed_commands": next_commands,
        "omitted_context": [_omitted_context(workspace)],
    }


def _candidates(workspace: Workspace, palari_id: str, mode: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for rank, item in enumerate(queue_items(workspace), start=1):
        if item.attention == "closed":
            continue
        work = workspace.work_item(item.id)
        if work is None or not _palari_can_see_work(workspace, work, palari_id):
            continue
        packet = build_agent_brief(workspace, work.id, palari_id, mode)
        blockers = packet.get("blockers", [])
        can_start = _can_start_agent_work(item, packet, mode)
        start_blockers = _start_blockers(item, packet, mode)
        brief_command = f"palari agent brief {work.id} --as {palari_id} --mode {mode} --json"
        check_command = _check_command(work.id, palari_id, mode)
        blocker_codes = [blocker.get("code", "") for blocker in blockers]
        finish = build_agent_finish(workspace, work.id, palari_id, mode)
        handoff_guidance = finish.get("handoff_guidance", [])
        finish_commands = (
            finish.get("next_allowed_commands", [])
            if "HUMAN_DECISION_REQUIRED" in blocker_codes and not handoff_guidance
            else []
        )
        next_command = _candidate_next_command(
            item,
            can_start,
            brief_command,
            handoff_guidance,
            finish_commands,
        )
        doctor_command = _doctor_command(work.id, palari_id, mode)
        loop_command = _loop_command(work.id, palari_id, mode)
        candidates.append(
            {
                "queue_rank": rank,
                "work_item_id": work.id,
                "title": work.title,
                "risk": work.risk,
                "intensity": work.intensity,
                "status": work.status,
                "attention": item.attention,
                "why": item.why,
                "next_action": item.next_action,
                "workbench": {
                    "id": item.workbench,
                    "label": item.workbench_label,
                },
                "packet_status": packet.get("status", "blocked"),
                "can_start": can_start,
                "blocker_codes": blocker_codes,
                "start_blocker_codes": [blocker["code"] for blocker in start_blockers],
                "start_blockers": start_blockers,
                "handoff_guidance": handoff_guidance,
                "next_step_type": item.next_step_type,
                "next_command": next_command,
                "doctor_command": doctor_command,
                "loop_command": loop_command,
                "next_commands": _candidate_next_commands(
                    item,
                    can_start,
                    brief_command,
                    check_command,
                    handoff_guidance,
                    finish_commands,
                    next_command,
                    doctor_command,
                    loop_command,
                    mode,
                ),
                "brief_command": brief_command,
                "check_command": check_command,
            }
        )
    return candidates


def _candidate_next_command(
    item: Any,
    can_start: bool,
    brief_command: str,
    handoff_guidance: list[dict[str, str]],
    finish_commands: list[str],
) -> str:
    if can_start and item.next_step_type == "check-active-proof":
        return item.next_commands[0] if item.next_commands else brief_command
    if can_start:
        return brief_command
    if handoff_guidance:
        return handoff_guidance[0]["command"]
    if finish_commands:
        return finish_commands[0]
    return item.next_commands[0]


def _candidate_next_commands(
    item: Any,
    can_start: bool,
    brief_command: str,
    check_command: str,
    handoff_guidance: list[dict[str, str]],
    finish_commands: list[str],
    next_command: str,
    doctor_command: str,
    loop_command: str,
    mode: str,
) -> list[str]:
    if can_start and item.next_step_type == "check-active-proof":
        commands = list(item.next_commands or [next_command, check_command])
        _append_once(commands, doctor_command)
        _append_once(commands, loop_command)
        return commands
    if can_start and mode == "review":
        return [
            brief_command,
            f"palari review guide {item.id} --json",
            check_command,
            doctor_command,
            loop_command,
        ]
    if can_start:
        return [brief_command, check_command, doctor_command, loop_command]
    if handoff_guidance:
        commands = [next_command]
        for guidance in handoff_guidance:
            _append_once(commands, guidance.get("guide_command", ""))
        for command in item.next_commands:
            _append_once(commands, command)
        _append_once(commands, doctor_command)
        _append_once(commands, loop_command)
        return commands
    commands = list(finish_commands or item.next_commands)
    _append_once(commands, doctor_command)
    _append_once(commands, loop_command)
    return commands


def _can_start_agent_work(item: Any, packet: dict[str, Any], mode: str) -> bool:
    if mode == "review":
        return packet.get("status") == "ready" and item.attention in AGENT_REVIEWABLE_ATTENTIONS
    return (
        packet.get("status") == "ready"
        and item.ai_safe_to_proceed
        and item.attention in AGENT_STARTABLE_ATTENTIONS
    )


def _start_blockers(item: Any, packet: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if packet.get("status") != "ready":
        blockers.append(
            {
                "code": "PACKET_BLOCKED",
                "message": "The agent packet is blocked; inspect blocker_codes before starting.",
            }
        )
    if mode == "review":
        if item.attention not in AGENT_REVIEWABLE_ATTENTIONS:
            blockers.append(
                {
                    "code": "ATTENTION_NOT_REVIEWABLE",
                    "message": (
                        f"Current attention state is {item.attention}; review mode is for "
                        "needs-review or receipt-ready work."
                    ),
                }
            )
        return blockers
    if not item.ai_safe_to_proceed:
        blockers.append(
            {
                "code": "QUEUE_NOT_AI_SAFE",
                "message": "The queue does not mark this work safe for autonomous AI execution.",
            }
        )
    if item.attention not in AGENT_STARTABLE_ATTENTIONS:
        blockers.append(
            {
                "code": "ATTENTION_NOT_STARTABLE",
                "message": f"Current attention state is {item.attention}; follow next_action instead.",
            }
        )
    return blockers


def _check_command(work_id: str, palari_id: str, mode: str) -> str:
    return f"palari agent check {work_id} --as {palari_id} --mode {mode} --json"


def _doctor_command(work_id: str, palari_id: str, mode: str) -> str:
    return f"palari agent doctor {work_id} --as {palari_id} --mode {mode} --json"


def _loop_command(work_id: str, palari_id: str, mode: str) -> str:
    return f"palari agent loop {work_id} --as {palari_id} --mode {mode} --json"


def _palari_can_see_work(workspace: Workspace, work: Any, palari_id: str) -> bool:
    if work.palari == palari_id:
        return True
    if not work.workbench_id:
        return False
    workbench = workspace.workbench(work.workbench_id)
    return bool(workbench and palari_id in workbench.palari_ids)


def _no_ready_blockers(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not candidates:
        return [
            {
                "code": "NO_ASSIGNED_WORK",
                "message": "No visible work items are assigned to or workbench-allowed for this Palari.",
                "human_visible": True,
            }
        ]
    return [
        {
            "code": "NO_READY_WORK",
            "message": "Visible work exists, but none is currently safe to start.",
            "human_visible": True,
        }
    ]


def _next_commands(candidates: list[dict[str, Any]], palari_id: str, mode: str) -> list[str]:
    for candidate in candidates:
        if candidate["can_start"]:
            return _candidate_commands(candidate)
    if candidates:
        first = candidates[0]
        return first.get("next_commands") or [
            f"palari detail {first['work_item_id']} --json",
            "palari queue --json",
            "palari validate --json",
        ]
    return [
        f"palari agent next --as {palari_id} --mode {mode} --json",
        "palari queue --json",
        "palari validate --json",
    ]


def _all_next_commands(agents: list[dict[str, Any]], mode: str) -> list[str]:
    top = _all_top_candidate(agents)
    if top:
        candidate = top["candidate"]
        if candidate["can_start"]:
            return _candidate_commands(candidate)
        return candidate.get("next_commands") or [
            f"palari detail {candidate['work_item_id']} --json",
            "palari queue --json",
            "palari validate --json",
        ]
    for agent in agents:
        if agent["ready_count"]:
            agent_id = agent["agent"]["id"]
            return [f"palari agent next --as {agent_id} --mode {mode} --json"]
    for agent in agents:
        commands = agent.get("next_allowed_commands") or []
        if commands:
            return commands
    return ["palari queue --json", "palari validate --json"]


def _candidate_commands(candidate: dict[str, Any]) -> list[str]:
    if candidate.get("next_commands"):
        return list(candidate["next_commands"])
    if candidate["next_command"] != candidate["brief_command"]:
        return candidate.get("next_commands") or [
            candidate["next_command"],
            candidate["check_command"],
        ]
    return [candidate["brief_command"], candidate["check_command"]]


def _append_once(commands: list[str], command: str) -> None:
    if command and command not in commands:
        commands.append(command)


def _all_top_candidate(agents: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        {
            "agent": agent.get("agent", {}),
            "candidate": candidate,
        }
        for agent in agents
        for candidate in agent.get("candidates", [])
    ]
    ready_candidates = [item for item in candidates if item["candidate"]["can_start"]]
    if ready_candidates:
        return sorted(ready_candidates, key=lambda item: item["candidate"]["queue_rank"])[0]
    if candidates:
        return sorted(candidates, key=lambda item: item["candidate"]["queue_rank"])[0]
    return None


def _omitted_context(workspace: Workspace) -> dict[str, Any]:
    return {
        "kind": "workspace_records",
        "reason": "Agent next v1 includes compact queue candidates, not full workspace records.",
        "counts": {
            "work_items": len(workspace.work_items),
            "palaris": len(workspace.palaris),
            "workbenches": len(workspace.workbenches),
            "sources": len(workspace.sources),
        },
    }


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
