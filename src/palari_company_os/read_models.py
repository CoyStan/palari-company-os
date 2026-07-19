from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, TypeVar

from .models import to_plain
from .pcaw_workspace import (
    RecordedGovernanceProjectionProvider,
)
from .record_order import record_time_key as _record_time_key
from .read_model_commands import (
    agent_commands,
    agent_handoff_command,
    agent_loop_command,
    work_next_commands,
)
from .read_model_coordination import (
    build_active_parallel_work,
    build_coordination_warnings,
    group_active_attempts,
    group_warning_messages,
)
from .workspace import Workspace


T = TypeVar("T")


@dataclass(frozen=True)
class QueueItem:
    id: str
    title: str
    attention: str
    why: str
    next_action: str
    next_step_type: str
    next_commands: list[str]
    agent_loop_command: str
    agent_handoff_command: str
    status: str
    terminal_disposition: str
    terminal_reason: str
    successor_work_item_id: str
    risk: str
    intensity: str
    goal: str
    goal_title: str
    palari: str
    palari_name: str
    owner: str
    external_provider: str
    external_key: str
    external_url: str
    external_updated_at: str
    ai_safe_to_proceed: bool
    waiting_on_human: bool
    evidence_state: str
    review_state: str
    receipt_state: str
    integration_state: str
    approval_progress: str
    acceptance_state: str
    scope_overlap_state: str
    workbench: str
    workbench_label: str
    active_attempts: list[dict[str, Any]]
    coordination_warnings: list[str]


@dataclass(frozen=True)
class _ReadContext:
    goals_by_id: dict[str, Any]
    palaris_by_id: dict[str, Any]
    humans_by_id: dict[str, Any]
    workbenches_by_id: dict[str, Any]
    work_by_id: dict[str, Any]
    attempts_by_id: dict[str, Any]
    latest_attempt_by_work: dict[str, Any]
    current_attempt_by_work: dict[str, Any]
    latest_evidence_by_work: dict[str, Any]
    latest_review_by_work: dict[str, Any]
    latest_human_decision_by_work: dict[str, Any]
    human_decisions_by_work: dict[str, list[Any]]
    latest_acceptance_by_work: dict[str, Any]
    latest_receipt_by_work: dict[str, Any]
    integration_plans_by_work: dict[str, list[Any]]
    pending_integration_plans_by_work: dict[str, list[Any]]
    integration_outbox_by_work: dict[str, list[Any]]
    queued_integration_outbox_by_work: dict[str, list[Any]]
    integration_outbox_by_plan: dict[str, Any]
    latest_outcome_by_work: dict[str, Any]
    open_decision_by_work: dict[str, Any]
    governance: RecordedGovernanceProjectionProvider
    active_parallel: list[dict[str, Any]]
    active_attempts_by_work: dict[str, list[dict[str, Any]]]
    coordination_warnings: list[dict[str, Any]]
    warning_messages_by_work: dict[str, list[str]]


@dataclass(frozen=True)
class _LifecycleView:
    attention: str
    why: str
    next_action: str
    evidence_state: str
    review_state: str
    receipt_state: str
    approval_progress: str
    acceptance_state: str
    integration_ready: bool


ATTENTION_PRIORITY = {
    "needs-human-decision": 0,
    "changes-requested": 1,
    "needs-review": 2,
    "needs-evidence": 3,
    "ready-to-integrate": 4,
    "ready-to-complete": 5,
    "ready-for-ai-work": 6,
    "blocked": 7,
    "closed": 8,
}

def queue_items(workspace: Workspace) -> list[QueueItem]:
    context = _read_context(workspace)
    items = [_queue_item(work, context) for work in workspace.work_items]
    return sorted(items, key=lambda item: (ATTENTION_PRIORITY.get(item.attention, 99), item.id))


def active_parallel_work(workspace: Workspace) -> list[dict[str, Any]]:
    return _read_context(workspace).active_parallel


def coordination_warnings(workspace: Workspace) -> list[dict[str, Any]]:
    return _read_context(workspace).coordination_warnings


def detail(workspace: Workspace, work_id: str) -> dict[str, Any]:
    context = _read_context(workspace)
    work = context.work_by_id.get(work_id)
    if work is None:
        known = ", ".join(sorted(item.id for item in workspace.work_items))
        raise KeyError(f"unknown work item {work_id}; known work items: {known}")

    goal = context.goals_by_id.get(work.goal)
    palari = context.palaris_by_id.get(work.palari)
    workbench = context.workbenches_by_id.get(work.workbench_id) if work.workbench_id else None
    attempt = _attempt_for_work(context, work)
    evidence = context.latest_evidence_by_work.get(work.id)
    review = context.latest_review_by_work.get(work.id)
    human_decision = context.latest_human_decision_by_work.get(work.id)
    receipt = context.latest_receipt_by_work.get(work.id)
    integration_plans = context.integration_plans_by_work.get(work.id, [])
    integration_outbox = context.integration_outbox_by_work.get(work.id, [])
    allowed_sources = set(work.allowed_sources)
    sources = [source for source in workspace.sources if source.id in allowed_sources]
    outcome = context.latest_outcome_by_work.get(work.id)
    linked_decisions = [decision for decision in workspace.decisions if decision.linked_work == work.id]
    child_work_items = [child for child in workspace.work_items if child.parent_work_item_id == work.id]
    dependencies = [
        dependency
        for dependency in (context.work_by_id.get(dependency_id) for dependency_id in work.dependency_ids)
        if dependency is not None
    ]
    human_decisions = context.human_decisions_by_work.get(work.id, [])
    queue_item = _queue_item(work, context)

    return {
        "work_item": to_plain(work),
        "external": _external_ref(work),
        "goal": to_plain(goal) if goal else None,
        "palari": to_plain(palari) if palari else None,
        "workbench": to_plain(workbench) if workbench else None,
        "parent_work_item": (
            to_plain(context.work_by_id.get(work.parent_work_item_id))
            if work.parent_work_item_id
            else None
        ),
        "child_work_items": to_plain(child_work_items),
        "dependencies": to_plain(dependencies),
        "attempt": to_plain(attempt) if attempt else None,
        "evidence": to_plain(evidence) if evidence else None,
        "review": to_plain(review) if review else None,
        "receipt": to_plain(receipt) if receipt else None,
        "integration_plans": to_plain(integration_plans),
        "integration_outbox": to_plain(integration_outbox),
        "sources": to_plain(sources),
        "human_decision": to_plain(human_decision) if human_decision else None,
        "human_decisions": to_plain(human_decisions),
        "linked_decisions": to_plain(linked_decisions),
        "outcome": to_plain(outcome) if outcome else None,
        "attention": queue_item.attention,
        "why": queue_item.why,
        "next_action": queue_item.next_action,
        "next_step_type": queue_item.next_step_type,
        "next_commands": queue_item.next_commands,
        "agent_loop_command": queue_item.agent_loop_command,
        "agent_handoff_command": queue_item.agent_handoff_command,
        "active_parallel_attempts": queue_item.active_attempts,
        "coordination_warnings": queue_item.coordination_warnings,
        "safety": {
            "ai_safe_to_proceed": queue_item.ai_safe_to_proceed,
            "waiting_on_human": queue_item.waiting_on_human,
            "evidence_state": queue_item.evidence_state,
            "review_state": queue_item.review_state,
            "receipt_state": queue_item.receipt_state,
            "integration_state": queue_item.integration_state,
            "approval_progress": queue_item.approval_progress,
            "acceptance_state": queue_item.acceptance_state,
            "scope_overlap_state": queue_item.scope_overlap_state,
        },
        "agent_commands": agent_commands(work, queue_item.next_step_type),
    }


def _external_ref(work: Any) -> dict[str, str] | None:
    if not work.external_provider:
        return None
    return {
        "provider": work.external_provider,
        "id": work.external_id,
        "key": work.external_key,
        "url": work.external_url,
        "updated_at": work.external_updated_at,
    }


def _read_context(workspace: Workspace) -> _ReadContext:
    goals_by_id = {goal.id: goal for goal in workspace.goals}
    palaris_by_id = {palari.id: palari for palari in workspace.palaris}
    humans_by_id = {human.id: human for human in workspace.humans}
    workbenches_by_id = {workbench.id: workbench for workbench in workspace.workbenches}
    work_by_id = {work.id: work for work in workspace.work_items}
    attempts_by_id = {attempt.id: attempt for attempt in workspace.attempts}
    latest_attempt_by_work = _latest_by_work(workspace.attempts)
    current_attempt_by_work = _current_attempts_by_work(
        workspace.work_items,
        attempts_by_id,
        latest_attempt_by_work,
    )
    active_parallel = build_active_parallel_work(
        workspace,
        work_by_id,
        workbenches_by_id,
    )
    coordination = build_coordination_warnings(workspace, current_attempt_by_work)
    active_attempts_by_work = group_active_attempts(active_parallel)
    warning_messages_by_work = group_warning_messages(coordination)
    return _ReadContext(
        goals_by_id=goals_by_id,
        palaris_by_id=palaris_by_id,
        humans_by_id=humans_by_id,
        workbenches_by_id=workbenches_by_id,
        work_by_id=work_by_id,
        attempts_by_id=attempts_by_id,
        latest_attempt_by_work=latest_attempt_by_work,
        current_attempt_by_work=current_attempt_by_work,
        latest_evidence_by_work=_latest_by_work(workspace.evidence_runs),
        latest_review_by_work=_latest_by_work(workspace.review_verdicts),
        latest_human_decision_by_work=_latest_by_work(workspace.human_decisions),
        human_decisions_by_work=_group_by_work(workspace.human_decisions),
        latest_acceptance_by_work=_latest_by_work(workspace.acceptance_records),
        latest_receipt_by_work=_latest_by_work(workspace.receipts),
        integration_plans_by_work=_group_by_work(workspace.integration_plans),
        pending_integration_plans_by_work=_pending_integration_plans_by_work(
            workspace.integration_plans
        ),
        integration_outbox_by_work=_group_by_work(workspace.integration_outbox),
        queued_integration_outbox_by_work=_queued_integration_outbox_by_work(
            workspace.integration_outbox
        ),
        integration_outbox_by_plan={
            item.plan_id: item for item in workspace.integration_outbox
        },
        latest_outcome_by_work=_latest_by_work(workspace.outcomes),
        open_decision_by_work=_open_decisions_by_work(workspace.decisions),
        governance=RecordedGovernanceProjectionProvider(workspace),
        active_parallel=active_parallel,
        active_attempts_by_work=active_attempts_by_work,
        coordination_warnings=coordination,
        warning_messages_by_work=warning_messages_by_work,
    )


def _queue_item(work: Any, context: _ReadContext) -> QueueItem:
    goal = context.goals_by_id.get(work.goal)
    palari = context.palaris_by_id.get(work.palari)
    workbench = context.workbenches_by_id.get(work.workbench_id) if work.workbench_id else None
    owner = ""
    if palari and palari.owner_human:
        human = context.humans_by_id.get(palari.owner_human)
        owner = human.name if human else palari.owner_human

    lifecycle = _lifecycle_view(work, context)
    attention, why, next_action = _attention(work, context, lifecycle)
    evidence_state = lifecycle.evidence_state
    review_state = lifecycle.review_state
    receipt_state = lifecycle.receipt_state
    integration_state = _integration_state(work, context, lifecycle)
    approval_progress = lifecycle.approval_progress
    acceptance_state = lifecycle.acceptance_state
    active_attempts = _active_attempts_for_work(work, context)
    warnings = _coordination_warning_messages_for_work(work, context)
    waiting_on_human = attention == "needs-human-decision"
    ai_safe_to_proceed = _ai_safe_to_proceed(attention)
    next_step_type = _next_step_type(
        attention,
        ai_safe_to_proceed,
        evidence_state,
    )
    return QueueItem(
        id=work.id,
        title=work.title,
        attention=attention,
        why=why,
        next_action=next_action,
        next_step_type=next_step_type,
        next_commands=work_next_commands(
            work,
            attention,
            context.open_decision_by_work.get(work.id),
            context.current_attempt_by_work.get(work.id) is not None,
            ai_safe_to_proceed,
        ),
        agent_loop_command=agent_loop_command(work),
        agent_handoff_command=agent_handoff_command(work, next_step_type),
        status=work.status,
        terminal_disposition=work.terminal_disposition,
        terminal_reason=work.terminal_reason,
        successor_work_item_id=work.successor_work_item_id,
        risk=work.risk,
        intensity=work.intensity,
        goal=work.goal,
        goal_title=goal.title if goal else work.goal,
        palari=work.palari,
        palari_name=palari.name if palari else work.palari,
        owner=owner,
        external_provider=work.external_provider,
        external_key=work.external_key,
        external_url=work.external_url,
        external_updated_at=work.external_updated_at,
        ai_safe_to_proceed=ai_safe_to_proceed,
        waiting_on_human=waiting_on_human,
        evidence_state=evidence_state,
        review_state=review_state,
        receipt_state=receipt_state,
        integration_state=integration_state,
        approval_progress=approval_progress,
        acceptance_state=acceptance_state,
        scope_overlap_state="blocked" if warnings else "clear",
        workbench=work.workbench_id,
        workbench_label=workbench.label if workbench else "",
        active_attempts=active_attempts,
        coordination_warnings=warnings,
    )


def _attention(
    work: Any,
    context: _ReadContext,
    lifecycle: _LifecycleView,
) -> tuple[str, str, str]:
    open_decision = context.open_decision_by_work.get(work.id)
    if open_decision is not None:
        return (
            "needs-human-decision",
            f"Decision {open_decision.id} is open for this work item.",
            f"Answer decision: {open_decision.question}",
        )

    if work.terminal_disposition:
        successor = work.successor_work_item_id
        next_action = (
            f"Inspect successor {successor}; this historical item remains audit-visible."
            if successor
            else "Inspect the retirement reason or create new work if the objective returns."
        )
        return (
            "closed",
            f"The work item was {work.terminal_disposition}: {work.terminal_reason}",
            next_action,
        )

    if lifecycle.attention == "closed":
        return lifecycle.attention, lifecycle.why, lifecycle.next_action

    warnings = _coordination_warning_messages_for_work(work, context)
    if warnings:
        return (
            "blocked",
            warnings[0],
            "Coordinate or split the overlapping output target before continuing.",
        )

    pending_plans = _pending_integration_plans_for_work(work, context)
    if pending_plans:
        plan = pending_plans[0]
        return (
            "needs-human-decision",
            f"Integration plan {plan.id} previews {plan.action} for {plan.event} "
            "and requires approval before any future live action.",
            "Review the dry-run payload and decide whether this external action should ever be enabled.",
        )

    queued_items = _queued_integration_outbox_for_work(work, context)
    if queued_items:
        item = queued_items[0]
        return (
            "ready-to-integrate",
            f"Integration outbox item {item.id} is queued for future execution boundary. "
            "No provider call is enabled yet.",
            "Review the queued payload; live execution remains disabled.",
        )

    canceled_items = _canceled_integration_outbox_for_work(work, context)
    if canceled_items:
        item = canceled_items[0]
        return (
            "needs-human-decision",
            f"Integration outbox item {item.id} was canceled: {item.cancel_reason}. "
            "No provider call was made.",
            "Review whether the external action should remain canceled or be replanned.",
        )

    approved_plans = _approved_unqueued_integration_plans_for_work(work, context)
    if approved_plans:
        plan = approved_plans[0]
        return (
            "needs-human-decision",
            f"Integration plan {plan.id} is approved and ready to enqueue. "
            "No provider call has been made.",
            f"Run `palari integration enqueue {plan.id} --by HUMAN-ID` to place it in the outbox.",
        )

    return lifecycle.attention, lifecycle.why, lifecycle.next_action


def _attempt_head(attempt: Any) -> str:
    return getattr(attempt, "head_sha", "") or (attempt.commits[-1] if attempt.commits else "")


def _next_step_type(
    attention: str,
    ai_safe_to_proceed: bool,
    evidence_state: str,
) -> str:
    if (
        attention == "needs-evidence"
        and ai_safe_to_proceed
        and evidence_state in {"missing", "stale", "failed", "invalid"}
    ):
        return "check-active-proof"
    if attention == "changes-requested":
        return "repair"
    if attention == "ready-for-ai-work" and ai_safe_to_proceed:
        return "start-work"
    if attention == "needs-human-decision":
        return "human-decision"
    if attention == "needs-review":
        return "review-handoff"
    if attention == "ready-to-complete":
        return "automatic-reconciliation"
    if attention == "closed":
        return "closed"
    return "inspect"


def _lifecycle_view(work: Any, context: _ReadContext) -> _LifecycleView:
    """Translate one non-authoritative kernel projection into operator language."""

    projection = context.governance.for_work(work.id)
    current = projection.evaluation
    candidate = projection.completion_evaluation
    candidate_properties = {item.name: item.status for item in candidate.properties}
    attempt = _attempt_for_work(context, work)
    evidence = context.latest_evidence_by_work.get(work.id)
    receipt = context.latest_receipt_by_work.get(work.id)
    review = context.latest_review_by_work.get(work.id)
    acceptance = context.latest_acceptance_by_work.get(work.id)
    approval_progress = (
        f"{len(candidate.qualified_human_ids)}/{work.required_approval_count}"
    )

    if attempt is None:
        next_action = "Start a bounded attempt using the declared scope and authority limits."
        return _LifecycleView(
            attention="ready-for-ai-work",
            why="No execution attempt exists yet.",
            next_action=next_action,
            evidence_state="not-started",
            review_state="waiting-on-evidence",
            receipt_state="not-started",
            approval_progress=approval_progress,
            acceptance_state="pending",
            integration_ready=False,
        )

    if evidence is None:
        evidence_state = "missing"
        proof_why = "There is an attempt but no evidence run for it."
        proof_next = "Run the focused verification expected for this work item."
    elif evidence.head_sha != _attempt_head(attempt):
        evidence_state = "stale"
        proof_why = "Latest evidence is stale for the current attempt head."
        proof_next = "Refresh evidence before requesting review or human decision."
    elif evidence.status != "passed":
        evidence_state = evidence.status
        proof_why = f"Latest evidence run {evidence.id} is {evidence.status}."
        proof_next = "Repair the failing check or record an explicit blocker."
    elif projection.recorded_proof_errors:
        evidence_state = "invalid"
        proof_why = (
            "Latest recorded proof is not current: "
            f"{projection.recorded_proof_errors[0]}."
        )
        proof_next = "Refresh exact passing evidence for the current attempt and receipt."
    else:
        evidence_state = "passed"
        proof_why = ""
        proof_next = ""

    proof_current = evidence_state == "passed"
    if receipt is None:
        receipt_state = "missing"
    elif receipt.attempt_id != attempt.id:
        receipt_state = "stale"
    elif proof_current and candidate_properties["receipt_binding"] == "verified":
        receipt_state = "ready"
    else:
        receipt_state = "invalid"

    if candidate_properties["independent_review"] == "not-required":
        review_state = "not-required"
    elif not proof_current:
        review_state = "waiting-on-evidence"
    elif review is None:
        review_state = "missing"
    elif review.verdict in {"changes-requested", "blocked", "needs-human-decision"}:
        review_state = review.verdict
    elif candidate_properties["independent_review"] == "verified":
        review_state = review.verdict
    else:
        review_state = "stale"

    if candidate_properties["acceptance_currency"] == "not-required":
        acceptance_state = "not-required"
    elif candidate_properties["acceptance_currency"] == "verified":
        acceptance_state = "accepted"
    elif acceptance is not None and acceptance.status != "accepted":
        acceptance_state = acceptance.status
    elif acceptance is not None:
        acceptance_state = "stale"
    elif candidate.derived_state == "accept-ready":
        acceptance_state = "ready-to-record"
    else:
        acceptance_state = "pending"

    common = {
        "evidence_state": evidence_state,
        "review_state": review_state,
        "receipt_state": receipt_state,
        "approval_progress": approval_progress,
        "acceptance_state": acceptance_state,
    }
    if not proof_current:
        return _LifecycleView(
            attention="needs-evidence",
            why=proof_why,
            next_action=proof_next,
            integration_ready=False,
            **common,
        )

    if work.status in {"closed", "completed", "done"} and current.derived_state == "completed":
        return _LifecycleView(
            attention="closed",
            why="The recorded current proof derives the terminal lifecycle state.",
            next_action="Review outcomes or start a follow-up only if needed.",
            integration_ready=True,
            **common,
        )

    review_matches_evidence = bool(
        review is not None
        and candidate.current_review_bound
    )
    if (
        review is not None
        and review_matches_evidence
        and review.verdict == "changes-requested"
    ):
        return _LifecycleView(
            attention="changes-requested",
            why=f"Review {review.id} requested changes.",
            next_action="Repair only the reviewed findings, then refresh evidence and review.",
            integration_ready=False,
            **common,
        )
    if (
        review is not None
        and review_matches_evidence
        and review.verdict in {"blocked", "needs-human-decision"}
    ):
        return _LifecycleView(
            attention="needs-human-decision",
            why=f"Review {review.id} requires human judgment.",
            next_action="Resolve the human decision before continuing.",
            integration_ready=False,
            **common,
        )

    state = candidate.derived_state
    if state == "review-required":
        why = "Current exact proof requires an independent review."
        if review is not None:
            diagnostic = _first_error_message(candidate)
            why = f"Review {review.id} is not current: {diagnostic}"
        return _LifecycleView(
            attention="needs-review",
            why=why,
            next_action="Request an independent review against the current exact proof.",
            integration_ready=False,
            **common,
        )
    if state == "human-decision-required":
        return _LifecycleView(
            attention="needs-human-decision",
            why=(
                "Review is accept-ready, but approval quorum is incomplete "
                f"({approval_progress})."
            ),
            next_action="Collect the required current decision from a qualified human.",
            integration_ready=False,
            **common,
        )
    if state in {"accept-ready", "accepted", "completed"}:
        return _LifecycleView(
            attention="ready-to-complete",
            why="Recorded current proof satisfies the lifecycle completion candidate.",
            next_action="Reconcile the terminal lifecycle state from externally verified proof.",
            integration_ready=True,
            **common,
        )

    return _LifecycleView(
        attention="blocked",
        why=_first_error_message(candidate),
        next_action="Inspect the current kernel diagnostics and repair the blocked proof.",
        integration_ready=False,
        **common,
    )


def _first_error_message(projection: Any) -> str:
    if projection.errors:
        return projection.errors[0].message
    return f"The governance kernel derives {projection.derived_state}."


def _integration_state(
    work: Any,
    context: _ReadContext,
    lifecycle: _LifecycleView,
) -> str:
    if lifecycle.attention == "closed":
        return "closed"
    if _pending_integration_plans_for_work(work, context):
        return "pending-plan"
    if _queued_integration_outbox_for_work(work, context):
        return "outbox-queued"
    if _canceled_integration_outbox_for_work(work, context):
        return "outbox-canceled"
    decided_state = _latest_decided_integration_plan_state_for_work(work, context)
    if decided_state:
        return decided_state
    if lifecycle.integration_ready:
        return "ready"
    if context.open_decision_by_work.get(work.id):
        return "blocked-by-decision"
    return "not-ready"


def _active_attempts_for_work(work: Any, context: _ReadContext) -> list[dict[str, Any]]:
    return context.active_attempts_by_work.get(work.id, [])


def _coordination_warning_messages_for_work(work: Any, context: _ReadContext) -> list[str]:
    return context.warning_messages_by_work.get(work.id, [])


def _pending_integration_plans_for_work(work: Any, context: _ReadContext) -> list[Any]:
    return context.pending_integration_plans_by_work.get(work.id, [])


def _queued_integration_outbox_for_work(work: Any, context: _ReadContext) -> list[Any]:
    return context.queued_integration_outbox_by_work.get(work.id, [])


def _canceled_integration_outbox_for_work(work: Any, context: _ReadContext) -> list[Any]:
    items = [
        item
        for item in context.integration_outbox_by_work.get(work.id, [])
        if item.status == "canceled"
    ]
    return sorted(items, key=_record_time_key, reverse=True)


def _approved_unqueued_integration_plans_for_work(work: Any, context: _ReadContext) -> list[Any]:
    plans = [
        plan
        for plan in context.integration_plans_by_work.get(work.id, [])
        if plan.status == "approved" and plan.id not in context.integration_outbox_by_plan
    ]
    return sorted(plans, key=_record_time_key, reverse=True)


def _latest_decided_integration_plan_state_for_work(work: Any, context: _ReadContext) -> str:
    plans = [
        plan
        for plan in context.integration_plans_by_work.get(work.id, [])
        if plan.status in {"approved", "rejected", "canceled"}
    ]
    if not plans:
        return ""
    plan = max(plans, key=_record_time_key)
    return f"plan-{plan.status}"


def _ai_safe_to_proceed(attention: str) -> bool:
    if attention in {
        "needs-human-decision",
        "needs-review",
        "ready-to-integrate",
        "ready-to-complete",
        "blocked",
        "closed",
    }:
        return False
    return True


def _attempt_for_work(context: _ReadContext, work: Any) -> Any | None:
    if work.current_attempt:
        current = context.attempts_by_id.get(work.current_attempt)
        if current is not None:
            return current
    return context.latest_attempt_by_work.get(work.id)


def _current_attempts_by_work(
    work_items: Iterable[Any],
    attempts_by_id: dict[str, Any],
    latest_attempt_by_work: dict[str, Any],
) -> dict[str, Any]:
    current: dict[str, Any] = {}
    for work in work_items:
        if work.current_attempt and work.current_attempt in attempts_by_id:
            current[work.id] = attempts_by_id[work.current_attempt]
        elif work.id in latest_attempt_by_work:
            current[work.id] = latest_attempt_by_work[work.id]
    return current


def _open_decisions_by_work(decisions: Iterable[Any]) -> dict[str, Any]:
    open_decisions: dict[str, Any] = {}
    for decision in decisions:
        if decision.linked_work and decision.status == "open":
            open_decisions.setdefault(decision.linked_work, decision)
    return open_decisions


def _group_by_work(records: Iterable[T]) -> dict[str, list[T]]:
    grouped: dict[str, list[T]] = {}
    for record in records:
        grouped.setdefault(getattr(record, "work_item_id"), []).append(record)
    return grouped


def _pending_integration_plans_by_work(records: Iterable[T]) -> dict[str, list[T]]:
    grouped: dict[str, list[T]] = {}
    for record in records:
        if getattr(record, "approval_required", False) and getattr(record, "status", "") in {
            "planned",
            "pending-approval",
        }:
            grouped.setdefault(getattr(record, "work_item_id"), []).append(record)
    for plans in grouped.values():
        plans.sort(key=_record_time_key, reverse=True)
    return grouped


def _queued_integration_outbox_by_work(records: Iterable[T]) -> dict[str, list[T]]:
    grouped: dict[str, list[T]] = {}
    for record in records:
        if getattr(record, "status", "") == "queued":
            grouped.setdefault(getattr(record, "work_item_id"), []).append(record)
    for items in grouped.values():
        items.sort(key=_record_time_key, reverse=True)
    return grouped


def _latest_by_work(records: Iterable[T]) -> dict[str, T]:
    latest: dict[str, T] = {}
    keys: dict[str, tuple[Any, ...]] = {}
    for record in records:
        work_id = getattr(record, "work_item_id")
        key = _record_time_key(record)
        if work_id not in latest or key >= keys[work_id]:
            latest[work_id] = record
            keys[work_id] = key
    return latest
