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
    EvidenceSnapshot,
    GovernanceCase,
    HumanAuthority,
    HumanDecisionSnapshot,
    IntegrityObservation,
    IntegrityObservations,
    LegacyProofBinding,
    ReceiptSnapshot,
    ReviewSnapshot,
    SourceBoundary,
    WorkContract,
)
from palari_company_os.governance_kernel import PROPERTY_NAMES, evaluate_governance_case


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
    def test_current_acceptance_verifies_all_eight_properties(self) -> None:
        result = evaluate_governance_case(accepted_case())

        self.assertEqual(result.derived_state, "accepted")
        self.assertTrue(result.fully_verified)
        self.assertEqual(tuple(item.name for item in result.properties), PROPERTY_NAMES)
        self.assertTrue(
            all(item.status in {"verified", "not-required"} for item in result.properties)
        )
        self.assertEqual(result.errors, ())

    def test_terminal_current_acceptance_derives_completed(self) -> None:
        result = evaluate_governance_case(accepted_case(claimed_state="completed", terminal=True))

        self.assertEqual(result.derived_state, "completed")
        self.assertTrue(result.fully_verified)

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

    def test_builder_reviewer_collision_requires_new_review(self) -> None:
        case = accepted_case(claimed_state="review-required")
        case = replace(case, review=replace(case.review, reviewer="PALARI-BUILDER"))

        result = evaluate_governance_case(case)

        self.assertEqual(result.derived_state, "review-required")
        self.assertIn("PCAW_REVIEWER_NOT_INDEPENDENT", {item.code for item in result.errors})

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


if __name__ == "__main__":
    unittest.main()
