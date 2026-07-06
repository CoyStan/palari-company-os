from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ACME = REPO_ROOT / "examples" / "acme-company-os"


class GovernanceCompletionTests(unittest.TestCase):
    def test_capability_policy_and_authority_are_visible_to_agents(self) -> None:
        capabilities = self.run_json("capability", "check", "WORK-0001", "--json")
        policy = self.run_json("capability", "export-policy", "WORK-0001", "--json")
        authority = self.run_json("authority", "check", "WORK-0002", "--json")
        packet = self.run_json(
            "agent",
            "brief",
            "WORK-0003",
            "--as",
            "PALARI-SOFIA",
            "--json",
        )

        self.assertTrue(capabilities["ok"])
        self.assertIn("repo-code", json.dumps(capabilities["allowed_capabilities"]))
        self.assertFalse(policy["enforcement"]["agents_may_accept_work"])
        self.assertEqual(authority["required_approval_count"], 2)
        self.assertTrue(authority["requires_human_acceptance"])
        self.assertIn("allowed_capabilities", packet)
        self.assertFalse(packet["capability_policy"]["must_not"][0].startswith("Agents may"))

    def test_proposal_adoption_and_scope_expansion_are_human_bounded(self) -> None:
        with self.temp_workspace() as workspace_file:
            rejected = self.run_cli(
                "--workspace",
                str(workspace_file),
                "proposal",
                "adopt",
                "PROP-MISSING",
                "--work-id",
                "WORK-PROP",
                "--by",
                "PALARI-SOFIA",
                "--json",
                check=False,
            )
            created = self.run_json(
                "--workspace",
                str(workspace_file),
                "proposal",
                "create",
                "PROP-1",
                "--title",
                "Draft governed proposal",
                "--goal",
                "GOAL-0001",
                "--palari",
                "PALARI-SOFIA",
                "--proposer",
                "PALARI-SOFIA",
                "--scope",
                "Write a bounded proposal note.",
                "--list",
                "allowed_resources=docs/product/company-os.md",
                "--json",
            )
            adopted = self.run_json(
                "--workspace",
                str(workspace_file),
                "proposal",
                "adopt",
                "PROP-1",
                "--work-id",
                "WORK-PROP",
                "--by",
                "HUMAN-FOUNDER",
                "--json",
            )
            expansion = self.run_json(
                "--workspace",
                str(workspace_file),
                "work",
                "expand-scope",
                "WORK-PROP",
                "--id",
                "DECISION-SCOPE",
                "--by",
                "PALARI-SOFIA",
                "--write",
                "secrets.env",
                "--reason",
                "The packet lacks this write boundary.",
                "--json",
            )
            detail = self.run_json(
                "--workspace",
                str(workspace_file),
                "detail",
                "WORK-PROP",
                "--json",
            )

        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("human not found", rejected.stderr)
        self.assertEqual(created["collection"], "proposals")
        self.assertEqual(adopted["work_item_id"], "WORK-PROP")
        self.assertEqual(expansion["decision_id"], "DECISION-SCOPE")
        self.assertIn("DECISION-SCOPE", json.dumps(detail["linked_decisions"]))
        self.assertNotIn("secrets.env", detail["work_item"].get("output_targets", []))
        self.assertEqual(detail["attention"], "needs-human-decision")

    def test_attempt_closeout_requires_clean_scope_and_evidence(self) -> None:
        with self.temp_workspace() as workspace_file:
            missing_evidence = self.run_cli(
                "--workspace",
                str(workspace_file),
                "attempt",
                "closeout",
                "ATTEMPT-0002",
                "--head-sha",
                "def5678",
                "--cleanliness",
                "clean",
                "--changed",
                "docs/product/company-os.md",
                "--json",
                check=False,
            )
            evidence = self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "record",
                "EVIDENCE-CLOSEOUT",
                "--work-item-id",
                "WORK-0003",
                "--attempt-id",
                "ATTEMPT-0002",
                "--head-sha",
                "def5678",
                "--status",
                "passed",
                "--timestamp",
                "2030-01-01T00:00:00Z",
                "--json",
            )
            closed = self.run_json(
                "--workspace",
                str(workspace_file),
                "attempt",
                "closeout",
                "ATTEMPT-0002",
                "--head-sha",
                "def5678",
                "--cleanliness",
                "clean",
                "--changed",
                "docs/product/company-os.md",
                "--json",
            )

        self.assertNotEqual(missing_evidence.returncode, 0)
        self.assertIn("cannot close out without evidence", missing_evidence.stderr)
        self.assertEqual(evidence["record_id"], "EVIDENCE-CLOSEOUT")
        self.assertEqual(closed["action"], "closed-out")

    def test_evidence_manifest_verification_detects_artifact_tampering(self) -> None:
        with self.temp_workspace() as workspace_file:
            workspace_dir = workspace_file.parent
            artifact = workspace_dir / "reports" / "evidence" / "WORK-0001" / "summary.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text('{"ok": true}\n', encoding="utf-8")
            self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "record",
                "EVIDENCE-MANIFEST",
                "--work-item-id",
                "WORK-0001",
                "--attempt-id",
                "ATTEMPT-0001",
                "--head-sha",
                "abc1234",
                "--status",
                "passed",
                "--timestamp",
                "2030-01-01T00:00:00Z",
                "--list",
                "artifacts=reports/evidence/WORK-0001/summary.json",
                "--json",
            )
            ok = self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "verify",
                "EVIDENCE-MANIFEST",
                "--json",
            )
            artifact.write_text('{"ok": false}\n', encoding="utf-8")
            tampered = self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "verify",
                "EVIDENCE-MANIFEST",
                "--json",
            )

        self.assertTrue(ok["ok"])
        self.assertFalse(tampered["ok"])
        self.assertFalse(tampered["artifact_hashes_ok"])

    def test_work_accept_records_human_decision_and_acceptance_record(self) -> None:
        with self.temp_workspace() as workspace_file:
            workspace_dir = workspace_file.parent
            artifact = workspace_dir / "reports" / "evidence" / "WORK-0001" / "summary.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text('{"ok": true}\n', encoding="utf-8")
            self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "record",
                "EVIDENCE-ACCEPT",
                "--work-item-id",
                "WORK-0001",
                "--attempt-id",
                "ATTEMPT-0001",
                "--head-sha",
                "abc1234",
                "--status",
                "passed",
                "--timestamp",
                "2030-01-01T00:00:00Z",
                "--list",
                "artifacts=reports/evidence/WORK-0001/summary.json",
                "--json",
            )
            self.run_json(
                "--workspace",
                str(workspace_file),
                "review",
                "record",
                "REVIEW-ACCEPT",
                "--work-item-id",
                "WORK-0001",
                "--reviewed-head",
                "abc1234",
                "--reviewer",
                "HUMAN-OPS",
                "--verdict",
                "accept-ready",
                "--timestamp",
                "2030-01-01T00:10:00Z",
                "--json",
            )
            accepted = self.run_json(
                "--workspace",
                str(workspace_file),
                "work",
                "accept",
                "WORK-0001",
                "--by",
                "HUMAN-FOUNDER",
                "--reviewed-head",
                "abc1234",
                "--id",
                "HUMAN-DECISION-ACCEPT",
                "--acceptance-id",
                "ACCEPTANCE-ACCEPT",
                "--reason",
                "ready for beta",
                "--json",
            )
            detail = self.run_json(
                "--workspace",
                str(workspace_file),
                "detail",
                "WORK-0001",
                "--json",
            )

        self.assertEqual(accepted["record_id"], "ACCEPTANCE-ACCEPT")
        self.assertEqual(detail["safety"]["acceptance_state"], "accepted")
        self.assertIn("HUMAN-DECISION-ACCEPT", json.dumps(detail["human_decisions"]))

    def run_json(self, *args: str) -> dict[str, object]:
        result = self.run_cli(*args)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            self.fail(f"CLI output was not valid JSON for {args}: {error}\n{result.stdout}")
        if not isinstance(payload, dict):
            self.fail(f"CLI output was not a JSON object for {args}: {payload!r}")
        return payload

    def run_cli(
        self,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", *args],
            cwd=REPO_ROOT,
            env=env,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def temp_workspace(self):
        return _TempWorkspace()


class _TempWorkspace:
    def __enter__(self) -> Path:
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name) / "workspace.json"
        shutil.copy(ACME / "workspace.json", self.path)
        return self.path

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._directory.cleanup()


if __name__ == "__main__":
    unittest.main()
