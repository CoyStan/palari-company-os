from __future__ import annotations

from typing import Any, Iterable, TypeVar

from .errors import WorkspaceError
from .models import Attempt, EvidenceRun, HumanDecision, Receipt, ReviewVerdict, WorkItem


T = TypeVar("T")

COLLECTION_KEYS = (
    "goals",
    "humans",
    "palaris",
    "sources",
    "work_items",
    "attempts",
    "evidence_runs",
    "review_verdicts",
    "human_decisions",
    "receipts",
    "decisions",
    "outcomes",
)

OPTIONAL_COLLECTION_KEYS = ("playbook_sources",)

ROOT_FIELDS = {"schema_version", "name", *COLLECTION_KEYS, *OPTIONAL_COLLECTION_KEYS}

ALLOWED_RECORD_FIELDS = {
    "goals": {
        "id",
        "title",
        "owner",
        "status",
        "priority",
        "success_criteria",
        "linked_palaris",
        "linked_work",
        "linked_decisions",
    },
    "humans": {
        "id",
        "name",
        "aliases",
        "role",
        "authority_level",
        "approval_capabilities",
        "skills",
        "ownership_areas",
        "availability",
        "capacity_signal",
    },
    "palaris": {
        "id",
        "name",
        "role",
        "scope",
        "allowed_inputs",
        "forbidden_inputs",
        "forbidden_actions",
        "standards",
        "memory_sources",
        "default_worker",
        "owner_human",
        "linked_goals",
        "active_work",
        "outcomes",
    },
    "sources": {
        "id",
        "label",
        "kind",
        "provider",
        "uri",
        "external_id",
        "access_mode",
        "selected",
        "owner_human",
        "allowed_palaris",
        "last_seen_revision",
        "last_read_at",
    },
    "work_items": {
        "id",
        "title",
        "goal",
        "palari",
        "risk",
        "intensity",
        "status",
        "scope",
        "allowed_resources",
        "allowed_sources",
        "allowed_actions",
        "output_targets",
        "forbidden_actions",
        "acceptance_target",
        "verification_expectations",
        "current_attempt",
        "required_approval_count",
        "required_approval_capability",
        "recommended_playbooks",
    },
    "playbook_sources": {
        "id",
        "label",
        "provider",
        "uri",
        "ref",
        "license",
        "enabled",
        "included_playbooks",
        "install_hint",
    },
    "attempts": {
        "id",
        "work_item_id",
        "actor",
        "status",
        "branch",
        "workspace_path",
        "model_or_worker",
        "commits",
        "changed_files",
        "cleanliness",
        "result",
        "started_at",
    },
    "evidence_runs": {
        "id",
        "work_item_id",
        "attempt_id",
        "head_sha",
        "status",
        "base_ref",
        "commands",
        "artifacts",
        "summary",
        "freshness",
        "timestamp",
    },
    "review_verdicts": {
        "id",
        "work_item_id",
        "reviewed_head",
        "reviewer",
        "verdict",
        "findings",
        "checks_inspected",
        "residual_risks",
        "timestamp",
    },
    "human_decisions": {
        "id",
        "work_item_id",
        "human_id",
        "reviewed_head",
        "decision",
        "status",
        "acceptance_mode",
        "quorum_status",
        "evidence_reference",
        "review_reference",
        "timestamp",
    },
    "receipts": {
        "id",
        "work_item_id",
        "attempt_id",
        "actor",
        "sources_used",
        "actions_taken",
        "outputs_created",
        "external_writes",
        "not_done",
        "undo_refs",
        "timestamp",
    },
    "decisions": {
        "id",
        "question",
        "status",
        "context",
        "options",
        "tradeoffs",
        "recommendation",
        "safe_default",
        "required_human",
        "required_role",
        "due_date",
        "linked_goal",
        "linked_work",
        "linked_palari",
        "result",
    },
    "outcomes": {
        "id",
        "work_item_id",
        "summary",
        "status",
        "what_happened",
        "what_changed",
        "useful",
        "failed",
        "follow_up_needed",
        "model_worker_notes",
        "timestamp",
    },
}

GOAL_STATUSES = {"active", "paused", "completed", "closed", "archived"}
WORK_STATUSES = {
    "proposed",
    "active",
    "in-review",
    "needs-human",
    "blocked",
    "completed",
    "closed",
    "done",
}
TERMINAL_WORK_STATUSES = {"completed", "closed", "done"}
RISKS = {"R1", "R2", "R3", "R4", "R5"}
INTENSITIES = {"light", "standard", "high"}
ATTEMPT_STATUSES = {"active", "complete", "completed", "failed", "blocked"}
EVIDENCE_STATUSES = {"passed", "failed", "skipped"}
REVIEW_VERDICTS = {"accept-ready", "changes-requested", "needs-human-decision", "blocked"}
DECISION_STATUSES = {"open", "decided", "answered", "closed", "blocked"}
HUMAN_DECISION_STATUSES = {
    "recorded",
    "accepted",
    "approved",
    "rejected",
    "changes-requested",
    "blocked",
}
HUMAN_DECISION_VALUES = {
    "accepted",
    "approved",
    "rejected",
    "needs-changes",
    "changes-requested",
    "blocked",
}
QUORUM_STATUSES = {"", "pending", "met", "not-met"}
OUTCOME_STATUSES = {"captured", "completed", "closed"}


def validate_raw_contract(raw: dict[str, object]) -> None:
    _reject_unknown_fields("workspace", raw, ROOT_FIELDS)
    if "name" not in raw:
        raise WorkspaceError("workspace.name is required")
    if not isinstance(raw["name"], str) or not raw["name"]:
        raise WorkspaceError("workspace.name must be a non-empty string")
    for key in COLLECTION_KEYS:
        if key not in raw:
            raise WorkspaceError(f"workspace.{key} collection is required")
        _validate_collection(raw, key)
    for key in OPTIONAL_COLLECTION_KEYS:
        if key in raw:
            _validate_collection(raw, key)


def _validate_collection(raw: dict[str, object], key: str) -> None:
    records = raw[key]
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise WorkspaceError(f"{key} must be a list of objects")
    for index, record in enumerate(records):
        label = _record_label(key, index, record)
        _reject_unknown_fields(label, record, ALLOWED_RECORD_FIELDS[key])


def validate_workspace_contract(workspace: Any) -> None:
    attempts_by_id = {attempt.id: attempt for attempt in workspace.attempts}
    evidence_by_id = {evidence.id: evidence for evidence in workspace.evidence_runs}
    reviews_by_id = {review.id: review for review in workspace.review_verdicts}
    work_by_id = {work.id: work for work in workspace.work_items}
    humans_by_id = {human.id: human for human in workspace.humans}
    sources_by_id = {source.id: source for source in workspace.sources}

    for goal in workspace.goals:
        _require_allowed_value("goals", goal.id, "status", goal.status, GOAL_STATUSES)

    for work in workspace.work_items:
        _require_allowed_value("work_items", work.id, "status", work.status, WORK_STATUSES)
        _require_allowed_value("work_items", work.id, "risk", work.risk, RISKS)
        _require_allowed_value("work_items", work.id, "intensity", work.intensity, INTENSITIES)

    for attempt in workspace.attempts:
        _require_allowed_value("attempts", attempt.id, "status", attempt.status, ATTEMPT_STATUSES)

    for evidence in workspace.evidence_runs:
        _require_allowed_value(
            "evidence_runs", evidence.id, "status", evidence.status, EVIDENCE_STATUSES
        )
        attempt = attempts_by_id[evidence.attempt_id]
        if evidence.work_item_id != attempt.work_item_id:
            raise WorkspaceError(
                f"evidence_runs.{evidence.id}.attempt_id references attempt "
                f"{attempt.id} for different work item {attempt.work_item_id}"
            )

    for review in workspace.review_verdicts:
        _require_allowed_value(
            "review_verdicts", review.id, "verdict", review.verdict, REVIEW_VERDICTS
        )

    for decision in workspace.decisions:
        _require_allowed_value("decisions", decision.id, "status", decision.status, DECISION_STATUSES)

    for human_decision in workspace.human_decisions:
        _require_allowed_value(
            "human_decisions",
            human_decision.id,
            "status",
            human_decision.status,
            HUMAN_DECISION_STATUSES,
        )
        _require_allowed_value(
            "human_decisions",
            human_decision.id,
            "decision",
            human_decision.decision,
            HUMAN_DECISION_VALUES,
        )
        _require_allowed_value(
            "human_decisions",
            human_decision.id,
            "quorum_status",
            human_decision.quorum_status,
            QUORUM_STATUSES,
        )
        if _is_acceptance(human_decision):
            _validate_accepted_human_decision(
                human_decision,
                work_by_id,
                humans_by_id,
                attempts_by_id,
                evidence_by_id,
                reviews_by_id,
            )

    for receipt in workspace.receipts:
        _validate_receipt(receipt, work_by_id, attempts_by_id, sources_by_id)

    for outcome in workspace.outcomes:
        _require_allowed_value("outcomes", outcome.id, "status", outcome.status, OUTCOME_STATUSES)

    for work in workspace.work_items:
        if work.status in TERMINAL_WORK_STATUSES:
            _validate_completed_work(workspace, work, attempts_by_id)


def _reject_unknown_fields(label: str, record: dict[str, object], allowed: set[str]) -> None:
    unknown = sorted(set(record) - allowed)
    if unknown:
        fields = ", ".join(unknown)
        raise WorkspaceError(f"{label} has unknown field(s): {fields}")


def _record_label(collection: str, index: int, record: dict[str, object]) -> str:
    record_id = record.get("id")
    if isinstance(record_id, str) and record_id:
        return f"{collection}.{record_id}"
    return f"{collection}[{index}]"


def _require_allowed_value(
    collection: str,
    record_id: str,
    field: str,
    value: str,
    allowed: set[str],
) -> None:
    if value not in allowed:
        allowed_values = ", ".join(sorted(item for item in allowed if item))
        if "" in allowed:
            allowed_values = f"empty, {allowed_values}"
        raise WorkspaceError(
            f"{collection}.{record_id}.{field} has unsupported value {value!r}; "
            f"expected one of: {allowed_values}"
        )


def _validate_accepted_human_decision(
    decision: HumanDecision,
    work_by_id: dict[str, WorkItem],
    humans_by_id: dict[str, Any],
    attempts_by_id: dict[str, Attempt],
    evidence_by_id: dict[str, EvidenceRun],
    reviews_by_id: dict[str, ReviewVerdict],
) -> None:
    work = work_by_id[decision.work_item_id]
    human = humans_by_id[decision.human_id]
    if work.required_approval_capability and (
        work.required_approval_capability not in human.approval_capabilities
    ):
        raise WorkspaceError(
            f"human_decisions.{decision.id}.human_id lacks required approval "
            f"capability {work.required_approval_capability}"
        )
    if not decision.evidence_reference:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.evidence_reference is required "
            "for accepted decisions"
        )
    if not decision.review_reference:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.review_reference is required "
            "for accepted decisions"
        )
    evidence = evidence_by_id[decision.evidence_reference]
    review = reviews_by_id[decision.review_reference]
    if evidence.work_item_id != work.id:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.evidence_reference points to "
            f"evidence for {evidence.work_item_id}, not {work.id}"
        )
    if review.work_item_id != work.id:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.review_reference points to "
            f"review for {review.work_item_id}, not {work.id}"
        )
    attempt = attempts_by_id[evidence.attempt_id]
    if work.current_attempt and evidence.attempt_id != work.current_attempt:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.evidence_reference is not for "
            f"current attempt {work.current_attempt}"
        )
    _require_fresh_passed_evidence(work.id, attempt, evidence)
    _require_fresh_accept_ready_review(work.id, evidence, review)
    if decision.reviewed_head != review.reviewed_head:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.reviewed_head does not match "
            f"review_reference head {review.reviewed_head}"
        )


def _validate_completed_work(
    workspace: Any,
    work: WorkItem,
    attempts_by_id: dict[str, Attempt],
) -> None:
    if _open_linked_decision(workspace, work.id) is not None:
        raise WorkspaceError(f"work_items.{work.id}.status cannot be terminal with open decisions")
    if not work.current_attempt:
        raise WorkspaceError(f"work_items.{work.id}.status is terminal but current_attempt is missing")
    attempt = attempts_by_id[work.current_attempt]
    evidence = _latest_for_work(workspace.evidence_runs, work.id)
    if evidence is None:
        raise WorkspaceError(f"work_items.{work.id}.status is terminal but evidence is missing")
    if evidence.attempt_id != work.current_attempt:
        raise WorkspaceError(
            f"work_items.{work.id}.status is terminal but latest evidence is "
            f"not for current attempt {work.current_attempt}"
        )
    _require_fresh_passed_evidence(work.id, attempt, evidence)
    review = _latest_for_work(workspace.review_verdicts, work.id)
    if review is None:
        raise WorkspaceError(f"work_items.{work.id}.status is terminal but review is missing")
    _require_fresh_accept_ready_review(work.id, evidence, review)
    count = _qualified_approval_count(workspace, work, review)
    if count < work.required_approval_count:
        raise WorkspaceError(
            f"work_items.{work.id}.status is terminal but approval quorum is "
            f"{count}/{work.required_approval_count}"
        )


def _validate_receipt(
    receipt: Receipt,
    work_by_id: dict[str, WorkItem],
    attempts_by_id: dict[str, Attempt],
    sources_by_id: dict[str, Any],
) -> None:
    work = work_by_id[receipt.work_item_id]
    attempt = attempts_by_id[receipt.attempt_id]
    if attempt.work_item_id != work.id:
        raise WorkspaceError(
            f"receipts.{receipt.id}.attempt_id references attempt "
            f"{attempt.id} for different work item {attempt.work_item_id}"
        )
    if receipt.actor not in {attempt.actor, work.palari}:
        raise WorkspaceError(
            f"receipts.{receipt.id}.actor must match attempt actor {attempt.actor} "
            f"or work Palari {work.palari}"
        )
    for source_id in receipt.sources_used:
        source = sources_by_id[source_id]
        if source_id not in work.allowed_sources:
            raise WorkspaceError(
                f"receipts.{receipt.id}.sources_used includes unallowed source {source_id}"
            )
        if source.allowed_palaris and work.palari not in source.allowed_palaris:
            raise WorkspaceError(
                f"receipts.{receipt.id}.sources_used includes source {source_id} "
                f"not allowed for Palari {work.palari}"
            )
    if receipt.external_writes and not _allows_external_writes(work):
        raise WorkspaceError(
            f"receipts.{receipt.id}.external_writes requires allowed action external_write"
        )


def _allows_external_writes(work: WorkItem) -> bool:
    allowed = set(work.allowed_actions)
    return bool(allowed & {"external_write", "write_external", "write"})


def _require_fresh_passed_evidence(
    work_id: str,
    attempt: Attempt,
    evidence: EvidenceRun,
) -> None:
    if evidence.status != "passed":
        raise WorkspaceError(
            f"work_items.{work_id} evidence {evidence.id} is {evidence.status}, not passed"
        )
    if evidence.head_sha != _attempt_head(attempt):
        raise WorkspaceError(f"work_items.{work_id} evidence {evidence.id} is stale")


def _require_fresh_accept_ready_review(
    work_id: str,
    evidence: EvidenceRun,
    review: ReviewVerdict,
) -> None:
    if review.verdict != "accept-ready":
        raise WorkspaceError(
            f"work_items.{work_id} review {review.id} is {review.verdict}, not accept-ready"
        )
    if review.reviewed_head != evidence.head_sha:
        raise WorkspaceError(f"work_items.{work_id} review {review.id} is stale")


def _qualified_approval_count(
    workspace: Any,
    work: WorkItem,
    review: ReviewVerdict,
) -> int:
    seen_humans: set[str] = set()
    humans_by_id = {human.id: human for human in workspace.humans}
    for decision in workspace.human_decisions:
        if decision.work_item_id != work.id:
            continue
        if decision.reviewed_head != review.reviewed_head:
            continue
        if not _is_acceptance(decision):
            continue
        human = humans_by_id.get(decision.human_id)
        if work.required_approval_capability and (
            human is None or work.required_approval_capability not in human.approval_capabilities
        ):
            continue
        seen_humans.add(decision.human_id)
    return len(seen_humans)


def _is_acceptance(decision: HumanDecision) -> bool:
    return decision.status in {"accepted", "approved"} or decision.decision in {
        "accepted",
        "approved",
    }


def _attempt_head(attempt: Attempt) -> str:
    return attempt.commits[-1] if attempt.commits else ""


def _open_linked_decision(workspace: Any, work_id: str) -> Any | None:
    for decision in workspace.decisions:
        if decision.linked_work == work_id and decision.status == "open":
            return decision
    return None


def _latest_for_work(records: Iterable[T], work_id: str) -> T | None:
    matching = [record for record in records if getattr(record, "work_item_id") == work_id]
    if not matching:
        return None
    return sorted(matching, key=lambda item: getattr(item, "timestamp", ""))[-1]
