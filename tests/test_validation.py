from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.evidence_manifest import (
    OUTPUT_BINDING_VERSION,
    evidence_manifest_hash,
    stamp_receipt_record,
)
from palari_company_os.governance_binding import (
    attempt_state_hash,
    review_proof_hash,
    work_contract_hash,
)
from palari_company_os.pcaw_workspace import recorded_governance_projection
from palari_company_os.store import WorkspaceStore, load_store, write_store
from palari_company_os.workspace import Workspace, WorkspaceError


FIXTURES = REPO_ROOT / "tests" / "fixtures" / "workspaces"


def fixture_data(name: str = "valid-source-receipt-loop.json") -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def current_completed_workspace_data() -> dict[str, Any]:
    """Build current exact terminal proof from the committed migration fixture."""

    data = fixture_data("valid-accepted-completed-work.json")
    work = data["work_items"][0]
    work.update(
        {
            "scope": "Create one local checklist.",
            "allowed_actions": ["local_write"],
            "output_targets": ["notes/output.md"],
            "path_intents": [{"path": "notes/output.md", "intent": "modify"}],
            "forbidden_actions": ["external_write"],
        }
    )
    attempt = data["attempts"][0]
    attempt.update(
        {
            "changed_files": ["notes/output.md"],
            "output_targets": ["notes/output.md"],
        }
    )
    receipt = data["receipts"][0]
    receipt["outputs_created"] = ["notes/output.md"]
    data["receipts"][0] = stamp_receipt_record(receipt, [])
    receipt = data["receipts"][0]
    evidence = data["evidence_runs"][0]
    evidence.update(
        {
            "artifacts": ["notes/output.md"],
            "artifact_hashes": [
                {
                    "path": "notes/output.md",
                    "sha256": "sha256:" + ("a" * 64),
                    "status": "present",
                }
            ],
            "output_binding_version": OUTPUT_BINDING_VERSION,
            "receipt_hash": receipt["receipt_hash"],
        }
    )
    evidence["manifest_hash"] = evidence_manifest_hash(evidence)

    proof_records = (
        data["review_verdicts"],
        data["human_decisions"],
        data["acceptance_records"],
    )
    data["review_verdicts"] = []
    data["human_decisions"] = []
    data["acceptance_records"] = []
    work["status"] = "active"
    structural_workspace = Workspace.from_raw(data, FIXTURES)
    data["review_verdicts"], data["human_decisions"], data["acceptance_records"] = (
        proof_records
    )
    work["status"] = "completed"

    review = data["review_verdicts"][0]
    review.update(
        {
            "attempt_hash": attempt_state_hash(structural_workspace.attempts[0]),
            "evidence_manifest_hash": evidence["manifest_hash"],
            "receipt_hash": receipt["receipt_hash"],
            "work_contract_hash": work_contract_hash(structural_workspace.work_items[0]),
        }
    )
    review["proof_hash"] = review_proof_hash(review)
    data["acceptance_records"][0]["receipt_hash"] = receipt["receipt_hash"]
    return data


def bounded_workspace_data() -> dict[str, Any]:
    data = fixture_data()
    data["workbenches"] = [
        {
            "id": "WORKBENCH-ROOT",
            "label": "Root boundary",
            "goal_ids": ["GOAL-1"],
            "palari_ids": ["PALARI-1"],
            "human_ids": ["HUMAN-1"],
            "source_ids": ["SOURCE-1"],
            "output_target_ids": ["notes/summary.md"],
        },
        {
            "id": "WORKBENCH-CHILD",
            "label": "Inherited boundary",
            "parent_workbench_id": "WORKBENCH-ROOT",
        },
    ]
    work = data["work_items"][0]
    work["workbench_id"] = "WORKBENCH-CHILD"
    work["path_intents"] = [
        {"path": "notes/summary.md", "intent": "modify"},
    ]
    return data


class WorkspaceContractTests(unittest.TestCase):
    def test_current_fixture_and_narrow_historical_inputs_load(self) -> None:
        current = Workspace.load(FIXTURES / "valid-source-receipt-loop.json")
        historical = Workspace.load(FIXTURES / "valid-workspace.json")

        self.assertEqual(current.schema_version, 2)
        self.assertEqual(current.work_items[0].path_intents, [])
        self.assertEqual(historical.evidence_runs[0].output_binding_version, "")
        self.assertEqual(historical.review_verdicts[0].binding_version, "")
        self.assertEqual(historical.review_verdicts[0].verdict, "blocked")

    def test_unversioned_terminal_fixture_loads_only_through_historical_boundary(self) -> None:
        with patch(
            "palari_company_os.pcaw_workspace.recorded_governance_projection",
            side_effect=AssertionError("historical migration must not claim current proof"),
        ):
            historical = Workspace.load(
                FIXTURES / "valid-accepted-completed-work.json"
            )

        self.assertEqual(historical.work_items[0].status, "completed")
        self.assertEqual(historical.evidence_runs[0].output_binding_version, "")

    def test_current_terminal_decision_drift_fails_closed_in_kernel(self) -> None:
        data = current_completed_workspace_data()
        decision = data["human_decisions"][0]
        decision["acceptance_mode"] = ""
        decision["quorum_status"] = "pending"

        with self.assertRaisesRegex(
            WorkspaceError,
            "current recorded proof does not derive completed",
        ):
            Workspace.from_raw(data, FIXTURES)

    def test_current_terminal_load_routes_through_recorded_kernel(self) -> None:
        with patch(
            "palari_company_os.pcaw_workspace.recorded_governance_projection",
            wraps=recorded_governance_projection,
        ) as projection:
            workspace = Workspace.from_raw(current_completed_workspace_data(), FIXTURES)

        projection.assert_called_once_with(workspace, "WORK-1")
        self.assertEqual(workspace.work_items[0].status, "completed")

    def test_nonterminal_acceptance_load_does_not_inspect_external_state(self) -> None:
        data = current_completed_workspace_data()
        data["work_items"][0]["status"] = "in-review"

        with (
            patch(
                "palari_company_os.evidence_manifest.verify_evidence",
                side_effect=AssertionError("load must not inspect artifact files"),
            ),
            patch(
                "palari_company_os.governance_journal.verify_workspace_journal",
                side_effect=AssertionError("load must not audit the journal"),
            ),
            patch(
                "subprocess.run",
                side_effect=AssertionError("load must not spawn Git or subprocesses"),
            ),
        ):
            workspace = Workspace.from_raw(data, FIXTURES)

        self.assertEqual(workspace.work_items[0].status, "in-review")

    def test_unbound_historical_review_cannot_grant_accept_ready_authority(self) -> None:
        data = fixture_data("valid-workspace.json")
        data["review_verdicts"][0]["verdict"] = "accept-ready"

        with self.assertRaisesRegex(
            WorkspaceError,
            "accept-ready requires exact proof binding",
        ):
            Workspace.from_raw(data, FIXTURES)

    def test_workspace_json_parser_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            malformed = root / "malformed.json"
            malformed.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceError, "invalid workspace JSON"):
                Workspace.load(malformed)

            non_object = root / "non-object.json"
            non_object.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceError, "root must be a JSON object"):
                Workspace.load(non_object)

            with self.assertRaisesRegex(WorkspaceError, "workspace file not found"):
                Workspace.load(root / "missing.json")

    def test_schema_version_boundary_is_exact(self) -> None:
        cases = (
            (None, "schema_version is missing"),
            (True, "schema_version must be an integer"),
            (1, "schema_version 1 is older than supported version 2"),
            (3, "schema_version 3 is newer than supported version 2"),
        )
        for version, expected in cases:
            with self.subTest(version=version):
                data = fixture_data()
                if version is None:
                    data.pop("schema_version")
                else:
                    data["schema_version"] = version
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(data, FIXTURES)

    def test_required_collections_and_record_shapes_fail_closed(self) -> None:
        cases: tuple[tuple[Callable[[dict[str, Any]], None], str], ...] = (
            (lambda data: data.pop("name"), "workspace.name is required"),
            (lambda data: data.pop("goals"), "workspace.goals collection is required"),
            (lambda data: data.__setitem__("goals", {}), "goals must be a list of objects"),
            (
                lambda data: data["work_items"][0].__setitem__("runtime_hint", "unsafe"),
                "work_items.WORK-1 has unknown field",
            ),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                data = fixture_data()
                mutate(data)
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(data, FIXTURES)

    def test_duplicate_ids_and_broken_references_fail_closed(self) -> None:
        duplicate = fixture_data()
        duplicate["work_items"].append(dict(duplicate["work_items"][0]))
        with self.assertRaisesRegex(WorkspaceError, "work_items contains duplicate id: WORK-1"):
            Workspace.from_raw(duplicate, FIXTURES)

        missing = fixture_data()
        missing["work_items"][0]["goal"] = "GOAL-MISSING"
        with self.assertRaisesRegex(
            WorkspaceError,
            "work_items.WORK-1.goal references missing id GOAL-MISSING",
        ):
            Workspace.from_raw(missing, FIXTURES)

    def test_structural_enums_fail_closed(self) -> None:
        cases = (
            ("work_items", "status", "probably-done", "unsupported value"),
            ("work_items", "risk", "R99", "unsupported value"),
            ("sources", "data_class", "secretish", "unsupported value"),
            ("sources", "authority", "unbounded", "unsupported value"),
        )
        for collection, field, value, expected in cases:
            with self.subTest(collection=collection, field=field):
                data = fixture_data()
                data[collection][0][field] = value
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(data, FIXTURES)

    def test_parent_and_dependency_graphs_fail_closed(self) -> None:
        parent_cycle = fixture_data()
        original = parent_cycle["work_items"][0]
        original["parent_work_item_id"] = "WORK-2"
        parent_cycle["work_items"].append(
            {
                "id": "WORK-2",
                "title": "Second work",
                "goal": "GOAL-1",
                "palari": "PALARI-1",
                "parent_work_item_id": "WORK-1",
            }
        )
        with self.assertRaisesRegex(WorkspaceError, "work_items parent graph contains a cycle"):
            Workspace.from_raw(parent_cycle, FIXTURES)

        dependency_cases = (
            (["WORK-MISSING"], "references missing id WORK-MISSING"),
            (["WORK-1"], "cannot reference itself"),
            (["WORK-2", "WORK-2"], "contains a duplicate id"),
        )
        for dependency_ids, expected in dependency_cases:
            with self.subTest(dependency_ids=dependency_ids):
                data = fixture_data()
                data["work_items"].append(
                    {
                        "id": "WORK-2",
                        "title": "Second work",
                        "goal": "GOAL-1",
                        "palari": "PALARI-1",
                    }
                )
                data["work_items"][0]["dependency_ids"] = dependency_ids
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(data, FIXTURES)

        dependency_cycle = fixture_data()
        dependency_cycle["work_items"][0]["dependency_ids"] = ["WORK-2"]
        dependency_cycle["work_items"].append(
            {
                "id": "WORK-2",
                "title": "Second work",
                "goal": "GOAL-1",
                "palari": "PALARI-1",
                "dependency_ids": ["WORK-1"],
            }
        )
        with self.assertRaisesRegex(WorkspaceError, "dependency graph contains a cycle"):
            Workspace.from_raw(dependency_cycle, FIXTURES)

    def test_workbench_references_inheritance_and_cycles(self) -> None:
        workspace = Workspace.from_raw(bounded_workspace_data(), FIXTURES)
        self.assertEqual(workspace.work_items[0].workbench_id, "WORKBENCH-CHILD")

        missing = bounded_workspace_data()
        missing["work_items"][0]["workbench_id"] = "WORKBENCH-MISSING"
        with self.assertRaisesRegex(WorkspaceError, "workbench_id references missing id"):
            Workspace.from_raw(missing, FIXTURES)

        cycle = bounded_workspace_data()
        cycle["workbenches"][0]["parent_workbench_id"] = "WORKBENCH-CHILD"
        with self.assertRaisesRegex(WorkspaceError, "workbenches parent graph contains a cycle"):
            Workspace.from_raw(cycle, FIXTURES)

    def test_workbench_source_and_output_boundaries_fail_closed(self) -> None:
        outside_source = bounded_workspace_data()
        outside_source["sources"].append(
            {
                "id": "SOURCE-OUTSIDE",
                "label": "Outside source",
                "allowed_palaris": ["PALARI-1"],
            }
        )
        outside_source["work_items"][0]["allowed_sources"] = ["SOURCE-OUTSIDE"]
        with self.assertRaisesRegex(WorkspaceError, "outside workbench WORKBENCH-CHILD"):
            Workspace.from_raw(outside_source, FIXTURES)

        outside_output = bounded_workspace_data()
        outside_output["work_items"][0]["output_targets"] = ["private/summary.md"]
        outside_output["work_items"][0]["path_intents"] = []
        with self.assertRaisesRegex(WorkspaceError, "outside workbench WORKBENCH-CHILD"):
            Workspace.from_raw(outside_output, FIXTURES)

    def test_source_and_memory_references_fail_closed(self) -> None:
        cases: tuple[tuple[Callable[[dict[str, Any]], None], str], ...] = (
            (
                lambda data: data["sources"][0].__setitem__(
                    "allowed_palaris", ["PALARI-MISSING"]
                ),
                "allowed_palaris references missing id PALARI-MISSING",
            ),
            (
                lambda data: data["sources"][0].__setitem__(
                    "steward_human", "HUMAN-MISSING"
                ),
                "steward_human references missing id HUMAN-MISSING",
            ),
            (
                lambda data: data["palaris"][0].__setitem__(
                    "memory_sources", ["SOURCE-MISSING"]
                ),
                "memory_sources references missing id SOURCE-MISSING",
            ),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                data = fixture_data()
                mutate(data)
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(data, FIXTURES)

    def test_receipt_source_actor_and_external_write_boundaries_fail_closed(self) -> None:
        fixtures = (
            ("invalid-receipt-unallowed-source.json", "includes unallowed source SOURCE-2"),
            ("invalid-receipt-missing-source.json", "references missing id SOURCE-MISSING"),
            ("invalid-receipt-external-write.json", "requires allowed action external_write"),
            ("invalid-receipt-actor.json", "must match attempt actor PALARI-1"),
        )
        for fixture, expected in fixtures:
            with self.subTest(fixture=fixture):
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.load(FIXTURES / fixture)

    def test_retired_write_aliases_do_not_grant_external_write_authority(self) -> None:
        for action in ("write", "write_external"):
            with self.subTest(action=action):
                data = fixture_data("invalid-receipt-external-write.json")
                data["work_items"][0]["allowed_actions"] = [action]
                data["work_items"][0]["forbidden_actions"] = []

                with self.assertRaisesRegex(
                    WorkspaceError, "requires allowed action external_write"
                ):
                    Workspace.from_raw(data, FIXTURES)

        canonical = fixture_data("invalid-receipt-external-write.json")
        canonical["work_items"][0]["allowed_actions"] = ["external_write"]
        canonical["work_items"][0]["forbidden_actions"] = []

        self.assertEqual(Workspace.from_raw(canonical, FIXTURES).name, canonical["name"])


class ScopeValidationTests(unittest.TestCase):
    def test_exact_path_intents_load(self) -> None:
        data = bounded_workspace_data()
        data["work_items"][0]["output_targets"] = ["notes"]
        data["workbenches"][0]["output_target_ids"] = ["notes"]
        data["work_items"][0]["path_intents"] = [
            {"path": "notes/new.md", "intent": "create"},
            {"path": "notes/summary.md", "intent": "modify"},
            {"path": "notes/old.md", "intent": "delete"},
        ]

        workspace = Workspace.from_raw(data, FIXTURES)

        self.assertEqual(
            [item["intent"] for item in workspace.work_items[0].path_intents],
            ["create", "modify", "delete"],
        )

    def test_invalid_path_intent_contracts_fail_closed(self) -> None:
        cases: tuple[tuple[list[dict[str, Any]], str], ...] = (
            ([{"path": "private.txt", "intent": "delete"}], "outside declared boundaries"),
            ([{"path": "notes/../private.txt", "intent": "delete"}], "unsafe path"),
            ([{"path": "notes\\summary.md", "intent": "modify"}], "not in canonical"),
            ([{"path": "notes/summary.md", "intent": "rename"}], "unsupported value"),
            (
                [
                    {"path": "notes/summary.md", "intent": "modify"},
                    {"path": "notes/summary.md", "intent": "delete"},
                ],
                "contains duplicate path",
            ),
            (
                [
                    {"path": "notes", "intent": "modify"},
                    {"path": "notes/summary.md", "intent": "modify"},
                ],
                "paths overlap by prefix",
            ),
            (
                [{"path": "notes/line\nbreak.md", "intent": "modify"}],
                "unsafe non-printable or control characters",
            ),
        )
        for intents, expected in cases:
            with self.subTest(intents=intents):
                data = bounded_workspace_data()
                if expected == "paths overlap by prefix":
                    data["work_items"][0]["output_targets"] = ["notes"]
                    data["workbenches"][0]["output_target_ids"] = ["notes"]
                data["work_items"][0]["path_intents"] = intents
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(data, FIXTURES)

    def test_attempt_file_boundaries_fail_closed(self) -> None:
        cases = (
            ("changed_files", ["private.txt"], {}, "outside declared boundaries"),
            ("changed_files", ["notes/../private.txt"], {}, "contains unsafe path"),
            (
                "changed_files",
                ["notes/summary.md"],
                {"forbidden_paths": ["notes"]},
                "includes forbidden path",
            ),
            ("output_targets", ["private.txt"], {}, "outside declared boundaries"),
        )
        for field, value, additions, expected in cases:
            with self.subTest(field=field, value=value):
                data = bounded_workspace_data()
                attempt = data["attempts"][0]
                attempt[field] = value
                attempt.update(additions)
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(data, FIXTURES)

    def test_receipt_output_and_undo_boundaries_fail_closed(self) -> None:
        cases = (
            ("outputs_created", ["private.txt"]),
            ("undo_refs", ["delete private.txt"]),
        )
        for field, value in cases:
            with self.subTest(field=field):
                data = bounded_workspace_data()
                data["receipts"][0][field] = value
                with self.assertRaisesRegex(WorkspaceError, "outside declared boundaries"):
                    Workspace.from_raw(data, FIXTURES)

    def test_absence_tombstone_requires_an_exact_delete_intent(self) -> None:
        data = bounded_workspace_data()
        data["evidence_runs"] = [
            {
                "id": "EVIDENCE-DELETE",
                "work_item_id": "WORK-1",
                "attempt_id": "ATTEMPT-1",
                "head_sha": "head-1",
                "status": "passed",
                "artifacts": ["notes/summary.md"],
                "artifact_hashes": [
                    {
                        "path": "notes/summary.md",
                        "sha256": "sha256:absent",
                        "status": "absent",
                    }
                ],
            }
        ]
        with self.assertRaisesRegex(WorkspaceError, "without a matching delete path intent"):
            Workspace.from_raw(data, FIXTURES)

        data["work_items"][0]["path_intents"][0]["intent"] = "delete"
        workspace = Workspace.from_raw(data, FIXTURES)
        self.assertEqual(workspace.evidence_runs[0].artifact_hashes[0]["status"], "absent")


class SplitWorkspaceCompatibilityTests(unittest.TestCase):
    def test_split_collection_reader_loads_committed_fixture(self) -> None:
        workspace = Workspace.load(FIXTURES / "split-workspace")

        self.assertEqual(workspace.name, "Split Workspace Fixture")
        self.assertEqual([item.id for item in workspace.work_items], ["WORK-SPLIT"])

    def test_split_reader_rejects_duplicate_ids(self) -> None:
        with self.copied_split_workspace() as root:
            data_path = root / "workspace.json"
            data = json.loads(data_path.read_text(encoding="utf-8"))
            data["work_items"] = [
                {
                    "id": "WORK-SPLIT",
                    "title": "Duplicate root work",
                    "goal": "GOAL-SPLIT",
                    "palari": "PALARI-SPLIT",
                }
            ]
            data_path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(WorkspaceError, "contains duplicate id: WORK-SPLIT"):
                Workspace.load(root)

    def test_split_reader_rejects_unsafe_missing_and_malformed_files(self) -> None:
        cases = (
            ("../outside.json", "must be workspace-relative"),
            ("/tmp/outside.json", "must be workspace-relative"),
            ("records/missing.json", "file not found"),
        )
        for relative_path, expected in cases:
            with self.subTest(relative_path=relative_path):
                with self.copied_split_workspace() as root:
                    data_path = root / "workspace.json"
                    data = json.loads(data_path.read_text(encoding="utf-8"))
                    data["collection_files"]["work_items"] = [relative_path]
                    data_path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaisesRegex(WorkspaceError, expected):
                        Workspace.load(root)

        with self.copied_split_workspace() as root:
            (root / "records" / "work-items.json").write_text(
                json.dumps({"id": "WORK-SPLIT"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkspaceError, "must contain a list of objects"):
                Workspace.load(root)

    def test_split_reader_rejects_unknown_collection(self) -> None:
        with self.copied_split_workspace() as root:
            data_path = root / "workspace.json"
            data = json.loads(data_path.read_text(encoding="utf-8"))
            data["collection_files"]["not_a_collection"] = ["records/work-items.json"]
            data_path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(WorkspaceError, "unknown collection"):
                Workspace.load(root)

    def test_authoring_refuses_parked_split_storage(self) -> None:
        with self.copied_split_workspace() as root:
            with self.assertRaisesRegex(
                WorkspaceError,
                "authoring writes are not supported for split workspaces",
            ):
                write_store(load_store(root))

    def copied_split_workspace(self):
        source = FIXTURES / "split-workspace"
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name) / "split-workspace"
        shutil.copytree(source, root)

        class CopiedSplitWorkspace:
            def __enter__(self) -> Path:
                return root

            def __exit__(self, *args: object) -> None:
                directory.cleanup()

        return CopiedSplitWorkspace()


class JournaledStoreTests(unittest.TestCase):
    def test_initial_checkpoint_and_update_use_v2_journal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = self.create_workspace(Path(directory))
            journal_path = data_path.parent / ".palari" / "governance-journal.v2.jsonl"
            self.assertTrue(journal_path.is_file())
            initial_record_count = len(journal_path.read_text(encoding="utf-8").splitlines())

            store = load_store(data_path)
            store.data["name"] = "Updated through current store"
            write_store(store)

            self.assertEqual(load_store(data_path).data["name"], "Updated through current store")
            records = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertGreater(len(records), initial_record_count)
            self.assertEqual(
                {record["schema_version"] for record in records},
                {"palari.governance-journal.v2"},
            )
            self.assertFalse(self.lock_path(data_path).exists())

    def test_compare_and_swap_rejects_stale_writer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = self.create_workspace(Path(directory))
            stale = load_store(data_path)
            fresh = load_store(data_path)
            fresh.data["name"] = "Fresh write wins"
            write_store(fresh)

            stale.data["name"] = "Stale write loses"
            with self.assertRaisesRegex(WorkspaceError, "workspace changed since it was loaded"):
                write_store(stale)

            self.assertEqual(load_store(data_path).data["name"], "Fresh write wins")

    def test_dead_pid_lock_is_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = self.create_workspace(Path(directory))
            lock_path = self.lock_path(data_path)
            lock_path.write_text("pid=999999999\n", encoding="utf-8")
            store = load_store(data_path)
            store.data["name"] = "Recovered from dead lock"

            write_store(store)

            self.assertEqual(load_store(data_path).data["name"], "Recovered from dead lock")
            self.assertFalse(lock_path.exists())

    def test_old_unowned_lock_is_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = self.create_workspace(Path(directory))
            lock_path = self.lock_path(data_path)
            lock_path.write_text("not a parseable lock\n", encoding="utf-8")
            old_time = time.time() - 120
            os.utime(lock_path, (old_time, old_time))
            store = load_store(data_path)
            store.data["name"] = "Recovered from old lock"

            write_store(store)

            self.assertEqual(load_store(data_path).data["name"], "Recovered from old lock")
            self.assertFalse(lock_path.exists())

    def test_live_process_lock_is_never_reclaimed_for_age(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = self.create_workspace(Path(directory))
            lock_path = self.lock_path(data_path)
            lock_path.write_text(f"pid={os.getpid()}\n", encoding="utf-8")
            old_time = time.time() - 120
            os.utime(lock_path, (old_time, old_time))
            store = load_store(data_path)
            store.data["name"] = "Must stay blocked"

            with self.assertRaisesRegex(
                WorkspaceError,
                "workspace write is already in progress; retry shortly",
            ):
                write_store(store)

            self.assertTrue(lock_path.exists())

    @staticmethod
    def create_workspace(root: Path) -> Path:
        data_path = root / "workspace.json"
        write_store(WorkspaceStore(data_path=data_path, data=fixture_data()))
        return data_path

    @staticmethod
    def lock_path(data_path: Path) -> Path:
        return data_path.parent / ".palari" / "locks" / "workspace.json.lock"


if __name__ == "__main__":
    unittest.main()
