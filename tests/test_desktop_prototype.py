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
    def test_desktop_prototype_generation_includes_card_console_panes(self) -> None:
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
        self.assertIn('data-source-id="comment-portal"', html)
        self.assertIn('data-source-preview-title', html)
        self.assertIn('data-work-id="comment"', html)
        self.assertIn('data-work-id="fees"', html)
        self.assertIn('data-artifact-title', html)
        self.assertIn('data-document-card', html)
        self.assertIn('data-open-context="receipt"', html)
        self.assertNotIn("folder-icon", html)
        self.assertNotIn('class="source-file-row" type="button" data-mobile-pane="artifact">\n              <span class="file-icon">', html)
        self.assertIn("sources-used", html)
        self.assertIn("document-card", html)
        self.assertIn("mobile-nav", html)

        # Demo scenario data.
        self.assertIn("Maya", html)
        self.assertIn("Alex Ramirez", html)
        self.assertIn("Jordan Lee", html)
        self.assertIn("Sam Patel", html)
        self.assertIn("Public Policy / Housing", html)
        self.assertIn("Draft public comment", html)
        self.assertIn("California HCD - 2025 Housing Plan", html)
        self.assertIn("State Housing Element Law", html)
        self.assertIn("Urban Institute - ADU Guide", html)
        self.assertIn("Oakland Planning Dept - Comment Portal", html)
        self.assertIn("Mayor's Office - Internal Strategy Doc", html)
        self.assertIn("Draft public comment on Housing Element", html)
        self.assertIn("Approval required before external write", html)
        self.assertIn("Receipt (Attempt 1)", html)
        self.assertIn("Changes &amp; History", html)

        # Permission and receipt language.
        self.assertIn("Readable", html)
        self.assertIn("Inherited (readable)", html)
        self.assertIn("Writable after approval", html)
        self.assertIn("Blocked", html)
        self.assertIn("External writes", html)
        self.assertIn("No external changes to undo", html)
        self.assertIn("Did not contact stakeholders", html)

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
        self.assertIn(".source-tree", css)
        self.assertIn(".source-children", css)
        self.assertIn(".source-folder.is-collapsed", css)
        self.assertIn("transform: rotate(90deg)", css)
        self.assertIn(".source-file-row", css)
        self.assertIn(".source-file-row.is-selected", css)
        self.assertIn(".source-preview", css)
        self.assertIn(".context-card.is-focused", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("@media (max-width: 1100px)", css)
        self.assertIn(
            "grid-template-columns: minmax(286px, 310px) minmax(560px, 1fr) minmax(300px, 340px)",
            css,
        )
        self.assertNotIn(".editor-tab.is-dragging", css)
        self.assertNotIn(".panel-resizer", css)

        self.assertIn("const sourceData", js)
        self.assertIn("const workData", js)
        self.assertIn("function selectSource", js)
        self.assertIn("function selectWork", js)
        self.assertIn("function toggleSourceFolder", js)
        self.assertIn("function openContext", js)
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

        self.assertIn('role="tree" aria-label="Source permissions by folder"', html)
        self.assertIn("Readable</strong>", html)
        self.assertIn("Inherited (readable)</strong>", html)
        self.assertIn("Writable after approval</strong>", html)
        self.assertIn("Blocked</strong>", html)
        self.assertIn("source-children", html)
        self.assertIn("This work can be published to the Oakland Planning Dept portal after human approval.", html)
        self.assertIn("On it. I'll use the selected sources and keep this within scope.", html)
        self.assertIn("Used</dt><dd data-receipt-used>3 sources", html)
        self.assertIn("Created</dt><dd data-receipt-created>1 document draft", html)
        self.assertIn("External writes</dt><dd data-receipt-external>None", html)
        self.assertIn("Undo</dt><dd data-receipt-undo>No external changes to undo", html)

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
