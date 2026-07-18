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


ACME = REPO_ROOT / "examples" / "acme-company-os"


class ReviewGuideTests(unittest.TestCase):
    def test_review_guide_summarizes_evidence_receipt_and_focus(self) -> None:
        workspace = Workspace.load(ACME)

        payload = build_review_guide(workspace, "WORK-0001")

        self.assertEqual(payload["schema_version"], "palari.review_guide.v1")
        self.assertEqual(payload["status"], "has-review")
        self.assertEqual(payload["would_mutate"], False)
        self.assertEqual(payload["work_item"]["id"], "WORK-0001")
        self.assertEqual(payload["evidence"]["id"], "EVIDENCE-0001")
        self.assertEqual(payload["evidence"]["head_sha"], "abc1234")
        self.assertEqual(payload["attempt"]["id"], "ATTEMPT-0001")
        self.assertIn("examples/acme-company-os/workspace.json", payload["attempt"]["changed_files"])
        self.assertEqual(payload["receipt"]["id"], "RECEIPT-0001A")
        self.assertIn("Confirm forbidden actions", " ".join(payload["review_focus"]))
        candidates = {item["id"]: item for item in payload["reviewer_candidates"]}
        self.assertEqual(payload["reviewer_candidates"][0]["id"], "PALARI-ALFRED")
        self.assertEqual(candidates["PALARI-ALFRED"]["identity_type"], "palari")
        self.assertTrue(candidates["PALARI-ALFRED"]["agent_may_execute"])
        self.assertEqual(candidates["HUMAN-FOUNDER"]["identity_type"], "human")
        self.assertFalse(candidates["HUMAN-FOUNDER"]["agent_may_execute"])
        self.assertNotIn("HUMAN-MAINTAINER", candidates)
        self.assertEqual(payload["review_record_commands"][0]["reviewer"], "PALARI-ALFRED")
        self.assertIn("--verdict VERDICT", payload["review_record_commands"][0]["command"])
        self.assertIn("separate from acceptance", candidates["HUMAN-FOUNDER"]["reason"])
        self.assertIn("--verdict VERDICT", payload["review_record_command_template"])

    def test_review_guide_reports_missing_evidence(self) -> None:
        workspace = Workspace.load(ACME)

        payload = build_review_guide(workspace, "WORK-0003")

        self.assertEqual(payload["status"], "missing-evidence")
        self.assertEqual(payload["evidence"], {"present": False})
        self.assertEqual(payload["attempt"]["id"], "ATTEMPT-0002")
        self.assertEqual(payload["attempt"]["status"], "active")
        self.assertEqual(payload["receipt"], {"present": False})

    def test_review_guide_excludes_human_attempt_actor(self) -> None:
        raw = json.loads((ACME / "workspace.json").read_text(encoding="utf-8"))
        raw["attempts"][0]["actor"] = "HUMAN-OPS"
        raw["review_verdicts"] = [
            item for item in raw["review_verdicts"] if item["work_item_id"] != "WORK-0001"
        ]
        workspace = Workspace.from_raw(raw, ACME)

        payload = build_review_guide(workspace, "WORK-0001")

        self.assertNotIn(
            "HUMAN-OPS", {candidate["id"] for candidate in payload["reviewer_candidates"]}
        )

    def test_review_guide_reports_stale_review_precisely(self) -> None:
        workspace = Workspace.load(ACME)

        payload = build_review_guide(workspace, "WORK-0006")

        self.assertEqual(payload["status"], "stale-review")
        self.assertEqual(payload["evidence"]["head_sha"], "review-fresh")
        self.assertIn("A review already exists", " ".join(payload["review_focus"]))

    def test_cli_review_guide_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli(
                "review",
                "guide",
                "WORK-0006",
                "--json",
                workspace=ACME,
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.review_guide.v1")
        self.assertEqual(result["status"], "stale-review")
        self.assertEqual(result["work_item"]["id"], "WORK-0006")

    def test_cli_review_guide_text_shows_reviewer_candidates(self) -> None:
        result = self.run_cli("review", "guide", "WORK-0001", workspace=ACME)

        self.assertIn("Reviewer candidates:", result.stdout)
        self.assertIn("PALARI-ALFRED", result.stdout)
        self.assertIn("HUMAN-FOUNDER", result.stdout)
        self.assertIn("record: palari review record REVIEW-ID", result.stdout)
        self.assertIn("--reviewer HUMAN-FOUNDER", result.stdout)

    def test_cli_agent_next_text_prints_start_blockers(self) -> None:
        result = self.run_cli(
            "agent",
            "next",
            "--as",
            "PALARI-SOFIA",
            workspace=ACME,
        )

        self.assertIn("start blockers:", result.stdout)
        self.assertIn("ATTENTION_NOT_STARTABLE", result.stdout)
        self.assertIn("step: review-handoff", result.stdout)

    def test_cli_agent_next_rollup_text_prints_top_candidate(self) -> None:
        payload = json.loads(self.run_cli("agent", "next", "--json").stdout)
        result = self.run_cli("agent", "next")
        top = payload["top_candidate"]
        if top is None:
            self.assertIn("Status: no-ready-work", result.stdout)
            self.assertNotIn("Top:", result.stdout)
            self.assertIn("Next commands:", result.stdout)
            self.assertIn(payload["next_allowed_commands"][0], result.stdout)
            return

        availability = "ready" if top["candidate"]["can_start"] else "waiting"

        self.assertIn(
            f"Top: {top['candidate']['work_item_id']} [{availability}] "
            f"via {top['agent']['id']}",
            result.stdout,
        )
        self.assertIn(f"step: {top['candidate']['next_step_type']}", result.stdout)
        self.assertIn(payload["next_allowed_commands"][0], result.stdout)

    def run_cli(
        self,
        *args: str,
        workspace: Path = ACME,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(workspace), *args],
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
