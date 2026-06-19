from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .history import read_history
from .read_models import detail, queue_items
from .workspace import Workspace


@dataclass(frozen=True)
class DashboardResult:
    workspace: str
    output_dir: str
    index_path: str
    assets: list[str]


def generate_dashboard(workspace_path: str | Path, output_dir: str | Path) -> DashboardResult:
    workspace = Workspace.load(workspace_path)
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    history = read_history(workspace.path, limit=200)
    items = queue_items(workspace)
    details = {work.id: detail(workspace, work.id) for work in workspace.work_items}

    style_path = output / "styles.css"
    script_path = output / "app.js"
    index_path = output / "index.html"
    style_path.write_text(_styles(), encoding="utf-8")
    script_path.write_text(_script(), encoding="utf-8")
    index_path.write_text(
        _html(
            workspace=workspace,
            queue=items,
            details=details,
            history=history,
        ),
        encoding="utf-8",
    )
    return DashboardResult(
        workspace=workspace.name,
        output_dir=str(output),
        index_path=str(index_path),
        assets=[str(style_path), str(script_path)],
    )


def _html(
    *,
    workspace: Workspace,
    queue: list[Any],
    details: dict[str, dict[str, Any]],
    history: dict[str, Any],
) -> str:
    attention_counts = _counts(item.attention for item in queue)
    open_decisions = [decision for decision in workspace.decisions if decision.status == "open"]
    human_blockers = [item for item in queue if item.waiting_on_human]
    body = "\n".join(
        [
            _header(workspace, queue, attention_counts),
            '<main class="dashboard-shell">',
            _nav(),
            '<div class="sections">',
            _queue_section(workspace, queue, attention_counts),
            _work_section(workspace, queue, details),
            _trust_section(workspace),
            _history_section(history),
            _authority_section(workspace, open_decisions, human_blockers),
            "</div>",
            "</main>",
            _provenance(workspace),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(workspace.name)} Dashboard</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
{body}
  <script src="app.js"></script>
</body>
</html>
"""


def _header(workspace: Workspace, queue: list[Any], attention_counts: dict[str, int]) -> str:
    needs_human = attention_counts.get("needs-human-decision", 0)
    receipt_ready = attention_counts.get("receipt-ready", 0)
    active = len([item for item in queue if item.attention != "closed"])
    selected_sources = len([source for source in workspace.sources if source.selected])
    return f"""
<header class="topbar">
  <div class="brand-lockup">
    <span class="brand-mark" aria-hidden="true">P</span>
    <div>
      <p class="eyebrow">Palari Company OS</p>
      <h1>{_e(workspace.name)}</h1>
    </div>
  </div>
  <div class="topbar-summary" aria-label="Workspace summary">
    <span><strong>{needs_human}</strong> need human</span>
    <span><strong>{receipt_ready}</strong> receipt-ready</span>
    <a href="#trust"><strong>{selected_sources}/{len(workspace.receipts)}</strong> trust</a>
    <span><strong>{active}</strong> active</span>
  </div>
  <span class="read-only-badge">Read-only dashboard</span>
</header>
"""


def _nav() -> str:
    items = [
        ("Queue", "queue"),
        ("Work", "work"),
        ("Trust", "trust"),
        ("History", "history"),
        ("Authority", "authority"),
    ]
    links = "\n".join(
        f'<a href="#{anchor}" data-tab-link="{anchor}">{label}</a>' for label, anchor in items
    )
    return f'<nav class="section-nav" aria-label="Dashboard sections">{links}</nav>'


def _queue_section(workspace: Workspace, queue: list[Any], attention_counts: dict[str, int]) -> str:
    count_cards = "\n".join(
        _metric(label.replace("-", " "), attention_counts[label], _attention_tone(label), label)
        for label in sorted(attention_counts, key=lambda item: _attention_sort_key(item))
    )
    rows = "\n".join(_queue_card(item) for item in queue) or _empty("No work items in queue.")
    return f"""
<section id="queue" class="panel" data-tab-panel>
  <div class="section-heading">
    <div>
      <p class="eyebrow">Queue</p>
      <h2>What needs attention now</h2>
    </div>
    <p class="section-note">Prioritized by human decision, review, evidence, receipts, and closure.</p>
  </div>
  <div class="queue-brief">
    <div class="brief-primary">
      <span class="brief-number">{attention_counts.get("needs-human-decision", 0)}</span>
      <span>need human attention</span>
    </div>
    {_trust_snapshot(workspace)}
  </div>
  <div class="metric-strip">{count_cards}</div>
  <div class="queue-list">{rows}</div>
</section>
"""


def _queue_card(item: Any) -> str:
    return f"""
<details class="queue-item attention-{_class_token(item.attention)}" data-attention="{_e(item.attention)}">
  <summary class="queue-row">
    <span class="state-dot" aria-hidden="true"></span>
    <span class="queue-main">
      <span class="queue-title">{_e(item.title)}</span>
      <span class="queue-meta">{_e(item.goal_title)} · {_owner_label(item.owner)} · {_stage_flow(item)}</span>
      <span class="queue-next">{_e(item.next_action)}</span>
    </span>
    <span class="queue-side">
      {_receipt_chip(item)}
      <span class="record-id">{_e(item.id)}</span>
    </span>
  </summary>
  <div class="queue-detail">
    <dl class="state-grid">
      {_state("Attention", item.attention)}
      {_state("Risk", f"{item.risk} / {item.intensity}")}
      {_state("Palari", item.palari_name)}
      {_state("Owner", item.owner or "unassigned")}
      {_state("AI safe", _yes_no(item.ai_safe_to_proceed))}
      {_state("Human", "needed" if item.waiting_on_human else "not waiting")}
      {_state("Receipt", item.receipt_state)}
      {_state("Evidence", item.evidence_state)}
      {_state("Review", item.review_state)}
      {_state("Approval", item.approval_progress)}
    </dl>
    <p class="subtle">{_e(item.why)}</p>
  </div>
</details>
"""


def _work_section(workspace: Workspace, queue: list[Any], details: dict[str, dict[str, Any]]) -> str:
    grouped: dict[str, list[Any]] = {}
    for item in queue:
        grouped.setdefault(item.attention, []).append(item)
    lanes = []
    for attention in sorted(grouped, key=_attention_sort_key):
        cards = "\n".join(_work_detail_card(details[item.id]) for item in grouped[attention])
        lanes.append(
            f"""
<section class="lane">
  <div class="lane-heading">
    {_pill(attention, _attention_tone(attention))}
    <span>{len(grouped[attention])} work item(s)</span>
  </div>
  {cards}
</section>
"""
        )
    return f"""
<section id="work" class="panel" data-tab-panel>
  <div class="section-heading">
    <div>
      <p class="eyebrow">Work</p>
      <h2>Where work is in the flow</h2>
    </div>
    <p class="section-note">{len(workspace.work_items)} work items grouped by current attention state.</p>
  </div>
  <div class="lane-grid">{''.join(lanes)}</div>
</section>
"""


def _work_detail_card(payload: dict[str, Any]) -> str:
    work = payload["work_item"]
    goal = payload.get("goal") or {}
    palari = payload.get("palari") or {}
    attempt = payload.get("attempt")
    evidence = payload.get("evidence")
    review = payload.get("review")
    human_decision = payload.get("human_decision")
    receipt = payload.get("receipt")
    safety = payload["safety"]
    return f"""
<details class="detail-card">
  <summary>
    <span>
      <strong>{_e(work['title'])}</strong>
      <small>{_e(work['id'])} · {_e(goal.get('title', work['goal']))}</small>
    </span>
    {_pill(payload['attention'], _attention_tone(payload['attention']))}
  </summary>
  <div class="detail-body">
    <p class="subtle">{_e(work.get('scope', ''))}</p>
    <div class="flow-row" aria-label="Work flow">
      {_flow_step("Attempt", _status(attempt))}
      {_flow_step("Receipt", safety.get("receipt_state", "missing"))}
      {_flow_step("Evidence", safety.get("evidence_state", "missing"))}
      {_flow_step("Review", safety.get("review_state", "missing"))}
      {_flow_step("Human", safety.get("approval_progress", "0/0"))}
    </div>
    <div class="detail-columns">
      <div>
        <h4>Scope</h4>
        {_kv("Palari", palari.get("name", work["palari"]))}
        {_kv("Risk", f"{work['risk']} / {work['intensity']}")}
        {_list_block("Allowed sources", work.get("allowed_sources", []))}
        {_list_block("Allowed actions", work.get("allowed_actions", []))}
        {_list_block("Output targets", work.get("output_targets", []))}
        {_list_block("Forbidden actions", work.get("forbidden_actions", []))}
      </div>
      <div>
        <h4>State</h4>
        {_kv("Attempt", _record_label(attempt))}
        {_kv("Receipt", _record_label(receipt))}
        {_kv("Evidence", _record_label(evidence))}
        {_kv("Review", _record_label(review))}
        {_kv("Human decision", _record_label(human_decision))}
      </div>
    </div>
    <p class="next-action">{_e(payload['next_action'])}</p>
  </div>
</details>
"""


def _trust_section(workspace: Workspace) -> str:
    sources = "\n".join(_source_card(source) for source in workspace.sources) or _empty(
        "No selected sources recorded yet."
    )
    receipts = "\n".join(_receipt_card(workspace, receipt) for receipt in workspace.receipts) or _empty(
        "No receipts recorded yet."
    )
    return f"""
<section id="trust" class="panel" data-tab-panel>
  <div class="section-heading">
    <div>
      <p class="eyebrow">Trust</p>
      <h2>What Palaris used, made, did not do, and can undo</h2>
    </div>
    <p class="section-note">Receipts are human-facing trust evidence, separate from governance evidence.</p>
  </div>
  <div class="trust-grid">
    <section class="ledger-panel">
      <div class="ledger-heading">
        <h3>Selected sources</h3>
        <span>{len(workspace.sources)} source(s)</span>
      </div>
      {sources}
    </section>
    <section class="ledger-panel">
      <div class="ledger-heading">
        <h3>Receipts</h3>
        <span>{len(workspace.receipts)} receipt(s)</span>
      </div>
      {receipts}
    </section>
  </div>
</section>
"""


def _source_card(source: Any) -> str:
    return f"""
<details class="ledger-row source-row">
  <summary>
    <span>
      <strong>{_e(source.label)}</strong>
      <small>{_e(source.id)} · {_e(source.provider or 'unspecified')} · {_e(source.kind or 'unspecified')}</small>
    </span>
    {_pill("selected" if source.selected else "available", "trust" if source.selected else "neutral")}
  </summary>
  <div class="ledger-detail">
    <dl class="compact-dl">
      {_state("Access", source.access_mode or "unspecified")}
      {_state("Owner", source.owner_human or "none")}
      {_state("Allowed Palaris", ", ".join(source.allowed_palaris) or "any")}
      {_state("URI", source.uri or source.external_id or "not recorded")}
      {_state("Last read", source.last_read_at or "not recorded")}
      {_state("Last seen revision", source.last_seen_revision or "not recorded")}
    </dl>
  </div>
</details>
"""


def _receipt_card(workspace: Workspace, receipt: Any) -> str:
    work = workspace.work_item(receipt.work_item_id)
    title = work.title if work else receipt.work_item_id
    return f"""
<details class="ledger-row receipt-card">
  <summary>
    <span>
      <strong>{_e(title)}</strong>
      <small>{_e(receipt.id)} · attempt {_e(receipt.attempt_id)}</small>
    </span>
    {_pill(receipt.actor, "neutral")}
  </summary>
  <div class="ledger-detail receipt-ledger-detail">
    {_list_block("Sources used", receipt.sources_used)}
    {_list_block("Actions taken", receipt.actions_taken)}
    {_list_block("Outputs created", receipt.outputs_created)}
    {_list_block("External writes", receipt.external_writes or ["none"])}
    {_list_block("Not done", receipt.not_done)}
    {_list_block("Undo refs", receipt.undo_refs)}
  </div>
</details>
"""


def _history_section(history: dict[str, Any]) -> str:
    events = history.get("events") or []
    timeline = "\n".join(_history_event(event) for event in events) or _empty(
        "No history events recorded for this workspace."
    )
    return f"""
<section id="history" class="panel" data-tab-panel>
  <div class="section-heading">
    <div>
      <p class="eyebrow">History</p>
      <h2>Append-only event timeline</h2>
    </div>
    <p class="section-note">Source: <code>{_e(str(history.get('history_file', '')))}</code></p>
  </div>
  <div class="timeline">{timeline}</div>
</section>
"""


def _history_event(event: dict[str, Any]) -> str:
    changed = event.get("changed_fields") or {}
    changed_text = ", ".join(sorted(changed)) if isinstance(changed, dict) and changed else "none"
    return f"""
<article class="timeline-event">
  <div class="timeline-dot"></div>
  <div>
    <p class="subtle">{_e(str(event.get('timestamp', 'unknown time')))} · {_e(str(event.get('actor', 'unknown actor')))}</p>
    <h3>{_e(str(event.get('action', 'event')))} {_e(str(event.get('object_type', 'object')))}/{_e(str(event.get('object_id', 'unknown')))}</h3>
    <p><code>{_e(str(event.get('command', '')))}</code></p>
    <p class="subtle">Changed fields: {_e(changed_text)}</p>
  </div>
</article>
"""


def _authority_section(
    workspace: Workspace,
    open_decisions: list[Any],
    human_blockers: list[Any],
) -> str:
    humans = "\n".join(_human_card(human) for human in workspace.humans) or _empty(
        "No humans recorded."
    )
    palaris = "\n".join(_palari_card(palari) for palari in workspace.palaris) or _empty(
        "No Palaris recorded."
    )
    decisions = "\n".join(_decision_card(decision) for decision in open_decisions) or _empty(
        "No open decisions."
    )
    blockers = "\n".join(_blocker_card(item) for item in human_blockers) or _empty(
        "No queue items are waiting on a human."
    )
    return f"""
<section id="authority" class="panel" data-tab-panel>
  <div class="section-heading">
    <div>
      <p class="eyebrow">Authority</p>
      <h2>Who can decide, who owns the work, and what is blocked</h2>
    </div>
    <p class="section-note">AI roles do not silently inherit human authority.</p>
  </div>
  <div class="authority-grid">
    <section><h3>Humans</h3>{humans}</section>
    <section><h3>Palaris</h3>{palaris}</section>
    <section><h3>Open decisions</h3>{decisions}</section>
    <section><h3>Human blockers</h3>{blockers}</section>
  </div>
</section>
"""


def _human_card(human: Any) -> str:
    return f"""
<article class="trust-card">
  <h4>{_e(human.name)}</h4>
  <p class="subtle">{_e(human.role or human.id)} · {_e(human.authority_level)}</p>
  {_list_block("Approval capabilities", human.approval_capabilities)}
  {_list_block("Ownership", human.ownership_areas)}
</article>
"""


def _palari_card(palari: Any) -> str:
    return f"""
<article class="trust-card">
  <h4>{_e(palari.name)}</h4>
  <p class="subtle">{_e(palari.role)} · owner {_e(palari.owner_human or 'none')}</p>
  <p>{_e(palari.scope)}</p>
  {_list_block("Forbidden actions", palari.forbidden_actions)}
  {_list_block("Active work", palari.active_work)}
</article>
"""


def _decision_card(decision: Any) -> str:
    return f"""
<article class="trust-card">
  <div class="card-title-row">
    <h4>{_e(decision.id)}</h4>
    {_pill(decision.status, "urgent" if decision.status == "open" else "neutral")}
  </div>
  <p>{_e(decision.question)}</p>
  <p class="subtle">Required: {_e(decision.required_human or decision.required_role or 'unspecified')}</p>
</article>
"""


def _blocker_card(item: Any) -> str:
    return f"""
<article class="trust-card">
  <div class="card-title-row">
    <h4>{_e(item.id)}</h4>
    {_pill(item.attention, _attention_tone(item.attention))}
  </div>
  <p>{_e(item.title)}</p>
  <p class="next-action">{_e(item.next_action)}</p>
</article>
"""


def _metric(label: str, value: int, tone: str, filter_value: str = "") -> str:
    data_filter = f' data-filter="{_e(filter_value)}"' if filter_value else ""
    return (
        f'<button class="metric metric-{tone}" type="button"{data_filter}>'
        f'<span>{_e(str(value))}</span><small>{_e(label)}</small></button>'
    )


def _pill(label: str, tone: str) -> str:
    return f'<span class="pill pill-{tone}">{_e(label)}</span>'


def _state(label: str, value: Any) -> str:
    return f"<dt>{_e(label)}</dt><dd>{_e(str(value))}</dd>"


def _kv(label: str, value: Any) -> str:
    return f'<p class="kv"><span>{_e(label)}</span><strong>{_e(str(value or "none"))}</strong></p>'


def _list_block(title: str, values: list[Any]) -> str:
    if not values:
        return f'<div class="list-block"><strong>{_e(title)}</strong><p class="subtle">none</p></div>'
    items = "".join(f"<li>{_e(str(item))}</li>" for item in values)
    return f'<div class="list-block"><strong>{_e(title)}</strong><ul>{items}</ul></div>'


def _flow_step(label: str, value: str) -> str:
    tone = _state_tone(value)
    return f'<div class="flow-step flow-{tone}"><span>{_e(label)}</span><strong>{_e(value)}</strong></div>'


def _stage_flow(item: Any) -> str:
    stages = [
        ("Receipt", item.receipt_state),
        ("Evidence", item.evidence_state),
        ("Review", item.review_state),
        ("Approval", item.approval_progress),
    ]
    rendered = []
    for label, value in stages:
        rendered.append(f'<span class="stage stage-{_state_tone(str(value))}">{_e(label)}</span>')
    return '<span class="stage-flow">' + '<span class="stage-sep">/</span>'.join(rendered) + "</span>"


def _receipt_chip(item: Any) -> str:
    state = item.receipt_state
    tone = "trust" if state == "ready" else "warn" if state in {"missing", "stale", "failed"} else "neutral"
    return f'<span class="receipt-chip receipt-{tone}">Receipt: {_e(state)}</span>'


def _owner_label(owner: str) -> str:
    return _e(owner) if owner else "unassigned"


def _trust_snapshot(workspace: Workspace) -> str:
    selected = len([source for source in workspace.sources if source.selected])
    receipts = len(workspace.receipts)
    external_writes = sum(1 for receipt in workspace.receipts if receipt.external_writes)
    return f"""
    <div class="trust-snapshot" aria-label="Trust summary">
      <span><strong>{selected}</strong> selected source(s)</span>
      <span><strong>{receipts}</strong> receipt(s)</span>
      <span><strong>{external_writes}</strong> external write(s)</span>
    </div>
    """


def _provenance(workspace: Workspace) -> str:
    return f"""
<footer class="provenance">
  <details>
    <summary>Source: filesystem workspace · path hidden</summary>
    <p>Read-only dashboard generated from <code>{_e(str(workspace.path))}</code>.</p>
  </details>
</footer>
"""


def _empty(message: str) -> str:
    return f'<div class="empty-state">{_e(message)}</div>'


def _owner(owner: str) -> str:
    return f" · owner {escape(owner)}" if owner else ""


def _record_label(record: dict[str, Any] | None) -> str:
    if not record:
        return "none"
    identifier = record.get("id") or record.get("status") or "recorded"
    status = record.get("status") or record.get("verdict") or ""
    return f"{identifier} ({status})" if status else str(identifier)


def _status(record: dict[str, Any] | None) -> str:
    if not record:
        return "missing"
    return str(record.get("status") or record.get("verdict") or "recorded")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _attention_sort_key(attention: str) -> int:
    order = {
        "needs-human-decision": 0,
        "changes-requested": 1,
        "needs-review": 2,
        "needs-evidence": 3,
        "ready-to-integrate": 4,
        "receipt-ready": 5,
        "ready-for-ai-work": 6,
        "blocked": 7,
        "closed": 8,
    }
    return order.get(attention, 99)


def _attention_tone(attention: str) -> str:
    if attention in {"needs-human-decision", "blocked", "changes-requested"}:
        return "urgent"
    if attention in {"needs-review", "needs-evidence"}:
        return "warn"
    if attention in {"receipt-ready", "ready-to-integrate"}:
        return "trust"
    if attention == "closed":
        return "done"
    return "neutral"


def _state_tone(value: str) -> str:
    lowered = value.lower()
    if lowered in {"ready", "passed", "accept-ready", "complete", "completed", "1/1"}:
        return "trust"
    if lowered in {"missing", "stale", "failed", "blocked"} or lowered.startswith("0/"):
        return "warn"
    return "neutral"


def _class_token(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")


def _e(value: Any) -> str:
    return escape(str(value), quote=True)


def _styles() -> str:
    return """
:root {
  --bg: #f3f6f8;
  --panel: #ffffff;
  --panel-2: #f8fafc;
  --ink: #10223a;
  --muted: #627084;
  --line: #d7e0ea;
  --line-strong: #c3d0dc;
  --urgent: #9d2f2f;
  --urgent-bg: #fff0ee;
  --warn: #9a6500;
  --warn-bg: #fff7df;
  --trust: #087b68;
  --trust-bg: #e7faf5;
  --done: #576476;
  --done-bg: #eef1f5;
  --neutral: #265da8;
  --neutral-bg: #edf5ff;
  --attention-bg: #fff7f5;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; overflow-x: hidden; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-size: 14px;
  line-height: 1.42;
  overflow-x: hidden;
}
a { color: inherit; }
button { font: inherit; }
code {
  color: #35465c;
  background: #edf2f7;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.08rem 0.32rem;
}
.topbar {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  min-height: 4rem;
  padding: 0.65rem clamp(0.85rem, 3vw, 1.4rem);
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.94);
  position: sticky;
  top: 0;
  z-index: 30;
  backdrop-filter: blur(10px);
}
h1, h2, h3, h4, p { margin-top: 0; }
h1 { margin-bottom: 0; font-size: clamp(1rem, 2vw, 1.3rem); letter-spacing: 0; line-height: 1.12; }
h2 { margin-bottom: 0.12rem; font-size: 1.25rem; }
h3 { margin-bottom: 0.35rem; font-size: 1rem; }
h4 { margin-bottom: 0.35rem; font-size: 0.95rem; }
.eyebrow {
  margin-bottom: 0.1rem;
  color: var(--trust);
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.subtle, .section-note { color: var(--muted); }
.brand-lockup {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 0.65rem;
}
.brand-mark {
  display: inline-grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  border-radius: 9px;
  color: #fff;
  background: var(--ink);
  font-weight: 900;
  flex: 0 0 2rem;
}
.topbar-summary {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  color: var(--muted);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.topbar-summary span {
  display: inline-flex;
  align-items: baseline;
  gap: 0.25rem;
}
.topbar-summary a {
  display: inline-flex;
  align-items: baseline;
  gap: 0.25rem;
  color: var(--trust);
  text-decoration: none;
  border-radius: 999px;
}
.topbar-summary strong { color: var(--ink); font-size: 1rem; }
.read-only-badge {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.35rem 0.65rem;
  background: var(--panel-2);
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 800;
}
.metric {
  min-height: 2.75rem;
  padding: 0.42rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: transparent;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
}
.metric:hover, .metric.is-active { border-color: var(--line-strong); background: #fff; }
.metric span { font-size: 1rem; font-weight: 850; margin-right: 0.25rem; }
.metric small { color: var(--muted); text-transform: capitalize; }
.metric-urgent { color: var(--urgent); background: var(--urgent-bg); border-color: #f0b8b2; }
.metric-warn { color: var(--warn); background: #fffdf5; border-color: #edd08f; }
.metric-trust { color: var(--trust); background: #f3fffb; border-color: #9fd8cc; }
.metric-done { background: var(--done-bg); }
.dashboard-shell {
  display: grid;
  gap: 0.9rem;
  width: min(100%, 1340px);
  margin: 0 auto;
  padding: 0.9rem clamp(0.75rem, 2vw, 1.35rem);
}
.section-nav {
  position: sticky;
  top: 4rem;
  z-index: 20;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.38rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
}
.section-nav a {
  min-height: 2.25rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.4rem 0.8rem;
  border-radius: 999px;
  color: var(--muted);
  text-decoration: none;
  font-weight: 800;
}
.section-nav a.is-active, .section-nav a:hover { color: var(--ink); background: var(--panel-2); }
.section-nav a:focus-visible,
.metric:focus-visible,
.queue-row:focus-visible,
.ledger-row summary:focus-visible,
.provenance summary:focus-visible,
.topbar-summary a:focus-visible {
  outline: 2px solid #6ba8ff;
  outline-offset: 2px;
}
.sections { display: grid; gap: 1rem; min-width: 0; }
.panel {
  padding: clamp(0.9rem, 2vw, 1.2rem);
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--panel);
}
.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.8rem;
  min-width: 0;
}
.queue-brief {
  display: grid;
  grid-template-columns: minmax(12rem, 0.7fr) minmax(0, 1fr);
  gap: 0.75rem;
  align-items: stretch;
  margin-bottom: 0.75rem;
  min-width: 0;
}
.brief-primary, .trust-snapshot {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-height: 3.25rem;
  padding: 0.65rem 0.8rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--panel-2);
}
.brief-number { color: var(--urgent); font-size: 1.65rem; font-weight: 900; }
.trust-snapshot {
  justify-content: space-between;
  color: var(--muted);
  min-width: 0;
}
.trust-snapshot span { display: inline-flex; gap: 0.3rem; }
.trust-snapshot strong { color: var(--ink); }
.metric-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
}
.queue-list {
  display: grid;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel);
}
.lane-grid, .trust-grid, .authority-grid { display: grid; gap: 0.75rem; }
.trust-grid, .authority-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.lane-grid { grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); align-items: start; }
.work-card, .detail-card, .trust-card, .timeline-event {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel-2);
}
.work-card {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(16rem, 0.75fr);
  gap: 1rem;
  padding: 0.9rem;
  border-left: 5px solid var(--neutral);
}
.attention-needs-human-decision, .attention-blocked, .attention-changes-requested { border-left-color: var(--urgent); }
.attention-needs-review, .attention-needs-evidence { border-left-color: var(--warn); }
.attention-receipt-ready, .attention-ready-to-integrate { border-left-color: var(--trust); }
.attention-closed { border-left-color: var(--done); }
.card-title-row, .lane-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}
.record-id { color: var(--muted); font-weight: 700; }
.queue-item {
  border-bottom: 1px solid var(--line);
}
.queue-item:last-child { border-bottom: 0; }
.queue-item[open] { background: #fbfdff; }
.queue-row {
  display: grid;
  grid-template-columns: 0.7rem minmax(0, 1fr) auto;
  gap: 0.75rem;
  align-items: center;
  min-height: 4.2rem;
  padding: 0.72rem 0.9rem;
  cursor: pointer;
  list-style: none;
}
.queue-row::-webkit-details-marker { display: none; }
.queue-row:hover, .queue-item[open] .queue-row { background: var(--panel-2); }
.state-dot {
  width: 0.62rem;
  height: 0.62rem;
  border-radius: 999px;
  background: var(--neutral);
}
.attention-needs-human-decision .state-dot,
.attention-blocked .state-dot,
.attention-changes-requested .state-dot { background: var(--urgent); }
.attention-needs-review .state-dot,
.attention-needs-evidence .state-dot { background: var(--warn); }
.attention-receipt-ready .state-dot,
.attention-ready-to-integrate .state-dot { background: var(--trust); }
.attention-closed .state-dot { background: var(--done); }
.attention-needs-human-decision .queue-row,
.attention-blocked .queue-row,
.attention-changes-requested .queue-row { background: var(--attention-bg); }
.queue-main {
  display: grid;
  min-width: 0;
  gap: 0.12rem;
}
.queue-title {
  min-width: 0;
  overflow: hidden;
  color: var(--ink);
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.queue-meta, .queue-next {
  min-width: 0;
  overflow: hidden;
  color: var(--muted);
  font-size: 0.82rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.queue-next { color: #2a3a50; font-weight: 700; }
.queue-side {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-self: end;
  min-width: 0;
}
.receipt-chip {
  display: inline-flex;
  align-items: center;
  min-height: 1.8rem;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 850;
  white-space: nowrap;
}
.receipt-trust { color: var(--trust); background: var(--trust-bg); border-color: #9fd8cc; }
.receipt-warn { color: var(--warn); background: var(--warn-bg); border-color: #edd08f; }
.receipt-neutral { color: var(--neutral); background: var(--neutral-bg); }
.queue-detail {
  padding: 0 0.9rem 0.9rem 2.35rem;
}
.stage-flow {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-left: 0.1rem;
}
.stage {
  font-weight: 800;
  color: var(--muted);
}
.stage-trust { color: var(--trust); }
.stage-warn { color: var(--warn); }
.stage-neutral { color: var(--neutral); }
.stage-sep { color: #b7c2cf; }
.pill {
  display: inline-flex;
  align-items: center;
  min-height: 1.65rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  font-size: 0.75rem;
  font-weight: 800;
  text-transform: capitalize;
  white-space: nowrap;
}
.pill-urgent { color: var(--urgent); background: var(--urgent-bg); border-color: #f0b8b2; }
.pill-warn { color: var(--warn); background: var(--warn-bg); border-color: #edd08f; }
.pill-trust { color: var(--trust); background: var(--trust-bg); border-color: #9fd8cc; }
.pill-done { color: var(--done); background: var(--done-bg); }
.pill-neutral { color: var(--neutral); background: var(--neutral-bg); }
.next-action {
  margin-bottom: 0;
  color: var(--ink);
  font-weight: 700;
}
.state-grid, .compact-dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.35rem 0.75rem;
  margin: 0;
}
dt { color: var(--muted); font-size: 0.78rem; }
dd { margin: 0; font-weight: 700; overflow-wrap: anywhere; }
.lane {
  display: grid;
  gap: 0.55rem;
  padding: 0.65rem;
  border: 1px dashed var(--line);
  border-radius: 10px;
}
.detail-card { overflow: hidden; }
.detail-card summary {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.75rem;
  cursor: pointer;
}
.detail-card summary small {
  display: block;
  color: var(--muted);
  margin-top: 0.1rem;
}
.detail-body {
  padding: 0 0.75rem 0.85rem;
  border-top: 1px solid var(--line);
}
.flow-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.4rem;
  margin: 0.8rem 0;
}
.flow-step {
  min-width: 0;
  padding: 0.55rem;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
.flow-step span { display: block; color: var(--muted); font-size: 0.74rem; }
.flow-step strong { overflow-wrap: anywhere; }
.flow-trust { border-color: #9fd8cc; background: var(--trust-bg); }
.flow-warn { border-color: #edd08f; background: var(--warn-bg); }
.detail-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}
.kv {
  display: flex;
  justify-content: space-between;
  gap: 0.6rem;
  margin-bottom: 0.35rem;
}
.kv span { color: var(--muted); }
.kv strong { text-align: right; overflow-wrap: anywhere; }
.trust-card { padding: 0.8rem; margin-bottom: 0.65rem; }
.ledger-panel {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel-2);
  overflow: hidden;
}
.ledger-heading {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: baseline;
  padding: 0.75rem 0.9rem;
  border-bottom: 1px solid var(--line);
  background: #fff;
}
.ledger-heading h3 { margin-bottom: 0; }
.ledger-heading span { color: var(--muted); font-size: 0.82rem; }
.ledger-row {
  border-bottom: 1px solid var(--line);
  background: #fff;
}
.ledger-row:last-child { border-bottom: 0; }
.ledger-row summary {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
  min-height: 3.55rem;
  padding: 0.65rem 0.9rem;
  cursor: pointer;
  list-style: none;
}
.ledger-row summary::-webkit-details-marker { display: none; }
.ledger-row summary small {
  display: block;
  color: var(--muted);
  margin-top: 0.12rem;
}
.ledger-row[open] summary { background: var(--panel-2); }
.ledger-detail {
  padding: 0 0.9rem 0.85rem;
  margin-left: 0.85rem;
  border-left: 3px solid var(--neutral-bg);
}
.receipt-ledger-detail {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.35rem 0.8rem;
}
.list-block { margin-top: 0.55rem; }
.list-block ul {
  margin: 0.25rem 0 0;
  padding-left: 1.1rem;
}
.list-block li { margin-bottom: 0.16rem; overflow-wrap: anywhere; }
.timeline { display: grid; gap: 0.7rem; }
.timeline-event {
  position: relative;
  display: grid;
  grid-template-columns: 1rem minmax(0, 1fr);
  gap: 0.7rem;
  padding: 0.8rem;
}
.timeline-dot {
  width: 0.72rem;
  height: 0.72rem;
  margin-top: 0.35rem;
  border-radius: 999px;
  background: var(--trust);
}
.empty-state {
  padding: 0.85rem;
  color: var(--muted);
  border: 1px dashed var(--line);
  border-radius: 8px;
  background: var(--panel-2);
}
.provenance {
  width: min(100%, 1340px);
  margin: 0 auto 1.2rem;
  padding: 0 clamp(0.75rem, 2vw, 1.35rem);
  color: var(--muted);
  font-size: 0.82rem;
}
.provenance details {
  border-top: 1px solid var(--line);
  padding-top: 0.7rem;
}
.provenance summary { cursor: pointer; font-weight: 800; }
.is-filtered-out { display: none; }

@media (max-width: 900px) {
  body { padding-bottom: calc(4.3rem + env(safe-area-inset-bottom)); }
  .topbar {
    position: static;
    flex-wrap: wrap;
    align-items: flex-start;
  }
  .topbar-summary { order: 3; width: 100%; }
  .read-only-badge { margin-left: auto; }
  .section-nav {
    position: fixed;
    top: auto;
    left: 0.6rem;
    right: 0.6rem;
    bottom: calc(0.6rem + env(safe-area-inset-bottom));
    justify-content: space-between;
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(16, 34, 58, 0.18);
  }
  .section-nav a { flex: 1 1 0; padding-inline: 0.35rem; }
  .queue-brief { grid-template-columns: 1fr; }
  .work-card, .trust-grid, .authority-grid, .detail-columns { grid-template-columns: 1fr; }
  .receipt-ledger-detail { grid-template-columns: 1fr; }
  .flow-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 520px) {
  body { font-size: 14px; }
  .dashboard-shell { padding: 0.55rem; }
  .panel { padding: 0.8rem; }
  .section-heading, .card-title-row { display: grid; }
  .topbar {
    min-height: 3.35rem;
    padding-block: 0.45rem;
  }
  .topbar-summary {
    display: flex;
    order: 2;
    width: auto;
    gap: 0.45rem;
    font-size: 0.76rem;
  }
  .topbar-summary a {
    align-items: center;
    min-height: 2.45rem;
    padding: 0 0.42rem;
    background: var(--trust-bg);
  }
  .topbar-summary span:nth-child(2),
  .topbar-summary span:nth-child(4) { display: none; }
  .brand-lockup { max-width: calc(100% - 7rem); }
  h1 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .eyebrow { display: none; }
  .read-only-badge { display: none; }
  .section-nav {
    gap: 0.25rem;
    padding: 0.3rem;
  }
  .section-nav a { min-height: 2.7rem; font-size: 0.84rem; }
  .brief-primary, .trust-snapshot {
    min-height: 2.35rem;
    padding: 0.45rem 0.6rem;
  }
  .brief-primary {
    display: flex;
  }
  .brief-number { font-size: 1.3rem; }
  .trust-snapshot {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow: visible;
    white-space: normal;
  }
  .trust-snapshot span:nth-child(3) { display: none; }
  .metric-strip {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow: visible;
    padding-bottom: 0;
  }
  .metric {
    min-width: 0;
    min-height: 2.3rem;
  }
  .queue-row {
    grid-template-columns: 0.65rem minmax(0, 1fr);
    min-height: 4.4rem;
    padding: 0.72rem;
  }
  .queue-side {
    grid-column: 2;
    justify-self: start;
    flex-wrap: wrap;
  }
  .receipt-chip { white-space: normal; }
  .queue-meta, .queue-next { white-space: normal; }
  .queue-detail { padding-left: 1.9rem; }
  .state-grid, .compact-dl, .flow-row { grid-template-columns: 1fr; }
}
"""


def _script() -> str:
    return """
(function () {
  const links = Array.from(document.querySelectorAll('[data-tab-link]'));
  const sections = links
    .map((link) => document.getElementById(link.getAttribute('data-tab-link')))
    .filter(Boolean);

  function updateActive() {
    let active = sections[0] && sections[0].id;
    for (const section of sections) {
      const rect = section.getBoundingClientRect();
      if (rect.top <= 120) active = section.id;
    }
    for (const link of links) {
      link.classList.toggle('is-active', link.getAttribute('data-tab-link') === active);
    }
  }

  const filters = Array.from(document.querySelectorAll('[data-filter]'));
  const queueItems = Array.from(document.querySelectorAll('[data-attention]'));
  let activeFilter = '';

  function applyFilter(filter) {
    activeFilter = activeFilter === filter ? '' : filter;
    for (const button of filters) {
      button.classList.toggle('is-active', button.getAttribute('data-filter') === activeFilter);
    }
    for (const item of queueItems) {
      item.classList.toggle(
        'is-filtered-out',
        Boolean(activeFilter) && item.getAttribute('data-attention') !== activeFilter
      );
    }
  }

  for (const button of filters) {
    button.addEventListener('click', () => applyFilter(button.getAttribute('data-filter')));
  }

  updateActive();
  document.addEventListener('scroll', updateActive, { passive: true });
})();
"""
