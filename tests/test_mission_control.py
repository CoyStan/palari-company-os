from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager, redirect_stderr
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from typing import Iterator
from unittest.mock import patch
from urllib.parse import urlencode


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cli_dispatch import run_command
from palari_company_os.cli_parser import build_parser
from palari_company_os.mission_control import (
    create_mission_control_server,
    host_security_warning,
    workspace_hash,
)
from palari_company_os.store import load_store, write_store
from palari_company_os.workspace import Workspace
from tests.workspace_fixture import write_current_agent_workspace


WORK_ID = "WORK-1"
ATTEMPT_ID = "ATTEMPT-1"
EVIDENCE_ID = "EVIDENCE-1"
REVIEW_ID = "REVIEW-1"
PLAN_ID = "PLAN-1"
HUMAN_ID = "HUMAN-FOUNDER"
CSRF_TOKEN = "mission-control-test-token"


class MissionControlTests(unittest.TestCase):
    def test_local_ui_projects_current_workspace_and_content_hash(self) -> None:
        with stored_workspace() as workspace_file:
            server = create_mission_control_server(
                workspace_file,
                HUMAN_ID,
                port=0,
                csrf_token=CSRF_TOKEN,
            )
            try:
                page = request(server, "GET", "/")
                state = request(server, "GET", "/state-hash")
                before = json.loads(state.body)["workspace_hash"]
                workspace_file.touch()
                touched = json.loads(request(server, "GET", "/state-hash").body)[
                    "workspace_hash"
                ]
                raw = json.loads(workspace_file.read_text(encoding="utf-8"))
                raw["name"] = "Changed Current Workspace"
                workspace_file.write_text(
                    json.dumps(raw, indent=2) + "\n",
                    encoding="utf-8",
                )
                changed = json.loads(request(server, "GET", "/state-hash").body)[
                    "workspace_hash"
                ]
            finally:
                server.server_close()

        self.assertEqual(page.status, 200)
        self.assertEqual(page.headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        self.assertIn("Current Mission Control", page.body)
        self.assertIn("Needs You", page.body)
        self.assertIn("Boundary View", page.body)
        self.assertIn("Temporary repository", page.body)
        self.assertIn("notes/result.md", page.body)
        self.assertIn("Receipt Drawer", page.body)
        self.assertIn("No external writes.", page.body)
        self.assertIn('action="/human-decision"', page.body)
        self.assertIn(">Approve</button>", page.body)
        self.assertIn(">Reject</button>", page.body)
        self.assertIn(">Defer</button>", page.body)
        self.assertIn("setInterval(pollStateHash, 2000)", page.body)
        self.assertNotIn("http://", page.body)
        self.assertNotIn("https://", page.body)
        self.assertEqual(state.headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(state.headers["Cache-Control"], "no-store")
        self.assertEqual(before, touched)
        self.assertNotEqual(before, changed)

    def test_human_reject_and_defer_persist_exact_authority_records(self) -> None:
        for action, decision_value in (("reject", "rejected"), ("defer", "deferred")):
            with self.subTest(action=action), stored_workspace() as workspace_file:
                server = create_mission_control_server(
                    workspace_file,
                    HUMAN_ID,
                    port=0,
                    csrf_token=CSRF_TOKEN,
                )
                decision_id = f"HUMAN-DECISION-{action.upper()}"
                try:
                    response = post_form(
                        server,
                        "/human-decision",
                        {
                            "csrf_token": CSRF_TOKEN,
                            "workspace_hash": workspace_hash(workspace_file),
                            "work_id": WORK_ID,
                            "action": action,
                            "decision_id": decision_id,
                            "timestamp": "2026-07-18T12:00:00Z",
                        },
                    )
                finally:
                    server.server_close()
                decision = Workspace.load(workspace_file).human_decisions[0]

                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(json.loads(response.body)["record_id"], decision_id)
                self.assertEqual(decision.id, decision_id)
                self.assertEqual(decision.work_item_id, WORK_ID)
                self.assertEqual(decision.human_id, HUMAN_ID)
                self.assertEqual(decision.reviewed_head, "head-1")
                self.assertEqual(decision.decision, decision_value)
                self.assertEqual(decision.status, decision_value)
                self.assertEqual(decision.acceptance_mode, "human")
                self.assertEqual(decision.quorum_status, "not-met")
                self.assertEqual(decision.evidence_reference, EVIDENCE_ID)
                self.assertEqual(decision.review_reference, REVIEW_ID)
                self.assertEqual(decision.timestamp, "2026-07-18T12:00:00Z")

    def test_csrf_and_workspace_cas_block_mutation_before_authoring(self) -> None:
        with stored_workspace() as workspace_file:
            server = create_mission_control_server(
                workspace_file,
                HUMAN_ID,
                port=0,
                csrf_token=CSRF_TOKEN,
            )
            with patch("palari_company_os.mission_control.create_human_decision") as create:
                try:
                    missing_csrf = post_form(
                        server,
                        "/human-decision",
                        {
                            "workspace_hash": workspace_hash(workspace_file),
                            "work_id": WORK_ID,
                            "action": "approve",
                        },
                    )
                    stale_hash = workspace_hash(workspace_file)
                    raw = json.loads(workspace_file.read_text(encoding="utf-8"))
                    raw["name"] = "Out-of-band edit"
                    workspace_file.write_text(
                        json.dumps(raw, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    stale_workspace = post_form(
                        server,
                        "/human-decision",
                        {
                            "csrf_token": CSRF_TOKEN,
                            "workspace_hash": stale_hash,
                            "work_id": WORK_ID,
                            "action": "approve",
                        },
                    )
                finally:
                    server.server_close()

        self.assertEqual(missing_csrf.status, 403)
        self.assertIn("invalid CSRF token", missing_csrf.body)
        self.assertEqual(stale_workspace.status, 409)
        self.assertIn("workspace changed", stale_workspace.body)
        create.assert_not_called()

    def test_generic_integration_plan_translates_to_local_decision_service(self) -> None:
        with stored_workspace(include_plan=True) as workspace_file:
            server = create_mission_control_server(
                workspace_file,
                HUMAN_ID,
                port=0,
                csrf_token=CSRF_TOKEN,
            )
            with patch(
                "palari_company_os.mission_control.decide_integration_plan",
                return_value={"status": "approved"},
            ) as decide:
                try:
                    page = request(server, "GET", "/")
                    response = post_form(
                        server,
                        "/integration-plan",
                        {
                            "csrf_token": CSRF_TOKEN,
                            "workspace_hash": workspace_hash(workspace_file),
                            "plan_id": PLAN_ID,
                            "action": "approve",
                            "reason": "Exact local operator approval.",
                        },
                    )
                finally:
                    server.server_close()

        self.assertIn("Integration plan waiting for approval", page.body)
        self.assertIn(PLAN_ID, page.body)
        self.assertIn("No provider call will happen from this UI.", page.body)
        self.assertEqual(response.status, 200)
        decide.assert_called_once_with(
            str(workspace_file),
            PLAN_ID,
            HUMAN_ID,
            "approve",
            reason="Exact local operator approval.",
        )

    def test_server_routes_fail_closed_with_non_cacheable_responses(self) -> None:
        with stored_workspace() as workspace_file:
            server = create_mission_control_server(
                workspace_file,
                HUMAN_ID,
                port=0,
                csrf_token=CSRF_TOKEN,
            )
            try:
                index = request(server, "GET", "/index.html")
                missing_get = request(server, "GET", "/missing")
                missing_post = request(server, "POST", "/missing")
                unsupported_method = request(server, "DELETE", "/")
            finally:
                server.server_close()

        self.assertEqual(index.status, 200)
        for response in (missing_get, missing_post):
            self.assertEqual(response.status, 404)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(
                response.headers["Content-Type"],
                "application/json; charset=utf-8",
            )
            self.assertEqual(json.loads(response.body), {"error": "unknown endpoint"})
        self.assertEqual(unsupported_method.status, 501)
        self.assertIn("Unsupported method", unsupported_method.body)

    def test_localhost_default_and_non_local_bind_warning_are_explicit(self) -> None:
        with stored_workspace() as workspace_file:
            local = create_mission_control_server(workspace_file, HUMAN_ID, port=0)
            try:
                self.assertEqual(local.server_address[0], "127.0.0.1")
            finally:
                local.server_close()

            stream = StringIO()
            with redirect_stderr(stream):
                wide = create_mission_control_server(
                    workspace_file,
                    HUMAN_ID,
                    host="0.0.0.0",
                    port=0,
                )
            wide.server_close()

        self.assertEqual(host_security_warning("localhost"), "")
        self.assertIn("SECURITY WARNING", stream.getvalue())
        self.assertIn("no authentication", host_security_warning("0.0.0.0"))

    def test_cli_serve_is_one_parser_dispatch_translation(self) -> None:
        args = build_parser().parse_args(
            [
                "--workspace",
                "/tmp/current-mission-control",
                "serve",
                "--as",
                HUMAN_ID,
                "--host",
                "localhost",
                "--port",
                "8787",
            ]
        )
        payload = {
            "url": "http://localhost:8787/",
            "workspace_file": "/tmp/current-mission-control/workspace.json",
        }

        with patch(
            "palari_company_os.mission_control.serve_mission_control",
            return_value=payload,
        ) as serve:
            result = run_command(args)

        serve.assert_called_once_with(
            "/tmp/current-mission-control",
            HUMAN_ID,
            host="localhost",
            port=8787,
        )
        self.assertEqual(result.kind, "mission-control-serve")
        self.assertEqual(result.payload, payload)
        self.assertFalse(result.as_json)


@contextmanager
def stored_workspace(*, include_plan: bool = False) -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as directory:
        workspace_file = Path(directory) / "workspace.json"
        write_current_agent_workspace(workspace_file)
        store = load_store(workspace_file)
        add_mission_control_records(store.data, include_plan=include_plan)
        write_store(store)
        yield workspace_file


def add_mission_control_records(
    raw: dict[str, object],
    *,
    include_plan: bool,
) -> None:
    raw["name"] = "Current Mission Control"
    raw["work_items"] = [
        {
            "id": WORK_ID,
            "title": "Produce one local result",
            "goal": "GOAL-REPO-0001",
            "palari": "PALARI-STEWARD",
            "risk": "R2",
            "intensity": "standard",
            "status": "active",
            "allowed_resources": ["notes/result.md"],
            "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
            "allowed_actions": ["local_write"],
            "output_targets": ["notes/result.md"],
            "forbidden_actions": ["external_write"],
            "current_attempt": ATTEMPT_ID,
            "required_approval_capability": "product",
        }
    ]
    raw["attempts"] = [
        {
            "id": ATTEMPT_ID,
            "work_item_id": WORK_ID,
            "actor": "PALARI-STEWARD",
            "status": "complete",
            "head_sha": "head-1",
            "changed_files": ["notes/result.md"],
            "allowed_paths": ["notes/result.md"],
        }
    ]
    raw["receipts"] = [
        {
            "id": "RECEIPT-1",
            "work_item_id": WORK_ID,
            "attempt_id": ATTEMPT_ID,
            "actor": "PALARI-STEWARD",
            "sources_used": ["SOURCE-REPO-FOUNDATION"],
            "outputs_created": ["notes/result.md"],
            "not_done": ["No external writes."],
        }
    ]
    raw["evidence_runs"] = [
        {
            "id": EVIDENCE_ID,
            "work_item_id": WORK_ID,
            "attempt_id": ATTEMPT_ID,
            "head_sha": "head-1",
            "status": "passed",
        }
    ]
    raw["review_verdicts"] = [
        {
            "id": REVIEW_ID,
            "work_item_id": WORK_ID,
            "reviewed_head": "head-1",
            "reviewer": "PALARI-ARCHITECT",
            "verdict": "needs-human-decision",
        }
    ]
    raw["integrations"] = [
        {
            "id": "INT-GENERIC",
            "provider": "custom_local",
            "label": "Provider-neutral notification",
            "mode": "notify",
            "owner_human": HUMAN_ID,
            "enabled": True,
            "allowed_events": ["approval_requested"],
            "allowed_actions": ["notify"],
            "secret_ref": "env:PALARI_TEST_CONNECTOR",
            "risk_level": "standard",
            "source_ids": ["SOURCE-REPO-FOUNDATION"],
        }
    ]
    if include_plan:
        raw["integration_plans"] = [
            {
                "id": PLAN_ID,
                "integration_id": "INT-GENERIC",
                "work_item_id": WORK_ID,
                "event": "approval_requested",
                "action": "notify",
                "status": "pending-approval",
                "payload_preview": {
                    "provider": "custom_local",
                    "operation": "external_action_preview",
                },
                "source_boundary": {
                    "integration_sources": ["SOURCE-REPO-FOUNDATION"],
                    "work_allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                    "shared_sources": ["SOURCE-REPO-FOUNDATION"],
                },
                "risk": "standard",
                "approval_required": True,
            }
        ]


@dataclass(frozen=True)
class Response:
    status: int
    body: str
    headers: dict[str, str]


def request(
    server: ThreadingHTTPServer,
    method: str,
    path: str,
    body: str = "",
    headers: dict[str, str] | None = None,
) -> Response:
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection(
        server.server_address[0],
        server.server_address[1],
        timeout=10,
    )
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        return Response(response.status, text, dict(response.getheaders()))
    finally:
        connection.close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise TimeoutError("server did not finish handling request")


def post_form(
    server: ThreadingHTTPServer,
    path: str,
    fields: dict[str, str],
) -> Response:
    return request(
        server,
        "POST",
        path,
        body=urlencode(fields),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


if __name__ == "__main__":
    unittest.main()
