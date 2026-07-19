from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.governance_journal import verify_journal
from palari_company_os.store import WorkspaceStore, write_store
from palari_company_os.validation import COLLECTION_FILE_KEYS


WORK_ID = "WORK-CURRENT"
ATTEMPT_ID = "ATTEMPT-CURRENT"
WORKER_ID = "PALARI-WORKER"
REVIEWER_ID = "PALARI-REVIEWER"
HUMAN_ID = "HUMAN-FOUNDER"
ARTIFACT = "result.txt"


class GovernanceCompletionTests(unittest.TestCase):
    def test_current_proof_authority_and_outcome_golden_path(self) -> None:
        with self.current_workspace(git_backed=True) as workspace_file:
            proof_head = self.git(workspace_file.parent, "rev-parse", "HEAD").stdout.strip()
            base_head = self.git(
                workspace_file.parent, "rev-parse", f"{proof_head}^"
            ).stdout.strip()

            receipt = self.run_json(
                workspace_file,
                "receipt",
                "record",
                "RECEIPT-CURRENT",
                "--work-item-id",
                WORK_ID,
                "--attempt-id",
                ATTEMPT_ID,
                "--actor",
                WORKER_ID,
                "--list",
                "actions_taken=created the bounded result",
                "--list",
                f"outputs_created={ARTIFACT}",
                "--json",
            )
            evidence = self.run_json(
                workspace_file,
                "evidence",
                "record",
                "EVIDENCE-CURRENT",
                "--work-item-id",
                WORK_ID,
                "--attempt-id",
                ATTEMPT_ID,
                "--head-sha",
                proof_head,
                "--base-ref",
                base_head,
                "--status",
                "passed",
                "--summary",
                "bounded verification passed",
                "--list",
                "commands=python -m unittest tests.test_governance_completion",
                "--list",
                f"artifacts={ARTIFACT}",
                "--json",
            )
            verified = self.run_json(
                workspace_file,
                "evidence",
                "verify",
                "EVIDENCE-CURRENT",
                "--json",
            )
            closeout = self.run_json(
                workspace_file,
                "attempt",
                "closeout",
                ATTEMPT_ID,
                "--head-sha",
                proof_head,
                "--cleanliness",
                "clean",
                "--changed",
                ARTIFACT,
                "--output-target",
                ARTIFACT,
                "--json",
            )
            review = self.run_json(
                workspace_file,
                "review",
                "record",
                "REVIEW-CURRENT",
                "--work-item-id",
                WORK_ID,
                "--reviewed-head",
                proof_head,
                "--reviewer",
                REVIEWER_ID,
                "--verdict",
                "accept-ready",
                "--json",
            )
            acceptance = self.run_json(
                workspace_file,
                "work",
                "accept",
                WORK_ID,
                "--by",
                HUMAN_ID,
                "--reviewed-head",
                proof_head,
                "--id",
                "DECISION-CURRENT",
                "--acceptance-id",
                "ACCEPTANCE-CURRENT",
                "--reason",
                "exact proof is ready",
                "--json",
            )
            outcome = self.run_json(
                workspace_file,
                "outcome",
                "record",
                "OUTCOME-CURRENT",
                "--work-item-id",
                WORK_ID,
                "--summary",
                "bounded work completed",
                "--what-happened",
                "Exact proof received independent review and human acceptance.",
                "--what-changed",
                ARTIFACT,
                "--json",
            )

            raw = json.loads(workspace_file.read_text(encoding="utf-8"))
            work = self.record(raw, "work_items", WORK_ID)
            attempt = self.record(raw, "attempts", ATTEMPT_ID)
            review_record = self.record(raw, "review_verdicts", "REVIEW-CURRENT")
            decision = self.record(raw, "human_decisions", "DECISION-CURRENT")
            acceptance_record = self.record(
                raw, "acceptance_records", "ACCEPTANCE-CURRENT"
            )
            journal = verify_journal(workspace_file, raw)

        self.assertEqual(receipt["record_id"], "RECEIPT-CURRENT")
        self.assertEqual(evidence["record_id"], "EVIDENCE-CURRENT")
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["output_coverage_ok"])
        self.assertEqual(closeout["action"], "closed-out")
        self.assertEqual(attempt["head_sha"], proof_head)
        self.assertEqual(review["record_id"], "REVIEW-CURRENT")
        self.assertEqual(review_record["reviewer"], REVIEWER_ID)
        self.assertNotEqual(review_record["reviewer"], attempt["actor"])
        self.assertTrue(review_record["proof_hash"].startswith("sha256:"))
        self.assertEqual(acceptance["record_id"], "ACCEPTANCE-CURRENT")
        self.assertIn("completed automatically", acceptance["next_action"])
        self.assertEqual(decision["human_id"], HUMAN_ID)
        self.assertEqual(decision["evidence_reference"], "EVIDENCE-CURRENT")
        self.assertEqual(decision["review_reference"], "REVIEW-CURRENT")
        self.assertEqual(acceptance_record["decision_id"], "DECISION-CURRENT")
        self.assertEqual(work["status"], "completed")
        self.assertEqual(outcome["record_id"], "OUTCOME-CURRENT")
        self.assertEqual(journal["journal_schema_version"], "palari.governance-journal.v2")
        self.assertTrue(journal["ok"])

    def test_accept_ready_review_rejects_missing_artifact(self) -> None:
        with self.current_workspace(
            artifact_present=False, git_backed=True
        ) as workspace_file:
            proof_head = self.git(
                workspace_file.parent, "rev-parse", "HEAD"
            ).stdout.strip()
            self.record_proof(workspace_file, proof_head)
            result = self.run_cli(
                workspace_file,
                "review",
                "record",
                "REVIEW-MISSING",
                "--work-item-id",
                WORK_ID,
                "--reviewed-head",
                proof_head,
                "--reviewer",
                REVIEWER_ID,
                "--verdict",
                "accept-ready",
                "--json",
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("artifact is not present", result.stderr)

    def test_attempt_actor_cannot_record_independent_review(self) -> None:
        with self.current_workspace(git_backed=True) as workspace_file:
            proof_head = self.git(
                workspace_file.parent, "rev-parse", "HEAD"
            ).stdout.strip()
            self.record_proof(workspace_file, proof_head)
            result = self.run_cli(
                workspace_file,
                "review",
                "record",
                "REVIEW-SELF",
                "--work-item-id",
                WORK_ID,
                "--reviewed-head",
                proof_head,
                "--reviewer",
                WORKER_ID,
                "--verdict",
                "accept-ready",
                "--json",
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("also attempt actor", result.stderr)

    def record_proof(self, workspace_file: Path, head_sha: str) -> None:
        raw = json.loads(workspace_file.read_text(encoding="utf-8"))
        base_sha = str(self.record(raw, "attempts", ATTEMPT_ID).get("base_sha") or "")
        self.run_json(
            workspace_file,
            "receipt",
            "record",
            "RECEIPT-CURRENT",
            "--work-item-id",
            WORK_ID,
            "--attempt-id",
            ATTEMPT_ID,
            "--actor",
            WORKER_ID,
            "--list",
            "actions_taken=created the bounded result",
            "--list",
            f"outputs_created={ARTIFACT}",
            "--json",
        )
        self.run_json(
            workspace_file,
            "evidence",
            "record",
            "EVIDENCE-CURRENT",
            "--work-item-id",
            WORK_ID,
            "--attempt-id",
            ATTEMPT_ID,
            "--head-sha",
            head_sha,
            "--base-ref",
            base_sha,
            "--status",
            "passed",
            "--list",
            "commands=focused verification",
            "--list",
            f"artifacts={ARTIFACT}",
            "--json",
        )
        self.run_json(
            workspace_file,
            "attempt",
            "closeout",
            ATTEMPT_ID,
            "--head-sha",
            head_sha,
            "--cleanliness",
            "clean",
            "--changed",
            ARTIFACT,
            "--output-target",
            ARTIFACT,
            "--json",
        )

    def run_json(self, workspace_file: Path, *args: str) -> dict[str, object]:
        result = self.run_cli(workspace_file, *args, check=False)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            self.fail(f"CLI output was not JSON for {args}: {error}\n{result.stdout}")
        if not isinstance(payload, dict):
            self.fail(f"CLI output was not an object for {args}: {payload!r}")
        if result.returncode != 0:
            self.fail(
                f"CLI failed for {args} ({result.returncode}):\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return payload

    def run_cli(
        self,
        workspace_file: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(workspace_file),
                *args,
            ],
            cwd=workspace_file.parent,
            env=env,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )

    def git(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )

    @contextmanager
    def current_workspace(
        self,
        *,
        artifact_present: bool = True,
        git_backed: bool = False,
    ) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace_file = root / "workspace.json"
            base_sha = ""
            if git_backed:
                self.git(root, "init", "--quiet")
                self.git(root, "config", "user.name", "Palari Test")
                self.git(root, "config", "user.email", "palari-test@example.invalid")
                self.git(root, "commit", "--quiet", "--allow-empty", "-m", "baseline")
                base_sha = self.git(root, "rev-parse", "HEAD").stdout.strip()
            if artifact_present:
                (root / ARTIFACT).write_text("bounded result\n", encoding="utf-8")
            write_store(
                WorkspaceStore(
                    data_path=workspace_file,
                    data=current_workspace_data(root, base_sha=base_sha),
                )
            )
            if git_backed:
                self.git(root, "add", "workspace.json", ".palari")
                if artifact_present:
                    self.git(root, "add", ARTIFACT)
                self.git(root, "commit", "--quiet", "-m", "proof candidate")
            yield workspace_file

    @staticmethod
    def record(
        raw: dict[str, object], collection: str, record_id: str
    ) -> dict[str, object]:
        records = raw[collection]
        if not isinstance(records, list):
            raise AssertionError(f"{collection} is not a list")
        return next(
            item
            for item in records
            if isinstance(item, dict) and item.get("id") == record_id
        )


def current_workspace_data(root: Path, *, base_sha: str = "") -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 2,
        "name": "Current Governance Completion Test",
    }
    for collection in COLLECTION_FILE_KEYS:
        data[collection] = []
    data["humans"] = [
        {
            "id": HUMAN_ID,
            "name": "Test Founder",
            "role": "Product authority",
            "authority_level": "admin",
            "approval_capabilities": ["product"],
            "availability": "active",
        }
    ]
    data["palaris"] = [
        {
            "id": WORKER_ID,
            "name": "Worker",
            "role": "Bounded implementer",
            "scope": "Create the declared result.",
            "owner_human": HUMAN_ID,
            "linked_goals": ["GOAL-CURRENT"],
            "forbidden_actions": ["external_write"],
        },
        {
            "id": REVIEWER_ID,
            "name": "Reviewer",
            "role": "Independent reviewer",
            "scope": "Inspect exact bounded proof.",
            "owner_human": HUMAN_ID,
            "linked_goals": ["GOAL-CURRENT"],
            "forbidden_actions": ["external_write"],
        },
    ]
    data["goals"] = [
        {
            "id": "GOAL-CURRENT",
            "title": "Complete bounded work",
            "owner": HUMAN_ID,
            "status": "active",
            "success_criteria": ["Exact governed proof completes."],
            "linked_palaris": [WORKER_ID, REVIEWER_ID],
            "linked_work": [WORK_ID],
        }
    ]
    data["workbenches"] = [
        {
            "id": "WORKBENCH-CURRENT",
            "label": "Temporary workspace",
            "goal_ids": ["GOAL-CURRENT"],
            "palari_ids": [WORKER_ID, REVIEWER_ID],
            "human_ids": [HUMAN_ID],
            "output_target_ids": [ARTIFACT],
            "status": "active",
        }
    ]
    data["work_items"] = [
        {
            "id": WORK_ID,
            "title": "Create a bounded result",
            "goal": "GOAL-CURRENT",
            "palari": WORKER_ID,
            "workbench_id": "WORKBENCH-CURRENT",
            "risk": "R4",
            "intensity": "standard",
            "status": "active",
            "scope": "Create only the declared result.",
            "allowed_resources": [ARTIFACT],
            "output_targets": [ARTIFACT],
            "path_intents": [{"path": ARTIFACT, "intent": "create"}],
            "forbidden_actions": ["external_write"],
            "acceptance_target": "Exact proof receives independent review.",
            "verification_expectations": ["The result exists and is current."],
            "current_attempt": ATTEMPT_ID,
            "required_approval_count": 1,
            "required_approval_capability": "product",
            "parallel_policy": "independent",
        }
    ]
    data["attempts"] = [
        {
            "id": ATTEMPT_ID,
            "work_item_id": WORK_ID,
            "actor": WORKER_ID,
            "status": "active",
            "workspace_path": str(root),
            "base_sha": base_sha,
            "allowed_paths": [ARTIFACT],
            "forbidden_paths": [],
            "started_at": "2026-07-18T00:00:00Z",
        }
    ]
    return data


if __name__ == "__main__":
    unittest.main()
