from __future__ import annotations

from dataclasses import asdict, dataclass
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
class GovernanceEvaluation:
    schema_version: str
    claimed_state: str
    derived_state: str
    fully_verified: bool
    properties: tuple[PropertyResult, ...]
    errors: tuple[Diagnostic, ...]
    warnings: tuple[Diagnostic, ...]
    security_limitations: tuple[str, ...]

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


def evaluate_governance_case(case: GovernanceCase) -> GovernanceEvaluation:
    """Evaluate one normalized case without filesystem, clock, Git, or workspace state."""

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
    evidence_result = _evidence_property(case, receipt_result, errors, warnings)
    properties["evidence_freshness"] = evidence_result

    legacy_receipt_completion = _legacy_receipt_completion(case, properties, errors)
    if legacy_receipt_completion:
        properties["evidence_freshness"] = PropertyResult(
            "evidence_freshness", "not-required", ("$.receipt",)
        )
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
        review_result = _review_property(case, evidence_result, receipt_result, errors)
        properties["independent_review"] = review_result
        quorum_result, current_decisions = _quorum_property(case, review_result, errors)
        properties["human_quorum"] = quorum_result
        acceptance_result = _acceptance_property(
            case, review_result, quorum_result, current_decisions, errors
        )
        properties["acceptance_currency"] = acceptance_result
        derived_state = _derive_state(case, properties)

    ordered_properties = tuple(properties[name] for name in PROPERTY_NAMES)
    if case.claimed_state != derived_state:
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
    if attempt is not None:
        _require_order(
            attempt.updated_at or attempt.started_at,
            receipt.timestamp,
            "$.receipt.timestamp",
            errors,
        )
    status = "failed" if len(errors) != before else "verified"
    return PropertyResult("receipt_binding", status, ("$.receipt",))


def _evidence_property(
    case: GovernanceCase,
    receipt_result: PropertyResult,
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

    hashes = {item.path: item for item in evidence.artifact_hashes}
    if len(hashes) != len(evidence.artifact_hashes) or len(set(evidence.artifacts)) != len(
        evidence.artifacts
    ):
        _error(
            errors,
            "PCAW_EVIDENCE_DUPLICATE_ARTIFACT",
            "$.evidence.artifact_hashes",
            "artifact paths must be unique",
            "Keep one digest for each output artifact.",
        )
    for path in evidence.artifacts:
        item = hashes.get(path)
        if item is None or item.status != "present" or not _valid_digest(item.sha256):
            _error(
                errors,
                "PCAW_EVIDENCE_ARTIFACT_UNVERIFIED",
                "$.evidence.artifact_hashes",
                f"artifact lacks a current SHA-256 digest: {path}",
                "Hash the current artifact bytes and refresh evidence.",
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


def _review_property(
    case: GovernanceCase,
    evidence_result: PropertyResult,
    receipt_result: PropertyResult,
    errors: list[Diagnostic],
) -> PropertyResult:
    review = case.review
    if review is None:
        return PropertyResult("independent_review", "failed")
    before = len(errors)
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
    humans = {human.id: human for human in case.humans}
    if review.reviewer not in humans:
        _error(
            errors,
            "PCAW_REVIEWER_UNKNOWN",
            "$.review.reviewer",
            "reviewer is not a declared human",
            "Include the reviewer authority record.",
        )
    if case.attempt is not None and review.reviewer == case.attempt.actor:
        _error(
            errors,
            "PCAW_REVIEWER_NOT_INDEPENDENT",
            "$.review.reviewer",
            "reviewer is also the attempt actor",
            "Assign a distinct human reviewer.",
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
    if evidence_result.status != "verified" or receipt_result.status != "verified":
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
    status = "failed" if len(errors) != before else "verified"
    return PropertyResult("independent_review", status, ("$.review", "$.humans"))


def _quorum_property(
    case: GovernanceCase,
    review_result: PropertyResult,
    errors: list[Diagnostic],
) -> tuple[PropertyResult, dict[str, HumanDecisionSnapshot]]:
    if case.contract.required_approval_count == 0:
        return (
            PropertyResult("human_quorum", "not-required", ("$.contract.required_approval_count",)),
            {},
        )
    if review_result.status != "verified" or case.review is None:
        return PropertyResult("human_quorum", "failed"), {}
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
        if (
            decision.reviewed_head != case.review.reviewed_head
            or decision.review_id != case.review.id
            or decision.evidence_id != (case.evidence.id if case.evidence else "")
            or decision.review_digest != review_digest
            or decision.evidence_digest != evidence_digest
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
    if len(qualified) < case.contract.required_approval_count:
        _error(
            errors,
            "PCAW_HUMAN_QUORUM_INCOMPLETE",
            "$.human_decisions",
            f"qualified human quorum is {len(qualified)}/{case.contract.required_approval_count}",
            "Collect current decisions from qualified humans.",
        )
    status = "failed" if len(errors) != before else "verified"
    return PropertyResult("human_quorum", status, ("$.human_decisions", "$.humans")), current


def _acceptance_property(
    case: GovernanceCase,
    review_result: PropertyResult,
    quorum_result: PropertyResult,
    current_decisions: dict[str, HumanDecisionSnapshot],
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


def _legacy_receipt_completion(
    case: GovernanceCase,
    properties: dict[str, PropertyResult],
    errors: list[Diagnostic],
) -> bool:
    if not (
        case.contract.status in TERMINAL_WORK_STATUSES
        and case.contract.risk in {"R1", "R2"}
        and case.contract.required_approval_count == 0
        and case.attempt is not None
        and case.attempt.status in TERMINAL_ATTEMPT_STATUSES
        and case.receipt is not None
        and properties["scope_compliance"].status == "verified"
        and properties["receipt_binding"].status == "verified"
    ):
        return False
    if (
        case.receipt.external_writes
        or case.receipt.planned_external_writes
        or case.receipt.queued_external_writes
    ):
        _error(
            errors,
            "PCAW_RECEIPT_PATH_EXTERNAL_WRITE",
            "$.receipt",
            "low-risk receipt completion cannot include external writes",
            "Use the governed review and human-acceptance path.",
        )
        return False
    if case.open_decisions or any(
        item.status not in TERMINAL_WORK_STATUSES for item in case.dependencies
    ):
        return False
    return True


def _derive_state(case: GovernanceCase, properties: dict[str, PropertyResult]) -> str:
    if (
        case.contract.status == "blocked"
        or case.open_decisions
        or any(item.status not in TERMINAL_WORK_STATUSES for item in case.dependencies)
        or case.attempt is None
        or case.attempt.status not in TERMINAL_ATTEMPT_STATUSES
        or case.attempt.cleanliness.lower() not in {"clean", "pristine"}
        or properties["scope_compliance"].status != "verified"
        or properties["receipt_binding"].status != "verified"
        or properties["evidence_freshness"].status != "verified"
    ):
        return "blocked"
    if case.review is not None and case.review.verdict in NEGATIVE_REVIEW_VERDICTS:
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
        and decision.acceptance_mode == "human"
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
