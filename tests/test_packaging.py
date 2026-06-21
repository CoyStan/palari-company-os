from __future__ import annotations

import filecmp
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_packaged_default_data_matches_canonical_repo_fixtures(self) -> None:
        pairs = [
            (
                "examples/acme-company-os/workspace.json",
                "src/palari_company_os/data/examples/acme-company-os/workspace.json",
            ),
            (
                "examples/acme-company-os/README.md",
                "src/palari_company_os/data/examples/acme-company-os/README.md",
            ),
            (
                "examples/desktop-demo/workspace.json",
                "src/palari_company_os/data/examples/desktop-demo/workspace.json",
            ),
            (
                "schemas/workspace.schema.json",
                "src/palari_company_os/data/schemas/workspace.schema.json",
            ),
        ]

        for canonical, packaged in pairs:
            with self.subTest(canonical=canonical):
                self.assertTrue(
                    filecmp.cmp(REPO_ROOT / canonical, REPO_ROOT / packaged, shallow=False),
                    f"{packaged} must stay synced with {canonical}",
                )


if __name__ == "__main__":
    unittest.main()
