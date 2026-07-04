from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .dashboard_assets import dashboard_script, dashboard_styles
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
    top_handoff = top.agent_handoff_command if top else ""
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
      {_agent_handoff_inline(top_handoff)}
      {_command_inline(top_command)}
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
    {_agent_handoff_block(item.agent_handoff_command)}
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
    {_agent_handoff_block(payload.get("agent_handoff_command", ""))}
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
        _command_row(str(label), command)
        for label, command in commands.items()
        if command
    )
    return f'<div class="agent-command-block"><strong>Agent loop</strong><ul>{rows}</ul></div>'


def _agent_handoff_block(command: str) -> str:
    if not command:
        return ""
    return (
        '<div class="agent-command-block agent-handoff-block">'
        '<strong>Agent handoff</strong>'
        '<p class="agent-boundary">Agent-safe bridge. Human review and decision actions stay human-only.</p>'
        f'<ul>{_command_row("bridge", command)}</ul>'
        "</div>"
    )


def _agent_handoff_inline(command: str) -> str:
    if not command:
        return ""
    return (
        '<p class="top-handoff"><strong>Agent handoff</strong> '
        '<span>agent-safe bridge</span> '
        f'{_command_inline(command)}</p>'
    )


def _command_list_block(title: str, commands: list[str]) -> str:
    if not commands:
        return ""
    rows = "".join(
        _command_row(str(index), command)
        for index, command in enumerate(commands, start=1)
    )
    return f'<div class="agent-command-block"><strong>{_e(title)}</strong><ul>{rows}</ul></div>'


def _command_row(label: str, command: str) -> str:
    return (
        '<li class="command-row">'
        f'<span>{_e(label)}</span>'
        f'<code>{_e(command)}</code>'
        f'<button class="copy-command" type="button" data-copy-command="{_e(command)}" '
        f'aria-label="Copy command: {_e(command)}">Copy</button>'
        "</li>"
    )


def _command_inline(command: str) -> str:
    return (
        '<span class="command-inline">'
        f'<code>{_e(command)}</code>'
        f'<button class="copy-command" type="button" data-copy-command="{_e(command)}" '
        f'aria-label="Copy command: {_e(command)}">Copy</button>'
        "</span>"
    )


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
    return dashboard_styles()


def _script() -> str:
    return dashboard_script()
