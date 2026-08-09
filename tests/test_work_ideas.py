from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cli import main as cli_main
from palari_company_os.onramp import initialize_starter_workspace
from palari_company_os.workspace import Workspace


class WorkIdeaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "founder-repo"
        self.project.mkdir()
        initialize_starter_workspace(self.project)
        self.workspace_file = self.project / "workspace.json"

    def test_agent_idea_grants_no_task_authority(self) -> None:
        added = self.run_cli(
            "work",
            "add",
            "Draft the launch page",
            "--idea",
            "--as",
            "PALARI-CLAUDE",
            "--create",
            "docs/launch.md",
            "--modify",
            "README.md",
            "--approvals",
            "2",
        )

        workspace = Workspace.load(self.workspace_file)
        idea = workspace.proposal(added["idea"]["id"])
        self.assertEqual(added["status"], "waiting-on-human")
        self.assertIn("grants no task authority", added["message"])
        self.assertEqual(len(workspace.work_items), 0)
        self.assertIsNotNone(idea)
        assert idea is not None
        self.assertEqual(idea.workbench_id, "WORKBENCH-MAIN")
        self.assertEqual(idea.required_approval_count, 2)
        self.assertEqual(
            idea.path_intents,
            [
                {"path": "docs/launch.md", "intent": "create"},
                {"path": "README.md", "intent": "modify"},
            ],
        )
        self.assertEqual(workspace.workbenches[0].output_target_ids, [])
        self.assertIn(f"approve {idea.id}", added["next_action"])

    def test_human_approval_turns_the_same_limits_into_active_work(self) -> None:
        added = self.run_cli(
            "work",
            "add",
            "Draft the launch page",
            "--idea",
            "--create",
            "docs/launch.md",
            "--read",
            "docs/brand.md",
            "--verify",
            "Launch page checks pass.",
        )
        idea_id = added["idea"]["id"]

        approved = self.run_cli("approve", idea_id, "--as", "HUMAN-FOUNDER")

        workspace = Workspace.load(self.workspace_file)
        idea = workspace.proposal(idea_id)
        work = workspace.work_item(approved["work_item_id"])
        self.assertEqual(approved["action"], "idea-approved")
        self.assertIsNotNone(idea)
        self.assertIsNotNone(work)
        assert idea is not None and work is not None
        self.assertEqual(idea.status, "adopted")
        self.assertEqual(idea.linked_work, work.id)
        self.assertEqual(work.status, "active")
        self.assertEqual(work.goal, idea.goal)
        self.assertEqual(work.palari, idea.palari)
        self.assertEqual(work.allowed_resources, idea.allowed_resources)
        self.assertEqual(work.path_intents, idea.path_intents)
        self.assertEqual(
            workspace.workbenches[0].output_target_ids,
            ["docs/launch.md"],
        )

    def test_work_add_without_idea_still_creates_a_task(self) -> None:
        added = self.run_cli("work", "add", "Fix the guide", "--modify", "README.md")

        workspace = Workspace.load(self.workspace_file)
        self.assertIn("work_item", added)
        self.assertEqual(len(workspace.work_items), 1)
        self.assertEqual(len(workspace.proposals), 0)
        self.assertEqual(workspace.work_items[0].status, "active")

    def run_cli(self, *arguments: str) -> dict[str, object]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = ["--workspace", str(self.workspace_file), *arguments, "--json"]
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli_main(argv)
        self.assertEqual(exit_code, 0, msg=stderr.getvalue() or stdout.getvalue())
        payload = json.loads(stdout.getvalue())
        self.assertIsInstance(payload, dict)
        return payload


if __name__ == "__main__":
    unittest.main()
