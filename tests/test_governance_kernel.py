from __future__ import annotations

import unittest
import sys
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.governance_case import (
    CASE_SCHEMA_VERSION,
    AcceptanceSnapshot,
    ArtifactDigest,
    AttemptSnapshot,
    DependencyState,
    EvidenceSnapshot,
    GovernanceCase,
    HumanAuthority,
    HumanDecisionSnapshot,
    IntegrityObservation,
    IntegrityObservations,
    LegacyProofBinding,
    ReceiptSnapshot,
    ReviewerAuthority,
    ReviewSnapshot,
    SourceBoundary,
    WorkContract,
)
from palari_company_os.governance_kernel import (
    PROPERTY_NAMES,
    ArtifactExpectation,
    GovernanceEvaluationContext,
    HumanAuthorityCandidate,
    evaluate_governance_case,
    evaluate_human_authority_candidate,
)


ARTIFACT_DIGEST = "a" * 64


def accepted_case(*, claimed_state: str = "accepted", terminal: bool = False) -> GovernanceCase:
    contract = WorkContract(
        id="WORK-1",
        title="Create governed artifact",
        goal="GOAL-1",
        palari="PALARI-BUILDER",
        risk="R4",
        intensity="high",
        status="completed" if terminal else "in-review",
        scope="Create one bounded output.",
        allowed_resources=("out",),
        allowed_sources=("SOURCE-1",),
        allowed_actions=("write",),
        output_targets=("out/result.txt",),
        forbidden_actions=("external-write",),
        acceptance_target="Qualified human acceptance.",
        verification_expectations=("focused tests pass",),
        current_attempt_id="ATTEMPT-1",
        required_approval_count=1,
        required_approval_capability="product",
    )
    attempt = AttemptSnapshot(
        id="ATTEMPT-1",
        work_item_id="WORK-1",
        actor="PALARI-BUILDER",
        status="complete",
        head_sha="head-1",
        commits=("head-1",),
        changed_files=("out/result.txt",),
        allowed_paths=("out",),
        cleanliness="clean",
        output_targets=("out/result.txt",),
        started_at="2030-01-01T00:00:00Z",
        updated_at="2030-01-01T00:01:00Z",
    )
    receipt = ReceiptSnapshot(
        id="RECEIPT-1",
        work_item_id="WORK-1",
        attempt_id="ATTEMPT-1",
        actor="PALARI-BUILDER",
        sources_used=("SOURCE-1",),
        actions_taken=("created bounded artifact",),
        outputs_created=("out/result.txt",),
        receipt_hash="sha256:" + "b" * 64,
        timestamp="2030-01-01T00:02:00Z",
    )
    partial = GovernanceCase(
        CASE_SCHEMA_VERSION,
        claimed_state,
        contract,
        sources=(SourceBoundary("SOURCE-1", allowed_palaris=("PALARI-BUILDER",)),),
        attempt=attempt,
        receipt=receipt,
        humans=(HumanAuthority("HUMAN-REVIEWER"), HumanAuthority("HUMAN-FOUNDER", ("product",))),
    )
    evidence = EvidenceSnapshot(
        id="EVIDENCE-1",
        work_item_id="WORK-1",
        attempt_id="ATTEMPT-1",
        head_sha="head-1",
        status="passed",
        commands=("python3 -m unittest",),
        artifacts=("out/result.txt",),
        artifact_hashes=(ArtifactDigest("out/result.txt", ARTIFACT_DIGEST),),
        manifest_hash="sha256:" + "c" * 64,
        receipt_id="RECEIPT-1",
        receipt_digest=partial.receipt_digest(),
        receipt_hash=receipt.receipt_hash,
        summary="Focused verification passed.",
        freshness="current",
        timestamp="2030-01-01T00:03:00Z",
    )
    partial = replace(partial, evidence=evidence)
    review = ReviewSnapshot(
        id="REVIEW-1",
        work_item_id="WORK-1",
        reviewed_head="head-1",
        reviewer="HUMAN-REVIEWER",
        verdict="accept-ready",
        attempt_id="ATTEMPT-1",
        evidence_id="EVIDENCE-1",
        receipt_id="RECEIPT-1",
        contract_digest=partial.contract_digest(),
        attempt_digest=partial.attempt_digest(),
        evidence_digest=partial.evidence_digest(),
        receipt_digest=partial.receipt_digest(),
        checks_inspected=("python3 -m unittest",),
        timestamp="2030-01-01T00:04:00Z",
        legacy_binding=LegacyProofBinding(binding_version="palari.review_binding.v1"),
    )
    partial = replace(partial, review=review)
    decision = HumanDecisionSnapshot(
        id="DECISION-1",
        work_item_id="WORK-1",
        human_id="HUMAN-FOUNDER",
        reviewed_head="head-1",
        decision="accepted",
        status="accepted",
        acceptance_mode="human",
        quorum_status="met",
        evidence_id="EVIDENCE-1",
        review_id="REVIEW-1",
        evidence_digest=partial.evidence_digest(),
        review_digest=partial.review_digest(),
        timestamp="2030-01-01T00:05:00Z",
    )
    acceptance = AcceptanceSnapshot(
        id="ACCEPTANCE-1",
        work_item_id="WORK-1",
        human_id="HUMAN-FOUNDER",
        reviewed_head="head-1",
        status="accepted",
        decision_id="DECISION-1",
        evidence_id="EVIDENCE-1",
        review_id="REVIEW-1",
        receipt_digest=partial.receipt_digest(),
        evidence_digest=partial.evidence_digest(),
        review_digest=partial.review_digest(),
        quorum_status="met",
        accepted_at="2030-01-01T00:06:00Z",
    )
    observations = IntegrityObservations(
        subject_integrity=IntegrityObservation("verified", ("all subjects match",)),
        evidence_integrity=IntegrityObservation("verified", ("manifest matches",)),
        journal_continuity=IntegrityObservation("not-required", ("legacy checkpoint",)),
    )
    return replace(
        partial,
        human_decisions=(decision,),
        acceptance_records=(acceptance,),
        observations=observations,
    )


def accepted_zero_quorum_case() -> GovernanceCase:
    case = accepted_case()
    case = replace(
        case,
        contract=replace(
            case.contract,
            required_approval_count=0,
            required_approval_capability="",
        ),
    )
    case = replace(
        case,
        review=replace(case.review, contract_digest=case.contract_digest()),
    )
    review_digest = case.review_digest()
    return replace(
        case,
        human_decisions=(
            replace(case.human_decisions[0], review_digest=review_digest),
        ),
        acceptance_records=(
            replace(case.acceptance_records[0], review_digest=review_digest),
        ),
    )


def evidence_complete_low_risk_case() -> GovernanceCase:
    case = accepted_case(claimed_state="completed", terminal=True)
    return replace(
        case,
        contract=replace(
            case.contract,
            risk="R1",
            intensity="light",
            required_approval_count=0,
            required_approval_capability="",
            allowed_actions=("local_write",),
        ),
        dependencies=(DependencyState("WORK-DEPENDENCY", "completed"),),
        review=None,
        humans=(),
        human_decisions=(),
        acceptance_records=(),
    )


def accepted_deletion_case() -> GovernanceCase:
    case = accepted_case()
    tombstone = ArtifactDigest("out/result.txt", "absent", status="absent")
    case = replace(
        case,
        evidence=replace(case.evidence, artifact_hashes=(tombstone,)),
    )
    case = replace(
        case,
        review=replace(case.review, evidence_digest=case.evidence_digest()),
    )
    review_digest = case.review_digest()
    return replace(
        case,
        human_decisions=(
            replace(
                case.human_decisions[0],
                evidence_digest=case.evidence_digest(),
                review_digest=review_digest,
            ),
        ),
        acceptance_records=(
            replace(
                case.acceptance_records[0],
                evidence_digest=case.evidence_digest(),
                review_digest=review_digest,
            ),
        ),
    )


class GovernanceCaseTests(unittest.TestCase):
    def test_case_round_trip_is_exact_and_rejects_unknown_fields(self) -> None:
        case = accepted_case()

        restored = GovernanceCase.from_dict(case.to_dict())

        self.assertEqual(restored, case)
        unknown = case.to_dict()
        unknown["surprise"] = True
        with self.assertRaisesRegex(ValueError, "unknown field"):
            GovernanceCase.from_dict(unknown)
        wrong_type = case.to_dict()
        wrong_type["contract"]["required_approval_count"] = True
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            GovernanceCase.from_dict(wrong_type)


class GovernanceKernelTests(unittest.TestCase):
    def test_candidate_decision_is_allowed_before_quorum_without_acceptance(self) -> None:
        case = accepted_case(claimed_state="human-decision-required")
        decision = case.human_decisions[0]
        case = replace(
            case,
            contract=replace(case.contract, required_approval_count=2),
            human_decisions=(),
            acceptance_records=(),
        )
        case = replace(
            case,
            review=replace(case.review, contract_digest=case.contract_digest()),
        )
        decision = replace(
            decision,
            quorum_status="pending",
            review_digest=case.review_digest(),
        )

        result = evaluate_human_authority_candidate(
            case,
            HumanAuthorityCandidate(decision),
        )
        premature_acceptance = evaluate_human_authority_candidate(
            case,
            HumanAuthorityCandidate(
                decision,
                replace(
                    accepted_case().acceptance_records[0],
                    quorum_status="met",
                ),
            ),
        )

        self.assertTrue(result.decision_allowed, result.errors)
        self.assertFalse(result.quorum_met)
        self.assertFalse(result.acceptance_allowed)
        self.assertFalse(premature_acceptance.acceptance_allowed)
        self.assertIn(
            "PCAW_HUMAN_QUORUM_INCOMPLETE",
            {item.code for item in premature_acceptance.errors},
        )
        self.assertEqual(result.governance.derived_state, "human-decision-required")

    def test_candidate_acceptance_requires_exact_current_qualified_authority(self) -> None:
        accepted = accepted_case()
        case = replace(accepted, human_decisions=(), acceptance_records=())
        decision = accepted.human_decisions[0]
        acceptance = accepted.acceptance_records[0]

        valid = evaluate_human_authority_candidate(
            case,
            HumanAuthorityCandidate(decision, acceptance),
        )
        self.assertTrue(valid.decision_allowed, valid.errors)
        self.assertTrue(valid.quorum_met)
        self.assertTrue(valid.acceptance_allowed, valid.errors)
        cases = (
            (
                "inactive",
                HumanAuthorityCandidate(decision, acceptance, human_active=False),
                "PCAW_CANDIDATE_HUMAN_INACTIVE",
            ),
            (
                "stale binding",
                HumanAuthorityCandidate(
                    replace(decision, reviewed_head="stale-head"), acceptance
                ),
                "PCAW_CANDIDATE_DECISION_STALE",
            ),
            (
                "unknown human",
                HumanAuthorityCandidate(
                    replace(decision, id="DECISION-UNKNOWN", human_id="HUMAN-UNKNOWN"),
                    acceptance,
                ),
                "PCAW_CANDIDATE_HUMAN_UNKNOWN",
            ),
        )
        for label, candidate, expected in cases:
            with self.subTest(label=label):
                result = evaluate_human_authority_candidate(case, candidate)
                self.assertFalse(result.decision_allowed)
                self.assertFalse(result.acceptance_allowed)
                self.assertIn(expected, {item.code for item in result.errors})

    def test_candidate_decision_cannot_borrow_another_humans_quorum(self) -> None:
        case = accepted_case(claimed_state="accept-ready")
        observer = HumanAuthority("HUMAN-OBSERVER")
        candidate = replace(
            case.human_decisions[0],
            id="DECISION-OBSERVER",
            human_id=observer.id,
            timestamp="2030-01-01T00:06:00Z",
        )

        result = evaluate_human_authority_candidate(
            replace(case, humans=(*case.humans, observer), acceptance_records=()),
            HumanAuthorityCandidate(candidate),
        )

        self.assertTrue(result.quorum_met)
        self.assertFalse(result.decision_allowed)
        self.assertIn(
            "PCAW_CANDIDATE_HUMAN_UNQUALIFIED",
            {item.code for item in result.errors},
        )

    def test_current_acceptance_verifies_all_eight_properties(self) -> None:
        result = evaluate_governance_case(accepted_case())

        self.assertEqual(result.derived_state, "accepted")
        self.assertTrue(result.fully_verified)
        self.assertEqual(tuple(item.name for item in result.properties), PROPERTY_NAMES)
        self.assertTrue(
            all(item.status in {"verified", "not-required"} for item in result.properties)
        )
        self.assertEqual(result.errors, ())

    def test_declared_palari_reviewer_verifies_without_becoming_human(self) -> None:
        case = accepted_case()
        review = replace(case.review, reviewer="PALARI-REVIEWER")
        case = replace(
            case,
            review=review,
            reviewer_authorities=(ReviewerAuthority("PALARI-REVIEWER"),),
        )
        review_digest = case.review_digest()
        case = replace(
            case,
            human_decisions=(
                replace(case.human_decisions[0], review_digest=review_digest),
            ),
            acceptance_records=(
                replace(case.acceptance_records[0], review_digest=review_digest),
            ),
        )

        result = evaluate_governance_case(case)
        properties = {item.name: item for item in result.properties}

        self.assertEqual(result.derived_state, "accepted")
        self.assertEqual(properties["independent_review"].status, "verified")
        self.assertEqual(properties["human_quorum"].status, "verified")

    def test_palari_reviewer_cannot_satisfy_human_quorum(self) -> None:
        case = accepted_case(claimed_state="human-decision-required")
        review = replace(case.review, reviewer="PALARI-REVIEWER")
        case = replace(
            case,
            review=review,
            reviewer_authorities=(ReviewerAuthority("PALARI-REVIEWER"),),
        )
        agent_decision = replace(
            case.human_decisions[0],
            human_id="PALARI-REVIEWER",
            review_digest=case.review_digest(),
        )

        result = evaluate_governance_case(
            replace(case, human_decisions=(agent_decision,), acceptance_records=())
        )

        self.assertEqual(result.derived_state, "human-decision-required")
        self.assertIn(
            "PCAW_HUMAN_QUORUM_INCOMPLETE", {item.code for item in result.errors}
        )

    def test_terminal_current_acceptance_derives_completed(self) -> None:
        result = evaluate_governance_case(accepted_case(claimed_state="completed", terminal=True))

        self.assertEqual(result.derived_state, "completed")
        self.assertTrue(result.fully_verified)

    def test_evidence_complete_low_risk_work_needs_no_review_or_human_acceptance(
        self,
    ) -> None:
        result = evaluate_governance_case(evidence_complete_low_risk_case())
        properties = {item.name: item.status for item in result.properties}

        self.assertEqual(result.derived_state, "completed")
        self.assertTrue(result.fully_verified)
        self.assertEqual(properties["scope_compliance"], "verified")
        self.assertEqual(properties["receipt_binding"], "verified")
        self.assertEqual(properties["evidence_freshness"], "verified")
        self.assertEqual(properties["independent_review"], "not-required")
        self.assertEqual(properties["human_quorum"], "not-required")
        self.assertEqual(properties["acceptance_currency"], "not-required")
        self.assertEqual(result.errors, ())

    def test_low_risk_completion_requires_exact_current_evidence(self) -> None:
        case = evidence_complete_low_risk_case()
        stale_receipt = replace(case.receipt, actions_taken=("changed after evidence",))
        cases = (
            (
                "missing",
                replace(case, claimed_state="blocked", evidence=None),
                "PCAW_EVIDENCE_MISSING",
            ),
            (
                "stale head",
                replace(
                    case,
                    claimed_state="blocked",
                    evidence=replace(case.evidence, head_sha="stale-head"),
                ),
                "PCAW_EVIDENCE_STALE",
            ),
            (
                "stale receipt binding",
                replace(case, claimed_state="blocked", receipt=stale_receipt),
                "PCAW_EVIDENCE_RECEIPT_STALE",
            ),
        )

        for label, candidate, expected_error in cases:
            with self.subTest(label):
                result = evaluate_governance_case(candidate)
                properties = {item.name: item.status for item in result.properties}

                self.assertEqual(result.derived_state, "blocked")
                self.assertFalse(result.fully_verified)
                self.assertEqual(properties["evidence_freshness"], "failed")
                self.assertNotEqual(properties["independent_review"], "not-required")
                self.assertIn(expected_error, {item.code for item in result.errors})

    def test_review_and_human_acceptance_are_optional_only_for_narrow_policy(
        self,
    ) -> None:
        case = evidence_complete_low_risk_case()

        external_write_cases = []
        for field in (
            "external_writes",
            "planned_external_writes",
            "queued_external_writes",
        ):
            receipt = replace(case.receipt, **{field: ("WRITE-1",)})
            candidate = replace(case, receipt=receipt)
            candidate = replace(
                candidate,
                evidence=replace(
                    candidate.evidence,
                    receipt_digest=candidate.receipt_digest(),
                ),
            )
            external_write_cases.append((field, candidate))

        cases = (
            ("R2 risk", replace(case, contract=replace(case.contract, risk="R2"))),
            (
                "non-light intensity",
                replace(case, contract=replace(case.contract, intensity="high")),
            ),
            (
                "approval required",
                replace(
                    case,
                    contract=replace(case.contract, required_approval_count=1),
                ),
            ),
            (
                "declared external write",
                replace(
                    case,
                    contract=replace(
                        case.contract,
                        allowed_actions=(*case.contract.allowed_actions, "external_write"),
                    ),
                ),
            ),
            (
                "non-terminal work",
                replace(case, contract=replace(case.contract, status="in-review")),
            ),
            (
                "non-terminal attempt",
                replace(case, attempt=replace(case.attempt, status="active")),
            ),
            (
                "dirty attempt",
                replace(case, attempt=replace(case.attempt, cleanliness="dirty")),
            ),
            (
                "non-current attempt",
                replace(
                    case,
                    contract=replace(case.contract, current_attempt_id="ATTEMPT-NEW"),
                ),
            ),
            (
                "scope failure",
                replace(
                    case,
                    attempt=replace(case.attempt, changed_files=("outside.txt",)),
                ),
            ),
            (
                "receipt failure",
                replace(case, receipt=replace(case.receipt, attempt_id="ATTEMPT-OLD")),
            ),
            ("open decision", replace(case, open_decisions=("DECISION-OPEN",))),
            (
                "unfinished dependency",
                replace(case, dependencies=(DependencyState("WORK-DEPENDENCY", "active"),)),
            ),
            *external_write_cases,
        )

        for label, candidate in cases:
            with self.subTest(label):
                result = evaluate_governance_case(candidate)
                properties = {item.name: item.status for item in result.properties}

                self.assertNotEqual(result.derived_state, "completed")
                self.assertFalse(result.fully_verified)
                self.assertNotEqual(properties["independent_review"], "not-required")

    def test_only_canonical_external_write_action_disables_low_risk_completion(self) -> None:
        case = evidence_complete_low_risk_case()

        for action, expected in (
            ("write", "completed"),
            ("write_external", "completed"),
            ("external_write", "review-required"),
        ):
            with self.subTest(action=action):
                candidate = replace(
                    case,
                    claimed_state=expected,
                    contract=replace(case.contract, allowed_actions=(action,)),
                )
                self.assertEqual(
                    evaluate_governance_case(candidate).derived_state,
                    expected,
                )

    def test_substantive_attempt_mutation_invalidates_evidence_review_and_acceptance(self) -> None:
        case = accepted_case(claimed_state="blocked")
        case = replace(case, attempt=replace(case.attempt, head_sha="mutated-head"))

        result = evaluate_governance_case(case)

        self.assertEqual(result.derived_state, "blocked")
        self.assertFalse(result.fully_verified)
        self.assertIn("PCAW_EVIDENCE_STALE", {item.code for item in result.errors})

    def test_contract_mutation_requires_a_fresh_review(self) -> None:
        case = accepted_case(claimed_state="review-required")
        case = replace(case, contract=replace(case.contract, scope="Substantively changed."))

        result = evaluate_governance_case(case)

        self.assertEqual(result.derived_state, "review-required")
        self.assertIn("PCAW_REVIEW_BINDING_STALE", {item.code for item in result.errors})

    def test_receipt_mutation_stales_evidence(self) -> None:
        case = accepted_case(claimed_state="blocked")
        case = replace(case, receipt=replace(case.receipt, actions_taken=("changed later",)))

        result = evaluate_governance_case(case)

        self.assertEqual(result.derived_state, "blocked")
        self.assertIn("PCAW_EVIDENCE_RECEIPT_STALE", {item.code for item in result.errors})

    def test_statement_only_cannot_fully_verify_acceptance(self) -> None:
        case = accepted_case()
        observations = replace(
            case.observations,
            subject_integrity=IntegrityObservation("not-checked", ("statement-only mode",)),
        )

        result = evaluate_governance_case(replace(case, observations=observations))

        self.assertEqual(result.derived_state, "accepted")
        self.assertFalse(result.fully_verified)
        self.assertIn("PCAW_STATEMENT_ONLY_INCOMPLETE", {item.code for item in result.warnings})

    def test_recorded_projection_derives_state_without_claiming_verification(self) -> None:
        case = accepted_case()
        observations = IntegrityObservations(
            subject_integrity=IntegrityObservation("not-checked", ("projection only",)),
            evidence_integrity=IntegrityObservation("not-checked", ("projection only",)),
            journal_continuity=IntegrityObservation("not-checked", ("projection only",)),
        )
        context = GovernanceEvaluationContext(
            projection_only_recorded_evidence_current=True
        )

        result = evaluate_governance_case(
            replace(case, observations=observations),
            context=context,
        )
        properties = {item.name: item.status for item in result.properties}

        self.assertEqual(result.derived_state, "accepted")
        self.assertEqual(properties["evidence_freshness"], "not-checked")
        self.assertEqual(result.qualified_human_ids, ("HUMAN-FOUNDER",))
        self.assertFalse(result.fully_verified)
        self.assertNotIn("qualified_human_ids", result.to_dict())

    def test_recorded_projection_flag_cannot_bypass_structural_evidence_failure(self) -> None:
        case = accepted_case(claimed_state="blocked")
        observations = replace(
            case.observations,
            evidence_integrity=IntegrityObservation("not-checked", ("projection only",)),
        )

        result = evaluate_governance_case(
            replace(
                case,
                evidence=replace(case.evidence, head_sha="stale-head"),
                observations=observations,
            ),
            context=GovernanceEvaluationContext(
                projection_only_recorded_evidence_current=True
            ),
        )

        self.assertEqual(result.derived_state, "blocked")
        self.assertFalse(result.fully_verified)
        self.assertIn("PCAW_EVIDENCE_STALE", {item.code for item in result.errors})

    def test_builder_reviewer_collision_requires_new_review(self) -> None:
        case = accepted_case(claimed_state="review-required")
        case = replace(case, review=replace(case.review, reviewer="PALARI-BUILDER"))

        result = evaluate_governance_case(case)

        self.assertEqual(result.derived_state, "review-required")
        self.assertIn("PCAW_REVIEWER_NOT_INDEPENDENT", {item.code for item in result.errors})

    def test_only_a_current_exact_negative_review_blocks_the_attempt(self) -> None:
        case = accepted_case(claimed_state="blocked")
        current_negative = replace(
            case,
            review=replace(case.review, verdict="changes-requested"),
        )
        stale_negative = replace(
            current_negative,
            claimed_state="review-required",
            review=replace(current_negative.review, reviewed_head="stale-head"),
        )

        blocked = evaluate_governance_case(current_negative)
        stale = evaluate_governance_case(stale_negative)

        self.assertEqual(blocked.derived_state, "blocked")
        self.assertTrue(blocked.current_review_bound)
        self.assertEqual(stale.derived_state, "review-required")
        self.assertFalse(stale.current_review_bound)
        self.assertNotIn("current_review_bound", blocked.to_dict())

    def test_later_negative_decision_revokes_quorum(self) -> None:
        case = accepted_case(claimed_state="human-decision-required")
        negative = replace(
            case.human_decisions[0],
            id="DECISION-2",
            decision="changes-requested",
            status="changes-requested",
            evidence_id="",
            review_id="",
            evidence_digest="",
            review_digest="",
            timestamp="2030-01-01T00:07:00Z",
        )

        result = evaluate_governance_case(
            replace(case, human_decisions=(*case.human_decisions, negative))
        )

        self.assertEqual(result.derived_state, "human-decision-required")
        self.assertIn("PCAW_HUMAN_QUORUM_INCOMPLETE", {item.code for item in result.errors})

    def test_acceptance_actor_must_belong_to_qualified_quorum(self) -> None:
        case = accepted_case(claimed_state="blocked")
        observer = HumanAuthority("HUMAN-OBSERVER")
        observer_decision = replace(
            case.human_decisions[0],
            id="DECISION-OBSERVER",
            human_id=observer.id,
            timestamp="2030-01-01T00:05:30Z",
        )
        observer_acceptance = replace(
            case.acceptance_records[0],
            id="ACCEPTANCE-OBSERVER",
            human_id=observer.id,
            decision_id=observer_decision.id,
            accepted_at="2030-01-01T00:06:30Z",
        )

        result = evaluate_governance_case(
            replace(
                case,
                humans=(*case.humans, observer),
                human_decisions=(*case.human_decisions, observer_decision),
                acceptance_records=(observer_acceptance,),
            )
        )

        self.assertEqual(result.derived_state, "blocked")
        self.assertIn(
            "PCAW_ACCEPTANCE_HUMAN_UNQUALIFIED",
            {item.code for item in result.errors},
        )

    def test_traversal_fails_scope_closed(self) -> None:
        case = accepted_case(claimed_state="blocked")
        case = replace(
            case,
            attempt=replace(case.attempt, changed_files=("out/../secret.txt",)),
        )

        result = evaluate_governance_case(case)

        self.assertEqual(result.derived_state, "blocked")
        self.assertEqual(result.properties[0].status, "failed")
        self.assertIn("PCAW_SCOPE_OUTSIDE_BOUNDARY", {item.code for item in result.errors})

    def test_artifact_digest_requires_raw_lowercase_sha256(self) -> None:
        case = accepted_case(claimed_state="blocked")
        bad_hash = replace(case.evidence.artifact_hashes[0], sha256="A" * 64)
        case = replace(
            case,
            evidence=replace(case.evidence, artifact_hashes=(bad_hash,)),
        )

        result = evaluate_governance_case(case)

        self.assertEqual(result.derived_state, "blocked")
        self.assertIn(
            "PCAW_EVIDENCE_ARTIFACT_UNVERIFIED",
            {item.code for item in result.errors},
        )

    def test_absence_tombstone_requires_explicit_local_expectation(self) -> None:
        case = accepted_deletion_case()

        portable_result = evaluate_governance_case(
            replace(case, claimed_state="blocked")
        )
        local_result = evaluate_governance_case(
            case,
            context=GovernanceEvaluationContext(
                (ArtifactExpectation("out/result.txt", "absent"),)
            ),
        )

        self.assertEqual(portable_result.derived_state, "blocked")
        self.assertIn(
            "PCAW_EVIDENCE_ARTIFACT_UNVERIFIED",
            {item.code for item in portable_result.errors},
        )
        self.assertEqual(local_result.derived_state, "accepted")
        self.assertTrue(local_result.fully_verified)
        self.assertEqual(local_result.errors, ())

    def test_malformed_local_artifact_expectations_fail_closed(self) -> None:
        case = accepted_deletion_case()
        contexts = (
            GovernanceEvaluationContext(
                (
                    ArtifactExpectation("out/result.txt", "absent"),
                    ArtifactExpectation("out/result.txt", "present"),
                )
            ),
            GovernanceEvaluationContext(
                (ArtifactExpectation("out/missing.txt", "absent"),)
            ),
            GovernanceEvaluationContext(
                (ArtifactExpectation("out/result.txt", "deleted"),)
            ),
        )

        for context in contexts:
            with self.subTest(context=context):
                result = evaluate_governance_case(
                    replace(case, claimed_state="blocked"),
                    context=context,
                )

                self.assertEqual(result.derived_state, "blocked")
                self.assertIn(
                    "PCAW_EVIDENCE_EXPECTATION_INVALID",
                    {item.code for item in result.errors},
                )

    def test_zero_numeric_quorum_still_binds_explicit_human_acceptance(self) -> None:
        result = evaluate_governance_case(accepted_zero_quorum_case())
        properties = {item.name: item for item in result.properties}

        self.assertEqual(result.derived_state, "accepted")
        self.assertTrue(result.fully_verified)
        self.assertEqual(properties["human_quorum"].status, "not-required")
        self.assertEqual(properties["acceptance_currency"].status, "verified")

    def test_zero_numeric_quorum_rejects_stale_explicit_decision(self) -> None:
        case = accepted_zero_quorum_case()
        stale = replace(case.human_decisions[0], review_id="REVIEW-STALE")

        result = evaluate_governance_case(replace(case, human_decisions=(stale,)))

        self.assertEqual(result.derived_state, "blocked")
        self.assertIn(
            "PCAW_ACCEPTANCE_DECISION_STALE",
            {item.code for item in result.errors},
        )

    def test_zero_numeric_quorum_later_rejection_revokes_acceptance(self) -> None:
        case = accepted_zero_quorum_case()
        rejection = replace(
            case.human_decisions[0],
            id="DECISION-2",
            decision="changes-requested",
            status="changes-requested",
            timestamp="2030-01-01T00:07:00Z",
        )

        result = evaluate_governance_case(
            replace(case, human_decisions=(*case.human_decisions, rejection))
        )

        self.assertEqual(result.derived_state, "blocked")
        self.assertIn(
            "PCAW_ACCEPTANCE_DECISION_STALE",
            {item.code for item in result.errors},
        )


if __name__ == "__main__":
    unittest.main()
