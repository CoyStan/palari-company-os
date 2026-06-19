# Contributing

Use ordinary software engineering.

Do:

- keep changes scoped
- update docs when commands or data contracts change
- add regression tests for lifecycle, authority, scope, evidence, and review
  behavior
- run `./scripts/verify.sh`

Do not:

- import old Palari Orchestrator POS ticket history
- import old evidence bundles, reports, claims, worktrees, caches, or runtime
  state
- add secrets
- enable real broker side effects
- turn policy simulation into real authority
- reintroduce the old ticket ceremony as the default workflow

