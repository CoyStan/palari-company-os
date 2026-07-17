from __future__ import annotations

import tempfile
import unittest
import sys
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.approval_packs import apply_pack_decision, build_approval_inbox
from palari_company_os.approval_presentations import (
    approval_presentation_digest,
    canonical_presentation_bytes,
)
from palari_company_os.pcaw_canonical import canonical_sha256
from palari_company_os.store import load_store, write_store
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.test_approval_packs import OUTPUT, make_ready_workspace


class ApprovalPresentationTests(unittest.TestCase):
    def test_projection_is_deterministic_and_changed_governed_bytes_change_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1)
            store = load_store(data_path)
            first = build_approval_inbox(Workspace.load(data_path), store.data)
            second = build_approval_inbox(Workspace.load(data_path), store.data)
            first_pack = first["packs"][0]
            first_presentation = first["presentations"][0]

            self.assertEqual(
                canonical_presentation_bytes(first_presentation, first_pack),
                canonical_presentation_bytes(second["presentations"][0], second["packs"][0]),
            )
            original_digest = first["approval_commands"][0]["presentation_digest"]
            (root / OUTPUT).write_text("one governed byte changed\n", encoding="utf-8")
            changed = load_store(data_path)
            rebuilt = build_approval_inbox(Workspace.load(data_path), changed.data)

        self.assertNotEqual(
            original_digest,
            rebuilt["approval_commands"][0]["presentation_digest"],
        )

    def test_changed_decision_context_rejects_old_presentation_then_fresh_action_converges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1, approvals=2)
            store = load_store(data_path)
            first_inbox = build_approval_inbox(Workspace.load(data_path), store.data)
            first_pack = first_inbox["packs"][0]
            first_digest = first_inbox["approval_commands"][0]["presentation_digest"]
            first = apply_pack_decision(
                str(data_path),
                pack_digest=first_pack["pack_digest"],
                presentation_digest=first_digest,
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
                reason="First exact presentation vote.",
            )

            with self.assertRaisesRegex(WorkspaceError, "presentation is missing or stale"):
                apply_pack_decision(
                    str(data_path),
                    pack_digest=first_pack["pack_digest"],
                    presentation_digest=first_digest,
                    human_id="HUMAN-SECOND",
                    approve_eligible=True,
                    reason="Old presentation must not hide the first vote.",
                )

            current = load_store(data_path)
            second_inbox = build_approval_inbox(Workspace.load(data_path), current.data)
            second_pack = second_inbox["packs"][0]
            second_presentation = second_inbox["presentations"][0]
            context = second_presentation["members"][0]["decision_context"]
            second = apply_pack_decision(
                str(data_path),
                pack_digest=second_pack["pack_digest"],
                presentation_digest=second_inbox["approval_commands"][0][
                    "presentation_digest"
                ],
                human_id="HUMAN-SECOND",
                approve_eligible=True,
                reason="Fresh presentation completes quorum.",
            )
            final = load_store(data_path)

        self.assertEqual(first["executed"], [])
        self.assertEqual([item["human_id"] for item in context], ["HUMAN-PRODUCT"])
        self.assertEqual(second["executed"], ["WORK-001"])
        self.assertEqual(second["convergence"]["attributable_human_actions"], 1)
        self.assertEqual(second["convergence"]["terminalized"], ["WORK-001"])
        self.assertTrue(second["convergence"]["atomic_local_transaction"])
        self.assertEqual(final.data["work_items"][0]["status"], "completed")
        self.assertEqual(len(final.data["acceptance_records"]), 1)
        self.assertTrue(
            all(item.get("approval_presentation_digest") for item in final.data["human_decisions"])
        )

    def test_blocked_and_non_batchable_presentations_do_not_offer_approval(self) -> None:
        cases = (
            ("blocked", {}),
            ("non-batchable", {"scope": "Approve a legal filing."}),
        )
        for expected_state, options in cases:
            with self.subTest(state=expected_state), tempfile.TemporaryDirectory() as directory:
                data_path = make_ready_workspace(Path(directory), count=1, **options)
                if expected_state == "blocked":
                    changed = load_store(data_path)
                    changed.data["review_verdicts"] = []
                    write_store(changed)
                store = load_store(data_path)
                inbox = build_approval_inbox(Workspace.load(data_path), store.data)
                presentation = inbox["presentations"][0]

                self.assertEqual(
                    presentation["members"][0]["decision_state"]["state"],
                    expected_state,
                )
                self.assertEqual(
                    presentation["action"]["available"],
                    ["defer", "reject"],
                )
                self.assertEqual(
                    presentation["action"]["primary"],
                    "inspect-exceptions",
                )
                self.assertFalse(inbox["primary_action"]["available"])

    def test_pack_v2_decision_cannot_downgrade_or_transplant_its_presentation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1)
            store = load_store(data_path)
            inbox = build_approval_inbox(Workspace.load(data_path), store.data)
            pack = inbox["packs"][0]
            apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                presentation_digest=inbox["approval_commands"][0]["presentation_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
            )
            raw = load_store(data_path).data

        downgraded = deepcopy(raw)
        decision = downgraded["human_decisions"][0]
        for field in (
            "approval_presentation_schema_version",
            "approval_presentation_digest",
            "approval_presentation_surface",
            "approval_presentation",
        ):
            decision.pop(field, None)
        with self.assertRaisesRegex(WorkspaceError, "pack v2 requires presentation binding"):
            Workspace.from_raw(downgraded, root)

        transplanted = deepcopy(raw)
        decision = transplanted["human_decisions"][0]
        decision["approval_presentation"]["members"][0]["title"] = "Different work"
        decision["approval_presentation_digest"] = canonical_sha256(
            decision["approval_presentation"]
        )
        with self.assertRaisesRegex(WorkspaceError, "member differs"):
            Workspace.from_raw(transplanted, root)

    def test_digest_helper_matches_inbox_command_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = make_ready_workspace(Path(directory), count=1)
            store = load_store(data_path)
            inbox = build_approval_inbox(Workspace.load(data_path), store.data)
            pack = inbox["packs"][0]
            presentation = inbox["presentations"][0]

        self.assertEqual(
            approval_presentation_digest(presentation, pack),
            inbox["approval_commands"][0]["presentation_digest"],
        )
        self.assertIn(
            "--presentation-digest " + inbox["approval_commands"][0]["presentation_digest"],
            inbox["approval_commands"][0]["approve_eligible"],
        )

    def test_historical_pack_v1_decision_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = make_ready_workspace(root, count=1)
            store = load_store(data_path)
            inbox = build_approval_inbox(Workspace.load(data_path), store.data)
            pack = inbox["packs"][0]
            apply_pack_decision(
                str(data_path),
                pack_digest=pack["pack_digest"],
                presentation_digest=inbox["approval_commands"][0]["presentation_digest"],
                human_id="HUMAN-PRODUCT",
                approve_eligible=True,
            )
            historical = load_store(data_path).data

        decision = historical["human_decisions"][0]
        manifest = decision["approval_pack_manifest"]
        manifest["schema_version"] = "palari.approval-pack.v1"
        manifest["pack_digest"] = canonical_sha256(
            {key: value for key, value in manifest.items() if key != "pack_digest"}
        )
        decision["approval_pack_digest"] = manifest["pack_digest"]
        for field in (
            "approval_presentation_schema_version",
            "approval_presentation_digest",
            "approval_presentation_surface",
            "approval_presentation",
        ):
            decision.pop(field, None)

        loaded = Workspace.from_raw(historical, root)
        self.assertEqual(loaded.human_decisions[0].approval_presentation_digest, "")


if __name__ == "__main__":
    unittest.main()
