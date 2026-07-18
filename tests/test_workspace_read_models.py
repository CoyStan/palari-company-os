from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_directive import compile_agent_directive
from palari_company_os.agent_checks import build_agent_check
from palari_company_os.agent_loop import build_agent_loop
from palari_company_os.agent_operation import AgentOperation
from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.evidence_manifest import (
    OUTPUT_BINDING_VERSION,
    evidence_manifest_hash,
    stamp_receipt_record,
)
from palari_company_os.maintainer import status as maintainer_status
from palari_company_os.governance_journal import JournalVerificationContext
from palari_company_os.read_models import (
    active_parallel_work,
    coordination_warnings,
    detail,
    queue_items,
)
from palari_company_os.scope import check_scope
from palari_company_os.workspace import Workspace
from palari_company_os.workspace_read_models import approval_inbox


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"
DOGFOOD_WORKSPACE = REPO_ROOT / "workspaces" / "palari-company-os"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "workspaces"


class WorkspaceReadModelTests(unittest.TestCase):
    def test_agent_operation_compiles_packet_check_and_directive_once(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        operation = AgentOperation(workspace, "WORK-0003", "PALARI-SOFIA")

        with patch(
            "palari_company_os.agent_operation.build_agent_brief",
            wraps=build_agent_brief,
        ) as build_brief:
            brief = operation.brief()
            check = operation.check()
            directive = operation.directive()

            self.assertIs(operation.brief(), brief)
            self.assertIs(operation.check(), check)
            self.assertIs(operation.directive(), directive)

        self.assertEqual(build_brief.call_count, 1)
        self.assertEqual(check["packet_id"], brief["packet_id"])
        self.assertEqual(directive["status"], "missing-proof")

    def test_agent_operation_check_matches_standalone_check(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        expected = build_agent_check(workspace, "WORK-0003", "PALARI-SOFIA")

        actual = AgentOperation(
            workspace,
            "WORK-0003",
            "PALARI-SOFIA",
        ).check()

        expected.pop("created_at")
        actual.pop("created_at")
        self.assertEqual(actual, expected)

    def test_agent_loop_reuses_one_packet_for_all_stages(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        with patch(
            "palari_company_os.agent_operation.build_agent_brief",
            wraps=build_agent_brief,
        ) as build_brief:
            result = build_agent_loop(workspace, "WORK-0003", "PALARI-SOFIA")

        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(build_brief.call_count, 1)

    def test_agent_directive_is_pure_and_preserves_human_boundary(self) -> None:
        check = {
            "mode": "execute",
            "ok": False,
            "agent": {"id": "PALARI-WORKER"},
            "work_item": {"id": "WORK-OPAQUE"},
            "next_step_type": "human-decision",
            "checks": [
                {
                    "code": "RECEIPT_PRESENT",
                    "status": "pass",
                    "required": True,
                    "message": "Receipt is present.",
                },
                {
                    "code": "EVIDENCE_PRESENT",
                    "status": "pass",
                    "required": True,
                    "message": "Evidence is present.",
                },
                {
                    "code": "REVIEW_PRESENT",
                    "status": "pass",
                    "required": True,
                    "message": "Review is present.",
                },
                {
                    "code": "HUMAN_DECISION_PRESENT",
                    "status": "fail",
                    "required": True,
                    "message": "Human decision quorum is incomplete.",
                },
            ],
            "blockers": [
                {
                    "code": "HUMAN_DECISION_REQUIRED",
                    "message": "Qualified human authority is required.",
                }
            ],
            "next_allowed_commands": [
                "palari human-decision record HUMAN-DECISION-ID --json"
            ],
        }
        original = deepcopy(check)

        first = compile_agent_directive(check)
        second = compile_agent_directive(check)

        self.assertEqual(first, second)
        self.assertEqual(check, original)
        self.assertEqual(first["status"], "handoff-ready")
        self.assertEqual(first["owner"], "human")
        self.assertTrue(first["agent_may_execute"])
        self.assertTrue(first["human_boundary"])
        self.assertFalse(first["review_boundary"])
        self.assertEqual(first["automatic_transitions"], [])
        self.assertEqual(
            first["next_action"]["command"],
            "palari agent handoff WORK-OPAQUE --as PALARI-WORKER --json",
        )
        self.assertEqual(first["handoff_guidance"][0]["code"], "HUMAN_APPROVAL_HANDOFF")
        self.assertTrue(first["resolution_summary"]["human_attention_required"])
        self.assertNotIn(
            "palari human-decision record",
            "\n".join(first["next_allowed_commands"]),
        )

    def test_approval_inbox_forwards_caller_owned_journal_context(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        context = JournalVerificationContext()
        expected = {"schema_version": "test.approval-inbox"}

        with patch(
            "palari_company_os.workspace_read_models.build_approval_inbox",
            return_value=expected,
        ) as build:
            result = approval_inbox(
                workspace,
                selected_work_ids=("WORK-0001",),
                journal_context=context,
            )

        self.assertEqual(result, expected)
        self.assertIs(build.call_args.kwargs["journal_context"], context)
        self.assertEqual(
            build.call_args.kwargs["selected_work_ids"],
            ("WORK-0001",),
        )

    def test_retired_work_is_closed_in_queue_but_remains_detailed(self) -> None:
        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            lambda raw: raw["work_items"][0].update(
                {
                    "status": "superseded",
                    "terminal_reason": "A successor now owns the objective.",
                }
            ),
        )

        item = queue_items(workspace)[0]
        payload = detail(workspace, item.id)

        self.assertEqual(item.attention, "closed")
        self.assertEqual(item.next_step_type, "closed")
        self.assertFalse(item.ai_safe_to_proceed)
        self.assertEqual(item.terminal_disposition, "superseded")
        self.assertIn("successor", item.why.lower())
        self.assertEqual(
            payload["work_item"]["terminal_reason"],
            "A successor now owns the objective.",
        )

    def test_approval_inbox_narrows_away_retired_work(self) -> None:
        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            lambda raw: raw["work_items"][0].update(
                {
                    "status": "abandoned",
                    "terminal_reason": "No longer worth operator attention.",
                }
            ),
        )
        workspace.work_items.append(
            workspace.work_items[0].__class__.from_record(
                {
                    "id": "WORK-ACTIVE",
                    "title": "Still active",
                    "goal": workspace.work_items[0].goal,
                    "palari": workspace.work_items[0].palari,
                    "status": "active",
                }
            )
        )
        expected = {"schema_version": "test.approval-inbox"}

        with (
            patch(
                "palari_company_os.workspace_read_models.load_store",
                return_value=SimpleNamespace(data={}),
            ),
            patch(
                "palari_company_os.workspace_read_models.build_approval_inbox",
                return_value=expected,
            ) as build,
        ):
            result = approval_inbox(workspace)

        self.assertEqual(result, expected)
        self.assertEqual(
            build.call_args.kwargs["selected_work_ids"],
            ("WORK-ACTIVE",),
        )

    def test_all_retired_approval_inbox_cannot_emit_an_authority_action(self) -> None:
        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            lambda raw: raw["work_items"][0].update(
                {
                    "status": "abandoned",
                    "terminal_reason": "No active objective remains.",
                }
            ),
        )
        built = {
            "schema_version": "test.approval-inbox",
            "individual_items": [{"id": "WORK-1"}],
            "packs": [{"pack_id": "PACK-UNSAFE"}],
            "approval_commands": [{"command": "must disappear"}],
            "counts": {
                "items": 1,
                "packs": 1,
                "eligible": 1,
                "blocked": 0,
                "stale": 0,
                "non_batchable": 0,
            },
            "primary_action": {
                "available": True,
                "count": 1,
                "commands": ["must disappear"],
            },
        }

        with (
            patch(
                "palari_company_os.workspace_read_models.load_store",
                return_value=SimpleNamespace(data={}),
            ),
            patch(
                "palari_company_os.workspace_read_models.build_approval_inbox",
                return_value=built,
            ),
        ):
            result = approval_inbox(workspace)

        self.assertEqual(result["individual_items"], [])
        self.assertEqual(result["packs"], [])
        self.assertEqual(result["approval_commands"], [])
        self.assertEqual(result["counts"]["items"], 0)
        self.assertFalse(result["primary_action"]["available"])
        self.assertEqual(result["primary_action"]["commands"], [])

    def test_ready_to_report_does_not_recommend_redundant_validation(self) -> None:
        directive = compile_agent_directive(
            {
                "ok": True,
                "agent": {"id": "PALARI-WORKER"},
                "work_item": {"id": "WORK-OPAQUE"},
                "next_step_type": "execute",
                "checks": [],
                "blockers": [],
                "next_allowed_commands": [],
            }
        )

        self.assertEqual(directive["status"], "ready-to-report")
        self.assertEqual(directive["owner"], "agent")
        self.assertEqual(directive["next_action"]["command"], "")
        self.assertFalse(directive["agent_may_execute"])
        self.assertIn("Report completion", directive["next_action"]["message"])

    def test_mixed_blockers_do_not_claim_automatic_transition_is_ready(self) -> None:
        directive = compile_agent_directive(
            {
                "ok": False,
                "agent": {"id": "PALARI-WORKER"},
                "work_item": {"id": "WORK-OPAQUE"},
                "next_step_type": "human-decision",
                "checks": [],
                "blockers": [
                    {"code": "ACCEPTANCE_PROJECTION_PENDING"},
                    {"code": "HUMAN_DECISION_REQUIRED"},
                ],
                "next_allowed_commands": [],
            }
        )

        self.assertTrue(directive["agent_may_execute"])
        self.assertEqual(directive["owner"], "human")
        self.assertEqual(directive["automatic_transitions"], [])

    def test_example_workspace_loads(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        self.assertEqual(workspace.name, "Acme Company OS Example")
        self.assertEqual(len(workspace.goals), 2)
        self.assertEqual(len(workspace.palaris), 2)
        self.assertEqual(
            [source.id for source in workspace.sources],
            ["SOURCE-0001", "SOURCE-0002", "SOURCE-0003"],
        )
        self.assertEqual(len(workspace.workbenches), 2)
        self.assertEqual(len(workspace.work_items), 7)
        self.assertEqual(len(workspace.receipts), 2)

    def test_dogfood_workspace_has_real_workbench_context(self) -> None:
        workspace = Workspace.load(DOGFOOD_WORKSPACE)
        payload = detail(workspace, "WORK-REPO-0002")
        queue = {item.id: item for item in queue_items(workspace)}

        self.assertEqual(len(workspace.workbenches), 2)
        self.assertEqual(payload["workbench"]["id"], "WORKBENCH-REPO-FOUNDATION")
        self.assertEqual(payload["workbench"]["label"], "Repo Foundation")
        self.assertEqual(queue["WORK-REPO-0002"].workbench_label, "Repo Foundation")
        self.assertEqual(queue["WORK-REPO-0006"].workbench_label, "Repo Foundation")

    def test_dogfood_review_waiting_work_is_not_ai_safe(self) -> None:
        workspace = Workspace.load(DOGFOOD_WORKSPACE)
        queue = {item.id: item for item in queue_items(workspace)}

        self.assertEqual(queue["WORK-REPO-0003"].attention, "needs-review")
        self.assertEqual(queue["WORK-REPO-0003"].review_state, "missing")
        self.assertFalse(queue["WORK-REPO-0003"].ai_safe_to_proceed)
        self.assertEqual(
            queue["WORK-REPO-0003"].next_commands[0],
            "palari review guide WORK-REPO-0003 --json",
        )
        self.assertEqual(
            queue["WORK-REPO-0003"].agent_handoff_command,
            "palari agent handoff WORK-REPO-0003 --as PALARI-STEWARD --json",
        )
        self.assertEqual(queue["WORK-REPO-0004"].attention, "ready-for-ai-work")
        self.assertFalse(queue["WORK-REPO-0004"].ai_safe_to_proceed)
        self.assertIn("Inspect the high-risk scope", queue["WORK-REPO-0004"].next_action)
        self.assertEqual(
            queue["WORK-REPO-0004"].next_commands[0],
            "palari detail WORK-REPO-0004 --json",
        )
        self.assertEqual(queue["WORK-REPO-0004"].agent_handoff_command, "")
        self.assertEqual(queue["WORK-REPO-0006"].attention, "needs-evidence")
        self.assertEqual(queue["WORK-REPO-0006"].next_step_type, "check-active-proof")
        self.assertEqual(queue["WORK-REPO-0006"].receipt_state, "ready")
        self.assertEqual(queue["WORK-REPO-0006"].evidence_state, "invalid")
        self.assertEqual(queue["WORK-REPO-0006"].approval_progress, "0/0")
        self.assertTrue(queue["WORK-REPO-0006"].ai_safe_to_proceed)
        self.assertEqual(
            queue["WORK-REPO-0006"].next_commands[0],
            "palari agent check WORK-REPO-0006 --as PALARI-STEWARD --mode execute --json",
        )
        self.assertEqual(queue["WORK-REPO-0006"].agent_handoff_command, "")

    def test_queue_prioritizes_human_decisions(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        items = queue_items(workspace)
        by_id = {item.id: item for item in items}

        self.assertEqual(items[0].attention, "needs-human-decision")
        self.assertEqual(by_id["WORK-0001"].attention, "needs-human-decision")
        self.assertIn("Review is accept-ready", by_id["WORK-0001"].why)
        self.assertEqual(by_id["WORK-0001"].approval_progress, "0/1")
        self.assertFalse(by_id["WORK-0001"].ai_safe_to_proceed)
        self.assertIn("keep low-risk work light", by_id["WORK-0001"].learning_signal)
        self.assertEqual(by_id["WORK-0002"].attention, "needs-human-decision")
        self.assertEqual(by_id["WORK-0002"].next_step_type, "human-decision")
        self.assertFalse(by_id["WORK-0002"].ai_safe_to_proceed)
        self.assertIn("DECISION-0001", by_id["WORK-0002"].why)
        self.assertEqual(
            by_id["WORK-0002"].next_commands[0],
            "palari decision guide DECISION-0001 --json",
        )
        self.assertEqual(by_id["WORK-0002"].recommended_intensity, "high")
        self.assertEqual(by_id["WORK-0002"].approval_progress, "0/2")
        self.assertEqual(
            by_id["WORK-0002"].agent_handoff_command,
            "palari agent handoff WORK-0002 --as PALARI-ALFRED --json",
        )
        self.assertEqual(
            by_id["WORK-0002"].agent_loop_command,
            "palari agent loop WORK-0002 --as PALARI-ALFRED --json",
        )
        self.assertEqual(by_id["WORK-0003"].attention, "needs-evidence")
        self.assertEqual(by_id["WORK-0003"].next_step_type, "check-active-proof")
        self.assertTrue(by_id["WORK-0003"].ai_safe_to_proceed)
        self.assertEqual(
            by_id["WORK-0003"].next_commands[:2],
            [
                "palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json",
                "palari agent finish WORK-0003 --as PALARI-SOFIA --json",
            ],
        )
        self.assertEqual(
            by_id["WORK-0003"].agent_loop_command,
            "palari agent loop WORK-0003 --as PALARI-SOFIA --json",
        )
        self.assertEqual(by_id["WORK-0005"].attention, "needs-evidence")
        self.assertEqual(by_id["WORK-0005"].evidence_state, "stale")
        self.assertEqual(
            by_id["WORK-0005"].next_commands[:2],
            [
                "palari agent check WORK-0005 --as PALARI-SOFIA --mode execute --json",
                "palari agent finish WORK-0005 --as PALARI-SOFIA --json",
            ],
        )
        self.assertEqual(by_id["WORK-0006"].attention, "needs-review")
        self.assertEqual(by_id["WORK-0006"].next_step_type, "review-handoff")
        self.assertEqual(by_id["WORK-0006"].review_state, "stale")
        self.assertFalse(by_id["WORK-0006"].ai_safe_to_proceed)
        self.assertEqual(
            by_id["WORK-0006"].next_commands[0],
            "palari review guide WORK-0006 --json",
        )
        self.assertEqual(by_id["WORK-0007"].attention, "needs-evidence")
        self.assertEqual(by_id["WORK-0007"].next_step_type, "check-active-proof")
        self.assertEqual(by_id["WORK-0007"].receipt_state, "ready")
        self.assertEqual(by_id["WORK-0007"].integration_state, "not-ready")
        self.assertEqual(by_id["WORK-0007"].acceptance_state, "pending")
        self.assertIn("focused verification", by_id["WORK-0007"].next_action)
        self.assertEqual(
            by_id["WORK-0007"].next_commands[0],
            "palari agent check WORK-0007 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(by_id["WORK-0004"].attention, "needs-human-decision")

    def test_detail_assembles_related_records(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        payload = detail(workspace, "WORK-0001")

        self.assertEqual(payload["work_item"]["title"], "Prepare beta launch checklist")
        self.assertEqual(payload["goal"]["id"], "GOAL-0001")
        self.assertEqual(payload["palari"]["name"], "Sofia")
        self.assertEqual(payload["workbench"]["id"], "WORKBENCH-BETA")
        self.assertEqual(payload["evidence"]["status"], "passed")
        self.assertEqual(payload["review"]["verdict"], "accept-ready")
        self.assertIsNone(payload["human_decision"])
        self.assertEqual(payload["attention"], "needs-human-decision")
        self.assertEqual(payload["next_step_type"], "human-decision")
        self.assertEqual(payload["safety"]["evidence_state"], "passed")
        self.assertEqual(payload["safety"]["review_state"], "accept-ready")
        self.assertEqual(payload["safety"]["approval_progress"], "0/1")
        self.assertEqual(payload["child_work_items"][0]["id"], "WORK-0007")

    def test_detail_includes_sources_and_receipt(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        payload = detail(workspace, "WORK-0007")

        self.assertEqual(payload["sources"][0]["id"], "SOURCE-0001")
        self.assertEqual(payload["receipt"]["id"], "RECEIPT-0001")
        self.assertEqual(payload["receipt"]["sources_used"], ["SOURCE-0001"])
        self.assertEqual(payload["safety"]["receipt_state"], "ready")
        self.assertEqual(payload["attention"], "needs-evidence")
        self.assertEqual(payload["next_step_type"], "check-active-proof")
        self.assertEqual(
            payload["next_commands"][0],
            "palari agent check WORK-0007 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            payload["agent_loop_command"],
            "palari agent loop WORK-0007 --as PALARI-SOFIA --json",
        )
        self.assertEqual(payload["agent_handoff_command"], "")
        self.assertEqual(payload["parent_work_item"]["id"], "WORK-0001")
        self.assertEqual(payload["dependencies"][0]["id"], "WORK-0003")
        self.assertEqual(
            payload["agent_commands"]["brief"],
            "palari agent brief WORK-0007 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            payload["agent_commands"]["check"],
            "palari agent check WORK-0007 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            payload["agent_commands"]["finish"],
            "palari agent finish WORK-0007 --as PALARI-SOFIA --json",
        )
        self.assertEqual(
            payload["agent_commands"]["doctor"],
            "palari agent doctor WORK-0007 --as PALARI-SOFIA --json",
        )
        self.assertEqual(
            payload["agent_commands"]["loop"],
            "palari agent loop WORK-0007 --as PALARI-SOFIA --json",
        )
        self.assertEqual(
            payload["agent_commands"]["handoff"],
            "palari agent handoff WORK-0007 --as PALARI-SOFIA --json",
        )
        self.assertNotIn("review", payload["agent_commands"])
        self.assertNotIn("review_check", payload["agent_commands"])

    def test_detail_omits_review_packet_commands_when_not_review_ready(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        payload = detail(workspace, "WORK-0003")

        self.assertEqual(payload["next_step_type"], "check-active-proof")
        self.assertNotIn("review", payload["agent_commands"])
        self.assertNotIn("review_check", payload["agent_commands"])

    def test_parallel_attempts_are_visible_without_conflict(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        active = active_parallel_work(workspace)
        queue = {item.id: item for item in queue_items(workspace)}

        self.assertEqual(
            [item["work_item_id"] for item in active],
            ["WORK-0003", "WORK-0005"],
        )
        self.assertEqual(coordination_warnings(workspace), [])
        self.assertEqual(queue["WORK-0003"].attention, "needs-evidence")
        self.assertEqual(queue["WORK-0003"].workbench_label, "Beta Operations")
        self.assertEqual(queue["WORK-0003"].active_attempts[0]["attempt_id"], "ATTEMPT-0002")

    def test_exclusive_parallel_conflict_is_surfaced_in_queue_and_detail(self) -> None:
        def add_conflict(data: dict[str, object]) -> None:
            data["work_items"][2]["parallel_policy"] = "exclusive"
            data["work_items"][2]["conflict_targets"] = [" DOCS/Product/Company-OS.md "]
            data["work_items"].append(
                {
                    "id": "WORK-CONFLICT",
                    "title": "Conflicting company model edit",
                    "goal": "GOAL-0001",
                    "palari": "PALARI-SOFIA",
                    "workbench_id": "WORKBENCH-BETA",
                    "risk": "R1",
                    "intensity": "light",
                    "status": "active",
                    "scope": "Edit the same company model document at the same time.",
                    "allowed_resources": ["docs/product/company-os.md"],
                    "conflict_targets": ["docs/product/company-os.md"],
                    "parallel_policy": "exclusive",
                    "current_attempt": "ATTEMPT-CONFLICT",
                    "required_approval_count": 0,
                }
            )
            data["attempts"].append(
                {
                    "id": "ATTEMPT-CONFLICT",
                    "work_item_id": "WORK-CONFLICT",
                    "actor": "PALARI-SOFIA",
                    "status": "active",
                    "branch": "copy/conflicting-company-model-edit",
                    "workspace_path": "/tmp/acme-company-os/WORK-CONFLICT",
                    "started_at": "2026-06-18T17:22:00Z",
                    "updated_at": "2026-06-18T17:30:00Z",
                    "output_targets": ["docs/product/company-os.md"],
                    "commits": ["conflict-head"],
                    "changed_files": ["docs/product/company-os.md"],
                }
            )

        workspace = self.modified_workspace(add_conflict)
        queue = {item.id: item for item in queue_items(workspace)}
        payload = detail(workspace, "WORK-0003")

        self.assertEqual(queue["WORK-0003"].attention, "blocked")
        self.assertFalse(queue["WORK-0003"].ai_safe_to_proceed)
        self.assertIn("WORK-CONFLICT", queue["WORK-0003"].coordination_warnings[0])
        self.assertIn("WORK-CONFLICT", payload["coordination_warnings"][0])
        self.assertEqual(
            coordination_warnings(workspace)[0]["targets"],
            ["docs/product/company-os.md"],
        )

    def test_receipt_without_evidence_is_not_completion_ready(self) -> None:
        workspace = Workspace.load(FIXTURES / "valid-source-receipt-loop.json")
        item = queue_items(workspace)[0]

        self.assertEqual(item.attention, "needs-evidence")
        self.assertEqual(item.next_step_type, "check-active-proof")
        self.assertEqual(item.receipt_state, "ready")
        self.assertEqual(item.integration_state, "not-ready")
        self.assertEqual(item.acceptance_state, "pending")
        self.assertTrue(item.ai_safe_to_proceed)
        self.assertIn("no evidence", item.why)

    def test_exact_low_risk_evidence_is_ready_for_automatic_completion(self) -> None:
        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            self.add_current_exact_evidence,
        )
        item = queue_items(workspace)[0]

        self.assertEqual(item.attention, "ready-to-complete")
        self.assertEqual(item.next_step_type, "automatic-reconciliation")
        self.assertEqual(item.evidence_state, "passed")
        self.assertEqual(item.integration_state, "ready")
        self.assertEqual(item.acceptance_state, "not-required")
        self.assertFalse(item.ai_safe_to_proceed)
        self.assertIn("exact passing evidence", item.why)

    def test_tampered_low_risk_evidence_returns_to_needs_evidence(self) -> None:
        def tamper(data: dict[str, Any]) -> None:
            self.add_current_exact_evidence(data)
            data["evidence_runs"][0]["commands"].append("unverified command")

        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            tamper,
        )
        item = queue_items(workspace)[0]

        self.assertEqual(item.attention, "needs-evidence")
        self.assertEqual(item.next_step_type, "check-active-proof")
        self.assertEqual(item.integration_state, "not-ready")
        self.assertEqual(item.acceptance_state, "pending")
        self.assertIn("not a current exact proof", item.why)

    def test_high_risk_work_still_requires_governance_even_with_receipt(self) -> None:
        def make_high_risk(data: dict[str, object]) -> None:
            self.add_current_exact_evidence(data)
            data["work_items"][0]["risk"] = "R3"
            data["work_items"][0]["intensity"] = "standard"

        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            make_high_risk,
        )
        item = queue_items(workspace)[0]

        self.assertEqual(item.receipt_state, "ready")
        self.assertEqual(item.attention, "needs-review")
        self.assertEqual(item.integration_state, "not-ready")

    def test_approval_required_low_risk_work_requires_review(self) -> None:
        def require_approval(data: dict[str, object]) -> None:
            self.add_current_exact_evidence(data)
            work_items = data["work_items"]
            assert isinstance(work_items, list)
            work_items[0]["required_approval_count"] = 1

        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            require_approval,
        )
        item = queue_items(workspace)[0]

        self.assertEqual(item.receipt_state, "ready")
        self.assertEqual(item.attention, "needs-review")
        self.assertEqual(item.integration_state, "not-ready")

    def test_external_write_disables_review_free_completion(self) -> None:
        def allow_external_write(data: dict[str, object]) -> None:
            data["work_items"][0]["allowed_actions"] = ["external_write"]
            data["receipts"][0]["external_writes"] = ["google_drive:doc-1"]
            self.add_current_exact_evidence(data)

        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            allow_external_write,
        )
        item = queue_items(workspace)[0]

        self.assertEqual(item.receipt_state, "ready")
        self.assertEqual(item.attention, "needs-review")
        self.assertEqual(item.integration_state, "not-ready")

    def test_evidence_staleness_blocks_review(self) -> None:
        def add_new_current_attempt(data: dict[str, object]) -> None:
            work = data["work_items"][0]
            work["current_attempt"] = "ATTEMPT-NEW"
            data["attempts"].append(
                {
                    **data["attempts"][0],
                    "id": "ATTEMPT-NEW",
                    "status": "active",
                    "commits": ["abc1234", "newhead"],
                    "updated_at": "2026-06-18T18:10:00Z",
                }
            )

        workspace = self.modified_workspace(add_new_current_attempt)
        item = {item.id: item for item in queue_items(workspace)}["WORK-0001"]
        self.assertEqual(item.attention, "needs-evidence")
        self.assertEqual(item.evidence_state, "stale")
        self.assertIn("stale", item.why)

    def test_changes_requested_is_classified_as_repair_with_actionable_guidance(self) -> None:
        def request_changes(data: dict[str, object]) -> None:
            reviews = data["review_verdicts"]
            assert isinstance(reviews, list)
            review = next(item for item in reviews if item["work_item_id"] == "WORK-0006")
            review["reviewed_head"] = "review-fresh"
            review["verdict"] = "changes-requested"

        workspace = self.modified_workspace(request_changes)
        item = {item.id: item for item in queue_items(workspace)}["WORK-0006"]
        payload = detail(workspace, "WORK-0006")

        self.assertEqual(item.attention, "changes-requested")
        self.assertEqual(item.next_step_type, "repair")
        self.assertTrue(item.ai_safe_to_proceed)
        self.assertIn("requested changes", item.why)
        self.assertIn("Repair only the reviewed findings", item.next_action)
        self.assertEqual(payload["next_step_type"], "repair")

    def test_qualified_human_decision_satisfies_quorum(self) -> None:
        def approve(data: dict[str, object]) -> None:
            data["human_decisions"].append(
                {
                    "id": "HUMAN-DECISION-0002",
                    "work_item_id": "WORK-0001",
                    "human_id": "HUMAN-FOUNDER",
                    "reviewed_head": "abc1234",
                    "decision": "accepted",
                    "status": "accepted",
                    "acceptance_mode": "human",
                    "quorum_status": "met",
                    "evidence_reference": "EVIDENCE-0001",
                    "review_reference": "REVIEW-0001",
                    "timestamp": "2026-06-18T18:00:00Z",
                }
            )

        workspace = self.modified_workspace(approve)
        item = {item.id: item for item in queue_items(workspace)}["WORK-0001"]
        self.assertEqual(item.attention, "ready-to-integrate")
        self.assertEqual(item.approval_progress, "1/1")
        self.assertEqual(item.integration_state, "ready")

    def test_later_negative_human_decision_revokes_read_model_quorum(self) -> None:
        def accept_then_reject(data: dict[str, object]) -> None:
            decisions = data["human_decisions"]
            decisions.extend(
                [
                    {
                        "id": "HUMAN-DECISION-0002",
                        "work_item_id": "WORK-0001",
                        "human_id": "HUMAN-FOUNDER",
                        "reviewed_head": "abc1234",
                        "decision": "accepted",
                        "status": "accepted",
                        "acceptance_mode": "human",
                        "quorum_status": "met",
                        "evidence_reference": "EVIDENCE-0001",
                        "review_reference": "REVIEW-0001",
                        "timestamp": "2026-06-18T18:00:00Z",
                    },
                    {
                        "id": "HUMAN-DECISION-0003",
                        "work_item_id": "WORK-0001",
                        "human_id": "HUMAN-FOUNDER",
                        "reviewed_head": "abc1234",
                        "decision": "changes-requested",
                        "status": "changes-requested",
                        "quorum_status": "not-met",
                        "timestamp": "2026-06-18T18:01:00Z",
                    },
                ]
            )

        workspace = self.modified_workspace(accept_then_reject)
        item = {item.id: item for item in queue_items(workspace)}["WORK-0001"]

        self.assertEqual(item.attention, "needs-human-decision")
        self.assertEqual(item.approval_progress, "0/1")
        self.assertEqual(item.integration_state, "not-ready")

    def test_approval_for_previous_review_does_not_count_for_refreshed_proof(self) -> None:
        from palari_company_os.governance_binding import review_proof_hash

        def refresh_review(data: dict[str, object]) -> None:
            reviews = data["review_verdicts"]
            original = next(item for item in reviews if item["id"] == "REVIEW-0001")
            data["human_decisions"].append(
                {
                    "id": "HUMAN-DECISION-OLD-PROOF",
                    "work_item_id": "WORK-0001",
                    "human_id": "HUMAN-FOUNDER",
                    "reviewed_head": "abc1234",
                    "decision": "accepted",
                    "status": "accepted",
                    "acceptance_mode": "human",
                    "quorum_status": "met",
                    "evidence_reference": "EVIDENCE-0001",
                    "review_reference": "REVIEW-0001",
                    "timestamp": "2026-06-18T18:00:00Z",
                }
            )
            refreshed = dict(original)
            refreshed["id"] = "REVIEW-REFRESHED"
            refreshed["timestamp"] = "2026-06-18T18:01:00Z"
            refreshed["proof_hash"] = review_proof_hash(refreshed)
            reviews.append(refreshed)

        workspace = self.modified_workspace(refresh_review)
        item = {item.id: item for item in queue_items(workspace)}["WORK-0001"]

        self.assertEqual(item.attention, "needs-human-decision")
        self.assertEqual(item.approval_progress, "0/1")

    def test_work_contract_change_stales_exact_bound_review(self) -> None:
        def change_contract(data: dict[str, object]) -> None:
            data["work_items"][0]["scope"] = "Changed after the exact review."

        workspace = self.modified_workspace(change_contract)
        item = {item.id: item for item in queue_items(workspace)}["WORK-0001"]

        self.assertEqual(item.attention, "needs-review")
        self.assertEqual(item.review_state, "stale")
        self.assertEqual(item.integration_state, "not-ready")
        self.assertIn("work_contract_hash is stale", item.why)

    def test_detail_uses_accepted_at_for_later_revocation(self) -> None:
        def revoke_later(data: dict[str, object]) -> None:
            data["work_items"][0]["status"] = "in-review"
            data["acceptance_records"].append(
                {
                    "id": "A-REVOKED",
                    "work_item_id": "WORK-1",
                    "human_id": "HUMAN-PRODUCT",
                    "reviewed_head": "head-1",
                    "status": "revoked",
                    "accepted_at": "2030-01-01T00:00:00-05:00",
                }
            )

        workspace = self.modified_fixture_workspace(
            "valid-accepted-completed-work.json",
            revoke_later,
        )
        payload = detail(workspace, "WORK-1")

        self.assertEqual(payload["safety"]["acceptance_state"], "revoked")

    def test_scope_check_allows_declared_path_and_blocks_violations(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        allowed = check_scope(
            workspace,
            "WORK-0001",
            ["examples/acme-company-os/workspace.json"],
            [],
        )
        blocked = check_scope(workspace, "WORK-0001", ["secrets.env"], ["deploy"])

        self.assertTrue(allowed.allowed)
        self.assertFalse(blocked.allowed)
        self.assertIn("Path is outside allowed resources: secrets.env", blocked.violations)
        self.assertIn("Action is explicitly forbidden: deploy", blocked.violations)

    def test_scope_check_rejects_path_traversal_prefix_bypass(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        blocked = check_scope(workspace, "WORK-0003", ["docs/../secrets.env"], [])

        self.assertFalse(blocked.allowed)
        self.assertIn(
            "Path is outside allowed resources: docs/../secrets.env",
            blocked.violations,
        )

    def test_detail_uses_declared_current_attempt_not_latest_attempt_record(self) -> None:
        def add_non_current_later_attempt(data: dict[str, object]) -> None:
            data["attempts"].append(
                {
                    "id": "ATTEMPT-NONCURRENT",
                    "work_item_id": "WORK-0001",
                    "actor": "PALARI-SOFIA",
                    "status": "active",
                    "branch": "non-current-later",
                    "workspace_path": "/tmp/acme-company-os/WORK-0001-later",
                    "started_at": "2026-06-19T10:00:00Z",
                    "updated_at": "2026-06-19T10:30:00Z",
                    "commits": ["different-head"],
                    "changed_files": ["examples/acme-company-os/workspace.json"],
                    "output_targets": ["examples/acme-company-os/workspace.json"],
                }
            )

        workspace = self.modified_workspace(add_non_current_later_attempt)
        payload = detail(workspace, "WORK-0001")

        self.assertEqual(payload["attempt"]["id"], "ATTEMPT-0001")
        self.assertEqual(payload["safety"]["evidence_state"], "passed")


    def test_scope_check_rejects_parent_traversal(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        result = check_scope(
            workspace,
            "WORK-0001",
            ["examples/acme-company-os/../secrets.env"],
            [],
        )

        self.assertFalse(result.allowed)
        self.assertIn(
            "Path is outside allowed resources: examples/acme-company-os/../secrets.env",
            result.violations,
        )

    def modified_workspace(self, mutate: object) -> Workspace:
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        mutate(source)
        return Workspace.from_raw(source, WORKSPACE)

    @staticmethod
    def add_current_exact_evidence(data: dict[str, Any]) -> None:
        receipt = stamp_receipt_record(data["receipts"][0], [])
        data["receipts"][0] = receipt
        evidence = {
            "id": "EVIDENCE-EXACT-1",
            "work_item_id": "WORK-1",
            "attempt_id": "ATTEMPT-1",
            "head_sha": "head-1",
            "status": "passed",
            "commands": ["python3 -m unittest tests.test_governance_kernel"],
            "artifacts": ["notes/summary.md"],
            "artifact_hashes": [
                {
                    "path": "notes/summary.md",
                    "sha256": "sha256:" + ("a" * 64),
                    "status": "present",
                }
            ],
            "output_binding_version": OUTPUT_BINDING_VERSION,
            "receipt_hash": receipt["receipt_hash"],
            "summary": "Current exact focused evidence passed.",
            "freshness": "exact-head",
            "timestamp": "2026-06-19T04:06:00Z",
        }
        evidence["manifest_hash"] = evidence_manifest_hash(evidence)
        data["evidence_runs"].append(evidence)

    def modified_fixture_workspace(self, fixture: str, mutate: object) -> Workspace:
        source = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
        mutate(source)
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            workspace_file.write_text(json.dumps(source), encoding="utf-8")
            return Workspace.load(workspace_file)


class CliTests(unittest.TestCase):
    def test_cli_queue_json(self) -> None:
        result = self.run_cli("queue", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["workspace"], "Acme Company OS Example")
        self.assertEqual(payload["queue"][0]["attention"], "needs-human-decision")
        self.assertNotIn("closed", {item["attention"] for item in payload["queue"]})
        self.assertEqual(
            payload["queue"][0]["agent_handoff_command"],
            "palari agent handoff WORK-0001 --as PALARI-SOFIA --json",
        )
        self.assertEqual(
            payload["queue"][0]["agent_loop_command"],
            "palari agent loop WORK-0001 --as PALARI-SOFIA --json",
        )

    def test_cli_queue_include_closed_json(self) -> None:
        result = self.run_cli_in_workspace(
            DOGFOOD_WORKSPACE, "queue", "--include-closed", "--json"
        )
        payload = json.loads(result.stdout)

        self.assertIn("closed", {item["attention"] for item in payload["queue"]})

    def test_cli_retirement_leaves_default_operating_surfaces_but_stays_auditable(self) -> None:
        with self.temp_workspace() as workspace:
            self.run_cli_in_workspace(
                workspace,
                "work",
                "create",
                "WORK-RETIRE",
                "--title",
                "Obsolete experiment",
                "--goal",
                "GOAL-0001",
                "--palari",
                "PALARI-SOFIA",
                "--status",
                "active",
                "--json",
            )
            update = self.run_cli_in_workspace(
                workspace,
                "work",
                "update",
                "WORK-RETIRE",
                "--status",
                "abandoned",
                "--terminal-reason",
                "The experiment no longer earns attention.",
                "--json",
                check=False,
            )
            self.assertEqual(update.returncode, 0, update.stderr)
            self.run_cli_in_workspace(
                workspace,
                "history",
                "--checkpoint",
                "--actor",
                "PALARI-SOFIA",
                "--reason",
                "Activate replayable history for the retirement read-model test.",
                "--json",
            )
            queue = json.loads(
                self.run_cli_in_workspace(workspace, "queue", "--json").stdout
            )
            audit_queue = json.loads(
                self.run_cli_in_workspace(
                    workspace,
                    "queue",
                    "--include-closed",
                    "--json",
                ).stdout
            )
            agent_next = json.loads(
                self.run_cli_in_workspace(
                    workspace,
                    "agent",
                    "next",
                    "--as",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            explicit_start = self.run_cli_in_workspace(
                workspace,
                "agent",
                "start",
                "WORK-RETIRE",
                "--as",
                "PALARI-SOFIA",
                "--json",
                check=False,
            )
            advance = self.run_cli_in_workspace(
                workspace,
                "agent",
                "advance",
                "WORK-RETIRE",
                "--as",
                "PALARI-SOFIA",
                "--json",
                check=False,
            )
            late_receipt = self.run_cli_in_workspace(
                workspace,
                "receipt",
                "record",
                "RECEIPT-LATE",
                "--work-item-id",
                "WORK-RETIRE",
                "--attempt-id",
                "ATTEMPT-LATE",
                "--actor",
                "PALARI-SOFIA",
                "--json",
                check=False,
            )
            inbox_result = self.run_cli_in_workspace(
                workspace,
                "queue",
                "--approval-inbox",
                "--json",
                check=False,
            )
            self.assertEqual(inbox_result.returncode, 0, inbox_result.stderr)
            inbox = json.loads(inbox_result.stdout)
            item = json.loads(
                self.run_cli_in_workspace(
                    workspace,
                    "detail",
                    "WORK-RETIRE",
                    "--json",
                ).stdout
            )

        self.assertEqual(json.loads(update.stdout)["action"], "updated")
        self.assertNotIn("WORK-RETIRE", {entry["id"] for entry in queue["queue"]})
        retired = {entry["id"]: entry for entry in audit_queue["queue"]}["WORK-RETIRE"]
        self.assertEqual(retired["terminal_disposition"], "abandoned")
        self.assertNotIn(
            "WORK-RETIRE",
            {entry["work_item_id"] for entry in agent_next["candidates"]},
        )
        explicit_start_payload = json.loads(explicit_start.stdout)
        self.assertNotEqual(
            explicit_start_payload.get("start", {}).get("status"),
            "claimed",
        )
        self.assertNotEqual(explicit_start_payload.get("status"), "ready")
        advance_payload = json.loads(advance.stdout)
        self.assertEqual(advance_payload["status"], "retired")
        self.assertFalse(advance_payload["can_advance"])
        self.assertFalse(advance_payload["would_mutate"])
        self.assertEqual(advance_payload["stop_boundary"], "terminal")
        self.assertNotEqual(late_receipt.returncode, 0)
        self.assertIn("retired work WORK-RETIRE is audit-only", late_receipt.stderr)
        self.assertNotIn(
            "WORK-RETIRE",
            {entry["id"] for entry in inbox["individual_items"]},
        )
        self.assertEqual(item["work_item"]["status"], "abandoned")

    def test_cli_detail_json(self) -> None:
        result = self.run_cli("detail", "WORK-0004", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["work_item"]["id"], "WORK-0004")
        self.assertEqual(payload["next_step_type"], "human-decision")
        self.assertEqual(payload["human_decision"]["status"], "blocked")
        self.assertEqual(payload["outcome"]["status"], "captured")

    def test_cli_validate_state_and_scope(self) -> None:
        validate = json.loads(self.run_cli("validate", "--json").stdout)
        state = json.loads(self.run_cli("state", "--json").stdout)
        scope = json.loads(
            self.run_cli(
                "scope",
                "WORK-0001",
                "--changed",
                "examples/acme-company-os/workspace.json",
                "--json",
            ).stdout
        )

        self.assertTrue(validate["valid"])
        self.assertEqual(state["attention"]["needs-human-decision"], 3)
        self.assertEqual(state["attention"]["needs-evidence"], 3)
        self.assertNotIn("receipt-ready", state["attention"])
        self.assertEqual(state["top_attention"]["id"], "WORK-0001")
        self.assertEqual(state["top_attention"]["next_step_type"], "human-decision")
        self.assertEqual(
            state["top_attention"]["next_commands"][0],
            "palari detail WORK-0001 --json",
        )
        self.assertEqual(
            state["top_attention"]["agent_handoff_command"],
            "palari agent handoff WORK-0001 --as PALARI-SOFIA --json",
        )
        self.assertEqual(
            state["top_attention"]["agent_loop_command"],
            "palari agent loop WORK-0001 --as PALARI-SOFIA --json",
        )
        self.assertTrue(scope["allowed"])

    def test_cli_state_text_shows_top_attention_command(self) -> None:
        result = self.run_cli("state")

        self.assertIn("Top attention", result.stdout)
        self.assertIn("WORK-0001: Prepare beta launch checklist", result.stdout)
        self.assertIn("step: human-decision", result.stdout)
        self.assertIn(
            "agent handoff: palari agent handoff WORK-0001 --as PALARI-SOFIA --json",
            result.stdout,
        )
        self.assertIn(
            "agent loop: palari agent loop WORK-0001 --as PALARI-SOFIA --json",
            result.stdout,
        )
        self.assertIn("command: palari detail WORK-0001 --json", result.stdout)

    def test_cli_queue_text_shows_agent_handoff_bridge(self) -> None:
        result = self.run_cli("queue")

        self.assertIn(
            "agent handoff: palari agent handoff WORK-0001 --as PALARI-SOFIA --json",
            result.stdout,
        )

    def test_cli_queue_text_labels_heuristic_intensity_as_concern(self) -> None:
        result = self.run_cli_in_workspace(DOGFOOD_WORKSPACE, "queue", "--include-closed")

        self.assertIn("WORK-REPO-0009 [light / R2] Harden dry-run integration validation", result.stdout)
        self.assertIn("intensity concern: heuristic suggests high", result.stdout)
        self.assertIn("Declared intensity is light", result.stdout)

    def test_cli_maintainer_status_json_has_pr_readiness(self) -> None:
        payload = json.loads(self.run_cli("maintainer", "status", "--repo", str(REPO_ROOT), "--json").stdout)
        self.assertIn("pr_readiness", payload)
        self.assertIn("pr_readiness_reason", payload)
        self.assertIn("focused_tests_run", payload)
        self.assertIn("focused_tests_source", payload)

    def test_cli_authoring_on_temp_workspace(self) -> None:
        with self.temp_workspace() as workspace:
            self.run_cli_in_workspace(workspace, "goal", "create", "GOAL-X", "--title", "Improve onboarding")
            self.run_cli_in_workspace(
                workspace,
                "human",
                "create",
                "HUMAN-X",
                "--name",
                "X Human",
                "--list",
                "approval_capabilities=product",
            )
            self.run_cli_in_workspace(
                workspace,
                "palari",
                "create",
                "PALARI-X",
                "--name",
                "Xena",
                "--role",
                "Onboarding partner",
                "--owner-human",
                "HUMAN-X",
                "--list",
                "linked_goals=GOAL-X",
            )
            self.run_cli_in_workspace(
                workspace,
                "source",
                "create",
                "SOURCE-X",
                "--label",
                "Onboarding source note",
                "--kind",
                "note",
                "--provider",
                "local_note",
                "--uri",
                "docs/product/company-os.md",
                "--access-mode",
                "read",
                "--owner-human",
                "HUMAN-X",
                "--data-class",
                "internal",
                "--authority",
                "company_owned",
                "--steward-human",
                "HUMAN-X",
                "--freshness-sla",
                "weekly",
                "--set",
                "selected=true",
                "--set",
                "redaction_required=true",
                "--list",
                "allowed_palaris=PALARI-X",
            )
            self.run_cli_in_workspace(
                workspace,
                "work",
                "create",
                "WORK-X",
                "--title",
                "Draft onboarding note",
                "--goal",
                "GOAL-X",
                "--palari",
                "PALARI-X",
                "--risk",
                "R2",
                "--intensity",
                "standard",
                "--list",
                "allowed_resources=docs/product/company-os.md",
                "--list",
                "allowed_sources=SOURCE-X",
                "--list",
                "allowed_actions=local_write",
                "--list",
                "output_targets=docs/product/company-os.md",
                "--list",
                "forbidden_actions=deploy",
                "--required-approval-capability",
                "product",
            )
            self.run_cli_in_workspace(
                workspace,
                "attempt",
                "record",
                "ATTEMPT-X",
                "--work-item-id",
                "WORK-X",
                "--actor",
                "PALARI-X",
                "--list",
                "commits=head-x",
                "--list",
                "changed_files=docs/product/company-os.md",
            )
            self.run_cli_in_workspace(
                workspace,
                "work",
                "update",
                "WORK-X",
                "--set",
                "current_attempt=ATTEMPT-X",
            )
            self.run_cli_in_workspace(
                workspace,
                "attempt",
                "closeout",
                "ATTEMPT-X",
                "--head-sha",
                "head-x",
                "--cleanliness",
                "clean",
                "--changed",
                "docs/product/company-os.md",
                "--allow-missing-evidence",
            )
            artifact = workspace / "docs" / "product" / "company-os.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("bounded onboarding note\n", encoding="utf-8")
            self.run_cli_in_workspace(
                workspace,
                "receipt",
                "record",
                "RECEIPT-X",
                "--work-item-id",
                "WORK-X",
                "--attempt-id",
                "ATTEMPT-X",
                "--actor",
                "PALARI-X",
                "--list",
                "sources_used=SOURCE-X",
                "--list",
                "actions_taken=read selected source,updated local note",
                "--list",
                "outputs_created=docs/product/company-os.md",
                "--list",
                "not_done=No external writes",
                "--list",
                "undo_refs=revert docs/product/company-os.md",
            )
            self.run_cli_in_workspace(
                workspace,
                "evidence",
                "record",
                "EVIDENCE-X",
                "--work-item-id",
                "WORK-X",
                "--attempt-id",
                "ATTEMPT-X",
                "--head-sha",
                "head-x",
                "--status",
                "passed",
                "--summary",
                "The full unit suite passed for the closed attempt.",
                "--list",
                "commands=python3 -m unittest discover -s tests",
                "--list",
                "artifacts=docs/product/company-os.md",
            )
            self.run_cli_in_workspace(
                workspace,
                "review",
                "record",
                "REVIEW-X",
                "--work-item-id",
                "WORK-X",
                "--reviewed-head",
                "head-x",
                "--reviewer",
                "HUMAN-OPS",
                "--verdict",
                "accept-ready",
            )
            self.run_cli_in_workspace(
                workspace,
                "human-decision",
                "record",
                "HUMAN-DECISION-X",
                "--work-item-id",
                "WORK-X",
                "--human-id",
                "HUMAN-X",
                "--reviewed-head",
                "head-x",
                "--decision",
                "accepted",
                "--status",
                "accepted",
                "--evidence-reference",
                "EVIDENCE-X",
                "--review-reference",
                "REVIEW-X",
            )
            complete = self.run_cli_in_workspace(workspace, "work", "complete", "WORK-X", "--json")
            self.run_cli_in_workspace(
                workspace,
                "outcome",
                "record",
                "OUTCOME-X",
                "--work-item-id",
                "WORK-X",
                "--summary",
                "The onboarding note was accepted.",
            )
            payload = json.loads(complete.stdout)
            final_workspace = Workspace.load(workspace)
            final_detail = detail(final_workspace, "WORK-X")

        self.assertEqual(payload["action"], "completed")
        self.assertEqual(final_detail["work_item"]["status"], "completed")
        self.assertEqual(final_detail["sources"][0]["id"], "SOURCE-X")
        authored_source = final_workspace.source("SOURCE-X")
        self.assertEqual(authored_source.data_class, "internal")
        self.assertEqual(authored_source.authority, "company_owned")
        self.assertEqual(authored_source.steward_human, "HUMAN-X")
        self.assertTrue(authored_source.redaction_required)
        self.assertEqual(final_detail["receipt"]["id"], "RECEIPT-X")
        self.assertEqual(final_detail["outcome"]["id"], "OUTCOME-X")

    def test_cli_complete_rejects_low_risk_receipt_without_evidence(self) -> None:
        with self.temp_workspace() as workspace:
            self.run_cli_in_workspace(
                workspace,
                "work",
                "update",
                "WORK-0007",
                "--list",
                "dependency_ids=",
            )
            result = self.run_cli_in_workspace(
                workspace,
                "work",
                "complete",
                "WORK-0007",
                check=False,
            )
            final_detail = detail(Workspace.load(workspace), "WORK-0007")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("integration_state is not-ready", result.stderr)
        self.assertEqual(final_detail["work_item"]["status"], "active")
        self.assertEqual(final_detail["receipt"]["id"], "RECEIPT-0001")

    def test_cli_acceptance_fails_closed_for_wrong_human_capability(self) -> None:
        with self.temp_workspace() as workspace:
            result = self.run_cli_in_workspace(
                workspace,
                "human-decision",
                "record",
                "BAD-DECISION",
                "--work-item-id",
                "WORK-0001",
                "--human-id",
                "HUMAN-OPS",
                "--reviewed-head",
                "abc1234",
                "--decision",
                "accepted",
                "--status",
                "accepted",
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lacks required approval capability", result.stderr)

    def test_cli_human_decision_update_cannot_bypass_authority(self) -> None:
        with self.temp_workspace() as workspace:
            self.run_cli_in_workspace(
                workspace,
                "human-decision",
                "record",
                "PENDING-DECISION",
                "--work-item-id",
                "WORK-0001",
                "--human-id",
                "HUMAN-OPS",
                "--reviewed-head",
                "abc1234",
                "--decision",
                "needs-changes",
                "--status",
                "recorded",
            )
            result = self.run_cli_in_workspace(
                workspace,
                "human-decision",
                "update",
                "PENDING-DECISION",
                "--set",
                "decision=accepted",
                "--set",
                "status=accepted",
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lacks required approval capability", result.stderr)

    def test_cli_complete_fails_closed_when_quorum_missing(self) -> None:
        with self.temp_workspace() as workspace:
            result = self.run_cli_in_workspace(
                workspace,
                "work",
                "complete",
                "WORK-0001",
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot be completed", result.stderr)

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
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(workspace),
                *args,
            ],
            cwd=REPO_ROOT,
            env=env,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def temp_workspace(self) -> Any:
        return _TempWorkspace()


class MaintainerStatusTests(unittest.TestCase):
    def test_maintainer_status_reports_tests_and_pr_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, timeout=30)
            (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
            (repo / ".gitignore").write_text(".palari-company-os/\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md", ".gitignore"], cwd=repo, check=True, timeout=30)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.email=tests@example.com",
                    "-c",
                    "user.name=Tests",
                    "commit",
                    "-m",
                    "initial",
                ],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                timeout=30,
            )
            state_dir = repo / ".palari-company-os"
            state_dir.mkdir()
            (state_dir / "verification.json").write_text(
                json.dumps(
                    {
                        "commands": [
                            {
                                "command": "python3 -m unittest discover -s tests",
                                "status": "passed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = maintainer_status(repo).to_dict()

        self.assertEqual(payload["pr_readiness"], "needs-upstream")
        self.assertEqual(payload["focused_tests_source"], str(state_dir / "verification.json"))
        self.assertEqual(
            payload["focused_tests_run"],
            ["python3 -m unittest discover -s tests [passed]"],
        )


if __name__ == "__main__":
    unittest.main()


class _TempWorkspace:
    def __enter__(self) -> Path:
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name)
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        (self.path / "workspace.json").write_text(json.dumps(source), encoding="utf-8")
        return self.path

    def __exit__(self, *_args: object) -> None:
        self._directory.cleanup()
