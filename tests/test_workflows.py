from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_pages_workflow_generates_dashboard_and_desktop_prototype(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")

        self.assertIn('branches: ["main"]', workflow)
        self.assertIn("permissions:", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("palari --workspace examples/acme-company-os dashboard --out public", workflow)
        self.assertIn("palari desktop-prototype --out public/desktop", workflow)
        self.assertIn("actions/upload-pages-artifact", workflow)
        self.assertIn("actions/deploy-pages", workflow)

    def test_release_workflow_builds_checks_publishes_and_creates_release(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn('tags: ["v*"]', workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("python -m build", workflow)
        self.assertIn("twine check dist/*", workflow)
        self.assertIn("pypa/gh-action-pypi-publish@release/v1", workflow)
        self.assertIn("CHANGELOG.md", workflow)
        self.assertIn("gh release create", workflow)


if __name__ == "__main__":
    unittest.main()
