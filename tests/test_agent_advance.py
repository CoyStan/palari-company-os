from __future__ import annotations

import hashlib
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
    _completed_projection,
    _git_commit_timestamp,
    _refresh_artifact_transition,
    _refresh_proof_narration,
    _verify_path_intents,
    agent_advance,
    agent_advance_dry_run,
    plan_advance,
)
from palari_company_os.agent_finish import build_agent_finish
from palari_company_os.agent_next import build_agent_next
from palari_company_os.agent_runtime import start_agent
from palari_company_os.agent_runtime import release_agent
from palari_company_os.authoring import (
    ReconciliationStateChanged,
    create_human_decision,
    create_record,
    reconcile_agent_proof,
    update_record,
)
from palari_company_os.cli_dispatch import run_command
from palari_company_os.cli_output_agent import print_agent_done
from palari_company_os.cli_parser import build_parser
from palari_company_os.evidence_manifest import (
    evidence_artifact_root,
    evidence_manifest_hash,
    git_artifact_state,
    receipt_hash,
    stamp_evidence_record,
    verify_evidence,
)
from palari_company_os.governance_journal import (
    MutationMetadata,
    _transaction_id,
    checkpoint_workspace_journal,
    journal_file_path,
    logical_changes,
    pending_workspace_journal_context,
    record_digest,
    transact,
    utc_timestamp,
    verify_workspace_journal,
    workspace_digest,
)
from palari_company_os.governance_convergence import (
    ConvergenceObservation,
    converge_work_item,
    run_fixed_point,
)
from palari_company_os.store import load_store
from palari_company_os.verification_attestations import (
    VerificationContext,
    VerificationProfile,
    cache_key,
    default_context,
    run_or_reuse,
    verification_profiles,
)
from palari_company_os.workspace import Workspace as Ws
from palari_company_os.workspace import WorkspaceError
from tests.workspace_fixture import write_portable_agent_workspace


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


class PathIntentAncestryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.name", "Test"],
            check=True,
        )
        (self.root / "modify.txt").write_text("before\n", encoding="utf-8")
        (self.root / "delete.txt").write_text("remove me\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", "base"],
            check=True,
        )
        self.base = self._head()
        (self.root / "create.txt").write_text("created\n", encoding="utf-8")
        (self.root / "modify.txt").write_text("after\n", encoding="utf-8")
        (self.root / "delete.txt").unlink()
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", "candidate"],
            check=True,
        )
        self.head = self._head()
        self.changed = ["create.txt", "delete.txt", "modify.txt"]

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_create_modify_and_delete_are_proven_against_exact_range(self) -> None:
        result = _verify_path_intents(
            self.root,
            [
                {"path": "create.txt", "intent": "create"},
                {"path": "modify.txt", "intent": "modify"},
                {"path": "delete.txt", "intent": "delete"},
            ],
            self.changed,
            self.base,
            self.head,
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(
            [item["status"] for item in result["checks"]],
            ["verified", "verified", "verified"],
        )

    def test_mislabeled_and_unchanged_intents_fail_closed(self) -> None:
        result = _verify_path_intents(
            self.root,
            [
                {"path": "modify.txt", "intent": "create"},
                {"path": "create.txt", "intent": "modify"},
                {"path": "delete.txt", "intent": "create"},
                {"path": "never.txt", "intent": "create"},
            ],
            self.changed,
            self.base,
            self.head,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(
            [item["code"] for item in result["errors"]],
            [
                "PATH_INTENT_MISMATCH",
                "PATH_INTENT_MISMATCH",
                "PATH_INTENT_MISMATCH",
                "PATH_INTENT_UNCHANGED",
            ],
        )

    def test_unreadable_range_fails_and_legacy_contract_remains_noop(self) -> None:
        invalid = _verify_path_intents(
            self.root,
            [{"path": "create.txt", "intent": "create"}],
            ["create.txt"],
            "0" * 40,
            self.head,
        )
        legacy = _verify_path_intents(
            self.root,
            [],
            self.changed,
            self.base,
            self.head,
        )

        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["errors"][0]["code"], "PATH_INTENT_GIT_UNREADABLE")
        self.assertEqual(legacy, {"required": False, "ok": True, "checks": [], "errors": []})

    def _head(self) -> str:
        return subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            text=True,
        ).strip()


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


class FixedPointDriverTests(unittest.TestCase):
    def test_repeated_state_and_action_cycle_fails_closed(self) -> None:
        digests = ["sha256:a", "sha256:b", "sha256:a"]
        position = {"value": 0}

        def observe() -> ConvergenceObservation:
            return ConvergenceObservation(
                digest=digests[position["value"]],
                status="ready",
                boundary="automatic-reconciliation",
                message="ready",
                action="step",
            )

        def apply(_action: str) -> None:
            position["value"] = min(position["value"] + 1, len(digests) - 1)

        result = run_fixed_point(observe, apply)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["code"], "CONVERGENCE_CYCLE")

    def test_no_progress_fails_closed(self) -> None:
        observation = ConvergenceObservation(
            digest="sha256:same",
            status="ready",
            boundary="automatic-reconciliation",
            message="ready",
            action="complete-work",
        )

        result = run_fixed_point(lambda: observation, lambda _action: None)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["code"], "CONVERGENCE_NO_PROGRESS")

    def test_iteration_limit_fails_closed(self) -> None:
        counter = {"value": 0}

        def observe() -> ConvergenceObservation:
            return ConvergenceObservation(
                digest=f"sha256:{counter['value']}",
                status="ready",
                boundary="automatic-reconciliation",
                message="ready",
                action="another-step",
            )

        def apply(_action: str) -> None:
            counter["value"] += 1

        result = run_fixed_point(observe, apply, max_steps=2)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["code"], "CONVERGENCE_ITERATION_LIMIT")
        self.assertEqual(len(result["steps"]), 2)


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

    def test_delete_intent_records_and_reverifies_core_tombstone(self) -> None:
        self._restart_with_path_intent("delete")
        (self.temp_dir / "README.md").unlink()
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "delete bounded output"],
            check=True,
        )

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "review-required", result)
        workspace = Ws.load(self.temp_dir)
        evidence = next(
            item for item in workspace.evidence_runs if item.work_item_id == self.work_id
        )
        tombstone = next(
            item for item in evidence.artifact_hashes if item["path"] == "README.md"
        )
        self.assertEqual(
            tombstone,
            {"path": "README.md", "sha256": "sha256:absent", "status": "absent"},
        )
        report = verify_evidence(workspace, evidence.id, require_output_coverage=True)
        self.assertTrue(report["ok"], report)

    def test_create_intent_rejects_modification_of_existing_file(self) -> None:
        self._restart_with_path_intent("create")
        (self.temp_dir / "README.md").write_text("not newly created\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "modify instead of create"],
            check=True,
        )

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            dry_run=True,
        )

        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(result["blockers"][0]["code"], "PREFLIGHT_BLOCKED")
        ancestry = result["preflight"]["path_intent_verification"]
        self.assertEqual(ancestry["errors"][0]["code"], "PATH_INTENT_MISMATCH")

    def test_fake_or_stale_delete_tombstone_fails_exact_verification(self) -> None:
        self._restart_with_path_intent("delete")
        (self.temp_dir / "README.md").unlink()
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "delete bounded output"],
            check=True,
        )
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(result["status"], "review-required", result)
        raw = deepcopy(load_store(self.temp_dir).data)
        evidence = next(
            item for item in raw["evidence_runs"] if item["work_item_id"] == self.work_id
        )
        fake = deepcopy(raw)
        fake_evidence = next(
            item for item in fake["evidence_runs"] if item["id"] == evidence["id"]
        )
        fake_evidence["artifact_hashes"][0]["previous_git_oid"] = "0" * 40
        fake_evidence["manifest_hash"] = evidence_manifest_hash(fake_evidence)
        fake_report = verify_evidence(
            Ws.from_raw(fake, self.temp_dir),
            evidence["id"],
            require_output_coverage=True,
        )

        stale = deepcopy(raw)
        stale_evidence = next(
            item for item in stale["evidence_runs"] if item["id"] == evidence["id"]
        )
        stale_evidence["base_ref"] = stale_evidence["head_sha"]
        stale_evidence["manifest_hash"] = evidence_manifest_hash(stale_evidence)
        stale_report = verify_evidence(
            Ws.from_raw(stale, self.temp_dir),
            evidence["id"],
            require_output_coverage=True,
        )

        self.assertFalse(fake_report["artifact_hashes_ok"])
        self.assertFalse(stale_report["artifact_hashes_ok"])
        self.assertEqual(
            stale_report["computed_artifact_hashes"][0]["status"],
            "invalid-deletion",
        )

    def test_delete_reappearing_after_reconciliation_blocks_terminalization(self) -> None:
        self._restart_with_path_intent("delete")
        (self.temp_dir / "README.md").unlink()
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "delete bounded output"],
            check=True,
        )

        def reconcile_then_reappear(*args, **kwargs):
            reconciled = reconcile_agent_proof(*args, **kwargs)
            (self.temp_dir / "README.md").write_text(
                "reappeared after reconciliation\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(self.temp_dir), "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", str(self.temp_dir), "commit", "-qm", "reintroduce output"],
                check=True,
            )
            return reconciled

        with (
            patch(
                "palari_company_os.agent_advance.run_or_reuse",
                side_effect=self._passing_attestation,
            ),
            patch(
                "palari_company_os.agent_advance.reconcile_agent_proof",
                side_effect=reconcile_then_reappear,
            ),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "state-changed", result)
        self.assertFalse(result["preflight"]["path_intent_verification"]["ok"])
        self.assertEqual(Ws.load(self.temp_dir).work_item(self.work_id).status, "active")

    def test_cas_intent_inference_is_unique_and_legacy_missing_stays_missing(self) -> None:
        self._restart_with_path_intent("delete")
        (self.temp_dir / "README.md").unlink()
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "delete bounded output"],
            check=True,
        )

        unique = git_artifact_state(
            self.temp_dir,
            ["README.md"],
            governance_workspace_path=self.temp_dir,
        )
        self.assertEqual(unique["artifact_hashes"][0]["status"], "absent")

        create_record(
            str(self.temp_dir),
            "work",
            {
                "id": "WORK-TEST-AMBIGUOUS-DELETE",
                "title": "Ambiguous deletion contract",
                "palari": "PALARI-STEWARD",
                "goal": "GOAL-REPO-0001",
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R4",
                "intensity": "high",
                "status": "active",
                "allowed_resources": ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": ["README.md"],
                "path_intents": [{"path": "README.md", "intent": "delete"}],
                "required_approval_count": 1,
            },
            command="test ambiguous delete contract",
            actor="PALARI-STEWARD",
        )
        ambiguous = git_artifact_state(
            self.temp_dir,
            ["README.md"],
            governance_workspace_path=self.temp_dir,
        )
        legacy = git_artifact_state(
            self.temp_dir,
            ["never-declared.txt"],
            governance_workspace_path=self.temp_dir,
        )

        self.assertEqual(ambiguous["artifact_hashes"][0]["status"], "missing")
        self.assertEqual(legacy["artifact_hashes"][0]["status"], "missing")

    def test_manual_evidence_stamp_uses_exact_work_contract_intent(self) -> None:
        self._restart_with_path_intent("delete")
        base_sha = subprocess.check_output(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"], text=True
        ).strip()
        (self.temp_dir / "README.md").unlink()
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "delete bounded output"],
            check=True,
        )
        head_sha = subprocess.check_output(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"], text=True
        ).strip()
        attempt = {
            "id": "ATTEMPT-MANUAL-DELETE",
            "workspace_path": str(self.temp_dir),
            "allowed_paths": ["README.md"],
            "forbidden_paths": [],
            "head_sha": head_sha,
        }
        record = {
            "id": "EVIDENCE-MANUAL-DELETE",
            "work_item_id": self.work_id,
            "attempt_id": attempt["id"],
            "head_sha": head_sha,
            "base_ref": base_sha,
            "status": "passed",
            "artifacts": ["README.md"],
        }

        inferred = stamp_evidence_record(
            record,
            self.temp_dir,
            attempts=[attempt],
        )
        explicit_legacy = stamp_evidence_record(
            {**record, "id": "EVIDENCE-EXPLICIT-NO-INTENT"},
            self.temp_dir,
            attempts=[attempt],
            path_intents=[],
        )

        self.assertEqual(inferred["artifact_hashes"][0]["status"], "absent")
        self.assertEqual(explicit_legacy["artifact_hashes"][0]["status"], "missing")

    def test_completed_proof_resume_rejects_changed_artifact_bytes(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        (self.temp_dir / "README.md").write_text(
            "changed after exact proof\n",
            encoding="utf-8",
        )

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "CURRENT_PROOF_INVALID")
        self.assertEqual(Ws.load(self.temp_dir).work_item(self.work_id).status, "active")

    def test_self_mutating_governance_outputs_bind_commit_and_allow_review(self) -> None:
        evidence = self._advance_with_projection_outputs()
        report = verify_evidence(
            Ws.load(self.temp_dir),
            evidence.id,
            require_output_coverage=True,
        )

        self.assertTrue(report["ok"], report)
        self.assertEqual(
            report["exact_head_artifacts"],
            [".palari/governance-journal.v1.jsonl"],
        )
        self.assertTrue(report["journal_continuity_ok"])
        result = create_record(
            str(self.temp_dir),
            "review",
            {
                "id": "REVIEW-TEST-SELF-JOURNAL",
                "work_item_id": self.work_id,
                "reviewed_head": evidence.head_sha,
                "reviewer": "PALARI-ARCHITECT",
                "verdict": "accept-ready",
                "findings": [],
                "checks_inspected": ["exact committed projection and live journal"],
                "residual_risks": [],
            },
            command="test exact-head self-journal review",
            actor="PALARI-ARCHITECT",
        )

        self.assertEqual(result.action, "created")
        self.assertTrue(verify_workspace_journal(self.temp_dir)["ok"])

    def test_self_mutating_governance_output_rejects_forged_committed_hash(self) -> None:
        evidence = self._advance_with_projection_outputs()
        raw = deepcopy(load_store(self.temp_dir).data)
        raw_evidence = next(
            item for item in raw["evidence_runs"] if item["id"] == evidence.id
        )
        journal_hash = next(
            item
            for item in raw_evidence["artifact_hashes"]
            if item["path"] == ".palari/governance-journal.v1.jsonl"
        )
        journal_hash["sha256"] = "sha256:" + "0" * 64
        raw_evidence["manifest_hash"] = evidence_manifest_hash(raw_evidence)
        forged = Ws.from_raw(raw, self.temp_dir)

        report = verify_evidence(
            forged,
            evidence.id,
            require_output_coverage=True,
        )

        self.assertFalse(report["ok"])
        self.assertFalse(report["artifact_hashes_ok"])
        self.assertFalse(report["manifest_hash_ok"])
        self.assertTrue(report["journal_continuity_ok"])

    def test_self_mutating_governance_output_rejects_invalid_live_journal(self) -> None:
        evidence = self._advance_with_projection_outputs()
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        with journal.open("a", encoding="utf-8") as stream:
            stream.write("{}\n")

        report = verify_evidence(
            Ws.load(self.temp_dir),
            evidence.id,
            require_output_coverage=True,
        )

        self.assertFalse(report["ok"])
        self.assertTrue(report["artifact_hashes_ok"])
        self.assertFalse(report["journal_continuity_ok"])
        with self.assertRaisesRegex(WorkspaceError, "complete exact proof"):
            create_record(
                str(self.temp_dir),
                "review",
                {
                    "id": "REVIEW-TEST-INVALID-LIVE-JOURNAL",
                    "work_item_id": self.work_id,
                    "reviewed_head": evidence.head_sha,
                    "reviewer": "PALARI-ARCHITECT",
                    "verdict": "accept-ready",
                    "findings": [],
                    "checks_inspected": ["invalid live journal"],
                    "residual_risks": [],
                },
                command="test invalid live journal rejection",
                actor="PALARI-ARCHITECT",
            )

    def test_self_mutating_governance_output_rejects_git_replace_substitution(self) -> None:
        evidence = self._advance_with_projection_outputs()
        replacement = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", f"{evidence.head_sha}^^"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "replace", evidence.head_sha, replacement],
            check=True,
        )
        object_spec = f"{evidence.head_sha}:.palari/governance-journal.v1.jsonl"
        substituted = subprocess.run(
            ["git", "-C", str(self.temp_dir), "cat-file", "blob", object_spec],
            check=True,
            capture_output=True,
        ).stdout
        original = subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "--no-replace-objects",
                "cat-file",
                "blob",
                object_spec,
            ],
            check=True,
            capture_output=True,
        ).stdout
        self.assertNotEqual(substituted, original)

        raw = deepcopy(load_store(self.temp_dir).data)
        raw_evidence = next(
            item for item in raw["evidence_runs"] if item["id"] == evidence.id
        )
        journal_hash = next(
            item
            for item in raw_evidence["artifact_hashes"]
            if item["path"] == ".palari/governance-journal.v1.jsonl"
        )
        journal_hash["sha256"] = "sha256:" + hashlib.sha256(substituted).hexdigest()
        raw_evidence["manifest_hash"] = evidence_manifest_hash(raw_evidence)

        report = verify_evidence(
            Ws.from_raw(raw, self.temp_dir),
            evidence.id,
            require_output_coverage=True,
        )

        self.assertFalse(report["ok"])
        self.assertFalse(report["artifact_hashes_ok"])
        self.assertFalse(report["manifest_hash_ok"])
        self.assertTrue(report["journal_continuity_ok"])

    def test_relocated_artifact_root_rejects_replace_only_candidate(self) -> None:
        fake_head = "1" * 40
        actual_head = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "update-ref",
                f"refs/replace/{fake_head}",
                actual_head,
            ],
            check=True,
        )
        ordinary = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", f"{fake_head}^{{commit}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        raw = subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "--no-replace-objects",
                "rev-parse",
                "--verify",
                f"{fake_head}^{{commit}}",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(ordinary, fake_head)
        self.assertNotEqual(raw.returncode, 0)

        with self.assertRaisesRegex(ValueError, "candidate commit is unavailable"):
            evidence_artifact_root(
                self.temp_dir,
                "ATTEMPT-RELOCATED-REPLACE",
                ["README.md"],
                [
                    {
                        "id": "ATTEMPT-RELOCATED-REPLACE",
                        "workspace_path": str(self.temp_dir / "missing-original-repo"),
                        "allowed_paths": ["README.md"],
                        "forbidden_paths": [],
                        "head_sha": fake_head,
                    }
                ],
            )

    def test_changes_requested_repair_bypasses_rejected_projection_resume(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        original = Ws.load(self.temp_dir)
        work = original.work_item(self.work_id)
        self.assertIsNotNone(work)
        assert work is not None and work.current_attempt
        attempt = next(item for item in original.attempts if item.id == work.current_attempt)
        original_head = attempt.head_sha or attempt.commits[-1]
        create_record(
            str(self.temp_dir),
            "review",
            {
                "id": "REVIEW-TEST-ADVANCE-CHANGES",
                "work_item_id": self.work_id,
                "reviewed_head": original_head,
                "reviewer": "PALARI-ARCHITECT",
                "verdict": "changes-requested",
                "findings": [],
                "checks_inspected": ["exact deterministic advance proof"],
                "residual_risks": [],
            },
            command="test independent review",
            actor="PALARI-ARCHITECT",
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "record review"],
            check=True,
        )
        start = start_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self.assertEqual(start["start"]["status"], "claimed")
        (self.temp_dir / "README.md").write_text("repaired\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "repair finding"],
            check=True,
        )
        dry_run = agent_advance_dry_run(
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )
        self.assertIsNotNone(dry_run)
        assert dry_run is not None
        steps = {item["step"]: item["status"] for item in dry_run["steps"]}
        self.assertEqual(steps["attempt-record"], "create")
        self.assertEqual(steps["work-attempt-bind"], "create")
        self.assertEqual(steps["receipt-record"], "create")
        self.assertEqual(steps["evidence-record"], "create")
        resumed = _completed_projection(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertIsNone(resumed)

    def test_changes_requested_refresh_previews_and_rebinds_without_claim(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        workspace = Ws.load(self.temp_dir)
        work = workspace.work_item(self.work_id)
        self.assertIsNotNone(work)
        assert work is not None and work.current_attempt
        attempt = next(item for item in workspace.attempts if item.id == work.current_attempt)
        previous_head = attempt.head_sha or attempt.commits[-1]
        self._record_changes_requested(previous_head, "REVIEW-REFRESH-CHANGES")
        (self.temp_dir / "RELATED.md").write_text(
            "separately governed context\n", encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "review and context"],
            check=True,
        )
        current_head = subprocess.check_output(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"], text=True
        ).strip()

        preview = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            dry_run=True,
            refresh_verification=True,
        )

        self.assertEqual(preview["status"], "planned", preview)
        self.assertFalse(preview["would_mutate"])
        self.assertEqual(preview["refresh"]["previous_head"], previous_head)
        self.assertEqual(preview["refresh"]["current_head"], current_head)
        after_preview = Ws.load(self.temp_dir)
        self.assertEqual(after_preview.work_item(self.work_id).current_attempt, attempt.id)
        self.assertFalse(
            any(
                item.id.startswith("ATTEMPT-REFRESH-")
                for item in after_preview.attempts
                if item.work_item_id == self.work_id
            )
        )
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            refreshed = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(refreshed["status"], "review-required", refreshed)
        self.assertFalse(
            (self.temp_dir / ".palari" / "claims" / f"{self.work_id}.json").exists()
        )
        current = Ws.load(self.temp_dir)
        current_work = current.work_item(self.work_id)
        self.assertIsNotNone(current_work)
        assert current_work is not None and current_work.current_attempt
        refreshed_attempt = next(
            item for item in current.attempts if item.id == current_work.current_attempt
        )
        self.assertEqual(refreshed_attempt.head_sha, current_head)
        stale_review = next(
            item for item in current.review_verdicts if item.id == "REVIEW-REFRESH-CHANGES"
        )
        self.assertEqual(stale_review.reviewed_head, previous_head)
        self.assertNotEqual(stale_review.reviewed_head, refreshed_attempt.head_sha)

    def test_changes_requested_refresh_rejects_active_claim(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        workspace = Ws.load(self.temp_dir)
        work = workspace.work_item(self.work_id)
        assert work is not None and work.current_attempt
        attempt = next(item for item in workspace.attempts if item.id == work.current_attempt)
        previous_head = attempt.head_sha or attempt.commits[-1]
        self._record_changes_requested(previous_head, "REVIEW-REFRESH-ACTIVE-CLAIM")
        (self.temp_dir / "RELATED.md").write_text("later context\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "later context"],
            check=True,
        )
        start_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            "execute",
        )

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            refresh_verification=True,
        )

        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(result["blockers"][0]["code"], "REFRESH_ACTIVE_CLAIM")

    def test_changes_requested_refresh_rebinds_self_mutating_projection_outputs(
        self,
    ) -> None:
        self._advance_with_projection_outputs()
        workspace = Ws.load(self.temp_dir)
        work = workspace.work_item(self.work_id)
        assert work is not None and work.current_attempt
        attempt = next(item for item in workspace.attempts if item.id == work.current_attempt)
        previous_head = attempt.head_sha or attempt.commits[-1]
        self._record_changes_requested(previous_head, "REVIEW-REFRESH-PROJECTION")
        (self.temp_dir / "RELATED.md").write_text(
            "separately governed context\n", encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "later projection"],
            check=True,
        )
        current_head = subprocess.check_output(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"], text=True
        ).strip()

        planned = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            dry_run=True,
            refresh_verification=True,
        )
        self.assertEqual(planned["status"], "planned", planned)
        self.assertFalse(planned["refresh"]["artifacts_unchanged"])
        self.assertEqual(
            planned["refresh"]["ordinary_artifacts_unchanged"], ["README.md"]
        )
        expected_projections = [
            ".palari/governance-journal.v1.jsonl",
            ".palari/history.jsonl",
            "workspace.json",
        ]
        self.assertEqual(
            [
                item["path"]
                for item in planned["refresh"]["projection_artifacts_rebound"]
            ],
            expected_projections,
        )
        rebound_by_path = {
            item["path"]: item
            for item in planned["refresh"]["projection_artifacts_rebound"]
        }
        self.assertEqual(
            rebound_by_path[".palari/history.jsonl"]["previous_status"],
            "not-recorded",
        )
        self.assertEqual(
            rebound_by_path["workspace.json"]["previous_status"],
            "not-recorded",
        )
        self.assertTrue(
            all(
                item["transition"] == "rebound"
                and item["current_status"] == "present"
                for item in rebound_by_path.values()
            )
        )
        self.assertEqual(
            planned["refresh"]["proof_projection_mutates_after_evidence"],
            expected_projections,
        )
        self.assertIn("mutate those projection files after the evidence head", planned["message"])

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(result["status"], "review-required", result)
        self.assertFalse(result["refresh"]["artifacts_unchanged"])
        self.assertEqual(
            result["refresh"]["ordinary_artifacts_unchanged"], ["README.md"]
        )
        self.assertEqual(
            [
                item["path"]
                for item in result["refresh"]["projection_artifacts_rebound"]
            ],
            expected_projections,
        )
        refreshed = Ws.load(self.temp_dir)
        refreshed_work = refreshed.work_item(self.work_id)
        assert refreshed_work is not None and refreshed_work.current_attempt
        refreshed_attempt = next(
            item for item in refreshed.attempts if item.id == refreshed_work.current_attempt
        )
        self.assertEqual(refreshed_attempt.head_sha, current_head)
        evidence = next(
            item
            for item in refreshed.evidence_runs
            if item.attempt_id == refreshed_attempt.id
        )
        self.assertEqual(
            set(evidence.artifacts),
            {
                "README.md",
                "workspace.json",
                ".palari/history.jsonl",
                ".palari/governance-journal.v1.jsonl",
            },
        )
        receipt = next(
            item
            for item in refreshed.receipts
            if item.attempt_id == refreshed_attempt.id
        )
        narration = " ".join(receipt.actions_taken + receipt.not_done)
        self.assertIn("self-mutating governance projection", narration)
        self.assertIn("after the evidence head", narration)
        self.assertNotIn("unchanged governed artifact", narration)
        self.assertIn("were rebound to exact current-HEAD Git bytes", evidence.summary)
        self.assertIn("after the evidence head", evidence.summary)

    def test_refresh_transition_rejects_missing_ordinary_artifact_hash(self) -> None:
        transition = _refresh_artifact_transition(
            self.temp_dir,
            self.temp_dir,
            ["README.md", "workspace.json"],
            [
                {
                    "path": "workspace.json",
                    "sha256": "sha256:" + "1" * 64,
                    "status": "present",
                }
            ],
            [
                {
                    "path": "README.md",
                    "sha256": "sha256:" + "2" * 64,
                    "status": "present",
                },
                {
                    "path": "workspace.json",
                    "sha256": "sha256:" + "3" * 64,
                    "status": "present",
                },
            ],
        )

        self.assertIsNone(transition)

    def test_refresh_transition_reports_uniform_projection_records(self) -> None:
        transition = _refresh_artifact_transition(
            self.temp_dir,
            self.temp_dir,
            [".palari/history.jsonl", "workspace.json"],
            [
                {
                    "path": ".palari/history.jsonl",
                    "sha256": "sha256:" + "1" * 64,
                    "status": "present",
                },
                {
                    "path": "workspace.json",
                    "sha256": "sha256:" + "2" * 64,
                    "status": "present",
                },
            ],
            [
                {
                    "path": ".palari/history.jsonl",
                    "sha256": "sha256:" + "3" * 64,
                    "status": "present",
                },
                {
                    "path": "workspace.json",
                    "sha256": "sha256:" + "2" * 64,
                    "status": "present",
                },
            ],
        )

        self.assertIsNotNone(transition)
        assert transition is not None
        self.assertEqual(
            transition["projection_artifacts_unchanged"],
            [
                {
                    "path": "workspace.json",
                    "transition": "unchanged",
                    "previous_sha256": "sha256:" + "2" * 64,
                    "previous_status": "present",
                    "current_sha256": "sha256:" + "2" * 64,
                    "current_status": "present",
                }
            ],
        )
        self.assertEqual(
            transition["projection_artifacts_rebound"],
            [
                {
                    "path": ".palari/history.jsonl",
                    "transition": "rebound",
                    "previous_sha256": "sha256:" + "1" * 64,
                    "previous_status": "present",
                    "current_sha256": "sha256:" + "3" * 64,
                    "current_status": "present",
                }
            ],
        )

    def test_refresh_transition_sorts_three_unchanged_projection_records(self) -> None:
        paths = [
            ".palari/governance-journal.v1.jsonl",
            ".palari/history.jsonl",
            "workspace.json",
        ]
        hashes = [
            {
                "path": path,
                "sha256": "sha256:" + str(index) * 64,
                "status": "present",
            }
            for index, path in enumerate(reversed(paths), start=1)
        ]

        transition = _refresh_artifact_transition(
            self.temp_dir,
            self.temp_dir,
            list(reversed(paths)),
            hashes,
            hashes,
        )

        self.assertIsNotNone(transition)
        assert transition is not None
        self.assertEqual(
            [
                item["path"]
                for item in transition["projection_artifacts_unchanged"]
            ],
            paths,
        )
        self.assertEqual(transition["projection_artifacts_rebound"], [])
        self.assertTrue(transition["artifacts_unchanged"])

    def test_refresh_proof_narration_preserves_projection_transitions(self) -> None:
        record = {
            "previous_sha256": "sha256:" + "1" * 64,
            "previous_status": "present",
            "current_sha256": "sha256:" + "1" * 64,
            "current_status": "present",
        }
        narration = _refresh_proof_narration(
            3,
            {
                "ordinary_artifacts_unchanged": [],
                "projection_artifacts_unchanged": [
                    {"path": "workspace.json", "transition": "unchanged", **record},
                    {
                        "path": ".palari/history.jsonl",
                        "transition": "unchanged",
                        **record,
                    },
                ],
                "projection_artifacts_rebound": [
                    {
                        "path": ".palari/governance-journal.v1.jsonl",
                        "transition": "rebound",
                        **record,
                        "current_sha256": "sha256:" + "2" * 64,
                    }
                ],
            },
        )

        actions = " ".join(narration["actions_taken"])
        self.assertIn("Confirmed 2", actions)
        self.assertIn("Rebound 1", actions)
        self.assertNotIn("Rebound 3", actions)
        self.assertIn("2 self-mutating governance projection", narration["evidence_summary"])
        self.assertIn("retained identical exact Git bytes", narration["evidence_summary"])
        self.assertIn("1 self-mutating governance projection", narration["evidence_summary"])
        self.assertIn("were rebound", narration["evidence_summary"])
        self.assertIn("after the evidence head", narration["evidence_summary"])

    def test_refresh_transition_rejects_malformed_hash_or_status(self) -> None:
        valid = {
            "path": "workspace.json",
            "sha256": "sha256:" + "1" * 64,
            "status": "present",
        }
        malformed = (
            {**valid, "sha256": "sha256:short"},
            {**valid, "status": "unknown"},
            {key: value for key, value in valid.items() if key != "status"},
        )

        for item in malformed:
            with self.subTest(item=item):
                transition = _refresh_artifact_transition(
                    self.temp_dir,
                    self.temp_dir,
                    ["workspace.json"],
                    [valid],
                    [item],
                )
                self.assertIsNone(transition)

    def test_changes_requested_refresh_rejects_mismatched_review_head(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        self._record_changes_requested("f" * 40, "REVIEW-REFRESH-WRONG-HEAD")
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "bad review binding"],
            check=True,
        )

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            dry_run=True,
            refresh_verification=True,
        )

        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(
            result["blockers"][0]["code"], "REFRESH_REVIEW_BINDING_INVALID"
        )

    def test_changes_requested_refresh_rejects_rewritten_history(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        workspace = Ws.load(self.temp_dir)
        work = workspace.work_item(self.work_id)
        assert work is not None and work.current_attempt
        attempt = next(item for item in workspace.attempts if item.id == work.current_attempt)
        previous_head = attempt.head_sha or attempt.commits[-1]
        self._record_changes_requested(previous_head, "REVIEW-REFRESH-REWRITTEN")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "checkout", "--orphan", "rewritten"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "rewritten history"],
            check=True,
        )

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            dry_run=True,
            refresh_verification=True,
        )

        self.assertEqual(result["status"], "blocked", result)
        self.assertFalse(result["can_advance"])

    def test_refresh_rejects_restored_output_history_overlap(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        previous_head, _evidence_id, _review_id = self._record_current_authority()
        self._record_changes_requested(
            previous_head,
            "REVIEW-REFRESH-RESTORED-OUTPUT",
        )
        artifact = (self.temp_dir / "README.md").read_bytes()
        (self.temp_dir / "README.md").write_text("temporary changed bytes\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "touch output"],
            check=True,
        )
        (self.temp_dir / "README.md").write_bytes(artifact)
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "restore output"],
            check=True,
        )

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=AssertionError("overlapping refresh ran verification"),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(
            result["blockers"][0]["code"], "REFRESH_OUTPUT_HISTORY_OVERLAP"
        )
        self.assertIn("README.md", result["blockers"][0]["message"])

    def test_refresh_rejects_output_changed_only_by_two_merges_then_restored(
        self,
    ) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        workspace = Ws.load(self.temp_dir)
        work = workspace.work_item(self.work_id)
        assert work is not None and work.current_attempt
        attempt = next(item for item in workspace.attempts if item.id == work.current_attempt)
        previous_head = attempt.head_sha or attempt.commits[-1]
        self._record_changes_requested(previous_head, "REVIEW-REFRESH-TWO-MERGES")
        original = (self.temp_dir / "README.md").read_bytes()
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "record review"],
            check=True,
        )
        main_branch = subprocess.check_output(
            ["git", "-C", str(self.temp_dir), "branch", "--show-current"], text=True
        ).strip()
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "checkout", "-qb", "topic-one"],
            check=True,
        )
        (self.temp_dir / "topic-one.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "topic-one.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "topic one"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "checkout", main_branch],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (self.temp_dir / "main-one.txt").write_text("main one\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "main-one.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "main one"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "merge",
                "--no-ff",
                "--no-commit",
                "topic-one",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (self.temp_dir / "README.md").write_text(
            "changed only by first merge\n", encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "first merge"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "checkout", "-qb", "topic-two"],
            check=True,
        )
        (self.temp_dir / "topic-two.txt").write_text("two\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "topic-two.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "topic two"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "checkout", main_branch],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (self.temp_dir / "main-two.txt").write_text("main two\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "main-two.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "main two"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "merge",
                "--no-ff",
                "--no-commit",
                "topic-two",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (self.temp_dir / "README.md").write_bytes(original)
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "second merge"],
            check=True,
        )

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=AssertionError("merge-overlap refresh ran verification"),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(
            result["blockers"][0]["code"], "REFRESH_OUTPUT_HISTORY_OVERLAP"
        )
        self.assertIn("README.md", result["blockers"][0]["message"])

    def test_current_human_decision_allows_deterministic_terminalization(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        self._record_current_authority()
        before = Ws.load(self.temp_dir)
        authority_counts = (
            len(before.review_verdicts),
            len(before.human_decisions),
        )
        finish = build_agent_finish(
            before,
            self.work_id,
            "PALARI-STEWARD",
        )
        self.assertEqual(finish["status"], "converge-ready")
        self.assertEqual(finish["next_step_type"], "automatic-reconciliation")
        self.assertEqual(
            finish["resolution_summary"]["primary_class"],
            "automatic-reconciliation",
        )
        self.assertIn("agent advance", finish["next_allowed_commands"][0])
        candidate = next(
            item
            for item in build_agent_next(
                before,
                "PALARI-STEWARD",
                limit=20,
            )["candidates"]
            if item["work_item_id"] == self.work_id
        )
        self.assertEqual(candidate["next_step_type"], "automatic-reconciliation")
        self.assertIn("agent advance", candidate["next_command"])

        completed = agent_advance(
            before,
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(completed["status"], "completed", completed)
        self.assertEqual(
            completed["authority_source"],
            "preexisting-current-human-decision",
        )
        self.assertFalse(completed["performed_human_authority"])
        after = Ws.load(self.temp_dir)
        self.assertEqual(after.work_item(self.work_id).status, "completed")
        self.assertEqual(
            authority_counts,
            (len(after.review_verdicts), len(after.human_decisions)),
        )
        self.assertTrue(
            any(record.work_item_id == self.work_id for record in after.acceptance_records)
        )

        repeated = agent_advance(
            after,
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )
        self.assertEqual(repeated["status"], "completed")
        self.assertFalse(repeated["would_mutate"])

    def test_human_decision_function_converges_without_an_agent_claim(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        workspace = Ws.load(self.temp_dir)
        work = workspace.work_item(self.work_id)
        assert work is not None and work.current_attempt
        attempt = next(item for item in workspace.attempts if item.id == work.current_attempt)
        evidence = next(
            item
            for item in workspace.evidence_runs
            if item.work_item_id == self.work_id and item.attempt_id == attempt.id
        )
        create_record(
            str(self.temp_dir),
            "review",
            {
                "id": "REVIEW-AUTO-CONVERGE",
                "work_item_id": self.work_id,
                "reviewed_head": attempt.head_sha,
                "reviewer": "PALARI-ARCHITECT",
                "verdict": "accept-ready",
            },
            actor="PALARI-ARCHITECT",
        )

        result = create_human_decision(
            str(self.temp_dir),
            {
                "id": "HUMAN-DECISION-AUTO-CONVERGE",
                "work_item_id": self.work_id,
                "human_id": "HUMAN-FOUNDER",
                "reviewed_head": attempt.head_sha,
                "decision": "accepted",
                "status": "accepted",
                "acceptance_mode": "human",
                "quorum_status": "met",
                "evidence_reference": evidence.id,
                "review_reference": "REVIEW-AUTO-CONVERGE",
            },
            actor="HUMAN-FOUNDER",
        )

        self.assertIn("completed automatically", result.next_action)
        completed = Ws.load(self.temp_dir)
        self.assertEqual(completed.work_item(self.work_id).status, "completed")
        self.assertTrue(
            any(item.work_item_id == self.work_id for item in completed.acceptance_records)
        )
        repeated = converge_work_item(
            self.temp_dir,
            self.work_id,
            actor="PALARI-STEWARD",
        )
        self.assertEqual(repeated["status"], "completed")
        self.assertFalse(repeated["would_mutate"])

    def test_reconciliation_observation_failure_preserves_human_decision(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        workspace = Ws.load(self.temp_dir)
        work = workspace.work_item(self.work_id)
        assert work is not None and work.current_attempt
        attempt = next(item for item in workspace.attempts if item.id == work.current_attempt)
        evidence = next(
            item
            for item in workspace.evidence_runs
            if item.work_item_id == self.work_id and item.attempt_id == attempt.id
        )
        create_record(
            str(self.temp_dir),
            "review",
            {
                "id": "REVIEW-OBSERVATION-FAILURE",
                "work_item_id": self.work_id,
                "reviewed_head": attempt.head_sha,
                "reviewer": "PALARI-ARCHITECT",
                "verdict": "accept-ready",
            },
            actor="PALARI-ARCHITECT",
        )

        with patch(
            "palari_company_os.governance_convergence.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["git"], 5),
        ):
            result = create_human_decision(
                str(self.temp_dir),
                {
                    "id": "HUMAN-DECISION-OBSERVATION-FAILURE",
                    "work_item_id": self.work_id,
                    "human_id": "HUMAN-FOUNDER",
                    "reviewed_head": attempt.head_sha,
                    "decision": "accepted",
                    "status": "accepted",
                    "acceptance_mode": "human",
                    "quorum_status": "met",
                    "evidence_reference": evidence.id,
                    "review_reference": "REVIEW-OBSERVATION-FAILURE",
                },
                actor="HUMAN-FOUNDER",
            )

        self.assertIn("stopped safely", result.next_action)
        after = Ws.load(self.temp_dir)
        self.assertEqual(after.work_item(self.work_id).status, "active")
        self.assertTrue(
            any(
                item.id == "HUMAN-DECISION-OBSERVATION-FAILURE"
                for item in after.human_decisions
            )
        )

    def test_governance_only_commits_preserve_current_proof(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        self._record_current_authority()
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "workspace.json"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "record governance proof"],
            check=True,
        )

        completed = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(completed["status"], "completed", completed)
        self.assertTrue(completed["convergence"]["proof"]["committed_paths"])
        self.assertEqual(
            completed["convergence"]["proof"]["substantive_paths"],
            [],
        )

    def test_substantive_commit_after_proof_blocks_convergence(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        self._record_current_authority()
        (self.temp_dir / "README.md").write_text("substantive later change\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "substantive later change"],
            check=True,
        )

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "CURRENT_PROOF_INVALID")
        self.assertIn("README.md", result["blockers"][0]["message"])

    def test_explicit_refresh_rebinds_unchanged_artifact_and_requires_fresh_authority(
        self,
    ) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        previous_head, _evidence_id, _review_id = self._record_current_authority()
        artifact_before = (self.temp_dir / "README.md").read_bytes()
        (self.temp_dir / "RELATED.md").write_text(
            "later repository context\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-u"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "RELATED.md"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "later context"],
            check=True,
        )
        current_head = subprocess.check_output(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            text=True,
        ).strip()

        without_refresh = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )
        self.assertEqual(without_refresh["status"], "blocked")
        self.assertEqual(
            without_refresh["blockers"][0]["code"],
            "CURRENT_PROOF_INVALID",
        )

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ) as runner:
            refreshed = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(refreshed["status"], "review-required", refreshed)
        self.assertEqual(runner.call_count, 3)
        self.assertTrue(refreshed["refresh"]["artifacts_unchanged"])
        self.assertEqual(
            refreshed["refresh"]["ordinary_artifacts_unchanged"], ["README.md"]
        )
        self.assertEqual(
            refreshed["refresh"]["projection_artifacts_rebound"], []
        )
        self.assertEqual(
            refreshed["refresh"]["proof_projection_mutates_after_evidence"], []
        )
        self.assertFalse(refreshed["refresh"]["performed_human_authority"])
        self.assertEqual(refreshed["refresh"]["previous_head"], previous_head)
        self.assertEqual(refreshed["refresh"]["current_head"], current_head)
        self.assertEqual((self.temp_dir / "README.md").read_bytes(), artifact_before)
        workspace = Ws.load(self.temp_dir)
        work = workspace.work_item(self.work_id)
        self.assertIsNotNone(work)
        assert work is not None and work.current_attempt
        attempt = next(item for item in workspace.attempts if item.id == work.current_attempt)
        previous_attempt = next(
            item for item in workspace.attempts if item.head_sha == previous_head
        )
        self.assertEqual(attempt.head_sha, current_head)
        self.assertEqual(attempt.changed_files, [])
        self.assertNotEqual(attempt.started_at, previous_attempt.started_at)
        evidence = next(
            item
            for item in workspace.evidence_runs
            if item.attempt_id == attempt.id
        )
        self.assertEqual(evidence.artifacts, ["README.md"])
        self.assertEqual(evidence.base_ref, previous_head)
        self.assertEqual(refreshed["stop_boundary"], "independent-review")
        self.assertEqual(work.status, "active")
        self.assertFalse(
            any(item.work_item_id == self.work_id for item in workspace.acceptance_records)
        )
        old_decision = next(
            item
            for item in workspace.human_decisions
            if item.id == "HUMAN-DECISION-TEST-ADVANCE"
        )
        self.assertEqual(old_decision.reviewed_head, previous_head)
        self.assertNotEqual(old_decision.reviewed_head, attempt.head_sha)

    def test_explicit_refresh_rejects_workspace_race_before_reconciliation(
        self,
    ) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        self._record_current_authority()
        (self.temp_dir / "RELATED.md").write_text(
            "later repository context\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-u"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "RELATED.md"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "later context"],
            check=True,
        )
        before = Ws.load(self.temp_dir)
        before_attempts = {
            item.id for item in before.attempts if item.work_item_id == self.work_id
        }
        before_receipts = {
            item.id for item in before.receipts if item.work_item_id == self.work_id
        }
        before_evidence = {
            item.id for item in before.evidence_runs if item.work_item_id == self.work_id
        }

        def mutate_then_reconcile(*args, **kwargs):
            create_record(
                str(self.temp_dir),
                "work",
                {
                    "id": "WORK-CONCURRENT-REFRESH-RACE",
                    "title": "Concurrent workspace mutation",
                    "palari": "PALARI-STEWARD",
                    "goal": "GOAL-REPO-0001",
                    "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                    "risk": "R1",
                    "intensity": "light",
                    "required_approval_count": 0,
                    "scope": "Prove refresh detects final-window state drift",
                    "acceptance_target": "The unrelated mutation remains visible",
                    "status": "active",
                    "allowed_resources": ["README.md"],
                    "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                    "output_targets": ["README.md"],
                    "forbidden_actions": ["deploy"],
                    "verification_expectations": ["affected verification"],
                },
                command="test concurrent refresh mutation",
                actor="PALARI-STEWARD",
            )
            return reconcile_agent_proof(*args, **kwargs)

        with (
            patch(
                "palari_company_os.agent_advance.run_or_reuse",
                side_effect=self._passing_attestation,
            ),
            patch(
                "palari_company_os.agent_advance.reconcile_agent_proof",
                side_effect=mutate_then_reconcile,
            ),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(result["blockers"][0]["code"], "REFRESH_STATE_CHANGED")
        after = Ws.load(self.temp_dir)
        self.assertIsNotNone(after.work_item("WORK-CONCURRENT-REFRESH-RACE"))
        self.assertEqual(
            before_attempts,
            {item.id for item in after.attempts if item.work_item_id == self.work_id},
        )
        self.assertEqual(
            before_receipts,
            {item.id for item in after.receipts if item.work_item_id == self.work_id},
        )
        self.assertEqual(
            before_evidence,
            {item.id for item in after.evidence_runs if item.work_item_id == self.work_id},
        )

    def test_explicit_refresh_rejects_artifact_race_before_reconciliation(
        self,
    ) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        self._record_current_authority()
        (self.temp_dir / "RELATED.md").write_text(
            "later repository context\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-u"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "RELATED.md"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "later context"],
            check=True,
        )
        before = Ws.load(self.temp_dir)
        before_attempts = {
            item.id for item in before.attempts if item.work_item_id == self.work_id
        }
        before_receipts = {
            item.id for item in before.receipts if item.work_item_id == self.work_id
        }
        before_evidence = {
            item.id for item in before.evidence_runs if item.work_item_id == self.work_id
        }

        def mutate_then_reconcile(*args, **kwargs):
            (self.temp_dir / "README.md").write_text(
                "tracked artifact drift after verification\n",
                encoding="utf-8",
            )
            return reconcile_agent_proof(*args, **kwargs)

        with (
            patch(
                "palari_company_os.agent_advance.run_or_reuse",
                side_effect=self._passing_attestation,
            ),
            patch(
                "palari_company_os.agent_advance.reconcile_agent_proof",
                side_effect=mutate_then_reconcile,
            ),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(result["blockers"][0]["code"], "REFRESH_STATE_CHANGED")
        after = Ws.load(self.temp_dir)
        self.assertEqual(
            before_attempts,
            {item.id for item in after.attempts if item.work_item_id == self.work_id},
        )
        self.assertEqual(
            before_receipts,
            {item.id for item in after.receipts if item.work_item_id == self.work_id},
        )
        self.assertEqual(
            before_evidence,
            {item.id for item in after.evidence_runs if item.work_item_id == self.work_id},
        )

    def test_explicit_refresh_rejects_rename_into_governance_path(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        self._record_current_authority()
        (self.temp_dir / "RELATED.md").write_text(
            "later repository context\n",
            encoding="utf-8",
        )
        (self.temp_dir / "VALUABLE.md").write_text(
            "substantive tracked state\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-u"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "add",
                "RELATED.md",
                "VALUABLE.md",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "later context"],
            check=True,
        )
        before = Ws.load(self.temp_dir)
        before_attempts = {
            item.id for item in before.attempts if item.work_item_id == self.work_id
        }
        before_receipts = {
            item.id for item in before.receipts if item.work_item_id == self.work_id
        }
        before_evidence = {
            item.id for item in before.evidence_runs if item.work_item_id == self.work_id
        }

        def rename_then_reconcile(*args, **kwargs):
            (self.temp_dir / ".palari" / "governance-journal.v1.jsonl").unlink()
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.temp_dir),
                    "mv",
                    "VALUABLE.md",
                    ".palari/governance-journal.v1.jsonl",
                ],
                check=True,
            )
            return reconcile_agent_proof(*args, **kwargs)

        with (
            patch(
                "palari_company_os.agent_advance.run_or_reuse",
                side_effect=self._passing_attestation,
            ),
            patch(
                "palari_company_os.agent_advance.reconcile_agent_proof",
                side_effect=rename_then_reconcile,
            ),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(result["blockers"][0]["code"], "REFRESH_STATE_CHANGED")
        after = Ws.load(self.temp_dir)
        self.assertEqual(
            before_attempts,
            {item.id for item in after.attempts if item.work_item_id == self.work_id},
        )
        self.assertEqual(
            before_receipts,
            {item.id for item in after.receipts if item.work_item_id == self.work_id},
        )
        self.assertEqual(
            before_evidence,
            {item.id for item in after.evidence_runs if item.work_item_id == self.work_id},
        )

    def test_ordinary_reconciliation_maps_workspace_cas_race_to_state_changed(
        self,
    ) -> None:
        before = Ws.load(self.temp_dir)
        with (
            patch(
                "palari_company_os.agent_advance.run_or_reuse",
                side_effect=self._passing_attestation,
            ),
            patch(
                "palari_company_os.authoring.write_store",
                side_effect=WorkspaceError(
                    "workspace changed since it was loaded; retry command"
                ),
            ),
        ):
            result = agent_advance(
                before,
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "state-changed", result)
        after = Ws.load(self.temp_dir)
        self.assertFalse(
            any(item.work_item_id == self.work_id for item in after.attempts)
        )
        self.assertFalse(
            any(item.work_item_id == self.work_id for item in after.receipts)
        )
        self.assertFalse(
            any(item.work_item_id == self.work_id for item in after.evidence_runs)
        )

    def test_explicit_refresh_rejects_changed_artifact_without_running_profiles(
        self,
    ) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        self._record_current_authority()
        (self.temp_dir / "README.md").write_text(
            "changed governed artifact\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-u"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "change artifact"],
            check=True,
        )

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=AssertionError("unsafe refresh ran verification"),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "REFRESH_ARTIFACT_CHANGED")

    def test_explicit_refresh_rejects_dirty_tracked_repository_context(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        (self.temp_dir / "RELATED.md").write_text("committed context\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.temp_dir), "add", "-u"], check=True)
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "RELATED.md"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "add context"],
            check=True,
        )
        (self.temp_dir / "RELATED.md").write_text("dirty context\n", encoding="utf-8")

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=AssertionError("dirty refresh ran verification"),
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
                refresh_verification=True,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "REFRESH_DIRTY_WORKTREE")
        self.assertIn("RELATED.md", result["blockers"][0]["message"])

    def test_later_negative_human_decision_blocks_terminalization(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        head_sha, evidence_id, review_id = self._record_current_authority()
        create_human_decision(
            str(self.temp_dir),
            {
                "id": "HUMAN-DECISION-TEST-ADVANCE-REVOKED",
                "work_item_id": self.work_id,
                "human_id": "HUMAN-FOUNDER",
                "reviewed_head": head_sha,
                "decision": "changes-requested",
                "status": "changes-requested",
                "acceptance_mode": "human",
                "quorum_status": "not-met",
                "evidence_reference": evidence_id,
                "review_reference": review_id,
            },
            command="test human revocation",
            actor="HUMAN-FOUNDER",
        )

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertNotEqual(result["status"], "completed")
        workspace = Ws.load(self.temp_dir)
        self.assertEqual(workspace.work_item(self.work_id).status, "active")
        self.assertFalse(
            any(
                record.work_item_id == self.work_id
                for record in workspace.acceptance_records
            )
        )

    def test_failed_terminal_projection_leaves_no_partial_acceptance(self) -> None:
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            first = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(first["status"], "review-required")
        self._record_current_authority()
        create_record(
            str(self.temp_dir),
            "decision",
            {
                "id": "DECISION-TEST-ADVANCE-OPEN",
                "question": "May this exact work complete?",
                "status": "open",
                "options": ["yes", "no"],
                "tradeoffs": ["Completion is blocked while this remains open."],
                "recommendation": "Resolve explicitly.",
                "safe_default": "no",
                "required_human": "HUMAN-FOUNDER",
                "linked_work": self.work_id,
            },
            command="test open decision",
            actor="HUMAN-FOUNDER",
        )

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["blockers"][0]["code"],
            "ACCEPTED_COMPLETION_INVALID",
        )
        workspace = Ws.load(self.temp_dir)
        self.assertEqual(workspace.work_item(self.work_id).status, "active")
        self.assertFalse(
            any(
                record.work_item_id == self.work_id
                for record in workspace.acceptance_records
            )
        )

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

    def test_custom_receipt_summary_fails_before_verification(self) -> None:
        before = (self.temp_dir / "workspace.json").read_bytes()
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=AssertionError("unsafe summary executed verification"),
        ):
            with self.assertRaisesRegex(WorkspaceError, "deterministic receipt actions"):
                agent_advance(
                    Ws.load(self.temp_dir),
                    self.temp_dir,
                    self.work_id,
                    "PALARI-STEWARD",
                    summary="Changed the bounded README artifact.",
                )
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

    def test_cli_help_describes_verification_cache_as_advisory(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as exit_context:
            build_parser().parse_args(["agent", "advance", "--help"])

        self.assertEqual(exit_context.exception.code, 0)
        rendered = output.getvalue()
        self.assertIn("Ignore advisory cached records", rendered)
        self.assertNotIn("reusing matching passing attestations", rendered)

    def test_legacy_claim_pending_prepare_dry_run_is_read_only(self) -> None:
        self._assert_legacy_pending_dry_run_is_read_only("before_apply")

    def test_legacy_claim_pending_commit_dry_run_is_read_only(self) -> None:
        self._assert_legacy_pending_dry_run_is_read_only("after_apply")

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

    def test_crash_after_workspace_replace_reverifies_before_commit_recovery(self) -> None:
        self._crash_reconciliation("after_apply")
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ) as runner:
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "review-required")
        self.assertFalse(result["would_mutate"])
        self.assertEqual(runner.call_count, 3)

    def test_pending_recovery_failed_fresh_verification_never_mutates_journal(self) -> None:
        self._crash_reconciliation("after_apply")
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        before_journal = journal.read_bytes()

        def failed(_workspace, _root, profile, context, **_kwargs):
            result = self._passing_attestation(
                _workspace, _root, profile, context, **_kwargs
            )
            result["attestation"]["status"] = "failed"
            return result

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=failed,
        ) as runner:
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["blockers"][0]["code"], "RECOVERY_VERIFICATION_FAILED"
        )
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(before_journal, journal.read_bytes())

    def test_pending_recovery_rechecks_scope_after_fresh_verification(self) -> None:
        self._crash_reconciliation("after_apply")
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        before_journal = journal.read_bytes()
        calls = 0

        def dirty_then_pass(_workspace, _root, profile, context, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                (self.temp_dir / "unapproved-after-verification.txt").write_text(
                    "unexpected mutation\n", encoding="utf-8"
                )
            return self._passing_attestation(
                _workspace, _root, profile, context, **_kwargs
            )

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=dirty_then_pass,
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "RECOVERY_STATE_CHANGED")
        self.assertEqual(before_journal, journal.read_bytes())

    def test_pending_prepare_rechecks_scope_after_fresh_verification(self) -> None:
        self._crash_reconciliation("before_apply")
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        before_journal = journal.read_bytes()
        calls = 0

        def dirty_then_pass(_workspace, _root, profile, context, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                (self.temp_dir / "unapproved-after-verification.txt").write_text(
                    "unexpected mutation\n", encoding="utf-8"
                )
            return self._passing_attestation(
                _workspace, _root, profile, context, **_kwargs
            )

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=dirty_then_pass,
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "RECOVERY_STATE_CHANGED")
        self.assertEqual(before_journal, journal.read_bytes())

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

    def test_unrelated_pending_commit_is_never_recovered(self) -> None:
        self._unrelated_pending_transaction("after_apply")
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        before_journal = journal.read_bytes()

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "PENDING_TRANSACTION_MISMATCH")
        self.assertEqual(before_journal, journal.read_bytes())

    def test_unrelated_pending_prepare_is_never_aborted(self) -> None:
        self._unrelated_pending_transaction("before_apply")
        journal = self.temp_dir / ".palari" / "governance-journal.v1.jsonl"
        before_journal = journal.read_bytes()

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "PENDING_TRANSACTION_MISMATCH")
        self.assertEqual(before_journal, journal.read_bytes())

    def test_proof_like_pending_commit_cannot_expand_bound_fields(self) -> None:
        def mutate(_metadata: dict, after: dict) -> None:
            work = next(item for item in after["work_items"] if item["id"] == self.work_id)
            attempt = next(
                item for item in after["attempts"] if item["id"] == work["current_attempt"]
            )
            work["title"] = "Expanded during recovery"
            work["allowed_resources"].append("outside/**")
            attempt["allowed_paths"].append("outside/**")
            attempt["claim_id"] = "CLAIM-SUBSTITUTED"
            attempt["claim_expires_at"] = "2099-01-01T00:00:00Z"
            attempt["model_or_worker"] = "substituted-worker"

        self._tamper_pending_proof("after_apply", mutate)
        self._assert_pending_mismatch_without_journal_mutation("pending-commit")

    def test_proof_like_pending_prepare_cannot_substitute_proof_ids(self) -> None:
        def mutate(metadata: dict, after: dict) -> None:
            replacements = {
                "attempt": "ATTEMPT-ARBITRARY",
                "receipt": "RECEIPT-ARBITRARY",
                "evidence": "EVIDENCE-ARBITRARY",
            }
            for item in metadata["objects"]:
                if item["type"] in replacements:
                    old_id = item["id"]
                    new_id = replacements[item["type"]]
                    item["id"] = new_id
                    collection = item["collection"]
                    record = next(value for value in after[collection] if value["id"] == old_id)
                    record["id"] = new_id
            work = next(item for item in after["work_items"] if item["id"] == self.work_id)
            work["current_attempt"] = replacements["attempt"]
            receipt = next(item for item in after["receipts"] if item["id"] == replacements["receipt"])
            receipt["attempt_id"] = replacements["attempt"]
            evidence = next(
                item for item in after["evidence_runs"] if item["id"] == replacements["evidence"]
            )
            evidence["attempt_id"] = replacements["attempt"]

        self._tamper_pending_proof("before_apply", mutate)
        self._assert_pending_mismatch_without_journal_mutation("pending-prepare")

    def test_proof_like_pending_prepare_rejects_unsafe_receipt_action(self) -> None:
        def mutate(metadata: dict, after: dict) -> None:
            receipt = next(
                item for item in after["receipts"] if item["work_item_id"] == self.work_id
            )
            receipt["actions_taken"][0] = "Performed an external deployment."
            metadata["reason"] = "receipt-action:" + receipt["actions_taken"][0]

        self._tamper_pending_proof("before_apply", mutate)
        self._assert_pending_mismatch_without_journal_mutation("pending-prepare")

    def test_proof_like_pending_commit_rejects_forged_verification_command(self) -> None:
        def mutate(_metadata: dict, after: dict) -> None:
            evidence = next(
                item for item in after["evidence_runs"] if item["work_item_id"] == self.work_id
            )
            evidence["commands"][0] = (
                "complete attestation VERIFY-COMPLETE-FORGED sha256:" + "0" * 64
            )

        self._tamper_pending_proof("after_apply", mutate)
        self._assert_pending_mismatch_without_journal_mutation("pending-commit")

    def test_proof_like_pending_prepare_rejects_commit_and_time_substitution(self) -> None:
        def mutate(_metadata: dict, after: dict) -> None:
            work = next(item for item in after["work_items"] if item["id"] == self.work_id)
            attempt = next(
                item for item in after["attempts"] if item["id"] == work["current_attempt"]
            )
            attempt["commits"] = ["b" * 40, attempt["head_sha"]]
            attempt["started_at"] = "2098-01-01T00:00:00Z"
            attempt["updated_at"] = "2099-01-01T00:00:00Z"

        self._tamper_pending_proof("before_apply", mutate)
        self._assert_pending_mismatch_without_journal_mutation("pending-prepare")

    def test_proof_like_pending_commit_rejects_coherent_timestamp_restamp(self) -> None:
        def mutate(metadata: dict, after: dict) -> None:
            substituted = "2030-01-01T00:00:00Z"
            work = next(item for item in after["work_items"] if item["id"] == self.work_id)
            attempt = next(
                item for item in after["attempts"] if item["id"] == work["current_attempt"]
            )
            receipt = next(
                item for item in after["receipts"] if item["work_item_id"] == self.work_id
            )
            evidence = next(
                item for item in after["evidence_runs"] if item["work_item_id"] == self.work_id
            )
            attempt["started_at"] = substituted
            attempt["updated_at"] = substituted
            receipt["timestamp"] = substituted
            receipt["receipt_hash"] = receipt_hash(receipt)
            evidence["timestamp"] = substituted
            evidence["receipt_hash"] = receipt["receipt_hash"]
            evidence["manifest_hash"] = evidence_manifest_hash(evidence)
            metadata["timestamp"] = substituted

        self._tamper_pending_proof("after_apply", mutate)
        self._assert_pending_mismatch_without_journal_mutation("pending-commit")

    def test_proof_like_pending_commit_requires_current_output_binding(self) -> None:
        def mutate(_metadata: dict, after: dict) -> None:
            evidence = next(
                item for item in after["evidence_runs"] if item["work_item_id"] == self.work_id
            )
            evidence["output_binding_version"] = ""
            evidence["manifest_hash"] = evidence_manifest_hash(evidence)

        self._tamper_pending_proof("after_apply", mutate)
        self._assert_pending_mismatch_without_journal_mutation("pending-commit")

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

        expected_state = git_artifact_state(self.temp_dir, ["README.md"])
        with self.assertRaisesRegex(
            ReconciliationStateChanged,
            "tracked cleanliness",
        ):
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
                    "commands": [
                        "complete attestation VERIFY-COMPLETE-TEST sha256:" + "1" * 64,
                        "install-smoke attestation VERIFY-INSTALL-SMOKE-TEST sha256:"
                        + "2" * 64,
                        "docs-check attestation VERIFY-DOCS-CHECK-TEST sha256:" + "3" * 64,
                    ],
                    "artifacts": ["README.md"],
                    "artifact_hashes": expected_state["artifact_hashes"],
                    "summary": "This must fail before mutation.",
                    "freshness": "exact-head",
                },
                head_sha=head,
                changed_files=["README.md"],
                output_targets=["README.md"],
                proof_timestamp=_git_commit_timestamp(
                    {"git_root": str(self.temp_dir), "head_sha": head}
                ),
                expected_workspace_digest=workspace_digest(
                    load_store(self.temp_dir).data
                ),
                expected_git_head=head,
                expected_artifact_hashes=expected_state["artifact_hashes"],
            )

        self.assertEqual(before, (self.temp_dir / "workspace.json").read_bytes())

    def _crash_reconciliation(self, point: str) -> None:
        head = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        base_sha = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD^"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        context = default_context(
            head_sha=head,
            base_sha=base_sha,
            changed_paths=["README.md"],
            cleanliness="clean",
        )
        commands = []
        for profile in verification_profiles("R4", ["README.md"]):
            key = cache_key(profile, context)
            attestation_id = f"VERIFY-{profile.id.upper()}-{key[-16:].upper()}"
            commands.append(f"{profile.id} attestation {attestation_id} {key}")
        expected_state = git_artifact_state(self.temp_dir, ["README.md"])

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
                    "base_sha": base_sha,
                    "allowed_paths": ["README.md"],
                },
                receipt_record={
                    "id": f"RECEIPT-ADVANCE-{self.work_id}-{head[:12].upper()}",
                    "work_item_id": self.work_id,
                    "attempt_id": f"ATTEMPT-ADVANCE-{self.work_id}-{head[:12].upper()}",
                    "actor": "PALARI-STEWARD",
                    "sources_used": ["SOURCE-REPO-FOUNDATION"],
                    "actions_taken": [
                        "Changed 1 bounded committed artifact(s).",
                        "Ran exact-state Palari verification profiles.",
                    ],
                    "outputs_created": ["README.md"],
                    "not_done": [
                        "No human review, decision, acceptance, external write, push, merge, or deployment was performed."
                    ],
                    "undo_refs": ["README.md"],
                },
                evidence_record={
                    "id": f"EVIDENCE-ADVANCE-{self.work_id}-{head[:12].upper()}",
                    "work_item_id": self.work_id,
                    "attempt_id": f"ATTEMPT-ADVANCE-{self.work_id}-{head[:12].upper()}",
                    "head_sha": head,
                    "status": "passed",
                    "base_ref": base_sha,
                    "commands": commands,
                    "artifacts": ["README.md"],
                    "artifact_hashes": expected_state["artifact_hashes"],
                    "summary": "3 exact-state verification profile(s) passed.",
                    "freshness": "exact-head",
                },
                head_sha=head,
                changed_files=["README.md"],
                output_targets=["README.md"],
                proof_timestamp=_git_commit_timestamp(
                    {"git_root": str(self.temp_dir), "head_sha": head}
                ),
                expected_workspace_digest=workspace_digest(
                    load_store(self.temp_dir).data
                ),
                expected_git_head=head,
                expected_artifact_hashes=expected_state["artifact_hashes"],
                crash_hook=crash_hook,
            )

    def _assert_legacy_pending_dry_run_is_read_only(self, point: str) -> None:
        self._crash_reconciliation(point)
        claim_path = next((self.temp_dir / ".palari" / "claims").glob("*.json"))
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        claim.pop("workspace_file_hash", None)
        claim_path.write_text(json.dumps(claim), encoding="utf-8")
        workspace_path = self.temp_dir / "workspace.json"
        journal_path = journal_file_path(workspace_path)
        before = {
            "workspace": workspace_path.read_bytes(),
            "journal": journal_path.read_bytes(),
            "claim": claim_path.read_bytes(),
        }
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

        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=AssertionError("legacy dry-run executed verification"),
        ):
            result = run_command(args)

        self.assertTrue(result.payload["dry_run"])
        self.assertFalse(result.payload["would_mutate"])
        self.assertEqual(before["workspace"], workspace_path.read_bytes())
        self.assertEqual(before["journal"], journal_path.read_bytes())
        self.assertEqual(before["claim"], claim_path.read_bytes())

    def _unrelated_pending_transaction(self, point: str) -> None:
        data_path = self.temp_dir / "workspace.json"
        before = json.loads(data_path.read_text(encoding="utf-8"))
        after = deepcopy(before)
        after["name"] = "Unrelated pending mutation"

        def apply() -> None:
            data_path.write_text(json.dumps(after), encoding="utf-8")

        def crash_hook(current: str) -> None:
            if current == point:
                raise RuntimeError(f"injected unrelated crash at {point}")

        with self.assertRaisesRegex(RuntimeError, point):
            transact(
                data_path,
                before_data=before,
                after_data=after,
                metadata=MutationMetadata(
                    command="other command",
                    actor="PALARI-REVIEWER",
                    action="unrelated-mutation",
                    timestamp=utc_timestamp(),
                    objects=(
                        {
                            "type": "workspace",
                            "collection": "workspace",
                            "id": "UNRELATED",
                        },
                    ),
                ),
                apply=apply,
                crash_hook=crash_hook,
            )

    def _tamper_pending_proof(self, point: str, mutate) -> None:
        self._crash_reconciliation(point)
        context = pending_workspace_journal_context(self.temp_dir)
        self.assertIsNotNone(context)
        assert context is not None
        journal = journal_file_path(self.temp_dir / "workspace.json")
        records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
        prepared = records[-1]
        self.assertEqual(prepared["record_type"], "prepare")
        mutate(prepared["metadata"], prepared["after_projection"])
        prepared["after_workspace_digest"] = workspace_digest(prepared["after_projection"])
        prepared["logical_changes"] = logical_changes(
            context["before_projection"], prepared["after_projection"]
        )
        prepared["transaction_id"] = _transaction_id(prepared)
        prepared["record_digest"] = record_digest(prepared)
        journal.write_text(
            "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in records),
            encoding="utf-8",
        )
        if point == "after_apply":
            (self.temp_dir / "workspace.json").write_text(
                json.dumps(prepared["after_projection"]), encoding="utf-8"
            )

    def _assert_pending_mismatch_without_journal_mutation(self, expected_status: str) -> None:
        report = verify_workspace_journal(self.temp_dir)
        self.assertEqual(report["status"], expected_status, report)
        journal = journal_file_path(self.temp_dir / "workspace.json")
        before_journal = journal.read_bytes()

        result = agent_advance(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"][0]["code"], "PENDING_TRANSACTION_MISMATCH")
        self.assertEqual(before_journal, journal.read_bytes())

    def _record_current_authority(self) -> tuple[str, str, str]:
        workspace = Ws.load(self.temp_dir)
        work = workspace.work_item(self.work_id)
        self.assertIsNotNone(work)
        assert work is not None and work.current_attempt
        attempt = next(
            item for item in workspace.attempts if item.id == work.current_attempt
        )
        head_sha = attempt.head_sha or attempt.commits[-1]
        evidence = next(
            item
            for item in workspace.evidence_runs
            if item.work_item_id == self.work_id and item.attempt_id == attempt.id
        )
        review_id = "REVIEW-TEST-ADVANCE"
        create_record(
            str(self.temp_dir),
            "review",
            {
                "id": review_id,
                "work_item_id": self.work_id,
                "reviewed_head": head_sha,
                "reviewer": "PALARI-ARCHITECT",
                "verdict": "accept-ready",
                "findings": [],
                "checks_inspected": ["exact deterministic advance proof"],
                "residual_risks": [],
            },
            command="test independent review",
            actor="PALARI-ARCHITECT",
        )
        create_human_decision(
            str(self.temp_dir),
            {
                "id": "HUMAN-DECISION-TEST-ADVANCE",
                "work_item_id": self.work_id,
                "human_id": "HUMAN-FOUNDER",
                "reviewed_head": head_sha,
                "decision": "accepted",
                "status": "accepted",
                "acceptance_mode": "human",
                "quorum_status": "met",
                "evidence_reference": evidence.id,
                "review_reference": review_id,
            },
            command="test human acceptance",
            actor="HUMAN-FOUNDER",
            automatic_convergence=False,
        )
        return head_sha, evidence.id, review_id

    def _record_changes_requested(self, head_sha: str, review_id: str) -> None:
        create_record(
            str(self.temp_dir),
            "review",
            {
                "id": review_id,
                "work_item_id": self.work_id,
                "reviewed_head": head_sha,
                "reviewer": "PALARI-ARCHITECT",
                "verdict": "changes-requested",
                "findings": [],
                "checks_inspected": ["exact reviewed proof head"],
                "residual_risks": [],
            },
            command="test independent changes requested",
            actor="PALARI-ARCHITECT",
        )

    def _advance_with_projection_outputs(self):
        release_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )
        projection_outputs = [
            "README.md",
            "workspace.json",
            ".palari/history.jsonl",
            ".palari/governance-journal.v1.jsonl",
        ]
        raw = load_store(self.temp_dir).data
        workbench = next(
            item
            for item in raw["workbenches"]
            if item["id"] == "WORKBENCH-REPO-FOUNDATION"
        )
        update_record(
            str(self.temp_dir),
            "workbench",
            "WORKBENCH-REPO-FOUNDATION",
            {
                "output_target_ids": sorted(
                    set(workbench["output_target_ids"]) | set(projection_outputs)
                )
            },
            command="test permit self-mutating governance outputs",
            actor="PALARI-STEWARD",
        )
        update_record(
            str(self.temp_dir),
            "work",
            self.work_id,
            {
                "allowed_resources": projection_outputs,
                "output_targets": projection_outputs,
            },
            command="test declare self-mutating governance outputs",
            actor="PALARI-STEWARD",
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "add",
                "workspace.json",
                ".palari/history.jsonl",
                ".palari/governance-journal.v1.jsonl",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "bind governance outputs"],
            check=True,
        )
        start_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            "execute",
        )
        (self.temp_dir / "README.md").write_text(
            "self-journal candidate\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "self-journal candidate"],
            check=True,
        )
        with patch(
            "palari_company_os.agent_advance.run_or_reuse",
            side_effect=self._passing_attestation,
        ):
            result = agent_advance(
                Ws.load(self.temp_dir),
                self.temp_dir,
                self.work_id,
                "PALARI-STEWARD",
            )
        self.assertEqual(result["status"], "review-required", result)
        workspace = Ws.load(self.temp_dir)
        return next(
            item for item in workspace.evidence_runs if item.work_item_id == self.work_id
        )

    def _restart_with_path_intent(self, intent: str) -> None:
        release_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )
        self.work_id = f"WORK-TEST-ADVANCE-{intent.upper()}"
        create_record(
            str(self.temp_dir),
            "work",
            {
                "id": self.work_id,
                "title": f"Test exact {intent} intent",
                "palari": "PALARI-STEWARD",
                "goal": "GOAL-REPO-0001",
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R4",
                "intensity": "high",
                "required_approval_count": 1,
                "required_approval_capability": "architecture",
                "scope": f"Prove an exact {intent} mutation",
                "acceptance_target": "Exact ancestry proof reaches review",
                "status": "active",
                "allowed_resources": ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": ["README.md"],
                "path_intents": [{"path": "README.md", "intent": intent}],
                "forbidden_actions": ["deploy", "human_review"],
                "verification_expectations": ["repository verification"],
            },
            command="test declare exact path intent",
            actor="PALARI-STEWARD",
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "add",
                "workspace.json",
                ".palari/history.jsonl",
                ".palari/governance-journal.v1.jsonl",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "bind path intent"],
            check=True,
        )
        started = start_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self.assertEqual(started["start"]["status"], "claimed")

    def _passing_attestation(self, _workspace, _root, profile, context, **_kwargs):
        key = cache_key(profile, context)
        return {
            "cache_hit": False,
            "attestation": {
                "attestation_id": f"VERIFY-{profile.id.upper()}-{key[-16:].upper()}",
                "cache_key": key,
                "status": "passed",
                "duration_ms": 1,
                "stdout_digest": "sha256:" + "1" * 64,
                "stderr_digest": "sha256:" + "2" * 64,
            },
        }


if __name__ == "__main__":
    unittest.main()
