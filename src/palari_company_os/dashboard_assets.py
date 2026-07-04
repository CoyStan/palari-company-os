from __future__ import annotations

DASHBOARD_CSS = """
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
.agent-command-block li { display: grid; grid-template-columns: 3.8rem minmax(0, 1fr) auto; gap: 0.4rem; align-items: baseline; }
.agent-command-block li span { color: var(--muted); font-size: 0.72rem; font-weight: 600; }
.agent-command-block code { font-size: 0.72rem; overflow-wrap: anywhere; }
.command-inline {
  display: flex; align-items: center; gap: 0.38rem; min-width: 0; flex-wrap: wrap;
}
.command-inline code { min-width: 0; overflow-wrap: anywhere; }
.copy-command {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: 1.45rem; padding: 0.12rem 0.42rem;
  border: 1px solid var(--line-strong); border-radius: 4px;
  background: var(--panel); color: var(--ink-2);
  font-size: 0.68rem; font-weight: 650; line-height: 1;
}
.copy-command:hover,
.copy-command:focus-visible {
  border-color: var(--accent); color: var(--accent); outline: none;
}
.copy-command.is-copied {
  border-color: var(--trust-line); color: var(--trust); background: var(--trust-bg);
}
.agent-boundary {
  margin: -0.08rem 0 0.32rem; color: var(--muted); font-size: 0.72rem;
}
.top-handoff span {
  color: var(--muted); font-size: 0.72rem; font-weight: 600; margin-right: 0.3rem;
}
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

def dashboard_styles() -> str:
    return DASHBOARD_CSS

DASHBOARD_JS = """
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

  const copyButtons = Array.from(document.querySelectorAll('[data-copy-command]'));

  async function copyCommand(command) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(command);
      return;
    }
    const area = document.createElement('textarea');
    area.value = command;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.left = '-9999px';
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }

  for (const button of copyButtons) {
    button.addEventListener('click', async () => {
      const command = button.getAttribute('data-copy-command') || '';
      const original = button.textContent || 'Copy';
      try {
        await copyCommand(command);
        button.textContent = 'Copied';
        button.classList.add('is-copied');
        setTimeout(() => {
          button.textContent = original;
          button.classList.remove('is-copied');
        }, 1200);
      } catch (error) {
        button.textContent = 'Select';
        button.classList.remove('is-copied');
      }
    });
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

def dashboard_script() -> str:
    return DASHBOARD_JS
