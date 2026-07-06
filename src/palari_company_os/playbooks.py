from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import PlaybookSource, WorkItem, to_plain
from .workspace import Workspace, WorkspaceError, current_attempt_for_work, latest_for_work


SUPERPOWERS_PLAYBOOKS: dict[str, dict[str, str]] = {
    "brainstorming": {
        "label": "Brainstorming",
        "description": "Explore product intent and options before choosing a plan.",
    },
    "writing-plans": {
        "label": "Writing Plans",
        "description": "Turn a chosen direction into an execution plan.",
    },
    "executing-plans": {
        "label": "Executing Plans",
        "description": "Work through a plan while tracking progress and preserving context.",
    },
    "verification-before-completion": {
        "label": "Verification Before Completion",
        "description": "Verify evidence before claiming work is complete.",
    },
    "requesting-code-review": {
        "label": "Requesting Code Review",
        "description": "Prepare focused review context for completed changes.",
    },
    "systematic-debugging": {
        "label": "Systematic Debugging",
        "description": "Use a disciplined debugging loop for failures and regressions.",
    },
    "subagent-driven-development": {
        "label": "Subagent-Driven Development",
        "description": "Split complex work across focused agent roles.",
    },
}

PLAYBOOK_ACTION_GUIDANCE = {
    "brainstorming": "Clarify the shape of the work before choosing implementation steps.",
    "writing-plans": "Write a short plan that names scope, order, and verification before editing.",
    "executing-plans": "Keep this as one bounded slice and preserve enough context to resume.",
    "verification-before-completion": "Run focused tests and full verification before claiming done.",
    "requesting-code-review": "Summarize changed files, checks, risks, and specific review focus.",
    "systematic-debugging": "If checks fail, fix the smallest failing cause and rerun the relevant check.",
    "subagent-driven-development": (
        "Use separate focused agents only for genuinely separable research or review."
    ),
}

CORE_DEFAULT_PLAYBOOK_IDS = (
    "superpowers:verification-before-completion",
    "superpowers:executing-plans",
    "superpowers:systematic-debugging",
)

OPEN_WORK_STATUSES = {"proposed", "active", "in-review", "needs-human", "blocked"}


@dataclass(frozen=True)
class Playbook:
    id: str
    source_id: str
    key: str
    label: str
    description: str
    uri: str
    enabled: bool
    core_default: bool = False


@dataclass(frozen=True)
class PlaybookRecommendation:
    id: str
    label: str
    source_id: str
    reason: str
    selected_by_user: bool = False
    core_default: bool = False
    action_guidance: str = ""


def playbook_catalog(workspace: Workspace) -> dict[str, Any]:
    playbooks = available_playbooks(workspace)
    playbook_by_id = {playbook.id: playbook for playbook in playbooks}
    return {
        "workspace": workspace.name,
        "sources": [to_plain(source) for source in workspace.playbook_sources],
        "core_defaults": [
            to_plain(playbook_by_id[playbook_id])
            for playbook_id in CORE_DEFAULT_PLAYBOOK_IDS
            if playbook_id in playbook_by_id
        ],
        "playbooks": [to_plain(playbook) for playbook in playbooks],
    }


def available_playbooks(workspace: Workspace) -> list[Playbook]:
    playbooks: list[Playbook] = []
    for source in workspace.playbook_sources:
        if not source.enabled:
            continue
        for key in source.included_playbooks:
            playbooks.append(_playbook_from_source(source, key))
    return playbooks


def recommend_playbooks(workspace: Workspace, work_id: str) -> dict[str, Any]:
    work = workspace.work_item(work_id)
    if work is None:
        known = ", ".join(sorted(item.id for item in workspace.work_items))
        raise WorkspaceError(f"unknown work item {work_id}; known work items: {known}")

    available = {playbook.id: playbook for playbook in available_playbooks(workspace)}
    manual = _manual_recommendations(work, available)
    defaults = _core_default_recommendations(work, available)
    automatic = _automatic_recommendations(workspace, work, available)
    merged = _merge_recommendations([*manual, *defaults, *automatic])
    return {
        "workspace": workspace.name,
        "work_item": work.id,
        "title": work.title,
        "sources": [to_plain(source) for source in workspace.playbook_sources],
        "selected": [to_plain(item) for item in manual],
        "defaults": [to_plain(item) for item in defaults],
        "suggested": [to_plain(item) for item in automatic],
        "recommended": [to_plain(item) for item in merged],
        "operating_guidance": _operating_guidance(merged),
        "next_action": _playbook_next_action(workspace, work, merged),
    }


def recommended_playbook_ids(workspace: Workspace, work: WorkItem) -> list[str]:
    payload = recommend_playbooks(workspace, work.id)
    return [item["id"] for item in payload["recommended"]]


def _manual_recommendations(
    work: WorkItem, available: dict[str, Playbook]
) -> list[PlaybookRecommendation]:
    recommendations: list[PlaybookRecommendation] = []
    for playbook_id in work.recommended_playbooks:
        playbook = available.get(playbook_id)
        if playbook:
            recommendations.append(
                PlaybookRecommendation(
                    id=playbook.id,
                    label=playbook.label,
                    source_id=playbook.source_id,
                    reason="Pinned on the work item by a human or Palari.",
                    selected_by_user=True,
                    core_default=playbook.core_default,
                    action_guidance=_action_guidance(playbook),
                )
            )
    return recommendations


def _core_default_recommendations(
    work: WorkItem, available: dict[str, Playbook]
) -> list[PlaybookRecommendation]:
    if work.status not in OPEN_WORK_STATUSES:
        return []

    reasons = {
        "superpowers:verification-before-completion": (
            "Core default: verify evidence before claiming work is complete."
        ),
        "superpowers:executing-plans": (
            "Core default: keep long-running work structured and resumable."
        ),
        "superpowers:systematic-debugging": (
            "Core default: use a disciplined repair loop when evidence or review fails."
        ),
    }

    recommendations: list[PlaybookRecommendation] = []
    for playbook_id in CORE_DEFAULT_PLAYBOOK_IDS:
        playbook = available.get(playbook_id)
        if not playbook:
            continue
        recommendations.append(
            PlaybookRecommendation(
                id=playbook.id,
                label=playbook.label,
                source_id=playbook.source_id,
                reason=reasons[playbook_id],
                core_default=True,
                action_guidance=_action_guidance(playbook),
            )
        )
    return recommendations


def _automatic_recommendations(
    workspace: Workspace, work: WorkItem, available: dict[str, Playbook]
) -> list[PlaybookRecommendation]:
    recommendations: list[PlaybookRecommendation] = []

    def add(playbook_id: str, reason: str) -> None:
        playbook = available.get(playbook_id)
        if not playbook:
            return
        recommendations.append(
            PlaybookRecommendation(
                id=playbook.id,
                label=playbook.label,
                source_id=playbook.source_id,
                reason=reason,
                action_guidance=_action_guidance(playbook),
            )
        )

    text = f"{work.title} {work.scope} {' '.join(work.verification_expectations)}".lower()
    attempt = current_attempt_for_work(work, workspace.attempts)
    evidence = latest_for_work(workspace.evidence_runs, work.id)
    review = latest_for_work(workspace.review_verdicts, work.id)
    outcome = latest_for_work(workspace.outcomes, work.id)

    if attempt is None and work.status in {"proposed", "active"}:
        add(
            "superpowers:brainstorming",
            "No attempt exists yet; clarify the shape of the work before execution.",
        )
        if any(word in text for word in ("plan", "design", "architecture", "scope", "split")):
            add(
                "superpowers:writing-plans",
                "The work appears planning-heavy; produce an explicit execution plan.",
            )

    if evidence is None and attempt is not None:
        add(
            "superpowers:verification-before-completion",
            "An attempt exists without evidence; verify before making completion claims.",
        )
    elif evidence is not None and attempt is not None and evidence.head_sha != _attempt_head(attempt):
        add(
            "superpowers:verification-before-completion",
            "Latest evidence is stale for the current attempt; refresh verification first.",
        )
    elif evidence is not None and evidence.status != "passed":
        add(
            "superpowers:systematic-debugging",
            f"Latest evidence is {evidence.status}; use a disciplined repair loop.",
        )

    if (
        evidence is not None
        and evidence.status == "passed"
        and attempt is not None
        and evidence.head_sha == _attempt_head(attempt)
        and review is None
    ):
        add(
            "superpowers:requesting-code-review",
            "Evidence exists but no review has inspected it yet.",
        )
    elif review is not None and review.verdict == "changes-requested":
        add(
            "superpowers:systematic-debugging",
            "Review requested changes; repair bounded findings before refreshing review.",
        )

    if work.risk in {"R4", "R5"} or work.intensity == "high":
        add(
            "superpowers:subagent-driven-development",
            "High-risk or high-intensity work may benefit from separated roles.",
        )

    if outcome and (outcome.failed or outcome.follow_up_needed):
        add(
            "superpowers:executing-plans",
            "Recent outcome has failures or follow-ups; keep the next execution structured.",
        )

    return recommendations


def _merge_recommendations(
    recommendations: list[PlaybookRecommendation],
) -> list[PlaybookRecommendation]:
    merged: dict[str, PlaybookRecommendation] = {}
    for recommendation in recommendations:
        existing = merged.get(recommendation.id)
        if (
            existing is None
            or recommendation.selected_by_user
            or (existing.core_default and not recommendation.core_default)
        ):
            merged[recommendation.id] = recommendation
    return list(merged.values())


def _playbook_next_action(
    workspace: Workspace,
    work: WorkItem,
    recommendations: list[PlaybookRecommendation],
) -> str:
    if not workspace.playbook_sources:
        return "Add a playbook source such as Superpowers before asking for recommendations."
    if not recommendations:
        return "No playbook recommendation right now; continue with the normal queue next action."
    ids = ", ".join(item.id for item in recommendations)
    return f"Use these playbooks as guidance for the next agent run: {ids}."


def _operating_guidance(
    recommendations: list[PlaybookRecommendation],
) -> list[dict[str, str]]:
    return [
        {
            "id": recommendation.id,
            "label": recommendation.label,
            "guidance": recommendation.action_guidance,
        }
        for recommendation in recommendations
        if recommendation.action_guidance
    ]


def _playbook_from_source(source: PlaybookSource, key: str) -> Playbook:
    metadata = SUPERPOWERS_PLAYBOOKS.get(key, {})
    playbook_id = f"{source.id}:{key}"
    return Playbook(
        id=playbook_id,
        source_id=source.id,
        key=key,
        label=metadata.get("label", key.replace("-", " ").title()),
        description=metadata.get("description", ""),
        uri=_playbook_uri(source, key),
        enabled=source.enabled,
        core_default=playbook_id in CORE_DEFAULT_PLAYBOOK_IDS,
    )


def _playbook_uri(source: PlaybookSource, key: str) -> str:
    if not source.uri:
        return ""
    if source.provider == "github":
        ref = source.ref or "main"
        return f"{source.uri.rstrip('/')}/blob/{ref}/skills/{key}/SKILL.md"
    return source.uri


def _action_guidance(playbook: Playbook) -> str:
    return PLAYBOOK_ACTION_GUIDANCE.get(playbook.key, "")


def _attempt_head(attempt: Any) -> str:
    return getattr(attempt, "head_sha", "") or (attempt.commits[-1] if attempt.commits else "")
