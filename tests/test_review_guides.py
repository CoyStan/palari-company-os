from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cli_dispatch import run_command
from palari_company_os.cli_parser import build_parser
from palari_company_os.evidence_manifest import (
    OUTPUT_BINDING_VERSION,
    evidence_manifest_hash,
    stamp_receipt_record,
)
from palari_company_os.review_guides import (
    _concrete_review_id,
    build_review_guide,
)
from palari_company_os.workspace import Workspace


def _workspace(
    *,
    include_evidence: bool = True,
    include_reviewer: bool = True,
    required_approval_count: int = 1,
    risk: str = "R2",
    intensity: str = "standard",
) -> Workspace:
    receipt = stamp_receipt_record(
        {
            "id": "RECEIPT-1",
            "work_item_id": "WORK-1",
            "attempt_id": "ATTEMPT-1",
            "actor": "PALARI-BUILDER",
            "sources_used": ["SOURCE-1"],
            "actions_taken": ["created the bounded output"],
            "outputs_created": ["notes/output.md"],
            "external_writes": [],
            "not_done": ["No external writes."],
            "undo_refs": ["restore notes/output.md"],
            "timestamp": "2026-07-18T10:02:00Z",
        },
        [],
    )
    evidence = {
        "id": "EVIDENCE-1",
        "work_item_id": "WORK-1",
        "attempt_id": "ATTEMPT-1",
        "head_sha": "head-1",
        "status": "passed",
        "commands": ["python3 -m unittest tests.test_governance_kernel"],
        "artifacts": ["notes/output.md"],
        "artifact_hashes": [
            {
                "path": "notes/output.md",
                "sha256": "sha256:" + ("a" * 64),
                "status": "present",
            }
        ],
        "output_binding_version": OUTPUT_BINDING_VERSION,
        "receipt_hash": receipt["receipt_hash"],
        "summary": "Current exact focused evidence passed.",
        "freshness": "exact-head",
        "timestamp": "2026-07-18T10:03:00Z",
    }
    evidence["manifest_hash"] = evidence_manifest_hash(evidence)

    raw = {
        "schema_version": 2,
        "name": "Review Guide Contract",
        "goals": [
            {
                "id": "GOAL-1",
                "title": "Keep bounded work independently reviewable",
                "status": "active",
            }
        ],
        "humans": [
            {
                "id": "HUMAN-REVIEWER",
                "name": "Independent Human Reviewer",
                "role": "Product owner",
                "approval_capabilities": ["technical-review", "product"],
            }
        ],
        "palaris": [
            {
                "id": "PALARI-BUILDER",
                "name": "Builder",
                "role": "Bounded worker",
                "owner_human": "HUMAN-REVIEWER",
                "linked_goals": ["GOAL-1"],
            },
            {
                "id": "PALARI-REVIEWER",
                "name": "Reviewer",
                "role": "Independent reviewer",
                "owner_human": "HUMAN-REVIEWER",
                "linked_goals": ["GOAL-1"],
            },
        ],
        "sources": [
            {
                "id": "SOURCE-1",
                "label": "Selected local note",
                "kind": "note",
                "provider": "local_note",
                "uri": "notes/source.md",
                "access_mode": "read",
                "selected": True,
                "owner_human": "HUMAN-REVIEWER",
                "allowed_palaris": ["PALARI-BUILDER", "PALARI-REVIEWER"],
                "data_class": "internal",
                "authority": "company_owned",
                "steward_human": "HUMAN-REVIEWER",
                "freshness_sla": "weekly",
                "redaction_required": False,
            }
        ],
        "workbenches": [
            {
                "id": "WORKBENCH-1",
                "label": "Local Product Work",
                "goal_ids": ["GOAL-1"],
                "palari_ids": ["PALARI-BUILDER", "PALARI-REVIEWER"],
                "human_ids": ["HUMAN-REVIEWER"],
                "source_ids": ["SOURCE-1"],
                "output_target_ids": ["notes/output.md"],
                "status": "active",
            }
        ],
        "work_items": [
            {
                "id": "WORK-1",
                "title": "Produce one bounded output",
                "goal": "GOAL-1",
                "palari": "PALARI-BUILDER",
                "workbench_id": "WORKBENCH-1",
                "risk": risk,
                "intensity": intensity,
                "status": "active",
                "scope": "Modify one declared local output.",
                "allowed_resources": ["notes/output.md"],
                "allowed_sources": ["SOURCE-1"],
                "allowed_actions": ["local_write"],
                "output_targets": ["notes/output.md"],
                "path_intents": [{"path": "notes/output.md", "intent": "modify"}],
                "forbidden_actions": ["external_write"],
                "acceptance_target": "The local output is inspectable.",
                "current_attempt": "ATTEMPT-1",
                "required_approval_count": required_approval_count,
                "required_approval_capability": "product",
            }
        ],
        "attempts": [
            {
                "id": "ATTEMPT-1",
                "work_item_id": "WORK-1",
                "actor": "PALARI-BUILDER",
                "status": "complete",
                "head_sha": "head-1",
                "commits": ["head-1"],
                "changed_files": ["notes/output.md"],
                "output_targets": ["notes/output.md"],
                "cleanliness": "clean",
                "started_at": "2026-07-18T10:00:00Z",
                "updated_at": "2026-07-18T10:01:00Z",
            }
        ],
        "evidence_runs": [evidence] if include_evidence else [],
        "review_verdicts": [],
        "human_decisions": [],
        "acceptance_records": [],
        "receipts": [receipt],
        "decisions": [],
        "outcomes": [],
    }
    if not include_reviewer:
        raw["palaris"] = [
            palari
            for palari in raw["palaris"]
            if palari["id"] != "PALARI-REVIEWER"
        ]
        raw["sources"][0]["allowed_palaris"] = ["PALARI-BUILDER"]
        raw["workbenches"][0]["palari_ids"] = ["PALARI-BUILDER"]
    return Workspace.from_raw(raw, Path("/tmp/palari-review-guide-contract"))


class ReviewGuideTests(unittest.TestCase):
    def test_receipt_without_exact_evidence_cannot_open_review(self) -> None:
        payload = build_review_guide(_workspace(include_evidence=False), "WORK-1")

        self.assertEqual(payload["status"], "missing-evidence")
        self.assertEqual(payload["evidence"], {"present": False})
        self.assertEqual(payload["receipt"]["id"], "RECEIPT-1")

    def test_current_exact_proof_yields_read_only_review_guide(self) -> None:
        payload = build_review_guide(_workspace(), "WORK-1")

        self.assertEqual(payload["schema_version"], "palari.review_guide.v2")
        self.assertEqual(payload["guide_id"], "REVIEW-GUIDE-WORK-1-V2")
        self.assertEqual(payload["status"], "review-needed")
        self.assertFalse(payload["would_mutate"])
        self.assertEqual(payload["attempt"]["id"], "ATTEMPT-1")
        self.assertEqual(payload["receipt"]["id"], "RECEIPT-1")
        self.assertEqual(payload["evidence"]["id"], "EVIDENCE-1")
        self.assertEqual(payload["evidence"]["head_sha"], "head-1")
        self.assertIn("--reviewed-head head-1", payload["review_record_command_template"])
        self.assertIn(
            "--binding-digest BINDING-DIGEST",
            payload["review_record_command_template"],
        )
        self.assertFalse(payload["review_record_command_template_executable"])
        self.assertIn("Review guide v2", payload["omitted_context"][0]["reason"])
        for action in payload["review_record_commands"]:
            self.assertIn(
                f"--binding-digest {action['review_binding_digest']}",
                action["command"],
            )

    def test_commands_retain_a_nondefault_explicit_workspace_file(self) -> None:
        data_path = Path("/tmp/palari-review-guide-contract/custom-state.json")
        workspace = _workspace()
        object.__setattr__(workspace, "data_path", data_path)
        payload = build_review_guide(workspace, "WORK-1")

        commands = [
            *payload["next_commands"],
            *(
                action["command"]
                for action in payload["review_record_commands"]
            ),
        ]
        self.assertTrue(commands)
        self.assertTrue(
            all(f"palari --workspace {data_path}" in command for command in commands)
        )

    def test_attempt_builder_is_not_an_independent_reviewer(self) -> None:
        payload = build_review_guide(_workspace(), "WORK-1")
        candidates = {candidate["id"] for candidate in payload["reviewer_candidates"]}

        self.assertNotIn("PALARI-BUILDER", candidates)
        self.assertIn("PALARI-REVIEWER", candidates)

    def test_reviewer_recommendation_preserves_a_distinct_human_approver(self) -> None:
        payload = build_review_guide(_workspace(), "WORK-1")
        candidates = {
            candidate["id"]: candidate
            for candidate in payload["reviewer_candidates"]
        }
        rejected = {
            candidate["id"]: candidate
            for candidate in payload["rejected_reviewer_candidates"]
        }

        self.assertIn("PALARI-REVIEWER", candidates)
        self.assertIn("1 distinct qualified human approver", candidates["PALARI-REVIEWER"]["reason"])
        self.assertEqual(rejected["HUMAN-REVIEWER"]["code"], "REVIEWER_EXHAUSTS_APPROVERS")
        self.assertIn("0/1", rejected["HUMAN-REVIEWER"]["reason"])
        self.assertIn("final approval", rejected["HUMAN-REVIEWER"]["smallest_correction"])

    def test_review_required_zero_quorum_reserves_one_final_human(self) -> None:
        payload = build_review_guide(
            _workspace(required_approval_count=0),
            "WORK-1",
        )
        plan = payload["authority_plan"]
        candidates = {
            candidate["id"]: candidate
            for candidate in payload["reviewer_candidates"]
        }
        rejected = {
            candidate["id"]: candidate
            for candidate in payload["rejected_reviewer_candidates"]
        }

        self.assertEqual(plan["required_approval_count"], 0)
        self.assertEqual(plan["effective_final_approval_count"], 1)
        self.assertTrue(plan["requires_review"])
        self.assertTrue(plan["requires_human_approval"])
        self.assertIn("PALARI-REVIEWER", candidates)
        self.assertEqual(
            rejected["HUMAN-REVIEWER"]["code"],
            "REVIEWER_EXHAUSTS_APPROVERS",
        )

    def test_concrete_review_ids_change_with_verdict_and_exact_binding(self) -> None:
        baseline = _concrete_review_id(
            "WORK-1",
            "PALARI-REVIEWER",
            "accept-ready",
            "head-1",
            "sha256:" + ("a" * 64),
        )
        changed_verdict = _concrete_review_id(
            "WORK-1",
            "PALARI-REVIEWER",
            "blocked",
            "head-1",
            "sha256:" + ("a" * 64),
        )
        changed_binding = _concrete_review_id(
            "WORK-1",
            "PALARI-REVIEWER",
            "accept-ready",
            "head-1",
            "sha256:" + ("b" * 64),
        )

        self.assertEqual(len({baseline, changed_verdict, changed_binding}), 3)

    def test_true_low_risk_light_zero_quorum_keeps_automatic_authority(self) -> None:
        payload = build_review_guide(
            _workspace(
                required_approval_count=0,
                risk="R1",
                intensity="light",
            ),
            "WORK-1",
        )
        plan = payload["authority_plan"]

        self.assertFalse(plan["requires_review"])
        self.assertFalse(plan["requires_human_approval"])
        self.assertEqual(plan["effective_final_approval_count"], 0)

    def test_impossible_reviewer_approver_plan_is_blocked_with_a_correction(self) -> None:
        payload = build_review_guide(
            _workspace(include_reviewer=False),
            "WORK-1",
        )

        self.assertEqual(payload["status"], "authority-plan-blocked")
        self.assertFalse(payload["authority_plan"]["viable"])
        self.assertEqual(payload["reviewer_candidates"], [])
        self.assertEqual(payload["review_record_commands"], [])
        self.assertEqual(payload["review_record_command_template"], "")
        rejected = {
            candidate["id"]: candidate
            for candidate in payload["rejected_reviewer_candidates"]
        }
        self.assertEqual(rejected["HUMAN-REVIEWER"]["code"], "REVIEWER_EXHAUSTS_APPROVERS")
        self.assertIn("Palari reviewer", payload["authority_plan"]["smallest_correction"])

    def test_parser_and_dispatch_translate_review_guide_directly(self) -> None:
        workspace = _workspace()
        args = build_parser().parse_args(
            ["--workspace", "/unused", "review", "guide", "WORK-1", "--json"]
        )

        with patch.object(Workspace, "load", return_value=workspace) as load:
            result = run_command(args)

        load.assert_called_once_with("/unused")
        self.assertEqual(result.kind, "review-guide")
        self.assertTrue(result.as_json)
        self.assertEqual(result.payload["status"], "review-needed")


if __name__ == "__main__":
    unittest.main()
