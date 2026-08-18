from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DemoCommandTests(unittest.TestCase):
    def test_demo_journey_reaches_founder_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            demo_dir = Path(directory) / "journey"
            result = self.run_cli(
                "demo",
                "--dir",
                str(demo_dir),
                "--journey",
                "--no-pause",
                "--json",
            )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "palari.demo.journey.v1")
        titles = [step["title"] for step in payload["steps"]]
        self.assertIn("Initialize a solo-maintainer workspace", titles)
        self.assertIn("Add local R2 work for one founder", titles)
        self.assertIn("Advance records checks and stops for approval", titles)
        self.assertIn("Inbox shows the waiting human decision", titles)
        self.assertIn("Founder approves once", titles)
        self.assertNotIn("Independent review accepts the exact candidate", titles)
        commands = "\n".join(step["command"] for step in payload["steps"])
        self.assertNotIn("review record", commands)
        self.assertIn(" inbox", f" {commands} ")
        self.assertTrue(
            any(step.get("stdout") == "Status: human-decision-required" for step in payload["steps"])
        )
        self.assertTrue(
            any("AUTHORITY_PLAN_UNSATISFIABLE" in sentence for sentence in payload["plain_summary"])
        )
        self.assertTrue(
            any("without independent review" in sentence for sentence in payload["plain_summary"])
        )
        self.assertEqual(result.returncode, 0)

    def test_demo_no_pause_prints_blocked_write_moment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            demo_dir = Path(directory) / "demo"
            result = self.run_cli("demo", "--dir", str(demo_dir), "--no-pause")

        self.assertIn("*** BLOCKED:", result.stdout)
        self.assertIn("outside Sofia's allowed files", result.stdout)
        self.assertIn("deploy/production.yml", result.stdout)
        self.assertIn("Allowed files: docs/product/company-os.md", result.stdout)
        self.assertIn("records checks and finishes the safe local task", result.stdout)
        self.assertIn("What just happened:", result.stdout)

    def test_demo_json_transcript_reports_blocked_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            demo_dir = Path(directory) / "demo"
            result = self.run_cli("demo", "--dir", str(demo_dir), "--no-pause", "--json")

        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "palari.demo.v1")
        self.assertEqual(payload["no_pause"], True)
        blocked_steps = [step for step in payload["steps"] if step.get("block_marker")]
        self.assertEqual(len(blocked_steps), 1)
        self.assertEqual(blocked_steps[0]["offending_path"], "deploy/production.yml")
        transcript = json.dumps(payload)
        self.assertNotIn("Docs: missing", transcript)
        self.assertNotIn("receipt record RECEIPT-ID", transcript)
        self.assertNotIn("evidence record EVIDENCE-ID", transcript)
        self.assertNotIn("deterministic proof", transcript)
        self.assertNotIn("active attempts", transcript)
        self.assertIn("run record, and check results", transcript)
        commands = "\n".join(step["command"] for step in payload["steps"])
        self.assertNotIn("agent check", commands)
        self.assertNotIn("agent finish", commands)
        self.assertNotIn("agent handoff", commands)
        self.assertRegex(
            commands,
            re.compile(r"agent advance WORK-[0-9A-F]{12}4[0-9A-F]{3}[89AB][0-9A-F]{15}"),
        )

    def test_demo_writes_only_inside_target_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            demo_dir = parent / "demo"
            self.run_cli("demo", "--dir", str(demo_dir), "--no-pause", "--json")

            self.assertEqual([path.name for path in parent.iterdir()], ["demo"])
            self.assertTrue((demo_dir / "workspace.json").exists())
            self.assertFalse(any((demo_dir / ".palari" / "claims").glob("*.json")))
            self.assertTrue(any((demo_dir / ".palari" / "packets").iterdir()))
            self.assertTrue((demo_dir / "docs" / "product" / "company-os.md").exists())

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", *args],
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
