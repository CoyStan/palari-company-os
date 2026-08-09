from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.approval_packs import (
    _batch_policy,
    apply_pack_decision as _apply_pack_decision,
    build_approval_inbox,
    evaluate_approval_pack,
    validate_pack_manifest,
)
from palari_company_os.approval_presentations import (
    approval_presentation_digest,
    build_approval_presentation,
)
from palari_company_os.agent_handoff import (
    _human_approval_handoff,
    build_agent_handoff,
)
from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.evidence_manifest import (
    stamp_evidence_record,
    stamp_receipt_record,
    verify_evidence,
)
from palari_company_os.governance_binding import (
    current_review_binding,
    current_review_binding_errors,
    review_proof_hash,
)
from palari_company_os.governance_journal import (
    JournalVerificationContext,
    journal_file_path,
    verify_journal,
    verify_workspace_journal,
)
from palari_company_os.pcaw_canonical import canonical_sha256
from palari_company_os.simple_approval import SimpleApprovalError, approve_work
from palari_company_os.store import WorkspaceStore, load_store, write_store
from palari_company_os.workspace import Workspace, WorkspaceError


FIXTURE = REPO_ROOT / "tests" / "fixtures" / "workspaces" / "valid-workspace.json"
OUTPUT = "artifacts/overnight-result.txt"


class InjectedCrash(RuntimeError):
    pass


def apply_pack_decision(
    workspace_path: str,
    *,
    pack_digest: str,
    presentation_digest: str = "",
    **kwargs: object,
) -> dict[str, object]:
    """Keep older tests concise while every production call stays presentation-bound."""

    store = load_store(workspace_path)
    existing = [
        item
        for item in store.data.get("human_decisions", [])
        if item.get("approval_pack_digest") == pack_digest
        and item.get("human_id") == kwargs.get("human_id")
    ]
    if not presentation_digest and existing:
        presentation_digest = str(existing[0].get("approval_presentation_digest") or "")
    if not presentation_digest:
        workspace = Workspace.load(workspace_path)
        inbox = build_approval_inbox(
            workspace,
            store.data,
            selected_work_ids=kwargs.get("pack_members", ()),
        )
        pack = next(
            (item for item in inbox["packs"] if item["pack_digest"] == pack_digest),
            None,
        )
        if pack is None:
            stored = [
                item.get("approval_pack_manifest")
                for item in store.data.get("human_decisions", [])
                if item.get("approval_pack_digest") == pack_digest
                and item.get("approval_pack_manifest")
            ]
            pack = stored[0] if stored else None
        if pack is None:
            raise AssertionError(f"test could not resolve approval pack {pack_digest}")
        presentation = build_approval_presentation(
            workspace,
            pack,
            evaluate_approval_pack(workspace, pack),
        )
        presentation_digest = approval_presentation_digest(presentation, pack)
    return _apply_pack_decision(
        workspace_path,
        pack_digest=pack_digest,
        presentation_digest=presentation_digest,
        **kwargs,
    )


class ApprovalPackTests(unittest.TestCase):
    def test_injected_journal_context_preserves_output_and_reuses_one_verification(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(
                Path(directory),
                count=2,
                dependencies={"WORK-002": ["WORK-001"]},
            )
            store = load_store(data_path)
            workspace = Workspace.load(data_path)
            baseline = build_approval_inbox(workspace, store.data)
            baseline_evaluation = evaluate_approval_pack(
                workspace,
                baseline["packs"][0],
            )
            context = JournalVerificationContext()

            with (
                patch(
                    "palari_company_os.governance_journal.verify_workspace_journal",
                    wraps=verify_workspace_journal,
                ) as verify_journal_once,
                patch(
                    "palari_company_os.pcaw_workspace.verify_evidence",
                    wraps=verify_evidence,
                ) as evidence_checks,
                patch(
                    "palari_company_os.pcaw_workspace.current_review_binding_errors",
                    wraps=current_review_binding_errors,
                ) as review_checks,
            ):
                injected = build_approval_inbox(
                    workspace,
                    store.data,
                    journal_context=context,
                )
                evaluated = evaluate_approval_pack(
                    workspace,
                    injected["packs"][0],
                    journal_context=context,
                )

        self.assertEqual(injected, baseline)
        self.assertEqual(evaluated, baseline_evaluation)
        self.assertEqual(verify_journal_once.call_count, 1)
        self.assertGreater(len(evidence_checks.call_args_list), 2)
        self.assertGreater(len(review_checks.call_args_list), 2)
        self.assertTrue(
            all(
                call.kwargs["journal_context"] is context
                for call in evidence_checks.call_args_list
            )
        )
        self.assertTrue(
            all(
                call.kwargs["journal_context"] is context
                for call in review_checks.call_args_list
            )
        )

    def test_injected_journal_context_reverifies_changed_witness_and_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            store = load_store(data_path)
            workspace = Workspace.load(data_path)
            context = JournalVerificationContext()
            journal_path = data_path.parent / ".palari" / "governance-journal.v2.jsonl"

            with patch(
                "palari_company_os.governance_journal.verify_workspace_journal",
                wraps=verify_workspace_journal,
            ) as verify:
                build_approval_inbox(
                    workspace,
                    store.data,
                    journal_context=context,
                )
                journal_path.write_text(
                    journal_path.read_text(encoding="utf-8") + "{}\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    WorkspaceError,
                    "verified, committed governance journal checkpoint",
                ):
                    build_approval_inbox(
                        workspace,
                        store.data,
                        journal_context=context,
                    )

        self.assertEqual(verify.call_count, 2)

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
                self.assertEqual(inbox["primary_action"]["mode"], "approve-eligible")
                self.assertEqual(inbox["primary_action"]["human_actions"], 1)
                modes = {item["id"]: item for item in inbox["approval_modes"]}
                self.assertTrue(modes["approve-eligible"]["available"])
                self.assertFalse(modes["review-and-accept"]["available"])

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
        self.assertEqual(
            inbox["evaluations"][0]["members"][0]["resolution"]["class"],
            "independent-review",
        )
        self.assertFalse(inbox["primary_action"]["available"])
        self.assertEqual(inbox["approval_commands"], [])

    def test_legacy_review_that_consumed_the_only_approver_stays_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            store = load_store(data_path)
            for human in store.data["humans"]:
                human["approval_capabilities"] = (
                    ["product"] if human["id"] == "HUMAN-REVIEW" else []
                )
            write_store(store)

            current = load_store(data_path)
            workspace = Workspace.load(data_path)
            inbox = build_approval_inbox(workspace, current.data)
            handoff = build_agent_handoff(
                workspace,
                "WORK-001",
                "PALARI-SOFIA",
            )

        item = inbox["evaluations"][0]["members"][0]
        self.assertEqual(item["state"], "blocked")
        self.assertTrue(
            any("0/1 distinct qualified human approvers" in reason for reason in item["reasons"])
        )
        self.assertEqual(inbox["approval_commands"], [])
        self.assertFalse(inbox["primary_action"]["available"])
        approval = handoff["human_approval_handoff"]
        self.assertIsNotNone(approval)
        self.assertFalse(approval["authority_plan"]["viable"])
        self.assertFalse(approval["approval_pack"]["available"])
        self.assertEqual(approval["approval_pack"]["approve_eligible_commands"], [])
        self.assertEqual(handoff["human_action_commands"], [])
        self.assertIn(
            "distinct Palari reviewer",
            approval["approval_pack"]["next_safe_action"],
        )

    def test_agent_handoff_exposes_one_pack_action_when_continuity_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)

            handoff = build_agent_handoff(
                Workspace.load(data_path),
                "WORK-001",
                "PALARI-SOFIA",
            )

        approval = handoff["human_approval_handoff"]
        self.assertIsNotNone(approval)
        self.assertTrue(approval["approval_pack"]["available"])
        self.assertEqual(approval["approval_pack"]["mode"], "approve-eligible")
        self.assertTrue(approval["approval_pack"]["presentation_digest"].startswith("sha256:"))
        self.assertEqual(
            approval["approval_pack"]["presentation"]["schema_version"],
            "palari.approval-presentation.v1",
        )
        self.assertEqual(len(handoff["human_action_commands"]), 2)
        self.assertTrue(
            all(
                item["type"] == "simple-approval"
                for item in handoff["human_action_commands"]
            )
        )
        self.assertIn(
            "queue --approval-inbox --select WORK-001",
            handoff["next_allowed_commands"][0],
        )
        self.assertIn(
            "--presentation-digest " + approval["approval_pack"]["presentation_digest"],
            approval["approval_pack"]["approve_eligible_commands"][0]["command"],
        )
        self.assertEqual(
            {item["actor"] for item in handoff["human_action_commands"]},
            {"HUMAN-PRODUCT", "HUMAN-SECOND"},
        )
        for item in handoff["human_action_commands"]:
            self.assertIn(f"palari --workspace {data_path.parent}", item["command"])
            self.assertIn(
                "--presented " + approval["approval_pack"]["presentation_digest"],
                item["command"],
            )
            self.assertNotIn("--pack-digest", item["command"])

    def test_agent_handoff_never_bypasses_an_unavailable_exact_pack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            with patch(
                "palari_company_os.agent_handoff.approval_inbox",
                side_effect=WorkspaceError("journal continuity is unavailable"),
            ):
                handoff = build_agent_handoff(
                    Workspace.load(data_path),
                    "WORK-001",
                    "PALARI-SOFIA",
                )

        approval = handoff["human_approval_handoff"]
        self.assertFalse(approval["approval_pack"]["available"])
        self.assertEqual(approval["approval_pack"]["mode"], "blocked")
        self.assertEqual(handoff["human_action_commands"], [])
        self.assertNotIn("human-decision record", json.dumps(handoff))
        self.assertIn("journal continuity", approval["approval_pack"]["reason"])

    def test_presented_handoff_digest_rejects_drift_without_manual_pack_digest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1)
            handoff = build_agent_handoff(
                Workspace.load(data_path),
                "WORK-001",
                "PALARI-SOFIA",
            )
            approval = handoff["human_approval_handoff"]["approval_pack"]
            presented = str(approval["presentation_digest"])
            command = str(approval["simple_approval_commands"][0]["command"])
            self.assertIn(f"--presented {presented}", command)
            self.assertNotIn("--pack-digest", command)
            workspace_before = data_path.read_bytes()
            (root / OUTPUT).write_text(
                "changed after handoff\n",
                encoding="utf-8",
            )

            with self.assertRaises(SimpleApprovalError) as error:
                approve_work(
                    str(data_path),
                    "WORK-001",
                    "HUMAN-PRODUCT",
                    presented_digest=presented,
                )

            self.assertEqual(error.exception.code, "APPROVAL_STATE_CHANGED")
            self.assertEqual(data_path.read_bytes(), workspace_before)

    def test_presented_digest_is_enforced_on_idempotent_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            handoff = build_agent_handoff(
                Workspace.load(data_path),
                "WORK-001",
                "PALARI-SOFIA",
            )
            presented = str(
                handoff["human_approval_handoff"]["approval_pack"][
                    "presentation_digest"
                ]
            )

            first = approve_work(
                str(data_path),
                "WORK-001",
                "HUMAN-PRODUCT",
                presented_digest=presented,
            )
            replay = approve_work(
                str(data_path),
                "WORK-001",
                "HUMAN-PRODUCT",
                presented_digest=presented,
            )
            with self.assertRaises(SimpleApprovalError) as error:
                approve_work(
                    str(data_path),
                    "WORK-001",
                    "HUMAN-PRODUCT",
                    presented_digest="sha256:" + ("0" * 64),
                )

            self.assertFalse(first["idempotent"])
            self.assertTrue(replay["idempotent"])
            self.assertEqual(error.exception.code, "APPROVAL_STATE_CHANGED")

    def test_cli_exposes_inbox_and_one_pack_decision_surface(self) -> None:
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
            rendered_inbox = run_text(
                "--workspace",
                str(data_path),
                "queue",
                "--approval-inbox",
                "--select",
                "WORK-001",
            )
            decision = run_json(
                "--workspace",
                str(data_path),
                "human-decision",
                "pack",
                "--pack-digest",
                inbox["packs"][0]["pack_digest"],
                "--presentation-digest",
                inbox["approval_commands"][0]["presentation_digest"],
                "--human-id",
                "HUMAN-PRODUCT",
                "--approve-eligible",
                "--pack-member",
                "WORK-001",
                "--reason",
                "CLI morning review.",
                "--json",
            )

        self.assertEqual(inbox["schema_version"], "palari.approval-inbox.v2")
        self.assertIn("Status: Needs approval", rendered_inbox)
        self.assertIn("Owner: qualified human", rendered_inbox)
        self.assertIn("Next: palari --workspace", rendered_inbox)
        self.assertIn("human-decision pack", rendered_inbox)
        self.assertLessEqual(len(rendered_inbox.splitlines()), 8)
        self.assertIn("--pack-member WORK-001", inbox["approval_commands"][0]["approve_eligible"])
        self.assertTrue(inbox["approval_commands"])
        for command in inbox["approval_commands"]:
            self.assertIn(
                f"--human-id {command['human_id']}",
                command["approve_eligible"],
            )
            self.assertNotIn("--human-id HUMAN-ID", command["approve_eligible"])
        self.assertEqual(decision["executed"], ["WORK-001"])

    def test_batch_policy_translates_only_structured_kernel_facts(self) -> None:
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

        self.assertEqual(_batch_policy(work(), [])["class"], "local-work")
        for prose_only_change in (
            {"title": "Scoped memory proposal"},
            {"allowed_actions": ["send email"]},
            {"scope": "expand access permission"},
            {"scope": "approve legal filing"},
        ):
            with self.subTest(prose_only_change):
                self.assertTrue(_batch_policy(work(**prose_only_change), [])["batchable"])
        self.assertFalse(
            _batch_policy(work(allowed_actions=["external_write"]), [])["batchable"]
        )
        self.assertFalse(_batch_policy(work(), ["OUTBOX-1"])["batchable"])
        for risk in ("R3", "R4", "R5", "unknown"):
            with self.subTest(risk=risk):
                self.assertFalse(_batch_policy(work(risk=risk), [])["batchable"])

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
        self.assertEqual(pack["pack_digest"], second["packs"][0]["pack_digest"])

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

    def test_expected_internal_dependency_completion_keeps_pack_executed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(
                Path(directory),
                count=2,
                dependencies={"WORK-002": ["WORK-001"]},
            )
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            result = apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="Approve exact dependency-ordered pack.",
            )
            evaluation = evaluate_approval_pack(Workspace.load(data_path), pack)

        self.assertEqual(result["executed"], ["WORK-001", "WORK-002"])
        self.assertEqual(
            [item["state"] for item in evaluation["members"]],
            ["executed", "executed"],
        )

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

    def test_commands_name_only_humans_who_can_act_on_the_current_quorum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1, approvals=2)
            store = load_store(data_path)
            inbox = build_approval_inbox(Workspace.load(data_path), store.data)
            pack = inbox["packs"][0]
            apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="First distinct quorum vote.",
            )

            current = load_store(data_path)
            workspace = Workspace.load(data_path)
            refreshed = build_approval_inbox(workspace, current.data)
            handoff = build_agent_handoff(
                workspace,
                "WORK-001",
                "PALARI-SOFIA",
            )

        self.assertEqual(
            [item["human_id"] for item in refreshed["approval_commands"]],
            ["HUMAN-SECOND"],
        )
        self.assertEqual(len(handoff["human_action_commands"]), 1)
        action = handoff["human_action_commands"][0]
        self.assertEqual(action["type"], "simple-approval")
        self.assertEqual(action["actor"], "HUMAN-SECOND")
        self.assertEqual(action["result"], "approve")
        self.assertIn(f"palari --workspace {data_path.parent}", action["command"])
        self.assertIn("--presented sha256:", action["command"])

    def test_inbox_commands_retain_a_nondefault_workspace_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            custom_data_path = data_path.with_name("governance-state.json")
            data_path.rename(custom_data_path)
            data_path.write_text("{}\n", encoding="utf-8")
            store = load_store(custom_data_path)
            workspace = Workspace.load(custom_data_path)
            inbox = build_approval_inbox(
                workspace,
                store.data,
            )
            packet = build_agent_brief(
                workspace,
                "WORK-001",
                "PALARI-SOFIA",
                "execute",
            )
            handoff = build_agent_handoff(
                workspace,
                "WORK-001",
                "PALARI-SOFIA",
            )
            emitted_read_commands = [
                *packet["next_allowed_commands"],
                *handoff["next_allowed_commands"],
            ]
            for command in emitted_read_commands:
                arguments = shlex.split(command)
                self.assertEqual(
                    arguments[1:3],
                    ["--workspace", str(custom_data_path)],
                )
                run_json(*arguments[1:])
            approval_command = next(
                item["command"]
                for item in handoff["human_action_commands"]
                if item["actor"] == "HUMAN-PRODUCT"
            )
            result = run_json(*shlex.split(approval_command)[1:])

        self.assertTrue(inbox["approval_commands"])
        self.assertTrue(
            all(
                f"palari --workspace {custom_data_path}" in item["approve_eligible"]
                for item in inbox["approval_commands"]
            )
        )
        self.assertTrue(result["completed"])
        self.assertFalse(result["performed_external_effects"])

    def test_reject_or_defer_does_not_suppress_a_later_founder_approval(self) -> None:
        for prior_action in ("reject", "defer"):
            with self.subTest(prior_action=prior_action), tempfile.TemporaryDirectory() as directory:
                data_path = make_ready_workspace(
                    Path(directory),
                    count=1,
                    reviewer_id="PALARI-REVIEWER",
                    single_maintainer=True,
                )
                store = load_store(data_path)
                inbox = build_approval_inbox(Workspace.load(data_path), store.data)
                pack = inbox["packs"][0]
                apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    human_id="HUMAN-PRODUCT",
                    **{prior_action: ["WORK-001"]},
                )

                current = load_store(data_path)
                refreshed = build_approval_inbox(
                    Workspace.load(data_path),
                    current.data,
                )
                command = refreshed["approval_commands"][0]
                result = approve_work(
                    str(data_path),
                    "WORK-001",
                    "HUMAN-PRODUCT",
                    presented_digest=command["presentation_digest"],
                )

                self.assertEqual(
                    refreshed["individual_items"][0]["state"],
                    "eligible",
                )
                self.assertEqual(
                    [item["human_id"] for item in refreshed["approval_commands"]],
                    ["HUMAN-PRODUCT"],
                )
                self.assertTrue(result["completed"])
                self.assertEqual(
                    Workspace.load(data_path).work_item("WORK-001").status,
                    "completed",
                )

    def test_changed_member_stales_pending_quorum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1, approvals=2)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            first = apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="First quorum vote before member change.",
            )
            changed = load_store(data_path)
            changed.data["work_items"][0]["title"] = "Renamed local governed draft"
            write_store(changed)

            evaluation = evaluate_approval_pack(Workspace.load(data_path), pack)
            with self.assertRaisesRegex(WorkspaceError, "stale"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    human_id="HUMAN-SECOND",
                    approve_eligible=True,
                    reason="Second vote must not reuse an older member presentation.",
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
        self.assertEqual(first["parked"], ["WORK-001"])
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

    def test_narrowed_pack_binds_terminal_dependency_artifact_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(
                root,
                count=2,
                dependencies={"WORK-002": ["WORK-001"]},
                approvals=2,
                distinct_outputs=True,
            )
            store = load_store(data_path)
            workspace = Workspace.load(data_path)
            parent_pack = build_approval_inbox(
                workspace,
                store.data,
                selected_work_ids=["WORK-001"],
            )["packs"][0]
            for human_id in ("HUMAN-PRODUCT", "HUMAN-SECOND"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=parent_pack["pack_digest"],
                    human_id=human_id,
                    approve_eligible=True,
                    pack_members=["WORK-001"],
                    reason=f"Complete terminal dependency as {human_id}.",
                )

            current = load_store(data_path)
            child_pack = build_approval_inbox(
                Workspace.load(data_path),
                current.data,
                selected_work_ids=["WORK-002"],
            )["packs"][0]
            first = apply_pack_decision(
                str(data_path),
                pack_digest=child_pack["pack_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                pack_members=["WORK-002"],
                reason="First child quorum vote.",
            )
            (root / "artifacts/result-001.txt").write_text(
                "terminal dependency artifact changed\n",
                encoding="utf-8",
            )

            evaluation = evaluate_approval_pack(Workspace.load(data_path), child_pack)
            with self.assertRaisesRegex(WorkspaceError, "stale"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=child_pack["pack_digest"],
                    human_id="HUMAN-SECOND",
                    approve_eligible=True,
                    pack_members=["WORK-002"],
                    reason="Changed parent bytes must block second child vote.",
                )

        self.assertEqual(first["executed"], [])
        self.assertEqual(evaluation["members"][0]["state"], "stale")

    def test_review_identity_and_pack_transplant_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            store = load_store(data_path)
            pack = build_approval_inbox(Workspace.load(data_path), store.data)["packs"][0]
            workspace = Workspace.load(data_path)
            presentation = build_approval_presentation(
                workspace,
                pack,
                evaluate_approval_pack(workspace, pack),
            )
            presented_digest = approval_presentation_digest(presentation, pack)
            with self.assertRaisesRegex(WorkspaceError, "distinct from builder and reviewer"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    presentation_digest=presented_digest,
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
                    presentation_digest=presented_digest,
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
            validate_pack_manifest(bad_base)

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
            validate_pack_manifest(bad_member)

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
                inbox = build_approval_inbox(Workspace.load(data_path), store.data)
                pack = inbox["packs"][0]
                presented_digest = inbox["approval_commands"][0]["presentation_digest"]
                with self.assertRaisesRegex(InjectedCrash, point):
                    apply_pack_decision(
                        str(data_path),
                        pack_digest=pack["pack_digest"],
                        presentation_digest=presented_digest,
                        human_id="HUMAN-PRODUCT",
                        approve_eligible=True,
                        reason="Crash boundary test.",
                        crash_hook=crash_at(point),
                    )
                retried = apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    presentation_digest=presented_digest,
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

    def test_final_prewrite_artifact_drift_cannot_mutate_workspace_or_journal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1)
            store = load_store(data_path)
            inbox = build_approval_inbox(
                Workspace.load(data_path),
                store.data,
                selected_work_ids=["WORK-001"],
            )
            pack = inbox["packs"][0]
            presentation_digest = inbox["approval_commands"][0][
                "presentation_digest"
            ]
            journal_path = journal_file_path(data_path)
            workspace_before = data_path.read_bytes()
            journal_before = journal_path.read_bytes()

            def mutate_at_final_prewrite(stage: str) -> None:
                if stage == "before_prepare_append":
                    (root / OUTPUT).write_text(
                        "changed at final prewrite\n",
                        encoding="utf-8",
                    )

            with self.assertRaisesRegex(
                WorkspaceError,
                "changed at the final prewrite boundary",
            ):
                _apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    presentation_digest=presentation_digest,
                    human_id="HUMAN-PRODUCT",
                    approve_eligible=True,
                    pack_members=["WORK-001"],
                    crash_hook=mutate_at_final_prewrite,
                )

            final = load_store(data_path)
            report = verify_journal(data_path, final.data)
            self.assertEqual(data_path.read_bytes(), workspace_before)
            self.assertEqual(journal_path.read_bytes(), journal_before)
            self.assertEqual(final.data["human_decisions"], [])
            self.assertEqual(final.data["acceptance_records"], [])
            self.assertIsNone(report["pending"])

    def test_stale_pending_before_approval_is_aborted_instead_of_auto_applied(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1)
            store = load_store(data_path)
            inbox = build_approval_inbox(
                Workspace.load(data_path),
                store.data,
                selected_work_ids=["WORK-001"],
            )
            pack = inbox["packs"][0]
            presentation_digest = inbox["approval_commands"][0][
                "presentation_digest"
            ]
            workspace_before = data_path.read_bytes()

            with self.assertRaisesRegex(InjectedCrash, "after_prepare_fsync"):
                _apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    presentation_digest=presentation_digest,
                    human_id="HUMAN-PRODUCT",
                    approve_eligible=True,
                    pack_members=["WORK-001"],
                    crash_hook=crash_at("after_prepare_fsync"),
                )
            pending = verify_journal(data_path, load_store(data_path).data)
            self.assertIsNotNone(pending["pending"])
            (root / OUTPUT).write_text(
                "changed after prepare\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                WorkspaceError,
                "changed at the final prewrite boundary",
            ):
                _apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    presentation_digest=presentation_digest,
                    human_id="HUMAN-PRODUCT",
                    approve_eligible=True,
                    pack_members=["WORK-001"],
                )

            final = load_store(data_path)
            report = verify_journal(data_path, final.data)
            self.assertEqual(data_path.read_bytes(), workspace_before)
            self.assertEqual(final.data["human_decisions"], [])
            self.assertIsNone(report["pending"])
            self.assertGreaterEqual(report["aborted_transactions"], 1)

    def test_artifact_drift_after_prepare_is_aborted_before_workspace_apply(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1)
            store = load_store(data_path)
            inbox = build_approval_inbox(
                Workspace.load(data_path),
                store.data,
                selected_work_ids=["WORK-001"],
            )
            pack = inbox["packs"][0]
            presentation_digest = inbox["approval_commands"][0][
                "presentation_digest"
            ]
            workspace_before = data_path.read_bytes()

            def mutate_before_apply(stage: str) -> None:
                if stage == "before_apply":
                    (root / OUTPUT).write_text(
                        "changed after prepare before apply\n",
                        encoding="utf-8",
                    )

            with self.assertRaisesRegex(
                WorkspaceError,
                "changed at the final prewrite boundary",
            ):
                _apply_pack_decision(
                    str(data_path),
                    pack_digest=pack["pack_digest"],
                    presentation_digest=presentation_digest,
                    human_id="HUMAN-PRODUCT",
                    approve_eligible=True,
                    pack_members=["WORK-001"],
                    crash_hook=mutate_before_apply,
                )

            final = load_store(data_path)
            report = verify_journal(data_path, final.data)
            self.assertEqual(data_path.read_bytes(), workspace_before)
            self.assertEqual(final.data["human_decisions"], [])
            self.assertIsNone(report["pending"])
            self.assertGreaterEqual(report["aborted_transactions"], 1)

    def test_review_required_zero_quorum_converges_with_one_maintainer_and_palari_reviewer(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(
                Path(directory),
                count=1,
                approvals=0,
                reviewer_id="PALARI-REVIEWER",
                single_maintainer=True,
            )
            store = load_store(data_path)
            inbox = build_approval_inbox(Workspace.load(data_path), store.data)

            self.assertEqual(
                [item["human_id"] for item in inbox["approval_commands"]],
                ["HUMAN-PRODUCT"],
            )
            authority = inbox["packs"][0]["members"][0]["authority"]
            self.assertEqual(authority["required_approval_count"], 0)
            self.assertEqual(authority["effective_final_approval_count"], 1)
            approval = _human_approval_handoff(
                Workspace.load(data_path),
                "WORK-001",
            )
            self.assertEqual(approval["required_approval_count"], 0)
            self.assertEqual(approval["effective_final_approval_count"], 1)
            result = approve_work(
                str(data_path),
                "WORK-001",
                "HUMAN-PRODUCT",
            )
            final = Workspace.load(data_path)

            self.assertTrue(result["completed"])
            self.assertEqual(final.work_item("WORK-001").status, "completed")
            self.assertEqual(len(final.human_decisions), 1)
            self.assertEqual(len(final.acceptance_records), 1)

    def test_review_required_zero_quorum_founder_reviewer_fails_before_approval(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(
                Path(directory),
                count=1,
                approvals=0,
                reviewer_id="HUMAN-PRODUCT",
                single_maintainer=True,
            )
            store = load_store(data_path)
            inbox = build_approval_inbox(
                Workspace.load(data_path),
                store.data,
                selected_work_ids=["WORK-001"],
            )

            self.assertEqual(inbox["approval_commands"], [])
            self.assertEqual(inbox["individual_items"][0]["state"], "blocked")
            with self.assertRaises(SimpleApprovalError) as error:
                approve_work(
                    str(data_path),
                    "WORK-001",
                    "HUMAN-PRODUCT",
                )
            self.assertIn(
                error.exception.code,
                {
                    "APPROVAL_AUTHORITY_PLAN_BLOCKED",
                    "APPROVAL_IDENTITY_COLLISION",
                    "APPROVAL_REVIEW_REQUIRED",
                },
            )


def make_ready_workspace(
    root: Path,
    *,
    count: int,
    dependencies: dict[str, list[str]] | None = None,
    approvals: int = 1,
    distinct_outputs: bool = False,
    scope: str = "Prepare one bounded local draft without external effects.",
    risk: str = "R2",
    reviewer_id: str = "HUMAN-REVIEW",
    single_maintainer: bool = False,
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
    if single_maintainer:
        raw["humans"] = [raw["humans"][0]]
    raw["palaris"][0]["owner_human"] = "HUMAN-PRODUCT"
    raw["palaris"][0]["active_work"] = []
    if reviewer_id == "PALARI-REVIEWER":
        raw["palaris"].append(
            {
                "id": "PALARI-REVIEWER",
                "name": "Independent reviewer",
                "role": "Review-only Palari",
                "owner_human": "HUMAN-PRODUCT",
                "linked_goals": ["GOAL-1"],
                "active_work": [],
            }
        )
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
    dependencies = dependencies or {}
    base_time = datetime(2020, 1, 1, tzinfo=timezone.utc)

    for index in range(1, count + 1):
        work_id = f"WORK-{index:03d}"
        attempt_id = f"ATTEMPT-{index:03d}"
        head = f"head-{index:03d}"
        output_path = (
            f"artifacts/result-{index:03d}.txt"
            if distinct_outputs
            else OUTPUT
        )
        output = root / output_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("exact reviewed bytes\n", encoding="utf-8")
        raw["work_items"].append(
            {
                "id": work_id,
                "title": f"Prepare local governed draft {index:03d}",
                "goal": "GOAL-1",
                "palari": "PALARI-SOFIA",
                "dependency_ids": dependencies.get(work_id, []),
                "risk": risk,
                "intensity": "standard",
                "status": "in-review",
                "scope": scope,
                "allowed_resources": [output_path],
                "allowed_actions": ["write local draft"],
                "output_targets": [output_path],
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
                "changed_files": [output_path],
                "allowed_paths": [output_path],
                "cleanliness": "clean",
                "output_targets": [output_path],
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
                "outputs_created": [output_path],
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
                "artifacts": [output_path],
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
            "reviewer": reviewer_id,
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


def run_text(*args: str) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-S", "-m", "palari_company_os", *args],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    ).stdout


if __name__ == "__main__":
    unittest.main()
