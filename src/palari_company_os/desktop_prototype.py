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
      <div class="source-tree" role="tree" aria-label="Source permissions by folder">
        <div class="source-folder read" role="treeitem" aria-expanded="true">
          <button class="source-folder-row" type="button" data-source-toggle aria-expanded="true">
            <span class="tree-caret" aria-hidden="true">&gt;</span>
            <span class="dot read"></span>
            <strong>Readable</strong>
            <span class="tree-count">5</span>
          </button>
          <div class="source-children" role="group">
            <button class="source-file-row is-selected" type="button" data-source-id="hcd-plan">
              <span>California HCD - 2025 Housing Plan</span>
              <span class="file-kind">PDF</span>
            </button>
            <button class="source-file-row" type="button" data-source-id="housing-law">
              <span>State Housing Element Law (Gov Code 65580)</span>
              <span class="file-kind">HTML</span>
            </button>
            <button class="source-file-row" type="button" data-source-id="adu-guide">
              <span>Urban Institute - ADU Guide</span>
              <span class="file-kind">PDF</span>
            </button>
            <button class="source-file-row" type="button" data-source-id="tenant-memo">
              <span>Oakland tenant protection memo</span>
              <span class="file-kind">Doc</span>
            </button>
            <button class="source-file-row" type="button" data-source-id="community-notes">
              <span>June community workshop notes</span>
              <span class="file-kind">MD</span>
            </button>
          </div>
        </div>

        <div class="source-folder inherit" role="treeitem" aria-expanded="true">
          <button class="source-folder-row" type="button" data-source-toggle aria-expanded="true">
            <span class="tree-caret" aria-hidden="true">&gt;</span>
            <span class="dot inherit"></span>
            <strong>Inherited (readable)</strong>
            <span class="tree-count">2</span>
          </button>
          <div class="source-children" role="group">
            <button class="source-file-row" type="button" data-source-id="oakland-element">
              <span>City of Oakland - Housing Element</span>
              <span class="file-kind">PDF</span>
            </button>
            <button class="source-file-row" type="button" data-source-id="rhna-targets">
              <span>Bay Area RHNA allocation table</span>
              <span class="file-kind">XLS</span>
            </button>
          </div>
        </div>

        <div class="source-folder write" role="treeitem" aria-expanded="true">
          <button class="source-folder-row" type="button" data-source-toggle aria-expanded="true">
            <span class="tree-caret" aria-hidden="true">&gt;</span>
            <span class="dot write"></span>
            <strong>Writable after approval</strong>
            <span class="tree-count">2</span>
          </button>
          <div class="source-children" role="group">
            <button class="source-file-row" type="button" data-source-id="comment-portal">
              <span>Oakland Planning Dept - Comment Portal</span>
              <span class="file-kind">Web</span>
            </button>
            <button class="source-file-row" type="button" data-source-id="work-drafts">
              <span>Work / public-comment drafts</span>
              <span class="file-kind">Drive</span>
            </button>
          </div>
        </div>

        <div class="source-folder blocked" role="treeitem" aria-expanded="true">
          <button class="source-folder-row" type="button" data-source-toggle aria-expanded="true">
            <span class="tree-caret" aria-hidden="true">&gt;</span>
            <span class="dot blocked"></span>
            <strong>Blocked</strong>
            <span class="tree-count">3</span>
          </button>
          <div class="source-children" role="group">
            <button class="source-file-row muted" type="button" data-source-id="mayor-strategy">
              <span>Mayor's Office - Internal Strategy Doc</span>
              <span class="file-kind">DOCX</span>
            </button>
            <button class="source-file-row muted" type="button" data-source-id="council-notes">
              <span>Councilmember Briefing Notes</span>
              <span class="file-kind">PDF</span>
            </button>
            <button class="source-file-row muted" type="button" data-source-id="private-email">
              <span>Private constituent email thread</span>
              <span class="file-kind">EML</span>
            </button>
          </div>
        </div>
      </div>
      <div class="source-preview" aria-live="polite">
        <div class="card-title-row">
          <h3>Source preview</h3>
          <span class="chip chip-green" data-source-preview-mode>Readable</span>
        </div>
        <strong data-source-preview-title>California HCD - 2025 Housing Plan</strong>
        <p data-source-preview-copy>Selected for Maya. She can read this planning source for the current draft; no write access is granted.</p>
        <dl class="source-meta-list">
          <div><dt>Provider</dt><dd data-source-preview-provider>Google Drive</dd></div>
          <div><dt>Access</dt><dd data-source-preview-access>Read selected file</dd></div>
          <div><dt>Owner</dt><dd data-source-preview-owner>Jordan Lee</dd></div>
          <div><dt>Last seen</dt><dd data-source-preview-seen>Jun 20, 2026 9:20 AM</dd></div>
        </dl>
      </div>
    </section>

    <section class="panel-section work-queue">
      <div class="section-title">
        <h2>Work Queue</h2>
        <button class="small-button" type="button">+ New</button>
      </div>
      <div class="queue-tabs" role="tablist" aria-label="Work queue filters">
        <button class="queue-tab is-active" type="button">Active <span>4</span></button>
        <button class="queue-tab" type="button">Review <span>2</span></button>
        <button class="queue-tab" type="button">Done <span>7</span></button>
      </div>
      <button class="queue-item is-active" type="button" data-work-id="comment">
        <strong>Draft public comment on Housing Element</strong>
        <span>Maya</span>
        <span>Due Jun 23</span>
        <span class="chip chip-blue">In Progress</span>
      </button>
      <button class="queue-item" type="button" data-work-id="fees">
        <strong>Research ADU fee structures</strong>
        <span>Maya</span>
        <span>Due Jun 24</span>
        <span class="chip chip-blue">In Progress</span>
      </button>
      <button class="queue-item" type="button" data-work-id="feedback">
        <strong>Summarize community feedback</strong>
        <span>Maya</span>
        <span>Due Jun 25</span>
        <span class="chip chip-gray">Not Started</span>
      </button>
      <button class="queue-item" type="button" data-work-id="memo">
        <strong>Prepare council memo for review</strong>
        <span>Maya</span>
        <span>Due Jun 26</span>
        <span class="chip chip-amber">Needs review</span>
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
        <h1 data-artifact-title>Draft public comment</h1>
        <div class="artifact-meta">
          <span>Work Item</span><strong data-artifact-id>PRL-HOUS-001</strong>
          <span>Attempt</span><strong data-artifact-attempt>1</strong>
          <span>Status</span><span class="chip chip-blue" data-artifact-status>In Progress</span>
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
        <p data-approval-copy>This work can be published to the Oakland Planning Dept portal after human approval.</p>
      </div>
      <button class="approval-button" type="button" data-open-context="authority" data-mobile-pane="context" data-context-card="authority">Request Approval</button>
    </div>

    <section class="sources-used">
      <div class="source-chip-list" aria-label="Sources used" data-sources-used>
        <span>Sources used</span>
        <button class="used-source" type="button"><span class="file-icon green">PDF</span>California HCD - 2025 Housing Plan</button>
        <button class="used-source" type="button"><span class="file-icon green">HTM</span>State Housing Element Law</button>
        <button class="used-source" type="button"><span class="file-icon blue">PDF</span>Urban Institute - ADU Guide</button>
      </div>
      <button class="secondary-button" type="button">+ Add</button>
    </section>

    <article class="document-card" data-document-card>
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
        <div><dt>Owner</dt><dd data-footer-owner>Maya</dd></div>
        <div><dt>Palari</dt><dd data-footer-palari>Policy Researcher</dd></div>
        <div><dt>Last updated</dt><dd data-footer-updated>Jun 20, 2026 10:42 AM</dd></div>
        <div><dt>Word count</dt><dd data-footer-word-count>612</dd></div>
        <div><dt>Language</dt><dd data-footer-language>English (US)</dd></div>
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
      <div class="chat-thread" data-chat-thread>
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
      <div class="card-title-row"><h2>Active Task</h2><span class="chip chip-blue" data-task-status>In Progress</span></div>
      <a class="task-link" href="#" data-open-context="task" data-task-title>Draft public comment on Housing Element</a>
      <dl class="compact-grid four">
        <div><dt>Due</dt><dd data-task-due>Jun 23, 2026</dd></div>
        <div><dt>Priority</dt><dd><span class="chip chip-red" data-task-priority>High</span></dd></div>
        <div><dt>Risk</dt><dd data-task-risk>R2</dd></div>
        <div><dt>Work Item</dt><dd data-task-id>PRL-HOUS-001</dd></div>
      </dl>
    </section>

    <section class="context-card" data-context-card="receipt">
      <div class="card-title-row">
        <h2 data-receipt-title>Receipt (Attempt 1)</h2>
        <span class="chip chip-blue" data-receipt-status>Ready for review</span>
      </div>
      <dl class="receipt-list">
        <div><dt>Used</dt><dd data-receipt-used>3 sources</dd></div>
        <div><dt>Created</dt><dd data-receipt-created>1 document draft</dd></div>
        <div><dt>External writes</dt><dd data-receipt-external>None</dd></div>
        <div><dt>Did not do</dt><dd data-receipt-not-done>Did not contact stakeholders</dd></div>
        <div><dt>Undo</dt><dd data-receipt-undo>No external changes to undo</dd></div>
      </dl>
      <button class="full-button" type="button" data-open-context="receipt">View full receipt -></button>
    </section>

    <section class="context-card" data-context-card="authority">
      <div class="card-title-row"><h2>Authority</h2></div>
      <p class="muted-line" data-authority-requirement>Approval required <span class="dot read inline"></span> R2</p>
      <div data-authority-list>
        <div class="approval-row">
        <span class="tiny-avatar jordan"></span><strong>Jordan Lee</strong><span>Policy Counsel</span><span class="chip chip-amber">Pending</span>
        </div>
        <div class="approval-row">
        <span class="tiny-avatar sam"></span><strong>Sam Patel</strong><span>Program Lead</span><span class="chip chip-gray">Pending</span>
        </div>
      </div>
      <p class="muted-line" data-authority-summary>1 of 2 approvals</p>
    </section>

    <section class="context-card" data-context-card="history">
      <div class="card-title-row"><h2>Changes &amp; History</h2></div>
      <p class="muted-line" data-history-count>3 changes</p>
      <ol class="history-list" data-history-list>
        <li><time>Jun 20, 10:42 AM</time><span>Draft created by Maya</span><span class="chip chip-gray">Attempt 1</span></li>
        <li><time>Jun 20, 10:30 AM</time><span>Sources selected</span><span class="chip chip-gray">Attempt 1</span></li>
        <li><time>Jun 20, 10:25 AM</time><span>Work item created</span><span class="chip chip-gray">-</span></li>
      </ol>
      <button class="link-row" type="button" data-open-context="history">View full history -></button>
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
  font-weight: 700;
}
.file-icon { width: 19px; height: 20px; }
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


def _script() -> str:
    return """
(function () {
  const body = document.body;
  const MOBILE_BREAKPOINT = 1100;
  const mobileTabs = Array.from(document.querySelectorAll("[data-mobile-target]"));
  const prototypeData = {
    workspaceId: "workspace_public_policy_housing",
    currentHumanId: "human_alex_ramirez",
    selectedPalariId: "palari_maya_policy",
    workbenchId: "workbench_public_policy_housing",
    humans: {
      human_alex_ramirez: { name: "Alex Ramirez", role: "Founder", initials: "AR" },
      human_jordan_lee: { name: "Jordan Lee", role: "Policy Counsel", initials: "JL" },
      human_sam_patel: { name: "Sam Patel", role: "Program Lead", initials: "SP" },
    },
    palaris: {
      palari_maya_policy: {
        name: "Maya",
        role: "Policy Researcher",
        scope: "Prepare public-policy work from selected sources; never write externally without approval.",
      },
    },
    sources: {
      "hcd-plan": {
        title: "California HCD - 2025 Housing Plan",
        provider: "Google Drive",
        externalId: "gdrive:file_hcd_2025_plan",
        access: "Read selected file",
        owner: "Jordan Lee",
        lastSeen: "Jun 20, 2026 9:20 AM",
        allowedPalaris: ["palari_maya_policy"],
        mode: "Readable",
        modeClass: "chip-green",
        summary: "Selected for Maya. She can read this statewide planning source for the current draft; no write access is granted.",
      },
      "housing-law": {
        title: "State Housing Element Law (Gov Code 65580)",
        provider: "Public web",
        externalId: "ca.gov:gov-code-65580",
        access: "Read public page",
        owner: "Public source",
        lastSeen: "Jun 20, 2026 9:22 AM",
        allowedPalaris: ["palari_maya_policy"],
        mode: "Readable",
        modeClass: "chip-green",
        summary: "A selected legal source Maya may use for statutory housing-element requirements and terminology.",
      },
      "adu-guide": {
        title: "Urban Institute - ADU Guide",
        provider: "Uploaded file",
        externalId: "upload:adu-guide.pdf",
        access: "Read selected upload",
        owner: "Alex Ramirez",
        lastSeen: "Jun 20, 2026 9:25 AM",
        allowedPalaris: ["palari_maya_policy"],
        mode: "Readable",
        modeClass: "chip-green",
        summary: "A selected research guide Maya may use for ADU policy context and practical recommendations.",
      },
      "tenant-memo": {
        title: "Oakland tenant protection memo",
        provider: "Google Doc",
        externalId: "gdoc:tenant-protection-memo",
        access: "Read selected document",
        owner: "Sam Patel",
        lastSeen: "Jun 20, 2026 9:31 AM",
        allowedPalaris: ["palari_maya_policy"],
        mode: "Readable",
        modeClass: "chip-green",
        summary: "A selected working memo Maya may use for tenant-protection arguments, with no permission to edit the source.",
      },
      "community-notes": {
        title: "June community workshop notes",
        provider: "Local note",
        externalId: "local-note:community-workshop-june",
        access: "Read workspace note",
        owner: "Alex Ramirez",
        lastSeen: "Jun 20, 2026 9:34 AM",
        allowedPalaris: ["palari_maya_policy"],
        mode: "Readable",
        modeClass: "chip-green",
        summary: "A local note selected for feedback summarization. It is safe to read and cannot be changed by this prototype.",
      },
      "oakland-element": {
        title: "City of Oakland - Housing Element",
        provider: "Parent workbench",
        externalId: "inherited:oakland-housing-element",
        access: "Inherited read",
        owner: "Housing parent workbench",
        lastSeen: "Jun 19, 2026 4:10 PM",
        allowedPalaris: ["palari_maya_policy"],
        mode: "Inherited",
        modeClass: "chip-blue",
        summary: "Readable through the parent Public Policy workbench. Maya can cite it here, but this child workbench did not add new permissions.",
      },
      "rhna-targets": {
        title: "Bay Area RHNA allocation table",
        provider: "Parent workbench",
        externalId: "inherited:rhna-targets",
        access: "Inherited read",
        owner: "Housing parent workbench",
        lastSeen: "Jun 19, 2026 4:15 PM",
        allowedPalaris: ["palari_maya_policy"],
        mode: "Inherited",
        modeClass: "chip-blue",
        summary: "Inherited planning table Maya may use for context, but it remains managed by the parent workbench.",
      },
      "comment-portal": {
        title: "Oakland Planning Dept - Comment Portal",
        provider: "External web",
        externalId: "web:oakland-comment-portal",
        access: "Write only after approval",
        owner: "Oakland Planning Dept",
        lastSeen: "Not written",
        allowedPalaris: ["palari_maya_policy"],
        mode: "Writable after approval",
        modeClass: "chip-amber",
        summary: "This is an output target. Maya may write here only after the required human approval, and the prototype will not perform the write.",
      },
      "work-drafts": {
        title: "Work / public-comment drafts",
        provider: "Google Drive",
        externalId: "gdrive:folder_public_comment_drafts",
        access: "Create approved work output",
        owner: "Alex Ramirez",
        lastSeen: "Jun 20, 2026 10:42 AM",
        allowedPalaris: ["palari_maya_policy"],
        mode: "Writable after approval",
        modeClass: "chip-amber",
        summary: "Maya can create reviewed drafts here after approval. Existing source files are not editable through this target.",
      },
      "mayor-strategy": {
        title: "Mayor's Office - Internal Strategy Doc",
        provider: "Google Drive",
        externalId: "gdrive:file_mayor_strategy_private",
        access: "Blocked",
        owner: "Mayor's Office",
        lastSeen: "Never",
        allowedPalaris: [],
        mode: "Blocked",
        modeClass: "chip-red",
        summary: "Maya cannot read this source in the current workbench. It is visible only to make the boundary explicit.",
      },
      "council-notes": {
        title: "Councilmember Briefing Notes",
        provider: "Email attachment",
        externalId: "mail-attachment:council-briefing-notes",
        access: "Blocked",
        owner: "Councilmember office",
        lastSeen: "Never",
        allowedPalaris: [],
        mode: "Blocked",
        modeClass: "chip-red",
        summary: "Maya cannot read this source unless a human explicitly adds it to the workbench later.",
      },
      "private-email": {
        title: "Private constituent email thread",
        provider: "Email",
        externalId: "mail:private-constituent-thread",
        access: "Blocked",
        owner: "Alex Ramirez",
        lastSeen: "Never",
        allowedPalaris: [],
        mode: "Blocked",
        modeClass: "chip-red",
        summary: "Private email is outside Maya's current boundary. The prototype shows the denial instead of hiding the risk.",
      },
    },
    workItems: {
    comment: {
      title: "Draft public comment",
      taskTitle: "Draft public comment on Housing Element",
      id: "PRL-HOUS-001",
      attempt: "1",
      status: "In Progress",
      statusClass: "chip-blue",
      due: "Jun 23, 2026",
      priority: "High",
      priorityClass: "chip-red",
      risk: "R2",
      allowedSources: ["hcd-plan", "housing-law", "adu-guide"],
      outputTargets: ["comment-portal", "work-drafts"],
      allowedActions: ["create_draft", "request_human_approval"],
      approvalCopy: "This work can be published to the Oakland Planning Dept portal after human approval.",
      footer: {
        owner: "Maya",
        palari: "Policy Researcher",
        updated: "Jun 20, 2026 10:42 AM",
        words: "612",
        language: "English (US)",
      },
      sources: [
        { label: "California HCD - 2025 Housing Plan", kind: "PDF", tone: "green" },
        { label: "State Housing Element Law", kind: "HTM", tone: "green" },
        { label: "Urban Institute - ADU Guide", kind: "PDF", tone: "blue" },
      ],
      document: `
        <h2>I. Introduction</h2>
        <p>Oakland's Housing Element update is a critical opportunity to advance housing affordability, fairness, and long-term community well-being.</p>
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
        <p>Thank you for the opportunity to comment. These steps will help Oakland build a more inclusive, resilient, and affordable future.</p>
      `,
      receipt: {
        status: "Ready for review",
        statusClass: "chip-blue",
        used: "3 sources",
        created: "1 document draft",
        external: "None",
        notDone: "Did not contact stakeholders",
        undo: "No external changes to undo",
      },
      authority: {
        requirement: "Approval required • R2 • external write target",
        summary: "1 of 2 approvals",
        approvers: [
          { name: "Jordan Lee", role: "Policy Counsel", status: "Pending", statusClass: "chip-amber", avatarClass: "jordan" },
          { name: "Sam Patel", role: "Program Lead", status: "Pending", statusClass: "chip-gray", avatarClass: "sam" },
        ],
      },
      chat: [
        { speaker: "Alex Ramirez", kind: "human", avatarClass: "alex", time: "10:25 AM", text: "Please draft a public comment on Oakland's Housing Element update focused on ADUs, tenant protections, and anti-displacement." },
        { speaker: "Maya", kind: "palari", avatarClass: "bot", time: "10:25 AM", text: "On it. I'll use the selected sources and keep this within scope." },
        { speaker: "Maya", kind: "palari", avatarClass: "bot", time: "10:42 AM", text: "Draft ready. Please review and let me know if you want any changes before approval." },
      ],
      history: [
        { time: "Jun 20, 10:42 AM", text: "Draft created by Maya", badge: "Attempt 1" },
        { time: "Jun 20, 10:30 AM", text: "Sources selected", badge: "Attempt 1" },
        { time: "Jun 20, 10:25 AM", text: "Work item created", badge: "-" },
      ],
    },
    fees: {
      title: "ADU fee research note",
      taskTitle: "Research ADU fee structures",
      id: "PRL-HOUS-002",
      attempt: "1",
      status: "In Progress",
      statusClass: "chip-blue",
      due: "Jun 24, 2026",
      priority: "Medium",
      priorityClass: "chip-amber",
      risk: "R2",
      allowedSources: ["housing-law", "adu-guide", "rhna-targets"],
      outputTargets: ["work-drafts"],
      allowedActions: ["create_research_note"],
      approvalCopy: "No external write is planned. Maya can save a research note to Work after review.",
      footer: {
        owner: "Maya",
        palari: "Policy Researcher",
        updated: "Jun 20, 2026 11:05 AM",
        words: "318",
        language: "English (US)",
      },
      sources: [
        { label: "State Housing Element Law", kind: "HTM", tone: "green" },
        { label: "Urban Institute - ADU Guide", kind: "PDF", tone: "blue" },
      ],
      document: `
        <h2>I. What Maya is comparing</h2>
        <p>Fee waivers, impact-fee timing, and ADU approval conditions across the selected housing sources.</p>
        <h2>II. Early pattern</h2>
        <ul>
          <li>Delay fee collection until later in the ADU process where legally possible.</li>
          <li>Separate affordability requirements from basic ministerial approval standards.</li>
          <li>Ask staff to publish a plain-language fee table for property owners.</li>
        </ul>
        <h2>III. Next review question</h2>
        <p>Confirm whether the comment should recommend a city fee schedule change or only ask for clearer standards.</p>
      `,
      receipt: {
        status: "Drafting",
        statusClass: "chip-blue",
        used: "2 sources",
        created: "1 research note",
        external: "None",
        notDone: "Did not estimate fees from unselected files",
        undo: "No external changes to undo",
      },
      authority: {
        requirement: "Human review optional • R2 • no external write",
        summary: "Review can be requested before using the note",
        approvers: [
          { name: "Jordan Lee", role: "Policy Counsel", status: "Available", statusClass: "chip-gray", avatarClass: "jordan" },
        ],
      },
      chat: [
        { speaker: "Alex Ramirez", kind: "human", avatarClass: "alex", time: "10:58 AM", text: "Can you compare the fee pieces separately from the comment draft?" },
        { speaker: "Maya", kind: "palari", avatarClass: "bot", time: "11:05 AM", text: "Yes. I made a research note and did not use any files outside the selected sources." },
      ],
      history: [
        { time: "Jun 20, 11:05 AM", text: "Research note drafted", badge: "Attempt 1" },
        { time: "Jun 20, 10:58 AM", text: "Work item split from public comment", badge: "Split" },
      ],
    },
    feedback: {
      title: "Community feedback summary",
      taskTitle: "Summarize community feedback",
      id: "PRL-HOUS-003",
      attempt: "0",
      status: "Not Started",
      statusClass: "chip-gray",
      due: "Jun 25, 2026",
      priority: "Normal",
      priorityClass: "chip-gray",
      risk: "R1",
      allowedSources: ["community-notes", "oakland-element"],
      outputTargets: ["work-drafts"],
      allowedActions: ["create_summary"],
      approvalCopy: "No draft has been created yet. Select readable community notes before Maya summarizes them.",
      footer: {
        owner: "Maya",
        palari: "Policy Researcher",
        updated: "Not started",
        words: "0",
        language: "English (US)",
      },
      sources: [
        { label: "City of Oakland - Housing Element", kind: "PDF", tone: "blue" },
      ],
      document: `
        <h2>Not started</h2>
        <p>Maya is waiting for a readable community-feedback source before drafting this summary.</p>
        <h2>What will happen next</h2>
        <p>Once the source is selected, Maya can make a compact summary and record a receipt that says exactly what she used.</p>
      `,
      receipt: {
        status: "Waiting",
        statusClass: "chip-gray",
        used: "No sources yet",
        created: "Nothing yet",
        external: "None",
        notDone: "No summary has been prepared",
        undo: "No changes to undo",
      },
      authority: {
        requirement: "No approval required yet • R1 • local summary",
        summary: "No approvers assigned",
        approvers: [],
      },
      chat: [
        { speaker: "Maya", kind: "palari", avatarClass: "bot", time: "11:12 AM", text: "I can summarize workshop notes once you confirm the selected note is the right source." },
      ],
      history: [
        { time: "Jun 20, 11:12 AM", text: "Waiting for source confirmation", badge: "Queued" },
      ],
    },
    memo: {
      title: "Council memo review packet",
      taskTitle: "Prepare council memo for review",
      id: "PRL-HOUS-004",
      attempt: "2",
      status: "Needs review",
      statusClass: "chip-amber",
      due: "Jun 26, 2026",
      priority: "High",
      priorityClass: "chip-red",
      risk: "R3",
      allowedSources: ["hcd-plan", "tenant-memo", "community-notes", "rhna-targets"],
      outputTargets: ["work-drafts"],
      allowedActions: ["prepare_review_packet"],
      approvalCopy: "This packet can be saved to Work for human review. It cannot be sent to council offices from the prototype.",
      footer: {
        owner: "Maya",
        palari: "Policy Researcher",
        updated: "Jun 20, 2026 11:32 AM",
        words: "884",
        language: "English (US)",
      },
      sources: [
        { label: "California HCD - 2025 Housing Plan", kind: "PDF", tone: "green" },
        { label: "Oakland tenant protection memo", kind: "Doc", tone: "green" },
        { label: "June community workshop notes", kind: "MD", tone: "green" },
        { label: "Bay Area RHNA allocation table", kind: "XLS", tone: "blue" },
      ],
      document: `
        <h2>Review packet summary</h2>
        <p>Maya prepared a council-facing memo outline with source-backed claims and unresolved questions separated for human review.</p>
        <h2>Included sections</h2>
        <ul>
          <li>One-page policy position summary.</li>
          <li>Evidence table mapping each claim to a selected source.</li>
          <li>Questions for Jordan before the packet is shared externally.</li>
        </ul>
        <h2>Human review needed</h2>
        <p>Confirm whether tenant-protection claims should be framed as recommendations or as conditions for support.</p>
      `,
      receipt: {
        status: "Needs review",
        statusClass: "chip-amber",
        used: "4 sources",
        created: "1 review packet",
        external: "None",
        notDone: "Did not email council offices",
        undo: "Remove draft packet from Work",
      },
      authority: {
        requirement: "Review required • R3 • sensitive policy packet",
        summary: "0 of 2 approvals",
        approvers: [
          { name: "Jordan Lee", role: "Policy Counsel", status: "Pending", statusClass: "chip-amber", avatarClass: "jordan" },
          { name: "Sam Patel", role: "Program Lead", status: "Pending", statusClass: "chip-amber", avatarClass: "sam" },
        ],
      },
      chat: [
        { speaker: "Maya", kind: "palari", avatarClass: "bot", time: "11:32 AM", text: "I prepared the packet for review and kept it inside Work. Nothing was sent externally." },
        { speaker: "Alex Ramirez", kind: "human", avatarClass: "alex", time: "11:34 AM", text: "Good. Keep the source map visible so Jordan can audit it quickly." },
      ],
      history: [
        { time: "Jun 20, 11:32 AM", text: "Review packet prepared", badge: "Attempt 2" },
        { time: "Jun 20, 11:18 AM", text: "Tenant memo added as source", badge: "Source" },
        { time: "Jun 20, 11:10 AM", text: "First packet attempt marked too broad", badge: "Revised" },
      ],
    },
  },
  };

  const sourceData = prototypeData.sources;
  const workData = prototypeData.workItems;

  const mobilePaneMap = {
    workbench: ["workbench", "chat"],
    artifact: ["artifact", "chat"],
    chat: ["context", "chat"],
    task: ["context", "task"],
    receipt: ["context", "receipt"],
    authority: ["context", "authority"],
    history: ["context", "history"],
  };

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (element) {
      element.textContent = value;
    }
  }

  function setHTML(selector, value) {
    const element = document.querySelector(selector);
    if (element) {
      element.innerHTML = value;
    }
  }

  function setChip(element, value, colorClass) {
    if (!element) {
      return;
    }
    element.textContent = value;
    element.className = "chip " + colorClass;
  }

  function escapeHTML(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function sourceChipHTML(source) {
    return `<button class="used-source" type="button"><span class="file-icon ${escapeHTML(source.tone)}">${escapeHTML(source.kind)}</span>${escapeHTML(source.label)}</button>`;
  }

  function renderChat(messages) {
    return messages.map((message) => `
      <div class="chat-message ${escapeHTML(message.kind)}">
        <span class="tiny-avatar ${escapeHTML(message.avatarClass)}">${message.kind === "palari" ? "M" : ""}</span>
        <div><strong>${escapeHTML(message.speaker)}</strong><time>${escapeHTML(message.time)}</time>
        <p>${escapeHTML(message.text)}</p></div>
      </div>
    `).join("");
  }

  function renderAuthority(authority) {
    if (!authority.approvers.length) {
      return '<p class="muted-line">No human approver is needed for this local safe step.</p>';
    }
    return authority.approvers.map((approver) => `
      <div class="approval-row">
        <span class="tiny-avatar ${escapeHTML(approver.avatarClass)}"></span>
        <strong>${escapeHTML(approver.name)}</strong>
        <span>${escapeHTML(approver.role)}</span>
        <span class="chip ${escapeHTML(approver.statusClass)}">${escapeHTML(approver.status)}</span>
      </div>
    `).join("");
  }

  function renderHistory(historyItems) {
    return historyItems.map((item) => `
      <li><time>${escapeHTML(item.time)}</time><span>${escapeHTML(item.text)}</span><span class="chip chip-gray">${escapeHTML(item.badge)}</span></li>
    `).join("");
  }

  function setMobileTarget(target) {
    const next = mobilePaneMap[target] ? target : "artifact";
    const profile = mobilePaneMap[next];
    body.dataset.mobilePane = profile[0];
    body.dataset.contextCard = profile[1];
    mobileTabs.forEach((tab) => {
      tab.classList.toggle("is-active", tab.dataset.mobileTarget === next);
    });
    if (window.innerWidth <= MOBILE_BREAKPOINT) {
      history.replaceState(null, "", "#" + next);
    }
  }

  function openContext(card, options) {
    const next = card || "chat";
    body.dataset.contextCard = next;
    document.querySelectorAll("[data-context-card]").forEach((element) => {
      element.classList.toggle("is-focused", element.dataset.contextCard === next);
    });
    if (window.innerWidth <= MOBILE_BREAKPOINT) {
      setMobileTarget(next);
      return;
    }
    if (!options || options.scroll !== false) {
      const target = document.querySelector(`.context-card[data-context-card="${next}"]`);
      if (target) {
        target.scrollIntoView({ block: "nearest" });
      }
    }
  }

  function selectSource(sourceId) {
    const source = sourceData[sourceId];
    if (!source) {
      return;
    }
    document.querySelectorAll("[data-source-id]").forEach((row) => {
      row.classList.toggle("is-selected", row.dataset.sourceId === sourceId);
    });
    setText("[data-source-preview-title]", source.title);
    setText("[data-source-preview-copy]", source.summary);
    setChip(document.querySelector("[data-source-preview-mode]"), source.mode, source.modeClass);
    setText("[data-source-preview-provider]", source.provider);
    setText("[data-source-preview-access]", source.access);
    setText("[data-source-preview-owner]", source.owner);
    setText("[data-source-preview-seen]", source.lastSeen);
  }

  function toggleSourceFolder(button) {
    const folder = button.closest(".source-folder");
    if (!folder) {
      return;
    }
    const collapsed = !folder.classList.contains("is-collapsed");
    folder.classList.toggle("is-collapsed", collapsed);
    folder.setAttribute("aria-expanded", String(!collapsed));
    button.setAttribute("aria-expanded", String(!collapsed));
    const caret = button.querySelector(".tree-caret");
    if (caret) {
      caret.textContent = ">";
    }
  }

  function selectWork(workId) {
    const work = workData[workId];
    if (!work) {
      return;
    }

    document.querySelectorAll("[data-work-id]").forEach((row) => {
      row.classList.toggle("is-active", row.dataset.workId === workId);
    });

    setText("[data-artifact-title]", work.title);
    setText("[data-artifact-id]", work.id);
    setText("[data-artifact-attempt]", work.attempt);
    setChip(document.querySelector("[data-artifact-status]"), work.status, work.statusClass);
    setText("[data-approval-copy]", work.approvalCopy);
    setHTML("[data-sources-used]", `<span>Sources used</span>${work.sources.map(sourceChipHTML).join("")}`);
    setHTML("[data-document-card]", work.document);

    setText("[data-footer-owner]", work.footer.owner);
    setText("[data-footer-palari]", work.footer.palari);
    setText("[data-footer-updated]", work.footer.updated);
    setText("[data-footer-word-count]", work.footer.words);
    setText("[data-footer-language]", work.footer.language);

    setText("[data-task-title]", work.taskTitle);
    setChip(document.querySelector("[data-task-status]"), work.status, work.statusClass);
    setText("[data-task-due]", work.due);
    setChip(document.querySelector("[data-task-priority]"), work.priority, work.priorityClass);
    setText("[data-task-risk]", work.risk);
    setText("[data-task-id]", work.id);

    setText("[data-receipt-used]", work.receipt.used);
    setText("[data-receipt-created]", work.receipt.created);
    setText("[data-receipt-external]", work.receipt.external);
    setText("[data-receipt-not-done]", work.receipt.notDone);
    setText("[data-receipt-undo]", work.receipt.undo);
    setText("[data-receipt-title]", `Receipt (Attempt ${work.attempt})`);
    setChip(document.querySelector("[data-receipt-status]"), work.receipt.status, work.receipt.statusClass);
    setHTML("[data-chat-thread]", renderChat(work.chat));
    setText("[data-authority-requirement]", work.authority.requirement);
    setHTML("[data-authority-list]", renderAuthority(work.authority));
    setText("[data-authority-summary]", work.authority.summary);
    setText("[data-history-count]", `${work.history.length} change${work.history.length === 1 ? "" : "s"}`);
    setHTML("[data-history-list]", renderHistory(work.history));

    if (window.innerWidth <= MOBILE_BREAKPOINT) {
      setMobileTarget("artifact");
    } else {
      openContext("task", { scroll: false });
    }
  }

  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-mobile-target]");
    if (target) {
      event.preventDefault();
      setMobileTarget(target.dataset.mobileTarget);
      return;
    }

    const sourceToggle = event.target.closest("[data-source-toggle]");
    if (sourceToggle) {
      event.preventDefault();
      toggleSourceFolder(sourceToggle);
      return;
    }

    const sourceRow = event.target.closest("[data-source-id]");
    if (sourceRow) {
      event.preventDefault();
      selectSource(sourceRow.dataset.sourceId);
      return;
    }

    const workRow = event.target.closest("[data-work-id]");
    if (workRow) {
      event.preventDefault();
      selectWork(workRow.dataset.workId);
      return;
    }

    const contextTrigger = event.target.closest("[data-open-context]");
    if (contextTrigger) {
      event.preventDefault();
      openContext(contextTrigger.dataset.openContext || contextTrigger.dataset.contextCard || "chat");
      return;
    }

    const pane = event.target.closest("[data-mobile-pane]");
    if (pane && window.innerWidth <= MOBILE_BREAKPOINT) {
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
  selectSource("hcd-plan");
  selectWork("comment");
  setMobileTarget(initial);
})();
"""
