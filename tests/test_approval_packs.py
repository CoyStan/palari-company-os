from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.approval_packs import (
    _batch_policy,
    apply_pack_decision,
    build_approval_inbox,
    canonical_pack_bytes,
    evaluate_approval_pack,
)
from palari_company_os.evidence_manifest import (
    stamp_evidence_record,
    stamp_receipt_record,
)
from palari_company_os.governance_binding import (
    current_review_binding,
    review_proof_hash,
)
from palari_company_os.governance_journal import verify_journal
from palari_company_os.pcaw_canonical import canonical_sha256
from palari_company_os.store import WorkspaceStore, load_store, write_store
from palari_company_os.workspace import Workspace, WorkspaceError


FIXTURE = REPO_ROOT / "tests" / "fixtures" / "workspaces" / "valid-workspace.json"
OUTPUT = "artifacts/overnight-result.txt"


class InjectedCrash(RuntimeError):
    pass


class ApprovalPackTests(unittest.TestCase):
    def test_interaction_measurement_is_one_session_and_action_for_1_10_100(self) -> None:
        for count in (1, 10, 100):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                data_path = make_ready_workspace(Path(directory), count=count)
                store = load_store(data_path)
                inbox = build_approval_inbox(Workspace.load(data_path), store.data)
                measurement = inbox["interaction_measurement"]

                self.assertEqual(measurement["review_sessions"], 1)
                self.assertEqual(measurement["attributable_approval_actions"], 1)
                self.assertEqual(measurement["individual_proof_records"], count)
                self.assertEqual(
                    measurement["commands_or_clicks"],
                    {"individual_approval_baseline": count, "approval_pack": 1},
                )

    def test_incomplete_member_remains_visible_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            incomplete = load_store(data_path)
            incomplete.data["review_verdicts"] = []
            write_store(incomplete)

            store = load_store(data_path)
            inbox = build_approval_inbox(Workspace.load(data_path), store.data)

        self.assertEqual(inbox["counts"]["blocked"], 1)
        self.assertEqual(inbox["evaluations"][0]["members"][0]["state"], "blocked")

    def test_cli_exposes_inbox_detail_and_one_pack_decision_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            inbox = run_json(
                "--workspace",
                str(data_path),
                "queue",
                "--approval-inbox",
                "--select",
                "WORK-001",
                "--json",
            )
            detail = run_json(
                "--workspace",
                str(data_path),
                "detail",
                "WORK-001",
                "--json",
            )
            decision = run_json(
                "--workspace",
                str(data_path),
                "human-decision",
                "pack",
                "--pack-digest",
                inbox["packs"][0]["pack_digest"],
                "--human-id",
                "HUMAN-PRODUCT",
                "--approve-eligible",
                "--pack-member",
                "WORK-001",
                "--reason",
                "CLI morning review.",
                "--json",
            )

        self.assertEqual(inbox["schema_version"], "palari.approval-inbox.v1")
        self.assertIn("--pack-member WORK-001", inbox["approval_commands"][0]["approve_eligible"])
        self.assertTrue(detail["approval_pack"]["available"])
        self.assertEqual(decision["executed"], ["WORK-001"])

    def test_risk_friction_policy_keeps_governed_effects_individually_gated(self) -> None:
        def work(**overrides: object) -> SimpleNamespace:
            values = {
                "title": "Prepare local record",
                "scope": "Prepare bounded local state",
                "allowed_actions": ["write local record"],
                "allowed_resources": ["artifacts/result.txt"],
                "forbidden_actions": [],
                "risk": "R2",
            }
            values.update(overrides)
            return SimpleNamespace(**values)

        self.assertEqual(_batch_policy(work(), [])["class"], "local-draft")
        self.assertTrue(_batch_policy(work(title="Scoped memory proposal"), [])["batchable"])
        self.assertFalse(_batch_policy(work(allowed_actions=["send email"]), [])["batchable"])
        self.assertFalse(_batch_policy(work(scope="expand access permission"), [])["batchable"])
        self.assertFalse(_batch_policy(work(scope="approve legal filing"), [])["batchable"])
        self.assertFalse(_batch_policy(work(risk="R4"), [])["batchable"])

    def test_one_hundred_items_keep_individual_proof_in_one_review_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=100)
            store = load_store(data_path)
            workspace = Workspace.load(data_path)

            first = build_approval_inbox(workspace, store.data)
            second = build_approval_inbox(workspace, store.data)
            pack = first["packs"][0]

        self.assertEqual(first["counts"]["packs"], 1)
        self.assertEqual(first["counts"]["items"], 100)
        self.assertEqual(first["counts"]["eligible"], 100)
        self.assertEqual(first["interaction_measurement"]["review_sessions"], 1)
        self.assertEqual(first["interaction_measurement"]["attributable_approval_actions"], 1)
        self.assertEqual(
            first["interaction_measurement"]["commands_or_clicks"],
            {"individual_approval_baseline": 100, "approval_pack": 1},
        )
        self.assertEqual(
            first["interaction_measurement"]["time_to_understand_proxy"]["pack_summaries"],
            1,
        )
        self.assertEqual(len({item["member_digest"] for item in pack["members"]}), 100)
        self.assertEqual(canonical_pack_bytes(pack), canonical_pack_bytes(second["packs"][0]))

    def test_one_action_approves_and_executes_every_exact_eligible_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=3)
            store = load_store(data_path)
            inbox = build_approval_inbox(Workspace.load(data_path), store.data)
            pack = inbox["packs"][0]

            result = apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="Morning review accepted the exact local bundle.",
            )
            replay = apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="Morning review accepted the exact local bundle.",
            )
            final = load_store(data_path)
            journal = verify_journal(final.data_path, final.data)

        self.assertEqual(result["executed"], ["WORK-001", "WORK-002", "WORK-003"])
        self.assertEqual(replay["status"], "already-applied")
        self.assertTrue(replay["idempotent"])
        self.assertTrue(all(item["status"] == "completed" for item in final.data["work_items"]))
        decisions = final.data["human_decisions"]
        self.assertEqual(len(decisions), 3)
        self.assertEqual(sum(bool(item.get("approval_pack_manifest")) for item in decisions), 1)
        self.assertTrue(journal["chain_valid"])
        self.assertEqual(journal["committed_transactions"], 2)

    def test_changed_dependency_stales_descendants_but_not_unrelated_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(
                Path(directory),
                count=3,
                dependencies={"WORK-002": ["WORK-001"]},
            )
            store = load_store(data_path)
            workspace = Workspace.load(data_path)
            pack = build_approval_inbox(workspace, store.data)["packs"][0]

            changed = load_store(data_path)
            changed.data["work_items"][0]["scope"] = "Changed after pack review."
            write_store(changed)
            evaluation = evaluate_approval_pack(Workspace.load(data_path), pack)
            states = {item["id"]: item["state"] for item in evaluation["members"]}

        self.assertEqual(states["WORK-001"], "stale")
        self.assertEqual(states["WORK-002"], "blocked")
        self.assertEqual(states["WORK-003"], "eligible")

    def test_pending_quorum_cannot_execute_changed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1, approvals=2)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]

            first = apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="First quorum vote.",
            )
            (root / OUTPUT).write_text("mutated after approval\n", encoding="utf-8")
            evaluation = evaluate_approval_pack(Workspace.load(data_path), pack)
            with self.assertRaisesRegex(WorkspaceError, "stale"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    human_id="HUMAN-SECOND",
                    approve_eligible=True,
                    reason="Second quorum vote after mutation.",
                )

        self.assertEqual(first["executed"], [])
        self.assertEqual(first["parked"], ["WORK-001"])
        self.assertEqual(evaluation["members"][0]["state"], "stale")

    def test_changed_batch_policy_stales_pending_quorum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1, approvals=2)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            first = apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="First quorum vote before policy change.",
            )
            changed = load_store(data_path)
            changed.data["work_items"][0]["title"] = "Approve legal filing and payment"
            write_store(changed)

            evaluation = evaluate_approval_pack(Workspace.load(data_path), pack)
            with self.assertRaisesRegex(WorkspaceError, "stale"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    human_id="HUMAN-SECOND",
                    approve_eligible=True,
                    reason="Second vote must not reuse an older risk policy.",
                )
            with self.assertRaisesRegex(WorkspaceError, "decision is stale"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    human_id="HUMAN-SECOND",
                    reject=["WORK-001"],
                    reason="A stale pack cannot authorize rejection either.",
                )

        self.assertEqual(first["executed"], [])
        self.assertEqual(evaluation["members"][0]["state"], "stale")

    def test_stored_pack_cannot_expand_a_narrowed_member_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=3, approvals=2)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="First exact full-pack quorum vote.",
            )

            with self.assertRaisesRegex(WorkspaceError, "selection does not match"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    human_id="HUMAN-SECOND",
                    approve_eligible=True,
                    pack_members=["WORK-001"],
                    reason="A narrow request must not expand to the stored full pack.",
                )
            decision_count = len(load_store(data_path).data["human_decisions"])

        self.assertEqual(decision_count, 3)

    def test_narrowed_pack_reports_unfinished_outside_dependency_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(
                Path(directory),
                count=2,
                dependencies={"WORK-002": ["WORK-001"]},
            )
            store = load_store(data_path)
            inbox = build_approval_inbox(
                Workspace.load(data_path),
                store.data,
                selected_work_ids=["WORK-002"],
            )

        item = inbox["evaluations"][0]["members"][0]
        self.assertEqual(item["state"], "blocked")
        self.assertIn("outside this pack is unfinished", item["reasons"][0])

    def test_review_identity_and_pack_transplant_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            with self.assertRaisesRegex(WorkspaceError, "distinct from builder and reviewer"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    human_id="HUMAN-REVIEW",
                    approve_eligible=True,
                )

            changed = load_store(data_path)
            changed.data["name"] = "Different exact pack base"
            write_store(changed)
            with self.assertRaisesRegex(WorkspaceError, "missing or stale"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    human_id="HUMAN-PRODUCT",
                    approve_eligible=True,
                )

    def test_reject_and_defer_require_the_work_capability(self) -> None:
        for action in ("reject", "defer"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                data_path = make_ready_workspace(Path(directory), count=1)
                store = load_store(data_path)
                pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]

                with self.assertRaisesRegex(WorkspaceError, "lacks required approval capability"):
                    apply_pack_decision(
                        str(data_path),
                        pack_digest=pack["pack_digest"],
                        human_id="HUMAN-UNQUALIFIED",
                        **{action: ["WORK-001"]},
                    )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                reject=["WORK-001"],
            )
            manufactured = load_store(data_path).data
            manufactured["human_decisions"][0]["human_id"] = "HUMAN-UNQUALIFIED"

            with self.assertRaisesRegex(WorkspaceError, "lacks required approval capability"):
                Workspace.from_raw(manufactured, root)

    def test_pack_manifest_rejects_unknown_nested_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]

        bad_base = deepcopy(pack)
        bad_base["base"]["unknown"] = "self-consistent but unsupported"
        bad_base["pack_digest"] = canonical_sha256(
            {key: value for key, value in bad_base.items() if key != "pack_digest"}
        )
        with self.assertRaisesRegex(WorkspaceError, "base has unknown or missing fields"):
            canonical_pack_bytes(bad_base)

        bad_member = deepcopy(pack)
        bad_member["members"][0]["unknown"] = "self-consistent but unsupported"
        bad_member["members"][0]["member_digest"] = canonical_sha256(
            {
                key: value
                for key, value in bad_member["members"][0].items()
                if key != "member_digest"
            }
        )
        bad_member["pack_digest"] = canonical_sha256(
            {key: value for key, value in bad_member.items() if key != "pack_digest"}
        )
        with self.assertRaisesRegex(WorkspaceError, r"members\[\] has unknown or missing fields"):
            canonical_pack_bytes(bad_member)

    def test_terminal_pack_proof_is_historical_but_changed_bytes_report_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="Complete exact local output.",
            )
            (root / OUTPUT).write_text("changed after terminal record\n", encoding="utf-8")

            historical = Workspace.load(data_path)
            evaluation = evaluate_approval_pack(historical, pack)

        self.assertEqual(historical.work_item("WORK-001").status, "completed")
        self.assertEqual(evaluation["members"][0]["state"], "stale")

    def test_stored_member_binding_cannot_be_copied_between_pack_items(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=2)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="Approve exact two-member pack.",
            )
            raw = load_store(data_path).data
            first, second = raw["human_decisions"]
            second["approval_pack_member_digest"] = first["approval_pack_member_digest"]

            with self.assertRaisesRegex(WorkspaceError, "transplanted or stale"):
                Workspace.from_raw(raw, root)

    def test_rejection_blocks_dependent_and_preserves_unrelated_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(
                Path(directory),
                count=3,
                dependencies={"WORK-002": ["WORK-001"]},
            )
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            result = apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve=["WORK-003"],
                reject=["WORK-001"],
                reason="Reject parent; accept unrelated item.",
            )
            evaluation = evaluate_approval_pack(Workspace.load(data_path), pack)
            states = {item["id"]: item["state"] for item in evaluation["members"]}

        self.assertEqual(result["executed"], ["WORK-003"])
        self.assertEqual(states["WORK-001"], "rejected")
        self.assertEqual(states["WORK-002"], "blocked")
        self.assertEqual(states["WORK-003"], "executed")

    def test_interrupted_pack_decision_retries_fail_closed_and_idempotently(self) -> None:
        for point in (
            "before_prepare_append",
            "after_prepare_fsync",
            "before_apply",
            "after_apply",
            "before_commit_append",
            "after_commit_fsync",
        ):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                data_path = make_ready_workspace(Path(directory), count=1)
                store = load_store(data_path)
                pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
                with self.assertRaisesRegex(InjectedCrash, point):
                    apply_pack_decision(
                        str(data_path),
                        pack_digest=pack["pack_digest"],
                        human_id="HUMAN-PRODUCT",
                        approve_eligible=True,
                        reason="Crash boundary test.",
                        crash_hook=crash_at(point),
                    )
                retried = apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    human_id="HUMAN-PRODUCT",
                    approve_eligible=True,
                    reason="Crash boundary test.",
                )
                final = load_store(data_path)
                report = verify_journal(final.data_path, final.data)

                self.assertIn(retried["status"], {"applied", "already-applied"})
                self.assertTrue(report["chain_valid"])
                self.assertIsNone(report["pending"])
                self.assertEqual(len(final.data["human_decisions"]), 1)


def make_ready_workspace(
    root: Path,
    *,
    count: int,
    dependencies: dict[str, list[str]] | None = None,
    approvals: int = 1,
) -> Path:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["name"] = "Approval Pack Fixture"
    raw["humans"] = [
        {
            "id": "HUMAN-PRODUCT",
            "name": "Product approver",
            "approval_capabilities": ["product"],
        },
        {
            "id": "HUMAN-SECOND",
            "name": "Second product approver",
            "approval_capabilities": ["product"],
        },
        {"id": "HUMAN-REVIEW", "name": "Independent reviewer"},
        {"id": "HUMAN-UNQUALIFIED", "name": "Unqualified human"},
    ]
    raw["palaris"][0]["owner_human"] = "HUMAN-PRODUCT"
    raw["palaris"][0]["active_work"] = []
    raw["work_items"] = []
    raw["attempts"] = []
    raw["receipts"] = []
    raw["evidence_runs"] = []
    raw["review_verdicts"] = []
    raw["human_decisions"] = []
    raw["acceptance_records"] = []
    raw["outcomes"] = []
    raw["decisions"] = []
    raw["integration_plans"] = []
    raw["integration_outbox"] = []
    raw["proposals"] = []
    root.mkdir(parents=True, exist_ok=True)
    output = root / OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("exact reviewed bytes\n", encoding="utf-8")
    dependencies = dependencies or {}
    base_time = datetime(2030, 1, 1, tzinfo=timezone.utc)

    for index in range(1, count + 1):
        work_id = f"WORK-{index:03d}"
        attempt_id = f"ATTEMPT-{index:03d}"
        head = f"head-{index:03d}"
        raw["work_items"].append(
            {
                "id": work_id,
                "title": f"Prepare local governed draft {index:03d}",
                "goal": "GOAL-1",
                "palari": "PALARI-SOFIA",
                "dependency_ids": dependencies.get(work_id, []),
                "risk": "R2",
                "intensity": "standard",
                "status": "in-review",
                "scope": "Prepare one bounded local draft without external effects.",
                "allowed_resources": [OUTPUT],
                "allowed_actions": ["write local draft"],
                "output_targets": [OUTPUT],
                "forbidden_actions": ["external writes", "send messages"],
                "acceptance_target": "Human confirms the exact reviewed local draft.",
                "current_attempt": attempt_id,
                "required_approval_count": approvals,
                "required_approval_capability": "product",
            }
        )
        raw["attempts"].append(
            {
                "id": attempt_id,
                "work_item_id": work_id,
                "actor": "PALARI-SOFIA",
                "status": "complete",
                "workspace_path": str(root),
                "base_sha": "base",
                "head_sha": head,
                "commits": [head],
                "changed_files": [OUTPUT],
                "allowed_paths": [OUTPUT],
                "cleanliness": "clean",
                "output_targets": [OUTPUT],
                "started_at": timestamp(base_time + timedelta(seconds=index * 10)),
                "updated_at": timestamp(base_time + timedelta(seconds=index * 10 + 1)),
            }
        )
        receipt = stamp_receipt_record(
            {
                "id": f"RECEIPT-{index:03d}",
                "work_item_id": work_id,
                "attempt_id": attempt_id,
                "actor": "PALARI-SOFIA",
                "actions_taken": ["prepared bounded local draft"],
                "outputs_created": [OUTPUT],
                "timestamp": timestamp(base_time + timedelta(seconds=index * 10 + 2)),
            },
            raw["receipts"],
        )
        raw["receipts"].append(receipt)
        evidence = stamp_evidence_record(
            {
                "id": f"EVIDENCE-{index:03d}",
                "work_item_id": work_id,
                "attempt_id": attempt_id,
                "head_sha": head,
                "status": "passed",
                "base_ref": "base",
                "commands": ["offline deterministic check"],
                "artifacts": [OUTPUT],
                "receipt_hash": receipt["receipt_hash"],
                "summary": "Exact local bytes verified.",
                "freshness": "fresh",
                "timestamp": timestamp(base_time + timedelta(seconds=index * 10 + 3)),
            },
            root,
            attempts=raw["attempts"],
        )
        raw["evidence_runs"].append(evidence)

    workspace = Workspace.from_raw(raw, root)
    for index in range(1, count + 1):
        work_id = f"WORK-{index:03d}"
        binding, errors = current_review_binding(
            workspace,
            work_id,
            require_output_coverage=True,
        )
        if errors:
            raise AssertionError(errors)
        review = {
            "id": f"REVIEW-{index:03d}",
            "work_item_id": work_id,
            "reviewed_head": f"head-{index:03d}",
            "reviewer": "HUMAN-REVIEW",
            "verdict": "accept-ready",
            **binding,
            "findings": [],
            "checks_inspected": ["offline deterministic check"],
            "residual_risks": ["Human usefulness judgment remains required."],
            "timestamp": timestamp(base_time + timedelta(seconds=index * 10 + 4)),
        }
        review["proof_hash"] = review_proof_hash(review)
        raw["review_verdicts"].append(review)
    Workspace.from_raw(raw, root)
    data_path = root / "workspace.json"
    write_store(WorkspaceStore(data_path=data_path, data=deepcopy(raw)))
    return data_path


def timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


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
