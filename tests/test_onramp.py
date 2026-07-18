from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.agent_runtime import start_agent
from palari_company_os.governance_journal import checkpoint_workspace_journal
from palari_company_os.onramp import initialize_starter_workspace, quick_add_work
from palari_company_os.work_identity import generate_work_id, is_opaque_work_id
from palari_company_os.workspace import Workspace, WorkspaceError, default_workspace_path


class InitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "acme-app"
        self.project.mkdir()

    def test_init_creates_valid_starter_workspace(self) -> None:
        result = initialize_starter_workspace(self.project)

        self.assertTrue(result["valid"])
        self.assertEqual(result["workspace"], "acme-app")
        workspace = Workspace.load(self.project)
        self.assertEqual([human.id for human in workspace.humans], ["HUMAN-FOUNDER"])
        self.assertEqual([palari.id for palari in workspace.palaris], ["PALARI-CLAUDE"])
        self.assertEqual([goal.id for goal in workspace.goals], ["GOAL-0001"])
        self.assertEqual([bench.id for bench in workspace.workbenches], ["WORKBENCH-MAIN"])
        self.assertEqual([source.id for source in workspace.sources], ["SOURCE-REPO"])
        self.assertEqual(workspace.palaris[0].default_worker, "claude-code")
        self.assertTrue(any("work add" in cmd for cmd in result["next_commands"]))
        self.assertTrue(any("agent start --next" in cmd for cmd in result["next_commands"]))
        self.assertEqual(result["agent_docs"]["status"], "ready")
        self.assertEqual(result["authority_anchor"]["status"], "not-required")
        self.assertTrue((self.project / "AGENTS.md").is_file())
        self.assertTrue((self.project / "docs/agent/verification.md").is_file())

    def test_init_refuses_existing_workspace(self) -> None:
        initialize_starter_workspace(self.project)

        with self.assertRaises(WorkspaceError):
            initialize_starter_workspace(self.project)

    def test_init_uses_git_user_name_when_available(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.name", "Maya Founder"],
            check=True,
        )

        result = initialize_starter_workspace(self.project)

        self.assertEqual(result["human"]["name"], "Maya Founder")

    def test_init_accepts_custom_name_and_palari(self) -> None:
        result = initialize_starter_workspace(
            self.project, name="My Company", palari_name="Codex"
        )

        self.assertEqual(result["workspace"], "My Company")
        self.assertEqual(result["palari"]["id"], "PALARI-CODEX")
        workspace = Workspace.load(self.project)
        self.assertEqual(workspace.palaris[0].default_worker, "codex")

    def test_init_anchors_only_generated_adoption_files_in_a_committed_repo(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.project),
                "config",
                "user.email",
                "test@example.invalid",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.project), "commit", "--allow-empty", "-qm", "initial"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.project), "config", "commit.gpgSign", "true"],
            check=True,
        )
        hook = self.project / ".git" / "hooks" / "pre-commit"
        hook.write_text(
            "#!/bin/sh\nprintf invoked > hook-ran\nexit 99\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)
        unrelated = self.project / "unrelated.txt"
        unrelated.write_text("pre-existing staged work\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.project), "add", "unrelated.txt"],
            check=True,
        )

        with patch.dict(
            os.environ,
            {"GIT_INDEX_FILE": str(self.project / "attacker-controlled-index")},
        ):
            result = initialize_starter_workspace(self.project, palari_name="Agent")

        anchor = result["authority_anchor"]
        self.assertEqual(anchor["status"], "anchored")
        self.assertEqual(anchor["commit"], self.git_output("rev-parse", "HEAD"))
        changed = set(
            self.git_output("show", "--format=", "--name-only", "HEAD").splitlines()
        )
        self.assertEqual(changed, set(anchor["paths"]))
        self.assertNotIn("unrelated.txt", changed)
        self.assertIn("A  unrelated.txt", self.git_output("status", "--short"))
        self.assertFalse((self.project / "hook-ran").exists())
        self.assertEqual(
            self.git_output("show", "HEAD:workspace.json").strip(),
            (self.project / "workspace.json").read_text(encoding="utf-8").strip(),
        )

    def test_init_preserves_existing_agent_guidance(self) -> None:
        agents = self.project / "AGENTS.md"
        agents.write_text("# Existing project instructions\n", encoding="utf-8")

        result = initialize_starter_workspace(self.project)

        self.assertEqual(agents.read_text(encoding="utf-8"), "# Existing project instructions\n")
        self.assertIn("AGENTS.md", result["agent_docs"]["preserved"])
        self.assertNotIn("AGENTS.md", result["agent_docs"]["created"])

    def test_init_can_install_and_anchor_codex_in_one_action(self) -> None:
        self._prepare_adoptable_git_project()

        result = initialize_starter_workspace(
            self.project,
            palari_name="Agent",
            host="codex",
        )

        self.assertEqual(result["adoption"]["status"], "ready")
        self.assertEqual(result["adoption"]["host"], "codex")
        self.assertEqual(
            result["adoption"]["enforcement"]["session_activation"],
            "requires-project-hook-trust",
        )
        self.assertIn(".codex/hooks.json", result["authority_anchor"]["paths"])
        self.assertTrue((self.project / ".git" / "hooks" / "pre-commit").is_file())
        self.assertEqual(self.git_output("status", "--short"), "")
        agents = (self.project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(agents.count("palari agent start --next"), 1)
        self.assertNotIn("palari:agent-contract:start", agents)

    def test_nested_init_anchors_repo_root_host_files_without_setup_dirt(self) -> None:
        self._prepare_adoptable_git_project()
        nested = self.project / "companies" / "acme"

        result = initialize_starter_workspace(
            nested,
            palari_name="Agent",
            host="codex",
        )

        self.assertEqual(result["adoption"]["status"], "ready")
        anchored = set(result["authority_anchor"]["paths"])
        self.assertIn("AGENTS.md", anchored)
        self.assertIn(".codex/hooks.json", anchored)
        self.assertIn("companies/acme/workspace.json", anchored)
        committed = set(self.git_output("show", "--format=", "--name-only", "HEAD").splitlines())
        self.assertEqual(committed, anchored)
        self.assertEqual(self.git_output("status", "--short"), "")

    def test_nested_init_does_not_absorb_existing_repo_root_host_config(self) -> None:
        self._prepare_adoptable_git_project()
        hooks_file = self.project / ".codex" / "hooks.json"
        hooks_file.parent.mkdir()
        foreign = '{"foreign_uncommitted": "do not anchor me"}\n'
        hooks_file.write_text(foreign, encoding="utf-8")

        result = initialize_starter_workspace(
            self.project / "companies" / "acme",
            palari_name="Agent",
            host="codex",
        )

        self.assertEqual(result["adoption"]["status"], "blocked")
        self.assertIn("existing .codex/hooks.json", result["adoption"]["message"])
        self.assertEqual(hooks_file.read_text(encoding="utf-8"), foreign)
        self.assertNotIn(".codex/hooks.json", result["authority_anchor"]["paths"])
        show = subprocess.run(
            ["git", "-C", str(self.project), "show", "HEAD:.codex/hooks.json"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertNotEqual(show.returncode, 0)
        self.assertIn("?? .codex/", self.git_output("status", "--short"))
        self.assertEqual(len(result["next_commands"]), 1)

    def test_nested_init_does_not_absorb_existing_repo_root_guidance(self) -> None:
        self._prepare_adoptable_git_project()
        agents = self.project / "AGENTS.md"
        foreign = "# Unreviewed root instructions\n"
        agents.write_text(foreign, encoding="utf-8")

        result = initialize_starter_workspace(
            self.project / "companies" / "acme",
            palari_name="Agent",
            host="codex",
        )

        self.assertEqual(result["adoption"]["status"], "blocked")
        self.assertIn("existing AGENTS.md is preserved", result["adoption"]["message"])
        self.assertEqual(agents.read_text(encoding="utf-8"), foreign)
        self.assertNotIn("AGENTS.md", result["authority_anchor"]["paths"])
        show = subprocess.run(
            ["git", "-C", str(self.project), "show", "HEAD:AGENTS.md"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertNotEqual(show.returncode, 0)
        self.assertIn("?? AGENTS.md", self.git_output("status", "--short"))

    def test_init_preserves_existing_host_files_and_returns_one_recovery_action(self) -> None:
        self._prepare_adoptable_git_project()
        agents = self.project / "AGENTS.md"
        agents.write_text("# Existing project instructions\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.project), "add", "AGENTS.md"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.project), "commit", "-qm", "existing guidance"],
            check=True,
        )

        result = initialize_starter_workspace(
            self.project,
            palari_name="Agent",
            host="codex",
        )

        self.assertEqual(result["adoption"]["status"], "blocked")
        self.assertIn("existing AGENTS.md is preserved", result["adoption"]["message"])
        self.assertEqual(len(result["next_commands"]), 1)
        self.assertIn("init", result["next_commands"][0])
        self.assertIn("--host codex", result["next_commands"][0])
        self.assertEqual(agents.read_text(encoding="utf-8"), "# Existing project instructions\n")
        self.assertFalse((self.project / ".codex" / "hooks.json").exists())
        self.assertEqual(self.git_output("status", "--short"), "")

    def test_init_rejects_agent_documentation_symlink_escape_before_workspace_write(
        self,
    ) -> None:
        outside = self.project.parent / "outside-docs"
        outside.mkdir()
        (self.project / "docs").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(WorkspaceError, "documentation path is unsafe"):
            initialize_starter_workspace(self.project)

        self.assertFalse((self.project / "workspace.json").exists())
        self.assertEqual(list(outside.iterdir()), [])

    def test_init_rejects_agent_documentation_file_parent_before_any_write(
        self,
    ) -> None:
        self._prepare_adoptable_git_project()
        docs = self.project / "docs"
        docs.write_bytes(b"existing non-directory\n")
        status_before = self.git_output("status", "--short")

        with self.assertRaisesRegex(
            WorkspaceError,
            "parent is not a directory: docs",
        ):
            initialize_starter_workspace(
                self.project,
                palari_name="Agent",
                host="generic",
            )

        self.assertEqual(docs.read_bytes(), b"existing non-directory\n")
        self.assertFalse((self.project / "workspace.json").exists())
        self.assertFalse((self.project / ".palari").exists())
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / ".git" / "hooks" / "pre-commit").exists())
        self.assertEqual(self.git_output("status", "--short"), status_before)

    def git_output(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.project), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()

    def _prepare_adoptable_git_project(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.project),
                "config",
                "user.email",
                "test@example.invalid",
            ],
            check=True,
        )
        wrapper = self.project / "bin" / "palari"
        wrapper.parent.mkdir()
        wrapper.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
            'export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"\n'
            'exec python3 -S -m palari_company_os "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        subprocess.run(
            ["git", "-C", str(self.project), "add", "bin/palari"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.project), "commit", "-qm", "initial"],
            check=True,
        )


class WorkAddTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "acme-app"
        self.project.mkdir()
        initialize_starter_workspace(self.project)

    def test_work_add_produces_a_ready_startable_packet(self) -> None:
        result = quick_add_work(
            self.project,
            "Clean up launch notes",
            write=["docs/notes.md"],
        )

        work_id = result["work_item"]["id"]
        self.assertTrue(is_opaque_work_id(work_id))
        workspace = Workspace.load(self.project)
        packet = build_agent_brief(workspace, work_id, "PALARI-CLAUDE", "execute")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["allowed_paths"]["write"], ["docs/notes.md"])
        self.assertEqual(
            result["next_commands"],
            ["palari agent start --next --as PALARI-CLAUDE --mode execute --json"],
        )

    def test_work_add_idempotently_recovers_an_unanchored_git_workspace(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run(
            ["git", "-C", str(self.project), "commit", "--allow-empty", "-qm", "initial"],
            check=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
            },
        )

        result = quick_add_work(
            self.project,
            "Recovered task",
            write=["docs/recovered.md"],
        )
        work_id = result["work_item"]["id"]

        self.assertEqual(result["authority_anchor"]["status"], "anchored")
        self.assertEqual(
            quick_add_work(
                self.project,
                "Second task",
                write=["docs/second.md"],
            )["authority_anchor"]["commit"],
            result["authority_anchor"]["commit"],
        )
        started = start_agent(
            Workspace.load(self.project),
            self.project,
            work_id,
            "PALARI-CLAUDE",
        )
        self.assertEqual(started["start"]["status"], "claimed")

    def test_write_paths_become_boundary_and_reads_stay_read_only(self) -> None:
        result = quick_add_work(
            self.project,
            "Summarize research",
            write=["docs/summary.md"],
            read=["research/raw.md"],
        )

        work = result["work_item"]
        self.assertEqual(work["output_targets"], ["docs/summary.md"])
        self.assertIn("research/raw.md", work["allowed_resources"])
        workspace = Workspace.load(self.project)
        packet = build_agent_brief(workspace, work["id"], "PALARI-CLAUDE", "execute")
        self.assertEqual(packet["allowed_paths"]["write"], ["docs/summary.md"])
        self.assertIn("research/raw.md", packet["allowed_paths"]["read"])

    def test_work_ids_are_unique_and_do_not_encode_creation_order(self) -> None:
        first = quick_add_work(self.project, "One", write=["docs/a.md"])
        second = quick_add_work(self.project, "Two", write=["docs/b.md"])

        first_id = first["work_item"]["id"]
        second_id = second["work_item"]["id"]
        self.assertTrue(is_opaque_work_id(first_id))
        self.assertTrue(is_opaque_work_id(second_id))
        self.assertNotEqual(first_id, second_id)

    def test_work_add_preserves_explicit_legacy_id(self) -> None:
        result = quick_add_work(
            self.project,
            "Legacy import",
            write=["docs/legacy.md"],
            work_id="WORK-0001",
        )

        self.assertEqual(result["work_item"]["id"], "WORK-0001")

    def test_opaque_id_retries_a_collision_without_scanning_numeric_ids(self) -> None:
        collision = UUID("00000000-0000-4000-8000-000000000001")
        fresh = UUID("00000000-0000-4000-8000-000000000002")
        values = iter((collision, fresh))

        result = generate_work_id(
            ["WORK-9999", f"WORK-{collision.hex.upper()}"],
            uuid_factory=lambda: next(values),
        )

        self.assertEqual(result, f"WORK-{fresh.hex.upper()}")

    def test_work_add_records_only_explicit_dependencies(self) -> None:
        first = quick_add_work(self.project, "One", write=["docs/a.md"])
        second = quick_add_work(
            self.project,
            "Two",
            write=["docs/b.md"],
            dependencies=[first["work_item"]["id"]],
            parallel_policy="coordinate",
        )

        self.assertEqual(
            second["work_item"]["dependency_ids"],
            [first["work_item"]["id"]],
        )
        self.assertEqual(second["work_item"]["parallel_policy"], "coordinate")

    def test_work_add_rejects_missing_duplicate_and_self_dependencies(self) -> None:
        first = quick_add_work(self.project, "One", write=["docs/a.md"])
        first_id = first["work_item"]["id"]
        with self.assertRaisesRegex(WorkspaceError, "unknown work item"):
            quick_add_work(
                self.project,
                "Missing",
                write=["docs/missing.md"],
                dependencies=["WORK-NOT-THERE"],
            )
        with self.assertRaisesRegex(WorkspaceError, "repeats work item"):
            quick_add_work(
                self.project,
                "Duplicate",
                write=["docs/duplicate.md"],
                dependencies=[first_id, first_id],
            )
        with self.assertRaisesRegex(WorkspaceError, "cannot reference the new work item"):
            quick_add_work(
                self.project,
                "Self",
                write=["docs/self.md"],
                work_id="WORK-SELF",
                dependencies=["WORK-SELF"],
            )

    def test_workbench_outputs_grow_with_the_work_boundary(self) -> None:
        result = quick_add_work(self.project, "One", write=["docs/a.md"])

        self.assertEqual(result["workbench_outputs_added"], ["docs/a.md"])
        workspace = Workspace.load(self.project)
        self.assertIn("docs/a.md", workspace.workbenches[0].output_target_ids)

    def test_exact_create_modify_delete_intents_compile_one_write_contract(self) -> None:
        result = quick_add_work(
            self.project,
            "Exact mutation",
            write=[],
            create=["docs/new.md"],
            modify=["docs/existing.md"],
            delete=["docs/obsolete.md"],
        )

        work_id = result["work_item"]["id"]
        workspace = Workspace.load(self.project)
        work = workspace.work_item(work_id)
        assert work is not None
        self.assertEqual(
            work.path_intents,
            [
                {"path": "docs/new.md", "intent": "create"},
                {"path": "docs/existing.md", "intent": "modify"},
                {"path": "docs/obsolete.md", "intent": "delete"},
            ],
        )
        self.assertEqual(
            work.acceptance_target,
            "Declared path intents hold and verification passes.",
        )
        packet = build_agent_brief(workspace, work_id, work.palari, "execute")
        self.assertEqual(
            packet["allowed_paths"]["write"],
            ["docs/new.md", "docs/existing.md", "docs/obsolete.md"],
        )
        self.assertEqual(
            packet["required_output"]["output_targets"],
            ["docs/new.md", "docs/existing.md"],
        )

    def test_exact_intents_cannot_be_mixed_with_legacy_write(self) -> None:
        workspace_file = self.project / "workspace.json"
        before = workspace_file.read_bytes()

        with self.assertRaisesRegex(WorkspaceError, "cannot be combined"):
            quick_add_work(
                self.project,
                "Ambiguous mutation",
                write=["docs/legacy.md"],
                delete=["docs/obsolete.md"],
            )

        self.assertEqual(workspace_file.read_bytes(), before)

    def test_work_add_validation_failure_leaves_workspace_and_journal_unchanged(self) -> None:
        workspace_file = self.project / "workspace.json"
        journal_file = self.project / ".palari" / "governance-journal.v2.jsonl"
        before = {
            "workspace": workspace_file.read_bytes(),
            "journal": journal_file.read_bytes(),
        }

        with self.assertRaisesRegex(WorkspaceError, "unknown goal"):
            quick_add_work(
                self.project,
                "Invalid",
                write=["docs/should-not-expand.md"],
                goal_id="GOAL-NOT-THERE",
            )

        self.assertEqual(workspace_file.read_bytes(), before["workspace"])
        self.assertEqual(journal_file.read_bytes(), before["journal"])

    def test_requires_at_least_one_write_path(self) -> None:
        with self.assertRaises(WorkspaceError):
            quick_add_work(self.project, "Unbounded", write=[])

    def test_rejects_paths_outside_the_workspace(self) -> None:
        with self.assertRaises(WorkspaceError):
            quick_add_work(self.project, "Escape", write=["../outside.md"])

    def test_ambiguous_palari_requires_explicit_choice(self) -> None:
        data = json.loads((self.project / "workspace.json").read_text(encoding="utf-8"))
        data["palaris"].append(dict(data["palaris"][0], id="PALARI-OTHER", name="Other"))
        (self.project / "workspace.json").write_text(json.dumps(data), encoding="utf-8")

        with self.assertRaises(WorkspaceError) as caught:
            quick_add_work(self.project, "Pick one", write=["docs/a.md"])
        self.assertIn("--as", str(caught.exception))

        checkpoint = checkpoint_workspace_journal(
            self.project,
            "HUMAN-FOUNDER",
            acknowledge_break=True,
            reason="Test fixture added a second Palari by manual edit.",
        )
        self.assertEqual(checkpoint["status"], "valid-with-continuity-break")

        result = quick_add_work(
            self.project, "Pick one", write=["docs/a.md"], palari_id="PALARI-OTHER"
        )
        self.assertEqual(result["work_item"]["palari"], "PALARI-OTHER")

    def test_requires_a_title(self) -> None:
        with self.assertRaises(WorkspaceError):
            quick_add_work(self.project, "   ", write=["docs/a.md"])


class DefaultWorkspaceTests(unittest.TestCase):
    def test_cwd_workspace_json_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            project.mkdir()
            initialize_starter_workspace(project)
            original = os.getcwd()
            os.chdir(project)
            try:
                self.assertEqual(default_workspace_path(), project.resolve())
            finally:
                os.chdir(original)

    def test_falls_back_to_example_without_local_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = os.getcwd()
            os.chdir(tmp)
            try:
                self.assertTrue(
                    str(default_workspace_path()).endswith("acme-company-os")
                )
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
