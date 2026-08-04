from __future__ import annotations

import unittest
import sys
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.governance_kernel import PROPERTY_NAMES, evaluate_governance_case
from tests.test_governance_kernel import accepted_case


class GovernanceExplorerTests(unittest.TestCase):
    def test_reachable_abstract_states_reach_fixed_point_and_preserve_invariants(self) -> None:
        """Explore the real evaluator over a finite lifecycle abstraction."""

        frontier = {(0, False)}
        reachable: set[tuple[int, bool]] = set()
        evaluations = {}

        while frontier:
            node = min(frontier)
            frontier.remove(node)
            if node in reachable:
                continue
            reachable.add(node)
            case = _case_for_node(node)
            first = evaluate_governance_case(case)
            second = evaluate_governance_case(case)
            self.assertEqual(first.to_dict(), second.to_dict())
            evaluations[node] = first
            frontier.update(_successors(node) - reachable)

        self.assertEqual(
            reachable,
            {
                (0, False),
                (1, False),
                (2, False),
                (3, False),
                (4, False),
                (5, False),
                (2, True),
                (3, True),
                (4, True),
                (5, True),
            },
        )
        self.assertFalse(set().union(*(_successors(node) for node in reachable)) - reachable)

        for node, result in evaluations.items():
            self.assertEqual(tuple(item.name for item in result.properties), PROPERTY_NAMES)
            if result.derived_state in {"accepted", "completed"}:
                by_name = {item.name: item.status for item in result.properties}
                for required in (
                    "scope_compliance",
                    "subject_integrity",
                    "evidence_freshness",
                    "receipt_binding",
                    "independent_review",
                    "human_quorum",
                    "acceptance_currency",
                ):
                    self.assertEqual(by_name[required], "verified", (node, required))
                self.assertTrue(result.fully_verified)
            if node[1] and node[0] >= 4:
                self.assertNotIn(result.derived_state, {"accepted", "completed"})
                self.assertFalse(result.fully_verified)

    def test_every_substantive_proof_mutation_invalidates_acceptance(self) -> None:
        base = accepted_case()
        mutations = (
            replace(base, contract=replace(base.contract, scope="changed")),
            replace(base, attempt=replace(base.attempt, result="changed")),
            replace(base, receipt=replace(base.receipt, actions_taken=("changed",))),
            replace(base, evidence=replace(base.evidence, summary="changed")),
            replace(base, review=replace(base.review, residual_risks=("changed",))),
        )

        for case in mutations:
            with self.subTest(case=case):
                result = evaluate_governance_case(replace(case, claimed_state="review-required"))
                self.assertNotIn(result.derived_state, {"accepted", "completed"})
                self.assertFalse(result.fully_verified)


def _case_for_node(node: tuple[int, bool]):
    stage, mutated = node
    terminal = stage == 5
    claimed = {
        0: "blocked",
        1: "review-required",
        2: "human-decision-required",
        3: "accept-ready",
        4: "accepted",
        5: "completed",
    }[stage]
    case = accepted_case(claimed_state=claimed, terminal=terminal)
    if stage == 0:
        case = replace(
            case,
            attempt=None,
            receipt=None,
            evidence=None,
            review=None,
            human_decisions=(),
            acceptance_records=(),
        )
    elif stage == 1:
        case = replace(case, review=None, human_decisions=(), acceptance_records=())
    elif stage == 2:
        case = replace(case, human_decisions=(), acceptance_records=())
    elif stage == 3:
        case = replace(case, acceptance_records=())
    if mutated:
        case = replace(
            case,
            claimed_state="review-required",
            contract=replace(case.contract, scope="mutated after review"),
        )
    return case


def _successors(node: tuple[int, bool]) -> set[tuple[int, bool]]:
    stage, mutated = node
    result: set[tuple[int, bool]] = set()
    if not mutated and stage < 5:
        result.add((stage + 1, False))
    if not mutated and stage >= 2:
        result.add((stage, True))
    return result


if __name__ == "__main__":
    unittest.main()
