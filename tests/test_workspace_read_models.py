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

from palari_company_os.read_models import detail, queue_items
from palari_company_os.scope import check_scope
from palari_company_os.workspace import Workspace, WorkspaceError


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class WorkspaceReadModelTests(unittest.TestCase):
    def test_example_workspace_loads(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        self.assertEqual(workspace.name, "Acme Company OS Example")
        self.assertEqual(len(workspace.goals), 2)
        self.assertEqual(len(workspace.palaris), 2)
        self.assertEqual(len(workspace.work_items), 4)

    def test_queue_prioritizes_human_decisions(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        items = queue_items(workspace)
        by_id = {item.id: item for item in items}

        self.assertEqual(items[0].attention, "needs-human-decision")
        self.assertEqual(by_id["WORK-0001"].attention, "needs-human-decision")
        self.assertIn("Review is accept-ready", by_id["WORK-0001"].why)
        self.assertEqual(by_id["WORK-0001"].approval_progress, "0/1")
        self.assertFalse(by_id["WORK-0001"].ai_safe_to_proceed)
        self.assertEqual(by_id["WORK-0002"].attention, "needs-human-decision")
        self.assertIn("DECISION-0001", by_id["WORK-0002"].why)
        self.assertEqual(by_id["WORK-0002"].recommended_intensity, "high")
        self.assertEqual(by_id["WORK-0002"].approval_progress, "0/2")
        self.assertEqual(by_id["WORK-0003"].attention, "needs-evidence")
        self.assertTrue(by_id["WORK-0003"].ai_safe_to_proceed)
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


if __name__ == "__main__":
    unittest.main()
