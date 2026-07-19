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
from typing import Any, Iterator
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.integrations import decide_integration_plan, enqueue_integration_plan
from palari_company_os.cli_parser import build_parser
from palari_company_os.linear_adapter import (
    LinearAdapterError,
    LinearClient,
    linear_connect,
    linear_doctor,
    linear_import,
    linear_issue,
    linear_post_gate,
    linear_push,
    linear_send,
    linear_start,
    parse_palari_block,
)
from palari_company_os.store import WorkspaceStore, write_store
from palari_company_os.validation import COLLECTION_FILE_KEYS
from palari_company_os.workspace import Workspace, WorkspaceError


HUMAN_ID = "HUMAN-FOUNDER"
PALARI_ID = "PALARI-SOFIA"
GOAL_ID = "GOAL-0001"
LOCAL_WORK_ID = "WORK-LOCAL-0001"
LINKED_WORK_ID = "WORK-LINEAR-ENG-200"


class FakeLinearClient:
    """An in-memory provider boundary with no network or hidden lifecycle."""

    def __init__(self, issue: dict[str, Any] | None = None) -> None:
        self._issue = deepcopy(issue or valid_issue())
        self.created_comments: list[dict[str, str]] = []
        self.created_issues: list[dict[str, str]] = []
        self.state_updates: list[dict[str, str]] = []
        self.states = [
            {"id": "state-todo", "name": "Todo", "type": "unstarted"},
            {"id": "state-started", "name": "In Progress", "type": "started"},
            {"id": "state-done", "name": "Done", "type": "completed"},
        ]

    def issue(self, identifier: str) -> dict[str, Any]:
        return deepcopy(dict(self._issue, key=identifier, identifier=identifier))

    def viewer(self) -> dict[str, Any]:
        return {
            "viewer": {"id": "user-1", "name": "Rafa", "email": "rafa@example.com"},
            "organization": {"id": "org-1", "name": "Acme", "urlKey": "acme"},
            "teams": [{"id": "team-1", "key": "ENG", "name": "Engineering"}],
        }

    def team_issues(self, team_key: str, *, first: int = 25) -> list[dict[str, Any]]:
        del team_key, first
        return [deepcopy(self._issue)]

    def team_states(self, team_key: str) -> list[dict[str, str]]:
        if team_key != "ENG":
            return []
        return deepcopy(self.states)

    def create_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        self.created_comments.append({"issue_id": issue_id, "body": body})
        return {
            "id": "comment-123",
            "url": "https://linear.app/acme/issue/ENG-200#comment-123",
            "createdAt": "2026-07-19T00:00:00.000Z",
        }

    def update_issue_state(self, issue_id: str, state_id: str) -> dict[str, Any]:
        state = next(item for item in self.states if item["id"] == state_id)
        self.state_updates.append({"issue_id": issue_id, "state_id": state_id})
        return {
            "id": issue_id,
            "identifier": "ENG-200",
            "url": "https://linear.app/acme/issue/ENG-200",
            "state": deepcopy(state),
        }

    def create_issue(self, team_id: str, title: str, description: str) -> dict[str, Any]:
        self.created_issues.append(
            {"team_id": team_id, "title": title, "description": description}
        )
        return {
            "id": "created-issue-1",
            "identifier": "ENG-901",
            "key": "ENG-901",
            "title": title,
            "description": description,
            "url": "https://linear.app/acme/issue/ENG-901",
            "updated_at": "2026-07-19T00:00:00.000Z",
            "state": deepcopy(self.states[0]),
            "team": {"id": team_id, "key": "ENG", "name": "Engineering"},
            "labels": [],
            "assignee": {},
        }


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class LinearAdapterContractTests(unittest.TestCase):
    def test_cli_runner_surface_defaults_to_a_supported_adapter(self) -> None:
        args = build_parser().parse_args(
            [
                "--workspace",
                "/tmp/linear-contract-workspace.json",
                "linear",
                "start",
                "ENG-123",
                "--as",
                PALARI_ID,
            ]
        )
        runner_action = next(
            action
            for action in build_parser()._subparsers._group_actions[0]
            .choices["linear"]
            ._subparsers._group_actions[0]
            .choices["start"]
            ._actions
            if "--runner" in action.option_strings
        )

        self.assertEqual(args.runner, "codex")
        self.assertEqual(tuple(runner_action.choices), ("codex", "claude-code"))

    def test_issue_read_is_normalized_and_never_mutates_local_state(self) -> None:
        client = LinearClient("test-token")
        provider_issue = {
            "id": "linear-issue-id",
            "identifier": "ENG-123",
            "title": "Tighten onboarding copy",
            "description": "Provider description",
            "url": "https://linear.app/acme/issue/ENG-123",
            "updatedAt": "2026-07-19T00:00:00.000Z",
            "state": {"id": "state-todo", "name": "Todo", "type": "unstarted"},
            "team": {"id": "team-1", "key": "ENG", "name": "Engineering"},
            "labels": {"nodes": [{"id": "label-1", "name": "docs"}]},
            "assignee": {"id": "user-1", "name": "Rafa", "email": "rafa@example.com"},
        }
        with patch(
            "palari_company_os.linear_core.urllib.request.urlopen",
            return_value=FakeResponse({"data": {"issue": provider_issue}}),
        ):
            payload = linear_issue("ENG-123", client=client)

        self.assertFalse(payload["would_mutate_workspace"])
        self.assertEqual(payload["issue"]["key"], "ENG-123")
        self.assertEqual(payload["issue"]["updated_at"], "2026-07-19T00:00:00.000Z")
        self.assertEqual(payload["issue"]["labels"], [{"id": "label-1", "name": "docs"}])

    def test_graphql_errors_fail_closed_without_echoing_credentials(self) -> None:
        client = LinearClient("super-secret-token")
        with patch(
            "palari_company_os.linear_core.urllib.request.urlopen",
            return_value=FakeResponse(
                {"data": {"issue": None}, "errors": [{"message": "permission denied"}]}
            ),
        ):
            with self.assertRaisesRegex(LinearAdapterError, "permission denied") as raised:
                client.issue("ENG-123")

        self.assertEqual(raised.exception.code, "LINEAR_GRAPHQL_ERROR")
        self.assertNotIn("super-secret-token", str(raised.exception))

    def test_doctor_and_one_cli_boundary_report_presence_not_secret_values(self) -> None:
        with stored_workspace() as workspace_path:
            with patch.dict(
                os.environ,
                {"LINEAR_API_KEY": "super-secret-token", "LINEAR_WEBHOOK_SECRET": "hook-secret"},
                clear=True,
            ):
                direct = linear_doctor(str(workspace_path))
                cli = run_cli_json(workspace_path, "linear", "doctor")

        for payload in (direct, cli):
            self.assertTrue(payload["env"]["linear_api_key_present"])
            self.assertTrue(payload["env"]["linear_webhook_secret_present"])
            self.assertFalse(payload["env"]["secret_value_stored"])
            serialized = json.dumps(payload)
            self.assertNotIn("super-secret-token", serialized)
            self.assertNotIn("hook-secret", serialized)

    def test_connect_prepares_only_a_governed_local_boundary_when_key_is_missing(self) -> None:
        with stored_workspace() as workspace_path:
            with patch.dict(os.environ, {}, clear=True):
                payload = linear_connect(str(workspace_path), actor=HUMAN_ID)
            integration = Workspace.load(workspace_path).integration("INT-LINEAR")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["blocker"]["code"], "LINEAR_API_KEY_MISSING")
        self.assertEqual(integration.secret_ref, "env:LINEAR_API_KEY")
        self.assertIn("comment", integration.allowed_actions)
        self.assertIn("update_issue", integration.allowed_actions)
        self.assertIn("create_issue", integration.allowed_actions)

    def test_structured_governance_block_rejects_unknown_or_malformed_fields(self) -> None:
        unknown = parse_palari_block('```palari\n{"goal": "GOAL-0001", "surprise": true}\n```')
        malformed = parse_palari_block('```palari\n{"goal": 3}\n```')
        missing = parse_palari_block("Plain Linear issue text")

        self.assertFalse(unknown.valid)
        self.assertEqual(unknown.unknown_fields, ["surprise"])
        self.assertEqual(unknown.fields, {})
        self.assertFalse(malformed.valid)
        self.assertIn("palari.goal must be a string", malformed.error)
        self.assertFalse(missing.present)
        self.assertIn("missing palari block", missing.error)

    def test_import_is_idempotent_translation_and_never_adopts_work(self) -> None:
        with stored_workspace() as workspace_path:
            client = FakeLinearClient()
            first = linear_import(str(workspace_path), "ENG-123", PALARI_ID, client=client)
            second = linear_import(str(workspace_path), "ENG-123", PALARI_ID, client=client)
            workspace = Workspace.load(workspace_path)
            matching = [item for item in workspace.proposals if item.external_key == "ENG-123"]

        self.assertEqual(first["action"], "created")
        self.assertEqual(second["action"], "updated")
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].id, "PROP-LINEAR-ENG-123")
        self.assertEqual(matching[0].external_provider, "linear")
        self.assertEqual(matching[0].allowed_resources, ["docs/product/company-os.md"])
        self.assertIsNone(workspace.work_item("WORK-LINEAR-ENG-123"))

    def test_start_cannot_create_human_authority_or_use_retired_runners(self) -> None:
        for runner in ("cursor", "generic", "windsurf"):
            with self.subTest(runner=runner), stored_workspace() as workspace_path:
                client = FakeLinearClient()
                with self.assertRaisesRegex(WorkspaceError, "unsupported Linear runner"):
                    linear_start(
                        str(workspace_path),
                        "ENG-123",
                        PALARI_ID,
                        runner=runner,
                        adopt_by=HUMAN_ID,
                        client=client,
                    )
                self.assertEqual(Workspace.load(workspace_path).proposals, [])

        with stored_workspace() as workspace_path:
            with self.assertRaisesRegex(WorkspaceError, "adopt-by must name a human"):
                linear_start(
                    str(workspace_path),
                    "ENG-123",
                    PALARI_ID,
                    runner="codex",
                    adopt_by=PALARI_ID,
                    client=FakeLinearClient(),
                )
            workspace = Workspace.load(workspace_path)

        self.assertIsNone(workspace.work_item("WORK-LINEAR-ENG-123"))
        self.assertEqual(workspace.proposal("PROP-LINEAR-ENG-123").status, "proposed")

    def test_write_previews_are_offline_and_do_not_mutate_the_workspace(self) -> None:
        with stored_workspace() as workspace_path:
            before = workspace_path.read_bytes()
            comment = linear_post_gate(
                str(workspace_path),
                "ENG-200",
                event="review_requested",
                actor=PALARI_ID,
                record=False,
            )
            update = linear_post_gate(
                str(workspace_path),
                "ENG-200",
                event="work_completed",
                actor=PALARI_ID,
                action="update_issue",
                record=False,
            )
            create = linear_push(
                str(workspace_path),
                LOCAL_WORK_ID,
                actor=PALARI_ID,
                team_key="ENG",
                record=False,
            )
            after = workspace_path.read_bytes()

        self.assertEqual(before, after)
        self.assertFalse(comment["would_call_provider"])
        self.assertFalse(update["would_call_provider"])
        self.assertFalse(create["would_call_provider"])
        self.assertEqual(comment["payload_preview"]["operation"], "commentCreate")
        self.assertEqual(update["payload_preview"]["operation"], "issueUpdate")
        self.assertEqual(create["payload_preview"]["operation"], "issueCreate")

    def test_comment_send_is_wired_only_after_plan_approval_and_enqueue(self) -> None:
        with stored_workspace() as workspace_path:
            client = FakeLinearClient(valid_issue(key="ENG-200", issue_id="linear-linked-id"))
            planned = linear_post_gate(
                str(workspace_path),
                "ENG-200",
                event="review_requested",
                actor=PALARI_ID,
                record=True,
            )
            self.assertEqual(client.created_comments, [])
            outbox_id = approve_and_enqueue(workspace_path, planned["integration_plan"]["id"])
            with self.assertRaisesRegex(WorkspaceError, "--confirm"):
                linear_send(
                    str(workspace_path),
                    outbox_id,
                    human_id=HUMAN_ID,
                    confirm=False,
                    client=client,
                )
            sent = linear_send(
                str(workspace_path),
                outbox_id,
                human_id=HUMAN_ID,
                confirm=True,
                client=client,
            )

        self.assertEqual(sent["status"], "sent")
        self.assertEqual(client.created_comments[0]["issue_id"], "linear-linked-id")

    def test_status_update_send_resolves_provider_state_only_at_send_time(self) -> None:
        with stored_workspace() as workspace_path:
            client = FakeLinearClient(valid_issue(key="ENG-200", issue_id="linear-linked-id"))
            planned = linear_post_gate(
                str(workspace_path),
                "ENG-200",
                event="work_completed",
                actor=PALARI_ID,
                action="update_issue",
                record=True,
            )
            preview = planned["payload_preview"]
            self.assertEqual(preview["target_state_type"], "completed")
            self.assertNotIn("state_id", preview)
            outbox_id = approve_and_enqueue(workspace_path, planned["integration_plan"]["id"])
            sent = linear_send(
                str(workspace_path),
                outbox_id,
                human_id=HUMAN_ID,
                confirm=True,
                client=client,
            )

        self.assertEqual(sent["provider_response"]["state_name"], "Done")
        self.assertEqual(
            client.state_updates,
            [{"issue_id": "linear-linked-id", "state_id": "state-done"}],
        )

    def test_issue_creation_send_links_only_the_exact_approved_local_work(self) -> None:
        with stored_workspace() as workspace_path:
            client = FakeLinearClient()
            planned = linear_push(
                str(workspace_path),
                LOCAL_WORK_ID,
                actor=PALARI_ID,
                team_key="ENG",
                record=True,
            )
            self.assertEqual(client.created_issues, [])
            outbox_id = approve_and_enqueue(workspace_path, planned["integration_plan"]["id"])
            sent = linear_send(
                str(workspace_path),
                outbox_id,
                human_id=HUMAN_ID,
                confirm=True,
                client=client,
            )
            workspace = Workspace.load(workspace_path)
            linked = workspace.work_item(LOCAL_WORK_ID)

        self.assertEqual(sent["provider_response"]["key"], "ENG-901")
        self.assertEqual(sent["linked_work_item"]["work_item_id"], LOCAL_WORK_ID)
        self.assertEqual(linked.external_provider, "linear")
        self.assertEqual(linked.external_key, "ENG-901")
        self.assertIn("```palari", client.created_issues[0]["description"])


def valid_issue(
    *, key: str = "ENG-123", issue_id: str = "linear-issue-id", description: str | None = None
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "key": key,
        "identifier": key,
        "title": "Tighten onboarding copy",
        "description": valid_description() if description is None else description,
        "url": f"https://linear.app/acme/issue/{key}/tighten-onboarding-copy",
        "updated_at": "2026-07-19T00:00:00.000Z",
        "state": {"id": "state-todo", "name": "Todo", "type": "unstarted"},
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
  "forbidden_actions": ["external_write"],
  "acceptance_target": "Copy is clearer and tests still pass.",
  "verification_expectations": ["./scripts/verify.sh focused tests.test_docs"]
}
```
""".strip()


def workspace_data() -> dict[str, Any]:
    data: dict[str, Any] = {"schema_version": 2, "name": "Linear Adapter Contract"}
    for collection in COLLECTION_FILE_KEYS:
        data[collection] = []
    data["goals"] = [
        {
            "id": GOAL_ID,
            "title": "Keep Linear translation bounded",
            "owner": HUMAN_ID,
            "status": "active",
            "priority": "high",
            "success_criteria": ["Linear remains an adapter, not governance authority."],
            "linked_palaris": [PALARI_ID],
        }
    ]
    data["humans"] = [
        {
            "id": HUMAN_ID,
            "name": "Product Founder",
            "role": "Product authority",
            "authority_level": "admin",
            "approval_capabilities": ["product"],
            "availability": "active",
        }
    ]
    data["palaris"] = [
        {
            "id": PALARI_ID,
            "name": "Sofia",
            "role": "Bounded product worker",
            "scope": "Change only declared local files.",
            "owner_human": HUMAN_ID,
            "linked_goals": [GOAL_ID],
            "memory_sources": ["SOURCE-LOCAL"],
            "forbidden_actions": ["external_write"],
        }
    ]
    data["sources"] = [
        {
            "id": "SOURCE-LOCAL",
            "label": "Temporary repository",
            "kind": "repo",
            "provider": "local",
            "uri": ".",
            "access_mode": "read",
            "selected": True,
            "owner_human": HUMAN_ID,
            "allowed_palaris": [PALARI_ID],
            "data_class": "internal",
            "authority": "company_owned",
            "steward_human": HUMAN_ID,
        }
    ]
    data["work_items"] = [
        work_item(LOCAL_WORK_ID, "Publish bounded local work to Linear"),
        work_item(
            LINKED_WORK_ID,
            "Linked Linear work",
            external={
                "external_provider": "linear",
                "external_id": "linear-linked-id",
                "external_key": "ENG-200",
                "external_url": "https://linear.app/acme/issue/ENG-200",
                "external_updated_at": "2026-07-19T00:00:00.000Z",
            },
        ),
    ]
    return data


def work_item(
    work_id: str,
    title: str,
    *,
    external: dict[str, str] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": work_id,
        "title": title,
        "goal": GOAL_ID,
        "palari": PALARI_ID,
        "risk": "R1",
        "intensity": "light",
        "status": "active",
        "scope": "Produce one bounded local documentation result.",
        "allowed_resources": ["docs/product/company-os.md"],
        "allowed_sources": ["SOURCE-LOCAL"],
        "allowed_actions": ["local_write"],
        "output_targets": ["docs/product/company-os.md"],
        "forbidden_actions": ["external_write"],
        "acceptance_target": "The exact documentation result is inspectable.",
        "required_approval_count": 1,
        "required_approval_capability": "product",
        "parallel_policy": "independent",
    }
    record.update(external or {})
    return record


@contextmanager
def stored_workspace() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "workspace.json"
        write_store(WorkspaceStore(data_path=path, data=workspace_data()))
        yield path


def approve_and_enqueue(workspace_path: Path, plan_id: str) -> str:
    decide_integration_plan(
        str(workspace_path),
        plan_id,
        HUMAN_ID,
        "approve",
        reason="Approve this exact Linear provider preview.",
    )
    payload = enqueue_integration_plan(str(workspace_path), plan_id, HUMAN_ID)
    return payload["integration_outbox_item"]["id"]


def run_cli_json(workspace_path: Path, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-m",
            "palari_company_os",
            "--workspace",
            str(workspace_path),
            *args,
            "--json",
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
