from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
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
