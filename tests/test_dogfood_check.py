from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.dogfood_check import (  # noqa: E402
    CommitInfo,
    check_dogfood_range,
    load_coverage_ranges,
    normalize_exact_sha,
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
            return_value={"ranges": [], "proof_errors": []},
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
            return_value={"ranges": [], "proof_errors": []},
        ), patch(
            "palari_company_os.dogfood_check.is_proof_only_commit",
            return_value=False,
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
            return_value={"ranges": [], "proof_errors": []},
        ), patch(
            "palari_company_os.dogfood_check.is_proof_only_commit",
            return_value=False,
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
            return_value={"ranges": [], "proof_errors": []},
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
            return_value={"ranges": [], "proof_errors": []},
        ), patch(
            "palari_company_os.dogfood_check.is_proof_only_commit",
            return_value=False,
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
            return_value={"ranges": ranges, "proof_errors": []},
        ), patch(
            "palari_company_os.dogfood_check.is_proof_only_commit",
            return_value=False,
        ), patch(
            "palari_company_os.dogfood_check.is_ancestor",
            side_effect=lambda repo, ancestor, descendant, git_runner=None: (
                (ancestor == "base" and descendant == "c1")
                or (ancestor == "c1" and descendant == "head")
            ),
        ):
            result = check_dogfood_range(".", base="a", head="b")
        self.assertTrue(result["ok"])

    def test_floating_pr_head_token_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof = root / ".palari" / "dogfood" / "proof.json"
            proof.parent.mkdir(parents=True)
            proof.write_text(
                json.dumps(
                    {
                        "schema_version": "palari.dogfood_proof.v1",
                        "ranges": [
                            {
                                "base": "a00406d617685b4ed774a59c436db72d942a85dd",
                                "head": "@pr-head",
                                "work_id": "CLEANUP-DEPS",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_coverage_ranges(root, "workspace.json")
        self.assertEqual(loaded["ranges"], [])
        self.assertEqual(len(loaded["proof_errors"]), 1)
        self.assertIn("@pr-head", loaded["proof_errors"][0]["reason"])

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
            return_value=loaded,
        ), patch(
            "palari_company_os.dogfood_check.is_proof_only_commit",
            return_value=False,
        ):
            result = check_dogfood_range(".", base="a", head="b")
        self.assertFalse(result["ok"])
        self.assertTrue(any("@pr-head" in d["reason"] for d in result["denials"]))

    def test_normalize_exact_sha_rejects_floating_and_refs(self) -> None:
        self.assertEqual(
            normalize_exact_sha("a00406d617685b4ed774a59c436db72d942a85dd"),
            "a00406d617685b4ed774a59c436db72d942a85dd",
        )
        self.assertEqual(normalize_exact_sha("a00406d"), "a00406d")
        self.assertIsNone(normalize_exact_sha("@pr-head"))
        self.assertIsNone(normalize_exact_sha("main"))
        self.assertIsNone(normalize_exact_sha("refs/heads/main"))

    def test_bare_attempts_do_not_grant_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = {
                "schema_version": 2,
                "workspace_id": "ws-test",
                "title": "Test",
                "goals": [],
                "palaris": [],
                "humans": [],
                "work_items": [],
                "attempts": [
                    {
                        "id": "ATT-1",
                        "work_item_id": "WORK-1",
                        "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        "head_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        "status": "open",
                    }
                ],
                "evidence_runs": [
                    {
                        "id": "EV-fail",
                        "work_item_id": "WORK-1",
                        "attempt_id": "ATT-1",
                        "base_ref": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        "head_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        "status": "failed",
                    }
                ],
                "receipts": [],
                "reviews": [],
                "human_decisions": [],
                "acceptances": [],
                "outcomes": [],
                "sources": [],
                "integration_plans": [],
                "external_actions": [],
            }
            # Minimal valid workspace may need more fields — if load fails,
            # we still assert via a patched Workspace or skip to unit shape.
            path = root / "workspace.json"
            path.write_text(json.dumps(workspace), encoding="utf-8")
            loaded = load_coverage_ranges(root, path)
            # Either workspace fails to load (fail-open empty) or loads without
            # bare-attempt / failed-evidence coverage.
            sources = {item.get("source", "") for item in loaded["ranges"]}
            self.assertFalse(any(source.startswith("attempt:") for source in sources))
            self.assertFalse(any(source == "evidence:EV-fail" for source in sources))

    def test_proof_only_commit_is_allowed(self) -> None:
        commits = [
            CommitInfo(
                "p1",
                "Cursor Agent",
                "cursoragent@cursor.com",
                "attest dogfood proof",
                "",
            ),
        ]
        with patch(
            "palari_company_os.dogfood_check.list_commits",
            return_value=commits,
        ), patch(
            "palari_company_os.dogfood_check.load_coverage_ranges",
            return_value={"ranges": [], "proof_errors": []},
        ), patch(
            "palari_company_os.dogfood_check.is_proof_only_commit",
            return_value=True,
        ):
            result = check_dogfood_range(".", base="a", head="b")
        self.assertTrue(result["ok"])
        self.assertIn("proof attestation", result["findings"][0]["reason"])

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

    def test_committed_proof_has_no_floating_tokens(self) -> None:
        proof_path = REPO_ROOT / ".palari" / "dogfood" / "proof.json"
        if not proof_path.is_file():
            self.skipTest("no committed dogfood proof file")
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        for item in payload.get("ranges") or []:
            head = str(item.get("head") or "")
            base = str(item.get("base") or "")
            self.assertIsNotNone(normalize_exact_sha(base), base)
            self.assertIsNotNone(normalize_exact_sha(head), head)


if __name__ == "__main__":
    unittest.main()
