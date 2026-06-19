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


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #

def _html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Palari Desktop Shell Prototype</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body class="workbench" data-view="workspace">
  <div class="titlebar">
    {_titlebar()}
  </div>
  <div class="workbench-grid" id="workbench-grid">
    {_activity_bar()}
    <div class="primary-sidebar pane" data-mobile-pane="explorer">
      {_primary_sidebar()}
    </div>
    <div class="splitter splitter-primary" id="splitter-primary" aria-label="Resize primary sidebar" role="separator"></div>
    <div class="editor-region">
      {_editor_area()}
      {_bottom_panel()}
    </div>
    <div class="splitter splitter-secondary" id="splitter-secondary" aria-label="Resize secondary sidebar" role="separator"></div>
    <div class="secondary-sidebar pane" data-mobile-pane="chat">
      {_secondary_sidebar()}
    </div>
  </div>
  {_status_bar()}
  {_mobile_nav()}
  <script src="app.js"></script>
</body>
</html>
"""


def _titlebar() -> str:
    return """
    <div class="titlebar-left">
      <button class="tb-icon" type="button" aria-label="Palari">P</button>
      <span class="tb-product">Palari</span>
      <span class="tb-sep" aria-hidden="true">/</span>
      <button class="tb-cmd" type="button" data-target="home">Company workbench</button>
    </div>
    <div class="tb-center">
      <div class="tb-search" role="search">
        <span class="tb-search-kbd" aria-hidden="true">Search sources, work, receipts</span>
      </div>
    </div>
    <div class="tb-right">
      <span class="tb-path">Public Policy / Housing</span>
      <span class="tb-user" title="Human owner">Rafa</span>
    </div>
"""


def _activity_bar() -> str:
    items = [
        ("home", "H", "Home"),
        ("explorer", "W", "Workbenches"),
        ("search", "S", "Sources / Search"),
        ("checkin", "C", "Work check-in"),
        ("receipt", "R", "Receipts"),
        ("settings", "G", "Settings"),
    ]
    buttons = "\n".join(
        f'    <button class="activity-btn {"is-active" if key == "explorer" else ""}" '
        f'type="button" data-target="{_e(key)}" title="{_e(label)}" aria-label="{_e(label)}">'
        f'<span class="activity-glyph">{_e(initial)}</span>'
        f'<span class="activity-label">{_e(label)}</span></button>'
        for key, initial, label in items
    )
    return f"""
<aside class="activity-bar" aria-label="Activity bar">
  <div class="activity-stack">
{buttons}
  </div>
  <div class="activity-foot">
    <button class="activity-btn" type="button" data-target="settings" title="Settings" aria-label="Settings">
      <span class="activity-glyph">G</span>
    </button>
  </div>
</aside>
"""


def _primary_sidebar() -> str:
    return f"""
  <div class="sidebar-header">
    <span class="sidebar-title">Explorer</span>
    <div class="sidebar-actions">
      <button class="icon-btn" type="button" aria-label="New workbench">+</button>
      <button class="icon-btn" type="button" aria-label="Refresh">⟳</button>
    </div>
  </div>
  <div class="sidebar-body">
    {_view_paths()}
    {_view_sources()}
    {_view_people()}
  </div>
"""


def _view_paths() -> str:
    return """
  <section class="tree-view is-expanded" data-tree="paths">
    <button class="tree-header" type="button" data-toggle="paths" aria-expanded="true">
      <span class="chevron">▾</span>
      <span>Workbench Paths</span>
      <span class="tree-count">6</span>
    </button>
    <ol class="tree" role="tree">
      <li role="treeitem" aria-expanded="true">
        <div class="tree-row depth-0"><span class="chevron">▾</span><span class="tree-icon">▣</span><span class="tree-label">Company</span><span class="tree-meta">Rafa</span></div>
        <ol role="group">
          <li role="treeitem" aria-expanded="true">
            <div class="tree-row depth-1"><span class="chevron">▾</span><span class="tree-icon">▣</span><span class="tree-label">Public Policy</span><span class="tree-meta badge inherit">parent</span></div>
            <ol role="group">
              <li role="treeitem" aria-expanded="true">
                <div class="tree-row depth-2 is-selected" data-target="explorer"><span class="chevron">▾</span><span class="tree-icon">▣</span><span class="tree-label">Housing</span><span class="tree-meta badge read">active</span></div>
                <ol role="group">
                  <li role="treeitem">
                    <div class="tree-row depth-3"><span class="chevron">▸</span><span class="tree-icon">▤</span><span class="tree-label">Rent Control</span><span class="tree-meta badge write">child</span></div>
                  </li>
                </ol>
              </li>
            </ol>
          </li>
          <li role="treeitem">
            <div class="tree-row depth-1"><span class="chevron">▸</span><span class="tree-icon">▣</span><span class="tree-label">Legal</span><span class="tree-meta badge blocked">privileged</span></div>
          </li>
          <li role="treeitem">
            <div class="tree-row depth-1"><span class="chevron">▸</span><span class="tree-icon">▣</span><span class="tree-label">Product</span><span class="tree-meta">Sofia</span></div>
          </li>
        </ol>
      </li>
    </ol>
  </section>
"""


def _view_sources() -> str:
    sources = [
        ("read", "Bill text", "HB 2148 zoning modernization", "readable"),
        ("read", "Committee memo", "Housing committee staff analysis", "readable"),
        ("inherit", "Public Policy style rules", "Inherited standards", "inherited"),
        ("blocked", "Private mailbox", "Not selected for Maya", "blocked"),
        ("blocked", "Legal privileged notes", "Sibling path; no access", "blocked"),
        ("write", "Work folder", "Write only after approval", "write after approval"),
    ]
    rows = "\n".join(
        f'      <li class="src-row perm-{tone}" data-target="draft" role="treeitem">'
        f'<span class="perm-dot"></span>'
        f'<span class="src-name">{_e(title)}</span>'
        f'<span class="src-note">{_e(description)}</span>'
        f'<span class="perm-badge">{_e(meta)}</span></li>'
        for tone, title, description, meta in sources
    )
    return f"""
  <section class="tree-view is-expanded" data-tree="sources">
    <button class="tree-header" type="button" data-toggle="sources" aria-expanded="true">
      <span class="chevron">▾</span>
      <span>Sources &amp; Permissions</span>
      <span class="tree-count">6</span>
    </button>
    <ol class="src-list" role="tree">
{rows}
    </ol>
    <div class="perm-legend">
      <span><i class="perm-dot read"></i>readable</span>
      <span><i class="perm-dot inherit"></i>inherited</span>
      <span><i class="perm-dot blocked"></i>blocked</span>
      <span><i class="perm-dot write"></i>write after approval</span>
    </div>
  </section>
"""


def _view_people() -> str:
    people = [
        ("M", "Maya", "Palari - policy development lead", "active"),
        ("C", "Clara", "Suggested for Rent Control", "write"),
        ("R", "Rafa", "Owner", "inherit"),
        ("D", "Diego", "Delegated reviewer", "inherit"),
    ]
    rows = "\n".join(
        f'      <li class="people-row"><span class="avatar">{_e(initial)}</span>'
        f'<span class="people-name">{_e(name)}</span>'
        f'<span class="people-role">{_e(role)}</span></li>'
        for initial, name, role, _ in people
    )
    return f"""
  <section class="tree-view is-collapsed" data-tree="people">
    <button class="tree-header" type="button" data-toggle="people" aria-expanded="false">
      <span class="chevron">▸</span>
      <span>People &amp; Palaris</span>
      <span class="tree-count">4</span>
    </button>
    <ol class="people-list" role="tree" hidden>
{rows}
    </ol>
  </section>
"""


def _editor_area() -> str:
    tabs = [
        ("home", "Home", False),
        ("draft", "Draft", True),
        ("source", "Source", False),
        ("receipt", "Receipt", False),
        ("workitem", "Work Item", False),
    ]
    tab_html = "\n".join(
        f'      <button class="editor-tab {"is-active" if active else ""}" type="button" '
        f'data-target="{_e(key)}"><span>{_e(label)}</span>'
        f'<span class="tab-close" aria-hidden="true">×</span></button>'
        for key, label, active in tabs
    )
    return f"""
    <div class="editor-area pane" data-mobile-pane="draft">
      <nav class="editor-tabs" role="tablist">
{tab_html}
      </nav>
      <div class="editor-content">
        {_editor_home()}
        {_editor_document()}
        {_editor_source()}
        {_editor_receipt()}
        {_editor_workitem()}
        {_editor_checkin_detail()}
      </div>
    </div>
"""


def _breadcrumb(trail: list[tuple[str, str]], action_label: str | None = None,
                action_target: str | None = None) -> str:
    crumbs = "".join(
        f'<span>{_e(label)}</span><span class="bc-sep">›</span>'
        for label, _ in trail[:-1]
    )
    last = trail[-1] if trail else None
    last_html = f'<span class="bc-current">{_e(last[0])}</span>' if last else ""
    action = ""
    if action_label:
        action = (f'<span class="bc-spacer"></span>'
                  f'<button class="crumb-action" type="button" data-target="{_e(action_target or "")}">'
                  f'{_e(action_label)}</button>')
    return f'<div class="breadcrumbs">{crumbs}{last_html}{action}</div>'


def _editor_home() -> str:
    bc = _breadcrumb(
        [("Company", "company"), ("Home", "home")],
        action_label="Open Housing", action_target="explorer",
    )
    return f"""
        <section class="doc-surface home-surface" data-doc="home" hidden>
          {bc}
          <div class="doc-meta">
            <span class="doc-state badge read">Home</span>
            <span class="doc-chip">Active workbench: Public Policy / Housing</span>
            <span class="doc-chip">Palari lead: Maya</span>
            <span class="doc-chip">Owner: Rafa - Reviewer: Diego</span>
          </div>
          <div class="home-grid">
            <div class="home-col">
              <h2 class="surface-h">Active workbenches</h2>
              <ul class="home-rows">
                <li class="home-row is-active" data-target="explorer">
                  <span class="home-path">Public Policy / Housing</span>
                  <span class="home-lead">Maya - policy development lead</span>
                  <span class="badge blocked">needs human decision</span>
                </li>
                <li class="home-row">
                  <span class="home-path">Public Policy / Housing / Rent Control</span>
                  <span class="home-lead">Clara suggested</span>
                  <span class="badge write">child workbench</span>
                </li>
                <li class="home-row">
                  <span class="home-path">Public Policy</span>
                  <span class="home-lead">Parent standards</span>
                  <span class="badge inherit">inherited</span>
                </li>
                <li class="home-row">
                  <span class="home-path">Legal</span>
                  <span class="home-lead">No Palari access</span>
                  <span class="badge blocked">privileged</span>
                </li>
                <li class="home-row">
                  <span class="home-path">Product</span>
                  <span class="home-lead">Sofia - development planning</span>
                  <span class="badge read">receipt-ready</span>
                </li>
              </ul>
              <h2 class="surface-h">Parent / child relationships</h2>
              <ul class="rule-list">
                <li>Child paths inherit standards and review rules from parent workbenches.</li>
                <li>Readable sources inherit only when explicitly allowed.</li>
                <li>Write permission never silently inherits to child workbenches.</li>
                <li>Child Palaris cannot automatically read sibling or parent paths.</li>
                <li>Parent owners can supervise child work; Palaris need explicit path rules.</li>
              </ul>
            </div>
            <div class="home-col">
              <h2 class="surface-h">Attention state</h2>
              <ul class="home-rows">
                <li class="home-row"><span class="home-path">Approve Work write</span><span class="badge blocked">needs human decision</span></li>
                <li class="home-row"><span class="home-path">Public comment draft</span><span class="badge inherit">needs review</span></li>
                <li class="home-row"><span class="home-path">Rent Control source setup</span><span class="badge write">waiting</span></li>
                <li class="home-row"><span class="home-path">Legal risk addendum</span><span class="badge blocked">blocked</span></li>
                <li class="home-row"><span class="home-path">Permit comparison table</span><span class="badge read">receipt-ready</span></li>
              </ul>
              <div class="reco-card">
                <h3>Recommendation</h3>
                <p><strong>Rent Control may deserve its own child Palari.</strong></p>
                <p>Reason: the Housing path now has a specialized policy subtopic with different sources and review expectations.</p>
                <p>This is not automatic. A human must create the child workbench or assign Clara.</p>
                <div class="doc-actions">
                  <button class="secondary-action" type="button">Create child workbench</button>
                  <button class="secondary-action" type="button">Decide later</button>
                </div>
              </div>
            </div>
          </div>
        </section>
"""


def _editor_checkin_detail() -> str:
    bc = _breadcrumb(
        [("Company", "company"), ("Public Policy", "pp"), ("Housing", "h"), ("Work check-in", "checkin")],
        action_label="Open draft", action_target="draft",
    )
    return f"""
        <section class="doc-surface checkin-surface" data-doc="checkin" hidden>
          {bc}
          <div class="doc-meta">
            <span class="doc-state badge blocked">Needs human decision</span>
            <span class="doc-chip">Owner Rafa</span>
            <span class="doc-chip">Reviewer Diego</span>
            <span class="doc-chip">Palari Maya</span>
            <span class="doc-chip">Path: Public Policy / Housing</span>
          </div>
          <article class="document checkin-doc">
            <h1>Approve Work write for public comment draft</h1>
            <h2>What happened</h2>
            <p>Maya used two selected Housing sources, created one local draft, and is asking to save it into the Housing Work folder.</p>
            <h2>What did not happen</h2>
            <p>No Google Drive write, no email, no filing, no Legal source access, and no child Palari creation.</p>
            <h2>Receipt summary</h2>
            <p>Used: bill text, committee memo. Created: one local draft. External writes: none. Undo: discard draft before approving.</p>
            <div class="doc-actions">
              <button class="primary-action" type="button" data-target="receipt">Approve Work write</button>
              <button class="secondary-action" type="button" data-target="receipt">Review receipt</button>
              <button class="secondary-action" type="button" data-target="draft">Open draft</button>
            </div>
          </article>
        </section>
"""


def _editor_document() -> str:
    bc = _breadcrumb(
        [("Company", "company"), ("Public Policy", "pp"), ("Housing", "h"), ("Rent Control", "rc")],
        action_label="View receipt", action_target="receipt",
    )
    return f"""
        <section class="doc-surface draft-surface" data-doc="draft">
          {bc}
          <div class="doc-meta">
          <span class="doc-state badge write">Draft</span>
          <span class="doc-chip">Owner Rafa</span>
          <span class="doc-chip">Reviewer Diego</span>
          <span class="doc-chip">Maya can write only after approval</span>
          <span class="doc-chip">Rent Control child path recommended</span>
        </div>
        <article class="document">
          <h1>Public comment on HB 2148</h1>
          <p>
            Maya prepared this draft from the selected bill text and committee memo inside the
            /Public Policy / Housing workbench. The draft supports expedited review for infill
            housing while preserving public notice, affordability reporting, and appeal clarity.
          </p>
          <h2>Recommended position</h2>
          <p>
            Support with amendments. The bill reduces duplicative local process, but the current
            language should name the approval timeline, require a public implementation dashboard,
            and preserve an exception path for safety findings.
          </p>
          <h2>Workbench boundary</h2>
          <p>
            I used only the two selected Housing sources. I did not inspect the private mailbox,
            Legal privileged notes, or sibling workbench files. Parent policy standards shaped the
            tone, but source access was not inherited automatically.
          </p>
          <h2>Suggested language</h2>
          <p>
            The city supports faster housing approvals when applicants meet published objective
            standards. We recommend adding a quarterly reporting requirement and a clear notice
            period before automatic approval begins.
          </p>
          <h2>Approval note</h2>
          <p>
            I have not submitted this comment, emailed anyone, changed any source file, or written
            to an external system. If approved, I will save one draft file to the Housing Work folder.
          </p>
          <div class="doc-actions">
            <button class="primary-action" type="button" data-target="checkin">Approve Work write</button>
            <button class="secondary-action" type="button">Request changes</button>
            <button class="secondary-action" type="button" data-target="receipt">Review receipt</button>
          </div>
        </article>
        </section>
"""


def _editor_source() -> str:
    bc = _breadcrumb(
        [("Company", "company"), ("Public Policy", "pp"), ("Housing", "h"), ("Sources", "src")],
        action_label="Open draft", action_target="draft",
    )
    sources = [
        ("read", "Bill text", "HB 2148 zoning modernization", "readable",
         "State legislature, introduced 2025. Authorizes by-right approval for qualifying infill housing developments that meet published objective standards."),
        ("read", "Committee memo", "Housing committee staff analysis", "readable",
         "Staff comparison of similar bills in peer cities, with projected permit-timeline reductions and a section on affordability reporting gaps."),
        ("inherit", "Public Policy style rules", "Inherited standards", "inherited",
         "Inherited writing and citation standards from the parent /Public Policy workbench. Explicitly allowed to inherit; not a source file."),
        ("blocked", "Private mailbox", "Not selected for Maya", "blocked",
         "Constituent and internal mail. Not selected as a readable source for Maya; no access granted in this workbench."),
        ("blocked", "Legal privileged notes", "Sibling path; no access", "blocked",
         "Belongs to the sibling /Legal workbench. Child and sibling Palaris cannot automatically read sibling or parent paths."),
        ("write", "Work folder", "Write only after approval", "write after approval",
         "Maya may save one approved draft file here. Write permission does not silently inherit; each write waits for human approval."),
    ]
    rows = "\n".join(
        f'            <tr class="src-table-row perm-{tone}">'
        f'<td><span class="perm-dot {tone}"></span> {_e(title)}</td>'
        f'<td><span class="perm-badge badge {tone}">{_e(meta)}</span></td>'
        f'<td>{_e(note)}</td></tr>'
        for tone, title, _desc, meta, note in sources
    )
    return f"""
        <section class="doc-surface source-surface" data-doc="source" hidden>
          {bc}
          <div class="doc-meta">
            <span class="doc-state badge read">Source</span>
            <span class="doc-chip">Workbench: Public Policy / Housing</span>
            <span class="doc-chip">Palari: Maya</span>
          </div>
          <article class="document source-doc">
            <h1>Sources &amp; permissions</h1>
            <p>Maya's readable, inherited, blocked, and writable sources inside the Housing workbench. Permissions are scoped to this path and do not silently inherit to children.</p>
            <table class="source-table">
              <thead><tr><th>Source</th><th>Permission</th><th>Detail</th></tr></thead>
              <tbody>
{rows}
              </tbody>
            </table>
            <div class="perm-legend perm-legend-inline">
              <span><i class="perm-dot read"></i>readable</span>
              <span><i class="perm-dot inherit"></i>inherited</span>
              <span><i class="perm-dot blocked"></i>blocked</span>
              <span><i class="perm-dot write"></i>write after approval</span>
            </div>
          </article>
        </section>
"""


def _editor_receipt() -> str:
    bc = _breadcrumb(
        [("Company", "company"), ("Public Policy", "pp"), ("Housing", "h"), ("Receipt", "r")],
        action_label="Open draft", action_target="draft",
    )
    return f"""
        <section class="doc-surface receipt-surface" data-doc="receipt" hidden>
          {bc}
          <div class="doc-meta">
            <span class="doc-state badge read">Receipt</span>
            <span class="doc-chip">Palari: Maya</span>
            <span class="doc-chip">Workbench: Public Policy / Housing</span>
            <span class="doc-chip">Task: public comment draft</span>
          </div>
          <article class="document receipt-doc">
            <h1>Receipt - public comment draft</h1>
            <p>A complete account of what Maya used, created, did not do, wrote externally, and can undo for this task. No external writes occurred; the Work write is waiting for approval.</p>
            <dl class="receipt-document-grid">
              <div><dt>Used</dt><dd>Bill text (HB 2148); committee memo (Housing staff analysis); inherited Public Policy style rules.</dd></div>
              <div><dt>Created</dt><dd>One local public comment draft artifact.</dd></div>
              <div><dt>Did not do</dt><dd>No email, no filing, no source edits, no Legal access, no child Palari creation.</dd></div>
              <div><dt>External writes</dt><dd>None. Work write is waiting for approval.</dd></div>
              <div><dt>Undo</dt><dd>Discard the local draft before approving the Work write.</dd></div>
            </dl>
            <div class="doc-actions">
              <button class="secondary-action" type="button" data-target="draft">Open draft</button>
              <button class="secondary-action" type="button" data-target="checkin">Open in check-in</button>
              <button class="secondary-action" type="button">Copy receipt</button>
            </div>
          </article>
        </section>
"""


def _editor_workitem() -> str:
    bc = _breadcrumb(
        [("Company", "company"), ("Public Policy", "pp"), ("Housing", "h"), ("Work item", "wi")],
        action_label="Open draft", action_target="draft",
    )
    return f"""
        <section class="doc-surface workitem-surface" data-doc="workitem" hidden>
          {bc}
          <div class="doc-meta">
            <span class="doc-state badge blocked">Needs human decision</span>
            <span class="doc-chip">Owner Rafa</span>
            <span class="doc-chip">Reviewer Diego</span>
            <span class="doc-chip">Palari Maya</span>
          </div>
          <article class="document workitem-doc">
            <h1>Work item: public comment draft</h1>
            <dl class="kv">
              <div><dt>Status</dt><dd><span class="badge blocked">Needs human decision</span></dd></div>
              <div><dt>Next action</dt><dd>Rafa reviews, Diego comments, then approve one Work write.</dd></div>
              <div><dt>Risk</dt><dd>R2 - local policy draft</dd></div>
              <div><dt>Workbench</dt><dd>/Public Policy / Housing</dd></div>
              <div><dt>Readable sources</dt><dd>Bill text, committee memo</dd></div>
              <div><dt>Blocked sources</dt><dd>Private mailbox, Legal privileged notes</dd></div>
              <div><dt>Write boundary</dt><dd>Work folder, only after approval</dd></div>
            </dl>
            <div class="doc-actions">
              <button class="primary-action" type="button" data-target="checkin">Approve Work write</button>
              <button class="secondary-action" type="button" data-target="receipt">Review receipt</button>
              <button class="secondary-action" type="button" data-target="draft">Open draft</button>
            </div>
          </article>
        </section>
"""


def _secondary_sidebar() -> str:
    return """
  <div class="sidebar-header">
    <span class="sidebar-title" id="sec-sidebar-title">Maya - Chat</span>
    <div class="sidebar-actions">
      <button class="icon-btn" type="button" aria-label="More">⋯</button>
    </div>
  </div>
  <div class="sec-tabs" role="tablist">
    <button class="sec-tab is-active" type="button" data-sec="chat">Chat</button>
    <button class="sec-tab" type="button" data-sec="task">Task</button>
    <button class="sec-tab" type="button" data-sec="receipt">Receipt</button>
    <button class="sec-tab" type="button" data-sec="changes">Changes</button>
    <button class="sec-tab" type="button" data-sec="authority">Authority</button>
  </div>
  <div class="sec-body">
    <section class="sec-panel is-active" data-sec-panel="chat" data-mobile-pane="chat">
      <div class="chat-thread">
        <div class="message user">Can you turn the zoning bill and staff memo into a public comment?</div>
        <div class="message palari">Yes. I can use the bill text and committee memo in Housing. I cannot read Legal notes or the private mailbox.</div>
        <div class="message palari">I made a local draft and held the Work write for approval.</div>
        <div class="message palari subtle">Rent Control may deserve a child Palari, but I will not create it unless you decide.</div>
      </div>
      <div class="chat-composer">
        <input type="text" placeholder="Message Maya in Housing" aria-label="Message Maya">
        <button class="primary-action compact" type="button">Send</button>
      </div>
    </section>
    <section class="sec-panel" data-sec-panel="task" data-mobile-pane="task" hidden>
      <h3 class="sec-heading">Active task</h3>
      <p class="sec-title">Prepare public comment draft</p>
      <dl class="kv">
        <div><dt>Status</dt><dd><span class="badge blocked">Needs human decision</span></dd></div>
        <div><dt>Next action</dt><dd>Rafa reviews, Diego comments, then approve one Work write.</dd></div>
        <div><dt>Risk</dt><dd>R2 - local policy draft</dd></div>
        <div><dt>Workbench</dt><dd>/Public Policy / Housing</dd></div>
      </dl>
      <button class="primary-action" type="button" data-target="draft">Open draft</button>
    </section>
    <section class="sec-panel" data-sec-panel="receipt" data-mobile-pane="receipt" hidden>
      <h3 class="sec-heading">Receipt</h3>
      <dl class="receipt-grid">
        <div><dt>Used</dt><dd>Bill text; committee memo; inherited style rules.</dd></div>
        <div><dt>Created</dt><dd>One local public comment draft.</dd></div>
        <div><dt>Did not do</dt><dd>No email, no filing, no source edits, no Legal access.</dd></div>
        <div><dt>External writes</dt><dd>None. Work write is waiting for approval.</dd></div>
        <div><dt>Undo</dt><dd>Discard draft before approving the Work write.</dd></div>
      </dl>
      <button class="secondary-action" type="button">Copy receipt</button>
    </section>
    <section class="sec-panel" data-sec-panel="changes" hidden>
      <h3 class="sec-heading">Changes &amp; history</h3>
      <ol class="history">
        <li><span class="ts">10:42</span> Read selected bill text.</li>
        <li><span class="ts">10:44</span> Compared committee memo findings.</li>
        <li><span class="ts">10:49</span> Created local draft artifact.</li>
        <li><span class="ts">10:51</span> Waiting for human approval.</li>
      </ol>
      <button class="secondary-action" type="button" data-target="checkin">View all</button>
    </section>
    <section class="sec-panel" data-sec-panel="authority" hidden>
      <h3 class="sec-heading">Authority</h3>
      <ul class="rule-list">
        <li>Rafa owns the Housing workbench.</li>
        <li>Diego is delegated reviewer for this task.</li>
        <li>Maya can draft locally and request one approved Work write.</li>
        <li>Clara can support only if the Rent Control child path is created.</li>
      </ul>
      <button class="secondary-action" type="button">Edit rules</button>
    </section>
  </div>
"""


def _bottom_panel() -> str:
    statuses = [
        ("active", "Active", "Council briefing memo", "Public Policy / Housing", "Maya"),
        ("waiting", "Waiting", "Rent Control source setup", "Public Policy / Housing / Rent Control", "Clara suggested"),
        ("blocked", "Blocked", "Legal risk addendum", "Legal", "No Palari access"),
        ("review", "Needs review", "Public comment draft", "Public Policy / Housing", "Diego"),
        ("human", "Needs human decision", "Approve Work write", "Public Policy / Housing", "Rafa"),
        ("receipt", "Receipt-ready", "Permit comparison table", "Public Policy / Housing", "Maya"),
        ("closed", "Closed", "Product launch notes summary", "Product", "Sofia"),
    ]
    rows = "\n".join(
        f'        <tr class="panel-row st-{tone}">'
        f'<td><span class="panel-status badge {tone}">{_e(label)}</span></td>'
        f'<td class="panel-title">{_e(title)}</td>'
        f'<td class="panel-path">{_e(path)}</td>'
        f'<td class="panel-owner">{_e(owner)}</td>'
        f'<td class="panel-cell"><button class="row-action" type="button" data-target="receipt">Open</button></td>'
        f'</tr>'
        for tone, label, title, path, owner in statuses
    )
    return f"""
    <section class="bottom-panel pane" data-mobile-pane="checkin" data-panel="checkin">
      <div class="panel-header">
        <div class="panel-tabs" role="tablist">
          <button class="panel-tab is-active" type="button" data-panel-tab="checkin">Work check-in</button>
          <button class="panel-tab" type="button" data-panel-tab="problems">Problems</button>
          <button class="panel-tab" type="button" data-panel-tab="output">Output</button>
        </div>
        <div class="panel-actions">
          <span class="panel-count">7 items</span>
          <button class="icon-btn" type="button" aria-label="Filter">Filter</button>
          <button class="icon-btn" type="button" aria-label="Collapse panel" data-target="explorer">▾</button>
        </div>
      </div>
      <div class="panel-body" data-panel-body="checkin">
        <table class="panel-table">
          <thead>
            <tr><th>Status</th><th>Work</th><th>Path</th><th>Owner / Palari</th><th></th></tr>
          </thead>
          <tbody>
{rows}
          </tbody>
        </table>
      </div>
    </section>
"""


def _status_bar() -> str:
    return """
  <footer class="status-bar" aria-label="Status bar">
    <span class="status-item status-accent"><span class="status-dot"></span> Maya</span>
    <span class="status-item">Path: Public Policy / Housing</span>
    <span class="status-item">Read: bill text, committee memo</span>
    <span class="status-item status-warn">Write: Work folder (after approval)</span>
    <span class="status-spacer"></span>
    <span class="status-item">Owner: Rafa</span>
    <span class="status-item">Reviewer: Diego</span>
    <span class="status-item">Rent Control: child Palari recommended</span>
  </footer>
"""


def _mobile_nav() -> str:
    items = [
        ("home", "Home"),
        ("explorer", "Explorer"),
        ("chat", "Chat"),
        ("task", "Task"),
        ("receipt", "Receipt"),
        ("draft", "Draft"),
        ("checkin", "Check-In"),
    ]
    buttons = "\n".join(
        f'<button class="mobile-tab {"is-active" if key == "explorer" else ""}" '
        f'type="button" data-target="{_e(key)}">{_e(label)}</button>'
        for key, label in items
    )
    return f'<nav class="mobile-nav" aria-label="Mobile workspace panes">{buttons}</nav>'


# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #

def _styles() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f3f4f6;
  --titlebar-bg: #2c2c2c;
  --titlebar-fg: #cccccc;
  --activity-bg: #2c2c2c;
  --activity-fg: #858585;
  --activity-active: #ffffff;
  --sidebar-bg: #f3f3f3;
  --sidebar-fg: #3b3b3b;
  --editor-bg: #ffffff;
  --editor-fg: #323233;
  --panel-bg: #f3f3f3;
  --status-bg: #007acc;
  --status-fg: #ffffff;
  --ink: #323233;
  --ink-2: #4d4d4d;
  --muted: #6c6c6c;
  --line: #d4d4d4;
  --line-soft: #e5e5e5;
  --line-strong: #c0c0c0;
  --brand: #007acc;
  --brand-2: #1f9cf0;
  /* permission colors */
  --perm-read: #2da44e;
  --perm-read-bg: #dafbe1;
  --perm-inherit: #0969da;
  --perm-inherit-bg: #ddf4ff;
  --perm-blocked: #cf222e;
  --perm-blocked-bg: #ffebe9;
  --perm-write: #9a6700;
  --perm-write-bg: #fff8c5;
  font-size: 13px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Segoe WPC", system-ui,
    "Ubuntu", "Droid Sans", sans-serif;
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  height: 100%;
}

body {
  background: var(--bg);
  color: var(--ink);
  overflow: hidden;
}

button { font: inherit; color: inherit; }
ul, ol { margin: 0; padding: 0; list-style: none; }

/* ---------- Title bar ---------- */
.titlebar {
  height: 35px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.6rem;
  background: var(--titlebar-bg);
  color: var(--titlebar-fg);
  font-size: 12px;
  border-bottom: 1px solid #1a1a1a;
  flex-shrink: 0;
}
.titlebar-left { display: flex; align-items: center; gap: 0.4rem; }
.tb-icon {
  width: 18px; height: 18px; border: 0; border-radius: 2px;
  background: var(--brand); color: #fff; font-weight: 700; font-size: 11px;
}
.tb-product { font-weight: 600; color: #fff; }
.tb-sep { color: #6a6a6a; }
.tb-cmd {
  border: 1px solid #414141; background: #1a1a1a; color: var(--titlebar-fg);
  padding: 2px 8px; border-radius: 2px; cursor: pointer; font-size: 12px;
}
.tb-cmd:hover { background: #2a2d2d; }
.tb-center { flex: 1; display: flex; justify-content: center; }
.tb-search {
  width: min(440px, 40vw); height: 24px; border: 1px solid #414141;
  border-radius: 2px; background: #1a1a1a; color: #6a6a6a;
  display: flex; align-items: center; padding: 0 8px; font-size: 11px;
}
.tb-right { display: flex; align-items: center; gap: 0.6rem; }
.tb-path { color: #cccccc; }
.tb-user {
  width: 20px; height: 20px; border-radius: 50%; background: var(--brand);
  color: #fff; display: grid; place-items: center; font-size: 11px; font-weight: 600;
}

/* ---------- Workbench grid ---------- */
.workbench-grid {
  --primary-w: 270px;
  --secondary-w: 320px;
  display: grid;
  grid-template-columns: 48px var(--primary-w) 4px minmax(0, 1fr) 4px var(--secondary-w);
  height: calc(100vh - 35px - 22px);
  min-height: 0;
}

/* ---------- Splitters ---------- */
.splitter {
  background: transparent;
  cursor: col-resize;
  position: relative;
  z-index: 5;
  min-width: 4px;
}
.splitter::after {
  content: ""; position: absolute; top: 0; bottom: 0; left: 1px; width: 1px;
  background: var(--line);
}
.splitter:hover::after, .splitter.is-dragging::after { background: var(--brand); width: 2px; left: 1px; }
.splitter.is-dragging { background: rgba(0,122,204,0.08); }

/* ---------- Activity bar ---------- */
.activity-bar {
  background: var(--activity-bg);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  min-height: 0;
  overflow: hidden;
}
.activity-stack { display: flex; flex-direction: column; }
.activity-foot { margin-top: auto; }
.activity-btn {
  position: relative;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 2px; height: 48px; border: 0; background: transparent;
  color: var(--activity-fg); cursor: pointer; padding: 0;
}
.activity-glyph {
  width: 24px; height: 24px; display: grid; place-items: center;
  font-size: 13px; font-weight: 700; border: 1px solid transparent; border-radius: 3px;
}
.activity-label { font-size: 9px; letter-spacing: 0.02em; }
.activity-btn:hover { color: var(--activity-active); }
.activity-btn:hover .activity-glyph { border-color: #4a4a4a; }
.activity-btn.is-active { color: var(--activity-active); }
.activity-btn.is-active::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 2px;
  background: var(--activity-active);
}
.activity-btn.is-active .activity-glyph { border-color: #6a6a6a; }
.activity-foot .activity-label { display: none; }

/* ---------- Sidebars (shared) ---------- */
.primary-sidebar,
.secondary-sidebar {
  background: var(--sidebar-bg);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.secondary-sidebar { border-right: 0; border-left: 1px solid var(--line); }

.sidebar-header {
  height: 35px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 0.6rem 0 0.8rem;
  border-bottom: 1px solid var(--line-soft);
}
.sidebar-title {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--ink-2);
}
.sidebar-actions { display: flex; gap: 2px; }
.icon-btn {
  width: 22px; height: 22px; border: 0; background: transparent;
  color: var(--muted); cursor: pointer; border-radius: 3px; font-size: 13px;
}
.icon-btn:hover { background: rgba(0,0,0,0.06); color: var(--ink); }

.sidebar-body { overflow-y: auto; min-height: 0; flex: 1; padding: 0.25rem 0; }

/* ---------- Tree views ---------- */
.tree-view { margin-bottom: 0.25rem; }
.tree-header {
  width: 100%; display: flex; align-items: center; gap: 0.3rem;
  padding: 4px 12px; border: 0; background: transparent;
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--ink-2); cursor: pointer;
}
.tree-header:hover { background: rgba(0,0,0,0.04); }
.tree-header .chevron { font-size: 9px; width: 10px; }
.tree-count { margin-left: auto; color: var(--muted); font-weight: 500; }

.chevron { display: inline-grid; place-items: center; width: 12px; color: var(--muted); font-size: 10px; }

.tree { padding-right: 6px; }
.tree-row {
  display: flex; align-items: center; gap: 0.25rem;
  height: 22px; padding: 0 6px 0 4px; border-radius: 2px;
  font-size: 13px; color: var(--ink); cursor: pointer; white-space: nowrap;
}
.tree-row:hover { background: rgba(0,0,0,0.04); }
.tree-row.is-selected { background: #e8e8e8; }
.tree-icon { color: var(--muted); font-size: 11px; width: 14px; text-align: center; }
.tree-label { overflow: hidden; text-overflow: ellipsis; }
.tree-meta { margin-left: auto; color: var(--muted); font-size: 11px; }
.tree ol { padding-left: 14px; }
.tree > li > .tree-row.depth-0 { font-weight: 600; }

/* permission badges */
.badge { display: inline-block; padding: 0 5px; border-radius: 2px; font-size: 10px; font-weight: 600; line-height: 16px; }
.badge.read { color: var(--perm-read); background: var(--perm-read-bg); }
.badge.inherit { color: var(--perm-inherit); background: var(--perm-inherit-bg); }
.badge.blocked { color: var(--perm-blocked); background: var(--perm-blocked-bg); }
.badge.write { color: var(--perm-write); background: var(--perm-write-bg); }
.badge.active { color: var(--perm-read); background: var(--perm-read-bg); }
.badge.waiting { color: var(--perm-write); background: var(--perm-write-bg); }
.badge.review { color: var(--perm-inherit); background: var(--perm-inherit-bg); }
.badge.human { color: var(--perm-blocked); background: var(--perm-blocked-bg); }
.badge.receipt { color: var(--perm-read); background: var(--perm-read-bg); }
.badge.closed { color: var(--muted); background: #eaeaea; }
.panel-row.st-closed { border-left: 2px solid var(--line-strong); }

/* ---------- Sources list ---------- */
.src-list { padding: 0 6px; }
.src-row {
  display: flex; align-items: center; gap: 0.4rem;
  padding: 4px 6px; border-radius: 2px; cursor: pointer;
  border-left: 2px solid transparent;
}
.src-row:hover { background: rgba(0,0,0,0.04); }
.src-row.perm-read { border-left-color: var(--perm-read); }
.src-row.perm-inherit { border-left-color: var(--perm-inherit); }
.src-row.perm-blocked { border-left-color: var(--perm-blocked); }
.src-row.perm-write { border-left-color: var(--perm-write); }
.perm-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.perm-dot.read, .perm-read .perm-dot { background: var(--perm-read); }
.perm-dot.inherit, .perm-inherit .perm-dot { background: var(--perm-inherit); }
.perm-dot.blocked, .perm-blocked .perm-dot { background: var(--perm-blocked); }
.perm-dot.write, .perm-write .perm-dot { background: var(--perm-write); }
.src-name { font-size: 13px; flex-shrink: 0; max-width: 9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.src-note { font-size: 11px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.perm-badge { font-size: 10px; font-weight: 600; flex-shrink: 0; }
.perm-read .perm-badge { color: var(--perm-read); }
.perm-inherit .perm-badge { color: var(--perm-inherit); }
.perm-blocked .perm-badge { color: var(--perm-blocked); }
.perm-write .perm-badge { color: var(--perm-write); }

.perm-legend {
  display: flex; flex-wrap: wrap; gap: 0.4rem 0.7rem;
  padding: 6px 12px; font-size: 10px; color: var(--muted);
}
.perm-legend span { display: inline-flex; align-items: center; gap: 3px; }
.perm-legend i.perm-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; }

/* ---------- People ---------- */
.people-list, .people-row { padding: 0 6px; }
.people-row {
  display: flex; align-items: center; gap: 0.4rem;
  padding: 4px 6px; border-radius: 2px; font-size: 13px;
}
.people-row:hover { background: rgba(0,0,0,0.04); }
.avatar {
  width: 18px; height: 18px; border-radius: 50%; flex-shrink: 0;
  background: var(--brand); color: #fff; display: grid; place-items: center;
  font-size: 10px; font-weight: 700;
}
.people-name { font-weight: 500; }
.people-role { color: var(--muted); font-size: 11px; margin-left: auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ---------- Editor region ---------- */
.editor-region {
  display: flex; flex-direction: column; min-width: 0; min-height: 0;
  background: var(--editor-bg);
}
.editor-area {
  flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden;
}
.editor-tabs {
  display: flex; height: 35px; flex-shrink: 0;
  background: var(--sidebar-bg); border-bottom: 1px solid var(--line);
  overflow-x: auto; scrollbar-width: thin;
}
.editor-tab {
  display: flex; align-items: center; gap: 0.3rem;
  padding: 0 0.7rem; height: 100%; border: 0; border-right: 1px solid var(--line-soft);
  background: transparent; color: var(--ink-2); cursor: pointer;
  font-size: 13px; white-space: nowrap;
}
.editor-tab:hover { background: rgba(0,0,0,0.04); }
.editor-tab.is-active { background: var(--editor-bg); color: var(--ink); position: relative; }
.editor-tab.is-active::before {
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: var(--brand);
}
.tab-close { color: var(--muted); font-size: 14px; }
.tab-close:hover { color: var(--ink); }

.breadcrumbs {
  display: flex; align-items: center; gap: 0.25rem;
  height: 22px; flex-shrink: 0; padding: 0 0.7rem;
  background: var(--editor-bg); border-bottom: 1px solid var(--line-soft);
  font-size: 12px; color: var(--ink-2); overflow: hidden;
}
.breadcrumbs span { white-space: nowrap; }
.bc-sep { color: var(--muted); }
.bc-current { color: var(--ink); }
.bc-spacer { flex: 1; }
.crumb-action {
  border: 0; background: transparent; color: var(--brand); cursor: pointer;
  font-size: 12px; padding: 0 4px;
}
.crumb-action:hover { text-decoration: underline; }

.editor-content {
  flex: 1; overflow-y: auto; min-height: 0;
}
.doc-surface { display: none; }
.doc-surface.is-active { display: block; }
.home-surface .doc-meta { margin: 0; border-bottom: 1px solid var(--line-soft); }

.home-grid {
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 1.4rem; max-width: 64rem; margin: 0 auto; padding: 1.2rem 1.4rem 3rem;
}
.home-col { min-width: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.surface-h {
  margin: 0.6rem 0 0.3rem; font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--ink-2);
}
.home-rows { display: flex; flex-direction: column; gap: 0.2rem; }
.home-row {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 5px 8px; border-radius: 2px; border-left: 2px solid transparent;
  cursor: pointer; font-size: 13px;
}
.home-row:hover { background: rgba(0,0,0,0.04); }
.home-row.is-active { background: #e8e8e8; border-left-color: var(--brand); }
.home-path { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.home-lead { color: var(--muted); font-size: 12px; margin-left: auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.home-row .badge { flex-shrink: 0; }

.reco-card {
  margin-top: 0.8rem; padding: 0.7rem 0.8rem; border: 1px solid var(--line);
  border-left: 3px solid var(--perm-write); border-radius: 2px; background: #fff;
}
.reco-card h3 { margin: 0 0 0.3rem; font-size: 12px; font-weight: 700; color: var(--perm-write); text-transform: uppercase; letter-spacing: 0.04em; }
.reco-card p { margin: 0 0 0.3rem; font-size: 12px; color: var(--ink-2); line-height: 1.45; }
.reco-card .doc-actions { margin-top: 0.6rem; }

.checkin-doc { max-width: 48rem; }

.doc-meta {
  display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
  padding: 0.55rem 1rem; border-bottom: 1px solid var(--line-soft);
  background: var(--sidebar-bg);
}
.doc-state { font-size: 11px; }
.doc-chip {
  font-size: 11px; color: var(--muted); border: 1px solid var(--line);
  background: #fff; padding: 1px 6px; border-radius: 2px;
}
.document {
  max-width: 52rem; margin: 0 auto; padding: 1.4rem 1.6rem 3rem;
  line-height: 1.6; color: var(--editor-fg);
}
.document h1 { margin: 0 0 0.8rem; font-size: 1.5rem; font-weight: 600; }
.document h2 {
  margin: 1.4rem 0 0.4rem; font-size: 0.82rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.04em; color: var(--brand);
}
.document p { margin: 0 0 0.75rem; color: var(--ink-2); }
.doc-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1.4rem; }

/* source / receipt / workitem document surfaces */
.source-table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 0.5rem 0; }
.source-table th {
  text-align: left; font-size: 11px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.03em; padding: 5px 8px;
  border-bottom: 1px solid var(--line); background: var(--sidebar-bg);
}
.source-table td { padding: 6px 8px; border-bottom: 1px solid var(--line-soft); vertical-align: top; }
.src-table-row { border-left: 2px solid transparent; }
.src-table-row.perm-read { border-left-color: var(--perm-read); }
.src-table-row.perm-inherit { border-left-color: var(--perm-inherit); }
.src-table-row.perm-blocked { border-left-color: var(--perm-blocked); }
.src-table-row.perm-write { border-left-color: var(--perm-write); }
.src-table-row .perm-dot { display: inline-block; margin-right: 4px; vertical-align: middle; }
.src-table-row td:last-child { color: var(--ink-2); font-size: 12px; }
.perm-legend-inline { margin-top: 0.8rem; padding: 0; }

.receipt-document-grid { display: grid; gap: 0.5rem; margin: 0.5rem 0 0; }
.receipt-document-grid div { border: 1px solid var(--line); border-left: 3px solid var(--brand); border-radius: 2px; padding: 6px 9px; background: #fff; }
.receipt-document-grid dt { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--brand); }
.receipt-document-grid dd { margin: 3px 0 0; font-size: 13px; color: var(--ink-2); line-height: 1.5; }

.source-doc, .receipt-doc, .workitem-doc { max-width: 52rem; }
.workitem-doc .kv { font-size: 13px; }

.primary-action {
  border: 0; background: var(--brand); color: #fff;
  padding: 5px 12px; border-radius: 2px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.primary-action:hover { background: #0062a3; }
.primary-action.compact { padding: 4px 10px; font-size: 12px; }
.secondary-action {
  border: 1px solid var(--line-strong); background: #fff; color: var(--ink);
  padding: 4px 12px; border-radius: 2px; font-size: 13px; cursor: pointer;
}
.secondary-action:hover { background: var(--line-soft); }

/* ---------- Secondary sidebar panels ---------- */
.sec-tabs {
  display: flex; height: 35px; flex-shrink: 0;
  border-bottom: 1px solid var(--line); background: var(--sidebar-bg);
  overflow-x: auto;
}
.sec-tab {
  border: 0; border-bottom: 1px solid transparent; background: transparent;
  color: var(--muted); cursor: pointer; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.03em; padding: 0 0.7rem; white-space: nowrap;
}
.sec-tab:hover { color: var(--ink); }
.sec-tab.is-active { color: var(--ink); border-bottom-color: var(--brand); }
.sec-body { flex: 1; overflow-y: auto; min-height: 0; }
.sec-panel { display: none; padding: 0.7rem; flex-direction: column; gap: 0.6rem; }
.sec-panel.is-active { display: flex; }
.sec-heading { margin: 0; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-2); }
.sec-title { margin: 0; font-size: 14px; font-weight: 600; }

.chat-thread { display: flex; flex-direction: column; gap: 0.4rem; }
.message {
  padding: 6px 9px; font-size: 13px; line-height: 1.4; border-radius: 3px;
  border: 1px solid var(--line); background: #fff; max-width: 92%;
}
.message.user { align-self: flex-end; background: var(--brand); color: #fff; border-color: var(--brand); }
.message.palari { align-self: flex-start; }
.message.subtle { border-left: 3px solid var(--perm-write); background: var(--perm-write-bg); }
.chat-composer { display: flex; gap: 0.35rem; margin-top: 0.3rem; }
.chat-composer input {
  flex: 1; min-width: 0; border: 1px solid var(--line); border-radius: 2px;
  padding: 5px 8px; font-size: 13px;
}

.kv { display: grid; gap: 0.35rem; margin: 0; }
.kv div { display: grid; grid-template-columns: 5.5rem minmax(0,1fr); gap: 0.4rem; }
.kv dt { font-size: 11px; color: var(--muted); }
.kv dd { margin: 0; font-size: 12px; color: var(--ink-2); overflow-wrap: anywhere; }

.receipt-grid { display: grid; gap: 0.35rem; margin: 0; }
.receipt-grid div { border: 1px solid var(--line); border-radius: 2px; padding: 5px 7px; background: #fff; }
.receipt-grid dt { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--brand); }
.receipt-grid dd { margin: 2px 0 0; font-size: 12px; color: var(--ink-2); }

.history { display: flex; flex-direction: column; gap: 0.3rem; }
.history li { font-size: 12px; color: var(--ink-2); padding: 3px 0; border-bottom: 1px solid var(--line-soft); }
.history .ts { color: var(--muted); font-variant-numeric: tabular-nums; margin-right: 0.4rem; }

.rule-list { display: flex; flex-direction: column; gap: 0.3rem; }
.rule-list li { font-size: 12px; color: var(--ink-2); padding-left: 0.9rem; position: relative; }
.rule-list li::before { content: "•"; position: absolute; left: 0.2rem; color: var(--muted); }

/* ---------- Bottom panel ---------- */
.bottom-panel {
  flex-shrink: 0; height: 200px; display: flex; flex-direction: column;
  background: var(--panel-bg); border-top: 1px solid var(--line); min-height: 0;
}
.panel-header {
  height: 35px; flex-shrink: 0; display: flex; align-items: center; justify-content: space-between;
  padding: 0 0.4rem 0 0.5rem; border-bottom: 1px solid var(--line); background: var(--sidebar-bg);
}
.panel-tabs { display: flex; height: 100%; }
.panel-tab {
  border: 0; border-bottom: 1px solid transparent; background: transparent;
  color: var(--muted); cursor: pointer; font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.04em; padding: 0 0.7rem; height: 100%;
}
.panel-tab:hover { color: var(--ink); }
.panel-tab.is-active { color: var(--ink); border-bottom-color: var(--brand); }
.panel-actions { display: flex; align-items: center; gap: 0.4rem; }
.panel-count { font-size: 11px; color: var(--muted); }
.panel-body { flex: 1; overflow: auto; min-height: 0; }

.panel-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.panel-table thead th {
  text-align: left; font-size: 11px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.03em; padding: 4px 10px;
  border-bottom: 1px solid var(--line); background: var(--panel-bg); position: sticky; top: 0;
}
.panel-table td { padding: 4px 10px; border-bottom: 1px solid var(--line-soft); vertical-align: middle; }
.panel-row:hover { background: rgba(0,0,0,0.03); }
.panel-row.st-blocked, .panel-row.st-human { border-left: 2px solid var(--perm-blocked); }
.panel-row.st-waiting { border-left: 2px solid var(--perm-write); }
.panel-row.st-review { border-left: 2px solid var(--perm-inherit); }
.panel-row.st-active, .panel-row.st-receipt { border-left: 2px solid var(--perm-read); }
.panel-status { white-space: nowrap; }
.panel-title { color: var(--ink); font-weight: 500; }
.panel-path, .panel-owner { color: var(--muted); white-space: nowrap; }
.row-action { border: 0; background: transparent; color: var(--brand); cursor: pointer; font-size: 12px; padding: 0; }
.row-action:hover { text-decoration: underline; }

/* ---------- Status bar ---------- */
.status-bar {
  height: 22px; flex-shrink: 0; display: flex; align-items: center; gap: 0.3rem;
  padding: 0 0.5rem; background: var(--status-bg); color: var(--status-fg);
  font-size: 12px; overflow: hidden;
}
.status-item { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; padding: 0 4px; }
.status-item:hover { background: rgba(255,255,255,0.12); cursor: default; }
.status-accent { font-weight: 600; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #73c991; }
.status-warn { background: rgba(255,255,255,0.18); }
.status-spacer { flex: 1; }

/* ---------- Mobile ---------- */
.mobile-nav, .mobile-back { display: none; }

.pane { display: flex; }

/* ---------- Mobile single-pane ---------- */
@media (max-width: 880px) {
  body { overflow: auto; }
  body.workbench { overflow: hidden; }
  .titlebar { height: 40px; padding: 0 0.5rem; }
  .tb-center, .tb-search { display: none; }
  .tb-cmd { font-size: 11px; max-width: 40vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tb-right .tb-path { display: none; }

  .workbench-grid {
    display: block; height: calc(100vh - 40px - 0px);
    position: relative;
  }
  .activity-bar { display: none; }
  .status-bar { display: none; }
  .splitter { display: none; }

  .primary-sidebar,
  .secondary-sidebar,
  .editor-region { display: none; }

  /* only the active mobile pane shows, full width */
  .pane { display: none; }
  .pane.is-mobile-active { display: flex; flex-direction: column; height: calc(100vh - 40px - 56px); min-height: 0; }

  .primary-sidebar.is-mobile-active,
  .secondary-sidebar.is-mobile-active { border: 0; }
  .editor-region.is-mobile-active {
    display: flex; flex-direction: column;
    height: calc(100vh - 40px - 56px); min-height: 0;
  }

  .bottom-panel { height: auto; flex: 1; }
  .panel-body { overflow: auto; }

  .sidebar-body, .sec-body, .editor-content { -webkit-overflow-scrolling: touch; }

  .mobile-nav {
    display: grid; grid-template-columns: repeat(7, minmax(0,1fr));
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 40;
    height: 56px; background: var(--sidebar-bg); border-top: 1px solid var(--line);
  }
  .mobile-tab {
    border: 0; background: transparent; color: var(--muted); cursor: pointer;
    font-size: 10px; font-weight: 600; padding: 4px 2px; min-width: 0;
    display: flex; align-items: center; justify-content: center; text-align: center;
    overflow: hidden;
  }
  .mobile-tab.is-active { color: var(--brand); border-top: 2px solid var(--brand); }

  .document { padding: 1rem; }
  .doc-meta { padding: 0.5rem 0.8rem; }
  .panel-table th:nth-child(3), .panel-table td:nth-child(3) { display: none; }
}

@media (max-width: 420px) {
  .editor-tab { padding: 0 0.5rem; font-size: 12px; }
  .panel-table th:nth-child(4), .panel-table td:nth-child(4) { display: none; }
  .doc-chip { font-size: 10px; }
  .mobile-tab { font-size: 9px; }
}
"""


def _script() -> str:
    return """
(function () {
  const mobilePaneTargets = new Set(["explorer", "chat", "task", "receipt", "draft", "checkin", "home"]);
  const DESKTOP = window.matchMedia("(min-width: 881px)");
  const body = document.body;
  const panes = Array.from(document.querySelectorAll(".pane"));
  const mobileTabs = Array.from(document.querySelectorAll(".mobile-tab"));
  const activityBtns = Array.from(document.querySelectorAll(".activity-btn[data-target]"));
  const editorTabs = Array.from(document.querySelectorAll(".editor-tab"));
  const secTabs = Array.from(document.querySelectorAll(".sec-tab"));
  const secPanels = Array.from(document.querySelectorAll(".sec-panel"));
  const panelTabs = Array.from(document.querySelectorAll(".panel-tab"));

  // map a mobile target to the container pane it lives in
  const PANE_GROUP = {
    home: null, // home is an editor document, shown via editor-area
    explorer: "explorer",
    chat: "chat", task: "chat", receipt: "chat",
    draft: "draft",
    checkin: "checkin",
  };

  function showMobilePane(name) {
    const group = PANE_GROUP[name] || null;

    // toggle top-level container panes
    panes.forEach((p) => {
      const paneName = p.getAttribute("data-mobile-pane");
      if (!paneName) return;
      p.classList.toggle("is-mobile-active", paneName === group);
    });

    // editor-region hosts editor-area + bottom-panel; show it for draft, checkin, and home
    const editorRegion = document.querySelector(".editor-region");
    const showEditorRegion = name === "draft" || name === "checkin" || name === "home";
    if (editorRegion) editorRegion.classList.toggle("is-mobile-active", showEditorRegion);

    const editorArea = document.querySelector(".editor-area");
    const bottomPanel = document.querySelector(".bottom-panel");
    if (editorArea) editorArea.style.display = name === "draft" || name === "home" ? "" : "none";
    if (bottomPanel) bottomPanel.style.display = name === "checkin" ? "flex" : "none";

    // within the secondary sidebar, switch the active sec-panel for chat/task/receipt
    if (group === "chat") {
      secPanels.forEach((p) => {
        const active = p.dataset.secPanel === name;
        p.classList.toggle("is-active", active);
        p.hidden = !active;
      });
      secTabs.forEach((t) => t.classList.toggle("is-active", t.dataset.sec === name));
      updateSecTitle(name);
    }

    // within the editor-area, show the matching document
    const docMap = { home: "home", draft: "draft", source: "source", receipt: "receipt", workitem: "workitem", checkin: "checkin" };
    if (docMap[name]) showDoc(docMap[name]);

    mobileTabs.forEach((t) => t.classList.toggle("is-active", t.dataset.target === name));
  }

  function showDoc(name) {
    const docs = Array.from(document.querySelectorAll(".doc-surface"));
    docs.forEach((d) => {
      const active = d.dataset.doc === name;
      d.classList.toggle("is-active", active);
      d.hidden = !active;
    });
  }

  const SEC_LABELS = { chat: "Chat", task: "Task", receipt: "Receipt", changes: "Changes", authority: "Authority" };
  function updateSecTitle(sec) {
    const el = document.getElementById("sec-sidebar-title");
    if (el && SEC_LABELS[sec]) el.textContent = "Maya - " + SEC_LABELS[sec];
  }

  function showDesktopActivity(target) {
    activityBtns.forEach((b) => {
      b.classList.toggle("is-active", b.dataset.target === target);
    });
  }

  function activate(target) {
    if (DESKTOP.matches) {
      showDesktopActivity(target);
      // editor document routing for editor tabs and activity targets
      if (target === "draft" || target === "source" || target === "receipt" || target === "home" || target === "workitem") {
        editorTabs.forEach((t) => t.classList.toggle("is-active", t.dataset.target === target));
        showDoc(target);
      }
      if (target === "checkin") {
        editorTabs.forEach((t) => t.classList.remove("is-active"));
        showDoc("checkin");
      }
    } else {
      showMobilePane(target);
    }
    history.replaceState(null, "", "#" + target);
  }

  // wire all data-target controls
  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-target]");
    if (!el) return;
    ev.preventDefault();
    activate(el.dataset.target);
  });

  // secondary sidebar tab switching (desktop)
  secTabs.forEach((tab) => {
    tab.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const sec = tab.dataset.sec;
      secTabs.forEach((t) => t.classList.toggle("is-active", t === tab));
      secPanels.forEach((p) => {
        const active = p.dataset.secPanel === sec;
        p.classList.toggle("is-active", active);
        p.hidden = !active;
      });
      history.replaceState(null, "", "#" + sec);
      updateSecTitle(sec);
    });
  });

  // bottom panel tab switching (static: only checkin has body)
  panelTabs.forEach((tab) => {
    tab.addEventListener("click", (ev) => {
      ev.stopPropagation();
      panelTabs.forEach((t) => t.classList.toggle("is-active", t === tab));
    });
  });

  // tree view collapse/expand
  document.querySelectorAll("[data-toggle]").forEach((header) => {
    header.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const view = header.closest(".tree-view");
      const expanded = view.classList.toggle("is-expanded");
      view.classList.toggle("is-collapsed", !expanded);
      header.setAttribute("aria-expanded", String(expanded));
      const chev = header.querySelector(".chevron");
      if (chev) chev.textContent = expanded ? "▾" : "▸";
      const list = view.querySelector(".tree, .src-list, .people-list");
      if (list) list.hidden = !expanded;
    });
  });

  function onBreakpointChange() {
    if (DESKTOP.matches) {
      // restore desktop layout
      panes.forEach((p) => {
        p.classList.remove("is-mobile-active");
        p.style.display = "";
      });
      const editorRegion = document.querySelector(".editor-region");
      if (editorRegion) editorRegion.classList.remove("is-mobile-active");
      const editorArea = document.querySelector(".editor-area");
      const bottomPanel = document.querySelector(".bottom-panel");
      if (editorArea) editorArea.style.display = "";
      if (bottomPanel) bottomPanel.style.display = "";
    } else {
      const initial = (location.hash.replace("#", "")) || "explorer";
      showMobilePane(mobilePaneTargets.has(initial) ? initial : "explorer");
    }
  }
  DESKTOP.addEventListener("change", onBreakpointChange);

  const initial = (location.hash.replace("#", "")) || "explorer";
  if (DESKTOP.matches) {
    // pick a sensible default doc based on initial target
    const docMap = { home: "home", draft: "draft", source: "source", receipt: "receipt", workitem: "workitem", checkin: "checkin" };
    showDoc(docMap[initial] || "draft");
    if (initial === "home" || initial === "checkin" || initial === "draft" || initial === "source" || initial === "receipt" || initial === "workitem") {
      activate(initial);
    } else {
      showDesktopActivity("explorer");
    }
  } else {
    showMobilePane(mobilePaneTargets.has(initial) ? initial : "explorer");
  }

  // ---------- Draggable splitters ----------
  function initSplitter(handle, side) {
    const grid = document.getElementById("workbench-grid");
    if (!grid) return;
    handle.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      handle.classList.add("is-dragging");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      const startX = ev.clientX;
      const startW = parseFloat(
        getComputedStyle(grid).getPropertyValue(side === "primary" ? "--primary-w" : "--secondary-w")
      );
      function onMove(e) {
        const delta = e.clientX - startX;
        let w = side === "primary" ? startW + delta : startW - delta;
        w = Math.max(180, Math.min(w, window.innerWidth * 0.5));
        grid.style.setProperty(side === "primary" ? "--primary-w" : "--secondary-w", w + "px");
      }
      function onUp() {
        handle.classList.remove("is-dragging");
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }
  initSplitter(document.getElementById("splitter-primary"), "primary");
  initSplitter(document.getElementById("splitter-secondary"), "secondary");
})();
"""
