from __future__ import annotations

import io
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

from palari_company_os.agent_adoption import adopt_agent_host, run_agent_hook
from palari_company_os.agent_runtime import start_agent
from palari_company_os.authoring import create_record
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.workspace_fixture import write_portable_agent_workspace


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


class AgentAdoptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.workspace = self.tmp / "workspaces" / "test"
        self.workspace.mkdir(parents=True)
        write_portable_agent_workspace(
            DOGFOOD / "workspace.json",
            self.workspace / "workspace.json",
        )
        shutil.rmtree(self.workspace / ".palari", ignore_errors=True)
        (self.tmp / "README.md").write_text("test\n", encoding="utf-8")
        (self.tmp / "bin").mkdir()
        (self.tmp / "bin" / "palari").write_text("#!/bin/sh\n", encoding="utf-8")
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
        self._git("init")
        self._git("config", "user.name", "Test")
        self._git("config", "user.email", "test@example.com")
        self._commit_all("initial fixture")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_generic_adoption_is_idempotent_and_preserves_existing_instructions(self) -> None:
        agents = self.tmp / "AGENTS.md"
        agents.write_text("# Existing rules\n\nKeep this.\n", encoding="utf-8")

        first = adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="generic",
            palari_id="PALARI-STEWARD",
        )
        second = adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="generic",
            palari_id="PALARI-STEWARD",
        )

        content = agents.read_text(encoding="utf-8")
        self.assertIn("# Existing rules", content)
        self.assertEqual(content.count("palari:agent-contract:start"), 1)
        self.assertIn("agent start --next --as PALARI-STEWARD", content)
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(first["enforcement"]["commit_boundary"], "structural")
        self.assertEqual(first["enforcement"]["session_boundary"], "advisory")
        self.assertTrue((self.tmp / ".git" / "hooks" / "pre-commit").is_file())

    def test_adoption_refuses_malformed_managed_block_without_installing_hook(self) -> None:
        (self.tmp / "AGENTS.md").write_text(
            "<!-- palari:agent-contract:start -->\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(WorkspaceError, "malformed Palari managed block"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="generic",
                palari_id="PALARI-STEWARD",
            )

        self.assertFalse((self.tmp / ".git" / "hooks" / "pre-commit").exists())

    def test_adoption_never_overwrites_an_unmanaged_git_hook(self) -> None:
        hook = self.tmp / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

        with self.assertRaisesRegex(WorkspaceError, "not Palari-managed"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="cursor",
                palari_id="PALARI-STEWARD",
            )

        self.assertFalse((self.tmp / "AGENTS.md").exists())
        self.assertEqual(hook.read_text(encoding="utf-8"), "#!/bin/sh\nexit 0\n")

    def test_codex_adoption_merges_hooks_and_requires_explicit_host_trust(self) -> None:
        hooks_file = self.tmp / ".codex" / "hooks.json"
        hooks_file.parent.mkdir()
        hooks_file.write_text(
            json.dumps(
                {
                    "description": "existing",
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "custom",
                                "hooks": [{"type": "command", "command": "custom-check"}],
                            }
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )

        first = adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="codex",
            palari_id="PALARI-STEWARD",
        )
        rendered_once = hooks_file.read_text(encoding="utf-8")
        second = adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="codex",
            palari_id="PALARI-STEWARD",
        )

        data = json.loads(rendered_once)
        commands = [
            hook["command"]
            for entry in data["hooks"]["PreToolUse"]
            for hook in entry["hooks"]
        ]
        self.assertIn("custom-check", commands)
        self.assertEqual(
            sum("agent adopt --host codex --hook-event" in command for command in commands),
            1,
        )
        self.assertEqual(hooks_file.read_text(encoding="utf-8"), rendered_once)
        self.assertEqual(
            first["enforcement"]["session_activation"],
            "requires-project-hook-trust",
        )
        self.assertIn("/hooks", first["host_adapter"]["next_action"])
        self.assertFalse(second["changed"])

    def test_codex_adoption_rejects_invalid_existing_hook_json_before_writes(self) -> None:
        hooks_file = self.tmp / ".codex" / "hooks.json"
        hooks_file.parent.mkdir()
        hooks_file.write_text("{broken", encoding="utf-8")

        with self.assertRaisesRegex(WorkspaceError, "not valid JSON"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="codex",
                palari_id="PALARI-STEWARD",
            )

        self.assertFalse((self.tmp / "AGENTS.md").exists())
        self.assertFalse((self.tmp / ".git" / "hooks" / "pre-commit").exists())

    def test_claude_adoption_preserves_settings_and_installs_structural_profile(self) -> None:
        settings = self.tmp / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text(
            json.dumps({"permissions": {"allow": ["Read"]}}),
            encoding="utf-8",
        )

        first = adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="claude",
            palari_id="PALARI-STEWARD",
        )
        rendered_once = settings.read_text(encoding="utf-8")
        second = adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="claude",
            palari_id="PALARI-STEWARD",
        )

        data = json.loads(rendered_once)
        self.assertEqual(data["permissions"], {"allow": ["Read"]})
        self.assertEqual(set(data["hooks"]), {"PreToolUse", "SessionStart", "Stop"})
        self.assertEqual(first["enforcement"]["session_boundary"], "structural")
        self.assertEqual(settings.read_text(encoding="utf-8"), rendered_once)
        self.assertFalse(second["changed"])

    def test_adoption_rejects_instruction_and_host_config_symlink_escape(self) -> None:
        outside = self.tmp.parent / f"{self.tmp.name}-outside"
        outside.mkdir()
        self.addCleanup(shutil.rmtree, outside, True)
        outside_agents = outside / "AGENTS.md"
        outside_agents.write_text("outside\n", encoding="utf-8")
        (self.tmp / "AGENTS.md").symlink_to(outside_agents)

        with self.assertRaisesRegex(WorkspaceError, "uses a symlink"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="generic",
                palari_id="PALARI-STEWARD",
            )
        self.assertEqual(outside_agents.read_text(encoding="utf-8"), "outside\n")
        (self.tmp / "AGENTS.md").unlink()

        (self.tmp / ".codex").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(WorkspaceError, "uses a symlink"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="codex",
                palari_id="PALARI-STEWARD",
            )
        self.assertFalse((outside / "hooks.json").exists())

    def test_cli_adoption_emits_one_structured_host_report(self) -> None:
        result = subprocess.run(
            [
                str(REPO_ROOT / "bin" / "palari"),
                "--workspace",
                str(self.workspace),
                "agent",
                "adopt",
                "--host",
                "devin",
                "--project-dir",
                str(self.tmp),
                "--as",
                "PALARI-STEWARD",
                "--json",
            ],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "palari.agent_adoption.v1")
        self.assertEqual(payload["host"], "devin")
        self.assertEqual(len(payload["next_commands"]), 2)

    def test_codex_hook_denies_outside_patch_and_allows_exact_claim_path(self) -> None:
        adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="codex",
            palari_id="PALARI-STEWARD",
        )
        self._create_work("WORK-ADOPT", ["README.md"])
        self._commit_all("adopt and declare work", no_verify=True)
        ws = Workspace.load(self.workspace)
        claimed = start_agent(
            ws,
            self.workspace,
            "WORK-ADOPT",
            "PALARI-STEWARD",
            "execute",
        )
        self.assertEqual(claimed["start"]["status"], "claimed")

        denied = self._codex_hook(
            "pre-tool-use",
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Add File: outside.txt\n+x\n*** End Patch"
                },
                "cwd": str(self.tmp),
            },
        )
        allowed = self._codex_hook(
            "pre-tool-use",
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-test\n+ok\n*** End Patch"
                },
                "cwd": str(self.tmp),
            },
        )

        self.assertEqual(
            denied["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertEqual(allowed, {})

    def test_codex_hook_converts_unsupported_ask_into_fail_closed_deny(self) -> None:
        adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="codex",
            palari_id="PALARI-STEWARD",
        )
        self._create_work("WORK-BASH", ["README.md"])
        self._commit_all("adopt and declare bash work", no_verify=True)
        start_agent(
            Workspace.load(self.workspace),
            self.workspace,
            "WORK-BASH",
            "PALARI-STEWARD",
            "execute",
        )

        result = self._codex_hook(
            "pre-tool-use",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "python3 -c 'open(\"README.md\", \"w\")'"},
                "cwd": str(self.tmp),
            },
        )

        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("has no ask decision", result["hookSpecificOutput"]["permissionDecisionReason"])

    def _codex_hook(self, event: str, payload: dict[str, object]) -> dict[str, object]:
        return run_agent_hook(
            "codex",
            event,
            self.workspace,
            stdin=io.StringIO(json.dumps(payload)),
        )

    def _create_work(self, work_id: str, paths: list[str]) -> None:
        create_record(
            str(self.workspace),
            "work",
            {
                "id": work_id,
                "title": "Adoption hook test",
                "palari": "PALARI-STEWARD",
                "goal": "GOAL-REPO-0001",
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R1",
                "intensity": "light",
                "required_approval_count": 0,
                "scope": "Test the adopted host boundary.",
                "acceptance_target": "Only exact paths are writable.",
                "status": "active",
                "allowed_resources": paths,
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": paths,
                "forbidden_actions": ["deploy"],
                "verification_expectations": ["true"],
            },
            command="test",
        )

    def _commit_all(self, message: str, *, no_verify: bool = False) -> None:
        self._git("add", ".")
        args = ["commit", "-m", message]
        if no_verify:
            args.insert(1, "--no-verify")
        self._git(*args)

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=self.tmp,
            check=True,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
