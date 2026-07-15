from __future__ import annotations

import json
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_advance import (
    agent_advance,
    agent_advance_dry_run,
    plan_advance,
)
from palari_company_os.agent_runtime import start_agent
from palari_company_os.agent_runtime import release_agent
from palari_company_os.authoring import create_record, reconcile_agent_proof
from palari_company_os.cli_dispatch import run_command
from palari_company_os.cli_output_agent import print_agent_done
from palari_company_os.cli_parser import build_parser
from palari_company_os.governance_journal import checkpoint_workspace_journal
from palari_company_os.verification_attestations import (
    VerificationContext,
    VerificationProfile,
    cache_key,
    run_or_reuse,
)
from palari_company_os.workspace import Workspace as Ws
from palari_company_os.workspace import WorkspaceError
from tests.workspace_fixture import write_portable_agent_workspace


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


class AdvancePlannerTests(unittest.TestCase):
    def test_plan_is_deterministic_and_input_order_independent(self) -> None:
        facts = self._facts()
        first = plan_advance(facts)
        permuted = deepcopy(facts)
        permuted["git"]["changed_files"].reverse()
        permuted["verification_profiles"].reverse()

        second = plan_advance(permuted)

        self.assertEqual(first, second)
        self.assertTrue(first["can_advance"])
        self.assertEqual(first["expected_state"], "review-required")
        self.assertEqual(first["stop_boundary"], "independent-review")

    def test_stale_claim_context_fails_closed_and_changes_digest(self) -> None:
        facts = self._facts()
        current = plan_advance(facts)
        facts["claim"]["context_hash"] = "sha256:stale"

        stale = plan_advance(facts)

        self.assertFalse(stale["can_advance"])
        self.assertIn("CLAIM_CONTEXT_STALE", {item["code"] for item in stale["blockers"]})
        self.assertNotEqual(current["plan_digest"], stale["plan_digest"])

    def test_dirty_scope_escape_and_missing_outputs_are_all_diagnosed(self) -> None:
        facts = self._facts()
        facts["git"].update(clean=False, scope_ok=False, outputs_ok=False)

        plan = plan_advance(facts)

        self.assertFalse(plan["can_advance"])
        self.assertEqual(
            {"GIT_DIRTY", "SCOPE_VIOLATION", "OUTPUT_MISSING"},
            {item["code"] for item in plan["blockers"]},
        )

    def test_r1_light_zero_approval_plan_completes_without_human_authority(self) -> None:
        facts = self._facts()
        facts["work"].update(risk="R1", intensity="light", required_approval_count=0)

        plan = plan_advance(facts)

        self.assertEqual(plan["expected_state"], "completed")
        self.assertEqual(plan["stop_boundary"], "none")
        self.assertIn("lifecycle-complete", [item["step"] for item in plan["steps"]])
        self.assertNotIn("review-handoff", [item["step"] for item in plan["steps"]])

    def _facts(self) -> dict[str, object]:
        return {
            "actor": "PALARI-STEWARD",
            "work": {
                "id": "WORK-TEST",
                "palari": "PALARI-STEWARD",
                "risk": "R4",
                "intensity": "high",
                "status": "active",
                "required_approval_count": 1,
                "current_attempt": "ATTEMPT-TEST",
            },
            "packet": {"status": "ready", "context_hash": "sha256:packet"},
            "claim": {
                "status": "pass",
                "claimed_by": "PALARI-STEWARD",
                "context_hash": "sha256:packet",
                "base_sha": "base",
            },
            "git": {
                "base_sha": "base",
                "head_sha": "head",
                "clean": True,
                "changed_files": ["src/b.py", "src/a.py"],
                "scope_ok": True,
                "outputs_ok": True,
            },
            "proof": {
                "attempt_id": "ATTEMPT-TEST",
                "receipt_id": "RECEIPT-TEST",
                "evidence_id": "EVIDENCE-TEST",
                "attempt_current": True,
                "attempt_bound": True,
                "receipt_current": False,
                "evidence_current": False,
                "attempt_closed": False,
            },
            "verification_profiles": [
                {"profile_id": "z", "cache_key": "sha256:z", "status": "required"},
                {"profile_id": "a", "cache_key": "sha256:a", "status": "required"},
            ],
            "workspace_digest": "sha256:workspace",
        }


class VerificationAttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        (self.temp_dir / "workspace.json").write_text("{}\n", encoding="utf-8")
        self.profile = VerificationProfile("focused", ("python3", "-c", "pass"), 10)
        self.context = VerificationContext(
            head_sha="a" * 40,
            base_sha="b" * 40,
            changed_paths=("src/a.py",),
            cleanliness="clean",
            source_digest="sha256:" + "c" * 64,
            python="cpython-test",
            platform="linux-test",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_matching_advisory_pass_is_reverified(self) -> None:
        first_runner = Mock(
            return_value=subprocess.CompletedProcess(self.profile.argv, 0, b"ok", b"")
        )
        first = run_or_reuse(
            self.temp_dir,
            REPO_ROOT,
            self.profile,
            self.context,
            runner=first_runner,
        )
        second_runner = Mock(
            return_value=subprocess.CompletedProcess(self.profile.argv, 0, b"ok", b"")
        )

        second = run_or_reuse(
            self.temp_dir,
            REPO_ROOT,
            self.profile,
            self.context,
            runner=second_runner,
        )

        self.assertFalse(first["cache_hit"])
        self.assertFalse(second["cache_hit"])
        self.assertTrue(second["cache_observed"])
        second_runner.assert_called_once()
        self.assertEqual(
            first["attestation"]["cache_key"], second["attestation"]["cache_key"]
        )

    def test_forged_cached_pass_cannot_create_passing_evidence(self) -> None:
        failed_runner = Mock(
            return_value=subprocess.CompletedProcess(self.profile.argv, 1, b"", b"failed")
        )
        failed = run_or_reuse(
            self.temp_dir,
            REPO_ROOT,
            self.profile,
            self.context,
            runner=failed_runner,
        )
        key = failed["attestation"]["cache_key"].removeprefix("sha256:")
        path = self.temp_dir / ".palari" / "verification" / f"{key}.json"
        forged = dict(failed["attestation"])
        forged.update(status="passed", exit_code=0)
        path.write_text(json.dumps(forged), encoding="utf-8")
        actual_runner = Mock(
            return_value=subprocess.CompletedProcess(self.profile.argv, 1, b"", b"still failed")
        )

        result = run_or_reuse(
            self.temp_dir,
            REPO_ROOT,
            self.profile,
            self.context,
            runner=actual_runner,
        )

        actual_runner.assert_called_once()
        self.assertFalse(result["cache_hit"])
        self.assertTrue(result["cache_observed"])
        self.assertEqual(result["attestation"]["status"], "failed")

    def test_head_profile_environment_and_dirty_state_do_not_reuse(self) -> None:
        runner = Mock(
            return_value=subprocess.CompletedProcess(self.profile.argv, 0, b"ok", b"")
        )
        run_or_reuse(self.temp_dir, REPO_ROOT, self.profile, self.context, runner=runner)
        changed_head = VerificationContext(**{**self.context.__dict__, "head_sha": "d" * 40})
        changed_python = VerificationContext(**{**self.context.__dict__, "python": "other"})
        changed_profile = VerificationProfile("focused", ("python3", "-c", "x = 1"), 10)

        run_or_reuse(self.temp_dir, REPO_ROOT, self.profile, changed_head, runner=runner)
        run_or_reuse(self.temp_dir, REPO_ROOT, self.profile, changed_python, runner=runner)
        run_or_reuse(self.temp_dir, REPO_ROOT, changed_profile, self.context, runner=runner)

        self.assertEqual(runner.call_count, 4)
        with self.assertRaisesRegex(WorkspaceError, "exactly clean"):
            dirty = VerificationContext(**{**self.context.__dict__, "cleanliness": "dirty"})
            run_or_reuse(self.temp_dir, REPO_ROOT, self.profile, dirty, runner=runner)

    def test_failure_is_recorded_but_never_reused_as_pass(self) -> None:
        runner = Mock(
            return_value=subprocess.CompletedProcess(self.profile.argv, 1, b"", b"failure")
        )
        result = run_or_reuse(
            self.temp_dir,
            REPO_ROOT,
            self.profile,
            self.context,
            runner=runner,
        )

        self.assertEqual(result["attestation"]["status"], "failed")
        with self.assertRaisesRegex(WorkspaceError, "not passing"):
            run_or_reuse(self.temp_dir, REPO_ROOT, self.profile, self.context)

    def test_malformed_duplicate_and_contradictory_cache_fail_closed(self) -> None:
        key = cache_key(self.profile, self.context).removeprefix("sha256:")
        directory = self.temp_dir / ".palari" / "verification"
        directory.mkdir(parents=True)
        path = directory / f"{key}.json"
        path.write_text('{"status":"passed","status":"failed"}\n', encoding="utf-8")
        with self.assertRaisesRegex(WorkspaceError, "duplicate JSON key"):
            run_or_reuse(self.temp_dir, REPO_ROOT, self.profile, self.context)

        path.unlink()
        runner = Mock(
            return_value=subprocess.CompletedProcess(self.profile.argv, 0, b"ok", b"")
        )
        result = run_or_reuse(
            self.temp_dir,
            REPO_ROOT,
            self.profile,
            self.context,
            runner=runner,
        )
        payload = result["attestation"]
        payload["exit_code"] = 7
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(WorkspaceError, "contradicts"):
            run_or_reuse(self.temp_dir, REPO_ROOT, self.profile, self.context)

    def test_symlink_cache_escape_is_rejected(self) -> None:
        outside = self.temp_dir.parent / f"{self.temp_dir.name}-outside"
        outside.mkdir()
        try:
            (self.temp_dir / ".palari").symlink_to(outside, target_is_directory=True)
            runner = Mock(
                return_value=subprocess.CompletedProcess(self.profile.argv, 0, b"ok", b"")
            )
            with self.assertRaisesRegex(WorkspaceError, "symlink"):
                run_or_reuse(
                    self.temp_dir,
                    REPO_ROOT,
                    self.profile,
                    self.context,
                    runner=runner,
                )
            self.assertFalse((outside / "verification").exists())
        finally:
            shutil.rmtree(outside, ignore_errors=True)


class AgentAdvanceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        write_portable_agent_workspace(
            DOGFOOD / "workspace.json",
            self.temp_dir / "workspace.json",
        )
        palari = self.temp_dir / ".palari"
        if palari.exists():
            shutil.rmtree(palari)
        self.work_id = "WORK-TEST-ADVANCE"
        create_record(
            str(self.temp_dir),
            "work",
            {
                "id": self.work_id,
                "title": "Test deterministic advance",
                "palari": "PALARI-STEWARD",
                "goal": "GOAL-REPO-0001",
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R4",
                "intensity": "high",
                "required_approval_count": 1,
                "required_approval_capability": "architecture",
                "scope": "Change one bounded artifact",
                "acceptance_target": "Exact proof reaches review",
                "status": "active",
                "allowed_resources": ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": ["README.md"],
                "forbidden_actions": ["deploy", "human_review"],
                "verification_expectations": ["repository verification"],
            },
            command="test setup",
        )
        checkpoint = checkpoint_workspace_journal(self.temp_dir, "PALARI-STEWARD")
        self.assertTrue(checkpoint["ok"])
        (self.temp_dir / "README.md").write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.temp_dir)], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "governed baseline"],
            check=True,
        )
        start_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            "execute",
        )
        (self.temp_dir / "README.md").write_text("after\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "bounded output"],
            check=True,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_one_command_reaches_review_and_repeated_call_is_idempotent(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ) as runner:
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(first["status"], "review-required")
        self.assertTrue(first["handoff"]["review_handoff"])
        self.assertEqual(runner.call_count, 3)
        workspace = Ws.load(self.temp_dir)
        counts = (len(workspace.attempts), len(workspace.receipts), len(workspace.evidence_runs))

        second = agent_advance(
            workspace,
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(second["status"], "review-required")
        resumed = Ws.load(self.temp_dir)
        self.assertEqual(
            counts,
            (len(resumed.attempts), len(resumed.receipts), len(resumed.evidence_runs)),
        )
        self.assertFalse(second["would_mutate"])

    def test_dry_run_never_executes_verification_or_mutates(self) -> None:
        before = (self.temp_dir / "workspace.json").read_bytes()
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=AssertionError("dry-run executed verification"),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                dry_run=True,
            )

        self.assertEqual(result["status"], "planned")
        self.assertTrue(result["can_advance"])
        self.assertEqual(before, (self.temp_dir / "workspace.json").read_bytes())

    def test_cli_dry_run_json_result_and_text_output_are_stable(self) -> None:
        args = build_parser().parse_args(
            [
                "--workspace",
                str(self.temp_dir),
                "agent",
                "advance",
                self.work_id,
                "--as",
                "PALARI-STEWARD",
                "--dry-run",
                "--json",
            ]
        )

        result = run_command(args)

        self.assertEqual(result.kind, "agent-done")
        self.assertEqual(result.payload["schema_version"], "palari.agent_advance.v1")
        self.assertEqual(result.payload["status"], "planned")
        self.assertTrue(result.payload["fast_path"])
        output = io.StringIO()
        with redirect_stdout(output):
            print_agent_done(result.payload, False)
        rendered = output.getvalue()
        self.assertIn(f"Agent advance: {self.work_id}", rendered)
        self.assertIn("Status: planned", rendered)
        self.assertIn("review-handoff: required", rendered)

    def test_fast_dry_run_rejects_any_workspace_byte_drift(self) -> None:
        data_path = self.temp_dir / "workspace.json"
        data_path.write_bytes(data_path.read_bytes() + b"\n")

        result = agent_advance_dry_run(
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            ["WORKSPACE_CHANGED_SINCE_CLAIM"],
            [item["code"] for item in result["blockers"]],
        )

    def test_r1_advance_completes_without_human_authority(self) -> None:
        release_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )
        work_id = "WORK-TEST-ADVANCE-R1"
        create_record(
            str(self.temp_dir),
            "work",
            {
                "id": work_id,
                "title": "Test low-risk deterministic advance",
                "palari": "PALARI-STEWARD",
                "goal": "GOAL-REPO-0001",
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R1",
                "intensity": "light",
                "required_approval_count": 0,
                "scope": "Change one bounded artifact",
                "acceptance_target": "Bounded work completes",
                "status": "active",
                "allowed_resources": ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": ["README.md"],
                "forbidden_actions": ["deploy", "human_review"],
                "verification_expectations": ["affected verification"],
            },
            command="test setup",
        )
        start_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        (self.temp_dir / "README.md").write_text("r1 after\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "r1 bounded output"],
            check=True,
        )
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ) as runner:
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(runner.call_count, 1)
        completed = Ws.load(self.temp_dir).work_item(work_id)
        self.assertIsNotNone(completed)
        assert completed is not None
        self.assertEqual(completed.status, "completed")

        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        with journal.open("a", encoding="utf-8") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(WorkspaceError, "valid journal continuity"):
            agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                work_id,
                "PALARI-STEWARD",
            )

    def test_crash_before_workspace_replace_aborts_prepare_and_retries(self) -> None:
        self._crash_reconciliation("before_apply")
        workspace = Ws.load(self.temp_dir)
        self.assertFalse(any(item.work_item_id == self.work_id for item in workspace.evidence_runs))

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            result = agent_advance(
                workspace,
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "review-required", result)

    def test_crash_after_workspace_replace_recovers_commit_without_rerun(self) -> None:
        self._crash_reconciliation("after_apply")
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=AssertionError("committed proof reran verification"),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "review-required")
        self.assertFalse(result["would_mutate"])

    def test_completed_proof_resume_rejects_wrong_actor_before_recovery(self) -> None:
        self._crash_reconciliation("after_apply")

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-REVIEWER",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "ACTOR_NOT_ASSIGNED")

    def test_completed_proof_resume_rejects_missing_claim_before_recovery(self) -> None:
        self._crash_reconciliation("after_apply")
        release_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "RESUME_PREFLIGHT_FAILED")

    def test_completed_proof_resume_rejects_stale_claim_packet(self) -> None:
        self._crash_reconciliation("after_apply")
        packet_path = next((self.temp_dir / ".palari" / "packets").glob("*.json"))
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["stop_conditions"] = ["forged packet authority"]
        packet_path.write_text(json.dumps(packet), encoding="utf-8")

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "RESUME_PREFLIGHT_FAILED")

    def test_completed_proof_resume_rejects_dirty_allowed_path(self) -> None:
        self._crash_reconciliation("after_apply")
        (self.temp_dir / "README.md").write_text("dirty after proof\n", encoding="utf-8")
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        before_journal = journal.read_bytes()

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "RESUME_PREFLIGHT_FAILED")
        self.assertEqual(before_journal, journal.read_bytes())

    def test_completed_proof_resume_rejects_dirty_unapproved_path(self) -> None:
        self._crash_reconciliation("after_apply")
        (self.temp_dir / "unapproved.txt").write_text("dirty after proof\n", encoding="utf-8")
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        before_journal = journal.read_bytes()

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "RESUME_PREFLIGHT_FAILED")
        self.assertEqual(before_journal, journal.read_bytes())

    def test_pending_prepare_rejects_dirty_scope_without_journal_mutation(self) -> None:
        self._crash_reconciliation("before_apply")
        (self.temp_dir / "unapproved.txt").write_text("dirty during prepare\n", encoding="utf-8")
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        before_journal = journal.read_bytes()

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "RESUME_PREFLIGHT_FAILED")
        self.assertEqual(before_journal, journal.read_bytes())

    def test_completed_proof_resume_rejects_new_protected_dirt(self) -> None:
        self._crash_reconciliation("after_apply")
        protected = self.temp_dir / "docs" / "company"
        protected.mkdir(parents=True)
        (protected / "private.md").write_text("must remain outside scope\n", encoding="utf-8")
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        before_journal = journal.read_bytes()

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "RESUME_PREFLIGHT_FAILED")
        self.assertEqual(before_journal, journal.read_bytes())

    def test_atomic_reconciliation_rejects_missing_artifact_before_mutation(self) -> None:
        head = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        (self.temp_dir / "README.md").unlink()
        before = (self.temp_dir / "workspace.json").read_bytes()

        with self.assertRaisesRegex(WorkspaceError, "manifest verification failed"):
            reconcile_agent_proof(
                str(self.temp_dir),
                work_id=self.work_id,
                palari_id="PALARI-STEWARD",
                attempt_record={
                    "id": "ATTEMPT-TEST-MISSING-ARTIFACT",
                    "work_item_id": self.work_id,
                    "actor": "PALARI-STEWARD",
                    "status": "active",
                    "workspace_path": str(self.temp_dir),
                    "base_sha": head,
                    "allowed_paths": ["README.md"],
                },
                receipt_record={
                    "id": "RECEIPT-TEST-MISSING-ARTIFACT",
                    "work_item_id": self.work_id,
                    "attempt_id": "ATTEMPT-TEST-MISSING-ARTIFACT",
                    "actor": "PALARI-STEWARD",
                    "sources_used": ["SOURCE-REPO-FOUNDATION"],
                    "actions_taken": ["Claimed a missing output."],
                    "outputs_created": ["README.md"],
                    "not_done": ["No human authority was exercised."],
                    "undo_refs": ["README.md"],
                },
                evidence_record={
                    "id": "EVIDENCE-TEST-MISSING-ARTIFACT",
                    "work_item_id": self.work_id,
                    "attempt_id": "ATTEMPT-TEST-MISSING-ARTIFACT",
                    "head_sha": head,
                    "status": "passed",
                    "commands": ["mock exact-state attestation"],
                    "artifacts": ["README.md"],
                    "summary": "This must fail before mutation.",
                    "freshness": "exact-head",
                },
                head_sha=head,
                changed_files=["README.md"],
                output_targets=["README.md"],
            )

        self.assertEqual(before, (self.temp_dir / "workspace.json").read_bytes())

    def _crash_reconciliation(self, point: str) -> None:
        head = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        def crash_hook(current: str) -> None:
            if current == point:
                raise RuntimeError(f"injected crash at {point}")

        with self.assertRaisesRegex(RuntimeError, point):
            reconcile_agent_proof(
                str(self.temp_dir),
                work_id=self.work_id,
                palari_id="PALARI-STEWARD",
                attempt_record={
                    "id": f"ATTEMPT-ADVANCE-{self.work_id}-{head[:12].upper()}",
                    "work_item_id": self.work_id,
                    "actor": "PALARI-STEWARD",
                    "status": "active",
                    "workspace_path": str(self.temp_dir),
                    "base_sha": subprocess.run(
                        ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD^"],
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip(),
                },
                receipt_record={
                    "id": f"RECEIPT-ADVANCE-{self.work_id}-{head[:12].upper()}",
                    "work_item_id": self.work_id,
                    "attempt_id": f"ATTEMPT-ADVANCE-{self.work_id}-{head[:12].upper()}",
                    "actor": "PALARI-STEWARD",
                    "sources_used": ["SOURCE-REPO-FOUNDATION"],
                    "actions_taken": ["Tested an atomic proof projection."],
                    "outputs_created": ["README.md"],
                    "not_done": ["No human authority was exercised."],
                    "undo_refs": ["README.md"],
                },
                evidence_record={
                    "id": f"EVIDENCE-ADVANCE-{self.work_id}-{head[:12].upper()}",
                    "work_item_id": self.work_id,
                    "attempt_id": f"ATTEMPT-ADVANCE-{self.work_id}-{head[:12].upper()}",
                    "head_sha": head,
                    "status": "passed",
                    "base_ref": "HEAD^",
                    "commands": ["mock exact-state attestation"],
                    "artifacts": ["README.md"],
                    "summary": "Exact-state verification passed before injection.",
                    "freshness": "exact-head",
                },
                head_sha=head,
                changed_files=["README.md"],
                output_targets=["README.md"],
                crash_hook=crash_hook,
            )

    def _passing_attestation(self, _workspace, _root, profile, context, **_kwargs):
        key = cache_key(profile, context)
        return {
            "cache_hit": False,
            "attestation": {
                "attestation_id": f"VERIFY-{profile.id.upper()}-TEST",
                "cache_key": key,
                "status": "passed",
                "duration_ms": 1,
                "stdout_digest": "sha256:" + "1" * 64,
                "stderr_digest": "sha256:" + "2" * 64,
            },
        }


if __name__ == "__main__":
    unittest.main()
