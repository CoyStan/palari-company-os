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


def _e(value: str) -> str:
    return escape(value, quote=True)


def _html() -> str:
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
    {_nav_rail()}
    <main class="workspace-console" aria-label="Palari Company OS workspace">
      {_workbench_panel()}
      {_artifact_panel()}
      {_context_panel()}
    </main>
    {_mobile_nav()}
  </div>
  <script src="app.js"></script>
</body>
</html>
"""


def _nav_rail() -> str:
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
      <span><strong>Alex Ramirez</strong><small>Founder</small></span>
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


def _workbench_panel() -> str:
    return """
  <section class="panel workbench-panel" data-pane="workbench">
    <header class="panel-header">
      <div>
        <h1>Workbench / Public Policy / Housing</h1>
      </div>
      <button class="ghost-button" type="button" aria-label="Workbench menu">...</button>
    </header>

    <section class="panel-section assigned-section">
      <h2>Assigned</h2>
      <div class="person-row">
        <span class="person-avatar photo maya"></span>
        <strong>Maya</strong>
        <span class="chip chip-blue">Palari</span>
        <span class="person-role">Policy Researcher</span>
      </div>
      <div class="person-row">
        <span class="person-avatar photo jordan"></span>
        <strong>Jordan Lee</strong>
        <span class="chip chip-amber">Human</span>
        <span class="person-role">Policy Counsel</span>
      </div>
      <div class="person-row">
        <span class="person-avatar photo sam"></span>
        <strong>Sam Patel</strong>
        <span class="chip chip-amber">Human</span>
        <span class="person-role">Program Lead</span>
      </div>
    </section>

    <section class="panel-section sources-section">
      <div class="section-title"><h2>Sources</h2></div>
      <div class="source-group">
        <div class="source-group-title"><span class="dot read"></span>Readable<span>3</span></div>
        <button class="source-row" type="button" data-mobile-pane="artifact">
          <span class="file-icon">PDF</span>
          <span>California HCD - 2025 Housing Plan</span>
          <span class="file-kind">PDF</span>
        </button>
        <button class="source-row" type="button" data-mobile-pane="artifact">
          <span class="file-icon">HTM</span>
          <span>State Housing Element Law (Gov Code 65580)</span>
          <span class="file-kind">HTML</span>
        </button>
        <button class="source-row" type="button" data-mobile-pane="artifact">
          <span class="file-icon">PDF</span>
          <span>Urban Institute - ADU Guide</span>
          <span class="file-kind">PDF</span>
        </button>
      </div>
      <div class="source-group">
        <div class="source-group-title"><span class="dot inherit"></span>Inherited (readable)<span>1</span></div>
        <button class="source-row" type="button">
          <span class="file-icon">PDF</span>
          <span>City of Oakland - Housing Element</span>
          <span class="file-kind">PDF</span>
        </button>
      </div>
      <div class="source-group">
        <div class="source-group-title"><span class="dot write"></span>Writable after approval<span>1</span></div>
        <button class="source-row" type="button">
          <span class="file-icon">WEB</span>
          <span>Oakland Planning Dept - Comment Portal</span>
          <span class="file-kind">Web</span>
        </button>
      </div>
      <div class="source-group">
        <div class="source-group-title"><span class="dot blocked"></span>Blocked<span>2</span></div>
        <button class="source-row muted" type="button">
          <span class="file-icon">DOC</span>
          <span>Mayor's Office - Internal Strategy Doc</span>
          <span class="file-kind">DOCX</span>
        </button>
        <button class="source-row muted" type="button">
          <span class="file-icon">PDF</span>
          <span>Councilmember Briefing Notes</span>
          <span class="file-kind">PDF</span>
        </button>
      </div>
    </section>

    <section class="panel-section work-queue">
      <div class="section-title">
        <h2>Work Queue</h2>
        <button class="small-button" type="button">+ New</button>
      </div>
      <div class="queue-tabs" role="tablist" aria-label="Work queue filters">
        <button class="queue-tab is-active" type="button">Active <span>3</span></button>
        <button class="queue-tab" type="button">Review <span>1</span></button>
        <button class="queue-tab" type="button">Done <span>7</span></button>
      </div>
      <button class="queue-item is-active" type="button" data-mobile-pane="artifact">
        <strong>Draft public comment on Housing Element</strong>
        <span>Maya</span>
        <span>Due Jun 23</span>
        <span class="chip chip-blue">In Progress</span>
      </button>
      <button class="queue-item" type="button">
        <strong>Research ADU fee structures</strong>
        <span>Maya</span>
        <span>Due Jun 24</span>
        <span class="chip chip-blue">In Progress</span>
      </button>
      <button class="queue-item" type="button">
        <strong>Summarize community feedback</strong>
        <span>Maya</span>
        <span>Due Jun 25</span>
        <span class="chip chip-gray">Not Started</span>
      </button>
      <button class="link-row" type="button">View all work items -></button>
    </section>
  </section>
"""


def _artifact_panel() -> str:
    return """
  <section class="panel artifact-panel" data-pane="artifact">
    <header class="artifact-header">
      <div>
        <h1>Draft public comment</h1>
        <div class="artifact-meta">
          <span>Work Item</span><strong>PRL-HOUS-001</strong>
          <span>Attempt</span><strong>1</strong>
          <span>Status</span><span class="chip chip-blue">In Progress</span>
        </div>
      </div>
      <div class="artifact-actions">
        <button class="icon-menu" type="button" aria-label="More actions">...</button>
        <button class="secondary-button" type="button" data-mobile-pane="context" data-context-card="task">Check-in</button>
      </div>
    </header>

    <div class="approval-banner">
      <span class="warning-icon" aria-hidden="true">!</span>
      <div>
        <strong>Approval required before external write</strong>
        <p>This work can be published to the Oakland Planning Dept portal after human approval.</p>
      </div>
      <button class="approval-button" type="button" data-mobile-pane="context" data-context-card="authority">Request Approval</button>
    </div>

    <section class="sources-used">
      <div class="source-chip-list" aria-label="Sources used">
        <span>Sources used</span>
        <button class="used-source" type="button"><span class="file-icon green">PDF</span>California HCD - 2025 Housing Plan</button>
        <button class="used-source" type="button"><span class="file-icon green">HTM</span>State Housing Element Law</button>
        <button class="used-source" type="button"><span class="file-icon blue">PDF</span>Urban Institute - ADU Guide</button>
      </div>
      <button class="secondary-button" type="button">+ Add</button>
    </section>

    <article class="document-card">
      <h2>I. Introduction</h2>
      <p>Oakland's Housing Element update is a critical opportunity to advance housing affordability,
      fairness, and long-term community well-being.</p>

      <h2>II. Support for Key Strategies</h2>
      <ul>
        <li>Preserve and expand affordable housing.</li>
        <li>Increase approval certainty for middle housing and ADUs.</li>
        <li>Invest in tenant protections and anti-displacement strategies.</li>
      </ul>

      <h2>III. Recommendations</h2>
      <ol>
        <li>Adopt clear, objective standards for ADU approval.</li>
        <li>Expand right-to-counsel and tenant stabilization programs.</li>
        <li>Align zoning and infrastructure planning with RHNA targets.</li>
      </ol>

      <h2>IV. Conclusion</h2>
      <p>Thank you for the opportunity to comment. These steps will help Oakland build a more
      inclusive, resilient, and affordable future.</p>
    </article>

    <footer class="artifact-footer">
      <dl>
        <div><dt>Owner</dt><dd>Maya</dd></div>
        <div><dt>Palari</dt><dd>Policy Researcher</dd></div>
        <div><dt>Last updated</dt><dd>Jun 20, 2026 10:42 AM</dd></div>
        <div><dt>Word count</dt><dd>612</dd></div>
        <div><dt>Language</dt><dd>English (US)</dd></div>
      </dl>
      <button class="notes-toggle" type="button">Notes for approvers and reviewers (internal) -></button>
    </footer>
  </section>
"""


def _context_panel() -> str:
    return """
  <aside class="context-column" data-pane="context">
    <section class="context-card chat-card" data-context-card="chat">
      <header class="context-header">
        <h2>Maya Chat</h2>
        <span class="online-dot"></span><span>Online</span>
        <button class="ghost-button" type="button" aria-label="Chat menu">...</button>
      </header>
      <div class="chat-thread">
        <div class="chat-message human">
          <span class="tiny-avatar alex"></span>
          <div><strong>Alex Ramirez</strong><time>10:25 AM</time>
          <p>Please draft a public comment on Oakland's Housing Element update focused on ADUs, tenant protections, and anti-displacement.</p></div>
        </div>
        <div class="chat-message palari">
          <span class="tiny-avatar bot">M</span>
          <div><strong>Maya</strong><time>10:25 AM</time>
          <p>On it. I'll use the selected sources and keep this within scope.</p></div>
        </div>
        <div class="chat-message palari">
          <span class="tiny-avatar bot">M</span>
          <div><strong>Maya</strong><time>10:42 AM</time>
          <p>Draft ready. Please review and let me know if you want any changes before approval.</p></div>
        </div>
      </div>
      <div class="composer">
        <input aria-label="Message Maya" placeholder="Message Maya...">
        <button type="button" aria-label="Attach">+</button>
        <button type="button" aria-label="Send">Send</button>
      </div>
    </section>

    <section class="context-card" data-context-card="task">
      <div class="card-title-row"><h2>Active Task</h2><span class="chip chip-blue">In Progress</span></div>
      <a class="task-link" href="#">Draft public comment on Housing Element</a>
      <dl class="compact-grid four">
        <div><dt>Due</dt><dd>Jun 23, 2026</dd></div>
        <div><dt>Priority</dt><dd><span class="chip chip-red">High</span></dd></div>
        <div><dt>Risk</dt><dd>R2</dd></div>
        <div><dt>Work Item</dt><dd>PRL-HOUS-001</dd></div>
      </dl>
    </section>

    <section class="context-card" data-context-card="receipt">
      <div class="card-title-row">
        <h2>Receipt (Attempt 1)</h2>
        <span class="chip chip-blue">Ready for review</span>
      </div>
      <dl class="receipt-list">
        <div><dt>Used</dt><dd>3 sources</dd></div>
        <div><dt>Created</dt><dd>1 document draft</dd></div>
        <div><dt>External writes</dt><dd>None</dd></div>
        <div><dt>Did not do</dt><dd>Did not contact stakeholders</dd></div>
        <div><dt>Undo</dt><dd>No external changes to undo</dd></div>
      </dl>
      <button class="full-button" type="button">View full receipt -></button>
    </section>

    <section class="context-card" data-context-card="authority">
      <div class="card-title-row"><h2>Authority</h2></div>
      <p class="muted-line">Approval required <span class="dot read inline"></span> R2</p>
      <div class="approval-row">
        <span class="tiny-avatar jordan"></span><strong>Jordan Lee</strong><span>Policy Counsel</span><span class="chip chip-amber">Pending</span>
      </div>
      <div class="approval-row">
        <span class="tiny-avatar sam"></span><strong>Sam Patel</strong><span>Program Lead</span><span class="chip chip-gray">Pending</span>
      </div>
      <p class="muted-line">1 of 2 approvals</p>
    </section>

    <section class="context-card" data-context-card="history">
      <div class="card-title-row"><h2>Changes &amp; History</h2></div>
      <p class="muted-line">3 changes</p>
      <ol class="history-list">
        <li><time>Jun 20, 10:42 AM</time><span>Draft created by Maya</span><span class="chip chip-gray">Attempt 1</span></li>
        <li><time>Jun 20, 10:30 AM</time><span>Sources selected</span><span class="chip chip-gray">Attempt 1</span></li>
        <li><time>Jun 20, 10:25 AM</time><span>Work item created</span><span class="chip chip-gray">-</span></li>
      </ol>
      <button class="link-row" type="button">View full history -></button>
    </section>
  </aside>
"""


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
.chip-amber { background: var(--amber-bg); color: var(--amber); }
.chip-red { background: var(--red-bg); color: var(--red); }
.chip-gray { background: #f3f4f6; color: var(--ink-soft); }

.sources-section { display: grid; gap: 13px; }
.source-group { display: grid; gap: 6px; }
.source-group-title {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  color: var(--ink-soft);
  font-weight: 650;
  font-size: 12px;
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
.source-row {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 28px;
  border: 0;
  background: transparent;
  color: var(--ink-soft);
  text-align: left;
  font-size: 12px;
}
.source-row:hover { background: var(--panel-soft); }
.source-row span:nth-child(2) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-row.muted { color: var(--muted); }
.file-icon, .file-kind {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  color: var(--muted);
  background: #fff;
  font-size: 9px;
  font-weight: 700;
}
.file-icon { width: 19px; height: 20px; }
.file-icon.green { color: var(--green); border-color: #bbf7d0; }
.file-icon.blue { color: var(--blue); border-color: #bfdbfe; }
.file-kind { min-width: 34px; padding: 1px 5px; }

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
  gap: 8px;
  max-width: 100%;
  min-height: 32px;
  padding: 0 10px;
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
    grid-template-columns: 160px minmax(0, 1fr);
  }
  .workspace-console {
    grid-template-columns: minmax(280px, 330px) minmax(0, 1fr);
  }
  .context-column {
    display: none;
  }
}

@media (max-width: 900px) {
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


def _script() -> str:
    return """
(function () {
  const body = document.body;
  const mobileTabs = Array.from(document.querySelectorAll("[data-mobile-target]"));
  const mobilePaneMap = {
    workbench: ["workbench", "chat"],
    artifact: ["artifact", "chat"],
    chat: ["context", "chat"],
    task: ["context", "task"],
    receipt: ["context", "receipt"],
    authority: ["context", "authority"],
    history: ["context", "history"],
  };

  function setMobileTarget(target) {
    const next = mobilePaneMap[target] ? target : "artifact";
    const profile = mobilePaneMap[next];
    body.dataset.mobilePane = profile[0];
    body.dataset.contextCard = profile[1];
    mobileTabs.forEach((tab) => {
      tab.classList.toggle("is-active", tab.dataset.mobileTarget === next);
    });
    if (window.innerWidth <= 900) {
      history.replaceState(null, "", "#" + next);
    }
  }

  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-mobile-target]");
    if (target) {
      event.preventDefault();
      setMobileTarget(target.dataset.mobileTarget);
      return;
    }

    const pane = event.target.closest("[data-mobile-pane]");
    if (pane && window.innerWidth <= 900) {
      event.preventDefault();
      const next = pane.dataset.mobilePane;
      if (next === "context") {
        body.dataset.mobilePane = "context";
        body.dataset.contextCard = pane.dataset.contextCard || "chat";
      } else if (next === "artifact") {
        setMobileTarget("artifact");
      } else if (next === "workbench") {
        setMobileTarget("workbench");
      }
    }
  });

  const initial = (location.hash || "#artifact").replace("#", "");
  setMobileTarget(initial);
})();
"""
