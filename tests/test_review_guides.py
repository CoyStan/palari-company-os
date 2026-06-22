from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.review_guides import build_review_guide
from palari_company_os.workspace import Workspace


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"
ACME = REPO_ROOT / "examples" / "acme-company-os"


class ReviewGuideTests(unittest.TestCase):
    def test_review_guide_summarizes_evidence_receipt_and_focus(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        payload = build_review_guide(workspace, "WORK-REPO-0003")

        self.assertEqual(payload["schema_version"], "palari.review_guide.v1")
        self.assertEqual(payload["status"], "review-needed")
        self.assertEqual(payload["would_mutate"], False)
        self.assertEqual(payload["work_item"]["id"], "WORK-REPO-0003")
        self.assertEqual(payload["evidence"]["id"], "EVIDENCE-REPO-0003")
        self.assertEqual(payload["evidence"]["head_sha"], "e0e70f")
        self.assertEqual(payload["attempt"]["id"], "ATTEMPT-REPO-0003")
        self.assertIn("src/palari_company_os/workspace.py", payload["attempt"]["changed_files"])
        self.assertEqual(payload["receipt"]["id"], "RECEIPT-REPO-0003")
        self.assertIn("Confirm forbidden actions", " ".join(payload["review_focus"]))
        self.assertIn("--verdict VERDICT", payload["review_record_command_template"])

    def test_review_guide_reports_missing_evidence(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        payload = build_review_guide(workspace, "WORK-REPO-0004")

        self.assertEqual(payload["status"], "missing-evidence")
        self.assertEqual(payload["evidence"], {"present": False})
        self.assertEqual(payload["attempt"], {"present": False})
        self.assertEqual(payload["receipt"], {"present": False})

    def test_review_guide_reports_stale_review_precisely(self) -> None:
        workspace = Workspace.load(ACME)

        payload = build_review_guide(workspace, "WORK-0006")

        self.assertEqual(payload["status"], "stale-review")
        self.assertEqual(payload["evidence"]["head_sha"], "review-fresh")
        self.assertIn("A review already exists", " ".join(payload["review_focus"]))

    def test_review_guide_keeps_receipt_ready_lightweight(self) -> None:
        workspace = Workspace.load(ACME)

        payload = build_review_guide(workspace, "WORK-0007")

        self.assertEqual(payload["status"], "receipt-ready")
        self.assertEqual(payload["evidence"], {"present": False})
        self.assertEqual(payload["receipt"]["id"], "RECEIPT-0001")
        self.assertIn("receipt-ready low-risk work", " ".join(payload["review_focus"]))

    def test_cli_review_guide_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli(
                "review",
                "guide",
                "WORK-REPO-0003",
                "--json",
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.review_guide.v1")
        self.assertEqual(result["status"], "review-needed")
        self.assertEqual(result["work_item"]["id"], "WORK-REPO-0003")

    def test_cli_agent_next_text_prints_start_blockers(self) -> None:
        result = self.run_cli("agent", "next", "--as", "PALARI-STEWARD")

        self.assertIn("start blockers:", result.stdout)
        self.assertIn("ATTENTION_NOT_STARTABLE", result.stdout)
        self.assertIn("step: review-handoff", result.stdout)

    def test_cli_agent_next_rollup_text_prints_top_candidate(self) -> None:
        result = self.run_cli("agent", "next")

        self.assertIn("Top: WORK-REPO-0005 [waiting] via PALARI-ARCHITECT", result.stdout)
        self.assertIn("step: human-decision", result.stdout)
        self.assertIn("palari decision guide DECISION-REPO-0001 --json", result.stdout)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(DOGFOOD), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
