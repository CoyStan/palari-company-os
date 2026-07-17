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


ACME = REPO_ROOT / "examples" / "acme-company-os"


class DecisionGuideTests(unittest.TestCase):
    def test_decision_guide_summarizes_open_decision_and_safe_default(self) -> None:
        workspace = Workspace.load(ACME)

        payload = build_decision_guide(workspace, "DECISION-0001")

        self.assertEqual(payload["schema_version"], "palari.decision_guide.v1")
        self.assertEqual(payload["status"], "open")
        self.assertEqual(payload["would_mutate"], False)
        self.assertEqual(payload["decision"]["id"], "DECISION-0001")
        self.assertEqual(payload["linked_work"]["id"], "WORK-0002")
        self.assertEqual(payload["required_human"]["id"], "HUMAN-FOUNDER")
        self.assertIn("No inbox use during beta", payload["decision"]["safe_default"])
        self.assertIn("safe default", " ".join(payload["decision_focus"]))
        self.assertIn("--set \"result=...\"", payload["decision_update_command_template"])
        commands = {item["result"]: item["command"] for item in payload["decision_update_commands"]}
        self.assertIn("No inbox use during beta", commands)
        self.assertIn(
            "--set 'result=No inbox use during beta'",
            commands["No inbox use during beta"],
        )

    def test_decision_guide_can_resolve_by_linked_work(self) -> None:
        workspace = Workspace.load(ACME)

        payload = build_decision_guide(workspace, "WORK-0002")

        self.assertEqual(payload["decision"]["id"], "DECISION-0001")

    def test_cli_decision_guide_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli(
                "decision",
                "guide",
                "WORK-0002",
                "--json",
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.decision_guide.v1")
        self.assertEqual(result["decision"]["id"], "DECISION-0001")
        self.assertIn("decision_update_commands", result)

    def test_cli_decision_guide_text_shows_suggested_update_commands(self) -> None:
        result = self.run_cli("decision", "guide", "WORK-0002")

        self.assertIn("Suggested update commands:", result.stdout)
        self.assertIn("--set 'result=No inbox use during beta'", result.stdout)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(ACME), *args],
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
