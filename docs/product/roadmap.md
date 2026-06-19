# Roadmap And Known Gaps

Implemented in the v0.1 local foundation:

- workspace schema v1
- queue/detail/state/validate/scope/maintainer commands
- authoring commands for all core objects
- lifecycle commands for evidence, review, human decision, completion, and
  outcome
- fail-closed gates for scope, stale evidence, stale review, human authority,
  and quorum
- append-only workspace history for successful mutating commands
- CI and install-smoke verification
- repo-local dogfood workspace for real Palari Company OS maturity work

Intentionally omitted from v0.1:

- web dashboard
- real broker execution
- real policy acceptance
- advanced GitHub automation
- enterprise administration
- signed gate/key custody

Likely next steps:

- split large workspaces into multiple source files
- add richer migration tests as schema versions evolve
- add import/export tooling
- add API or web read-model layer
- add optional JSON Schema validation dependency if it becomes useful
