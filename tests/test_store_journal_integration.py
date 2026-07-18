from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.governance_journal import (
    checkpoint_workspace_journal,
    journal_file_path,
    legacy_journal_file_path,
    v2_journal_file_path,
    verify_workspace_journal,
)
from palari_company_os.store import (
    WorkspaceStore,
    _assert_retired_work_immutable,
    load_store,
    write_store,
)
from palari_company_os.workspace import WorkspaceError


FIXTURE = REPO_ROOT / "tests" / "fixtures" / "workspaces" / "valid-workspace.json"


class StoreJournalIntegrationTests(unittest.TestCase):
    def test_new_workspace_starts_complete_journal_and_mutations_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "new" / "workspace.json"
            data = json.loads(FIXTURE.read_text(encoding="utf-8"))

            write_store(WorkspaceStore(data_path=data_path, data=data))
            first = verify_workspace_journal(data_path)
            store = load_store(data_path)
            store.data["name"] = "Journal mutation"
            write_store(store)
            second = verify_workspace_journal(data_path)

        self.assertTrue(first["ok"])
        self.assertEqual(first["journal_schema_version"], "palari.governance-journal.v1")
        self.assertEqual(first["continuity"]["initial_coverage"], "complete")
        self.assertTrue(second["ok"])
        self.assertEqual(second["committed_transactions"], 2)
        self.assertEqual(second["replay_workspace_digest"], second["current_workspace_digest"])

    def test_legacy_workspace_remains_unjournaled_until_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            shutil.copy(FIXTURE, data_path)
            store = load_store(data_path)
            store.data["name"] = "Legacy compatible"
            write_store(store)

            self.assertFalse(journal_file_path(data_path).exists())
            checkpoint = checkpoint_workspace_journal(data_path, "HUMAN-OPERATOR")
            self.assertEqual(
                journal_file_path(data_path), legacy_journal_file_path(data_path)
            )
            self.assertFalse(v2_journal_file_path(data_path).exists())

        self.assertTrue(checkpoint["ok"])
        self.assertEqual(checkpoint["continuity"]["initial_coverage"], "from-checkpoint")
        self.assertEqual(checkpoint["journal_schema_version"], "palari.governance-journal.v1")

    def test_manual_divergence_blocks_next_journaled_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            shutil.copy(FIXTURE, data_path)
            checkpoint_workspace_journal(data_path, "HUMAN-OPERATOR")
            raw = json.loads(data_path.read_text(encoding="utf-8"))
            raw["name"] = "Manual divergence"
            data_path.write_text(json.dumps(raw), encoding="utf-8")
            store = load_store(data_path)
            store.data["name"] = "Attempted silent continuation"

            with self.assertRaisesRegex(
                WorkspaceError, "JOURNAL_WORKSPACE_DIVERGENCE"
            ):
                write_store(store)

    def test_retired_work_preserves_prior_proof_but_rejects_later_lifecycle_changes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            data = json.loads(FIXTURE.read_text(encoding="utf-8"))
            write_store(WorkspaceStore(data_path=data_path, data=data))
            retirement = load_store(data_path)
            retirement.data["work_items"][0].update(
                {
                    "status": "abandoned",
                    "terminal_reason": "The objective is intentionally parked.",
                }
            )
            write_store(retirement)
            original = data_path.read_bytes()

            proof_change = load_store(data_path)
            proof_change.data["evidence_runs"][0]["summary"] = "late rewrite"
            with self.assertRaisesRegex(
                WorkspaceError,
                "retired work WORK-1 is audit-only; evidence_runs cannot change",
            ):
                write_store(proof_change)
            self.assertEqual(data_path.read_bytes(), original)

            authority_change = load_store(data_path)
            authority_change.data.setdefault("acceptance_records", []).append(
                {"id": "ACCEPTANCE-LATE", "work_item_id": "WORK-1"}
            )
            with self.assertRaisesRegex(
                WorkspaceError,
                "retired work WORK-1 is audit-only; acceptance_records cannot change",
            ):
                write_store(authority_change)
            self.assertEqual(data_path.read_bytes(), original)

            contract_change = load_store(data_path)
            contract_change.data["work_items"][0]["terminal_reason"] = "rewritten"
            with self.assertRaisesRegex(
                WorkspaceError,
                "retired work WORK-1 is immutable",
            ):
                write_store(contract_change)
            self.assertEqual(data_path.read_bytes(), original)

            unrelated = load_store(data_path)
            unrelated.data["name"] = "Unrelated workspace metadata update"
            write_store(unrelated)
            self.assertEqual(
                load_store(data_path).data["name"],
                "Unrelated workspace metadata update",
            )

    def test_retirement_cannot_bundle_new_authority_into_the_same_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            data = json.loads(FIXTURE.read_text(encoding="utf-8"))
            write_store(WorkspaceStore(data_path=data_path, data=data))
            retirement = load_store(data_path)
            retirement.data["work_items"][0].update(
                {
                    "status": "abandoned",
                    "terminal_reason": "Parked without new authority.",
                }
            )
            retirement.data["human_decisions"].append(
                {"id": "HUMAN-DECISION-LATE", "work_item_id": "WORK-1"}
            )

            with self.assertRaisesRegex(
                WorkspaceError,
                "retired work WORK-1 is audit-only; human_decisions cannot change",
            ):
                write_store(retirement)

            persisted = load_store(data_path).data
            self.assertEqual(persisted["work_items"][0]["status"], "in-review")
            self.assertEqual(persisted["human_decisions"], [])

    def test_retired_work_rejects_later_changes_to_its_adopted_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            data = json.loads(FIXTURE.read_text(encoding="utf-8"))
            data["proposals"] = [
                {
                    "id": "PROPOSAL-WORK-1",
                    "title": data["work_items"][0]["title"],
                    "goal": data["work_items"][0]["goal"],
                    "palari": data["work_items"][0]["palari"],
                    "status": "adopted",
                    "linked_work": "WORK-1",
                }
            ]
            write_store(WorkspaceStore(data_path=data_path, data=data))
            retirement = load_store(data_path)
            retirement.data["work_items"][0].update(
                {
                    "status": "abandoned",
                    "terminal_reason": "The adopted objective is parked.",
                }
            )
            write_store(retirement)

            proposal_change = load_store(data_path)
            proposal_change.data["proposals"][0]["reason"] = "late rewrite"
            with self.assertRaisesRegex(
                WorkspaceError,
                "retired work WORK-1 is audit-only; proposals cannot change",
            ):
                write_store(proposal_change)

    def test_successful_work_cannot_be_reclassified_as_retired_in_one_write(self) -> None:
        before = {
            "work_items": [{"id": "WORK-DONE", "status": "completed"}],
        }
        after = {
            "work_items": [
                {
                    "id": "WORK-DONE",
                    "status": "abandoned",
                    "terminal_reason": "rewrite",
                }
            ],
        }

        with self.assertRaisesRegex(
            WorkspaceError,
            "successfully completed work WORK-DONE cannot be relabeled",
        ):
            _assert_retired_work_immutable(before, after)


if __name__ == "__main__":
    unittest.main()
