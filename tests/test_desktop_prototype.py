from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from html import unescape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.desktop_prototype import (
    DEFAULT_DESKTOP_DEMO_FIXTURE,
    generate_desktop_prototype,
    load_desktop_demo_data,
    validate_desktop_app_data,
)


class DesktopPrototypeTests(unittest.TestCase):
    def test_desktop_demo_fixture_matches_documented_contract(self) -> None:
        data = load_desktop_demo_data()

        self.assertTrue(DEFAULT_DESKTOP_DEMO_FIXTURE.exists())
        self.assertEqual(data["schema_version"], "desktop-app-data/v0")
        self.assertEqual(data["selected_workbench_id"], "workbench_public_policy_housing")
        self.assertIn("human_alex_ramirez", data["humans"])
        self.assertIn("palari_maya_policy", data["palaris"])
        self.assertIn("hcd-plan", data["sources"])
        self.assertIn("comment", data["work_items"])
        self.assertIn("memo", data["work_items"])

        validate_desktop_app_data(data)

    def test_desktop_demo_fixture_rejects_sources_outside_work_item_boundary(self) -> None:
        data = deepcopy(load_desktop_demo_data())
        data["work_items"]["comment"]["attempts"]["comment-attempt-1"]["sources_used"].append("private-email")

        with self.assertRaisesRegex(ValueError, "outside work item boundary"):
            validate_desktop_app_data(data)

    def test_desktop_prototype_renders_from_supplied_fixture_data(self) -> None:
        data = deepcopy(load_desktop_demo_data())
        data["sources"]["hcd-plan"]["title"] = "Fixture controlled housing plan"
        data["work_items"]["comment"]["artifact_title"] = "Fixture controlled public comment"

        with tempfile.TemporaryDirectory() as directory:
            result = generate_desktop_prototype(directory, data=data)
            html = Path(result.index_path).read_text(encoding="utf-8")
            js = Path(result.assets[1]).read_text(encoding="utf-8")

        self.assertIn("Fixture controlled housing plan", html)
        self.assertIn("Fixture controlled housing plan", js)
        self.assertIn("Fixture controlled public comment", html)
        self.assertIn("Fixture controlled public comment", js)

    def test_desktop_prototype_generation_includes_card_console_panes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_desktop_prototype(directory)
            index = Path(result.index_path)
            styles = Path(result.assets[0])
            script = Path(result.assets[1])
            html = index.read_text(encoding="utf-8")
            visible_html = unescape(html)

        self.assertEqual(result.title, "Palari Desktop Shell Prototype")
        self.assertEqual(index.name, "index.html")
        self.assertEqual(styles.name, "styles.css")
        self.assertEqual(script.name, "app.js")
        self.assertIn("Palari Desktop Shell Prototype", html)

        # Reference-image card console anatomy.
        self.assertIn("nav-rail", html)
        self.assertIn("workspace-console", html)
        self.assertIn("workbench-panel", html)
        self.assertIn("artifact-panel", html)
        self.assertIn("context-column", html)
        self.assertIn("approval-banner", html)
        self.assertIn("source-tree", html)
        self.assertIn("source-folder-row", html)
        self.assertIn("source-file-row", html)
        self.assertIn("source-preview", html)
        self.assertIn('<span class="tree-caret" aria-hidden="true">&gt;</span>', html)
        self.assertNotIn('<span class="tree-caret" aria-hidden="true">v</span>', html)
        self.assertIn('data-source-toggle', html)
        self.assertIn('data-source-id="hcd-plan"', html)
        self.assertIn('data-source-id="tenant-memo"', html)
        self.assertIn('data-source-id="private-email"', html)
        self.assertIn('data-source-id="comment-portal"', html)
        self.assertIn('data-source-preview-title', html)
        self.assertIn('data-source-preview-provider', html)
        self.assertIn('data-source-preview-access', html)
        self.assertIn('data-work-id="comment"', html)
        self.assertIn('data-work-id="fees"', html)
        self.assertIn('data-work-id="memo"', html)
        self.assertIn('data-artifact-title', html)
        self.assertIn('data-document-card', html)
        self.assertIn('data-chat-thread', html)
        self.assertIn('data-authority-list', html)
        self.assertIn('data-history-list', html)
        self.assertIn('data-open-context="receipt"', html)
        self.assertIn('data-open-context="kilo"', html)
        self.assertIn('data-context-card="kilo"', html)
        self.assertIn("data-kilo-preview", html)
        self.assertIn("data-kilo-run", html)
        self.assertNotIn("folder-icon", html)
        self.assertNotIn('class="source-file-row" type="button" data-mobile-pane="artifact">\n              <span class="file-icon">', html)
        self.assertIn("sources-used", html)
        self.assertIn("document-card", html)
        self.assertIn("mobile-nav", html)

        # Demo scenario data.
        self.assertIn("Maya", visible_html)
        self.assertIn("Alex Ramirez", visible_html)
        self.assertIn("Jordan Lee", visible_html)
        self.assertIn("Sam Patel", visible_html)
        self.assertIn("Public Policy / Housing", visible_html)
        self.assertIn("Draft public comment", visible_html)
        self.assertIn("California HCD - 2025 Housing Plan", visible_html)
        self.assertIn("State Housing Element Law", visible_html)
        self.assertIn("Urban Institute - ADU Guide", visible_html)
        self.assertIn("Oakland Planning Dept - Comment Portal", visible_html)
        self.assertIn("Mayor's Office - Internal Strategy Doc", visible_html)
        self.assertIn("Draft public comment on Housing Element", visible_html)
        self.assertIn("Approval required before external write", visible_html)
        self.assertIn("Receipt (Attempt 1)", visible_html)
        self.assertIn("Changes & History", visible_html)

        # Permission and receipt language.
        self.assertIn("Readable", visible_html)
        self.assertIn("Inherited (readable)", visible_html)
        self.assertIn("Writable after approval", visible_html)
        self.assertIn("Blocked", visible_html)
        self.assertIn("External writes", visible_html)
        self.assertIn("No external changes to undo", visible_html)
        self.assertIn("Did not contact stakeholders", visible_html)

        # Mobile single-pane navigation.
        self.assertIn('data-mobile-target="workbench"', html)
        self.assertIn('data-mobile-target="artifact"', html)
        self.assertIn('data-mobile-target="receipt"', html)
        self.assertIn('data-context-card="authority"', html)

        # The old VS Code prototype anatomy should not return.
        self.assertNotIn("activity-bar", html)
        self.assertNotIn("editor-tabs", html)
        self.assertNotIn("bottom-panel", html)
        self.assertNotIn("status-bar", html)

    def test_cli_desktop_prototype_json_reports_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli("desktop-prototype", "--out", directory, "--json")
            payload = json.loads(result.stdout)

        self.assertEqual(payload["title"], "Palari Desktop Shell Prototype")
        self.assertTrue(payload["index_path"].endswith("index.html"))
        self.assertEqual(len(payload["assets"]), 2)

    def test_desktop_prototype_styles_match_card_console_direction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_desktop_prototype(directory)
            index = Path(result.index_path)
            styles = Path(result.assets[0])
            script = Path(result.assets[1])
            html = index.read_text(encoding="utf-8")
            css = styles.read_text(encoding="utf-8")
            js = script.read_text(encoding="utf-8")

        self.assertIn("workspace-console", html)
        self.assertIn("context-card", html)

        self.assertIn(".workspace-console", css)
        self.assertIn(".approval-banner", css)
        self.assertIn(".context-card", css)
        self.assertIn(".kilo-card", css)
        self.assertIn(".kilo-output", css)
        self.assertIn(".source-tree", css)
        self.assertIn(".source-children", css)
        self.assertIn(".source-folder.is-collapsed", css)
        self.assertIn("transform: rotate(90deg)", css)
        self.assertIn(".source-file-row", css)
        self.assertIn(".source-file-row.is-selected", css)
        self.assertIn(".source-preview", css)
        self.assertIn("width: max-content", css)
        self.assertIn("min-width: 24px", css)
        self.assertIn(".source-meta-list", css)
        self.assertIn(".context-card.is-focused", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("@media (max-width: 1100px)", css)
        self.assertIn(
            "grid-template-columns: minmax(286px, 310px) minmax(560px, 1fr) minmax(300px, 340px)",
            css,
        )
        self.assertNotIn(".editor-tab.is-dragging", css)
        self.assertNotIn(".panel-resizer", css)

        self.assertIn("const MOBILE_BREAKPOINT = prototypeData.ui.mobile_breakpoint || 1100", js)
        self.assertIn("const prototypeData", js)
        self.assertIn('"schema_version": "desktop-app-data/v0"', js)
        self.assertIn('"workspace_public_policy_demo"', js)
        self.assertIn('"palari_maya_policy"', js)
        self.assertIn("allowed_palari_ids", js)
        self.assertIn("allowed_source_ids", js)
        self.assertIn("output_target_ids", js)
        self.assertNotIn("allowedPalaris", js)
        self.assertNotIn("allowedSources", js)
        self.assertNotIn("outputTargets", js)
        self.assertIn("const sourceData = prototypeData.sources", js)
        self.assertIn("const workData = prototypeData.work_items", js)
        self.assertIn("function selectSource", js)
        self.assertIn("function selectWork", js)
        self.assertIn("function renderChat", js)
        self.assertIn("function renderAuthority", js)
        self.assertIn("function renderHistory", js)
        self.assertIn("function toggleSourceFolder", js)
        self.assertIn("function openContext", js)
        self.assertIn("async function requestKilo", js)
        self.assertIn('fetch("/api/kilo/status"', js)
        self.assertIn('fetch("/api/kilo/run"', js)
        self.assertIn("function setMobileTarget", js)
        self.assertIn("mobilePaneMap", js)
        self.assertIn("data-mobile-target", js)
        self.assertIn("data-mobile-pane", js)
        self.assertIn("dataset.contextCard", js)
        self.assertNotIn("function closeEditorTab", js)
        self.assertNotIn("function initEditorTabDrag", js)

    def test_desktop_prototype_sources_and_receipts_are_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_desktop_prototype(directory)
            index = Path(result.index_path)
            html = index.read_text(encoding="utf-8")
            visible_html = unescape(html)

        self.assertIn('role="tree" aria-label="Source permissions by folder"', html)
        self.assertIn("Readable</strong>", html)
        self.assertIn("Inherited (readable)</strong>", html)
        self.assertIn("Writable after approval</strong>", html)
        self.assertIn("Blocked</strong>", html)
        self.assertIn("source-children", html)
        self.assertIn("This work can be published to the Oakland Planning Dept portal after human approval.", html)
        self.assertIn("On it. I'll use the selected sources and keep this within scope.", visible_html)
        self.assertIn("Used</dt><dd data-receipt-used>3 sources", html)
        self.assertIn("Created</dt><dd data-receipt-created>1 document draft", html)
        self.assertIn("External writes</dt><dd data-receipt-external>None", html)
        self.assertIn("Undo</dt><dd data-receipt-undo>No external changes to undo", html)

    def test_desktop_prototype_script_is_valid_javascript_when_node_is_available(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node is not available for JavaScript syntax validation")

        with tempfile.TemporaryDirectory() as directory:
            result = generate_desktop_prototype(directory)
            script = Path(result.assets[1])

            subprocess.run(
                ["node", "--check", str(script)],
                cwd=REPO_ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

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
