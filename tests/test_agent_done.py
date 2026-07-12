from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_done import agent_done
from palari_company_os.agent_runtime import start_agent
from palari_company_os.workspace import Workspace as Ws


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


class AgentDoneTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.workspace_path = Path(self._tmp)
        src = DOGFOOD / "workspace.json"
        dst = self.workspace_path / "workspace.json"
        shutil.copy2(src, dst)
        palari_dir = self.workspace_path / ".palari"
        if palari_dir.exists():
            shutil.rmtree(palari_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_rejects_r2_work(self) -> None:
        workspace = Ws.load(self.workspace_path)
        result = agent_done(
            workspace,
            self.workspace_path,
            "WORK-0007",
            "PALARI-STEWARD",
        )
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(result["can_done"])
        self.assertIn("R1/light/0-approval", result["message"])

    def test_rejects_already_completed(self) -> None:
        workspace = Ws.load(self.workspace_path)
        result = agent_done(
            workspace,
            self.workspace_path,
            "WORK-0001",
            "PALARI-STEWARD",
        )
        self.assertEqual(result["status"], "already-completed")
        self.assertFalse(result["can_done"])

    def test_completes_r1_light_work(self) -> None:
        from palari_company_os.authoring import create_record

        workspace = Ws.load(self.workspace_path)
        work_record = {
            "id": "WORK-TEST-DONE",
            "title": "Test done shortcut",
            "palari": "PALARI-STEWARD",
            "goal": "GOAL-REPO-0001",
            "workbench_id": "WORKBENCH-REPO-FOUNDATION",
            "risk": "R1",
            "intensity": "light",
            "required_approval_count": 0,
            "scope": "Test scope",
            "acceptance_target": "Test acceptance",
            "status": "active",
            "allowed_resources": ["README.md"],
            "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
            "output_targets": ["README.md"],
            "forbidden_actions": ["deploy"],
            "verification_expectations": ["echo ok"],
        }
        create_record(
            str(self.workspace_path),
            "work",
            work_record,
            command="test",
        )

        workspace = Ws.load(self.workspace_path)
        start_agent(
            workspace,
            self.workspace_path,
            "WORK-TEST-DONE",
            "PALARI-STEWARD",
            "execute",
        )

        workspace = Ws.load(self.workspace_path)
        result = agent_done(
            workspace,
            self.workspace_path,
            "WORK-TEST-DONE",
            "PALARI-STEWARD",
            changed=["README.md"],
        )
        self.assertEqual(result["status"], "done")
        self.assertTrue(result["can_done"])
        self.assertEqual(result["attempt_id"], "ATTEMPT-DONE-WORK-TEST-DONE")
        self.assertEqual(result["receipt_id"], "RECEIPT-DONE-WORK-TEST-DONE")

        workspace = Ws.load(self.workspace_path)
        work = workspace.work_item("WORK-TEST-DONE")
        self.assertIsNotNone(work)
        assert work is not None
        self.assertEqual(work.status, "completed")


if __name__ == "__main__":
    unittest.main()
