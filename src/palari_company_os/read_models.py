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
        "linked_decisions": to_plain(linked_decisions),
        "outcome": to_plain(outcome) if outcome else None,
        "attention": queue_item.attention,
        "why": queue_item.why,
        "next_action": queue_item.next_action,
    }


def _queue_item(workspace: Workspace, work: Any) -> QueueItem:
    goal = workspace.goal(work.goal)
    palari = workspace.palari(work.palari)
    owner = ""
    if palari and palari.owner_human:
        human = workspace.human(palari.owner_human)
        owner = human.name if human else palari.owner_human

    attention, why, next_action = _attention(workspace, work)
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
        return (
            "needs-human-decision",
            "Review is accept-ready, but no human decision is recorded.",
            "Human accepts, requests changes, or blocks this work item.",
        )
    if human_decision and human_decision.status in {"accepted", "approved"}:
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

