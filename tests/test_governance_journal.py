from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.governance_journal import (
    JournalError,
    MutationMetadata,
    append_record_fsync,
    checkpoint_workspace_journal,
    journal_file_path,
    logical_changes,
    prepare_record,
    record_digest,
    recover_pending,
    recover_workspace_journal_if_current,
    transact,
    verify_journal,
    verify_workspace_journal,
    workspace_digest,
)
from palari_company_os.store import workspace_write_lock
from palari_company_os.workspace import WorkspaceError


TIMESTAMP = "2026-07-14T12:00:00Z"


class GovernanceJournalTests(unittest.TestCase):
    def test_initial_checkpoint_and_mutation_replay_exact_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "workspace.json"
            initial = workspace("Initial")
            first = run_change(
                data_path,
                before=None,
                after=initial,
                event_kind="checkpoint",
                coverage="complete",
            )
            updated = workspace("Updated")
            second = run_change(data_path, before=initial, after=updated)

            records = read_records(data_path)

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual([item["record_type"] for item in records], [
            "prepare",
            "commit",
            "prepare",
            "commit",
        ])
        self.assertEqual(records[1]["previous_record_digest"], records[0]["record_digest"])
        self.assertEqual(records[2]["previous_record_digest"], records[1]["record_digest"])
        self.assertEqual(records[3]["previous_record_digest"], records[2]["record_digest"])
        self.assertEqual(records[2]["logical_changes"], [{"op": "replace", "path": "/name"}])
        self.assertEqual(second["replay_workspace_digest"], workspace_digest(updated))
        self.assertEqual(second["committed_transactions"], 2)

    def test_transaction_id_excludes_timestamp_but_record_digest_does_not(self) -> None:
        projection = workspace("Deterministic")
        first = prepare_record(
            sequence=0,
            previous_record_digest=None,
            event_kind="checkpoint",
            coverage="complete",
            expected_before_workspace_digest=None,
            before_workspace_digest=None,
            after_projection=projection,
            metadata=metadata(timestamp="2026-07-14T12:00:00Z"),
        )
        second = prepare_record(
            sequence=0,
            previous_record_digest=None,
            event_kind="checkpoint",
            coverage="complete",
            expected_before_workspace_digest=None,
            before_workspace_digest=None,
            after_projection=projection,
            metadata=metadata(timestamp="2026-07-14T12:00:01Z"),
        )

        self.assertEqual(first["transaction_id"], second["transaction_id"])
        self.assertNotEqual(first["record_digest"], second["record_digest"])

    def test_every_committed_prefix_replays_to_its_recorded_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            initial = workspace("Initial")
            updated = workspace("Updated")
            run_change(
                data_path,
                before=None,
                after=initial,
                event_kind="checkpoint",
                coverage="complete",
            )
            run_change(data_path, before=initial, after=updated)
            records = read_records(data_path)

            write_records(data_path, records[:2])
            first_prefix = verify_journal(data_path, initial)
            write_records(data_path, records)
            second_prefix = verify_journal(data_path, updated)

        self.assertTrue(first_prefix["ok"])
        self.assertEqual(first_prefix["replay_workspace_digest"], workspace_digest(initial))
        self.assertTrue(second_prefix["ok"])
        self.assertEqual(second_prefix["replay_workspace_digest"], workspace_digest(updated))

    def test_logical_changes_are_sorted_and_escape_json_pointer(self) -> None:
        before = {"z": 1, "a/b": {"~key": "old"}, "removed": True}
        after = {"z": 2, "a/b": {"~key": "new"}, "added": False}

        self.assertEqual(logical_changes(before, after), [
            {"op": "replace", "path": "/a~1b/~0key"},
            {"op": "add", "path": "/added"},
            {"op": "remove", "path": "/removed"},
            {"op": "replace", "path": "/z"},
        ])

    def test_legacy_checkpoint_is_explicit_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "workspace.json"
            data_path.write_text(json.dumps(workspace("Legacy")), encoding="utf-8")

            first = checkpoint_workspace_journal(
                root,
                "PALARI-STEWARD",
                reason="Start coverage without claiming old history",
                timestamp=TIMESTAMP,
            )
            second = checkpoint_workspace_journal(root, "PALARI-STEWARD", timestamp=TIMESTAMP)

        self.assertTrue(first["ok"])
        self.assertTrue(first["enabled"])
        self.assertEqual(first["continuity"]["initial_coverage"], "from-checkpoint")
        self.assertEqual(second["record_count"], 2)

    def test_manual_edit_requires_visible_continuity_break(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "workspace.json"
            initial = workspace("Initial")
            run_change(
                data_path,
                before=None,
                after=initial,
                event_kind="checkpoint",
                coverage="complete",
            )
            changed = workspace("Manual")
            data_path.write_text(json.dumps(changed), encoding="utf-8")

            rejected = checkpoint_workspace_journal(
                root, "HUMAN-FOUNDER", timestamp=TIMESTAMP
            )
            self.assertFalse(rejected["ok"])
            self.assertEqual(rejected["errors"][0]["code"], "JOURNAL_WORKSPACE_DIVERGENCE")
            report = checkpoint_workspace_journal(
                root,
                "HUMAN-FOUNDER",
                acknowledge_break=True,
                reason="Acknowledged manual repair",
                timestamp=TIMESTAMP,
            )

        self.assertFalse(report["ok"])
        self.assertTrue(report["chain_valid"])
        self.assertTrue(report["writable"])
        self.assertEqual(report["status"], "valid-with-continuity-break")
        self.assertEqual(report["continuity"]["break_sequences"], [2])
        self.assertEqual(report["warnings"][0]["code"], "JOURNAL_CONTINUITY_BREAK")

    def test_changed_record_digest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            data = workspace("Original")
            run_change(
                data_path,
                before=None,
                after=data,
                event_kind="checkpoint",
                coverage="complete",
            )
            records = read_records(data_path)
            records[0]["after_projection"]["name"] = "Tampered"
            write_records(data_path, records)

            report = verify_journal(data_path, data)

        self.assertFalse(report["ok"])
        self.assertEqual(report["diagnostics"][0]["code"], "JOURNAL_RECORD_DIGEST_MISMATCH")

    def test_duplicate_json_key_and_unknown_field_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            journal_path = journal_file_path(data_path)
            journal_path.parent.mkdir(parents=True)
            journal_path.write_text('{"schema_version":"x","schema_version":"y"}\n', encoding="utf-8")
            duplicate = verify_journal(data_path, None)

            record = prepare_record(
                sequence=0,
                previous_record_digest=None,
                event_kind="checkpoint",
                coverage="complete",
                expected_before_workspace_digest=None,
                before_workspace_digest=None,
                after_projection=workspace("Strict"),
                metadata=metadata(),
            )
            record["unknown"] = True
            record["record_digest"] = record_digest(record)
            journal_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            unknown = verify_journal(data_path, None)

        self.assertEqual(duplicate["diagnostics"][0]["code"], "JOURNAL_DUPLICATE_KEY")
        self.assertEqual(unknown["diagnostics"][0]["code"], "JOURNAL_RECORD_FIELDS_INVALID")

    def test_truncated_line_and_committed_tail_truncation_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            initial = workspace("Initial")
            updated = workspace("Updated")
            run_change(
                data_path,
                before=None,
                after=initial,
                event_kind="checkpoint",
                coverage="complete",
            )
            run_change(data_path, before=initial, after=updated)
            journal_path = journal_file_path(data_path)
            complete = journal_path.read_bytes()
            journal_path.write_bytes(complete[:-1])
            partial = verify_journal(data_path, updated)

            records = [json.loads(line) for line in complete.decode().splitlines()]
            write_records(data_path, records[:-2])
            tail = verify_journal(data_path, updated)

        self.assertEqual(partial["diagnostics"][0]["code"], "JOURNAL_TRUNCATED_RECORD")
        self.assertEqual(tail["diagnostics"][0]["code"], "JOURNAL_WORKSPACE_DIVERGENCE")

    def test_reorder_and_duplicate_commit_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            data = workspace("Ordered")
            run_change(
                data_path,
                before=None,
                after=data,
                event_kind="checkpoint",
                coverage="complete",
            )
            original = read_records(data_path)
            write_records(data_path, list(reversed(original)))
            reordered = verify_journal(data_path, data)

            duplicate = dict(original[1])
            duplicate["sequence"] = 2
            duplicate["previous_record_digest"] = original[1]["record_digest"]
            duplicate["record_digest"] = record_digest(duplicate)
            write_records(data_path, original + [duplicate])
            repeated = verify_journal(data_path, data)

        self.assertIn(
            reordered["diagnostics"][0]["code"],
            {"JOURNAL_SEQUENCE_GAP", "JOURNAL_CHAIN_MISMATCH"},
        )
        self.assertEqual(repeated["diagnostics"][0]["code"], "JOURNAL_DUPLICATE_TERMINAL")

    def test_pending_prepare_can_abort_visibly_and_only_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            initial = workspace("Initial")
            run_change(
                data_path,
                before=None,
                after=initial,
                event_kind="checkpoint",
                coverage="complete",
            )
            updated = workspace("Pending")
            prepared = prepare_record(
                sequence=2,
                previous_record_digest=read_records(data_path)[-1]["record_digest"],
                event_kind="mutation",
                coverage="continuous",
                expected_before_workspace_digest=workspace_digest(initial),
                before_workspace_digest=workspace_digest(initial),
                after_projection=updated,
                metadata=metadata(),
            )
            prepared["logical_changes"] = logical_changes(initial, updated)
            prepared["transaction_id"] = transaction_id_for_test(prepared)
            prepared["record_digest"] = record_digest(prepared)
            append_record_fsync(data_path, prepared)

            pending = verify_journal(data_path, initial)
            aborted = recover_pending(
                data_path,
                initial,
                action="abort",
                reason="Operator chose a different safe mutation",
            )
            repeated = recover_pending(
                data_path,
                initial,
                action="abort",
                reason="Operator chose a different safe mutation",
            )

        self.assertEqual(pending["status"], "pending-prepare")
        self.assertTrue(aborted["ok"])
        self.assertEqual(aborted["aborted_transactions"], 1)
        self.assertEqual(repeated["record_count"], aborted["record_count"])

    def test_exact_recovery_holds_writer_lock_until_terminal_append(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "workspace.json"
            initial = workspace("Initial")
            updated = workspace("Updated")
            run_change(
                data_path,
                before=None,
                after=initial,
                event_kind="checkpoint",
                coverage="complete",
            )

            def crash_after_apply(point: str) -> None:
                if point == "after_apply":
                    raise RuntimeError("injected after apply")

            with self.assertRaisesRegex(RuntimeError, "after apply"):
                transact(
                    data_path,
                    before_data=initial,
                    after_data=updated,
                    metadata=metadata(),
                    apply=lambda: data_path.write_text(
                        json.dumps(updated), encoding="utf-8"
                    ),
                    crash_hook=crash_after_apply,
                )
            prepared = read_records(data_path)[-1]
            actual_recover = recover_pending

            def recover_while_asserting_lock(*args, **kwargs):
                with self.assertRaisesRegex(WorkspaceError, "write is already in progress"):
                    with workspace_write_lock(root):
                        pass
                return actual_recover(*args, **kwargs)

            with patch(
                "palari_company_os.governance_journal.recover_pending",
                side_effect=recover_while_asserting_lock,
            ):
                report = recover_workspace_journal_if_current(
                    root,
                    "PALARI-TEST",
                    expected_status="pending-commit",
                    expected_workspace_digest=workspace_digest(updated),
                    expected_prepare_digest=str(prepared["record_digest"]),
                    expected_transaction_id=str(prepared["transaction_id"]),
                )

        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "valid")

    def test_exact_recovery_state_mismatch_never_appends(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "workspace.json"
            initial = workspace("Initial")
            updated = workspace("Updated")
            run_change(
                data_path,
                before=None,
                after=initial,
                event_kind="checkpoint",
                coverage="complete",
            )

            def crash_before_apply(point: str) -> None:
                if point == "before_apply":
                    raise RuntimeError("injected before apply")

            with self.assertRaisesRegex(RuntimeError, "before apply"):
                transact(
                    data_path,
                    before_data=initial,
                    after_data=updated,
                    metadata=metadata(),
                    apply=lambda: data_path.write_text(
                        json.dumps(updated), encoding="utf-8"
                    ),
                    crash_hook=crash_before_apply,
                )
            prepared = read_records(data_path)[-1]
            journal = journal_file_path(data_path)
            before_journal = journal.read_bytes()
            report = recover_workspace_journal_if_current(
                root,
                "PALARI-TEST",
                expected_status="pending-prepare",
                expected_workspace_digest=workspace_digest(initial),
                expected_prepare_digest="sha256:" + "0" * 64,
                expected_transaction_id=str(prepared["transaction_id"]),
                action="abort",
            )

            self.assertFalse(report["ok"])
            self.assertEqual(
                report["errors"][0]["code"], "JOURNAL_RECOVERY_STATE_CHANGED"
            )
            self.assertEqual(before_journal, journal.read_bytes())

    def test_journal_path_rejects_palari_and_file_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            data_path = root / "workspace.json"
            (root / ".palari").symlink_to(Path(outside), target_is_directory=True)
            with self.assertRaisesRegex(JournalError, "contains a symlink"):
                journal_file_path(data_path)

        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            data_path = root / "workspace.json"
            journal_dir = root / ".palari"
            journal_dir.mkdir()
            external = Path(outside) / "journal.jsonl"
            external.write_text("", encoding="utf-8")
            (journal_dir / "governance-journal.v1.jsonl").symlink_to(external)
            with self.assertRaisesRegex(JournalError, "contains a symlink"):
                journal_file_path(data_path)

    def test_operator_verify_reports_legacy_as_not_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "workspace.json").write_text(json.dumps(workspace("Legacy")), encoding="utf-8")
            report = verify_workspace_journal(root)

        self.assertFalse(report["enabled"])
        self.assertEqual(report["status"], "not-enabled")
        self.assertEqual(report["warnings"][0]["code"], "JOURNAL_NOT_ENABLED")

    def test_float_invalid_timestamp_and_unpaired_surrogate_are_rejected(self) -> None:
        with self.assertRaisesRegex(JournalError, "floating-point"):
            workspace_digest({"value": 1.5})
        with self.assertRaisesRegex(JournalError, "calendar instant"):
            metadata(timestamp="2026-99-99T12:00:00Z").as_dict()
        with self.assertRaisesRegex(JournalError, "Unicode surrogate"):
            workspace_digest({"value": "\ud800"})


def workspace(name: str) -> dict[str, object]:
    return {"schema_version": 2, "name": name, "goals": []}


def metadata(*, timestamp: str = TIMESTAMP) -> MutationMetadata:
    return MutationMetadata(
        command="test mutation",
        actor="PALARI-TEST",
        action="updated",
        timestamp=timestamp,
        objects=({"type": "workspace", "collection": "workspace", "id": "TEST"},),
    )


def run_change(
    data_path: Path,
    *,
    before: dict[str, object] | None,
    after: dict[str, object],
    event_kind: str = "mutation",
    coverage: str = "continuous",
) -> dict[str, object]:
    def apply() -> None:
        data_path.write_text(json.dumps(after), encoding="utf-8")

    return transact(
        data_path,
        before_data=before,
        after_data=after,
        metadata=metadata(),
        apply=apply,
        event_kind=event_kind,
        coverage=coverage,
    )


def read_records(data_path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in journal_file_path(data_path).read_text().splitlines()]


def write_records(data_path: Path, records: list[dict[str, object]]) -> None:
    journal_file_path(data_path).write_text(
        "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


def transaction_id_for_test(record: dict[str, object]) -> str:
    # Rebuild through prepare_record rather than depending on a private helper.
    rebuilt = prepare_record(
        sequence=int(record["sequence"]),
        previous_record_digest=record["previous_record_digest"],
        event_kind=str(record["event_kind"]),
        coverage=str(record["coverage"]),
        expected_before_workspace_digest=record["expected_before_workspace_digest"],
        before_workspace_digest=record["before_workspace_digest"],
        after_projection=record["after_projection"],
        metadata=record["metadata"],
    )
    rebuilt["logical_changes"] = record["logical_changes"]
    # transaction ids are independent of sequence/timestamp, but logical changes
    # are part of the identity. Use the module's public digest behavior indirectly.
    from palari_company_os.governance_journal import _transaction_id

    return _transaction_id(rebuilt)


if __name__ == "__main__":
    unittest.main()
