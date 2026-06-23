# Roadmap And Known Gaps

Implemented in the v0.1 local foundation:

- workspace schema v1
- queue/detail/state/validate/scope/maintainer commands
- authoring commands for all core objects
- lifecycle commands for evidence, review, human decision, completion, and
  outcome
- integration registry, dry-run payload planner, auditable integration plan
  records, and human approve/reject/cancel decisions for Slack/GitHub/Jira/email
  style notifications without live provider calls
- integration outbox records for approved external-action plans waiting at the
  future execution boundary, including human cancellation before live execution
- fail-closed gates for scope, stale evidence, stale review, human authority,
  quorum, integration references, integration allowed events/actions, and raw
  secret values
- agent-ready repo documentation with `docs check`, `docs map`, `docs init`,
  compact packet doc hints, and canonical `docs/agent/` orientation docs
- append-only workspace history for successful mutating commands
- CI and install-smoke verification
- repo-local dogfood workspace for real Palari Company OS maturity work

Intentionally omitted from v0.1:

- web app
- live Slack/GitHub/Jira/email connector calls
- real broker execution
- real policy acceptance
- advanced GitHub automation
- enterprise administration
- signed gate/key custody

Likely next steps:

- design live execution for approved and queued integration outbox items
- add richer migration tests as schema versions evolve
- add import/export tooling
- add API or web read-model layer
- add optional JSON Schema validation dependency if it becomes useful
