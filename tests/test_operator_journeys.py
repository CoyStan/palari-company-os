from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_parking import park_agent
from palari_company_os.agent_runtime import read_claim, start_agent
from palari_company_os.cli_output_agent import print_agent_park
from palari_company_os.governance_journal import (
    checkpoint_workspace_journal,
    journal_file_path,
    verify_workspace_journal,
)
from palari_company_os.store import load_store, write_store
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.workspace_fixture import write_current_agent_workspace


WORK_ID = "WORK-PARK"
PALARI_ID = "PALARI-STEWARD"
OTHER_PALARI_ID = "PALARI-ARCHITECT"
ALLOWED_PATH = "README.md"
REASON = "A product decision is required before this work can continue."
NEXT_ACTION = "Ask the owner to choose the final wording."
PROOF_COLLECTIONS = (
    "receipts",
    "evidence_runs",
    "review_verdicts",
    "human_decisions",
    "acceptance_records",
    "outcomes",
)


class OperatorJourneyTests(unittest.TestCase):
    """The interruption journey that is not covered by the CLI golden path."""

    def test_park_records_one_blocked_attempt_releases_and_creates_no_proof(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            started = start_agent(
                Workspace.load(workspace_file), workspace_file, WORK_ID, PALARI_ID
            )
            claimed_packet = started["start"]["claim"]
            (root / ALLOWED_PATH).write_text("unfinished bounded edit\n", encoding="utf-8")
            (root / "outside-scope.txt").write_text(
                "must remain visible while parked\n",
                encoding="utf-8",
            )
            before = json.loads(workspace_file.read_text(encoding="utf-8"))
            proof_counts = {
                key: len(before.get(key, [])) for key in PROOF_COLLECTIONS
            }

            result = park_agent(
                workspace_file,
                WORK_ID,
                PALARI_ID,
                reason=REASON,
                next_action=NEXT_ACTION,
            )

            self.assertEqual(result["schema_version"], "palari.agent_parking.v1")
            self.assertEqual(result["status"], "parked")
            self.assertTrue(result["claim_released"])
            self.assertFalse(result["resumed"])
            self.assertEqual(result["reason"], REASON)
            self.assertEqual(result["next_action"], NEXT_ACTION)
            binding = result["packet_head_digest_changes"]
            self.assertEqual(binding["packet"]["packet_id"], claimed_packet["packet_id"])
            self.assertEqual(
                binding["packet"]["context_hash"], claimed_packet["context_hash"]
            )
            self.assertTrue(binding["packet"]["packet_digest"].startswith("sha256:"))
            self.assertIn(ALLOWED_PATH, binding["observation"]["inside_write_boundary"])
            self.assertIn(
                "outside-scope.txt",
                binding["observation"]["outside_write_boundary"],
            )

            after = json.loads(workspace_file.read_text(encoding="utf-8"))
            work = next(item for item in after["work_items"] if item["id"] == WORK_ID)
            attempt = next(
                item for item in after["attempts"] if item["id"] == result["attempt_id"]
            )
            self.assertEqual(work["status"], "blocked")
            self.assertEqual(work["current_attempt"], attempt["id"])
            self.assertEqual(attempt["status"], "blocked")
            self.assertEqual(attempt["changed_files"], [ALLOWED_PATH])
            parking = json.loads(attempt["result"])
            self.assertEqual(parking["schema_version"], "palari.agent_parking_record.v1")
            self.assertEqual(
                parking["authority_non_claims"],
                [
                    "no-receipt",
                    "no-evidence",
                    "no-review",
                    "no-human-decision",
                    "no-acceptance",
                    "no-outcome",
                    "no-convergence",
                ],
            )
            self.assertIsNone(read_claim(workspace_file, WORK_ID))
            self.assertEqual(
                {key: len(after.get(key, [])) for key in PROOF_COLLECTIONS},
                proof_counts,
            )
            journal = verify_workspace_journal(workspace_file)
            self.assertTrue(journal["chain_valid"])
            self.assertEqual(
                journal["current_workspace_digest"],
                binding["workspace_digest_after"],
            )

            output = io.StringIO()
            with redirect_stdout(output):
                print_agent_park(result, False)
            self.assertEqual(
                output.getvalue().splitlines(),
                [
                    f"Work: {WORK_ID} [blocked]",
                    f"Owner: {PALARI_ID}",
                    f"Reason: {REASON}",
                    f"Next: {NEXT_ACTION}",
                    "Claim released: yes",
                ],
            )
            self.assertNotIn("sha256:", output.getvalue())

    def test_retry_after_durable_write_releases_once_without_rewriting_history(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            start_agent(
                Workspace.load(workspace_file), workspace_file, WORK_ID, PALARI_ID
            )
            (root / ALLOWED_PATH).write_text("unfinished bounded edit\n", encoding="utf-8")

            def interrupt(_payload: dict[str, object]) -> None:
                raise RuntimeError("simulated interruption before claim release")

            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                    _after_persist=interrupt,
                )

            persisted = json.loads(workspace_file.read_text(encoding="utf-8"))
            self.assertEqual(self._parking_attempt_count(persisted), 1)
            self.assertIsNotNone(read_claim(workspace_file, WORK_ID))
            journal_path = journal_file_path(workspace_file)
            journal_before_retry = journal_path.read_bytes()

            result = park_agent(
                workspace_file,
                WORK_ID,
                PALARI_ID,
                reason=REASON,
                next_action=NEXT_ACTION,
            )

            self.assertTrue(result["resumed"])
            self.assertTrue(result["claim_released"])
            self.assertIsNone(read_claim(workspace_file, WORK_ID))
            self.assertEqual(journal_path.read_bytes(), journal_before_retry)
            after = json.loads(workspace_file.read_text(encoding="utf-8"))
            self.assertEqual(self._parking_attempt_count(after), 1)

    def test_parking_requires_an_owned_claim_and_current_journal(self) -> None:
        with self.git_workspace() as workspace_file:
            workspace = Workspace.load(workspace_file)
            start_agent(workspace, workspace_file, WORK_ID, PALARI_ID)
            workspace_before = workspace_file.read_bytes()

            with self.assertRaisesRegex(
                WorkspaceError, f"claim belongs to {PALARI_ID}"
            ):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    OTHER_PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                )
            self.assertEqual(workspace_file.read_bytes(), workspace_before)
            self.assertIsNotNone(read_claim(workspace_file, WORK_ID))

        with self.git_workspace() as workspace_file:
            with self.assertRaisesRegex(WorkspaceError, "no claim exists"):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                )
            self.assertEqual(Workspace.load(workspace_file).work_item(WORK_ID).status, "active")

        with self.git_workspace(journal=False) as workspace_file:
            start_agent(
                Workspace.load(workspace_file), workspace_file, WORK_ID, PALARI_ID
            )
            before = workspace_file.read_bytes()
            with self.assertRaisesRegex(
                WorkspaceError,
                "history --checkpoint.*Activate journal",
            ):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                )
            self.assertEqual(workspace_file.read_bytes(), before)
            self.assertIsNotNone(read_claim(workspace_file, WORK_ID))

    @staticmethod
    def _parking_attempt_count(data: dict[str, object]) -> int:
        attempts = data.get("attempts")
        assert isinstance(attempts, list)
        return len(
            [
                item
                for item in attempts
                if isinstance(item, dict)
                and str(item.get("id") or "").startswith("ATTEMPT-PARK-")
            ]
        )

    @contextmanager
    def git_workspace(self, *, journal: bool = True) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            root.mkdir()
            workspace_file = root / "workspace.json"
            write_current_agent_workspace(workspace_file)
            store = load_store(workspace_file)
            store.data["work_items"] = [
                {
                    "id": WORK_ID,
                    "title": "Park one interrupted bounded change",
                    "goal": "GOAL-REPO-0001",
                    "palari": PALARI_ID,
                    "risk": "R2",
                    "intensity": "standard",
                    "required_approval_count": 0,
                    "scope": "Modify only the declared artifact.",
                    "acceptance_target": "The interruption is durable and auditable.",
                    "status": "active",
                    "allowed_resources": [ALLOWED_PATH],
                    "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                    "output_targets": [ALLOWED_PATH],
                    "path_intents": [{"path": ALLOWED_PATH, "intent": "modify"}],
                    "forbidden_actions": ["deploy"],
                    "verification_expectations": ["focused parking journey passes"],
                }
            ]
            for palari in store.data["palaris"]:
                if palari["id"] == PALARI_ID:
                    palari["active_work"] = [WORK_ID]
            write_store(store)
            shutil.rmtree(root / ".palari", ignore_errors=True)
            (root / ALLOWED_PATH).write_text("initial copy\n", encoding="utf-8")

            self.run_git(root, "init", "-q")
            self.run_git(root, "config", "user.email", "test@example.invalid")
            self.run_git(root, "config", "user.name", "Test")
            self.run_git(root, "add", "-A")
            self.run_git(root, "commit", "-qm", "current fixture")
            if journal:
                checkpoint_workspace_journal(
                    workspace_file,
                    PALARI_ID,
                    reason="Activate current journal for the parking journey.",
                )
            yield workspace_file

    @staticmethod
    def run_git(root: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


if __name__ == "__main__":
    unittest.main()
