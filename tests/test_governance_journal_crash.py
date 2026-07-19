from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.governance_journal import (
    MutationMetadata,
    _active_state,
    _v1_predecessor_binding,
    legacy_journal_file_path,
    recover_pending,
    transact,
    verify_journal,
)


TIMESTAMP = "2026-07-14T12:00:00Z"
COMMITTED_V1_FIXTURE = (
    REPO_ROOT
    / "workspaces"
    / "palari-company-os"
    / ".palari"
    / "governance-journal.v1.jsonl"
)
COMMITTED_V1_PAIR_SHA256 = (
    "2a9adc1844c3eeb710087dd35032fb978845da80bb0230b433686eba8de6218b"
)


class InjectedCrash(RuntimeError):
    pass


class GovernanceJournalCrashTests(unittest.TestCase):
    def test_v1_to_v2_activation_crashes_remain_recoverable(self) -> None:
        for point, expected in {
            "after_prepare_fsync": "pending-prepare",
            # Activation is a no-op workspace checkpoint, so before and after
            # digests are intentionally identical at every crash boundary.
            "after_apply": "pending-prepare",
        }.items():
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                data_path = Path(directory) / "workspace.json"
                data, sealed_v1 = install_committed_v1_predecessor(data_path)
                predecessor = _v1_predecessor_binding(data_path, _active_state(data_path))

                with self.assertRaisesRegex(InjectedCrash, point):
                    transact(
                        data_path,
                        before_data=data,
                        after_data=data,
                        metadata=metadata(action="activated-v2"),
                        apply=lambda: None,
                        event_kind="checkpoint",
                        coverage="continuous",
                        crash_hook=crash_at(point),
                        _predecessor=predecessor,
                    )

                pending = verify_journal(data_path, data)
                recovered = recover_pending(data_path, data)

                self.assertEqual(pending["status"], expected)
                self.assertTrue(recovered["ok"])
                self.assertEqual(
                    legacy_journal_file_path(data_path).read_bytes(), sealed_v1
                )

    def test_initial_checkpoint_crash_boundaries_are_detectable(self) -> None:
        expectations = {
            "after_prepare_write": "pending-prepare",
            "after_prepare_fsync": "pending-prepare",
            "after_prepare_directory_fsync": "pending-prepare",
            "before_apply": "pending-prepare",
            "after_apply": "pending-commit",
            "before_commit_append": "pending-commit",
            "after_commit_write": "valid",
            "after_commit_fsync": "valid",
        }
        for point, expected_status in expectations.items():
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                data_path = Path(directory) / "workspace.json"
                after = workspace("Created")

                with self.assertRaisesRegex(InjectedCrash, point):
                    transact(
                        data_path,
                        before_data=None,
                        after_data=after,
                        metadata=metadata(),
                        apply=lambda: write_workspace(data_path, after),
                        event_kind="checkpoint",
                        coverage="complete",
                        crash_hook=crash_at(point),
                    )

                current = after if data_path.exists() else None
                report = verify_journal(data_path, current)

                self.assertEqual(report["status"], expected_status)
                self.assertTrue(report["chain_valid"])

    def test_crash_before_prepare_append_leaves_no_partial_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            after = workspace("Created")
            with self.assertRaisesRegex(InjectedCrash, "before_prepare_append"):
                transact(
                    data_path,
                    before_data=None,
                    after_data=after,
                    metadata=metadata(),
                    apply=lambda: write_workspace(data_path, after),
                    event_kind="checkpoint",
                    coverage="complete",
                    crash_hook=crash_at("before_prepare_append"),
                )

            report = verify_journal(data_path, None)

        self.assertEqual(report["status"], "not-enabled")
        self.assertFalse(data_path.exists())

    def test_retry_identical_prepare_does_not_duplicate_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            after = workspace("Created")
            with self.assertRaises(InjectedCrash):
                transact(
                    data_path,
                    before_data=None,
                    after_data=after,
                    metadata=metadata(),
                    apply=lambda: write_workspace(data_path, after),
                    event_kind="checkpoint",
                    coverage="complete",
                    crash_hook=crash_at("after_prepare_fsync"),
                )

            report = transact(
                data_path,
                before_data=None,
                after_data=after,
                metadata=metadata(timestamp="2026-07-14T12:00:01Z"),
                apply=lambda: write_workspace(data_path, after),
                event_kind="checkpoint",
                coverage="complete",
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["record_count"], 2)
        self.assertEqual(report["committed_transactions"], 1)

    def test_missing_commit_recovers_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            after = workspace("Created")
            with self.assertRaises(InjectedCrash):
                transact(
                    data_path,
                    before_data=None,
                    after_data=after,
                    metadata=metadata(),
                    apply=lambda: write_workspace(data_path, after),
                    event_kind="checkpoint",
                    coverage="complete",
                    crash_hook=crash_at("after_apply"),
                )

            first = recover_pending(data_path, after)
            second = recover_pending(data_path, after)

        self.assertTrue(first["ok"])
        self.assertEqual(first["record_count"], 2)
        self.assertEqual(second["record_count"], 2)

    def test_retry_existing_workspace_prepare_reuses_exact_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            initial = workspace("Initial")
            transact(
                data_path,
                before_data=None,
                after_data=initial,
                metadata=metadata(),
                apply=lambda: write_workspace(data_path, initial),
                event_kind="checkpoint",
                coverage="complete",
            )
            updated = workspace("Updated")
            with self.assertRaises(InjectedCrash):
                transact(
                    data_path,
                    before_data=initial,
                    after_data=updated,
                    metadata=metadata(action="changed"),
                    apply=lambda: write_workspace(data_path, updated),
                    crash_hook=crash_at("after_prepare_fsync"),
                )

            report = transact(
                data_path,
                before_data=initial,
                after_data=updated,
                metadata=metadata(action="changed", timestamp="2026-07-14T12:00:01Z"),
                apply=lambda: write_workspace(data_path, updated),
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["record_count"], 4)
        self.assertEqual(report["committed_transactions"], 2)

    def test_different_mutation_cannot_replace_pending_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            initial = workspace("Initial")
            transact(
                data_path,
                before_data=None,
                after_data=initial,
                metadata=metadata(),
                apply=lambda: write_workspace(data_path, initial),
                event_kind="checkpoint",
                coverage="complete",
            )
            first_after = workspace("First pending")
            with self.assertRaises(InjectedCrash):
                transact(
                    data_path,
                    before_data=initial,
                    after_data=first_after,
                    metadata=metadata(action="first"),
                    apply=lambda: write_workspace(data_path, first_after),
                    crash_hook=crash_at("after_prepare_fsync"),
                )

            with self.assertRaisesRegex(Exception, "different prepared mutation"):
                transact(
                    data_path,
                    before_data=initial,
                    after_data=workspace("Second mutation"),
                    metadata=metadata(action="second"),
                    apply=lambda: None,
                )

    def test_pending_divergence_never_auto_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            initial = workspace("Initial")
            transact(
                data_path,
                before_data=None,
                after_data=initial,
                metadata=metadata(),
                apply=lambda: write_workspace(data_path, initial),
                event_kind="checkpoint",
                coverage="complete",
            )
            after = workspace("Expected")
            with self.assertRaises(InjectedCrash):
                transact(
                    data_path,
                    before_data=initial,
                    after_data=after,
                    metadata=metadata(),
                    apply=lambda: write_workspace(data_path, after),
                    crash_hook=crash_at("after_prepare_fsync"),
                )
            diverged = workspace("Unexpected")
            write_workspace(data_path, diverged)

            report = verify_journal(data_path, diverged)
            with self.assertRaisesRegex(Exception, "neither side"):
                recover_pending(data_path, diverged)

        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["diagnostics"][0]["code"], "JOURNAL_WORKSPACE_DIVERGENCE")


def crash_at(target: str):
    def hook(point: str) -> None:
        if point == target:
            raise InjectedCrash(point)

    return hook


def workspace(name: str) -> dict[str, object]:
    return {"schema_version": 2, "name": name, "goals": []}


def metadata(
    *,
    action: str = "updated",
    timestamp: str = TIMESTAMP,
) -> MutationMetadata:
    return MutationMetadata(
        command="test transaction",
        actor="PALARI-TEST",
        action=action,
        timestamp=timestamp,
    )


def write_workspace(data_path: Path, data: dict[str, object]) -> None:
    data_path.write_text(json.dumps(data), encoding="utf-8")


def install_committed_v1_predecessor(
    data_path: Path,
) -> tuple[dict[str, object], bytes]:
    with COMMITTED_V1_FIXTURE.open("rb") as source:
        pair = source.readline() + source.readline()
    if hashlib.sha256(pair).hexdigest() != COMMITTED_V1_PAIR_SHA256:
        raise AssertionError("tracked v1 predecessor fixture changed")
    records = [json.loads(line) for line in pair.splitlines()]
    projection = records[0].get("after_projection")
    if (
        [record.get("record_type") for record in records] != ["prepare", "commit"]
        or not isinstance(projection, dict)
    ):
        raise AssertionError("bounded v1 fixture is not one committed transaction")
    legacy = legacy_journal_file_path(data_path)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(pair)
    write_workspace(data_path, projection)
    return projection, pair


if __name__ == "__main__":
    unittest.main()
