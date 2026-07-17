from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, TypeVar

from .errors import WorkspaceError
from .integration_contracts import PROVIDER_ACTIONS, supported_actions_for_mode
from .models import (
    AcceptanceRecord,
    Attempt,
    AuthorityProfile,
    Capability,
    EvidenceRun,
    HumanDecision,
    Integration,
    IntegrationOutboxItem,
    IntegrationPlan,
    Proposal,
    Receipt,
    ReviewVerdict,
    WorkItem,
)
from .path_policy import path_allowed, validate_workspace_path
from .record_order import record_time_key, timestamp_order


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

OPTIONAL_COLLECTION_KEYS = (
    "playbook_sources",
    "workbenches",
    "capabilities",
    "authority_profiles",
    "integrations",
    "integration_plans",
    "integration_outbox",
    "proposals",
    "acceptance_records",
)
COLLECTION_FILE_KEYS = (*COLLECTION_KEYS, *OPTIONAL_COLLECTION_KEYS)

ROOT_FIELDS = {
    "schema_version",
    "name",
    "collection_files",
    *COLLECTION_KEYS,
    *OPTIONAL_COLLECTION_KEYS,
}

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
        "data_class",
        "authority",
        "steward_human",
        "freshness_sla",
        "redaction_required",
        "last_seen_revision",
        "last_read_at",
    },
    "workbenches": {
        "id",
        "label",
        "summary",
        "parent_workbench_id",
        "goal_ids",
        "palari_ids",
        "human_ids",
        "source_ids",
        "output_target_ids",
        "status",
    },
    "work_items": {
        "id",
        "title",
        "goal",
        "palari",
        "workbench_id",
        "parent_work_item_id",
        "dependency_ids",
        "risk",
        "intensity",
        "status",
        "scope",
        "allowed_resources",
        "allowed_sources",
        "allowed_actions",
        "output_targets",
        "path_intents",
        "forbidden_actions",
        "acceptance_target",
        "verification_expectations",
        "current_attempt",
        "required_approval_count",
        "required_approval_capability",
        "recommended_playbooks",
        "conflict_targets",
        "parallel_policy",
        "external_provider",
        "external_id",
        "external_key",
        "external_url",
        "external_updated_at",
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
    "capabilities": {
        "id",
        "label",
        "kind",
        "provider",
        "status",
        "owner_human",
        "allowed_actions",
        "allowed_palaris",
        "source_ids",
        "risk_level",
        "policy_ref",
        "notes",
    },
    "authority_profiles": {
        "id",
        "label",
        "mode",
        "summary",
        "require_human_for_risks",
        "receipt_ready_risks",
        "minimum_approval_count",
        "r5_approval_count",
        "required_approval_capability",
        "allow_agent_scope_expansion",
        "notes",
    },
    "integrations": {
        "id",
        "provider",
        "label",
        "mode",
        "owner_human",
        "enabled",
        "allowed_events",
        "allowed_actions",
        "secret_ref",
        "risk_level",
        "source_ids",
        "notes",
    },
    "integration_plans": {
        "id",
        "integration_id",
        "work_item_id",
        "event",
        "action",
        "actor",
        "status",
        "payload_preview",
        "source_boundary",
        "risk",
        "approval_required",
        "timestamp",
        "reviewed_by",
        "reviewed_at",
        "decision_reason",
        "notes",
    },
    "integration_outbox": {
        "id",
        "plan_id",
        "integration_id",
        "work_item_id",
        "event",
        "action",
        "enqueued_by",
        "status",
        "payload_preview",
        "source_boundary",
        "risk",
        "timestamp",
        "canceled_by",
        "canceled_at",
        "cancel_reason",
        "sent_by",
        "sent_at",
        "provider_response",
        "failed_at",
        "failure_reason",
        "notes",
    },
    "attempts": {
        "id",
        "work_item_id",
        "actor",
        "status",
        "branch",
        "workspace_path",
        "base_sha",
        "head_sha",
        "model_or_worker",
        "commits",
        "changed_files",
        "allowed_paths",
        "forbidden_paths",
        "claim_id",
        "claim_expires_at",
        "cleanliness",
        "result",
        "started_at",
        "updated_at",
        "output_targets",
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
        "artifact_hashes",
        "output_binding_version",
        "manifest_hash",
        "receipt_hash",
        "previous_receipt_hash",
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
        "binding_version",
        "attempt_id",
        "attempt_hash",
        "evidence_reference",
        "evidence_manifest_hash",
        "receipt_reference",
        "receipt_hash",
        "work_contract_hash",
        "proof_hash",
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
        "approval_pack_id",
        "approval_pack_digest",
        "approval_pack_member_digest",
        "approval_pack_subject_digest",
        "approval_pack_request_digest",
        "approval_pack_action",
        "approval_pack_manifest",
        "approval_presentation_schema_version",
        "approval_presentation_digest",
        "approval_presentation_surface",
        "approval_presentation",
        "timestamp",
    },
    "acceptance_records": {
        "id",
        "work_item_id",
        "human_id",
        "reviewed_head",
        "status",
        "decision_id",
        "evidence_reference",
        "review_reference",
        "receipt_hash",
        "authority_profile",
        "quorum_status",
        "reason",
        "accepted_at",
    },
    "receipts": {
        "id",
        "work_item_id",
        "attempt_id",
        "actor",
        "context_packet",
        "context_hash",
        "sources_used",
        "actions_taken",
        "outputs_created",
        "planned_external_writes",
        "queued_external_writes",
        "external_writes",
        "not_done",
        "undo_refs",
        "receipt_hash",
        "previous_receipt_hash",
        "evidence_manifest_hash",
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
    "proposals": {
        "id",
        "title",
        "goal",
        "palari",
        "proposer",
        "status",
        "summary",
        "scope",
        "risk",
        "intensity",
        "allowed_resources",
        "allowed_sources",
        "allowed_actions",
        "output_targets",
        "forbidden_actions",
        "acceptance_target",
        "verification_expectations",
        "recommended_playbooks",
        "conflict_targets",
        "parallel_policy",
        "linked_work",
        "decision_id",
        "created_at",
        "decided_by",
        "decided_at",
        "reason",
        "external_provider",
        "external_id",
        "external_key",
        "external_url",
        "external_updated_at",
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
WORKBENCH_STATUSES = {"active", "paused", "completed", "closed", "archived"}
TERMINAL_WORK_STATUSES = {"completed", "closed", "done"}
RISKS = {"R1", "R2", "R3", "R4", "R5"}
INTENSITIES = {"light", "standard", "high"}
PARALLEL_POLICIES = {"independent", "coordinate", "exclusive"}
CAPABILITY_KINDS = {
    "repo",
    "external_tool",
    "skill_pack",
    "mcp_adapter",
    "integration",
    "playbook",
    "policy",
}
CAPABILITY_STATUSES = {"enabled", "disabled", "review", "deprecated"}
PROPOSAL_STATUSES = {"proposed", "under-review", "adopted", "rejected", "deferred"}
AUTHORITY_MODES = {"solo-founder", "team-safe", "strict", "custom"}
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
    "deferred",
}
HUMAN_DECISION_VALUES = {
    "accepted",
    "approved",
    "rejected",
    "needs-changes",
    "changes-requested",
    "blocked",
    "deferred",
}
APPROVAL_PACK_ACTIONS = {"approve", "reject", "defer"}
QUORUM_STATUSES = {"", "pending", "met", "not-met"}
ACCEPTANCE_RECORD_STATUSES = {"accepted", "rejected", "revoked"}
OUTCOME_STATUSES = {"captured", "completed", "closed"}
INTEGRATION_PROVIDERS = {"slack", "github", "jira", "email", "linear"}
INTEGRATION_MODES = {"notify", "read", "write", "read_write", "webhook", "dry_run"}
INTEGRATION_RISK_LEVELS = {"low", "standard", "high", "critical"}
SOURCE_DATA_CLASSES = {"", "public", "internal", "confidential", "restricted"}
SOURCE_AUTHORITIES = {"", "user_owned", "company_owned", "external_public", "external_private"}
INTEGRATION_PLAN_STATUSES = {"planned", "pending-approval", "approved", "rejected", "canceled"}
INTEGRATION_OUTBOX_STATUSES = {"queued", "canceled", "sent", "failed"}
INTEGRATION_EVENTS = {
    "approval_requested",
    "incident_opened",
    "review_requested",
    "work_started",
    "work_completed",
    "work_blocked",
}
INTEGRATION_ACTIONS = {"notify", "comment", "create_issue", "update_issue"}
SECRET_REF_RE = re.compile(r"^env:[A-Z_][A-Z0-9_]*$")


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
    if "collection_files" in raw:
        _validate_collection_files(raw["collection_files"])


def _validate_collection_files(value: object) -> None:
    if not isinstance(value, dict):
        raise WorkspaceError("workspace.collection_files must be an object")
    unknown = sorted(set(value) - set(COLLECTION_FILE_KEYS))
    if unknown:
        fields = ", ".join(unknown)
        raise WorkspaceError(f"workspace.collection_files has unknown collection(s): {fields}")
    for key, paths in value.items():
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            raise WorkspaceError(f"workspace.collection_files.{key} must be a list of paths")


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
    palaris_by_id = {palari.id: palari for palari in workspace.palaris}
    sources_by_id = {source.id: source for source in workspace.sources}
    integrations_by_id = {integration.id: integration for integration in workspace.integrations}
    integration_plans_by_id = {plan.id: plan for plan in workspace.integration_plans}
    integration_outbox_by_id = {item.id: item for item in workspace.integration_outbox}
    decisions_by_id = {decision.id: decision for decision in workspace.decisions}
    human_decisions_by_id = {decision.id: decision for decision in workspace.human_decisions}

    for goal in workspace.goals:
        _require_allowed_value("goals", goal.id, "status", goal.status, GOAL_STATUSES)

    for workbench in workspace.workbenches:
        _require_allowed_value(
            "workbenches",
            workbench.id,
            "status",
            workbench.status,
            WORKBENCH_STATUSES,
        )

    for source in workspace.sources:
        _require_allowed_value(
            "sources",
            source.id,
            "data_class",
            source.data_class,
            SOURCE_DATA_CLASSES,
        )
        _require_allowed_value(
            "sources",
            source.id,
            "authority",
            source.authority,
            SOURCE_AUTHORITIES,
        )

    for capability in workspace.capabilities:
        _validate_capability(capability)

    for profile in workspace.authority_profiles:
        _validate_authority_profile(profile)

    for proposal in workspace.proposals:
        _validate_proposal(proposal, work_by_id, decisions_by_id)

    for work in workspace.work_items:
        _require_allowed_value("work_items", work.id, "status", work.status, WORK_STATUSES)
        _require_allowed_value("work_items", work.id, "risk", work.risk, RISKS)
        _require_allowed_value("work_items", work.id, "intensity", work.intensity, INTENSITIES)
        _require_allowed_value(
            "work_items",
            work.id,
            "parallel_policy",
            work.parallel_policy,
            PARALLEL_POLICIES,
        )
        _validate_path_intents(work)

    for integration in workspace.integrations:
        _validate_integration(integration)

    for plan in workspace.integration_plans:
        _validate_integration_plan(plan, integrations_by_id, work_by_id, humans_by_id)

    _validate_unique_outbox_plans(workspace.integration_outbox)
    for item in workspace.integration_outbox:
        _validate_integration_outbox_item(
            item,
            integration_plans_by_id,
            integrations_by_id,
            work_by_id,
            humans_by_id,
        )

    for attempt in workspace.attempts:
        _require_allowed_value("attempts", attempt.id, "status", attempt.status, ATTEMPT_STATUSES)
        _validate_attempt_boundaries(attempt, work_by_id)

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
        _validate_evidence_manifest_shape(evidence, work_by_id[evidence.work_item_id])

    for review in workspace.review_verdicts:
        _require_allowed_value(
            "review_verdicts", review.id, "verdict", review.verdict, REVIEW_VERDICTS
        )
        if review.reviewer not in humans_by_id and review.reviewer not in palaris_by_id:
            raise WorkspaceError(
                f"review_verdicts.{review.id}.reviewer references missing human or Palari "
                f"{review.reviewer}"
            )
        work = work_by_id[review.work_item_id]
        reviewer_palari = palaris_by_id.get(review.reviewer)
        if reviewer_palari is not None:
            if work.goal and work.goal not in reviewer_palari.linked_goals:
                raise WorkspaceError(
                    f"review_verdicts.{review.id}.reviewer Palari {review.reviewer} "
                    f"is not linked to goal {work.goal}"
                )
            for source_id in work.allowed_sources:
                source = sources_by_id[source_id]
                if source.allowed_palaris and review.reviewer not in source.allowed_palaris:
                    raise WorkspaceError(
                        f"review_verdicts.{review.id}.reviewer Palari {review.reviewer} "
                        f"is not allowed for source {source_id}"
                    )
        attempt = attempts_by_id.get(review.attempt_id or work.current_attempt)
        if attempt is not None and review.reviewer == attempt.actor:
            raise WorkspaceError(
                f"review_verdicts.{review.id}.reviewer must be independent from "
                f"attempt actor {attempt.actor}"
            )
        if review.binding_version:
            from .governance_binding import review_binding_integrity_errors

            binding_errors = review_binding_integrity_errors(workspace, review)
            if binding_errors:
                raise WorkspaceError(f"review_verdicts.{review.id}: {binding_errors[0]}")
        elif review.verdict == "accept-ready":
            raise WorkspaceError(
                f"review_verdicts.{review.id}.verdict accept-ready requires exact proof binding"
            )
        for field, value in (
            ("attempt_hash", review.attempt_hash),
            ("evidence_manifest_hash", review.evidence_manifest_hash),
            ("receipt_hash", review.receipt_hash),
            ("work_contract_hash", review.work_contract_hash),
            ("proof_hash", review.proof_hash),
        ):
            _require_hash_prefix("review_verdicts", review.id, field, value)

    for decision in workspace.decisions:
        _require_allowed_value("decisions", decision.id, "status", decision.status, DECISION_STATUSES)

    latest_human_decisions: dict[tuple[str, str], HumanDecision] = {}
    for human_decision in workspace.human_decisions:
        key = (human_decision.work_item_id, human_decision.human_id)
        previous = latest_human_decisions.get(key)
        if previous is None or _decision_order_key(human_decision) > _decision_order_key(
            previous
        ):
            latest_human_decisions[key] = human_decision

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
        if not human_decision.timestamp:
            raise WorkspaceError(
                f"human_decisions.{human_decision.id}.timestamp is required"
            )
        try:
            parsed_timestamp = datetime.fromisoformat(
                human_decision.timestamp.replace("Z", "+00:00")
            )
        except (OverflowError, ValueError) as exc:
            raise WorkspaceError(
                f"human_decisions.{human_decision.id}.timestamp must be ISO-8601"
            ) from exc
        if parsed_timestamp.utcoffset() is None:
            raise WorkspaceError(
                f"human_decisions.{human_decision.id}.timestamp must include a timezone"
            )
        try:
            parsed_timestamp.astimezone(timezone.utc)
        except OverflowError as exc:
            raise WorkspaceError(
                f"human_decisions.{human_decision.id}.timestamp must represent a valid UTC instant"
            ) from exc
        status_accepts = human_decision.status in {"accepted", "approved"}
        value_accepts = human_decision.decision in {"accepted", "approved"}
        if status_accepts != value_accepts:
            raise WorkspaceError(
                f"human_decisions.{human_decision.id} has contradictory decision and status"
            )
        _validate_approval_pack_decision(human_decision)
        if _is_acceptance(human_decision):
            latest_for_human = (
                latest_human_decisions[
                    (human_decision.work_item_id, human_decision.human_id)
                ].id
                == human_decision.id
            )
            decision_evidence = evidence_by_id.get(human_decision.evidence_reference)
            work = work_by_id[human_decision.work_item_id]
            references_current_attempt = bool(
                not work.current_attempt
                or (
                    decision_evidence is not None
                    and decision_evidence.attempt_id == work.current_attempt
                )
            )
            _validate_accepted_human_decision(
                human_decision,
                work_by_id,
                humans_by_id,
                attempts_by_id,
                evidence_by_id,
                reviews_by_id,
                # An accepted decision remains immutable audit history after a
                # new attempt becomes current. Current-binding checks apply
                # only when the decision claims authority for that attempt;
                # read models and the governance kernel count only exact
                # current review/evidence bindings toward quorum.
                require_current=latest_for_human and references_current_attempt,
            )
    _validate_human_decision_order(workspace.human_decisions)
    _validate_approval_pack_decision_sets(workspace)

    _validate_ordered_trust_records(
        "attempts",
        workspace.attempts,
        ("updated_at", "started_at"),
    )
    _validate_ordered_trust_records(
        "evidence_runs",
        workspace.evidence_runs,
        ("timestamp",),
    )
    _validate_ordered_trust_records(
        "review_verdicts",
        workspace.review_verdicts,
        ("timestamp",),
    )
    _validate_ordered_trust_records(
        "acceptance_records",
        workspace.acceptance_records,
        ("accepted_at",),
    )
    _validate_ordered_trust_records(
        "receipts",
        workspace.receipts,
        ("timestamp",),
    )
    _validate_ordered_trust_records(
        "outcomes",
        workspace.outcomes,
        ("timestamp",),
    )
    _validate_ordered_trust_records(
        "integration_plans",
        workspace.integration_plans,
        ("timestamp",),
    )
    _validate_ordered_trust_records(
        "integration_outbox",
        workspace.integration_outbox,
        ("timestamp",),
    )

    for acceptance in workspace.acceptance_records:
        _validate_acceptance_record(
            workspace,
            acceptance,
            work_by_id,
            humans_by_id,
            attempts_by_id,
            evidence_by_id,
            reviews_by_id,
            human_decisions_by_id,
        )

    for receipt in workspace.receipts:
        _validate_receipt(
            receipt,
            work_by_id,
            attempts_by_id,
            sources_by_id,
            integration_plans_by_id,
            integration_outbox_by_id,
        )
        _validate_receipt_hash_shape(receipt)

    for outcome in workspace.outcomes:
        _require_allowed_value("outcomes", outcome.id, "status", outcome.status, OUTCOME_STATUSES)

    for work in workspace.work_items:
        if work.status in TERMINAL_WORK_STATUSES:
            _validate_completed_work(workspace, work, attempts_by_id)

    # Exercise the same pure evaluator used by transitions and PCAW verification.
    # Existing workspace acceptance semantics remain authoritative for compatibility;
    # PCAW property failures are reported by proof/status surfaces, not converted here.
    from .governance_kernel import PROPERTY_NAMES
    from .pcaw_workspace import evaluate_workspace_governance

    governed_work_ids = {
        acceptance.work_item_id for acceptance in workspace.acceptance_records
    }
    for work in workspace.work_items:
        if work.status not in TERMINAL_WORK_STATUSES and work.id not in governed_work_ids:
            continue
        evaluation = evaluate_workspace_governance(
            workspace, work.id, inspect_external=False
        )
        if tuple(item.name for item in evaluation.properties) != PROPERTY_NAMES:
            raise WorkspaceError(
                f"governance kernel returned an incomplete property set for {work.id}"
            )


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


def _validate_integration(integration: Integration) -> None:
    _require_allowed_value(
        "integrations",
        integration.id,
        "provider",
        integration.provider,
        INTEGRATION_PROVIDERS,
    )
    _require_allowed_value(
        "integrations",
        integration.id,
        "mode",
        integration.mode,
        INTEGRATION_MODES,
    )
    _require_allowed_value(
        "integrations",
        integration.id,
        "risk_level",
        integration.risk_level,
        INTEGRATION_RISK_LEVELS,
    )
    for event in integration.allowed_events:
        _require_allowed_value(
            "integrations",
            integration.id,
            "allowed_events",
            event,
            INTEGRATION_EVENTS,
        )
    for action in integration.allowed_actions:
        _require_allowed_value(
            "integrations",
            integration.id,
            "allowed_actions",
            action,
            INTEGRATION_ACTIONS,
        )
        if action not in PROVIDER_ACTIONS[integration.provider]:
            raise WorkspaceError(
                f"integrations.{integration.id}.allowed_actions includes action "
                f"{action!r} unsupported by provider {integration.provider}"
            )
        if action not in supported_actions_for_mode(integration.mode, integration.provider):
            raise WorkspaceError(
                f"integrations.{integration.id}.allowed_actions includes action "
                f"{action!r} unsupported by mode {integration.mode}"
            )
    if integration.secret_ref and not SECRET_REF_RE.match(integration.secret_ref):
        raise WorkspaceError(
            f"integrations.{integration.id}.secret_ref must be an env:NAME reference, "
            "not a raw token or key"
        )


def _validate_capability(capability: Capability) -> None:
    _require_allowed_value(
        "capabilities",
        capability.id,
        "kind",
        capability.kind,
        CAPABILITY_KINDS,
    )
    _require_allowed_value(
        "capabilities",
        capability.id,
        "status",
        capability.status,
        CAPABILITY_STATUSES,
    )
    _require_allowed_value(
        "capabilities",
        capability.id,
        "risk_level",
        capability.risk_level,
        INTEGRATION_RISK_LEVELS,
    )


def _validate_authority_profile(profile: AuthorityProfile) -> None:
    _require_allowed_value("authority_profiles", profile.id, "mode", profile.mode, AUTHORITY_MODES)
    for risk in profile.require_human_for_risks:
        _require_allowed_value("authority_profiles", profile.id, "require_human_for_risks", risk, RISKS)
    for risk in profile.receipt_ready_risks:
        _require_allowed_value("authority_profiles", profile.id, "receipt_ready_risks", risk, RISKS)
    if profile.minimum_approval_count < 0:
        raise WorkspaceError(
            f"authority_profiles.{profile.id}.minimum_approval_count must be zero or greater"
        )
    if profile.r5_approval_count < profile.minimum_approval_count:
        raise WorkspaceError(
            f"authority_profiles.{profile.id}.r5_approval_count must be at least "
            "minimum_approval_count"
        )


def _validate_proposal(
    proposal: Proposal,
    work_by_id: dict[str, WorkItem],
    decisions_by_id: dict[str, Any],
) -> None:
    _require_allowed_value("proposals", proposal.id, "status", proposal.status, PROPOSAL_STATUSES)
    _require_allowed_value("proposals", proposal.id, "risk", proposal.risk, RISKS)
    _require_allowed_value("proposals", proposal.id, "intensity", proposal.intensity, INTENSITIES)
    _require_allowed_value(
        "proposals",
        proposal.id,
        "parallel_policy",
        proposal.parallel_policy,
        PARALLEL_POLICIES,
    )
    if proposal.status == "adopted":
        if not proposal.linked_work:
            raise WorkspaceError(f"proposals.{proposal.id}.linked_work is required when adopted")
        work = work_by_id[proposal.linked_work]
        if work.title != proposal.title:
            raise WorkspaceError(
                f"proposals.{proposal.id}.linked_work {work.id} title does not match proposal"
            )
    if proposal.status in {"rejected", "deferred"} and not proposal.reason:
        raise WorkspaceError(f"proposals.{proposal.id}.reason is required when {proposal.status}")
    if proposal.decision_id:
        decision = decisions_by_id[proposal.decision_id]
        if decision.linked_work and proposal.linked_work and decision.linked_work != proposal.linked_work:
            raise WorkspaceError(
                f"proposals.{proposal.id}.decision_id links to decision {decision.id} "
                f"for different work item {decision.linked_work}"
            )


def _validate_integration_plan(
    plan: IntegrationPlan,
    integrations_by_id: dict[str, Integration],
    work_by_id: dict[str, WorkItem],
    humans_by_id: dict[str, Any],
) -> None:
    _require_allowed_value(
        "integration_plans",
        plan.id,
        "status",
        plan.status,
        INTEGRATION_PLAN_STATUSES,
    )
    integration = integrations_by_id[plan.integration_id]
    _validate_integration(integration)
    if not integration.enabled:
        raise WorkspaceError(
            f"integration_plans.{plan.id}.integration_id references disabled integration "
            f"{integration.id}"
        )
    if plan.event not in integration.allowed_events:
        raise WorkspaceError(
            f"integration_plans.{plan.id}.event {plan.event!r} is not allowed by "
            f"integration {integration.id}"
        )
    if plan.action not in integration.allowed_actions:
        raise WorkspaceError(
            f"integration_plans.{plan.id}.action {plan.action!r} is not allowed by "
            f"integration {integration.id}"
        )
    _require_allowed_value(
        "integration_plans",
        plan.id,
        "event",
        plan.event,
        INTEGRATION_EVENTS,
    )
    _require_allowed_value(
        "integration_plans",
        plan.id,
        "action",
        plan.action,
        INTEGRATION_ACTIONS,
    )
    _require_allowed_value(
        "integration_plans",
        plan.id,
        "risk",
        plan.risk,
        INTEGRATION_RISK_LEVELS,
    )
    if not plan.approval_required:
        raise WorkspaceError(
            f"integration_plans.{plan.id}.approval_required must be true for external actions"
        )
    if not isinstance(plan.payload_preview, dict):
        raise WorkspaceError(f"integration_plans.{plan.id}.payload_preview must be an object")
    if not isinstance(plan.source_boundary, dict):
        raise WorkspaceError(f"integration_plans.{plan.id}.source_boundary must be an object")
    _validate_no_raw_secret_values(
        f"integration_plans.{plan.id}.payload_preview",
        plan.payload_preview,
    )
    if plan.status in {"approved", "rejected", "canceled"}:
        if not plan.reviewed_by:
            raise WorkspaceError(
                f"integration_plans.{plan.id}.reviewed_by is required when status is "
                f"{plan.status}"
            )
        if not plan.reviewed_at:
            raise WorkspaceError(
                f"integration_plans.{plan.id}.reviewed_at is required when status is "
                f"{plan.status}"
            )
        human = humans_by_id[plan.reviewed_by]
        work = work_by_id[plan.work_item_id]
        if not _human_can_decide_integration_plan(
            human,
            work,
            integration,
        ):
            raise WorkspaceError(
                f"integration_plans.{plan.id}.reviewed_by {human.id} lacks authority "
                "to decide this integration plan"
            )


def _human_can_decide_integration_plan(
    human: Any,
    work: WorkItem,
    integration: Integration,
) -> bool:
    if human.authority_level == "admin":
        return True
    if work.required_approval_capability:
        return work.required_approval_capability in human.approval_capabilities
    if integration.owner_human == human.id and integration.risk_level in {"low", "standard"}:
        return True
    if integration.risk_level in {"high", "critical"}:
        return bool({"policy", "deploy", "security"} & set(human.approval_capabilities))
    return bool(
        {"operations", "product", "policy", "merge", "deploy"} & set(human.approval_capabilities)
    )


def _validate_unique_outbox_plans(items: Iterable[IntegrationOutboxItem]) -> None:
    seen: dict[str, str] = {}
    for item in items:
        if item.plan_id in seen:
            raise WorkspaceError(
                f"integration_outbox.{item.id}.plan_id duplicates "
                f"integration_outbox.{seen[item.plan_id]} for plan {item.plan_id}"
            )
        seen[item.plan_id] = item.id


def _validate_integration_outbox_item(
    item: IntegrationOutboxItem,
    integration_plans_by_id: dict[str, IntegrationPlan],
    integrations_by_id: dict[str, Integration],
    work_by_id: dict[str, WorkItem],
    humans_by_id: dict[str, Any],
) -> None:
    _require_allowed_value(
        "integration_outbox",
        item.id,
        "status",
        item.status,
        INTEGRATION_OUTBOX_STATUSES,
    )
    _require_allowed_value(
        "integration_outbox",
        item.id,
        "event",
        item.event,
        INTEGRATION_EVENTS,
    )
    _require_allowed_value(
        "integration_outbox",
        item.id,
        "action",
        item.action,
        INTEGRATION_ACTIONS,
    )
    _require_allowed_value(
        "integration_outbox",
        item.id,
        "risk",
        item.risk,
        INTEGRATION_RISK_LEVELS,
    )
    plan = integration_plans_by_id[item.plan_id]
    integration = integrations_by_id[item.integration_id]
    work = work_by_id[item.work_item_id]
    human = humans_by_id[item.enqueued_by]
    if plan.status != "approved":
        raise WorkspaceError(
            f"integration_outbox.{item.id}.plan_id references plan {plan.id} "
            f"with status {plan.status}; expected approved"
        )
    if item.integration_id != plan.integration_id:
        raise WorkspaceError(
            f"integration_outbox.{item.id}.integration_id does not match plan {plan.id}"
        )
    if item.work_item_id != plan.work_item_id:
        raise WorkspaceError(
            f"integration_outbox.{item.id}.work_item_id does not match plan {plan.id}"
        )
    if item.event != plan.event or item.action != plan.action:
        raise WorkspaceError(
            f"integration_outbox.{item.id}.event/action does not match plan {plan.id}"
        )
    if item.risk != plan.risk:
        raise WorkspaceError(f"integration_outbox.{item.id}.risk does not match plan {plan.id}")
    if not _human_can_decide_integration_plan(human, work, integration):
        raise WorkspaceError(
            f"integration_outbox.{item.id}.enqueued_by {human.id} lacks authority "
            "to enqueue this integration plan"
        )
    if item.status == "canceled":
        if not item.canceled_by:
            raise WorkspaceError(
                f"integration_outbox.{item.id}.canceled_by is required when status is canceled"
            )
        if not item.canceled_at:
            raise WorkspaceError(
                f"integration_outbox.{item.id}.canceled_at is required when status is canceled"
            )
        if not item.cancel_reason:
            raise WorkspaceError(
                f"integration_outbox.{item.id}.cancel_reason is required when status is canceled"
            )
        canceling_human = humans_by_id[item.canceled_by]
        if not _human_can_decide_integration_plan(canceling_human, work, integration):
            raise WorkspaceError(
                f"integration_outbox.{item.id}.canceled_by {canceling_human.id} lacks "
                "authority to cancel this integration outbox item"
            )
    if item.status == "sent":
        if not item.sent_by:
            raise WorkspaceError(
                f"integration_outbox.{item.id}.sent_by is required when status is sent"
            )
        if not item.sent_at:
            raise WorkspaceError(
                f"integration_outbox.{item.id}.sent_at is required when status is sent"
            )
        if not item.provider_response:
            raise WorkspaceError(
                f"integration_outbox.{item.id}.provider_response is required when status is sent"
            )
    if item.status == "failed":
        if not item.failed_at:
            raise WorkspaceError(
                f"integration_outbox.{item.id}.failed_at is required when status is failed"
            )
        if not item.failure_reason:
            raise WorkspaceError(
                f"integration_outbox.{item.id}.failure_reason is required when status is failed"
            )
    if item.sent_by:
        sending_human = humans_by_id[item.sent_by]
        if not _human_can_decide_integration_plan(sending_human, work, integration):
            raise WorkspaceError(
                f"integration_outbox.{item.id}.sent_by {sending_human.id} lacks "
                "authority to send this integration outbox item"
            )
    if not isinstance(item.payload_preview, dict):
        raise WorkspaceError(f"integration_outbox.{item.id}.payload_preview must be an object")
    if not isinstance(item.source_boundary, dict):
        raise WorkspaceError(f"integration_outbox.{item.id}.source_boundary must be an object")
    _validate_no_raw_secret_values(f"integration_outbox.{item.id}.payload_preview", item.payload_preview)
    if item.payload_preview != plan.payload_preview:
        raise WorkspaceError(
            f"integration_outbox.{item.id}.payload_preview does not match approved "
            f"plan {plan.id}"
        )
    if item.source_boundary != plan.source_boundary:
        raise WorkspaceError(
            f"integration_outbox.{item.id}.source_boundary does not match approved "
            f"plan {plan.id}"
        )


RAW_SECRET_VALUE_RE = re.compile(r"(xox[baprs]-|sk-[A-Za-z0-9]|gh[pousr]_|ya29\.|-----BEGIN)")


def _validate_no_raw_secret_values(label: str, value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_label = f"{label}.{key}"
            if isinstance(item, str) and _looks_like_secret_field(str(key), item):
                raise WorkspaceError(
                    f"{child_label} must be an env:NAME reference, not a raw secret"
                )
            _validate_no_raw_secret_values(child_label, item)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_no_raw_secret_values(f"{label}[{index}]", item)
        return
    if isinstance(value, str) and RAW_SECRET_VALUE_RE.search(value):
        raise WorkspaceError(f"{label} contains a raw secret-looking value")


def _looks_like_secret_field(key: str, value: str) -> bool:
    lowered = key.lower()
    if not any(marker in lowered for marker in ("secret", "token", "webhook")):
        return False
    if not value:
        return False
    return not value.startswith("env:")


def _validate_attempt_boundaries(
    attempt: Attempt,
    work_by_id: dict[str, WorkItem],
) -> None:
    work = work_by_id[attempt.work_item_id]
    write_boundaries = _write_boundaries(work)
    output_boundaries = _output_boundaries(work)
    attempt_boundaries = attempt.allowed_paths or write_boundaries

    for changed_file in attempt.changed_files:
        _require_path_in_boundaries(
            f"attempts.{attempt.id}.changed_files",
            changed_file,
            attempt_boundaries,
        )
        for forbidden_path in attempt.forbidden_paths:
            _require_changed_file_outside_forbidden_path(attempt.id, changed_file, forbidden_path)
    for output_target in attempt.output_targets:
        _require_path_in_boundaries(
            f"attempts.{attempt.id}.output_targets",
            output_target,
            output_boundaries,
        )


def _validate_path_intents(work: WorkItem) -> None:
    """Validate the additive exact-path mutation contract.

    Legacy work items omit ``path_intents`` and retain their existing
    output-target semantics. Once the field is present, every entry is an
    exact canonical path with one unambiguous final-state intent.
    """

    seen: set[str] = set()
    boundaries = _write_boundaries(work)
    for index, item in enumerate(work.path_intents):
        label = f"work_items.{work.id}.path_intents[{index}]"
        unknown = sorted(set(item) - {"path", "intent"})
        if unknown:
            raise WorkspaceError(f"{label} has unknown field(s): {', '.join(unknown)}")
        path = item.get("path")
        intent = item.get("intent")
        if not isinstance(path, str) or not path:
            raise WorkspaceError(f"{label}.path must be a non-empty string")
        if intent not in {"create", "modify", "delete"}:
            raise WorkspaceError(
                f"{label}.intent has unsupported value {intent!r}; "
                "expected one of: create, delete, modify"
            )
        try:
            normalized = validate_workspace_path(path)
        except ValueError as exc:
            raise WorkspaceError(f"{label}.path contains unsafe path {path}: {exc}") from exc
        if normalized != path:
            raise WorkspaceError(f"{label}.path is not in canonical repository form: {path}")
        if path in seen:
            raise WorkspaceError(
                f"work_items.{work.id}.path_intents contains duplicate path: {path}"
            )
        seen.add(path)
        for other in seen - {path}:
            if path_allowed(path, [other]) or path_allowed(other, [path]):
                raise WorkspaceError(
                    f"work_items.{work.id}.path_intents paths overlap by prefix: "
                    f"{other}, {path}"
                )
        if not boundaries or not path_allowed(path, boundaries):
            raise WorkspaceError(
                f"{label}.path includes path outside declared boundaries: {path}"
            )


def _validate_receipt_boundaries(receipt: Receipt, work: WorkItem) -> None:
    write_boundaries = _write_boundaries(work)
    for output in receipt.outputs_created:
        _require_path_in_boundaries(
            f"receipts.{receipt.id}.outputs_created",
            output,
            write_boundaries,
        )
    for undo_ref in receipt.undo_refs:
        undo_path = _undo_ref_path(undo_ref)
        if undo_path:
            _require_path_in_boundaries(
                f"receipts.{receipt.id}.undo_refs",
                undo_path,
                write_boundaries,
            )


def _write_boundaries(work: WorkItem) -> list[str]:
    return [*work.output_targets, *work.allowed_resources]


def _output_boundaries(work: WorkItem) -> list[str]:
    return list(work.output_targets or work.allowed_resources)


def _require_path_in_boundaries(label: str, path: str, boundaries: list[str]) -> None:
    if not boundaries:
        raise WorkspaceError(f"{label} has no declared output or resource boundary for {path}")
    try:
        validate_workspace_path(path)
    except ValueError as exc:
        raise WorkspaceError(f"{label} contains unsafe path {path}: {exc}") from exc
    if not path_allowed(path, boundaries):
        raise WorkspaceError(f"{label} includes path outside declared boundaries: {path}")


def _require_changed_file_outside_forbidden_path(
    attempt_id: str,
    changed_file: str,
    forbidden_path: str,
) -> None:
    try:
        validate_workspace_path(forbidden_path)
    except ValueError as exc:
        raise WorkspaceError(
            f"attempts.{attempt_id}.forbidden_paths contains unsafe path {forbidden_path}: {exc}"
        ) from exc
    if path_allowed(changed_file, [forbidden_path]):
        raise WorkspaceError(
            f"attempts.{attempt_id}.changed_files includes forbidden path {changed_file}"
        )


def _undo_ref_path(undo_ref: str) -> str:
    stripped = undo_ref.strip()
    if not stripped:
        return ""
    lower = stripped.lower()
    for prefix in ("delete ", "remove ", "revert ", "restore ", "unlink "):
        if lower.startswith(prefix):
            return stripped[len(prefix):].strip()
    if "/" in stripped or "." in stripped:
        return stripped
    return ""


def _validate_accepted_human_decision(
    decision: HumanDecision,
    work_by_id: dict[str, WorkItem],
    humans_by_id: dict[str, Any],
    attempts_by_id: dict[str, Attempt],
    evidence_by_id: dict[str, EvidenceRun],
    reviews_by_id: dict[str, ReviewVerdict],
    *,
    require_current: bool,
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
    if (
        require_current
        and work.current_attempt
        and evidence.attempt_id != work.current_attempt
    ):
        raise WorkspaceError(
            f"human_decisions.{decision.id}.evidence_reference is not for "
            f"current attempt {work.current_attempt}"
        )
    _require_fresh_passed_evidence(work.id, attempt, evidence)
    _require_fresh_accept_ready_review(work.id, evidence, review)
    if decision.evidence_reference != review.evidence_reference:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.evidence_reference does not match "
            f"bound review evidence {review.evidence_reference}"
        )
    if review.attempt_id != evidence.attempt_id:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.review_reference is bound to a "
            "different attempt"
        )
    from .governance_binding import work_contract_hash

    if require_current and review.work_contract_hash != work_contract_hash(work):
        raise WorkspaceError(
            f"human_decisions.{decision.id}.review_reference is stale for the work contract"
        )
    if decision.reviewed_head != review.reviewed_head:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.reviewed_head does not match "
            f"review_reference head {review.reviewed_head}"
        )


def _validate_acceptance_record(
    workspace: Any,
    acceptance: AcceptanceRecord,
    work_by_id: dict[str, WorkItem],
    humans_by_id: dict[str, Any],
    attempts_by_id: dict[str, Attempt],
    evidence_by_id: dict[str, EvidenceRun],
    reviews_by_id: dict[str, ReviewVerdict],
    human_decisions_by_id: dict[str, HumanDecision],
) -> None:
    _require_allowed_value(
        "acceptance_records",
        acceptance.id,
        "status",
        acceptance.status,
        ACCEPTANCE_RECORD_STATUSES,
    )
    _require_allowed_value(
        "acceptance_records",
        acceptance.id,
        "quorum_status",
        acceptance.quorum_status,
        QUORUM_STATUSES,
    )
    if acceptance.status != "accepted":
        return
    work = work_by_id[acceptance.work_item_id]
    human = humans_by_id[acceptance.human_id]
    if work.required_approval_capability and (
        work.required_approval_capability not in human.approval_capabilities
    ):
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.human_id lacks required approval "
            f"capability {work.required_approval_capability}"
        )
    if acceptance.quorum_status != "met":
        raise WorkspaceError(f"acceptance_records.{acceptance.id}.quorum_status must be met")
    if not acceptance.decision_id:
        raise WorkspaceError(f"acceptance_records.{acceptance.id}.decision_id is required")
    if not acceptance.evidence_reference:
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.evidence_reference is required"
        )
    if not acceptance.review_reference:
        raise WorkspaceError(f"acceptance_records.{acceptance.id}.review_reference is required")
    evidence = evidence_by_id[acceptance.evidence_reference]
    review = reviews_by_id[acceptance.review_reference]
    decision = human_decisions_by_id[acceptance.decision_id]
    if not _is_acceptance(decision):
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.decision_id points to non-acceptance "
            f"decision {decision.id}"
        )
    if decision.work_item_id != work.id or decision.human_id != acceptance.human_id:
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.decision_id does not match its work and human"
        )
    if (
        decision.reviewed_head != acceptance.reviewed_head
        or decision.evidence_reference != acceptance.evidence_reference
        or decision.review_reference != acceptance.review_reference
    ):
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.decision_id does not match its exact proof"
        )
    if evidence.work_item_id != work.id:
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.evidence_reference points to "
            f"evidence for {evidence.work_item_id}, not {work.id}"
        )
    if review.work_item_id != work.id:
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.review_reference points to "
            f"review for {review.work_item_id}, not {work.id}"
        )
    attempt = attempts_by_id[evidence.attempt_id]
    if work.current_attempt and evidence.attempt_id != work.current_attempt:
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.evidence_reference is not for "
            f"current attempt {work.current_attempt}"
        )
    _require_fresh_passed_evidence(work.id, attempt, evidence)
    _require_fresh_accept_ready_review(work.id, evidence, review)
    if work.status in TERMINAL_WORK_STATUSES:
        stored_errors = _stored_evidence_integrity_errors(workspace, evidence)
        if stored_errors:
            raise WorkspaceError(
                f"acceptance_records.{acceptance.id}.evidence_reference fails exact "
                f"evidence or receipt integrity: {stored_errors[0]}"
            )
    else:
        from .evidence_manifest import verify_evidence

        # Before execution, approval is always bound to current artifact bytes.
        verification = verify_evidence(workspace, evidence.id, require_output_coverage=None)
        if not verification["ok"]:
            raise WorkspaceError(
                f"acceptance_records.{acceptance.id}.evidence_reference fails exact "
                "evidence or receipt integrity"
            )
    if acceptance.evidence_reference != review.evidence_reference:
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.evidence_reference does not match "
            f"bound review evidence {review.evidence_reference}"
        )
    if not acceptance.receipt_hash or acceptance.receipt_hash != review.receipt_hash:
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.receipt_hash does not match bound review"
        )
    if acceptance.reviewed_head != review.reviewed_head:
        raise WorkspaceError(
            f"acceptance_records.{acceptance.id}.reviewed_head does not match "
            f"review_reference head {review.reviewed_head}"
        )


def _validate_ordered_trust_records(
    collection: str,
    records: Iterable[Any],
    timestamp_fields: tuple[str, ...],
) -> None:
    """Reject malformed or ambiguous timestamps used for latest-record selection.

    Schema v2 historically allowed one undated record. Keep that representation
    loadable when no ordering choice exists, but require an unambiguous instant as
    soon as two records compete for the same work item.
    """

    grouped: dict[str, list[Any]] = {}
    for record in records:
        grouped.setdefault(str(getattr(record, "work_item_id", "")), []).append(record)

    for work_id, work_records in grouped.items():
        seen: dict[datetime, str] = {}
        for record in work_records:
            record_id = str(getattr(record, "id", ""))
            values: list[tuple[str, str]] = []
            for field in timestamp_fields:
                value = str(getattr(record, field, "") or "")
                if not value:
                    continue
                _require_timezone_timestamp(collection, record_id, field, value)
                values.append((field, value))

            if not values:
                if len(work_records) > 1:
                    fields = " or ".join(timestamp_fields)
                    raise WorkspaceError(
                        f"{collection}.{record_id}.{fields} is required because "
                        f"{work_id} has multiple {collection} records; latest record "
                        "would be ambiguous"
                    )
                continue

            effective = timestamp_order(values[0][1])
            previous = seen.get(effective)
            if previous is not None:
                raise WorkspaceError(
                    f"{collection}.{record_id}.{values[0][0]} duplicates {previous} "
                    f"for {work_id}; latest record would be ambiguous"
                )
            seen[effective] = record_id


def _require_timezone_timestamp(
    collection: str,
    record_id: str,
    field: str,
    value: str,
) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OverflowError, ValueError) as exc:
        raise WorkspaceError(
            f"{collection}.{record_id}.{field} must be ISO-8601"
        ) from exc
    if parsed.utcoffset() is None:
        raise WorkspaceError(
            f"{collection}.{record_id}.{field} must include a timezone"
        )
    try:
        parsed.astimezone(timezone.utc)
    except OverflowError as exc:
        raise WorkspaceError(
            f"{collection}.{record_id}.{field} must represent a valid UTC instant"
        ) from exc


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
    unfinished_dependencies = _unfinished_dependency_ids(workspace, work)
    if unfinished_dependencies:
        raise WorkspaceError(
            f"work_items.{work.id}.status is terminal but dependencies are unfinished: "
            f"{', '.join(unfinished_dependencies)}"
        )
    if _completed_via_low_risk_receipt(workspace, work, attempt):
        return
    if attempt.status not in {"complete", "completed"}:
        raise WorkspaceError(
            f"work_items.{work.id}.status is terminal but current attempt "
            f"{attempt.id} is {attempt.status}"
        )
    if attempt.cleanliness.lower() not in {"clean", "pristine"}:
        raise WorkspaceError(
            f"work_items.{work.id}.status is terminal but current attempt "
            f"{attempt.id} is not clean"
        )
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
    if review.binding_version:
        from .governance_binding import review_binding_integrity_errors, work_contract_hash

        # Exact output coverage is mandatory for versioned evidence. Terminal
        # records with genuinely unversioned evidence remain loadable as
        # legacy state, but a v1 record cannot use that compatibility path.
        binding_errors = review_binding_integrity_errors(workspace, review)
        binding_errors.extend(_stored_evidence_integrity_errors(workspace, evidence))
        if review.work_contract_hash != work_contract_hash(work):
            binding_errors.append(f"review {review.id} work contract is stale")
        if binding_errors:
            raise WorkspaceError(
                f"work_items.{work.id}.status is terminal but exact review proof is stale: "
                f"{binding_errors[0]}"
            )
        matching_acceptance = _latest_for_work(workspace.acceptance_records, work.id)
        if matching_acceptance is None:
            raise WorkspaceError(
                f"work_items.{work.id}.status is terminal but exact acceptance record is missing"
            )
        if matching_acceptance.status != "accepted":
            raise WorkspaceError(
                f"work_items.{work.id}.status is terminal but latest acceptance record "
                f"{matching_acceptance.id} is {matching_acceptance.status}"
            )
        if (
            matching_acceptance.review_reference != review.id
            or matching_acceptance.evidence_reference != evidence.id
            or matching_acceptance.reviewed_head != review.reviewed_head
            or matching_acceptance.receipt_hash != review.receipt_hash
        ):
            raise WorkspaceError(
                f"work_items.{work.id}.status is terminal but latest acceptance record "
                "does not match current exact proof"
            )
    count = _qualified_approval_count(workspace, work, review)
    if count < work.required_approval_count:
        raise WorkspaceError(
            f"work_items.{work.id}.status is terminal but approval quorum is "
            f"{count}/{work.required_approval_count}"
        )


def _stored_evidence_integrity_errors(
    workspace: Any,
    evidence: EvidenceRun,
) -> list[str]:
    """Validate terminal proof records without rebinding them to a later checkout."""

    from .evidence_manifest import evidence_manifest_hash, receipt_hash
    from .models import to_plain

    record = to_plain(evidence)
    errors: list[str] = []
    if not evidence.manifest_hash or evidence.manifest_hash != evidence_manifest_hash(record):
        errors.append(f"evidence {evidence.id} manifest content changed")
    receipts = [
        receipt
        for receipt in workspace.receipts
        if receipt.work_item_id == evidence.work_item_id
        and receipt.attempt_id == evidence.attempt_id
    ]
    receipt = max(receipts, key=record_time_key) if receipts else None
    if receipt is None:
        errors.append(f"evidence {evidence.id} receipt is missing")
    else:
        if not receipt.receipt_hash or receipt.receipt_hash != receipt_hash(to_plain(receipt)):
            errors.append(f"receipt {receipt.id} content changed")
        if evidence.receipt_hash != receipt.receipt_hash:
            errors.append(f"evidence {evidence.id} receipt binding changed")
    if evidence.output_binding_version:
        declared_paths = sorted(evidence.artifacts)
        hashed_paths = sorted(
            str(item.get("path", ""))
            for item in evidence.artifact_hashes
            if item.get("status") == "present"
            and re.fullmatch(r"sha256:[0-9a-f]{64}", str(item.get("sha256", "")))
        )
        if declared_paths != hashed_paths:
            errors.append(f"evidence {evidence.id} output hashes are incomplete")
        if not hashed_paths:
            errors.append(f"evidence {evidence.id} versioned output proof is vacuous")
        if receipt is not None and not set(receipt.outputs_created).issubset(hashed_paths):
            errors.append(f"evidence {evidence.id} receipt outputs are not artifact-hashed")
    return list(dict.fromkeys(errors))


def _completed_via_low_risk_receipt(workspace: Any, work: WorkItem, attempt: Attempt) -> bool:
    if work.risk not in {"R1", "R2"}:
        return False
    if work.required_approval_count != 0:
        return False
    if attempt.status not in {"complete", "completed"}:
        return False
    if _unfinished_dependency_ids(workspace, work):
        return False
    receipt = _latest_for_work(workspace.receipts, work.id)
    if receipt is None or receipt.attempt_id != work.current_attempt:
        return False
    return not (
        receipt.external_writes
        or receipt.planned_external_writes
        or receipt.queued_external_writes
    )


def _unfinished_dependency_ids(workspace: Any, work: WorkItem) -> list[str]:
    work_by_id = {item.id: item for item in workspace.work_items}
    return [
        dependency_id
        for dependency_id in work.dependency_ids
        if work_by_id[dependency_id].status not in TERMINAL_WORK_STATUSES
    ]


def _validate_receipt(
    receipt: Receipt,
    work_by_id: dict[str, WorkItem],
    attempts_by_id: dict[str, Attempt],
    sources_by_id: dict[str, Any],
    integration_plans_by_id: dict[str, IntegrationPlan],
    integration_outbox_by_id: dict[str, IntegrationOutboxItem],
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
    _validate_receipt_boundaries(receipt, work)
    for plan_id in receipt.planned_external_writes:
        plan = integration_plans_by_id[plan_id]
        if plan.work_item_id != work.id:
            raise WorkspaceError(
                f"receipts.{receipt.id}.planned_external_writes includes plan {plan_id} "
                f"for different work item {plan.work_item_id}"
            )
        if plan.status != "approved":
            raise WorkspaceError(
                f"receipts.{receipt.id}.planned_external_writes requires approved "
                f"integration plan {plan_id}; status is {plan.status}"
            )
    for item_id in receipt.queued_external_writes:
        item = integration_outbox_by_id[item_id]
        if item.work_item_id != work.id:
            raise WorkspaceError(
                f"receipts.{receipt.id}.queued_external_writes includes outbox item "
                f"{item_id} for different work item {item.work_item_id}"
            )
        if item.status != "queued":
            raise WorkspaceError(
                f"receipts.{receipt.id}.queued_external_writes requires queued outbox "
                f"item {item_id}; status is {item.status}"
            )
    if receipt.external_writes and not _allows_external_writes(work):
        raise WorkspaceError(
            f"receipts.{receipt.id}.external_writes requires allowed action external_write"
        )


def _validate_evidence_manifest_shape(evidence: EvidenceRun, work: WorkItem) -> None:
    delete_paths = {
        str(item.get("path"))
        for item in work.path_intents
        if isinstance(item, dict)
        and item.get("intent") == "delete"
        and isinstance(item.get("path"), str)
    }
    for artifact_hash in evidence.artifact_hashes:
        path = artifact_hash.get("path")
        digest = artifact_hash.get("sha256")
        status = artifact_hash.get("status")
        if not isinstance(path, str) or not path:
            raise WorkspaceError(
                f"evidence_runs.{evidence.id}.artifact_hashes items require path"
            )
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise WorkspaceError(
                f"evidence_runs.{evidence.id}.artifact_hashes.{path} requires sha256 digest"
            )
        if status == "absent":
            if digest != "sha256:absent":
                raise WorkspaceError(
                    f"evidence_runs.{evidence.id}.artifact_hashes.{path} absent tombstone "
                    "requires sha256:absent"
                )
            if path not in delete_paths:
                raise WorkspaceError(
                    f"evidence_runs.{evidence.id}.artifact_hashes.{path} claims absence "
                    "without a matching delete path intent"
                )
            if path not in evidence.artifacts:
                raise WorkspaceError(
                    f"evidence_runs.{evidence.id}.artifact_hashes.{path} tombstone "
                    "must be declared as an artifact"
                )
        elif digest == "sha256:absent":
            raise WorkspaceError(
                f"evidence_runs.{evidence.id}.artifact_hashes.{path} sha256:absent "
                "requires absent status"
            )
        try:
            validate_workspace_path(path)
        except ValueError as exc:
            raise WorkspaceError(
                f"evidence_runs.{evidence.id}.artifact_hashes contains unsafe path {path}: {exc}"
            ) from exc
    _require_hash_prefix("evidence_runs", evidence.id, "manifest_hash", evidence.manifest_hash)
    _require_hash_prefix("evidence_runs", evidence.id, "receipt_hash", evidence.receipt_hash)
    _require_hash_prefix(
        "evidence_runs",
        evidence.id,
        "previous_receipt_hash",
        evidence.previous_receipt_hash,
    )


def _validate_receipt_hash_shape(receipt: Receipt) -> None:
    _require_hash_prefix("receipts", receipt.id, "receipt_hash", receipt.receipt_hash)
    _require_hash_prefix(
        "receipts",
        receipt.id,
        "previous_receipt_hash",
        receipt.previous_receipt_hash,
    )
    _require_hash_prefix(
        "receipts",
        receipt.id,
        "evidence_manifest_hash",
        receipt.evidence_manifest_hash,
    )


def _require_hash_prefix(collection: str, record_id: str, field: str, value: str) -> None:
    if value and not value.startswith("sha256:"):
        raise WorkspaceError(f"{collection}.{record_id}.{field} must use sha256:HEX format")


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
    latest_by_human: dict[str, HumanDecision] = {}
    for decision in workspace.human_decisions:
        if decision.work_item_id != work.id:
            continue
        if decision.reviewed_head != review.reviewed_head:
            continue
        previous = latest_by_human.get(decision.human_id)
        if previous is None or _decision_order_key(decision) > _decision_order_key(previous):
            latest_by_human[decision.human_id] = decision
    for decision in latest_by_human.values():
        if not _is_acceptance(decision):
            continue
        if (
            decision.review_reference != review.id
            or decision.evidence_reference != review.evidence_reference
        ):
            continue
        human = humans_by_id.get(decision.human_id)
        if work.required_approval_capability and (
            human is None or work.required_approval_capability not in human.approval_capabilities
        ):
            continue
        seen_humans.add(decision.human_id)
    return len(seen_humans)


def _decision_order_key(decision: HumanDecision) -> tuple[datetime, str]:
    try:
        timestamp = datetime.fromisoformat(decision.timestamp.replace("Z", "+00:00"))
    except ValueError:
        timestamp = datetime.min.replace(tzinfo=timezone.utc)
    return (timestamp, decision.id)


def _is_acceptance(decision: HumanDecision) -> bool:
    return decision.status in {"accepted", "approved"} and decision.decision in {
        "accepted",
        "approved",
    }


def _validate_approval_pack_decision(decision: HumanDecision) -> None:
    fields = {
        "approval_pack_id": decision.approval_pack_id,
        "approval_pack_digest": decision.approval_pack_digest,
        "approval_pack_member_digest": decision.approval_pack_member_digest,
        "approval_pack_subject_digest": decision.approval_pack_subject_digest,
        "approval_pack_request_digest": decision.approval_pack_request_digest,
        "approval_pack_action": decision.approval_pack_action,
    }
    present = {key for key, value in fields.items() if value}
    if not present:
        return
    if present != set(fields):
        missing = ", ".join(sorted(set(fields) - present))
        raise WorkspaceError(
            f"human_decisions.{decision.id} has incomplete approval-pack binding: {missing}"
        )
    if decision.acceptance_mode != "approval-pack":
        raise WorkspaceError(
            f"human_decisions.{decision.id}.acceptance_mode must be approval-pack"
        )
    if decision.approval_pack_action not in APPROVAL_PACK_ACTIONS:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.approval_pack_action is unsupported"
        )
    for field in (
        "approval_pack_digest",
        "approval_pack_member_digest",
        "approval_pack_subject_digest",
        "approval_pack_request_digest",
    ):
        value = getattr(decision, field)
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            raise WorkspaceError(
                f"human_decisions.{decision.id}.{field} must be a sha256 digest"
            )
    expected = {
        "approve": ({"accepted", "approved"}, {"accepted", "approved"}),
        "reject": ({"rejected"}, {"rejected"}),
        "defer": ({"deferred"}, {"deferred"}),
    }[decision.approval_pack_action]
    if decision.decision not in expected[0] or decision.status not in expected[1]:
        raise WorkspaceError(
            f"human_decisions.{decision.id} action contradicts decision or status"
        )
    presentation_fields = {
        "approval_presentation_schema_version": decision.approval_presentation_schema_version,
        "approval_presentation_digest": decision.approval_presentation_digest,
        "approval_presentation_surface": decision.approval_presentation_surface,
    }
    presentation_present = {
        key for key, value in presentation_fields.items() if value
    }
    if not presentation_present:
        if decision.approval_presentation:
            raise WorkspaceError(
                f"human_decisions.{decision.id}.approval_presentation requires presentation binding"
            )
        return
    if presentation_present != set(presentation_fields):
        missing = ", ".join(sorted(set(presentation_fields) - presentation_present))
        raise WorkspaceError(
            f"human_decisions.{decision.id} has incomplete approval-presentation binding: {missing}"
        )
    from .approval_presentations import DECISION_SURFACE, PRESENTATION_SCHEMA_VERSION

    if decision.approval_presentation_schema_version != PRESENTATION_SCHEMA_VERSION:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.approval_presentation_schema_version is unsupported"
        )
    if decision.approval_presentation_surface != DECISION_SURFACE:
        raise WorkspaceError(
            f"human_decisions.{decision.id}.approval_presentation_surface is unsupported"
        )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", decision.approval_presentation_digest):
        raise WorkspaceError(
            f"human_decisions.{decision.id}.approval_presentation_digest must be a sha256 digest"
        )


def _validate_approval_pack_decision_sets(workspace: Any) -> None:
    decisions = workspace.human_decisions
    grouped: dict[str, list[HumanDecision]] = {}
    for decision in decisions:
        if decision.approval_pack_digest:
            grouped.setdefault(decision.approval_pack_digest, []).append(decision)
        elif decision.approval_pack_manifest:
            raise WorkspaceError(
                f"human_decisions.{decision.id}.approval_pack_manifest requires pack binding"
            )

    for pack_digest, bound in grouped.items():
        manifests = [
            decision.approval_pack_manifest
            for decision in bound
            if decision.approval_pack_manifest
        ]
        if len(manifests) != 1:
            raise WorkspaceError(
                f"human_decisions approval pack {pack_digest} must retain exactly one canonical manifest"
            )
        from .approval_packs import validate_pack_manifest

        manifest = manifests[0]
        validate_pack_manifest(manifest)
        if manifest["pack_digest"] != pack_digest:
            raise WorkspaceError(
                f"human_decisions approval pack {pack_digest} manifest digest does not match"
            )
        if manifest.get("schema_version") == "palari.approval-pack.v2":
            unbound = [
                decision.id
                for decision in bound
                if not decision.approval_presentation_digest
            ]
            if unbound:
                raise WorkspaceError(
                    "human_decisions approval pack v2 requires presentation binding: "
                    + ", ".join(sorted(unbound))
                )
        presentation_groups: dict[str, list[HumanDecision]] = {}
        for decision in bound:
            if decision.approval_presentation_digest:
                presentation_groups.setdefault(
                    decision.approval_presentation_digest, []
                ).append(decision)
        from .approval_presentations import (
            approval_presentation_digest,
            validate_approval_presentation,
        )

        for presentation_digest, presented_decisions in presentation_groups.items():
            presentations = [
                decision.approval_presentation
                for decision in presented_decisions
                if decision.approval_presentation
            ]
            if len(presentations) != 1:
                raise WorkspaceError(
                    "human_decisions approval presentation "
                    f"{presentation_digest} must retain exactly one canonical artifact"
                )
            presentation = presentations[0]
            validate_approval_presentation(presentation, manifest)
            if approval_presentation_digest(presentation, manifest) != presentation_digest:
                raise WorkspaceError(
                    "human_decisions approval presentation "
                    f"{presentation_digest} digest does not match"
                )
        members = {member["id"]: member for member in manifest["members"]}
        for decision in bound:
            member = members.get(decision.work_item_id)
            if member is None:
                raise WorkspaceError(
                    f"human_decisions.{decision.id} is not a member of its approval pack"
                )
            if member["member_digest"] != decision.approval_pack_member_digest:
                raise WorkspaceError(
                    f"human_decisions.{decision.id}.approval_pack_member_digest is transplanted or stale"
                )
            if member["subject_digest"] != decision.approval_pack_subject_digest:
                raise WorkspaceError(
                    f"human_decisions.{decision.id}.approval_pack_subject_digest is transplanted or stale"
                )
            work = workspace.work_item(decision.work_item_id)
            human = workspace.human(decision.human_id)
            if work is None or human is None:
                continue
            if work.required_approval_capability and (
                work.required_approval_capability not in human.approval_capabilities
            ):
                raise WorkspaceError(
                    f"human_decisions.{decision.id}.human_id lacks required approval "
                    f"capability {work.required_approval_capability}"
                )
            if decision.approval_pack_action == "approve":
                attempt = next(
                    (
                        item
                        for item in workspace.attempts
                        if item.work_item_id == work.id
                        and item.id == member["proof"]["attempt_id"]
                    ),
                    None,
                )
                review = next(
                    (
                        item
                        for item in workspace.review_verdicts
                        if item.work_item_id == work.id
                        and item.id == member["proof"]["review_reference"]
                    ),
                    None,
                )
                if attempt is not None and decision.human_id == attempt.actor:
                    raise WorkspaceError(
                        f"human_decisions.{decision.id}.human_id collides with the builder"
                    )
                if review is not None and decision.human_id == review.reviewer:
                    raise WorkspaceError(
                        f"human_decisions.{decision.id}.human_id collides with the reviewer"
                    )


def _validate_human_decision_order(decisions: Iterable[HumanDecision]) -> None:
    seen: dict[tuple[str, str, str, datetime], str] = {}
    for decision in decisions:
        timestamp = datetime.fromisoformat(
            decision.timestamp.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        key = (
            decision.work_item_id,
            decision.human_id,
            decision.reviewed_head,
            timestamp,
        )
        previous = seen.get(key)
        if previous is not None:
            raise WorkspaceError(
                f"human_decisions.{decision.id}.timestamp duplicates {previous}; "
                "decision order would be ambiguous"
            )
        seen[key] = decision.id


def _attempt_head(attempt: Attempt) -> str:
    return attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")


def _open_linked_decision(workspace: Any, work_id: str) -> Any | None:
    for decision in workspace.decisions:
        if decision.linked_work == work_id and decision.status == "open":
            return decision
    return None


def _latest_for_work(records: Iterable[T], work_id: str) -> T | None:
    latest: T | None = None
    latest_key = None
    for record in records:
        if getattr(record, "work_item_id") != work_id:
            continue
        key = record_time_key(record)
        if latest_key is None or key > latest_key:
            latest = record
            latest_key = key
    return latest
