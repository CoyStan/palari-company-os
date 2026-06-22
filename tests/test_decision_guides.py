from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.decision_guides import build_decision_guide
from palari_company_os.workspace import Workspace


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


class DecisionGuideTests(unittest.TestCase):
    def test_decision_guide_summarizes_open_decision_and_safe_default(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        payload = build_decision_guide(workspace, "DECISION-REPO-0001")

        self.assertEqual(payload["schema_version"], "palari.decision_guide.v1")
        self.assertEqual(payload["status"], "open")
        self.assertEqual(payload["would_mutate"], False)
        self.assertEqual(payload["decision"]["id"], "DECISION-REPO-0001")
        self.assertEqual(payload["linked_work"]["id"], "WORK-REPO-0005")
        self.assertEqual(payload["required_human"]["id"], "HUMAN-FOUNDER")
        self.assertIn("Do not implement external side effects", payload["decision"]["safe_default"])
        self.assertIn("safe default", " ".join(payload["decision_focus"]))
        self.assertIn("--set \"result=...\"", payload["decision_update_command_template"])
        commands = {item["result"]: item["command"] for item in payload["decision_update_commands"]}
        self.assertIn("keep disabled", commands)
        self.assertIn("--set 'result=keep disabled'", commands["keep disabled"])
        self.assertIn("defer", commands)

    def test_decision_guide_can_resolve_by_linked_work(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        payload = build_decision_guide(workspace, "WORK-REPO-0005")

        self.assertEqual(payload["decision"]["id"], "DECISION-REPO-0001")

    def test_cli_decision_guide_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli(
                "decision",
                "guide",
                "WORK-REPO-0005",
                "--json",
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.decision_guide.v1")
        self.assertEqual(result["decision"]["id"], "DECISION-REPO-0001")
        self.assertIn("decision_update_commands", result)

    def test_cli_decision_guide_text_shows_suggested_update_commands(self) -> None:
        result = self.run_cli("decision", "guide", "WORK-REPO-0005")

        self.assertIn("Suggested update commands:", result.stdout)
        self.assertIn("--set 'result=keep disabled'", result.stdout)
        self.assertIn("--set result=defer", result.stdout)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(DOGFOOD), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
