from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class VerifyPageTests(unittest.TestCase):
    def test_verify_readme_states_honesty_bounds(self) -> None:
        text = (REPO_ROOT / "verify" / "README.md").read_text(encoding="utf-8")
        self.assertIn("Not WRP-10", text)
        self.assertIn("unsigned pcaw v1", text.lower())
        self.assertIn("palari proof verify", text)

    def test_index_does_not_claim_signatures(self) -> None:
        html = (REPO_ROOT / "verify" / "index.html").read_text(encoding="utf-8")
        self.assertIn("does not verify signatures", html.lower())
        self.assertIn("Not WRP-10", html)
        self.assertIn("pcaw_integrity.js", html)

    def test_fixture_matches_spec_vector(self) -> None:
        fixture = REPO_ROOT / "verify" / "fixtures" / "accepted" / "statement.json"
        vector = (
            REPO_ROOT / "spec" / "pcaw" / "v1" / "vectors" / "valid" / "accepted" / "statement.json"
        )
        self.assertEqual(fixture.read_bytes(), vector.read_bytes())

    def test_node_integrity_suite(self) -> None:
        script = REPO_ROOT / "verify" / "test_integrity.mjs"
        completed = subprocess.run(
            ["node", str(script)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("OK:", completed.stdout)

    def test_public_surface_lists_verify_page(self) -> None:
        surface = (REPO_ROOT / "docs" / "product" / "public-surface.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Drop-a-receipt verifier", surface)


if __name__ == "__main__":
    unittest.main()
