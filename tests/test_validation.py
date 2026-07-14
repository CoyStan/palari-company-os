from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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

    def test_completed_low_risk_receipt_ready_work_loads(self) -> None:
        raw = json.loads((FIXTURES / "valid-source-receipt-loop.json").read_text(encoding="utf-8"))
        raw["work_items"][0]["status"] = "completed"
        workspace = Workspace.from_raw(raw, FIXTURES)

        self.assertEqual(workspace.work_items[0].status, "completed")

    def test_completed_work_with_unfinished_dependency_fails_closed(self) -> None:
        raw = json.loads((FIXTURES / "valid-source-receipt-loop.json").read_text(encoding="utf-8"))
        raw["work_items"][0]["status"] = "completed"
        raw["work_items"][0]["dependency_ids"] = ["WORK-OPEN"]
        raw["work_items"].append(
            {
                "id": "WORK-OPEN",
                "title": "Open dependency",
                "goal": "GOAL-1",
                "palari": "PALARI-1",
                "risk": "R1",
                "intensity": "light",
                "status": "active",
            }
        )

        with self.assertRaisesRegex(
            WorkspaceError,
            "work_items.WORK-1.status is terminal but dependencies are unfinished: WORK-OPEN",
        ):
            Workspace.from_raw(raw, FIXTURES)

    def test_example_workbench_graph_loads(self) -> None:
        workspace = Workspace.load(EXAMPLE_WORKSPACE)

        self.assertEqual([workbench.id for workbench in workspace.workbenches], [
            "WORKBENCH-BETA",
            "WORKBENCH-AUTHORITY",
        ])
        self.assertEqual(workspace.work_item("WORK-0007").parent_work_item_id, "WORK-0001")

    def test_work_item_missing_workbench_reference_fails_closed(self) -> None:
        def missing_workbench(data: dict[str, object]) -> None:
            data["work_items"][0]["workbench_id"] = "WORKBENCH-MISSING"

        with self.assertRaisesRegex(
            WorkspaceError,
            "work_items.WORK-0001.workbench_id references missing id WORKBENCH-MISSING",
        ):
            self.modified_example_workspace(missing_workbench)

    def test_parent_workbench_cycle_fails_closed(self) -> None:
        def cycle(data: dict[str, object]) -> None:
            data["workbenches"][0]["parent_workbench_id"] = "WORKBENCH-AUTHORITY"
            data["workbenches"][1]["parent_workbench_id"] = "WORKBENCH-BETA"

        with self.assertRaisesRegex(
            WorkspaceError,
            "workbenches parent graph contains a cycle",
        ):
            self.modified_example_workspace(cycle)

    def test_parent_work_item_cycle_fails_closed(self) -> None:
        def cycle(data: dict[str, object]) -> None:
            data["work_items"][0]["parent_work_item_id"] = "WORK-0007"
            data["work_items"][6]["parent_work_item_id"] = "WORK-0001"

        with self.assertRaisesRegex(
            WorkspaceError,
            "work_items parent graph contains a cycle",
        ):
            self.modified_example_workspace(cycle)

    def test_missing_dependency_fails_closed(self) -> None:
        def missing_dependency(data: dict[str, object]) -> None:
            data["work_items"][6]["dependency_ids"] = ["WORK-MISSING"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "work_items.WORK-0007.dependency_ids references missing id WORK-MISSING",
        ):
            self.modified_example_workspace(missing_dependency)

    def test_work_item_source_outside_workbench_boundary_fails_closed(self) -> None:
        def outside_source(data: dict[str, object]) -> None:
            data["sources"].append(
                {
                    "id": "SOURCE-OUTSIDE",
                    "label": "Outside source",
                    "kind": "note",
                    "provider": "local_note",
                    "uri": "outside.md",
                    "access_mode": "read",
                    "selected": True,
                    "owner_human": "HUMAN-FOUNDER",
                    "allowed_palaris": ["PALARI-SOFIA"],
                }
            )
            data["work_items"][2]["allowed_sources"] = ["SOURCE-OUTSIDE"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "work_items.WORK-0003.allowed_sources includes source SOURCE-OUTSIDE "
            "outside workbench WORKBENCH-BETA",
        ):
            self.modified_example_workspace(outside_source)

    def test_work_item_output_outside_workbench_boundary_fails_closed(self) -> None:
        def outside_output(data: dict[str, object]) -> None:
            data["work_items"][6]["output_targets"] = ["outside.md"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "work_items.WORK-0007.output_targets includes target outside.md "
            "outside workbench WORKBENCH-BETA",
        ):
            self.modified_example_workspace(outside_output)

    def test_attempt_changed_file_outside_declared_boundary_fails_closed(self) -> None:
        def outside_changed_file(data: dict[str, object]) -> None:
            data["attempts"][0]["changed_files"] = ["secrets.env"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "attempts.ATTEMPT-0001.changed_files includes path outside declared boundaries",
        ):
            self.modified_example_workspace(outside_changed_file)

    def test_attempt_changed_file_with_traversal_fails_closed(self) -> None:
        def traversal(data: dict[str, object]) -> None:
            data["attempts"][0]["changed_files"] = ["docs/../secrets.env"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "attempts.ATTEMPT-0001.changed_files contains unsafe path",
        ):
            self.modified_example_workspace(traversal)

    def test_receipt_output_outside_declared_boundary_fails_closed(self) -> None:
        def outside_output(data: dict[str, object]) -> None:
            receipt = next(item for item in data["receipts"] if item["id"] == "RECEIPT-0001")
            receipt["outputs_created"] = ["secrets.env"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "receipts.RECEIPT-0001.outputs_created includes path outside declared boundaries",
        ):
            self.modified_example_workspace(outside_output)

    def test_receipt_undo_ref_outside_declared_boundary_fails_closed(self) -> None:
        def outside_undo(data: dict[str, object]) -> None:
            receipt = next(item for item in data["receipts"] if item["id"] == "RECEIPT-0001")
            receipt["undo_refs"] = ["delete secrets.env"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "receipts.RECEIPT-0001.undo_refs includes path outside declared boundaries",
        ):
            self.modified_example_workspace(outside_undo)


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

    def test_write_store_fails_when_workspace_changed_after_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            shutil.copy(EXAMPLE_WORKSPACE / "workspace.json", workspace_file)
            stale_store = load_store(workspace_file)
            fresh_store = load_store(workspace_file)
            fresh_store.data["name"] = "Fresh write wins"
            write_store(fresh_store)

            stale_store.data["name"] = "Stale write loses"
            with self.assertRaisesRegex(
                WorkspaceError,
                "workspace changed since it was loaded; retry command",
            ):
                write_store(stale_store)

            self.assertEqual(load_store(workspace_file).data["name"], "Fresh write wins")

    def test_write_store_reclaims_stale_workspace_lock_with_dead_pid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            shutil.copy(EXAMPLE_WORKSPACE / "workspace.json", workspace_file)
            store = load_store(workspace_file)
            store.data["name"] = "Recovered from dead lock pid"
            lock_path = workspace_file.parent / ".palari" / "locks" / "workspace.json.lock"
            lock_path.parent.mkdir(parents=True)
            dead_process = subprocess.Popen([sys.executable, "-c", "pass"])
            dead_pid = dead_process.pid
            dead_process.wait(timeout=30)
            lock_path.write_text(f"pid={dead_pid}\n", encoding="utf-8")

            write_store(store)

            self.assertEqual(load_store(workspace_file).data["name"], "Recovered from dead lock pid")
            self.assertFalse(lock_path.exists())

    def test_write_store_reclaims_old_workspace_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            shutil.copy(EXAMPLE_WORKSPACE / "workspace.json", workspace_file)
            store = load_store(workspace_file)
            store.data["name"] = "Recovered from old lock"
            lock_path = workspace_file.parent / ".palari" / "locks" / "workspace.json.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text("not a parseable lock\n", encoding="utf-8")
            old_time = time.time() - 120
            os.utime(lock_path, (old_time, old_time))

            write_store(store)

            self.assertEqual(load_store(workspace_file).data["name"], "Recovered from old lock")
            self.assertFalse(lock_path.exists())

    def test_write_store_fails_when_fresh_live_workspace_lock_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            shutil.copy(EXAMPLE_WORKSPACE / "workspace.json", workspace_file)
            store = load_store(workspace_file)
            store.data["name"] = "Blocked by lock"
            lock_path = workspace_file.parent / ".palari" / "locks" / "workspace.json.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text(f"pid={os.getpid()}\n", encoding="utf-8")

            with self.assertRaisesRegex(
                WorkspaceError,
                "workspace write is already in progress; retry shortly",
            ):
                write_store(store)

            self.assertTrue(lock_path.exists())

    def test_write_store_removes_workspace_lock_after_successful_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            shutil.copy(EXAMPLE_WORKSPACE / "workspace.json", workspace_file)
            store = load_store(workspace_file)
            store.data["name"] = "Normal write"
            lock_path = workspace_file.parent / ".palari" / "locks" / "workspace.json.lock"

            write_store(store)

            self.assertEqual(load_store(workspace_file).data["name"], "Normal write")
            self.assertFalse(lock_path.exists())

    def test_unknown_record_field_fails_closed(self) -> None:
        self.assert_fixture_error(
            "unknown-field.json",
            "work_items.WORK-1 has unknown field(s): unknown_runtime_hint",
        )

    def test_unsupported_schema_version_fails_closed(self) -> None:
        self.assert_fixture_error(
            "unsupported-schema-version.json",
            "workspace schema_version 99 is newer than supported version 2",
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

    def test_accepted_decision_with_failed_evidence_fails_closed(self) -> None:
        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        raw["evidence_runs"][0]["status"] = "failed"

        with self.assertRaisesRegex(WorkspaceError, "evidence EVIDENCE-1 is failed"):
            Workspace.from_raw(raw, FIXTURES)

    def test_accepted_decision_with_mismatched_review_head_fails_closed(self) -> None:
        from palari_company_os.governance_binding import review_proof_hash

        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        review = raw["review_verdicts"][0]
        review["reviewed_head"] = "different-head"
        review["proof_hash"] = review_proof_hash(review)

        with self.assertRaisesRegex(WorkspaceError, "evidence head does not match reviewed head"):
            Workspace.from_raw(raw, FIXTURES)

    def test_accepted_decision_with_unqualified_human_fails_closed(self) -> None:
        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        raw["humans"][0]["approval_capabilities"] = []

        with self.assertRaisesRegex(
            WorkspaceError,
            "human_decisions.HUMAN-DECISION-1.human_id lacks required approval capability product",
        ):
            Workspace.from_raw(raw, FIXTURES)

    def test_review_builder_must_be_independent_human(self) -> None:
        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        raw["attempts"][0]["actor"] = "HUMAN-PRODUCT"

        with self.assertRaisesRegex(
            WorkspaceError,
            "reviewer must be independent from attempt actor HUMAN-PRODUCT",
        ):
            Workspace.from_raw(raw, FIXTURES)

    def test_acceptance_record_cannot_reference_negative_decision(self) -> None:
        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        raw["human_decisions"][0]["decision"] = "changes-requested"
        raw["human_decisions"][0]["status"] = "changes-requested"
        raw["human_decisions"][0]["quorum_status"] = "not-met"
        raw["acceptance_records"] = [
            {
                "id": "ACCEPTANCE-1",
                "work_item_id": "WORK-1",
                "human_id": "HUMAN-PRODUCT",
                "reviewed_head": "head-1",
                "status": "accepted",
                "decision_id": "HUMAN-DECISION-1",
                "evidence_reference": "EVIDENCE-1",
                "review_reference": "REVIEW-1",
                "quorum_status": "met",
            }
        ]

        with self.assertRaisesRegex(WorkspaceError, "points to non-acceptance decision"):
            Workspace.from_raw(raw, FIXTURES)

    def test_later_negative_decision_revokes_completion_quorum(self) -> None:
        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        raw["human_decisions"].append(
            {
                "id": "HUMAN-DECISION-2",
                "work_item_id": "WORK-1",
                "human_id": "HUMAN-PRODUCT",
                "reviewed_head": "head-1",
                "decision": "changes-requested",
                "status": "changes-requested",
                "quorum_status": "not-met",
                "timestamp": "2030-01-01T00:00:00Z",
            }
        )

        with self.assertRaisesRegex(WorkspaceError, "approval quorum is 0/1"):
            Workspace.from_raw(raw, FIXTURES)

    def test_contradictory_acceptance_decision_fails_closed(self) -> None:
        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        raw["human_decisions"][0]["status"] = "rejected"

        with self.assertRaisesRegex(WorkspaceError, "contradictory decision and status"):
            Workspace.from_raw(raw, FIXTURES)

    def test_human_decision_requires_timestamp(self) -> None:
        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        raw["human_decisions"][0].pop("timestamp")

        with self.assertRaisesRegex(WorkspaceError, "timestamp is required"):
            Workspace.from_raw(raw, FIXTURES)

    def test_duplicate_human_decision_timestamp_fails_closed(self) -> None:
        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        raw["human_decisions"].append(
            {
                "id": "HUMAN-DECISION-2",
                "work_item_id": "WORK-1",
                "human_id": "HUMAN-PRODUCT",
                "reviewed_head": "head-1",
                "decision": "changes-requested",
                "status": "changes-requested",
                "quorum_status": "not-met",
                "timestamp": "2026-06-19T04:03:00Z",
            }
        )

        with self.assertRaisesRegex(WorkspaceError, "decision order would be ambiguous"):
            Workspace.from_raw(raw, FIXTURES)

    def test_human_decision_update_stamps_new_ordering_time(self) -> None:
        from palari_company_os.authoring import update_human_decision

        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            raw = json.loads(
                (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
            )
            raw["work_items"][0]["status"] = "in-review"
            raw["acceptance_records"] = []
            workspace_file.write_text(json.dumps(raw), encoding="utf-8")
            original = raw["human_decisions"][0]["timestamp"]

            update_human_decision(
                str(workspace_file),
                "HUMAN-DECISION-1",
                {
                    "decision": "changes-requested",
                    "status": "changes-requested",
                    "quorum_status": "not-met",
                },
            )

            decision = Workspace.load(workspace_file).human_decisions[0]
            self.assertNotEqual(decision.timestamp, original)
            self.assertEqual(decision.status, "changes-requested")

    def test_completed_work_rejects_stale_exact_work_contract(self) -> None:
        raw = json.loads((EXAMPLE_WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        work = next(item for item in raw["work_items"] if item["id"] == "WORK-0001")
        work["status"] = "completed"
        work["scope"] = "Changed after exact review."
        raw["human_decisions"].append(
            {
                "id": "HUMAN-DECISION-EXACT",
                "work_item_id": "WORK-0001",
                "human_id": "HUMAN-FOUNDER",
                "reviewed_head": "abc1234",
                "decision": "accepted",
                "status": "accepted",
                "acceptance_mode": "human",
                "quorum_status": "met",
                "evidence_reference": "EVIDENCE-0001",
                "review_reference": "REVIEW-0001",
                "timestamp": "2026-06-18T18:00:00Z",
            }
        )

        with self.assertRaisesRegex(
            WorkspaceError,
            "review_reference is stale for the work contract",
        ):
            Workspace.from_raw(raw, EXAMPLE_WORKSPACE)

    def test_exact_bound_review_content_cannot_change_without_invalidating_proof(self) -> None:
        raw = json.loads((EXAMPLE_WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        review = next(item for item in raw["review_verdicts"] if item["id"] == "REVIEW-0001")
        review["findings"] = [{"severity": "high", "message": "added after review"}]

        with self.assertRaisesRegex(
            WorkspaceError,
            "review REVIEW-0001 proof hash is missing or malformed",
        ):
            Workspace.from_raw(raw, EXAMPLE_WORKSPACE)

    def test_exact_bound_terminal_work_requires_acceptance_record(self) -> None:
        raw = json.loads((EXAMPLE_WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        work = next(item for item in raw["work_items"] if item["id"] == "WORK-0001")
        work["status"] = "completed"
        raw["human_decisions"].append(
            {
                "id": "HUMAN-DECISION-EXACT",
                "work_item_id": "WORK-0001",
                "human_id": "HUMAN-FOUNDER",
                "reviewed_head": "abc1234",
                "decision": "accepted",
                "status": "accepted",
                "acceptance_mode": "human",
                "quorum_status": "met",
                "evidence_reference": "EVIDENCE-0001",
                "review_reference": "REVIEW-0001",
                "timestamp": "2026-06-18T18:00:00Z",
            }
        )

        with self.assertRaisesRegex(
            WorkspaceError,
            "status is terminal but exact acceptance record is missing",
        ):
            Workspace.from_raw(raw, EXAMPLE_WORKSPACE)

    def test_high_risk_terminal_work_requires_terminal_attempt(self) -> None:
        raw = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        raw["attempts"][0]["status"] = "active"

        with self.assertRaisesRegex(WorkspaceError, "attempt state changed after review"):
            Workspace.from_raw(raw, FIXTURES)

    def test_schema_v2_rejects_unbound_accept_ready_review(self) -> None:
        self.assert_fixture_error(
            "invalid-completed-work.json",
            "review_verdicts.REVIEW-1.verdict accept-ready requires exact proof binding",
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

    def test_source_readiness_values_are_strict(self) -> None:
        def bad_data_class(data: dict[str, object]) -> None:
            data["sources"][0]["data_class"] = "secretish"

        with self.assertRaisesRegex(
            WorkspaceError,
            "sources.SOURCE-0001.data_class has unsupported value 'secretish'",
        ):
            self.modified_example_workspace(bad_data_class)

    def test_source_steward_human_must_exist(self) -> None:
        def bad_steward(data: dict[str, object]) -> None:
            data["sources"][0]["steward_human"] = "HUMAN-MISSING"

        with self.assertRaisesRegex(
            WorkspaceError,
            "sources.SOURCE-0001.steward_human references missing id HUMAN-MISSING",
        ):
            self.modified_example_workspace(bad_steward)

    def test_palari_memory_sources_must_exist(self) -> None:
        def missing_memory_source(data: dict[str, object]) -> None:
            data["palaris"][0]["memory_sources"] = ["SOURCE-MISSING"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "palaris.PALARI-SOFIA.memory_sources references missing id SOURCE-MISSING",
        ):
            self.modified_example_workspace(missing_memory_source)

    def test_cli_validate_reports_clear_fixture_errors(self) -> None:
        result = self.run_cli_validate(FIXTURES / "unknown-field.json")

        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown_runtime_hint", result.stderr)

    def test_migration_adds_schema_version_to_legacy_workspace(self) -> None:
        legacy = json.loads((EXAMPLE_WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        legacy.pop("schema_version")
        migrated, changes = migrate_data(legacy)

        self.assertEqual(migrated["schema_version"], 2)
        self.assertIn("Added legacy schema_version: 1 before migration.", changes)
        self.assertIn("Upgraded schema_version from 1 to 2.", changes)

    def test_schema_version_zero_requires_migration(self) -> None:
        legacy = json.loads((EXAMPLE_WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        legacy["schema_version"] = 0

        with self.assertRaisesRegex(
            WorkspaceError,
            "workspace schema_version 0 is older than supported version 2",
        ):
            Workspace.from_raw(legacy, EXAMPLE_WORKSPACE)
        migrated, changes = migrate_data(legacy)
        self.assertEqual(migrated["schema_version"], 2)
        self.assertIn("Upgraded schema_version from 0 to 1 before migration.", changes)

    def test_schema_v1_migration_invalidates_unbound_acceptance(self) -> None:
        legacy = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        legacy["schema_version"] = 1
        legacy["review_verdicts"][0].pop("binding_version")

        migrated, changes = migrate_data(legacy)
        workspace = Workspace.from_raw(migrated, FIXTURES)

        self.assertEqual(workspace.schema_version, 2)
        self.assertEqual(workspace.review_verdicts[0].verdict, "blocked")
        self.assertEqual(workspace.human_decisions[0].decision, "blocked")
        self.assertEqual(workspace.acceptance_records[0].status, "revoked")
        self.assertEqual(workspace.work_items[0].status, "in-review")
        self.assertIn("Blocked 1 legacy accept-ready review(s) without exact binding.", changes)

    def test_schema_v1_migration_preserves_valid_exact_acceptance(self) -> None:
        legacy = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )
        legacy["schema_version"] = 1
        legacy["review_verdicts"][0]["proof_hash"] = "sha256:legacy-binding-only"

        migrated, changes = migrate_data(legacy)
        workspace = Workspace.from_raw(migrated, FIXTURES)

        self.assertEqual(workspace.work_items[0].status, "completed")
        self.assertEqual(workspace.acceptance_records[0].status, "accepted")
        self.assertIn("Upgraded aggregate proof hash for bound review REVIEW-1.", changes)

    def test_schema_v2_migration_is_idempotent(self) -> None:
        current = json.loads(
            (FIXTURES / "valid-accepted-completed-work.json").read_text(encoding="utf-8")
        )

        migrated, changes = migrate_data(current)

        self.assertEqual(migrated["schema_version"], current["schema_version"])
        self.assertEqual(migrated["work_items"], current["work_items"])
        self.assertEqual(migrated["review_verdicts"], current["review_verdicts"])
        self.assertIn("Workspace already uses schema_version: 2.", changes)

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
                "-S",
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
            timeout=30,
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

    def modified_example_workspace(self, mutate: object) -> Workspace:
        source = json.loads((EXAMPLE_WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        mutate(source)
        return Workspace.from_raw(source, EXAMPLE_WORKSPACE)


if __name__ == "__main__":
    unittest.main()
