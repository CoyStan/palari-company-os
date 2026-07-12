from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cursor_rules import (
    RULE_RELATIVE_PATH,
    cursor_rules_status,
    install_cursor_rules,
)
from palari_company_os.workspace import Workspace as Ws


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


class CursorRulesTests(unittest.TestCase):
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
            ["git", "config", "user.name", "Test"],
            cwd=self._tmp,
            check=True,
            env=env,
            capture_output=True,
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
                "id": "WORK-TEST-CURSOR",
                "title": "Test cursor rules",
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
        result = start_agent(ws, self.workspace_path, "WORK-TEST-CURSOR", "PALARI-STEWARD", "execute")
        assert result.get("start", {}).get("status") == "claimed", f"Claim failed: {result.get('start', {})}"

    def _rule_path(self) -> Path:
        return Path(self._tmp) / RULE_RELATIVE_PATH

    def test_install_creates_rule_and_git_hook(self) -> None:
        result = install_cursor_rules(self._tmp, self.workspace_path)
        self.assertEqual(result["status"], "installed")
        self.assertTrue(result["changed"])
        self.assertEqual(result["schema_version"], "palari.cursor_install.v1")

        rule_path = self._rule_path()
        self.assertTrue(rule_path.exists())
        content = rule_path.read_text(encoding="utf-8")
        self.assertIn("palari cursor rule", content)
        self.assertIn("alwaysApply: true", content)

        self.assertIsNotNone(result["git_hook"])
        self.assertEqual(result["git_hook"]["status"], "installed")
        hook_path = Path(self._tmp) / ".git" / "hooks" / "pre-commit"
        self.assertTrue(hook_path.exists())
        self.assertTrue(os.access(hook_path, os.X_OK))

    def test_install_is_idempotent(self) -> None:
        install_cursor_rules(self._tmp, self.workspace_path)
        result = install_cursor_rules(self._tmp, self.workspace_path)
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["changed"])

    def test_install_no_git_hook(self) -> None:
        result = install_cursor_rules(self._tmp, self.workspace_path, git_hook=False)
        self.assertEqual(result["status"], "installed")
        self.assertIsNone(result["git_hook"])
        self.assertTrue(self._rule_path().exists())
        hook_path = Path(self._tmp) / ".git" / "hooks" / "pre-commit"
        self.assertFalse(hook_path.exists())

    def test_install_then_remove(self) -> None:
        install_cursor_rules(self._tmp, self.workspace_path)
        result = install_cursor_rules(self._tmp, self.workspace_path, remove=True)
        self.assertEqual(result["status"], "removed")
        self.assertTrue(result["changed"])
        self.assertFalse(self._rule_path().exists())
        hook_path = Path(self._tmp) / ".git" / "hooks" / "pre-commit"
        self.assertFalse(hook_path.exists())

    def test_remove_when_not_installed(self) -> None:
        result = install_cursor_rules(self._tmp, self.workspace_path, remove=True)
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["changed"])

    def test_install_refuses_to_overwrite_unmanaged_rule(self) -> None:
        rule_path = self._rule_path()
        rule_path.parent.mkdir(parents=True, exist_ok=True)
        rule_path.write_text("# hand-written cursor rule\n", encoding="utf-8")
        result = install_cursor_rules(self._tmp, self.workspace_path)
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["changed"])
        self.assertIn("hand-written", rule_path.read_text(encoding="utf-8"))

    def test_install_without_git_repo_still_writes_rule(self) -> None:
        no_git = tempfile.mkdtemp()
        try:
            result = install_cursor_rules(no_git, self.workspace_path)
            self.assertEqual(result["status"], "installed")
            self.assertTrue((Path(no_git) / RULE_RELATIVE_PATH).exists())
            self.assertEqual(result["git_hook"]["status"], "error")
        finally:
            shutil.rmtree(no_git, ignore_errors=True)

    def test_status_shows_installed(self) -> None:
        install_cursor_rules(self._tmp, self.workspace_path)
        result = cursor_rules_status(self._tmp, self.workspace_path)
        self.assertTrue(result["installed"])
        self.assertTrue(result["git_hook_installed"])
        self.assertEqual(result["schema_version"], "palari.cursor_status.v1")

    def test_status_shows_not_installed(self) -> None:
        result = cursor_rules_status(self._tmp, self.workspace_path)
        self.assertFalse(result["installed"])
        self.assertFalse(result["git_hook_installed"])

    def test_status_reports_active_claim_write_paths(self) -> None:
        install_cursor_rules(self._tmp, self.workspace_path)
        self._start_claim()
        result = cursor_rules_status(self._tmp, self.workspace_path)
        claims = result["active_claims"]
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["work_item"], "WORK-TEST-CURSOR")
        self.assertIn("README.md", claims[0]["allowed_write_paths"])


if __name__ == "__main__":
    unittest.main()
