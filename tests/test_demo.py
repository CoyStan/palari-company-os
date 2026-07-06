from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DemoCommandTests(unittest.TestCase):
    def test_demo_no_pause_prints_blocked_write_moment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            demo_dir = Path(directory) / "demo"
            result = self.run_cli("demo", "--dir", str(demo_dir), "--no-pause")

        self.assertIn("*** BLOCKED:", result.stdout)
        self.assertIn("deploy/production.yml", result.stdout)
        self.assertIn("Allowed write paths: docs/product/company-os.md", result.stdout)
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

    def test_demo_writes_only_inside_target_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            demo_dir = parent / "demo"
            self.run_cli("demo", "--dir", str(demo_dir), "--no-pause", "--json")

            self.assertEqual([path.name for path in parent.iterdir()], ["demo"])
            self.assertTrue((demo_dir / "workspace.json").exists())
            self.assertTrue((demo_dir / ".palari" / "claims" / "WORK-0003.json").exists())
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
