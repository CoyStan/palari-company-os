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
from tests.workspace_fixture import current_recommendation_data


class DocumentationTests(unittest.TestCase):
    def test_readme_launch_path_is_scenario_first(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        quickstart_index = readme.index("## Quickstart")
        first_screen = readme[:quickstart_index]

        self.assertIn(
            "![Palari terminal showing a blocked write outside the approved boundary]",
            first_screen,
        )
        self.assertIn("(docs/assets/palari-blocked-terminal.png)", first_screen)
        self.assertTrue((REPO_ROOT / "scripts/make_demo_assets.sh").exists())
        self.assertLess(first_screen.count("\n"), 50)
        self.assertIn("palari demo", readme)
        self.assertIn("./bin/palari demo --serve", readme)
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
            "palari-blocked-terminal.png",
        ):
            with self.subTest(asset=asset):
                path = REPO_ROOT / "docs" / "assets" / asset
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 1000)
        self.assertTrue((REPO_ROOT / "scripts" / "make_demo_assets.sh").exists())

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
        self.assertLess(
            quickstart.index("palari serve --as HUMAN-FOUNDER"),
            quickstart.index("## Verify The Repo"),
        )
        command_reference = (REPO_ROOT / "docs/product/command-reference.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Mission Control", command_reference)
        self.assertIn("palari demo --serve", command_reference)

    def test_minimality_contract_is_linked_and_enforced(self) -> None:
        contract_path = REPO_ROOT / "docs/product/minimality-contract.md"
        contract = contract_path.read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        quickstart = (REPO_ROOT / "docs/product/quickstart.md").read_text(
            encoding="utf-8"
        )
        invariants = (
            REPO_ROOT / "docs/agent/contracts-and-invariants.md"
        ).read_text(encoding="utf-8")
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertTrue(contract_path.exists())
        self.assertIn("[Minimality Contract](docs/product/minimality-contract.md)", readme)
        self.assertIn("[Minimality Contract](minimality-contract.md)", quickstart)
        self.assertIn("[Minimality Contract](../product/minimality-contract.md)", invariants)
        self.assertRegex(pyproject, r"(?m)^dependencies = \[\]$")
        for forbidden_growth in (
            "runtime dependency",
            "background service by default",
            "live provider write without approval",
            "OAuth by default",
            "schema growth without governance behavior",
        ):
            self.assertIn(forbidden_growth, contract)

    def test_historical_implementation_docs_are_not_current_product_docs(self) -> None:
        archive = REPO_ROOT / "docs/archive"
        self.assertEqual(
            [path for path in archive.rglob("*") if path.is_file()],
            [],
        )
        self.assertFalse((REPO_ROOT / "docs/plans").exists())
        self.assertFalse((REPO_ROOT / "docs/research").exists())
        self.assertFalse((REPO_ROOT / "docs/product/ai-ops-memory-roadmap-review.md").exists())

        product_docs = REPO_ROOT / "docs/product"
        historical_patterns = (
            "approval-packs-*",
            "compact-journal-*",
            "deterministic-agent-*",
            "golden-path-*",
            "governance-hardening-*",
            "invisible-*",
            "opaque-*",
            "portable-*",
            "presentation-*",
            "proof-carrying-governance-*",
            "universal-agent-*",
        )
        for pattern in historical_patterns:
            with self.subTest(pattern=pattern):
                self.assertEqual(list(product_docs.glob(pattern)), [])

        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("docs/archive/", readme)
        self.assertIn("## Golden Paths", readme)

    def test_linear_operating_loop_is_linked_and_stays_minimal(self) -> None:
        loop_path = REPO_ROOT / "docs/product/linear-operating-loop.md"
        loop = loop_path.read_text(encoding="utf-8")
        quickstart = (REPO_ROOT / "docs/product/quickstart.md").read_text(
            encoding="utf-8"
        )
        command_reference = (REPO_ROOT / "docs/product/command-reference.md").read_text(
            encoding="utf-8"
        )

        self.assertTrue(loop_path.exists())
        self.assertIn("[Linear Operating Loop](linear-operating-loop.md)", quickstart)
        self.assertIn("[Linear Operating Loop](linear-operating-loop.md)", command_reference)
        for snippet in (
            "./bin/palari linear doctor --json",
            "./bin/palari linear block-template",
            "./bin/palari linear inspect-block ENG-123 --as PALARI-SOFIA --json",
            "./bin/palari linear import ENG-123 --as PALARI-SOFIA --json",
            "./bin/palari linear start ENG-123",
            "./bin/palari linear post-gate ENG-123",
            "./bin/palari linear send OUTBOX-ID --by HUMAN-FOUNDER --confirm --json",
            "./bin/palari linear webhook serve --host 127.0.0.1 --port 0 --json",
            "./bin/palari linear webhook verify",
            "./bin/palari linear webhook events --limit 20 --json",
            "./bin/palari linear status ENG-123 --json",
            "./bin/palari linear linked --json",
        ):
            self.assertIn(snippet, loop)
        for non_goal in (
            "OAuth",
            "Linear status writes",
            "Linear label writes",
            "Linear Agent Sessions",
            "background runners",
        ):
            self.assertIn(non_goal, loop)

    def test_agent_loop_smoke_is_linked_and_names_core_commands(self) -> None:
        smoke = (REPO_ROOT / "docs/product/agent-loop-smoke.md").read_text(
            encoding="utf-8"
        )
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        for doc in (readme, agents):
            self.assertIn("docs/product/agent-loop-smoke.md", doc)

        required_snippets = [
            'PALARI_SMOKE_ROOT="$(mktemp -d)"',
            'cp -R examples/acme-company-os "$PALARI_SMOKE_ROOT/workspace"',
            './bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent next --all',
            './bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json',
            './bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent check WORK-0003 --as PALARI-SOFIA --mode execute --json',
            './bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent finish WORK-0003 --as PALARI-SOFIA --json',
            './bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent doctor WORK-0003 --as PALARI-SOFIA --json',
            './bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent loop WORK-0003 --as PALARI-SOFIA --json',
            './bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent handoff WORK-0001 --as PALARI-ALFRED --json',
            "human_action_boundary",
            "human_action_commands",
        ]

        for snippet in required_snippets:
            self.assertIn(snippet, smoke)
        self.assertNotIn("--workspace workspaces/palari-company-os", smoke)

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
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "pyproject.toml").write_text(
                "[project]\nname='docs-cli-fixture'\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(REPO_ROOT / "bin" / "palari"),
                    "docs",
                    "check",
                    "--repo",
                    str(repo),
                    "--json",
                ],
                cwd=repo,
                text=True,
                capture_output=True,
                check=True,
            )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["schema_version"], "palari.repo_docs.v1")
        self.assertEqual(payload["kind"], "docs-check")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["repo"], str(repo))

    def test_agent_packet_includes_compact_doc_hints(self) -> None:
        workspace = Workspace.from_raw(current_recommendation_data(), REPO_ROOT)

        packet = build_agent_brief(workspace, "WORK-1", "PALARI-1", "execute")

        self.assertEqual(packet["documentation_state"]["status"], "ready")
        paths = {item["path"] for item in packet["recommended_docs"]}
        self.assertIn("docs/agent/repo-map.md", paths)
        self.assertIn("docs/agent/contracts-and-invariants.md", paths)
        omitted_kinds = {item["kind"] for item in packet["omitted_context"]}
        self.assertIn("agent_ready_docs", omitted_kinds)
