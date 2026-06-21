from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, TypeVar

from .models import to_plain
from .playbooks import recommend_playbooks, recommended_playbook_ids
from .workspace import Workspace


T = TypeVar("T")


@dataclass(frozen=True)
class QueueItem:
    id: str
    title: str
    attention: str
    why: str
    next_action: str
    status: str
    risk: str
    intensity: str
    goal: str
    goal_title: str
    palari: str
    palari_name: str
    owner: str
    ai_safe_to_proceed: bool
    waiting_on_human: bool
    evidence_state: str
    review_state: str
    receipt_state: str
    integration_state: str
    approval_progress: str
    recommended_intensity: str
    intensity_reason: str
    learning_signal: str
    playbook_recommendations: list[str]
    workbench: str
    workbench_label: str
    active_attempts: list[dict[str, Any]]
    coordination_warnings: list[str]


@dataclass(frozen=True)
class _ReadContext:
    goals_by_id: dict[str, Any]
    palaris_by_id: dict[str, Any]
    humans_by_id: dict[str, Any]
    sources_by_id: dict[str, Any]
    workbenches_by_id: dict[str, Any]
    work_by_id: dict[str, Any]
    attempts_by_id: dict[str, Any]
    outcomes_by_id: dict[str, Any]
    latest_attempt_by_work: dict[str, Any]
    current_attempt_by_work: dict[str, Any]
    latest_evidence_by_work: dict[str, Any]
    latest_review_by_work: dict[str, Any]
    latest_human_decision_by_work: dict[str, Any]
    human_decisions_by_work: dict[str, list[Any]]
    latest_receipt_by_work: dict[str, Any]
    integration_plans_by_work: dict[str, list[Any]]
    pending_integration_plans_by_work: dict[str, list[Any]]
    integration_outbox_by_work: dict[str, list[Any]]
    queued_integration_outbox_by_work: dict[str, list[Any]]
    integration_outbox_by_plan: dict[str, Any]
    latest_outcome_by_work: dict[str, Any]
    open_decision_by_work: dict[str, Any]
    active_parallel: list[dict[str, Any]]
    active_attempts_by_work: dict[str, list[dict[str, Any]]]
    coordination_warnings: list[dict[str, Any]]
    warning_messages_by_work: dict[str, list[str]] = field(default_factory=dict)


ATTENTION_PRIORITY = {
    "needs-human-decision": 0,
    "changes-requested": 1,
    "needs-review": 2,
    "needs-evidence": 3,
    "ready-to-integrate": 4,
    "receipt-ready": 5,
    "ready-for-ai-work": 6,
    "blocked": 7,
    "closed": 8,
}


def queue_items(workspace: Workspace) -> list[QueueItem]:
    context = _read_context(workspace)
    items = [_queue_item(workspace, work, context) for work in workspace.work_items]
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
    queue_item = _queue_item(workspace, work, context)
    playbooks = recommend_playbooks(workspace, work.id)

    return {
        "work_item": to_plain(work),
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
            "recommended_intensity": queue_item.recommended_intensity,
            "intensity_reason": queue_item.intensity_reason,
        },
        "playbooks": playbooks,
    }


def _read_context(workspace: Workspace) -> _ReadContext:
    goals_by_id = {goal.id: goal for goal in workspace.goals}
    palaris_by_id = {palari.id: palari for palari in workspace.palaris}
    humans_by_id = {human.id: human for human in workspace.humans}
    sources_by_id = {source.id: source for source in workspace.sources}
    workbenches_by_id = {workbench.id: workbench for workbench in workspace.workbenches}
    work_by_id = {work.id: work for work in workspace.work_items}
    attempts_by_id = {attempt.id: attempt for attempt in workspace.attempts}
    outcomes_by_id = {outcome.id: outcome for outcome in workspace.outcomes}
    latest_attempt_by_work = _latest_by_work(workspace.attempts)
    current_attempt_by_work = _current_attempts_by_work(
        workspace.work_items,
        attempts_by_id,
        latest_attempt_by_work,
    )
    active_parallel = _build_active_parallel_work(
        workspace,
        work_by_id,
        workbenches_by_id,
    )
    coordination = _build_coordination_warnings(workspace, current_attempt_by_work)
    active_attempts_by_work = _group_active_attempts(active_parallel)
    warning_messages_by_work = _group_warning_messages(coordination)
    return _ReadContext(
        goals_by_id=goals_by_id,
        palaris_by_id=palaris_by_id,
        humans_by_id=humans_by_id,
        sources_by_id=sources_by_id,
        workbenches_by_id=workbenches_by_id,
        work_by_id=work_by_id,
        attempts_by_id=attempts_by_id,
        outcomes_by_id=outcomes_by_id,
        latest_attempt_by_work=latest_attempt_by_work,
        current_attempt_by_work=current_attempt_by_work,
        latest_evidence_by_work=_latest_by_work(workspace.evidence_runs),
        latest_review_by_work=_latest_by_work(workspace.review_verdicts),
        latest_human_decision_by_work=_latest_by_work(workspace.human_decisions),
        human_decisions_by_work=_group_by_work(workspace.human_decisions),
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
        active_parallel=active_parallel,
        active_attempts_by_work=active_attempts_by_work,
        coordination_warnings=coordination,
        warning_messages_by_work=warning_messages_by_work,
    )


def _queue_item(workspace: Workspace, work: Any, context: _ReadContext) -> QueueItem:
    goal = context.goals_by_id.get(work.goal)
    palari = context.palaris_by_id.get(work.palari)
    workbench = context.workbenches_by_id.get(work.workbench_id) if work.workbench_id else None
    owner = ""
    if palari and palari.owner_human:
        human = context.humans_by_id.get(palari.owner_human)
        owner = human.name if human else palari.owner_human

    attention, why, next_action = _attention(workspace, work, context)
    evidence_state = _evidence_state(work, context)
    review_state = _review_state(work, context)
    receipt_state = _receipt_state(work, context)
    integration_state = _integration_state(workspace, work, context)
    approval_progress = _approval_progress(work, context)
    recommended_intensity, intensity_reason = recommend_intensity(work)
    learning_signal = _learning_signal(context, palari)
    playbook_recommendations = recommended_playbook_ids(workspace, work)
    active_attempts = _active_attempts_for_work(work, context)
    warnings = _coordination_warning_messages_for_work(work, context)
    waiting_on_human = attention == "needs-human-decision"
    ai_safe_to_proceed = _ai_safe_to_proceed(work, attention, context)
    return QueueItem(
        id=work.id,
        title=work.title,
        attention=attention,
        why=why,
        next_action=next_action,
        status=work.status,
        risk=work.risk,
        intensity=work.intensity,
        goal=work.goal,
        goal_title=goal.title if goal else work.goal,
        palari=work.palari,
        palari_name=palari.name if palari else work.palari,
        owner=owner,
        ai_safe_to_proceed=ai_safe_to_proceed,
        waiting_on_human=waiting_on_human,
        evidence_state=evidence_state,
        review_state=review_state,
        receipt_state=receipt_state,
        integration_state=integration_state,
        approval_progress=approval_progress,
        recommended_intensity=recommended_intensity,
        intensity_reason=intensity_reason,
        learning_signal=learning_signal,
        playbook_recommendations=playbook_recommendations,
        workbench=work.workbench_id,
        workbench_label=workbench.label if workbench else "",
        active_attempts=active_attempts,
        coordination_warnings=warnings,
    )


def _attention(workspace: Workspace, work: Any, context: _ReadContext) -> tuple[str, str, str]:
    open_decision = context.open_decision_by_work.get(work.id)
    if open_decision is not None:
        return (
            "needs-human-decision",
            f"Decision {open_decision.id} is open for this work item.",
            f"Answer decision: {open_decision.question}",
        )

    if work.status in {"closed", "completed", "done"}:
        return (
            "closed",
            "The work item is complete and has a recorded terminal status.",
            "Review outcomes or start a follow-up only if needed.",
        )

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

    attempt = _attempt_for_work(context, work)
    if attempt is None:
        return (
            "ready-for-ai-work",
            "No execution attempt exists yet.",
            "Start a bounded attempt using the declared scope and authority limits.",
        )

    if _low_risk_receipt_ready(work, attempt, context):
        return (
            "receipt-ready",
            "A completed low-risk attempt has a receipt showing sources, actions, outputs, and limits.",
            "Review the output, undo it if needed, or continue with the next bounded step.",
        )

    evidence = context.latest_evidence_by_work.get(work.id)
    if evidence is None:
        return (
            "needs-evidence",
            "There is an attempt but no evidence run for it.",
            "Run the focused verification expected for this work item.",
        )
    if evidence.head_sha != _attempt_head(attempt):
        return (
            "needs-evidence",
            "Latest evidence is stale for the current attempt head.",
            "Refresh evidence before requesting review or human decision.",
        )
    if evidence.status != "passed":
        return (
            "needs-evidence",
            f"Latest evidence run {evidence.id} is {evidence.status}.",
            "Repair the failing check or record an explicit blocker.",
        )

    review = context.latest_review_by_work.get(work.id)
    if review is None:
        return (
            "needs-review",
            "Evidence exists, but no review verdict has inspected it.",
            "Request an independent review against the evidence head.",
        )
    if review.reviewed_head != evidence.head_sha:
        return (
            "needs-review",
            "The latest review does not match the latest evidence head.",
            "Refresh review before asking for a human decision.",
        )
    if review.verdict == "changes-requested":
        return (
            "changes-requested",
            f"Review {review.id} requested changes.",
            "Repair only the reviewed findings, then refresh evidence and review.",
        )
    if review.verdict in {"blocked", "needs-human-decision"}:
        return (
            "needs-human-decision",
            f"Review {review.id} requires human judgment.",
            "Resolve the human decision before continuing.",
        )

    human_decision = context.latest_human_decision_by_work.get(work.id)
    if review.verdict == "accept-ready" and human_decision is None:
        approval_progress = _approval_progress(work, context)
        return (
            "needs-human-decision",
            f"Review is accept-ready, but approval quorum is incomplete ({approval_progress}).",
            "Human accepts, requests changes, or blocks this work item.",
        )
    if review.verdict == "accept-ready" and not _approval_quorum_met(work, review, context):
        return (
            "needs-human-decision",
            f"Review is accept-ready, but approval quorum is incomplete ({_approval_progress(work, context)}).",
            "Collect the required human approval before integration.",
        )
    if human_decision and _approval_quorum_met(work, review, context):
        return (
            "ready-to-integrate",
            "Human decision is recorded after fresh evidence and review.",
            "Integrate or close according to the repo's merge policy.",
        )

    return (
        "blocked",
        "The current state is valid but does not map to a known next action.",
        "Inspect the work detail and record the missing state explicitly.",
    )


def recommend_intensity(work: Any) -> tuple[str, str]:
    haystack = " ".join(
        [
            work.id,
            work.title,
            work.risk,
            work.scope,
            " ".join(work.allowed_resources),
            work.acceptance_target,
        ]
    ).lower()
    high_terms = [
        "r5",
        "production",
        "deploy",
        "security",
        "secret",
        "credential",
        "policy",
        "broker",
        "external",
        "oauth",
        "customer data",
        "authority",
    ]
    standard_terms = ["r2", "r3", "schema", "shared authority", "shared standard"]
    if work.risk in {"R5", "R4"} or any(term in haystack for term in high_terms):
        return (
            "high",
            "High-risk, external-side-effect, security, policy, broker, or authority language is present.",
        )
    if work.risk in {"R2", "R3"} or any(term in haystack for term in standard_terms):
        return ("standard", "Normal governed work needs evidence, review, and possible human decision.")
    return ("light", "Low-risk internal maintenance can use the lightest responsible proof.")


def _attempt_head(attempt: Any) -> str:
    return attempt.commits[-1] if attempt.commits else ""


def _evidence_state(work: Any, context: _ReadContext) -> str:
    attempt = _attempt_for_work(context, work)
    evidence = context.latest_evidence_by_work.get(work.id)
    if attempt is None:
        return "not-started"
    if evidence is None:
        return "missing"
    if evidence.head_sha != _attempt_head(attempt):
        return "stale"
    return evidence.status


def _review_state(work: Any, context: _ReadContext) -> str:
    evidence = context.latest_evidence_by_work.get(work.id)
    review = context.latest_review_by_work.get(work.id)
    if evidence is None:
        return "waiting-on-evidence"
    if review is None:
        return "missing"
    if review.reviewed_head != evidence.head_sha:
        return "stale"
    return review.verdict


def _receipt_state(work: Any, context: _ReadContext) -> str:
    attempt = _attempt_for_work(context, work)
    receipt = context.latest_receipt_by_work.get(work.id)
    if attempt is None:
        return "not-started"
    if receipt is None:
        return "missing"
    if receipt.attempt_id != attempt.id:
        return "stale"
    return "ready"


def _integration_state(workspace: Workspace, work: Any, context: _ReadContext) -> str:
    if work.status in {"closed", "completed", "done"}:
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
    attempt = _attempt_for_work(context, work)
    if attempt and _low_risk_receipt_ready(work, attempt, context):
        return "receipt-ready"
    review = context.latest_review_by_work.get(work.id)
    if review and review.verdict == "accept-ready" and _approval_quorum_met(work, review, context):
        return "ready"
    if context.open_decision_by_work.get(work.id):
        return "blocked-by-decision"
    return "not-ready"


def _approval_progress(work: Any, context: _ReadContext) -> str:
    review = context.latest_review_by_work.get(work.id)
    if review is None:
        return f"0/{work.required_approval_count}"
    count = _qualified_approval_count(work, review, context)
    return f"{count}/{work.required_approval_count}"


def _approval_quorum_met(work: Any, review: Any, context: _ReadContext) -> bool:
    if work.required_approval_count == 0:
        return True
    return _qualified_approval_count(work, review, context) >= work.required_approval_count


def _qualified_approval_count(work: Any, review: Any, context: _ReadContext) -> int:
    seen_humans: set[str] = set()
    for decision in context.human_decisions_by_work.get(work.id, []):
        if decision.work_item_id != work.id:
            continue
        if decision.reviewed_head != review.reviewed_head:
            continue
        if decision.status not in {"accepted", "approved"} and decision.decision not in {
            "accepted",
            "approved",
        }:
            continue
        if work.required_approval_capability:
            human = context.humans_by_id.get(decision.human_id)
            if not human or work.required_approval_capability not in human.approval_capabilities:
                continue
        seen_humans.add(decision.human_id)
    return len(seen_humans)


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


def _build_active_parallel_work(
    workspace: Workspace,
    work_by_id: dict[str, Any],
    workbenches_by_id: dict[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for attempt in workspace.attempts:
        if attempt.status != "active":
            continue
        work = work_by_id.get(attempt.work_item_id)
        if work is None:
            continue
        workbench = workbenches_by_id.get(work.workbench_id) if work.workbench_id else None
        entries.append(
            {
                "work_item_id": work.id,
                "work_item_title": work.title,
                "workbench_id": work.workbench_id,
                "workbench_label": workbench.label if workbench else "",
                "attempt_id": attempt.id,
                "actor": attempt.actor,
                "status": attempt.status,
                "branch": attempt.branch,
                "workspace_path": attempt.workspace_path,
                "started_at": attempt.started_at,
                "updated_at": attempt.updated_at,
                "output_targets": _attempt_targets(work, attempt),
            }
        )
    return sorted(entries, key=lambda item: (item["workbench_id"], item["work_item_id"]))


def _build_coordination_warnings(
    workspace: Workspace,
    current_attempt_by_work: dict[str, Any],
) -> list[dict[str, Any]]:
    subjects = _coordination_subjects(workspace, current_attempt_by_work)
    warnings: list[dict[str, Any]] = []
    for index, left in enumerate(subjects):
        for right in subjects[index + 1 :]:
            if left["workbench_id"] != right["workbench_id"]:
                continue
            if "exclusive" not in {left["parallel_policy"], right["parallel_policy"]}:
                continue
            overlap = sorted(left["normalized_targets"] & right["normalized_targets"])
            if not overlap:
                continue
            warnings.append(
                {
                    "workbench_id": left["workbench_id"],
                    "target": overlap[0],
                    "targets": overlap,
                    "work_item_ids": [left["work_item_id"], right["work_item_id"]],
                    "message": (
                        f"{left['work_item_id']} and {right['work_item_id']} both target "
                        f"{overlap[0]} with exclusive coordination."
                    ),
                }
            )
    return warnings


def _coordination_subjects(
    workspace: Workspace,
    current_attempt_by_work: dict[str, Any],
) -> list[dict[str, Any]]:
    subjects: list[dict[str, Any]] = []
    for work in workspace.work_items:
        if not work.workbench_id or work.status in {"closed", "completed", "done", "blocked"}:
            continue
        attempt = current_attempt_by_work.get(work.id)
        has_active_attempt = attempt is not None and attempt.status == "active"
        has_active_work = attempt is None and work.status in {
            "proposed",
            "active",
            "in-review",
            "needs-human",
        }
        if not (has_active_attempt or has_active_work):
            continue
        targets = _conflict_targets(work)
        normalized_targets = {_normalize_target(target) for target in targets if target.strip()}
        if not normalized_targets:
            continue
        subjects.append(
            {
                "work_item_id": work.id,
                "workbench_id": work.workbench_id,
                "parallel_policy": work.parallel_policy,
                "normalized_targets": normalized_targets,
            }
        )
    return subjects


def _group_active_attempts(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(entry["work_item_id"], []).append(entry)
    return grouped


def _group_warning_messages(warnings: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for warning in warnings:
        for work_id in warning["work_item_ids"]:
            grouped.setdefault(work_id, []).append(warning["message"])
    return grouped


def _conflict_targets(work: Any) -> list[str]:
    if work.conflict_targets:
        return work.conflict_targets
    return work.output_targets


def _normalize_target(target: str) -> str:
    return " ".join(target.strip().lower().replace("\\", "/").split())


def _attempt_targets(work: Any, attempt: Any) -> list[str]:
    if attempt.output_targets:
        return attempt.output_targets
    if work.conflict_targets:
        return work.conflict_targets
    if work.output_targets:
        return work.output_targets
    return attempt.changed_files


def _ai_safe_to_proceed(work: Any, attention: str, context: _ReadContext) -> bool:
    if attention in {"needs-human-decision", "ready-to-integrate", "receipt-ready", "blocked", "closed"}:
        return False
    recommended, _ = recommend_intensity(work)
    if recommended == "high" and _attempt_for_work(context, work) is None:
        return False
    return True


def _low_risk_receipt_ready(work: Any, attempt: Any, context: _ReadContext) -> bool:
    if work.risk not in {"R1", "R2"}:
        return False
    if attempt.status not in {"complete", "completed"}:
        return False
    receipt = context.latest_receipt_by_work.get(work.id)
    return receipt is not None and receipt.attempt_id == attempt.id and not receipt.external_writes


def _learning_signal(context: _ReadContext, palari: Any | None) -> str:
    if palari is None:
        return ""
    linked_outcomes = [
        context.outcomes_by_id[outcome_id]
        for outcome_id in palari.outcomes
        if outcome_id in context.outcomes_by_id
    ]
    if not linked_outcomes:
        return ""
    latest = max(linked_outcomes, key=lambda outcome: outcome.timestamp)
    if latest.follow_up_needed:
        return f"Outcome follow-up: {latest.follow_up_needed[0]}"
    if latest.model_worker_notes:
        return f"Model note: {latest.model_worker_notes[0]}"
    return latest.summary


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
            grouped.setdefault(record.work_item_id, []).append(record)
    for plans in grouped.values():
        plans.sort(key=_record_time_key, reverse=True)
    return grouped


def _queued_integration_outbox_by_work(records: Iterable[T]) -> dict[str, list[T]]:
    grouped: dict[str, list[T]] = {}
    for record in records:
        if getattr(record, "status", "") == "queued":
            grouped.setdefault(record.work_item_id, []).append(record)
    for items in grouped.values():
        items.sort(key=_record_time_key, reverse=True)
    return grouped


def _latest_by_work(records: Iterable[T]) -> dict[str, T]:
    latest: dict[str, T] = {}
    keys: dict[str, tuple[str, str, str]] = {}
    for record in records:
        work_id = getattr(record, "work_item_id")
        key = _record_time_key(record)
        if work_id not in latest or key >= keys[work_id]:
            latest[work_id] = record
            keys[work_id] = key
    return latest


def _record_time_key(record: object) -> tuple[str, str, str]:
    return (
        str(getattr(record, "timestamp", "") or getattr(record, "updated_at", "")),
        str(getattr(record, "started_at", "")),
        str(getattr(record, "id", "")),
    )
