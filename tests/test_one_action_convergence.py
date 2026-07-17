from __future__ import annotations

import unittest
import sys
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.governance_kernel import evaluate_governance_case

from tests.test_governance_kernel import accepted_zero_quorum_case


class OneActionAuthorityConvergenceTests(unittest.TestCase):
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
