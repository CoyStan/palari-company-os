from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_advance import agent_advance, agent_advance_dry_run
from palari_company_os.agent_runtime import claim_integrity_error, read_claim
from palari_company_os.authoring import ReconciliationStateChanged, update_record
from palari_company_os.governance_journal import (
    MutationMetadata,
    utc_timestamp,
    verify_workspace_journal,
)
from palari_company_os.store import load_store, write_store
from palari_company_os.verification_attestations import cache_key
from palari_company_os.workspace import Workspace
from tests.maintainer_profile_fixture import create_git_repository, git


agent_advance_module = importlib.import_module("palari_company_os.agent_advance")


class MaintainerProfileRuntimeTests(unittest.TestCase):
    def test_create_modify_delete_intents_bind_exact_source_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            (repo.root / "REMOVE.md").write_text("remove me\n", encoding="utf-8")
            git(repo.root, "add", "--", "REMOVE.md")
            git(repo.root, "commit", "-qm", "add deletion fixture")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()
            added = repo.profile_json(
                "work",
                "add",
                "Exercise exact maintainer path intents",
                "--create",
                "artifacts/created.txt",
                "--modify",
                "README.md",
                "--delete",
                "REMOVE.md",
                "--risk",
                "R1",
                "--intensity",
                "light",
                "--approvals",
                "0",
                "--verify",
                "Exact path intents hold.",
                "--json",
            )
            work_id = str(added["work_item"]["id"])
            started = repo.emitted_json(added["next_commands"][0])
            self.assertEqual(started["start"]["status"], "claimed")

            created = repo.root / "artifacts" / "created.txt"
            created.parent.mkdir(parents=True)
            created.write_text("created\n", encoding="utf-8")
            (repo.root / "README.md").write_text(
                "modified source candidate\n",
                encoding="utf-8",
            )
            (repo.root / "REMOVE.md").unlink()
            git(repo.root, "add", "-A")
            git(repo.root, "commit", "-qm", "apply exact path intents")
            candidate_head = git(repo.root, "rev-parse", "HEAD").stdout.strip()

            with patch.object(
                agent_advance_module,
                "run_or_reuse",
                side_effect=self._passing_attestation,
            ):
                result = agent_advance(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            self.assertEqual(result["status"], "completed", result)
            self.assertIsNotNone(work)
            assert work is not None and work.current_attempt
            attempt = next(
                item for item in final.attempts if item.id == work.current_attempt
            )
            self.assertEqual(attempt.head_sha, candidate_head)
            self.assertEqual(
                attempt.changed_files,
                ["README.md", "REMOVE.md", "artifacts/created.txt"],
            )
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_source_change_outside_task_boundary_blocks_before_proof(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            (repo.root / "UNRELATED.md").write_text(
                "unrelated baseline\n",
                encoding="utf-8",
            )
            git(repo.root, "add", "--", "UNRELATED.md")
            git(repo.root, "commit", "-qm", "add unrelated fixture")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()
            work_id = self._claim_work(repo)
            (repo.root / "UNRELATED.md").write_text(
                "unrelated tracked change\n",
                encoding="utf-8",
            )
            git(repo.root, "add", "--", "UNRELATED.md")
            git(repo.root, "commit", "-qm", "change outside task boundary")

            with patch.object(
                agent_advance_module,
                "run_or_reuse",
                side_effect=AssertionError("blocked work ran verification"),
            ):
                result = agent_advance(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            self.assertEqual(result["status"], "blocked", result)
            self.assertFalse(result["would_mutate"])
            self.assertFalse(
                any(
                    item.work_item_id == work_id
                    for item in Workspace.load(repo.workspace_file).evidence_runs
                )
            )
            self.assertIsNotNone(read_claim(repo.workspace_file, work_id))
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_claim_bound_dry_run_uses_exact_maintainer_data_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)

            result = agent_advance_dry_run(
                repo.workspace_file,
                work_id,
                "PALARI-CLAUDE",
            )

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["status"], "planned", result)
            self.assertTrue(result["dry_run"])
            self.assertTrue(result["preflight"]["ok"], result)
            self.assertEqual(repo.status(), "")

    def test_unrelated_valid_journal_extension_is_not_claim_owned_proof(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()
            work_id = self._claim_work(repo)
            claim = read_claim(repo.workspace_file, work_id)
            self.assertIsNotNone(claim)
            assert claim is not None

            update_record(
                str(repo.workspace_file),
                "goal",
                "GOAL-0001",
                {"title": "A valid but unrelated local mutation"},
                command="test unrelated maintainer mutation",
                actor="PALARI-CLAUDE",
            )

            error = claim_integrity_error(
                repo.workspace_file,
                work_id,
                claim,
                allow_maintainer_journal_extension=True,
            )
            self.assertIn(
                "not claim-owned proof reconciliation",
                error,
            )
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_forged_proof_metadata_cannot_hide_unrelated_projection_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()
            work_id = self._claim_work(repo)
            claim = read_claim(repo.workspace_file, work_id)
            self.assertIsNotNone(claim)
            assert claim is not None

            store = load_store(repo.workspace_file)
            store.data["goals"][0]["title"] = "Forged proof-side goal mutation"
            write_store(
                store,
                metadata=MutationMetadata(
                    command="agent advance",
                    actor="PALARI-CLAUDE",
                    action="reconciled-agent-proof",
                    timestamp=utc_timestamp(),
                    objects=(
                        {
                            "type": "work",
                            "collection": "work_items",
                            "id": work_id,
                        },
                        {
                            "type": "attempt",
                            "collection": "attempts",
                            "id": "ATTEMPT-FORGED",
                        },
                        {
                            "type": "receipt",
                            "collection": "receipts",
                            "id": "RECEIPT-FORGED",
                        },
                        {
                            "type": "evidence",
                            "collection": "evidence_runs",
                            "id": "EVIDENCE-FORGED",
                        },
                    ),
                    reason="receipt-action:forged",
                ),
            )

            error = claim_integrity_error(
                repo.workspace_file,
                work_id,
                claim,
                allow_maintainer_journal_extension=True,
            )
            self.assertIn(
                "changes state outside its proof binding",
                error,
            )
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_fabricated_verification_result_cannot_reconcile_proof(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)
            workspace = Workspace.load(repo.workspace_file)
            facts, _, _, preflight = agent_advance_module._collect_facts(
                workspace,
                repo.workspace_file,
                work_id,
                "PALARI-CLAUDE",
            )
            fabricated = [
                {
                    "profile_id": "bogus",
                    "attestation_id": "NOT-RUN",
                    "cache_key": "sha256:" + "0" * 64,
                    "cache_hit": False,
                    "status": "passed",
                    "duration_ms": 1,
                    "stdout_digest": "sha256:" + "1" * 64,
                    "stderr_digest": "sha256:" + "2" * 64,
                }
            ]

            with self.assertRaisesRegex(
                ReconciliationStateChanged,
                "verification results",
            ):
                agent_advance_module._reconcile_proof(
                    workspace,
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                    preflight,
                    fabricated,
                    expected_workspace_digest=str(facts["workspace_digest"]),
                    expected_git_head=str(facts["git"]["head_sha"]),
                    expected_artifact_hashes=list(
                        facts["git"]["artifact_hashes"]
                    ),
                )

            final = Workspace.load(repo.workspace_file)
            self.assertFalse(
                any(item.work_item_id == work_id for item in final.evidence_runs)
            )
            self.assertIsNotNone(read_claim(repo.workspace_file, work_id))
            self.assertTrue(verify_workspace_journal(repo.workspace_file)["ok"])
            self.assertEqual(repo.status(), "")

    def test_completion_source_cas_rejects_commit_race_before_terminal_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)
            original_complete = agent_advance_module.complete_work

            def commit_before_completion(
                *args: object,
                **kwargs: object,
            ) -> object:
                (repo.root / "README.md").write_text(
                    "unreviewed concurrent candidate\n",
                    encoding="utf-8",
                )
                git(repo.root, "add", "--", "README.md")
                git(repo.root, "commit", "-qm", "inject concurrent candidate")
                return original_complete(*args, **kwargs)

            with (
                patch.object(
                    agent_advance_module,
                    "run_or_reuse",
                    side_effect=self._passing_attestation,
                ),
                patch.object(
                    agent_advance_module,
                    "complete_work",
                    side_effect=commit_before_completion,
                ),
            ):
                result = agent_advance(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            self.assertEqual(result["status"], "state-changed", result)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn(work.status, {"completed", "closed", "done"})
            self.assertIsNotNone(read_claim(repo.workspace_file, work_id))
            self.assertTrue(verify_workspace_journal(repo.workspace_file)["ok"])
            self.assertEqual(repo.status(), "")

    def test_r1_proof_reconciliation_completes_with_clean_source_checkout(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)

            with patch(
                "palari_company_os.agent_advance.run_or_reuse",
                side_effect=self._passing_attestation,
            ):
                result = agent_advance(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            journal = verify_workspace_journal(repo.workspace_file)
            self.assertEqual(result["status"], "completed", result)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertEqual(work.status, "completed")
            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            self.assertTrue(journal["ok"], journal)
            self.assertTrue(journal["chain_valid"], journal)
            self.assertIsNone(journal["pending"])
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )
            self.assertEqual(repo.tracked_profile_paths(), [])

    def test_r1_pending_commit_recovery_completes_and_releases_claim(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)
            original_reconcile = agent_advance_module.reconcile_agent_proof

            def crash_after_apply(*args: object, **kwargs: object) -> object:
                def crash_hook(point: str) -> None:
                    if point == "after_apply":
                        raise RuntimeError("injected maintainer crash after_apply")

                return original_reconcile(
                    *args,
                    **kwargs,
                    crash_hook=crash_hook,
                )

            with (
                patch.object(
                    agent_advance_module,
                    "run_or_reuse",
                    side_effect=self._passing_attestation,
                ),
                patch.object(
                    agent_advance_module,
                    "reconcile_agent_proof",
                    side_effect=crash_after_apply,
                ),
                self.assertRaisesRegex(RuntimeError, "after_apply"),
            ):
                agent_advance(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            pending = verify_workspace_journal(repo.workspace_file)
            self.assertEqual(pending["status"], "pending-commit", pending)
            self.assertIsNotNone(read_claim(repo.workspace_file, work_id))

            with patch.object(
                agent_advance_module,
                "run_or_reuse",
                side_effect=self._passing_attestation,
            ):
                result = agent_advance(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            self.assertEqual(result["status"], "completed", result)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertEqual(work.status, "completed")
            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            self.assertTrue(verify_workspace_journal(repo.workspace_file)["ok"])
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_terminal_retry_releases_leftover_owned_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)

            with (
                patch.object(
                    agent_advance_module,
                    "run_or_reuse",
                    side_effect=self._passing_attestation,
                ),
                patch.object(
                    agent_advance_module,
                    "_release_claim_if_owned",
                    side_effect=RuntimeError("injected crash before claim release"),
                ),
                self.assertRaisesRegex(RuntimeError, "before claim release"),
            ):
                agent_advance(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            completed = Workspace.load(repo.workspace_file).work_item(work_id)
            self.assertIsNotNone(completed)
            assert completed is not None
            self.assertEqual(completed.status, "completed")
            self.assertIsNotNone(read_claim(repo.workspace_file, work_id))

            result = agent_advance(
                Workspace.load(repo.workspace_file),
                repo.workspace_file,
                work_id,
                "PALARI-CLAUDE",
            )

            self.assertEqual(result["status"], "completed", result)
            self.assertTrue(result["would_mutate"])
            self.assertTrue(
                any(
                    step.get("step") == "claim-release"
                    and step.get("status") == "released"
                    for step in result["steps"]
                )
            )
            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def _claim_work(
        self,
        repo: Any,
        *,
        commit_candidate: bool = False,
    ) -> str:
        added = repo.profile_json(
            "work",
            "add",
            "Create one bounded maintainer artifact",
            "--create",
            "artifacts/maintainer-result.txt",
            "--risk",
            "R1",
            "--intensity",
            "light",
            "--approvals",
            "0",
            "--acceptance",
            "The exact local artifact is present.",
            "--verify",
            "Bounded deterministic checks pass.",
            "--json",
        )
        work_id = str(added["work_item"]["id"])
        started = repo.emitted_json(added["next_commands"][0])
        self.assertEqual(started["start"]["status"], "claimed")
        self.assertEqual(repo.status(), "")
        if commit_candidate:
            output = repo.root / "artifacts" / "maintainer-result.txt"
            output.parent.mkdir(parents=True)
            output.write_text("maintainer profile result\n", encoding="utf-8")
            git(repo.root, "add", "--", "artifacts/maintainer-result.txt")
            git(repo.root, "commit", "-qm", "add bounded maintainer result")
            self.assertEqual(repo.status(), "")
        return work_id

    @staticmethod
    def _passing_attestation(
        _workspace: object,
        _repo_root: object,
        profile: Any,
        context: Any,
        **_kwargs: object,
    ) -> dict[str, Any]:
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
