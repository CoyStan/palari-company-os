from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .decision_guides import build_decision_guide
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
            '<div class="app">',
            _nav(),
            '<main class="content" id="top">',
            _attention_strip(workspace, queue, attention_counts),
            _queue_section(workspace, queue, attention_counts),
            _work_section(workspace, queue, details),
            _trust_section(workspace),
            _history_section(history),
            _authority_section(workspace, open_decisions, human_blockers),
            "</main>",
            _provenance(workspace),
            "</div>",
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
    selected_sources = len([source for source in workspace.sources if source.selected])
    active = len([item for item in queue if item.attention != "closed"])
    human_tone = "hot" if needs_human else "calm"
    return f"""
<header class="topbar">
  <a class="brand" href="#top" aria-label="Dashboard top">
    <span class="brand-mark" aria-hidden="true">P</span>
    <span class="brand-name">{_e(workspace.name)}</span>
  </a>
  <div class="topbar-rail" aria-label="Workspace summary">
    <a class="rail-chip rail-{human_tone}" href="#queue" title="Items needing a human decision">
      <span class="rail-num">{needs_human}</span><span class="rail-label">need human</span>
    </a>
    <a class="rail-chip" href="#trust" title="Selected sources / receipts">
      <span class="rail-num">{selected_sources}/{len(workspace.receipts)}</span><span class="rail-label">trust</span>
    </a>
    <span class="rail-chip rail-mute" title="Active (non-closed) work items">
      <span class="rail-num">{active}</span><span class="rail-label">active</span>
    </span>
  </div>
  <span class="ro-badge">Read-only dashboard</span>
</header>
"""


def _nav() -> str:
    items = [
        ("Queue", "queue", "Q"),
        ("Work", "work", "W"),
        ("Trust", "trust", "T"),
        ("History", "history", "H"),
        ("Authority", "authority", "A"),
    ]
    links = "\n".join(
        f'<a href="#{anchor}" data-tab-link="{anchor}" data-nav="{anchor}">'
        f'<span class="nav-glyph" aria-hidden="true">{glyph}</span>'
        f'<span class="nav-text">{label}</span></a>'
        for label, anchor, glyph in items
    )
    return f'<nav class="rail" aria-label="Dashboard sections">\n<div class="rail-inner">{links}</div>\n</nav>'


def _attention_strip(workspace: Workspace, queue: list[Any], attention_counts: dict[str, int]) -> str:
    needs_human = attention_counts.get("needs-human-decision", 0)
    needs_review = attention_counts.get("needs-review", 0)
    needs_evidence = attention_counts.get("needs-evidence", 0)
    receipt_ready = attention_counts.get("receipt-ready", 0)
    closed = attention_counts.get("closed", 0)
    selected = len([source for source in workspace.sources if source.selected])
    external_writes = sum(1 for receipt in workspace.receipts if receipt.external_writes)
    top = queue[0] if queue else None
    top_command = top.next_commands[0] if top and top.next_commands else "palari queue --json"
    top_card = (
        f"""
    <article class="top-attention-card attention-{_class_token(top.attention)}">
      <div class="top-attention-head">
        <span class="mono">{_e(top.id)}</span>
        {_pill(top.attention, _attention_tone(top.attention))}
      </div>
      <h3>{_e(top.title)}</h3>
      <p class="top-step"><strong>Step</strong> {_e(top.next_step_type)}</p>
      <p>{_e(top.why)}</p>
      <code>{_e(top_command)}</code>
    </article>
"""
        if top
        else '<p class="none">No queue items need attention.</p>'
    )
    chips = "".join(
        _metric(label.replace("-", " "), value, _attention_tone(label), label)
        for label, value in (
            ("needs-human-decision", needs_human),
            ("needs-review", needs_review),
            ("needs-evidence", needs_evidence),
            ("receipt-ready", receipt_ready),
            ("closed", closed),
        )
        if value
    ) or '<span class="strip-empty">No active attention.</span>'
    return f"""
<section class="attention" aria-label="Current attention" data-tab-panel="queue">
  <div class="attn-left">
    <h1 class="attn-title">What needs attention now</h1>
    <div class="attn-counts">{chips}</div>
    <div class="attn-trustline">
      <span><strong>{selected}</strong> selected source(s)</span>
      <span><strong>{len(workspace.receipts)}</strong> receipt(s)</span>
      <span><strong>{external_writes}</strong> external write(s)</span>
    </div>
  </div>
  <div class="attn-right">
    <h2 class="attn-right-title">Top attention</h2>
    {top_card}
  </div>
</section>
"""


def _queue_section(workspace: Workspace, queue: list[Any], attention_counts: dict[str, int]) -> str:
    rows = "\n".join(_queue_card(item) for item in queue) or _empty("No work items in queue.")
    return f"""
<section class="panel" data-tab-panel="queue">
  <header class="panel-head">
    <div>
      <p class="eyebrow">Queue</p>
      <h2 class="panel-title">Prioritized work items</h2>
    </div>
    <p class="panel-note">Ordered by human decision, review, evidence, receipts, and closure.</p>
  </header>
  <div class="queue-list" data-queue>{rows}</div>
</section>
"""


def _queue_card(item: Any) -> str:
    return f"""
<details class="queue-item attention-{_class_token(item.attention)}" data-attention="{_e(item.attention)}">
  <summary class="queue-row">
    <span class="state-dot" aria-hidden="true"></span>
    <span class="queue-main">
      <span class="queue-title">{_e(item.title)}</span>
      <span class="queue-meta">{_e(item.goal_title)} · {_owner_label(item.owner)} · {_stage_flow(item)} · step {_e(item.next_step_type)}</span>
      <span class="queue-next">{_e(item.next_action)}</span>
    </span>
    <span class="queue-side">
      {_receipt_chip(item)}
      <span class="record-id mono">{_e(item.id)}</span>
    </span>
  </summary>
  <div class="queue-detail">
    <dl class="state-grid">
      {_state("Attention", item.attention)}
      {_state("Risk", f"{item.risk} / {item.intensity}")}
      {_state("Step", item.next_step_type)}
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
    {_command_list_block("Next commands", item.next_commands)}
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
<section class="lane lane-{_class_token(attention)}" data-lane="{_e(attention)}">
  <header class="lane-head">
    {_pill(attention, _attention_tone(attention))}
    <span class="lane-count mono">{len(grouped[attention])}</span>
  </header>
  {cards}
</section>
"""
        )
    return f"""
<section class="panel" data-tab-panel="work">
  <header class="panel-head">
    <div>
      <p class="eyebrow">Work</p>
      <h2 class="panel-title">Where work is in the flow</h2>
    </div>
    <p class="panel-note">{len(workspace.work_items)} work items grouped by current attention state.</p>
  </header>
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
    <span class="dc-title">
      <strong>{_e(work['title'])}</strong>
      <small><span class="mono">{_e(work['id'])}</span> · {_e(goal.get('title', work['goal']))}</small>
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
    <dl class="compact-dl">
      {_state("Step", payload.get("next_step_type", "inspect"))}
    </dl>
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
    {_command_list_block("Next commands", payload.get("next_commands", []))}
    {_agent_command_block(payload.get("agent_commands", {}))}
    <p class="next-action"><span class="na-label">Next</span>{_e(payload['next_action'])}</p>
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
<section class="panel trust-panel" data-tab-panel="trust">
  <header class="panel-head">
    <div>
      <p class="eyebrow">Trust</p>
      <h2 class="panel-title">What Palaris used, made, did not do, and can undo</h2>
    </div>
    <p class="panel-note">Receipts are human-facing trust evidence, separate from governance evidence.</p>
  </header>
  <div class="trust-grid">
    <section class="ledger">
      <header class="ledger-head">
        <h3>Selected sources</h3>
        <span class="ledger-count mono">{len(workspace.sources)}</span>
      </header>
      <div class="ledger-body">{sources}</div>
    </section>
    <section class="ledger ledger-receipts">
      <header class="ledger-head">
        <h3>Receipts</h3>
        <span class="ledger-count mono">{len(workspace.receipts)}</span>
      </header>
      <div class="ledger-body">{receipts}</div>
    </section>
  </div>
</section>
"""


def _source_card(source: Any) -> str:
    return f"""
<details class="ledger-row source-row">
  <summary>
    <span class="lr-title">
      <strong>{_e(source.label)}</strong>
      <small><span class="mono">{_e(source.id)}</span> · {_e(source.provider or 'unspecified')} · {_e(source.kind or 'unspecified')}</small>
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
    not_done = receipt.not_done or ["none"]
    undo_refs = receipt.undo_refs or ["none"]
    planned_writes = receipt.planned_external_writes or ["none"]
    return f"""
<details class="ledger-row receipt-card">
  <summary>
    <span class="lr-title">
      <strong>{_e(title)}</strong>
      <small><span class="mono">{_e(receipt.id)}</span> · attempt <span class="mono">{_e(receipt.attempt_id)}</span> · actor {_e(receipt.actor)}</small>
    </span>
    <span class="receipt-mark" aria-hidden="true">R</span>
  </summary>
  <div class="ledger-detail receipt-detail">
    <div class="receipt-trio">
      <div class="trio-cell trio-did">
        <h4>Used</h4>
        {_mini_list(receipt.sources_used, "sources")}
      </div>
      <div class="trio-cell trio-did">
        <h4>Did</h4>
        {_mini_list(receipt.actions_taken, "actions")}
      </div>
      <div class="trio-cell trio-did">
        <h4>Made</h4>
        {_mini_list(receipt.outputs_created, "outputs")}
      </div>
    </div>
    <div class="receipt-trio receipt-trio-2">
      <div class="trio-cell trio-writes">
        <h4>Planned external writes</h4>
        {_mini_list(planned_writes, "planned")}
      </div>
      <div class="trio-cell trio-writes">
        <h4>External writes</h4>
        {_mini_list(receipt.external_writes or ["none"], "writes")}
      </div>
      <div class="trio-cell trio-notdone">
        <h4>Not done</h4>
        {_mini_list(not_done, "none")}
      </div>
    </div>
    <div class="receipt-trio receipt-trio-2">
      <div class="trio-cell trio-undo">
        <h4>Undo refs</h4>
        {_mini_list(undo_refs, "none")}
      </div>
    </div>
  </div>
</details>
"""


def _history_section(history: dict[str, Any]) -> str:
    events = history.get("events") or []
    timeline = "\n".join(_history_event(event) for event in events) or _empty(
        "No history events recorded for this workspace."
    )
    return f"""
<section class="panel" data-tab-panel="history">
  <header class="panel-head">
    <div>
      <p class="eyebrow">History</p>
      <h2 class="panel-title">Append-only event timeline</h2>
    </div>
    <p class="panel-note">Source: <code>{_e(str(history.get('history_file', '')))}</code></p>
  </header>
  <div class="timeline">{timeline}</div>
</section>
"""


def _history_event(event: dict[str, Any]) -> str:
    changed = event.get("changed_fields") or {}
    changed_text = ", ".join(sorted(changed)) if isinstance(changed, dict) and changed else "none"
    return f"""
<article class="timeline-event">
  <div class="timeline-rail"><span class="timeline-dot"></span></div>
  <div class="timeline-body">
    <p class="timeline-meta"><span class="mono">{_e(str(event.get('timestamp', 'unknown time')))}</span> · {_e(str(event.get('actor', 'unknown actor')))}</p>
    <h3 class="timeline-title">{_e(str(event.get('action', 'event')))} {_e(str(event.get('object_type', 'object')))}/{_e(str(event.get('object_id', 'unknown')))}</h3>
    <p class="timeline-cmd"><code>{_e(str(event.get('command', '')))}</code></p>
    <p class="timeline-changed">Changed: {_e(changed_text)}</p>
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
    decision_guides = {
        decision.id: build_decision_guide(workspace, decision.id) for decision in open_decisions
    }
    decisions = "\n".join(
        _decision_card(decision, decision_guides.get(decision.id, {}))
        for decision in open_decisions
    ) or _empty("No open decisions.")
    blockers = "\n".join(_blocker_card(item) for item in human_blockers) or _empty(
        "No queue items are waiting on a human."
    )
    return f"""
<section class="panel" data-tab-panel="authority">
  <header class="panel-head">
    <div>
      <p class="eyebrow">Authority</p>
      <h2 class="panel-title">Who can decide, who owns the work, and what is blocked</h2>
    </div>
    <p class="panel-note">AI roles do not silently inherit human authority.</p>
  </header>
  <div class="authority-grid">
    <section class="auth-col">
      <h3>Humans</h3>
      <div class="auth-rows">{humans}</div>
    </section>
    <section class="auth-col">
      <h3>Palaris</h3>
      <div class="auth-rows">{palaris}</div>
    </section>
    <section class="auth-col">
      <h3>Open decisions</h3>
      <div class="auth-rows">{decisions}</div>
    </section>
    <section class="auth-col">
      <h3>Human blockers</h3>
      <div class="auth-rows">{blockers}</div>
    </section>
  </div>
</section>
"""


def _human_card(human: Any) -> str:
    return f"""
<article class="auth-row">
  <h4>{_e(human.name)}</h4>
  <p class="subtle">{_e(human.role or human.id)} · <span class="auth-level">{_e(human.authority_level)}</span></p>
  {_mini_list(human.approval_capabilities, "no approval capabilities")}
  <p class="auth-owns"><span>Owns</span> {_e(", ".join(human.ownership_areas) or "nothing")}</p>
</article>
"""


def _palari_card(palari: Any) -> str:
    return f"""
<article class="auth-row">
  <h4>{_e(palari.name)}</h4>
  <p class="subtle">{_e(palari.role)} · owner {_e(palari.owner_human or 'none')}</p>
  <p class="auth-scope">{_e(palari.scope)}</p>
  {_mini_list(palari.forbidden_actions, "no forbidden actions", "Forbidden")}
  <p class="auth-owns"><span>Active</span> {_e(", ".join(palari.active_work) or "none")}</p>
</article>
"""


def _decision_card(decision: Any, guide: dict[str, Any]) -> str:
    return f"""
<article class="auth-row auth-decision">
  <div class="card-title-row">
    <h4><span class="mono">{_e(decision.id)}</span></h4>
    {_pill(decision.status, "urgent" if decision.status == "open" else "neutral")}
  </div>
  <p class="auth-question">{_e(decision.question)}</p>
  <p class="subtle">Required: {_e(decision.required_human or decision.required_role or 'unspecified')}</p>
  {_command_list_block("Decision commands", _decision_commands(guide))}
</article>
"""


def _blocker_card(item: Any) -> str:
    return f"""
<article class="auth-row auth-blocker">
  <div class="card-title-row">
    <h4><span class="mono">{_e(item.id)}</span></h4>
    {_pill(item.attention, _attention_tone(item.attention))}
  </div>
  <p>{_e(item.title)}</p>
  <p class="next-action"><span class="na-label">Next</span>{_e(item.next_action)}</p>
</article>
"""


def _decision_commands(guide: dict[str, Any]) -> list[str]:
    if not guide:
        return []
    commands = [f"palari decision guide {guide['decision']['id']} --json"]
    suggested = guide.get("decision_update_commands", [])
    if suggested:
        commands.append(suggested[0]["command"])
    return commands


def _metric(label: str, value: int, tone: str, filter_value: str = "") -> str:
    data_filter = f' data-filter="{_e(filter_value)}"' if filter_value else ""
    return (
        f'<button class="chip chip-{tone}" type="button"{data_filter}>'
        f'<span class="chip-num mono">{_e(str(value))}</span><span class="chip-label">{_e(label)}</span></button>'
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


def _agent_command_block(commands: dict[str, str]) -> str:
    if not commands:
        return ""
    rows = "".join(
        f"<li><span>{_e(label)}</span><code>{_e(command)}</code></li>"
        for label, command in commands.items()
        if command
    )
    return f'<div class="agent-command-block"><strong>Agent loop</strong><ul>{rows}</ul></div>'


def _command_list_block(title: str, commands: list[str]) -> str:
    if not commands:
        return ""
    rows = "".join(
        f"<li><span>{index}</span><code>{_e(command)}</code></li>"
        for index, command in enumerate(commands, start=1)
    )
    return f'<div class="agent-command-block"><strong>{_e(title)}</strong><ul>{rows}</ul></div>'


def _mini_list(values: list[Any], empty_label: str, heading: str = "") -> str:
    if not values:
        return f'<p class="subtle mini-empty">{_e(empty_label)}</p>'
    items = "".join(f"<li>{_e(str(item))}</li>" for item in values)
    head = f'<p class="mini-head">{_e(heading)}</p>' if heading else ""
    return f'{head}<ul class="mini-list">{items}</ul>'


def _flow_step(label: str, value: str) -> str:
    tone = _state_tone(value)
    return f'<div class="flow-step flow-{tone}"><span class="flow-label">{_e(label)}</span><strong class="flow-value">{_e(value)}</strong></div>'


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
    return '<span class="stage-flow">' + '<span class="stage-sep" aria-hidden="true">/</span>'.join(rendered) + "</span>"


def _receipt_chip(item: Any) -> str:
    state = item.receipt_state
    tone = "trust" if state == "ready" else "warn" if state in {"missing", "stale", "failed"} else "neutral"
    return f'<span class="receipt-chip receipt-{tone}">Receipt: {_e(state)}</span>'


def _owner_label(owner: str) -> str:
    return _e(owner) if owner else "unassigned"


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
  --bg: #f6f8fa;
  --panel: #ffffff;
  --panel-2: #f1f5f9;
  --ink: #0f1d2d;
  --ink-2: #1c2b3d;
  --muted: #5b6b7e;
  --muted-2: #8593a3;
  --line: #dfe6ee;
  --line-2: #e7edf3;
  --line-strong: #c6d2de;
  --hot: #b3261e;
  --hot-bg: #fdecea;
  --hot-line: #f3b3ad;
  --urgent: #9a3324;
  --urgent-bg: #fbe9e3;
  --urgent-line: #e9b9a8;
  --warn: #8a5a00;
  --warn-bg: #fdf2d8;
  --warn-line: #e3c486;
  --trust: #0b6e5e;
  --trust-bg: #e3f4ef;
  --trust-line: #8fc9bb;
  --done: #4a5868;
  --done-bg: #eef2f6;
  --neutral: #1f4e79;
  --neutral-bg: #eaf1fb;
  --neutral-line: #b6cfe8;
  --calm: #1f4e79;
  --rail-bg: #fbfcfe;
  --shadow: 0 1px 2px rgba(15,29,45,.06), 0 1px 1px rgba(15,29,45,.04);
  --shadow-lg: 0 10px 30px rgba(15,29,45,.12);
  --radius: 10px;
  --radius-sm: 7px;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-family: var(--sans);
  font-size: 13.5px;
  line-height: 1.5;
  -webkit-text-size-adjust: 100%;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; overflow-x: hidden; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  overflow-x: hidden;
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; text-decoration: none; }
button { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; }
code {
  font-family: var(--mono);
  font-size: 0.86em;
  color: #2a3a50;
  background: #eef2f7;
  border: 1px solid var(--line);
  border-radius: 5px;
  padding: 0.04em 0.32em;
  white-space: nowrap;
  overflow-wrap: anywhere;
}
.mono { font-family: var(--mono); font-size: 0.84em; color: var(--muted); }
.subtle { color: var(--muted); }
h1, h2, h3, h4, p { margin: 0; }
h1 { font-size: 1.04rem; font-weight: 650; letter-spacing: -0.01em; }
h2 { font-size: 1.04rem; font-weight: 650; letter-spacing: -0.01em; }
h3 { font-size: 0.86rem; font-weight: 600; }
h4 { font-size: 0.82rem; font-weight: 600; }
strong { font-weight: 600; }

/* ---------- Topbar ---------- */
.topbar {
  position: sticky; top: 0; z-index: 40;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 0.75rem;
  min-height: 44px;
  padding: 0.35rem clamp(0.6rem, 2vw, 1rem);
  background: rgba(255,255,255,.92);
  border-bottom: 1px solid var(--line);
  backdrop-filter: saturate(160%) blur(10px);
}
.brand { display: inline-flex; align-items: center; gap: 0.5rem; min-width: 0; }
.brand-mark {
  display: inline-grid; place-items: center;
  width: 22px; height: 22px;
  border-radius: 6px;
  background: var(--ink); color: #fff;
  font-weight: 700; font-size: 0.74rem;
  flex: 0 0 22px;
}
.brand-name {
  font-weight: 650; font-size: 0.92rem; color: var(--ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  min-width: 0; max-width: min(40vw, 22rem);
}
.topbar-rail { display: inline-flex; align-items: center; gap: 0.35rem; min-width: 0; justify-self: start; }
.rail-chip {
  display: inline-flex; align-items: center; gap: 0.3rem;
  height: 26px; padding: 0 0.55rem;
  border: 1px solid var(--line); border-radius: 999px;
  background: var(--panel); color: var(--muted);
  font-size: 0.74rem; white-space: nowrap;
}
.rail-chip .rail-num { font-weight: 650; color: var(--ink); font-size: 0.8rem; }
.rail-chip .rail-label { color: var(--muted-2); }
.rail-chip:hover { border-color: var(--line-strong); }
.rail-hot { border-color: var(--hot-line); background: var(--hot-bg); }
.rail-hot .rail-num { color: var(--hot); }
.rail-hot .rail-label { color: var(--hot); }
.rail-calm { border-color: var(--neutral-line); background: var(--neutral-bg); }
.rail-calm .rail-num { color: var(--neutral); }
.rail-calm .rail-label { color: var(--neutral); }
.rail-mute { background: transparent; }
.rail-mute .rail-num { color: var(--done); }
.ro-badge {
  display: inline-flex; align-items: center;
  height: 26px; padding: 0 0.6rem;
  border: 1px solid var(--line); border-radius: 999px;
  background: var(--panel-2); color: var(--muted);
  font-size: 0.7rem; font-weight: 600; letter-spacing: 0.02em;
  white-space: nowrap;
}

/* ---------- App shell ---------- */
.app { display: grid; grid-template-columns: 168px minmax(0, 1fr); align-items: start; }
.content {
  min-width: 0;
  padding: 0.75rem clamp(0.7rem, 2vw, 1.2rem) 1rem;
  max-width: 1280px;
}

/* ---------- Left rail nav ---------- */
.rail {
  position: sticky; top: 44px; z-index: 30;
  align-self: start;
  height: calc(100vh - 44px);
  display: flex; flex-direction: column;
  padding: 0.5rem 0.6rem 0.4rem;
  background: var(--rail-bg);
  border-right: 1px solid var(--line);
}
.rail-inner { display: grid; gap: 0.15rem; }
.rail a {
  display: inline-flex; align-items: center; gap: 0.5rem;
  height: 30px; padding: 0 0.6rem;
  border-radius: 7px;
  color: var(--muted); font-size: 0.84rem; font-weight: 550;
  border: 1px solid transparent;
}
.rail a .nav-glyph {
  display: inline-grid; place-items: center;
  width: 18px; height: 18px;
  font-family: var(--mono); font-size: 0.72rem; font-weight: 600;
  color: var(--muted-2);
  border: 1px solid var(--line); border-radius: 5px;
  background: var(--panel);
}
.rail a .nav-text { min-width: 0; }
.rail a:hover { background: var(--panel); color: var(--ink); }
.rail a.is-active {
  background: var(--panel); color: var(--ink); border-color: var(--line);
  box-shadow: var(--shadow);
}
.rail a.is-active .nav-glyph { color: var(--trust); border-color: var(--trust-line); background: var(--trust-bg); }
.nav-top { margin-top: auto; }

/* ---------- Attention strip (first viewport) ---------- */
.attention {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 0.75rem;
  align-items: stretch;
  margin-bottom: 0.85rem;
  padding: 0.85rem 1rem 0.9rem;
  background: linear-gradient(180deg, #fff, var(--panel-2));
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.attn-left { min-width: 0; display: grid; align-content: start; gap: 0.6rem; }
.attn-title { font-size: 1.12rem; font-weight: 650; letter-spacing: -0.015em; color: var(--ink); }
.attn-counts { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.chip {
  display: inline-flex; align-items: center; gap: 0.4rem;
  height: 28px; padding: 0 0.6rem 0 0.4rem;
  border: 1px solid var(--line); border-radius: 999px;
  background: var(--panel); color: var(--ink);
  font-size: 0.78rem;
}
.chip:hover { border-color: var(--line-strong); }
.chip.is-active { box-shadow: 0 0 0 2px rgba(31,78,121,.18); }
.chip-num { font-weight: 650; font-size: 0.86rem; }
.chip-urgent { border-color: var(--urgent-line); background: var(--urgent-bg); }
.chip-urgent .chip-num { color: var(--urgent); }
.chip-warn { border-color: var(--warn-line); background: var(--warn-bg); }
.chip-warn .chip-num { color: var(--warn); }
.chip-trust { border-color: var(--trust-line); background: var(--trust-bg); }
.chip-trust .chip-num { color: var(--trust); }
.chip-done { border-color: var(--line); background: var(--done-bg); }
.chip-done .chip-num { color: var(--done); }
.strip-empty { color: var(--muted); font-size: 0.82rem; }
.attn-trustline {
  display: flex; flex-wrap: wrap; gap: 0.4rem 1.1rem;
  padding-top: 0.5rem; border-top: 1px dashed var(--line);
  font-size: 0.78rem; color: var(--muted);
}
.attn-trustline strong { color: var(--ink); font-weight: 650; margin-right: 0.18rem; }
.attn-right {
  min-width: 0;
  display: grid; align-content: start; gap: 0.35rem;
  padding: 0.75rem 0.85rem;
  border-left: 1px solid var(--line);
}
.attn-right-title { font-size: 0.76rem; font-weight: 650; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
.top-attention-card {
  min-width: 0;
  display: grid;
  gap: 0.28rem;
  padding: 0.48rem 0.55rem;
  border: 1px solid var(--line);
  border-left: 3px solid var(--neutral);
  border-radius: 6px;
  background: var(--panel);
}
.top-attention-card.attention-needs-human-decision { border-left-color: var(--urgent); }
.top-attention-card.attention-needs-review,
.top-attention-card.attention-needs-evidence,
.top-attention-card.attention-receipt-ready { border-left-color: var(--warn); }
.top-attention-card.attention-ready-for-ai-work { border-left-color: var(--trust); }
.top-attention-head {
  display: flex;
  gap: 0.4rem;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
}
.top-attention-head .mono { color: var(--muted); font-size: 0.72rem; }
.top-attention-card h3 {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.25;
  font-weight: 650;
  color: var(--ink);
}
.top-attention-card p {
  margin: 0;
  color: var(--ink-2);
  font-size: 0.78rem;
  line-height: 1.35;
}
.top-attention-card .top-step {
  color: var(--muted);
  font-size: 0.72rem;
}
.top-attention-card .top-step strong {
  color: var(--ink);
  font-weight: 650;
  margin-right: 0.2rem;
}
.top-attention-card code {
  display: block;
  min-width: 0;
  overflow-wrap: anywhere;
  padding-top: 0.3rem;
  border-top: 1px dashed var(--line);
  color: var(--ink);
}
/* ---------- Panels ---------- */
.panel {
  margin-bottom: 0.85rem;
  padding: 0.9rem 1rem 1rem;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  min-width: 0;
}
.panel-head {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;
  margin-bottom: 0.75rem; min-width: 0;
}
.panel-head > div { min-width: 0; }
.eyebrow {
  font-size: 0.68rem; font-weight: 650; color: var(--trust);
  letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.15rem;
}
.panel-title { font-size: 1.02rem; font-weight: 600; letter-spacing: -0.01em; }
.panel-note { color: var(--muted); font-size: 0.78rem; max-width: 22rem; text-align: right; min-width: 0; overflow-wrap: anywhere; }

/* ---------- Queue list ---------- */
.queue-list {
  border: 1px solid var(--line); border-radius: var(--radius-sm); overflow: hidden;
  background: var(--panel);
}
.queue-item { border-bottom: 1px solid var(--line-2); }
.queue-item:last-child { border-bottom: 0; }
.queue-item[open] { background: #fbfdff; }
.queue-row {
  display: grid; grid-template-columns: 4px minmax(0, 1fr) auto;
  gap: 0.7rem; align-items: center;
  min-height: 46px; padding: 0.5rem 0.7rem 0.5rem 0.55rem;
  cursor: pointer; list-style: none;
}
.queue-row::-webkit-details-marker { display: none; }
.queue-row::marker { display: none; }
.queue-row:hover { background: var(--panel-2); }
.state-dot { width: 7px; height: 7px; border-radius: 999px; background: var(--neutral); margin-left: 0.1rem; }
.attention-needs-human-decision .state-dot,
.attention-blocked .state-dot,
.attention-changes-requested .state-dot { background: var(--urgent); }
.attention-needs-review .state-dot,
.attention-needs-evidence .state-dot { background: var(--warn); }
.attention-receipt-ready .state-dot,
.attention-ready-to-integrate .state-dot { background: var(--trust); }
.attention-closed .state-dot { background: var(--done); }
.queue-main { display: grid; min-width: 0; gap: 0.08rem; }
.queue-title {
  font-weight: 600; color: var(--ink); font-size: 0.92rem;
  min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.queue-meta { color: var(--muted); font-size: 0.76rem; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.queue-next { color: #2c3e54; font-size: 0.78rem; font-weight: 500; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.queue-side { display: inline-flex; align-items: center; gap: 0.45rem; justify-self: end; min-width: 0; }
.record-id { font-size: 0.74rem; }
.receipt-chip {
  display: inline-flex; align-items: center; height: 22px; padding: 0 0.5rem;
  border: 1px solid var(--line); border-radius: 999px;
  font-size: 0.72rem; font-weight: 550; white-space: nowrap;
}
.receipt-trust { color: var(--trust); background: var(--trust-bg); border-color: var(--trust-line); }
.receipt-warn { color: var(--warn); background: var(--warn-bg); border-color: var(--warn-line); }
.receipt-neutral { color: var(--neutral); background: var(--neutral-bg); border-color: var(--neutral-line); }
.queue-detail { padding: 0.3rem 0.7rem 0.7rem 1.4rem; border-top: 1px solid var(--line-2); }
.stage-flow { display: inline-flex; flex-wrap: wrap; gap: 0.2rem; align-items: center; }
.stage { font-size: 0.72rem; font-weight: 550; color: var(--muted); }
.stage-trust { color: var(--trust); }
.stage-warn { color: var(--warn); }
.stage-neutral { color: var(--neutral); }
.stage-sep { color: var(--muted-2); }

/* left accent stripe by tone */
.queue-item.attention-needs-human-decision,
.queue-item.attention-blocked,
.queue-item.attention-changes-requested { box-shadow: inset 3px 0 0 var(--urgent); }
.queue-item.attention-needs-review,
.queue-item.attention-needs-evidence { box-shadow: inset 3px 0 0 var(--warn); }
.queue-item.attention-receipt-ready,
.queue-item.attention-ready-to-integrate { box-shadow: inset 3px 0 0 var(--trust); }
.queue-item.attention-closed { box-shadow: inset 3px 0 0 var(--done); }

.state-grid, .compact-dl {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.3rem 1rem;
  margin: 0.3rem 0 0;
}
dt { color: var(--muted); font-size: 0.72rem; font-weight: 500; }
dd { margin: 0; font-weight: 550; font-size: 0.82rem; overflow-wrap: anywhere; }

/* ---------- Work lanes ---------- */
.lane-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(19rem, 1fr)); gap: 0.7rem; align-items: start; }
.lane {
  display: grid; gap: 0.4rem;
  padding: 0.55rem 0.6rem 0.7rem;
  border: 1px solid var(--line); border-radius: var(--radius-sm);
  background: var(--panel-2);
  min-width: 0;
}
.lane-head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
.lane-count { font-size: 0.78rem; color: var(--muted); }
.detail-card {
  border: 1px solid var(--line); border-radius: var(--radius-sm);
  background: var(--panel); overflow: hidden;
}
.detail-card summary {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 0.7rem;
  padding: 0.55rem 0.7rem; cursor: pointer; list-style: none;
}
.detail-card summary::-webkit-details-marker { display: none; }
.dc-title { min-width: 0; }
.dc-title strong { display: block; font-size: 0.86rem; font-weight: 600; }
.dc-title small { display: block; color: var(--muted); font-size: 0.72rem; margin-top: 0.08rem; }
.detail-card[open] summary { border-bottom: 1px solid var(--line); }
.detail-body { padding: 0.55rem 0.7rem 0.7rem; }
.flow-row {
  display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0.3rem;
  margin: 0.5rem 0 0.55rem;
}
.flow-step {
  min-width: 0; padding: 0.4rem 0.45rem;
  border: 1px solid var(--line); border-radius: 6px; background: var(--panel-2);
  display: grid; gap: 0.1rem;
}
.flow-label { color: var(--muted); font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.04em; }
.flow-value { font-size: 0.76rem; font-weight: 600; overflow-wrap: anywhere; }
.flow-trust { border-color: var(--trust-line); background: var(--trust-bg); }
.flow-trust .flow-value { color: var(--trust); }
.flow-warn { border-color: var(--warn-line); background: var(--warn-bg); }
.flow-warn .flow-value { color: var(--warn); }
.flow-neutral { border-color: var(--line); }
.flow-neutral .flow-value { color: var(--ink-2); }
.detail-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.7rem; }
.kv { display: flex; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.25rem; font-size: 0.78rem; }
.kv span { color: var(--muted); }
.kv strong { text-align: right; overflow-wrap: anywhere; font-weight: 550; }
.list-block { margin-top: 0.4rem; }
.list-block strong { display: block; font-size: 0.74rem; color: var(--muted); font-weight: 600; margin-bottom: 0.1rem; }
.list-block ul { margin: 0; padding-left: 1rem; }
.list-block li { font-size: 0.78rem; margin-bottom: 0.08rem; overflow-wrap: anywhere; }
.agent-command-block {
  margin-top: 0.55rem; padding: 0.5rem 0.55rem;
  border: 1px solid var(--line); border-radius: 6px; background: var(--panel-2);
}
.agent-command-block strong {
  display: block; font-size: 0.72rem; color: var(--muted); font-weight: 650;
  margin-bottom: 0.3rem; text-transform: uppercase; letter-spacing: 0.04em;
}
.agent-command-block ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 0.24rem; }
.agent-command-block li { display: grid; grid-template-columns: 3.8rem minmax(0, 1fr); gap: 0.4rem; align-items: baseline; }
.agent-command-block li span { color: var(--muted); font-size: 0.72rem; font-weight: 600; }
.agent-command-block code { font-size: 0.72rem; overflow-wrap: anywhere; }
.next-action {
  margin: 0.5rem 0 0; padding: 0.4rem 0.55rem;
  border: 1px solid var(--line); border-radius: 6px; background: #fffdf6;
  font-size: 0.82rem; font-weight: 500; color: var(--ink-2);
  display: flex; gap: 0.5rem; align-items: baseline;
}
.na-label {
  flex: 0 0 auto; font-size: 0.64rem; font-weight: 650; color: var(--warn);
  text-transform: uppercase; letter-spacing: 0.06em;
  border: 1px solid var(--warn-line); background: var(--warn-bg);
  padding: 0.06rem 0.3rem; border-radius: 4px;
}

/* ---------- Trust ledger ---------- */
.trust-panel { background: #fbfcfe; }
.trust-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.7rem; }
.ledger {
  min-width: 0; display: grid; align-content: start;
  border: 1px solid var(--line); border-radius: var(--radius-sm);
  background: var(--panel); overflow: hidden;
}
.ledger-receipts { border-color: var(--trust-line); }
.ledger-head {
  display: flex; justify-content: space-between; align-items: baseline; gap: 0.7rem;
  padding: 0.55rem 0.8rem; border-bottom: 1px solid var(--line);
  background: var(--panel-2);
}
.ledger-receipts .ledger-head { background: var(--trust-bg); }
.ledger-receipts .ledger-head h3 { color: var(--trust); }
.ledger-head h3 { font-size: 0.84rem; font-weight: 650; }
.ledger-count { font-size: 0.74rem; color: var(--muted); }
.ledger-body { display: grid; min-width: 0; }
.ledger-row { border-bottom: 1px solid var(--line-2); }
.ledger-row:last-child { border-bottom: 0; }
.ledger-row[open] { background: var(--panel-2); }
.ledger-row summary {
  display: flex; justify-content: space-between; align-items: center; gap: 0.6rem;
  min-height: 42px; padding: 0.45rem 0.8rem; cursor: pointer; list-style: none;
}
.ledger-row summary::-webkit-details-marker { display: none; }
.lr-title { min-width: 0; }
.lr-title strong { display: block; font-size: 0.84rem; font-weight: 600; }
.lr-title small { display: block; color: var(--muted); font-size: 0.7rem; margin-top: 0.06rem; }
.receipt-mark {
  display: inline-grid; place-items: center;
  width: 20px; height: 20px; border-radius: 5px;
  background: var(--trust); color: #fff; font-weight: 700; font-size: 0.7rem;
  font-family: var(--mono);
}
.ledger-detail { padding: 0.4rem 0.8rem 0.7rem 1.6rem; border-top: 1px solid var(--line-2); border-left: 3px solid var(--trust-bg); }
.receipt-detail { display: grid; gap: 0.5rem; }
.receipt-trio { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.45rem; }
.receipt-trio-2 { margin-top: 0; }
.trio-cell {
  min-width: 0; padding: 0.4rem 0.55rem;
  border: 1px solid var(--line); border-radius: 6px; background: var(--panel);
  display: grid; align-content: start; gap: 0.2rem;
}
.trio-cell h4 { font-size: 0.7rem; font-weight: 650; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
.trio-writes { border-color: var(--warn-line); background: var(--warn-bg); }
.trio-writes h4 { color: var(--warn); }
.trio-notdone { border-color: var(--line); }
.trio-undo { border-color: var(--neutral-line); background: var(--neutral-bg); }
.trio-undo h4 { color: var(--neutral); }
.mini-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.12rem; }
.mini-list li { font-size: 0.76rem; overflow-wrap: anywhere; padding-left: 0.7rem; position: relative; }
.mini-list li::before { content: ""; position: absolute; left: 0.1rem; top: 0.5rem; width: 4px; height: 4px; border-radius: 999px; background: var(--muted-2); }
.mini-empty { font-size: 0.76rem; margin: 0; }
.mini-head { font-size: 0.7rem; font-weight: 650; color: var(--muted); margin: 0 0 0.1rem; }

/* ---------- History ---------- */
.timeline { display: grid; gap: 0.4rem; }
.timeline-event {
  display: grid; grid-template-columns: 1.4rem minmax(0, 1fr); gap: 0.55rem;
  padding: 0.5rem 0.4rem 0.5rem 0.2rem;
  border-bottom: 1px solid var(--line-2);
}
.timeline-event:last-child { border-bottom: 0; }
.timeline-rail { position: relative; }
.timeline-dot {
  position: absolute; top: 0.4rem; left: 0.35rem;
  width: 8px; height: 8px; border-radius: 999px;
  background: var(--trust); box-shadow: 0 0 0 3px var(--trust-bg);
}
.timeline-body { min-width: 0; }
.timeline-meta { font-size: 0.72rem; color: var(--muted); margin-bottom: 0.1rem; }
.timeline-title { font-size: 0.84rem; font-weight: 600; }
.timeline-cmd { margin: 0.15rem 0 0.1rem; }
.timeline-cmd code { font-size: 0.76rem; }
.timeline-changed {
  margin: 0;
  color: var(--muted);
  font-size: 0.72rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

/* ---------- Authority ---------- */
.authority-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.7rem; }
.auth-col { min-width: 0; display: grid; align-content: start; gap: 0.4rem; }
.auth-col > h3 {
  font-size: 0.74rem; font-weight: 650; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.06em;
  padding-bottom: 0.3rem; border-bottom: 1px solid var(--line);
}
.auth-rows { display: grid; gap: 0.4rem; }
.auth-row {
  padding: 0.5rem 0.6rem; border: 1px solid var(--line); border-radius: 7px; background: var(--panel-2);
}
.auth-row h4 { font-size: 0.84rem; font-weight: 600; margin-bottom: 0.1rem; }
.auth-row .subtle { font-size: 0.74rem; }
.auth-level { font-family: var(--mono); font-size: 0.86em; color: var(--neutral); }
.auth-scope { font-size: 0.78rem; margin: 0.2rem 0 0.3rem; color: var(--ink-2); }
.auth-owns { font-size: 0.74rem; color: var(--muted); margin-top: 0.25rem; }
.auth-owns span { color: var(--muted-2); }
.auth-question { font-size: 0.84rem; margin: 0.2rem 0 0.1rem; }
.card-title-row { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.auth-blocker { border-color: var(--urgent-line); background: var(--urgent-bg); }
.auth-decision { border-color: var(--urgent-line); }
.pill {
  display: inline-flex; align-items: center; height: 20px; padding: 0 0.5rem;
  border: 1px solid var(--line); border-radius: 999px;
  font-size: 0.7rem; font-weight: 550; text-transform: capitalize; white-space: nowrap;
}
.pill-urgent { color: var(--urgent); background: var(--urgent-bg); border-color: var(--urgent-line); }
.pill-warn { color: var(--warn); background: var(--warn-bg); border-color: var(--warn-line); }
.pill-trust { color: var(--trust); background: var(--trust-bg); border-color: var(--trust-line); }
.pill-done { color: var(--done); background: var(--done-bg); border-color: var(--line); }
.pill-neutral { color: var(--neutral); background: var(--neutral-bg); border-color: var(--neutral-line); }

/* ---------- Empty / provenance ---------- */
.empty-state {
  padding: 0.6rem 0.8rem; color: var(--muted); font-size: 0.8rem;
  border: 1px dashed var(--line); border-radius: 7px; background: var(--panel-2);
}
.provenance {
  padding: 0.6rem 0 0.8rem; color: var(--muted); font-size: 0.74rem;
  border-top: 1px solid var(--line); margin-top: 0.5rem;
}
.provenance details { padding-top: 0.3rem; }
.provenance summary { cursor: pointer; font-weight: 550; }
.provenance p { margin-top: 0.2rem; }

.is-filtered-out { display: none; }
[hidden] { display: none !important; }

/* ---------- Responsive ---------- */
@media (max-width: 900px) {
  .app { grid-template-columns: 1fr; }
  .content { padding: 0.55rem 0.7rem calc(4.5rem + env(safe-area-inset-bottom)); max-width: 100%; }
  .rail {
    position: fixed; top: auto; left: 0; right: 0; bottom: 0;
    z-index: 50; height: auto;
    flex-direction: row; align-items: center;
    padding: 0.3rem 0.4rem calc(0.3rem + env(safe-area-inset-bottom));
    background: rgba(255,255,255,.96);
    border-right: 0; border-top: 1px solid var(--line);
    box-shadow: 0 -6px 20px rgba(15,29,45,.08);
    overflow-x: auto;
  }
  .rail-inner { display: contents; }
  .rail a { flex: 1 1 0; min-width: 0; height: 38px; justify-content: center; gap: 0.25rem; padding: 0 0.2rem; }
  .rail a .nav-text { font-size: 0.7rem; }
  .rail a .nav-glyph { width: 16px; height: 16px; font-size: 0.66rem; }
  .nav-top { display: none; }
  .attention { grid-template-columns: 1fr; padding: 0.6rem 0.75rem; gap: 0.55rem; }
  .attn-right { border-left: 0; border-top: 1px solid var(--line); padding-top: 0.5rem; padding-left: 0; }
  .attn-right-title { margin-bottom: 0; }
  .trust-grid, .authority-grid { grid-template-columns: 1fr; }
  .lane-grid { grid-template-columns: 1fr; }
  .detail-columns { grid-template-columns: 1fr; }
  .flow-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .receipt-trio { grid-template-columns: 1fr; }
  .panel-head { flex-wrap: wrap; }
  .panel-note { text-align: left; max-width: 100%; }
}
@media (max-width: 520px) {
  :root { font-size: 13px; }
  .topbar { grid-template-columns: auto 1fr; min-height: 40px; padding: 0.3rem 0.6rem; }
  .topbar-rail { order: 3; grid-column: 1 / -1; justify-self: stretch; overflow-x: auto; padding-bottom: 0.2rem; }
  .ro-badge { display: none; }
  .brand-name { max-width: 70vw; }
  .rail-chip { flex: 0 0 auto; }
  .attention { padding: 0.6rem 0.7rem; }
  .attn-title { font-size: 1rem; }
  .panel { padding: 0.7rem 0.75rem 0.8rem; }
  .panel-title { font-size: 0.92rem; }
  .queue-row { min-height: 50px; padding: 0.45rem 0.55rem; grid-template-columns: 4px minmax(0, 1fr); }
  .queue-side { grid-column: 2; justify-self: start; flex-wrap: wrap; gap: 0.3rem; }
  .queue-meta, .queue-next { white-space: normal; }
  .state-grid, .compact-dl { grid-template-columns: 1fr; }
  .flow-row { grid-template-columns: 1fr; }
  .detail-columns { grid-template-columns: 1fr; }
  .receipt-trio { grid-template-columns: 1fr; }
  .timeline-event { grid-template-columns: 1.4rem minmax(0, 1fr); }
  .rail a .nav-text { font-size: 0.66rem; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  * { transition: none !important; animation: none !important; }
}

/* ---------- Tooling-native visual pass ---------- */
:root {
  --bg: #f6f8fa;
  --panel: #ffffff;
  --panel-2: #f6f8fa;
  --ink: #1f2328;
  --ink-2: #24292f;
  --muted: #57606a;
  --muted-2: #6e7781;
  --line: #d0d7de;
  --line-2: #d8dee4;
  --line-strong: #8c959f;
  --hot: #cf222e;
  --hot-bg: #fff8f8;
  --hot-line: #cf222e;
  --urgent: #cf222e;
  --urgent-bg: #fff8f8;
  --urgent-line: #cf222e;
  --warn: #9a6700;
  --warn-bg: #fff8c5;
  --warn-line: #bf8700;
  --trust: #116329;
  --trust-bg: #dafbe1;
  --trust-line: #2da44e;
  --done: #57606a;
  --done-bg: #f6f8fa;
  --neutral: #0969da;
  --neutral-bg: #ddf4ff;
  --neutral-line: #0969da;
  --calm: #0969da;
  --rail-bg: #f6f8fa;
  --shadow: none;
  --shadow-lg: none;
  --radius: 3px;
  --radius-sm: 2px;
  font-size: 13px;
}

body {
  background:
    linear-gradient(90deg, rgba(208,215,222,.65) 0, rgba(208,215,222,.65) 1px, transparent 1px, transparent 100%)
    0 0 / 168px 100% no-repeat,
    var(--bg);
}

code {
  border-radius: 2px;
  background: #f6f8fa;
  color: #24292f;
}

.topbar {
  min-height: 34px;
  padding: 0 0.65rem;
  gap: 0.5rem;
  background: #ffffff;
  border-bottom: 1px solid var(--line);
  backdrop-filter: none;
}

.brand-mark {
  width: 20px;
  height: 20px;
  flex-basis: 20px;
  border-radius: 2px;
  background: #24292f;
}

.brand-name {
  font-size: 0.84rem;
  font-weight: 650;
}

.topbar-rail {
  gap: 0;
  border-left: 1px solid var(--line);
}

.rail-chip,
.ro-badge,
.chip,
.receipt-chip,
.pill {
  border-radius: 2px;
  background: #fff;
  box-shadow: none;
}

.rail-chip {
  height: 24px;
  border-color: transparent;
  border-right: 1px solid var(--line);
}

.rail-chip:hover {
  background: #f6f8fa;
}

.rail-hot,
.rail-calm,
.rail-mute {
  background: transparent;
}

.ro-badge {
  height: 22px;
  background: #f6f8fa;
  color: var(--muted);
}

.app {
  grid-template-columns: 154px minmax(0, 1fr);
}

.content {
  max-width: none;
  padding: 0.65rem 0.85rem 1rem;
}

.rail {
  top: 34px;
  height: calc(100vh - 34px);
  padding: 0.45rem 0;
  background: #f6f8fa;
}

.rail-inner {
  gap: 0;
}

.rail a {
  width: 100%;
  height: 28px;
  padding: 0 0.75rem;
  border: 0;
  border-left: 3px solid transparent;
  border-radius: 0;
  font-size: 0.82rem;
}

.rail a .nav-glyph {
  width: 18px;
  height: 18px;
  border-radius: 2px;
  background: #ffffff;
}

.rail a:hover {
  background: #ffffff;
}

.rail a.is-active {
  background: #ffffff;
  border-left-color: var(--neutral);
  box-shadow: none;
}

.rail a.is-active .nav-glyph {
  color: var(--neutral);
  border-color: var(--neutral);
  background: #ffffff;
}

.attention,
.panel,
.lane,
.detail-card,
.ledger,
.auth-row,
.trio-cell,
.flow-step,
.empty-state,
.next-action {
  border-radius: 3px;
  box-shadow: none;
}

.attention {
  background: #ffffff;
  padding: 0.7rem 0.85rem;
}

.attn-title {
  font-size: 1rem;
  font-weight: 650;
}

.chip {
  height: 24px;
  padding: 0 0.45rem;
}

.chip-urgent,
.chip-warn,
.chip-trust,
.chip-done,
.pill-urgent,
.pill-warn,
.pill-trust,
.pill-done,
.receipt-trust,
.receipt-warn,
.receipt-neutral {
  background: #ffffff;
}

.chip-urgent,
.pill-urgent {
  color: var(--urgent);
  border-color: var(--urgent-line);
}

.chip-warn,
.pill-warn {
  color: var(--warn);
  border-color: var(--warn-line);
}

.chip-trust,
.pill-trust {
  color: var(--trust);
  border-color: var(--trust-line);
}

.chip-done,
.pill-done {
  color: var(--done);
  border-color: var(--line);
}

.attn-right {
  padding: 0.55rem 0.75rem;
}

.panel {
  padding: 0.75rem 0.85rem 0.85rem;
}

.panel-head {
  margin-bottom: 0.55rem;
}

.eyebrow {
  color: var(--muted);
  letter-spacing: 0.06em;
}

.queue-list,
.ledger {
  border-radius: 3px;
}

.queue-row {
  min-height: 42px;
  padding-block: 0.42rem;
}

.queue-row:hover,
.queue-item[open] .queue-row,
.ledger-row[open],
.ledger-row summary:hover,
.detail-card summary:hover {
  background: #f6f8fa;
}

.state-dot {
  border-radius: 2px;
}

.queue-item.attention-needs-human-decision,
.queue-item.attention-blocked,
.queue-item.attention-changes-requested,
.queue-item.attention-needs-review,
.queue-item.attention-needs-evidence,
.queue-item.attention-receipt-ready,
.queue-item.attention-ready-to-integrate,
.queue-item.attention-closed {
  box-shadow: none;
}

.queue-item.attention-needs-human-decision .queue-row,
.queue-item.attention-blocked .queue-row,
.queue-item.attention-changes-requested .queue-row {
  border-left: 3px solid var(--urgent);
}

.queue-item.attention-needs-review .queue-row,
.queue-item.attention-needs-evidence .queue-row {
  border-left: 3px solid var(--warn);
}

.queue-item.attention-receipt-ready .queue-row,
.queue-item.attention-ready-to-integrate .queue-row {
  border-left: 3px solid var(--trust);
}

.queue-item.attention-closed .queue-row {
  border-left: 3px solid var(--done);
}

.receipt-chip {
  height: 20px;
  padding-inline: 0.4rem;
}

.lane {
  background: #f6f8fa;
}

.detail-card {
  background: #ffffff;
}

.ledger-head {
  background: #f6f8fa;
}

.ledger-receipts .ledger-head {
  background: #f6f8fa;
  border-bottom-color: var(--trust-line);
}

.receipt-mark {
  border-radius: 2px;
}

.ledger-detail {
  border-left-color: var(--neutral);
}

.trio-writes,
.trio-undo {
  background: #ffffff;
}

.auth-row {
  background: #ffffff;
}

.auth-blocker {
  background: #fff8f8;
}

.provenance {
  margin-left: 154px;
  padding-inline: 0.85rem;
}

.section-nav a:focus-visible,
.rail a:focus-visible,
.metric:focus-visible,
.chip:focus-visible,
.queue-row:focus-visible,
.ledger-row summary:focus-visible,
.detail-card summary:focus-visible,
.provenance summary:focus-visible,
.topbar-rail a:focus-visible {
  outline: 2px solid var(--neutral);
  outline-offset: -2px;
}

@media (max-width: 900px) {
  body { background: var(--bg); }
  .app { grid-template-columns: 1fr; }
  .content { padding-inline: 0.5rem; }
  .rail {
    top: auto;
    height: auto;
    padding: 0;
    background: #ffffff;
  }
  .rail a {
    border-left: 0;
    border-top: 2px solid transparent;
    border-radius: 0;
    height: 42px;
  }
  .rail a.is-active {
    border-top-color: var(--neutral);
  }
  .attention,
  .panel {
    border-radius: 3px;
  }
  .provenance {
    margin-left: 0;
  }
}

@media (max-width: 520px) {
  .topbar {
    min-height: 36px;
  }
  .topbar-rail {
    border-left: 0;
  }
  .rail-chip {
    border: 1px solid var(--line);
  }
  .queue-row {
    grid-template-columns: 3px minmax(0, 1fr);
  }
}
"""


def _script() -> str:
    return """
(function () {
  const links = Array.from(document.querySelectorAll('[data-tab-link]'));
  const panels = Array.from(document.querySelectorAll('[data-tab-panel]'));
  const validTabs = new Set(links.map((link) => link.getAttribute('data-tab-link')));
  let activeTab = 'queue';

  function currentHashTab() {
    const value = window.location.hash.replace(/^#/, '');
    return validTabs.has(value) ? value : 'queue';
  }

  function setActiveTab(tab, options) {
    if (!validTabs.has(tab)) tab = 'queue';
    activeTab = tab;
    for (const link of links) {
      const isActive = link.getAttribute('data-tab-link') === tab;
      link.classList.toggle('is-active', isActive);
      link.setAttribute('aria-current', isActive ? 'page' : 'false');
    }
    for (const panel of panels) {
      const isActive = panel.getAttribute('data-tab-panel') === tab;
      panel.hidden = !isActive;
      panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
    }
    if (!options || options.updateHash !== false) {
      const targetHash = '#' + tab;
      if (window.location.hash !== targetHash) {
        history.pushState(null, '', targetHash);
      }
    }
    if (options && options.scrollTop) {
      if (options.scrollTop === 'instant') {
        window.scrollTo(0, 0);
      } else {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }
  }

  for (const link of links) {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      setActiveTab(link.getAttribute('data-tab-link'), { scrollTop: true });
    });
  }

  for (const anchor of Array.from(document.querySelectorAll('a[href^="#"]'))) {
    const tab = anchor.getAttribute('href').replace(/^#/, '');
    if (!validTabs.has(tab) || anchor.hasAttribute('data-tab-link')) continue;
    anchor.addEventListener('click', (event) => {
      event.preventDefault();
      setActiveTab(tab, { scrollTop: true });
    });
  }

  const filters = Array.from(document.querySelectorAll('[data-filter]'));
  const queueItems = Array.from(document.querySelectorAll('.queue-item[data-attention]'));
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

  window.addEventListener('popstate', () => {
    setActiveTab(currentHashTab(), { updateHash: false, scrollTop: 'instant' });
  });
  setActiveTab(currentHashTab(), { updateHash: false });
  requestAnimationFrame(() => window.scrollTo(0, 0));
  setTimeout(() => window.scrollTo(0, 0), 0);
  setTimeout(() => window.scrollTo(0, 0), 80);
})();
"""
