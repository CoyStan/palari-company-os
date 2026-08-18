from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "palari-review-work"
SKILL_PATH = SKILL_DIR / "SKILL.md"


class PalariReviewSkillTests(unittest.TestCase):
    def test_skill_has_minimal_valid_frontmatter(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
        self.assertIsNotNone(match)
        fields = {line.split(":", 1)[0] for line in match.group(1).splitlines() if ":" in line}
        self.assertEqual(fields, {"name", "description"})
        self.assertIn("name: palari-review-work", match.group(1))
        self.assertIn("Use when", match.group(1))

    def test_skill_teaches_exact_read_only_review_path(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("agent start WORK-ID --as REVIEWER-ID --mode review", text)
        self.assertIn("agent status WORK-ID --as REVIEWER-ID --mode review", text)
        self.assertIn("agent_action_commands", text)
        self.assertIn("review_record_commands", text)
        self.assertIn("Never review work built by the same identity", text)
        self.assertIn("Never run `palari approve`", text)
        self.assertNotIn("palari review record REVIEW-ID", text)
        self.assertLessEqual(len(text.splitlines()), 100)

    def test_verdict_reference_is_complete_and_fail_closed(self) -> None:
        text = (SKILL_DIR / "references" / "verdicts.md").read_text(encoding="utf-8")
        for verdict in (
            "accept-ready",
            "changes-requested",
            "needs-human-decision",
            "blocked",
        ):
            self.assertIn(f"`{verdict}`", text)
        self.assertIn("finding is enough to reject `accept-ready`", text)
        self.assertIn("Stale required proof is always `blocked`", text)
        self.assertIn("Palari's emitted commands remain authoritative", text)

    def test_metadata_and_readme_expose_the_review_skill(self) -> None:
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('display_name: "Palari Review Work"', metadata)
        self.assertIn("$palari-review-work", metadata)
        self.assertIn("skills/palari-review-work/SKILL.md", readme)


if __name__ == "__main__":
    unittest.main()
