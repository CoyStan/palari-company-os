from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_advance import (
    _git_commit_timestamp,
    _verify_path_intents,
    agent_advance,
    plan_advance,
)
from palari_company_os.agent_finish import build_agent_finish
from palari_company_os.agent_next import build_agent_next
from palari_company_os.agent_runtime import (
    release_agent,
    start_agent,
)
from palari_company_os.authoring import (
    create_human_decision,
    create_record,
    reconcile_agent_proof,
    update_record,
)
from palari_company_os.evidence_manifest import (
    git_artifact_state,
    verify_evidence,
)
from palari_company_os.governance_journal import (
    MutationMetadata,
    _prepare_v2_record,
    checkpoint_workspace_journal,
    journal_file_path,
    pending_workspace_journal_context,
    transact,
    utc_timestamp,
    verify_workspace_journal,
    workspace_digest,
)
from palari_company_os.governance_convergence import (
    ConvergenceObservation,
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
from tests.workspace_fixture import write_current_agent_workspace


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

    def test_unreadable_range_fails_and_missing_intent_contract_is_noop(self) -> None:
        invalid = _verify_path_intents(
            self.root,
            [{"path": "create.txt", "intent": "create"}],
            ["create.txt"],
            "0" * 40,
            self.head,
        )
        missing_contract = _verify_path_intents(
            self.root,
            [],
            self.changed,
            self.base,
            self.head,
        )

        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["errors"][0]["code"], "PATH_INTENT_GIT_UNREADABLE")
        self.assertEqual(
            missing_contract,
            {"required": False, "ok": True, "checks": [], "errors": []},
        )

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

    def test_declared_external_write_disables_low_risk_auto_completion(self) -> None:
        facts = self._facts()
        facts["work"].update(
            risk="R1",
            intensity="light",
            required_approval_count=0,
            allowed_actions=["external_write"],
        )

        plan = plan_advance(facts)

        self.assertEqual(plan["expected_state"], "review-required")
        self.assertEqual(plan["stop_boundary"], "independent-review")
        self.assertIn("review-handoff", [item["step"] for item in plan["steps"]])

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
                "allowed_actions": ["local_write"],
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
        write_current_agent_workspace(self.temp_dir / "workspace.json")
        palari = self.temp_dir / ".palari"
        if palari.exists():
            shutil.rmtree(palari)
        checkpoint = checkpoint_workspace_journal(self.temp_dir, "PALARI-STEWARD")
        self.assertTrue(checkpoint["ok"])
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

    def _declare_current_only_work(self, work_id: str) -> None:
        """Declare work in the live workspace without adding it to the Git anchor."""
        self.work_id = work_id
        create_record(
            str(self.temp_dir),
            "work",
            {
                "id": self.work_id,
                "title": "Test current-only authority catalog",
                "palari": "PALARI-STEWARD",
                "goal": "GOAL-REPO-0001",
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R4",
                "intensity": "high",
                "required_approval_count": 1,
                "required_approval_capability": "architecture",
                "scope": "Produce one bounded README change.",
                "acceptance_target": "An uncommitted work contract remains bound to its first claim authority.",
                "status": "active",
                "allowed_resources": ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": ["README.md"],
                "parallel_policy": "independent",
                "forbidden_actions": ["deploy", "human_review"],
                "verification_expectations": ["repository verification"],
            },
            command="test declare current-only authority work",
            actor="PALARI-STEWARD",
        )
        anchored_workspace = subprocess.check_output(
            ["git", "-C", str(self.temp_dir), "show", "HEAD:workspace.json"],
            text=True,
        )
        self.assertNotIn(self.work_id, anchored_workspace)

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

    def test_preclaim_scope_and_actor_tamper_is_blocked_before_lease(self) -> None:
        release_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )
        self.assertTrue(
            (self.temp_dir / ".palari" / "claims" / f"{self.work_id}.baseline").exists()
        )
        update_record(
            str(self.temp_dir),
            "work",
            self.work_id,
            {
                "scope": "Expanded beyond the immutable work authority.",
                "allowed_resources": ["README.md", "AGENTS.md"],
                "output_targets": ["README.md", "AGENTS.md"],
            },
            command="test pre-claim scope authority expansion",
            actor="HUMAN-FOUNDER",
        )
        update_record(
            str(self.temp_dir),
            "palari",
            "PALARI-STEWARD",
            {
                "scope": "Expanded actor authority after the immutable baseline.",
                "default_worker": "substituted-worker",
            },
            command="test pre-claim actor authority substitution",
            actor="HUMAN-FOUNDER",
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "add",
                "workspace.json",
                ".palari/governance-journal.v2.jsonl",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-qm", "expand authority"],
            check=True,
        )

        with patch("palari_company_os.agent_runtime._claim_git_lease") as claim_lease:
            with self.assertRaisesRegex(
                WorkspaceError,
                "pre-claim scope authority differs from immutable baseline",
            ):
                start_agent(
                    Ws.load(self.temp_dir),
                    self.temp_dir,
                    self.work_id,
                    "PALARI-STEWARD",
                    "execute",
                )
        claim_lease.assert_not_called()
        self.assertFalse(
            (self.temp_dir / ".palari" / "claims" / f"{self.work_id}.json").exists()
        )
        lease_refs = subprocess.check_output(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "for-each-ref",
                "--format=%(refname)",
                "refs/palari/leases/",
            ],
            text=True,
        )
        self.assertNotIn(self.work_id, lease_refs)

    def test_current_only_catalog_rejects_post_lease_parallel_race_without_persisting(
        self,
        ) -> None:
        release_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )
        self._declare_current_only_work("WORK-TEST-CURRENT-ONLY-CATALOG-RACE")
        claim_path = self.temp_dir / ".palari" / "claims" / f"{self.work_id}.json"
        baseline_path = self.temp_dir / ".palari" / "claims" / f"{self.work_id}.baseline"

        from palari_company_os import agent_runtime

        original_claim_lease = agent_runtime._claim_git_lease
        provisional: dict[str, str] = {}

        def claim_lease_then_change_parallel_policy(
            *args: object,
            **kwargs: object,
        ) -> dict[str, str]:
            acquired = original_claim_lease(*args, **kwargs)
            provisional.update(acquired)
            update_record(
                str(self.temp_dir),
                "work",
                self.work_id,
                {"parallel_policy": "coordinate"},
                command="test current-only catalog post-lease authority change",
                actor="HUMAN-FOUNDER",
            )
            return acquired

        with patch(
            "palari_company_os.agent_runtime._claim_git_lease",
            side_effect=claim_lease_then_change_parallel_policy,
        ) as claim_lease:
            with self.assertRaisesRegex(
                WorkspaceError,
                "pre-claim scope authority differs from immutable baseline",
            ):
                start_agent(
                    Ws.load(self.temp_dir),
                    self.temp_dir,
                    self.work_id,
                    "PALARI-STEWARD",
                    "execute",
                )

        claim_lease.assert_called_once()
        self.assertTrue(provisional)
        self.assertFalse(claim_path.exists())
        self.assertFalse(baseline_path.exists())
        lease = subprocess.run(
            [
                "git",
                "-C",
                str(self.temp_dir),
                "rev-parse",
                "--verify",
                str(provisional["git_lease_ref"]),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(lease.returncode, 0)

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

    def test_dry_run_never_executes_verification_or_mutates(self) -> None:
        workspace_path = self.temp_dir / "workspace.json"
        journal_path = journal_file_path(workspace_path)
        claim_path = self.temp_dir / ".palari" / "claims" / f"{self.work_id}.json"
        before = {
            "workspace": workspace_path.read_bytes(),
            "journal": journal_path.read_bytes(),
            "claim": claim_path.read_bytes(),
        }
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
        self.assertEqual(before["workspace"], workspace_path.read_bytes())
        self.assertEqual(before["journal"], journal_path.read_bytes())
        self.assertEqual(before["claim"], claim_path.read_bytes())

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
        workspace = Ws.load(self.temp_dir)
        completed = workspace.work_item(work_id)
        self.assertIsNotNone(completed)
        assert completed is not None
        self.assertEqual(completed.status, "completed")
        self.assertIsNotNone(completed.current_attempt)
        evidence = next(
            item
            for item in workspace.evidence_runs
            if item.work_item_id == work_id
            and item.attempt_id == completed.current_attempt
        )
        current_head = subprocess.check_output(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        self.assertEqual(evidence.head_sha, current_head)
        self.assertTrue(
            verify_evidence(workspace, evidence.id, require_output_coverage=True)["ok"]
        )

    def test_v2_crash_before_apply_aborts_prepare_and_retries(self) -> None:
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

    def test_v2_crash_after_apply_reverifies_before_commit_recovery(self) -> None:
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

    def test_unrelated_pending_commit_is_never_recovered(self) -> None:
        self._unrelated_pending_transaction("after_apply")
        journal = self.temp_dir / ".palari" / "governance-journal.v2.jsonl"
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

    def test_v2_pending_proof_cannot_expand_bound_fields(self) -> None:
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
        after_projection = deepcopy(context["prepare"]["after_projection"])
        metadata = deepcopy(prepared["metadata"])
        mutate(metadata, after_projection)
        prepared = _prepare_v2_record(
            sequence=prepared["sequence"],
            previous_record_digest=prepared["previous_record_digest"],
            event_kind=prepared["event_kind"],
            coverage=prepared["coverage"],
            expected_before_workspace_digest=prepared[
                "expected_before_workspace_digest"
            ],
            before_workspace_digest=prepared["before_workspace_digest"],
            after_projection=after_projection,
            metadata=metadata,
            before_projection=context["before_projection"],
            predecessor=prepared.get("predecessor"),
        )
        records[-1] = prepared
        journal.write_text(
            "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in records),
            encoding="utf-8",
        )
        if point == "after_apply":
            (self.temp_dir / "workspace.json").write_text(
                json.dumps(after_projection), encoding="utf-8"
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
                ".palari/governance-journal.v2.jsonl",
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

class NonGitAgentStartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        write_current_agent_workspace(self.temp_dir / "workspace.json")
        self.work_id = "WORK-TEST-NON-GIT-RESTART"
        create_record(
            str(self.temp_dir),
            "work",
            {
                "id": self.work_id,
                "title": "Test non-Git claim restart",
                "palari": "PALARI-STEWARD",
                "goal": "GOAL-REPO-0001",
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R4",
                "intensity": "high",
                "required_approval_count": 1,
                "required_approval_capability": "architecture",
                "scope": "Start and restart bounded local work without Git metadata.",
                "acceptance_target": "A non-Git claim can be safely released or renewed.",
                "status": "active",
                "allowed_resources": ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": ["README.md"],
                "forbidden_actions": ["deploy", "human_review"],
                "verification_expectations": ["repository verification"],
            },
            command="test non-Git setup",
            actor="PALARI-STEWARD",
        )
        checkpoint = checkpoint_workspace_journal(self.temp_dir, "PALARI-STEWARD")
        self.assertTrue(checkpoint["ok"])
        (self.temp_dir / "README.md").write_text("before\n", encoding="utf-8")
        self.assertFalse((self.temp_dir / ".git").exists())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_non_git_release_and_expiry_restart_remain_supported(self) -> None:
        initial = start_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self.assertEqual(initial["start"]["status"], "claimed")
        initial_claim = initial["start"]["claim"]
        self.assertEqual(initial_claim["git_baseline"]["git_root"], "")
        self.assertEqual(initial_claim["git_baseline"]["head_sha"], "")

        released = release_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
        )
        self.assertTrue(released["released"])
        restarted = start_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self.assertEqual(restarted["start"]["status"], "claimed")
        restarted_claim = restarted["start"]["claim"]
        self.assertNotEqual(restarted_claim["claim_session"], initial_claim["claim_session"])

        claim_path = self.temp_dir / ".palari" / "claims" / f"{self.work_id}.json"
        expired = json.loads(claim_path.read_text(encoding="utf-8"))
        expired["lease_expires_at"] = "2000-01-01T00:00:00Z"
        claim_path.write_text(json.dumps(expired), encoding="utf-8")
        renewed = start_agent(
            Ws.load(self.temp_dir),
            self.temp_dir,
            self.work_id,
            "PALARI-STEWARD",
            "execute",
        )
        self.assertEqual(renewed["start"]["status"], "claimed")
        renewed_claim = renewed["start"]["claim"]
        self.assertNotEqual(renewed_claim["claim_session"], restarted_claim["claim_session"])
        self.assertNotEqual(renewed_claim["lease_expires_at"], "2000-01-01T00:00:00Z")

if __name__ == "__main__":
    unittest.main()
