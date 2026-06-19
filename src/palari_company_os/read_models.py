from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import to_plain
from .workspace import Workspace, latest_for_work


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
    integration_state: str
    approval_progress: str
    recommended_intensity: str
    intensity_reason: str
    learning_signal: str


ATTENTION_PRIORITY = {
    "needs-human-decision": 0,
    "changes-requested": 1,
    "needs-review": 2,
    "needs-evidence": 3,
    "ready-to-integrate": 4,
    "ready-for-ai-work": 5,
    "blocked": 6,
    "closed": 7,
}


def queue_items(workspace: Workspace) -> list[QueueItem]:
    items = [_queue_item(workspace, work) for work in workspace.work_items]
    return sorted(items, key=lambda item: (ATTENTION_PRIORITY.get(item.attention, 99), item.id))


def detail(workspace: Workspace, work_id: str) -> dict[str, Any]:
    work = workspace.work_item(work_id)
    if work is None:
        known = ", ".join(sorted(item.id for item in workspace.work_items))
        raise KeyError(f"unknown work item {work_id}; known work items: {known}")

    goal = workspace.goal(work.goal)
    palari = workspace.palari(work.palari)
    attempt = latest_for_work(workspace.attempts, work.id)
    evidence = latest_for_work(workspace.evidence_runs, work.id)
    review = latest_for_work(workspace.review_verdicts, work.id)
    human_decision = latest_for_work(workspace.human_decisions, work.id)
    human_decisions = [
        decision for decision in workspace.human_decisions if decision.work_item_id == work.id
    ]
    outcome = latest_for_work(workspace.outcomes, work.id)
    linked_decisions = [decision for decision in workspace.decisions if decision.linked_work == work.id]
    queue_item = _queue_item(workspace, work)

    return {
        "work_item": to_plain(work),
        "goal": to_plain(goal) if goal else None,
        "palari": to_plain(palari) if palari else None,
        "attempt": to_plain(attempt) if attempt else None,
        "evidence": to_plain(evidence) if evidence else None,
        "review": to_plain(review) if review else None,
        "human_decision": to_plain(human_decision) if human_decision else None,
        "human_decisions": to_plain(human_decisions),
        "linked_decisions": to_plain(linked_decisions),
        "outcome": to_plain(outcome) if outcome else None,
        "attention": queue_item.attention,
        "why": queue_item.why,
        "next_action": queue_item.next_action,
        "safety": {
            "ai_safe_to_proceed": queue_item.ai_safe_to_proceed,
            "waiting_on_human": queue_item.waiting_on_human,
            "evidence_state": queue_item.evidence_state,
            "review_state": queue_item.review_state,
            "integration_state": queue_item.integration_state,
            "approval_progress": queue_item.approval_progress,
            "recommended_intensity": queue_item.recommended_intensity,
            "intensity_reason": queue_item.intensity_reason,
        },
    }


def _queue_item(workspace: Workspace, work: Any) -> QueueItem:
    goal = workspace.goal(work.goal)
    palari = workspace.palari(work.palari)
    owner = ""
    if palari and palari.owner_human:
        human = workspace.human(palari.owner_human)
        owner = human.name if human else palari.owner_human

    attention, why, next_action = _attention(workspace, work)
    evidence_state = _evidence_state(workspace, work)
    review_state = _review_state(workspace, work)
    integration_state = _integration_state(workspace, work)
    approval_progress = _approval_progress(workspace, work)
    recommended_intensity, intensity_reason = recommend_intensity(work)
    learning_signal = _learning_signal(workspace, palari)
    waiting_on_human = attention == "needs-human-decision"
    ai_safe_to_proceed = _ai_safe_to_proceed(workspace, work, attention)
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
        integration_state=integration_state,
        approval_progress=approval_progress,
        recommended_intensity=recommended_intensity,
        intensity_reason=intensity_reason,
        learning_signal=learning_signal,
    )


def _attention(workspace: Workspace, work: Any) -> tuple[str, str, str]:
    open_decision = _open_linked_decision(workspace, work.id)
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

    attempt = latest_for_work(workspace.attempts, work.id)
    if attempt is None:
        return (
            "ready-for-ai-work",
            "No execution attempt exists yet.",
            "Start a bounded attempt using the declared scope and authority limits.",
        )

    evidence = latest_for_work(workspace.evidence_runs, work.id)
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

    review = latest_for_work(workspace.review_verdicts, work.id)
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

    human_decision = latest_for_work(workspace.human_decisions, work.id)
    if review.verdict == "accept-ready" and human_decision is None:
        approval_progress = _approval_progress(workspace, work)
        return (
            "needs-human-decision",
            f"Review is accept-ready, but approval quorum is incomplete ({approval_progress}).",
            "Human accepts, requests changes, or blocks this work item.",
        )
    if review.verdict == "accept-ready" and not _approval_quorum_met(workspace, work, review):
        return (
            "needs-human-decision",
            f"Review is accept-ready, but approval quorum is incomplete ({_approval_progress(workspace, work)}).",
            "Collect the required human approval before integration.",
        )
    if human_decision and _approval_quorum_met(workspace, work, review):
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


def _open_linked_decision(workspace: Workspace, work_id: str) -> Any | None:
    for decision in workspace.decisions:
        if decision.linked_work == work_id and decision.status == "open":
            return decision
    return None


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


def _evidence_state(workspace: Workspace, work: Any) -> str:
    attempt = latest_for_work(workspace.attempts, work.id)
    evidence = latest_for_work(workspace.evidence_runs, work.id)
    if attempt is None:
        return "not-started"
    if evidence is None:
        return "missing"
    if evidence.head_sha != _attempt_head(attempt):
        return "stale"
    return evidence.status


def _review_state(workspace: Workspace, work: Any) -> str:
    evidence = latest_for_work(workspace.evidence_runs, work.id)
    review = latest_for_work(workspace.review_verdicts, work.id)
    if evidence is None:
        return "waiting-on-evidence"
    if review is None:
        return "missing"
    if review.reviewed_head != evidence.head_sha:
        return "stale"
    return review.verdict


def _integration_state(workspace: Workspace, work: Any) -> str:
    if work.status in {"closed", "completed", "done"}:
        return "closed"
    review = latest_for_work(workspace.review_verdicts, work.id)
    if review and review.verdict == "accept-ready" and _approval_quorum_met(workspace, work, review):
        return "ready"
    if _open_linked_decision(workspace, work.id):
        return "blocked-by-decision"
    return "not-ready"


def _approval_progress(workspace: Workspace, work: Any) -> str:
    review = latest_for_work(workspace.review_verdicts, work.id)
    if review is None:
        return f"0/{work.required_approval_count}"
    count = _qualified_approval_count(workspace, work, review)
    return f"{count}/{work.required_approval_count}"


def _approval_quorum_met(workspace: Workspace, work: Any, review: Any) -> bool:
    if work.required_approval_count == 0:
        return True
    return _qualified_approval_count(workspace, work, review) >= work.required_approval_count


def _qualified_approval_count(workspace: Workspace, work: Any, review: Any) -> int:
    seen_humans: set[str] = set()
    for decision in workspace.human_decisions:
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
            human = workspace.human(decision.human_id)
            if not human or work.required_approval_capability not in human.approval_capabilities:
                continue
        seen_humans.add(decision.human_id)
    return len(seen_humans)


def _ai_safe_to_proceed(workspace: Workspace, work: Any, attention: str) -> bool:
    if attention in {"needs-human-decision", "ready-to-integrate", "closed"}:
        return False
    recommended, _ = recommend_intensity(work)
    if recommended == "high" and latest_for_work(workspace.attempts, work.id) is None:
        return False
    return True


def _learning_signal(workspace: Workspace, palari: Any | None) -> str:
    if palari is None:
        return ""
    linked_outcomes = [outcome for outcome in workspace.outcomes if outcome.id in palari.outcomes]
    if not linked_outcomes:
        return ""
    latest = sorted(linked_outcomes, key=lambda outcome: outcome.timestamp)[-1]
    if latest.follow_up_needed:
        return f"Outcome follow-up: {latest.follow_up_needed[0]}"
    if latest.model_worker_notes:
        return f"Model note: {latest.model_worker_notes[0]}"
    return latest.summary
