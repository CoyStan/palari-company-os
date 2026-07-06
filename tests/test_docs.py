from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.repo_docs import check_docs, init_docs
from palari_company_os.workspace import Workspace

WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class DocumentationTests(unittest.TestCase):
    def test_readme_launch_path_is_scenario_first(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        quickstart_index = readme.index("## Quickstart")
        first_screen = readme[:quickstart_index]

        self.assertIn("![Palari blocks an out-of-bound file change]", first_screen)
        self.assertIn("(docs/assets/palari-dashboard-light-desktop.png)", first_screen)
        self.assertTrue((REPO_ROOT / "scripts/make_demo_assets.sh").exists())
        self.assertLess(first_screen.count("\n"), 50)
        self.assertIn("palari demo", readme)
        self.assertIn("https://coystan.github.io/palari-company-os/", readme)
        for late_noun in (
            "workbench",
            "work item",
            "receipt",
            "evidence",
            "human decision",
            "gate profile",
        ):
            self.assertNotIn(late_noun, first_screen.lower())

    def test_demo_assets_are_committed_and_regeneratable(self) -> None:
        for asset in (
            "palari-dashboard-light-desktop.png",
            "palari-dashboard-dark-desktop.png",
            "palari-dashboard-light-mobile.png",
            "palari-dashboard-dark-mobile.png",
        ):
            with self.subTest(asset=asset):
                path = REPO_ROOT / "docs" / "assets" / asset
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 1000)
        self.assertTrue((REPO_ROOT / "scripts" / "make_demo_assets.sh").exists())

    def test_demo_recording_script_is_literal_enough_for_human(self) -> None:
        script = (REPO_ROOT / "docs" / "plans" / "demo-recording-script.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("./bin/palari demo", script)
        self.assertIn("*** BLOCKED: file change is outside Sofia's write boundary ***", script)
        self.assertIn("deploy/production.yml", script)
        self.assertIn("docs/product/company-os.md", script)
        self.assertIn("0:00-0:08", script)
        self.assertIn("1:17-1:30", script)
        self.assertIn("Human Finish Step", script)

    def test_glossary_covers_core_object_headings(self) -> None:
        core = (REPO_ROOT / "docs/product/core-objects.md").read_text(encoding="utf-8")
        glossary = (REPO_ROOT / "docs/product/glossary.md").read_text(encoding="utf-8")
        headings = re.findall(r"^## (.+)$", core, flags=re.MULTILINE)

        self.assertGreater(len(headings), 0)
        for heading in headings:
            with self.subTest(heading=heading):
                marker = f"## {heading}"
                self.assertIn(marker, glossary)
                section = glossary.split(marker, 1)[1].split("\n## ", 1)[0]
                self.assertIn("You see it when", section)

    def test_newcomer_docs_link_to_glossary(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        quickstart = (REPO_ROOT / "docs/product/quickstart.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("[Glossary](docs/product/glossary.md)", readme)
        self.assertIn("[Glossary](glossary.md)", quickstart)

    def test_agent_loop_smoke_is_linked_and_names_core_commands(self) -> None:
        smoke = (REPO_ROOT / "docs/product/agent-loop-smoke.md").read_text(
            encoding="utf-8"
        )
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        for doc in (readme, agents):
            self.assertIn("docs/product/agent-loop-smoke.md", doc)

        required_snippets = [
            "./bin/palari agent next --all",
            "./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json",
            "./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json",
            "./bin/palari agent finish WORK-0003 --as PALARI-SOFIA --json",
            "./bin/palari agent doctor WORK-0003 --as PALARI-SOFIA --json",
            "./bin/palari agent loop WORK-0003 --as PALARI-SOFIA --json",
            "./bin/palari --workspace workspaces/palari-company-os agent handoff WORK-REPO-0003 --as PALARI-STEWARD --json",
            "human_action_boundary",
            "human_action_commands",
        ]

        for snippet in required_snippets:
            self.assertIn(snippet, smoke)

    def test_docs_check_current_repo_has_no_failures(self) -> None:
        result = check_docs(REPO_ROOT)

        self.assertTrue(result["ok"])
        self.assertNotEqual(result["status"], "fail")
        self.assertEqual(result["documentation_state"]["status"], "ready")
        failed = [check for check in result["checks"] if check["status"] == "fail"]
        self.assertEqual(failed, [])

    def test_docs_check_missing_docs_warns_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

            result = check_docs(repo)

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "warn")
            self.assertEqual(result["documentation_state"]["status"], "missing")
            self.assertEqual(
                result["documentation_state"]["recommended_next_command"],
                "palari docs init",
            )

    def test_docs_init_dry_run_proposes_starter_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

            result = init_docs(repo)

            self.assertFalse(result["would_mutate"])
            self.assertEqual(result["mode"], "dry-run")
            proposed = {item["path"] for item in result["files"]}
            self.assertIn("AGENTS.md", proposed)
            self.assertIn("docs/agent/repo-map.md", proposed)
            self.assertFalse((repo / "AGENTS.md").exists())

    def test_docs_init_write_does_not_overwrite_existing_docs_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (repo / "AGENTS.md").write_text("custom instructions\n", encoding="utf-8")

            result = init_docs(repo, write=True)

            self.assertTrue(result["would_mutate"])
            self.assertIn("AGENTS.md", result["skipped_existing"])
            self.assertEqual((repo / "AGENTS.md").read_text(encoding="utf-8"), "custom instructions\n")
            self.assertTrue((repo / "docs" / "agent" / "repo-map.md").exists())

    def test_cli_docs_check_emits_json_shape(self) -> None:
        result = subprocess.run(
            [str(REPO_ROOT / "bin" / "palari"), "docs", "check", "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["schema_version"], "palari.repo_docs.v1")
        self.assertEqual(payload["kind"], "docs-check")
        self.assertTrue(payload["ok"])

    def test_agent_packet_includes_compact_doc_hints(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["documentation_state"]["status"], "ready")
        paths = {item["path"] for item in packet["recommended_docs"]}
        self.assertIn("docs/agent/repo-map.md", paths)
        self.assertIn("docs/agent/contracts-and-invariants.md", paths)
        omitted_kinds = {item["kind"] for item in packet["omitted_context"]}
        self.assertIn("agent_ready_docs", omitted_kinds)
