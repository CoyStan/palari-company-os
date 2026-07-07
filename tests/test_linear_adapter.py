from __future__ import annotations

import json
import shutil
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
    linear_import,
    linear_issue,
    linear_post_gate,
    linear_send,
    linear_start,
    linear_status,
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

    def test_status_maps_palari_queue_state_to_linear_facing_status(self) -> None:
        with temp_workspace() as workspace_path:
            before = linear_status(workspace_path, "ENG-123")
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="generic",
                adopt_by="HUMAN-FOUNDER",
                client=FakeLinearClient(valid_issue()),
            )
            after = linear_status(workspace_path, "ENG-123")

        self.assertEqual(before["status"], "NEEDS_HUMAN")
        self.assertEqual(after["status"], "READY")
        self.assertEqual(after["work_item"]["external_key"], "ENG-123")

    def test_graphql_errors_array_fails_even_with_http_200(self) -> None:
        client = LinearClient("test-token")
        response = FakeResponse({"errors": [{"message": "issue missing"}], "data": {}})

        with patch("urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(WorkspaceError, "Linear GraphQL error: issue missing"):
                client.request("query { viewer { id } }", {})

    def test_structured_block_parser_rejects_unknown_fields(self) -> None:
        block = parse_palari_block('```palari\n{"goal": "GOAL-0001", "x": 1}\n```')

        self.assertTrue(block.present)
        self.assertFalse(block.valid)
        self.assertIn("unknown palari governance fields", block.error)

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


def valid_issue(description: str | None = None) -> dict[str, Any]:
    return {
        "id": "linear-issue-id",
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


class TempWorkspace:
    def __enter__(self) -> str:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        shutil.copytree(WORKSPACE, root / "workspace")
        return str(root / "workspace" / "workspace.json")

    def __exit__(self, *_args: object) -> None:
        self._tmp.cleanup()
