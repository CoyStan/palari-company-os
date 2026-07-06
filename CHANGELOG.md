# Changelog

All notable changes to Palari Company OS are recorded here.

This project is still in the v0 foundation stage. The changelog describes
repository milestones, not a production Company OS release.

## [Unreleased]

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
