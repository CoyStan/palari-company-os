from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.store import load_store, migrate_data, write_store
from palari_company_os.workspace import Workspace, WorkspaceError


FIXTURES = REPO_ROOT / "tests" / "fixtures" / "workspaces"
EXAMPLE_WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class WorkspaceValidationTests(unittest.TestCase):
    def test_valid_fixture_loads(self) -> None:
        workspace = Workspace.load(FIXTURES / "valid-workspace.json")

        self.assertEqual(workspace.name, "Valid Workspace Fixture")
        self.assertEqual(workspace.work_items[0].id, "WORK-1")

    def test_valid_accepted_completed_work_fixture_loads(self) -> None:
        workspace = Workspace.load(FIXTURES / "valid-accepted-completed-work.json")

        self.assertEqual(workspace.work_items[0].status, "completed")
        self.assertEqual(workspace.human_decisions[0].status, "accepted")

    def test_valid_source_receipt_loop_fixture_loads(self) -> None:
        workspace = Workspace.load(FIXTURES / "valid-source-receipt-loop.json")

        self.assertEqual(workspace.sources[0].id, "SOURCE-1")
        self.assertEqual(workspace.receipts[0].sources_used, ["SOURCE-1"])

    def test_split_workspace_collection_file_loads(self) -> None:
        workspace = Workspace.load(FIXTURES / "split-workspace")

        self.assertEqual(workspace.name, "Split Workspace Fixture")
        self.assertEqual([item.id for item in workspace.work_items], ["WORK-SPLIT"])
        self.assertEqual(workspace.palaris[0].active_work, ["WORK-SPLIT"])

    def test_split_workspace_duplicate_id_fails_closed(self) -> None:
        def duplicate(data: dict[str, object]) -> None:
            data["work_items"] = [
                {
                    "id": "WORK-SPLIT",
                    "title": "Duplicate root work",
                    "goal": "GOAL-SPLIT",
                    "palari": "PALARI-SPLIT",
                }
            ]

        with self.modified_split_workspace(duplicate) as workspace:
            with self.assertRaisesRegex(WorkspaceError, "work_items contains duplicate id: WORK-SPLIT"):
                Workspace.load(workspace)

    def test_split_workspace_unknown_collection_fails_closed(self) -> None:
        def unknown(data: dict[str, object]) -> None:
            data["collection_files"]["not_a_collection"] = ["records/work-items.json"]

        with self.modified_split_workspace(unknown) as workspace:
            with self.assertRaisesRegex(
                WorkspaceError,
                "workspace.collection_files has unknown collection",
            ):
                Workspace.load(workspace)

    def test_split_workspace_rejects_unsafe_collection_path(self) -> None:
        def unsafe(data: dict[str, object]) -> None:
            data["collection_files"]["work_items"] = ["../work-items.json"]

        with self.modified_split_workspace(unsafe) as workspace:
            with self.assertRaisesRegex(
                WorkspaceError,
                "path must be workspace-relative and must not contain",
            ):
                Workspace.load(workspace)

    def test_split_workspace_rejects_absolute_collection_path(self) -> None:
        def unsafe(data: dict[str, object]) -> None:
            data["collection_files"]["work_items"] = ["/tmp/work-items.json"]

        with self.modified_split_workspace(unsafe) as workspace:
            with self.assertRaisesRegex(
                WorkspaceError,
                "path must be workspace-relative and must not contain",
            ):
                Workspace.load(workspace)

    def test_split_workspace_collection_file_must_be_record_array(self) -> None:
        def replace_collection_file(data: dict[str, object]) -> None:
            pass

        with self.modified_split_workspace(replace_collection_file) as workspace:
            collection_file = workspace / "records" / "work-items.json"
            collection_file.write_text(json.dumps({"id": "WORK-SPLIT"}), encoding="utf-8")

            with self.assertRaisesRegex(
                WorkspaceError,
                "must contain a list of objects",
            ):
                Workspace.load(workspace)

    def test_split_workspace_missing_collection_file_fails_closed(self) -> None:
        def missing(data: dict[str, object]) -> None:
            data["collection_files"]["work_items"] = ["records/missing.json"]

        with self.modified_split_workspace(missing) as workspace:
            with self.assertRaisesRegex(
                WorkspaceError,
                "workspace.collection_files.work_items file not found",
            ):
                Workspace.load(workspace)

    def test_write_store_refuses_split_workspace(self) -> None:
        with self.modified_split_workspace(lambda data: None) as workspace:
            store = load_store(workspace)
            store.data["name"] = "Changed Split Workspace"

            with self.assertRaisesRegex(
                WorkspaceError,
                "authoring writes are not supported for split workspaces",
            ):
                write_store(store)

    def test_unknown_record_field_fails_closed(self) -> None:
        self.assert_fixture_error(
            "unknown-field.json",
            "work_items.WORK-1 has unknown field(s): unknown_runtime_hint",
        )

    def test_unsupported_schema_version_fails_closed(self) -> None:
        self.assert_fixture_error(
            "unsupported-schema-version.json",
            "workspace schema_version 99 is newer than supported version 1",
        )

    def test_broken_reference_fails_closed(self) -> None:
        self.assert_fixture_error(
            "broken-reference.json",
            "work_items.WORK-1.goal references missing id GOAL-MISSING",
        )

    def test_invalid_lifecycle_state_fails_closed(self) -> None:
        self.assert_fixture_error(
            "invalid-lifecycle-state.json",
            "work_items.WORK-1.status has unsupported value 'probably-done'",
        )

    def test_accepted_decision_with_stale_evidence_fails_closed(self) -> None:
        self.assert_fixture_error(
            "stale-evidence.json",
            "work_items.WORK-1 evidence EVIDENCE-1 is stale",
        )

    def test_accepted_decision_with_stale_review_fails_closed(self) -> None:
        self.assert_fixture_error(
            "stale-review.json",
            "work_items.WORK-1 review REVIEW-1 is stale",
        )

    def test_accepted_decision_with_unqualified_human_fails_closed(self) -> None:
        self.assert_fixture_error(
            "invalid-human-approval-capability.json",
            "human_decisions.HUMAN-DECISION-1.human_id lacks required approval capability product",
        )

    def test_completed_work_without_quorum_fails_closed(self) -> None:
        self.assert_fixture_error(
            "invalid-completed-work.json",
            "work_items.WORK-1.status is terminal but approval quorum is 0/1",
        )

    def test_receipt_with_unallowed_source_fails_closed(self) -> None:
        self.assert_fixture_error(
            "invalid-receipt-unallowed-source.json",
            "receipts.RECEIPT-1.sources_used includes unallowed source SOURCE-2",
        )

    def test_receipt_with_missing_source_fails_closed(self) -> None:
        self.assert_fixture_error(
            "invalid-receipt-missing-source.json",
            "receipts.RECEIPT-1.sources_used references missing id SOURCE-MISSING",
        )

    def test_receipt_external_write_without_allowed_action_fails_closed(self) -> None:
        self.assert_fixture_error(
            "invalid-receipt-external-write.json",
            "receipts.RECEIPT-1.external_writes requires allowed action external_write",
        )

    def test_receipt_actor_must_match_attempt_or_palari_boundary(self) -> None:
        self.assert_fixture_error(
            "invalid-receipt-actor.json",
            "receipts.RECEIPT-1.actor must match attempt actor PALARI-1",
        )

    def test_source_allowed_palaris_must_exist(self) -> None:
        self.assert_fixture_error(
            "invalid-source-missing-palari.json",
            "sources.SOURCE-1.allowed_palaris references missing id PALARI-MISSING",
        )

    def test_cli_validate_reports_clear_fixture_errors(self) -> None:
        result = self.run_cli_validate(FIXTURES / "unknown-field.json")

        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown_runtime_hint", result.stderr)

    def test_migration_adds_schema_version_to_legacy_workspace(self) -> None:
        legacy = json.loads((EXAMPLE_WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        legacy.pop("schema_version")
        migrated, changes = migrate_data(legacy)

        self.assertEqual(migrated["schema_version"], 1)
        self.assertIn("Added schema_version: 1.", changes)

    def test_schema_version_zero_requires_migration(self) -> None:
        legacy = json.loads((EXAMPLE_WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        legacy["schema_version"] = 0

        with self.assertRaisesRegex(
            WorkspaceError,
            "workspace schema_version 0 is older than supported version 1",
        ):
            Workspace.from_raw(legacy, EXAMPLE_WORKSPACE)
        migrated, changes = migrate_data(legacy)
        self.assertEqual(migrated["schema_version"], 1)
        self.assertIn("Upgraded schema_version from 0 to 1.", changes)

    def assert_fixture_error(self, fixture: str, expected: str) -> None:
        with self.assertRaises(WorkspaceError) as context:
            Workspace.load(FIXTURES / fixture)
        self.assertIn(expected, str(context.exception))

    def run_cli_validate(self, workspace_file: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "palari_company_os",
                "--workspace",
                str(workspace_file),
                "validate",
            ],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def modified_split_workspace(self, mutate: object):
        source = FIXTURES / "split-workspace"
        directory = tempfile.TemporaryDirectory()
        workspace = Path(directory.name) / "split-workspace"
        shutil.copytree(source, workspace)
        workspace_file = workspace / "workspace.json"
        data = json.loads(workspace_file.read_text(encoding="utf-8"))
        mutate(data)
        workspace_file.write_text(json.dumps(data), encoding="utf-8")

        class SplitWorkspaceFixture:
            def __enter__(self) -> Path:
                return workspace

            def __exit__(self, *args: object) -> None:
                directory.cleanup()

        return SplitWorkspaceFixture()


if __name__ == "__main__":
    unittest.main()
