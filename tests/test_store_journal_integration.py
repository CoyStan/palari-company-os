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
from palari_company_os.store import WorkspaceStore, load_store, write_store
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


if __name__ == "__main__":
    unittest.main()
