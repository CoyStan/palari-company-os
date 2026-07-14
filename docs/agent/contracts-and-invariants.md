# Contracts And Invariants

These are the repo truths agents must preserve when changing Palari Company OS.

## Data And Validation

- Workspace data is local, file-backed, inspectable JSON.
- Unknown workspace fields fail closed.
- Workspace writes are one-writer-at-a-time. If the file changed after a
  command loaded it, the command must fail closed and ask the agent to retry.
- Split collection files are read-time only for ordinary authoring; authoring
  writes refuse split workspaces rather than silently collapsing records.
  Schema migration preserves record placement, detects concurrent changes to
  every participating file, and advances the root version last.
- Collection file paths must be workspace-relative and must not contain `..`.
- Repo examples must not contain raw secrets or machine-local absolute paths.

## Authority

- Human authority is explicit. Agents do not silently inherit approval power.
- Human decisions, reviews, receipts, evidence, and outcomes are separate
  records with separate meanings.
- New accept-ready reviews bind the exact terminal attempt, receipt, evidence,
  reviewed head, and work contract. Bound reviews are immutable.
- Schema v2 loads historical unbound non-accepting reviews for inspection, but
  rejects unbound `accept-ready`; v1 migration blocks those legacy verdicts and
  revokes their dependent acceptance.
- Each human's latest timezone-ordered decision for the exact review and
  evidence controls quorum; contradictory or ambiguous ordering fails closed.
- Gates recommend what to inspect; they do not grant acceptance authority.
- Playbooks are process guidance; the work item scope and Palari authority
  remain the source of truth.

## Agent Contract

- `palari agent brief` is read-only.
- `palari agent start` persists the exact packet and writes a local claim for
  ready execution work, including a hashed metadata-only Git dirty baseline
  and a dedicated local Git ref/reflog witness when Git is available. Releasing
  and restarting the same work item must reuse that baseline rather than
  laundering later changes.
- Blocked packets must not be claimed.
- Agent packets define allowed paths, sources, actions, stop conditions, and
  required outputs.
- `agent check` verifies proof state and, when requested, observed file changes
  against the packet boundary.
- `agent done` attributes every committed path from the persisted claim-start
  head to current `HEAD`, not merely the tip commit. The claim, companion
  baseline, Git witness ref, and original witness reflog entry must agree.
- Execute hooks rebuild the current workspace packet before granting writes;
  coordinated claim/packet self-rehashing cannot expand current scope.
- Generic work updates cannot change an actively claimed packet, and an active
  claim cannot renew against different current packet authority.
- Supported agent hooks deny human-attributed and packet-authority Palari
  mutations and require a human decision for opaque interpreters, unreviewed
  or path-qualified executables, unquoted pathname expansion, recursive/tree
  writes, hidden backup outputs, hook self-modification, unclassified Palari
  commands, dynamic shell indirection, or Git witness mutations, including Git
  global-option forms. Human integration enqueue/cancel/send and Linear
  adoption are agent-inaccessible. Every shell segment is classified even when
  another segment has a visible write target; command environment and
  helper-launching options cannot inherit read-only status. Workspace truth,
  split collection files, `.palari/`, and Git metadata cannot be directly
  rewritten around those gates, including after claim release. Option-encoded
  destinations and linked worktree/common Git directories are part of the same
  protected boundary;
  compact/newline shell segments and ordinary directory destinations must
  preserve the effective path. Repository overrides and pager/filter/ripgrep
  helpers are execution-capable, not read-only. Global option abbreviations do
  not create a second CLI grammar, and destructive protected-path ancestors
  require review.
- Canonical path, traversal, symlink, ambiguous-claim, and incomplete Git
  observations fail closed. Only unchanged start-time dirt is excluded from
  agent attribution.
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
