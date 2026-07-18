# Agent Contract

Palari Company OS is primarily an operating contract for AI agents. Humans use
structured read models, Mission Control, receipts, blockers, and approval
records to supervise work.
Agents use the CLI to discover one bounded task, receive context, act inside
scope, and stop when human authority is required.

## Canonical Loop

Ordinary execution starts by selecting and claiming one safe item:

```bash
palari agent start --next --as PALARI-ID --json
```

Explicit inspection and selection remain available:

```bash
palari agent next --as PALARI-ID --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --session-contract --json
palari agent start WORK-ID --as PALARI-ID --mode execute --json
palari agent brief WORK-ID --as PALARI-ID --mode review --json
```

`palari agent brief` is a read-only preview. `palari agent start` is the
operational entry point for ready execution work: it persists the exact packet
the agent received, persists its deterministic portable session contract, and
records a digest-bound local lease claim. Blocked packets remain read-only and
are not claimed. `agent brief --session-contract` emits the portable contract
instead of the full packet without writing runtime state. `agent start --next`
uses the same queue eligibility and packet compiler, then persists exactly one
ready packet and claim. It does not infer new authority or silently choose
blocked work. Use explicit `start WORK-ID --isolate` when a committed work item
needs its own deterministic branch and worktree.

For first adoption in a Git worktree, `palari init` writes only missing
agent-ready guidance and makes one path-limited local commit of the new
governance projection plus those generated docs. Add `--host HOST` to install
the portable contract, claim-bound Git gate, and any proven project-local host
hooks in the same anchored action. Existing guidance, host configuration, and
unrelated staged or unstaged paths are preserved rather than absorbed into the
bootstrap commit. This is an immutable baseline bootstrap, not review,
acceptance, or authenticated human attribution.
`palari work add` idempotently recovers a missing starter anchor before changing
the work declaration. If a manually assembled workspace still has no committed
authority origin, `agent start` fails closed with one exact `git add` plus
path-limited `git commit --only` recovery action.

An existing Palari workspace uses `palari agent adopt --host HOST --as
PALARI-ID --json`. Claude and Codex have tested native session adapters; Codex
project hooks require explicit `/hooks` trust. Cursor, Devin, GLM, and generic
profiles install the portable contract and structural commit boundary but
remain explicitly advisory at session time. Adoption grants no review, human
decision, acceptance, merge, push, deployment, provider, or external-write
authority.

The ordinary loop is deliberately short:

1. Run `palari agent start --next --as PALARI-ID --json` and continue only when
   the returned packet is ready. Read and write only its allowed paths and
   sources.
2. Do the bounded work and commit it. Then run `palari agent advance WORK-ID
   --as PALARI-ID --json` once. It derives the complete claim-start range, checks
   exact create/modify/delete intent, runs fixed verification profiles, and
   atomically records deterministic attempt, receipt, evidence, and closeout
   state. It stops at independent review, human authority, external state, or a
   concrete blocker; it never creates a review or human decision.
3. Follow the one command returned at that boundary. After a separate current
   review, a qualified human opens `palari queue --approval-inbox --json`,
   inspects the exact presentation, and may run its bound `human-decision pack`
   command once. Current authority can trigger only deterministic local
   terminal bookkeeping.

Use `agent advance --dry-run` to inspect the plan, `agent check`, `finish`,
`handoff`, `doctor`, and `loop` for detailed diagnosis, and `agent done` as the
compatible R1/light/zero-approval shortcut. Proof refresh remains an explicit
claimless recovery path: `agent advance --refresh-verification --dry-run`
previews it, and the non-dry-run form creates fresh exact-head proof only when
ordinary governed outputs remain byte-identical. Prior review and human
authority never carry forward.

If execution must stop before proof is ready, run:

```bash
palari agent release WORK-ID --as PALARI-ID \
  --reason "Why work stopped" --next-action "The next safe step" --json
```

Parking durably records one blocked attempt, exact packet/head/workspace
bindings, observed in-scope and out-of-scope changes, the reason, and the next
safe action before releasing the owned execute claim. A retry after an
interrupted release is idempotent only for the same durable record and unchanged
repository state. Parking creates no receipt, evidence, review, decision,
acceptance, outcome, or convergence. Use bare `agent release` only when no
durable interrupted-work record is required. Parking requires an activated,
writable governance journal. A legacy workspace without one fails before
mutation with the exact `history --checkpoint` activation command; it never
silently claims continuity for earlier history.

For independent inspection work, use `--mode review` after a work item is in
`needs-review` or `receipt-ready`. A distinct source-authorized Palari may also
open a supplemental review packet when a positive human review is waiting on a
different acceptance identity. The packet is read-only with respect to work
outputs. It includes the review guide focus, attempt, evidence, receipt,
suggested verdicts, and typed reviewer candidates. A matching Palari reviewer
may record only its advisory verdict; it cannot create human acceptance.
`palari agent next --as PALARI-ID --mode review --json` ranks those reviewable
items as ready while keeping non-reviewable work blocked.

## Packet Purpose

The packet is a compact context compiler. It prevents agents from inferring a
workflow from many separate commands. A packet answers:

- who the agent is
- which work item is in scope
- why the work matters
- which paths, sources, and actions are allowed
- source readiness metadata such as data class, authority, steward, freshness,
  and redaction requirement
- which actions are forbidden
- what output is required
- what receipt, evidence, review, human decision, or integration state matters
- when the agent must stop
- which commands are safe to run next

The packet must not dump the whole workspace. It includes only directly related
records and explicit omitted-context notes.

Aggregate agent views share one request-local packet, check, directive, and
journal-verification observation. A pure directive compiler turns that current
check into state, owner, blocker class, and next safe action. It has no clock,
filesystem, mutation, review, or human-authority access. Transition checks—not
the directive—remain authoritative, and a changed journal witness forces a new
scan.

## Documentation Hints

Agent packets include compact repo-documentation context:

- `documentation_state` says whether agent-ready repo docs are present,
  partial, or missing.
- `recommended_docs` points to committed docs likely to help with the selected
  work item.
- `omitted_context` states that full documentation text was not loaded into the
  packet.

This keeps packets context-window-safe. Agents should read recommended docs only
when they need that orientation. Missing docs are low context, not a work
blocker; use `palari docs init --dry-run --json` to inspect the proposed starter
set.

## Gate Recommendations

`palari gate recommend WORK-ID --json` is a read-only companion to packets and
review guides. It does not review work and does not grant acceptance authority.
It chooses the review contracts likely to matter for the selected work item:

- prompt authority
- source boundary
- external writes
- human approval
- deploy/runtime
- privacy/multimodal
- product overclaim

Each recommended gate includes a reviewer role, what to inspect, blocker
checklist, required evidence, and accept-ready standard. Simple low-risk work can
return `no_special_gate_required: true`; that means use the normal
receipt/evidence/review loop, not that review is waived where the work item
requires it.

## Packet Status

`status: ready` means the agent may proceed inside the packet boundary.

`status: blocked` means the agent must not perform the work. It may run only the
commands listed in `next_allowed_commands`, or report the blockers to a human.

Finish, loop, next, handoff, and Approval Inbox JSON classify the resolver as
`automatic-reconciliation`, `agent-action`, `independent-review`,
`human-authority`, `external-state`, or `terminal`. A human-looking blocker is
not retained after the required authority already exists: current post-decision
bookkeeping reports `converge-ready` and points back to `agent advance`.
Completed work reports `closed` with no remediation blocker.

Common blocker codes include:

- `MISSING_PALARI`
- `MISSING_WORK_ITEM`
- `PALARI_NOT_ASSIGNED`
- `DEPENDENCY_NOT_TERMINAL`
- `SOURCE_MISSING`
- `SOURCE_NOT_ALLOWED`
- `EXTERNAL_WRITE_REQUIRES_APPROVAL`
- `HUMAN_DECISION_REQUIRED`
- `WORK_BLOCKED`
- `WORK_CLOSED`
- `INTEGRATION_BOUNDARY`
- `REVIEW_REQUIRED`
- `RECEIPT_READY_REVIEW`

## Boundaries

Agents must never:

- read secrets or raw provider tokens
- read or write outside `allowed_paths`
- use sources not listed in `allowed_sources`
- ignore source readiness fields in `allowed_sources`
- perform external writes without an approved integration plan and queued
  outbox state
- create durable memory without a future approved memory contract
- treat an informal source as policy
- bypass human decisions, review, receipts, evidence, or approval boundaries

## V1 Scope

Agent Packet Contract v1 keeps provider actions read-only, but the local agent
runtime writes packet/claim audit state and, when Git has a committed head, a
local Git witness for ready started work:

- `.palari/packets/PACKET-...json` stores the exact bounded packet.
- `.palari/packets/session-contracts/SESSION-CONTRACT-...json` stores the
  deterministic provider-neutral projection of packet scope, obligations,
  authority binding, enforcement status, and limitations. Its identifier is
  derived from its canonical digest; repeated compilation of the same packet
  authority produces identical bytes.
- `.palari/claims/WORK-ID.json` stores claim schema v2, the Palari, mode, lease
  expiry, packet id,
  context hash, portable-contract path and digest, and a hashed metadata-only
  Git dirty baseline for the active local claim. The baseline records
  path/status/stat metadata, never contents.
  Its `.baseline` companion survives claim release/restart for the same work
  item so an agent cannot reclassify its own later changes as pre-existing.
  For a committed claim-start head, `refs/palari/claims/...` and its oldest
  local reflog entry provide a separate Git-backed witness. All four views must
  agree before claim authority or `agent done` attribution is accepted.
  For every complete Git-backed baseline, including a first claim and any
  restart or expiry recovery, Palari derives a canonical execution-authority
  digest from exact baseline workspace bytes and strict current root and
  split-collection bytes before the lease, then repeats the comparison under the
  final workspace mutation lock and holds that lock through witness, baseline,
  packet, and claim persistence.
  It binds the acting Palari's identity, role, scope, worker, standards,
  input/memory boundaries and mode; reviewer goal linkage; work and dependency
  lifecycle authority; paths; selected-source provider/URI/external identity;
  capabilities; output contract; coordination policy; and static completion
  gates while deliberately
  excluding mutable proof records and current builder/reviewer proof context.
  An uncommitted or committed authority change, malformed/unsafe collection,
  or split mismatch fails closed. A declared journal actor or `agent handoff`
  does not authorize a reset: preserve the original record and create a
  successor work item for a changed contract. Unrelated read-model/journal
  projection may still be classified separately.
  When a first claim's current work declaration is absent from the baseline
  commit, Palari
  stores a normalized all-Palari execute/review digest catalog inside the hashed
  baseline instead of copying the workspace. The v2 Git witness's oldest reflog
  message binds the exact catalog digest. This keeps the no-extra-commit
  workflow while preventing release, expiry, another worktree, or a newly
  authorized reviewer from silently choosing a different authority origin.
  Catalog-free v1 witnesses remain compatible when that baseline commit already
  contains the work. A historical current-only baseline without a catalog fails
  closed and requires a successor because no durable authority origin exists.
  Existing witness refs, heads, and v2 catalog messages are verified before a
  restart lease and again under the final lock before local claim persistence.
  New v2 claims require both portable-contract binding fields. Historical v1
  claims without those fields remain readable and upgrade on restart; the
  schema marker is declared local state, not authentication against a hostile
  same-user process.

Implemented:

- `palari agent next --json`
- `palari agent next --all --json`
- `palari agent next --as PALARI-ID --json`
- `palari agent brief WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent brief WORK-ID --as PALARI-ID --mode execute --session-contract --json`
- `palari agent start --next --as PALARI-ID --mode execute --json`
- `palari agent start WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent start WORK-ID --as PALARI-ID --mode execute --isolate --json`
- `palari agent check WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent check WORK-ID --as PALARI-ID --mode execute --changed PATH --json`
- `palari agent check WORK-ID --as PALARI-ID --mode execute --git-diff --json`
- `palari agent release WORK-ID --as PALARI-ID --json`
- `palari agent release WORK-ID --as PALARI-ID --reason "..." --next-action "..." --json`
- `palari agent finish WORK-ID --as PALARI-ID --json`
- `palari agent handoff WORK-ID --as PALARI-ID --json`
- `palari agent doctor WORK-ID --as PALARI-ID --json`
- `palari agent done WORK-ID --as PALARI-ID --json` (R1/light/0-approval only)
- `palari agent advance WORK-ID --as PALARI-ID --dry-run --json`
- `palari agent advance WORK-ID --as PALARI-ID --json`
- `palari agent loop WORK-ID --as PALARI-ID --json`
- `palari git install` (IDE-agnostic pre-commit boundary enforcement)
- `palari git status`
- `palari git pre-commit`
- compact Palari-specific work candidate discovery
- compact ready/blocked packets
- machine-readable packet compliance checks
- local packet persistence and local claim leases
- deterministic one-item selection and claiming through `agent start --next`
- durable, claim-bound interrupted-work parking without completion authority
- deterministic portable session-contract compilation, inspection, persistence,
  and claim binding
- optional changed-file boundary checks
- explicit create/modify/delete path intent with exact absent-path deletion
  tombstones; legacy work retains presence-required output behavior
- unchanged pre-existing dirty-file attribution and tamper-checked Git baselines
- claim-start commit-range proof for `agent done`, preserved across release and
  restart so earlier out-of-boundary commits remain visible
- deterministic claim-range planning and atomic proof reconciliation through
  `agent advance`, with governed exact-proof reuse, an authority stop, and
  deterministic post-decision terminalization
- machine-readable JSON failures for agent commands when `--json` is requested
- read-only completion report guidance
- read-only human handoff packets
- plain-language read-only agent safety diagnoses
- compact read-only agent loop summaries
- deterministic blocker codes
- packet context hash
- receipt `context_packet` and `context_hash` fields
- direct work, goal, workbench, source, dependency, proof, and integration state
- opaque default work identity whose value carries no execution-order meaning
- repository-shared compare-and-swap claim leases across linked Git worktrees
- optional deterministic isolated branches/worktrees for concurrent sessions

Not implemented yet:

- packet expansion
- review/planning/repair modes
- portable host installation or native sandbox adapters beyond the existing
  separately documented Claude hook integration
- live connector execution
- memory providers or vector search
- portable deletion-history proof in PCAW v1; workspace tombstones are enforced
  locally but are not exported as a new protocol guarantee

`agent check` rebuilds the packet, reports packet blockers, verifies the active
local claim for ready packets, carries the current
`next_step_type`, and then evaluates the current workspace against the
completion contract. It returns `ok: false` when required receipt, evidence,
review, human decision, source, dependency, or external-write checks fail. Light
low-risk work may satisfy its trust loop with a valid receipt without requiring
review or human approval. Missing receipt, evidence, and review checks include
the next safe command Palari can infer for the current work item. Human-decision
record commands are held back until prerequisite proof, such as receipt,
evidence, and review, is present, so agents do not jump from missing review
straight to approval. When a blocked packet is already waiting on review,
`agent check` points to `agent handoff` before lower-level inspect commands.

When `--changed PATH` or `--git-diff` is supplied, `agent check` also compares
observed file changes against the packet's writable paths and required outputs.
It reports changed files inside and outside the write boundary, missing file
outputs, and changed files not represented by the current attempt/receipt
records. For claims started in Git, unchanged dirty paths captured at start are
listed separately and not attributed to the agent; a changed fingerprint is
attributed normally. This is intentionally content-blind: Palari compares Git
status and file metadata, rejects traversal/symlink escape and incomplete
observations, and never treats the baseline as cryptographic provenance.
When a work item declares `path_intents`, each exact normalized path is one of
`create`, `modify`, or `delete`. Create and modify require a regular file in the
expected Git change class; delete requires the exact path to be absent and the
Git observation to report deletion. That absent-path record is a local
governance tombstone, not a missing-output exception. Unsafe, overlapping,
duplicate, symlinked, mismatched, or undeclared paths fail closed. Work items
without `path_intents` keep their historical presence-required behavior.
Execute-mode hooks additionally rebuild the current packet from workspace truth
before granting writes, so coordinated edits to a packet and claim cannot
expand scope. A generic `work update` cannot mutate a work item while any local
claim is active, and `agent start` refuses to renew an active claim when the
current workspace would compile different packet authority. After release or
expiry, a same-ID execution-contract change still cannot start: exact
baseline/current authority comparison fails before lease creation and final
claim write. A declared actor and `agent handoff` do not rebaseline the work;
preserve the record and create a successor work item for the changed contract.
Opaque interpreters, unreviewed executables, dynamic shell expansion or
indirection, and Git witness mutations (including Git commands with global
`-C`, `--git-dir`, or `--work-tree` options) require a human hook decision.
That review applies to every shell segment even when an earlier segment has an
in-scope write target, and execution-capable command environments, `git -c`,
external diff/text-conversion options, and `rg --pre` cannot inherit a read-only
classification. Opaque or indirect commands still ask when no claim is active,
so releasing a claim cannot turn indirection into an authority bypass.
Direct writes to the workspace root, declared split collection files,
`.palari/`, or Git metadata are denied or escalated even without an active
claim; option-encoded destinations such as `dd of=` and `--target-directory`
are inspected, and linked worktree Git/common directories are included. Those
surfaces must change through governed Palari/Git commands. Pager and filter
options that can launch helpers are not read-only Git operations. Compact or
newline-separated shell segments are tokenized identically, and ordinary
existing-directory destinations resolve the effective destination basename.
Repository overrides and ripgrep preprocessor/hostname helpers require review.
The CLI does not accept abbreviated long options at any parser nesting level,
and the hook still scans protected Palari command pairs defensively. Unquoted
pathname expansion, tree-shaped or backup-producing writes, path-qualified
trusted-command names, hook self-modification, and unclassified Palari commands
require review. The same applies to Bash `|&`, assignment-position tilde
expansion, abbreviated GNU write/Git helper options, and Git pathspec-file
imports. Destructive removal or move
targets include ancestors of workspace, runtime, Git truth, and the standard
Claude hook settings, so deleting a parent directory cannot bypass the
exact-file checks. Quoted Git pathspec magic/globs and dash-prefixed operands
after `--` remain reviewable. Agent-safe Palari mutations cannot point
`--workspace` at another workspace or silently use a different default.
Human-attributed review, decision, integration approval/cancel/enqueue/send,
Linear adoption, terminal lifecycle, work-accept, and generic packet-authority
mutation commands are denied from the supported agent shell.

Latest evidence, review, receipt, attempt, acceptance, outcome, and integration
records are ordered by timezone-normalized UTC instants. ISO offset spelling
cannot make an older pass or acceptance outrank a semantically later failure,
rejection, or revocation. Malformed, timezone-free, missing-while-competing, and
equivalent-instant ordering claims fail closed; record ids never decide trust
authority. A single undated schema-v2 legacy record may remain only when no
ordering choice exists; multiple competing records must all be dated.

Agent command failures are JSON when `--json` is requested. The payload uses
`ok: false`, a stable error code where possible, the message, target work item
and Palari when present, and next safe read commands.

Bare `agent next` returns the all-Palaris rollup. `agent next --as PALARI-ID`
reads the current queue for one Palari, puts safe-to-start candidates first,
keeps blocked or waiting visible with blocker codes, and omits closed work from
candidate lists. Waiting candidates include `handoff_guidance` when the next
safe action is a human review or decision. Those candidates point first to
`agent handoff`, then to the lower-level review or decision guide. It does not
create a claim, mutate state, or assign work. Candidates also include
`loop_command` so an agent can open the compact loop summary after seeing the
first concrete next step.

`agent finish` wraps `agent check` into final-report guidance. It never mutates
workspace state in v1. It carries the same `next_step_type`, distinguishes
missing proof from handoff-ready work, such as low-risk receipt-ready results
that should stop execution and move to a human review path. Its
`next_allowed_commands` prioritize missing proof or approval record templates
before generic inspect/validate commands. For receipt-ready review handoffs and
work that already has evidence but still needs review, `agent handoff` is
listed before the direct review guide command. Approval commands appear only
after the earlier proof required for approval is present. In review mode,
`agent finish` means the agent may report a review recommendation; it does not
mean the agent may record a human review or claim the original work item is
complete.

When the next step is a human handoff, `agent finish` also returns
`handoff_guidance`. Review handoffs point to `review guide`, which includes
review focus, receipt limits, and ready-to-edit review record commands.
Decision handoffs point to `decision guide`, which includes suggested decision
update commands. The agent still does not record those human actions itself.

`agent handoff` compiles the final handoff packet for that moment. It wraps the
`agent finish` result and includes compact `review guide` or `decision guide`
context when applicable. Text handoff output surfaces the same review focus and
receipt claims so a human can inspect the right thing without parsing JSON
first. Agent-safe read commands remain separate from `human_action_commands`, so
a model can show the right review or decision commands without pretending it is
authorized to perform them. It is read-only in v1 and does not create reviews,
decisions, receipts, evidence, claims, or history events. Handoff packets also
include `human_action_boundary`, which marks every `human_action_commands`
entry as human-only. Eligible Palari review commands are instead listed under
`agent_action_commands`, paired with the required review-packet command and an
`agent_action_boundary`; they remain advisory and reviewer-specific.

Review-mode `agent brief` packets separate `human_review_commands` from
`agent_review_commands`. The human boundary still forbids an agent from running
human-attributed review or decision commands. A distinct eligible Palari may
run only the agent review command matching its packet identity. Builder
self-review, missing goal linkage, unapproved sources, and any attempt to turn
the advisory verdict into human quorum fail closed.

`agent loop` is a compact read-only control surface over the same commands. It
summarizes `brief`, `check`, `finish`, and handoff status, includes the exact
stage commands, and omits detailed payloads so agents can orient quickly without
receiving the whole workspace.

`agent doctor` is a plain-language read-only diagnosis over the same loop. It
answers whether the work is agent-safe, missing proof, blocked, or waiting for a
human handoff, and lists the next recommended commands without adding authority
or mutating workspace state.

## Git Pre-Commit Enforcement

`palari git install` writes a pre-commit hook into `.git/hooks/pre-commit` that
checks staged files against active claim write boundaries. If any staged file is
outside the boundary, the commit is rejected with a message listing the
offending files and allowed paths. This provides IDE-agnostic boundary
enforcement that works in any environment — Windsurf, Cursor, Devin, terminal —
not just Claude Code.

Unlike Claude Code hooks (which intercept writes before they happen), the git
hook is reactive: it blocks the commit, not the edit. This means an agent can
write outside the boundary during a session, but the commit cannot land until
the out-of-boundary changes are reverted or the boundary is expanded by a human.

`palari git status` shows whether the hook is installed and lists active claims
with their allowed write paths. `palari git pre-commit` is the check command the
hook calls; it can also be run manually before committing.

The same local Git repository holds expiring claim leases under
`refs/palari/leases/`. They prevent two linked worktrees from treating the same
work item as actively owned while allowing unrelated work items to proceed.
They are local coordination records, not identity authentication or human
authority. `palari git status --work-id WORK-ID --target-ref REF` separately checks
the exact governed candidate against a current target and requires renewed
proof after any divergent merge projection.
