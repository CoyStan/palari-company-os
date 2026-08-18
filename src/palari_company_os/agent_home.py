from __future__ import annotations
from typing import Any
from .agent_next import build_agent_next
from .workspace import Workspace
def build_agent_home(workspace: Workspace, palari_id: str) -> dict[str, Any]:
    agent = workspace.palari(palari_id)
    view = build_agent_next(workspace, palari_id, "execute", 4)
    candidates = list(view.get("candidates") or [])
    now = [item for item in candidates if _owned_claim(item, palari_id)]
    available = [item for item in candidates if not _owned_claim(item, palari_id)]
    goals = [workspace.goal(goal_id) for goal_id in agent.linked_goals] if agent else []
    work_ids = {work.id for work in workspace.work_items if agent and work.palari == agent.id}
    outcomes = [item for item in workspace.outcomes if item.work_item_id in work_ids][-3:]
    projects = [item for item in workspace.workbenches if agent and agent.id in item.palari_ids]
    ideas = [item for item in workspace.proposals if agent and item.palari == agent.id]
    runs = [item for item in workspace.attempts if agent and item.actor == agent.id][-3:]
    blockers = list(view.get("blockers") or []) + [blocker for item in candidates
                                                    for blocker in item.get("start_blockers") or []]
    components = {
        "goals": {"scope": agent.scope if agent else "", "items": [{"id": goal.id,
                  "title": goal.title, "success": goal.success_criteria} for goal in goals if goal]},
        "team": ({"id": agent.id, "name": agent.name, "role": agent.role, "owner": agent.owner_human}
                 if agent else {}),
        "work": {
            "projects": [{"id": item.id, "name": item.label} for item in projects],
            "ideas": [{"id": item.id, "name": item.title, "status": item.status} for item in ideas],
            "tasks": {"now": [_initiative(item) for item in now[:3]], "next": _initiative(available[0])
                      if available else None, "later": [_initiative(item) for item in available[1:3]]},
            "runs": [{"id": item.id, "status": item.status} for item in runs]},
        "checks": {"records": _records(workspace.receipts, work_ids),
                   "tests": _records(workspace.evidence_runs, work_ids),
                   "reviews": _records(workspace.review_verdicts, work_ids),
                   "choices": _records([*workspace.decisions, *workspace.human_decisions], work_ids),
                   "results": [{"id": item.id, "summary": item.summary, "change": item.what_changed}
                               for item in outcomes]},
        "limits": {
            "sources": {"read": list(agent.allowed_inputs) if agent else [], "saved":
                        list(agent.memory_sources) if agent else []},
            "guides": {"items": list(agent.standards) if agent else []},
            "tools": {"commands": list(view.get("next_allowed_commands") or [])},
            "rules": {"allowed": {"grants_permission": False, "rule": "Start a ready task before writing."},
                      "ask": blockers, "never": {"actions": [*(agent.forbidden_actions if agent else []),
                      "write without a current task brief", "perform a human approval"],
                      "inputs": list(agent.forbidden_inputs) if agent else []}},
            "outside": {"apps": [{"id": item.id, "on": item.enabled} for item in workspace.integrations],
                        "plans": _records(workspace.integration_plans, work_ids),
                        "queue": _records(workspace.integration_outbox, work_ids)}}}
    return {"schema_version": "palari.agent_home.v2", "workspace": workspace.name, "status": "blocked"
            if not agent else "working" if now else "ready" if available else "waiting",
            "agent": {"id": palari_id, "found": agent is not None}, "components": components,
            "next_allowed_commands": list(view.get("next_allowed_commands") or [])}
def _owned_claim(candidate: dict[str, Any], palari_id: str) -> bool:
    claim = candidate.get("claim") or {}
    return bool(claim.get("active") and claim.get("claimed_by") == palari_id)
def _initiative(candidate: dict[str, Any]) -> dict[str, Any]:
    keys = ("work_item_id", "title", "attention", "next_step_type", "next_command")
    return {key: candidate.get(key, "") for key in keys}
def _records(items: list[Any], work_ids: set[str]) -> list[dict[str, Any]]:
    return [{"id": item.id, "status": getattr(item, "status", "")} for item in items
            if getattr(item, "work_item_id", getattr(item, "linked_work", "")) in work_ids][-3:]
