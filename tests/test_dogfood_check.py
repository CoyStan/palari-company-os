from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.dogfood_check import (  # noqa: E402
    CommitInfo,
    check_dogfood_range,
)


class DogfoodCheckTests(unittest.TestCase):
    def test_human_no_claim_commits_remain_green(self) -> None:
        commits = [
            CommitInfo("h1", "Human", "human@example.com", "fix typo", ""),
        ]
        with patch(
            "palari_company_os.dogfood_check.list_commits",
            return_value=commits,
        ), patch(
            "palari_company_os.dogfood_check.load_coverage_ranges",
            return_value=[],
        ):
            result = check_dogfood_range(".", base="a", head="b")
        self.assertTrue(result["ok"])
        self.assertEqual(result["findings"][0]["status"], "allow")

    def test_agent_commit_without_coverage_is_denied(self) -> None:
        commits = [
            CommitInfo(
                "a1",
                "Cursor Agent",
                "cursoragent@cursor.com",
                "agent change",
                "",
            ),
        ]
        with patch(
            "palari_company_os.dogfood_check.list_commits",
            return_value=commits,
        ), patch(
            "palari_company_os.dogfood_check.load_coverage_ranges",
            return_value=[],
        ):
            result = check_dogfood_range(".", base="a", head="b")
        self.assertFalse(result["ok"])
        self.assertEqual(result["denials"][0]["sha"], "a1")

    def test_agent_skip_trailer_is_rejected(self) -> None:
        commits = [
            CommitInfo(
                "a2",
                "Claude",
                "noreply@anthropic.com",
                "agent change",
                "skip-dogfood: emergency",
            ),
        ]
        with patch(
            "palari_company_os.dogfood_check.list_commits",
            return_value=commits,
        ), patch(
            "palari_company_os.dogfood_check.load_coverage_ranges",
            return_value=[],
        ):
            result = check_dogfood_range(".", base="a", head="b")
        self.assertFalse(result["ok"])
        self.assertIn("reserved for human", result["denials"][0]["reason"])

    def test_human_on_labeled_pr_can_skip(self) -> None:
        commits = [
            CommitInfo(
                "h2",
                "Human",
                "human@example.com",
                "hotfix",
                "skip-dogfood: emergency hotfix outside claim loop",
            ),
        ]
        with patch(
            "palari_company_os.dogfood_check.list_commits",
            return_value=commits,
        ), patch(
            "palari_company_os.dogfood_check.load_coverage_ranges",
            return_value=[],
        ):
            result = check_dogfood_range(
                ".",
                base="a",
                head="b",
                labels={"agent"},
            )
        self.assertTrue(result["ok"])

    def test_human_on_labeled_pr_without_skip_is_denied(self) -> None:
        commits = [
            CommitInfo("h3", "Human", "human@example.com", "labeled change", ""),
        ]
        with patch(
            "palari_company_os.dogfood_check.list_commits",
            return_value=commits,
        ), patch(
            "palari_company_os.dogfood_check.load_coverage_ranges",
            return_value=[],
        ):
            result = check_dogfood_range(
                ".",
                base="a",
                head="b",
                labels={"cursor"},
            )
        self.assertFalse(result["ok"])

    def test_covering_range_allows_agent_commit(self) -> None:
        commits = [
            CommitInfo(
                "c1",
                "Cursor Agent",
                "cursoragent@cursor.com",
                "covered",
                "",
            ),
        ]
        ranges = [
            {
                "base": "base",
                "head": "head",
                "source": "proof-file",
                "work_id": "WORK-1",
            }
        ]
        with patch(
            "palari_company_os.dogfood_check.list_commits",
            return_value=commits,
        ), patch(
            "palari_company_os.dogfood_check.load_coverage_ranges",
            return_value=ranges,
        ), patch(
            "palari_company_os.dogfood_check.is_ancestor",
            side_effect=lambda repo, ancestor, descendant, git_runner=None: (
                (ancestor == "base" and descendant == "c1")
                or (ancestor == "c1" and descendant == "head")
            ),
        ):
            result = check_dogfood_range(".", base="a", head="b")
        self.assertTrue(result["ok"])

    def test_script_entrypoint_empty_range_is_green(self) -> None:
        script = REPO_ROOT / "scripts" / "check_dogfood.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--base",
                "HEAD",
                "--head",
                "HEAD",
                "--json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["commit_count"], 0)


if __name__ == "__main__":
    unittest.main()
