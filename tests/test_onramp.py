from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.onramp import initialize_starter_workspace, quick_add_work
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
        self.assertTrue(any("claude install" in cmd for cmd in result["next_commands"]))

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

        self.assertEqual(result["work_item"]["id"], "WORK-0001")
        workspace = Workspace.load(self.project)
        packet = build_agent_brief(workspace, "WORK-0001", "PALARI-CLAUDE", "execute")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["allowed_paths"]["write"], ["docs/notes.md"])

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

    def test_work_ids_auto_increment(self) -> None:
        first = quick_add_work(self.project, "One", write=["docs/a.md"])
        second = quick_add_work(self.project, "Two", write=["docs/b.md"])

        self.assertEqual(first["work_item"]["id"], "WORK-0001")
        self.assertEqual(second["work_item"]["id"], "WORK-0002")

    def test_workbench_outputs_grow_with_the_work_boundary(self) -> None:
        result = quick_add_work(self.project, "One", write=["docs/a.md"])

        self.assertEqual(result["workbench_outputs_added"], ["docs/a.md"])
        workspace = Workspace.load(self.project)
        self.assertIn("docs/a.md", workspace.workbenches[0].output_target_ids)

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
