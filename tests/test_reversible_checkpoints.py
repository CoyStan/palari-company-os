from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.checkpoints import (
    _external_effects_after,
    list_checkpoints,
    restore_checkpoint,
)
from palari_company_os.governance_journal import (
    committed_journal_states,
    verify_journal,
)
from palari_company_os.store import WorkspaceStore, load_store, write_store
from palari_company_os.workspace import WorkspaceError


FIXTURE = REPO_ROOT / "tests" / "fixtures" / "workspaces" / "valid-workspace.json"


class InjectedCrash(RuntimeError):
    pass


class ReversibleCheckpointTests(unittest.TestCase):
    def test_history_cli_lists_and_restores_exact_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_chain(Path(directory))
            listed = run_json(
                "--workspace",
                str(data_path),
                "history",
                "--checkpoints",
                "--json",
            )
            restored = run_json(
                "--workspace",
                str(data_path),
                "history",
                "--restore",
                listed["checkpoints"][0]["checkpoint_digest"],
                "--actor",
                "HUMAN-PRODUCT",
                "--reason",
                "CLI restoration test.",
                "--json",
            )

        self.assertEqual(listed["schema_version"], "palari.checkpoints.v1")
        self.assertEqual(restored["status"], "restored")
        self.assertTrue(restored["history_preserved"])

    def test_restoration_reproduces_exact_projection_and_appends_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_chain(Path(directory))
            before = committed_journal_states(data_path)
            target = before[1]
            result = restore_checkpoint(
                str(data_path),
                target["checkpoint_digest"],
                actor="HUMAN-PRODUCT",
                reason="Return to the reviewed S1 projection.",
            )
            final = load_store(data_path)
            after = committed_journal_states(data_path)
            report = verify_journal(final.data_path, final.data)

        self.assertEqual(final.data, target["projection"])
        self.assertEqual(result["status"], "restored")
        self.assertEqual(result["restoration_class"], "reversible-local")
        self.assertTrue(result["history_preserved"])
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(after[-1]["event_kind"], "restoration")
        self.assertEqual(after[-1]["checkpoint_digest"], target["checkpoint_digest"])
        self.assertTrue(report["chain_valid"])
        self.assertIsNone(report["pending"])

    def test_repeated_restoration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_chain(Path(directory))
            target = committed_journal_states(data_path)[0]["checkpoint_digest"]
            first = restore_checkpoint(
                str(data_path),
                target,
                actor="HUMAN-PRODUCT",
                reason="Restore the initial governed state.",
            )
            count = len(committed_journal_states(data_path))
            second = restore_checkpoint(
                str(data_path),
                target,
                actor="HUMAN-PRODUCT",
                reason="Restore the initial governed state.",
            )
            final_count = len(committed_journal_states(data_path))

        self.assertEqual(first["status"], "restored")
        self.assertEqual(second["status"], "already-at-checkpoint")
        self.assertTrue(second["idempotent"])
        self.assertEqual(final_count, count)

    def test_crash_at_each_restoration_boundary_recovers_safely(self) -> None:
        for point in (
            "before_prepare_append",
            "after_prepare_fsync",
            "before_apply",
            "after_apply",
            "before_commit_append",
            "after_commit_fsync",
        ):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                data_path = make_chain(Path(directory))
                target = committed_journal_states(data_path)[0]["checkpoint_digest"]
                with self.assertRaisesRegex(InjectedCrash, point):
                    restore_checkpoint(
                        str(data_path),
                        target,
                        actor="HUMAN-PRODUCT",
                        reason="Restoration crash test.",
                        crash_hook=crash_at(point),
                    )
                result = restore_checkpoint(
                    str(data_path),
                    target,
                    actor="HUMAN-PRODUCT",
                    reason="Restoration crash test.",
                )
                final = load_store(data_path)
                report = verify_journal(final.data_path, final.data)

                self.assertIn(result["status"], {"restored", "already-at-checkpoint"})
                self.assertEqual(report["replay_workspace_digest"], target)
                self.assertTrue(report["chain_valid"])
                self.assertIsNone(report["pending"])

    def test_external_effects_are_never_described_as_rollback_safe(self) -> None:
        target = {"receipts": [], "integration_outbox": []}
        current = {
            "receipts": [
                {"id": "RECEIPT-EXT", "external_writes": ["email:sent-message"]}
            ],
            "integration_outbox": [{"id": "OUTBOX-1", "status": "sent"}],
        }

        effects = _external_effects_after(target, current)

        self.assertEqual(
            effects,
            ["outbox:OUTBOX-1:sent", "receipt:RECEIPT-EXT:email:sent-message"],
        )

    def test_existing_records_gaining_external_effects_are_detected(self) -> None:
        target = {
            "receipts": [{"id": "RECEIPT-EXT", "external_writes": []}],
            "integration_outbox": [{"id": "OUTBOX-1", "status": "queued"}],
        }
        current = {
            "receipts": [
                {"id": "RECEIPT-EXT", "external_writes": ["email:sent-message"]}
            ],
            "integration_outbox": [{"id": "OUTBOX-1", "status": "sent"}],
        }

        self.assertEqual(
            _external_effects_after(target, current),
            ["outbox:OUTBOX-1:sent", "receipt:RECEIPT-EXT:email:sent-message"],
        )

    def test_restoration_blocks_before_mutation_when_external_effects_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_chain(Path(directory))
            target = committed_journal_states(data_path)[0]["checkpoint_digest"]
            before = load_store(data_path).data
            before_count = len(committed_journal_states(data_path))

            with patch(
                "palari_company_os.checkpoints._external_effects_after",
                return_value=["outbox:OUTBOX-1:sent"],
            ), self.assertRaisesRegex(WorkspaceError, "restoration blocked"):
                restore_checkpoint(
                    str(data_path),
                    target,
                    actor="HUMAN-PRODUCT",
                    reason="Must not requeue a sent external action.",
                )

            after = load_store(data_path)
            after_count = len(committed_journal_states(data_path))

        self.assertEqual(after.data, before)
        self.assertEqual(after_count, before_count)

    def test_restore_requires_declared_human_reason_and_exact_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_chain(Path(directory))
            target = committed_journal_states(data_path)[0]["checkpoint_digest"]
            with self.assertRaisesRegex(WorkspaceError, "declared human"):
                restore_checkpoint(
                    str(data_path),
                    target,
                    actor="PALARI-SOFIA",
                    reason="Agent may not restore authority state.",
                )
            with self.assertRaisesRegex(WorkspaceError, "non-empty reason"):
                restore_checkpoint(
                    str(data_path),
                    target,
                    actor="HUMAN-PRODUCT",
                    reason="",
                )
            with self.assertRaisesRegex(WorkspaceError, "full sha256"):
                restore_checkpoint(
                    str(data_path),
                    "../S1",
                    actor="HUMAN-PRODUCT",
                    reason="Traversal must fail closed.",
                )

    def test_checkpoint_listing_exposes_content_addressed_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_chain(Path(directory))
            payload = list_checkpoints(str(data_path))

        self.assertEqual(payload["count"], 4)
        self.assertTrue(payload["semantics"]["content_addressed"])
        self.assertTrue(payload["semantics"]["append_only_history"])
        self.assertFalse(payload["semantics"]["external_effects_undoable"])


def make_chain(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    data_path = root / "workspace.json"
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    write_store(WorkspaceStore(data_path=data_path, data=raw))
    for name in ("S1", "S2", "S3"):
        store = load_store(data_path)
        store.data["name"] = name
        write_store(store)
    return data_path


def crash_at(target: str):
    def hook(point: str) -> None:
        if point == target:
            raise InjectedCrash(point)

    return hook


def run_json(*args: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-S", "-m", "palari_company_os", *args],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise AssertionError(payload)
    return payload


if __name__ == "__main__":
    unittest.main()
