# Contracts And Invariants

These are the repo truths agents must preserve when changing Palari Company OS.
They use plain product words first and exact stored or protocol names where a
code change must match them. See
[Plain Language](../product/plain-language.md).

## Data And Validation

- Workspace data is local, file-backed, inspectable JSON.
- Unknown workspace fields fail closed.
- Workspace writes are one-writer-at-a-time. If the file changed after a
  command loaded it, the command must fail closed and ask the agent to retry.
- Task IDs are identity only. New quick-created work uses collision-resistant
  opaque IDs; legacy IDs remain valid. Dependency authority exists only through
  explicit, reference-valid, duplicate-free, acyclic `dependency_ids` edges.
- New workspaces begin replayable v2 tamper-evident history. A workspace with a
  committed valid v1 journal is read-only until an operator explicitly
  activates v2. That activation does not rewrite v1: the v2 restore point
  content-binds the exact sealed predecessor, then deterministic value deltas
  form the streamed tail. Existing unjournaled workspaces also require an
  explicit v2 restore point; no current record is written under the v1 filename.
  Prepared and
  committed records still bracket the atomic, fsynced workspace replacement;
  divergence, corruption, pending transactions, and continuity breaks remain
  visible.
- Check results for self-mutating state files (`workspace.json` and the
  current governance journal) bind their bytes at the exact Git head. The live
  history is verified separately against the current workspace, so recording
  checks does not stale itself and history corruption or state divergence
  still fails closed. Ordinary output files
  remain bound to current filesystem bytes.
- Ordinary queue, detail, and status operations translate recorded checks
  through a status view that grants no permission. They do not inspect output
  bytes or scan history. Trusted transitions and explicit Approval
  Inbox/handoff operations perform current check and history verification;
  nested verification in one such operation may share
  only an in-memory request context. Persistent caches never become authority.
- Split collection files are read-time only for ordinary authoring; authoring
  writes refuse split workspaces rather than silently collapsing records.
  This reader is parked compatibility, not a supported write or migration
  surface.
- Collection file paths must be workspace-relative and must not contain `..`.
- Declared `path_intents` are exact, normalized, duplicate-free, and
  prefix-disjoint. Create/modify require the intended regular-file Git state;
  delete requires an absent exact path plus an observed Git deletion. Legacy
  work without intents retains its presence-required output behavior.
- Repo examples must not contain raw secrets or machine-local absolute paths.
- Sealed v1 predecessor verification is linear in parsed journal records. V2 hashes the
  sealed v1 predecessor as bytes and strictly streams only its compact segment,
  retaining one replay projection rather than all records or projections.
  Request-local reuse may remove duplicate scans only while workspace, v1, and
  v2 filesystem witnesses remain unchanged; no persistent cache may authorize
  a transition.

## Permissions And Approval

- Human approval is explicit. Agents do not silently inherit approval power.
- Approvals, reviews, run records, check results, and results are separate
  records with separate meanings.
- Approval Packs compress one human approval interaction, never independent
  review or item evidence.
  Pack and member digests are exact; recursive dependency bindings retain
  exact check/output freshness even outside a narrowed pack. Changed members
  or dependencies fail closed, and external or irreversible actions remain
  individually gated.
- Approval Pack v3 decisions bind the exact canonical presentation artifact
  named by the human command and retain both declared and effective final
  approval counts. The reader remains compatible with pack v2. Relevant
  decision-context changes stale the old presentation. One action may perform
  only crash-safe local automatic finishing already allowed by current
  authority; it cannot manufacture review, another vote, external effects, or
  expanded permission. Approval Pack v1 is unsupported; an unsupported pack or
  missing presentation binding fails closed.
- Agents may prepare, refresh, or summarize packs. Only a human may invoke the
  simple `approve` or pack-decision authority surface; supported agent shell
  adapters hard-deny both.
- The one-task `approve` command derives a singleton pack and presentation and
  delegates mutation to the existing pack transaction. Handoff emits it with a
  machine-supplied presentation binding; a bare invocation selects current
  state at invocation. It accepts only reversible local work whose current
  qualified human action completes the effective final count; it cannot create
  a review, missing vote, external effect, or wider permission. Same-human
  retry must validate the exact stored decision, presentation token, and
  acceptance before returning a no-op.
- Authority feasibility is checked before execution and review. A selected
  reviewer must be independent and eligible and must leave enough distinct
  qualified human approvers. Approval commands are emitted only for named
  humans who can execute them against the current state.
- New accept-ready reviews bind the exact terminal attempt, receipt, evidence,
  reviewed head, and work contract. Concrete Review Guide actions carry the
  current binding digest and fail if that proof changes before recording.
  Bound reviews are immutable.
- Schema v2 loads historical unbound non-accepting reviews for inspection, but
  rejects unbound `accept-ready`. Older workspace schema versions fail closed;
  current runtime does not infer or manufacture upgraded authority.
- Each human's latest timezone-ordered decision for the exact review and
  evidence controls quorum; a prior rejection or defer does not suppress a
  later exact approval action, while contradictory or ambiguous ordering fails
  closed.
- Suggested checks recommend what to inspect; they do not grant approval.
- Playbooks are process guidance; the task limits and Palari permissions
  remain the source of truth.

## Agent Contract

- `palari agent brief` is read-only.
- `palari agent start` saves the exact task brief and writes a local task lock for
  ready execution work, including a hashed metadata-only Git dirty baseline
  and a dedicated local Git ref/reflog witness when Git is available. Releasing
  and restarting the same task must reuse that baseline rather than
  laundering later changes.
- For every complete Git-backed baseline, including a first claim and any
  restart or expiry recovery, Palari compares a canonical execution-authority
  projection from exact baseline workspace bytes with strict current root and
  split-collection bytes before it can
  acquire a lease, then repeats that comparison under the final local workspace
  mutation lock and holds that lock through witness, baseline, packet, and claim
  persistence. It covers the acting Palari's identity, role, scope, worker,
  standards, input/memory boundaries and mode; reviewer goal linkage; work and
  dependency lifecycle authority; paths; selected-source provider/URI/external
  identity; capabilities; outputs; coordination policy; and static completion
  gates. Mutable proof records and current builder/reviewer proof context are
  deliberately excluded. A changed authority, malformed strict JSON, unsafe
  collection path, or mismatched split collection fails closed. Journal actor
  labels and `agent handoff` do not authorize a rebaseline. Preserve the old
  record and create a successor work item for a changed contract; unrelated
  read-model projection remains eligible for separate classification.
- If a first claim's current work declaration is absent from the baseline commit,
  Palari captures a normalized digest catalog for every declared Palari in both
  execute and review modes. The catalog carries only actor IDs, modes, and
  authority digests and is embedded in the hashed baseline beside Git and dirty
  path metadata. A v2 witness's oldest reflog message binds its exact canonical
  digest. A later actor/mode absent from that catalog or any changed
  catalog-bound authority fails closed. A historical current-only baseline
  without a catalog cannot be safely upgraded; preserve it and use a successor.
- A persisted Git witness is checked before lease acquisition and again while
  the final workspace lock is held. Missing refs, changed heads, and mismatched
  v2 catalog messages block restart before a durable claim can be renewed.
- `agent start --next` selects one candidate only through the existing
  `agent next` eligibility policy, then invokes the same explicit start path.
  It must not claim blocked work or invent a second priority/authority rule.
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
  advisory unless a separately verified adapter provides it. Local workspace
  selectors and workspace paths are normalized only in the portable projection,
  which continues to hash every other task-brief field; the persisted task brief
  and claim keep their exact local selector and authority binding. Missing,
  malformed, duplicate-key, digest-mismatched, path-mismatched, or
  current-packet-mismatched contracts invalidate the claim. Claim schema v2
  requires both binding fields, so removing both cannot fall back to another
  path. Claim schema v1 is unsupported and is not upgraded in place.
- Git integration readiness compares the exact attempt commit with a target in
  an isolated temporary clone. Divergent projections always require refreshed
  exact proof even when the simulated merge is clean.
- Blocked packets must not be claimed.
- Agent packets define allowed paths, sources, actions, stop conditions, and
  required outputs.
- `agent check` verifies proof state and, when requested, observed file changes
  against the packet boundary.
- One request-local agent operation shares a packet, check, and directive
  across aggregate read views. The pure directive compiler classifies the next
  owner/action; transition gates remain the sole mutation authority. Exact
  Approval Inbox and proof-binding operations own journal verification.
- `agent release` with reason and next action durably records one claim-bound blocked attempt, exact state
  bindings, reason, observation, and next safe action before claim release.
  Exact crash retry is idempotent. A projection-bound retry recognizes only the
  durable claim-epoch transition from the packet's original work status to
  `blocked`; it normalizes that single field and rehashes every other scope-
  authority field before the exact attempt is released. It never creates
  receipt, evidence, review, human decision, acceptance, outcome, or convergence
  records. It requires an existing writable journal; legacy activation remains
  an explicit checkpoint with a visible pre-checkpoint continuity boundary.
- `agent advance` is the sole current execution-to-proof path. It attributes
  every committed path from the persisted claim-start head to current `HEAD`,
  not merely the tip commit. The claim, companion baseline, Git witness ref,
  and original witness reflog entry must agree.
- `agent advance` uses that complete claim-start range and packet boundary,
  runs only built-in shell-free verification profiles, rechecks the exact plan,
  and atomically reconciles attempt, receipt, current exact evidence, and
  closeout records. Completion always requires current passing evidence bound
  to the exact attempt, receipt, head, and output artifacts and evaluated
  against the current work contract.
  Only R1/light/0-approval work with no allowed, planned, queued, or actual
  external writes may omit independent review and human acceptance; every
  other item stops at the next required authority boundary.
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
- Supported native agent hooks deny human-attributed and packet-authority Palari
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
- Supported host adoption installs or reuses the portable repository contract.
  Claude and Codex also install the claim-bound Git commit gate and tested
  session hooks (strict no-claim on adoption); Codex requires explicit
  repository-hook trust. Cursor is a tested advisory host profile — the Git
  commit gate is opt-in (`--strict-git`, `cursor install`, or `git install`).
  No profile may grant review or human authority.
- Latest trust records are selected by timezone-normalized instants, then stable
  record id, never by the lexical spelling of an ISO timestamp offset.
- Canonical path, traversal, symlink, ambiguous-claim, and incomplete Git
  observations fail closed. Only unchanged start-time dirt is excluded from
  agent attribution.
- JSON agent command failures must remain machine-readable when `--json` is
  requested.

## Portable Verification (PCAW)

- PCAW statements are strict canonical JSON: duplicate keys, floats, unsafe
  integers, invalid Unicode, unknown fields, unsupported algorithms, and
  ambiguous timestamps fail closed.
- Full verification reads only normalized relative regular-file subjects beneath
  the selected root. Traversal, sibling-prefix confusion, symlinks, missing
  files, changed-during-read files, and digest mismatches fail closed.
- Statement-only verification never claims artifact or acceptance verification.
- The pure rules evaluator derives the PCAW scope, subject, evidence, receipt,
  review, quorum, acceptance, and journal properties. Export adapters may normalize
  workspace data but are not part of the offline verifier trusted-code base.
- PCAW v1 attribution is declared, not cryptographically authenticated. It
  grants no acceptance, merge, push, deployment, or external-write authority.
- PCAW v1 does not claim portable deletion-history proof. Local workspace
  deletion tombstones remain outside the v1 protocol guarantee.
- Removed restore-point spellings remain denied by session hooks as obsolete
  authority-shaped input.

## Sources, Run Records, And External Actions

- Sources define what an agent may use; unlisted sources are outside the task.
- Run records (`receipts` in stored JSON) are human-facing records: what was used, created, changed, not
  done, and undoable.
- Check results (`evidence`) are not the same thing as a run record. A run
  record alone can never complete work; every completion path requires current
  checks tied to the exact version.
- Dry-run integration plans never call providers.
- External writes require explicit approval and an outbox boundary before any
  supported live execution.
- Queued external writes are not actual external writes.

## Documentation

- Repo truth belongs in committed docs, not machine-local memory.
- Every tracked file belongs to one branch in `docs/agent/repo-tree.json`.
  Each split has three to five plain-named parts, with no overlap and no gaps.
- `AGENTS.md` should stay compact and point to deeper canonical docs.
- Update docs when commands, schema, agent behavior, integrations, required checks, or
  examples change in ways future agents need to know.
- Preserve the [Minimality Contract](../product/minimality-contract.md): no
  runtime dependency, background service by default, live provider write without
  approval, OAuth by default, or schema growth without changed safety behavior.
- Check the [Public Surface](../product/public-surface.md) before changing CLI,
  provider, visual, example, or archive surfaces.
