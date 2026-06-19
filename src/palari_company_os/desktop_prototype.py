from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path


@dataclass(frozen=True)
class DesktopPrototypeResult:
    title: str
    output_dir: str
    index_path: str
    assets: list[str]


def generate_desktop_prototype(output_dir: str | Path) -> DesktopPrototypeResult:
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    style_path = output / "styles.css"
    script_path = output / "app.js"
    index_path = output / "index.html"
    style_path.write_text(_styles(), encoding="utf-8")
    script_path.write_text(_script(), encoding="utf-8")
    index_path.write_text(_html(), encoding="utf-8")
    return DesktopPrototypeResult(
        title="Palari Desktop Shell Prototype",
        output_dir=str(output),
        index_path=str(index_path),
        assets=[str(style_path), str(script_path)],
    )


def _html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Palari Desktop Shell Prototype</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="prototype-shell">
    {_rail()}
    {_explorer()}
    {_artifact()}
    {_sidecar()}
  </div>
  {_mobile_nav()}
  <script src="app.js"></script>
</body>
</html>
"""


def _rail() -> str:
    items = [
        ("M", "Maya", "active"),
        ("S", "Sofia", ""),
        ("A", "Alfred", ""),
        ("N", "Noah", ""),
    ]
    buttons = "\n".join(
        f'<button class="rail-button {tone}" type="button" aria-label="{_e(name)}">'
        f"<span>{_e(initial)}</span></button>"
        for initial, name, tone in items
    )
    return f"""
<aside class="rail" aria-label="Workspace navigation">
  <div class="rail-logo">P</div>
  <div class="rail-stack">
    {buttons}
  </div>
  <button class="rail-button rail-plus" type="button" aria-label="Create Palari">+</button>
</aside>
"""


def _explorer() -> str:
    sources = [
        ("read", "Bill text", "HB 2148 zoning modernization", "12 pages"),
        ("read", "Committee memo", "Housing committee staff analysis", "4 pages"),
        ("blocked", "Private mailbox", "Not selected for Maya", "blocked"),
        ("write", "Work folder", "Drafts after founder approval", "approval only"),
    ]
    source_rows = "\n".join(
        f"""
      <button class="source-row {tone}" type="button">
        <span class="source-dot" aria-hidden="true"></span>
        <span class="source-copy">
          <strong>{_e(title)}</strong>
          <small>{_e(description)}</small>
        </span>
        <span class="source-badge">{_e(meta)}</span>
      </button>
"""
        for tone, title, description, meta in sources
    )
    work_items = [
        ("active", "Public comment draft", "Needs approval"),
        ("queued", "Council briefing memo", "Waiting on source"),
        ("done", "Permit comparison table", "Receipt ready"),
    ]
    work_rows = "\n".join(
        f"""
      <button class="work-row {tone}" type="button">
        <span>{_e(title)}</span>
        <small>{_e(meta)}</small>
      </button>
"""
        for tone, title, meta in work_items
    )
    return f"""
<aside class="explorer pane pane-source is-active" data-mobile-pane="source">
  <header class="pane-header">
    <p>Selected Palari</p>
    <h1>Maya</h1>
    <span>Policy development lead</span>
  </header>
  <section class="explorer-card">
    <div class="section-title">
      <span>Sources</span>
      <button type="button">Add</button>
    </div>
    {source_rows}
  </section>
  <section class="explorer-card">
    <div class="section-title">
      <span>Work</span>
      <button type="button">New</button>
    </div>
    {work_rows}
  </section>
  <section class="explorer-card permissions">
    <h2>Boundaries</h2>
    <ul>
      <li><strong>Can read:</strong> selected policy files only.</li>
      <li><strong>Cannot read:</strong> private inbox or unselected folders.</li>
      <li><strong>Can write:</strong> Work drafts after approval.</li>
    </ul>
  </section>
</aside>
"""


def _artifact() -> str:
    return """
<main class="artifact pane pane-document" data-mobile-pane="document">
  <header class="artifact-top">
    <button class="mobile-back" type="button" data-mobile-target="source">Back to sources</button>
    <div>
      <p>Selected artifact</p>
      <h2>Draft public comment: Downtown Housing Bill</h2>
      <span>Work output - pending founder approval</span>
    </div>
    <button class="primary-action" type="button">Approve write</button>
  </header>
  <section class="document-card">
    <div class="doc-toolbar">
      <span class="doc-state">Draft</span>
      <span>Uses 2 readable sources</span>
      <span>No external write yet</span>
    </div>
    <article class="document">
      <h3>Public comment on HB 2148</h3>
      <p>
        Maya prepared this draft from the selected bill text and committee memo. The draft
        supports expedited review for infill housing while asking the committee to preserve
        public notice, affordability reporting, and appeal clarity.
      </p>
      <h4>Recommended position</h4>
      <p>
        Support with amendments. The bill reduces duplicative local process, but the current
        language should name the approval timeline, require a public implementation dashboard,
        and preserve an exception path for safety findings.
      </p>
      <h4>Suggested language</h4>
      <p>
        The city supports faster housing approvals when applicants meet published objective
        standards. We recommend adding a quarterly reporting requirement and a clear notice
        period before automatic approval begins.
      </p>
      <h4>Approval note</h4>
      <p>
        I have not submitted this comment, emailed anyone, changed any source file, or written
        to an external system. If approved, I will save one draft file to the Work folder.
      </p>
    </article>
  </section>
</main>
"""


def _sidecar() -> str:
    return """
<aside class="sidecar pane pane-chat" data-mobile-pane="chat">
  <header class="sidecar-head">
    <button class="mobile-back" type="button" data-mobile-target="source">Back</button>
    <div>
      <p>Maya chat</p>
      <h2>Review session</h2>
    </div>
  </header>
  <section class="chat-thread">
    <div class="message user">Can you turn the zoning bill and staff memo into a public comment?</div>
    <div class="message palari">Yes. I can use the bill text and committee memo. I cannot read the private mailbox.</div>
    <div class="message palari">I made a draft and held the Work write for approval.</div>
  </section>
  <section class="task-card pane-task" data-mobile-pane="task">
    <div class="section-title">
      <span>Active task</span>
      <button type="button">Open</button>
    </div>
    <h3>Prepare public comment draft</h3>
    <dl>
      <div><dt>Status</dt><dd>Needs approval</dd></div>
      <div><dt>Next action</dt><dd>Review draft, then approve one Work write.</dd></div>
      <div><dt>Risk</dt><dd>R2 - local draft only</dd></div>
    </dl>
  </section>
  <section class="receipt-card pane-receipt" data-mobile-pane="receipt">
    <div class="section-title">
      <span>Receipt</span>
      <button type="button">Copy</button>
    </div>
    <div class="receipt-grid">
      <div><strong>Used</strong><span>Bill text, committee memo</span></div>
      <div><strong>Created</strong><span>One draft comment</span></div>
      <div><strong>Did not do</strong><span>No email, no filing, no source edits</span></div>
      <div><strong>External writes</strong><span>None yet</span></div>
      <div><strong>Undo</strong><span>Discard draft before approval</span></div>
    </div>
  </section>
  <section class="changes-card">
    <div class="section-title">
      <span>Changes and history</span>
      <button type="button">View all</button>
    </div>
    <ol>
      <li><span>10:42</span> Read selected bill text.</li>
      <li><span>10:44</span> Compared committee memo findings.</li>
      <li><span>10:49</span> Created local draft artifact.</li>
      <li><span>10:51</span> Waiting for human approval.</li>
    </ol>
  </section>
</aside>
"""


def _mobile_nav() -> str:
    items = [
        ("chat", "Chat"),
        ("task", "Task"),
        ("receipt", "Receipt"),
        ("source", "Sources"),
        ("document", "Draft"),
    ]
    buttons = "\n".join(
        f'<button class="mobile-tab {"is-active" if key == "chat" else ""}" '
        f'type="button" data-mobile-target="{_e(key)}">{_e(label)}</button>'
        for key, label in items
    )
    return f'<nav class="mobile-nav" aria-label="Mobile workspace panes">{buttons}</nav>'


def _styles() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #eef3f7;
  --panel: #ffffff;
  --panel-soft: #f7f9fb;
  --ink: #132033;
  --ink-2: #405069;
  --muted: #6a788d;
  --line: #d7e0ea;
  --line-strong: #b6c5d5;
  --brand: #0c796b;
  --brand-2: #0f9b88;
  --navy: #10233e;
  --warn: #9a6500;
  --danger: #a33a3a;
  --ok-bg: #e7f7f3;
  --warn-bg: #fff6de;
  --danger-bg: #fff0f0;
  --shadow: 0 18px 44px rgba(25, 39, 58, 0.12);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  min-width: 0;
}

button {
  font: inherit;
}

.prototype-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 4.25rem minmax(16rem, 20rem) minmax(28rem, 1fr) minmax(20rem, 25rem);
  gap: 0;
}

.rail {
  background: #0d1725;
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 0.8rem 0.55rem;
  border-right: 1px solid #1f3046;
}

.rail-logo {
  width: 2.3rem;
  height: 2.3rem;
  border-radius: 0.55rem;
  display: grid;
  place-items: center;
  background: #fff;
  color: var(--navy);
  font-weight: 800;
}

.rail-stack {
  display: grid;
  gap: 0.55rem;
  width: 100%;
}

.rail-button {
  width: 2.8rem;
  height: 2.8rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 0.8rem;
  background: #15243a;
  color: #dbe8f6;
  display: grid;
  place-items: center;
  cursor: default;
}

.rail-button.active {
  background: var(--brand);
  color: #fff;
  box-shadow: 0 0 0 3px rgba(15, 155, 136, 0.2);
}

.rail-plus {
  margin-top: auto;
  color: #fff;
}

.explorer,
.artifact,
.sidecar {
  min-width: 0;
  min-height: 100vh;
}

.explorer {
  background: var(--panel-soft);
  border-right: 1px solid var(--line);
  padding: 1rem;
  overflow-y: auto;
}

.pane-header {
  padding: 0.2rem 0.25rem 1rem;
}

.pane-header p,
.artifact-top p,
.sidecar-head p {
  margin: 0 0 0.25rem;
  color: var(--brand);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.72rem;
  font-weight: 800;
}

.pane-header h1,
.artifact-top h2,
.sidecar-head h2 {
  margin: 0;
  font-size: 1.35rem;
  line-height: 1.15;
}

.pane-header span,
.artifact-top span {
  color: var(--muted);
  font-size: 0.9rem;
}

.explorer-card,
.document-card,
.task-card,
.receipt-card,
.changes-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  box-shadow: 0 1px 0 rgba(20, 35, 55, 0.04);
}

.explorer-card {
  padding: 0.7rem;
  margin-bottom: 0.8rem;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
  margin-bottom: 0.55rem;
}

.section-title span {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-2);
  font-size: 0.72rem;
  font-weight: 800;
}

.section-title button,
.primary-action,
.mobile-back {
  border: 1px solid var(--line-strong);
  background: #fff;
  border-radius: 0.55rem;
  color: var(--navy);
  min-height: 2.35rem;
  padding: 0 0.75rem;
  font-weight: 700;
}

.primary-action {
  background: var(--navy);
  color: #fff;
  border-color: var(--navy);
}

.source-row,
.work-row {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.6rem;
  min-height: 3.8rem;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 0.7rem;
  text-align: left;
  padding: 0.55rem;
  color: inherit;
}

.source-row.read {
  background: var(--ok-bg);
  border-color: #9fd8cd;
}

.source-row.blocked {
  background: var(--danger-bg);
  border-color: #efb7b7;
}

.source-row.write {
  background: var(--warn-bg);
  border-color: #ead08f;
}

.source-dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 999px;
  background: var(--brand);
}

.blocked .source-dot { background: var(--danger); }
.write .source-dot { background: var(--warn); }

.source-copy,
.work-row span {
  min-width: 0;
  display: grid;
  gap: 0.12rem;
}

.source-copy strong,
.work-row span {
  overflow-wrap: anywhere;
  font-size: 0.9rem;
}

.source-copy small,
.source-badge,
.work-row small {
  color: var(--muted);
  font-size: 0.78rem;
}

.source-badge {
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  white-space: nowrap;
}

.work-row {
  grid-template-columns: minmax(0, 1fr) auto;
  background: #fff;
  border-color: var(--line);
  margin-top: 0.4rem;
}

.work-row.active {
  border-color: var(--brand-2);
  box-shadow: inset 3px 0 0 var(--brand);
}

.permissions h2 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}

.permissions ul {
  margin: 0;
  padding-left: 1rem;
  color: var(--ink-2);
  font-size: 0.86rem;
  line-height: 1.5;
}

.artifact {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  padding: 1rem;
  overflow: hidden;
}

.artifact-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.document-card {
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
  box-shadow: var(--shadow);
}

.doc-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.8rem;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.82rem;
}

.doc-toolbar span {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.25rem 0.55rem;
  background: #fff;
}

.doc-toolbar .doc-state {
  color: var(--warn);
  background: var(--warn-bg);
  border-color: #e3c56d;
  font-weight: 800;
}

.document {
  overflow-y: auto;
  padding: clamp(1rem, 2vw, 2rem);
  max-width: 48rem;
  margin: 0 auto;
  line-height: 1.62;
}

.document h3 {
  margin: 0 0 1rem;
  font-size: clamp(1.4rem, 2.6vw, 2.2rem);
  line-height: 1.1;
}

.document h4 {
  margin: 1.35rem 0 0.35rem;
  font-size: 0.92rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--brand);
}

.document p {
  margin: 0 0 0.8rem;
  color: var(--ink-2);
}

.sidecar {
  background: #f9fbfd;
  border-left: 1px solid var(--line);
  padding: 1rem;
  overflow-y: auto;
  display: grid;
  align-content: start;
  gap: 0.8rem;
}

.sidecar-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.chat-thread {
  display: grid;
  gap: 0.55rem;
}

.message {
  border-radius: 0.85rem;
  padding: 0.7rem 0.8rem;
  font-size: 0.9rem;
  line-height: 1.4;
  border: 1px solid var(--line);
  background: #fff;
}

.message.user {
  margin-left: 2rem;
  background: var(--navy);
  color: #fff;
  border-color: var(--navy);
}

.message.palari {
  margin-right: 1rem;
}

.task-card,
.receipt-card,
.changes-card {
  padding: 0.8rem;
}

.task-card h3 {
  margin: 0 0 0.7rem;
  font-size: 1rem;
}

dl {
  margin: 0;
  display: grid;
  gap: 0.45rem;
}

dl div {
  display: grid;
  grid-template-columns: 5.5rem minmax(0, 1fr);
  gap: 0.5rem;
}

dt {
  color: var(--muted);
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 800;
}

dd {
  margin: 0;
  color: var(--ink-2);
  font-size: 0.86rem;
}

.receipt-grid {
  display: grid;
  gap: 0.45rem;
}

.receipt-grid div {
  border: 1px solid var(--line);
  border-radius: 0.6rem;
  padding: 0.55rem;
  background: var(--panel-soft);
  display: grid;
  gap: 0.15rem;
}

.receipt-grid strong {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--brand);
}

.receipt-grid span,
.changes-card li {
  color: var(--ink-2);
  font-size: 0.84rem;
  line-height: 1.35;
}

.changes-card ol {
  margin: 0;
  padding-left: 1.2rem;
}

.changes-card li + li {
  margin-top: 0.4rem;
}

.changes-card li span {
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.mobile-back,
.mobile-nav {
  display: none;
}

@media (max-width: 980px) {
  body {
    background: #fff;
  }

  .prototype-shell {
    display: block;
    min-height: 100vh;
    padding-bottom: 4.35rem;
  }

  .rail {
    display: none;
  }

  .pane {
    display: none;
    min-height: calc(100vh - 4.35rem);
    border: 0;
  }

  .pane.is-active {
    display: block;
  }

  .explorer,
  .artifact,
  .sidecar {
    padding: 0.85rem;
    padding-bottom: 5.2rem;
    overflow: visible;
  }

  .artifact {
    min-height: calc(100vh - 4.35rem);
  }

  .artifact-top {
    align-items: flex-start;
    flex-direction: column;
  }

  .document-card {
    min-height: auto;
    display: block;
    box-shadow: none;
  }

  .document {
    overflow: visible;
    padding: 1rem;
  }

  .sidecar {
    display: none;
    min-height: calc(100vh - 4.35rem);
  }

  .sidecar.is-active {
    display: grid;
  }

  .sidecar .task-card,
  .sidecar .receipt-card,
  .sidecar .changes-card {
    display: none;
  }

  .sidecar.show-task .task-card,
  .sidecar.show-receipt .receipt-card {
    display: block;
  }

  .sidecar.show-task .chat-thread,
  .sidecar.show-task .sidecar-head {
    display: none;
  }

  .sidecar.show-receipt .chat-thread,
  .sidecar.show-receipt .sidecar-head {
    display: none;
  }

  .mobile-back {
    display: inline-flex;
    align-items: center;
  }

  .mobile-nav {
    position: fixed;
    z-index: 20;
    left: 0.55rem;
    right: 0.55rem;
    bottom: 0.55rem;
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.35rem;
    padding: 0.35rem;
    border: 1px solid var(--line);
    border-radius: 1rem;
    background: rgba(255, 255, 255, 0.94);
    box-shadow: 0 14px 38px rgba(20, 35, 55, 0.16);
  }

  .mobile-tab {
    min-width: 0;
    min-height: 2.75rem;
    border: 0;
    border-radius: 0.75rem;
    background: transparent;
    color: var(--ink-2);
    font-size: 0.78rem;
    font-weight: 800;
  }

  .mobile-tab.is-active {
    background: var(--navy);
    color: #fff;
  }
}

@media (max-width: 420px) {
  .source-row {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .source-badge {
    grid-column: 2;
    justify-self: start;
  }

  dl div {
    grid-template-columns: 1fr;
  }
}
"""


def _script() -> str:
    return """
(function () {
  const tabs = Array.from(document.querySelectorAll("[data-mobile-target]"));
  const panes = Array.from(document.querySelectorAll("[data-mobile-pane]"));
  const sidecar = document.querySelector(".sidecar");

  function activate(target) {
    const isTask = target === "task";
    const isReceipt = target === "receipt";
    const paneTarget = isTask || isReceipt ? "chat" : target;

    panes.forEach((pane) => {
      pane.classList.toggle("is-active", pane.dataset.mobilePane === paneTarget);
    });

    if (sidecar) {
      sidecar.classList.toggle("show-task", isTask);
      sidecar.classList.toggle("show-receipt", isReceipt);
    }

    tabs.forEach((tab) => {
      tab.classList.toggle("is-active", tab.dataset.mobileTarget === target);
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.mobileTarget;
      activate(target);
      if (target) {
        history.replaceState(null, "", "#" + target);
      }
    });
  });

  if (window.matchMedia("(max-width: 980px)").matches) {
    const initial = window.location.hash.replace("#", "") || "chat";
    const valid = tabs.some((tab) => tab.dataset.mobileTarget === initial);
    activate(valid ? initial : "chat");
  }
})();
"""


def _e(value: str) -> str:
    return escape(value, quote=True)
