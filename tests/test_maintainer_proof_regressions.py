from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_advance import _git_commit_timestamp, agent_advance
from palari_company_os.agent_runtime import start_agent
from palari_company_os.authoring import (
    complete_work,
    create_record,
    reconcile_agent_proof,
    update_record,
)
from palari_company_os.evidence_manifest import (
    git_artifact_state,
    stamp_evidence_record,
    verify_evidence,
)
from palari_company_os import governance_convergence as convergence_module
from palari_company_os.governance_convergence import converge_work_item
from palari_company_os.governance_journal import (
    checkpoint_workspace_journal,
    workspace_digest,
)
from palari_company_os.store import load_store, write_store
from palari_company_os.verification_attestations import (
    expected_verification_commands,
)
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.workspace_fixture import write_current_agent_workspace


agent_advance_module = importlib.import_module("palari_company_os.agent_advance")


class MaintainerProofRegressionTests(unittest.TestCase):
    def test_already_current_bogus_verification_commands_cannot_complete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ordinary-source"
            root.mkdir()
            work_id = self._seed_bogus_current_proof(root)

            convergence = converge_work_item(
                root,
                work_id,
                actor="PALARI-STEWARD",
            )

            self.assertEqual(convergence["status"], "blocked", convergence)
            self.assertEqual(convergence["code"], "CURRENT_PROOF_INVALID")
            self.assertIn("commands", convergence["message"])
            converged_work = Workspace.load(root).work_item(work_id)
            self.assertIsNotNone(converged_work)
            assert converged_work is not None
            self.assertNotIn(
                converged_work.status,
                {"completed", "closed", "done"},
            )

            with self.assertRaisesRegex(
                WorkspaceError,
                "evidence commands do not match",
            ):
                complete_work(
                    str(root),
                    work_id,
                    actor="PALARI-STEWARD",
                )

            with patch.object(
                agent_advance_module,
                "run_or_reuse",
                side_effect=AssertionError(
                    "already-current invalid proof must not rerun or replace checks"
                ),
            ):
                advanced = agent_advance(
                    Workspace.load(root),
                    root,
                    work_id,
                    "PALARI-STEWARD",
                )

            self.assertEqual(advanced["status"], "blocked", advanced)
            self.assertEqual(
                advanced["blockers"][0]["code"],
                "CURRENT_PROOF_INVALID",
            )
            self.assertIn("commands", advanced["blockers"][0]["message"])
            final_work = Workspace.load(root).work_item(work_id)
            self.assertIsNotNone(final_work)
            assert final_work is not None
            self.assertNotIn(final_work.status, {"completed", "closed", "done"})

    def test_untracked_source_after_proof_blocks_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ordinary-source"
            root.mkdir()
            work_id = self._seed_current_proof(root, bogus=False)
            (root / "UNTRACKED.md").write_text(
                "unverified source\n",
                encoding="utf-8",
            )

            result = converge_work_item(
                root,
                work_id,
                actor="PALARI-STEWARD",
            )

            self.assertEqual(result["status"], "blocked", result)
            self.assertEqual(result["code"], "CURRENT_PROOF_INVALID")
            self.assertIn("UNTRACKED.md", result["message"])
            work = Workspace.load(root).work_item(work_id)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn(work.status, {"completed", "closed", "done"})

    def test_workspace_swap_between_observe_and_apply_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ordinary-source"
            root.mkdir()
            work_id = self._seed_current_proof(root, bogus=False)
            original_observe = convergence_module._observe_work
            injected = False

            def mutate_after_observe(
                path: Path,
                observed_work_id: str,
                actor: str,
            ) -> object:
                nonlocal injected
                observation = original_observe(path, observed_work_id, actor)
                if not injected and observation.action == "complete-work":
                    injected = True
                    update_record(
                        str(root),
                        "goal",
                        "GOAL-REPO-0001",
                        {"title": "Concurrent governed state"},
                        command="test convergence state swap",
                        actor="PALARI-STEWARD",
                    )
                return observation

            with patch.object(
                convergence_module,
                "_observe_work",
                side_effect=mutate_after_observe,
            ):
                result = converge_work_item(
                    root,
                    work_id,
                    actor="PALARI-STEWARD",
                )

            self.assertTrue(injected)
            self.assertEqual(result["status"], "blocked", result)
            self.assertEqual(result["code"], "TRANSITION_REJECTED")
            self.assertIn("governed state changed", result["message"])
            final = Workspace.load(root)
            work = final.work_item(work_id)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertNotIn(work.status, {"completed", "closed", "done"})
            self.assertEqual(
                final.goal("GOAL-REPO-0001").title,
                "Concurrent governed state",
            )

    def test_latest_evidence_uses_timestamp_not_physical_list_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ordinary-source"
            root.mkdir()
            work_id = self._seed_current_proof(root, bogus=False)
            store = load_store(root)
            current = dict(store.data["evidence_runs"][0])
            older = stamp_evidence_record(
                {
                    **current,
                    "id": "EVIDENCE-OLDER-PHYSICALLY-LAST",
                    "commands": [
                        "bogus attestation NOT-RUN sha256:" + "0" * 64
                    ],
                    "timestamp": "2000-01-01T00:00:00Z",
                },
                root,
                attempts=store.data["attempts"],
                governance_workspace_path=store.data_path,
            )
            store.data["evidence_runs"].append(older)
            write_store(store)
            self.assertEqual(
                Workspace.load(root).evidence_runs[-1].id,
                older["id"],
            )

            result = converge_work_item(
                root,
                work_id,
                actor="PALARI-STEWARD",
            )

            self.assertEqual(result["status"], "completed", result)
            work = Workspace.load(root).work_item(work_id)
            self.assertIsNotNone(work)
            assert work is not None
            self.assertEqual(work.status, "completed")

    def _seed_bogus_current_proof(self, root: Path) -> str:
        return self._seed_current_proof(root, bogus=True)

    def _seed_current_proof(self, root: Path, *, bogus: bool) -> str:
        workspace_path = root / "workspace.json"
        write_current_agent_workspace(workspace_path)
        shutil.rmtree(root / ".palari", ignore_errors=True)
        checkpoint = checkpoint_workspace_journal(root, "PALARI-STEWARD")
        self.assertTrue(checkpoint["ok"], checkpoint)
        work_id = "WORK-BOGUS-CURRENT-PROOF"
        create_record(
            str(root),
            "work",
            {
                "id": work_id,
                "title": "Reject an already-current fabricated proof",
                "palari": "PALARI-STEWARD",
                "goal": "GOAL-REPO-0001",
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R1",
                "intensity": "light",
                "required_approval_count": 0,
                "scope": "Change one bounded local artifact.",
                "acceptance_target": "Only exact required verification may complete.",
                "status": "active",
                "allowed_resources": ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "allowed_actions": ["local_write"],
                "output_targets": ["README.md"],
                "forbidden_actions": ["deploy"],
                "verification_expectations": ["affected verification"],
            },
            command="test declare proof regression",
            actor="PALARI-STEWARD",
        )
        (root / "README.md").write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "governed baseline"],
            check=True,
        )
        start_agent(
            Workspace.load(root),
            root,
            work_id,
            "PALARI-STEWARD",
            "execute",
        )
        (root / "README.md").write_text("after\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(root), "add", "--", "README.md"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "bounded candidate"],
            check=True,
        )
        head_sha = self._git(root, "rev-parse", "HEAD")
        base_sha = self._git(root, "rev-parse", "HEAD^")
        attempt_id = f"ATTEMPT-ADVANCE-{work_id}-{head_sha[:12].upper()}"
        receipt_id = f"RECEIPT-ADVANCE-{work_id}-{head_sha[:12].upper()}"
        evidence_id = f"EVIDENCE-ADVANCE-{work_id}-{head_sha[:12].upper()}"
        artifact_state = git_artifact_state(
            root,
            ["README.md"],
            governance_workspace_path=workspace_path,
        )
        expected_commands = expected_verification_commands(
            "R1",
            ["README.md"],
            base_sha=base_sha,
            head_sha=head_sha,
        )
        reconcile_agent_proof(
            str(root),
            work_id=work_id,
            palari_id="PALARI-STEWARD",
            attempt_record={
                "id": attempt_id,
                "work_item_id": work_id,
                "actor": "PALARI-STEWARD",
                "status": "active",
                "workspace_path": str(root),
                "base_sha": base_sha,
                "allowed_paths": ["README.md"],
            },
            receipt_record={
                "id": receipt_id,
                "work_item_id": work_id,
                "attempt_id": attempt_id,
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
                "id": evidence_id,
                "work_item_id": work_id,
                "attempt_id": attempt_id,
                "head_sha": head_sha,
                "status": "passed",
                "base_ref": base_sha,
                "commands": (
                    ["bogus attestation NOT-RUN sha256:" + "0" * 64]
                    if bogus
                    else expected_commands
                ),
                "artifacts": ["README.md"],
                "artifact_hashes": artifact_state["artifact_hashes"],
                "summary": (
                    f"{len(expected_commands)} exact-state verification profile(s) passed."
                ),
                "freshness": "exact-head",
            },
            head_sha=head_sha,
            changed_files=["README.md"],
            output_targets=["README.md"],
            proof_timestamp=_git_commit_timestamp(
                {"git_root": str(root), "head_sha": head_sha}
            ),
            expected_workspace_digest=workspace_digest(load_store(root).data),
            expected_git_head=head_sha,
            expected_artifact_hashes=artifact_state["artifact_hashes"],
        )
        workspace = Workspace.load(root)
        evidence_report = verify_evidence(
            workspace,
            evidence_id,
            require_output_coverage=True,
        )
        self.assertTrue(evidence_report["ok"], evidence_report)
        return work_id

    @staticmethod
    def _git(root: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()


if __name__ == "__main__":
    unittest.main()
