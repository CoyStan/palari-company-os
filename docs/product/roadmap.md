# Roadmap And Known Gaps

Implemented now:

- workspace schema v1
- queue/detail/state/validate/scope/maintainer commands
- authoring commands for all core objects
- lifecycle commands for evidence, review, human decision, completion, and
  outcome
- fail-closed gates for scope, stale evidence, stale review, human authority,
  and quorum
- CI verification

Intentionally omitted:

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

