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

        self.assertEqual(len(actual), 135)
        self.assertEqual(actual, expected)

    def test_public_surface_doc_classifies_core_and_visual_surfaces(self) -> None:
        surface = _read("docs/product/public-surface.md")

        self.assertIn(
            "Palari core kernel = workspace schema + agent packets + boundary checks +",
            surface,
        )
        self.assertIn("receipts/evidence/review/acceptance + integration outbox", surface)
        self.assertIn("| Dashboard and local serve | visual |", surface)
        self.assertIn("| Desktop prototype and desktop serve | visual |", surface)
        self.assertNotRegex(surface, r"(?i)dashboard and local serve \| core")
        self.assertNotRegex(surface, r"(?i)desktop prototype and desktop serve \| core")
        self.assertIn("Current CLI command count from parser inspection: **135**.", surface)

    def test_provider_surface_is_bounded(self) -> None:
        surface = _read("docs/product/public-surface.md")

        self.assertIn("Slack, GitHub, Jira, and email are dry-run planning providers only.", surface)
        self.assertIn("does not execute live provider calls for them", surface)
        self.assertIn("Linear is the only current live provider path.", surface)
        self.assertIn("governed issue", surface)
        self.assertIn("reads/imports, approved comment sends, and verified Issue webhooks", surface)
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


def _fixture_lines(name: str) -> list[str]:
    path = REPO_ROOT / "tests" / "fixtures" / name
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")
