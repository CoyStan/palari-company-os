from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .authority_plan import build_authority_plan
from .agent_finish import build_agent_finish
from .agent_operation import AgentOperation, ensure_agent_operation
from .decision_guides import build_decision_guide
from .command_surface import (
    bind_palari_workspace_command,
    palari_command_parts,
    palari_workspace_command,
)
from .read_models import detail
from .review_guides import build_review_guide
from .transition_checks import check_transition
from .workspace import Workspace, WorkspaceError
from .workspace_read_models import approval_inbox


def simple_approval_offer_for_human(
    workspace: Workspace,
    work_id: str,
    human_id: str,
) -> dict[str, str] | None:
    """Return one exact presentation-bound approve offer for ``human_id``, if any.

    Reuses the same Approval Pack / simple-approval command compilation as
    agent handoff. Returns ``None`` when the task is not eligible for a
    one-click reversible-local approval by that human.
    """
    handoff = _human_approval_handoff(workspace, work_id)
    pack = handoff.get("approval_pack") or {}
    if not pack.get("available"):
        return None
    for command in pack.get("simple_approval_commands") or []:
        if str(command.get("human_id") or "") != human_id:
            continue
        digest = str(command.get("presentation_digest") or "")
        if not digest:
            return None
        return {
            "work_id": work_id,
            "human_id": human_id,
            "presentation_digest": digest,
        }
    return None


def build_agent_handoff(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    *,
    operation: AgentOperation | None = None,
) -> dict[str, Any]:
    operation_state = ensure_agent_operation(
        workspace,
        work_id,
        palari_id,
        mode,
        operation=operation,
    )
    finish = build_agent_finish(
        workspace,
        work_id,
        palari_id,
        mode,
        operation=operation_state,
    )
    guidance_codes = {item.get("code", "") for item in finish.get("handoff_guidance", [])}
    has_linked_decision = _has_linked_decision(workspace, work_id)
    decision_requested = "DECISION_HANDOFF" in guidance_codes or (
        "HUMAN_APPROVAL_HANDOFF" in guidance_codes and has_linked_decision
    )
    human_approval_requested = (
        "HUMAN_APPROVAL_HANDOFF" in guidance_codes and not has_linked_decision
    )
    review_handoff = (
        _review_handoff(workspace, work_id) if "REVIEW_HANDOFF" in guidance_codes else None
    )
    decision_handoff = _decision_handoff(workspace, work_id) if decision_requested else None
    human_approval_handoff = (
        _human_approval_handoff(
            workspace,
            work_id,
        )
        if human_approval_requested
        else None
    )
    human_action_commands = _human_action_commands(
        review_handoff,
        decision_handoff,
        human_approval_handoff,
    )
    agent_action_commands = _agent_action_commands(review_handoff)
    return {
        "schema_version": "palari.agent_handoff.v1",
        "handoff_id": _handoff_id(work_id, palari_id, mode),
        "created_at": _timestamp(),
        "workspace": finish.get("workspace", workspace.name),
        "workspace_file": str(workspace.data_path),
        "would_mutate": False,
        "mode": mode or "execute",
        "status": finish.get("status", "blocked"),
        "handoff_available": bool(review_handoff or decision_handoff or human_approval_handoff),
        "handoff_types": _handoff_types(review_handoff, decision_handoff, human_approval_handoff),
        "next_step_type": finish.get("next_step_type", "inspect"),
        "agent": finish.get("agent", {}),
        "work_item": finish.get("work_item", {}),
        "finish": _finish_summary(finish),
        "review_handoff": review_handoff,
        "decision_handoff": decision_handoff,
        "human_approval_handoff": human_approval_handoff,
        "resolution_summary": finish.get("resolution_summary", {}),
        "next_allowed_commands": _agent_safe_commands(
            workspace,
            finish,
            review_handoff,
            decision_handoff,
            human_approval_handoff,
        ),
        "human_action_commands": human_action_commands,
        "human_action_boundary": _human_action_boundary(human_action_commands),
        "agent_action_commands": agent_action_commands,
        "agent_action_boundary": _agent_action_boundary(agent_action_commands),
        "omitted_context": [
            {
                "kind": "workspace_records",
                "reason": "The handoff includes finish guidance and only the relevant human review or approval context.",
                "counts": {
                    "work_items": len(workspace.work_items),
                    "decisions": len(workspace.decisions),
                    "review_verdicts": len(workspace.review_verdicts),
                    "human_decisions": len(workspace.human_decisions),
                },
            }
        ],
    }


def _review_handoff(workspace: Workspace, work_id: str) -> dict[str, Any]:
    guide = build_review_guide(workspace, work_id)
    return {
        "schema_version": guide["schema_version"],
        "guide_id": guide["guide_id"],
        "command": palari_workspace_command(
            workspace.data_path,
            "review",
            "guide",
            work_id,
            "--json",
        ),
        "status": guide["status"],
        "attention": guide.get("attention", ""),
        "why": guide.get("why", ""),
        "next_action": guide.get("next_action", ""),
        "work_item": guide["work_item"],
        "evidence": _pick(
            guide.get("evidence", {}),
            ["present", "id", "status", "head_sha", "summary"],
        ),
        "attempt": _pick(
            guide.get("attempt", {}),
            ["present", "id", "actor", "status", "result"],
        ),
        "receipt": _pick(
            guide.get("receipt", {}),
            [
                "present",
                "id",
                "sources_used",
                "outputs_created",
                "external_writes",
                "not_done",
                "undo_refs",
            ],
        ),
        "review_focus": guide.get("review_focus", []),
        "reviewer_candidates": guide.get("reviewer_candidates", []),
        "review_record_commands": guide.get("review_record_commands", []),
        "suggested_verdicts": guide.get("suggested_verdicts", []),
    }


def _decision_handoff(workspace: Workspace, work_id: str) -> dict[str, Any]:
    guide = build_decision_guide(workspace, work_id)
    decision_update_commands = [
        {
            **item,
            "command": bind_palari_workspace_command(
                workspace.data_path,
                str(item.get("command") or ""),
            ),
        }
        for item in guide.get("decision_update_commands", [])
    ]
    return {
        "schema_version": guide["schema_version"],
        "guide_id": guide["guide_id"],
        "command": palari_workspace_command(
            workspace.data_path,
            "decision",
            "guide",
            str(guide["decision"]["id"]),
            "--json",
        ),
        "status": guide["status"],
        "attention": guide.get("attention", ""),
        "why": guide.get("why", ""),
        "next_action": guide.get("next_action", ""),
        "decision": _pick(
            guide["decision"],
            [
                "id",
                "question",
                "status",
                "options",
                "recommendation",
                "safe_default",
                "required_human",
                "result",
            ],
        ),
        "required_human": guide.get("required_human", {}),
        "linked_work": guide.get("linked_work", {}),
        "decision_focus": guide.get("decision_focus", []),
        "suggested_results": guide.get("suggested_results", []),
        "decision_update_commands": decision_update_commands,
    }


def _has_linked_decision(workspace: Workspace, work_id: str) -> bool:
    return any(
        decision.linked_work == work_id and decision.status == "open"
        for decision in workspace.decisions
    )


def _human_approval_handoff(
    workspace: Workspace,
    work_id: str,
) -> dict[str, Any]:
    payload = detail(workspace, work_id)
    work = payload["work_item"]
    evidence = payload.get("evidence") or {}
    review = payload.get("review") or {}
    attempt = payload.get("attempt") or {}
    required_capability = work.get("required_approval_capability", "")
    authority_plan = build_authority_plan(
        workspace,
        work_id,
        builder_id=str(attempt.get("actor") or ""),
        reviewer_id=str(review.get("reviewer") or ""),
    )
    candidates = _approval_candidates(
        workspace,
        authority_plan,
    )
    reviewed_head = review.get("reviewed_head") or evidence.get("head_sha") or _attempt_head(attempt)
    approval_pack = _approval_pack_handoff(
        workspace,
        work_id,
        candidates,
        authority_plan,
        str(reviewed_head),
    )
    command = (
        str(approval_pack["inbox_command"])
        if approval_pack.get("available")
        else palari_workspace_command(
            workspace.data_path,
            "detail",
            work_id,
            "--json",
        )
    )
    return {
        "schema_version": "palari.human_approval_handoff.v1",
        "guide_id": f"HUMAN-APPROVAL-{_safe_id(work_id)}-V1",
        "command": command,
        "status": payload.get("attention", ""),
        "attention": payload.get("attention", ""),
        "why": payload.get("why", ""),
        "next_action": payload.get("next_action", ""),
        "approval_progress": payload.get("safety", {}).get("approval_progress", ""),
        "required_approval_count": work.get("required_approval_count", 0),
        "effective_final_approval_count": authority_plan[
            "effective_final_approval_count"
        ],
        "required_approval_capability": required_capability,
        "authority_plan": authority_plan,
        "reviewed_head": reviewed_head,
        "work_item": _pick(
            work,
            [
                "id",
                "title",
                "risk",
                "status",
                "scope",
                "acceptance_target",
                "forbidden_actions",
            ],
        ),
        "evidence": _pick(evidence, ["id", "status", "head_sha", "summary"]),
        "review": _pick(review, ["id", "reviewer", "verdict", "reviewed_head", "residual_risks"]),
        "attempt": _pick(attempt, ["id", "actor", "status", "result"]),
        "approval_candidates": candidates,
        "approval_focus": _approval_focus(payload),
        "approval_pack": approval_pack,
    }


def _finish_summary(finish: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": finish["schema_version"],
        "finish_id": finish["finish_id"],
        "packet_id": finish.get("packet_id", ""),
        "packet_context_hash": finish.get("packet_context_hash", ""),
        "check_id": finish.get("check_id", ""),
        "status": finish["status"],
        "can_finish": finish["can_finish"],
        "handoff_ready": finish["handoff_ready"],
        "report_guidance": finish["report_guidance"],
        "handoff_guidance": finish.get("handoff_guidance", []),
        "missing_requirements": finish.get("missing_requirements", []),
        "completed_requirements": finish.get("completed_requirements", []),
        "blockers": finish.get("blockers", []),
        "resolution_summary": finish.get("resolution_summary", {}),
    }


def _handoff_types(
    review_handoff: dict[str, Any] | None,
    decision_handoff: dict[str, Any] | None,
    human_approval_handoff: dict[str, Any] | None,
) -> list[str]:
    types: list[str] = []
    if review_handoff is not None:
        types.append("review")
    if decision_handoff is not None:
        types.append("decision")
    if human_approval_handoff is not None:
        types.append("human-approval")
    return types


def _agent_safe_commands(
    workspace: Workspace,
    finish: dict[str, Any],
    review_handoff: dict[str, Any] | None,
    decision_handoff: dict[str, Any] | None,
    human_approval_handoff: dict[str, Any] | None,
) -> list[str]:
    commands: list[str] = []
    has_handoff = bool(review_handoff or decision_handoff or human_approval_handoff)
    if review_handoff is not None:
        _append_once(commands, review_handoff["command"])
    if decision_handoff is not None:
        _append_once(commands, decision_handoff["command"])
    if human_approval_handoff is not None:
        _append_once(commands, human_approval_handoff["command"])
    for command in finish.get("next_allowed_commands", []):
        bound = bind_palari_workspace_command(
            workspace.data_path,
            str(command),
        )
        if not has_handoff or _is_read_only_command(bound):
            _append_once(commands, bound)
    _append_once(
        commands,
        palari_workspace_command(workspace.data_path, "validate", "--json"),
    )
    return commands


def _is_read_only_command(command: str) -> bool:
    parts = palari_command_parts(command)
    if not parts:
        return False
    return bool(
        parts[0] in {"detail", "queue", "validate"}
        or parts[:2] in {("review", "guide"), ("decision", "guide")}
    )


def _human_action_commands(
    review_handoff: dict[str, Any] | None,
    decision_handoff: dict[str, Any] | None,
    human_approval_handoff: dict[str, Any] | None,
) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    if review_handoff is not None:
        for item in review_handoff.get("review_record_commands", []):
            if item.get("identity_type") != "human":
                continue
            commands.append(
                {
                    "type": "review-record",
                    "actor": item.get("reviewer", ""),
                    "command": item.get("command", ""),
                }
            )
    if decision_handoff is not None:
        for item in decision_handoff.get("decision_update_commands", []):
            commands.append(
                {
                    "type": "decision-update",
                    "actor": decision_handoff.get("decision", {}).get("required_human", ""),
                    "result": item.get("result", ""),
                    "command": item.get("command", ""),
                }
            )
    if human_approval_handoff is not None:
        approval_pack = human_approval_handoff.get("approval_pack", {})
        for item in _pack_human_commands(approval_pack):
            commands.append(
                {
                    "type": item.get("type", "human-approval-record"),
                    "actor": item.get("human_id", ""),
                    "result": item.get("decision", ""),
                    "command": item.get("command", ""),
                }
            )
    return commands


def _agent_action_commands(
    review_handoff: dict[str, Any] | None,
) -> list[dict[str, str]]:
    if review_handoff is None:
        return []
    return [
        {
            "type": "palari-review-record",
            "actor": str(item.get("reviewer", "")),
            "command": str(item.get("command", "")),
            "packet_command": str(
                next(
                    (
                        candidate.get("review_packet_command", "")
                        for candidate in review_handoff.get("reviewer_candidates", [])
                        if candidate.get("id") == item.get("reviewer")
                    ),
                    "",
                )
            ),
        }
        for item in review_handoff.get("review_record_commands", [])
        if item.get("identity_type") == "palari"
    ]


def _human_action_boundary(human_action_commands: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "agent_may_execute": False,
        "agent_allowed_use": "Quote or summarize human-only commands for a human supervisor.",
        "human_only_command_fields": ["human_action_commands[].command"],
        "count": len(human_action_commands),
        "must_not": [
            "Do not run human action commands.",
            "Do not claim to be the required human actor.",
            "Do not convert a recommendation into human review, approval, or rejection.",
        ],
    }


def _agent_action_boundary(agent_action_commands: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "agent_may_execute": bool(agent_action_commands),
        "agent_action_command_fields": ["agent_action_commands[].command"],
        "count": len(agent_action_commands),
        "must": [
            "Open the named review task brief before recording a review result.",
            "The task-brief agent must match the command actor.",
        ],
        "must_not": [
            "Do not let the builder review its own run.",
            "Do not convert an agent review result into human approval.",
        ],
    }


def _pick(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload}


def _approval_candidates(
    workspace: Workspace,
    authority_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for human_id in authority_plan["qualified_approver_ids"]:
        human = workspace.human(str(human_id))
        if human is None:
            continue
        candidates.append(
            {
                "id": human.id,
                "name": human.name,
                "role": human.role,
                "authority_level": human.authority_level,
                "approval_capabilities": human.approval_capabilities,
            }
        )
    return candidates


def _approval_pack_handoff(
    workspace: Workspace,
    work_id: str,
    candidates: list[dict[str, Any]],
    authority_plan: dict[str, Any],
    reviewed_head: str,
) -> dict[str, Any]:
    inbox_command = palari_workspace_command(
        workspace.data_path,
        "queue",
        "--approval-inbox",
        "--select",
        work_id,
        "--json",
    )
    try:
        inbox = approval_inbox(
            workspace,
            selected_work_ids=(work_id,),
        )
    except WorkspaceError as exc:
        return {
            "available": False,
            "work_item_id": work_id,
            "mode": "blocked",
            "reason": str(exc),
            "next_safe_action": (
                "Repair or checkpoint journal continuity before rebuilding the "
                "exact presentation-bound Approval Pack."
            ),
        }
    item = next(
        (candidate for candidate in inbox["individual_items"] if candidate["id"] == work_id),
        None,
    )
    pack = inbox["packs"][0] if inbox["packs"] else None
    presentation = inbox["presentations"][0] if inbox["presentations"] else None
    candidate_ids = {str(candidate["id"]) for candidate in candidates}
    commands = [
        command
        for command in inbox["approval_commands"]
        if str(command.get("human_id") or "") in candidate_ids
        and (pack is None or command.get("pack_id") == pack.get("pack_id"))
    ]
    command = commands[0] if commands else None
    approval_mode = str(command.get("mode") or "") if command is not None else ""
    available = bool(
        authority_plan["viable"]
        and item
        and pack
        and commands
        and item.get("state") in {"eligible", "approved", "non-batchable"}
    )
    simple_commands = [
        {
            "human_id": str(candidate["id"]),
            "presentation_digest": str(
                command.get("presentation_digest", "") if command is not None else ""
            ),
            "command": palari_workspace_command(
                workspace.data_path,
                "approve",
                work_id,
                "--as",
                str(candidate["id"]),
                "--presented",
                str(command.get("presentation_digest", "") if command is not None else ""),
                "--json",
            ),
        }
        for candidate in candidates
        if available
        and check_transition(
            workspace,
            "work_accept",
            work_id,
            actor=str(candidate["id"]),
            context={"reviewed_head": reviewed_head},
        ).ok
    ]
    return {
        "available": available,
        "work_item_id": work_id,
        "mode": approval_mode if available else "blocked",
        "inbox_command": inbox_command,
        "pack_id": pack["pack_id"] if pack else "",
        "pack_digest": pack["pack_digest"] if pack else "",
        "presentation_digest": (
            command.get("presentation_digest", "") if command is not None else ""
        ),
        "presentation": presentation if presentation is not None else {},
        "item_state": item.get("state", "missing") if item else "missing",
        "reasons": item.get("reasons", []) if item else ["task is not in the inbox"],
        "approve_eligible_commands": [
            {
                "human_id": str(candidate["human_id"]),
                "command": str(candidate["command"]),
            }
            for candidate in commands
            if candidate.get("mode") == "approve-eligible"
        ],
        "simple_approval_commands": simple_commands,
        "approve_eligible_command": (
            command["command"]
            if command is not None
            and available
            and approval_mode == "approve-eligible"
            else ""
        ),
        "next_safe_action": (
            "A qualified human may run one exact presentation-bound simple approval command once."
            if available
            else (
                str(authority_plan["smallest_correction"])
                or "Repair the listed check or batching blockers, then rebuild the exact Approval Pack."
            )
        ),
    }


def _pack_human_commands(
    approval_pack: dict[str, Any],
) -> list[dict[str, str]]:
    commands = approval_pack.get("simple_approval_commands") or []
    if not approval_pack.get("available") or not commands:
        return []
    return [
        {
            "type": "simple-approval",
            "human_id": str(candidate["human_id"]),
            "decision": "approve",
            "command": str(candidate["command"]),
        }
        for candidate in commands
    ]


def _approval_focus(payload: dict[str, Any]) -> list[str]:
    focus = [
        "Inspect the task output, checks, review result, and residual risks before approving.",
        "Do not approve if required checks are missing or stale.",
    ]
    safety = payload.get("safety", {})
    if safety.get("receipt_state") != "ready":
        focus.append(
            f"Run-record status is {safety.get('receipt_state', 'unknown')}; "
            "require a run record if the completion rules ask for one."
        )
    work = payload.get("work_item", {})
    if work.get("forbidden_actions"):
        focus.append(
            "Confirm approval does not allow forbidden actions without a new task with explicit limits."
        )
    return focus


def _attempt_head(attempt: dict[str, Any]) -> str:
    if attempt.get("head_sha"):
        return str(attempt["head_sha"])
    commits = attempt.get("commits", [])
    return commits[-1] if commits else ""


def _append_once(commands: list[str], command: str) -> None:
    if command and command not in commands:
        commands.append(command)


def _handoff_id(work_id: str, palari_id: str, mode: str) -> str:
    return f"HANDOFF-{_safe_id(work_id)}-{_safe_id(palari_id)}-{_safe_id(mode).upper()}-V1"


def _safe_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
    return cleaned.strip("-") or "UNKNOWN"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
