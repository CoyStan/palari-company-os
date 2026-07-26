from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_adoption import (
    adopt_agent_host,
    install_claude_host_hooks,
)
from palari_company_os.agent_isolation import start_isolated_agent
from palari_company_os.cli_parser import build_parser
from palari_company_os.command_surface import bind_palari_command_payload
from palari_company_os.git_hooks import install_git_hook
from palari_company_os.onramp import (
    initialize_maintainer_workspace,
    quick_add_work,
)
from palari_company_os.workspace import WorkspaceError
from palari_company_os.workspace_layout import (
    MAINTAINER_REPOSITORY_ID_FILENAME,
    MAINTAINER_STATE_ROOT,
    MAINTAINER_WORKSPACE_FILENAME,
)
from tests.workspace_fixture import write_current_agent_workspace


class MaintainerProfileCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Maintainer Test")
        self.git("config", "user.email", "maintainer@example.invalid")
        (self.root / "README.md").write_text("source candidate\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "source candidate")

    def test_parser_defaults_to_ordinary_and_accepts_explicit_maintainer(self) -> None:
        ordinary = build_parser().parse_args(["init", str(self.root)])
        maintainer = build_parser().parse_args(
            ["init", str(self.root), "--profile", "maintainer"]
        )

        self.assertEqual(ordinary.profile, "ordinary")
        self.assertEqual(maintainer.profile, "maintainer")

    def test_init_preserves_tracked_root_state_and_emits_exact_commands(self) -> None:
        write_current_agent_workspace(self.root / "workspace.json")
        self.git("add", "workspace.json", ".palari")
        self.git("commit", "-qm", "historical ordinary state")
        workspace_before = (self.root / "workspace.json").read_bytes()
        control_before = self.snapshot(self.root / ".palari")

        result = self.cli(
            "init",
            str(self.root),
            "--profile",
            "maintainer",
            "--name",
            "Maintainer Local",
            "--json",
        )
        payload = json.loads(result.stdout)
        workspace_file = self.root / MAINTAINER_WORKSPACE_FILENAME

        self.assertEqual(payload["schema_version"], "palari.init.v1")
        self.assertEqual(payload["profile"], "maintainer")
        self.assertEqual(payload["workspace_file"], str(workspace_file))
        self.assertEqual(payload["agent_docs"]["status"], "not-required")
        self.assertEqual(payload["authority_anchor"]["status"], "not-required")
        self.assertEqual(payload["adoption"]["status"], "not-requested")
        self.assertTrue(workspace_file.is_file())
        self.assertTrue(
            (self.root / MAINTAINER_STATE_ROOT / "binding.json").is_file()
        )
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual(
            (self.root / "workspace.json").read_bytes(),
            workspace_before,
        )
        self.assertEqual(self.snapshot(self.root / ".palari"), control_before)
        self.assertEqual(self.git_output("status", "--porcelain", "--untracked-files=all"), "")
        for command in payload["next_commands"]:
            tokens = shlex.split(command)
            self.assertEqual(
                tokens[:3],
                ["palari", "--workspace", str(workspace_file)],
            )

        ordinary = json.loads(self.cli("validate", "--json").stdout)
        explicit = json.loads(
            self.cli(
                "--workspace",
                str(workspace_file),
                "validate",
                "--json",
            ).stdout
        )
        self.assertEqual(ordinary["workspace"], "Current Agent Test Workspace")
        self.assertEqual(explicit["workspace"], "Maintainer Local")

    def test_maintainer_init_rejects_host_options_before_any_state_write(self) -> None:
        exclude = self.root / ".git" / "info" / "exclude"
        exclude_before = exclude.read_bytes()
        repository_id = self.root / ".git" / MAINTAINER_REPOSITORY_ID_FILENAME
        commands = (
            ("--host", "codex"),
            ("--as", "PALARI-CLAUDE"),
            ("--host", "codex", "--hook-event", "session-start"),
        )

        for extra in commands:
            with self.subTest(extra=extra):
                result = self.cli(
                    "init",
                    str(self.root),
                    "--profile",
                    "maintainer",
                    *extra,
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("maintainer profile v1 does not support", result.stderr)
                self.assertFalse(
                    (self.root / MAINTAINER_WORKSPACE_FILENAME).exists()
                )
                self.assertFalse((self.root / MAINTAINER_STATE_ROOT).exists())
                self.assertFalse(repository_id.exists())
                self.assertEqual(exclude.read_bytes(), exclude_before)
                self.assertEqual(
                    self.git_output(
                        "status",
                        "--porcelain",
                        "--untracked-files=all",
                    ),
                    "",
                )

    def test_maintainer_init_rolls_back_layout_when_workspace_write_fails(self) -> None:
        exclude = self.root / ".git" / "info" / "exclude"
        exclude_before = exclude.read_bytes()
        repository_id = self.root / ".git" / MAINTAINER_REPOSITORY_ID_FILENAME

        with (
            mock.patch(
                "palari_company_os.onramp.write_store",
                side_effect=WorkspaceError("injected workspace failure"),
            ),
            self.assertRaisesRegex(WorkspaceError, "injected workspace failure"),
        ):
            initialize_maintainer_workspace(self.root)

        self.assertFalse((self.root / MAINTAINER_WORKSPACE_FILENAME).exists())
        self.assertFalse((self.root / MAINTAINER_STATE_ROOT).exists())
        self.assertFalse(repository_id.exists())
        self.assertEqual(exclude.read_bytes(), exclude_before)
        self.assertEqual(self.git_output("status", "--porcelain", "--untracked-files=all"), "")

    def test_host_install_surfaces_reject_maintainer_without_mutation(self) -> None:
        initialized = initialize_maintainer_workspace(self.root)
        workspace_file = Path(initialized["workspace_file"])
        state_before = self.snapshot(self.root / MAINTAINER_STATE_ROOT)

        operations = (
            lambda: adopt_agent_host(
                workspace_file,
                project_dir=self.root,
                host="codex",
                palari_id="PALARI-CLAUDE",
            ),
            lambda: install_claude_host_hooks(
                self.root,
                workspace_file,
            ),
            lambda: install_claude_host_hooks(
                self.root,
                workspace_file,
                remove=True,
            ),
            lambda: install_git_hook(
                self.root,
                workspace_file,
            ),
            lambda: install_git_hook(
                self.root,
                workspace_file,
                remove=True,
            ),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(
                    WorkspaceError,
                    "does not support .* installation or removal",
                ):
                    operation()

        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.root / ".codex").exists())
        self.assertFalse((self.root / ".claude").exists())
        self.assertFalse((self.root / ".git" / "hooks" / "pre-commit").exists())
        self.assertEqual(
            self.snapshot(self.root / MAINTAINER_STATE_ROOT),
            state_before,
        )
        self.assertEqual(self.git_output("status", "--porcelain", "--untracked-files=all"), "")

    def test_isolation_rejects_before_branch_worktree_or_runtime_mutation(self) -> None:
        initialized = initialize_maintainer_workspace(self.root)
        workspace_file = Path(initialized["workspace_file"])
        state_before = self.snapshot(self.root / MAINTAINER_STATE_ROOT)
        refs_before = self.git_output("for-each-ref", "--format=%(refname)")
        worktrees_before = self.git_output("worktree", "list", "--porcelain")

        with self.assertRaisesRegex(
            WorkspaceError,
            "does not support agent start --isolate",
        ):
            start_isolated_agent(
                workspace_file,
                "WORK-NOT-CREATED",
                "PALARI-CLAUDE",
            )
        result = self.cli(
            "--workspace",
            str(workspace_file),
            "agent",
            "start",
            "WORK-NOT-CREATED",
            "--as",
            "PALARI-CLAUDE",
            "--isolate",
            "--json",
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("does not support agent start --isolate", result.stdout)
        self.assertEqual(
            self.snapshot(self.root / MAINTAINER_STATE_ROOT),
            state_before,
        )
        self.assertEqual(
            self.git_output("for-each-ref", "--format=%(refname)"),
            refs_before,
        )
        self.assertEqual(
            self.git_output("worktree", "list", "--porcelain"),
            worktrees_before,
        )
        self.assertFalse(
            (self.root.parent / ".palari-worktrees").exists()
        )
        self.assertEqual(self.git_output("status", "--porcelain", "--untracked-files=all"), "")

    def test_work_add_never_force_adds_maintainer_state(self) -> None:
        initialized = initialize_maintainer_workspace(self.root)
        workspace_file = Path(initialized["workspace_file"])
        head_before = self.git_output("rev-parse", "HEAD")

        result = quick_add_work(
            workspace_file,
            "Add local notes",
            write=["docs/notes.md"],
        )

        self.assertEqual(result["authority_anchor"]["status"], "not-required")
        self.assertEqual(self.git_output("rev-parse", "HEAD"), head_before)
        self.assertEqual(self.git_output("status", "--porcelain", "--untracked-files=all"), "")
        for command in result["next_commands"]:
            tokens = shlex.split(command)
            self.assertEqual(
                tokens[:3],
                ["palari", "--workspace", str(workspace_file)],
            )

    def test_command_binding_replaces_foreign_selector_and_binds_next_action(self) -> None:
        workspace_file = self.root / MAINTAINER_WORKSPACE_FILENAME
        payload = bind_palari_command_payload(
            workspace_file,
            {
                "next_action": "palari --workspace /tmp/foreign validate --json",
                "next_commands": ["palari queue --json"],
            },
        )

        for command in (payload["next_action"], *payload["next_commands"]):
            tokens = shlex.split(command)
            self.assertEqual(
                tokens[:3],
                ["palari", "--workspace", str(workspace_file)],
            )

    def cli(
        self,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(REPO_ROOT / "bin" / "palari"), *arguments],
            cwd=self.root,
            check=check,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )

    def git_output(self, *arguments: str) -> str:
        return self.git(*arguments).stdout.strip()

    @staticmethod
    def snapshot(root: Path) -> dict[str, bytes]:
        if not root.exists():
            return {}
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
