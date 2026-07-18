from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.integrations import (
    cancel_integration_outbox_item,
    check_integration,
    check_integration_outbox,
    decide_integration_plan,
    enqueue_integration_plan,
    plan_integration,
    record_integration_plan,
)
from palari_company_os.store import WorkspaceStore, write_store
from palari_company_os.workspace import Workspace, WorkspaceError


WORK_ID = "WORK-1"
OTHER_WORK_ID = "WORK-2"
INTEGRATION_ID = "INT-NOTIFY"
OTHER_INTEGRATION_ID = "INT-EMAIL"
PLAN_ID = "PLAN-1"
OUTBOX_ID = "OUTBOX-1"
OWNER_ID = "HUMAN-OWNER"
UNQUALIFIED_ID = "HUMAN-OBSERVER"


def _source(source_id: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "label": f"Local source {source_id}",
        "kind": "note",
        "provider": "local_note",
        "uri": f"notes/{source_id.lower()}.md",
        "access_mode": "read",
        "selected": True,
        "owner_human": OWNER_ID,
        "allowed_palaris": ["PALARI-1"],
        "data_class": "internal",
        "authority": "company_owned",
        "steward_human": OWNER_ID,
        "freshness_sla": "weekly",
        "redaction_required": False,
    }


def _work(work_id: str, source_id: str) -> dict[str, Any]:
    return {
        "id": work_id,
        "title": f"Bounded work {work_id}",
        "goal": "GOAL-1",
        "palari": "PALARI-1",
        "risk": "R1",
        "intensity": "light",
        "status": "active",
        "scope": "Produce one local bounded result.",
        "allowed_resources": [f"notes/{work_id.lower()}.md"],
        "allowed_sources": [source_id],
        "allowed_actions": ["local_write"],
        "output_targets": [f"notes/{work_id.lower()}.md"],
        "forbidden_actions": ["external_write"],
        "acceptance_target": "The bounded result is inspectable.",
        "required_approval_count": 1,
        "required_approval_capability": "product",
    }


def _base_raw() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "name": "Integration Boundary Contract",
        "goals": [{"id": "GOAL-1", "title": "Keep external effects governed"}],
        "humans": [
            {
                "id": OWNER_ID,
                "name": "Integration Owner",
                "approval_capabilities": ["product"],
            },
            {"id": UNQUALIFIED_ID, "name": "Observer"},
        ],
        "palaris": [
            {
                "id": "PALARI-1",
                "name": "Sofia",
                "role": "Bounded worker",
                "owner_human": OWNER_ID,
                "linked_goals": ["GOAL-1"],
            }
        ],
        "sources": [_source("SOURCE-1"), _source("SOURCE-2")],
        "work_items": [_work(WORK_ID, "SOURCE-1"), _work(OTHER_WORK_ID, "SOURCE-2")],
        "integrations": [
            {
                "id": INTEGRATION_ID,
                "provider": "slack",
                "label": "Bounded notification",
                "mode": "notify",
                "owner_human": OWNER_ID,
                "enabled": True,
                "allowed_events": ["approval_requested"],
                "allowed_actions": ["notify"],
                "secret_ref": "env:PALARI_TEST_WEBHOOK",
                "risk_level": "standard",
                "source_ids": ["SOURCE-1", "SOURCE-2"],
            },
            {
                "id": OTHER_INTEGRATION_ID,
                "provider": "email",
                "label": "Other provider",
                "mode": "notify",
                "owner_human": OWNER_ID,
                "enabled": True,
                "allowed_events": ["approval_requested"],
                "allowed_actions": ["notify"],
                "secret_ref": "env:PALARI_TEST_MAILER",
                "risk_level": "standard",
                "source_ids": ["SOURCE-2"],
            },
        ],
        "integration_plans": [],
        "integration_outbox": [],
        "attempts": [],
        "evidence_runs": [],
        "review_verdicts": [],
        "human_decisions": [],
        "acceptance_records": [],
        "receipts": [],
        "decisions": [],
        "outcomes": [],
    }


def _payload_preview() -> dict[str, Any]:
    return {
        "provider": "slack",
        "operation": "post_message",
        "webhook_ref": "env:PALARI_TEST_WEBHOOK",
        "json": {"text": "Approved deterministic preview."},
    }


def _source_boundary() -> dict[str, Any]:
    return {
        "integration_sources": ["SOURCE-1", "SOURCE-2"],
        "work_allowed_sources": ["SOURCE-1"],
        "shared_sources": ["SOURCE-1"],
        "shared_source_labels": ["Local source SOURCE-1"],
    }


def _approved_plan() -> dict[str, Any]:
    return {
        "id": PLAN_ID,
        "integration_id": INTEGRATION_ID,
        "work_item_id": WORK_ID,
        "event": "approval_requested",
        "action": "notify",
        "actor": "PALARI-1",
        "status": "approved",
        "payload_preview": _payload_preview(),
        "source_boundary": _source_boundary(),
        "risk": "standard",
        "approval_required": True,
        "timestamp": "2026-07-18T10:00:00Z",
        "reviewed_by": OWNER_ID,
        "reviewed_at": "2026-07-18T10:01:00Z",
    }


def _queued_outbox() -> dict[str, Any]:
    return {
        "id": OUTBOX_ID,
        "plan_id": PLAN_ID,
        "integration_id": INTEGRATION_ID,
        "work_item_id": WORK_ID,
        "event": "approval_requested",
        "action": "notify",
        "enqueued_by": OWNER_ID,
        "status": "queued",
        "payload_preview": _payload_preview(),
        "source_boundary": _source_boundary(),
        "risk": "standard",
        "timestamp": "2026-07-18T10:02:00Z",
    }


def _raw_with_approved_outbox() -> dict[str, Any]:
    raw = _base_raw()
    raw["integration_plans"] = [_approved_plan()]
    raw["integration_outbox"] = [_queued_outbox()]
    return raw


def _workspace(
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> Workspace:
    raw = _base_raw()
    if mutate is not None:
        mutate(raw)
    return Workspace.from_raw(raw, Path("/tmp/palari-integration-boundary"))


@contextmanager
def _stored_workspace(
    raw: dict[str, Any] | None = None,
) -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        write_store(
            WorkspaceStore(
                data_path=path / "workspace.json",
                data=deepcopy(raw if raw is not None else _base_raw()),
            )
        )
        yield path


def _record_and_approve(path: Path) -> None:
    record_integration_plan(
        str(path),
        INTEGRATION_ID,
        WORK_ID,
        "approval_requested",
        "notify",
        actor="PALARI-1",
        plan_id=PLAN_ID,
    )
    decide_integration_plan(str(path), PLAN_ID, OWNER_ID, "approve", reason="approved")


class IntegrationBoundaryTests(unittest.TestCase):
    def test_plan_preview_is_deterministic_redacted_and_non_executing(self) -> None:
        workspace = _workspace()

        first = plan_integration(
            workspace,
            INTEGRATION_ID,
            WORK_ID,
            "approval_requested",
            "notify",
        )
        second = plan_integration(
            workspace,
            INTEGRATION_ID,
            WORK_ID,
            "approval_requested",
            "notify",
        )

        self.assertEqual(first, second)
        self.assertTrue(first["dry_run"])
        self.assertFalse(first["would_call_provider"])
        self.assertIsNone(first["integration_plan"])
        self.assertEqual(
            first["safety"]["secret_handling"],
            "secret_ref only; no secret value read",
        )
        self.assertNotIn("xoxb-", json.dumps(first))

    def test_plan_preview_intersects_declared_source_boundaries(self) -> None:
        preview = plan_integration(
            _workspace(),
            INTEGRATION_ID,
            WORK_ID,
            "approval_requested",
            "notify",
        )

        self.assertEqual(preview["safety"]["source_boundary"], _source_boundary())

    def test_check_reports_a_local_non_executing_boundary(self) -> None:
        payload = check_integration(_workspace(), INTEGRATION_ID)

        self.assertTrue(payload["valid"])
        self.assertTrue(payload["dry_run_only"])
        self.assertEqual(payload["plannable_actions"], ["notify"])
        self.assertTrue(payload["secret_ref_present"])
        self.assertIn("No live provider calls", " ".join(payload["notes"]))

    def test_disabled_integration_cannot_plan(self) -> None:
        workspace = _workspace(
            lambda raw: raw["integrations"][0].update({"enabled": False})
        )

        with self.assertRaisesRegex(WorkspaceError, "integration INT-NOTIFY is disabled"):
            plan_integration(
                workspace,
                INTEGRATION_ID,
                WORK_ID,
                "approval_requested",
                "notify",
            )

    def test_plan_requires_allowlisted_event_and_action(self) -> None:
        workspace = _workspace()

        for event, action, expected in (
            ("work_completed", "notify", "does not allow event work_completed"),
            ("approval_requested", "comment", "does not allow action comment"),
        ):
            with self.subTest(event=event, action=action):
                with self.assertRaisesRegex(WorkspaceError, expected):
                    plan_integration(workspace, INTEGRATION_ID, WORK_ID, event, action)

    def test_malformed_or_unsupported_integration_fails_closed(self) -> None:
        cases = (
            (
                lambda raw: raw["integrations"][0].update(
                    {"secret_ref": "xoxb-real-token-looking-value"}
                ),
                "secret_ref must be an env:NAME reference",
            ),
            (
                lambda raw: raw["integrations"][0].update({"provider": "unsupported"}),
                "provider has unsupported value",
            ),
            (
                lambda raw: raw["integrations"][0].update(
                    {"allowed_actions": ["comment"]}
                ),
                "action 'comment' unsupported by provider slack",
            ),
            (
                lambda raw: raw["integrations"][0].update({"mode": "read"}),
                "action 'notify' unsupported by mode read",
            ),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(WorkspaceError, expected):
                    _workspace(mutate)

    def test_recorded_plan_requires_explicit_human_approval(self) -> None:
        raw = _base_raw()
        plan = _approved_plan()
        plan.update({"status": "pending-approval", "approval_required": False})
        plan.pop("reviewed_by")
        plan.pop("reviewed_at")
        raw["integration_plans"] = [plan]

        with self.assertRaisesRegex(WorkspaceError, "approval_required must be true"):
            Workspace.from_raw(raw, Path("/tmp/palari-integration-boundary"))

    def test_recorded_plan_cannot_contain_raw_secret_material(self) -> None:
        raw = _base_raw()
        plan = _approved_plan()
        plan["payload_preview"] = {"token": "xoxb-real-token-looking-value"}
        raw["integration_plans"] = [plan]

        with self.assertRaisesRegex(WorkspaceError, "not a raw secret"):
            Workspace.from_raw(raw, Path("/tmp/palari-integration-boundary"))

    def test_recorded_plan_must_match_the_enabled_integration_contract(self) -> None:
        cases = (
            (lambda raw: raw["integrations"][0].update({"enabled": False}), "disabled"),
            (
                lambda raw: raw["integration_plans"][0].update(
                    {"event": "work_completed"}
                ),
                "event 'work_completed' is not allowed",
            ),
            (
                lambda raw: raw["integration_plans"][0].update({"action": "comment"}),
                "action 'comment' is not allowed",
            ),
        )
        for mutate, expected in cases:
            raw = _base_raw()
            raw["integration_plans"] = [_approved_plan()]
            mutate(raw)
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(raw, Path("/tmp/palari-integration-boundary"))

    def test_recording_a_plan_only_persists_a_pending_local_preview(self) -> None:
        with _stored_workspace() as path:
            payload = record_integration_plan(
                str(path),
                INTEGRATION_ID,
                WORK_ID,
                "approval_requested",
                "notify",
                actor="PALARI-1",
                plan_id=PLAN_ID,
            )
            workspace = Workspace.load(path)

        self.assertTrue(payload["recorded"])
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(workspace.integration_plan(PLAN_ID).status, "pending-approval")
        self.assertEqual(workspace.integration_outbox, [])

    def test_pending_plan_cannot_be_enqueued(self) -> None:
        with _stored_workspace() as path:
            record_integration_plan(
                str(path),
                INTEGRATION_ID,
                WORK_ID,
                "approval_requested",
                "notify",
                plan_id=PLAN_ID,
            )

            with self.assertRaisesRegex(WorkspaceError, "must be approved before enqueue"):
                enqueue_integration_plan(str(path), PLAN_ID, OWNER_ID)

    def test_only_an_authorized_human_can_approve_a_plan(self) -> None:
        with _stored_workspace() as path:
            record_integration_plan(
                str(path),
                INTEGRATION_ID,
                WORK_ID,
                "approval_requested",
                "notify",
                plan_id=PLAN_ID,
            )

            with self.assertRaisesRegex(WorkspaceError, "lacks authority"):
                decide_integration_plan(
                    str(path),
                    PLAN_ID,
                    UNQUALIFIED_ID,
                    "approve",
                )
            approved = decide_integration_plan(
                str(path),
                PLAN_ID,
                OWNER_ID,
                "approve",
                reason="exact preview approved",
            )

        self.assertEqual(approved["status"], "approved")
        self.assertFalse(approved["would_call_provider"])
        self.assertEqual(approved["integration_plan"]["reviewed_by"], OWNER_ID)

    def test_approved_plan_enqueues_an_exact_local_outbox_item(self) -> None:
        with _stored_workspace() as path:
            _record_and_approve(path)
            payload = enqueue_integration_plan(str(path), PLAN_ID, OWNER_ID)
            workspace = Workspace.load(path)

        item = payload["integration_outbox_item"]
        plan = workspace.integration_plan(PLAN_ID)
        self.assertEqual(payload["status"], "queued")
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(item["work_item_id"], plan.work_item_id)
        self.assertEqual(item["integration_id"], plan.integration_id)
        self.assertEqual(item["payload_preview"], plan.payload_preview)
        self.assertEqual(item["source_boundary"], plan.source_boundary)
        self.assertEqual(len(workspace.integration_outbox), 1)

    def test_plan_can_be_enqueued_only_once(self) -> None:
        with _stored_workspace() as path:
            _record_and_approve(path)
            enqueue_integration_plan(str(path), PLAN_ID, OWNER_ID)

            with self.assertRaisesRegex(WorkspaceError, "already enqueued"):
                enqueue_integration_plan(str(path), PLAN_ID, OWNER_ID)

    def test_queued_outbox_preflight_never_enables_execution(self) -> None:
        workspace = Workspace.from_raw(
            _raw_with_approved_outbox(),
            Path("/tmp/palari-integration-boundary"),
        )

        payload = check_integration_outbox(workspace, OUTBOX_ID)

        self.assertEqual(payload["status"], "queued-preflight-ready")
        self.assertFalse(payload["would_call_provider"])
        self.assertFalse(payload["execution_enabled"])
        self.assertTrue(all(check["status"] == "pass" for check in payload["checks"]))

    def test_canceled_outbox_is_stale_for_execution_preflight(self) -> None:
        raw = _raw_with_approved_outbox()
        raw["integration_outbox"][0].update(
            {
                "status": "canceled",
                "canceled_by": OWNER_ID,
                "canceled_at": "2026-07-18T10:03:00Z",
                "cancel_reason": "No longer required.",
            }
        )
        workspace = Workspace.from_raw(raw, Path("/tmp/palari-integration-boundary"))

        payload = check_integration_outbox(workspace, OUTBOX_ID)
        checks = {check["code"]: check for check in payload["checks"]}

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(checks["STATUS_QUEUED"]["status"], "fail")
        self.assertFalse(payload["execution_enabled"])

    def test_outbox_cancellation_is_local_and_requires_a_reason(self) -> None:
        with _stored_workspace(_raw_with_approved_outbox()) as path:
            with self.assertRaisesRegex(WorkspaceError, "requires a reason"):
                cancel_integration_outbox_item(str(path), OUTBOX_ID, OWNER_ID, reason=" ")

            payload = cancel_integration_outbox_item(
                str(path),
                OUTBOX_ID,
                OWNER_ID,
                reason="Action is no longer required.",
            )
            workspace = Workspace.load(path)

        self.assertEqual(payload["status"], "canceled")
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(workspace.integration_outbox_item(OUTBOX_ID).status, "canceled")

    def test_stale_plan_cannot_back_a_queued_outbox_item(self) -> None:
        raw = _raw_with_approved_outbox()
        raw["integration_plans"][0].update({"status": "pending-approval"})
        raw["integration_plans"][0].pop("reviewed_by")
        raw["integration_plans"][0].pop("reviewed_at")

        with self.assertRaisesRegex(WorkspaceError, "with status pending-approval"):
            Workspace.from_raw(raw, Path("/tmp/palari-integration-boundary"))

    def test_outbox_must_match_the_exact_work_and_provider_binding(self) -> None:
        cases = (
            ("integration_id", OTHER_INTEGRATION_ID, "integration_id does not match"),
            ("work_item_id", OTHER_WORK_ID, "work_item_id does not match"),
        )
        for field, value, expected in cases:
            raw = _raw_with_approved_outbox()
            raw["integration_outbox"][0][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(raw, Path("/tmp/palari-integration-boundary"))

    def test_outbox_rejects_payload_or_source_boundary_drift(self) -> None:
        cases = (
            (
                "payload_preview",
                {"provider": "slack", "operation": "changed"},
                "payload_preview does not match",
            ),
            (
                "source_boundary",
                {"shared_sources": []},
                "source_boundary does not match",
            ),
        )
        for field, value, expected in cases:
            raw = _raw_with_approved_outbox()
            raw["integration_outbox"][0][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.from_raw(raw, Path("/tmp/palari-integration-boundary"))

    def test_cli_plan_is_one_isolated_translation_boundary(self) -> None:
        with _stored_workspace() as path:
            environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
            completed = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    "-m",
                    "palari_company_os",
                    "--workspace",
                    str(path),
                    "integration",
                    "plan",
                    INTEGRATION_ID,
                    "--work",
                    WORK_ID,
                    "--event",
                    "approval_requested",
                    "--action",
                    "notify",
                    "--json",
                ],
                cwd=REPO_ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            payload = json.loads(completed.stdout)
            workspace = Workspace.load(path)

        self.assertFalse(payload["recorded"])
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(payload["work_item"]["id"], WORK_ID)
        self.assertEqual(workspace.integration_plans, [])


if __name__ == "__main__":
    unittest.main()
