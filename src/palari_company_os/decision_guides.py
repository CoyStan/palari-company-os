from __future__ import annotations

from datetime import datetime, timezone
from shlex import quote
from typing import Any

from .read_models import detail
from .workspace import Workspace


def build_decision_guide(workspace: Workspace, target_id: str) -> dict[str, Any]:
    decision = _resolve_decision(workspace, target_id)
    work_detail = detail(workspace, decision.linked_work) if decision.linked_work else None
    return {
        "schema_version": "palari.decision_guide.v1",
        "guide_id": f"DECISION-GUIDE-{decision.id}-V1",
        "created_at": _timestamp(),
        "workspace": workspace.name,
        "would_mutate": False,
        "status": decision.status,
        "decision": _decision_summary(decision),
        "required_human": _human_summary(workspace, decision.required_human),
        "linked_work": _work_summary(work_detail),
        "goal": _compact(work_detail.get("goal") if work_detail else None, ["id", "title", "owner"]),
        "palari": _compact(
            work_detail.get("palari") if work_detail else None,
            ["id", "name", "role", "owner_human"],
        ),
        "workbench": _compact(
            work_detail.get("workbench") if work_detail else None,
            ["id", "label", "summary", "status"],
        ),
        "attention": work_detail.get("attention", "") if work_detail else "",
        "why": work_detail.get("why", "") if work_detail else "",
        "next_action": work_detail.get("next_action", "") if work_detail else "",
        "decision_focus": _decision_focus(decision, work_detail),
        "suggested_results": _suggested_results(decision),
        "decision_update_command_template": _decision_update_command_template(decision),
        "decision_update_commands": _decision_update_commands(decision),
        "next_commands": _next_commands(decision),
        "omitted_context": [
            {
                "kind": "workspace_records",
                "reason": "Decision guide v1 includes only the target decision and directly linked work context.",
                "counts": {
                    "decisions": len(workspace.decisions),
                    "work_items": len(workspace.work_items),
                    "palaris": len(workspace.palaris),
                    "humans": len(workspace.humans),
                },
            }
        ],
    }


def _resolve_decision(workspace: Workspace, target_id: str) -> Any:
    for decision in workspace.decisions:
        if decision.id == target_id:
            return decision
    work = workspace.work_item(target_id)
    if work is not None:
        for decision in workspace.decisions:
            if decision.linked_work == work.id and decision.status == "open":
                return decision
        for decision in workspace.decisions:
            if decision.linked_work == work.id:
                return decision
    known = ", ".join(sorted(decision.id for decision in workspace.decisions))
    raise KeyError(f"unknown decision or linked work {target_id}; known decisions: {known}")


def _decision_summary(decision: Any) -> dict[str, Any]:
    return {
        "id": decision.id,
        "question": decision.question,
        "status": decision.status,
        "context": decision.context,
        "options": decision.options,
        "tradeoffs": decision.tradeoffs,
        "recommendation": decision.recommendation,
        "safe_default": decision.safe_default,
        "required_human": decision.required_human,
        "required_role": decision.required_role,
        "due_date": decision.due_date,
        "linked_goal": decision.linked_goal,
        "linked_work": decision.linked_work,
        "linked_palari": decision.linked_palari,
        "result": decision.result,
    }


def _human_summary(workspace: Workspace, human_id: str) -> dict[str, Any]:
    human = workspace.human(human_id) if human_id else None
    if human is None:
        return {"id": human_id, "found": False}
    return {
        "id": human.id,
        "found": True,
        "name": human.name,
        "role": human.role,
        "authority_level": human.authority_level,
        "approval_capabilities": human.approval_capabilities,
    }


def _work_summary(work_detail: dict[str, Any] | None) -> dict[str, Any]:
    if work_detail is None:
        return {}
    work = work_detail["work_item"]
    return {
        "id": work["id"],
        "title": work["title"],
        "risk": work["risk"],
        "status": work["status"],
        "scope": work.get("scope", ""),
        "acceptance_target": work.get("acceptance_target", ""),
        "forbidden_actions": work.get("forbidden_actions", []),
        "safety": work_detail.get("safety", {}),
    }


def _decision_focus(decision: Any, work_detail: dict[str, Any] | None) -> list[str]:
    focus = [
        "Answer the decision question explicitly, or keep the safe default if the answer is not ready.",
        "Compare the listed options, tradeoffs, recommendation, and safe default before deciding.",
    ]
    work = work_detail.get("work_item") if work_detail else None
    if work and work.get("forbidden_actions"):
        focus.append("Confirm the decision does not authorize forbidden actions without a new scoped change.")
    if decision.required_human:
        focus.append(f"Decision authority is expected from {decision.required_human}.")
    if decision.status != "open":
        focus.append("Decision is not open; verify whether the recorded result still reflects current intent.")
    return focus


def _suggested_results(decision: Any) -> list[str]:
    results = list(decision.options)
    results.extend(["defer", "block"])
    return results


def _decision_update_command_template(decision: Any) -> str:
    return f'palari decision update {decision.id} --status decided --set "result=..." --json'


def _decision_update_commands(decision: Any) -> list[dict[str, str]]:
    return [
        {
            "result": result,
            "command": _decision_update_command(decision, result),
        }
        for result in _suggested_results(decision)
    ]


def _decision_update_command(decision: Any, result: str) -> str:
    return (
        f"palari decision update {decision.id} --status decided "
        f"--set {quote(f'result={result}')} --json"
    )


def _next_commands(decision: Any) -> list[str]:
    commands = [f"palari decision guide {decision.id} --json"]
    if decision.linked_work:
        commands.append(f"palari detail {decision.linked_work} --json")
    commands.append("palari validate --json")
    return commands


def _compact(record: dict[str, Any] | None, keys: list[str]) -> dict[str, Any]:
    if not record:
        return {}
    return {key: record.get(key, "") for key in keys}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
