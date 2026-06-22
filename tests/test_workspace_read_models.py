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

from palari_company_os.maintainer import status as maintainer_status
from palari_company_os.read_models import (
    active_parallel_work,
    coordination_warnings,
    detail,
    queue_items,
)
from palari_company_os.scope import check_scope
from palari_company_os.workspace import Workspace


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"
DOGFOOD_WORKSPACE = REPO_ROOT / "workspaces" / "palari-company-os"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "workspaces"


class WorkspaceReadModelTests(unittest.TestCase):
    def test_example_workspace_loads(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        self.assertEqual(workspace.name, "Acme Company OS Example")
        self.assertEqual(len(workspace.goals), 2)
        self.assertEqual(len(workspace.palaris), 2)
        self.assertEqual(len(workspace.sources), 1)
        self.assertEqual(len(workspace.workbenches), 2)
        self.assertEqual(len(workspace.work_items), 7)
        self.assertEqual(len(workspace.receipts), 1)

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

        self.assertEqual(queue["WORK-REPO-0005"].attention, "needs-human-decision")
        self.assertEqual(queue["WORK-REPO-0005"].next_step_type, "human-decision")
        self.assertEqual(
            queue["WORK-REPO-0005"].next_commands[0],
            "palari decision guide DECISION-REPO-0001 --json",
        )
        self.assertEqual(queue["WORK-REPO-0003"].attention, "needs-review")
        self.assertEqual(queue["WORK-REPO-0003"].review_state, "missing")
        self.assertFalse(queue["WORK-REPO-0003"].ai_safe_to_proceed)
        self.assertEqual(
            queue["WORK-REPO-0003"].next_commands[0],
            "palari review guide WORK-REPO-0003 --json",
        )
        self.assertEqual(queue["WORK-REPO-0004"].attention, "ready-for-ai-work")
        self.assertFalse(queue["WORK-REPO-0004"].ai_safe_to_proceed)
        self.assertIn("Inspect the high-risk scope", queue["WORK-REPO-0004"].next_action)
        self.assertEqual(
            queue["WORK-REPO-0004"].next_commands[0],
            "palari detail WORK-REPO-0004 --json",
        )
        self.assertEqual(queue["WORK-REPO-0006"].attention, "receipt-ready")
        self.assertEqual(queue["WORK-REPO-0006"].next_step_type, "review-handoff")
        self.assertEqual(queue["WORK-REPO-0006"].receipt_state, "ready")
        self.assertEqual(queue["WORK-REPO-0006"].evidence_state, "passed")
        self.assertEqual(queue["WORK-REPO-0006"].approval_progress, "0/0")
        self.assertFalse(queue["WORK-REPO-0006"].ai_safe_to_proceed)
        self.assertEqual(
            queue["WORK-REPO-0006"].next_commands[0],
            "palari review guide WORK-REPO-0006 --json",
        )

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
        self.assertIn("DECISION-0001", by_id["WORK-0002"].why)
        self.assertEqual(
            by_id["WORK-0002"].next_commands[0],
            "palari decision guide DECISION-0001 --json",
        )
        self.assertEqual(by_id["WORK-0002"].recommended_intensity, "high")
        self.assertEqual(by_id["WORK-0002"].approval_progress, "0/2")
        self.assertEqual(by_id["WORK-0003"].attention, "needs-evidence")
        self.assertEqual(by_id["WORK-0003"].next_step_type, "check-active-proof")
        self.assertTrue(by_id["WORK-0003"].ai_safe_to_proceed)
        self.assertEqual(
            by_id["WORK-0003"].next_commands[:2],
            [
                "palari agent check WORK-0003 --as PALARI-SOFIA --json",
                "palari agent finish WORK-0003 --as PALARI-SOFIA --json",
            ],
        )
        self.assertEqual(by_id["WORK-0005"].attention, "needs-evidence")
        self.assertEqual(by_id["WORK-0005"].evidence_state, "stale")
        self.assertEqual(
            by_id["WORK-0005"].next_commands[:2],
            [
                "palari agent check WORK-0005 --as PALARI-SOFIA --json",
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
        self.assertEqual(by_id["WORK-0007"].attention, "receipt-ready")
        self.assertEqual(by_id["WORK-0007"].next_step_type, "review-handoff")
        self.assertEqual(by_id["WORK-0007"].receipt_state, "ready")
        self.assertEqual(by_id["WORK-0007"].integration_state, "receipt-ready")
        self.assertIn("Review the output", by_id["WORK-0007"].next_action)
        self.assertEqual(
            by_id["WORK-0007"].next_commands[0],
            "palari review guide WORK-0007 --json",
        )
        self.assertEqual(by_id["WORK-0004"].attention, "closed")

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
        self.assertEqual(payload["attention"], "receipt-ready")
        self.assertEqual(payload["next_step_type"], "review-handoff")
        self.assertEqual(payload["next_commands"][0], "palari review guide WORK-0007 --json")
        self.assertEqual(payload["parent_work_item"]["id"], "WORK-0001")
        self.assertEqual(payload["dependencies"][0]["id"], "WORK-0003")
        self.assertEqual(
            payload["agent_commands"]["brief"],
            "palari agent brief WORK-0007 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            payload["agent_commands"]["finish"],
            "palari agent finish WORK-0007 --as PALARI-SOFIA --json",
        )

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

    def test_receipt_ready_queue_state_for_light_work(self) -> None:
        workspace = Workspace.load(FIXTURES / "valid-source-receipt-loop.json")
        item = queue_items(workspace)[0]

        self.assertEqual(item.attention, "receipt-ready")
        self.assertEqual(item.receipt_state, "ready")
        self.assertEqual(item.integration_state, "receipt-ready")
        self.assertFalse(item.ai_safe_to_proceed)
        self.assertIn("actions, outputs, and limits", item.why)

    def test_high_risk_work_still_requires_governance_even_with_receipt(self) -> None:
        def make_high_risk(data: dict[str, object]) -> None:
            data["work_items"][0]["risk"] = "R3"
            data["work_items"][0]["intensity"] = "standard"

        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            make_high_risk,
        )
        item = queue_items(workspace)[0]

        self.assertEqual(item.receipt_state, "ready")
        self.assertEqual(item.attention, "needs-evidence")
        self.assertEqual(item.integration_state, "not-ready")

    def test_external_write_receipt_does_not_use_light_receipt_ready_path(self) -> None:
        def allow_external_write(data: dict[str, object]) -> None:
            data["work_items"][0]["allowed_actions"] = ["external_write"]
            data["receipts"][0]["external_writes"] = ["google_drive:doc-1"]

        workspace = self.modified_fixture_workspace(
            "valid-source-receipt-loop.json",
            allow_external_write,
        )
        item = queue_items(workspace)[0]

        self.assertEqual(item.receipt_state, "ready")
        self.assertEqual(item.attention, "needs-evidence")

    def test_evidence_staleness_blocks_review(self) -> None:
        workspace = self.modified_workspace(
            lambda data: data["attempts"][0].update({"commits": ["abc1234", "newhead"]})
        )
        item = {item.id: item for item in queue_items(workspace)}["WORK-0001"]
        self.assertEqual(item.attention, "needs-evidence")
        self.assertEqual(item.evidence_state, "stale")
        self.assertIn("stale", item.why)

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
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            workspace_file.write_text(json.dumps(source), encoding="utf-8")
            return Workspace.load(workspace_file)

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

    def test_cli_detail_json(self) -> None:
        result = self.run_cli("detail", "WORK-0004", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["work_item"]["id"], "WORK-0004")
        self.assertEqual(payload["next_step_type"], "closed")
        self.assertEqual(payload["human_decision"]["status"], "accepted")
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
        self.assertEqual(state["attention"]["needs-human-decision"], 2)
        self.assertEqual(state["attention"]["receipt-ready"], 1)
        self.assertEqual(state["top_attention"]["id"], "WORK-0001")
        self.assertEqual(state["top_attention"]["next_step_type"], "human-decision")
        self.assertEqual(
            state["top_attention"]["next_commands"][0],
            "palari detail WORK-0001 --json",
        )
        self.assertTrue(scope["allowed"])

    def test_cli_state_text_shows_top_attention_command(self) -> None:
        result = self.run_cli("state")

        self.assertIn("Top attention", result.stdout)
        self.assertIn("WORK-0001: Prepare beta launch checklist", result.stdout)
        self.assertIn("step: human-decision", result.stdout)
        self.assertIn("command: palari detail WORK-0001 --json", result.stdout)

    def test_cli_maintainer_status_json_has_pr_readiness(self) -> None:
        payload = json.loads(self.run_cli("maintainer", "status", "--repo", str(REPO_ROOT), "--json").stdout)
        self.assertIn("pr_readiness", payload)
        self.assertIn("pr_readiness_reason", payload)
        self.assertIn("focused_tests_run", payload)
        self.assertIn("focused_tests_source", payload)

    def test_cli_authoring_and_lifecycle_on_temp_workspace(self) -> None:
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
                "--set",
                "selected=true",
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
            self.run_cli_in_workspace(workspace, "work", "update", "WORK-X", "--set", "current_attempt=ATTEMPT-X")
            self.run_cli_in_workspace(
                workspace,
                "lifecycle",
                "evidence",
                "EVIDENCE-X",
                "--work-item-id",
                "WORK-X",
                "--attempt-id",
                "ATTEMPT-X",
                "--head-sha",
                "head-x",
                "--status",
                "passed",
                "--list",
                "commands=python3 -m unittest discover -s tests",
            )
            self.run_cli_in_workspace(
                workspace,
                "lifecycle",
                "review",
                "REVIEW-X",
                "--work-item-id",
                "WORK-X",
                "--reviewed-head",
                "head-x",
                "--reviewer",
                "HUMAN-X",
                "--verdict",
                "accept-ready",
            )
            self.run_cli_in_workspace(
                workspace,
                "lifecycle",
                "decide",
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
            complete = self.run_cli_in_workspace(workspace, "lifecycle", "complete", "WORK-X", "--json")
            self.run_cli_in_workspace(
                workspace,
                "lifecycle",
                "outcome",
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
        self.assertEqual(final_detail["receipt"]["id"], "RECEIPT-X")
        self.assertEqual(final_detail["outcome"]["id"], "OUTCOME-X")

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
