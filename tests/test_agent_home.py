from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_home import build_agent_home
from palari_company_os.cli import main
from palari_company_os.workspace import Workspace
from tests.workspace_fixture import write_current_agent_workspace


class AgentHomeTests(unittest.TestCase):
    ROOT_COMPONENTS = ("goals", "team", "work", "checks", "limits")
    CHILD_COMPONENTS = {
        "work": ("projects", "ideas", "tasks", "runs"),
        "tasks": ("now", "next", "later"),
        "checks": ("records", "tests", "reviews", "choices", "results"),
        "limits": ("sources", "guides", "tools", "rules", "outside"),
        "rules": ("allowed", "ask", "never"),
        "outside": ("apps", "plans", "queue"),
    }

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.workspace_file = self.root / "workspace.json"
        write_current_agent_workspace(self.workspace_file)
        self.workspace = Workspace.load(self.workspace_file)

    def test_home_uses_three_to_five_plain_parts_without_overlap(self) -> None:
        payload = build_agent_home(self.workspace, "PALARI-STEWARD")
        tree = json.loads(
            (REPO_ROOT / "docs/agent/repo-tree.json").read_text(encoding="utf-8")
        )

        self.assertEqual(tuple(payload["components"]), self.ROOT_COMPONENTS)
        self.assertEqual(
            tuple(part["name"] for part in tree["product"]["parts"]),
            self.ROOT_COMPONENTS,
        )
        for parent, children in self.CHILD_COMPONENTS.items():
            part = payload["components"].get(parent)
            if part is None:
                part = payload["components"]["work"].get(parent)
            if part is None:
                part = payload["components"]["limits"].get(parent)
            self.assertEqual(tuple(part), children)
            self.assertLessEqual(len(children), 5)
        self.assertEqual(payload["status"], "waiting")
        self.assertEqual(
            payload["components"]["goals"]["items"][0]["id"],
            "GOAL-REPO-0001",
        )
        self.assertFalse(
            payload["components"]["limits"]["rules"]["allowed"]["grants_permission"]
        )

    def test_initiative_partitions_current_next_and_later_without_overlap(self) -> None:
        candidates = [
            _candidate("WORK-NOW", active=True),
            _candidate("WORK-NEXT"),
            _candidate("WORK-LATER"),
        ]
        next_view = {
            "candidates": candidates,
            "blockers": [],
            "next_allowed_commands": ["palari agent brief WORK-NEXT --json"],
        }
        with patch("palari_company_os.agent_home.build_agent_next", return_value=next_view):
            payload = build_agent_home(self.workspace, "PALARI-STEWARD")

        work = payload["components"]["work"]["tasks"]
        self.assertEqual([item["work_item_id"] for item in work["now"]], ["WORK-NOW"])
        self.assertEqual(work["next"]["work_item_id"], "WORK-NEXT")
        self.assertEqual(
            [item["work_item_id"] for item in work["later"]],
            ["WORK-LATER"],
        )
        self.assertEqual(payload["status"], "working")

    def test_missing_agent_fails_closed_with_the_same_five_parts(self) -> None:
        payload = build_agent_home(self.workspace, "PALARI-MISSING")

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["agent"]["found"])
        self.assertEqual(tuple(payload["components"]), self.ROOT_COMPONENTS)
        self.assertFalse(
            payload["components"]["limits"]["rules"]["allowed"]["grants_permission"]
        )

    def test_cli_json_and_text_present_the_agent_home(self) -> None:
        json_output = io.StringIO()
        with redirect_stdout(json_output):
            json_code = main(
                [
                    "--workspace",
                    str(self.workspace_file),
                    "agent",
                    "home",
                    "--as",
                    "PALARI-STEWARD",
                    "--json",
                ]
            )
        payload = json.loads(json_output.getvalue())

        text_output = io.StringIO()
        with redirect_stdout(text_output):
            text_code = main(
                [
                    "--workspace",
                    str(self.workspace_file),
                    "agent",
                    "home",
                    "--as",
                    "PALARI-STEWARD",
                ]
            )

        self.assertEqual(json_code, 0)
        self.assertEqual(text_code, 0)
        self.assertEqual(payload["schema_version"], "palari.agent_home.v2")
        self.assertEqual(set(payload["components"]), set(self.ROOT_COMPONENTS))
        rendered = text_output.getvalue()
        self.assertIn("Agent home: PALARI-STEWARD", rendered)
        self.assertIn("Goals", rendered)
        self.assertIn("Team", rendered)
        self.assertIn("Work", rendered)
        self.assertIn("Checks", rendered)
        self.assertIn("Limits", rendered)


def _candidate(work_id: str, *, active: bool = False) -> dict[str, object]:
    return {
        "work_item_id": work_id,
        "title": work_id.replace("-", " ").title(),
        "status": "active",
        "attention": "ready-for-ai-work",
        "next_step_type": "start-work",
        "next_command": f"palari agent brief {work_id} --json",
        "claim": {
            "active": active,
            "claimed_by": "PALARI-STEWARD" if active else "",
        },
        "start_blockers": [],
    }


if __name__ == "__main__":
    unittest.main()
