from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from .governance_case import (
    AcceptanceSnapshot,
    GovernanceCase,
    HumanDecisionSnapshot,
    IntegrityObservation,
)


EVALUATION_SCHEMA_VERSION = "pcaw.governance_evaluation.v1"
PROPERTY_NAMES = (
    "scope_compliance",
    "subject_integrity",
    "evidence_freshness",
    "receipt_binding",
    "independent_review",
    "human_quorum",
    "acceptance_currency",
    "journal_continuity",
)
TERMINAL_WORK_STATUSES = {"completed", "closed", "done"}
TERMINAL_ATTEMPT_STATUSES = {"complete", "completed"}
APPROVAL_VALUES = {"accepted", "approved"}
NEGATIVE_REVIEW_VERDICTS = {"changes-requested", "needs-human-decision", "blocked"}
PROPERTY_STATUSES = {"verified", "failed", "not-checked", "not-required"}
EXTERNAL_WRITE_ACTIONS = frozenset({"external_write"})


@dataclass(frozen=True)
class Diagnostic:
    code: str
    path: str
    message: str
    next_action: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PropertyResult:
    name: str
    status: str
    evidence_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.name not in PROPERTY_NAMES:
            raise ValueError(f"unsupported verified property: {self.name}")
        if self.status not in PROPERTY_STATUSES:
            raise ValueError(f"unsupported property status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "evidence_paths": list(self.evidence_paths),
        }


@dataclass(frozen=True)
class ArtifactExpectation:
    """Local final-state expectation for one governed artifact path.

    PCAW v1 has no portable deletion-proof claim.  Expectations therefore live
    in evaluator context rather than in the serialized governance case.
    """

    path: str
    status: str


@dataclass(frozen=True)
class GovernanceEvaluationContext:
    """Trusted local context that is deliberately excluded from PCAW proofs."""

    artifact_expectations: tuple[ArtifactExpectation, ...] = ()
    projection_only_recorded_evidence_current: bool = False
    candidate_projection: bool = False


@dataclass(frozen=True)
class GovernanceEvaluation:
    schema_version: str
    claimed_state: str
    derived_state: str
    fully_verified: bool
    properties: tuple[PropertyResult, ...]
    errors: tuple[Diagnostic, ...]
    warnings: tuple[Diagnostic, ...]
    security_limitations: tuple[str, ...]
    qualified_human_ids: tuple[str, ...] = ()
    qualified_decision_ids: tuple[str, ...] = ()
    current_review_bound: bool = False
    human_decision_ready: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "claimed_state": self.claimed_state,
            "derived_state": self.derived_state,
            "fully_verified": self.fully_verified,
            "properties": [item.to_dict() for item in self.properties],
            "errors": [item.to_dict() for item in self.errors],
            "warnings": [item.to_dict() for item in self.warnings],
            "security_limitations": list(self.security_limitations),
        }


@dataclass(frozen=True)
class HumanAuthorityCandidate:
    """One proposed approving decision and its optional acceptance event.

    The candidate is deliberately separate from the portable PCAW statement:
    it is a local transition proposal evaluated against an already normalized
    case, not historical proof that an event occurred.
    """

    decision: HumanDecisionSnapshot
    acceptance: AcceptanceSnapshot | None = None
    human_active: bool = True


@dataclass(frozen=True)
class HumanAuthorityCandidateEvaluation:
    """Pure result for a proposed human-authority transition."""

    governance: GovernanceEvaluation
    decision_allowed: bool
    quorum_met: bool
    acceptance_allowed: bool
    errors: tuple[Diagnostic, ...]


@dataclass(frozen=True)
class ApprovalBatchPolicyEvaluation:
    """Pure decision about whether one governed item may share an approval action."""

    policy_class: str
    batchable: bool
    reversibility: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "class": self.policy_class,
            "batchable": self.batchable,
            "reversibility": self.reversibility,
            "reason": self.reason,
        }


def evaluate_governance_case(
    case: GovernanceCase,
    *,
    context: GovernanceEvaluationContext | None = None,
) -> GovernanceEvaluation:
    """Evaluate one normalized case without filesystem, clock, Git, or workspace state."""

    context = context or GovernanceEvaluationContext()
    errors: list[Diagnostic] = []
    warnings: list[Diagnostic] = []
    properties: dict[str, PropertyResult] = {}

    properties["scope_compliance"] = _scope_property(case, errors)
    properties["subject_integrity"] = _observation_property(
        "subject_integrity", case.observations.subject_integrity, errors, warnings
    )
    properties["journal_continuity"] = _observation_property(
        "journal_continuity", case.observations.journal_continuity, errors, warnings
    )

    receipt_result = _receipt_property(case, errors)
    properties["receipt_binding"] = receipt_result
    evidence_result = _evidence_property(
        case,
        receipt_result,
        context,
        errors,
        warnings,
    )
    properties["evidence_freshness"] = evidence_result

    evidence_complete_low_risk_completion = _evidence_complete_low_risk_completion(
        case, properties, context
    )
    qualified_humans: set[str] = set()
    current_decisions: dict[str, HumanDecisionSnapshot] = {}
    current_review_bound = False
    if evidence_complete_low_risk_completion:
        properties["independent_review"] = PropertyResult(
            "independent_review", "not-required", ("$.contract.risk",)
        )
        properties["human_quorum"] = PropertyResult(
            "human_quorum", "not-required", ("$.contract.required_approval_count",)
        )
        properties["acceptance_currency"] = PropertyResult(
            "acceptance_currency", "not-required", ("$.contract.status",)
        )
        derived_state = "completed"
    else:
        review_result, current_review_bound = _review_property(
            case,
            evidence_result,
            receipt_result,
            context,
            errors,
        )
        properties["independent_review"] = review_result
        quorum_result, current_decisions, qualified_humans = _quorum_property(
            case, review_result, errors
        )
        properties["human_quorum"] = quorum_result
        acceptance_result = _acceptance_property(
            case,
            review_result,
            quorum_result,
            current_decisions,
            qualified_humans,
            errors,
        )
        properties["acceptance_currency"] = acceptance_result
        derived_state = _derive_state(
            case,
            properties,
            context,
            current_negative_review=bool(
                current_review_bound
                and case.review is not None
                and case.review.verdict in NEGATIVE_REVIEW_VERDICTS
            ),
        )

    ordered_properties = tuple(properties[name] for name in PROPERTY_NAMES)
    if case.claimed_state != derived_state and not context.candidate_projection:
        errors.append(
            Diagnostic(
                "PCAW_CLAIMED_STATE_MISMATCH",
                "$.claimed_state",
                f"claimed state {case.claimed_state!r} does not match "
                f"derived state {derived_state!r}",
                "Refresh the proof from the current governed state.",
            )
        )

    fully_verified = derived_state in {"accepted", "completed"} and not errors and all(
        item.status in {"verified", "not-required"} for item in ordered_properties
    )
    if (
        derived_state in {"accepted", "completed"}
        and case.observations.subject_integrity.status == "not-checked"
    ):
        warnings.append(
            Diagnostic(
                "PCAW_STATEMENT_ONLY_INCOMPLETE",
                "$.observations.subject_integrity",
                "statement-only verification does not verify artifact bytes or full acceptance",
                "Verify again with subject files available.",
                severity="warning",
            )
        )
        fully_verified = False
    if context.projection_only_recorded_evidence_current:
        fully_verified = False

    return GovernanceEvaluation(
        schema_version=EVALUATION_SCHEMA_VERSION,
        claimed_state=case.claimed_state,
        derived_state=derived_state,
        fully_verified=fully_verified,
        properties=ordered_properties,
        errors=tuple(_unique_diagnostics(errors)),
        warnings=tuple(_unique_diagnostics(warnings)),
        security_limitations=(
            "Actor, reviewer, and human identities are declared, not "
            "cryptographically authenticated.",
            "Unsigned PCAW v1 verifies internal consistency and supplied "
            "subject bytes, not who created the statement.",
        ),
        qualified_human_ids=tuple(sorted(qualified_humans)),
        qualified_decision_ids=tuple(
            sorted(
                current_decisions[human_id].id
                for human_id in qualified_humans
                if human_id in current_decisions
            )
        ),
        current_review_bound=current_review_bound,
        human_decision_ready=_human_decision_ready(
            case,
            properties,
            current_review_bound=current_review_bound,
        ),
    )


def evaluate_human_authority_candidate(
    case: GovernanceCase,
    candidate: HumanAuthorityCandidate,
    *,
    context: GovernanceEvaluationContext | None = None,
) -> HumanAuthorityCandidateEvaluation:
    """Evaluate a proposed approving decision/acceptance without side effects.

    A decision may be recorded before the full quorum is met.  That expected
    intermediate state is the only kernel diagnostic that does not block the
    decision itself.  Acceptance remains fail-closed and requires the complete
    current proof, independent review, qualified quorum, and exact candidate
    binding in one evaluation.
    """

    context = replace(
        context or GovernanceEvaluationContext(),
        candidate_projection=True,
    )
    errors: list[Diagnostic] = []
    decision = candidate.decision
    acceptance = candidate.acceptance
    humans = {item.id: item for item in case.humans}
    human = humans.get(decision.human_id)
    authority_error: tuple[str, str] | None = None
    if human is None:
        authority_error = (
            "PCAW_CANDIDATE_HUMAN_UNKNOWN",
            f"human authority is not declared: {decision.human_id}",
        )
    elif not candidate.human_active:
        authority_error = (
            "PCAW_CANDIDATE_HUMAN_INACTIVE",
            f"human {decision.human_id} is inactive",
        )
    elif (
        case.contract.required_approval_capability
        and case.contract.required_approval_capability
        not in human.approval_capabilities
    ):
        authority_error = (
            "PCAW_CANDIDATE_HUMAN_UNQUALIFIED",
            f"human {decision.human_id} lacks required approval capability "
            f"{case.contract.required_approval_capability}",
        )
    if authority_error is not None:
        _error(
            errors,
            authority_error[0],
            "$.candidate.decision.human_id",
            authority_error[1],
            "Use a current human with the required approval capability.",
        )

    projected_decisions = tuple(
        item for item in case.human_decisions if item.id != decision.id
    )
    projected_decisions = (*projected_decisions, decision)
    projected_acceptances: tuple[AcceptanceSnapshot, ...] = ()
    if acceptance is not None:
        projected_acceptances = tuple(
            item for item in case.acceptance_records if item.id != acceptance.id
        )
        projected_acceptances = (*projected_acceptances, acceptance)

    projected = replace(
        case,
        human_decisions=projected_decisions,
        acceptance_records=projected_acceptances,
    )
    governance = evaluate_governance_case(projected, context=context)
    candidate_qualified = decision.id in governance.qualified_decision_ids
    if not candidate_qualified and not errors:
        _error(
            errors,
            "PCAW_CANDIDATE_DECISION_STALE",
            "$.candidate.decision",
            "proposed decision is not current qualified authority for the exact proof",
            "Bind a later qualified decision to the current review and evidence.",
        )
    decision_errors = [
        item
        for item in governance.errors
        if item.code != "PCAW_HUMAN_QUORUM_INCOMPLETE"
    ]
    decision_allowed = bool(
        not errors
        and not decision_errors
        and candidate_qualified
        and governance.human_decision_ready
    )
    quorum = next(item for item in governance.properties if item.name == "human_quorum")
    quorum_met = quorum.status in {"verified", "not-required"}
    acceptance_allowed = bool(
        acceptance is not None
        and not errors
        and not governance.errors
        and candidate_qualified
        and governance.current_review_bound
        and governance.fully_verified
        and governance.derived_state in {"accepted", "completed"}
    )
    combined = tuple(_unique_diagnostics([*errors, *governance.errors]))
    return HumanAuthorityCandidateEvaluation(
        governance=governance,
        decision_allowed=decision_allowed,
        quorum_met=quorum_met,
        acceptance_allowed=acceptance_allowed,
        errors=combined,
    )


def _human_decision_ready(
    case: GovernanceCase,
    properties: dict[str, PropertyResult],
    *,
    current_review_bound: bool,
) -> bool:
    required = {
        "scope_compliance",
        "subject_integrity",
        "evidence_freshness",
        "receipt_binding",
        "independent_review",
        "journal_continuity",
    }
    return bool(
        current_review_bound
        and not case.open_decisions
        and case.attempt is not None
        and case.attempt.status in TERMINAL_ATTEMPT_STATUSES
        and case.attempt.cleanliness.lower() in {"clean", "pristine"}
        and all(
            item.status in {"verified", "not-required"}
            for item in properties.values()
            if item.name in required
        )
    )


def _scope_property(case: GovernanceCase, errors: list[Diagnostic]) -> PropertyResult:
    before = len(errors)
    contract = case.contract
    boundaries = tuple(dict.fromkeys((*contract.allowed_resources, *contract.output_targets)))
    for path, label in (
        *((path, "allowed resource") for path in contract.allowed_resources),
        *((path, "output target") for path in contract.output_targets),
    ):
        if not _safe_path(path):
            _error(
                errors,
                "PCAW_SCOPE_PATH_UNSAFE",
                "$.contract",
                f"{label} is not a canonical workspace-relative path: {path}",
                "Use a canonical workspace-relative POSIX path.",
            )

    attempt = case.attempt
    attempt_boundaries = boundaries
    if attempt is not None:
        if attempt.allowed_paths:
            attempt_boundaries = attempt.allowed_paths
            for path in attempt.allowed_paths:
                if not _path_in(path, boundaries):
                    _scope_outside(errors, "$.attempt.allowed_paths", path)
        for path in attempt.changed_files:
            if not _path_in(path, attempt_boundaries):
                _scope_outside(errors, "$.attempt.changed_files", path)
            if any(_path_in(path, (forbidden,)) for forbidden in attempt.forbidden_paths):
                _error(
                    errors,
                    "PCAW_SCOPE_FORBIDDEN_PATH",
                    "$.attempt.changed_files",
                    f"changed file is inside a forbidden path: {path}",
                    "Remove the change or obtain a new bounded work contract.",
                )
        for path in attempt.output_targets:
            if not _path_in(path, boundaries):
                _scope_outside(errors, "$.attempt.output_targets", path)

    receipt = case.receipt
    if receipt is not None:
        for path in (*receipt.outputs_created, *receipt.undo_refs):
            if not _path_in(path, boundaries):
                _scope_outside(errors, "$.receipt.outputs_created", path)
        if any(source not in contract.allowed_sources for source in receipt.sources_used):
            _error(
                errors,
                "PCAW_SOURCE_NOT_ALLOWED",
                "$.receipt.sources_used",
                "receipt declares a source outside the work contract",
                "Remove the source or refresh the work contract and proof.",
            )
        sources = {source.id: source for source in case.sources}
        for source_id in receipt.sources_used:
            source = sources.get(source_id)
            if source is None or not source.selected:
                _error(
                    errors,
                    "PCAW_SOURCE_NOT_SELECTED",
                    "$.sources",
                    f"used source is missing or unselected: {source_id}",
                    "Include the selected source boundary in the proof.",
                )
            elif source.allowed_palaris and contract.palari not in source.allowed_palaris:
                _error(
                    errors,
                    "PCAW_SOURCE_ACTOR_NOT_ALLOWED",
                    "$.sources",
                    f"source {source_id} is not allowed for {contract.palari}",
                    "Use an approved source or refresh authority.",
                )

    evidence = case.evidence
    if evidence is not None:
        for path in evidence.artifacts:
            if not _path_in(path, boundaries):
                _scope_outside(errors, "$.evidence.artifacts", path)

    status = "failed" if len(errors) != before else "verified"
    return PropertyResult("scope_compliance", status, ("$.contract", "$.attempt", "$.receipt"))


def _receipt_property(case: GovernanceCase, errors: list[Diagnostic]) -> PropertyResult:
    receipt = case.receipt
    attempt = case.attempt
    if receipt is None:
        _error(
            errors,
            "PCAW_RECEIPT_MISSING",
            "$.receipt",
            "the current attempt has no receipt",
            "Record a receipt for the current attempt.",
        )
        return PropertyResult("receipt_binding", "failed")
    before = len(errors)
    if attempt is not None and (
        attempt.id != case.contract.current_attempt_id
        or attempt.work_item_id != case.contract.id
    ):
        _error(
            errors,
            "PCAW_ATTEMPT_NOT_CURRENT",
            "$.attempt",
            "attempt does not match the work contract's declared current attempt",
            "Export the exact declared current attempt.",
        )
    if attempt is None or receipt.attempt_id != attempt.id:
        _error(
            errors,
            "PCAW_RECEIPT_ATTEMPT_MISMATCH",
            "$.receipt.attempt_id",
            "receipt is not bound to the current attempt",
            "Record a receipt for the declared current attempt.",
        )
    if receipt.work_item_id != case.contract.id:
        _error(
            errors,
            "PCAW_RECEIPT_WORK_MISMATCH",
            "$.receipt.work_item_id",
            "receipt belongs to a different work item",
            "Use the receipt for this work item.",
        )
    if attempt is not None and receipt.actor not in {attempt.actor, case.contract.palari}:
        _error(
            errors,
            "PCAW_RECEIPT_ACTOR_MISMATCH",
            "$.receipt.actor",
            "receipt actor does not match the attempt actor or assigned Palari",
            "Record the actual bounded actor.",
        )
    if not receipt.actions_taken and not receipt.outputs_created:
        _error(
            errors,
            "PCAW_RECEIPT_EMPTY",
            "$.receipt",
            "receipt records neither actions nor outputs",
            "Record what the attempt actually did.",
        )
    if attempt is not None and attempt.started_at:
        _require_order(attempt.started_at, receipt.timestamp, "$.receipt.timestamp", errors)
    status = "failed" if len(errors) != before else "verified"
    return PropertyResult("receipt_binding", status, ("$.receipt",))


def _evidence_property(
    case: GovernanceCase,
    receipt_result: PropertyResult,
    context: GovernanceEvaluationContext,
    errors: list[Diagnostic],
    warnings: list[Diagnostic],
) -> PropertyResult:
    evidence = case.evidence
    attempt = case.attempt
    if evidence is None:
        _error(
            errors,
            "PCAW_EVIDENCE_MISSING",
            "$.evidence",
            "the current attempt has no evidence",
            "Run and record current verification evidence.",
        )
        return PropertyResult("evidence_freshness", "failed")
    before = len(errors)
    if attempt is None or evidence.attempt_id != attempt.id:
        _error(
            errors,
            "PCAW_EVIDENCE_ATTEMPT_MISMATCH",
            "$.evidence.attempt_id",
            "evidence is not bound to the current attempt",
            "Refresh evidence for the current attempt.",
        )
    if evidence.work_item_id != case.contract.id:
        _error(
            errors,
            "PCAW_EVIDENCE_WORK_MISMATCH",
            "$.evidence.work_item_id",
            "evidence belongs to a different work item",
            "Use evidence for this work item.",
        )
    if evidence.status != "passed":
        _error(
            errors,
            "PCAW_EVIDENCE_NOT_PASSED",
            "$.evidence.status",
            f"evidence status is {evidence.status!r}, not 'passed'",
            "Repair verification failures and record fresh evidence.",
        )
    if attempt is None or not _attempt_head(attempt) or evidence.head_sha != _attempt_head(attempt):
        _error(
            errors,
            "PCAW_EVIDENCE_STALE",
            "$.evidence.head_sha",
            "evidence head does not match the current attempt head",
            "Refresh evidence against the exact current head.",
        )
    if not evidence.commands or not evidence.summary.strip() or not evidence.timestamp:
        _error(
            errors,
            "PCAW_EVIDENCE_INCOMPLETE",
            "$.evidence",
            "evidence requires commands, a summary, and a timestamp",
            "Record complete verification evidence.",
        )
    if case.receipt is not None:
        if (
            evidence.receipt_id != case.receipt.id
            or evidence.receipt_digest != case.receipt_digest()
        ):
            _error(
                errors,
                "PCAW_EVIDENCE_RECEIPT_STALE",
                "$.evidence.receipt_digest",
                "evidence is not bound to the exact current receipt",
                "Refresh evidence after recording the current receipt.",
            )
        _require_order(
            case.receipt.timestamp,
            evidence.timestamp,
            "$.evidence.timestamp",
            errors,
        )
    if receipt_result.status != "verified":
        _error(
            errors,
            "PCAW_EVIDENCE_RECEIPT_INVALID",
            "$.receipt",
            "evidence cannot be current because its receipt is invalid",
            "Repair the receipt and refresh evidence.",
        )

    expected_statuses = _artifact_expectation_statuses(case, context, errors)
    hashes = {item.path: item for item in evidence.artifact_hashes}
    if (
        len(hashes) != len(evidence.artifact_hashes)
        or len(set(evidence.artifacts)) != len(evidence.artifacts)
        or set(hashes) != set(evidence.artifacts)
    ):
        _error(
            errors,
            "PCAW_EVIDENCE_DUPLICATE_ARTIFACT",
            "$.evidence.artifact_hashes",
            "artifact paths and digests must form one exact unique set",
            "Keep exactly one digest for each output artifact.",
        )
    for path in evidence.artifacts:
        item = hashes.get(path)
        expected_status = expected_statuses.get(path, "present")
        if expected_status == "absent":
            verified = (
                item is not None
                and item.status == "absent"
                and item.sha256 == "absent"
            )
            message = f"artifact does not prove its expected absence: {path}"
            next_action = (
                "Record exact local deletion evidence and verify the governed Git range."
            )
        else:
            verified = (
                item is not None
                and item.status == "present"
                and _valid_digest(item.sha256)
            )
            message = f"artifact lacks a current SHA-256 digest: {path}"
            next_action = "Hash the current artifact bytes and refresh evidence."
        if not verified:
            _error(
                errors,
                "PCAW_EVIDENCE_ARTIFACT_UNVERIFIED",
                "$.evidence.artifact_hashes",
                message,
                next_action,
            )
    if case.receipt is not None:
        missing_outputs = sorted(set(case.receipt.outputs_created) - set(evidence.artifacts))
        if missing_outputs:
            _error(
                errors,
                "PCAW_EVIDENCE_OUTPUT_UNHASHED",
                "$.evidence.artifacts",
                "receipt outputs lack evidence digests: " + ", ".join(missing_outputs),
                "Include every created output in the evidence artifact list.",
            )

    observation = case.observations.evidence_integrity
    if observation.status == "failed":
        _observation_diagnostics("evidence_integrity", observation, errors, "error")
    elif observation.status == "not-checked":
        _observation_diagnostics("evidence_integrity", observation, warnings, "warning")
    if len(errors) != before:
        status = "failed"
    elif observation.status in {"verified", "not-required"}:
        status = "verified"
    else:
        status = observation.status
    return PropertyResult("evidence_freshness", status, ("$.attempt", "$.evidence"))


def _artifact_expectation_statuses(
    case: GovernanceCase,
    context: GovernanceEvaluationContext,
    errors: list[Diagnostic],
) -> dict[str, str]:
    """Validate local expectations and return exact per-path status overrides."""

    statuses: dict[str, str] = {}
    for index, expectation in enumerate(context.artifact_expectations):
        if not isinstance(expectation, ArtifactExpectation):
            _error(
                errors,
                "PCAW_EVIDENCE_EXPECTATION_INVALID",
                "$.evidence.artifacts",
                f"artifact expectation {index} is malformed",
                "Use one typed final-state expectation for each artifact path.",
            )
            continue
        path = expectation.path
        label = f"artifact expectation {index}"
        if not isinstance(path, str) or not _safe_path(path):
            _error(
                errors,
                "PCAW_EVIDENCE_EXPECTATION_INVALID",
                "$.evidence.artifacts",
                f"{label} has an unsafe path: {path!r}",
                "Use one canonical workspace-relative artifact expectation.",
            )
            continue
        if not isinstance(expectation.status, str) or expectation.status not in {
            "present",
            "absent",
        }:
            _error(
                errors,
                "PCAW_EVIDENCE_EXPECTATION_INVALID",
                "$.evidence.artifacts",
                f"{label} has unsupported status: {expectation.status!r}",
                "Expect each local artifact to be either present or absent.",
            )
            continue
        if path in statuses:
            _error(
                errors,
                "PCAW_EVIDENCE_EXPECTATION_INVALID",
                "$.evidence.artifacts",
                f"local artifact expectation is duplicated: {path}",
                "Keep one final-state expectation for each artifact path.",
            )
            continue
        statuses[path] = expectation.status

    evidence_paths = set(case.evidence.artifacts if case.evidence is not None else ())
    unexpected = sorted(set(statuses) - evidence_paths)
    if unexpected:
        _error(
            errors,
            "PCAW_EVIDENCE_EXPECTATION_INVALID",
            "$.evidence.artifacts",
            "local artifact expectations lack evidence: " + ", ".join(unexpected),
            "Include exact evidence for every local artifact expectation.",
        )
    return statuses


def _review_property(
    case: GovernanceCase,
    evidence_result: PropertyResult,
    receipt_result: PropertyResult,
    context: GovernanceEvaluationContext,
    errors: list[Diagnostic],
) -> tuple[PropertyResult, bool]:
    review = case.review
    if review is None:
        return PropertyResult("independent_review", "failed"), False
    before = len(errors)
    humans = {human.id: human for human in case.humans}
    reviewer_authorities = {authority.id for authority in case.reviewer_authorities}
    if review.reviewer not in humans and review.reviewer not in reviewer_authorities:
        _error(
            errors,
            "PCAW_REVIEWER_UNKNOWN",
            "$.review.reviewer",
            "reviewer is not a declared human or reviewer authority",
            "Include the human or Palari reviewer authority record.",
        )
    if case.attempt is not None and review.reviewer == case.attempt.actor:
        _error(
            errors,
            "PCAW_REVIEWER_NOT_INDEPENDENT",
            "$.review.reviewer",
            "reviewer is also the attempt actor",
            "Assign a distinct human or Palari reviewer.",
        )
    expected = {
        "work_item_id": case.contract.id,
        "reviewed_head": _attempt_head(case.attempt),
        "attempt_id": case.attempt.id if case.attempt else "",
        "evidence_id": case.evidence.id if case.evidence else "",
        "receipt_id": case.receipt.id if case.receipt else "",
        "contract_digest": case.contract_digest(),
        "attempt_digest": case.attempt_digest(),
        "evidence_digest": case.evidence_digest(),
        "receipt_digest": case.receipt_digest(),
    }
    for field, value in expected.items():
        if getattr(review, field) != value:
            _error(
                errors,
                "PCAW_REVIEW_BINDING_STALE",
                f"$.review.{field}",
                f"review {field} does not match the current exact proof",
                "Obtain a new review against the current exact proof.",
            )
    if not _evidence_ready(evidence_result, context) or receipt_result.status != "verified":
        _error(
            errors,
            "PCAW_REVIEW_PREREQUISITE_INVALID",
            "$.review",
            "review cannot be current while receipt or evidence proof is invalid",
            "Repair proof and obtain a fresh independent review.",
        )
    _require_order(
        case.evidence.timestamp if case.evidence else "",
        review.timestamp,
        "$.review.timestamp",
        errors,
    )
    current_binding = len(errors) == before
    if review.verdict != "accept-ready":
        code = (
            "PCAW_REVIEW_NEGATIVE"
            if review.verdict in NEGATIVE_REVIEW_VERDICTS
            else "PCAW_REVIEW_NOT_READY"
        )
        _error(
            errors,
            code,
            "$.review.verdict",
            f"review verdict is {review.verdict!r}, not 'accept-ready'",
            "Obtain a fresh independent accept-ready review.",
        )
    status = "failed" if len(errors) != before else "verified"
    authority_path = (
        "$.humans" if review.reviewer in humans else "$.reviewer_authorities"
    )
    return (
        PropertyResult("independent_review", status, ("$.review", authority_path)),
        current_binding,
    )


def _quorum_property(
    case: GovernanceCase,
    review_result: PropertyResult,
    errors: list[Diagnostic],
) -> tuple[PropertyResult, dict[str, HumanDecisionSnapshot], set[str]]:
    required_count = case.contract.required_approval_count
    if review_result.status != "verified" or case.review is None:
        if required_count == 0:
            return (
                PropertyResult(
                    "human_quorum",
                    "not-required",
                    ("$.contract.required_approval_count",),
                ),
                {},
                set(),
            )
        return PropertyResult("human_quorum", "failed"), {}, set()
    before = len(errors)
    current: dict[str, HumanDecisionSnapshot] = {}
    seen_instants: dict[tuple[str, datetime], str] = {}
    review_digest = case.review_digest()
    evidence_digest = case.evidence_digest()
    for decision in case.human_decisions:
        if decision.work_item_id != case.contract.id:
            continue
        instant = _timestamp(decision.timestamp)
        if instant is None:
            _error(
                errors,
                "PCAW_DECISION_TIMESTAMP_INVALID",
                "$.human_decisions",
                f"decision {decision.id} has an invalid or ambiguous timestamp",
                "Use an ISO-8601 timestamp with an explicit timezone.",
            )
            continue
        key = (decision.human_id, instant)
        if key in seen_instants:
            _error(
                errors,
                "PCAW_DECISION_ORDER_AMBIGUOUS",
                "$.human_decisions",
                f"decisions {seen_instants[key]} and {decision.id} have the same human and instant",
                "Record an unambiguous later decision timestamp.",
            )
        seen_instants[key] = decision.id
        previous = current.get(decision.human_id)
        if previous is None or (_timestamp(previous.timestamp), previous.id) < (
            instant,
            decision.id,
        ):
            current[decision.human_id] = decision

    humans = {human.id: human for human in case.humans}
    qualified: set[str] = set()
    for decision in current.values():
        if (decision.decision in APPROVAL_VALUES) != (decision.status in APPROVAL_VALUES):
            _error(
                errors,
                "PCAW_DECISION_CONTRADICTORY",
                "$.human_decisions",
                f"decision {decision.id} has contradictory decision and status values",
                "Record one explicit, internally consistent human decision.",
            )
        if not _decision_is_approval(decision):
            continue
        if not _decision_matches_current_proof(
            case,
            decision,
            review_digest=review_digest,
            evidence_digest=evidence_digest,
        ):
            continue
        human = humans.get(decision.human_id)
        if human is None:
            continue
        capability = case.contract.required_approval_capability
        if capability and capability not in human.approval_capabilities:
            continue
        _require_order(case.review.timestamp, decision.timestamp, "$.human_decisions", errors)
        qualified.add(decision.human_id)
    if len(qualified) < required_count:
        _error(
            errors,
            "PCAW_HUMAN_QUORUM_INCOMPLETE",
            "$.human_decisions",
            f"qualified human quorum is {len(qualified)}/{required_count}",
            "Collect current decisions from qualified humans.",
        )
    if len(errors) != before:
        status = "failed"
    elif required_count == 0:
        status = "not-required"
    else:
        status = "verified"
    return (
        PropertyResult("human_quorum", status, ("$.human_decisions", "$.humans")),
        current,
        qualified,
    )


def _acceptance_property(
    case: GovernanceCase,
    review_result: PropertyResult,
    quorum_result: PropertyResult,
    current_decisions: dict[str, HumanDecisionSnapshot],
    qualified_humans: set[str],
    errors: list[Diagnostic],
) -> PropertyResult:
    if not case.acceptance_records:
        return PropertyResult("acceptance_currency", "failed")
    before = len(errors)
    ordered: list[tuple[datetime, AcceptanceSnapshot]] = []
    seen: dict[datetime, str] = {}
    for acceptance in case.acceptance_records:
        instant = _timestamp(acceptance.accepted_at)
        if instant is None:
            _error(
                errors,
                "PCAW_ACCEPTANCE_TIMESTAMP_INVALID",
                "$.acceptance_records",
                f"acceptance {acceptance.id} has an invalid timestamp",
                "Use an ISO-8601 timestamp with an explicit timezone.",
            )
            continue
        if instant in seen:
            _error(
                errors,
                "PCAW_ACCEPTANCE_ORDER_AMBIGUOUS",
                "$.acceptance_records",
                f"acceptances {seen[instant]} and {acceptance.id} have the same instant",
                "Record an unambiguous later acceptance event.",
            )
        seen[instant] = acceptance.id
        ordered.append((instant, acceptance))
    if not ordered:
        return PropertyResult("acceptance_currency", "failed")
    acceptance = max(ordered, key=lambda item: (item[0], item[1].id))[1]
    if acceptance.status != "accepted":
        _error(
            errors,
            "PCAW_ACCEPTANCE_REVOKED",
            "$.acceptance_records",
            f"latest acceptance status is {acceptance.status!r}",
            "Obtain a new current human decision and acceptance.",
        )
    review = case.review
    expected = {
        "work_item_id": case.contract.id,
        "reviewed_head": review.reviewed_head if review else "",
        "evidence_id": case.evidence.id if case.evidence else "",
        "review_id": review.id if review else "",
        "receipt_digest": case.receipt_digest(),
        "evidence_digest": case.evidence_digest(),
        "review_digest": case.review_digest(),
        "quorum_status": "met",
    }
    for field, value in expected.items():
        if getattr(acceptance, field) != value:
            _error(
                errors,
                "PCAW_ACCEPTANCE_BINDING_STALE",
                f"$.acceptance_records.{field}",
                f"acceptance {field} does not match current proof",
                "Record a new acceptance for the current exact proof.",
            )
    decision = current_decisions.get(acceptance.human_id)
    if (
        decision is None
        or decision.id != acceptance.decision_id
        or not _decision_is_approval(decision)
    ):
        _error(
            errors,
            "PCAW_ACCEPTANCE_DECISION_STALE",
            "$.acceptance_records.decision_id",
            "acceptance does not reference the current approving decision",
            "Record acceptance from a current qualified decision.",
        )
    elif not _decision_matches_current_proof(case, decision):
        _error(
            errors,
            "PCAW_ACCEPTANCE_DECISION_STALE",
            "$.acceptance_records.decision_id",
            "acceptance decision does not match the current exact proof",
            "Record acceptance from a current qualified decision.",
        )
    elif acceptance.human_id not in qualified_humans:
        _error(
            errors,
            "PCAW_ACCEPTANCE_HUMAN_UNQUALIFIED",
            "$.acceptance_records.human_id",
            "acceptance is attributed to a human outside the qualified quorum",
            "Record acceptance from a current human with the required capability.",
        )
    elif decision.timestamp:
        _require_order(decision.timestamp, acceptance.accepted_at, "$.acceptance_records", errors)
    if review_result.status != "verified" or quorum_result.status not in {
        "verified",
        "not-required",
    }:
        _error(
            errors,
            "PCAW_ACCEPTANCE_PREREQUISITE_INVALID",
            "$.acceptance_records",
            "acceptance is not current because review or quorum is invalid",
            "Refresh review and human quorum before acceptance.",
        )
    status = "failed" if len(errors) != before else "verified"
    return PropertyResult("acceptance_currency", status, ("$.acceptance_records",))


def _evidence_complete_low_risk_completion(
    case: GovernanceCase,
    properties: dict[str, PropertyResult],
    context: GovernanceEvaluationContext,
) -> bool:
    if not (
        case.contract.status in TERMINAL_WORK_STATUSES
        and low_risk_completion_policy_applies(
            risk=case.contract.risk,
            intensity=case.contract.intensity,
            required_approval_count=case.contract.required_approval_count,
            allowed_actions=case.contract.allowed_actions,
            planned_external_writes=(
                case.receipt.planned_external_writes if case.receipt else ()
            ),
            queued_external_writes=(
                case.receipt.queued_external_writes if case.receipt else ()
            ),
            external_writes=case.receipt.external_writes if case.receipt else (),
        )
        and case.attempt is not None
        and case.attempt.status in TERMINAL_ATTEMPT_STATUSES
        and case.attempt.cleanliness.lower() in {"clean", "pristine"}
        and case.receipt is not None
        and properties["scope_compliance"].status == "verified"
        and properties["receipt_binding"].status == "verified"
        and _evidence_ready(properties["evidence_freshness"], context)
    ):
        return False
    if case.open_decisions or any(
        item.status not in TERMINAL_WORK_STATUSES for item in case.dependencies
    ):
        return False
    return True


def low_risk_completion_policy_applies(
    *,
    risk: str,
    intensity: str,
    required_approval_count: int,
    allowed_actions: tuple[str, ...] | list[str] = (),
    planned_external_writes: tuple[str, ...] | list[str] = (),
    queued_external_writes: tuple[str, ...] | list[str] = (),
    external_writes: tuple[str, ...] | list[str] = (),
) -> bool:
    """Return whether exact evidence may replace review and human acceptance."""

    return bool(
        risk == "R1"
        and intensity == "light"
        and required_approval_count == 0
        and not (set(allowed_actions) & EXTERNAL_WRITE_ACTIONS)
        and not planned_external_writes
        and not queued_external_writes
        and not external_writes
    )


def evaluate_approval_batch_policy(
    *,
    risk: str,
    allowed_actions: tuple[str, ...] | list[str] = (),
    external_effects: tuple[str, ...] | list[str] = (),
) -> ApprovalBatchPolicyEvaluation:
    """Derive Approval Pack batching authority from declared governance facts."""

    if external_effects or set(allowed_actions) & EXTERNAL_WRITE_ACTIONS:
        return ApprovalBatchPolicyEvaluation(
            policy_class="external-effect",
            batchable=False,
            reversibility="compensating-action-required",
            reason=(
                "declared external-write authority or a recorded external effect "
                "requires individual human authority"
            ),
        )
    if risk in {"R1", "R2"}:
        return ApprovalBatchPolicyEvaluation(
            policy_class="local-work",
            batchable=True,
            reversibility="reversible-local",
            reason="R1/R2 local work without external effects is eligible for batched approval",
        )
    if risk in {"R3", "R4", "R5"}:
        return ApprovalBatchPolicyEvaluation(
            policy_class="elevated-risk",
            batchable=False,
            reversibility="reversible-local",
            reason=f"{risk} work requires individual human authority",
        )
    return ApprovalBatchPolicyEvaluation(
        policy_class="unknown-risk",
        batchable=False,
        reversibility="reversible-local",
        reason="unknown risk classifications fail closed to individual human authority",
    )


def _derive_state(
    case: GovernanceCase,
    properties: dict[str, PropertyResult],
    context: GovernanceEvaluationContext,
    *,
    current_negative_review: bool,
) -> str:
    if case.contract.status in {"proposed", "active"} and (
        case.attempt is None or case.attempt.status == "active"
    ):
        return "in-progress"
    if (
        case.contract.status == "blocked"
        or case.open_decisions
        or any(item.status not in TERMINAL_WORK_STATUSES for item in case.dependencies)
        or case.attempt is None
        or case.attempt.status not in TERMINAL_ATTEMPT_STATUSES
        or case.attempt.cleanliness.lower() not in {"clean", "pristine"}
        or properties["scope_compliance"].status != "verified"
        or properties["receipt_binding"].status != "verified"
        or not _evidence_ready(properties["evidence_freshness"], context)
    ):
        return "blocked"
    if current_negative_review:
        return "blocked"
    if properties["independent_review"].status != "verified":
        return "review-required"
    if properties["human_quorum"].status not in {"verified", "not-required"}:
        return "human-decision-required"
    if not case.acceptance_records:
        return "accept-ready"
    if properties["acceptance_currency"].status != "verified":
        return "blocked"
    if case.contract.status in TERMINAL_WORK_STATUSES:
        return "completed"
    return "accepted"


def _evidence_ready(
    result: PropertyResult,
    context: GovernanceEvaluationContext,
) -> bool:
    """Allow structurally current stored evidence to drive read-only projection."""

    return result.status == "verified" or bool(
        context.projection_only_recorded_evidence_current
        and result.status == "not-checked"
    )


def _observation_property(
    name: str,
    observation: IntegrityObservation,
    errors: list[Diagnostic],
    warnings: list[Diagnostic],
) -> PropertyResult:
    target = errors if observation.status == "failed" else warnings
    severity = "error" if observation.status == "failed" else "warning"
    if observation.status in {"failed", "not-checked"}:
        _observation_diagnostics(name, observation, target, severity)
    return PropertyResult(name, observation.status, (f"$.observations.{name}",))


def _observation_diagnostics(
    name: str,
    observation: IntegrityObservation,
    target: list[Diagnostic],
    severity: str,
) -> None:
    details = "; ".join(observation.details) or f"{name.replace('_', ' ')} is {observation.status}"
    target.append(
        Diagnostic(
            f"PCAW_{name.upper()}_{observation.status.upper().replace('-', '_')}",
            f"$.observations.{name}",
            details,
            "Provide the required bytes or continuity evidence and verify again.",
            severity=severity,
        )
    )


def _attempt_head(attempt: Any) -> str:
    if attempt is None:
        return ""
    return attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")


def _decision_is_approval(decision: HumanDecisionSnapshot) -> bool:
    return (
        decision.decision in APPROVAL_VALUES
        and decision.status in APPROVAL_VALUES
        and decision.acceptance_mode in {"human", "approval-pack"}
    )


def _decision_matches_current_proof(
    case: GovernanceCase,
    decision: HumanDecisionSnapshot,
    *,
    review_digest: str | None = None,
    evidence_digest: str | None = None,
) -> bool:
    review = case.review
    if review is None:
        return False
    return (
        decision.reviewed_head == review.reviewed_head
        and decision.review_id == review.id
        and decision.evidence_id == (case.evidence.id if case.evidence else "")
        and decision.review_digest == (review_digest or case.review_digest())
        and decision.evidence_digest == (evidence_digest or case.evidence_digest())
    )


def _require_order(
    earlier: str,
    later: str,
    path: str,
    errors: list[Diagnostic],
) -> None:
    first = _timestamp(earlier)
    second = _timestamp(later)
    if first is None or second is None or second < first:
        _error(
            errors,
            "PCAW_LIFECYCLE_ORDER_INVALID",
            path,
            "lifecycle timestamps are missing, malformed, or reversed",
            "Record each lifecycle event after its prerequisite using timezone-aware timestamps.",
        )


def _timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        return None
    if parsed.utcoffset() is None:
        return None
    try:
        return parsed.astimezone(timezone.utc)
    except OverflowError:
        return None


def _safe_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        return False
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    first = parts[0]
    if len(first) >= 2 and first[1] == ":" and first[0].isalpha():
        return False
    return str(PurePosixPath(path)) == path


def _path_in(path: str, boundaries: tuple[str, ...]) -> bool:
    if not _safe_path(path):
        return False
    for boundary in boundaries:
        if _safe_path(boundary) and (path == boundary or path.startswith(boundary + "/")):
            return True
    return False


def _scope_outside(errors: list[Diagnostic], path: str, value: str) -> None:
    _error(
        errors,
        "PCAW_SCOPE_OUTSIDE_BOUNDARY",
        path,
        f"path is outside the declared boundary: {value}",
        "Remove the path or obtain a new bounded work contract.",
    )


def _valid_digest(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _error(
    errors: list[Diagnostic],
    code: str,
    path: str,
    message: str,
    next_action: str,
) -> None:
    errors.append(Diagnostic(code, path, message, next_action))


def _unique_diagnostics(values: list[Diagnostic]) -> list[Diagnostic]:
    seen: set[tuple[str, str, str]] = set()
    result: list[Diagnostic] = []
    for value in values:
        key = (value.code, value.path, value.message)
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result
