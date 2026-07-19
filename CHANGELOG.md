# Changelog

All notable changes to Palari Company OS are recorded here.

This project is still in the v0 foundation stage. The changelog describes
repository milestones, not a production Company OS release.

## [Unreleased]

### Fixed

- Bound new accept-ready reviews to the exact terminal attempt, receipt,
  evidence manifest, reviewed head, and work contract. Acceptance, completion,
  read models, and quorum now fail closed on stale or contradictory proof, and
  later negative decisions revoke earlier approval from the same human.
- Hardened filesystem enforcement against traversal, sibling-prefix and
  symlink escape, malformed Git observations, ambiguous claims, and review-mode
  writes. Agent claims now distinguish unchanged pre-existing dirt with a
  hashed metadata-only baseline plus an independent local Git ref/reflog
  witness; hooks reconcile execute scope with current workspace truth.
- Revalidate evidence manifests, artifacts, and receipt hashes for active
  acceptance records, and stop supported agent shells from invoking
  human-attributed Palari mutations or silently running opaque interpreters.

### Changed

- Removed the hidden packaged ACME workspace and schema copies. Commands now
  use an explicit workspace or the current directory. The ACME workspace is a
  repository example only, while the isolated wheel smoke owns the installed
  package boundary.
- Removed the superseded `palari agent done` command and receipt-only
  completion lifecycle. `palari agent advance` is now the sole current
  execution-to-proof path, every completion requires current exact evidence,
  and only R1/light/zero-approval work with no external-write surface may omit
  independent review and human acceptance.
- Removed the unsupported static visual stack: the old `dashboard` generator,
  desktop prototype/server/assets/demo schema, showcase narrative, and Pages
  deployment. Mission Control is now the sole supported local human UI. These
  are intentional pre-1.0 removals and have no compatibility aliases.
- Made workspace schema v2 and governance-journal v2 the sole current write
  formats. Removed the synthetic v0/v1 workspace `migrate` command and the
  duplicate `.palari/history.jsonl` runtime. A strict governance-journal v1
  predecessor remains only as a sealed, explicit activation input proven by
  committed data; its bytes are never rewritten.
- Removed synthetic agent-claim v1 and Approval Pack v1 compatibility branches.
  Current claims require schema v2 plus an exact session-contract binding, and
  current Approval Packs require v2 plus an exact canonical presentation.
- Replaced affected-path test routing with two explicit profiles: one
  authoritative `complete` candidate gate and a focused mode that runs only the
  named test modules. CI runs the complete gate once on Python 3.12, one wheel
  build/install smoke, and thin import/kernel/help checks on the other supported
  interpreters.
- Removed unsupported Cursor, Devin, GLM, and generic session-profile aliases.
  Claude and Codex are the tested session adapters; other harnesses may consume
  the provider-neutral contract and host-neutral Git boundary without being
  advertised as supported profiles.
- Made generic external-action previews opaque and provider-neutral instead of
  maintaining speculative Slack, GitHub, Jira, or email payload shapes. Linear
  remains the only current live provider adapter.
- Reconstructed the slow packet, read-model, transition, validation, adapter,
  hook, and CLI tests around pure kernel decisions and genuine system
  boundaries. Candidate verification no longer executes Palari against the
  committed ACME example or dogfood workspace.
- Human review and approval templates are emitted only inside explicit
  read-only handoff boundaries after their prerequisite proof passes.

### Added

- Completed the governed Linear loop: `palari linear connect` verifies
  credentials and prepares the integration record (reporting a missing
  `LINEAR_API_KEY` as a structured blocker instead of an error), `palari
  linear issues` lists team issues annotated with palari-block presence and
  local link state, and `palari linear sync` pull-refreshes linked records
  without webhooks.
- Added governed Linear status write-back: `linear post-gate --action
  update-issue` plans an issue state change (by state name or default state
  type per event), and the existing human approval, enqueue, and `linear
  send` gates execute it through `issueUpdate`. Added the `work_started`
  integration event.
- Added `palari linear push WORK-ID`, governed issue creation for local work
  items: the plan embeds the work item's palari block in the issue
  description, and after approval `linear send` creates the issue and links
  the returned key/id/url back to the work item, so Palari-born tickets are
  trackable in Linear like any other issue.

## [0.2.0] - 2026-07-11

### Fixed

- Fixed the Release workflow's changelog-notes extraction, whose regex crashed
  at compile time and would have failed every tagged release before
  publishing. The workflow now also verifies the tag matches the package
  version before building.

### Changed

- The README now lists the governed Linear adapter as implemented and states
  the live-write boundary precisely: approval-gated Linear comment sends are
  the one live external write path.
- `./scripts/verify.sh` now smokes `linear doctor --json` against the dogfood
  workspace.
- Documented the tag-to-PyPI release flow and the one-time trusted-publishing
  setup in release-and-operations.

### Added

- Added a two-minute onramp for existing repos: `palari init` creates a
  starter workspace (one human, one Palari, one goal, one workbench, one repo
  source) and `palari work add TITLE --write PATH` creates an agent-startable
  work item from a title and its write paths. When the current directory has a
  `workspace.json`, commands use it as the default workspace, so
  `init` -> `work add` -> `claude install` works without `--workspace` flags.

- Added `palari claude install|status|hook`, a Claude Code enforcement adapter
  that turns the packet write boundary into structural enforcement: PreToolUse
  hooks deny out-of-boundary `Write`/`Edit`/`NotebookEdit` calls before the
  write happens, suspected out-of-boundary Bash writes escalate to a human ask,
  a Stop hook blocks turn completion while `git status` shows changes outside
  the boundary, and a SessionStart hook injects the active packet contract.
  Documented in `docs/product/claude-code-integration.md`.

## [0.1.2] - 2026-07-06

### Added

- Added `palari demo`, a two-minute offline blocked-write scenario for the
  first-run product moment.
- Added dashboard theme controls, dark-mode styling, ARIA tab markup, and
  command-rich empty states.
- Added a scenario-first README opening, launch visual asset, and plain-language
  glossary.
- Added GitHub Pages workflow rails for publishing the generated dashboard and
  desktop prototype.
- Added release workflow rails for building, checking, publishing with PyPI
  Trusted Publishing, and creating GitHub Releases from changelog notes.

### Changed

- Reworked the quickstart to start with the demo and one boundary check before
  introducing deeper model vocabulary.
- Extended docs tests to protect the README first-screen story and glossary
  coverage.

## [0.1.1] - 2026-06-21

### Fixed

- Packaged default example and desktop-demo data so installed wheels can run
  default CLI commands without a source checkout.
- Closed path traversal and output-boundary validation gaps for scope checks,
  attempts, receipts, and undo references.
- Made desktop prototype document HTML fail closed with a strict sanitizer.
- Made read models honor a work item's declared `current_attempt`.

### Changed

- Lazy-load heavier command modules to reduce startup cost for lightweight CLI
  commands.
- Added indexed workspace lookups and faster, timeout-bounded test subprocesses.
- Switched install smoke and CI package checks to exercise built wheels.
- Added GitHub CI and install-smoke verification for normal package usage.
- Added professional repository metadata, license, and maturity wording.
- Added a repo-local dogfood workspace for Palari Company OS maturity work.
- Made dogfood workspace history paths portable across clones.

## [0.1.0] - 2026-06-19

### Added

- Created the Palari Company OS Python CLI package.
- Added the `palari` console entry point and local `./bin/palari` wrapper.
- Added workspace schema v1 and strict workspace validation.
- Added the ACME example workspace.
- Added queue, detail, state, validate, scope, history, and maintainer commands.
- Added authoring and lifecycle commands for goals, Palaris, humans, decisions,
  work, attempts, evidence, reviews, human decisions, and outcomes.
- Added fail-closed checks for scope boundaries, stale evidence, stale review,
  human authority, and approval quorum.
- Added append-only workspace history for successful mutating commands.
- Added a small unittest suite and local verification script.

### Not Included

- No web UI.
- No production deployment.
- No real broker execution or external side effects.
- No real policy acceptance authority.
- No enterprise administration.
- No signed gate/key custody implementation.
