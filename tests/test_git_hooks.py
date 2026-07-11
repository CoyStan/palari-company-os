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

from palari_company_os.git_hooks import (
    git_hook_status,
    install_git_hook,
    pre_commit,
)
from palari_company_os.workspace import Workspace as Ws


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


class GitHooksTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.workspace_path = Path(self._tmp) / "ws"
        self.workspace_path.mkdir()
        shutil.copy2(DOGFOOD / "workspace.json", self.workspace_path / "workspace.json")
        palari_dir = self.workspace_path / ".palari"
        if palari_dir.exists():
            shutil.rmtree(palari_dir)

        self._git_init()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _git_init(self) -> None:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
        }
        subprocess.run(["git", "init"], cwd=self._tmp, check=True, env=env, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=self._tmp, check=True, env=env, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=self._tmp,
            check=True,
            env=env,
            capture_output=True,
        )
        (Path(self._tmp) / "README.md").write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self._tmp, check=True, env=env, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=self._tmp, check=True, env=env, capture_output=True
        )

    def _start_claim(self) -> None:
        from palari_company_os.agent_runtime import start_agent
        from palari_company_os.authoring import create_record

        create_record(
            str(self.workspace_path),
            "work",
            {
                "id": "WORK-TEST-GIT",
                "title": "Test git hooks",
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
        ws = Ws.load(self.workspace_path)
        result = start_agent(ws, self.workspace_path, "WORK-TEST-GIT", "PALARI-STEWARD", "execute")
        assert result.get("start", {}).get("status") == "claimed", f"Claim failed: {result.get('start', {})}"
        claims_dir = self.workspace_path / ".palari" / "claims"
        assert claims_dir.exists() and any(claims_dir.glob("*.json")), "No claim file created"

    def test_install_creates_pre_commit_hook(self) -> None:
        result = install_git_hook(self._tmp, self.workspace_path)
        self.assertEqual(result["status"], "installed")
        self.assertTrue(result["changed"])
        hook_path = Path(self._tmp) / ".git" / "hooks" / "pre-commit"
        self.assertTrue(hook_path.exists())
        content = hook_path.read_text()
        self.assertIn("palari git hook", content)
        self.assertIn("git pre-commit", content)
        self.assertTrue(os.access(hook_path, os.X_OK))

    def test_install_is_idempotent(self) -> None:
        install_git_hook(self._tmp, self.workspace_path)
        result = install_git_hook(self._tmp, self.workspace_path)
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["changed"])

    def test_install_then_remove(self) -> None:
        install_git_hook(self._tmp, self.workspace_path)
        result = install_git_hook(self._tmp, self.workspace_path, remove=True)
        self.assertEqual(result["status"], "removed")
        self.assertTrue(result["changed"])
        hook_path = Path(self._tmp) / ".git" / "hooks" / "pre-commit"
        self.assertFalse(hook_path.exists())

    def test_remove_when_not_installed(self) -> None:
        result = install_git_hook(self._tmp, self.workspace_path, remove=True)
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["changed"])

    def test_install_refuses_to_overwrite_unmanaged_hook(self) -> None:
        hook_path = Path(self._tmp) / ".git" / "hooks" / "pre-commit"
        hook_path.parent.mkdir(parents=True, exist_ok=True)
        hook_path.write_text("# custom hook\nexit 0\n", encoding="utf-8")
        result = install_git_hook(self._tmp, self.workspace_path)
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["changed"])

    def test_status_shows_installed(self) -> None:
        install_git_hook(self._tmp, self.workspace_path)
        result = git_hook_status(self._tmp, self.workspace_path)
        self.assertTrue(result["installed"])
        self.assertEqual(result["schema_version"], "palari.git_status.v1")

    def test_status_shows_not_installed(self) -> None:
        result = git_hook_status(self._tmp, self.workspace_path)
        self.assertFalse(result["installed"])

    def test_pre_commit_passes_no_active_claim(self) -> None:
        result = pre_commit(self.workspace_path, cwd=self._tmp)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "no-active-claim")

    def test_pre_commit_blocks_out_of_boundary_files(self) -> None:
        self._start_claim()
        outside_file = Path(self._tmp) / "random_file.txt"
        outside_file.write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "add", "random_file.txt"], cwd=self._tmp, check=True, capture_output=True)
        result = pre_commit(self.workspace_path, cwd=self._tmp)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("random_file.txt", result["outside"])

    def test_pre_commit_passes_in_boundary_files(self) -> None:
        self._start_claim()
        in_boundary = Path(self._tmp) / "README.md"
        in_boundary.write_text("updated\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self._tmp, check=True, capture_output=True)
        result = pre_commit(self.workspace_path, cwd=self._tmp)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "pass")
        self.assertIn("README.md", result["staged"])
        self.assertEqual(result["outside"], [])

    def test_pre_commit_no_git_repo(self) -> None:
        no_git = tempfile.mkdtemp()
        try:
            result = pre_commit(self.workspace_path, cwd=no_git)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "no-git-repo")
        finally:
            shutil.rmtree(no_git, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
