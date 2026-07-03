from __future__ import annotations

import unittest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.path_policy import (
    path_allowed,
    path_candidates,
    validate_workspace_path,
)


class PathPolicyTests(unittest.TestCase):
    def test_validate_workspace_path_normalizes_relative_paths(self) -> None:
        self.assertEqual(validate_workspace_path("docs\\product\\company-os.md"), "docs/product/company-os.md")
        self.assertEqual(validate_workspace_path("./docs/product/company-os.md"), "docs/product/company-os.md")

    def test_validate_workspace_path_rejects_unsafe_paths(self) -> None:
        unsafe_paths = [
            "",
            "/etc/passwd",
            "../secrets.env",
            "docs/../secrets.env",
            "C:/Users/Alex/secrets.env",
            "C:\\Users\\Alex\\secrets.env",
        ]

        for path in unsafe_paths:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    validate_workspace_path(path)

    def test_path_allowed_allows_exact_and_descendant_paths_only(self) -> None:
        allowed = ["docs/product", "examples/acme-company-os/workspace.json"]

        self.assertTrue(path_allowed("docs/product/company-os.md", allowed))
        self.assertTrue(path_allowed("examples/acme-company-os/workspace.json", allowed))
        self.assertFalse(path_allowed("docs/private/company-os.md", allowed))
        self.assertFalse(path_allowed("docs/productivity/notes.md", allowed))
        self.assertFalse(path_allowed("../docs/product/company-os.md", allowed))

    def test_path_allowed_ignores_invalid_allowed_entries(self) -> None:
        self.assertTrue(path_allowed("docs/product/company-os.md", ["/abs/path", "docs/product"]))
        self.assertFalse(path_allowed("docs/product/company-os.md", ["/abs/path", "../docs"]))

    def test_path_candidates_extracts_and_deduplicates_path_like_tokens(self) -> None:
        candidates = path_candidates(
            "Change docs/product/company-os.md, then mention docs/product/company-os.md "
            "and maybe examples/acme-company-os/workspace.json."
        )

        self.assertEqual(
            candidates,
            [
                "docs/product/company-os.md",
                "examples/acme-company-os/workspace.json",
            ],
        )


if __name__ == "__main__":
    unittest.main()
