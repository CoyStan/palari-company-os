# Changelog

All notable changes to Palari Company OS are recorded here.

This project is still in the v0 foundation stage. The changelog describes
repository milestones, not a production Company OS release.

## [Unreleased]

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
