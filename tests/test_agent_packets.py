from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_checks import build_agent_check
from palari_company_os.agent_doctor import build_agent_doctor
from palari_company_os.agent_finish import build_agent_finish
from palari_company_os.agent_handoff import build_agent_handoff
from palari_company_os.agent_loop import build_agent_loop
from palari_company_os.agent_next import build_agent_next, build_agent_next_all
from palari_company_os.agent_packets import _context_hash, build_agent_brief
from palari_company_os.workspace import Workspace


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"
DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


def _remove_work_0001_exact_proof(data: dict[str, object]) -> None:
    data["receipts"] = [
        item for item in data["receipts"] if item.get("work_item_id") != "WORK-0001"
    ]
    data["review_verdicts"] = [
        item for item in data["review_verdicts"] if item.get("work_item_id") != "WORK-0001"
    ]
    evidence = next(
        item for item in data["evidence_runs"] if item.get("work_item_id") == "WORK-0001"
    )
    for field in ("artifact_hashes", "manifest_hash", "receipt_hash"):
        evidence.pop(field, None)


class AgentPacketTests(unittest.TestCase):
    def test_agent_next_lists_safe_candidates_first_for_palari(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_next(workspace, "PALARI-SOFIA")

        self.assertEqual(result["schema_version"], "palari.agent_next.v1")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["agent"]["id"], "PALARI-SOFIA")
        self.assertGreaterEqual(result["ready_count"], 1)
        self.assertEqual(result["candidates"][0]["work_item_id"], "WORK-0003")
        self.assertEqual(result["candidates"][0]["can_start"], True)
        self.assertEqual(result["candidates"][0]["start_blockers"], [])
        self.assertEqual(
            result["candidates"][0]["next_command"],
            "palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            result["candidates"][0]["loop_command"],
            "palari agent loop WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            result["candidates"][0]["doctor_command"],
            "palari agent doctor WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(result["candidates"][0]["next_step_type"], "check-active-proof")
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json",
                "palari agent finish WORK-0003 --as PALARI-SOFIA --json",
            ],
        )

    def test_agent_next_includes_blocked_visible_work_without_marking_it_safe(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_next(workspace, "PALARI-SOFIA", limit=20)
        by_id = {item["work_item_id"]: item for item in result["candidates"]}

        self.assertIn("WORK-0001", by_id)
        self.assertEqual(by_id["WORK-0001"]["can_start"], False)
        self.assertIn("HUMAN_DECISION_REQUIRED", by_id["WORK-0001"]["blocker_codes"])
        self.assertEqual(
            by_id["WORK-0001"]["handoff_guidance"][0]["code"],
            "HUMAN_APPROVAL_HANDOFF",
        )
        self.assertEqual(
            by_id["WORK-0001"]["next_command"],
            "palari agent handoff WORK-0001 --as PALARI-SOFIA --json",
        )
        self.assertIn("PACKET_BLOCKED", by_id["WORK-0001"]["start_blocker_codes"])
        self.assertIn("ATTENTION_NOT_STARTABLE", by_id["WORK-0001"]["start_blocker_codes"])
        self.assertIn("WORK-0007", by_id)
        self.assertEqual(by_id["WORK-0007"]["can_start"], False)
        self.assertIn("RECEIPT_READY_REVIEW", by_id["WORK-0007"]["blocker_codes"])
        self.assertEqual(by_id["WORK-0007"]["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertIn(
            "ready-to-edit review record commands",
            by_id["WORK-0007"]["handoff_guidance"][0]["message"],
        )
        self.assertIn("ATTENTION_NOT_STARTABLE", by_id["WORK-0007"]["start_blocker_codes"])
        self.assertIn("WORK-0004", by_id)
        self.assertFalse(by_id["WORK-0004"]["can_start"])
        self.assertIn("HUMAN_DECISION_REQUIRED", by_id["WORK-0004"]["blocker_codes"])

    def test_agent_next_does_not_restart_work_waiting_for_review(self) -> None:
        def add_evidence_without_review(data: dict[str, object]) -> None:
            work = data["work_items"][2]
            attempt = next(
                item for item in data["attempts"] if item["id"] == work["current_attempt"]
            )
            data["evidence_runs"].append(
                {
                    "id": "EVIDENCE-WAITING-REVIEW",
                    "work_item_id": work["id"],
                    "attempt_id": attempt["id"],
                    "head_sha": attempt["commits"][-1],
                    "status": "passed",
                    "summary": "Evidence is present, but no review exists yet.",
                    "timestamp": "2026-06-22T01:00:00Z",
                }
            )

        workspace = self.modified_workspace(add_evidence_without_review)

        result = build_agent_next(workspace, "PALARI-SOFIA", limit=20)
        candidate = {
            item["work_item_id"]: item for item in result["candidates"]
        }["WORK-0003"]

        self.assertEqual(candidate["attention"], "needs-review")
        self.assertEqual(candidate["packet_status"], "blocked")
        self.assertEqual(candidate["can_start"], False)
        self.assertEqual(candidate["next_step_type"], "review-handoff")
        self.assertIn("REVIEW_REQUIRED", candidate["blocker_codes"])
        self.assertIn("PACKET_BLOCKED", candidate["start_blocker_codes"])
        self.assertIn("ATTENTION_NOT_STARTABLE", candidate["start_blocker_codes"])
        self.assertEqual(
            candidate["next_command"],
            "palari review guide WORK-0003 --json",
        )
        self.assertEqual(
            candidate["next_commands"][0],
            "palari review guide WORK-0003 --json",
        )
        self.assertEqual(candidate["handoff_guidance"], [])
        self.assertEqual(
            candidate["loop_command"],
            "palari agent loop WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            candidate["doctor_command"],
            "palari agent doctor WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertIn(candidate["doctor_command"], candidate["next_commands"])
        self.assertIn(candidate["loop_command"], candidate["next_commands"])

    def test_agent_next_does_not_offer_start_command_when_queue_is_not_ai_safe(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_next(workspace, "PALARI-ARCHITECT", limit=20)
        candidate = {
            item["work_item_id"]: item for item in result["candidates"]
        }["WORK-REPO-0004"]

        self.assertEqual(candidate["attention"], "ready-for-ai-work")
        self.assertEqual(candidate["can_start"], False)
        self.assertEqual(candidate["next_step_type"], "inspect")
        self.assertIn("QUEUE_NOT_AI_SAFE", candidate["start_blocker_codes"])
        self.assertEqual(candidate["next_command"], "palari detail WORK-REPO-0004 --json")

    def test_agent_next_review_mode_marks_reviewable_work_ready(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_next(workspace, "PALARI-STEWARD", mode="review", limit=20)
        candidate = {
            item["work_item_id"]: item for item in result["candidates"]
        }["WORK-REPO-0003"]

        self.assertEqual(result["schema_version"], "palari.agent_next.v1")
        self.assertEqual(result["status"], "ready")
        self.assertGreaterEqual(result["ready_count"], 1)
        self.assertEqual(candidate["attention"], "needs-review")
        self.assertEqual(candidate["packet_status"], "ready")
        self.assertTrue(candidate["can_start"])
        self.assertEqual(candidate["start_blockers"], [])
        self.assertEqual(
            candidate["next_command"],
            "palari agent brief WORK-REPO-0003 --as PALARI-STEWARD --mode review --json",
        )
        self.assertEqual(
            candidate["next_commands"][:4],
            [
                "palari agent brief WORK-REPO-0003 --as PALARI-STEWARD --mode review --json",
                "palari review guide WORK-REPO-0003 --json",
                "palari agent check WORK-REPO-0003 --as PALARI-STEWARD --mode review --json",
                "palari agent doctor WORK-REPO-0003 --as PALARI-STEWARD --mode review --json",
            ],
        )
        self.assertEqual(
            candidate["next_commands"][4],
            "palari agent loop WORK-REPO-0003 --as PALARI-STEWARD --mode review --json",
        )

    def test_agent_next_review_mode_blocks_non_reviewable_work(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_next(workspace, "PALARI-ARCHITECT", mode="review", limit=20)
        candidate = {
            item["work_item_id"]: item for item in result["candidates"]
        }["WORK-REPO-0004"]

        self.assertFalse(candidate["can_start"])
        self.assertEqual(candidate["packet_status"], "blocked")
        self.assertIn("REVIEW_NOT_READY", candidate["blocker_codes"])
        self.assertIn("ATTENTION_NOT_REVIEWABLE", candidate["start_blocker_codes"])

    def test_agent_next_all_rolls_up_all_palaris(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_next_all(workspace)
        agent_ids = {agent["agent"]["id"] for agent in result["agents"]}

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(agent_ids, {"PALARI-STEWARD", "PALARI-ARCHITECT"})
        self.assertEqual(result["top_candidate"]["agent"]["id"], "PALARI-STEWARD")
        self.assertEqual(result["top_candidate"]["candidate"]["work_item_id"], "WORK-REPO-0023")
        self.assertEqual(result["top_candidate"]["candidate"]["can_start"], True)
        self.assertEqual(
            result["top_candidate"]["candidate"]["next_step_type"],
            "check-active-proof",
        )
        self.assertEqual(result["top_candidate"]["candidate"]["handoff_guidance"], [])
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari agent check WORK-REPO-0023 --as PALARI-STEWARD --mode execute --json",
        )
        self.assertEqual(
            result["next_allowed_commands"][1],
            "palari agent finish WORK-REPO-0023 --as PALARI-STEWARD --json",
        )

    def test_agent_next_all_exposes_top_ready_candidate(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_next_all(workspace)

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["top_candidate"]["agent"]["id"], "PALARI-SOFIA")
        self.assertEqual(result["top_candidate"]["candidate"]["work_item_id"], "WORK-0003")
        self.assertEqual(result["top_candidate"]["candidate"]["can_start"], True)
        self.assertEqual(result["top_candidate"]["candidate"]["next_step_type"], "check-active-proof")
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )

    def test_agent_next_missing_palari_is_blocked(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_next(workspace, "PALARI-MISSING")

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["ready_count"], 0)
        self.assertEqual(result["blockers"][0]["code"], "MISSING_PALARI")
        self.assertEqual(result["candidates"], [])

    def test_cli_agent_next_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "next", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_next.v1")
        self.assertEqual(result["status"], "ready")
        self.assertIn("candidates", result)
        self.assertEqual(result["candidates"][0]["can_start"], True)
        self.assertEqual(
            result["candidates"][0]["loop_command"],
            "palari agent loop WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            result["candidates"][0]["doctor_command"],
            "palari agent doctor WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )

    def test_cli_agent_next_text_prints_handoff_guidance(self) -> None:
        result = self.run_cli(
            "--workspace",
            str(DOGFOOD),
            "agent",
            "next",
            "--as",
            "PALARI-STEWARD",
        )

        self.assertIn("handoff: REVIEW_HANDOFF", result.stdout)
        self.assertIn("ready-to-edit review record commands", result.stdout)
        self.assertIn("doctor: palari agent doctor WORK-REPO-0003", result.stdout)
        self.assertIn("loop: palari agent loop WORK-REPO-0003", result.stdout)

    def test_cli_agent_next_text_prints_mode(self) -> None:
        result = self.run_cli(
            "agent",
            "next",
            "--as",
            "PALARI-SOFIA",
            "--mode",
            "review",
        )

        self.assertIn("Mode: review", result.stdout)
        self.assertIn("doctor: palari agent doctor", result.stdout)
        self.assertIn("loop: palari agent loop", result.stdout)

    def test_cli_agent_next_all_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli(
                "--workspace",
                str(DOGFOOD),
                "agent",
                "next",
                "--all",
                "--json",
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(len(result["agents"]), 2)

    def test_cli_agent_next_defaults_to_all_rollup(self) -> None:
        result = json.loads(
            self.run_cli(
                "--workspace",
                str(DOGFOOD),
                "agent",
                "next",
                "--json",
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(len(result["agents"]), 2)

    def test_cli_agent_next_all_text_prints_mode(self) -> None:
        result = self.run_cli(
            "--workspace",
            str(DOGFOOD),
            "agent",
            "next",
            "--all",
            "--mode",
            "review",
        )

        self.assertIn("Mode: review", result.stdout)
        self.assertIn("doctor: palari agent doctor", result.stdout)
        self.assertIn("loop: palari agent loop", result.stdout)

    def test_agent_finish_missing_proof_does_not_allow_completion_claim(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_finish(workspace, "WORK-0003", "PALARI-SOFIA")
        missing_codes = {item["code"] for item in result["missing_requirements"]}

        self.assertEqual(result["schema_version"], "palari.agent_finish.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["can_finish"], False)
        self.assertEqual(result["handoff_ready"], False)
        self.assertEqual(result["would_mutate"], False)
        self.assertIn("RECEIPT_PRESENT", missing_codes)
        self.assertIn("EVIDENCE_PRESENT", missing_codes)
        commands = "\n".join(result["next_allowed_commands"])
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json",
                "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
                "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
            ],
        )
        self.assertIn("CLAIM_OWNED", missing_codes)
        self.assertIn(
            "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
            "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
            commands,
        )
        self.assertIn(
            "palari evidence record EVIDENCE-ID --work-item-id WORK-0003 "
            "--attempt-id ATTEMPT-0002 --head-sha def5678 --status passed",
            commands,
        )

    def test_agent_finish_low_risk_receipt_ready_hands_off_to_human(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_finish(workspace, "WORK-0007", "PALARI-SOFIA")

        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["can_finish"], False)
        self.assertEqual(result["handoff_ready"], True)
        self.assertEqual(result["missing_requirements"], [])
        self.assertIn(
            "RECEIPT_PRESENT",
            {item["code"] for item in result["completed_requirements"]},
        )
        self.assertIn(
            "RECEIPT_READY_REVIEW",
            {blocker["code"] for blocker in result["blockers"]},
        )
        self.assertEqual(result["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertIn("ready-to-edit review record commands", result["handoff_guidance"][0]["message"])
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari agent handoff WORK-0007 --as PALARI-SOFIA --json",
        )
        self.assertEqual(result["next_allowed_commands"][1], "palari review guide WORK-0007 --json")

    def test_agent_finish_dogfood_agent_loop_record_hands_off_to_review(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_finish(workspace, "WORK-REPO-0006", "PALARI-STEWARD")

        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["next_step_type"], "review-handoff")
        self.assertEqual(result["can_finish"], False)
        self.assertEqual(result["handoff_ready"], True)
        self.assertEqual(result["missing_requirements"], [])
        self.assertIn(
            "RECEIPT_PRESENT",
            {item["code"] for item in result["completed_requirements"]},
        )
        self.assertIn(
            "RECEIPT_READY_REVIEW",
            {blocker["code"] for blocker in result["blockers"]},
        )
        self.assertEqual(result["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertEqual(
            result["handoff_guidance"][0]["command"],
            "palari agent handoff WORK-REPO-0006 --as PALARI-STEWARD --json",
        )
        self.assertEqual(
            result["handoff_guidance"][0]["guide_command"],
            "palari review guide WORK-REPO-0006 --json",
        )
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari agent handoff WORK-REPO-0006 --as PALARI-STEWARD --json",
        )
        self.assertEqual(
            result["next_allowed_commands"][1],
            "palari review guide WORK-REPO-0006 --json",
        )

    def test_agent_finish_human_decision_required_remains_blocked(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_finish(workspace, "WORK-0001", "PALARI-SOFIA")

        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["can_finish"], False)
        missing = {item["code"]: item for item in result["missing_requirements"]}
        self.assertIn("HUMAN_DECISION_PRESENT", missing)
        self.assertNotIn("next_command", missing["HUMAN_DECISION_PRESENT"])
        self.assertTrue(result["handoff_ready"])
        self.assertEqual(result["handoff_guidance"][0]["code"], "HUMAN_APPROVAL_HANDOFF")
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari detail WORK-0001 --json",
        )
        self.assertNotIn("palari human-decision record", "\n".join(result["next_allowed_commands"]))

    def test_agent_finish_waiting_for_review_prioritizes_review_handoff(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_finish(workspace, "WORK-REPO-0003", "PALARI-STEWARD")
        missing = {item["code"]: item for item in result["missing_requirements"]}

        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["next_step_type"], "review-handoff")
        self.assertEqual(result["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent handoff WORK-REPO-0003 --as PALARI-STEWARD --json",
                "palari review guide WORK-REPO-0003 --json",
            ],
        )
        self.assertEqual(
            missing["REVIEW_PRESENT"]["next_command"],
            "palari review guide WORK-REPO-0003 --json",
        )
        self.assertNotIn("next_command", missing["HUMAN_DECISION_PRESENT"])
        self.assertNotIn("palari human-decision record", "\n".join(result["next_allowed_commands"]))

    def test_agent_finish_review_mode_guides_review_recommendation_not_completion(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_finish(
            workspace,
            "WORK-REPO-0003",
            "PALARI-STEWARD",
            mode="review",
        )

        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["mode"], "review")
        self.assertFalse(result["can_finish"])
        self.assertIn("CLAIM_OWNED", {item["code"] for item in result["missing_requirements"]})
        self.assertIn(
            "palari agent start WORK-REPO-0003 --as PALARI-STEWARD --mode review --json",
            result["next_allowed_commands"],
        )

    def test_cli_agent_finish_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "finish", "WORK-0003", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_finish.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["next_step_type"], "check-active-proof")
        self.assertEqual(result["can_finish"], False)
        self.assertEqual(result["would_mutate"], False)

    def test_cli_agent_finish_text_shows_completed_requirements(self) -> None:
        result = self.run_cli("agent", "finish", "WORK-0007", "--as", "PALARI-SOFIA")

        self.assertIn("Status: handoff-ready", result.stdout)
        self.assertIn("Step: review-handoff", result.stdout)
        self.assertIn("Completed requirements:", result.stdout)
        self.assertIn("RECEIPT_PRESENT", result.stdout)
        self.assertIn("Handoff guidance:", result.stdout)
        self.assertIn("ready-to-edit review record commands", result.stdout)
        self.assertIn("Guidance: Do not continue execution.", result.stdout)

    def test_agent_handoff_receipt_ready_compiles_review_context(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_handoff(workspace, "WORK-REPO-0006", "PALARI-STEWARD")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["handoff_types"], ["review"])
        self.assertEqual(result["handoff_available"], True)
        self.assertEqual(result["would_mutate"], False)
        self.assertEqual(result["finish"]["handoff_ready"], True)
        self.assertEqual(result["finish"]["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertIsNotNone(result["review_handoff"])
        self.assertIsNone(result["decision_handoff"])
        review = result["review_handoff"]
        self.assertEqual(review["status"], "receipt-ready")
        self.assertEqual(review["command"], "palari review guide WORK-REPO-0006 --json")
        self.assertIn("Hand off", result["finish"]["report_guidance"])
        self.assertIn(
            "palari review guide WORK-REPO-0006 --json",
            result["next_allowed_commands"],
        )
        self.assertNotIn(
            "palari review record REVIEW-ID",
            "\n".join(result["next_allowed_commands"]),
        )
        self.assertIn(
            "HUMAN-MAINTAINER",
            {candidate["id"] for candidate in review["reviewer_candidates"]},
        )
        human_commands = "\n".join(item["command"] for item in result["human_action_commands"])
        self.assertIn("--reviewer HUMAN-MAINTAINER", human_commands)
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(result["human_action_boundary"]["count"], len(result["human_action_commands"]))
        self.assertIn(
            "human_action_commands[].command",
            result["human_action_boundary"]["human_only_command_fields"],
        )

    def test_agent_handoff_waiting_for_review_compiles_review_context(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_handoff(workspace, "WORK-REPO-0003", "PALARI-STEWARD")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["handoff_types"], ["review"])
        self.assertEqual(result["handoff_available"], True)
        self.assertIsNotNone(result["review_handoff"])
        self.assertIsNone(result["decision_handoff"])
        self.assertEqual(result["review_handoff"]["status"], "review-needed")
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari review guide WORK-REPO-0003 --json",
        )
        self.assertNotIn(
            "palari human-decision record",
            "\n".join(result["next_allowed_commands"]),
        )
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(result["human_action_boundary"]["count"], len(result["human_action_commands"]))

    def test_agent_handoff_human_decision_compiles_decision_context(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_handoff(workspace, "WORK-REPO-0005", "PALARI-ARCHITECT")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["handoff_types"], ["decision"])
        self.assertEqual(result["handoff_available"], True)
        self.assertEqual(result["next_step_type"], "human-decision")
        self.assertIsNone(result["review_handoff"])
        decision = result["decision_handoff"]
        self.assertIsNotNone(decision)
        self.assertEqual(decision["decision"]["id"], "DECISION-REPO-0001")
        self.assertEqual(
            decision["command"],
            "palari decision guide DECISION-REPO-0001 --json",
        )
        self.assertIn(
            "palari decision guide DECISION-REPO-0001 --json",
            result["next_allowed_commands"],
        )
        self.assertIn(
            "keep disabled",
            {item["result"] for item in decision["decision_update_commands"]},
        )
        human_commands = "\n".join(item["command"] for item in result["human_action_commands"])
        self.assertIn("palari decision update DECISION-REPO-0001", human_commands)
        self.assertIn("'result=keep disabled'", human_commands)
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(result["human_action_boundary"]["count"], len(result["human_action_commands"]))

    def test_agent_handoff_suppresses_human_approval_until_proof_is_complete(self) -> None:
        workspace = self.modified_workspace(_remove_work_0001_exact_proof)

        result = build_agent_handoff(workspace, "WORK-0001", "PALARI-SOFIA")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["handoff_types"], [])
        self.assertEqual(result["handoff_available"], False)
        self.assertIsNone(result["human_approval_handoff"])
        self.assertEqual(result["human_action_commands"], [])
        self.assertIn("palari receipt record RECEIPT-ID", result["next_allowed_commands"][0])

    def test_agent_handoff_human_approval_compiles_work_approval_context(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_handoff(workspace, "WORK-0001", "PALARI-SOFIA")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["handoff_types"], ["human-approval"])
        self.assertEqual(result["handoff_available"], True)
        self.assertEqual(result["next_step_type"], "human-decision")
        self.assertIsNone(result["review_handoff"])
        self.assertIsNone(result["decision_handoff"])
        approval = result["human_approval_handoff"]
        self.assertIsNotNone(approval)
        self.assertEqual(approval["work_item"]["id"], "WORK-0001")
        self.assertEqual(approval["approval_progress"], "0/1")
        self.assertEqual(approval["required_approval_capability"], "product")
        self.assertEqual(approval["approval_candidates"][0]["id"], "HUMAN-FOUNDER")
        self.assertNotIn("Receipt state is missing", " ".join(approval["approval_focus"]))
        self.assertEqual(
            result["next_allowed_commands"][:2],
            ["palari detail WORK-0001 --json", "palari queue --json"],
        )
        commands = "\n".join(item["command"] for item in result["human_action_commands"])
        self.assertIn("palari human-decision record", commands)
        self.assertNotIn("'palari human-decision record'", commands)
        self.assertIn("--decision accepted", commands)
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)

    def test_emitted_agent_safe_commands_for_human_approval_work_execute(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            workspace = Workspace.load(workspace_file)
            queue_payload = json.loads(
                self.run_cli_in_workspace(workspace_file, "queue", "--json").stdout
            )
            queue_item = {
                item["id"]: item for item in queue_payload["queue"]
            }["WORK-0001"]
            next_payload = build_agent_next(workspace, "PALARI-SOFIA", limit=20)
            candidate = {
                item["work_item_id"]: item for item in next_payload["candidates"]
            }["WORK-0001"]
            loop_payload = build_agent_loop(workspace, "WORK-0001", "PALARI-SOFIA")
            doctor_payload = build_agent_doctor(workspace, "WORK-0001", "PALARI-SOFIA")
            handoff_payload = build_agent_handoff(workspace, "WORK-0001", "PALARI-SOFIA")

            commands = [
                queue_item["agent_handoff_command"],
                queue_item["agent_loop_command"],
                *queue_item["next_commands"],
                candidate["next_command"],
                *candidate["next_commands"],
                *loop_payload["next_allowed_commands"],
                *doctor_payload["recommended_commands"],
                *handoff_payload["next_allowed_commands"],
            ]
            if loop_payload["commands"].get("handoff"):
                commands.append(loop_payload["commands"]["handoff"])
            self.assertEqual(
                candidate["handoff_guidance"][0]["code"], "HUMAN_APPROVAL_HANDOFF"
            )
            self.assertIn("handoff", loop_payload["commands"])
            self.assertTrue(handoff_payload["human_action_commands"])
            for command in sorted(set(commands)):
                with self.subTest(command=command):
                    self.run_cli_in_workspace(workspace_file, *shlex.split(command)[1:])

    def test_cli_agent_handoff_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli(
                "--workspace",
                str(DOGFOOD),
                "agent",
                "handoff",
                "WORK-REPO-0006",
                "--as",
                "PALARI-STEWARD",
                "--json",
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["handoff_types"], ["review"])
        self.assertEqual(result["review_handoff"]["status"], "receipt-ready")
        self.assertEqual(result["human_action_commands"][0]["type"], "review-record")
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)

    def test_cli_agent_handoff_text_shows_review_commands(self) -> None:
        result = self.run_cli(
            "--workspace",
            str(DOGFOOD),
            "agent",
            "handoff",
            "WORK-REPO-0006",
            "--as",
            "PALARI-STEWARD",
        )

        self.assertIn("Agent handoff:", result.stdout)
        self.assertIn("Review handoff:", result.stdout)
        self.assertIn("review focus:", result.stdout)
        self.assertIn("Compare the attempt result", result.stdout)
        self.assertIn("receipt:", result.stdout)
        self.assertIn("external writes: none", result.stdout)
        self.assertIn("No deployment performed", result.stdout)
        self.assertIn("ready-to-edit review record commands", result.stdout)
        self.assertIn("review record commands:", result.stdout)
        self.assertIn("Human action boundary: agent may quote", result.stdout)

    def test_ready_execute_packet_is_compact_and_actionable(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["schema_version"], "palari.agent_packet.v1")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "execute")
        self.assertEqual(packet["agent"]["id"], "PALARI-SOFIA")
        self.assertEqual(packet["work_item"]["id"], "WORK-0003")
        self.assertEqual(packet["workbench"]["id"], "WORKBENCH-BETA")
        self.assertEqual(packet["allowed_paths"]["read"], ["docs/product/company-os.md"])
        self.assertEqual(packet["allowed_paths"]["write"], ["docs/product/company-os.md"])
        self.assertEqual(packet["completion_contract"]["requires_receipt"], True)
        self.assertEqual(packet["completion_contract"]["requires_evidence"], True)
        self.assertEqual(packet["state"]["next_step_type"], "check-active-proof")
        self.assertEqual(packet["proof_state"]["attempt"]["head_sha"], "def5678")
        self.assertIn("palari scope WORK-0003 --json", packet["next_allowed_commands"])
        self.assertIn(
            "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
            "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
            packet["next_allowed_commands"],
        )
        self.assertIn("Stop if you need to read or write outside allowed_paths.", packet["stop_conditions"])
        self.assertEqual(packet["blockers"], [])
        self.assertTrue(packet["context_hash"].startswith("sha256:"))

    def test_review_mode_packet_is_ready_for_receipt_ready_work(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0007", "PALARI-SOFIA", "review")

        self.assertEqual(packet["schema_version"], "palari.agent_packet.v1")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "review")
        self.assertEqual(packet["allowed_paths"]["write"], [])
        self.assertEqual(packet["completion_contract"]["review_mode"], True)
        self.assertEqual(packet["review_context"]["status"], "receipt-ready")
        self.assertIn("review_focus", packet["review_context"])
        self.assertEqual(packet["human_action_boundary"]["agent_may_execute"], False)
        self.assertIn(
            "review_context.review_record_commands[].command",
            packet["human_action_boundary"]["human_only_command_fields"],
        )
        self.assertEqual(
            packet["next_allowed_commands"][0],
            "palari review guide WORK-0007 --json",
        )
        self.assertIn("Stop before editing work outputs", packet["stop_conditions"][0])
        self.assertEqual(packet["blockers"], [])

    def test_review_mode_packet_is_ready_for_needs_review_work(self) -> None:
        def add_evidence_without_review(data: dict[str, object]) -> None:
            work = data["work_items"][2]
            attempt = next(
                item for item in data["attempts"] if item["id"] == work["current_attempt"]
            )
            data["evidence_runs"].append(
                {
                    "id": "EVIDENCE-WAITING-REVIEW",
                    "work_item_id": work["id"],
                    "attempt_id": attempt["id"],
                    "head_sha": attempt["commits"][-1],
                    "status": "passed",
                    "summary": "Evidence is present, but no review exists yet.",
                    "timestamp": "2026-06-22T04:10:00Z",
                }
            )

        workspace = self.modified_workspace(add_evidence_without_review)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "review")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "review")
        self.assertEqual(packet["review_context"]["status"], "review-needed")
        self.assertEqual(packet["review_context"]["evidence"]["id"], "EVIDENCE-WAITING-REVIEW")
        self.assertEqual(packet["completion_contract"]["requires_evidence"], False)
        self.assertEqual(
            packet["human_action_boundary"]["agent_allowed_use"],
            "Quote or summarize human-only commands for a human supervisor.",
        )

    def test_review_mode_blocks_work_that_is_not_review_ready(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "review")

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("REVIEW_NOT_READY", {blocker["code"] for blocker in packet["blockers"]})
        self.assertEqual(
            packet["next_allowed_commands"],
            [
                "palari detail WORK-0003 --json",
                "palari queue --json",
                "palari validate --json",
            ],
        )

    def test_packet_context_hash_ignores_created_at(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")
        changed_timestamp = dict(packet)
        changed_timestamp["created_at"] = "2099-01-01T00:00:00Z"

        self.assertEqual(_context_hash(packet), _context_hash(changed_timestamp))

    def test_blocked_packet_names_dependency_and_receipt_review_blockers(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0007", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["status"], "blocked")
        codes = {blocker["code"] for blocker in packet["blockers"]}
        self.assertIn("DEPENDENCY_NOT_TERMINAL", codes)
        self.assertIn("RECEIPT_READY_REVIEW", codes)
        self.assertEqual(packet["dependencies"][0]["id"], "WORK-0003")
        self.assertEqual(packet["allowed_sources"][0]["id"], "SOURCE-0001")
        self.assertEqual(packet["allowed_sources"][0]["data_class"], "internal")
        self.assertEqual(packet["allowed_sources"][0]["authority"], "company_owned")
        self.assertEqual(packet["allowed_sources"][0]["steward_human"], "HUMAN-FOUNDER")
        self.assertEqual(packet["allowed_sources"][0]["freshness_sla"], "weekly")
        self.assertFalse(packet["allowed_sources"][0]["redaction_required"])
        self.assertEqual(packet["completion_contract"]["requires_evidence"], False)
        self.assertEqual(
            packet["next_allowed_commands"],
            [
                "palari detail WORK-0007 --json",
                "palari queue --json",
                "palari validate --json",
            ],
        )

    def test_invalid_work_or_palari_returns_blocked_packet(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        missing_work = build_agent_brief(workspace, "WORK-MISSING", "PALARI-SOFIA", "execute")
        missing_palari = build_agent_brief(workspace, "WORK-0003", "PALARI-MISSING", "execute")

        self.assertEqual(missing_work["status"], "blocked")
        self.assertEqual(missing_work["blockers"][0]["code"], "MISSING_WORK_ITEM")
        self.assertEqual(missing_palari["status"], "blocked")
        self.assertEqual(missing_palari["blockers"][0]["code"], "MISSING_PALARI")

    def test_wrong_palari_and_external_write_are_blocked(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        wrong_palari = build_agent_brief(workspace, "WORK-0003", "PALARI-ALFRED", "execute")

        self.assertEqual(wrong_palari["status"], "blocked")
        self.assertIn(
            "PALARI_NOT_ASSIGNED",
            {blocker["code"] for blocker in wrong_palari["blockers"]},
        )

        external_write = self.modified_workspace(
            lambda data: data["work_items"][2].update({"allowed_actions": ["external_write"]})
        )
        packet = build_agent_brief(external_write, "WORK-0003", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "EXTERNAL_WRITE_REQUIRES_APPROVAL",
            {blocker["code"] for blocker in packet["blockers"]},
        )

    def test_packet_does_not_dump_unrelated_workspace_records(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")
        encoded = json.dumps(packet, sort_keys=True)

        self.assertNotIn("WORK-0001", encoded)
        self.assertNotIn("Prepare beta launch checklist", encoded)
        self.assertIn("omitted_context", packet)
        self.assertEqual(packet["omitted_context"][0]["counts"]["work_items"], 7)

    def test_cli_agent_brief_is_read_only_and_start_persists_packet_and_claim(self) -> None:
        brief = json.loads(
            self.run_cli("agent", "brief", "WORK-0003", "--as", "PALARI-SOFIA", "--mode", "execute", "--json").stdout
        )

        self.assertEqual(brief["status"], "ready")
        self.assertNotIn("start", brief)

        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            start = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--mode",
                    "execute",
                    "--json",
                ).stdout
            )
            packet_path = workspace_file.parent / start["start"]["packet_path"]
            claim_path = workspace_file.parent / start["start"]["claim_path"]

            self.assertEqual(start["status"], "ready")
            self.assertEqual(brief["packet_id"], start["packet_id"])
            self.assertEqual(start["start"]["status"], "claimed")
            self.assertTrue(packet_path.exists())
            self.assertTrue(claim_path.exists())
            self.assertEqual(json.loads(packet_path.read_text())["packet_id"], start["packet_id"])
            claim = json.loads(claim_path.read_text())
            self.assertEqual(claim["claimed_by"], "PALARI-SOFIA")
            self.assertEqual(claim["git_baseline"]["schema_version"], "palari.git_baseline.v1")
            self.assertTrue(claim["git_baseline_hash"].startswith("sha256:"))

            claim["git_baseline"]["entries"].append(
                {"path": "hidden.txt", "status": "untracked", "fingerprint": {"exists": True}}
            )
            claim_path.write_text(json.dumps(claim), encoding="utf-8")
            check = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "check",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            claim_check = next(item for item in check["checks"] if item["code"] == "CLAIM_OWNED")
            self.assertEqual(claim_check["status"], "fail")
            self.assertIn("git_baseline_hash", claim_check["message"])

            release = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "release",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            self.assertTrue(release["released"])
            self.assertFalse(claim_path.exists())

    def test_cli_agent_start_reports_claim_update_lock_as_json(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            lock_dir = workspace_file.parent / ".palari" / "claims"
            lock_dir.mkdir(parents=True)
            lock_path = lock_dir / "WORK-0003.lock"
            lock_path.write_text("test lock\n", encoding="utf-8")

            result = self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
                "--json",
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertEqual(payload["ok"], False)
            self.assertEqual(payload["error"]["code"], "CLAIM_UPDATE_IN_PROGRESS")
            self.assertEqual(payload["error"]["work_item"], "WORK-0003")
            self.assertIn("retry shortly", payload["error"]["message"])
            self.assertTrue(lock_path.exists())

    def test_generic_work_update_is_blocked_during_active_claim(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
                "--json",
            )

            result = self.run_cli_in_workspace(
                workspace_file,
                "work",
                "update",
                "WORK-0003",
                "--list",
                "allowed_resources=docs,deploy",
                "--json",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("active execute claim", result.stderr)
            self.assertIn("cannot change its packet authority", result.stderr)

    def test_active_claim_cannot_restart_with_changed_packet_authority(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            first = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--mode",
                    "execute",
                    "--json",
                ).stdout
            )
            data = json.loads(workspace_file.read_text(encoding="utf-8"))
            work = next(item for item in data["work_items"] if item["id"] == "WORK-0003")
            work["allowed_resources"] = ["docs", "deploy"]
            workspace_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

            result = self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
                "--json",
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("packet authority differs", payload["error"]["message"])
            claim_path = workspace_file.parent / first["start"]["claim_path"]
            claim = json.loads(claim_path.read_text(encoding="utf-8"))
            self.assertEqual(claim["context_hash"], first["context_hash"])

    def test_active_claim_can_refresh_after_proof_state_changes(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            first = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--mode",
                    "execute",
                    "--json",
                ).stdout
            )
            self.run_cli_in_workspace(
                workspace_file,
                "receipt",
                "record",
                "RECEIPT-CLAIM-REFRESH",
                "--work-item-id",
                "WORK-0003",
                "--attempt-id",
                "ATTEMPT-0002",
                "--actor",
                "PALARI-SOFIA",
                "--list",
                "actions_taken=recorded bounded proof",
                "--list",
                "outputs_created=docs/product/company-os.md",
                "--json",
            )

            refreshed = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--mode",
                    "execute",
                    "--json",
                ).stdout
            )

            self.assertEqual(refreshed["start"]["status"], "claimed")
            self.assertNotEqual(refreshed["context_hash"], first["context_hash"])
            self.assertEqual(
                refreshed["start"]["claim"]["git_baseline"],
                first["start"]["claim"]["git_baseline"],
            )

    def test_release_and_restart_cannot_launder_changed_preexisting_dirt(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            root = workspace_file.parent
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"],
                check=True,
            )
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "workspace"], check=True
            )
            note = root / "user-note.txt"
            note.write_text("pre-existing\n", encoding="utf-8")

            first = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            first_baseline = first["start"]["claim"]["git_baseline"]
            self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "release",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--json",
            )
            note.write_text("changed after the original claim with a new size\n", encoding="utf-8")

            second = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            self.assertEqual(second["start"]["claim"]["git_baseline"], first_baseline)
            check = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "check",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--git-diff",
                    "--json",
                ).stdout
            )

            self.assertIn("user-note.txt", check["file_changes"]["changed_files"])
            self.assertIn("user-note.txt", check["file_changes"]["outside_write_boundary"])

    def test_cli_agent_brief_review_mode_emits_review_context(self) -> None:
        result = json.loads(
            self.run_cli(
                "agent",
                "brief",
                "WORK-0007",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "review",
                "--json",
            ).stdout
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["mode"], "review")
        self.assertEqual(result["review_context"]["command"], "palari review guide WORK-0007 --json")
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)

    def test_agent_check_ready_packet_fails_missing_completion_proof(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_check(workspace, "WORK-0003", "PALARI-SOFIA")
        checks = self.checks_by_code(result)

        self.assertEqual(result["schema_version"], "palari.agent_check.v1")
        self.assertEqual(result["ok"], False)
        self.assertEqual(result["packet_status"], "ready")
        self.assertEqual(checks["PACKET_READY"]["status"], "pass")
        self.assertEqual(checks["RECEIPT_PRESENT"]["status"], "fail")
        self.assertEqual(checks["EVIDENCE_PRESENT"]["status"], "fail")
        self.assertEqual(checks["CLAIM_OWNED"]["status"], "fail")
        self.assertEqual(checks["REVIEW_PRESENT"]["status"], "pass")
        self.assertEqual(checks["REVIEW_PRESENT"]["required"], False)
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["status"], "pass")
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["required"], False)
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json",
                "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
                "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
            ],
        )

    def test_agent_check_passes_claim_and_file_boundary_after_start(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--json",
            )
            result = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "check",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--changed",
                    "docs/product/company-os.md",
                    "--json",
                ).stdout
            )
            checks = self.checks_by_code(result)

            self.assertEqual(checks["CLAIM_OWNED"]["status"], "pass")
            self.assertEqual(checks["FILE_CHANGES_WITHIN_WRITE_BOUNDARY"]["status"], "pass")
            self.assertEqual(checks["FILE_CHANGES_RECORDED"]["status"], "pass")
            self.assertEqual(result["file_changes"]["inside_write_boundary"], ["docs/product/company-os.md"])

    def test_agent_check_reports_out_of_boundary_and_unrecorded_changes(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--json",
            )
            result = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "check",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--changed",
                    "secrets.env",
                    "--json",
                ).stdout
            )
            checks = self.checks_by_code(result)

            self.assertEqual(checks["FILE_CHANGES_WITHIN_WRITE_BOUNDARY"]["status"], "fail")
            self.assertEqual(checks["FILE_CHANGES_RECORDED"]["status"], "fail")
            self.assertEqual(result["file_changes"]["outside_write_boundary"], ["secrets.env"])
            self.assertEqual(result["file_changes"]["unrecorded_changed_files"], ["secrets.env"])

    def test_agent_json_errors_are_machine_readable(self) -> None:
        result = self.run_cli_in_workspace(
            Path("/tmp/palari-missing-workspace"),
            "agent",
            "check",
            "WORK-0003",
            "--as",
            "PALARI-SOFIA",
            "--json",
            check=False,
        )
        payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["code"], "WORKSPACE_FILE_NOT_FOUND")
        self.assertEqual(payload["error"]["work_item"], "WORK-0003")
        self.assertIn("palari agent brief WORK-0003 --as PALARI-SOFIA", payload["next_allowed_commands"][0])

    def test_agent_json_parse_errors_are_machine_readable(self) -> None:
        result = self.run_cli_in_workspace(
            WORKSPACE,
            "agent",
            "check",
            "WORK-0003",
            "--json",
            check=False,
        )
        payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["code"], "ARGUMENT_PARSE_ERROR")
        self.assertEqual(payload["error"]["work_item"], "WORK-0003")
        self.assertIn("--as", payload["error"]["message"])
        self.assertIn("palari queue --json", payload["next_allowed_commands"])

    def test_agent_check_blocked_packet_returns_packet_blockers(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_check(workspace, "WORK-0007", "PALARI-SOFIA")
        codes = {blocker["code"] for blocker in result["blockers"]}

        self.assertEqual(result["ok"], False)
        self.assertEqual(result["packet_status"], "blocked")
        self.assertIn("DEPENDENCY_NOT_TERMINAL", codes)
        self.assertIn("RECEIPT_READY_REVIEW", codes)
        self.assertEqual(self.checks_by_code(result)["PACKET_READY"]["status"], "fail")

    def test_agent_check_receipt_ready_low_risk_does_not_require_review_or_human_decision(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_check(workspace, "WORK-0007", "PALARI-SOFIA")
        checks = self.checks_by_code(result)

        self.assertEqual(checks["RECEIPT_PRESENT"]["status"], "pass")
        self.assertEqual(checks["EVIDENCE_PRESENT"]["status"], "pass")
        self.assertEqual(checks["EVIDENCE_PRESENT"]["required"], False)
        self.assertEqual(checks["REVIEW_PRESENT"]["status"], "pass")
        self.assertEqual(checks["REVIEW_PRESENT"]["required"], False)
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["status"], "pass")
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["required"], False)

    def test_agent_check_human_decision_required_work_fails_until_approval_exists(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_check(workspace, "WORK-0001", "PALARI-SOFIA")
        checks = self.checks_by_code(result)

        self.assertEqual(result["ok"], False)
        self.assertIn(
            "HUMAN_DECISION_REQUIRED",
            {blocker["code"] for blocker in result["blockers"]},
        )
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["status"], "fail")
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["required"], True)

    def test_agent_check_waiting_for_review_does_not_offer_human_decision(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_check(workspace, "WORK-REPO-0003", "PALARI-STEWARD")
        checks = self.checks_by_code(result)

        self.assertEqual(result["next_step_type"], "review-handoff")
        self.assertEqual(checks["REVIEW_PRESENT"]["status"], "fail")
        self.assertEqual(
            checks["REVIEW_PRESENT"]["next_command"],
            "palari review guide WORK-REPO-0003 --json",
        )
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["status"], "fail")
        self.assertNotIn("next_command", checks["HUMAN_DECISION_PRESENT"])
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent handoff WORK-REPO-0003 --as PALARI-STEWARD --json",
                "palari review guide WORK-REPO-0003 --json",
            ],
        )
        self.assertNotIn("palari human-decision record", "\n".join(result["next_allowed_commands"]))

    def test_cli_agent_check_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "check", "WORK-0003", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_check.v1")
        self.assertEqual(result["ok"], False)
        self.assertEqual(result["packet_id"], "PACKET-WORK-0003-PALARI-SOFIA-EXECUTE-V1")
        self.assertTrue(result["packet_context_hash"].startswith("sha256:"))
        self.assertEqual(result["next_step_type"], "check-active-proof")
        self.assertIn("checks", result)
        self.assertIn("next_allowed_commands", result)

    def test_cli_agent_check_text_prints_mode(self) -> None:
        result = self.run_cli(
            "agent",
            "check",
            "WORK-0003",
            "--as",
            "PALARI-SOFIA",
            "--mode",
            "execute",
        )

        self.assertIn("Mode: execute", result.stdout)

    def test_agent_loop_summarizes_existing_read_only_steps(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_loop(workspace, "WORK-0003", "PALARI-SOFIA")
        stages = {stage["name"]: stage for stage in result["stages"]}

        self.assertEqual(result["schema_version"], "palari.agent_loop.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["next_step_type"], "check-active-proof")
        self.assertEqual(result["would_mutate"], False)
        self.assertEqual(result["commands"]["brief"], stages["brief"]["command"])
        self.assertEqual(result["commands"]["check"], stages["check"]["command"])
        self.assertEqual(result["commands"]["finish"], stages["finish"]["command"])
        self.assertNotIn("handoff", result["commands"])
        self.assertEqual(stages["brief"]["status"], "ready")
        self.assertEqual(stages["check"]["status"], "fail")
        self.assertIn("RECEIPT_PRESENT", stages["check"]["failed_required_checks"])
        self.assertIn("EVIDENCE_PRESENT", stages["check"]["failed_required_checks"])
        self.assertIn("Run the stage commands", result["omitted_context"][0]["reason"])

    def test_agent_loop_includes_human_boundary_for_handoff(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_loop(workspace, "WORK-REPO-0003", "PALARI-STEWARD")
        stages = {stage["name"]: stage for stage in result["stages"]}

        self.assertEqual(result["status"], "handoff-required")
        self.assertEqual(result["next_step_type"], "review-handoff")
        self.assertIn("handoff", result["commands"])
        self.assertEqual(stages["handoff"]["status"], "available")
        self.assertEqual(stages["handoff"]["handoff_types"], ["review"])
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(
            result["human_action_boundary"]["human_only_command_fields"],
            ["human_action_commands[].command"],
        )

    def test_cli_agent_loop_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "loop", "WORK-0003", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_loop.v1")
        self.assertEqual(result["loop_id"], "LOOP-WORK-0003-PALARI-SOFIA-EXECUTE-V1")
        self.assertEqual([stage["name"] for stage in result["stages"]], ["brief", "check", "finish"])
        self.assertIn("next_allowed_commands", result)

    def test_cli_agent_loop_text_prints_stage_commands(self) -> None:
        result = self.run_cli("agent", "loop", "WORK-0003", "--as", "PALARI-SOFIA")

        self.assertIn("Agent loop: LOOP-WORK-0003-PALARI-SOFIA-EXECUTE-V1", result.stdout)
        self.assertIn("Stages:", result.stdout)
        self.assertIn("palari agent brief WORK-0003 --as PALARI-SOFIA", result.stdout)

    def test_agent_doctor_explains_missing_proof_without_mutation(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_doctor(workspace, "WORK-0003", "PALARI-SOFIA")
        checks = {check["code"]: check for check in result["checks"]}

        self.assertEqual(result["schema_version"], "palari.agent_doctor.v1")
        self.assertEqual(result["doctor_id"], "DOCTOR-WORK-0003-PALARI-SOFIA-EXECUTE-V1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["agent_safe"], True)
        self.assertEqual(result["human_handoff_required"], False)
        self.assertEqual(result["would_mutate"], False)
        self.assertIn("RECEIPT_PRESENT", result["summary"])
        self.assertEqual(checks["PACKET"]["status"], "pass")
        self.assertEqual(checks["CONTRACT"]["status"], "fail")
        self.assertIn(
            "palari receipt record RECEIPT-ID --work-item-id WORK-0003",
            "\n".join(result["recommended_commands"]),
        )
        self.assertIn(
            "palari agent loop WORK-0003 --as PALARI-SOFIA --mode execute --json",
            result["recommended_commands"],
        )

    def test_agent_doctor_marks_human_handoff_boundary(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_doctor(workspace, "WORK-REPO-0003", "PALARI-STEWARD")
        checks = {check["code"]: check for check in result["checks"]}

        self.assertEqual(result["status"], "human-handoff-required")
        self.assertEqual(result["agent_safe"], False)
        self.assertEqual(result["human_handoff_required"], True)
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(checks["HANDOFF"]["status"], "warn")
        self.assertEqual(checks["HUMAN_ACTION_BOUNDARY"]["status"], "warn")
        self.assertIn("agent handoff", result["recommended_commands"][0])

    def test_agent_doctor_prioritizes_missing_receipt_before_human_approval(self) -> None:
        workspace = self.modified_workspace(_remove_work_0001_exact_proof)

        result = build_agent_doctor(workspace, "WORK-0001", "PALARI-SOFIA")

        self.assertEqual(result["status"], "missing-proof")
        self.assertFalse(result["human_handoff_required"])
        self.assertIsNone(result["human_action_boundary"])
        self.assertIn("RECEIPT_PRESENT", result["summary"])
        self.assertTrue(result["recommended_commands"][0].startswith("palari receipt record "))

    def test_cli_agent_doctor_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "doctor", "WORK-0003", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_doctor.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertIn("checks", result)
        self.assertIn("recommended_commands", result)

    def test_cli_agent_doctor_text_prints_summary(self) -> None:
        result = self.run_cli("agent", "doctor", "WORK-0003", "--as", "PALARI-SOFIA")

        self.assertIn("Agent doctor: DOCTOR-WORK-0003-PALARI-SOFIA-EXECUTE-V1", result.stdout)
        self.assertIn("Summary:", result.stdout)
        self.assertIn("Diagnosis:", result.stdout)

    def checks_by_code(self, result: dict[str, object]) -> dict[str, dict[str, object]]:
        return {check["code"]: check for check in result["checks"]}

    def modified_workspace(self, mutate: object) -> Workspace:
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        mutate(source)
        return Workspace.from_raw(source, WORKSPACE)

    @contextmanager
    def temp_workspace_file(self, source_workspace: Path) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as directory:
            workspace_root = Path(directory) / "workspace"
            shutil.copytree(
                source_workspace,
                workspace_root,
                ignore=shutil.ignore_patterns(".palari"),
            )
            yield workspace_root / "workspace.json"

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(WORKSPACE), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def run_cli_in_workspace(
        self,
        workspace: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(workspace), *args],
            cwd=REPO_ROOT,
            env=env,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
