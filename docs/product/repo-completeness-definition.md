# Repo Completeness Definition

This document defines when Palari Company OS should be considered a
professional repository for a clearly declared scope.

It is intentionally stricter than "the code runs." A repo can be small and
professional, but it should not be called complete unless a new engineer or AI
maintainer can clone it, understand it, operate it, test it, and extend it
without relying on hidden context from the founder.

## Core Standard

Palari Company OS is complete when it is a usable operating layer for company AI
work, not only a model viewer or example dataset.

A complete repo must support the full product loop:

```text
Goal
  -> Palari
    -> Work
      -> Evidence
        -> Review
          -> Human Decision
            -> Outcome
```

The loop must be executable through documented commands, validated data, tests,
and clear authority boundaries.

## Status Levels

### Prototype

A prototype proves the idea.

It may have:

- basic docs
- example data
- a few commands
- local tests
- simplified validation

It is useful for design and learning, but it is not ready to run real company
work.

### Professional Foundation

A professional foundation is safe to build on.

It has:

- clean repo structure
- clear docs
- passing tests
- coherent schemas or models
- a working CLI
- examples that explain the product
- no copied runtime junk, secrets, caches, or historical ceremony

It can still be incomplete if important lifecycle actions are manual or only
documented.

### Complete Repo

A complete repo is ready to be used, reviewed, extended, and trusted as the
source of truth for its intended scope.

It does not need every future feature, but the features it claims to provide
must be real, documented, tested, and operable.

## Conditions For Completeness

### 1. Clear Product Contract

The repo must clearly state:

- what Palari Company OS is
- what a Palari is
- what problem the repo solves
- what the repo does today
- what the repo intentionally does not do
- who the expected users are
- how humans, Palaris, AI workers, evidence, reviews, and outcomes relate

The README must let a new person understand the product in minutes, and the
product docs must explain the model in enough detail to make design decisions.

The repo is not complete if its purpose only exists in chat history.

### 2. Fresh Clone Works

From a fresh clone, a maintainer must be able to:

- install or run the project using documented commands
- run the test suite
- run the main CLI commands
- validate the example workspace
- inspect the queue
- inspect a work item detail
- understand failures from command output

No required step should depend on untracked files, local shell history, old
worktrees, hidden environment variables, or founder-only context.

### 3. Full Lifecycle Authoring

The repo must not only read hand-authored JSON. It must support creating and
updating the core records through documented, validated commands or an equally
clear interface.

At minimum, a complete repo should support:

- create and update goals
- create and update Palaris
- create and update humans or human profiles
- create and update work items
- record attempts
- record evidence runs
- record review verdicts
- record human decisions or acceptance
- record outcomes
- close or complete work
- explain the next action at each state

Manual JSON editing may remain possible, but it should not be the primary way
to operate the system.

The repo is not complete if it can show a queue but cannot safely move work
through the queue.

### 4. Authority And Safety Boundaries

The repo must preserve human authority as a first-class rule.

It must clearly enforce or fail closed around:

- who may approve which work
- when human quorum is required
- when review is required
- when evidence is stale
- when review is stale
- which paths or resources are in scope
- which actions are forbidden
- when AI may proceed
- when AI must stop and ask a human

For high-risk work, the repo must make authority boundaries harder to bypass,
not easier.

The repo is not complete if approval, review, scope, or quorum are only
comments in docs and not represented in data, commands, and tests.

### 5. Evidence And Review Integrity

Evidence and review must be tied to the work they evaluate.

A complete repo should track:

- work item id
- attempt id
- commit or head reference where applicable
- commands run
- pass, fail, or skipped status
- artifact references
- reviewer identity or role
- review verdict
- findings
- residual risks
- timestamps
- freshness state

The system must detect stale evidence and stale reviews.

The repo is not complete if an old passing check can silently justify newer
changes.

### 6. Tests Prove Behavior, Not Only Imports

The test suite must prove the important behavior.

It should include:

- model loading tests
- schema validation tests
- invalid fixture tests
- queue state tests
- detail assembly tests
- scope allow/block tests
- stale evidence tests
- stale review tests
- quorum tests
- human authority tests
- lifecycle transition tests
- CLI smoke tests
- regression tests for known failures

The repo should have enough tests that a maintainer can change the code without
guessing whether they broke the product model.

The repo is not complete if tests only prove that the happy-path example loads.

### 7. CI And Quality Gates

The repo must have a normal CI path.

CI should run:

- unit tests
- CLI smoke tests
- schema validation
- formatting or style checks
- type checks if the project uses typed Python seriously
- any focused regression suites

CI must be documented and should run on pull requests.

The repo is not complete if quality depends on a developer remembering to run
local commands manually.

### 8. Data Model Versioning And Migration

The workspace schema must have a versioning story.

A complete repo should define:

- schema version field
- compatibility expectations
- migration path for old workspace files
- validation errors that explain what to fix
- fixtures for supported schema versions

The repo is not complete if changing the schema would strand existing
workspaces with no migration guidance.

### 9. Real Examples

The repo must include examples that show the product honestly.

Examples should cover:

- low-risk light work
- standard governed work
- high-risk work requiring stronger review or quorum
- blocked work
- stale evidence
- stale review
- accepted or completed work
- recorded outcome
- at least one decision requiring human judgment

The examples should be useful as both documentation and test fixtures.

The repo is not complete if the example is too small or too polished to reveal
real operating states.

### 10. Professional Documentation

The docs must cover more than product philosophy.

A complete repo should include:

- quickstart
- installation
- command reference
- architecture overview
- core object model
- source-of-truth rules
- lifecycle guide
- authority and human decision guide
- evidence and review guide
- maintainer guide
- testing guide
- troubleshooting guide
- roadmap or known gaps
- security policy or security notes
- contribution expectations

Docs should make clear what is implemented versus aspirational.

The repo is not complete if docs overstate maturity.

### 11. Developer Experience

A new maintainer should be able to make a change confidently.

The repo should provide:

- simple package layout
- clear module boundaries
- small commands with predictable output
- useful error messages
- documented fixtures
- one obvious verification command
- no hidden dependency on old Palari Orchestrator state
- no generated files committed accidentally
- no ignored local state required for normal operation

The repo is not complete if only the original author understands how to extend
it.

### 12. Security And Secret Hygiene

The repo must be safe by default.

It should:

- not include secrets
- not require secrets for basic local verification
- document any future secret use
- avoid logging sensitive data
- fail closed for unknown authority
- keep broker or external side effects disabled unless explicitly implemented
- keep policy acceptance simulation-only unless a future approved design changes
  that rule

The repo is not complete if a normal test or demo can accidentally perform an
external side effect.

### 13. Integration Boundaries

The repo should define how it interacts with surrounding systems.

This includes:

- GitHub or PR integration expectations
- branch and merge assumptions
- external maintainer mode
- relationship to the old Palari Orchestrator
- whether old artifacts can be imported
- what should never be imported
- how future web UI or API layers should consume the read model

The repo is not complete if its boundaries are unclear enough that future
agents might copy old ceremony back into it by accident.

### 14. Outcome Learning

Outcomes must not be decorative.

A complete repo should make outcomes useful for:

- understanding whether work helped
- recording model or worker performance
- identifying follow-up work
- improving adaptive intensity
- improving future queue recommendations

The repo is not complete if outcomes are stored but never used by any read
model, command, or decision process.

### 15. Release And Operational Readiness

If the repo is meant to be used by other people, it needs operational basics.

Depending on the intended distribution, this may include:

- versioning
- changelog
- release process
- package metadata
- supported Python version
- compatibility policy
- backup/export guidance for workspace data
- recovery guidance for invalid workspace state

The repo is not complete if a user can run it once but cannot understand how it
will evolve safely.

## Minimum Professional Foundation

The first version that can honestly be called a professional local foundation
should include:

- documented fresh-clone setup
- passing CI
- schema versioning
- validated example workspaces
- queue, detail, state, validate, and scope commands
- authoring commands for all core objects
- lifecycle commands for evidence, review, human decision, and outcome
- fail-closed checks for scope, evidence freshness, review freshness, and
  authority/quorum
- regression tests for those gates
- clear maintainer docs
- clear known gaps

This version may still omit:

- web dashboard
- real broker execution
- real policy acceptance
- advanced GitHub automation
- enterprise team administration
- signed gate/key custody

Those omissions are acceptable only if the repo says so plainly.

## Things That Do Not Prove Completeness

The repo should not be considered complete merely because:

- it has a README
- tests pass
- the example workspace loads
- the queue prints something useful
- the schema exists
- the docs describe future concepts
- an AI agent says the milestone is complete
- the code is clean
- the repo is small

Those are good signs, but they are not enough.

## Current Repo Interpretation

At the time this document was written, Palari Company OS should be treated as a
working professional foundation, not a complete finished Company OS.

It has:

- a clean skeleton
- product docs
- core schemas and models
- an example workspace
- queue, detail, state, validate, scope, history, and maintainer commands
- authoring and lifecycle commands
- validation, authority, freshness, quorum, and scope checks
- a light external maintainer status command
- local tests, install smoke, and CI verification

It still needs for a finished Company OS product:

- a web or API surface if the product should be operated outside the CLI
- real broker execution only after explicit safety design
- real policy acceptance only after explicit authority design
- enterprise administration
- signed gate/key custody
- concurrent storage or a merge/conflict model
- deeper outcome-driven recommendations

Until those exist, the repo should be described as:

```text
Palari Company OS v0 foundation: professional local workspace/CLI foundation,
not a finished Company OS product.
```
