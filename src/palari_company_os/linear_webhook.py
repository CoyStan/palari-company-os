from __future__ import annotations

import hmac
import json
import os
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .errors import WorkspaceError
from .governance_journal import MutationMetadata, utc_timestamp
from .models import Proposal, WorkItem
from .store import load_store, validate_data, workspace_file_path, write_store
from .workspace import Workspace


LINEAR_WEBHOOK_SECRET_REF = "env:LINEAR_WEBHOOK_SECRET"
LINEAR_WEBHOOK_PATH = "/linear/webhook"
LINEAR_WEBHOOK_EVENT_LOG = "linear-events.jsonl"
LINEAR_WEBHOOK_REPLAY_WINDOW_MS = 60_000


class LinearWebhookError(WorkspaceError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        next_action: str = "",
        http_status: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action
        self.http_status = http_status


@dataclass(frozen=True)
class LinearWebhookConfig:
    workspace_path: Path
    secret: str
    now_ms: Callable[[], int]


def linear_webhook_event_log_path(workspace_path: str | Path) -> Path:
    data_path = workspace_file_path(workspace_path)
    return data_path.parent / ".palari" / LINEAR_WEBHOOK_EVENT_LOG


def linear_webhook_event_log_summary(workspace_path: str | Path) -> dict[str, Any]:
    events = _read_event_log(workspace_path)
    path = linear_webhook_event_log_path(workspace_path)
    latest = events[-1] if events else None
    return {
        "path": str(path),
        "exists": path.exists(),
        "event_count": len(events),
        "latest_delivery_id": latest.get("delivery_id", "") if latest else "",
        "latest_received_at": latest.get("received_at", "") if latest else "",
    }


def latest_linear_webhook_events_by_key(workspace_path: str | Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in _read_event_log(workspace_path):
        issue = event.get("linear_issue", {})
        if not isinstance(issue, dict):
            continue
        key = str(issue.get("key") or "")
        if not key:
            continue
        latest[key] = _compact_event(event)
    return latest


def linear_webhook_events(workspace_path: str | Path, *, limit: int = 20) -> dict[str, Any]:
    events = _read_event_log(workspace_path)
    selected = events if limit < 0 else events[-limit:] if limit else []
    return {
        "schema_version": "palari.linear_webhook_events.v1",
        "provider": "linear",
        "event_log": linear_webhook_event_log_summary(workspace_path),
        "count": len(events),
        "events": selected,
        "next_action": "Use `palari linear status ISSUE-KEY --json` for focused sync state.",
    }


def linear_webhook_verify_file(
    payload_file: str | Path,
    *,
    signature: str,
    timestamp: str,
    secret: str | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    path = Path(payload_file)
    raw_body = path.read_bytes()
    payload = verify_linear_webhook_payload(
        raw_body,
        signature=signature,
        timestamp=timestamp,
        secret=secret,
        now_ms=now_ms,
    )
    return {
        "schema_version": "palari.linear_webhook_verify.v1",
        "ok": True,
        "provider": "linear",
        "payload_file": str(path),
        "event_type": _event_type({}, payload),
        "action": _string(payload.get("action")),
        "would_mutate_workspace": False,
        "next_action": "Signature, timestamp, and JSON shape are valid.",
    }


def verify_linear_webhook_payload(
    raw_body: bytes,
    *,
    signature: str,
    timestamp: str,
    secret: str | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    secret = secret if secret is not None else os.environ.get("LINEAR_WEBHOOK_SECRET", "")
    if not secret:
        raise LinearWebhookError(
            "LINEAR_WEBHOOK_SECRET is required for Linear webhook verification",
            code="LINEAR_WEBHOOK_SECRET_MISSING",
            next_action="Set LINEAR_WEBHOOK_SECRET before verifying or serving webhooks.",
            http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
    if not signature:
        raise LinearWebhookError(
            "Linear webhook signature is required",
            code="LINEAR_WEBHOOK_SIGNATURE_MISSING",
            next_action="Pass the Linear-Signature header value.",
            http_status=HTTPStatus.UNAUTHORIZED,
        )
    _assert_timestamp_fresh(timestamp, now_ms=_current_ms() if now_ms is None else now_ms)
    expected = hmac.new(secret.encode("utf-8"), raw_body, sha256).hexdigest()
    if not hmac.compare_digest(expected.lower(), signature.strip().lower()):
        raise LinearWebhookError(
            "Linear webhook signature did not match the raw payload",
            code="LINEAR_WEBHOOK_BAD_SIGNATURE",
            next_action="Check LINEAR_WEBHOOK_SECRET and use the unmodified raw request body.",
            http_status=HTTPStatus.UNAUTHORIZED,
        )
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise LinearWebhookError(
            f"Linear webhook payload was not valid JSON: {exc.msg}",
            code="LINEAR_WEBHOOK_INVALID_JSON",
            next_action="Inspect the webhook sender; Palari did not store the malformed payload.",
        ) from exc
    if not isinstance(payload, dict):
        raise LinearWebhookError(
            "Linear webhook payload must be a JSON object",
            code="LINEAR_WEBHOOK_UNSUPPORTED_PAYLOAD",
            next_action="Inspect the webhook sender; Palari expects Linear object payloads.",
        )
    return payload


def process_linear_webhook(
    workspace_path: str | Path,
    raw_body: bytes,
    headers: dict[str, str],
    *,
    secret: str | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    timestamp = normalized_headers.get("linear-timestamp", "")
    payload = verify_linear_webhook_payload(
        raw_body,
        signature=normalized_headers.get("linear-signature", ""),
        timestamp=timestamp,
        secret=secret,
        now_ms=now_ms,
    )
    event_type = _event_type(normalized_headers, payload)
    if event_type != "Issue":
        raise LinearWebhookError(
            f"unsupported Linear webhook event type: {event_type or 'unknown'}",
            code="LINEAR_WEBHOOK_UNSUPPORTED_EVENT",
            next_action="This dogfood slice accepts only Linear Issue webhooks.",
        )
    delivery_id = normalized_headers.get("linear-delivery", "")
    if not delivery_id:
        raise LinearWebhookError(
            "Linear-Delivery header is required for webhook dedupe",
            code="LINEAR_WEBHOOK_DELIVERY_MISSING",
            next_action="Forward the Linear-Delivery header to Palari unchanged.",
        )
    existing = _event_by_delivery(workspace_path, delivery_id)
    if existing is not None:
        return {
            "schema_version": "palari.linear_webhook_process.v1",
            "ok": True,
            "provider": "linear",
            "duplicate": True,
            "delivery_id": delivery_id,
            "event": _compact_event(existing),
            "next_action": "Duplicate delivery ignored; no workspace mutation was attempted.",
        }

    issue = _issue_from_payload(payload)
    action = _string(payload.get("action"))
    sync_result = _sync_issue_event(workspace_path, issue, action)
    record = _event_record(
        workspace_path,
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        issue=issue,
        sync_result=sync_result,
    )
    _append_event_log(workspace_path, record)
    return {
        "schema_version": "palari.linear_webhook_process.v1",
        "ok": True,
        "provider": "linear",
        "duplicate": False,
        "delivery_id": delivery_id,
        "event": record,
        "sync": sync_result,
        "next_action": record["next_action"],
    }


def create_linear_webhook_server(
    workspace_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    secret: str | None = None,
    now_ms: Callable[[], int] | None = None,
) -> ThreadingHTTPServer:
    secret = secret if secret is not None else os.environ.get("LINEAR_WEBHOOK_SECRET", "")
    if not secret:
        raise LinearWebhookError(
            "LINEAR_WEBHOOK_SECRET is required to serve Linear webhooks",
            code="LINEAR_WEBHOOK_SECRET_MISSING",
            next_action="Set LINEAR_WEBHOOK_SECRET before running `palari linear webhook serve`.",
            http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
    workspace_file = workspace_file_path(workspace_path)
    Workspace.load(workspace_file)
    config = LinearWebhookConfig(
        workspace_path=workspace_file,
        secret=secret,
        now_ms=now_ms or _current_ms,
    )
    return ThreadingHTTPServer((host, port), make_linear_webhook_handler(config))


def serve_linear_webhook(
    workspace_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    as_json: bool = False,
) -> dict[str, Any]:
    server = create_linear_webhook_server(workspace_path, host=host, port=port)
    payload = _server_payload(server, workspace_path)
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    else:
        print(f"Palari Linear webhook server: {payload['url']}", flush=True)
        print(f"Webhook path: {payload['webhook_path']}", flush=True)
        print(f"Workspace: {payload['workspace_file']}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    payload["stopped"] = True
    return payload


def make_linear_webhook_handler(config: LinearWebhookConfig) -> type[BaseHTTPRequestHandler]:
    class LinearWebhookHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/health":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "provider": "linear",
                        "webhook_path": LINEAR_WEBHOOK_PATH,
                    },
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown endpoint"})

        def do_POST(self) -> None:
            if self.path != LINEAR_WEBHOOK_PATH:
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown endpoint"})
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length else b""
            try:
                payload = process_linear_webhook(
                    config.workspace_path,
                    raw_body,
                    dict(self.headers.items()),
                    secret=config.secret,
                    now_ms=config.now_ms(),
                )
                self._send_json(HTTPStatus.OK, payload)
            except LinearWebhookError as exc:
                self._send_json(
                    exc.http_status,
                    {
                        "ok": False,
                        "error": {
                            "code": exc.code,
                            "message": str(exc),
                        },
                        "next_action": exc.next_action,
                    },
                )
            except Exception as exc:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": {"code": "LINEAR_WEBHOOK_ERROR", "message": str(exc)}},
                )

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    return LinearWebhookHandler


def _sync_issue_event(workspace_path: str | Path, issue: dict[str, str], action: str) -> dict[str, Any]:
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    proposal_matches = _linked_proposals(workspace, issue)
    work_matches = _linked_work_items(workspace, issue)
    remove_like = action == "remove" or bool(issue.get("archived_at"))
    if remove_like:
        return {
            "mutated": False,
            "reason": "remove_or_archive_event_is_audit_only",
            "proposal_ids": [proposal.id for proposal in proposal_matches],
            "work_item_ids": [work.id for work in work_matches],
        }
    if not proposal_matches and not work_matches:
        return {
            "mutated": False,
            "reason": "issue_not_linked",
            "proposal_ids": [],
            "work_item_ids": [],
        }

    proposals = _records(store.data, "proposals")
    work_items = _records(store.data, "work_items")
    mutated = False
    updated_proposals: list[str] = []
    updated_work: list[str] = []

    for proposal in proposal_matches:
        record = _record_by_id(proposals, proposal.id)
        before = deepcopy(record)
        _sync_external_fields(record, issue)
        if proposal.status != "adopted":
            record["title"] = issue["title"] or record.get("title", "")
            record["summary"] = issue["description"]
        if record != before:
            mutated = True
            updated_proposals.append(proposal.id)

    for work in work_matches:
        record = _record_by_id(work_items, work.id)
        before = deepcopy(record)
        _sync_external_fields(record, issue)
        if record != before:
            mutated = True
            updated_work.append(work.id)

    if mutated:
        objects = tuple(
            {"type": "proposal", "collection": "proposals", "id": object_id}
            for object_id in updated_proposals
        ) + tuple(
            {"type": "work", "collection": "work_items", "id": object_id}
            for object_id in updated_work
        )
        write_store(
            store,
            metadata=MutationMetadata(
                command="linear webhook",
                actor="linear-webhook",
                action="synced",
                timestamp=utc_timestamp(),
                objects=objects,
            ),
        )
    return {
        "mutated": mutated,
        "reason": "linked_records_synced" if mutated else "linked_records_already_current",
        "proposal_ids": [proposal.id for proposal in proposal_matches],
        "work_item_ids": [work.id for work in work_matches],
        "updated_proposals": updated_proposals,
        "updated_work_items": updated_work,
    }

def _event_record(
    workspace_path: str | Path,
    *,
    delivery_id: str,
    event_type: str,
    action: str,
    issue: dict[str, str],
    sync_result: dict[str, Any],
) -> dict[str, Any]:
    next_action, next_commands = _event_next_action(issue, sync_result)
    return {
        "schema_version": "palari.linear_webhook_event.v1",
        "delivery_id": delivery_id,
        "received_at": _timestamp(),
        "provider": "linear",
        "event_type": event_type,
        "action": action,
        "linear_issue": {
            "id": issue["id"],
            "key": issue["key"],
            "url": issue["url"],
            "updated_at": issue["updated_at"],
            "title": issue["title"],
        },
        "linked": {
            "proposal_ids": sync_result.get("proposal_ids", []),
            "work_item_ids": sync_result.get("work_item_ids", []),
        },
        "mutation": {
            "mutated": bool(sync_result.get("mutated")),
            "reason": sync_result.get("reason", ""),
            "updated_proposals": sync_result.get("updated_proposals", []),
            "updated_work_items": sync_result.get("updated_work_items", []),
        },
        "event_log_path": str(linear_webhook_event_log_path(workspace_path)),
        "next_action": next_action,
        "next_commands": next_commands,
    }


def _event_next_action(issue: dict[str, str], sync_result: dict[str, Any]) -> tuple[str, list[str]]:
    key = issue["key"] or issue["id"] or "ISSUE-KEY"
    if sync_result.get("reason") == "issue_not_linked":
        command = f"palari linear import {key} --as PALARI-ID --json"
        return "Linear issue is not linked to Palari; review and import if it belongs here.", [command]
    if sync_result.get("reason") == "remove_or_archive_event_is_audit_only":
        command = f"palari linear status {key} --json"
        return "Linear issue was removed or archived; review linked Palari records manually.", [command]
    return (
        "Linear issue sync recorded; inspect Palari status before taking action.",
        [f"palari linear status {key} --json", "palari linear linked --json"],
    )


def _event_type(headers: dict[str, str], payload: dict[str, Any]) -> str:
    header_value = headers.get("linear-event", "")
    payload_value = _string(payload.get("type"))
    return header_value or payload_value


def _issue_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise LinearWebhookError(
            "Linear Issue webhook payload is missing data object",
            code="LINEAR_WEBHOOK_ISSUE_DATA_MISSING",
            next_action="Inspect the webhook payload shape from Linear.",
        )
    identifier = _string(data.get("identifier")) or _string(data.get("key")) or _string(data.get("id"))
    return {
        "id": _string(data.get("id")),
        "key": identifier,
        "identifier": identifier,
        "title": _string(data.get("title")) or identifier,
        "description": _string(data.get("description")),
        "url": _string(data.get("url")),
        "updated_at": _string(data.get("updatedAt")) or _string(data.get("updated_at")),
        "archived_at": _string(data.get("archivedAt")) or _string(data.get("archived_at")),
    }


def _linked_proposals(workspace: Workspace, issue: dict[str, str]) -> list[Proposal]:
    return [proposal for proposal in workspace.proposals if _matches_linear(proposal, issue)]


def _linked_work_items(workspace: Workspace, issue: dict[str, str]) -> list[WorkItem]:
    return [work for work in workspace.work_items if _matches_linear(work, issue)]


def _matches_linear(record: Any, issue: dict[str, str]) -> bool:
    if getattr(record, "external_provider", "") != "linear":
        return False
    external_id = getattr(record, "external_id", "")
    external_key = getattr(record, "external_key", "")
    return bool(
        (issue.get("id") and external_id == issue["id"])
        or (issue.get("key") and external_key == issue["key"])
    )


def _sync_external_fields(record: dict[str, Any], issue: dict[str, str]) -> None:
    record.update(
        {
            "external_provider": "linear",
            "external_id": issue["id"],
            "external_key": issue["key"],
            "external_url": issue["url"],
            "external_updated_at": issue["updated_at"],
        }
    )


def _append_event_log(workspace_path: str | Path, event: dict[str, Any]) -> None:
    path = linear_webhook_event_log_path(workspace_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _read_event_log(workspace_path: str | Path) -> list[dict[str, Any]]:
    path = linear_webhook_event_log_path(workspace_path)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise LinearWebhookError(
                "Linear webhook event log contains a non-object record",
                code="LINEAR_WEBHOOK_EVENT_LOG_INVALID",
                next_action="Inspect .palari/linear-events.jsonl before continuing.",
            )
        events.append(event)
    return events


def _event_by_delivery(workspace_path: str | Path, delivery_id: str) -> dict[str, Any] | None:
    for event in _read_event_log(workspace_path):
        if event.get("delivery_id") == delivery_id:
            return event
    return None


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    issue = event.get("linear_issue", {})
    mutation = event.get("mutation", {})
    return {
        "delivery_id": event.get("delivery_id", ""),
        "received_at": event.get("received_at", ""),
        "event_type": event.get("event_type", ""),
        "action": event.get("action", ""),
        "issue_id": issue.get("id", "") if isinstance(issue, dict) else "",
        "issue_key": issue.get("key", "") if isinstance(issue, dict) else "",
        "issue_url": issue.get("url", "") if isinstance(issue, dict) else "",
        "updated_at": issue.get("updated_at", "") if isinstance(issue, dict) else "",
        "mutation": deepcopy(mutation) if isinstance(mutation, dict) else {},
        "next_action": event.get("next_action", ""),
    }


def _records(data: dict[str, Any], collection: str) -> list[dict[str, Any]]:
    records = data.setdefault(collection, [])
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise WorkspaceError(f"{collection} must be a list of objects")
    return records


def _record_by_id(records: list[dict[str, Any]], record_id: str) -> dict[str, Any]:
    for record in records:
        if str(record.get("id", "")) == record_id:
            return record
    raise WorkspaceError(f"record not found: {record_id}")


def _assert_timestamp_fresh(timestamp: str, *, now_ms: int) -> None:
    if not timestamp:
        raise LinearWebhookError(
            "Linear webhook timestamp is required",
            code="LINEAR_WEBHOOK_TIMESTAMP_MISSING",
            next_action="Pass the Linear-Timestamp header value.",
            http_status=HTTPStatus.UNAUTHORIZED,
        )
    try:
        timestamp_ms = int(timestamp)
    except ValueError as exc:
        raise LinearWebhookError(
            "Linear webhook timestamp must be milliseconds since epoch",
            code="LINEAR_WEBHOOK_TIMESTAMP_INVALID",
            next_action="Forward the Linear-Timestamp header unchanged.",
            http_status=HTTPStatus.UNAUTHORIZED,
        ) from exc
    if abs(now_ms - timestamp_ms) > LINEAR_WEBHOOK_REPLAY_WINDOW_MS:
        raise LinearWebhookError(
            "Linear webhook timestamp is outside the replay window",
            code="LINEAR_WEBHOOK_TIMESTAMP_STALE",
            next_action="Reject replayed webhooks and check the server clock.",
            http_status=HTTPStatus.UNAUTHORIZED,
        )


def _server_payload(server: ThreadingHTTPServer, workspace_path: str | Path) -> dict[str, Any]:
    bound_host = _host_text(str(server.server_address[0]))
    port = int(server.server_address[1])
    url = f"http://{bound_host}:{port}/"
    return {
        "schema_version": "palari.linear_webhook_server.v1",
        "ok": True,
        "provider": "linear",
        "url": url,
        "webhook_path": LINEAR_WEBHOOK_PATH,
        "webhook_url": url.rstrip("/") + LINEAR_WEBHOOK_PATH,
        "workspace_file": str(workspace_file_path(workspace_path)),
        "secret_ref": LINEAR_WEBHOOK_SECRET_REF,
        "secret_value_stored": False,
    }


def _host_text(host: str) -> str:
    return "127.0.0.1" if host in {"::", "0.0.0.0"} else host


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _current_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def main() -> int:
    print("Use `palari linear webhook ...`.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
