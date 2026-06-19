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
        # VS Code workbench anatomy
        self.assertIn("activity-bar", html)
        self.assertIn("primary-sidebar", html)
        self.assertIn("editor-tabs", html)
        self.assertIn("breadcrumbs", html)
        self.assertIn("secondary-sidebar", html)
        self.assertIn("bottom-panel", html)
        self.assertIn("status-bar", html)
        self.assertIn("titlebar", html)
        # demo scenario data
        self.assertIn("Maya", html)
        self.assertIn("Public Policy / Housing", html)
        self.assertIn("Rent Control", html)
        self.assertIn("Work check-in", html)
        self.assertIn("HB 2148 zoning modernization", html)
        self.assertIn("Home [SSH: PALARI_DEV2]", html)
        self.assertIn("palari-company-os", html)
        self.assertIn("sources", html)
        self.assertIn("selected", html)
        self.assertIn("work-items", html)
        self.assertIn("public-comment-hb-2148.md", html)
        self.assertIn("Private mailbox", html)
        self.assertIn("Approve Work write", html)
        self.assertIn("External writes", html)
        self.assertIn("Legal privileged notes", html)
        self.assertIn("Needs human decision", html)
        self.assertIn("Rafa", html)
        self.assertIn("Diego", html)
        self.assertIn("Clara", html)
        # permission language
        self.assertIn("readable", html)
        self.assertIn("blocked", html)
        self.assertIn("inherited", html)
        self.assertIn("write after approval", html)
        # mobile single-pane navigation
        self.assertIn('data-mobile-pane="chat"', html)
        self.assertIn('data-mobile-pane="explorer"', html)
        self.assertIn('data-mobile-pane="draft"', html)
        self.assertIn('data-mobile-pane="checkin"', html)
        self.assertIn('data-target="receipt"', html)

    def test_cli_desktop_prototype_json_reports_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli("desktop-prototype", "--out", directory, "--json")
            payload = json.loads(result.stdout)

        self.assertEqual(payload["title"], "Palari Desktop Shell Prototype")
        self.assertTrue(payload["index_path"].endswith("index.html"))
        self.assertEqual(len(payload["assets"]), 2)

    def test_desktop_prototype_includes_polished_workbench_interactions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_desktop_prototype(directory)
            index = Path(result.index_path)
            styles = Path(result.assets[0])
            script = Path(result.assets[1])
            html = index.read_text(encoding="utf-8")
            css = styles.read_text(encoding="utf-8")
            js = script.read_text(encoding="utf-8")

        self.assertIn('draggable="true"', html)
        self.assertIn('data-close-tab="draft"', html)
        self.assertIn('data-pinned="true"', html)
        self.assertIn('id="panel-resizer"', html)
        self.assertIn("data-panel-collapse", html)
        self.assertIn('tabindex="0" data-target="receipt"', html)

        self.assertIn(".editor-tab.is-dragging", css)
        self.assertIn(".panel-resizer", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("grid-template-columns: repeat(5, minmax(0,1fr))", css)

        self.assertIn("function closeEditorTab", js)
        self.assertIn("function initEditorTabDrag", js)
        self.assertIn("function initBottomPanelResize", js)
        self.assertIn("function updateMobileContext", js)
        self.assertIn('changes: "chat", authority: "chat"', js)

    def test_desktop_prototype_explorer_uses_folder_file_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = generate_desktop_prototype(directory)
            index = Path(result.index_path)
            styles = Path(result.assets[0])
            script = Path(result.assets[1])
            html = index.read_text(encoding="utf-8")
            css = styles.read_text(encoding="utf-8")
            js = script.read_text(encoding="utf-8")

        self.assertIn('data-tree="workspace"', html)
        self.assertIn('data-folder-toggle', html)
        self.assertIn('data-collapse-tree', html)
        self.assertIn('class="tree workspace-tree"', html)
        self.assertIn("HB 2148 zoning modernization.md", html)
        self.assertIn("Housing committee staff analysis.md", html)
        self.assertIn("public-comment-draft.receipt.json", html)
        self.assertNotIn("Sources &amp; Permissions", html)

        self.assertIn(".workspace-tree ol", css)
        self.assertIn(".folder-row .tree-icon", css)
        self.assertIn(".file-row .file-icon", css)

        self.assertIn("function toggleFolderRow", js)
        self.assertIn("function setFolderExpanded", js)
        self.assertIn("[data-collapse-tree]", js)

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
