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
from palari_company_os.read_models import detail, queue_items
from palari_company_os.scope import check_scope
from palari_company_os.store import load_store, migrate_data
from palari_company_os.workspace import Workspace, WorkspaceError


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class WorkspaceReadModelTests(unittest.TestCase):
    def test_example_workspace_loads(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        self.assertEqual(workspace.name, "Acme Company OS Example")
        self.assertEqual(len(workspace.goals), 2)
        self.assertEqual(len(workspace.palaris), 2)
        self.assertEqual(len(workspace.work_items), 6)

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
        self.assertEqual(by_id["WORK-0002"].recommended_intensity, "high")
        self.assertEqual(by_id["WORK-0002"].approval_progress, "0/2")
        self.assertEqual(by_id["WORK-0003"].attention, "needs-evidence")
        self.assertTrue(by_id["WORK-0003"].ai_safe_to_proceed)
        self.assertEqual(by_id["WORK-0005"].attention, "needs-evidence")
        self.assertEqual(by_id["WORK-0005"].evidence_state, "stale")
        self.assertEqual(by_id["WORK-0006"].attention, "needs-review")
        self.assertEqual(by_id["WORK-0006"].review_state, "stale")
        self.assertEqual(by_id["WORK-0004"].attention, "closed")

    def test_detail_assembles_related_records(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        payload = detail(workspace, "WORK-0001")

        self.assertEqual(payload["work_item"]["title"], "Prepare beta launch checklist")
        self.assertEqual(payload["goal"]["id"], "GOAL-0001")
        self.assertEqual(payload["palari"]["name"], "Sofia")
        self.assertEqual(payload["evidence"]["status"], "passed")
        self.assertEqual(payload["review"]["verdict"], "accept-ready")
        self.assertIsNone(payload["human_decision"])
        self.assertEqual(payload["attention"], "needs-human-decision")
        self.assertEqual(payload["safety"]["evidence_state"], "passed")
        self.assertEqual(payload["safety"]["review_state"], "accept-ready")
        self.assertEqual(payload["safety"]["approval_progress"], "0/1")

    def test_workspace_validation_rejects_missing_refs(self) -> None:
        broken_path = WORKSPACE / "broken-workspace.json"
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        source["work_items"][0]["goal"] = "GOAL-MISSING"
        broken_path.write_text(json.dumps(source), encoding="utf-8")
        try:
            with self.assertRaises(WorkspaceError):
                Workspace.load(broken_path)
        finally:
            broken_path.unlink(missing_ok=True)

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

    def modified_workspace(self, mutate: object) -> Workspace:
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
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
        self.assertTrue(scope["allowed"])

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

    def test_migration_adds_schema_version_to_legacy_workspace(self) -> None:
        legacy = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        legacy.pop("schema_version")
        migrated, changes = migrate_data(legacy)
        self.assertEqual(migrated["schema_version"], 1)
        self.assertIn("Added schema_version: 1.", changes)

    def test_schema_version_zero_requires_migration(self) -> None:
        legacy = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        legacy["schema_version"] = 0
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            workspace_file.write_text(json.dumps(legacy), encoding="utf-8")
            with self.assertRaises(WorkspaceError):
                Workspace.load(workspace_file)
        migrated, changes = migrate_data(legacy)
        self.assertEqual(migrated["schema_version"], 1)
        self.assertIn("Upgraded schema_version from 0 to 1.", changes)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "palari_company_os", "--workspace", str(WORKSPACE), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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
        )

    def temp_workspace(self) -> Any:
        return _TempWorkspace()


class MaintainerStatusTests(unittest.TestCase):
    def test_maintainer_status_reports_tests_and_pr_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
            (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
            (repo / ".gitignore").write_text(".palari-company-os/\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md", ".gitignore"], cwd=repo, check=True)
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
