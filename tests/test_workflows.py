from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_candidate_workflow_runs_one_complete_gate_and_thin_compatibility(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )

        self.assertEqual(workflow.count('branches: ["main"]'), 2)
        self.assertNotIn('branches: ["**"]', workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertIn("Candidate gate (Python 3.12)", workflow)
        self.assertIn(
            'python -m pip install "setuptools>=68" -e ".[dev]"',
            workflow,
        )
        self.assertEqual(workflow.count("./scripts/verify.sh complete"), 1)
        self.assertIn(
            'python-version: ["3.10", "3.11", "3.13", "3.14"]',
            workflow,
        )
        self.assertIn("tests.test_governance_kernel", workflow)
        self.assertIn("python -S -m palari_company_os --help", workflow)
        for duplicate in (
            "unittest discover",
            "pip wheel",
            "install_smoke.sh",
            "examples/acme-company-os",
            "workspaces/palari-company-os",
        ):
            self.assertNotIn(duplicate, workflow)

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
