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

from palari_company_os.desktop_prototype import generate_desktop_prototype


class DesktopPrototypeTests(unittest.TestCase):
    def test_desktop_prototype_generation_includes_future_shell_panes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_desktop_prototype(directory)
            index = Path(result.index_path)
            styles = Path(result.assets[0])
            script = Path(result.assets[1])
            html = index.read_text(encoding="utf-8")

        self.assertEqual(result.title, "Palari Desktop Shell Prototype")
        self.assertEqual(index.name, "index.html")
        self.assertEqual(styles.name, "styles.css")
        self.assertEqual(script.name, "app.js")
        self.assertIn("Palari Desktop Shell Prototype", html)
        self.assertIn("Maya", html)
        self.assertIn("/Public Policy / Housing", html)
        self.assertIn("/Rent Control", html)
        self.assertIn("Work check-in", html)
        self.assertIn("HB 2148 zoning modernization", html)
        self.assertIn("Private mailbox", html)
        self.assertIn("Approve Work write", html)
        self.assertIn("External writes", html)
        self.assertIn("Legal privileged notes", html)
        self.assertIn("Human decides", html)
        self.assertIn('data-mobile-pane="chat"', html)
        self.assertIn('data-target="receipt"', html)

    def test_cli_desktop_prototype_json_reports_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli("desktop-prototype", "--out", directory, "--json")
            payload = json.loads(result.stdout)

        self.assertEqual(payload["title"], "Palari Desktop Shell Prototype")
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
