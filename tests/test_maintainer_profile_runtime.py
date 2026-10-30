from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os import store as store_module
from palari_company_os.agent_advance import agent_advance, agent_advance_dry_run
from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.agent_runtime import claim_integrity_error, read_claim
from palari_company_os.approval_packs import (
    apply_pack_decision,
    build_approval_inbox,
)
from palari_company_os.authoring import (
    ReconciliationStateChanged,
    accept_work,
    create_human_decision,
    create_record,
    update_record,
)
from palari_company_os.evidence_manifest import stamp_evidence_record
from palari_company_os.governance_binding import review_proof_hash
from palari_company_os.governance_journal import (
    MutationMetadata,
    utc_timestamp,
    verify_workspace_journal,
)
from palari_company_os.review_guides import build_review_guide
from palari_company_os.store import load_store, write_store
from palari_company_os.simple_approval import SimpleApprovalError, approve_work
from palari_company_os.verification_attestations import cache_key
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.maintainer_profile_fixture import create_git_repository, git


agent_advance_module = importlib.import_module("palari_company_os.agent_advance")


def executable_palari_commands(value: object) -> list[str]:
    commands: list[str] = []

    def visit(item: object, *, executable: bool = True) -> None:
        if isinstance(item, dict):
            record_executable = executable and item.get("executable") is not False
            for key, nested in item.items():
                key_executable = record_executable
                marker = item.get(f"{key}_executable")
                if marker is False:
                    key_executable = False
                visit(nested, executable=key_executable)
        elif isinstance(item, list):
            for nested in item:
                visit(nested, executable=executable)
        elif (
            executable
            and isinstance(item, str)
            and item.lstrip().startswith("palari ")
        ):
            commands.append(item)

    visit(value)
    return commands


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
            self.assertEqual(added["work_item"]["risk"], "R1")
            self.assertEqual(added["work_item"]["intensity"], "light")
            self.assertEqual(
                added["work_item"]["required_approval_count"],
                1,
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
            ) as runner:
                result = agent_advance(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )
            self.assertEqual(runner.call_count, 1)

            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            self.assertEqual(result["status"], "review-required", result)
            self.assertTrue(result["handoff"]["review_handoff"], result)
            self.assertIsNotNone(work)
            assert work is not None and work.current_attempt
            self.assertNotIn(work.status, {"completed", "closed", "done"})
            attempt = next(
                item for item in final.attempts if item.id == work.current_attempt
            )
            self.assertEqual(attempt.head_sha, candidate_head)
            self.assertEqual(
                attempt.changed_files,
                ["README.md", "REMOVE.md", "artifacts/created.txt"],
            )
            self.assertIsNone(read_claim(repo.workspace_file, work_id))
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
            self._advance_to_review(repo, work_id)
            self._record_accept_ready_review(repo, work_id)

            def commit_before_completion() -> None:
                (repo.root / "README.md").write_text(
                    "unreviewed concurrent candidate\n",
                    encoding="utf-8",
                )
                git(repo.root, "add", "--", "README.md")
                git(repo.root, "commit", "-qm", "inject concurrent candidate")

            with self.assertRaisesRegex(
                SimpleApprovalError,
                "approval pack is missing or stale",
            ):
                approve_work(
                    str(repo.workspace_file),
                    work_id,
                    "HUMAN-FOUNDER",
                    reason="approve exact reviewed maintainer work",
                    _before_apply=commit_before_completion,
                )

            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn(work.status, {"completed", "closed", "done"})
            self.assertFalse(
                any(
                    item.work_item_id == work_id
                    for item in final.human_decisions
                )
            )
            self.assertFalse(
                any(
                    item.work_item_id == work_id
                    for item in final.acceptance_records
                )
            )
            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            journal = verify_workspace_journal(repo.workspace_file)
            self.assertTrue(journal["ok"], journal)
            self.assertIsNone(journal["pending"])
            self.assertEqual(repo.status(), "")

    def test_legacy_empty_pack_selection_recovery_rechecks_source_cas(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)
            self._advance_to_review(repo, work_id)
            self._record_accept_ready_review(repo, work_id)
            store = load_store(repo.workspace_file)
            inbox = build_approval_inbox(
                Workspace.load(repo.workspace_file),
                store.data,
                selected_work_ids=[work_id],
            )
            pack = inbox["packs"][0]
            approval = inbox["approval_commands"][0]
            workspace_before = repo.workspace_file.read_bytes()

            def crash_after_prepare(stage: str) -> None:
                if stage == "after_prepare_fsync":
                    raise RuntimeError("injected crash after_prepare_fsync")

            with self.assertRaisesRegex(
                RuntimeError,
                "after_prepare_fsync",
            ):
                apply_pack_decision(
                    str(repo.workspace_file),
                    pack_digest=pack["pack_digest"],
                    presentation_digest=approval["presentation_digest"],
                    human_id="HUMAN-FOUNDER",
                    approve_eligible=True,
                    reason="test legacy empty member selection",
                    crash_hook=crash_after_prepare,
                )
            pending = verify_workspace_journal(repo.workspace_file)
            self.assertEqual(pending["status"], "pending-prepare", pending)

            (repo.root / "UNTRACKED.md").write_text(
                "unverified source drift\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                WorkspaceError,
                "Repository source changed after verification",
            ):
                apply_pack_decision(
                    str(repo.workspace_file),
                    pack_digest=pack["pack_digest"],
                    presentation_digest=approval["presentation_digest"],
                    human_id="HUMAN-FOUNDER",
                    approve_eligible=True,
                    reason="test legacy empty member selection",
                )

            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn(work.status, {"completed", "closed", "done"})
            self.assertFalse(
                any(
                    item.work_item_id == work_id
                    for item in final.human_decisions
                )
            )
            self.assertFalse(
                any(
                    item.work_item_id == work_id
                    for item in final.acceptance_records
                )
            )
            journal = verify_workspace_journal(repo.workspace_file)
            self.assertTrue(journal["ok"], journal)
            self.assertIsNone(journal["pending"])
            self.assertGreaterEqual(journal["aborted_transactions"], 1)
            self.assertEqual(repo.workspace_file.read_bytes(), workspace_before)

    def test_direct_completion_rechecks_untracked_source_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)
            self._advance_to_review(repo, work_id)
            self._record_accept_ready_review(repo, work_id)
            (repo.root / "UNTRACKED.md").write_text(
                "unverified source\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                SimpleApprovalError,
                "source changed after verification",
            ):
                approve_work(
                    str(repo.workspace_file),
                    work_id,
                    "HUMAN-FOUNDER",
                    reason="approve exact reviewed maintainer work",
                )

            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn(work.status, {"completed", "closed", "done"})
            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            journal = verify_workspace_journal(repo.workspace_file)
            self.assertTrue(journal["ok"], journal)
            self.assertIsNone(journal["pending"])

    def test_completion_rechecks_source_after_staging_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)
            self._advance_to_review(repo, work_id)
            self._record_accept_ready_review(repo, work_id)
            original_replace = store_module._atomic_replace_text
            injected = False

            def inject_after_completion_is_staged(
                data_path: Path,
                text: str,
                *,
                pre_replace_check: Callable[[], None] | None = None,
                publication_callback: Callable[[object], None] | None = None,
            ) -> None:
                nonlocal injected
                candidate = json.loads(text)
                candidate_work: dict[str, Any] = next(
                    (
                        item
                        for item in candidate.get("work_items", [])
                        if item.get("id") == work_id
                    ),
                    {},
                )
                if (
                    not injected
                    and candidate_work.get("status") == "completed"
                ):
                    injected = True
                    concurrent = repo.root / "CONCURRENT.md"
                    concurrent.write_text(
                        "unreviewed concurrent candidate\n",
                        encoding="utf-8",
                    )
                    git(repo.root, "add", "--", "CONCURRENT.md")
                    git(repo.root, "commit", "-qm", "inject after staging")
                original_replace(
                    data_path,
                    text,
                    pre_replace_check=pre_replace_check,
                    publication_callback=publication_callback,
                )

            with patch.object(
                store_module,
                "_atomic_replace_text",
                side_effect=inject_after_completion_is_staged,
            ):
                with self.assertRaisesRegex(
                    SimpleApprovalError,
                    "source changed after verification",
                ):
                    approve_work(
                        str(repo.workspace_file),
                        work_id,
                        "HUMAN-FOUNDER",
                        reason="approve exact reviewed maintainer work",
                    )

            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            journal = verify_workspace_journal(repo.workspace_file)
            self.assertTrue(injected)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn(work.status, {"completed", "closed", "done"})
            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            self.assertTrue(journal["ok"], journal)
            self.assertIsNone(journal["pending"])
            self.assertGreaterEqual(journal["aborted_transactions"], 1)
            self.assertEqual(repo.status(), "")

    def test_proof_reconciliation_stops_at_review_and_releases_claim(
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
            self.assertEqual(result["status"], "review-required", result)
            self.assertTrue(result["handoff"]["review_handoff"], result)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn(work.status, {"completed", "closed", "done"})
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

    def test_pending_commit_recovery_stops_at_review_and_releases_claim(
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
            self.assertEqual(result["status"], "review-required", result)
            self.assertTrue(result["handoff"]["review_handoff"], result)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn(work.status, {"completed", "closed", "done"})
            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            self.assertTrue(verify_workspace_journal(repo.workspace_file)["ok"])
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_review_handoff_retry_is_idempotent_after_claim_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)

            first = self._advance_to_review(repo, work_id)
            after_first = Workspace.load(repo.workspace_file)
            counts = (
                len(after_first.attempts),
                len(after_first.receipts),
                len(after_first.evidence_runs),
            )

            with patch.object(
                agent_advance_module,
                "run_or_reuse",
                side_effect=AssertionError("current proof reran verification"),
            ):
                second = agent_advance(
                    after_first,
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            resumed = Workspace.load(repo.workspace_file)
            self.assertEqual(first["status"], "review-required", first)
            self.assertEqual(second["status"], "review-required", second)
            self.assertFalse(second["would_mutate"], second)
            self.assertTrue(second["handoff"]["review_handoff"], second)
            self.assertEqual(
                counts,
                (
                    len(resumed.attempts),
                    len(resumed.receipts),
                    len(resumed.evidence_runs),
                ),
            )
            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_invalid_complete_proof_never_starts_or_records_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)
            self._advance_to_review(repo, work_id)
            evidence = Workspace.load(repo.workspace_file).evidence_runs[0]
            update_record(
                str(repo.workspace_file),
                "evidence",
                evidence.id,
                {
                    "commands": [
                        "bogus attestation NOT-RUN sha256:" + "0" * 64
                    ]
                },
                command="test invalidate complete proof",
                actor="PALARI-CLAUDE",
            )

            workspace = Workspace.load(repo.workspace_file)
            guide = build_review_guide(workspace, work_id)
            packet = build_agent_brief(
                workspace,
                work_id,
                "PALARI-REVIEWER",
                "review",
            )

            self.assertEqual(guide["review_record_commands"], [])
            self.assertTrue(guide["review_binding_errors"])
            review_actions = [
                command
                for command in executable_palari_commands(guide)
                if " agent start " in command or " review record " in command
            ]
            self.assertEqual(review_actions, [])
            self.assertEqual(packet["status"], "blocked", packet)
            self.assertIn(
                "REVIEW_PROOF_NOT_READY",
                {item["code"] for item in packet["blockers"]},
            )
            with self.assertRaisesRegex(
                WorkspaceError,
                "accept-ready review requires current exact verification proof",
            ):
                self._record_accept_ready_review(repo, work_id)

    def test_policy_invalid_proof_emits_no_review_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)
            self._advance_to_review(repo, work_id)
            update_record(
                str(repo.workspace_file),
                "work",
                work_id,
                {"allowed_actions": ["local_write", "push"]},
                command="test invalidate Maintainer policy",
                actor="HUMAN-FOUNDER",
            )

            workspace = Workspace.load(repo.workspace_file)
            guide = build_review_guide(workspace, work_id)
            packet = build_agent_brief(
                workspace,
                work_id,
                "PALARI-REVIEWER",
                "review",
            )

            self.assertEqual(guide["review_record_commands"], [])
            review_actions = [
                command
                for command in executable_palari_commands(guide)
                if " agent start " in command or " review record " in command
            ]
            self.assertEqual(review_actions, [])
            self.assertTrue(
                any(
                    "push" in error
                    for error in guide["review_binding_errors"]
                )
            )
            self.assertEqual(packet["status"], "blocked", packet)
            self.assertIn(
                "MAINTAINER_PROFILE_CAPABILITY_DENIED",
                {item["code"] for item in packet["blockers"]},
            )

    def test_invalid_complete_proof_cannot_publish_human_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            work_id = self._claim_work(repo, commit_candidate=True)
            self._advance_to_review(repo, work_id)
            self._record_accept_ready_review(repo, work_id)
            workspace = Workspace.load(repo.workspace_file)
            work = workspace.work_item(work_id)
            self.assertIsNotNone(work)
            assert work is not None and work.current_attempt
            attempt = next(
                item
                for item in workspace.attempts
                if item.id == work.current_attempt
            )
            evidence = next(
                item
                for item in workspace.evidence_runs
                if item.attempt_id == attempt.id
            )
            review = next(
                item
                for item in workspace.review_verdicts
                if item.work_item_id == work_id
            )
            reviewed_head = attempt.head_sha or attempt.commits[-1]
            store = load_store(repo.workspace_file)
            evidence_record = next(
                item
                for item in store.data["evidence_runs"]
                if item["id"] == evidence.id
            )
            evidence_record["commands"] = [
                "bogus attestation NOT-RUN sha256:" + "0" * 64
            ]
            stamped_evidence = stamp_evidence_record(
                evidence_record,
                repo.root,
                attempts=store.data["attempts"],
                governance_workspace_path=store.data_path,
            )
            evidence_record.clear()
            evidence_record.update(stamped_evidence)
            review_record = next(
                item
                for item in store.data["review_verdicts"]
                if item["id"] == review.id
            )
            review_record["evidence_manifest_hash"] = evidence_record[
                "manifest_hash"
            ]
            review_record["proof_hash"] = review_proof_hash(review_record)
            write_store(
                store,
                metadata=MutationMetadata(
                    command="test import structurally bound legacy proof",
                    actor="PALARI-CLAUDE",
                    action="imported-legacy-proof",
                    timestamp=utc_timestamp(),
                    objects=(
                        {
                            "type": "evidence",
                            "collection": "evidence_runs",
                            "id": evidence.id,
                        },
                        {
                            "type": "review",
                            "collection": "review_verdicts",
                            "id": review.id,
                        },
                    ),
                ),
            )
            before = repo.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "Maintainer acceptance requires current complete exact proof",
            ):
                create_human_decision(
                    str(repo.workspace_file),
                    {
                        "id": "HUMAN-DECISION-INVALID-PROOF",
                        "work_item_id": work_id,
                        "human_id": "HUMAN-FOUNDER",
                        "reviewed_head": reviewed_head,
                        "decision": "accepted",
                        "status": "accepted",
                        "acceptance_mode": "human",
                        "evidence_reference": evidence.id,
                        "review_reference": review.id,
                    },
                    command="test invalid direct human decision",
                    actor="HUMAN-FOUNDER",
                    automatic_convergence=False,
                )
            self.assertEqual(repo.safety_snapshot(), before)

            with self.assertRaisesRegex(
                WorkspaceError,
                "Maintainer acceptance requires current complete exact proof",
            ):
                accept_work(
                    str(repo.workspace_file),
                    work_id,
                    "HUMAN-FOUNDER",
                    reviewed_head,
                    command="test invalid work acceptance",
                )
            self.assertEqual(repo.safety_snapshot(), before)
            final = Workspace.load(repo.workspace_file)
            self.assertFalse(
                any(
                    item.work_item_id == work_id
                    for item in final.human_decisions
                )
            )
            self.assertFalse(
                any(
                    item.work_item_id == work_id
                    for item in final.acceptance_records
                )
            )

    def _advance_to_review(self, repo: Any, work_id: str) -> dict[str, Any]:
        with patch.object(
            agent_advance_module,
            "run_or_reuse",
            side_effect=self._passing_attestation,
        ) as runner:
            result = agent_advance(
                Workspace.load(repo.workspace_file),
                repo.workspace_file,
                work_id,
                "PALARI-CLAUDE",
            )
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(result["status"], "review-required", result)
        self.assertTrue(result["handoff"]["review_handoff"], result)
        self.assertIsNone(read_claim(repo.workspace_file, work_id))
        return result

    def _record_accept_ready_review(self, repo: Any, work_id: str) -> None:
        workspace = Workspace.load(repo.workspace_file)
        work = workspace.work_item(work_id)
        self.assertIsNotNone(work)
        assert work is not None and work.current_attempt
        attempt = next(
            item for item in workspace.attempts if item.id == work.current_attempt
        )
        create_record(
            str(repo.workspace_file),
            "review",
            {
                "id": "REVIEW-MAINTAINER-PROOF",
                "work_item_id": work_id,
                "reviewed_head": attempt.head_sha or attempt.commits[-1],
                "reviewer": "PALARI-REVIEWER",
                "verdict": "accept-ready",
                "findings": [],
                "checks_inspected": ["exact deterministic advance proof"],
                "residual_risks": [],
            },
            command="test independent maintainer review",
            actor="PALARI-REVIEWER",
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
        self.assertEqual(added["work_item"]["risk"], "R1")
        self.assertEqual(added["work_item"]["intensity"], "light")
        self.assertEqual(added["work_item"]["required_approval_count"], 1)
        self.assertEqual(
            added["profile_adjustments"],
            ["required human approvals elevated to one"],
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
        if profile.id != "complete" or profile.argv != ("./scripts/verify.sh",):
            raise AssertionError(
                f"unexpected Maintainer verification profile: {profile!r}"
            )
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
