from __future__ import annotations

import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from http.server import ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.authoring import create_record
from palari_company_os.history import read_history
from palari_company_os.integrations import record_integration_plan
from palari_company_os.models import to_plain
from palari_company_os.mission_control import (
    create_mission_control_server,
    human_decision_record_for_action,
    host_security_warning,
    workspace_hash,
)
from palari_company_os.workspace import Workspace


ACME = REPO_ROOT / "examples" / "acme-company-os"


class MissionControlTests(unittest.TestCase):
    def test_server_starts_serves_ui_and_shuts_down_cleanly(self) -> None:
        with temp_workspace() as workspace_file:
            server = create_mission_control_server(
                workspace_file,
                "HUMAN-FOUNDER",
                port=0,
                csrf_token="test-token",
            )
            try:
                status, body = request(server, "GET", "/")
            finally:
                server.server_close()

        self.assertEqual(status, 200)
        self.assertIn("Needs You", body)
        self.assertIn("Boundary View", body)
        self.assertIn("Live Activity", body)
        self.assertIn("Receipt Drawer", body)
        self.assertIn("Approve", body)

    def test_state_hash_changes_only_when_workspace_content_changes(self) -> None:
        with temp_workspace() as workspace_file:
            server = create_mission_control_server(workspace_file, "HUMAN-FOUNDER", port=0)
            try:
                first = json.loads(request(server, "GET", "/state-hash")[1])["workspace_hash"]
                workspace_file.touch()
                second = json.loads(request(server, "GET", "/state-hash")[1])["workspace_hash"]
                data = json.loads(workspace_file.read_text(encoding="utf-8"))
                data["name"] = data["name"] + " Updated"
                workspace_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                third = json.loads(request(server, "GET", "/state-hash")[1])["workspace_hash"]
            finally:
                server.server_close()

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_post_without_csrf_is_rejected(self) -> None:
        with temp_workspace() as workspace_file:
            server = create_mission_control_server(
                workspace_file,
                "HUMAN-FOUNDER",
                port=0,
                csrf_token="test-token",
            )
            try:
                status, body = post_form(
                    server,
                    "/human-decision",
                    {"work_id": "WORK-0001", "action": "approve", "workspace_hash": workspace_hash(workspace_file)},
                )
            finally:
                server.server_close()
            decisions = decisions_for_work(workspace_file, "WORK-0001")

        self.assertEqual(status, 403)
        self.assertIn("invalid CSRF token", body)
        self.assertEqual(decisions, [])

    def test_post_after_out_of_band_edit_conflicts_without_writing(self) -> None:
        with temp_workspace() as workspace_file:
            old_hash = workspace_hash(workspace_file)
            data = json.loads(workspace_file.read_text(encoding="utf-8"))
            data["name"] = "Changed Outside Browser"
            workspace_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            server = create_mission_control_server(
                workspace_file,
                "HUMAN-FOUNDER",
                port=0,
                csrf_token="test-token",
            )
            try:
                status, body = post_form(
                    server,
                    "/human-decision",
                    {
                        "csrf_token": "test-token",
                        "workspace_hash": old_hash,
                        "work_id": "WORK-0001",
                        "action": "approve",
                    },
                )
            finally:
                server.server_close()
            decisions = decisions_for_work(workspace_file, "WORK-0001")

        self.assertEqual(status, 409)
        self.assertIn("workspace changed", body)
        self.assertEqual(decisions, [])

    def test_post_honors_workspace_write_lock(self) -> None:
        with temp_workspace() as workspace_file:
            record_bound_work_0001(workspace_file)
            lock_path = workspace_file.parent / ".palari" / "locks" / "workspace.json.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text(f"pid={os.getpid()}\n", encoding="utf-8")
            server = create_mission_control_server(
                workspace_file,
                "HUMAN-FOUNDER",
                port=0,
                csrf_token="test-token",
            )
            try:
                status, body = post_form(
                    server,
                    "/human-decision",
                    {
                        "csrf_token": "test-token",
                        "workspace_hash": workspace_hash(workspace_file),
                        "work_id": "WORK-0001",
                        "action": "approve",
                    },
                )
            finally:
                lock_path.unlink(missing_ok=True)
                server.server_close()
            decisions = decisions_for_work(workspace_file, "WORK-0001")

        self.assertEqual(status, 400)
        self.assertIn("workspace write is already in progress", body)
        self.assertEqual(decisions, [])

    def test_ui_approve_matches_cli_human_decision_record_shape(self) -> None:
        with temp_workspace() as ui_workspace, temp_workspace() as cli_workspace:
            record_bound_work_0001(ui_workspace)
            record_bound_work_0001(cli_workspace)
            decision_id = "HUMAN-DECISION-SAME"
            timestamp = "2026-07-06T14:00:00Z"
            server = create_mission_control_server(
                ui_workspace,
                "HUMAN-FOUNDER",
                port=0,
                csrf_token="test-token",
            )
            try:
                status, _body = post_form(
                    server,
                    "/human-decision",
                    {
                        "csrf_token": "test-token",
                        "workspace_hash": workspace_hash(ui_workspace),
                        "work_id": "WORK-0001",
                        "action": "approve",
                        "decision_id": decision_id,
                        "timestamp": timestamp,
                    },
                )
            finally:
                server.server_close()

            self.assertEqual(status, 200)
            expected = human_decision_record_for_action(
                Workspace.load(cli_workspace),
                "WORK-0001",
                "HUMAN-FOUNDER",
                "approve",
                decision_id=decision_id,
                timestamp=timestamp,
            )
            run_cli(
                "--workspace",
                str(cli_workspace),
                "human-decision",
                "record",
                decision_id,
                "--work-item-id",
                expected["work_item_id"],
                "--human-id",
                expected["human_id"],
                "--reviewed-head",
                expected["reviewed_head"],
                "--decision",
                expected["decision"],
                "--status",
                expected["status"],
                "--acceptance-mode",
                expected["acceptance_mode"],
                "--quorum-status",
                expected["quorum_status"],
                "--evidence-reference",
                expected["evidence_reference"],
                "--review-reference",
                expected["review_reference"],
                "--timestamp",
                expected["timestamp"],
                "--json",
            )

            ui_data = Workspace.load(ui_workspace)
            cli_data = Workspace.load(cli_workspace)
            self.assertEqual(to_records(ui_data.human_decisions), to_records(cli_data.human_decisions))
            self.assertEqual(
                normalize_history(read_history(ui_workspace)["events"][-1]),
                normalize_history(read_history(cli_workspace)["events"][-1]),
            )

    def test_pending_integration_plans_render_and_can_be_decided(self) -> None:
        with temp_workspace() as workspace_file:
            record_integration_plan(
                str(workspace_file),
                "INT-SLACK-OPS",
                "WORK-0001",
                "approval_requested",
                "notify",
                actor="HUMAN-FOUNDER",
                plan_id="PLAN-MISSION",
            )
            server = create_mission_control_server(
                workspace_file,
                "HUMAN-FOUNDER",
                port=0,
                csrf_token="test-token",
            )
            try:
                html = request(server, "GET", "/")[1]
                status, _body = post_form(
                    server,
                    "/integration-plan",
                    {
                        "csrf_token": "test-token",
                        "workspace_hash": workspace_hash(workspace_file),
                        "plan_id": "PLAN-MISSION",
                        "action": "approve",
                    },
                )
            finally:
                server.server_close()
            plan = Workspace.load(workspace_file).integration_plan("PLAN-MISSION")

        self.assertIn("Integration plan waiting for approval", html)
        self.assertIn("PLAN-MISSION", html)
        self.assertEqual(status, 200)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.status, "approved")

    def test_default_host_is_loopback_and_non_localhost_warns(self) -> None:
        with temp_workspace() as workspace_file:
            server = create_mission_control_server(workspace_file, "HUMAN-FOUNDER", port=0)
            try:
                self.assertEqual(server.server_address[0], "127.0.0.1")
            finally:
                server.server_close()
            stream = StringIO()
            with redirect_stderr(stream):
                wide_server = create_mission_control_server(
                    workspace_file,
                    "HUMAN-FOUNDER",
                    host="0.0.0.0",
                    port=0,
                )
            wide_server.server_close()

        self.assertIn("SECURITY WARNING", stream.getvalue())
        self.assertIn("no authentication", host_security_warning("0.0.0.0"))

    def test_cli_help_documents_serve_and_demo_serve(self) -> None:
        serve = subprocess.run(
            [str(REPO_ROOT / "bin" / "palari"), "serve", "--help"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        demo = subprocess.run(
            [str(REPO_ROOT / "bin" / "palari"), "demo", "--help"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("--as HUMAN_ID", serve.stdout)
        self.assertIn("--host HOST", serve.stdout)
        self.assertIn("--serve", demo.stdout)
        self.assertIn("Mission", demo.stdout)
        self.assertIn("Control", demo.stdout)

    def test_served_assets_have_no_external_network_references(self) -> None:
        with temp_workspace() as workspace_file:
            server = create_mission_control_server(workspace_file, "HUMAN-FOUNDER", port=0)
            try:
                html = request(server, "GET", "/")[1]
            finally:
                server.server_close()

        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertIn("setInterval(pollStateHash, 2000)", html)


def temp_workspace() -> Any:
    return _TempWorkspace()


def record_bound_work_0001(workspace_file: Path) -> None:
    raw = json.loads(workspace_file.read_text(encoding="utf-8"))
    attempt = next(item for item in raw["attempts"] if item["id"] == "ATTEMPT-0001")
    attempt["workspace_path"] = str(workspace_file.parent)
    attempt["allowed_paths"] = [
        "examples/acme-company-os/workspace.json",
        "docs/product/company-os.md",
    ]
    attempt["output_targets"] = ["docs/product/company-os.md"]
    raw["review_verdicts"] = [
        item for item in raw["review_verdicts"] if item["work_item_id"] != "WORK-0001"
    ]
    raw["human_decisions"] = [
        item for item in raw["human_decisions"] if item["work_item_id"] != "WORK-0001"
    ]
    raw["acceptance_records"] = [
        item for item in raw["acceptance_records"] if item["work_item_id"] != "WORK-0001"
    ]
    workspace_file.write_text(json.dumps(raw), encoding="utf-8")
    artifact = workspace_file.parent / "docs" / "product" / "company-os.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("mission-control proof\n", encoding="utf-8")
    create_record(
        workspace_file,
        "receipt",
        {
            "id": "RECEIPT-MISSION-BOUND",
            "work_item_id": "WORK-0001",
            "attempt_id": "ATTEMPT-0001",
            "actor": "PALARI-SOFIA",
            "sources_used": [],
            "actions_taken": ["prepared exact proof for the mission-control test"],
            "outputs_created": ["docs/product/company-os.md"],
            "external_writes": [],
            "not_done": ["No external writes performed"],
            "undo_refs": [],
        },
    )
    create_record(
        workspace_file,
        "evidence",
        {
            "id": "EVIDENCE-MISSION-BOUND",
            "work_item_id": "WORK-0001",
            "attempt_id": "ATTEMPT-0001",
            "head_sha": "abc1234",
            "status": "passed",
            "base_ref": "main",
            "commands": ["python3 -m unittest tests.test_mission_control"],
            "artifacts": ["docs/product/company-os.md"],
            "summary": "Mission-control acceptance fixture proof passed.",
            "freshness": "fresh",
        },
    )
    create_record(
        workspace_file,
        "review",
        {
            "id": "REVIEW-MISSION-BOUND",
            "work_item_id": "WORK-0001",
            "reviewed_head": "abc1234",
            "reviewer": "HUMAN-OPS",
            "verdict": "accept-ready",
            "findings": [],
            "checks_inspected": ["python3 -m unittest tests.test_mission_control"],
            "residual_risks": [],
        },
    )


class _TempWorkspace:
    def __enter__(self) -> Path:
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name) / "workspace.json"
        shutil.copy(ACME / "workspace.json", self.path)
        return self.path

    def __exit__(self, *_exc: object) -> None:
        self._directory.cleanup()


def request(
    server: ThreadingHTTPServer,
    method: str,
    path: str,
    body: str = "",
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    conn = http.client.HTTPConnection(server.server_address[0], server.server_address[1], timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        text = response.read().decode("utf-8")
        return response.status, text
    finally:
        conn.close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise TimeoutError("server did not finish handling request")


def post_form(
    server: ThreadingHTTPServer,
    path: str,
    fields: dict[str, str],
) -> tuple[int, str]:
    return request(
        server,
        "POST",
        path,
        body=urlencode(fields),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
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


def to_records(records: object) -> list[dict[str, object]]:
    value = to_plain(records)
    if not isinstance(value, list):
        raise TypeError("expected list of records")
    return value


def normalize_history(event: dict[str, object]) -> dict[str, object]:
    normalized = dict(event)
    normalized.pop("event_id", None)
    normalized.pop("timestamp", None)
    return normalized


def decisions_for_work(workspace_file: Path, work_id: str) -> list[object]:
    return [
        decision
        for decision in Workspace.load(workspace_file).human_decisions
        if decision.work_item_id == work_id
    ]


if __name__ == "__main__":
    unittest.main()
