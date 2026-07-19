from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import timezone
from typing import Any, Iterable, TypeVar

from .evidence_manifest import evidence_artifact_root, verify_evidence
from .governance_case import (
    CASE_SCHEMA_VERSION,
    AcceptanceSnapshot,
    ArtifactDigest,
    AttemptSnapshot,
    DependencyState,
    EvidenceSnapshot,
    Finding,
    GovernanceCase,
    HumanAuthority,
    HumanDecisionSnapshot,
    IntegrityObservation,
    IntegrityObservations,
    LegacyProofBinding,
    OutcomeSnapshot,
    ReceiptSnapshot,
    ReviewerAuthority,
    ReviewSnapshot,
    SourceBoundary,
    WorkContract,
)
from .governance_binding import (
    current_review_binding_errors,
    recorded_current_proof_errors,
    recorded_current_review_binding_errors,
)
from .governance_kernel import (
    ArtifactExpectation,
    GovernanceEvaluation,
    GovernanceEvaluationContext,
    HumanAuthorityCandidate,
    HumanAuthorityCandidateEvaluation,
    evaluate_governance_case,
    evaluate_human_authority_candidate,
)
from .pcaw_canonical import canonical_sha256
from .pcaw_subjects import SubjectError, hash_subject, validate_subject_name
from .record_order import record_time_key, timestamp_order
from .workspace import Workspace, WorkspaceError, current_attempt_for_work


T = TypeVar("T")


@dataclass(frozen=True)
class RecordedGovernanceProjection:
    """Non-authoritative lifecycle projection from stored proof records only."""

    evaluation: GovernanceEvaluation
    completion_evaluation: GovernanceEvaluation
    recorded_proof_errors: tuple[str, ...]
    basis: str = "recorded"
    authoritative: bool = False


@dataclass(frozen=True)
class CompletionAuthorityProjection:
    """Authoritative terminal projection and any required acceptance event."""

    evaluation: GovernanceEvaluation
    candidate: HumanAuthorityCandidateEvaluation | None = None
    acceptance: AcceptanceSnapshot | None = None

    @property
    def ready(self) -> bool:
        return bool(
            (
                self.evaluation.derived_state == "completed"
                and self.evaluation.fully_verified
                and not self.evaluation.errors
            )
            or (self.candidate is not None and self.candidate.acceptance_allowed)
        )


class RecordedGovernanceProjectionProvider:
    """Request-local memoizer for non-authoritative recorded projections.

    The provider deliberately lives outside ``Workspace`` and is created by a
    single read request.  It therefore avoids projecting unrelated work for a
    targeted detail read without turning a recorded projection into persistent
    authority or allowing it to outlive the workspace snapshot it describes.
    """

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace
        self._projections: dict[str, RecordedGovernanceProjection] = {}

    def for_work(self, work_id: str) -> RecordedGovernanceProjection:
        projection = self._projections.get(work_id)
        if projection is None:
            projection = recorded_governance_projection(self._workspace, work_id)
            self._projections[work_id] = projection
        return projection


def governance_context_from_workspace(
    workspace: Workspace,
    work_id: str,
) -> GovernanceEvaluationContext:
    """Project local path intents without adding them to portable PCAW v1."""

    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"unknown work item: {work_id}")
    statuses = {"create": "present", "modify": "present", "delete": "absent"}
    return GovernanceEvaluationContext(
        artifact_expectations=tuple(
            ArtifactExpectation(
                path=str(item.get("path", "")),
                status=statuses.get(str(item.get("intent", "")), ""),
            )
            for item in work.path_intents
        )
    )


def evaluate_workspace_human_authority_candidate(
    workspace: Workspace,
    work_id: str,
    *,
    decision_id: str,
    human_id: str,
    reviewed_head: str,
    timestamp: str,
    acceptance_mode: str,
    decision_value: str = "accepted",
    decision_status: str = "accepted",
    evidence_id: str | None = None,
    review_id: str | None = None,
    acceptance_id: str = "",
    accepted_at: str = "",
    projected_terminal: bool = False,
) -> HumanAuthorityCandidateEvaluation:
    """Project one proposed human decision/acceptance through the pure kernel."""

    governance_case, _ = governance_case_from_workspace(
        workspace,
        work_id,
        projected_contract_status="completed" if projected_terminal else "",
    )
    review = governance_case.review
    evidence = governance_case.evidence
    evidence_id = evidence.id if evidence_id is None and evidence is not None else evidence_id or ""
    review_id = review.id if review_id is None and review is not None else review_id or ""
    decision = HumanDecisionSnapshot(
        id=decision_id,
        work_item_id=work_id,
        human_id=human_id,
        reviewed_head=reviewed_head,
        decision=decision_value,
        status=decision_status,
        acceptance_mode=acceptance_mode,
        quorum_status="pending",
        evidence_id=evidence_id,
        review_id=review_id,
        evidence_digest=governance_case.evidence_digest(),
        review_digest=governance_case.review_digest(),
        timestamp=_timestamp(timestamp),
    )
    acceptance = None
    if acceptance_id:
        acceptance = AcceptanceSnapshot(
            id=acceptance_id,
            work_item_id=work_id,
            human_id=human_id,
            reviewed_head=reviewed_head,
            status="accepted",
            decision_id=decision_id,
            evidence_id=evidence_id,
            review_id=review_id,
            receipt_digest=governance_case.receipt_digest(),
            evidence_digest=governance_case.evidence_digest(),
            review_digest=governance_case.review_digest(),
            quorum_status="met",
            accepted_at=_timestamp(accepted_at or timestamp),
        )
    human = workspace.human(human_id)
    return evaluate_human_authority_candidate(
        governance_case,
        HumanAuthorityCandidate(
            decision=decision,
            acceptance=acceptance,
            human_active=bool(human is not None and human.availability != "inactive"),
        ),
        context=governance_context_from_workspace(workspace, work_id),
    )


def evaluate_workspace_completion_authority(
    workspace: Workspace,
    work_id: str,
    *,
    accepted_at: str,
    acceptance_id: str = "",
) -> CompletionAuthorityProjection:
    """Evaluate terminal authority and project one missing acceptance if safe."""

    governance_case, _ = governance_case_from_workspace(
        workspace,
        work_id,
        projected_contract_status="completed",
    )
    governance_case = replace(governance_case, claimed_state="completed")
    context = governance_context_from_workspace(workspace, work_id)
    evaluation = evaluate_governance_case(governance_case, context=context)
    if (
        evaluation.derived_state == "completed"
        and evaluation.fully_verified
        and not evaluation.errors
    ):
        return CompletionAuthorityProjection(evaluation=evaluation)

    qualified_ids = set(evaluation.qualified_decision_ids)
    decisions = [
        item for item in governance_case.human_decisions if item.id in qualified_ids
    ]
    if not decisions:
        return CompletionAuthorityProjection(evaluation=evaluation)
    decision = max(decisions, key=lambda item: (item.timestamp, item.id))
    acceptance_id = acceptance_id or f"ACCEPTANCE-{work_id}-{decision.human_id}"
    acceptance = AcceptanceSnapshot(
        id=acceptance_id,
        work_item_id=work_id,
        human_id=decision.human_id,
        reviewed_head=decision.reviewed_head,
        status="accepted",
        decision_id=decision.id,
        evidence_id=decision.evidence_id,
        review_id=decision.review_id,
        receipt_digest=governance_case.receipt_digest(),
        evidence_digest=governance_case.evidence_digest(),
        review_digest=governance_case.review_digest(),
        quorum_status="met",
        accepted_at=_timestamp(accepted_at),
    )
    human = workspace.human(decision.human_id)
    candidate = evaluate_human_authority_candidate(
        governance_case,
        HumanAuthorityCandidate(
            decision=decision,
            acceptance=acceptance,
            human_active=bool(human is not None and human.availability != "inactive"),
        ),
        context=context,
    )
    return CompletionAuthorityProjection(
        evaluation=evaluation,
        candidate=candidate,
        acceptance=acceptance,
    )


def recorded_governance_projection(
    workspace: Workspace,
    work_id: str,
) -> RecordedGovernanceProjection:
    """Derive current and candidate-terminal state without external inspection.

    The result is suitable for status, queue, and structural validation.  Its
    evidence observation remains ``not-checked`` and it can never be fully
    verified; transitions must use the external inspection path.
    """

    proof_errors = tuple(recorded_current_proof_errors(workspace, work_id))
    context = replace(
        governance_context_from_workspace(workspace, work_id),
        projection_only_recorded_evidence_current=not proof_errors,
    )
    current_case, _ = governance_case_from_workspace(
        workspace,
        work_id,
        inspect_external=False,
    )
    completion_case, _ = governance_case_from_workspace(
        workspace,
        work_id,
        inspect_external=False,
        projected_contract_status="completed",
    )
    completion_case = replace(completion_case, claimed_state="completed")
    return RecordedGovernanceProjection(
        evaluation=_evaluate_recorded_projection(current_case, context),
        completion_evaluation=_evaluate_recorded_projection(completion_case, context),
        recorded_proof_errors=proof_errors,
    )


def _evaluate_recorded_projection(
    case: GovernanceCase,
    context: GovernanceEvaluationContext,
) -> GovernanceEvaluation:
    """Normalize coarse workspace status to the kernel's more precise state."""

    evaluation = evaluate_governance_case(case, context=context)
    if evaluation.claimed_state == evaluation.derived_state:
        return evaluation
    return evaluate_governance_case(
        replace(case, claimed_state=evaluation.derived_state),
        context=context,
    )


def governance_case_from_workspace(
    workspace: Workspace,
    work_id: str,
    *,
    inspect_external: bool = True,
    projected_contract_status: str = "",
    journal_context: Any | None = None,
) -> tuple[GovernanceCase, list[dict[str, str]]]:
    """Normalize one workspace lifecycle into the provider-neutral PCAW case.

    ``projected_contract_status`` is used only by the authoritative transition
    gate to evaluate a proposed status change.  Applying it before review,
    decision, and acceptance snapshots are normalized keeps every canonical
    digest bound to the same projected case.
    """

    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"unknown work item: {work_id}")

    attempt = current_attempt_for_work(work, workspace.attempts)
    receipt = _latest_for_attempt(workspace.receipts, work_id, _id(attempt))
    evidence = _latest_for_attempt(workspace.evidence_runs, work_id, _id(attempt))
    review = _latest_for_work(workspace.review_verdicts, work_id)
    outcome = _latest_for_work(workspace.outcomes, work_id)

    contract = WorkContract(
        id=work.id,
        title=work.title,
        goal=work.goal,
        palari=work.palari,
        workbench_id=work.workbench_id,
        parent_work_item_id=work.parent_work_item_id,
        risk=work.risk,
        intensity=work.intensity,
        status=projected_contract_status or work.status,
        scope=work.scope,
        allowed_resources=tuple(sorted(work.allowed_resources)),
        allowed_sources=tuple(sorted(work.allowed_sources)),
        allowed_actions=tuple(sorted(work.allowed_actions)),
        output_targets=tuple(sorted(work.output_targets)),
        forbidden_actions=tuple(sorted(work.forbidden_actions)),
        acceptance_target=work.acceptance_target,
        verification_expectations=tuple(work.verification_expectations),
        current_attempt_id=work.current_attempt,
        required_approval_count=work.required_approval_count,
        required_approval_capability=work.required_approval_capability,
        conflict_targets=tuple(sorted(work.conflict_targets)),
        parallel_policy=work.parallel_policy,
    )
    attempt_snapshot = _attempt_snapshot(attempt)
    receipt_snapshot = _receipt_snapshot(receipt)
    evidence_snapshot = _evidence_snapshot(evidence, receipt_snapshot)

    claimed_state = _claimed_workspace_state(work.status)
    case_stub = GovernanceCase(
        schema_version=CASE_SCHEMA_VERSION,
        claimed_state=claimed_state,
        contract=contract,
        attempt=attempt_snapshot,
        receipt=receipt_snapshot,
        evidence=evidence_snapshot,
    )
    review_binding_current = _review_binding_current(
        workspace,
        review,
        inspect_external=inspect_external,
        journal_context=journal_context,
    )
    review_snapshot = _review_snapshot(review, case_stub, review_binding_current)
    review_case = GovernanceCase(
        schema_version=CASE_SCHEMA_VERSION,
        claimed_state=claimed_state,
        contract=contract,
        attempt=attempt_snapshot,
        receipt=receipt_snapshot,
        evidence=evidence_snapshot,
        review=review_snapshot,
    )
    review_digest = review_case.review_digest()
    evidence_digest = case_stub.evidence_digest()
    receipt_digest = case_stub.receipt_digest()
    current_decisions = _current_human_decisions(workspace, work_id, review)
    current_decisions_by_id = {item.id: item for item in current_decisions}
    decisions = tuple(
        _decision_snapshot(
            item,
            evidence_digest if review_binding_current else "",
            review_digest if review_binding_current else "",
        )
        for item in current_decisions
    )
    acceptances = tuple(
        _bound_acceptance_snapshot(
            item,
            review=review,
            current_decisions_by_id=current_decisions_by_id,
            review_binding_current=review_binding_current,
            receipt_digest=receipt_digest,
            evidence_digest=evidence_digest,
            review_digest=review_digest,
        )
        for item in _ordered_for_work(workspace.acceptance_records, work_id)
    )

    if inspect_external:
        context = governance_context_from_workspace(workspace, work_id)
        expected_absent_paths = {
            item.path
            for item in context.artifact_expectations
            if item.status == "absent"
        }
        subject_observation, artifact_subjects = _artifact_subjects(
            workspace,
            evidence,
            expected_absent_paths=expected_absent_paths,
        )
        evidence_observation = _evidence_observation(
            workspace,
            evidence,
            journal_context=journal_context,
        )
        journal_observation = _journal_observation(
            workspace,
            journal_context=journal_context,
        )
    else:
        subject_observation = IntegrityObservation(
            "not-checked" if evidence is not None and evidence.artifacts else "not-required"
        )
        artifact_subjects = []
        evidence_observation = IntegrityObservation(
            "not-checked" if evidence is not None else "not-required"
        )
        journal_observation = IntegrityObservation("not-checked")

    governance_case = GovernanceCase(
        schema_version=CASE_SCHEMA_VERSION,
        claimed_state=claimed_state,
        contract=contract,
        dependencies=tuple(
            DependencyState(id=dependency_id, status=_work_status(workspace, dependency_id))
            for dependency_id in sorted(work.dependency_ids)
        ),
        open_decisions=tuple(
            sorted(
                item.id
                for item in workspace.decisions
                if item.linked_work == work_id and item.status == "open"
            )
        ),
        sources=tuple(
            _source_boundary(source)
            for source in sorted(
                (workspace.source(item) for item in work.allowed_sources),
                key=lambda item: _id(item),
            )
            if source is not None
        ),
        attempt=attempt_snapshot,
        receipt=receipt_snapshot,
        evidence=evidence_snapshot,
        review=review_snapshot,
        reviewer_authorities=tuple(
            ReviewerAuthority(id=palari.id)
            for palari in sorted(workspace.palaris, key=lambda item: item.id)
            if review is not None and palari.id == review.reviewer
        ),
        humans=tuple(
            HumanAuthority(
                id=human.id,
                approval_capabilities=tuple(sorted(human.approval_capabilities)),
            )
            for human in sorted(workspace.humans, key=lambda item: item.id)
        ),
        human_decisions=decisions,
        acceptance_records=acceptances,
        outcome=(
            OutcomeSnapshot(
                id=outcome.id,
                work_item_id=outcome.work_item_id,
                status=outcome.status,
                timestamp=_timestamp(outcome.timestamp),
            )
            if outcome is not None
            else None
        ),
        observations=IntegrityObservations(
            subject_integrity=subject_observation,
            evidence_integrity=evidence_observation,
            journal_continuity=journal_observation,
        ),
    )
    return governance_case, artifact_subjects


def _attempt_snapshot(attempt: Any | None) -> AttemptSnapshot | None:
    if attempt is None:
        return None
    return AttemptSnapshot(
        id=attempt.id,
        work_item_id=attempt.work_item_id,
        actor=attempt.actor,
        status=attempt.status,
        base_sha=attempt.base_sha,
        head_sha=attempt.head_sha,
        commits=tuple(attempt.commits),
        changed_files=tuple(sorted(attempt.changed_files)),
        allowed_paths=tuple(sorted(attempt.allowed_paths)),
        forbidden_paths=tuple(sorted(attempt.forbidden_paths)),
        cleanliness=attempt.cleanliness,
        result=attempt.result,
        output_targets=tuple(sorted(attempt.output_targets)),
        started_at=_timestamp(attempt.started_at),
        updated_at=_timestamp(attempt.updated_at),
    )


def _receipt_snapshot(receipt: Any | None) -> ReceiptSnapshot | None:
    if receipt is None:
        return None
    return ReceiptSnapshot(
        id=receipt.id,
        work_item_id=receipt.work_item_id,
        attempt_id=receipt.attempt_id,
        actor=receipt.actor,
        context_hash=receipt.context_hash,
        sources_used=tuple(sorted(receipt.sources_used)),
        actions_taken=tuple(receipt.actions_taken),
        outputs_created=tuple(sorted(receipt.outputs_created)),
        planned_external_writes=tuple(receipt.planned_external_writes),
        queued_external_writes=tuple(receipt.queued_external_writes),
        external_writes=tuple(receipt.external_writes),
        not_done=tuple(receipt.not_done),
        undo_refs=tuple(
            path for path in (_undo_ref_path(item) for item in receipt.undo_refs) if path
        ),
        receipt_hash=receipt.receipt_hash,
        previous_receipt_hash=receipt.previous_receipt_hash,
        evidence_manifest_hash=receipt.evidence_manifest_hash,
        timestamp=_timestamp(receipt.timestamp),
    )


def _evidence_snapshot(
    evidence: Any | None, receipt: ReceiptSnapshot | None
) -> EvidenceSnapshot | None:
    if evidence is None:
        return None
    artifact_hashes = tuple(
        ArtifactDigest(
            path=str(item.get("path", "")),
            sha256=str(item.get("sha256", "")).removeprefix("sha256:"),
            status=str(item.get("status", "")),
        )
        for item in sorted(evidence.artifact_hashes, key=lambda item: str(item.get("path", "")))
    )
    receipt_digest = canonical_sha256(asdict(receipt)) if receipt is not None else ""
    return EvidenceSnapshot(
        id=evidence.id,
        work_item_id=evidence.work_item_id,
        attempt_id=evidence.attempt_id,
        head_sha=evidence.head_sha,
        status=evidence.status,
        base_ref=evidence.base_ref,
        commands=tuple(evidence.commands),
        artifacts=tuple(sorted(evidence.artifacts)),
        artifact_hashes=artifact_hashes,
        manifest_hash=evidence.manifest_hash,
        receipt_id=receipt.id if receipt is not None else "",
        receipt_digest=receipt_digest,
        receipt_hash=evidence.receipt_hash,
        previous_receipt_hash=evidence.previous_receipt_hash,
        summary=evidence.summary,
        freshness=evidence.freshness,
        timestamp=_timestamp(evidence.timestamp),
    )


def _review_snapshot(
    review: Any | None,
    case: GovernanceCase,
    binding_current: bool,
) -> ReviewSnapshot | None:
    if review is None:
        return None
    return ReviewSnapshot(
        id=review.id,
        work_item_id=review.work_item_id,
        reviewed_head=review.reviewed_head,
        reviewer=review.reviewer,
        verdict=review.verdict,
        attempt_id=review.attempt_id,
        evidence_id=review.evidence_reference,
        receipt_id=review.receipt_reference,
        contract_digest=(
            case.contract_digest() if binding_current else review.work_contract_hash
        ),
        attempt_digest=case.attempt_digest() if binding_current else review.attempt_hash,
        evidence_digest=(
            case.evidence_digest() if binding_current else review.evidence_manifest_hash
        ),
        receipt_digest=case.receipt_digest() if binding_current else review.receipt_hash,
        findings=tuple(_finding(item) for item in review.findings),
        checks_inspected=tuple(review.checks_inspected),
        residual_risks=tuple(review.residual_risks),
        timestamp=_timestamp(review.timestamp),
        legacy_binding=LegacyProofBinding(
            binding_version=review.binding_version,
            attempt_hash=review.attempt_hash,
            evidence_manifest_hash=review.evidence_manifest_hash,
            receipt_hash=review.receipt_hash,
            work_contract_hash=review.work_contract_hash,
            proof_hash=review.proof_hash,
        ),
    )


def _decision_snapshot(
    decision: Any, evidence_digest: str, review_digest: str
) -> HumanDecisionSnapshot:
    return HumanDecisionSnapshot(
        id=decision.id,
        work_item_id=decision.work_item_id,
        human_id=decision.human_id,
        reviewed_head=decision.reviewed_head,
        decision=decision.decision,
        status=decision.status,
        acceptance_mode=decision.acceptance_mode,
        quorum_status=decision.quorum_status,
        evidence_id=decision.evidence_reference,
        review_id=decision.review_reference,
        evidence_digest=evidence_digest,
        review_digest=review_digest,
        timestamp=_timestamp(decision.timestamp),
    )


def _acceptance_snapshot(
    acceptance: Any, receipt_digest: str, evidence_digest: str, review_digest: str
) -> AcceptanceSnapshot:
    return AcceptanceSnapshot(
        id=acceptance.id,
        work_item_id=acceptance.work_item_id,
        human_id=acceptance.human_id,
        reviewed_head=acceptance.reviewed_head,
        status=acceptance.status,
        decision_id=acceptance.decision_id,
        evidence_id=acceptance.evidence_reference,
        review_id=acceptance.review_reference,
        receipt_digest=receipt_digest,
        evidence_digest=evidence_digest,
        review_digest=review_digest,
        quorum_status=acceptance.quorum_status,
        accepted_at=_timestamp(acceptance.accepted_at),
    )


def _bound_acceptance_snapshot(
    acceptance: Any,
    *,
    review: Any | None,
    current_decisions_by_id: dict[str, Any],
    review_binding_current: bool,
    receipt_digest: str,
    evidence_digest: str,
    review_digest: str,
) -> AcceptanceSnapshot:
    decision = current_decisions_by_id.get(acceptance.decision_id)
    binding_current = bool(
        review_binding_current
        and review is not None
        and acceptance.review_reference == review.id
        and acceptance.reviewed_head == review.reviewed_head
        and acceptance.evidence_reference == review.evidence_reference
        and acceptance.receipt_hash == review.receipt_hash
        and decision is not None
        and decision.human_id == acceptance.human_id
        and decision.reviewed_head == acceptance.reviewed_head
        and decision.evidence_reference == acceptance.evidence_reference
        and decision.review_reference == acceptance.review_reference
    )
    if not binding_current:
        receipt_digest = evidence_digest = review_digest = ""
    return _acceptance_snapshot(
        acceptance,
        receipt_digest,
        evidence_digest,
        review_digest,
    )


def _source_boundary(source: Any) -> SourceBoundary:
    return SourceBoundary(
        id=source.id,
        selected=source.selected,
        allowed_palaris=tuple(sorted(source.allowed_palaris)),
        data_class=source.data_class,
        authority=source.authority,
        steward_human=source.steward_human,
        freshness=source.freshness_sla,
        redaction_required=source.redaction_required,
    )


def _finding(value: dict[str, Any]) -> Finding:
    return Finding(
        severity=str(value.get("severity") or value.get("status") or ""),
        summary=str(value.get("summary") or value.get("message") or value.get("title") or ""),
        details=str(value.get("details") or value.get("detail") or ""),
    )


def _artifact_subjects(
    workspace: Workspace,
    evidence: Any | None,
    *,
    expected_absent_paths: set[str] | None = None,
) -> tuple[IntegrityObservation, list[dict[str, str]]]:
    if evidence is None or not evidence.artifacts:
        return IntegrityObservation("not-required"), []
    expected_absent = expected_absent_paths or set()
    try:
        root = evidence_artifact_root(
            workspace.path,
            evidence.attempt_id,
            evidence.artifacts,
            workspace.attempts,
        )
    except ValueError as exc:
        return IntegrityObservation("failed", (f"artifact boundary: {exc}",)), []
    details: list[str] = []
    subjects: list[dict[str, str]] = []
    seen: set[str] = set()
    # Absence has no bytes to hash. Full local evaluation verifies those paths
    # through evidence/Git observations; PCAW export rejects the tombstones.
    portable_artifacts = [
        raw_name
        for raw_name in sorted(evidence.artifacts)
        if raw_name not in expected_absent
    ]
    for index, raw_name in enumerate(portable_artifacts):
        try:
            name = validate_subject_name(raw_name)
            if name in seen:
                raise SubjectError("PCAW_SUBJECT_DUPLICATE", f"duplicate artifact: {name}")
            seen.add(name)
            subjects.append({"name": name, "sha256": hash_subject(root, name)})
        except (OSError, SubjectError, ValueError) as exc:
            details.append(f"artifact[{index}] {raw_name}: {exc}")
    if not portable_artifacts and not details:
        status = "not-required"
    else:
        status = (
            "verified"
            if not details and len(subjects) == len(portable_artifacts)
            else "failed"
        )
    return IntegrityObservation(status, tuple(details)), subjects


def _evidence_observation(
    workspace: Workspace,
    evidence: Any | None,
    *,
    journal_context: Any | None = None,
) -> IntegrityObservation:
    if evidence is None:
        return IntegrityObservation("not-checked", ("current attempt has no evidence",))
    try:
        result = verify_evidence(
            workspace,
            evidence.id,
            require_output_coverage=True,
            journal_context=journal_context,
        )
    except (OSError, ValueError, WorkspaceError) as exc:
        return IntegrityObservation("failed", (str(exc),))
    if result.get("ok"):
        return IntegrityObservation("verified")
    details: list[str] = []
    if not result.get("artifact_hashes_ok"):
        details.append("artifact hashes do not match current files")
    if not result.get("manifest_hash_ok"):
        details.append("evidence manifest hash is stale or malformed")
    if not all(item.get("ok") for item in result.get("receipt_checks", [])):
        details.append("receipt binding is stale or malformed")
    return IntegrityObservation("failed", tuple(details))


def _journal_observation(
    workspace: Workspace,
    *,
    journal_context: Any | None = None,
) -> IntegrityObservation:
    from .governance_journal import JournalError, journal_file_path, verify_journal

    try:
        path = journal_file_path(workspace.path / "workspace.json")
        if not path.exists():
            return IntegrityObservation("not-required", ("legacy workspace not checkpointed",))
        report = (
            journal_context.verify(workspace.path)
            if journal_context is not None
            else verify_journal(workspace.path / "workspace.json")
        )
    except (OSError, ValueError, WorkspaceError, JournalError) as exc:
        return IntegrityObservation("failed", (str(exc),))
    if report.get("ok"):
        return IntegrityObservation("verified")
    details = tuple(
        str(item.get("message", "journal verification failed"))
        for item in report.get("diagnostics", [])
    )
    return IntegrityObservation("failed", details or ("journal verification failed",))


def _current_human_decisions(
    workspace: Workspace, work_id: str, review: Any | None
) -> list[Any]:
    if review is None:
        return []
    latest: dict[str, Any] = {}
    for decision in workspace.human_decisions:
        if decision.work_item_id != work_id or decision.reviewed_head != review.reviewed_head:
            continue
        prior = latest.get(decision.human_id)
        if prior is None or record_time_key(decision) > record_time_key(prior):
            latest[decision.human_id] = decision
    return sorted(latest.values(), key=lambda item: item.human_id)


def _review_binding_current(
    workspace: Workspace,
    review: Any | None,
    *,
    inspect_external: bool,
    journal_context: Any | None = None,
) -> bool:
    if review is None:
        return False
    try:
        if inspect_external:
            errors = current_review_binding_errors(
                workspace,
                review,
                require_output_coverage=True,
                journal_context=journal_context,
            )
        else:
            errors = recorded_current_review_binding_errors(workspace, review)
        return not errors
    except (OSError, ValueError, WorkspaceError):
        return False


def _claimed_workspace_state(status: str) -> str:
    mapping = {
        "proposed": "in-progress",
        "active": "in-progress",
        "in-review": "review-required",
        "needs-human": "human-decision-required",
        "blocked": "blocked",
        "completed": "completed",
        "closed": "completed",
        "done": "completed",
    }
    return mapping.get(status, status)


def _latest_for_attempt(records: Iterable[T], work_id: str, attempt_id: str) -> T | None:
    matching = [
        item
        for item in records
        if getattr(item, "work_item_id", "") == work_id
        and getattr(item, "attempt_id", "") == attempt_id
    ]
    return max(matching, key=record_time_key) if matching else None


def _latest_for_work(records: Iterable[T], work_id: str) -> T | None:
    matching = [item for item in records if getattr(item, "work_item_id", "") == work_id]
    return max(matching, key=record_time_key) if matching else None


def _ordered_for_work(records: Iterable[T], work_id: str) -> list[T]:
    return sorted(
        (item for item in records if getattr(item, "work_item_id", "") == work_id),
        key=record_time_key,
    )


def _work_status(workspace: Workspace, work_id: str) -> str:
    work = workspace.work_item(work_id)
    return work.status if work is not None else "missing"


def _timestamp(value: str) -> str:
    if not value:
        return ""
    parsed = timestamp_order(value)
    if parsed.year == 1:
        raise WorkspaceError(f"ambiguous or malformed timestamp cannot be exported: {value}")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _undo_ref_path(value: str) -> str:
    stripped = value.strip()
    lowered = stripped.lower()
    for prefix in ("delete ", "remove ", "revert ", "restore ", "unlink "):
        if lowered.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped if "/" in stripped or "." in stripped else ""


def _id(value: Any | None) -> str:
    return str(getattr(value, "id", ""))
