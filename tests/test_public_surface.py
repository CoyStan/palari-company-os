from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cli_parser import build_parser


class PublicSurfaceTests(unittest.TestCase):
    def test_public_command_surface_matches_snapshot(self) -> None:
        expected = _fixture_lines("public_commands.txt")
        actual = _collect_commands()

        self.assertEqual(len(actual), 142)
        self.assertEqual(actual, expected)

    def test_default_help_leads_with_the_ordinary_journey(self) -> None:
        help_text = build_parser().format_help()

        self.assertIn(
            "init -> work add -> agent start --next -> agent advance",
            help_text,
        )
        for command in ("init", "work", "agent", "queue", "proof", "validate"):
            self.assertRegex(help_text, rf"(?m)^    {command}\s")
        self.assertNotIn("desktop-prototype", help_text)
        self.assertNotIn("human-decision      ", help_text)

        init_parser = _subparser("init")
        init_help = init_parser.format_help()
        self.assertIn("--host", init_help)
        host_action = next(
            action for action in init_parser._actions if "--host" in action.option_strings
        )
        self.assertEqual(tuple(host_action.choices), ("claude", "codex"))

    def test_public_surface_doc_classifies_core_and_supported_visual_surface(self) -> None:
        surface = _read("docs/product/public-surface.md")

        self.assertIn(
            "Palari core kernel = workspace schema + agent packets + boundary checks +",
            surface,
        )
        self.assertIn("receipts/evidence/review/acceptance + integration outbox", surface)
        self.assertIn("| Mission Control and local serve | visual |", surface)
        self.assertNotRegex(surface, r"(?i)desktop[- ]prototype|desktop[- ]serve")
        self.assertIn("Current CLI command count from parser inspection: **142**.", surface)

    def test_provider_surface_is_bounded(self) -> None:
        surface = _read("docs/product/public-surface.md")

        self.assertIn("Generic integration records keep the provider name opaque.", surface)
        self.assertIn("does not model Slack, GitHub, Jira, email", surface)
        self.assertIn("adapter or enable execution", surface)
        self.assertIn("Linear is the only current live provider path.", surface)
        self.assertIn("governed issue", surface)
        self.assertIn(
            "reads/imports, approved comment sends, approved issue status updates, and",
            surface,
        )
        self.assertIn("remains the source of truth", surface)

    def test_public_surface_is_linked_from_minimality_docs(self) -> None:
        readme = _read("README.md")
        contract = _read("docs/product/minimality-contract.md")
        invariants = _read("docs/agent/contracts-and-invariants.md")

        self.assertIn("[Public Surface](docs/product/public-surface.md)", readme)
        self.assertIn("[Public Surface](public-surface.md)", contract)
        self.assertIn("[Public Surface](../product/public-surface.md)", invariants)

    def test_runtime_dependencies_remain_empty(self) -> None:
        pyproject = _read("pyproject.toml")

        self.assertRegex(pyproject, r"(?m)^dependencies = \[\]$")


def _collect_commands() -> list[str]:
    commands: list[str] = []

    def walk(parser: Any, prefix: str = "palari") -> None:
        for action in parser._actions:
            choices = getattr(action, "choices", None)
            if not isinstance(choices, dict):
                continue
            for name, subparser in choices.items():
                if not hasattr(subparser, "_actions"):
                    continue
                command = f"{prefix} {name}"
                commands.append(command)
                walk(subparser, command)

    walk(build_parser())
    return commands


def _subparser(name: str) -> Any:
    for action in build_parser()._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and name in choices:
            return choices[name]
    raise AssertionError(f"missing subparser: {name}")


def _fixture_lines(name: str) -> list[str]:
    path = REPO_ROOT / "tests" / "fixtures" / name
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")
