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
from palari_company_os.agent_runtime import _git_baseline_hash, release_agent, start_agent
from palari_company_os.workspace import Workspace as Ws
from tests.workspace_fixture import write_portable_agent_workspace


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


class AgentDoneTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.workspace_path = Path(self._tmp)
        write_portable_agent_workspace(
            DOGFOOD / "workspace.json",
            self.workspace_path / "workspace.json",
        )
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
        self._initialize_repo()
        workspace = Ws.load(self.workspace_path)
        start_agent(
            workspace,
            self.workspace_path,
            "WORK-TEST-DONE",
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_readme_change()

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
        self._initialize_repo()
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_readme_change()

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

    def test_commit_range_deduplicates_paths_changed_in_multiple_commits(self) -> None:
        work_id = "WORK-TEST-DEDUPLICATE-RANGE"
        self._create_light_work(work_id)
        self._initialize_repo()
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_readme_change()
        self._commit_path("README.md", "after again\n", "second bounded output")

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            changed=["README.md"],
        )

        self.assertEqual(result["status"], "done")
        attempt = next(
            item
            for item in Ws.load(self.workspace_path).attempts
            if item.id == f"ATTEMPT-DONE-{work_id}"
        )
        self.assertEqual(attempt.changed_files, ["README.md"])

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
        self._initialize_repo()
        workspace = Ws.load(self.workspace_path)
        start_agent(workspace, self.workspace_path, work_id, "PALARI-STEWARD", "execute")
        self._commit_readme_change()

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

    def test_commit_created_before_claim_is_not_attributed_to_agent(self) -> None:
        work_id = "WORK-TEST-PRECLAIM"
        self._create_light_work(work_id)
        self._initialize_repo()
        self._commit_readme_change()
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
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("since the claim started", result["message"])

    def test_release_restart_cannot_hide_out_of_scope_commit(self) -> None:
        work_id = "WORK-TEST-RANGE"
        self._create_light_work(work_id)
        self._initialize_repo()
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_path("docs/.palari/note.txt", "outside boundary\n", "outside change")
        release_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
        )
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_readme_change()

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("docs/.palari/note.txt", result["message"])

    def test_reverted_out_of_scope_commit_remains_in_claim_range(self) -> None:
        work_id = "WORK-TEST-REVERTED-RANGE"
        self._create_light_work(work_id)
        self._initialize_repo()
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_path("outside.txt", "temporary outside change\n", "outside change")
        (self.workspace_path / "outside.txt").unlink()
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "add", "--", "outside.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "commit", "-qm", "revert outside change"],
            check=True,
        )
        self._commit_readme_change()

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("outside.txt", result["message"])

    def test_tampered_claim_baseline_head_is_rejected_before_attribution(self) -> None:
        work_id = "WORK-TEST-TAMPERED-BASELINE"
        self._create_light_work(work_id)
        self._initialize_repo()
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_path("outside.txt", "outside boundary\n", "outside change")
        outside_head = self._git_head()
        claim_path = self.workspace_path / ".palari" / "claims" / f"{work_id}.json"
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        claim["git_baseline"]["head_sha"] = outside_head
        claim_path.write_text(json.dumps(claim), encoding="utf-8")
        self._commit_readme_change()

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("git_baseline_hash", result["message"])
        self.assertNotIn(
            f"ATTEMPT-DONE-{work_id}",
            {item.id for item in Ws.load(self.workspace_path).attempts},
        )

    def test_rehashed_claim_cannot_override_persisted_baseline(self) -> None:
        work_id = "WORK-TEST-REHASHED-BASELINE"
        self._create_light_work(work_id)
        self._initialize_repo()
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_path("outside.txt", "outside boundary\n", "outside change")
        claim_path = self.workspace_path / ".palari" / "claims" / f"{work_id}.json"
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        claim["git_baseline"]["head_sha"] = self._git_head()
        claim["git_baseline_hash"] = _git_baseline_hash(claim["git_baseline"])
        claim_path.write_text(json.dumps(claim), encoding="utf-8")
        self._commit_readme_change()

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("persisted baseline", result["message"])
        self.assertNotIn(
            f"ATTEMPT-DONE-{work_id}",
            {item.id for item in Ws.load(self.workspace_path).attempts},
        )

    def test_coordinated_claim_and_baseline_rehash_cannot_override_git_witness(self) -> None:
        work_id = "WORK-TEST-COORDINATED-BASELINE"
        self._create_light_work(work_id)
        self._initialize_repo()
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_path("outside.txt", "outside boundary\n", "outside change")
        outside_head = self._git_head()
        claim_path = self.workspace_path / ".palari" / "claims" / f"{work_id}.json"
        baseline_path = claim_path.with_suffix(".baseline")
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        persisted = json.loads(baseline_path.read_text(encoding="utf-8"))
        for record in (claim, persisted):
            record["git_baseline"]["head_sha"] = outside_head
            record["git_baseline_hash"] = _git_baseline_hash(record["git_baseline"])
        claim_path.write_text(json.dumps(claim), encoding="utf-8")
        baseline_path.write_text(json.dumps(persisted), encoding="utf-8")
        self._commit_readme_change()

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("Git witness", result["message"])
        self.assertNotIn(
            f"ATTEMPT-DONE-{work_id}",
            {item.id for item in Ws.load(self.workspace_path).attempts},
        )

    def test_git_witness_rewrite_keeps_original_head_in_reflog(self) -> None:
        work_id = "WORK-TEST-REWRITTEN-WITNESS"
        self._create_light_work(work_id)
        self._initialize_repo()
        start_agent(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self._commit_path("outside.txt", "outside boundary\n", "outside change")
        outside_head = self._git_head()
        claim_path = self.workspace_path / ".palari" / "claims" / f"{work_id}.json"
        baseline_path = claim_path.with_suffix(".baseline")
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        persisted = json.loads(baseline_path.read_text(encoding="utf-8"))
        for record in (claim, persisted):
            record["git_baseline"]["head_sha"] = outside_head
            record["git_baseline_hash"] = _git_baseline_hash(record["git_baseline"])
        claim_path.write_text(json.dumps(claim), encoding="utf-8")
        baseline_path.write_text(json.dumps(persisted), encoding="utf-8")
        subprocess.run(
            [
                "git",
                "-C",
                str(self.workspace_path),
                "update-ref",
                claim["git_witness_ref"],
                outside_head,
            ],
            check=True,
        )
        self._commit_readme_change()

        result = agent_done(
            Ws.load(self.workspace_path),
            self.workspace_path,
            work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("Git witness history", result["message"])

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

    def _initialize_repo(self) -> None:
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

    def _commit_readme_change(self) -> None:
        (self.workspace_path / "README.md").write_text("after\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "commit", "-qm", "bounded output"],
            check=True,
        )

    def _commit_path(self, path: str, content: str, message: str) -> None:
        target = self.workspace_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "add", "--", path], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.workspace_path), "commit", "-qm", message], check=True
        )

    def _git_head(self) -> str:
        return subprocess.run(
            ["git", "-C", str(self.workspace_path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()


if __name__ == "__main__":
    unittest.main()
