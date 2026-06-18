from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.read_models import detail, queue_items
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
        self.assertEqual(by_id["WORK-0002"].attention, "needs-human-decision")
        self.assertIn("DECISION-0001", by_id["WORK-0002"].why)
        self.assertEqual(by_id["WORK-0003"].attention, "needs-evidence")
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
