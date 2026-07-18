from __future__ import annotations

import hmac
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from hashlib import sha256
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.linear_adapter import (
    linear_doctor,
    linear_import,
    linear_linked,
    linear_start,
    linear_status,
)
from palari_company_os.linear_webhook import (
    LinearWebhookError,
    create_linear_webhook_server,
    latest_linear_webhook_events_by_key,
    linear_webhook_event_log_path,
    linear_webhook_events,
    process_linear_webhook,
    verify_linear_webhook_payload,
)
from palari_company_os.store import WorkspaceStore, write_store
from palari_company_os.workspace import Workspace


WORKSPACE = REPO_ROOT / "src" / "palari_company_os" / "data" / "examples" / "acme-company-os"
SECRET = "linear-webhook-test-secret"
NOW_MS = 1_800_000_000_000


class FakeLinearClient:
    def __init__(self, issue: dict[str, Any]) -> None:
        self._issue = issue

    def issue(self, identifier: str) -> dict[str, Any]:
        return dict(self._issue, key=identifier, identifier=identifier)

    def create_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        return {"id": "comment-123", "url": "", "createdAt": "2026-07-07T00:00:00.000Z"}


class LinearWebhookTests(unittest.TestCase):
    def test_signature_verification_accepts_valid_payload(self) -> None:
        raw = raw_payload()
        payload = verify_linear_webhook_payload(
            raw,
            signature=signature(raw),
            timestamp=str(NOW_MS),
            secret=SECRET,
            now_ms=NOW_MS,
        )

        self.assertEqual(payload["type"], "Issue")
        self.assertEqual(payload["data"]["identifier"], "ENG-123")

    def test_signature_verification_rejects_bad_missing_stale_and_invalid_json(self) -> None:
        raw = raw_payload()
        with self.assertRaisesRegex(LinearWebhookError, "signature is required") as missing:
            verify_linear_webhook_payload(
                raw,
                signature="",
                timestamp=str(NOW_MS),
                secret=SECRET,
                now_ms=NOW_MS,
            )
        with self.assertRaisesRegex(LinearWebhookError, "signature did not match") as bad:
            verify_linear_webhook_payload(
                raw,
                signature="deadbeef",
                timestamp=str(NOW_MS),
                secret=SECRET,
                now_ms=NOW_MS,
            )
        with self.assertRaisesRegex(LinearWebhookError, "outside the replay window") as stale:
            verify_linear_webhook_payload(
                raw,
                signature=signature(raw),
                timestamp=str(NOW_MS),
                secret=SECRET,
                now_ms=NOW_MS + 120_000,
            )
        malformed = b"{"
        with self.assertRaisesRegex(LinearWebhookError, "not valid JSON") as invalid:
            verify_linear_webhook_payload(
                malformed,
                signature=signature(malformed),
                timestamp=str(NOW_MS),
                secret=SECRET,
                now_ms=NOW_MS,
            )

        self.assertEqual(missing.exception.code, "LINEAR_WEBHOOK_SIGNATURE_MISSING")
        self.assertEqual(bad.exception.code, "LINEAR_WEBHOOK_BAD_SIGNATURE")
        self.assertEqual(stale.exception.code, "LINEAR_WEBHOOK_TIMESTAMP_STALE")
        self.assertEqual(invalid.exception.code, "LINEAR_WEBHOOK_INVALID_JSON")

    def test_unlinked_issue_is_recorded_without_workspace_import(self) -> None:
        with temp_workspace() as workspace_path:
            raw = raw_payload(issue_key="ENG-999", issue_id="linear-unlinked")
            payload = process_linear_webhook(
                workspace_path,
                raw,
                signed_headers(raw, delivery="delivery-unlinked"),
                secret=SECRET,
                now_ms=NOW_MS,
            )
            workspace = Workspace.load(workspace_path)
            events = linear_webhook_events(workspace_path, limit=20)

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["sync"]["mutated"])
        self.assertEqual(payload["sync"]["reason"], "issue_not_linked")
        self.assertIsNone(workspace.proposal("PROP-LINEAR-ENG-999"))
        self.assertEqual(events["count"], 1)
        self.assertIn("palari linear import ENG-999", events["events"][0]["next_commands"][0])

    def test_linked_proposal_sync_updates_external_refs_and_dedupes_delivery(self) -> None:
        with temp_workspace() as workspace_path:
            linear_import(workspace_path, "ENG-123", "PALARI-SOFIA", client=FakeLinearClient(issue()))
            raw = raw_payload(
                title="Updated Linear title",
                description="Updated Linear description",
                updated_at="2026-07-07T01:00:00.000Z",
            )
            first = process_linear_webhook(
                workspace_path,
                raw,
                signed_headers(raw, delivery="delivery-proposal"),
                secret=SECRET,
                now_ms=NOW_MS,
            )
            duplicate = process_linear_webhook(
                workspace_path,
                raw,
                signed_headers(raw, delivery="delivery-proposal"),
                secret=SECRET,
                now_ms=NOW_MS,
            )
            workspace = Workspace.load(workspace_path)
            proposal = workspace.proposal("PROP-LINEAR-ENG-123")
            events = linear_webhook_events(workspace_path, limit=20)
            doctor = linear_doctor(workspace_path)
            linked = linear_linked(workspace_path)

        self.assertTrue(first["sync"]["mutated"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(events["count"], 1)
        self.assertEqual(proposal.title, "Updated Linear title")
        self.assertEqual(proposal.summary, "Updated Linear description")
        self.assertEqual(proposal.external_updated_at, "2026-07-07T01:00:00.000Z")
        self.assertIn("linear_webhook_secret_present", doctor["env"])
        self.assertEqual(doctor["webhook"]["event_log"]["event_count"], 1)
        self.assertEqual(linked["items"][0]["latest_webhook_event"]["delivery_id"], "delivery-proposal")

    def test_linked_work_sync_updates_only_external_refs(self) -> None:
        with temp_workspace() as workspace_path:
            linear_start(
                workspace_path,
                "ENG-123",
                "PALARI-SOFIA",
                runner="generic",
                adopt_by="HUMAN-FOUNDER",
                client=FakeLinearClient(issue()),
            )
            before = Workspace.load(workspace_path).work_item("WORK-LINEAR-ENG-123")
            raw = raw_payload(
                title="Linear changed title",
                description="Linear changed description",
                updated_at="2026-07-07T02:00:00.000Z",
            )
            process_linear_webhook(
                workspace_path,
                raw,
                signed_headers(raw, delivery="delivery-work"),
                secret=SECRET,
                now_ms=NOW_MS,
            )
            workspace = Workspace.load(workspace_path)
            work = workspace.work_item("WORK-LINEAR-ENG-123")
            proposal = workspace.proposal("PROP-LINEAR-ENG-123")
            status = linear_status(workspace_path, "ENG-123")

        self.assertEqual(work.title, before.title)
        self.assertEqual(work.scope, before.scope)
        self.assertEqual(work.external_updated_at, "2026-07-07T02:00:00.000Z")
        self.assertEqual(proposal.title, before.title)
        self.assertEqual(status["latest_webhook_event"]["delivery_id"], "delivery-work")

    def test_remove_event_never_deletes_or_rewrites_linked_records(self) -> None:
        with temp_workspace() as workspace_path:
            linear_import(workspace_path, "ENG-123", "PALARI-SOFIA", client=FakeLinearClient(issue()))
            raw = raw_payload(action="remove", title="Removed title")
            process_linear_webhook(
                workspace_path,
                raw,
                signed_headers(raw, delivery="delivery-remove"),
                secret=SECRET,
                now_ms=NOW_MS,
            )
            workspace = Workspace.load(workspace_path)
            proposal = workspace.proposal("PROP-LINEAR-ENG-123")
            events = linear_webhook_events(workspace_path, limit=20)

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.title, "Tighten onboarding copy")
        self.assertEqual(events["events"][0]["mutation"]["reason"], "remove_or_archive_event_is_audit_only")

    def test_event_log_never_contains_secret_and_latest_events_are_indexed(self) -> None:
        with temp_workspace() as workspace_path:
            raw = raw_payload()
            process_linear_webhook(
                workspace_path,
                raw,
                signed_headers(raw, delivery="delivery-secret"),
                secret=SECRET,
                now_ms=NOW_MS,
            )
            log_text = linear_webhook_event_log_path(workspace_path).read_text(encoding="utf-8")
            latest = latest_linear_webhook_events_by_key(workspace_path)

        self.assertNotIn(SECRET, log_text)
        self.assertEqual(latest["ENG-123"]["delivery_id"], "delivery-secret")

    def test_cli_verify_and_events_return_json(self) -> None:
        with temp_workspace() as workspace_path:
            raw = raw_payload()
            current_ms = str(int(time.time() * 1000))
            payload_file = Path(workspace_path).parent / "payload.json"
            payload_file.write_bytes(raw)
            good = run_cli_json(
                workspace_path,
                "linear",
                "webhook",
                "verify",
                "--payload-file",
                str(payload_file),
                "--signature",
                signature(raw),
                "--timestamp",
                current_ms,
            )
            bad = run_cli(
                workspace_path,
                "linear",
                "webhook",
                "verify",
                "--payload-file",
                str(payload_file),
                "--signature",
                "bad",
                "--timestamp",
                current_ms,
                "--json",
                check=False,
            )
            events = run_cli_json(workspace_path, "linear", "webhook", "events")

        bad_payload = json.loads(bad.stdout)
        self.assertTrue(good["ok"])
        self.assertEqual(good["event_type"], "Issue")
        self.assertFalse(bad_payload["ok"])
        self.assertEqual(bad_payload["error"]["code"], "LINEAR_WEBHOOK_BAD_SIGNATURE")
        self.assertEqual(bad_payload["error"]["command"], "linear webhook verify")
        self.assertEqual(events["count"], 0)

    def test_http_server_receives_signed_issue_webhook(self) -> None:
        with temp_workspace() as workspace_path:
            server = create_linear_webhook_server(
                workspace_path,
                host="127.0.0.1",
                port=0,
                secret=SECRET,
                now_ms=lambda: NOW_MS,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                health = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5)
                raw = raw_payload()
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/linear/webhook",
                    data=raw,
                    headers=signed_headers(raw, delivery="delivery-http"),
                    method="POST",
                )
                response = urllib.request.urlopen(request, timeout=5)
                payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            events = linear_webhook_events(workspace_path, limit=20)

        self.assertEqual(health.status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["delivery_id"], "delivery-http")
        self.assertEqual(events["count"], 1)


def issue(
    *,
    issue_id: str = "linear-issue-id",
    key: str = "ENG-123",
    title: str = "Tighten onboarding copy",
    description: str | None = None,
    updated_at: str = "2026-07-07T00:00:00.000Z",
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "key": key,
        "identifier": key,
        "title": title,
        "description": description if description is not None else valid_description(),
        "url": f"https://linear.app/acme/issue/{key}/tighten-onboarding-copy",
        "updated_at": updated_at,
        "state": {"id": "state-1", "name": "Todo", "type": "unstarted"},
        "team": {"id": "team-1", "key": "ENG", "name": "Engineering"},
        "labels": [{"id": "label-1", "name": "docs"}],
        "assignee": {"id": "user-1", "name": "Rafa", "email": "rafa@example.com"},
    }


def raw_payload(
    *,
    action: str = "update",
    issue_id: str = "linear-issue-id",
    issue_key: str = "ENG-123",
    title: str = "Tighten onboarding copy",
    description: str = "Linear webhook description",
    updated_at: str = "2026-07-07T00:00:00.000Z",
) -> bytes:
    payload = {
        "action": action,
        "type": "Issue",
        "createdAt": "2026-07-07T00:00:00.000Z",
        "webhookTimestamp": NOW_MS,
        "data": {
            "id": issue_id,
            "identifier": issue_key,
            "title": title,
            "description": description,
            "url": f"https://linear.app/acme/issue/{issue_key}/tighten-onboarding-copy",
            "updatedAt": updated_at,
        },
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def signature(raw: bytes, *, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), raw, sha256).hexdigest()


def signed_headers(raw: bytes, *, delivery: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Linear-Delivery": delivery,
        "Linear-Event": "Issue",
        "Linear-Signature": signature(raw),
        "Linear-Timestamp": str(NOW_MS),
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


def run_cli_json(workspace_path: str, *args: str) -> dict[str, Any]:
    result = run_cli(workspace_path, *args, "--json")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise AssertionError(f"expected JSON object, got {payload!r}")
    return payload


def run_cli(
    workspace_path: str,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["LINEAR_WEBHOOK_SECRET"] = SECRET
    return subprocess.run(
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
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )


def temp_workspace() -> Any:
    return TempWorkspace()


class TempWorkspace:
    def __enter__(self) -> str:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        shutil.copytree(WORKSPACE, root / "workspace")
        data_path = root / "workspace" / "workspace.json"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        data_path.unlink()
        write_store(WorkspaceStore(data_path=data_path, data=data))
        return str(data_path)

    def __exit__(self, *_args: object) -> None:
        self._tmp.cleanup()
