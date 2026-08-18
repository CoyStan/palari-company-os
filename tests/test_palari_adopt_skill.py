from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "palari-adopt-repo"
SKILL_PATH = SKILL_DIR / "SKILL.md"


class PalariAdoptSkillTests(unittest.TestCase):
    def test_skill_has_minimal_valid_frontmatter(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
        self.assertIsNotNone(match)
        fields = {line.split(":", 1)[0] for line in match.group(1).splitlines() if ":" in line}
        self.assertEqual(fields, {"name", "description"})
        self.assertIn("name: palari-adopt-repo", match.group(1))
        self.assertIn("Use when", match.group(1))

    def test_skill_teaches_one_fresh_and_one_existing_init_path(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("palari init --palari Agent --host HOST --json", text)
        self.assertIn("palari init WORKSPACE-DIR --host HOST --as PALARI-ID --json", text)
        self.assertEqual(text.count("palari init --palari Agent"), 1)
        self.assertEqual(text.count("palari init WORKSPACE-DIR"), 1)
        self.assertIn("palari --workspace WORKSPACE-DIR validate --json", text)
        self.assertIn("The Git root and `WORKSPACE-DIR` may differ", text)
        self.assertNotIn("palari init REPO-ROOT", text)
        self.assertIn("stop and ask the human to review `/hooks`", text)
        self.assertIn("Never invent", text)
        self.assertNotIn("palari claude install", text)
        self.assertNotIn("palari cursor install", text)
        self.assertLessEqual(len(text.splitlines()), 100)

    def test_host_reference_makes_enforcement_differences_explicit(self) -> None:
        text = (SKILL_DIR / "references" / "hosts.md").read_text(encoding="utf-8")
        for host in ("claude", "codex", "cursor"):
            self.assertIn(f"`{host}`", text)
        self.assertIn("`--strict-git`", text)
        self.assertIn("through `/hooks`", text)
        self.assertIn("No host profile grants permission", text)

    def test_metadata_and_readme_expose_the_adoption_skill(self) -> None:
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('display_name: "Palari Adopt Repo"', metadata)
        self.assertIn("$palari-adopt-repo", metadata)
        self.assertIn("skills/palari-adopt-repo/SKILL.md", readme)


if __name__ == "__main__":
    unittest.main()
