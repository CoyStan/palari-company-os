# Contracts And Invariants

These are the repo truths agents must preserve when changing Palari Company OS.

## Data And Validation

- Workspace data is local, file-backed, inspectable JSON.
- Unknown workspace fields fail closed.
- Workspace writes are one-writer-at-a-time. If the file changed after a
  command loaded it, the command must fail closed and ask the agent to retry.
- Split collection files are read-time only for now; authoring writes refuse
  split workspaces rather than silently collapsing records.
- Collection file paths must be workspace-relative and must not contain `..`.
- Repo examples must not contain raw secrets or machine-local absolute paths.

## Authority

- Human authority is explicit. Agents do not silently inherit approval power.
- Human decisions, reviews, receipts, evidence, and outcomes are separate
  records with separate meanings.
- Gates recommend what to inspect; they do not grant acceptance authority.
- Playbooks are process guidance; the work item scope and Palari authority
  remain the source of truth.

## Agent Contract

- `palari agent brief` is read-only.
- `palari agent start` persists the exact packet and writes a local claim for
  ready execution work.
- Blocked packets must not be claimed.
- Agent packets define allowed paths, sources, actions, stop conditions, and
  required outputs.
- `agent check` verifies proof state and, when requested, observed file changes
  against the packet boundary.
- JSON agent command failures must remain machine-readable when `--json` is
  requested.

## Sources, Receipts, And External Actions

- Sources define what a Palari may use; unlisted sources are out of scope.
- Receipts are human-facing trust records: what was used, created, changed, not
  done, and undoable.
- Governance evidence is not the same thing as a receipt.
- Dry-run integration plans never call providers.
- External writes require explicit approval and an outbox boundary before future
  live execution.
- Queued external writes are not actual external writes.

## Documentation

- Repo truth belongs in committed docs, not machine-local memory.
- `AGENTS.md` should stay compact and point to deeper canonical docs.
- Update docs when commands, schema, agent behavior, integrations, gates, or
  examples change in ways future agents need to know.
- Preserve the [Minimality Contract](../product/minimality-contract.md): no
  runtime dependency, background service by default, live provider write without
  approval, OAuth by default, or schema growth without governance behavior.
- Check the [Public Surface](../product/public-surface.md) before changing CLI,
  provider, visual, example, or archive surfaces.
