from __future__ import annotations

import json
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .authoring import create_human_decision
from .history import read_history
from .integrations import decide_integration_plan
from .read_models import detail, queue_items
from .store import workspace_file_path
from .workspace import Workspace, WorkspaceError


LOCALHOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class MissionControlConfig:
    workspace_path: Path
    human_id: str
    csrf_token: str


def serve_mission_control(
    workspace_path: str | Path,
    human_id: str,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> dict[str, Any]:
    server = create_mission_control_server(workspace_path, human_id, host=host, port=port)
    bound_host = _host_text(server.server_address[0])
    url = f"http://{bound_host}:{server.server_address[1]}/"
    print(f"Palari Mission Control: {url}", flush=True)
    print(f"Workspace: {workspace_file_path(workspace_path)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return {"url": url, "workspace_file": str(workspace_file_path(workspace_path))}


def create_mission_control_server(
    workspace_path: str | Path,
    human_id: str,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    csrf_token: str | None = None,
) -> ThreadingHTTPServer:
    workspace = Workspace.load(workspace_path)
    if workspace.human(human_id) is None:
        raise WorkspaceError(f"human not found: {human_id}")
    warning = host_security_warning(host)
    if warning:
        print(warning, file=sys.stderr, flush=True)
    config = MissionControlConfig(
        workspace_path=workspace_file_path(workspace_path),
        human_id=human_id,
        csrf_token=csrf_token or secrets.token_urlsafe(24),
    )
    return ThreadingHTTPServer((host, port), make_mission_control_handler(config))


def host_security_warning(host: str) -> str:
    if host in LOCALHOSTS:
        return ""
    return (
        "SECURITY WARNING: palari serve has no authentication. "
        f"Binding to {host!r} may expose local workspace controls."
    )


def workspace_hash(workspace_path: str | Path) -> str:
    data_path = workspace_file_path(workspace_path)
    return sha256(data_path.read_bytes()).hexdigest()


def make_mission_control_handler(config: MissionControlConfig) -> type[BaseHTTPRequestHandler]:
    class MissionControlHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send_html(_render_page(config))
                return
            if parsed.path == "/state-hash":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "workspace_hash": workspace_hash(config.workspace_path),
                        "workspace_file": str(config.workspace_path),
                    },
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/human-decision":
                self._handle_human_decision()
                return
            if parsed.path == "/integration-plan":
                self._handle_integration_plan()
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle_human_decision(self) -> None:
            payload = self._read_payload()
            blocked = self._guard_mutation(payload)
            if blocked:
                return
            try:
                record = human_decision_record_for_action(
                    Workspace.load(config.workspace_path),
                    str(payload.get("work_id") or ""),
                    config.human_id,
                    str(payload.get("action") or ""),
                    decision_id=str(payload.get("decision_id") or ""),
                    timestamp=str(payload.get("timestamp") or ""),
                )
                result = create_human_decision(
                    str(config.workspace_path),
                    record,
                    command="human-decision record",
                    actor=config.human_id,
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "action": result.action,
                        "record_id": result.record_id,
                        "workspace_hash": workspace_hash(config.workspace_path),
                    },
                )
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})

        def _handle_integration_plan(self) -> None:
            payload = self._read_payload()
            blocked = self._guard_mutation(payload)
            if blocked:
                return
            try:
                result = decide_integration_plan(
                    str(config.workspace_path),
                    str(payload.get("plan_id") or ""),
                    config.human_id,
                    str(payload.get("action") or ""),
                    reason=str(payload.get("reason") or "Mission Control decision."),
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "status": result["status"],
                        "workspace_hash": workspace_hash(config.workspace_path),
                    },
                )
            except Exception as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})

        def _guard_mutation(self, payload: dict[str, str]) -> bool:
            if payload.get("csrf_token") != config.csrf_token:
                self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "invalid CSRF token"})
                return True
            expected_hash = payload.get("workspace_hash")
            current_hash = workspace_hash(config.workspace_path)
            if expected_hash != current_hash:
                self._send_json(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": "workspace changed, refresh before writing",
                        "workspace_hash": current_hash,
                    },
                )
                return True
            return False

        def _read_payload(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            content_type = self.headers.get("Content-Type", "")
            if "application/json" in content_type:
                value = json.loads(raw or "{}")
                if not isinstance(value, dict):
                    raise ValueError("request body must be an object")
                return {str(key): str(val) for key, val in value.items()}
            parsed = parse_qs(raw, keep_blank_values=True)
            return {key: values[-1] if values else "" for key, values in parsed.items()}

        def _send_html(self, body: str) -> None:
            raw = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    return MissionControlHandler


def human_decision_record_for_action(
    workspace: Workspace,
    work_id: str,
    human_id: str,
    action: str,
    *,
    decision_id: str = "",
    timestamp: str = "",
) -> dict[str, Any]:
    if action not in {"approve", "reject", "cancel"}:
        raise WorkspaceError(f"unsupported human decision action: {action}")
    human = workspace.human(human_id)
    if human is None:
        raise WorkspaceError(f"human not found: {human_id}")
    work_detail = detail(workspace, work_id)
    review = work_detail.get("review") or {}
    evidence = work_detail.get("evidence") or {}
    if not review.get("reviewed_head"):
        raise WorkspaceError(f"work {work_id} has no reviewed head for human decision")
    decision = {
        "approve": "accepted",
        "reject": "rejected",
        "cancel": "canceled",
    }[action]
    return {
        "id": decision_id or _default_human_decision_id(work_id, human_id, action),
        "work_item_id": work_id,
        "human_id": human_id,
        "reviewed_head": str(review["reviewed_head"]),
        "decision": decision,
        "status": decision,
        "acceptance_mode": "human",
        "quorum_status": "met" if action == "approve" else "not-applicable",
        "evidence_reference": str(evidence.get("id") or ""),
        "review_reference": str(review.get("id") or ""),
        "timestamp": timestamp or _timestamp(),
    }


def _render_page(config: MissionControlConfig) -> str:
    workspace = Workspace.load(config.workspace_path)
    current_hash = workspace_hash(config.workspace_path)
    items = queue_items(workspace)
    needs = [item for item in items if item.waiting_on_human or item.attention == "blocked"]
    selected = needs[0] if needs else (items[0] if items else None)
    selected_detail = detail(workspace, selected.id) if selected else None
    history = read_history(config.workspace_path, limit=30)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(workspace.name)} Mission Control</title>
  <style>{_styles()}</style>
</head>
<body>
  <header class="topbar">
    <div><strong>Palari Mission Control</strong><span>{_e(workspace.name)}</span></div>
    <div class="badge">Acting as {_e(config.human_id)}</div>
  </header>
  <main class="shell">
    <section class="panel hero" id="needs-you">
      <div class="panel-head">
        <div><span class="eyebrow">Needs You</span><h1>Approval desk for your AI workforce</h1></div>
        <span class="count">{len(needs)} waiting</span>
      </div>
      {_needs_lane(workspace, needs, config, current_hash)}
    </section>
    <section class="panel" id="boundary-view">
      <span class="eyebrow">Boundary View</span>
      {_boundary_view(selected_detail)}
    </section>
    <section class="panel" id="activity-feed">
      <span class="eyebrow">Live Activity</span>
      {_activity_feed(history)}
    </section>
    <section class="panel" id="receipt-drawer">
      <span class="eyebrow">Receipt Drawer</span>
      {_receipt_drawer(selected_detail)}
    </section>
  </main>
  <script>
    const initialHash = {json.dumps(current_hash)};
    async function pollStateHash() {{
      try {{
        const response = await fetch('/state-hash', {{cache: 'no-store'}});
        const state = await response.json();
        if (state.workspace_hash && state.workspace_hash !== initialHash) {{
          window.location.reload();
        }}
      }} catch (error) {{}}
    }}
    setInterval(pollStateHash, 2000);
  </script>
</body>
</html>
"""


def _needs_lane(
    workspace: Workspace,
    needs: list[Any],
    config: MissionControlConfig,
    current_hash: str,
) -> str:
    pending_plans = [plan for plan in workspace.integration_plans if plan.status == "pending-approval"]
    if not needs and not pending_plans:
        return '<p class="empty">Nothing needs you. Your agents are inside their boundaries.</p>'
    cards = []
    for item in needs:
        forms = ""
        if item.next_step_type == "human-decision":
            forms = "".join(
                _human_decision_form(item.id, action, config, current_hash)
                for action in ("approve", "reject", "cancel")
            )
        cards.append(
            f"""
            <article class="need-card">
              <div>
                <span class="item-id">{_e(item.id)}</span>
                <h2>{_e(item.title)}</h2>
                <p>{_e(item.why)}</p>
                <p class="next">{_e(item.next_action)}</p>
              </div>
              <div class="actions">{forms or '<span class="muted">No direct UI action yet.</span>'}</div>
            </article>
            """
        )
    for plan in pending_plans:
        cards.append(
            f"""
            <article class="need-card">
              <div>
                <span class="item-id">{_e(plan.id)}</span>
                <h2>Integration plan waiting for approval</h2>
                <p>{_e(plan.integration_id)} wants to {_e(plan.action)} for {_e(plan.work_item_id)}.</p>
                <p class="next">No provider call will happen from this UI.</p>
              </div>
              <div class="actions">{_integration_plan_forms(plan.id, config, current_hash)}</div>
            </article>
            """
        )
    return "\n".join(cards)


def _human_decision_form(
    work_id: str,
    action: str,
    config: MissionControlConfig,
    current_hash: str,
) -> str:
    label = {"approve": "Approve", "reject": "Reject", "cancel": "Cancel"}[action]
    return f"""
    <form method="post" action="/human-decision">
      <input type="hidden" name="csrf_token" value="{_e(config.csrf_token)}">
      <input type="hidden" name="workspace_hash" value="{_e(current_hash)}">
      <input type="hidden" name="work_id" value="{_e(work_id)}">
      <input type="hidden" name="action" value="{_e(action)}">
      <button class="button button-{_e(action)}" type="submit">{_e(label)}</button>
    </form>
    """


def _integration_plan_forms(
    plan_id: str,
    config: MissionControlConfig,
    current_hash: str,
) -> str:
    return "".join(
        _integration_plan_form(plan_id, action, config, current_hash)
        for action in ("approve", "reject", "cancel")
    )


def _integration_plan_form(
    plan_id: str,
    action: str,
    config: MissionControlConfig,
    current_hash: str,
) -> str:
    label = {"approve": "Approve", "reject": "Reject", "cancel": "Cancel"}[action]
    return f"""
    <form method="post" action="/integration-plan">
      <input type="hidden" name="csrf_token" value="{_e(config.csrf_token)}">
      <input type="hidden" name="workspace_hash" value="{_e(current_hash)}">
      <input type="hidden" name="plan_id" value="{_e(plan_id)}">
      <input type="hidden" name="action" value="{_e(action)}">
      <input type="hidden" name="reason" value="Mission Control {label.lower()}">
      <button class="button button-{_e(action)}" type="submit">{_e(label)}</button>
    </form>
    """


def _boundary_view(work_detail: dict[str, Any] | None) -> str:
    if not work_detail:
        return '<p class="empty">No selected work item. Create work to see its read/write fence.</p>'
    work = work_detail["work_item"]
    attempt = work_detail.get("attempt") or {}
    sources = work_detail.get("sources") or []
    writes = work.get("output_targets") or work.get("allowed_resources") or []
    changed = attempt.get("changed_files") or []
    return f"""
    <h2>{_e(work['title'])}</h2>
    <div class="fence-grid">
      <div><h3>May read</h3>{_list(source.get('label', source.get('id', '')) for source in sources)}</div>
      <div><h3>May write after approval</h3>{_list(writes)}</div>
      <div><h3>Observed changes</h3>{_list(changed)}</div>
    </div>
    """


def _activity_feed(history: dict[str, Any]) -> str:
    events = list(reversed(history.get("events") or []))
    if not events:
        return '<p class="empty">No activity yet. Claims, checks, finishes, handoffs, and decisions appear here.</p>'
    return "<ol class=\"timeline\">" + "".join(
        f"<li><strong>{_e(event.get('action', 'event'))}</strong> "
        f"{_e(event.get('object_type', 'object'))}/{_e(event.get('object_id', ''))} "
        f"<span>{_e(event.get('timestamp', ''))}</span></li>"
        for event in events[:12]
    ) + "</ol>"


def _receipt_drawer(work_detail: dict[str, Any] | None) -> str:
    if not work_detail or not work_detail.get("receipt"):
        return '<p class="empty">No receipt for the selected work yet.</p>'
    receipt = work_detail["receipt"]
    return f"""
    <div class="receipt-grid">
      <div><h3>Used</h3>{_list(receipt.get('sources_used') or [])}</div>
      <div><h3>Created</h3>{_list(receipt.get('outputs_created') or [])}</div>
      <div><h3>Did not do</h3>{_list(receipt.get('not_done') or [])}</div>
      <div><h3>External writes</h3>{_list(receipt.get('external_writes') or [])}</div>
      <div><h3>Undo</h3>{_list(receipt.get('undo_refs') or [])}</div>
    </div>
    """


def _list(values: Any) -> str:
    items = [str(value) for value in values if str(value)]
    if not items:
        return '<p class="muted">None recorded.</p>'
    return "<ul>" + "".join(f"<li>{_e(item)}</li>" for item in items) + "</ul>"


def _styles() -> str:
    return """
    :root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#111827;background:#f6f8fa;font-size:14px;line-height:1.45}
    *{box-sizing:border-box}body{margin:0}.topbar{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;border-bottom:1px solid #d0d7de;background:#fff;position:sticky;top:0;z-index:5}.topbar span{margin-left:10px;color:#57606a}.badge{border:1px solid #d0d7de;border-radius:999px;padding:4px 10px;color:#57606a;background:#f6f8fa}
    .shell{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(280px,.65fr);gap:12px;padding:12px;max-width:1280px}.panel{border:1px solid #d0d7de;background:#fff;border-radius:8px;padding:14px}.hero{grid-column:1/-1;border-left:4px solid #cf222e}.panel-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.eyebrow{display:block;color:#57606a;font-weight:700;text-transform:uppercase;font-size:12px;letter-spacing:.06em}h1,h2,h3,p{margin:0}h1{font-size:20px}h2{font-size:16px;margin-top:4px}h3{font-size:12px;text-transform:uppercase;color:#57606a;margin-bottom:6px}.count{color:#cf222e;font-weight:700}.need-card{display:flex;justify-content:space-between;gap:16px;border:1px solid #d0d7de;border-radius:7px;padding:12px;margin-top:12px}.item-id{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#57606a}.next{margin-top:6px;color:#57606a}.actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.button{min-height:36px;border:1px solid #8c959f;background:#fff;border-radius:6px;padding:0 12px;font-weight:700;cursor:pointer}.button-approve{border-color:#1a7f37;color:#116329;background:#dafbe1}.button-reject{border-color:#bf8700;color:#9a6700;background:#fff8c5}.button-cancel{border-color:#8c959f;color:#57606a;background:#f6f8fa}
    .fence-grid,.receipt-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}.receipt-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.fence-grid>div,.receipt-grid>div{border:1px solid #d0d7de;border-radius:6px;padding:10px;background:#f6f8fa}ul{margin:0;padding-left:18px}.timeline{margin:12px 0 0;padding-left:18px}.timeline li{margin-bottom:8px}.timeline span{display:block;color:#57606a;font-size:12px}.empty,.muted{color:#57606a}@media(max-width:760px){.shell{grid-template-columns:1fr;padding:8px}.need-card{display:grid}.fence-grid,.receipt-grid{grid-template-columns:1fr}.topbar{height:auto;align-items:flex-start;gap:8px;padding:10px;flex-direction:column}}
    """


def _default_human_decision_id(work_id: str, human_id: str, action: str) -> str:
    return "HUMAN-DECISION-" + _slug(f"{work_id}-{human_id}-{action}")


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value.upper()).strip("-")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _host_text(host: Any) -> str:
    return host.decode("utf-8") if isinstance(host, bytes) else str(host)


def _e(value: Any) -> str:
    return escape(str(value), quote=True)
