# Contracts And Invariants

These are the repo truths agents must preserve when changing Palari Company OS.

## Data And Validation

- Workspace data is local, file-backed, inspectable JSON.
- Unknown workspace fields fail closed.
- Workspace writes are one-writer-at-a-time. If the file changed after a
  command loaded it, the command must fail closed and ask the agent to retry.
- Work-item IDs are identity only. New quick-created work uses collision-resistant
  opaque IDs; legacy IDs remain valid. Dependency authority exists only through
  explicit, reference-valid, duplicate-free, acyclic `dependency_ids` edges.
- New workspaces begin a replayable governance journal. Legacy workspaces keep
  working until an operator explicitly checkpoints them. Prepared and committed
  journal records bracket the atomic, fsynced workspace replacement; divergence,
  corruption, pending transactions, and continuity breaks remain visible.
- Evidence for self-mutating governance projection files (`workspace.json`,
  legacy history, and the governance journal) binds their bytes at the exact
  evidence Git head. The live journal is verified separately against the
  current workspace, so recording proof does not stale itself and journal
  corruption or projection divergence still fails closed. Ordinary artifacts
  remain bound to current filesystem bytes.
- One bounded read-model operation may reuse a journal-verification result only
  through an in-memory request context and only while SHA-256 fingerprints of
  both `workspace.json` and the journal remain exact. Byte changes force fresh
  verification; persistent advisory caches never become acceptance authority.
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
- Approval Packs compress one human approval interaction, never independent
  review or item evidence.
  Pack and member digests are exact; recursive dependency bindings retain
  exact proof/artifact freshness even outside a narrowed pack. Changed members
  or dependencies fail closed, and external or irreversible actions remain
  individually gated.
- New Approval Pack v2 decisions bind the exact canonical presentation artifact
  named by the human command. Relevant decision-context changes stale the old
  presentation. One action may perform only the crash-safe local convergence
  already authorized by current quorum; it cannot manufacture review, another
  vote, external effects, or expanded authority. Historical pack v1 decisions
  remain readable but are not presentation-bound.
- Agents may prepare, refresh, or summarize packs. Only a human may invoke the
  pack-decision authority surface; Claude agent shells hard-deny it.
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
- Linked Git worktrees coordinate active ownership through an expiring atomic
  ref-to-blob lease. A foreign live lease and malformed or contradictory lease
  state fail closed. Different work items retain independent leases.
- `agent start --isolate` requires a committed work definition, creates or
  resumes a deterministic local branch/worktree, and grants no review,
  acceptance, merge, push, deploy, or external-write authority.
- Every new ready claim binds a deterministic portable session contract stored
  beneath `.palari/packets/session-contracts/`. The contract contains no
  wall-clock compilation time or absolute local path, grants no authority by
  itself, and labels host write/read/stop enforcement as adapter-required or
  advisory unless a separately verified adapter provides it. Missing,
  malformed, duplicate-key, digest-mismatched, path-mismatched, or
  current-packet-mismatched contracts invalidate the claim. New claim schema v2
  requires both binding fields, so removing both cannot fall back to legacy
  handling. Historical claim schema v1 records without the additive binding
  remain readable until restarted, when they are upgraded to v2.
- Git integration readiness compares the exact attempt commit with a target in
  an isolated temporary clone. Divergent projections always require refreshed
  exact proof even when the simulated merge is clean.
- Blocked packets must not be claimed.
- Agent packets define allowed paths, sources, actions, stop conditions, and
  required outputs.
- `agent check` verifies proof state and, when requested, observed file changes
  against the packet boundary.
- `agent done` attributes every committed path from the persisted claim-start
  head to current `HEAD`, not merely the tip commit. The claim, companion
  baseline, Git witness ref, and original witness reflog entry must agree.
- `agent advance` uses the same complete claim-start range and packet boundary,
  runs only built-in shell-free verification profiles, rechecks the exact plan,
  and atomically reconciles attempt, receipt, evidence, and closeout records.
  It may complete R1/light/0 work; higher-risk work stops at independent review.
  After a current separate review and qualified human decision already exist,
  the shared bounded fixed-point driver may derive the acceptance record and
  terminalize the work mechanically. Authority-producing functions invoke that
  driver immediately; `agent advance` remains an idempotent recovery surface.
  Later Git state is reusable only when post-proof committed and dirty tracked
  paths are governance projection data. The driver must never create the review
  or human decision, and cycle, no-progress, or iteration-limit states fail
  closed.
- Explicit exact-head proof refresh is claimless. A current changes-requested
  review may route byte-unchanged ordinary outputs through that transaction after
  separately governed descendant commits; dry-run previews it without
  verification or mutation. Self-mutating workspace, history, and journal
  projections are classified separately: their previous and current exact Git
  hashes and statuses are reported in one uniform record as unchanged or
  rebound; malformed digests or statuses fail closed. A missing legacy
  projection hash is explicit `not-recorded`, never inferred. The receipt
  discloses that recording proof mutates those projections after the evidence
  head. Every raw
  commit is compared with every parent, with Git replacement objects disabled.
  Any non-projection output touch, even if later restored, active claim,
  mismatched review head, dirty tracked state, or divergent history fails closed.
  Refresh creates new attempt, receipt, and evidence only; prior review and human
  authority never carry forward.
- Blockers expose stable resolver metadata. Current authority followed only by
  mechanical bookkeeping is automatic reconciliation; terminal work is closed,
  not a blocker; external, review, and human boundaries remain distinct.
- Verification cache files are advisory diagnostics, never proof authority.
  They bind exact state and malformed or contradictory records fail closed, but
  a structurally valid cached pass is still rerun. Only exact proof already
  reconciled into current governed evidence may skip subprocess verification.
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
  helpers are execution-capable, not read-only. Git pathspec-file imports,
  helper-option abbreviations, abbreviated GNU write options,
  assignment-position tilde expansion, and Bash `|&` composition require
  review. Global Palari option abbreviations do not create a second CLI grammar,
  and destructive protected-path or standard Claude-settings ancestors require
  review. Git pathspec magic/globs, dash-prefixed operands after `--`, and
  agent-safe Palari mutations pointed at another workspace also require review.
- Latest trust records are selected by timezone-normalized instants, then stable
  record id, never by the lexical spelling of an ISO timestamp offset.
- Canonical path, traversal, symlink, ambiguous-claim, and incomplete Git
  observations fail closed. Only unchanged start-time dirt is excluded from
  agent attribution.
- JSON agent command failures must remain machine-readable when `--json` is
  requested.

## Proof-Carrying Work

- PCAW statements are strict canonical JSON: duplicate keys, floats, unsafe
  integers, invalid Unicode, unknown fields, unsupported algorithms, and
  ambiguous timestamps fail closed.
- Full verification reads only normalized relative regular-file subjects beneath
  the selected root. Traversal, sibling-prefix confusion, symlinks, missing
  files, changed-during-read files, and digest mismatches fail closed.
- Statement-only verification never claims artifact or acceptance verification.
- The pure governance kernel derives scope, subject, evidence, receipt, review,
  quorum, acceptance, and journal properties. Export adapters may normalize
  workspace data but are not part of the offline verifier trusted-code base.
- PCAW v1 attribution is declared, not cryptographically authenticated. It
  grants no acceptance, merge, push, deployment, or external-write authority.
- Every committed journal projection is a content-addressed checkpoint.
  Restoration appends a human-attributed transition only for an effect-free
  local chain. Every committed projection after the earliest matching digest
  is inspected; external effects block restoration before any projection
  change, even if later local state hid the effect or returned to the target.
- `history --restore` is a human-only shell authority command. An agent cannot
  acquire it by supplying a declared human id.

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
