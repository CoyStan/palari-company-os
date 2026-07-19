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

from palari_company_os.agent_runtime import start_agent
from palari_company_os.git_hooks import install_git_hook, pre_commit
from palari_company_os.store import WorkspaceStore, write_store
from palari_company_os.workspace import Workspace


WORK_ID = "WORK-GIT-BOUNDARY"
PALARI_ID = "PALARI-GIT"
ALLOWED_PATH = "README.md"


def _write_minimal_workspace(path: Path) -> None:
    """Write only the current records needed to compile one execute claim."""

    data = {
        "schema_version": 2,
        "name": "Git Hook Boundary Test",
        "goals": [
            {
                "id": "GOAL-GIT",
                "title": "Protect the Git boundary",
                "status": "active",
                "linked_palaris": [PALARI_ID],
                "linked_work": [WORK_ID],
            }
        ],
        "humans": [{"id": "HUMAN-GIT", "name": "Git Test Human"}],
        "palaris": [
            {
                "id": PALARI_ID,
                "name": "Git Test Agent",
                "role": "Boundary worker",
                "owner_human": "HUMAN-GIT",
                "linked_goals": ["GOAL-GIT"],
                "active_work": [WORK_ID],
            }
        ],
        "sources": [],
        "work_items": [
            {
                "id": WORK_ID,
                "title": "Exercise the Git boundary",
                "goal": "GOAL-GIT",
                "palari": PALARI_ID,
                "risk": "R1",
                "intensity": "light",
                "required_approval_count": 0,
                "scope": "Change only the declared repository file.",
                "acceptance_target": "The commit boundary rejects every other path.",
                "status": "active",
                "allowed_resources": [ALLOWED_PATH],
                "allowed_sources": [],
                "output_targets": [ALLOWED_PATH],
                "forbidden_actions": ["deploy"],
                "verification_expectations": ["focused Git-hook test passes"],
            }
        ],
        "attempts": [],
        "evidence_runs": [],
        "review_verdicts": [],
        "human_decisions": [],
        "receipts": [],
        "decisions": [],
        "outcomes": [],
    }
    write_store(
        WorkspaceStore(
            data_path=path / "workspace.json",
            data=data,
        )
    )


class GitHooksTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.repo = Path(self._tmp)
        self.workspace_path = self.repo / "workspace"
        self.workspace_path.mkdir()
        _write_minimal_workspace(self.workspace_path)
        (self.repo / ALLOWED_PATH).write_text("initial\n", encoding="utf-8")
        self._git_init()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _git_init(self) -> None:
        environment = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
        subprocess.run(
            ["git", "init"],
            cwd=self.repo,
            check=True,
            env=environment,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.repo,
            check=True,
            env=environment,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo,
            check=True,
            env=environment,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=self.repo,
            check=True,
            env=environment,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "initial fixture"],
            cwd=self.repo,
            check=True,
            env=environment,
            capture_output=True,
        )

    def _start_current_claim(self) -> Path:
        result = start_agent(
            Workspace.load(self.workspace_path),
            self.workspace_path,
            WORK_ID,
            PALARI_ID,
            "execute",
        )
        self.assertEqual(result["start"]["status"], "claimed")
        claim_path = self.workspace_path / ".palari" / "claims" / f"{WORK_ID}.json"
        self.assertTrue(claim_path.is_file())
        return claim_path

    def _stage(self, path: str) -> None:
        subprocess.run(
            ["git", "add", "--", path],
            cwd=self.repo,
            check=True,
            capture_output=True,
        )

    def test_install_is_executable_and_idempotent(self) -> None:
        installed = install_git_hook(self.repo, self.workspace_path)
        unchanged = install_git_hook(self.repo, self.workspace_path)
        hook_path = self.repo / ".git" / "hooks" / "pre-commit"

        self.assertEqual(installed["status"], "installed")
        self.assertTrue(installed["changed"])
        self.assertEqual(unchanged["status"], "unchanged")
        self.assertFalse(unchanged["changed"])
        self.assertTrue(os.access(hook_path, os.X_OK))
        self.assertIn("palari git hook", hook_path.read_text(encoding="utf-8"))

    def test_install_preserves_an_unmanaged_hook(self) -> None:
        hook_path = self.repo / ".git" / "hooks" / "pre-commit"
        original = "#!/bin/sh\n# project-owned hook\nexit 0\n"
        hook_path.write_text(original, encoding="utf-8")
        hook_path.chmod(0o755)

        result = install_git_hook(self.repo, self.workspace_path)

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["changed"])
        self.assertEqual(hook_path.read_text(encoding="utf-8"), original)

    def test_pre_commit_allows_one_bounded_change(self) -> None:
        self._start_current_claim()
        (self.repo / ALLOWED_PATH).write_text("bounded change\n", encoding="utf-8")
        self._stage(ALLOWED_PATH)

        result = pre_commit(self.workspace_path, cwd=self.repo)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["staged"], [ALLOWED_PATH])
        self.assertEqual(result["outside"], [])
        self.assertEqual(result["claim"], WORK_ID)

    def test_pre_commit_denies_one_out_of_scope_change(self) -> None:
        self._start_current_claim()
        outside_path = "outside.txt"
        (self.repo / outside_path).write_text("outside\n", encoding="utf-8")
        self._stage(outside_path)

        result = pre_commit(self.workspace_path, cwd=self.repo)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["outside"], [outside_path])

    def test_pre_commit_denies_a_tampered_packet(self) -> None:
        claim_path = self._start_current_claim()
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        packet_path = self.workspace_path / claim["packet_path"]
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["context_hash"] = "sha256:tampered"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        (self.repo / ALLOWED_PATH).write_text("bounded change\n", encoding="utf-8")
        self._stage(ALLOWED_PATH)

        result = pre_commit(self.workspace_path, cwd=self.repo)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "invalid-claim")
        self.assertTrue(any("context_hash" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
