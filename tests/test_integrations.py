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
from palari_company_os.history import read_history
from palari_company_os.read_models import detail, queue_items
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

    def test_recorded_plan_is_visible_in_queue_detail_and_history(self) -> None:
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
            history = read_history(workspace_path)

        self.assertTrue(payload["recorded"])
        self.assertFalse(payload["would_call_provider"])
        self.assertEqual(payload["integration_plan"]["id"], "PLAN-TEST")
        self.assertEqual(workspace.integration_plan("PLAN-TEST").status, "pending-approval")
        self.assertEqual(queue["WORK-0001"].integration_state, "pending-plan")
        self.assertIn("Integration plan PLAN-TEST", queue["WORK-0001"].why)
        self.assertEqual(work_detail["integration_plans"][0]["id"], "PLAN-TEST")
        self.assertEqual(history["events"][-1]["object_type"], "integration-plan")
        self.assertEqual(history["events"][-1]["object_id"], "PLAN-TEST")

    def test_plain_plan_preview_does_not_write_history(self) -> None:
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
            history = read_history(workspace_path)

        self.assertFalse(payload["recorded"])
        self.assertEqual(workspace.integration_plans, [])
        self.assertEqual(history["events"], [])

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
                }
            ]
            data["receipts"][0]["planned_external_writes"] = ["PLAN-WRONG-WORK"]

        with self.assertRaisesRegex(WorkspaceError, "for different work item WORK-0001"):
            self.modified_workspace(wrong_work)

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
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(workspace), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def temp_workspace(self) -> object:
        return _TempWorkspace()

class _TempWorkspace:
    def __enter__(self) -> Path:
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name)
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        (self.path / "workspace.json").write_text(json.dumps(source), encoding="utf-8")
        return self.path

    def __exit__(self, *_args: object) -> None:
        self._directory.cleanup()


if __name__ == "__main__":
    unittest.main()
