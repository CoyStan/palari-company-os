from __future__ import annotations

DESKTOP_PROTOTYPE_CSS = """
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

def desktop_prototype_styles() -> str:
    return DESKTOP_PROTOTYPE_CSS

DESKTOP_PROTOTYPE_JS_TEMPLATE = """
(function () {
  const body = document.body;
  const prototypeData = __PALARI_DESKTOP_PROTOTYPE_DATA_JSON__;
  const MOBILE_BREAKPOINT = prototypeData.ui.mobile_breakpoint || 1100;
  const mobileTabs = Array.from(document.querySelectorAll("[data-mobile-target]"));
  const sourceData = prototypeData.sources;
  const workData = prototypeData.work_items;
  const humanData = prototypeData.humans;
  const palariData = prototypeData.palaris;
  let currentWorkId = prototypeData.ui.default_work_item_id;

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

  const allowedDocumentTags = new Set([
    "blockquote", "br", "code", "em", "h1", "h2", "h3",
    "i", "li", "ol", "p", "pre", "strong", "ul",
  ]);

  function sanitizeDocumentHTML(value) {
    const template = document.createElement("template");
    template.innerHTML = String(value);
    Array.from(template.content.querySelectorAll("*")).forEach((element) => {
      const tag = element.tagName.toLowerCase();
      if (!allowedDocumentTags.has(tag)) {
        const parent = element.parentNode;
        if (parent) {
          while (element.firstChild) {
            parent.insertBefore(element.firstChild, element);
          }
          parent.removeChild(element);
        }
        return;
      }
      Array.from(element.attributes).forEach((attribute) => element.removeAttribute(attribute.name));
    });
    return template.innerHTML;
  }

  function currentAttempt(work) {
    return work.attempts[work.current_attempt_id];
  }

  function humanName(humanId, fallback) {
    const human = humanData[humanId];
    return human ? human.name : fallback || "Unknown human";
  }

  function actorName(kind, actorId) {
    if (kind === "human") {
      return humanName(actorId);
    }
    const palari = palariData[actorId];
    return palari ? palari.name : "Unknown Palari";
  }

  function actorAvatarClass(kind, actorId) {
    if (kind === "human") {
      const human = humanData[actorId];
      return human ? human.avatar_class : "alex";
    }
    return "bot";
  }

  function sourceOwner(source) {
    return source.owner_human_id ? humanName(source.owner_human_id, source.owner_label) : source.owner_label;
  }

  function sourceChipHTML(sourceId) {
    const source = sourceData[sourceId];
    if (!source) {
      return "";
    }
    return `<button class="used-source" type="button"><span class="file-icon ${escapeHTML(source.tone)}">${escapeHTML(source.type_label)}</span>${escapeHTML(source.title)}</button>`;
  }

  function renderChat(messages) {
    return messages.map((message) => `
      <div class="chat-message ${escapeHTML(message.speaker_kind)}">
        <span class="tiny-avatar ${escapeHTML(actorAvatarClass(message.speaker_kind, message.speaker_id))}">${message.speaker_kind === "palari" ? "M" : ""}</span>
        <div><strong>${escapeHTML(actorName(message.speaker_kind, message.speaker_id))}</strong><time>${escapeHTML(message.time)}</time>
        <p>${escapeHTML(message.text)}</p></div>
      </div>
    `).join("");
  }

  function renderAuthority(authority) {
    if (!authority.approvals.length) {
      return '<p class="muted-line">No human approver is needed for this local safe step.</p>';
    }
    return authority.approvals.map((approval) => {
      const human = humanData[approval.human_id];
      return `
        <div class="approval-row">
          <span class="tiny-avatar ${escapeHTML(human.avatar_class)}"></span>
          <strong>${escapeHTML(human.name)}</strong>
          <span>${escapeHTML(approval.role)}</span>
          <span class="chip ${escapeHTML(approval.status_class)}">${escapeHTML(approval.status_label)}</span>
        </div>
      `;
    }).join("");
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
    setChip(document.querySelector("[data-source-preview-mode]"), source.mode, source.mode_class);
    setText("[data-source-preview-provider]", source.provider);
    setText("[data-source-preview-access]", source.access);
    setText("[data-source-preview-owner]", sourceOwner(source));
    setText("[data-source-preview-seen]", source.last_seen);
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
    currentWorkId = workId;
    const attempt = currentAttempt(work);
    const palari = palariData[work.palari_id];
    const receipt = attempt.receipt;
    const authority = attempt.authority;

    document.querySelectorAll("[data-work-id]").forEach((row) => {
      row.classList.toggle("is-active", row.dataset.workId === workId);
    });

    setText("[data-artifact-title]", work.artifact_title);
    setText("[data-artifact-id]", work.public_id);
    setText("[data-artifact-attempt]", attempt.number);
    setChip(document.querySelector("[data-artifact-status]"), attempt.status_label, attempt.status_class);
    setText("[data-approval-copy]", work.approval_copy);
    setHTML("[data-sources-used]", `<span>Sources used</span>${attempt.sources_used.map(sourceChipHTML).join("")}`);
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
    setText("[data-receipt-title]", `Receipt (Attempt ${attempt.number})`);
    setChip(document.querySelector("[data-receipt-status]"), receipt.status_label, receipt.status_class);
    setHTML("[data-chat-thread]", renderChat(attempt.chat_messages));
    setText("[data-authority-requirement]", authority.requirement);
    setHTML("[data-authority-list]", renderAuthority(authority));
    setText("[data-authority-summary]", authority.summary);
    setText("[data-history-count]", `${attempt.history_events.length} change${attempt.history_events.length === 1 ? "" : "s"}`);
    setHTML("[data-history-list]", renderHistory(attempt.history_events));

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
  selectSource(prototypeData.ui.default_source_id);
  selectWork(prototypeData.ui.default_work_item_id);
  setMobileTarget(initial);
})();
"""

def desktop_prototype_script(data_json: str) -> str:
    return DESKTOP_PROTOTYPE_JS_TEMPLATE.replace(
        "__PALARI_DESKTOP_PROTOTYPE_DATA_JSON__", data_json
    )
