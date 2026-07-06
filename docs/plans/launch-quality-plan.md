# Launch Quality Plan: "Oh Shit, This Is Good"

This is an autonomous work brief for a coding agent. Work through it until
every condition in the **Definition of Perfect** section is objectively
satisfied. Do not stop after one pass; loop: implement, verify, self-audit
against the checklists, fix gaps, repeat.

## Mission

Palari Company OS is already engineered well. What it lacks is the first-five-
minutes experience: a stranger arriving from a social link must reach an
"oh shit, this is good" moment in under two minutes, without reading theory.

The product moment we are selling: **an AI coding agent tries to touch
something it should not, Palari blocks it, and the human gets a receipt.**
Every workstream below exists to put that moment in front of a stranger
faster, more visibly, and with less vocabulary.

## Operating Rules (read first, non-negotiable)

1. Follow the repo contract in `AGENTS.md` and `CLAUDE.md`. Record work in the
   dogfood workspace (`workspaces/palari-company-os`) as the contract requires.
2. Never break the quality gate. After EVERY commit, all of these must pass:

   ```bash
   python3 -m unittest discover -s tests
   ruff check .
   mypy
   ./scripts/verify.sh
   python3 -S scripts/check_style.py
   ```

3. Zero new runtime dependencies. The stdlib-only constraint is a core product
   claim. Dev/CI tooling may use pinned dev dependencies only.
4. New behavior requires new tests. Every new command, flag, or generated
   asset gets unit tests in `tests/`.
5. Small, focused commits with clear messages. One workstream may span many
   commits; never mix workstreams in one commit.
6. Do not rewrite history, do not touch unrelated files, do not "improve"
   code outside the workstreams below.
7. Tasks marked **[HUMAN]** cannot be completed by the agent (recording video,
   creating a PyPI account, taking the final GIF). Prepare everything up to
   the human step, then document the exact remaining human action in the
   Self-Audit section at the bottom of this file.
8. When a condition is ambiguous, choose the interpretation a skeptical
   first-time visitor would prefer, and note the decision in the Self-Audit.

---

## Workstream 1: `palari demo` — the two-minute aha

Build a `palari demo` subcommand that gives a newcomer the core product
moment with zero setup.

Behavior:

- `palari demo` creates a throwaway demo workspace in a temp directory (or
  `--dir PATH`), never touching the user's files or the repo's committed
  examples.
- It then walks a scripted scenario, printing each step with real command
  output, pausing between acts (`--no-pause` flag for CI):
  1. Show the queue: a small believable company workspace (3-5 work items,
     one agent persona, one human).
  2. An agent claims a work item (`agent start`) and shows its packet: what
     it may read, what it may write.
  3. **The moment:** the agent "tries" to change a file outside its write
     boundary (e.g. `deploy/production.yml`). Run the real
     `agent check --changed` machinery and show the real fail-closed block,
     visually unmistakable (clear BLOCKED marker, the offending path, the
     boundary it violated).
  4. Show the contrast: the same check passing for an in-scope file.
  5. Show the receipt/finish flow and where a human decision is required.
  6. End with: what just happened in three plain sentences, and the three
     commands to try on your own repo.
- `palari demo --json` emits a machine-readable transcript (for tests).
- The entire demo runs offline, deterministically, in under 30 seconds of
  compute.

Done when:

- [x] `palari demo --no-pause` exits 0 and prints the blocked-write moment,
      verified by a unit test asserting the block marker and offending path
      appear in output.
- [x] The demo writes nothing outside its target directory (test asserts).
- [x] A fresh reader following only README instructions reaches the demo in
      two commands: `pip install -e .` (or clone+`./bin/palari`) then
      `palari demo`.
- [x] The demo script text contains no invented vocabulary before the moment
      it is demonstrated (see Workstream 4 rules).
- [x] `scripts/verify.sh` runs `palari demo --no-pause` as part of the gate.

## Workstream 2: Dashboard at screenshot quality

The generated dashboard (`palari dashboard`) must look like a product, not a
report. It will be screenshotted, shared, and deployed as the live demo, so
every pixel is marketing.

Requirements:

- Single self-contained static HTML output (no external fonts, scripts, or
  network requests) — this is already true; keep it true.
- Clear visual hierarchy: the queue ("what needs a human now") is the hero.
  Blocked items and pending human decisions must be visually loud; completed
  work quiet.
- A deliberate design system: one accent color plus a neutral scale, a
  consistent type scale (max 4 sizes), consistent spacing units, and
  status colors that are distinguishable for color-blind users (never color
  alone — pair with icons or labels).
- Dark and light theme, honoring `prefers-color-scheme`, with a manual toggle.
- Responsive: fully usable at 375px wide (phone) and 1440px; no horizontal
  page scroll at any width; wide tables scroll inside their own container.
- Empty states: every panel shows a helpful sentence (and the command that
  fills it) instead of a blank region when a collection is empty.
- Receipts rendered as first-class cards: what was read, changed, skipped,
  left undoable — scannable in five seconds.
- Zero browser console errors or warnings on load.
- Keyboard navigable; interactive elements have visible focus states; basic
  ARIA roles on tabs and toggles.

Done when:

- [x] All requirements above are implemented in the generated HTML/CSS.
- [x] Unit tests assert: theme toggle markup present, empty-state text
      present for an empty workspace, no `http://` or `https://` asset
      references in output, viewport meta present.
- [x] The acme example dashboard and an EMPTY workspace dashboard both look
      intentional (empty states verified by test, visual quality by the
      Squint Test below).
- [x] Squint Test self-audit written into this file: open the rendered HTML,
      and answer in writing — "What draws the eye first?" The answer must be
      the queue/blocked items, not chrome, headers, or navigation.

## Workstream 3: README rewrite — scenario first

The README must sell the moment before it explains the system.

Structure (top to bottom):

1. One-sentence hook naming the pain: agents doing more than you asked.
2. A screenshot or GIF of the blocked-write moment or dashboard
   (see Workstream 6; use a committed PNG/SVG until the GIF exists).
3. A 10-15 line concrete scenario in plain English: what the agent tried,
   what Palari did, what the human saw. Real command snippets, real output
   excerpts.
4. Quickstart: install → `palari demo` → link to live demo. Nothing else
   before this point.
5. Only THEN: what Palari is, the object model, links to deep docs.
6. Honest status section (what works, what does not) — keep, it builds trust.

Done when:

- [x] Everything above the quickstart fits in the first ~50 lines.
- [x] The first screen contains zero invented nouns except "Palari" itself
      (no workbench, receipt, gate profile, adaptive intensity until after
      the quickstart; "receipt" may appear once if immediately shown).
- [x] Every feature claim in the README is demonstrated by a command a
      reader can run, or linked to the doc that proves it.
- [x] `tests/test_docs.py` (extend it) asserts the README contains: an image
      before the quickstart, a `palari demo` mention, and the live demo link.
- [x] A "60-second skeptic" self-audit is written into this file: read only
      the first screen of the README and write down what a skeptic now
      believes the product does. It must match the actual product.

## Workstream 4: Kill the vocabulary tax

Rules applied across README and `docs/product/quickstart.md` (deep docs may
keep full vocabulary):

- Plain-English-first: every invented noun is introduced by the plain phrase
  it replaces ("a bounded work assignment — Palari calls this a work item").
- Progressive disclosure: a newcomer path (README → quickstart → demo) that
  requires at most THREE invented nouns total. Count them; list them in the
  Self-Audit.
- Add `docs/product/glossary.md`: every Palari noun, one plain-English
  sentence each, one "you see it when…" example each. Link it prominently.
- Rename nothing in the schema/code (no breaking changes); this is a
  documentation-layer fix only.

Done when:

- [x] Glossary exists, is linked from README and quickstart, and covers every
      noun in `docs/product/core-objects.md`.
- [x] The newcomer path noun-count is ≤ 3 and documented in the Self-Audit.
- [x] A docs test asserts the glossary covers all core object names.

## Workstream 5: Live demo + release rails

GitHub Pages:

- Add a workflow that, on push to `main`, generates the acme example
  dashboard and the desktop prototype and deploys them to GitHub Pages
  (dashboard at `/`, prototype at `/desktop/`).
- README links to the live demo near the top.
- **[HUMAN]** Enable Pages in repo settings if the workflow cannot.

PyPI:

- Add a release workflow: on a version tag (`v*`), build sdist+wheel,
  `twine check`, publish via PyPI Trusted Publishing, and create a GitHub
  Release with the CHANGELOG section for that version.
- Verify locally that `python -m build` and `twine check dist/*` pass.
- Bump version and update CHANGELOG for the launch release.
- **[HUMAN]** Register the PyPI project / configure Trusted Publishing, then
  push the tag.

Done when:

- [x] Pages workflow YAML exists, is syntactically valid, and the exact same
      generation commands succeed locally.
- [x] Release workflow YAML exists; local build + twine check pass.
- [x] Both human follow-up actions are documented step-by-step in the
      Self-Audit.

## Workstream 6: Demo assets

- Add `scripts/make_demo_assets.sh` (or `.py`) that regenerates every visual
  asset from source: renders the dashboard, and if Playwright/Chromium is
  available captures PNG screenshots (light + dark, desktop + 375px) into
  `docs/assets/`; degrades gracefully with a clear message if no browser is
  available.
- Commit the generated screenshots used by the README.
- Write `docs/plans/demo-recording-script.md`: an exact 90-second shot list
  for the human to record as a GIF/video — every command to type, what the
  screen shows, and the single sentence of on-screen caption per act.
- **[HUMAN]** Record the GIF; replace the README screenshot with it.

Done when:

- [ ] Asset script exists, is idempotent, and is covered by `bash -n` in the
      style/verify gate.
- [ ] README images exist in the repo and render on GitHub (relative paths).
- [ ] The recording script is complete enough that a person who has never
      used Palari could record the demo by following it literally.

## Workstream 7: `palari serve` — live Mission Control

The static dashboard is the export/share format. This workstream adds the
product people will actually screenshot: a LIVE local web app where a human
supervises agents and clicks the buttons. Positioning: an approval desk for
your AI workforce.

Architecture constraints (these protect the product's core claims):

- Stdlib only: `ThreadingHTTPServer`, following the existing pattern in
  `desktop_server.py`. No frameworks, no npm, no build step.
- Files stay the source of truth: every GET re-reads `workspace.json` (or
  serves from a cache keyed by the file's content hash); the server holds no
  state that is not in the files.
- Every POST goes through the existing store/authoring layer, so the write
  lock, load-hash conflict check, and validation all apply. A conflict
  returns a clear "workspace changed, refresh" response, never a silent
  overwrite.
- Localhost by default (`127.0.0.1`, port 0 or `--port`). Every mutating
  request requires a per-session CSRF token embedded in the served page.
  `--host` other than localhost prints a loud warning (no auth exists yet).
- Attribution is explicit: `palari serve --as HUMAN-ID` is required; every
  decision made in the UI records that human, identically to the CLI path.

The experience (in priority order — the first two ARE the product):

1. **The "Needs You" lane (hero).** Pending approvals, blocked agents, and
   items awaiting human decision, sorted by urgency. Each card: what the
   agent wants, why it stopped, and real Approve / Reject / Cancel buttons
   that write the same human-decision and integration-plan records the CLI
   writes. Empty state: "Nothing needs you. Your agents are inside their
   boundaries." (That sentence is the product pitch; keep it.)
2. **The boundary view (screenshot magnet).** For a selected work item with
   an active claim: allowed read sources and write paths rendered as a
   visual fence, with any out-of-bounds attempted change from
   `agent check` shown loudly outside it. This is the blocked-write moment
   as a picture instead of a paragraph.
3. **Live activity feed.** Claims, checks, finishes, handoffs, and decisions
   as a reverse-chronological stream sourced from workspace history, updated
   without manual refresh.
4. **Receipt drawer.** Click any finished item: the receipt card (read /
   changed / skipped / undoable) slides in; one keypress or click to get
   back to the queue.
5. Liveness via polling `fetch` every ~2s against a `/state-hash` endpoint;
   re-render only when the hash changes. No SSE/WebSockets in v1 (keep the
   server trivial); document this choice.
6. Same design system, themes, responsive, and accessibility bar as
   Workstream 2 — one visual language across static and live.
7. Demo synergy: `palari demo --serve` runs the demo scenario against the
   live UI so the newcomer's aha-moment is clickable, not just printed.

Done when:

- [ ] `palari serve --as HUMAN-ID` starts, serves the UI, and shuts down
      cleanly on Ctrl+C; covered by tests using a port-0 server instance.
- [ ] Tests prove UI-approve and CLI-approve produce byte-identical record
      shapes (same fields, same history entries) for the same scenario.
- [ ] Tests prove: mutating POST without the CSRF token is rejected; POST
      after an out-of-band workspace edit returns the conflict response and
      changes nothing; all writes hold the workspace lock.
- [ ] `/state-hash` changes when and only when the workspace file changes
      (test with two edits and one no-op touch).
- [ ] The Needs You lane, boundary view, activity feed, and receipt drawer
      all render with the acme example data, each covered by a markup
      assertion test, and each with an intentional empty state.
- [ ] No external network references in any served asset (test).
- [ ] `--host 0.0.0.0` prints the security warning (test); default bind is
      loopback (test).
- [ ] README and quickstart show `palari serve` as the second thing to try
      (after `palari demo`); the static `palari dashboard` is repositioned
      in docs as the export/share/Pages format.
- [ ] Squint Test self-audit for the live UI, same rule as Workstream 2:
      the eye must land on the Needs You lane first.

---

## Definition of Perfect (the exit gate)

The work is complete ONLY when every box in Workstreams 1-7 is checked AND
all of the following hold:

1. **Two-minute test:** from a fresh clone, `./bin/palari demo --no-pause`
   shows the blocked-write moment; from README alone the path is two
   commands. `palari serve` then makes that moment clickable in one more
   command.
2. **Quality gate:** the full command list in Operating Rules passes, and CI
   is green on the working branch.
3. **First-screen test:** README first screen = hook + image + scenario, ≤ 3
   invented nouns on the whole newcomer path.
4. **Screenshot test:** the committed dashboard screenshots would not
   embarrass a designer: consistent spacing, deliberate hierarchy, working
   dark mode, real content (not lorem ipsum), no clipped text.
5. **Stranger audit:** the Self-Audit section below is filled in honestly,
   including the Squint Test, the 60-second skeptic test, the noun count,
   every ambiguity decision, and the exact remaining [HUMAN] steps.
6. **No regressions:** every capability that worked before (all existing
   commands, MCP server, verify script) still works; test count only goes up.

If any condition cannot be met, do not silently drop it: document why in the
Self-Audit and propose the closest achievable alternative.

## Self-Audit (append; do not delete previous entries)

_The working agent fills this in as the final task of each loop iteration._

### 2026-07-06 — Workstream 1: `palari demo`

- Implemented `palari demo` with `--dir`, `--no-pause`, and `--json`.
- The demo copies the packaged Acme workspace into a temp or explicitly empty
  target directory, starts Sofia on `WORK-0003`, shows a real
  `agent check --changed deploy/production.yml` failure, contrasts it with an
  allowed `docs/product/company-os.md` change, records a receipt and evidence,
  and shows review/human-approval handoff output.
- Unit tests cover the blocked marker/offending path, JSON transcript, and the
  "writes only inside target directory" guarantee.
- Ambiguity decision: the plan says "demo script text" contains no invented
  vocabulary before the moment; I interpreted that as the new narration owned
  by `palari demo`, not the existing real command output, because the command
  output must remain authentic and already includes established CLI terms.
- README quickstart now points both repo-local and editable-install users to
  `palari demo` immediately.

### 2026-07-06 — Workstream 2: dashboard screenshot quality

- Implemented dashboard tab wrappers with `role="tablist"`, `role="tab"`,
  and `role="tabpanel"` while preserving the existing tab behavior.
- Added a compact manual theme toggle that cycles system/light/dark, honors
  `prefers-color-scheme` when left on system, and stores the explicit choice
  in `localStorage`.
- Added dark-theme tokens and contrast fixes for the dense dashboard style.
  Visual check: the dark dashboard remains dense and readable; the queue rows
  and top attention card stay visually dominant.
- Improved empty dashboard states so empty panels include a helpful sentence
  plus a real copyable command to fill the panel.
- Unit tests now assert viewport meta, theme toggle markup, dark-mode CSS,
  empty-workspace empty-state text, no remote asset references, and ARIA tab
  markup.
- Visual Squint Test:
  - Acme 1440px light: the eye lands first on "What needs attention now,"
    then the red top attention/work-queue items.
  - Acme 375px light: the eye lands first on "What needs attention now" and
    the red top attention card; the bottom nav no longer shows a horizontal
    scrollbar.
  - Acme 1440px dark: the eye still lands on the queue/blocked items, not
    the chrome or navigation.
  - Empty 1440px light: the queue empty state reads intentional and gives a
    command to create the first work item.
- Browser note: Chromium headless rendered the generated pages and screenshots
  successfully. The only stderr noise observed was Snap/DBus environment
  logging, not dashboard page-console output.

### 2026-07-06 — Workstream 3: README scenario first

- Rewrote the README opening so it starts with the concrete blocked-write
  scenario, a repo-local visual asset, the real blocked output shape, and then
  the quickstart.
- Added `docs/assets/blocked-write-dashboard.svg` as a temporary screenshot
  slot until Workstream 6 generates and commits browser screenshots/GIF assets.
- Added a docs regression test asserting image-before-quickstart, `palari demo`,
  the live demo link, and no late object-model nouns in the pre-quickstart
  first screen.
- First-screen audit: the Quickstart begins after 25 lines, below the
  ~50-line target.
- First-screen noun count: 0 of the late Palari nouns (`workbench`,
  `work item`, `receipt`, `evidence`, `human decision`, `gate profile`) appear
  before Quickstart; only the name Palari appears.
- 60-second skeptic audit: a skeptical reader who only sees the first screen
  should believe Palari lets an AI agent work inside visible file boundaries,
  blocks an attempted change outside those boundaries, and shows the human
  exactly what happened and what command is safe next. That matches the current
  `palari demo` behavior.
- Ambiguity decision: the README now links the GitHub Pages live-demo target
  near the top even though Workstream 5 still has to enable the workflow. The
  quickstart labels it "Live demo target" to avoid claiming the deployment is
  already complete.

### 2026-07-06 — Workstream 4: vocabulary tax

- Added `docs/product/glossary.md` with every heading from
  `docs/product/core-objects.md`, each with one plain definition and one
  "You see it when..." example.
- Linked the glossary from README and `docs/product/quickstart.md`.
- Rewrote the quickstart to lead with `palari demo`, one allowed boundary
  check, one blocked boundary check, and a dashboard export, before sending
  readers to deeper docs.
- Added docs tests proving glossary coverage and glossary links.
- Newcomer path noun-count decision: the README first screen plus quickstart
  intentionally introduces only three recurring product-facing terms:
  `Palari`, `agent`, and `boundary`. `dashboard` appears as a generic UI word,
  not a Palari object. Heavy model nouns (`workbench`, `work item`, `receipt`,
  `evidence`, `human decision`, `source`) are deferred until after the
  quickstart/glossary path.

### 2026-07-06 — Workstream 5: live demo + release rails

- Added `.github/workflows/pages.yml`. It runs on pushes to `main`, installs
  the package, generates the Acme dashboard at `/`, generates the desktop
  prototype at `/desktop/`, uploads the `public/` artifact, and deploys with
  GitHub Pages actions.
- Verified the exact Pages generation commands locally:
  `palari --workspace examples/acme-company-os dashboard --out public`
  and `palari desktop-prototype --out public/desktop`, using
  `/tmp/palari-pages-preview` as the output root.
- Added `.github/workflows/release.yml`. It runs on `v*` tags, builds the
  sdist and wheel, runs `twine check`, extracts the matching CHANGELOG section,
  publishes with PyPI Trusted Publishing, and creates a GitHub Release with the
  built artifacts and changelog notes.
- Bumped the launch version to `0.1.2` in `pyproject.toml`,
  `src/palari_company_os/__init__.py`, and `docs/product/release-and-operations.md`.
  Added a `CHANGELOG.md` section for `0.1.2`.
- Updated packaging license metadata to the SPDX-style `license = "MIT"` plus
  `license-files = ["LICENSE"]`, so the local launch build is warning-free
  with current setuptools.
- Verified workflow YAML syntax locally with PyYAML. Note: PyYAML reports the
  GitHub Actions `on` key as `True` because of its YAML 1.1 boolean rules; the
  parse still proves YAML syntax is valid, and GitHub Actions treats `on` as
  the workflow trigger key.
- Verified release artifacts locally with:
  `/tmp/palari-release-tools/bin/python -m build --outdir /tmp/palari-release-dist`
  and `/tmp/palari-release-tools/bin/twine check /tmp/palari-release-dist/*`.
- Human follow-up: enable GitHub Pages if it is not already enabled.
  1. Open the GitHub repo settings.
  2. Go to Pages.
  3. Set Source to GitHub Actions.
  4. Run or re-run the Pages workflow.
  5. Confirm the public URL serves the dashboard at
     `https://coystan.github.io/palari-company-os/` and the prototype at
     `https://coystan.github.io/palari-company-os/desktop/`.
- Human follow-up: configure the PyPI release path before tagging.
  1. Ensure the PyPI project name `palari-company-os` exists or is available.
  2. Configure PyPI Trusted Publishing for GitHub repository
     `CoyStan/palari-company-os`, workflow `.github/workflows/release.yml`.
  3. Push tag `v0.1.2` only after Trusted Publishing is configured.
  4. Confirm the workflow publishes the package and creates the GitHub Release.
- Ambiguity decision: the release workflow extracts changelog notes before
  publishing to PyPI, so a missing `CHANGELOG.md` section fails before a
  publish-side effect. The workflow does not define a GitHub environment for
  PyPI because the plan did not require one; if PyPI Trusted Publishing is
  configured with an environment later, the workflow should be updated in the
  same release-rails area.
