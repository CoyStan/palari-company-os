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
    {_home_view()}
    {_workspace_view()}
    {_checkin_view()}
  </div>
  {_mobile_nav()}
  <script src="app.js"></script>
</body>
</html>
"""


def _rail() -> str:
    items = [
        ("home", "H", "Home"),
        ("source", "P", "Public Policy / Housing"),
        ("checkin", "C", "Work check-in"),
        ("chat", "M", "Maya"),
        ("receipt", "R", "Receipts"),
    ]
    buttons = "\n".join(
        f"""
    <button class="rail-button {"is-active" if key == "source" else ""}" type="button"
      data-target="{_e(key)}" aria-label="{_e(label)}">
      <span>{_e(initial)}</span>
    </button>
"""
        for key, initial, label in items
    )
    return f"""
<aside class="rail" aria-label="Palari workspace navigation">
  <div class="rail-logo">P</div>
  <div class="rail-stack">
    {buttons}
  </div>
  <button class="rail-button rail-plus" type="button" aria-label="Create workbench or Palari">+</button>
</aside>
"""


def _home_view() -> str:
    return """
<main class="view home-view" data-view="home">
  <section class="home-shell">
    <header class="home-hero">
      <p>Company workbenches</p>
      <h1>Choose the workbench before choosing the AI coworker.</h1>
      <span>Workbenches hold people, Palaris, sources, standards, drafts, receipts, and authority boundaries.</span>
    </header>
    <section class="home-grid">
      <article class="workbench-tree">
        <div class="section-title">
          <span>Workbench tree</span>
          <button type="button" data-target="source">Open Housing</button>
        </div>
        <ol class="tree">
          <li>
            <div class="tree-node company"><strong>/Company</strong><small>Rafa owns company standards</small></div>
            <ol>
              <li>
                <div class="tree-node parent"><strong>/Public Policy</strong><small>Parent standards inherited by child paths</small></div>
                <ol>
                  <li>
                    <button class="tree-node active" type="button" data-target="source">
                      <strong>/Housing</strong><small>Maya lead - needs human approval</small>
                    </button>
                    <ol>
                      <li>
                        <div class="tree-node child"><strong>/Rent Control</strong><small>Recommendation: create child Palari Clara</small></div>
                      </li>
                    </ol>
                  </li>
                </ol>
              </li>
              <li><div class="tree-node blocked"><strong>/Legal</strong><small>Privileged notes are not inherited</small></div></li>
              <li><div class="tree-node quiet"><strong>/Product</strong><small>Separate development workbench</small></div></li>
            </ol>
          </li>
        </ol>
      </article>
      <article class="home-panel priority-panel">
        <div class="section-title">
          <span>Needs attention</span>
          <button type="button" data-target="checkin">Check in</button>
        </div>
        <div class="attention-row hot">
          <strong>Public Policy / Housing</strong>
          <span>Approve one Work write for Maya's public comment draft.</span>
          <small>Owner Rafa - reviewer Diego - Palari Maya</small>
        </div>
        <div class="attention-row warn">
          <strong>Rent Control</strong>
          <span>May deserve its own child Palari before deeper source review.</span>
          <small>Recommendation only. Human decides.</small>
        </div>
        <div class="attention-row calm">
          <strong>Product</strong>
          <span>Development workbench is quiet; one receipt is ready.</span>
          <small>No external writes pending.</small>
        </div>
      </article>
      <article class="home-panel lead-panel">
        <div class="section-title"><span>Palari leads</span><button type="button">Manage</button></div>
        <div class="lead-row active"><span>M</span><div><strong>Maya</strong><small>/Public Policy / Housing - policy development lead</small></div></div>
        <div class="lead-row"><span>C</span><div><strong>Clara</strong><small>Suggested for /Rent Control - specialist not active yet</small></div></div>
        <div class="lead-row"><span>S</span><div><strong>Sofia</strong><small>/Product - development planning support</small></div></div>
      </article>
      <article class="home-panel rule-panel">
        <div class="section-title"><span>Inheritance rules</span><button type="button" data-target="source">Inspect</button></div>
        <ul>
          <li>Child paths inherit standards and review rules from parent workbenches.</li>
          <li>Readable sources inherit only when explicitly allowed.</li>
          <li>Write permission never silently inherits to child workbenches.</li>
          <li>Parent owners can supervise child work, but Palaris need explicit path rules.</li>
        </ul>
      </article>
    </section>
  </section>
</main>
"""


def _workspace_view() -> str:
    return f"""
<main class="view workspace-view is-active" data-view="workspace">
  {_explorer()}
  {_artifact()}
  {_sidecar()}
</main>
"""


def _explorer() -> str:
    sources = [
        ("read", "Bill text", "HB 2148 zoning modernization", "readable"),
        ("read", "Committee memo", "Housing committee staff analysis", "readable"),
        ("inherit", "Public Policy style rules", "Inherited rule set, not source files", "parent"),
        ("blocked", "Private mailbox", "Not selected for Maya", "blocked"),
        ("blocked", "Legal privileged notes", "Sibling path; no automatic access", "blocked"),
        ("write", "Work folder", "Drafts saved only after approval", "approval"),
        ("child", "Rent Control", "Child workbench with specialist recommendation", "child path"),
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
        ("waiting", "Council briefing memo", "Waiting on reviewer"),
        ("blocked", "Legal risk addendum", "Blocked by privileged source"),
        ("done", "Permit comparison table", "Receipt-ready"),
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
    <p>Open workbench</p>
    <h1>/Public Policy / Housing</h1>
    <span>Parent: /Public Policy - child: /Rent Control</span>
  </header>
  <section class="explorer-card people-card">
    <div class="section-title"><span>Assigned people and Palaris</span><button type="button">Edit</button></div>
    <dl>
      <div><dt>Owner</dt><dd>Rafa</dd></div>
      <div><dt>Reviewer</dt><dd>Diego</dd></div>
      <div><dt>Palari</dt><dd>Maya - policy development lead</dd></div>
      <div><dt>Support</dt><dd>Clara suggested for Rent Control</dd></div>
    </dl>
  </section>
  <section class="explorer-card">
    <div class="section-title">
      <span>Sources and paths</span>
      <button type="button">Add</button>
    </div>
    {source_rows}
  </section>
  <section class="explorer-card">
    <div class="section-title">
      <span>Work inside Housing</span>
      <button type="button" data-target="checkin">Check in</button>
    </div>
    {work_rows}
  </section>
  <section class="explorer-card permissions">
    <h2>Maya's boundary in this path</h2>
    <ul>
      <li><strong>Can read:</strong> selected bill text and committee memo.</li>
      <li><strong>Cannot read:</strong> legal privileged notes, private inbox, sibling paths.</li>
      <li><strong>Can draft locally:</strong> public comment, briefing memo, comparison table.</li>
      <li><strong>Can write:</strong> Work folder only after approval.</li>
    </ul>
  </section>
</aside>
"""


def _artifact() -> str:
    return """
<section class="artifact pane pane-document" data-mobile-pane="document">
  <header class="artifact-top">
    <button class="mobile-back" type="button" data-target="source">Back to sources</button>
    <div>
      <p>Selected artifact</p>
      <h2>Draft public comment: Downtown Housing Bill</h2>
      <span>/Company / Public Policy / Housing - Work output pending approval</span>
    </div>
    <button class="primary-action" type="button">Approve Work write</button>
  </header>
  <section class="document-card">
    <div class="doc-toolbar">
      <span class="doc-state">Draft</span>
      <span>Owner Rafa</span>
      <span>Reviewer Diego</span>
      <span>Maya can write only after approval</span>
      <span>Rent Control child path recommended</span>
    </div>
    <article class="document">
      <h3>Public comment on HB 2148</h3>
      <p>
        Maya prepared this draft from the selected bill text and committee memo inside the
        /Public Policy / Housing workbench. The draft supports expedited review for infill
        housing while preserving public notice, affordability reporting, and appeal clarity.
      </p>
      <h4>Recommended position</h4>
      <p>
        Support with amendments. The bill reduces duplicative local process, but the current
        language should name the approval timeline, require a public implementation dashboard,
        and preserve an exception path for safety findings.
      </p>
      <h4>Workbench boundary</h4>
      <p>
        I used only the two selected Housing sources. I did not inspect the private mailbox,
        Legal privileged notes, or sibling workbench files. Parent policy standards shaped the
        tone, but source access was not inherited automatically.
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
        to an external system. If approved, I will save one draft file to the Housing Work folder.
      </p>
    </article>
  </section>
</section>
"""


def _sidecar() -> str:
    return """
<aside class="sidecar pane pane-chat" data-mobile-pane="chat">
  <header class="sidecar-head">
    <button class="mobile-back" type="button" data-target="source">Back</button>
    <div>
      <p>Maya chat</p>
      <h2>Policy development lead</h2>
      <span>/Public Policy / Housing</span>
    </div>
  </header>
  <section class="chat-thread">
    <div class="message user">Can you turn the zoning bill and staff memo into a public comment?</div>
    <div class="message palari">Yes. I can use the bill text and committee memo in Housing. I cannot read Legal notes or the private mailbox.</div>
    <div class="message palari">I made a local draft and held the Work write for approval.</div>
    <div class="message palari subtle-message">Rent Control may deserve a child Palari, but I will not create it unless you decide.</div>
  </section>
  <section class="task-card pane-task" data-mobile-pane="task">
    <div class="section-title">
      <span>Active task</span>
      <button type="button" data-target="document">Open draft</button>
    </div>
    <h3>Prepare public comment draft</h3>
    <dl>
      <div><dt>Status</dt><dd>Needs human decision</dd></div>
      <div><dt>Next action</dt><dd>Rafa reviews, Diego comments, then approve one Work write.</dd></div>
      <div><dt>Risk</dt><dd>R2 - local policy draft</dd></div>
      <div><dt>Workbench</dt><dd>/Public Policy / Housing</dd></div>
    </dl>
  </section>
  <section class="receipt-card pane-receipt" data-mobile-pane="receipt">
    <div class="section-title">
      <span>Receipt</span>
      <button type="button">Copy</button>
    </div>
    <div class="receipt-grid">
      <div><strong>Used</strong><span>Bill text; committee memo; inherited style rules.</span></div>
      <div><strong>Created</strong><span>One local public comment draft.</span></div>
      <div><strong>Did not do</strong><span>No email, no filing, no source edits, no Legal access.</span></div>
      <div><strong>External writes</strong><span>None. Work write is waiting for approval.</span></div>
      <div><strong>Undo</strong><span>Discard draft before approving the Work write.</span></div>
    </div>
  </section>
  <section class="authority-card">
    <div class="section-title"><span>Authority</span><button type="button">Rules</button></div>
    <ul>
      <li>Rafa owns the Housing workbench.</li>
      <li>Diego is delegated reviewer for this task.</li>
      <li>Maya can draft locally and request one approved Work write.</li>
      <li>Clara can support only if the Rent Control child path is created.</li>
    </ul>
  </section>
  <section class="changes-card">
    <div class="section-title">
      <span>Changes and history</span>
      <button type="button" data-target="checkin">View all</button>
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


def _checkin_view() -> str:
    statuses = [
        ("active", "Active", "Council briefing memo", "/Public Policy / Housing", "Maya"),
        ("waiting", "Waiting", "Rent Control source setup", "/Public Policy / Housing / Rent Control", "Clara suggested"),
        ("blocked", "Blocked", "Legal risk addendum", "/Legal", "No Palari access"),
        ("review", "Needs review", "Public comment draft", "/Public Policy / Housing", "Diego"),
        ("human", "Needs human decision", "Approve Work write", "/Public Policy / Housing", "Rafa"),
        ("receipt", "Receipt-ready", "Permit comparison table", "/Public Policy / Housing", "Maya"),
        ("closed", "Closed", "Product launch notes summary", "/Product", "Sofia"),
    ]
    rows = "\n".join(
        f"""
      <button class="check-row {tone}" type="button">
        <span class="check-status">{_e(label)}</span>
        <strong>{_e(title)}</strong>
        <small>{_e(path)}</small>
        <em>{_e(owner)}</em>
      </button>
"""
        for tone, label, title, path, owner in statuses
    )
    return f"""
<main class="view checkin-view" data-view="checkin">
  <section class="checkin-shell">
    <header class="checkin-top">
      <button class="mobile-back" type="button" data-target="home">Back home</button>
      <div>
        <p>Work check-in</p>
        <h1>Supervise active work without old ceremony.</h1>
        <span>Every row is a human-readable next step across workbench paths, Palaris, and receipts.</span>
      </div>
    </header>
    <section class="checkin-layout">
      <aside class="checkin-list">
        <div class="section-title"><span>Status lanes</span><button type="button">Filter</button></div>
        {rows}
      </aside>
      <article class="checkin-detail">
        <p>Selected check-in</p>
        <h2>Approve Work write for public comment draft</h2>
        <div class="decision-strip">
          <span>Needs human decision</span>
          <span>Owner Rafa</span>
          <span>Reviewer Diego</span>
          <span>Palari Maya</span>
        </div>
        <h3>What happened</h3>
        <p>Maya used two selected Housing sources, created one local draft, and is asking to save it into the Housing Work folder.</p>
        <h3>What did not happen</h3>
        <p>No Google Drive write, no email, no filing, no Legal source access, and no child Palari creation.</p>
        <div class="check-actions">
          <button class="primary-action" type="button">Approve Work write</button>
          <button type="button" data-target="receipt">Review receipt</button>
          <button type="button" data-target="document">Open draft</button>
        </div>
      </article>
      <aside class="checkin-context">
        <div class="section-title"><span>Recommendation</span><button type="button">Decide later</button></div>
        <p><strong>Rent Control may deserve its own child Palari.</strong></p>
        <p>Reason: the Housing path now has a specialized policy subtopic with different sources and review expectations.</p>
        <p>This is not automatic. A human must create the child workbench or assign Clara.</p>
      </aside>
    </section>
  </section>
</main>
"""


def _mobile_nav() -> str:
    items = [
        ("home", "Home"),
        ("chat", "Chat"),
        ("task", "Task"),
        ("receipt", "Receipt"),
        ("source", "Sources"),
        ("document", "Draft"),
        ("checkin", "Check-in"),
    ]
    buttons = "\n".join(
        f'<button class="mobile-tab {"is-active" if key == "chat" else ""}" '
        f'type="button" data-target="{_e(key)}">{_e(label)}</button>'
        for key, label in items
    )
    return f'<nav class="mobile-nav" aria-label="Mobile workspace panes">{buttons}</nav>'


def _styles() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #edf2f7;
  --panel: #ffffff;
  --panel-soft: #f7f9fc;
  --ink: #101b2d;
  --ink-2: #34445d;
  --muted: #65748a;
  --line: #d6e0eb;
  --line-strong: #b5c5d7;
  --brand: #087c6f;
  --brand-2: #0ba08f;
  --navy: #10233e;
  --warn: #9a6500;
  --danger: #a33a3a;
  --blue: #1e5aa8;
  --ok-bg: #e6f7f3;
  --warn-bg: #fff5d9;
  --danger-bg: #fff0f0;
  --blue-bg: #edf5ff;
  --shadow: 0 18px 44px rgba(25, 39, 58, 0.12);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  min-width: 0;
  background: var(--bg);
  color: var(--ink);
}

button {
  font: inherit;
}

.prototype-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 4.25rem minmax(0, 1fr);
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
  cursor: pointer;
}

.rail-button.is-active {
  background: var(--brand);
  color: #fff;
  box-shadow: 0 0 0 3px rgba(15, 155, 136, 0.2);
}

.rail-plus {
  margin-top: auto;
}

.view {
  display: none;
  min-width: 0;
  min-height: 100vh;
}

.view.is-active {
  display: block;
}

.workspace-view.is-active {
  display: grid;
  grid-template-columns: minmax(18rem, 21rem) minmax(28rem, 1fr) minmax(20rem, 25rem);
}

.home-shell,
.checkin-shell {
  padding: 1.25rem;
  min-height: 100vh;
}

.home-hero,
.checkin-top {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  padding: 1rem;
  margin-bottom: 1rem;
}

.home-hero p,
.checkin-top p,
.pane-header p,
.artifact-top p,
.sidecar-head p,
.checkin-detail p:first-child {
  margin: 0 0 0.25rem;
  color: var(--brand);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.72rem;
  font-weight: 800;
}

.home-hero h1,
.checkin-top h1 {
  margin: 0 0 0.35rem;
  max-width: 52rem;
  font-size: clamp(1.6rem, 3vw, 2.55rem);
  line-height: 1.05;
}

.home-hero span,
.checkin-top span,
.pane-header span,
.artifact-top span,
.sidecar-head span {
  color: var(--muted);
}

.home-grid {
  display: grid;
  grid-template-columns: minmax(19rem, 1.05fr) minmax(20rem, 1fr) minmax(18rem, 0.8fr);
  gap: 1rem;
}

.workbench-tree,
.home-panel,
.explorer-card,
.document-card,
.task-card,
.receipt-card,
.authority-card,
.changes-card,
.checkin-list,
.checkin-detail,
.checkin-context {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 0.8rem;
  box-shadow: 0 1px 0 rgba(20, 35, 55, 0.04);
}

.workbench-tree,
.home-panel,
.checkin-list,
.checkin-detail,
.checkin-context {
  padding: 0.85rem;
}

.priority-panel {
  grid-row: span 2;
}

.lead-panel,
.rule-panel {
  align-self: start;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
  margin-bottom: 0.65rem;
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
.mobile-back,
.check-actions button {
  border: 1px solid var(--line-strong);
  background: #fff;
  border-radius: 0.55rem;
  color: var(--navy);
  min-height: 2.35rem;
  padding: 0 0.75rem;
  font-weight: 750;
}

.primary-action {
  background: var(--navy);
  color: #fff;
  border-color: var(--navy);
}

.tree,
.tree ol {
  list-style: none;
  margin: 0;
  padding-left: 0.9rem;
}

.tree > li {
  padding-left: 0;
}

.tree-node {
  width: 100%;
  display: grid;
  gap: 0.12rem;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: var(--panel-soft);
  color: inherit;
  text-align: left;
  margin: 0.35rem 0;
  padding: 0.55rem 0.65rem;
}

.tree-node strong {
  overflow-wrap: anywhere;
}

.tree-node small {
  color: var(--muted);
  line-height: 1.3;
}

.tree-node.active {
  border-color: var(--brand-2);
  background: var(--ok-bg);
  box-shadow: inset 3px 0 0 var(--brand);
}

.tree-node.parent {
  background: var(--blue-bg);
}

.tree-node.child {
  background: var(--warn-bg);
  border-color: #e6c875;
}

.tree-node.blocked {
  background: var(--danger-bg);
  border-color: #e8b7b7;
}

.attention-row {
  display: grid;
  gap: 0.2rem;
  padding: 0.75rem;
  border-radius: 0.75rem;
  border: 1px solid var(--line);
  margin-bottom: 0.55rem;
}

.attention-row.hot {
  background: var(--danger-bg);
  border-color: #e8b7b7;
}

.attention-row.warn {
  background: var(--warn-bg);
  border-color: #e6c875;
}

.attention-row.calm {
  background: var(--ok-bg);
  border-color: #9fd8cd;
}

.attention-row span,
.attention-row small,
.home-panel li {
  color: var(--ink-2);
  line-height: 1.4;
}

.attention-row small {
  color: var(--muted);
}

.lead-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.65rem;
  align-items: center;
  padding: 0.6rem;
  border: 1px solid var(--line);
  border-radius: 0.7rem;
  margin-bottom: 0.5rem;
}

.lead-row > span {
  width: 2.2rem;
  height: 2.2rem;
  display: grid;
  place-items: center;
  border-radius: 0.6rem;
  background: var(--navy);
  color: #fff;
  font-weight: 800;
}

.lead-row.active > span {
  background: var(--brand);
}

.lead-row small {
  color: var(--muted);
  line-height: 1.35;
}

.rule-panel ul,
.authority-card ul,
.permissions ul {
  margin: 0;
  padding-left: 1rem;
  color: var(--ink-2);
  font-size: 0.88rem;
  line-height: 1.5;
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

.pane-header h1,
.artifact-top h2,
.sidecar-head h2 {
  margin: 0;
  font-size: 1.28rem;
  line-height: 1.15;
}

.explorer-card {
  padding: 0.7rem;
  margin-bottom: 0.8rem;
}

.people-card dl,
.task-card dl {
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
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 800;
}

dd {
  margin: 0;
  color: var(--ink-2);
  font-size: 0.86rem;
  overflow-wrap: anywhere;
}

.source-row,
.work-row {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.6rem;
  min-height: 3.6rem;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 0.7rem;
  text-align: left;
  padding: 0.52rem;
  color: inherit;
}

.source-row.read {
  background: var(--ok-bg);
  border-color: #9fd8cd;
}

.source-row.inherit {
  background: var(--blue-bg);
  border-color: #aac9f0;
}

.source-row.blocked {
  background: var(--danger-bg);
  border-color: #efb7b7;
}

.source-row.write,
.source-row.child {
  background: var(--warn-bg);
  border-color: #ead08f;
}

.source-dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 999px;
  background: var(--brand);
}

.inherit .source-dot { background: var(--blue); }
.blocked .source-dot { background: var(--danger); }
.write .source-dot,
.child .source-dot { background: var(--warn); }

.source-copy,
.work-row span {
  min-width: 0;
  display: grid;
  gap: 0.12rem;
}

.source-copy strong,
.work-row span {
  overflow-wrap: anywhere;
  font-size: 0.88rem;
}

.source-copy small,
.source-badge,
.work-row small {
  color: var(--muted);
  font-size: 0.76rem;
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

.work-row.blocked {
  background: var(--danger-bg);
}

.work-row.waiting {
  background: var(--warn-bg);
}

.permissions h2 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
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
  padding: 0.75rem;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.8rem;
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
  font-size: clamp(1.35rem, 2.5vw, 2.05rem);
  line-height: 1.1;
}

.document h4 {
  margin: 1.25rem 0 0.35rem;
  font-size: 0.88rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--brand);
}

.document p {
  margin: 0 0 0.75rem;
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
  font-size: 0.88rem;
  line-height: 1.42;
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

.subtle-message {
  background: var(--warn-bg);
  border-color: #e3c56d;
}

.task-card,
.receipt-card,
.authority-card,
.changes-card {
  padding: 0.8rem;
}

.task-card h3,
.checkin-detail h2 {
  margin: 0 0 0.7rem;
  font-size: 1rem;
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
  font-size: 0.73rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--brand);
}

.receipt-grid span,
.changes-card li,
.authority-card li {
  color: var(--ink-2);
  font-size: 0.83rem;
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

.checkin-layout {
  display: grid;
  grid-template-columns: minmax(18rem, 23rem) minmax(28rem, 1fr) minmax(18rem, 22rem);
  gap: 1rem;
}

.check-row {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.25rem 0.65rem;
  align-items: center;
  text-align: left;
  background: var(--panel-soft);
  border: 1px solid var(--line);
  border-radius: 0.7rem;
  padding: 0.65rem;
  margin-bottom: 0.5rem;
  color: inherit;
}

.check-row strong,
.check-row small {
  min-width: 0;
  overflow-wrap: anywhere;
}

.check-row small,
.check-row em {
  color: var(--muted);
  font-size: 0.78rem;
  font-style: normal;
}

.check-status {
  grid-row: span 2;
  align-self: start;
  min-width: 5.5rem;
  text-align: center;
  border-radius: 999px;
  padding: 0.22rem 0.45rem;
  background: #fff;
  color: var(--ink-2);
  font-size: 0.72rem;
  font-weight: 800;
}

.check-row.human,
.check-row.blocked {
  background: var(--danger-bg);
  border-color: #e8b7b7;
}

.check-row.waiting {
  background: var(--warn-bg);
  border-color: #e6c875;
}

.check-row.receipt,
.check-row.active {
  background: var(--ok-bg);
  border-color: #9fd8cd;
}

.check-row.review {
  background: var(--blue-bg);
  border-color: #aac9f0;
}

.decision-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.8rem 0 1rem;
}

.decision-strip span {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.28rem 0.6rem;
  background: var(--panel-soft);
  color: var(--ink-2);
  font-size: 0.8rem;
}

.checkin-detail h3 {
  margin: 1rem 0 0.3rem;
  font-size: 0.85rem;
  color: var(--brand);
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.checkin-detail p,
.checkin-context p {
  color: var(--ink-2);
  line-height: 1.5;
}

.check-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 1rem;
}

.mobile-back,
.mobile-nav {
  display: none;
}

@media (max-width: 1120px) {
  .workspace-view.is-active {
    grid-template-columns: minmax(17rem, 20rem) minmax(26rem, 1fr);
  }

  .sidecar {
    grid-column: 1 / -1;
    min-height: auto;
    border-left: 0;
    border-top: 1px solid var(--line);
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  body {
    background: #fff;
  }

  .prototype-shell {
    display: block;
    min-height: 100vh;
    padding-bottom: 6.8rem;
  }

  .rail {
    display: none;
  }

  .view,
  .workspace-view.is-active,
  .home-view.is-active,
  .checkin-view.is-active {
    display: none;
  }

  .view.is-active {
    display: block;
  }

  .home-shell,
  .checkin-shell {
    padding: 0.85rem 0.85rem 7.1rem;
    min-height: calc(100vh - 6.8rem);
  }

  .home-grid,
  .checkin-layout {
    display: block;
  }

  .home-panel,
  .workbench-tree,
  .checkin-list,
  .checkin-detail,
  .checkin-context {
    margin-bottom: 0.85rem;
  }

  .pane {
    display: none;
    min-height: calc(100vh - 6.8rem);
    border: 0;
  }

  .pane.is-active {
    display: block;
  }

  .explorer,
  .artifact,
  .sidecar {
    padding: 0.85rem;
    padding-bottom: 7.1rem;
    overflow: visible;
  }

  .artifact {
    min-height: calc(100vh - 6.8rem);
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
    min-height: calc(100vh - 6.8rem);
    border: 0;
    grid-template-columns: 1fr;
  }

  .sidecar.is-active {
    display: grid;
  }

  .sidecar .task-card,
  .sidecar .receipt-card {
    display: none;
  }

  .sidecar.show-task .task-card,
  .sidecar.show-receipt .receipt-card {
    display: block;
  }

  .sidecar.show-task .chat-thread,
  .sidecar.show-task .sidecar-head,
  .sidecar.show-task .receipt-card,
  .sidecar.show-task .authority-card,
  .sidecar.show-task .changes-card {
    display: none;
  }

  .sidecar.show-receipt .chat-thread,
  .sidecar.show-receipt .sidecar-head,
  .sidecar.show-receipt .task-card,
  .sidecar.show-receipt .authority-card,
  .sidecar.show-receipt .changes-card {
    display: none;
  }

  .sidecar:not(.show-task):not(.show-receipt) .authority-card,
  .sidecar:not(.show-task):not(.show-receipt) .changes-card {
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
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.25rem;
    padding: 0.35rem;
    border: 1px solid var(--line);
    border-radius: 1rem;
    background: rgba(255, 255, 255, 0.95);
    box-shadow: 0 14px 38px rgba(20, 35, 55, 0.16);
  }

  .mobile-tab {
    min-width: 0;
    min-height: 2.45rem;
    border: 0;
    border-radius: 0.75rem;
    background: transparent;
    color: var(--ink-2);
    font-size: 0.74rem;
    font-weight: 800;
  }

  .mobile-tab.is-active {
    background: var(--navy);
    color: #fff;
  }
}

@media (max-width: 420px) {
  .home-hero h1,
  .checkin-top h1 {
    font-size: 1.7rem;
  }

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

/* ---------- Dashboard visual language pass ---------- */
:root {
  --bg: #f6f8fa;
  --panel: #ffffff;
  --panel-soft: #f6f8fa;
  --ink: #1f2328;
  --ink-2: #24292f;
  --muted: #57606a;
  --muted-2: #6e7781;
  --line: #d0d7de;
  --line-strong: #8c959f;
  --brand: #116329;
  --brand-2: #2da44e;
  --navy: #24292f;
  --warn: #9a6700;
  --danger: #cf222e;
  --blue: #0969da;
  --ok-bg: #dafbe1;
  --warn-bg: #fff8c5;
  --danger-bg: #fff8f8;
  --blue-bg: #ddf4ff;
  --shadow: none;
  font-size: 13px;
}

body {
  background:
    linear-gradient(90deg, rgba(208,215,222,.65) 0, rgba(208,215,222,.65) 1px, transparent 1px, transparent 100%)
    0 0 / 48px 100% no-repeat,
    var(--bg);
}

.prototype-shell {
  grid-template-columns: 48px minmax(0, 1fr);
}

.rail {
  background: var(--panel-soft);
  color: var(--ink);
  gap: 0.25rem;
  padding: 0.45rem 0;
  border-right: 1px solid var(--line);
}

.rail-logo {
  width: 24px;
  height: 24px;
  flex-basis: 24px;
  border-radius: 2px;
  background: var(--ink);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}

.rail-stack {
  gap: 0;
}

.rail-button {
  width: 100%;
  height: 30px;
  border: 0;
  border-left: 3px solid transparent;
  border-radius: 0;
  background: transparent;
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 650;
  box-shadow: none;
}

.rail-button span {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--panel);
}

.rail-button:hover {
  background: var(--panel);
}

.rail-button.is-active {
  background: var(--panel);
  border-left-color: var(--brand);
  color: var(--ink);
  box-shadow: none;
}

.rail-button.is-active span {
  border-color: var(--brand-2);
  background: var(--ok-bg);
  color: var(--brand);
}

.view,
.explorer,
.artifact,
.sidecar {
  min-height: 100vh;
}

.home-shell,
.checkin-shell {
  padding: 0.65rem 0.85rem 1rem;
}

.workspace-view.is-active {
  grid-template-columns: minmax(270px, 300px) minmax(390px, 1fr) minmax(300px, 340px);
}

.home-hero,
.checkin-top,
.workbench-tree,
.home-panel,
.explorer-card,
.document-card,
.task-card,
.receipt-card,
.authority-card,
.changes-card,
.checkin-list,
.checkin-detail,
.checkin-context {
  border-radius: 3px;
  border-color: var(--line);
  box-shadow: none;
}

.home-hero,
.checkin-top {
  padding: 0.72rem 0.85rem;
  margin-bottom: 0.75rem;
  background: linear-gradient(180deg, #fff, var(--panel-soft));
}

.home-hero p,
.checkin-top p,
.pane-header p,
.artifact-top p,
.sidecar-head p,
.checkin-detail p:first-child,
.section-title span {
  font-size: 0.68rem;
  font-weight: 650;
  color: var(--brand);
  letter-spacing: 0.08em;
}

.home-hero h1,
.checkin-top h1 {
  max-width: none;
  font-size: 1.12rem;
  font-weight: 650;
  line-height: 1.18;
  letter-spacing: -0.015em;
}

.home-hero span,
.checkin-top span,
.pane-header span,
.artifact-top span,
.sidecar-head span {
  font-size: 0.82rem;
}

.home-grid {
  grid-template-columns: minmax(260px, 1.05fr) minmax(290px, 1fr) minmax(250px, 0.8fr);
  gap: 0.7rem;
}

.workbench-tree,
.home-panel,
.checkin-list,
.checkin-detail,
.checkin-context,
.explorer-card,
.task-card,
.receipt-card,
.authority-card,
.changes-card {
  padding: 0.62rem 0.7rem;
}

.section-title {
  margin-bottom: 0.45rem;
}

.section-title button,
.primary-action,
.mobile-back,
.check-actions button {
  min-height: 26px;
  padding: 0 0.55rem;
  border-radius: 2px;
  background: var(--panel);
  color: var(--ink);
  font-size: 0.82rem;
  font-weight: 600;
}

.primary-action {
  background: var(--ink);
  border-color: var(--ink);
  color: #fff;
}

.tree,
.tree ol {
  padding-left: 0.72rem;
}

.tree-node,
.attention-row,
.lead-row,
.source-row,
.work-row,
.check-row,
.receipt-grid div,
.message {
  border-radius: 3px;
  background: var(--panel);
  box-shadow: none;
}

.tree-node {
  margin: 0.25rem 0;
  padding: 0.42rem 0.52rem;
  border-left: 3px solid transparent;
}

.tree-node strong,
.attention-row strong,
.lead-row strong,
.source-copy strong,
.work-row span,
.check-row strong {
  font-size: 0.86rem;
  font-weight: 600;
}

.tree-node small,
.attention-row span,
.attention-row small,
.lead-row small,
.source-copy small,
.source-badge,
.work-row small,
.check-row small,
.check-row em {
  font-size: 0.74rem;
}

.tree-node.parent {
  background: var(--panel);
  border-left-color: var(--blue);
}

.tree-node.active {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--brand);
  box-shadow: none;
}

.tree-node.child {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--warn);
}

.tree-node.blocked {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--danger);
}

.attention-row {
  gap: 0.12rem;
  padding: 0.48rem 0.58rem;
  margin-bottom: 0.38rem;
  border-left: 3px solid var(--line);
}

.attention-row.hot {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--danger);
}

.attention-row.warn {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--warn);
}

.attention-row.calm {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--brand);
}

.lead-row {
  gap: 0.5rem;
  padding: 0.42rem 0.5rem;
  margin-bottom: 0.34rem;
}

.lead-row > span {
  width: 22px;
  height: 22px;
  border-radius: 2px;
  background: var(--ink);
  font-size: 0.76rem;
}

.lead-row.active > span {
  background: var(--brand);
}

.rule-panel ul,
.authority-card ul,
.permissions ul {
  font-size: 0.78rem;
  line-height: 1.42;
}

.explorer {
  background: var(--panel-soft);
  padding: 0.65rem;
}

.pane-header {
  padding: 0.1rem 0.1rem 0.62rem;
}

.pane-header h1,
.artifact-top h2,
.sidecar-head h2 {
  font-size: 1.02rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.explorer-card {
  margin-bottom: 0.55rem;
}

dl div {
  grid-template-columns: 4.6rem minmax(0, 1fr);
  gap: 0.35rem;
}

dt {
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0;
  text-transform: none;
}

dd {
  font-size: 0.78rem;
  font-weight: 550;
}

.source-row,
.work-row {
  min-height: 38px;
  gap: 0.45rem;
  padding: 0.38rem 0.48rem;
  border-color: var(--line);
  border-left: 3px solid var(--line);
  margin-top: 0.26rem;
}

.source-row.read,
.source-row.inherit,
.source-row.blocked,
.source-row.write,
.source-row.child,
.work-row.active,
.work-row.blocked,
.work-row.waiting {
  background: var(--panel);
  border-color: var(--line);
}

.source-row.read,
.work-row.active {
  border-left-color: var(--brand);
}

.source-row.inherit {
  border-left-color: var(--blue);
}

.source-row.blocked,
.work-row.blocked {
  border-left-color: var(--danger);
}

.source-row.write,
.source-row.child,
.work-row.waiting {
  border-left-color: var(--warn);
}

.source-dot {
  width: 7px;
  height: 7px;
}

.source-badge,
.decision-strip span,
.doc-toolbar span,
.check-status {
  border-radius: 2px;
  background: var(--panel-soft);
  border: 1px solid var(--line);
  color: var(--muted);
}

.artifact {
  padding: 0.65rem 0.85rem;
}

.artifact-top {
  margin-bottom: 0.62rem;
}

.document-card {
  background: var(--panel);
}

.doc-toolbar {
  gap: 0.35rem;
  padding: 0.52rem 0.65rem;
  font-size: 0.74rem;
}

.doc-toolbar .doc-state {
  background: var(--warn-bg);
  border-color: var(--warn);
  color: var(--warn);
}

.document {
  max-width: 44rem;
  padding: 1rem 1.2rem;
  line-height: 1.56;
}

.document h3 {
  font-size: 1.34rem;
  font-weight: 650;
  letter-spacing: -0.015em;
}

.document h4 {
  margin-top: 1rem;
  font-size: 0.72rem;
  font-weight: 650;
}

.document p {
  font-size: 0.9rem;
}

.sidecar {
  background: var(--panel-soft);
  padding: 0.65rem;
  gap: 0.55rem;
}

.sidecar-head {
  gap: 0.45rem;
}

.chat-thread {
  gap: 0.38rem;
}

.message {
  padding: 0.48rem 0.6rem;
  font-size: 0.82rem;
  line-height: 1.38;
}

.message.user {
  margin-left: 1rem;
  background: var(--ink);
  border-color: var(--ink);
}

.message.palari {
  margin-right: 0.4rem;
}

.subtle-message {
  background: var(--panel);
  border-left: 3px solid var(--warn);
}

.task-card h3,
.checkin-detail h2 {
  font-size: 0.9rem;
}

.receipt-grid {
  gap: 0.32rem;
}

.receipt-grid div {
  padding: 0.4rem 0.5rem;
}

.receipt-grid strong {
  font-size: 0.68rem;
  font-weight: 650;
}

.receipt-grid span,
.changes-card li,
.authority-card li {
  font-size: 0.76rem;
}

.checkin-shell {
  padding: 0.65rem 0.85rem 1rem;
}

.checkin-layout {
  grid-template-columns: minmax(270px, 330px) minmax(390px, 1fr) minmax(260px, 320px);
  gap: 0.7rem;
}

.check-row {
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.18rem 0.5rem;
  padding: 0.45rem 0.55rem;
  margin-bottom: 0.35rem;
  border-left: 3px solid var(--line);
}

.check-row.human,
.check-row.blocked {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--danger);
}

.check-row.waiting {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--warn);
}

.check-row.receipt,
.check-row.active {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--brand);
}

.check-row.review {
  background: var(--panel);
  border-color: var(--line);
  border-left-color: var(--blue);
}

.check-status {
  min-width: 4.8rem;
  padding: 0.12rem 0.35rem;
  font-size: 0.68rem;
}

.decision-strip {
  margin: 0.45rem 0 0.75rem;
}

.checkin-detail h3 {
  font-size: 0.72rem;
  font-weight: 650;
}

.checkin-detail p,
.checkin-context p {
  font-size: 0.84rem;
}

.check-actions {
  gap: 0.4rem;
}

@media (max-width: 980px) {
  body {
    background: var(--bg);
  }

  .prototype-shell {
    padding-bottom: 6.25rem;
  }

  .home-shell,
  .checkin-shell,
  .explorer,
  .artifact,
  .sidecar {
    padding: 0.55rem 0.65rem 6.75rem;
  }

  .home-hero h1,
  .checkin-top h1 {
    font-size: 1.08rem;
  }

  .mobile-nav {
    left: 0.35rem;
    right: 0.35rem;
    bottom: 0.35rem;
    gap: 0;
    padding: 0.25rem;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.97);
    box-shadow: 0 -6px 20px rgba(15,29,45,.08);
  }

  .mobile-tab {
    min-height: 2.25rem;
    border-radius: 2px;
    font-size: 0.68rem;
  }

  .mobile-tab.is-active {
    background: var(--ink);
  }
}

@media (max-width: 420px) {
  .home-hero h1,
  .checkin-top h1 {
    font-size: 1.04rem;
  }
}

/* Screenshot refinement: use the dashboard's denser desktop rhythm without
   changing the prototype information architecture. */
@media (min-width: 1160px) {
  .home-grid {
    grid-template-columns:
      minmax(290px, 0.95fr)
      minmax(320px, 0.9fr)
      minmax(280px, 0.75fr)
      minmax(250px, 0.65fr);
    align-items: start;
  }

  .priority-panel {
    grid-row: auto;
  }
}

.home-shell,
.checkin-shell {
  max-width: none;
}

.attention-row strong,
.lead-row strong,
.source-copy strong,
.work-row span,
.check-row strong,
.task-card h3 {
  font-weight: 600;
}

.attention-row small,
.lead-row small,
.source-copy small,
.work-row small,
.check-row small,
.check-row em,
.receipt-grid span,
.changes-card li,
.authority-card li {
  line-height: 1.34;
}

.lead-row,
.attention-row {
  min-height: auto;
}

.home-panel,
.workbench-tree {
  align-self: stretch;
}
"""


def _script() -> str:
    return """
(function () {
  const controls = Array.from(document.querySelectorAll("[data-target]"));
  const views = Array.from(document.querySelectorAll("[data-view]"));
  const panes = Array.from(document.querySelectorAll("[data-mobile-pane]"));
  const sidecar = document.querySelector(".sidecar");
  const mobileTabs = Array.from(document.querySelectorAll(".mobile-tab"));
  const railButtons = Array.from(document.querySelectorAll(".rail-button[data-target]"));
  const viewTargets = new Set(["home", "checkin"]);
  const paneTargets = new Set(["source", "document", "chat", "task", "receipt"]);

  function targetView(target) {
    if (target === "home") return "home";
    if (target === "checkin") return "checkin";
    return "workspace";
  }

  function activate(target, replaceHash) {
    const next = viewTargets.has(target) || paneTargets.has(target) ? target : "source";
    const viewName = targetView(next);
    const paneName = next === "task" || next === "receipt" ? "chat" : next;

    views.forEach((view) => {
      view.classList.toggle("is-active", view.dataset.view === viewName);
    });

    panes.forEach((pane) => {
      pane.classList.toggle("is-active", pane.dataset.mobilePane === paneName);
    });

    if (sidecar) {
      sidecar.classList.toggle("show-task", next === "task");
      sidecar.classList.toggle("show-receipt", next === "receipt");
    }

    mobileTabs.forEach((tab) => {
      tab.classList.toggle("is-active", tab.dataset.target === next);
    });

    railButtons.forEach((button) => {
      const key = button.dataset.target;
      const active = key === next || (viewName === "workspace" && key === "source");
      button.classList.toggle("is-active", active);
    });

    if (replaceHash) {
      history.replaceState(null, "", "#" + next);
    }
  }

  controls.forEach((control) => {
    control.addEventListener("click", () => activate(control.dataset.target, true));
  });

  const initial = window.location.hash.replace("#", "") || "source";
  activate(initial, false);
})();
"""


def _e(value: str) -> str:
    return escape(value, quote=True)
