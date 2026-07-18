from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.integrations import check_integration, plan_integration
from palari_company_os.read_models import detail, queue_items
from palari_company_os.store import WorkspaceStore, write_store
from palari_company_os.workspace import Workspace, WorkspaceError


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class IntegrationRegistryTests(unittest.TestCase):
    def test_example_integration_records_load(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        self.assertEqual(
            [integration.id for integration in workspace.integrations],
            ["INT-SLACK-OPS", "INT-GITHUB-REPO", "INT-JIRA-OPS"],
        )
        self.assertEqual(workspace.integration("INT-SLACK-OPS").provider, "slack")

    def test_raw_secret_value_fails_closed(self) -> None:
        def raw_secret(data: dict[str, object]) -> None:
            data["integrations"][0]["secret_ref"] = "xoxb-real-token-looking-value"

        with self.assertRaisesRegex(
            WorkspaceError,
            "secret_ref must be an env:NAME reference",
        ):
            self.modified_workspace(raw_secret)

    def test_unknown_provider_event_and_action_fail_closed(self) -> None:
        def unknown_provider(data: dict[str, object]) -> None:
            data["integrations"][0]["provider"] = "not-slack"

        def unknown_event(data: dict[str, object]) -> None:
            data["integrations"][0]["allowed_events"] = ["calendar_invite_sent"]

        def unknown_action(data: dict[str, object]) -> None:
            data["integrations"][0]["allowed_actions"] = ["send_live_message"]

        for mutate, expected in (
            (unknown_provider, "provider has unsupported value"),
            (unknown_event, "allowed_events has unsupported value"),
            (unknown_action, "allowed_actions has unsupported value"),
        ):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(WorkspaceError, expected):
                    self.modified_workspace(mutate)

    def test_bad_owner_and_source_refs_fail_closed(self) -> None:
        def bad_owner(data: dict[str, object]) -> None:
            data["integrations"][0]["owner_human"] = "HUMAN-MISSING"

        def bad_source(data: dict[str, object]) -> None:
            data["integrations"][0]["source_ids"] = ["SOURCE-MISSING"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "integrations.INT-SLACK-OPS.owner_human references missing id HUMAN-MISSING",
        ):
            self.modified_workspace(bad_owner)
        with self.assertRaisesRegex(
            WorkspaceError,
            "integrations.INT-SLACK-OPS.source_ids references missing id SOURCE-MISSING",
        ):
            self.modified_workspace(bad_source)

    def test_disabled_integration_cannot_plan(self) -> None:
        workspace = self.modified_workspace(
            lambda data: data["integrations"][0].update({"enabled": False})
        )

        with self.assertRaisesRegex(
            WorkspaceError,
            "integration INT-SLACK-OPS is disabled",
        ):
            plan_integration(
                workspace,
                "INT-SLACK-OPS",
                "WORK-0001",
                "approval_requested",
                "notify",
            )

    def test_plan_requires_allowed_event_and_action(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        with self.assertRaisesRegex(WorkspaceError, "does not allow event work_completed"):
            plan_integration(
                workspace,
                "INT-SLACK-OPS",
                "WORK-0001",
                "work_completed",
                "notify",
            )
        with self.assertRaisesRegex(WorkspaceError, "does not allow action comment"):
            plan_integration(
                workspace,
                "INT-SLACK-OPS",
                "WORK-0001",
                "approval_requested",
                "comment",
            )

    def test_provider_action_matrix_is_validated_for_workspace_records(self) -> None:
        def unsupported_provider_action(data: dict[str, object]) -> None:
            data["integrations"][0]["allowed_actions"] = ["notify", "comment"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "allowed_actions includes action 'comment' unsupported by provider slack",
        ):
            self.modified_workspace(unsupported_provider_action)

    def test_integration_mode_limits_allowed_actions(self) -> None:
        def notify_mode_with_write_action(data: dict[str, object]) -> None:
            data["integrations"][1]["mode"] = "notify"

        with self.assertRaisesRegex(
            WorkspaceError,
            "allowed_actions includes action 'comment' unsupported by mode notify",
        ):
            self.modified_workspace(notify_mode_with_write_action)

        workspace = Workspace.load(WORKSPACE)
        self.assertEqual(workspace.integration("INT-GITHUB-REPO").mode, "dry_run")
        self.assertIn("comment", workspace.integration("INT-GITHUB-REPO").allowed_actions)

    def test_slack_plan_is_dry_run_payload_preview(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        payload = plan_integration(
            workspace,
            "INT-SLACK-OPS",
            "WORK-0001",
            "approval_requested",
            "notify",
        )

        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(payload["payload_preview"]["provider"], "slack")
        self.assertEqual(payload["payload_preview"]["operation"], "post_message")
        self.assertEqual(payload["payload_preview"]["webhook_ref"], "env:PALARI_SLACK_WEBHOOK_URL")
        self.assertEqual(
            payload["safety"]["secret_handling"],
            "secret_ref only; no secret value read",
        )

    def test_github_and_jira_plan_payload_shapes(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        github = plan_integration(
            workspace,
            "INT-GITHUB-REPO",
            "WORK-0001",
            "work_completed",
            "create_issue",
        )
        jira = plan_integration(
            workspace,
            "INT-JIRA-OPS",
            "WORK-0001",
            "work_completed",
            "comment",
        )

        self.assertEqual(github["payload_preview"]["provider"], "github")
        self.assertEqual(github["payload_preview"]["operation"], "create_issue")
        self.assertIn("body", github["payload_preview"]["json"])
        self.assertEqual(jira["payload_preview"]["provider"], "jira")
        self.assertEqual(jira["payload_preview"]["operation"], "add_comment")
        self.assertIn("description", jira["payload_preview"]["json"])

    def test_integration_check_reports_dry_run_boundary(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        payload = check_integration(workspace, "INT-GITHUB-REPO")

        self.assertTrue(payload["valid"])
        self.assertTrue(payload["dry_run_only"])
        self.assertIn("comment", payload["plannable_actions"])
        self.assertIn("secret_ref is metadata only", " ".join(payload["notes"]))

    def test_cli_integration_commands_emit_json(self) -> None:
        integrations = json.loads(self.run_cli("integrations", "--json").stdout)
        check = json.loads(
            self.run_cli("integration", "check", "INT-SLACK-OPS", "--json").stdout
        )
        plan = json.loads(
            self.run_cli(
                "integration",
                "plan",
                "INT-SLACK-OPS",
                "--work",
                "WORK-0001",
                "--event",
                "approval_requested",
                "--action",
                "notify",
                "--json",
            ).stdout
        )

        self.assertEqual(integrations["integrations"][0]["id"], "INT-SLACK-OPS")
        self.assertEqual(check["integration"]["provider"], "slack")
        self.assertFalse(plan["would_call_provider"])

    def test_recorded_plan_is_visible_in_queue_and_detail(self) -> None:
        with self.temp_workspace() as workspace_path:
            payload = json.loads(
                self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "plan",
                    "INT-SLACK-OPS",
                    "--work",
                    "WORK-0001",
                    "--event",
                    "approval_requested",
                    "--action",
                    "notify",
                    "--record",
                    "--id",
                    "PLAN-TEST",
                    "--actor",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            workspace = Workspace.load(workspace_path)
            queue = {item.id: item for item in queue_items(workspace)}
            work_detail = detail(workspace, "WORK-0001")

        self.assertTrue(payload["recorded"])
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(payload["integration_plan"]["id"], "PLAN-TEST")
        self.assertEqual(workspace.integration_plan("PLAN-TEST").status, "pending-approval")
        self.assertEqual(queue["WORK-0001"].integration_state, "pending-plan")
        self.assertIn("Integration plan PLAN-TEST", queue["WORK-0001"].why)
        self.assertEqual(work_detail["integration_plans"][0]["id"], "PLAN-TEST")

    def test_plan_approval_records_human_decision_without_provider_call(self) -> None:
        with self.temp_workspace() as workspace_path:
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "plan",
                "INT-SLACK-OPS",
                "--work",
                "WORK-0001",
                "--event",
                "approval_requested",
                "--action",
                "notify",
                "--record",
                "--id",
                "PLAN-APPROVE",
                "--json",
            )
            payload = json.loads(
                self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "approve",
                    "PLAN-APPROVE",
                    "--by",
                    "HUMAN-FOUNDER",
                    "--reason",
                    "safe dry-run notification",
                    "--json",
                ).stdout
            )
            workspace = Workspace.load(workspace_path)
            queue = {item.id: item for item in queue_items(workspace)}
            work_detail = detail(workspace, "WORK-0001")

        self.assertEqual(payload["status"], "approved")
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(payload["integration_plan"]["reviewed_by"], "HUMAN-FOUNDER")
        self.assertEqual(payload["integration_plan"]["decision_reason"], "safe dry-run notification")
        self.assertEqual(workspace.integration_plan("PLAN-APPROVE").status, "approved")
        self.assertEqual(queue["WORK-0001"].integration_state, "plan-approved")
        self.assertEqual(work_detail["integration_plans"][0]["status"], "approved")

    def test_plan_reject_and_cancel_states_do_not_call_provider(self) -> None:
        for command, expected_status in (("reject", "rejected"), ("cancel", "canceled")):
            with self.subTest(command=command), self.temp_workspace() as workspace_path:
                plan_id = f"PLAN-{expected_status.upper()}"
                self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "plan",
                    "INT-SLACK-OPS",
                    "--work",
                    "WORK-0001",
                    "--event",
                    "approval_requested",
                    "--action",
                    "notify",
                    "--record",
                    "--id",
                    plan_id,
                    "--json",
                )
                payload = json.loads(
                    self.run_cli_in_workspace(
                        workspace_path,
                        "integration",
                        command,
                        plan_id,
                        "--by",
                        "HUMAN-FOUNDER",
                        "--reason",
                        f"{command} in test",
                        "--json",
                    ).stdout
                )
                workspace = Workspace.load(workspace_path)
                queue = {item.id: item for item in queue_items(workspace)}

            self.assertEqual(payload["status"], expected_status)
            self.assertFalse(payload["would_call_provider"])
            self.assertEqual(workspace.integration_plan(plan_id).status, expected_status)
            self.assertEqual(queue["WORK-0001"].integration_state, f"plan-{expected_status}")

    def test_unqualified_human_cannot_decide_plan(self) -> None:
        with self.temp_workspace() as workspace_path:
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "plan",
                "INT-SLACK-OPS",
                "--work",
                "WORK-0001",
                "--event",
                "approval_requested",
                "--action",
                "notify",
                "--record",
                "--id",
                "PLAN-UNQUALIFIED",
                "--json",
            )
            result = self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "approve",
                "PLAN-UNQUALIFIED",
                "--by",
                "HUMAN-OPS",
                "--json",
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lacks authority", result.stderr)

    def test_decided_plan_cannot_be_decided_again(self) -> None:
        with self.temp_workspace() as workspace_path:
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "plan",
                "INT-SLACK-OPS",
                "--work",
                "WORK-0001",
                "--event",
                "approval_requested",
                "--action",
                "notify",
                "--record",
                "--id",
                "PLAN-ONCE",
                "--json",
            )
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "reject",
                "PLAN-ONCE",
                "--by",
                "HUMAN-FOUNDER",
                "--reason",
                "not needed",
                "--json",
            )
            result = self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "approve",
                "PLAN-ONCE",
                "--by",
                "HUMAN-FOUNDER",
                "--json",
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot transition from rejected", result.stderr)

    def test_approved_plan_can_be_enqueued_without_provider_call(self) -> None:
        with self.temp_workspace() as workspace_path:
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "plan",
                "INT-SLACK-OPS",
                "--work",
                "WORK-0001",
                "--event",
                "approval_requested",
                "--action",
                "notify",
                "--record",
                "--id",
                "PLAN-ENQUEUE",
                "--json",
            )
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "approve",
                "PLAN-ENQUEUE",
                "--by",
                "HUMAN-FOUNDER",
                "--reason",
                "queue for test",
                "--json",
            )
            payload = json.loads(
                self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "enqueue",
                    "PLAN-ENQUEUE",
                    "--by",
                    "HUMAN-FOUNDER",
                    "--json",
                ).stdout
            )
            workspace = Workspace.load(workspace_path)
            queue = {item.id: item for item in queue_items(workspace)}
            work_detail = detail(workspace, "WORK-0001")

        outbox = payload["integration_outbox_item"]
        self.assertEqual(payload["status"], "queued")
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(outbox["plan_id"], "PLAN-ENQUEUE")
        self.assertEqual(outbox["enqueued_by"], "HUMAN-FOUNDER")
        self.assertEqual(len(workspace.integration_outbox), 1)
        self.assertEqual(queue["WORK-0001"].attention, "ready-to-integrate")
        self.assertEqual(queue["WORK-0001"].integration_state, "outbox-queued")
        self.assertEqual(work_detail["integration_outbox"][0]["plan_id"], "PLAN-ENQUEUE")

    def test_outbox_check_preflights_queued_item_without_provider_call(self) -> None:
        with self.temp_workspace() as workspace_path:
            enqueued = self.record_approve_enqueue(workspace_path, "PLAN-PREFLIGHT")
            outbox_id = enqueued["integration_outbox_item"]["id"]
            payload = json.loads(
                self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "outbox-check",
                    outbox_id,
                    "--json",
                ).stdout
            )
            text = self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "outbox-check",
                outbox_id,
            ).stdout

        self.assertEqual(payload["schema_version"], "palari.integration_outbox_check.v1")
        self.assertEqual(payload["status"], "queued-preflight-ready")
        self.assertFalse(payload["would_call_provider"])
        self.assertFalse(payload["execution_enabled"])
        self.assertEqual(payload["integration"]["provider"], "slack")
        self.assertEqual(payload["payload_preview"]["provider"], "slack")
        self.assertTrue(all(check["status"] == "pass" for check in payload["checks"]))
        self.assertIn("Integration outbox preflight", text)
        self.assertIn("Execution enabled: no", text)

    def test_queued_outbox_can_be_canceled_without_provider_call(self) -> None:
        with self.temp_workspace() as workspace_path:
            enqueued = self.record_approve_enqueue(workspace_path, "PLAN-CANCEL-OUTBOX")
            outbox_id = enqueued["integration_outbox_item"]["id"]
            payload = json.loads(
                self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "outbox-cancel",
                    outbox_id,
                    "--by",
                    "HUMAN-FOUNDER",
                    "--reason",
                    "not needed after all",
                    "--json",
                ).stdout
            )
            workspace = Workspace.load(workspace_path)
            queue = {item.id: item for item in queue_items(workspace)}
            work_detail = detail(workspace, "WORK-0001")

        outbox = payload["integration_outbox_item"]
        self.assertEqual(payload["status"], "canceled")
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(outbox["status"], "canceled")
        self.assertEqual(outbox["canceled_by"], "HUMAN-FOUNDER")
        self.assertEqual(outbox["cancel_reason"], "not needed after all")
        self.assertEqual(workspace.integration_outbox_item(outbox_id).status, "canceled")
        self.assertEqual(queue["WORK-0001"].integration_state, "outbox-canceled")
        self.assertEqual(queue["WORK-0001"].attention, "needs-human-decision")
        self.assertEqual(work_detail["integration_outbox"][0]["status"], "canceled")

    def test_outbox_check_blocks_canceled_item_without_provider_call(self) -> None:
        with self.temp_workspace() as workspace_path:
            enqueued = self.record_approve_enqueue(workspace_path, "PLAN-PREFLIGHT-CANCELED")
            outbox_id = enqueued["integration_outbox_item"]["id"]
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "outbox-cancel",
                outbox_id,
                "--by",
                "HUMAN-FOUNDER",
                "--reason",
                "not needed after all",
                "--json",
            )
            payload = json.loads(
                self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "outbox-check",
                    outbox_id,
                    "--json",
                ).stdout
            )

        checks = {check["code"]: check for check in payload["checks"]}
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(checks["STATUS_QUEUED"]["status"], "fail")
        self.assertIn("canceled", checks["STATUS_QUEUED"]["message"])

    def test_non_queued_outbox_cannot_be_canceled(self) -> None:
        with self.temp_workspace() as workspace_path:
            enqueued = self.record_approve_enqueue(workspace_path, "PLAN-CANCEL-ONCE")
            outbox_id = enqueued["integration_outbox_item"]["id"]
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "outbox-cancel",
                outbox_id,
                "--by",
                "HUMAN-FOUNDER",
                "--reason",
                "first cancel",
                "--json",
            )
            result = self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "outbox-cancel",
                outbox_id,
                "--by",
                "HUMAN-FOUNDER",
                "--reason",
                "second cancel",
                "--json",
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot be canceled from canceled", result.stderr)

    def test_unqualified_human_cannot_cancel_outbox(self) -> None:
        with self.temp_workspace() as workspace_path:
            enqueued = self.record_approve_enqueue(workspace_path, "PLAN-CANCEL-UNQUALIFIED")
            outbox_id = enqueued["integration_outbox_item"]["id"]
            result = self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "outbox-cancel",
                outbox_id,
                "--by",
                "HUMAN-OPS",
                "--reason",
                "not my call",
                "--json",
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lacks authority", result.stderr)

    def test_pending_rejected_and_canceled_plans_cannot_be_enqueued(self) -> None:
        cases = (
            ("pending-approval", ()),
            ("rejected", ("reject",)),
            ("canceled", ("cancel",)),
        )
        for expected_status, decision in cases:
            with self.subTest(status=expected_status), self.temp_workspace() as workspace_path:
                plan_id = f"PLAN-{expected_status.upper()}"
                self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "plan",
                    "INT-SLACK-OPS",
                    "--work",
                    "WORK-0001",
                    "--event",
                    "approval_requested",
                    "--action",
                    "notify",
                    "--record",
                    "--id",
                    plan_id,
                    "--json",
                )
                if decision:
                    self.run_cli_in_workspace(
                        workspace_path,
                        "integration",
                        decision[0],
                        plan_id,
                        "--by",
                        "HUMAN-FOUNDER",
                        "--reason",
                        "not going out",
                        "--json",
                    )
                result = self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "enqueue",
                    plan_id,
                    "--by",
                    "HUMAN-FOUNDER",
                    "--json",
                    check=False,
                )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(f"status is {expected_status}", result.stderr)

    def test_duplicate_enqueue_fails_closed(self) -> None:
        with self.temp_workspace() as workspace_path:
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "plan",
                "INT-SLACK-OPS",
                "--work",
                "WORK-0001",
                "--event",
                "approval_requested",
                "--action",
                "notify",
                "--record",
                "--id",
                "PLAN-DUPLICATE-ENQUEUE",
                "--json",
            )
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "approve",
                "PLAN-DUPLICATE-ENQUEUE",
                "--by",
                "HUMAN-FOUNDER",
                "--json",
            )
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "enqueue",
                "PLAN-DUPLICATE-ENQUEUE",
                "--by",
                "HUMAN-FOUNDER",
                "--json",
            )
            result = self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "enqueue",
                "PLAN-DUPLICATE-ENQUEUE",
                "--by",
                "HUMAN-FOUNDER",
                "--json",
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already enqueued", result.stderr)

    def test_unqualified_human_cannot_enqueue(self) -> None:
        with self.temp_workspace() as workspace_path:
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "plan",
                "INT-SLACK-OPS",
                "--work",
                "WORK-0001",
                "--event",
                "approval_requested",
                "--action",
                "notify",
                "--record",
                "--id",
                "PLAN-ENQUEUE-UNQUALIFIED",
                "--json",
            )
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "approve",
                "PLAN-ENQUEUE-UNQUALIFIED",
                "--by",
                "HUMAN-FOUNDER",
                "--json",
            )
            result = self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "enqueue",
                "PLAN-ENQUEUE-UNQUALIFIED",
                "--by",
                "HUMAN-OPS",
                "--json",
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lacks authority", result.stderr)

    def test_plain_plan_preview_does_not_write_workspace_state(self) -> None:
        with self.temp_workspace() as workspace_path:
            payload = json.loads(
                self.run_cli_in_workspace(
                    workspace_path,
                    "integration",
                    "plan",
                    "INT-SLACK-OPS",
                    "--work",
                    "WORK-0001",
                    "--event",
                    "approval_requested",
                    "--action",
                    "notify",
                    "--json",
                ).stdout
            )
            workspace = Workspace.load(workspace_path)

        self.assertFalse(payload["recorded"])
        self.assertEqual(workspace.integration_plans, [])

    def test_plan_record_with_disabled_integration_fails_closed(self) -> None:
        def disabled_plan(data: dict[str, object]) -> None:
            data["integrations"][0]["enabled"] = False
            data["integration_plans"] = [
                {
                    "id": "PLAN-BAD",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "approval_requested",
                    "action": "notify",
                    "actor": "PALARI-SOFIA",
                    "status": "pending-approval",
                    "payload_preview": {},
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": True,
                }
            ]

        with self.assertRaisesRegex(
            WorkspaceError,
            "references disabled integration INT-SLACK-OPS",
        ):
            self.modified_workspace(disabled_plan)

    def test_plan_record_must_use_allowed_event_and_action(self) -> None:
        def bad_event(data: dict[str, object]) -> None:
            data["integration_plans"] = [
                {
                    "id": "PLAN-BAD",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "work_completed",
                    "action": "notify",
                    "actor": "PALARI-SOFIA",
                    "status": "pending-approval",
                    "payload_preview": {},
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": True,
                }
            ]

        def bad_action(data: dict[str, object]) -> None:
            data["integration_plans"] = [
                {
                    "id": "PLAN-BAD",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "approval_requested",
                    "action": "comment",
                    "actor": "PALARI-SOFIA",
                    "status": "pending-approval",
                    "payload_preview": {},
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": True,
                }
            ]

        with self.assertRaisesRegex(WorkspaceError, "event 'work_completed' is not allowed"):
            self.modified_workspace(bad_event)
        with self.assertRaisesRegex(WorkspaceError, "action 'comment' is not allowed"):
            self.modified_workspace(bad_action)

    def test_plan_record_requires_human_approval_flag(self) -> None:
        def no_approval(data: dict[str, object]) -> None:
            data["integration_plans"] = [
                {
                    "id": "PLAN-BAD",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "approval_requested",
                    "action": "notify",
                    "actor": "PALARI-SOFIA",
                    "status": "pending-approval",
                    "payload_preview": {},
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": False,
                }
            ]

        with self.assertRaisesRegex(WorkspaceError, "approval_required must be true"):
            self.modified_workspace(no_approval)

    def test_plan_payload_cannot_store_raw_secret(self) -> None:
        def raw_secret_plan_payload(data: dict[str, object]) -> None:
            data["integration_plans"] = [
                {
                    "id": "PLAN-RAW-PAYLOAD",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "approval_requested",
                    "action": "notify",
                    "actor": "PALARI-SOFIA",
                    "status": "pending-approval",
                    "payload_preview": {
                        "operation": "post_message",
                        "webhook_ref": "xoxb-real-token-looking-value",
                    },
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": True,
                }
            ]

        with self.assertRaisesRegex(WorkspaceError, "not a raw secret"):
            self.modified_workspace(raw_secret_plan_payload)

    def test_receipt_planned_external_write_references_plan_without_actual_write(self) -> None:
        def add_plan_to_receipt(data: dict[str, object]) -> None:
            data["integration_plans"] = [
                {
                    "id": "PLAN-RECEIPT",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0007",
                    "event": "approval_requested",
                    "action": "notify",
                    "actor": "PALARI-SOFIA",
                    "status": "approved",
                    "payload_preview": {"operation": "post_message"},
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": True,
                    "reviewed_by": "HUMAN-FOUNDER",
                    "reviewed_at": "2026-06-21T00:00:00Z",
                }
            ]
            data["receipts"][0]["planned_external_writes"] = ["PLAN-RECEIPT"]

        workspace = self.modified_workspace(add_plan_to_receipt)

        self.assertEqual(
            workspace.receipts[0].planned_external_writes,
            ["PLAN-RECEIPT"],
        )
        self.assertEqual(workspace.receipts[0].external_writes, [])

    def test_receipt_planned_external_write_for_other_work_item_fails_closed(self) -> None:
        def wrong_work(data: dict[str, object]) -> None:
            data["integration_plans"] = [
                {
                    "id": "PLAN-WRONG-WORK",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "approval_requested",
                    "action": "notify",
                    "actor": "PALARI-SOFIA",
                    "status": "approved",
                    "payload_preview": {"operation": "post_message"},
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": True,
                    "reviewed_by": "HUMAN-FOUNDER",
                    "reviewed_at": "2026-06-21T00:00:00Z",
                }
            ]
            data["receipts"][0]["planned_external_writes"] = ["PLAN-WRONG-WORK"]

        with self.assertRaisesRegex(WorkspaceError, "for different work item WORK-0001"):
            self.modified_workspace(wrong_work)

    def test_receipt_planned_external_write_requires_approved_plan(self) -> None:
        for status in ("pending-approval", "rejected", "canceled"):
            with self.subTest(status=status):
                def non_approved_plan(data: dict[str, object]) -> None:
                    record = {
                        "id": "PLAN-NOT-APPROVED",
                        "integration_id": "INT-SLACK-OPS",
                        "work_item_id": "WORK-0007",
                        "event": "approval_requested",
                        "action": "notify",
                        "actor": "PALARI-SOFIA",
                        "status": status,
                        "payload_preview": {"operation": "post_message"},
                        "source_boundary": {},
                        "risk": "standard",
                        "approval_required": True,
                    }
                    if status in {"rejected", "canceled"}:
                        record["reviewed_by"] = "HUMAN-FOUNDER"
                        record["reviewed_at"] = "2026-06-21T00:00:00Z"
                        record["decision_reason"] = "not needed"
                    data["integration_plans"] = [record]
                    data["receipts"][0]["planned_external_writes"] = ["PLAN-NOT-APPROVED"]

                with self.assertRaisesRegex(WorkspaceError, "requires approved integration plan"):
                    self.modified_workspace(non_approved_plan)

    def test_receipt_queued_external_write_references_outbox_without_actual_write(self) -> None:
        def add_outbox_to_receipt(data: dict[str, object]) -> None:
            data["integration_plans"] = [
                {
                    "id": "PLAN-QUEUED-RECEIPT",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0007",
                    "event": "approval_requested",
                    "action": "notify",
                    "actor": "PALARI-SOFIA",
                    "status": "approved",
                    "payload_preview": {"operation": "post_message", "webhook_ref": "env:PALARI_SLACK_WEBHOOK_URL"},
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": True,
                    "reviewed_by": "HUMAN-FOUNDER",
                    "reviewed_at": "2026-06-21T00:00:00Z",
                }
            ]
            data["integration_outbox"] = [
                {
                    "id": "OUTBOX-RECEIPT",
                    "plan_id": "PLAN-QUEUED-RECEIPT",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0007",
                    "event": "approval_requested",
                    "action": "notify",
                    "enqueued_by": "HUMAN-FOUNDER",
                    "status": "queued",
                    "payload_preview": {
                        "operation": "post_message",
                        "webhook_ref": "env:PALARI_SLACK_WEBHOOK_URL",
                    },
                    "source_boundary": {},
                    "risk": "standard",
                    "timestamp": "2026-06-21T00:00:01Z",
                }
            ]
            data["receipts"][0]["queued_external_writes"] = ["OUTBOX-RECEIPT"]

        workspace = self.modified_workspace(add_outbox_to_receipt)

        self.assertEqual(workspace.receipts[0].queued_external_writes, ["OUTBOX-RECEIPT"])
        self.assertEqual(workspace.receipts[0].external_writes, [])

    def test_receipt_queued_external_write_must_match_work_and_status(self) -> None:
        def wrong_work(data: dict[str, object]) -> None:
            data["integration_plans"] = [
                {
                    "id": "PLAN-QUEUED-WRONG-WORK",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "approval_requested",
                    "action": "notify",
                    "actor": "PALARI-SOFIA",
                    "status": "approved",
                    "payload_preview": {"operation": "post_message"},
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": True,
                    "reviewed_by": "HUMAN-FOUNDER",
                    "reviewed_at": "2026-06-21T00:00:00Z",
                }
            ]
            data["integration_outbox"] = [
                {
                    "id": "OUTBOX-WRONG-WORK",
                    "plan_id": "PLAN-QUEUED-WRONG-WORK",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "approval_requested",
                    "action": "notify",
                    "enqueued_by": "HUMAN-FOUNDER",
                    "status": "queued",
                    "payload_preview": {"operation": "post_message"},
                    "source_boundary": {},
                    "risk": "standard",
                }
            ]
            data["receipts"][0]["queued_external_writes"] = ["OUTBOX-WRONG-WORK"]

        def canceled_item(data: dict[str, object]) -> None:
            wrong_work(data)
            data["integration_plans"][0]["id"] = "PLAN-QUEUED-CANCELED"
            data["integration_outbox"][0]["id"] = "OUTBOX-CANCELED"
            data["integration_outbox"][0]["plan_id"] = "PLAN-QUEUED-CANCELED"
            data["integration_outbox"][0]["work_item_id"] = "WORK-0007"
            data["integration_plans"][0]["work_item_id"] = "WORK-0007"
            data["integration_outbox"][0]["status"] = "canceled"
            data["integration_outbox"][0]["canceled_by"] = "HUMAN-FOUNDER"
            data["integration_outbox"][0]["canceled_at"] = "2026-06-21T00:00:02Z"
            data["integration_outbox"][0]["cancel_reason"] = "not needed"
            data["receipts"][0]["queued_external_writes"] = ["OUTBOX-CANCELED"]

        with self.assertRaisesRegex(WorkspaceError, "for different work item WORK-0001"):
            self.modified_workspace(wrong_work)
        with self.assertRaisesRegex(WorkspaceError, "requires queued outbox item"):
            self.modified_workspace(canceled_item)

    def test_outbox_payload_and_source_boundary_must_match_approved_plan(self) -> None:
        def base_plan_and_outbox() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
            plan = {
                "id": "PLAN-OUTBOX-MATCH",
                "integration_id": "INT-SLACK-OPS",
                "work_item_id": "WORK-0007",
                "event": "approval_requested",
                "action": "notify",
                "actor": "PALARI-SOFIA",
                "status": "approved",
                "payload_preview": {"operation": "post_message", "text": "approved preview"},
                "source_boundary": {"sources": ["SOURCE-0001"]},
                "risk": "standard",
                "approval_required": True,
                "reviewed_by": "HUMAN-FOUNDER",
                "reviewed_at": "2026-06-21T00:00:00Z",
            }
            outbox = {
                "id": "OUTBOX-DRIFT",
                "plan_id": "PLAN-OUTBOX-MATCH",
                "integration_id": "INT-SLACK-OPS",
                "work_item_id": "WORK-0007",
                "event": "approval_requested",
                "action": "notify",
                "enqueued_by": "HUMAN-FOUNDER",
                "status": "queued",
                "payload_preview": {"operation": "post_message", "text": "approved preview"},
                "source_boundary": {"sources": ["SOURCE-0001"]},
                "risk": "standard",
                "timestamp": "2026-06-21T00:00:01Z",
            }
            return [plan], [outbox]

        def payload_drift(data: dict[str, object]) -> None:
            plans, outbox = base_plan_and_outbox()
            outbox[0]["payload_preview"] = {"operation": "post_message", "text": "changed"}
            data["integration_plans"] = plans
            data["integration_outbox"] = outbox

        def source_boundary_drift(data: dict[str, object]) -> None:
            plans, outbox = base_plan_and_outbox()
            outbox[0]["source_boundary"] = {"sources": []}
            data["integration_plans"] = plans
            data["integration_outbox"] = outbox

        with self.assertRaisesRegex(WorkspaceError, "payload_preview does not match"):
            self.modified_workspace(payload_drift)
        with self.assertRaisesRegex(WorkspaceError, "source_boundary does not match"):
            self.modified_workspace(source_boundary_drift)

    def test_outbox_payload_cannot_store_raw_secret(self) -> None:
        def raw_secret_payload(data: dict[str, object]) -> None:
            data["integration_plans"] = [
                {
                    "id": "PLAN-RAW-OUTBOX",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "approval_requested",
                    "action": "notify",
                    "actor": "PALARI-SOFIA",
                    "status": "approved",
                    "payload_preview": {"operation": "post_message"},
                    "source_boundary": {},
                    "risk": "standard",
                    "approval_required": True,
                    "reviewed_by": "HUMAN-FOUNDER",
                    "reviewed_at": "2026-06-21T00:00:00Z",
                }
            ]
            data["integration_outbox"] = [
                {
                    "id": "OUTBOX-RAW",
                    "plan_id": "PLAN-RAW-OUTBOX",
                    "integration_id": "INT-SLACK-OPS",
                    "work_item_id": "WORK-0001",
                    "event": "approval_requested",
                    "action": "notify",
                    "enqueued_by": "HUMAN-FOUNDER",
                    "status": "queued",
                    "payload_preview": {
                        "operation": "post_message",
                        "webhook_ref": "xoxb-real-token-looking-value",
                    },
                    "source_boundary": {},
                    "risk": "standard",
                }
            ]

        with self.assertRaisesRegex(WorkspaceError, "not a raw secret"):
            self.modified_workspace(raw_secret_payload)

    def test_receipt_planned_external_write_missing_plan_fails_closed(self) -> None:
        def missing_plan(data: dict[str, object]) -> None:
            data["receipts"][0]["planned_external_writes"] = ["PLAN-MISSING"]

        with self.assertRaisesRegex(
            WorkspaceError,
            "planned_external_writes references missing id PLAN-MISSING",
        ):
            self.modified_workspace(missing_plan)

    def modified_workspace(self, mutate: object) -> Workspace:
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        mutate(source)
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            workspace_file.write_text(json.dumps(source), encoding="utf-8")
            return Workspace.load(workspace_file)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
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
        )

    def run_cli_in_workspace(
        self,
        workspace: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(workspace), *args],
            cwd=REPO_ROOT,
            env=env,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def record_approve_enqueue(self, workspace_path: Path, plan_id: str) -> dict[str, object]:
        self.run_cli_in_workspace(
            workspace_path,
            "integration",
            "plan",
            "INT-SLACK-OPS",
            "--work",
            "WORK-0001",
            "--event",
            "approval_requested",
            "--action",
            "notify",
            "--record",
            "--id",
            plan_id,
            "--json",
        )
        self.run_cli_in_workspace(
            workspace_path,
            "integration",
            "approve",
            plan_id,
            "--by",
            "HUMAN-FOUNDER",
            "--reason",
            "test approval",
            "--json",
        )
        return json.loads(
            self.run_cli_in_workspace(
                workspace_path,
                "integration",
                "enqueue",
                plan_id,
                "--by",
                "HUMAN-FOUNDER",
                "--json",
            ).stdout
        )

    def temp_workspace(self) -> object:
        return _TempWorkspace()

class _TempWorkspace:
    def __enter__(self) -> Path:
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name)
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        write_store(WorkspaceStore(data_path=self.path / "workspace.json", data=source))
        return self.path

    def __exit__(self, *_args: object) -> None:
        self._directory.cleanup()


if __name__ == "__main__":
    unittest.main()
