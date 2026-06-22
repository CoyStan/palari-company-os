from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_checks import build_agent_check
from palari_company_os.agent_finish import build_agent_finish
from palari_company_os.agent_handoff import build_agent_handoff
from palari_company_os.agent_next import build_agent_next, build_agent_next_all
from palari_company_os.agent_packets import _context_hash, build_agent_brief
from palari_company_os.workspace import Workspace


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"
DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


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
            "palari agent check WORK-0003 --as PALARI-SOFIA --json",
        )
        self.assertEqual(result["candidates"][0]["next_step_type"], "check-active-proof")
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent check WORK-0003 --as PALARI-SOFIA --json",
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
        self.assertEqual(by_id["WORK-0001"]["handoff_guidance"][0]["code"], "DECISION_HANDOFF")
        self.assertIn("decision guide", by_id["WORK-0001"]["handoff_guidance"][0]["message"])
        self.assertIn("PACKET_BLOCKED", by_id["WORK-0001"]["start_blocker_codes"])
        self.assertIn("ATTENTION_NOT_STARTABLE", by_id["WORK-0001"]["start_blocker_codes"])
        self.assertIn("WORK-0007", by_id)
        self.assertEqual(by_id["WORK-0007"]["can_start"], False)
        self.assertIn("RECEIPT_READY_REVIEW", by_id["WORK-0007"]["blocker_codes"])
        self.assertEqual(by_id["WORK-0007"]["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertIn("review guide", by_id["WORK-0007"]["handoff_guidance"][0]["message"])
        self.assertIn("ATTENTION_NOT_STARTABLE", by_id["WORK-0007"]["start_blocker_codes"])
        self.assertNotIn("WORK-0004", by_id)

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
            "palari agent handoff WORK-0003 --as PALARI-SOFIA --json",
        )
        self.assertEqual(
            candidate["next_commands"][0],
            "palari agent handoff WORK-0003 --as PALARI-SOFIA --json",
        )
        self.assertEqual(candidate["next_commands"][1], "palari review guide WORK-0003 --json")

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

    def test_agent_next_all_rolls_up_all_palaris(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_next_all(workspace)
        agent_ids = {agent["agent"]["id"] for agent in result["agents"]}

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(result["status"], "no-ready-work")
        self.assertEqual(agent_ids, {"PALARI-STEWARD", "PALARI-ARCHITECT"})
        self.assertEqual(result["top_candidate"]["agent"]["id"], "PALARI-ARCHITECT")
        self.assertEqual(result["top_candidate"]["candidate"]["work_item_id"], "WORK-REPO-0005")
        self.assertEqual(result["top_candidate"]["candidate"]["can_start"], False)
        self.assertEqual(result["top_candidate"]["candidate"]["next_step_type"], "human-decision")
        self.assertEqual(
            result["top_candidate"]["candidate"]["handoff_guidance"][0]["code"],
            "DECISION_HANDOFF",
        )
        self.assertIn(
            "suggested decision update commands",
            result["top_candidate"]["candidate"]["handoff_guidance"][0]["message"],
        )
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari agent handoff WORK-REPO-0005 --as PALARI-ARCHITECT --json",
        )
        self.assertEqual(
            result["next_allowed_commands"][1],
            "palari decision guide DECISION-REPO-0001 --json",
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
            "palari agent check WORK-0003 --as PALARI-SOFIA --json",
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
                "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
                "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
                "palari evidence record EVIDENCE-ID --work-item-id WORK-0003 "
                '--attempt-id ATTEMPT-0002 --head-sha def5678 --status passed --summary "verification passed" --json',
            ],
        )
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

        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["can_finish"], False)
        self.assertIn(
            "HUMAN_DECISION_PRESENT",
            {item["code"] for item in result["missing_requirements"]},
        )
        command = next(
            item["next_command"]
            for item in result["missing_requirements"]
            if item["code"] == "HUMAN_DECISION_PRESENT"
        )
        self.assertIn("--work-item-id WORK-0001", command)
        self.assertIn("--reviewed-head abc1234", command)
        self.assertIn("--evidence-reference EVIDENCE-0001", command)
        self.assertIn("--review-reference REVIEW-0001", command)
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari receipt record RECEIPT-ID --work-item-id WORK-0001 "
            "--attempt-id ATTEMPT-0001 --actor PALARI-SOFIA --json",
        )
        self.assertEqual(result["next_allowed_commands"][1], command)

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
        self.assertIn("ready-to-edit review record commands", result.stdout)
        self.assertIn("review record commands:", result.stdout)

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

    def test_cli_agent_brief_and_start_alias_emit_json(self) -> None:
        brief = json.loads(
            self.run_cli("agent", "brief", "WORK-0003", "--as", "PALARI-SOFIA", "--mode", "execute", "--json").stdout
        )
        start = json.loads(
            self.run_cli("agent", "start", "WORK-0003", "--as", "PALARI-SOFIA", "--mode", "execute", "--json").stdout
        )

        self.assertEqual(brief["status"], "ready")
        self.assertEqual(start["status"], "ready")
        self.assertEqual(brief["packet_id"], start["packet_id"])

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
        self.assertEqual(checks["REVIEW_PRESENT"]["status"], "pass")
        self.assertEqual(checks["REVIEW_PRESENT"]["required"], False)
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["status"], "pass")
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["required"], False)
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
                "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
                "palari evidence record EVIDENCE-ID --work-item-id WORK-0003 "
                '--attempt-id ATTEMPT-0002 --head-sha def5678 --status passed --summary "verification passed" --json',
            ],
        )

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

    def checks_by_code(self, result: dict[str, object]) -> dict[str, dict[str, object]]:
        return {check["code"]: check for check in result["checks"]}

    def modified_workspace(self, mutate: object) -> Workspace:
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        mutate(source)
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            workspace_file.write_text(json.dumps(source), encoding="utf-8")
            return Workspace.load(workspace_file)

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


if __name__ == "__main__":
    unittest.main()
