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
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.pcaw_workspace import governance_case_from_workspace
from palari_company_os.workspace import Workspace


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
            artifact = workspace_dir / "examples" / "acme-company-os" / "workspace.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text('{"ok": true}\n', encoding="utf-8")
            self.run_cli(
                "--workspace",
                str(workspace_file),
                "receipt",
                "record",
                "RECEIPT-ACCEPT",
                "--work-item-id",
                "WORK-0001",
                "--attempt-id",
                "ATTEMPT-0001",
                "--actor",
                "PALARI-SOFIA",
                "--list",
                "actions_taken=verified bounded output",
                "--list",
                "outputs_created=examples/acme-company-os/workspace.json",
                "--json",
            )
            self.run_cli(
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
                "--summary",
                "verification passed",
                "--timestamp",
                "2030-01-01T00:00:00Z",
                "--list",
                "commands=python3 -m unittest tests.test_governance_completion",
                "--list",
                "artifacts=examples/acme-company-os/workspace.json",
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
            raw = json.loads(workspace_file.read_text(encoding="utf-8"))
            receipt = next(
                item for item in raw["receipts"] if item["id"] == "RECEIPT-ACCEPT"
            )
            receipt["actions_taken"].append("tampered after evidence")
            workspace_file.write_text(json.dumps(raw), encoding="utf-8")
            receipt_tampered = self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "verify",
                "EVIDENCE-MANIFEST",
                "--json",
                check=False,
            )
            receipt["actions_taken"].pop()
            workspace_file.write_text(json.dumps(raw), encoding="utf-8")
            artifact.write_text('{"ok": false}\n', encoding="utf-8")
            tampered = self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "verify",
                "EVIDENCE-MANIFEST",
                "--json",
                check=False,
            )
            self.run_cli(
                "--workspace",
                str(workspace_file),
                "evidence",
                "update",
                "EVIDENCE-MANIFEST",
                "--list",
                "artifacts=",
                "--json",
            )
            cleared_result = self.run_cli(
                "--workspace",
                str(workspace_file),
                "evidence",
                "verify",
                "EVIDENCE-MANIFEST",
                "--json",
                check=False,
            )
            cleared = json.loads(cleared_result.stdout)

        self.assertTrue(ok["ok"])
        self.assertFalse(receipt_tampered["ok"])
        self.assertFalse(receipt_tampered["receipt_checks"][0]["ok"])
        self.assertFalse(tampered["ok"])
        self.assertFalse(tampered["artifact_hashes_ok"])
        self.assertFalse(cleared["ok"])
        self.assertEqual(cleared_result.returncode, 1)
        self.assertEqual(
            cleared["output_binding_version"], "palari.evidence_outputs.v1"
        )
        self.assertTrue(cleared["output_coverage_required"])
        self.assertFalse(cleared["output_coverage_ok"])
        self.assertEqual(
            cleared["unhashed_receipt_outputs"],
            ["examples/acme-company-os/workspace.json"],
        )
        self.assertEqual(cleared["declared_artifact_hashes"], [])

    def test_nested_workspace_hashes_outputs_from_bounded_attempt_root(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            repo_root = Path(root_name)
            workspace_file = repo_root / "workspaces" / "dogfood" / "workspace.json"
            workspace_file.parent.mkdir(parents=True)
            raw = json.loads((ACME / "workspace.json").read_text(encoding="utf-8"))
            attempt = next(item for item in raw["attempts"] if item["id"] == "ATTEMPT-0002")
            attempt["workspace_path"] = str(repo_root)
            attempt["allowed_paths"] = ["docs/product/company-os.md"]
            work = next(item for item in raw["work_items"] if item["id"] == "WORK-0003")
            work["risk"] = "R4"
            work["required_approval_count"] = 1
            work["required_approval_capability"] = "product"
            workspace_file.write_text(json.dumps(raw), encoding="utf-8")
            artifact = repo_root / "docs" / "product" / "company-os.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("bounded result\n", encoding="utf-8")

            receipt_result = self.run_cli(
                "--workspace",
                str(workspace_file),
                "receipt",
                "record",
                "RECEIPT-NESTED",
                "--work-item-id",
                "WORK-0003",
                "--attempt-id",
                "ATTEMPT-0002",
                "--actor",
                "PALARI-SOFIA",
                "--list",
                "actions_taken=created bounded result",
                "--list",
                "outputs_created=docs/product/company-os.md",
                "--json",
                check=False,
            )
            self.assertEqual(receipt_result.returncode, 0, receipt_result.stderr)
            self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "record",
                "EVIDENCE-NESTED",
                "--work-item-id",
                "WORK-0003",
                "--attempt-id",
                "ATTEMPT-0002",
                "--head-sha",
                "def5678",
                "--status",
                "passed",
                "--summary",
                "nested workspace verification passed",
                "--list",
                "commands=python3 -m unittest tests.test_governance_completion",
                "--list",
                "artifacts=docs/product/company-os.md",
                "--json",
            )
            verified = self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "verify",
                "EVIDENCE-NESTED",
                "--json",
            )
            governance_case, subjects = governance_case_from_workspace(
                Workspace.load(workspace_file),
                "WORK-0003",
            )
            self.run_json(
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
                "--output-target",
                "docs/product/company-os.md",
                "--json",
            )
            self.run_json(
                "--workspace",
                str(workspace_file),
                "review",
                "record",
                "REVIEW-NESTED",
                "--work-item-id",
                "WORK-0003",
                "--reviewed-head",
                "def5678",
                "--reviewer",
                "HUMAN-FOUNDER",
                "--verdict",
                "accept-ready",
                "--json",
            )
            self.run_json(
                "--workspace",
                str(workspace_file),
                "human-decision",
                "record",
                "DECISION-NESTED",
                "--work-item-id",
                "WORK-0003",
                "--human-id",
                "HUMAN-FOUNDER",
                "--reviewed-head",
                "def5678",
                "--decision",
                "accepted",
                "--status",
                "accepted",
                "--quorum-status",
                "met",
                "--evidence-reference",
                "EVIDENCE-NESTED",
                "--review-reference",
                "REVIEW-NESTED",
                "--json",
            )
            completed = self.run_json(
                "--workspace",
                str(workspace_file),
                "work",
                "complete",
                "WORK-0003",
                "--json",
            )

        self.assertTrue(verified["ok"])
        self.assertTrue(verified["output_coverage_ok"])
        self.assertEqual(verified["unhashed_receipt_outputs"], [])
        self.assertEqual(verified["declared_artifact_hashes"][0]["status"], "present")
        self.assertEqual(governance_case.observations.subject_integrity.status, "verified")
        self.assertEqual(
            subjects[0]["name"],
            verified["declared_artifact_hashes"][0]["path"],
        )
        self.assertEqual(
            f"sha256:{subjects[0]['sha256']}",
            verified["declared_artifact_hashes"][0]["sha256"],
        )
        self.assertEqual(completed["action"], "completed")

    def test_new_output_binding_rejects_vacuous_empty_manifest(self) -> None:
        with self.temp_workspace() as workspace_file:
            self.run_json(
                "--workspace",
                str(workspace_file),
                "receipt",
                "record",
                "RECEIPT-EMPTY",
                "--work-item-id",
                "WORK-0003",
                "--attempt-id",
                "ATTEMPT-0002",
                "--actor",
                "PALARI-SOFIA",
                "--list",
                "actions_taken=verified no declared output",
                "--list",
                "outputs_created=",
                "--json",
            )
            self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "record",
                "EVIDENCE-EMPTY",
                "--work-item-id",
                "WORK-0003",
                "--attempt-id",
                "ATTEMPT-0002",
                "--head-sha",
                "def5678",
                "--status",
                "passed",
                "--summary",
                "empty output proof must fail",
                "--list",
                "commands=python3 -m unittest tests.test_governance_completion",
                "--list",
                "artifacts=",
                "--json",
            )
            result = self.run_cli(
                "--workspace",
                str(workspace_file),
                "evidence",
                "verify",
                "EVIDENCE-EMPTY",
                "--json",
                check=False,
            )
            payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["output_coverage_ok"])
        self.assertTrue(payload["output_coverage_required"])
        self.assertEqual(payload["declared_receipt_outputs"], [])

    def test_work_accept_records_human_decision_and_acceptance_record(self) -> None:
        with self.temp_workspace() as workspace_file:
            workspace_dir = workspace_file.parent
            artifact = workspace_dir / "examples" / "acme-company-os" / "workspace.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text('{"ok": true}\n', encoding="utf-8")
            self.run_json(
                "--workspace",
                str(workspace_file),
                "receipt",
                "record",
                "RECEIPT-WORK-ACCEPT",
                "--work-item-id",
                "WORK-0001",
                "--attempt-id",
                "ATTEMPT-0001",
                "--actor",
                "PALARI-SOFIA",
                "--list",
                "actions_taken=verified bounded output",
                "--list",
                "outputs_created=examples/acme-company-os/workspace.json",
                "--json",
            )
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
                "--summary",
                "verification passed",
                "--timestamp",
                "2030-01-01T00:00:00Z",
                "--list",
                "commands=python3 -m unittest tests.test_governance_completion",
                "--list",
                "artifacts=examples/acme-company-os/workspace.json",
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
            raw = json.loads(workspace_file.read_text(encoding="utf-8"))
            review = next(
                item for item in raw["review_verdicts"] if item["id"] == "REVIEW-ACCEPT"
            )
            stale = self.run_cli(
                "--workspace",
                str(workspace_file),
                "work",
                "update",
                "WORK-0001",
                "--set",
                "scope=Substantively changed after review.",
                "--json",
                check=False,
            )

        self.assertEqual(accepted["record_id"], "ACCEPTANCE-ACCEPT")
        self.assertEqual(detail["safety"]["acceptance_state"], "accepted")
        self.assertIn("HUMAN-DECISION-ACCEPT", json.dumps(detail["human_decisions"]))
        self.assertTrue(review["proof_hash"].startswith("sha256:"))
        self.assertEqual(review["attempt_id"], "ATTEMPT-0001")
        self.assertEqual(review["evidence_reference"], "EVIDENCE-ACCEPT")
        self.assertEqual(review["receipt_reference"], "RECEIPT-WORK-ACCEPT")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("review_reference is stale for the work contract", stale.stderr)

    def test_accept_ready_review_rejects_missing_artifact(self) -> None:
        with self.temp_workspace() as workspace_file:
            self.run_json(
                "--workspace",
                str(workspace_file),
                "receipt",
                "record",
                "RECEIPT-MISSING-ARTIFACT",
                "--work-item-id",
                "WORK-0001",
                "--attempt-id",
                "ATTEMPT-0001",
                "--actor",
                "PALARI-SOFIA",
                "--list",
                "actions_taken=ran bounded verification",
                "--list",
                "outputs_created=examples/acme-company-os/workspace.json",
                "--json",
            )
            self.run_json(
                "--workspace",
                str(workspace_file),
                "evidence",
                "record",
                "EVIDENCE-MISSING-ARTIFACT",
                "--work-item-id",
                "WORK-0001",
                "--attempt-id",
                "ATTEMPT-0001",
                "--head-sha",
                "abc1234",
                "--status",
                "passed",
                "--summary",
                "verification claimed",
                "--timestamp",
                "2030-01-02T00:00:00Z",
                "--list",
                "commands=python3 -m unittest tests.test_governance_completion",
                "--list",
                "artifacts=reports/evidence/does-not-exist.json",
                "--json",
            )
            result = self.run_cli(
                "--workspace",
                str(workspace_file),
                "review",
                "record",
                "REVIEW-MISSING-ARTIFACT",
                "--work-item-id",
                "WORK-0001",
                "--reviewed-head",
                "abc1234",
                "--reviewer",
                "HUMAN-OPS",
                "--verdict",
                "accept-ready",
                "--json",
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("artifact is not present", result.stderr)

    def run_json(self, *args: str, check: bool = True) -> dict[str, object]:
        result = self.run_cli(*args, check=check)
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
