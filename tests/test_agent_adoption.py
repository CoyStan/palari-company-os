from __future__ import annotations

import io
import json
import os
import shlex
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
        (self.tmp / "bin" / "palari").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
            'export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"\n'
            'exec python3 -S -m palari_company_os "$@"\n',
            encoding="utf-8",
        )
        (self.tmp / "bin" / "palari").chmod(0o755)
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

    def test_adoption_reuses_equivalent_existing_portable_guidance(self) -> None:
        agents = self.tmp / "AGENTS.md"
        existing = (
            "# Existing Palari guidance\n\n"
            "Run palari agent start --next before edits. Run palari agent advance "
            "after the commit, and stop for human review.\n"
        )
        agents.write_text(existing, encoding="utf-8")

        result = adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="generic",
            palari_id="PALARI-STEWARD",
        )

        self.assertEqual(agents.read_text(encoding="utf-8"), existing)
        self.assertNotIn("AGENTS.md", result["changed_files"])

    def test_unproven_hosts_are_honestly_advisory_and_commit_gated(self) -> None:
        for host in ("cursor", "devin", "glm"):
            with self.subTest(host=host):
                result = adopt_agent_host(
                    self.workspace,
                    project_dir=self.tmp,
                    host=host,
                    palari_id="PALARI-STEWARD",
                )
                self.assertEqual(result["host"], host)
                self.assertEqual(result["enforcement"]["session_boundary"], "advisory")
                self.assertEqual(result["enforcement"]["commit_boundary"], "structural")
                self.assertEqual(
                    result["host_adapter"]["activation"],
                    "no-proven-session-hook",
                )

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

    def test_adoption_refuses_a_non_executable_local_wrapper(self) -> None:
        (self.tmp / "bin" / "palari").chmod(0o644)

        with self.assertRaisesRegex(WorkspaceError, "not executable"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="generic",
                palari_id="PALARI-STEWARD",
            )

        self.assertFalse((self.tmp / "AGENTS.md").exists())
        self.assertFalse((self.tmp / ".git" / "hooks" / "pre-commit").exists())

    def test_adoption_refuses_noop_and_symlinked_local_wrappers(self) -> None:
        wrapper = self.tmp / "bin" / "palari"
        wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

        with self.assertRaisesRegex(WorkspaceError, "not an inspectable Palari launcher"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="generic",
                palari_id="PALARI-STEWARD",
            )

        wrapper.unlink()
        outside = self.tmp.parent / f"{self.tmp.name}-palari"
        outside.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        outside.chmod(0o755)
        self.addCleanup(outside.unlink, True)
        wrapper.symlink_to(outside)
        with self.assertRaisesRegex(WorkspaceError, "must not be a symlink"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="generic",
                palari_id="PALARI-STEWARD",
            )

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
            sum(
                " init " in command and "--host codex --hook-event" in command
                for command in commands
            ),
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

        with self.assertRaisesRegex(WorkspaceError, "not valid .*JSON"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="codex",
                palari_id="PALARI-STEWARD",
            )

        self.assertFalse((self.tmp / "AGENTS.md").exists())
        self.assertFalse((self.tmp / ".git" / "hooks" / "pre-commit").exists())

    def test_codex_adoption_rejects_invalid_utf8_and_regular_config_parent_before_writes(self) -> None:
        codex = self.tmp / ".codex"
        codex.mkdir()
        (codex / "hooks.json").write_bytes(b"\xff")
        with self.assertRaisesRegex(WorkspaceError, "valid UTF-8 JSON"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="codex",
                palari_id="PALARI-STEWARD",
            )
        self.assertFalse((self.tmp / "AGENTS.md").exists())
        self.assertFalse((self.tmp / ".git" / "hooks" / "pre-commit").exists())

        shutil.rmtree(codex)
        codex.write_text("not a directory\n", encoding="utf-8")
        with self.assertRaisesRegex(WorkspaceError, "parent is not a directory"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="codex",
                palari_id="PALARI-STEWARD",
            )
        self.assertFalse((self.tmp / "AGENTS.md").exists())
        self.assertFalse((self.tmp / ".git" / "hooks" / "pre-commit").exists())

    def test_adoption_rolls_back_project_files_when_git_hook_target_is_not_local(self) -> None:
        outside = self.tmp.parent / f"{self.tmp.name}-hooks"
        self.addCleanup(shutil.rmtree, outside, True)
        self._git("config", "core.hooksPath", str(outside))

        with self.assertRaisesRegex(WorkspaceError, "outside this repository"):
            adopt_agent_host(
                self.workspace,
                project_dir=self.tmp,
                host="codex",
                palari_id="PALARI-STEWARD",
            )

        self.assertFalse((self.tmp / "AGENTS.md").exists())
        self.assertFalse((self.tmp / ".codex").exists())
        self.assertFalse((outside / "pre-commit").exists())

    def test_codex_adoption_preserves_foreign_hook_co_located_with_managed_hook(self) -> None:
        hooks_file = self.tmp / ".codex" / "hooks.json"
        hooks_file.parent.mkdir()
        hooks_file.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "mixed",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "palari agent adopt --host codex --hook-event pre-tool-use",
                                    },
                                    {"type": "command", "command": "foreign-check"},
                                ],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        adopt_agent_host(
            self.workspace,
            project_dir=self.tmp,
            host="codex",
            palari_id="PALARI-STEWARD",
        )

        entries = json.loads(hooks_file.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
        commands = [hook["command"] for entry in entries for hook in entry["hooks"]]
        self.assertIn("foreign-check", commands)
        self.assertEqual(sum("--host codex --hook-event" in item for item in commands), 1)

    def test_generated_commands_quote_adversarial_workspace_path_as_data(self) -> None:
        malicious = self.tmp / "ws$(touch PWNED)"
        shutil.copytree(self.workspace, malicious)

        result = adopt_agent_host(
            malicious,
            project_dir=self.tmp,
            host="codex",
            palari_id="PALARI-STEWARD",
        )
        hooks = json.loads((self.tmp / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        command = hooks["hooks"]["SessionStart"][-1]["hooks"][0]["command"]
        subprocess.run(
            command,
            cwd=self.tmp,
            input="{}",
            text=True,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertFalse((self.tmp / "PWNED").exists())
        command_tokens = shlex.split(command)
        self.assertIn("init", command_tokens)
        self.assertNotIn("adopt", command_tokens)
        self.assertIn(str(malicious), command_tokens)
        self.assertIn(str(malicious), shlex.split(result["mcp"]["command"]))

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
                "init",
                str(self.workspace),
                "--host",
                "devin",
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

        plain = subprocess.run(
            [
                str(REPO_ROOT / "bin" / "palari"),
                "init",
                str(self.workspace),
                "--host",
                "devin",
                "--as",
                "PALARI-STEWARD",
            ],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertIn("Agent adoption: devin", plain.stdout)

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

        session = self._codex_hook(
            "session-start",
            {"cwd": str(self.tmp), "source": "startup"},
        )
        context = session["hookSpecificOutput"]["additionalContext"]
        self.assertIn("WORK-ADOPT", context)
        self.assertIn("README.md", context)

        (self.tmp / "outside.txt").write_text("outside\n", encoding="utf-8")
        stopped = self._codex_hook("stop", {"cwd": str(self.tmp)})
        self.assertEqual(stopped["continue"], False)
        self.assertIn("outside.txt", stopped["stopReason"])

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

        authority = self._codex_hook(
            "pre-tool-use",
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "palari human-decision record FORGED --work-item-id WORK-BASH"
                },
                "cwd": str(self.tmp),
            },
        )
        self.assertEqual(authority["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("human-only", authority["hookSpecificOutput"]["permissionDecisionReason"])

        allowed_advance = self._codex_hook(
            "pre-tool-use",
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        f"palari --workspace {shlex.quote(str(self.workspace))} "
                        "agent advance WORK-BASH --as PALARI-STEWARD --json"
                    )
                },
                "cwd": str(self.tmp),
            },
        )
        self.assertEqual(allowed_advance, {})

        foreign_advance = self._codex_hook(
            "pre-tool-use",
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "palari --workspace /tmp/foreign "
                        "agent advance WORK-BASH --as PALARI-STEWARD --json"
                    )
                },
                "cwd": str(self.tmp),
            },
        )
        self.assertEqual(
            foreign_advance["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

        claude_advance = run_agent_hook(
            "claude",
            "pre-tool-use",
            self.workspace,
            stdin=io.StringIO(
                json.dumps(
                    {
                        "tool_name": "Bash",
                        "tool_input": {
                            "command": (
                                f"palari --workspace {shlex.quote(str(self.workspace))} "
                                "agent advance WORK-BASH --as PALARI-STEWARD --json"
                            )
                        },
                        "cwd": str(self.tmp),
                    }
                )
            ),
        )
        self.assertEqual(claude_advance, {})

    def test_compatible_claude_install_cli_uses_hardened_absolute_command(self) -> None:
        result = subprocess.run(
            [
                str(REPO_ROOT / "bin" / "palari"),
                "--workspace",
                str(self.workspace),
                "claude",
                "install",
                "--project-dir",
                str(self.tmp),
                "--strict",
                "--json",
            ],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "palari.claude_install.v1")
        settings = json.loads(
            (self.tmp / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        command = settings["hooks"]["PreToolUse"][-1]["hooks"][0]["command"]
        tokens = shlex.split(command)
        self.assertEqual(tokens[tokens.index("--workspace") + 1], str(self.workspace))
        self.assertEqual(tokens[-4:], ["claude", "hook", "pre-tool-use", "--strict"])

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
