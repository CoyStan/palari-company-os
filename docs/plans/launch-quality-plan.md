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

- [ ] `palari demo --no-pause` exits 0 and prints the blocked-write moment,
      verified by a unit test asserting the block marker and offending path
      appear in output.
- [ ] The demo writes nothing outside its target directory (test asserts).
- [ ] A fresh reader following only README instructions reaches the demo in
      two commands: `pip install -e .` (or clone+`./bin/palari`) then
      `palari demo`.
- [ ] The demo script text contains no invented vocabulary before the moment
      it is demonstrated (see Workstream 4 rules).
- [ ] `scripts/verify.sh` runs `palari demo --no-pause` as part of the gate.

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

- [ ] All requirements above are implemented in the generated HTML/CSS.
- [ ] Unit tests assert: theme toggle markup present, empty-state text
      present for an empty workspace, no `http://` or `https://` asset
      references in output, viewport meta present.
- [ ] The acme example dashboard and an EMPTY workspace dashboard both look
      intentional (empty states verified by test, visual quality by the
      Squint Test below).
- [ ] Squint Test self-audit written into this file: open the rendered HTML,
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

- [ ] Everything above the quickstart fits in the first ~50 lines.
- [ ] The first screen contains zero invented nouns except "Palari" itself
      (no workbench, receipt, gate profile, adaptive intensity until after
      the quickstart; "receipt" may appear once if immediately shown).
- [ ] Every feature claim in the README is demonstrated by a command a
      reader can run, or linked to the doc that proves it.
- [ ] `tests/test_docs.py` (extend it) asserts the README contains: an image
      before the quickstart, a `palari demo` mention, and the live demo link.
- [ ] A "60-second skeptic" self-audit is written into this file: read only
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

- [ ] Glossary exists, is linked from README and quickstart, and covers every
      noun in `docs/product/core-objects.md`.
- [ ] The newcomer path noun-count is ≤ 3 and documented in the Self-Audit.
- [ ] A docs test asserts the glossary covers all core object names.

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

- [ ] Pages workflow YAML exists, is syntactically valid, and the exact same
      generation commands succeed locally.
- [ ] Release workflow YAML exists; local build + twine check pass.
- [ ] Both human follow-up actions are documented step-by-step in the
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

---

## Definition of Perfect (the exit gate)

The work is complete ONLY when every box in Workstreams 1-6 is checked AND
all of the following hold:

1. **Two-minute test:** from a fresh clone, `./bin/palari demo --no-pause`
   shows the blocked-write moment; from README alone the path is two
   commands.
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
