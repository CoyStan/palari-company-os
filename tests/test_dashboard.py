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

from palari_company_os.dashboard import generate_dashboard


ACME = REPO_ROOT / "examples" / "acme-company-os"
DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


class DashboardTests(unittest.TestCase):
    def test_dashboard_generation_includes_required_sections_and_trust_loop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_dashboard(ACME, directory)
            index = Path(result.index_path)
            styles = Path(result.assets[0])
            script = Path(result.assets[1])
            self.assertTrue(index.exists())
            self.assertTrue(styles.exists())
            self.assertTrue(script.exists())
            html = index.read_text(encoding="utf-8")

        self.assertEqual(result.workspace, "Acme Company OS Example")
        self.assertEqual(index.name, "index.html")
        self.assertEqual(styles.name, "styles.css")
        self.assertEqual(script.name, "app.js")
        for section in ("Queue", "Work", "Trust", "History", "Authority"):
            self.assertIn(section, html)
        self.assertIn("receipt-ready", html)
        self.assertIn("SOURCE-0001", html)
        self.assertIn("RECEIPT-0001", html)
        self.assertIn("Read-only dashboard", html)
        self.assertIn("What Palaris used, made, did not do, and can undo", html)

    def test_dashboard_generation_handles_dogfood_workspace_and_empty_trust(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_dashboard(DOGFOOD, directory)
            html = Path(result.index_path).read_text(encoding="utf-8")

        self.assertEqual(result.workspace, "Palari Company OS Dogfood Workspace")
        self.assertIn("No selected sources recorded yet.", html)
        self.assertIn("No receipts recorded yet.", html)
        self.assertIn("Authority", html)

    def test_dashboard_uses_real_tab_panels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_dashboard(ACME, directory)
            html = Path(result.index_path).read_text(encoding="utf-8")
            script = Path(result.assets[1]).read_text(encoding="utf-8")

        for tab in ("queue", "work", "trust", "history", "authority"):
            self.assertIn(f'data-tab-link="{tab}"', html)
            self.assertIn(f'data-tab-panel="{tab}"', html)
        self.assertIn("function setActiveTab", script)
        self.assertNotIn('id="queue" class="panel"', html)

    def test_cli_dashboard_json_reports_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(
                "--workspace",
                str(ACME),
                "dashboard",
                "--out",
                directory,
                "--json",
            )
            payload = json.loads(result.stdout)

        self.assertEqual(payload["workspace"], "Acme Company OS Example")
        self.assertTrue(payload["index_path"].endswith("index.html"))
        self.assertEqual(len(payload["assets"]), 2)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "palari_company_os", *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
