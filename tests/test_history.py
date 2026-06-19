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

from palari_company_os.history import history_file_path, read_history
from palari_company_os.workspace import Workspace


FIXTURES = REPO_ROOT / "tests" / "fixtures" / "workspaces"


class HistoryTests(unittest.TestCase):
    def test_create_and_update_records_append_events(self) -> None:
        with self.empty_workspace() as workspace:
            self.run_cli(
                workspace,
                "goal",
                "create",
                "GOAL-X",
                "--title",
                "Improve onboarding",
            )
            self.run_cli(
                workspace,
                "goal",
                "update",
                "GOAL-X",
                "--priority",
                "high",
            )
            events = read_history(workspace)["events"]

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["command"], "goal create")
        self.assertEqual(events[0]["action"], "created")
        self.assertEqual(events[0]["object_type"], "goal")
        self.assertEqual(events[0]["object_id"], "GOAL-X")
        self.assertEqual(events[1]["command"], "goal update")
        self.assertEqual(events[1]["changed_fields"]["priority"]["after"], "high")

    def test_lifecycle_decide_complete_and_outcome_append_events(self) -> None:
        with self.fixture_workspace("valid-workspace.json") as workspace:
            self.run_cli(
                workspace,
                "lifecycle",
                "decide",
                "HUMAN-DECISION-1",
                "--work-item-id",
                "WORK-1",
                "--human-id",
                "HUMAN-PRODUCT",
                "--reviewed-head",
                "head-1",
                "--decision",
                "accepted",
                "--status",
                "accepted",
                "--evidence-reference",
                "EVIDENCE-1",
                "--review-reference",
                "REVIEW-1",
            )
            self.run_cli(workspace, "lifecycle", "complete", "WORK-1")
            self.run_cli(
                workspace,
                "lifecycle",
                "outcome",
                "OUTCOME-1",
                "--work-item-id",
                "WORK-1",
                "--summary",
                "The checklist was accepted.",
            )
            events = read_history(workspace)["events"]
            Workspace.load(workspace)

        self.assertEqual([event["command"] for event in events], [
            "lifecycle decide",
            "lifecycle complete",
            "lifecycle outcome",
        ])
        self.assertEqual(events[0]["actor"], "HUMAN-PRODUCT")
        self.assertEqual(events[1]["action"], "completed")
        self.assertEqual(events[1]["changed_fields"]["status"]["after"], "completed")
        self.assertEqual(events[2]["object_type"], "outcome")

    def test_failed_invalid_mutation_does_not_append_event(self) -> None:
        with self.fixture_workspace("valid-workspace.json") as workspace:
            result = self.run_cli(
                workspace,
                "work",
                "complete",
                "WORK-1",
                check=False,
            )
            history_path = history_file_path(workspace)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot be completed", result.stderr)
        self.assertFalse(history_path.exists())

    def test_migrate_write_appends_event(self) -> None:
        with self.empty_workspace() as workspace:
            data_path = workspace / "workspace.json"
            data = json.loads(data_path.read_text(encoding="utf-8"))
            data.pop("schema_version")
            data_path.write_text(json.dumps(data), encoding="utf-8")

            self.run_cli(workspace, "migrate", "--write")
            history = read_history(workspace)
            Workspace.load(workspace)

        self.assertEqual(len(history["events"]), 1)
        self.assertEqual(history["events"][0]["command"], "migrate --write")
        self.assertEqual(history["events"][0]["action"], "migrated")
        self.assertEqual(history["events"][0]["object_type"], "workspace")

    def test_history_survives_multiple_mutations_and_cli_limit(self) -> None:
        with self.empty_workspace() as workspace:
            self.run_cli(workspace, "goal", "create", "GOAL-X", "--title", "First")
            self.run_cli(workspace, "goal", "create", "GOAL-Y", "--title", "Second")
            self.run_cli(workspace, "human", "create", "HUMAN-X", "--name", "X Human")
            history = json.loads(self.run_cli(workspace, "history", "--limit", "2", "--json").stdout)

        self.assertEqual(len(history["events"]), 2)
        self.assertEqual(history["events"][0]["object_id"], "GOAL-Y")
        self.assertEqual(history["events"][1]["object_id"], "HUMAN-X")

    def test_history_paths_are_workspace_relative(self) -> None:
        with self.empty_workspace() as workspace:
            self.run_cli(workspace, "goal", "create", "GOAL-X", "--title", "Portable history")
            history = read_history(workspace)
            cli_history = json.loads(self.run_cli(workspace, "history", "--json").stdout)

        serialized = json.dumps(history)
        self.assertEqual(history["workspace_file"], "workspace.json")
        self.assertEqual(history["history_file"], ".palari/history.jsonl")
        self.assertEqual(history["events"][0]["workspace_file"], "workspace.json")
        self.assertNotIn(str(workspace), serialized)
        self.assertEqual(cli_history["workspace_file"], "workspace.json")
        self.assertEqual(cli_history["history_file"], ".palari/history.jsonl")

    def test_legacy_absolute_history_event_paths_still_read(self) -> None:
        with self.empty_workspace() as workspace:
            history_path = history_file_path(workspace)
            history_path.parent.mkdir(parents=True)
            legacy_event = {
                "event_id": "event-legacy",
                "workspace_file": str(workspace / "workspace.json"),
                "object_type": "goal",
                "object_id": "GOAL-X",
            }
            history_path.write_text(json.dumps(legacy_event) + "\n", encoding="utf-8")

            history = read_history(workspace)

        self.assertEqual(history["events"][0]["workspace_file"], legacy_event["workspace_file"])

    def empty_workspace(self) -> "_WorkspaceCopy":
        data = {
            "schema_version": 1,
            "name": "History Test Workspace",
            "goals": [],
            "humans": [],
            "palaris": [],
            "work_items": [],
            "attempts": [],
            "evidence_runs": [],
            "review_verdicts": [],
            "human_decisions": [],
            "decisions": [],
            "outcomes": [],
        }
        return _WorkspaceCopy(data)

    def fixture_workspace(self, fixture_name: str) -> "_WorkspaceCopy":
        data = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
        return _WorkspaceCopy(data)

    def run_cli(
        self,
        workspace: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["PALARI_HISTORY_ACTOR"] = "test-operator"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "palari_company_os",
                "--workspace",
                str(workspace),
                *args,
            ],
            cwd=REPO_ROOT,
            env=env,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


class _WorkspaceCopy:
    def __init__(self, data: dict[str, object]) -> None:
        self.data = data

    def __enter__(self) -> Path:
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name)
        (self.path / "workspace.json").write_text(json.dumps(self.data), encoding="utf-8")
        return self.path

    def __exit__(self, *_args: object) -> None:
        self._directory.cleanup()


if __name__ == "__main__":
    unittest.main()
