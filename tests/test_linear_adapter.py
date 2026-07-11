from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.integrations import decide_integration_plan, enqueue_integration_plan
from palari_company_os.linear_adapter import (
    LinearClient,
    linear_block_template,
    linear_connect,
    linear_doctor,
    linear_import,
    linear_inspect_block,
    linear_issue,
    linear_issues,
    linear_linked,
    linear_post_gate,
    linear_send,
    linear_start,
    linear_status,
    linear_sync,
    parse_palari_block,
)
from palari_company_os.read_models import detail, queue_items
from palari_company_os.workspace import Workspace, WorkspaceError


WORKSPACE = REPO_ROOT / "src" / "palari_company_os" / "data" / "examples" / "acme-company-os"


class FakeLinearClient:
    def __init__(self, issue: dict[str, Any]) -> None:
        self._issue = issue
        self.created_comments: list[dict[str, str]] = []

    def issue(self, identifier: str) -> dict[str, Any]:
        return dict(self._issue, key=identifier, identifier=identifier)

    def create_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        self.created_comments.append({"issue_id": issue_id, "body": body})
        return {
            "id": "comment-123",
            "url": "https://linear.app/acme/issue/ENG-123#comment-123",
            "createdAt": "2026-07-07T00:00:00.000Z",
        }


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class LinearAdapterTests(unittest.TestCase):
    def test_linear_issue_fetches_and_normalizes_mocked_issue(self) -> None:
        payload = linear_issue("ENG-123", client=FakeLinearClient(valid_issue()))

        self.assertFalse(payload["would_mutate_workspace"])
        self.assertEqual(payload["issue"]["id"], "linear-issue-id")
        self.assertEqual(payload["issue"]["key"], "ENG-123")
        self.assertEqual(payload["issue"]["labels"][0]["name"], "docs")

    def test_linear_doctor_reports_readiness_without_secrets_or_provider_access(self) -> None:
        with temp_workspace() as workspace_path:
            with patch.dict(os.environ, {}, clear=True):
                missing = linear_doctor(workspace_path)
            with patch.dict(os.environ, {"LINEAR_API_KEY": "super-secret-token"}, clear=True):
                present = linear_doctor(workspace_path)

        self.assertFalse(missing["env"]["linear_api_key_present"])
        self.assertTrue(present["env"]["linear_api_key_present"])
        self.assertFalse(present["env"]["secret_value_stored"])
        self.assertIn("issue", present["live_provider_commands"])
        self.assertNotIn("super-secret-token", json.dumps(present))

    def test_import_creates_idempotent_proposal_with_external_refs(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearClient(valid_issue())
            first = linear_import(workspace_path, "ENG-123", "PALARI-SOFIA", client=client)
            second = linear_import(workspace_path, "ENG-123", "PALARI-SOFIA", client=client)
            workspace = Workspace.load(workspace_path)
            proposals = [proposal for proposal in workspace.proposals if proposal.external_key == "ENG-123"]

        self.assertEqual(first["action"], "created")
        self.assertEqual(second["action"], "updated")
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].id, "PROP-LINEAR-ENG-123")
        self.assertEqual(proposals[0].external_provider, "linear")
        self.assertEqual(proposals[0].allowed_resources, ["docs/product/company-os.md"])
        self.assertTrue(first["governance"]["valid"])

    def test_start_without_adopted_work_fails_closed_with_next_commands(self) -> None:
        with temp_workspace() as workspace_path:
            payload = linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="codex",
                client=FakeLinearClient(valid_issue()),
            )
            workspace = Workspace.load(workspace_path)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "needs_adoption")
        self.assertIn("palari proposal adopt PROP-LINEAR-ENG-123", payload["proposal_adopt_command"])
        self.assertIsNone(workspace.work_item("WORK-LINEAR-ENG-123"))

    def test_start_with_human_adoption_emits_governed_agent_packet(self) -> None:
        with temp_workspace() as workspace_path:
            payload = linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="codex",
                adopt_by="HUMAN-FOUNDER",
                client=FakeLinearClient(valid_issue()),
            )
            workspace = Workspace.load(workspace_path)
            queue = {item.id: item for item in queue_items(workspace)}
            work_detail = detail(workspace, "WORK-LINEAR-ENG-123")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["agent_start"]["status"], "ready")
        self.assertEqual(payload["agent_start"]["start"]["status"], "claimed")
        self.assertEqual(queue["WORK-LINEAR-ENG-123"].external_key, "ENG-123")
        self.assertEqual(work_detail["work_item"]["external_provider"], "linear")
        self.assertEqual(queue["WORK-LINEAR-ENG-123"].external_updated_at, "2026-07-07T00:00:00.000Z")
        self.assertEqual(work_detail["external"]["key"], "ENG-123")
        self.assertEqual(work_detail["external"]["updated_at"], "2026-07-07T00:00:00.000Z")

    def test_missing_or_invalid_palari_block_never_auto_starts(self) -> None:
        missing = valid_issue(description="Plain Linear text without a governance block.")
        invalid = valid_issue(
            description='```palari\n{"goal": "GOAL-0001", "surprise": true}\n```'
        )

        with temp_workspace() as workspace_path:
            missing_payload = linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="generic",
                adopt_by="HUMAN-FOUNDER",
                client=FakeLinearClient(missing),
            )
            invalid_import = linear_import(
                workspace_path,
                "ENG-124",
                "PALARI-SOFIA",
                client=FakeLinearClient(dict(invalid, id="linear-issue-id-2")),
            )
            workspace = Workspace.load(workspace_path)

        self.assertFalse(missing_payload["ok"])
        self.assertEqual(missing_payload["status"], "needs_adoption")
        self.assertFalse(invalid_import["governance"]["valid"])
        self.assertIn("unknown palari governance fields", invalid_import["governance"]["error"])
        self.assertIsNone(workspace.work_item("WORK-LINEAR-ENG-123"))
        self.assertIsNone(workspace.work_item("WORK-LINEAR-ENG-124"))

    def test_agent_cannot_self_adopt_with_palari_id(self) -> None:
        with temp_workspace() as workspace_path:
            with self.assertRaisesRegex(WorkspaceError, "adopt-by must name a human"):
                linear_start(
                    workspace_path,
                    "ENG-123",
                    "PALARI-SOFIA",
                    runner="codex",
                    adopt_by="PALARI-SOFIA",
                    client=FakeLinearClient(valid_issue()),
                )

    def test_post_gate_records_plan_and_send_records_provider_metadata(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearClient(valid_issue())
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="codex",
                adopt_by="HUMAN-FOUNDER",
                client=client,
            )
            planned = linear_post_gate(
                workspace_path,
                "ENG-123",
                event="review_requested",
                actor="PALARI-SOFIA",
                record=True,
            )
            plan_id = planned["integration_plan"]["id"]
            decide_integration_plan(
                workspace_path,
                plan_id,
                "HUMAN-FOUNDER",
                "approve",
                reason="send Linear visibility update",
            )
            enqueued = enqueue_integration_plan(workspace_path, plan_id, "HUMAN-FOUNDER")
            outbox_id = enqueued["integration_outbox_item"]["id"]
            with self.assertRaisesRegex(WorkspaceError, "--confirm"):
                linear_send(
                    workspace_path,
                    outbox_id,
                    human_id="HUMAN-FOUNDER",
                    confirm=False,
                    client=client,
                )
            sent = linear_send(
                workspace_path,
                outbox_id,
                human_id="HUMAN-FOUNDER",
                confirm=True,
                client=client,
            )
            workspace = Workspace.load(workspace_path)
            outbox_item = workspace.integration_outbox_item(outbox_id)

        self.assertTrue(planned["recorded"])
        self.assertFalse(planned["would_call_provider"])
        self.assertEqual(planned["payload_preview"]["operation"], "commentCreate")
        self.assertEqual(sent["status"], "sent")
        self.assertEqual(outbox_item.status, "sent")
        self.assertEqual(outbox_item.provider_response["id"], "comment-123")
        self.assertEqual(client.created_comments[0]["issue_id"], "linear-issue-id")

    def test_send_rejects_drift_and_records_failed_metadata(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearClient(valid_issue())
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="codex",
                adopt_by="HUMAN-FOUNDER",
                client=client,
            )
            planned = linear_post_gate(
                workspace_path,
                "ENG-123",
                event="review_requested",
                actor="PALARI-SOFIA",
                record=True,
            )
            plan_id = planned["integration_plan"]["id"]
            decide_integration_plan(
                workspace_path,
                plan_id,
                "HUMAN-FOUNDER",
                "approve",
                reason="send Linear visibility update",
            )
            enqueued = enqueue_integration_plan(workspace_path, plan_id, "HUMAN-FOUNDER")
            outbox_id = enqueued["integration_outbox_item"]["id"]

            workspace_file = Path(workspace_path)
            data = json.loads(workspace_file.read_text(encoding="utf-8"))
            for collection in ("integration_plans", "integration_outbox"):
                preview = data[collection][0]["payload_preview"]
                preview["issue_id"] = "linear-issue-drifted"
                preview["json"]["issueId"] = "linear-issue-drifted"
            workspace_file.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(WorkspaceError, "issueId drifted"):
                linear_send(
                    workspace_path,
                    outbox_id,
                    human_id="HUMAN-FOUNDER",
                    confirm=True,
                    client=client,
                )
            workspace = Workspace.load(workspace_path)
            outbox_item = workspace.integration_outbox_item(outbox_id)

        self.assertEqual(outbox_item.status, "failed")
        self.assertIn("issueId drifted", outbox_item.failure_reason)
        self.assertEqual(outbox_item.payload_preview["json"]["issueId"], "linear-issue-drifted")
        self.assertEqual(client.created_comments, [])

    def test_status_maps_palari_queue_state_to_linear_facing_status(self) -> None:
        with temp_workspace() as workspace_path:
            before = linear_status(workspace_path, "ENG-123")
            linear_import(
                workspace_path,
                "ENG-124",
                "PALARI-SOFIA",
                client=FakeLinearClient(
                    valid_issue(
                        description="Plain Linear text without a governance block.",
                        issue_id="linear-issue-id-124",
                    )
                ),
            )
            proposal_only = linear_status(workspace_path, "ENG-124")
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="generic",
                adopt_by="HUMAN-FOUNDER",
                client=FakeLinearClient(valid_issue()),
            )
            after = linear_status(workspace_path, "ENG-123")
            linked = linear_linked(workspace_path)

        self.assertEqual(before["status"], "NEEDS_HUMAN")
        self.assertEqual(before["link_state"], "not_imported")
        self.assertEqual(proposal_only["link_state"], "proposal_only")
        self.assertEqual(after["status"], "READY")
        self.assertEqual(after["link_state"], "work_linked")
        self.assertEqual(after["linear_ref"]["key"], "ENG-123")
        self.assertIn("gate_summary", after)
        self.assertIn("next_commands", after)
        self.assertEqual(after["work_item"]["external_key"], "ENG-123")
        linked_by_key = {item["linear_ref"]["key"]: item for item in linked["items"]}
        self.assertEqual(linked_by_key["ENG-124"]["link_state"], "proposal_only")
        self.assertEqual(linked_by_key["ENG-123"]["work_item"]["id"], "WORK-LINEAR-ENG-123")

    def test_graphql_errors_array_fails_even_with_http_200(self) -> None:
        client = LinearClient("test-token")
        response = FakeResponse({"errors": [{"message": "issue missing"}], "data": {}})

        with patch("urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(WorkspaceError, "Linear GraphQL error: issue missing") as caught:
                client.request("query { viewer { id } }", {})
        self.assertEqual(getattr(caught.exception, "code", ""), "LINEAR_GRAPHQL_ERROR")

    def test_structured_block_parser_rejects_unknown_fields(self) -> None:
        block = parse_palari_block('```palari\n{"goal": "GOAL-0001", "x": 1}\n```')

        self.assertTrue(block.present)
        self.assertFalse(block.valid)
        self.assertIn("unknown palari governance fields", block.error)
        self.assertEqual(block.unknown_fields, ["x"])

    def test_block_template_emits_valid_fenced_json_and_rejects_bad_refs(self) -> None:
        with temp_workspace() as workspace_path:
            payload = linear_block_template(
                workspace_path,
                "PALARI-SOFIA",
                "GOAL-0001",
                risk="R1",
                intensity="light",
                scope="Tighten onboarding copy without product behavior changes.",
                acceptance_target="Copy is clearer and tests still pass.",
                allowed_resources=["docs/product/company-os.md"],
                output_targets=["docs/product/company-os.md"],
                verification_expectations=["./scripts/verify.sh"],
            )
            with self.assertRaisesRegex(WorkspaceError, "goal not found"):
                linear_block_template(
                    workspace_path,
                    "PALARI-SOFIA",
                    "GOAL-MISSING",
                    risk="R1",
                    intensity="light",
                    scope="Scope",
                    acceptance_target="Acceptance",
                )

        self.assertTrue(payload["valid"])
        self.assertTrue(payload["fenced_block"].startswith("```palari\n"))
        self.assertTrue(payload["governance"]["valid"])
        self.assertEqual(payload["governance"]["fields"]["goal"], "GOAL-0001")

    def test_inspect_block_reports_validation_warnings_and_errors(self) -> None:
        unknown = valid_issue(description='```palari\n{"goal": "GOAL-0001", "x": 1}\n```')
        mismatch = valid_issue(
            description=valid_description().replace("PALARI-SOFIA", "PALARI-MISSING")
        )
        missing = valid_issue(description="No structured governance block.")
        bad_source = valid_issue(
            description=valid_description().replace(
                '"output_targets": ["docs/product/company-os.md"],',
                '"allowed_sources": ["SOURCE-MISSING"],\n'
                '  "output_targets": ["docs/product/company-os.md"],',
            )
        )

        with temp_workspace() as workspace_path:
            unknown_payload = linear_inspect_block(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                client=FakeLinearClient(unknown),
            )
            mismatch_payload = linear_inspect_block(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                client=FakeLinearClient(mismatch),
            )
            missing_payload = linear_inspect_block(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                client=FakeLinearClient(missing),
            )
            source_payload = linear_inspect_block(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                client=FakeLinearClient(bad_source),
            )

        self.assertFalse(unknown_payload["valid"])
        self.assertIn("x", unknown_payload["governance"]["unknown_fields"])
        self.assertFalse(mismatch_payload["eligible_for_adopt_start"])
        self.assertIn("not command actor", json.dumps(mismatch_payload["errors"]))
        self.assertFalse(missing_payload["governance"]["present"])
        self.assertIn("missing palari block", missing_payload["errors"])
        self.assertIn("allowed source not found", json.dumps(source_payload["errors"]))

    def test_linear_cli_json_errors_are_structured_and_redacted(self) -> None:
        with temp_workspace() as workspace_path:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT / "src")
            env.pop("LINEAR_API_KEY", None)
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    "-m",
                    "palari_company_os",
                    "--workspace",
                    workspace_path,
                    "linear",
                    "issue",
                    "ENG-123",
                    "--json",
                ],
                cwd=REPO_ROOT,
                env=env,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "LINEAR_API_KEY_MISSING")
        self.assertEqual(payload["error"]["command"], "linear issue ENG-123")
        self.assertIn("palari linear doctor --json", payload["next_allowed_commands"])
        self.assertNotIn("LINEAR_API_KEY=", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_linear_cli_local_smoke_commands_return_json(self) -> None:
        with temp_workspace() as workspace_path:
            doctor = run_cli_json(workspace_path, "linear", "doctor", "--json")
            linked = run_cli_json(workspace_path, "linear", "linked", "--json")
            block = run_cli_json(
                workspace_path,
                "linear",
                "block-template",
                "--as",
                "PALARI-SOFIA",
                "--goal",
                "GOAL-0001",
                "--risk",
                "R1",
                "--intensity",
                "light",
                "--scope",
                "Tighten onboarding copy without product behavior changes.",
                "--acceptance-target",
                "Copy is clearer and tests still pass.",
                "--verification",
                "./scripts/verify.sh",
                "--json",
            )

        self.assertTrue(doctor["ok"])
        self.assertEqual(linked["count"], 0)
        self.assertTrue(block["valid"])

    def test_unsupported_runner_fails_validation(self) -> None:
        with temp_workspace() as workspace_path:
            with self.assertRaisesRegex(WorkspaceError, "unsupported Linear runner"):
                linear_start(
                    workspace_path,
                    "ENG-123",
                    "PALARI-SOFIA",
                    runner="windsurf",
                    client=FakeLinearClient(valid_issue()),
                )


class FakeLinearWorkspaceClient(FakeLinearClient):
    """Fake with the full client surface: viewer, issues, states, issueUpdate."""

    def __init__(self, issue: dict[str, Any], *, teams: list[dict[str, str]] | None = None) -> None:
        super().__init__(issue)
        self.teams = teams if teams is not None else [
            {"id": "team-1", "key": "ENG", "name": "Engineering"}
        ]
        self.states = [
            {"id": "state-1", "name": "Todo", "type": "unstarted"},
            {"id": "state-2", "name": "In Progress", "type": "started"},
            {"id": "state-3", "name": "In Review", "type": "started"},
            {"id": "state-4", "name": "Done", "type": "completed"},
        ]
        self.state_updates: list[dict[str, str]] = []

    def viewer(self) -> dict[str, Any]:
        return {
            "viewer": {"id": "user-1", "name": "Rafa", "email": "rafa@example.com"},
            "organization": {"id": "org-1", "name": "Acme", "urlKey": "acme"},
            "teams": list(self.teams),
        }

    def team_issues(self, team_key: str, *, first: int = 25) -> list[dict[str, Any]]:
        return [dict(self._issue)]

    def team_states(self, team_key: str) -> list[dict[str, Any]]:
        return list(self.states)

    def update_issue_state(self, issue_id: str, state_id: str) -> dict[str, Any]:
        self.state_updates.append({"issue_id": issue_id, "state_id": state_id})
        state = next(item for item in self.states if item["id"] == state_id)
        return {
            "id": issue_id,
            "identifier": "ENG-123",
            "url": "https://linear.app/acme/issue/ENG-123",
            "state": dict(state),
        }


class LinearWorkspaceLoopTests(unittest.TestCase):
    def test_connect_without_key_prepares_record_and_reports_blocker(self) -> None:
        with temp_workspace() as workspace_path, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LINEAR_API_KEY", None)
            result = linear_connect(workspace_path, actor="HUMAN-FOUNDER")
            workspace = Workspace.load(workspace_path)

        self.assertFalse(result["ok"])
        self.assertEqual(result["blocker"]["code"], "LINEAR_API_KEY_MISSING")
        integration = workspace.integration("INT-LINEAR")
        self.assertIn("update_issue", integration.allowed_actions)
        self.assertIn("work_started", integration.allowed_events)
        self.assertTrue(any("LINEAR_API_KEY" in cmd for cmd in result["next_commands"]))

    def test_connect_with_client_verifies_and_reports_teams(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            result = linear_connect(workspace_path, actor="HUMAN-FOUNDER", client=client)

        self.assertTrue(result["ok"])
        self.assertTrue(result["connection"]["verified"])
        self.assertEqual(result["connection"]["teams"][0]["key"], "ENG")
        self.assertIn("palari linear issues --team ENG --json", result["next_commands"])

    def test_connect_is_idempotent(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            linear_connect(workspace_path, actor="HUMAN-FOUNDER", client=client)
            first = Workspace.load(workspace_path).integration("INT-LINEAR")
            linear_connect(workspace_path, actor="HUMAN-FOUNDER", client=client)
            second = Workspace.load(workspace_path).integration("INT-LINEAR")

        self.assertEqual(first.allowed_actions, second.allowed_actions)
        self.assertEqual(first.allowed_events, second.allowed_events)

    def test_issues_lists_team_issues_with_link_state(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            before_import = linear_issues(workspace_path, client=client)
            linear_import(workspace_path, "ENG-123", "PALARI-SOFIA", client=client)
            after_import = linear_issues(workspace_path, team_key="ENG", client=client)

        self.assertEqual(before_import["team"], "ENG")
        first = before_import["issues"][0]
        self.assertTrue(first["has_palari_block"])
        self.assertEqual(first["linked_proposal"], "")
        self.assertIn("linear import", first["next_command"])
        linked = after_import["issues"][0]
        self.assertTrue(linked["linked_proposal"])
        self.assertIn("linear start", linked["next_command"])

    def test_issues_requires_team_when_ambiguous(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(
                valid_issue(),
                teams=[
                    {"id": "team-1", "key": "ENG", "name": "Engineering"},
                    {"id": "team-2", "key": "OPS", "name": "Operations"},
                ],
            )
            with self.assertRaisesRegex(WorkspaceError, "--team"):
                linear_issues(workspace_path, client=client)

    def test_sync_refreshes_linked_records_without_webhooks(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            linear_import(workspace_path, "ENG-123", "PALARI-SOFIA", client=client)
            client._issue = dict(valid_issue(), title="Retitled in Linear")
            result = linear_sync(workspace_path, "ENG-123", client=client)
            workspace = Workspace.load(workspace_path)
            proposal = next(
                item for item in workspace.proposals if item.external_key == "ENG-123"
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["sync"]["mutated"])
        self.assertEqual(proposal.title, "Retitled in Linear")

    def test_sync_reports_unlinked_issue(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            result = linear_sync(workspace_path, "ENG-123", client=client)

        self.assertFalse(result["sync"]["mutated"])
        self.assertIn("linear import", result["next_action"])

    def test_status_update_flows_through_plan_approve_outbox_send(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            linear_connect(workspace_path, actor="HUMAN-FOUNDER", client=client)
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="codex",
                adopt_by="HUMAN-FOUNDER",
                client=client,
            )
            planned = linear_post_gate(
                workspace_path,
                "ENG-123",
                event="work_completed",
                actor="PALARI-SOFIA",
                record=True,
                action="update_issue",
            )
            plan = planned["integration_plan"]
            decide_integration_plan(
                workspace_path,
                plan["id"],
                "HUMAN-FOUNDER",
                "approve",
                reason="move the issue to Done",
            )
            enqueued = enqueue_integration_plan(workspace_path, plan["id"], "HUMAN-FOUNDER")
            outbox_id = enqueued["integration_outbox_item"]["id"]
            sent = linear_send(
                workspace_path,
                outbox_id,
                human_id="HUMAN-FOUNDER",
                confirm=True,
                client=client,
            )

        self.assertEqual(plan["action"], "update_issue")
        preview = plan["payload_preview"]
        self.assertEqual(preview["operation"], "issueUpdate")
        self.assertEqual(preview["target_state_type"], "completed")
        self.assertEqual(preview["team_key"], "ENG")
        self.assertEqual(sent["status"], "sent")
        self.assertEqual(sent["provider_response"]["state_name"], "Done")
        self.assertEqual(
            client.state_updates,
            [{"issue_id": "linear-issue-id", "state_id": "state-4"}],
        )
        self.assertEqual(client.created_comments, [])

    def test_status_update_with_explicit_state_name(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            linear_connect(workspace_path, actor="HUMAN-FOUNDER", client=client)
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="codex",
                adopt_by="HUMAN-FOUNDER",
                client=client,
            )
            planned = linear_post_gate(
                workspace_path,
                "ENG-123",
                event="review_requested",
                actor="PALARI-SOFIA",
                record=True,
                action="update_issue",
                target_state="In Review",
            )
            plan = planned["integration_plan"]
            decide_integration_plan(
                workspace_path, plan["id"], "HUMAN-FOUNDER", "approve", reason="review"
            )
            enqueued = enqueue_integration_plan(workspace_path, plan["id"], "HUMAN-FOUNDER")
            sent = linear_send(
                workspace_path,
                enqueued["integration_outbox_item"]["id"],
                human_id="HUMAN-FOUNDER",
                confirm=True,
                client=client,
            )

        self.assertEqual(sent["provider_response"]["state_name"], "In Review")
        self.assertEqual(client.state_updates[0]["state_id"], "state-3")

    def test_work_blocked_requires_explicit_state(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="codex",
                adopt_by="HUMAN-FOUNDER",
                client=client,
            )
            with self.assertRaisesRegex(WorkspaceError, "--to-state"):
                linear_post_gate(
                    workspace_path,
                    "ENG-123",
                    event="work_blocked",
                    actor="PALARI-SOFIA",
                    record=True,
                    action="update_issue",
                )

    def test_unknown_state_name_fails_at_send_with_available_states(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="codex",
                adopt_by="HUMAN-FOUNDER",
                client=client,
            )
            planned = linear_post_gate(
                workspace_path,
                "ENG-123",
                event="work_completed",
                actor="PALARI-SOFIA",
                record=True,
                action="update_issue",
                target_state="Shipped",
            )
            plan = planned["integration_plan"]
            decide_integration_plan(
                workspace_path, plan["id"], "HUMAN-FOUNDER", "approve", reason="ship"
            )
            enqueued = enqueue_integration_plan(workspace_path, plan["id"], "HUMAN-FOUNDER")
            outbox_id = enqueued["integration_outbox_item"]["id"]
            with self.assertRaisesRegex(WorkspaceError, "Shipped"):
                linear_send(
                    workspace_path,
                    outbox_id,
                    human_id="HUMAN-FOUNDER",
                    confirm=True,
                    client=client,
                )
            workspace = Workspace.load(workspace_path)
            outbox_item = workspace.integration_outbox_item(outbox_id)

        self.assertEqual(outbox_item.status, "failed")
        self.assertEqual(client.state_updates, [])

    def test_comment_send_still_works_after_action_generalization(self) -> None:
        with temp_workspace() as workspace_path:
            client = FakeLinearWorkspaceClient(valid_issue())
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="codex",
                adopt_by="HUMAN-FOUNDER",
                client=client,
            )
            planned = linear_post_gate(
                workspace_path,
                "ENG-123",
                event="review_requested",
                actor="PALARI-SOFIA",
                record=True,
            )
            plan = planned["integration_plan"]
            decide_integration_plan(
                workspace_path, plan["id"], "HUMAN-FOUNDER", "approve", reason="notify"
            )
            enqueued = enqueue_integration_plan(workspace_path, plan["id"], "HUMAN-FOUNDER")
            sent = linear_send(
                workspace_path,
                enqueued["integration_outbox_item"]["id"],
                human_id="HUMAN-FOUNDER",
                confirm=True,
                client=client,
            )

        self.assertEqual(plan["action"], "comment")
        self.assertEqual(sent["provider_response"]["id"], "comment-123")
        self.assertEqual(client.state_updates, [])


def valid_issue(description: str | None = None, *, issue_id: str = "linear-issue-id") -> dict[str, Any]:
    return {
        "id": issue_id,
        "key": "ENG-123",
        "identifier": "ENG-123",
        "title": "Tighten onboarding copy",
        "description": description if description is not None else valid_description(),
        "url": "https://linear.app/acme/issue/ENG-123/tighten-onboarding-copy",
        "updated_at": "2026-07-07T00:00:00.000Z",
        "state": {"id": "state-1", "name": "Todo", "type": "unstarted"},
        "team": {"id": "team-1", "key": "ENG", "name": "Engineering"},
        "labels": [{"id": "label-1", "name": "docs"}],
        "assignee": {"id": "user-1", "name": "Rafa", "email": "rafa@example.com"},
    }


def valid_description() -> str:
    return """
Tighten the onboarding copy while keeping behavior unchanged.

```palari
{
  "goal": "GOAL-0001",
  "palari": "PALARI-SOFIA",
  "risk": "R1",
  "intensity": "light",
  "scope": "Tighten onboarding copy without product behavior changes.",
  "allowed_resources": ["docs/product/company-os.md"],
  "output_targets": ["docs/product/company-os.md"],
  "forbidden_actions": ["edit deploy files"],
  "acceptance_target": "Copy is clearer and tests still pass.",
  "verification_expectations": ["./scripts/verify.sh"]
}
```
""".strip()


def temp_workspace() -> Any:
    return TempWorkspace()


def run_cli_json(workspace_path: str, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-m",
            "palari_company_os",
            "--workspace",
            workspace_path,
            *args,
        ],
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
        raise AssertionError(f"expected JSON object, got {payload!r}")
    return payload


class TempWorkspace:
    def __enter__(self) -> str:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        shutil.copytree(WORKSPACE, root / "workspace")
        return str(root / "workspace" / "workspace.json")

    def __exit__(self, *_args: object) -> None:
        self._tmp.cleanup()
