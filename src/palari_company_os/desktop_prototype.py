from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
from typing import Any

from .desktop_prototype_assets import desktop_prototype_script, desktop_prototype_styles


@dataclass(frozen=True)
class DesktopPrototypeResult:
    title: str
    output_dir: str
    index_path: str
    assets: list[str]


REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_desktop_demo_fixture() -> Path:
    checkout_fixture = REPO_ROOT / "examples" / "desktop-demo" / "workspace.json"
    if checkout_fixture.exists():
        return checkout_fixture
    return Path(str(files("palari_company_os").joinpath("data/examples/desktop-demo/workspace.json")))


DEFAULT_DESKTOP_DEMO_FIXTURE = _default_desktop_demo_fixture()


def generate_desktop_prototype(
    output_dir: str | Path,
    fixture_path: str | Path | None = None,
    data: dict[str, Any] | None = None,
) -> DesktopPrototypeResult:
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    prototype_data = data if data is not None else load_desktop_demo_data(fixture_path)
    validate_desktop_app_data(prototype_data)
    prototype_data = _sanitized_desktop_app_data(prototype_data)

    style_path = output / "styles.css"
    script_path = output / "app.js"
    index_path = output / "index.html"
    style_path.write_text(_styles(), encoding="utf-8")
    script_path.write_text(_script(prototype_data), encoding="utf-8")
    index_path.write_text(_html(prototype_data), encoding="utf-8")
    return DesktopPrototypeResult(
        title="Palari Desktop Shell Prototype",
        output_dir=str(output),
        index_path=str(index_path),
        assets=[str(style_path), str(script_path)],
    )


def load_desktop_demo_data(fixture_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(fixture_path) if fixture_path is not None else DEFAULT_DESKTOP_DEMO_FIXTURE
    with path.expanduser().resolve().open(encoding="utf-8") as handle:
        data = json.load(handle)
    validate_desktop_app_data(data)
    return data


def validate_desktop_app_data(data: dict[str, Any]) -> None:
    required_top_level = {
        "schema_version",
        "workspace",
        "selected_workbench_id",
        "workbenches",
        "humans",
        "palaris",
        "sources",
        "work_items",
        "ui",
    }
    missing = sorted(required_top_level - data.keys())
    if missing:
        raise ValueError(f"desktop app data missing required fields: {', '.join(missing)}")
    if data["schema_version"] != "desktop-app-data/v0":
        raise ValueError(f"unsupported desktop app data schema: {data['schema_version']}")

    humans = data["humans"]
    palaris = data["palaris"]
    sources = data["sources"]
    work_items = data["work_items"]
    selected_workbench_id = data["selected_workbench_id"]
    if selected_workbench_id not in data["workbenches"]:
        raise ValueError(f"selected workbench does not exist: {selected_workbench_id}")
    if data["workspace"]["owner_human_id"] not in humans:
        raise ValueError("workspace owner_human_id must reference a human")

    for palari_id, palari in palaris.items():
        if palari.get("id") != palari_id:
            raise ValueError(f"Palari id mismatch: {palari_id}")

    for human_id, human in humans.items():
        if human.get("id") != human_id:
            raise ValueError(f"human id mismatch: {human_id}")

    for workbench_id, workbench in data["workbenches"].items():
        if workbench.get("id") != workbench_id:
            raise ValueError(f"workbench id mismatch: {workbench_id}")
        if workbench["selected_palari_id"] not in palaris:
            raise ValueError(f"workbench selected_palari_id does not exist: {workbench_id}")
        for human_id in workbench["assigned_human_ids"]:
            if human_id not in humans:
                raise ValueError(f"workbench assigned_human_id does not exist: {human_id}")
        for group in workbench["source_groups"]:
            for source_id in group["source_ids"]:
                if source_id not in sources:
                    raise ValueError(f"source group references missing source: {source_id}")
        for work_item_id in workbench["work_item_ids"]:
            if work_item_id not in work_items:
                raise ValueError(f"workbench references missing work item: {work_item_id}")

    for source_id, source in sources.items():
        if source.get("id") != source_id:
            raise ValueError(f"source id mismatch: {source_id}")
        owner_human_id = source.get("owner_human_id")
        if owner_human_id is not None and owner_human_id not in humans:
            raise ValueError(f"source owner_human_id does not exist: {source_id}")
        for palari_id in source["allowed_palari_ids"]:
            if palari_id not in palaris:
                raise ValueError(f"source allowed_palari_id does not exist: {palari_id}")

    for work_item_id, work_item in work_items.items():
        if work_item.get("id") != work_item_id:
            raise ValueError(f"work item id mismatch: {work_item_id}")
        if work_item["palari_id"] not in palaris:
            raise ValueError(f"work item palari_id does not exist: {work_item_id}")
        for source_id in work_item["allowed_source_ids"]:
            if source_id not in sources:
                raise ValueError(f"work item allowed_source_id does not exist: {source_id}")
        for source_id in work_item["output_target_ids"]:
            if source_id not in sources:
                raise ValueError(f"work item output_target_id does not exist: {source_id}")
        attempts = work_item["attempts"]
        current_attempt_id = work_item["current_attempt_id"]
        if current_attempt_id not in attempts:
            raise ValueError(f"work item current_attempt_id does not exist: {work_item_id}")
        for attempt_id, attempt in attempts.items():
            if attempt.get("id") != attempt_id:
                raise ValueError(f"attempt id mismatch: {attempt_id}")
            for source_id in attempt["sources_used"]:
                if source_id not in sources:
                    raise ValueError(f"attempt sources_used references missing source: {source_id}")
                if source_id not in work_item["allowed_source_ids"] and source_id not in work_item["output_target_ids"]:
                    raise ValueError(f"attempt uses source outside work item boundary: {source_id}")
            document_html = attempt.get("document_html")
            if not isinstance(document_html, str):
                raise ValueError(f"attempt document_html must be a string: {attempt_id}")
            _sanitize_document_html(document_html, reject_unsafe=True)
            for approval in attempt["authority"]["approvals"]:
                if approval["human_id"] not in humans:
                    raise ValueError(f"authority approval references missing human: {approval['human_id']}")
            for message in attempt["chat_messages"]:
                if message["speaker_kind"] == "human" and message["speaker_id"] not in humans:
                    raise ValueError(f"chat message references missing human: {message['speaker_id']}")
                if message["speaker_kind"] == "palari" and message["speaker_id"] not in palaris:
                    raise ValueError(f"chat message references missing Palari: {message['speaker_id']}")

    ui = data["ui"]
    if ui["default_source_id"] not in sources:
        raise ValueError("ui default_source_id must reference a source")
    if ui["default_work_item_id"] not in work_items:
        raise ValueError("ui default_work_item_id must reference a work item")


def _e(value: str) -> str:
    return escape(value, quote=True)


ALLOWED_DOCUMENT_TAGS = {
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
VOID_DOCUMENT_TAGS = {"br"}


class _DocumentHTMLSanitizer(HTMLParser):
    def __init__(self, reject_unsafe: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.reject_unsafe = reject_unsafe
        self.parts: list[str] = []
        self.unsafe_reasons: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized not in ALLOWED_DOCUMENT_TAGS:
            self._unsafe(f"unsupported tag <{normalized}>")
            return
        if attrs:
            self._unsafe(f"attributes are not allowed on <{normalized}>")
        self.parts.append(f"<{normalized}>")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in ALLOWED_DOCUMENT_TAGS and normalized not in VOID_DOCUMENT_TAGS:
            self.parts.append(f"</{normalized}>")
        elif normalized not in ALLOWED_DOCUMENT_TAGS:
            self._unsafe(f"unsupported tag </{normalized}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self._unsafe("comments are not allowed")

    def _unsafe(self, reason: str) -> None:
        self.unsafe_reasons.append(reason)


def _sanitize_document_html(value: str, reject_unsafe: bool = False) -> str:
    sanitizer = _DocumentHTMLSanitizer(reject_unsafe=reject_unsafe)
    sanitizer.feed(value)
    sanitizer.close()
    if reject_unsafe and sanitizer.unsafe_reasons:
        reasons = ", ".join(sanitizer.unsafe_reasons[:3])
        raise ValueError(f"attempt document_html contains unsafe markup: {reasons}")
    return "".join(sanitizer.parts)


def _sanitized_desktop_app_data(data: dict[str, Any]) -> dict[str, Any]:
    sanitized = deepcopy(data)
    for work_item in sanitized["work_items"].values():
        for attempt in work_item["attempts"].values():
            attempt["document_html"] = _sanitize_document_html(attempt["document_html"])
    return sanitized


def _html(data: dict[str, Any]) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Palari Desktop Shell Prototype</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body data-mobile-pane="artifact">
  <div class="prototype-shell">
    {_nav_rail(data)}
    <main class="workspace-console" aria-label="Palari Company OS workspace">
      {_workbench_panel(data)}
      {_artifact_panel(data)}
      {_context_panel(data)}
    </main>
    {_mobile_nav()}
  </div>
  <script src="app.js"></script>
</body>
</html>
"""


def _selected_workbench(data: dict[str, Any]) -> dict[str, Any]:
    return data["workbenches"][data["selected_workbench_id"]]


def _selected_work_item(data: dict[str, Any]) -> dict[str, Any]:
    return data["work_items"][data["ui"]["default_work_item_id"]]


def _current_attempt(work_item: dict[str, Any]) -> dict[str, Any]:
    return work_item["attempts"][work_item["current_attempt_id"]]


def _human_name(data: dict[str, Any], human_id: str | None, fallback: str = "") -> str:
    if human_id and human_id in data["humans"]:
        return str(data["humans"][human_id]["name"])
    return fallback


def _actor_name(data: dict[str, Any], kind: str, actor_id: str) -> str:
    if kind == "human":
        return str(data["humans"][actor_id]["name"])
    return str(data["palaris"][actor_id]["name"])


def _actor_avatar_class(data: dict[str, Any], kind: str, actor_id: str) -> str:
    if kind == "human":
        return str(data["humans"][actor_id]["avatar_class"])
    return "bot"


def _source_chip(data: dict[str, Any], source_id: str) -> str:
    source = data["sources"][source_id]
    return (
        f'<button class="used-source" type="button"><span class="file-icon {_e(source["tone"])}">'
        f'{_e(source["type_label"])}</span>{_e(source["title"])}</button>'
    )


def _nav_rail(data: dict[str, Any]) -> str:
    items = [
        ("queue", "Queue", "7"),
        ("workbench", "Workbenches", ""),
        ("trust", "Trust", ""),
        ("history", "History", ""),
        ("people", "People", ""),
        ("settings", "Settings", ""),
    ]
    rows = "\n".join(
        f"""      <button class="rail-item {'is-active' if key == 'workbench' else ''}" type="button" data-nav="{_e(key)}">
        <span class="rail-icon" aria-hidden="true">{_rail_icon(key)}</span>
        <span class="rail-label">{_e(label)}</span>
        {f'<span class="rail-count">{_e(count)}</span>' if count else ''}
      </button>"""
        for key, label, count in items
    )
    return f"""
  <aside class="nav-rail" aria-label="Primary navigation">
    <div class="brand-mark">
      <span class="brand-icon">P</span>
      <span><strong>Palari</strong><small>Company OS</small></span>
    </div>
    <nav class="rail-list">
{rows}
    </nav>
    <div class="founder-card">
      <span class="founder-avatar">AR</span>
      <span><strong>{_e(_human_name(data, data["workspace"]["owner_human_id"]))}</strong><small>Founder</small></span>
    </div>
  </aside>
"""


def _rail_icon(key: str) -> str:
    icons = {
        "queue": "Q",
        "workbench": "W",
        "trust": "T",
        "history": "H",
        "people": "P",
        "settings": "S",
    }
    return icons[key]


def _workbench_panel(data: dict[str, Any]) -> str:
    workbench = _selected_workbench(data)
    selected_palari = data["palaris"][workbench["selected_palari_id"]]
    assigned_rows = [_person_row(selected_palari["name"], selected_palari["role"], "Palari", "chip-blue", selected_palari["avatar_class"])]
    for human_id in workbench["assigned_human_ids"]:
        human = data["humans"][human_id]
        assigned_rows.append(_person_row(human["name"], human["role"], "Human", "chip-amber", human["avatar_class"]))
    source_groups = "\n".join(_source_group(data, group) for group in workbench["source_groups"])
    queue_tabs = "\n".join(
        f'<button class="queue-tab {"is-active" if tab["active"] else ""}" type="button">{_e(tab["label"])} <span>{_e(str(tab["count"]))}</span></button>'
        for tab in workbench["work_queue"]["tabs"]
    )
    queue_items = "\n".join(_queue_item(data, data["work_items"][work_item_id]) for work_item_id in workbench["work_item_ids"])
    default_source = data["sources"][data["ui"]["default_source_id"]]
    return f"""
  <section class="panel workbench-panel" data-pane="workbench">
    <header class="panel-header">
      <div>
        <h1>{_e(workbench["title"])}</h1>
      </div>
      <button class="ghost-button" type="button" aria-label="Workbench menu">...</button>
    </header>

    <section class="panel-section assigned-section">
      <h2>Assigned</h2>
      {"".join(assigned_rows)}
    </section>

    <section class="panel-section sources-section">
      <div class="section-title"><h2>Sources</h2></div>
      <div class="source-tree" role="tree" aria-label="Source permissions by folder">
        {source_groups}
      </div>
      <div class="source-preview" aria-live="polite">
        <div class="card-title-row">
          <h3>Source preview</h3>
          <span class="chip {_e(default_source["mode_class"])}" data-source-preview-mode>{_e(default_source["mode"])}</span>
        </div>
        <strong data-source-preview-title>{_e(default_source["title"])}</strong>
        <p data-source-preview-copy>{_e(default_source["summary"])}</p>
        <dl class="source-meta-list">
          <div><dt>Provider</dt><dd data-source-preview-provider>{_e(default_source["provider"])}</dd></div>
          <div><dt>Access</dt><dd data-source-preview-access>{_e(default_source["access"])}</dd></div>
          <div><dt>Owner</dt><dd data-source-preview-owner>{_e(_human_name(data, default_source.get("owner_human_id"), default_source["owner_label"]))}</dd></div>
          <div><dt>Last seen</dt><dd data-source-preview-seen>{_e(default_source["last_seen"])}</dd></div>
        </dl>
      </div>
    </section>

    <section class="panel-section work-queue">
      <div class="section-title">
        <h2>Work Queue</h2>
        <button class="small-button" type="button">+ New</button>
      </div>
      <div class="queue-tabs" role="tablist" aria-label="Work queue filters">
        {queue_tabs}
      </div>
      {queue_items}
      <button class="link-row" type="button">View all work items -></button>
    </section>
  </section>
"""


def _person_row(name: str, role: str, label: str, chip_class: str, avatar_class: str) -> str:
    return f"""
      <div class="person-row">
        <span class="person-avatar photo {_e(avatar_class)}"></span>
        <strong>{_e(name)}</strong>
        <span class="chip {_e(chip_class)}">{_e(label)}</span>
        <span class="person-role">{_e(role)}</span>
      </div>
"""


def _source_group(data: dict[str, Any], group: dict[str, Any]) -> str:
    source_rows = "\n".join(_source_row(data, source_id) for source_id in group["source_ids"])
    return f"""
        <div class="source-folder {_e(group["tone"])}" role="treeitem" aria-expanded="true">
          <button class="source-folder-row" type="button" data-source-toggle aria-expanded="true">
            <span class="tree-caret" aria-hidden="true">&gt;</span>
            <span class="dot {_e(group["tone"])}"></span>
            <strong>{_e(group["label"])}</strong>
            <span class="tree-count">{len(group["source_ids"])}</span>
          </button>
          <div class="source-children" role="group">
            {source_rows}
          </div>
        </div>
"""


def _source_row(data: dict[str, Any], source_id: str) -> str:
    source = data["sources"][source_id]
    selected = " is-selected" if source_id == data["ui"]["default_source_id"] else ""
    muted = " muted" if source.get("row_muted") else ""
    return f"""
            <button class="source-file-row{selected}{muted}" type="button" data-source-id="{_e(source_id)}">
              <span>{_e(source["title"])}</span>
              <span class="file-kind">{_e(source["type_label"])}</span>
            </button>
"""


def _queue_item(data: dict[str, Any], work_item: dict[str, Any]) -> str:
    attempt = _current_attempt(work_item)
    selected = " is-active" if work_item["id"] == data["ui"]["default_work_item_id"] else ""
    palari = data["palaris"][work_item["palari_id"]]
    return f"""
      <button class="queue-item{selected}" type="button" data-work-id="{_e(work_item["id"])}">
        <strong>{_e(work_item["title"])}</strong>
        <span>{_e(palari["name"])}</span>
        <span>{_e(work_item["due_short"])}</span>
        <span class="chip {_e(attempt["status_class"])}">{_e(attempt["status_label"])}</span>
      </button>
"""


def _artifact_panel(data: dict[str, Any]) -> str:
    work_item = _selected_work_item(data)
    attempt = _current_attempt(work_item)
    source_chips = "\n        ".join(_source_chip(data, source_id) for source_id in attempt["sources_used"])
    palari = data["palaris"][work_item["palari_id"]]
    return f"""
  <section class="panel artifact-panel" data-pane="artifact">
    <header class="artifact-header">
      <div>
        <h1 data-artifact-title>{_e(work_item["artifact_title"])}</h1>
        <div class="artifact-meta">
          <span>Work Item</span><strong data-artifact-id>{_e(work_item["public_id"])}</strong>
          <span>Attempt</span><strong data-artifact-attempt>{_e(attempt["number"])}</strong>
          <span>Status</span><span class="chip {_e(attempt["status_class"])}" data-artifact-status>{_e(attempt["status_label"])}</span>
        </div>
      </div>
      <div class="artifact-actions">
        <button class="icon-menu" type="button" aria-label="More actions">...</button>
        <button class="secondary-button" type="button" data-open-context="task" data-mobile-pane="context" data-context-card="task">Check-in</button>
      </div>
    </header>

    <div class="approval-banner">
      <span class="warning-icon" aria-hidden="true">!</span>
      <div>
        <strong>Approval required before external write</strong>
        <p data-approval-copy>{_e(work_item["approval_copy"])}</p>
      </div>
      <button class="approval-button" type="button" data-open-context="authority" data-mobile-pane="context" data-context-card="authority">Request Approval</button>
    </div>

    <section class="sources-used">
      <div class="source-chip-list" aria-label="Sources used" data-sources-used>
        <span>Sources used</span>
        {source_chips}
      </div>
      <button class="secondary-button" type="button">+ Add</button>
    </section>

    <article class="document-card" data-document-card>
      {_sanitize_document_html(str(attempt["document_html"]))}
    </article>

    <footer class="artifact-footer">
      <dl>
        <div><dt>Owner</dt><dd data-footer-owner>{_e(palari["name"])}</dd></div>
        <div><dt>Palari</dt><dd data-footer-palari>{_e(palari["role"])}</dd></div>
        <div><dt>Last updated</dt><dd data-footer-updated>{_e(attempt["updated_label"])}</dd></div>
        <div><dt>Word count</dt><dd data-footer-word-count>{_e(attempt["word_count"])}</dd></div>
        <div><dt>Language</dt><dd data-footer-language>{_e(attempt["language"])}</dd></div>
      </dl>
      <button class="notes-toggle" type="button">Notes for approvers and reviewers (internal) -></button>
    </footer>
  </section>
"""


def _context_panel(data: dict[str, Any]) -> str:
    work_item = _selected_work_item(data)
    attempt = _current_attempt(work_item)
    receipt = attempt["receipt"]
    authority = attempt["authority"]
    chat_messages = "\n".join(_chat_message(data, message) for message in attempt["chat_messages"])
    approvals = "\n".join(_approval_row(data, approval) for approval in authority["approvals"])
    if not approvals:
        approvals = '<p class="muted-line">No human approver is needed for this local safe step.</p>'
    history_items = "\n".join(_history_item(event) for event in attempt["history_events"])
    palari = data["palaris"][work_item["palari_id"]]
    history_count = len(attempt["history_events"])
    return f"""
  <aside class="context-column" data-pane="context">
    <section class="context-card chat-card" data-context-card="chat">
      <header class="context-header">
        <h2>{_e(palari["name"])} Chat</h2>
        <span class="online-dot"></span><span>Online</span>
        <button class="ghost-button" type="button" aria-label="Chat menu">...</button>
      </header>
      <div class="chat-thread" data-chat-thread>
        {chat_messages}
      </div>
      <div class="composer">
        <input aria-label="Message {_e(palari["name"])}" placeholder="Message {_e(palari["name"])}...">
        <button type="button" aria-label="Attach">+</button>
        <button type="button" aria-label="Send">Send</button>
      </div>
    </section>

    <section class="context-card" data-context-card="task">
      <div class="card-title-row"><h2>Active Task</h2><span class="chip {_e(attempt["status_class"])}" data-task-status>{_e(attempt["status_label"])}</span></div>
      <a class="task-link" href="#" data-open-context="task" data-task-title>{_e(work_item["title"])}</a>
      <dl class="compact-grid four">
        <div><dt>Due</dt><dd data-task-due>{_e(work_item["due_label"])}</dd></div>
        <div><dt>Priority</dt><dd><span class="chip {_e(work_item["priority_class"])}" data-task-priority>{_e(work_item["priority_label"])}</span></dd></div>
        <div><dt>Risk</dt><dd data-task-risk>{_e(work_item["risk_label"])}</dd></div>
        <div><dt>Work Item</dt><dd data-task-id>{_e(work_item["public_id"])}</dd></div>
      </dl>
    </section>

    <section class="context-card" data-context-card="receipt">
      <div class="card-title-row">
        <h2 data-receipt-title>Receipt (Attempt {_e(attempt["number"])})</h2>
        <span class="chip {_e(receipt["status_class"])}" data-receipt-status>{_e(receipt["status_label"])}</span>
      </div>
      <dl class="receipt-list">
        <div><dt>Used</dt><dd data-receipt-used>{_e(receipt["sources_used"])}</dd></div>
        <div><dt>Created</dt><dd data-receipt-created>{_e(receipt["created"])}</dd></div>
        <div><dt>External writes</dt><dd data-receipt-external>{_e(receipt["external_writes"])}</dd></div>
        <div><dt>Did not do</dt><dd data-receipt-not-done>{_e(receipt["not_done"])}</dd></div>
        <div><dt>Undo</dt><dd data-receipt-undo>{_e(receipt["undo"])}</dd></div>
      </dl>
      <button class="full-button" type="button" data-open-context="receipt">View full receipt -></button>
    </section>

    <section class="context-card" data-context-card="authority">
      <div class="card-title-row"><h2>Authority</h2></div>
      <p class="muted-line" data-authority-requirement>{_e(authority["requirement"])}</p>
      <div data-authority-list>
        {approvals}
      </div>
      <p class="muted-line" data-authority-summary>{_e(authority["summary"])}</p>
    </section>

    <section class="context-card" data-context-card="history">
      <div class="card-title-row"><h2>Changes &amp; History</h2></div>
      <p class="muted-line" data-history-count>{history_count} change{"s" if history_count != 1 else ""}</p>
      <ol class="history-list" data-history-list>
        {history_items}
      </ol>
      <button class="link-row" type="button" data-open-context="history">View full history -></button>
    </section>
  </aside>
"""


def _chat_message(data: dict[str, Any], message: dict[str, Any]) -> str:
    avatar_class = _actor_avatar_class(data, message["speaker_kind"], message["speaker_id"])
    marker = "M" if message["speaker_kind"] == "palari" else ""
    return f"""
        <div class="chat-message {_e(message["speaker_kind"])}">
          <span class="tiny-avatar {_e(avatar_class)}">{marker}</span>
          <div><strong>{_e(_actor_name(data, message["speaker_kind"], message["speaker_id"]))}</strong><time>{_e(message["time"])}</time>
          <p>{_e(message["text"])}</p></div>
        </div>
"""


def _approval_row(data: dict[str, Any], approval: dict[str, Any]) -> str:
    human = data["humans"][approval["human_id"]]
    return f"""
        <div class="approval-row">
          <span class="tiny-avatar {_e(human["avatar_class"])}"></span><strong>{_e(human["name"])}</strong><span>{_e(approval["role"])}</span><span class="chip {_e(approval["status_class"])}">{_e(approval["status_label"])}</span>
        </div>
"""


def _history_item(event: dict[str, Any]) -> str:
    return f'<li><time>{_e(event["time"])}</time><span>{_e(event["text"])}</span><span class="chip chip-gray">{_e(event["badge"])}</span></li>'


def _mobile_nav() -> str:
    items = [
        ("workbench", "Work"),
        ("artifact", "Draft"),
        ("chat", "Chat"),
        ("task", "Task"),
        ("receipt", "Receipt"),
        ("authority", "Auth"),
        ("history", "Hist"),
    ]
    buttons = "\n".join(
        f'<button class="mobile-tab {"is-active" if key == "artifact" else ""}" type="button" '
        f'data-mobile-target="{_e(key)}">{_e(label)}</button>'
        for key, label in items
    )
    return f'<nav class="mobile-nav" aria-label="Mobile workspace navigation">{buttons}</nav>'


def _styles() -> str:
    return desktop_prototype_styles()


def _script(data: dict[str, Any]) -> str:
    return desktop_prototype_script(_safe_json_for_script(data))


def _safe_json_for_script(data: dict[str, Any]) -> str:
    return (
        json.dumps(data, ensure_ascii=True, indent=2)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
