from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "palari-execute-work"
SKILL_PATH = SKILL_DIR / "SKILL.md"


class PalariExecuteSkillTests(unittest.TestCase):
    def test_skill_has_minimal_valid_frontmatter(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
        self.assertIsNotNone(match)
        fields = {
            line.split(":", 1)[0]
            for line in match.group(1).splitlines()
            if ":" in line
        }
        self.assertEqual(fields, {"name", "description"})
        self.assertIn("name: palari-execute-work", match.group(1))
        self.assertIn("Use when", match.group(1))

    def test_skill_teaches_one_execution_path_and_stop_boundaries(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("palari agent start --next", text)
        self.assertIn("palari agent advance WORK-ID", text)
        self.assertIn("allowed_paths.write", text)
        self.assertIn("Never run `palari approve`", text)
        self.assertIn("Never perform independent review", text)
        self.assertIn("references/result-states.md", text)
        self.assertNotIn("palari agent doctor", text)
        self.assertNotIn("palari agent loop", text)
        self.assertLessEqual(len(text.splitlines()), 100)

    def test_result_reference_routes_by_owner_without_granting_authority(self) -> None:
        text = (SKILL_DIR / "references" / "result-states.md").read_text(
            encoding="utf-8"
        )
        for signal in (
            "agent_may_execute",
            "review_boundary",
            "human_boundary",
            "next_allowed_commands",
        ):
            self.assertIn(signal, text)
        self.assertIn("Never execute the command", text)
        self.assertIn("remain authoritative", text)

    def test_codex_metadata_and_readme_expose_the_canonical_skill(self) -> None:
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        tree = (ROOT / "docs" / "agent" / "repo-tree.json").read_text(
            encoding="utf-8"
        )
        self.assertIn('display_name: "Palari Execute Work"', metadata)
        self.assertIn("$palari-execute-work", metadata)
        self.assertIn("skills/palari-execute-work/SKILL.md", readme)
        self.assertIn('"skills/"', tree)


if __name__ == "__main__":
    unittest.main()
