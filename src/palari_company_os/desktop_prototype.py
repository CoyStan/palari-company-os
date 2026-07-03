from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
from typing import Any


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
    return """
:root {
  color-scheme: light;
  --bg: #f6f7fb;
  --panel: #ffffff;
  --panel-soft: #fafbfc;
  --ink: #111827;
  --ink-soft: #374151;
  --muted: #6b7280;
  --line: #e5e7eb;
  --line-strong: #d1d5db;
  --blue: #2563eb;
  --blue-bg: #eaf2ff;
  --green: #16a34a;
  --green-bg: #eafaf0;
  --amber: #b45309;
  --amber-bg: #fff7ed;
  --red: #dc2626;
  --red-bg: #fef2f2;
  --shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 13px;
}

* { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; }
body {
  background: var(--bg);
  color: var(--ink);
  overflow: hidden;
}
button, input { font: inherit; }
button { cursor: pointer; }
button:focus-visible, input:focus-visible {
  outline: 2px solid rgba(37, 99, 235, 0.35);
  outline-offset: 2px;
}

.prototype-shell {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr);
  height: 100vh;
  min-height: 0;
  gap: 8px;
  padding: 8px 8px 8px 0;
}

.nav-rail {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 16px 10px 14px;
  border-right: 1px solid var(--line);
  background: #fbfcfe;
}
.brand-mark {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 22px;
}
.brand-icon {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: 5px;
  color: var(--blue);
  font-weight: 800;
}
.brand-mark strong, .brand-mark small, .founder-card strong, .founder-card small {
  display: block;
}
.brand-mark strong { font-size: 13px; }
.brand-mark small, .founder-card small { color: var(--muted); font-size: 11px; }
.rail-list { display: grid; gap: 6px; }
.rail-item {
  min-height: 40px;
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) auto;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--ink-soft);
  text-align: left;
}
.rail-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}
.rail-item:hover, .rail-item.is-active {
  background: #eef0f4;
}
.rail-item.is-active {
  color: var(--ink);
  font-weight: 700;
}
.rail-icon {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  color: var(--muted);
}
.rail-count {
  min-width: 20px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #eef0f4;
  color: var(--muted);
  font-size: 11px;
  text-align: center;
}
.founder-card {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 6px;
}
.founder-avatar {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #59a779;
  color: white;
  font-size: 12px;
  font-weight: 800;
}

.workspace-console {
  display: grid;
  grid-template-columns: minmax(286px, 310px) minmax(560px, 1fr) minmax(300px, 340px);
  min-width: 0;
  min-height: 0;
  gap: 8px;
}
.panel, .context-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
}
.workbench-panel, .artifact-panel, .context-column {
  min-height: 0;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: #cfd6df transparent;
}
.workbench-panel::-webkit-scrollbar,
.artifact-panel::-webkit-scrollbar,
.context-column::-webkit-scrollbar {
  width: 8px;
}
.workbench-panel::-webkit-scrollbar-thumb,
.artifact-panel::-webkit-scrollbar-thumb,
.context-column::-webkit-scrollbar-thumb {
  background: #cfd6df;
  border-radius: 999px;
}
.workbench-panel, .artifact-panel {
  display: flex;
  flex-direction: column;
}
.panel-header, .artifact-header, .context-header, .card-title-row, .section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.panel-header {
  padding: 16px 16px 14px;
  border-bottom: 1px solid var(--line);
}
h1, h2, h3, p { margin: 0; }
.panel-header h1, .artifact-header h1 {
  font-size: 16px;
  line-height: 1.25;
  font-weight: 750;
  letter-spacing: -0.01em;
}
.panel-section {
  padding: 16px;
  border-bottom: 1px solid var(--line);
}
.panel-section:last-child { border-bottom: 0; }
.panel-section h2, .context-card h2 {
  font-size: 12px;
  font-weight: 750;
  color: var(--ink-soft);
}
.assigned-section {
  display: grid;
  gap: 12px;
}
.person-row {
  display: grid;
  grid-template-columns: 28px auto auto 1fr;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.person-row strong { font-size: 12px; white-space: nowrap; }
.person-role {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.person-avatar, .tiny-avatar {
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #dbeafe;
  color: var(--blue);
  font-weight: 800;
}
.person-avatar { width: 26px; height: 26px; }
.tiny-avatar { width: 24px; height: 24px; flex: 0 0 24px; font-size: 10px; }
.photo.maya, .tiny-avatar.bot { background: #e0f2fe; color: #0369a1; }
.photo.jordan, .tiny-avatar.jordan { background: #fef3c7; color: #92400e; }
.photo.sam, .tiny-avatar.sam { background: #fee2e2; color: #991b1b; }
.tiny-avatar.alex { background: #dcfce7; color: #166534; }

.chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  justify-self: start;
  min-height: 18px;
  padding: 1px 7px;
  border-radius: 5px;
  font-size: 11px;
  line-height: 1.3;
  font-weight: 700;
  white-space: nowrap;
}
.chip-blue { background: var(--blue-bg); color: var(--blue); }
.chip-green { background: var(--green-bg); color: var(--green); }
.chip-amber { background: var(--amber-bg); color: var(--amber); }
.chip-red { background: var(--red-bg); color: var(--red); }
.chip-gray { background: #f3f4f6; color: var(--ink-soft); }

.sources-section { display: grid; gap: 10px; }
.source-tree {
  display: grid;
  gap: 4px;
  font-size: 12px;
}
.source-folder {
  display: grid;
  gap: 2px;
}
.source-folder-row {
  display: grid;
  grid-template-columns: 12px 6px minmax(0, 1fr) auto;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-height: 28px;
  padding: 0 4px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--ink);
  text-align: left;
}
.source-folder-row:hover {
  background: var(--panel-soft);
}
.source-folder-row strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tree-caret {
  display: inline-grid;
  place-items: center;
  color: var(--muted);
  font-size: 10px;
  line-height: 1;
  transform: rotate(90deg);
  transform-origin: center;
  transition: transform 120ms ease;
}
.source-folder.is-collapsed .tree-caret {
  transform: rotate(0deg);
}
.tree-count {
  min-width: 18px;
  color: var(--ink-soft);
  font-weight: 750;
  text-align: right;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--muted);
}
.dot.inline { display: inline-block; margin: 0 3px; }
.dot.read { background: var(--green); }
.dot.inherit { background: var(--blue); }
.dot.write { background: #f59e0b; }
.dot.blocked { background: var(--red); }
.source-children {
  display: grid;
  gap: 1px;
  margin-left: 18px;
  padding-left: 9px;
  border-left: 1px solid var(--line);
}
.source-folder.is-collapsed .source-children {
  display: none;
}
.source-file-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 7px;
  width: 100%;
  min-height: 26px;
  padding: 0 4px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--ink-soft);
  text-align: left;
  font-size: 12px;
}
.source-file-row:hover { background: var(--panel-soft); }
.source-file-row.is-selected {
  background: var(--blue-bg);
  color: var(--ink);
}
.source-file-row.is-selected .file-kind {
  border-color: #bfdbfe;
  color: var(--blue);
}
.source-file-row span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-file-row.muted { color: var(--muted); }
.file-icon, .file-kind {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  color: var(--muted);
  background: #fff;
  font-size: 9px;
  line-height: 1;
  font-weight: 700;
  white-space: nowrap;
}
.file-icon {
  min-width: 24px;
  width: max-content;
  height: 20px;
  padding: 0 4px;
  flex: 0 0 auto;
}
.file-icon.green { color: var(--green); border-color: #bbf7d0; }
.file-icon.blue { color: var(--blue); border-color: #bfdbfe; }
.file-kind { min-width: 34px; padding: 1px 5px; }
.source-preview {
  display: grid;
  gap: 7px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--panel-soft);
}
.source-preview h3 {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.source-preview strong {
  color: var(--ink);
  font-size: 12px;
}
.source-preview p {
  color: var(--ink-soft);
  font-size: 12px;
  line-height: 1.35;
}
.source-meta-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 10px;
  margin: 2px 0 0;
}
.source-meta-list div {
  min-width: 0;
}
.source-meta-list dt {
  color: var(--muted);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.source-meta-list dd {
  margin: 2px 0 0;
  color: var(--ink-soft);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.work-queue { display: grid; gap: 12px; }
.queue-tabs {
  display: flex;
  gap: 16px;
  border-bottom: 1px solid var(--line);
}
.queue-tab {
  border: 0;
  background: transparent;
  padding: 0 0 10px;
  color: var(--muted);
  font-weight: 700;
}
.queue-tab.is-active {
  color: var(--ink);
  box-shadow: inset 0 -2px 0 var(--ink);
}
.queue-tab span {
  margin-left: 4px;
  color: var(--muted);
}
.queue-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 6px 10px;
  width: 100%;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-soft);
  text-align: left;
}
.queue-item strong {
  grid-column: 1 / -1;
  color: var(--ink);
  font-size: 12px;
}
.queue-item.is-active {
  border-color: #93c5fd;
  background: #f8fbff;
}
.link-row {
  justify-self: start;
  min-height: 28px;
  border: 0;
  background: transparent;
  color: var(--ink-soft);
  padding: 4px 0;
}
.small-button, .ghost-button, .secondary-button, .icon-menu, .approval-button, .full-button {
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--ink);
  border-radius: 6px;
}
.small-button { min-height: 30px; padding: 0 10px; }
.ghost-button, .icon-menu { width: 32px; height: 32px; }

.artifact-panel { padding: 0; }
.artifact-header {
  padding: 16px 20px 14px;
}
.artifact-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-top: 12px;
  color: var(--muted);
  font-size: 11px;
}
.artifact-meta strong {
  color: var(--ink-soft);
}
.artifact-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.secondary-button, .approval-button {
  min-height: 36px;
  padding: 0 14px;
  font-weight: 700;
  white-space: nowrap;
}
.approval-banner {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  margin: 6px 12px 18px;
  padding: 14px 16px;
  border: 1px solid #fed7aa;
  border-radius: 7px;
  background: var(--amber-bg);
  color: var(--amber);
}
.approval-banner p {
  margin-top: 6px;
  color: #9a3412;
}
.warning-icon {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border: 1px solid var(--amber);
  border-radius: 50%;
  font-weight: 800;
}
.approval-button { background: #fff; }

.sources-used {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: space-between;
  margin: 0 12px 20px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: #fff;
}
.source-chip-list {
  display: flex;
  align-items: center;
  min-width: 0;
  flex-wrap: wrap;
  gap: 8px;
}
.source-chip-list > span {
  width: 100%;
  color: var(--muted);
  font-size: 11px;
}
.used-source {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: 100%;
  min-height: 30px;
  padding: 0 9px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: #fff;
  white-space: nowrap;
}

.document-card {
  max-width: 690px;
  margin: 0 auto;
  padding: 10px 20px 28px;
  line-height: 1.55;
  font-size: 13px;
}
.document-card h2 {
  margin: 20px 0 10px;
  font-size: 15px;
  color: var(--ink);
}
.document-card p, .document-card li {
  color: var(--ink-soft);
}
.document-card ul, .document-card ol {
  padding-left: 20px;
  margin: 0;
}
.document-card li + li {
  margin-top: 6px;
}
.artifact-footer {
  margin: auto 12px 14px;
  display: grid;
  gap: 12px;
}
.artifact-footer dl {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 0;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: #fff;
}
.artifact-footer div {
  padding: 12px 14px;
  border-right: 1px solid var(--line);
}
.artifact-footer div:last-child { border-right: 0; }
.artifact-footer dt {
  color: var(--muted);
  font-size: 11px;
}
.artifact-footer dd {
  margin: 6px 0 0;
  color: var(--ink-soft);
}
.notes-toggle, .full-button {
  min-height: 34px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  color: var(--ink-soft);
}

.context-column {
  display: grid;
  grid-auto-rows: min-content;
  gap: 8px;
}
.context-card {
  padding: 12px;
}
.context-card.is-focused {
  border-color: #93c5fd;
  box-shadow: inset 3px 0 0 var(--blue), var(--shadow);
}
.context-header {
  margin-bottom: 10px;
}
.context-header h2, .context-card h2 {
  font-size: 13px;
  font-weight: 750;
}
.online-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--green);
  margin-left: auto;
}
.chat-thread {
  display: grid;
  gap: 10px;
}
.chat-message {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.chat-message strong {
  font-size: 12px;
}
.chat-message time {
  margin-left: 8px;
  color: var(--muted);
  font-size: 11px;
}
.chat-message p {
  margin-top: 4px;
  color: var(--ink-soft);
  line-height: 1.35;
}
.composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px 34px;
  align-items: center;
  gap: 6px;
  margin-top: 14px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 7px;
}
.composer input {
  min-width: 0;
  min-height: 28px;
  border: 0;
  outline: 0;
}
.composer button {
  min-height: 28px;
  border: 0;
  background: transparent;
  color: var(--muted);
}
.task-link {
  display: block;
  margin: 12px 0;
  min-height: 22px;
  line-height: 1.35;
  color: var(--blue);
  text-decoration: none;
  font-weight: 700;
}
.compact-grid {
  display: grid;
  gap: 8px;
  margin: 0;
}
.compact-grid.four {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.compact-grid dt, .receipt-list dt {
  color: var(--muted);
  font-size: 11px;
}
.compact-grid dd, .receipt-list dd {
  margin: 4px 0 0;
  color: var(--ink-soft);
}
.receipt-list {
  display: grid;
  gap: 6px;
  margin: 12px 0;
}
.receipt-list div {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr);
}
.muted-line {
  color: var(--muted);
  margin: 8px 0;
}
.approval-row {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) minmax(80px, 1fr) auto;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  color: var(--ink-soft);
}
.history-list {
  display: grid;
  gap: 8px;
  padding: 0;
  margin: 12px 0;
  list-style: none;
}
.history-list li {
  display: grid;
  grid-template-columns: 94px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  color: var(--ink-soft);
}
.history-list time {
  color: var(--muted);
}

.mobile-nav { display: none; }

@media (max-width: 1320px) {
  .prototype-shell {
    grid-template-columns: 150px minmax(0, 1fr);
  }
  .workspace-console {
    grid-template-columns: minmax(250px, 280px) minmax(430px, 1fr) minmax(260px, 300px);
  }
}

@media (max-width: 1100px) {
  body {
    overflow: hidden;
  }
  .prototype-shell {
    display: block;
    height: 100vh;
    padding: 0;
  }
  .nav-rail {
    height: 54px;
    flex-direction: row;
    align-items: center;
    padding: 8px 10px;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .brand-mark {
    padding: 0;
  }
  .brand-mark small,
  .rail-list,
  .founder-card {
    display: none;
  }
  .workspace-console {
    display: block;
    height: calc(100vh - 54px - 58px);
    padding: 8px;
    overflow: hidden;
  }
  .workbench-panel,
  .artifact-panel,
  .context-column {
    display: none;
    height: 100%;
    overflow: auto;
  }
  body[data-mobile-pane="workbench"] .workbench-panel,
  body[data-mobile-pane="artifact"] .artifact-panel,
  body[data-mobile-pane="context"] .context-column {
    display: flex;
  }
  body[data-mobile-pane="context"] .context-column {
    display: grid;
  }
  .artifact-panel {
    border-radius: 8px;
  }
  .artifact-header,
  .approval-banner,
  .sources-used {
    margin-inline: 0;
  }
  .approval-banner,
  .sources-used {
    grid-template-columns: 1fr;
  }
  .sources-used {
    flex-direction: column;
    align-items: stretch;
  }
  .source-chip-list {
    width: 100%;
  }
  .approval-button,
  .secondary-button {
    width: 100%;
  }
  .document-card {
    padding-inline: 14px;
  }
  .artifact-footer dl {
    grid-template-columns: 1fr;
  }
  .artifact-footer div {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .artifact-footer div:last-child {
    border-bottom: 0;
  }
  .context-card {
    display: none;
  }
  body[data-context-card="chat"] [data-context-card="chat"],
  body[data-context-card="task"] [data-context-card="task"],
  body[data-context-card="receipt"] [data-context-card="receipt"],
  body[data-context-card="authority"] [data-context-card="authority"],
  body[data-context-card="history"] [data-context-card="history"] {
    display: block;
  }
  .mobile-nav {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    height: 58px;
    border-top: 1px solid var(--line);
    background: #fff;
    z-index: 50;
  }
  .mobile-tab {
    border: 0;
    background: transparent;
    color: var(--muted);
    font-size: 10px;
    font-weight: 700;
  }
  .mobile-tab.is-active {
    color: var(--blue);
    box-shadow: inset 0 2px 0 var(--blue);
  }
}

@media (max-width: 420px) {
  .panel-header,
  .artifact-header,
  .panel-section,
  .context-card {
    padding: 12px;
  }
  .panel-header h1,
  .artifact-header h1 {
    font-size: 15px;
  }
  .artifact-header {
    align-items: stretch;
    flex-direction: column;
  }
  .artifact-actions {
    justify-content: flex-end;
  }
  .artifact-actions .secondary-button {
    width: auto;
  }
  .person-row {
    grid-template-columns: 26px auto auto;
  }
  .person-role {
    grid-column: 2 / -1;
  }
  .compact-grid.four,
  .approval-row,
  .history-list li,
  .receipt-list div {
    grid-template-columns: 1fr;
  }
  .queue-item {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .queue-item .chip {
    justify-self: start;
  }
}
"""


def _script(data: dict[str, Any]) -> str:
    data_json = _safe_json_for_script(data)
    return f"""
(function () {{
  const body = document.body;
  const prototypeData = {data_json};
  const MOBILE_BREAKPOINT = prototypeData.ui.mobile_breakpoint || 1100;
  const mobileTabs = Array.from(document.querySelectorAll("[data-mobile-target]"));
  const sourceData = prototypeData.sources;
  const workData = prototypeData.work_items;
  const humanData = prototypeData.humans;
  const palariData = prototypeData.palaris;
  let currentWorkId = prototypeData.ui.default_work_item_id;

  const mobilePaneMap = {{
    workbench: ["workbench", "chat"],
    artifact: ["artifact", "chat"],
    chat: ["context", "chat"],
    task: ["context", "task"],
    receipt: ["context", "receipt"],
    authority: ["context", "authority"],
    history: ["context", "history"],
  }};

  function setText(selector, value) {{
    const element = document.querySelector(selector);
    if (element) {{
      element.textContent = value;
    }}
  }}

  function setHTML(selector, value) {{
    const element = document.querySelector(selector);
    if (element) {{
      element.innerHTML = value;
    }}
  }}

  function setChip(element, value, colorClass) {{
    if (!element) {{
      return;
    }}
    element.textContent = value;
    element.className = "chip " + colorClass;
  }}

  function escapeHTML(value) {{
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }}

  const allowedDocumentTags = new Set([
    "blockquote", "br", "code", "em", "h1", "h2", "h3",
    "i", "li", "ol", "p", "pre", "strong", "ul",
  ]);

  function sanitizeDocumentHTML(value) {{
    const template = document.createElement("template");
    template.innerHTML = String(value);
    Array.from(template.content.querySelectorAll("*")).forEach((element) => {{
      const tag = element.tagName.toLowerCase();
      if (!allowedDocumentTags.has(tag)) {{
        const parent = element.parentNode;
        if (parent) {{
          while (element.firstChild) {{
            parent.insertBefore(element.firstChild, element);
          }}
          parent.removeChild(element);
        }}
        return;
      }}
      Array.from(element.attributes).forEach((attribute) => element.removeAttribute(attribute.name));
    }});
    return template.innerHTML;
  }}

  function currentAttempt(work) {{
    return work.attempts[work.current_attempt_id];
  }}

  function humanName(humanId, fallback) {{
    const human = humanData[humanId];
    return human ? human.name : fallback || "Unknown human";
  }}

  function actorName(kind, actorId) {{
    if (kind === "human") {{
      return humanName(actorId);
    }}
    const palari = palariData[actorId];
    return palari ? palari.name : "Unknown Palari";
  }}

  function actorAvatarClass(kind, actorId) {{
    if (kind === "human") {{
      const human = humanData[actorId];
      return human ? human.avatar_class : "alex";
    }}
    return "bot";
  }}

  function sourceOwner(source) {{
    return source.owner_human_id ? humanName(source.owner_human_id, source.owner_label) : source.owner_label;
  }}

  function sourceChipHTML(sourceId) {{
    const source = sourceData[sourceId];
    if (!source) {{
      return "";
    }}
    return `<button class="used-source" type="button"><span class="file-icon ${{escapeHTML(source.tone)}}">${{escapeHTML(source.type_label)}}</span>${{escapeHTML(source.title)}}</button>`;
  }}

  function renderChat(messages) {{
    return messages.map((message) => `
      <div class="chat-message ${{escapeHTML(message.speaker_kind)}}">
        <span class="tiny-avatar ${{escapeHTML(actorAvatarClass(message.speaker_kind, message.speaker_id))}}">${{message.speaker_kind === "palari" ? "M" : ""}}</span>
        <div><strong>${{escapeHTML(actorName(message.speaker_kind, message.speaker_id))}}</strong><time>${{escapeHTML(message.time)}}</time>
        <p>${{escapeHTML(message.text)}}</p></div>
      </div>
    `).join("");
  }}

  function renderAuthority(authority) {{
    if (!authority.approvals.length) {{
      return '<p class="muted-line">No human approver is needed for this local safe step.</p>';
    }}
    return authority.approvals.map((approval) => {{
      const human = humanData[approval.human_id];
      return `
        <div class="approval-row">
          <span class="tiny-avatar ${{escapeHTML(human.avatar_class)}}"></span>
          <strong>${{escapeHTML(human.name)}}</strong>
          <span>${{escapeHTML(approval.role)}}</span>
          <span class="chip ${{escapeHTML(approval.status_class)}}">${{escapeHTML(approval.status_label)}}</span>
        </div>
      `;
    }}).join("");
  }}

  function renderHistory(historyItems) {{
    return historyItems.map((item) => `
      <li><time>${{escapeHTML(item.time)}}</time><span>${{escapeHTML(item.text)}}</span><span class="chip chip-gray">${{escapeHTML(item.badge)}}</span></li>
    `).join("");
  }}

  function setMobileTarget(target) {{
    const next = mobilePaneMap[target] ? target : "artifact";
    const profile = mobilePaneMap[next];
    body.dataset.mobilePane = profile[0];
    body.dataset.contextCard = profile[1];
    mobileTabs.forEach((tab) => {{
      tab.classList.toggle("is-active", tab.dataset.mobileTarget === next);
    }});
    if (window.innerWidth <= MOBILE_BREAKPOINT) {{
      history.replaceState(null, "", "#" + next);
    }}
  }}

  function openContext(card, options) {{
    const next = card || "chat";
    body.dataset.contextCard = next;
    document.querySelectorAll("[data-context-card]").forEach((element) => {{
      element.classList.toggle("is-focused", element.dataset.contextCard === next);
    }});
    if (window.innerWidth <= MOBILE_BREAKPOINT) {{
      setMobileTarget(next);
      return;
    }}
    if (!options || options.scroll !== false) {{
      const target = document.querySelector(`.context-card[data-context-card="${{next}}"]`);
      if (target) {{
        target.scrollIntoView({{ block: "nearest" }});
      }}
    }}
  }}

  function selectSource(sourceId) {{
    const source = sourceData[sourceId];
    if (!source) {{
      return;
    }}
    document.querySelectorAll("[data-source-id]").forEach((row) => {{
      row.classList.toggle("is-selected", row.dataset.sourceId === sourceId);
    }});
    setText("[data-source-preview-title]", source.title);
    setText("[data-source-preview-copy]", source.summary);
    setChip(document.querySelector("[data-source-preview-mode]"), source.mode, source.mode_class);
    setText("[data-source-preview-provider]", source.provider);
    setText("[data-source-preview-access]", source.access);
    setText("[data-source-preview-owner]", sourceOwner(source));
    setText("[data-source-preview-seen]", source.last_seen);
  }}

  function toggleSourceFolder(button) {{
    const folder = button.closest(".source-folder");
    if (!folder) {{
      return;
    }}
    const collapsed = !folder.classList.contains("is-collapsed");
    folder.classList.toggle("is-collapsed", collapsed);
    folder.setAttribute("aria-expanded", String(!collapsed));
    button.setAttribute("aria-expanded", String(!collapsed));
    const caret = button.querySelector(".tree-caret");
    if (caret) {{
      caret.textContent = ">";
    }}
  }}

  function selectWork(workId) {{
    const work = workData[workId];
    if (!work) {{
      return;
    }}
    currentWorkId = workId;
    const attempt = currentAttempt(work);
    const palari = palariData[work.palari_id];
    const receipt = attempt.receipt;
    const authority = attempt.authority;

    document.querySelectorAll("[data-work-id]").forEach((row) => {{
      row.classList.toggle("is-active", row.dataset.workId === workId);
    }});

    setText("[data-artifact-title]", work.artifact_title);
    setText("[data-artifact-id]", work.public_id);
    setText("[data-artifact-attempt]", attempt.number);
    setChip(document.querySelector("[data-artifact-status]"), attempt.status_label, attempt.status_class);
    setText("[data-approval-copy]", work.approval_copy);
    setHTML("[data-sources-used]", `<span>Sources used</span>${{attempt.sources_used.map(sourceChipHTML).join("")}}`);
    setHTML("[data-document-card]", sanitizeDocumentHTML(attempt.document_html));

    setText("[data-footer-owner]", palari.name);
    setText("[data-footer-palari]", palari.role);
    setText("[data-footer-updated]", attempt.updated_label);
    setText("[data-footer-word-count]", attempt.word_count);
    setText("[data-footer-language]", attempt.language);

    setText("[data-task-title]", work.title);
    setChip(document.querySelector("[data-task-status]"), attempt.status_label, attempt.status_class);
    setText("[data-task-due]", work.due_label);
    setChip(document.querySelector("[data-task-priority]"), work.priority_label, work.priority_class);
    setText("[data-task-risk]", work.risk_label);
    setText("[data-task-id]", work.public_id);

    setText("[data-receipt-used]", receipt.sources_used);
    setText("[data-receipt-created]", receipt.created);
    setText("[data-receipt-external]", receipt.external_writes);
    setText("[data-receipt-not-done]", receipt.not_done);
    setText("[data-receipt-undo]", receipt.undo);
    setText("[data-receipt-title]", `Receipt (Attempt ${{attempt.number}})`);
    setChip(document.querySelector("[data-receipt-status]"), receipt.status_label, receipt.status_class);
    setHTML("[data-chat-thread]", renderChat(attempt.chat_messages));
    setText("[data-authority-requirement]", authority.requirement);
    setHTML("[data-authority-list]", renderAuthority(authority));
    setText("[data-authority-summary]", authority.summary);
    setText("[data-history-count]", `${{attempt.history_events.length}} change${{attempt.history_events.length === 1 ? "" : "s"}}`);
    setHTML("[data-history-list]", renderHistory(attempt.history_events));

    if (window.innerWidth <= MOBILE_BREAKPOINT) {{
      setMobileTarget("artifact");
    }} else {{
      openContext("task", {{ scroll: false }});
    }}
  }}

  document.addEventListener("click", (event) => {{
    const target = event.target.closest("[data-mobile-target]");
    if (target) {{
      event.preventDefault();
      setMobileTarget(target.dataset.mobileTarget);
      return;
    }}

    const sourceToggle = event.target.closest("[data-source-toggle]");
    if (sourceToggle) {{
      event.preventDefault();
      toggleSourceFolder(sourceToggle);
      return;
    }}

    const sourceRow = event.target.closest("[data-source-id]");
    if (sourceRow) {{
      event.preventDefault();
      selectSource(sourceRow.dataset.sourceId);
      return;
    }}

    const workRow = event.target.closest("[data-work-id]");
    if (workRow) {{
      event.preventDefault();
      selectWork(workRow.dataset.workId);
      return;
    }}

    const contextTrigger = event.target.closest("[data-open-context]");
    if (contextTrigger) {{
      event.preventDefault();
      openContext(contextTrigger.dataset.openContext || contextTrigger.dataset.contextCard || "chat");
      return;
    }}

    const pane = event.target.closest("[data-mobile-pane]");
    if (pane && window.innerWidth <= MOBILE_BREAKPOINT) {{
      event.preventDefault();
      const next = pane.dataset.mobilePane;
      if (next === "context") {{
        body.dataset.mobilePane = "context";
        body.dataset.contextCard = pane.dataset.contextCard || "chat";
      }} else if (next === "artifact") {{
        setMobileTarget("artifact");
      }} else if (next === "workbench") {{
        setMobileTarget("workbench");
      }}
    }}
  }});

  const initial = (location.hash || "#artifact").replace("#", "");
  selectSource(prototypeData.ui.default_source_id);
  selectWork(prototypeData.ui.default_work_item_id);
  setMobileTarget(initial);
}})();
"""


def _safe_json_for_script(data: dict[str, Any]) -> str:
    return (
        json.dumps(data, ensure_ascii=True, indent=2)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
