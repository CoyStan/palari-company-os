from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_packets import build_agent_brief
from .read_models import queue_items
from .workspace import Workspace


AGENT_STARTABLE_ATTENTIONS = {"ready-for-ai-work", "needs-evidence", "changes-requested"}


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
    next_commands = _all_next_commands(agents, mode)
    return {
        "schema_version": "palari.agent_next_all.v1",
        "created_at": _timestamp(),
        "workspace": workspace.name,
        "status": "ready" if ready_count else "no-ready-work",
        "mode": mode or "execute",
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "agents": agents,
        "next_allowed_commands": next_commands,
        "omitted_context": [_omitted_context(workspace)],
    }


def _candidates(workspace: Workspace, palari_id: str, mode: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for rank, item in enumerate(queue_items(workspace), start=1):
        work = workspace.work_item(item.id)
        if work is None or not _palari_can_see_work(workspace, work, palari_id):
            continue
        packet = build_agent_brief(workspace, work.id, palari_id, mode)
        blockers = packet.get("blockers", [])
        can_start = _can_start_agent_work(item, packet)
        start_blockers = _start_blockers(item, packet)
        next_command = (
            f"palari agent brief {work.id} --as {palari_id} --mode {mode} --json"
            if can_start
            else item.next_commands[0]
        )
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
                "blocker_codes": [blocker.get("code", "") for blocker in blockers],
                "start_blocker_codes": [blocker["code"] for blocker in start_blockers],
                "start_blockers": start_blockers,
                "next_command": next_command,
                "next_commands": item.next_commands,
                "brief_command": (
                    f"palari agent brief {work.id} --as {palari_id} --mode {mode} --json"
                ),
                "check_command": f"palari agent check {work.id} --as {palari_id} --json",
            }
        )
    return candidates


def _can_start_agent_work(item: Any, packet: dict[str, Any]) -> bool:
    return (
        packet.get("status") == "ready"
        and item.ai_safe_to_proceed
        and item.attention in AGENT_STARTABLE_ATTENTIONS
    )


def _start_blockers(item: Any, packet: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if packet.get("status") != "ready":
        blockers.append(
            {
                "code": "PACKET_BLOCKED",
                "message": "The agent packet is blocked; inspect blocker_codes before starting.",
            }
        )
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
            return [candidate["brief_command"], candidate["check_command"]]
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
    for agent in agents:
        if agent["ready_count"]:
            agent_id = agent["agent"]["id"]
            return [f"palari agent next --as {agent_id} --mode {mode} --json"]
    for agent in agents:
        commands = agent.get("next_allowed_commands") or []
        if commands:
            return commands
    return ["palari queue --json", "palari validate --json"]


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
