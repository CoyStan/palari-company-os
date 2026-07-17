from __future__ import annotations

import html as html_lib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.dashboard import generate_dashboard
from palari_company_os.workspace_init import initialize_workspace


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
        self.assertIn("Top attention", html)
        self.assertIn('<p class="top-step"><strong>Step</strong> human-decision</p>', html)
        self.assertIn("What Palaris used, made, did not do, and can undo", html)
        self.assertIn("Agent loop", html)
        self.assertIn("Agent handoff", html)
        self.assertIn("agent-safe bridge", html)
        self.assertIn("Human review and decision actions stay human-only", html)
        self.assertIn("palari agent brief WORK-0007 --as PALARI-SOFIA", html)
        self.assertIn("palari agent finish WORK-0007 --as PALARI-SOFIA", html)
        self.assertIn("palari agent doctor WORK-0007 --as PALARI-SOFIA", html)
        self.assertIn("palari agent loop WORK-0007 --as PALARI-SOFIA", html)
        self.assertIn("palari agent handoff WORK-0007 --as PALARI-SOFIA", html)
        self.assertIn("palari agent brief WORK-0007 --as PALARI-SOFIA --mode review", html)
        self.assertIn("palari agent check WORK-0007 --as PALARI-SOFIA --mode review", html)
        self.assertIn("Next commands", html)
        self.assertIn('class="copy-command"', html)
        self.assertIn('data-copy-command="palari agent handoff WORK-0007', html)
        self.assertIn("palari review guide WORK-0007 --json", html)
        self.assertIn("palari decision guide DECISION-0001 --json", html)
        self.assertIn("Decision commands", html)
        self.assertIn("palari decision update DECISION-0001", html)
        self.assertIn("result=No inbox use during beta", html)
        self.assertIn("step check-active-proof", html)
        self.assertIn("<dt>Step</dt>", html)
        self.assertIn("<dd>review-handoff</dd>", html)

    def test_dashboard_generation_handles_dogfood_workspace_trust_loop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_dashboard(DOGFOOD, directory)
            html = Path(result.index_path).read_text(encoding="utf-8")

        self.assertEqual(result.workspace, "Palari Company OS Dogfood Workspace")
        self.assertIn("SOURCE-REPO-FOUNDATION", html)
        self.assertIn("RECEIPT-REPO-0001", html)
        self.assertIn("RECEIPT-REPO-0006", html)
        self.assertIn("top-attention-card", html)
        self.assertIn("palari review guide WORK-REPO-0006 --json", html)
        self.assertIn("palari review guide WORK-REPO-0003 --json", html)
        self.assertIn("Human review and decision actions stay human-only", html)
        self.assertIn("human-decision", html)
        self.assertIn("Authority", html)

    def test_dashboard_agent_safe_command_hints_are_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_dashboard(ACME, directory)
            html = Path(result.index_path).read_text(encoding="utf-8")

        commands = {
            html_lib.unescape(command)
            for command in re.findall(r"<code>(palari .*?)</code>", html)
        }
        agent_safe_commands = sorted(
            command
            for command in commands
            if _is_agent_safe_command_hint(command)
        )
        self.assertGreater(len(agent_safe_commands), 0)
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir) / "workspace.json"
            shutil.copy(ACME / "workspace.json", workspace_path)
            for command in agent_safe_commands:
                with self.subTest(command=command):
                    self.run_cli("--workspace", str(workspace_path), *shlex.split(command)[1:])

    def test_dashboard_copy_actions_match_rendered_command_hints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_dashboard(ACME, directory)
            html = Path(result.index_path).read_text(encoding="utf-8")
            script = Path(result.assets[1]).read_text(encoding="utf-8")

        code_commands = {
            html_lib.unescape(command)
            for command in re.findall(r"<code>(palari .*?)</code>", html)
        }
        copy_commands = {
            html_lib.unescape(command)
            for command in re.findall(r'data-copy-command="(palari .*?)"', html)
        }

        self.assertGreater(len(copy_commands), 0)
        self.assertEqual(copy_commands, code_commands)
        self.assertIn("async function copyCommand", script)
        self.assertIn("navigator.clipboard.writeText", script)

    def test_dashboard_uses_real_tab_panels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_dashboard(ACME, directory)
            html = Path(result.index_path).read_text(encoding="utf-8")
            script = Path(result.assets[1]).read_text(encoding="utf-8")

        for tab in ("queue", "work", "trust", "history", "authority"):
            self.assertIn(f'data-tab-link="{tab}"', html)
            self.assertIn(f'data-tab-panel="{tab}"', html)
            self.assertIn(f'id="tab-{tab}" role="tab"', html)
            self.assertIn(f'id="panel-{tab}" role="tabpanel"', html)
        self.assertIn('role="tablist"', html)
        self.assertIn('aria-selected="false"', html)
        self.assertIn("function setActiveTab", script)
        self.assertNotIn('id="queue" class="panel"', html)

    def test_dashboard_quality_contract_markup_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_dashboard(ACME, directory)
            html = Path(result.index_path).read_text(encoding="utf-8")
            css = Path(result.assets[0]).read_text(encoding="utf-8")
            script = Path(result.assets[1]).read_text(encoding="utf-8")

        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', html)
        self.assertIn('data-theme-toggle', html)
        self.assertIn('data-theme-label', html)
        self.assertIn('aria-pressed="false"', html)
        self.assertIn("@media (prefers-color-scheme: dark)", css)
        self.assertIn(":root[data-theme=\"dark\"]", css)
        self.assertIn("palari-dashboard-theme", script)
        self.assertIn("aria-selected", script)
        for output in (html, css, script):
            self.assertNotIn('href="http://', output)
            self.assertNotIn('href="https://', output)
            self.assertNotIn('src="http://', output)
            self.assertNotIn('src="https://', output)

    def test_dashboard_empty_workspace_has_intentional_empty_states(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_directory:
            workspace_path = Path(workspace_directory) / "empty"
            initialize_workspace(workspace_path, "Empty Dashboard Workspace")
            with tempfile.TemporaryDirectory() as output_directory:
                result = generate_dashboard(workspace_path, output_directory)
                html = Path(result.index_path).read_text(encoding="utf-8")

        self.assertIn("No work items in queue.", html)
        self.assertIn("palari work create WORK-0001", html)
        self.assertIn("No selected sources recorded yet.", html)
        self.assertIn("palari source create SOURCE-0001", html)
        self.assertIn("No receipts recorded yet.", html)
        self.assertIn("palari receipt record RECEIPT-0001", html)
        self.assertIn("No humans recorded.", html)
        self.assertIn("palari human create HUMAN-FOUNDER", html)
        self.assertIn("No Palaris recorded.", html)
        self.assertIn("palari palari create PALARI-STEWARD", html)

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
            [sys.executable, "-S", "-m", "palari_company_os", *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )


def _is_agent_safe_command_hint(command: str) -> bool:
    return command.startswith(
        (
            "palari agent ",
            "palari detail ",
            "palari queue ",
            "palari validate ",
            "palari review guide ",
            "palari decision guide ",
        )
    )


if __name__ == "__main__":
    unittest.main()
