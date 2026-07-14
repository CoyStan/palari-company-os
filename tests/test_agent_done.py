from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_done import agent_done
from palari_company_os.agent_runtime import release_agent, start_agent
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
        (self.workspace_path / "README.md").write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.workspace_path)], check=True)
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(["git", "-C", str(self.workspace_path), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "commit", "-qm", "governed work"],
            check=True,
        )
        (self.workspace_path / "README.md").write_text("after\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "commit", "-qm", "bounded output"],
            check=True,
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

    def test_foreign_claim_blocks_before_creating_proof(self) -> None:
        self._create_light_work("WORK-TEST-FOREIGN")
        workspace = Ws.load(self.workspace_path)
        start_agent(
            workspace,
            self.workspace_path,
            "WORK-TEST-FOREIGN",
            "PALARI-STEWARD",
            "execute",
        )
        claim_path = self.workspace_path / ".palari" / "claims" / "WORK-TEST-FOREIGN.json"
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        claim["claimed_by"] = "PALARI-ARCHITECT"
        claim_path.write_text(json.dumps(claim), encoding="utf-8")

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            "WORK-TEST-FOREIGN",
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        workspace = Ws.load(self.workspace_path)
        self.assertNotIn(
            "ATTEMPT-DONE-WORK-TEST-FOREIGN", {item.id for item in workspace.attempts}
        )

    def test_declared_head_must_match_verified_git_head(self) -> None:
        work_id = "WORK-TEST-HEAD"
        self._create_light_work(work_id)
        self._commit_bounded_output()
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            head_sha="not-the-current-head",
            changed=["README.md"],
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("does not match", result["message"])
        workspace = Ws.load(self.workspace_path)
        self.assertNotIn(
            f"ATTEMPT-DONE-{work_id}", {item.id for item in workspace.attempts}
        )

    def test_resumes_matching_partial_attempt(self) -> None:
        from palari_company_os.authoring import create_record, update_record

        work_id = "WORK-TEST-RESUME"
        self._create_light_work(work_id)
        attempt_id = f"ATTEMPT-DONE-{work_id}"
        create_record(
            str(self.workspace_path),
            "attempt",
            {
                "id": attempt_id,
                "work_item_id": work_id,
                "actor": "PALARI-STEWARD",
                "status": "active",
            },
            command="test partial",
        )
        update_record(
            str(self.workspace_path),
            "work",
            work_id,
            {"current_attempt": attempt_id},
            command="test partial",
        )
        self._commit_bounded_output()
        workspace = Ws.load(self.workspace_path)
        start_agent(workspace, self.workspace_path, work_id, "PALARI-STEWARD", "execute")

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            changed=["README.md"],
        )

        self.assertEqual(result["status"], "done")
        self.assertIn(
            {"step": "attempt-record", "id": attempt_id, "status": "resumed"},
            result["steps"],
        )

    def _create_light_work(self, work_id: str) -> None:
        from palari_company_os.authoring import create_record

        create_record(
            str(self.workspace_path),
            "work",
            {
                "id": work_id,
                "title": "Test done safety",
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
            },
            command="test",
        )

    def _commit_bounded_output(self) -> None:
        (self.workspace_path / "README.md").write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.workspace_path)], check=True)
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(["git", "-C", str(self.workspace_path), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "commit", "-qm", "governed work"],
            check=True,
        )
        (self.workspace_path / "README.md").write_text("after\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "commit", "-qm", "bounded output"],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
