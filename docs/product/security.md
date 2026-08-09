# Security Notes

Palari is a local system of explicit rules and checks. By default it does not
contact a provider, use a credential, or let an agent approve its own work.

This document uses exact security, storage, and PCAW protocol terms where
precision matters. For ordinary product wording, see
[Plain Language](plain-language.md).

It does not:

- require secrets for local verification
- provide generic broker execution or perform an external write without an
  exact approved plan, queued outbox item, supported adapter, and explicit send
- approve real policy
- deploy anything
- contact external systems during tests or examples

Linear is the sole current live provider adapter. Its comment, issue-status,
and issue-creation writes are separate human actions after planning, approval,
and enqueue; generic integration commands remain local and non-executing.

Safety rules:

- Human approval is separate from review.
- Before execution and review, the authority plan verifies that the builder,
  selected independent reviewer, and required qualified human approvers can
  remain distinct. A reviewer candidate that would consume a required final
  approver is rejected before the review is recorded.
- Required permission to approve is checked before accepted decisions are
  recorded.
- The required number of approvals is checked before a task can be completed.
- Every completion requires current passing check results tied to the exact
  run, run record, commit, output files, and task rules.
- Approval requires a finished clean run, complete check/run-record integrity,
  and an independent review tied to the exact run, commit, and task rules.
- Independent review and human approval may both be omitted only for
  R1/light/0-approval work with no allowed, planned, queued, or actual external
  writes. That narrow policy never waives checks.
- Each person's latest timezone-ordered decision for the exact review and
  check results controls the required approvals; a later negative decision
  revokes an earlier approval, while contradictory or ambiguous records fail
  closed.
- A zero stored numeric `quorum` removes extra counted votes; it does not remove
  the final human boundary for review-required work. Outside the narrow
  R1/light/zero-count/no-external automatic exemption, the effective final
  approval count is at least one. Such approval still requires the current
  exact review/check binding and a declared human, and a later rejection
  revokes it.
- Bound reviews are immutable, and generic update commands cannot rewrite
  terminal task or run trust fields. Their aggregate hash covers reviewer
  identity, review result, findings, inspected checks, residual risks, and
  timestamp.
- Allowed-file checks use canonical repository paths and fail closed for
  traversal, sibling-prefix confusion, symlink escape, malformed Git output,
  unknown paths, and forbidden actions.
- Active task locks hash their metadata-only dirty baseline. Unchanged
  pre-existing changes are not attributed to the agent, while changes made
  after assignment are checked against the task limits.
- The baseline also records the claim-start commit. `agent advance` checks the
  entire descendant commit range, so claim restart cannot hide an earlier
  out-of-boundary commit or claim work already committed before ownership. A
  dedicated local Git ref and its oldest reflog entry independently witness
  the original head; coordinated rewrites of the claim and baseline fail.
- Every complete Git-backed baseline, including a first claim and any restart
  or expiry recovery, derives a canonical execution-authority digest from exact
  baseline workspace bytes and strict current root/split bytes before a lease,
  then repeats it under the final workspace mutation lock and holds that lock
  through witness, baseline, packet, and claim persistence. It binds actor
  identity, role, scope, worker, standards, input/memory boundaries and mode;
  reviewer goal linkage; work/dependency lifecycle authority; paths;
  selected-source provider/URI/external identity; capabilities; outputs;
  coordination; and static required checks—not mutable verification records.
  Committed or uncommitted expansion, malformed or duplicate
  JSON, unsafe collection paths, and split mismatch fail closed; journal actor
  metadata and handoff do not rebaseline a work item. A substantive amendment
  requires a successor work item.
- If a first-claim current work declaration is absent from the baseline commit, the
  baseline contains a normalized actor/mode authority digest catalog rather
  than workspace or proof narration. Its canonical digest is bound in the
  oldest v2 Git-witness reflog message. With that witness intact, catalog-bound
  authority differences in another worktree, coordinated catalog/JSON rehashing,
  and actors added after the anchor fail closed. This is not authentication
  against a hostile same-user process that can rewrite local Git metadata.
  Every complete Git-backed claim uses the current v2 witness, v2 lease, and v2
  governance-projection snapshot, including an explicit empty changed-path set
  when the projection is unchanged. Legacy v1 claim witnesses, leases, and
  snapshots are unsupported and are not upgraded in place; a historical
  current-only baseline without a catalog requires a successor.
- Persisted v2 witness ref/head/history, lease, and projection-snapshot binding
  are checked before restart lease acquisition and again before claim
  persistence. Unsupported claim state is rejected by claim integrity and
  cannot reach `agent advance`.
- Durable parking crash recovery is the sole narrow exception to live status
  equality: after confirming the exact persisted parking-attempt/claim epoch, it
  normalizes current `blocked` status back to the immutable packet status and
  rehashes every other authority field. Any additional scope or actor change
  still fails closed before the claim is released.
- Proof-only refresh does not reset or replace that baseline. It runs without a
  claim, requires exact descendant history with replacement objects disabled,
  and compares every raw commit with every parent in the range. Separately governed
  commits may advance repository context, but touching a governed
  non-projection output blocks refresh even if a later commit restores identical
  bytes. Self-mutating projection artifacts may evolve through legitimate
  governance transactions, but refresh reports their previous/current exact Git
  hashes and statuses in uniform unchanged/rebound records rather than calling
  them byte-unchanged. Missing legacy projection hashes are explicit and
  malformed hash/status records fail closed. Refresh also discloses
  that recording refreshed proof mutates those projections after the evidence
  head. The refreshed proof invalidates prior review and human authority.
- `agent advance` is the sole current execution-to-proof path and applies that
  same exact-range proof to every risk tier. Its
  planner is side-effect free; executable verification profiles are fixed
  argument vectors rather than workspace prose. Run records bind the head,
  base, changed-path digest, clean state, profile, source state, interpreter,
  and platform, but local cache files are advisory and a cached pass is rerun.
  Only current proof already reconciled into governed evidence is reusable.
  The command rechecks its plan and post-proof actor, claim, clean-tree, and
  scope boundaries, commits agent-owned proof as one journaled transaction,
  and either completes only under the narrow R1/light/0-approval/no-external
  exemption or stops before required independent review or human authority. A
  pending prepare is aborted before a safe retry; an already-applied pending
  commit is completed only under the exact original execution authority.
- `agent start --next` does not introduce a second eligibility policy. It
  selects the first candidate already marked safe by `agent next`, then invokes
  the same packet, portable-contract, claim, baseline, witness, and lease path
  as explicit `agent start WORK-ID`. No-ready and ambiguous invocation states
  write nothing.
- `palari approve WORK-ID --as HUMAN-ID` is a human-only composition over the
  existing singleton Approval Pack transaction. The handoff emits it with a
  machine-supplied `--presented` digest; a bare invocation instead selects
  current state at invocation. It verifies exact journal replay, actor
  separation, capability, artifact/check/review currency, and the effective
  final count, then revalidates the presentation and artifacts immediately
  before writing approval and local completion atomically. It cannot perform
  an external effect, supply a missing review or vote, or admit individual-only
  work. Safe replay by the same human validates the stored
  pack/presentation/decision/acceptance binding and any supplied presentation
  token before returning a no-op. Supported agent hooks deny this top-level
  command.
- Explicit path intent separates authorization from final-state proof. A
  `delete` intent authorizes only its exact normalized path and succeeds only
  when Git reports deletion and the path is absent. Create/modify mismatches,
  traversal, symlink escape, duplicate or prefix-overlapping intents, and
  undeclared changes fail closed. Output and read lists cannot replace the
  required path rules.
- durable `agent release` is claim-bound interruption state, not completion. It records a
  blocked attempt, packet/head/workspace bindings, observed boundary changes,
  a human-readable reason, and one next safe action in a journaled mutation
  before releasing the owned execute claim. Crash retry is idempotent only for
  the exact same durable record and repository state. It creates no receipt,
  evidence, review, decision, acceptance, outcome, or convergence.
  Parking requires a current writable governance journal; legacy workspaces
  fail before mutation with an explicit `history --checkpoint` next action and
  never receive a retroactive continuity claim.
- Hook and packet checks reject ambiguous execute claims; review claims are
  read-only. Execute hooks also compare persisted scope with a freshly compiled
  workspace packet, deny human-attributed and generic packet-authority Palari
  commands, and require human approval for opaque interpreters, unreviewed or
  path-qualified executables, unquoted pathname expansion, tree-shaped writes,
  hidden backup outputs, hook self-modification, unclassified Palari commands,
  dynamic shell indirection, and Git witness mutations even when Git global
  options precede the subcommand. Generic public work updates are absent, and
  active claims cannot be renewed against changed
  packet authority. Shell review is segment-independent: an observed allowed
  write cannot mask a later unsafe segment, and command environment assignments,
  execution-capable Git config/diff options, and `rg --pre` require review.
  Workspace root/split files, `.palari/`, and Git metadata remain protected from
  direct file writes after claim release as well as during a claim. Protection
  resolves linked-worktree common Git directories and option-encoded write
  destinations, including ordinary existing-directory basename semantics.
  Compact/newline command separators cannot hide later targets. Git repository
  overrides, pager/filter helpers, and ripgrep preprocessor/hostname helpers
  require review. Git pathspec-file imports, accepted Git helper-option
  abbreviations, abbreviated GNU write options, assignment-position tilde
  expansion, and Bash `|&` composition require review. Global CLI long-option
  abbreviations are disabled, and destructive targets cannot remove or move an
  ancestor of protected truth or the standard Claude hook settings.
  Git pathspec magic/globs and dash-prefixed operands after `--` cannot hide
  destructive targets. Agent-safe Palari mutations are bound to the hook's
  configured workspace rather than trusting an arbitrary `--workspace` path.
  Human integration enqueue/cancel/send, Linear adoption, and external
  playbook-source authority changes are denied from agent shell commands.
- The pure directive compiler and request-local operation context reduce
  repeated packet/check/journal work; they do not replace transition checks or
  cache authority across requests. A changed journal witness forces a fresh
  complete scan.
- `palari init --host HOST` creates and adopts a fresh workspace; `palari init
  WORKSPACE-DIR --host HOST --as PALARI-ID` idempotently adopts an existing
  one; `HOST` is `claude`, `codex`, or `cursor`. Claude and Codex install or
  reuse the portable contract, claim-bound Git commit gate, and tested
  repository-local session hooks (strict no-claim on adoption) without granting
  authority; Codex hooks activate only after explicit host `/hooks` review.
  Cursor installs an advisory project rule by default; the Git commit gate is
  opt-in via `--strict-git`, `palari cursor install`, or `palari git install`.
  No profile is an OS sandbox, and an unrestricted same-user process can still
  rewrite local files or Git metadata. Nested workspace adoption resolves and
  preflights the enclosing Git root before any write, so existing root
  instructions or host configuration cannot be silently absorbed into the
  bootstrap commit. A symlinked workspace file or escaping managed target fails
  before the workspace is loaded or repository files are written. Generated
  commands use an inspectable repository-local launcher when present; otherwise
  they preserve the absolute Palari entrypoint currently running or a validated
  `PATH` entry. `palari claude install` remains the Claude hook-only management,
  repair, and removal surface. It manages current Palari entries without
  duplicating them and preserves co-located foreign host hooks.
- Starter initialization declares a second, review-only Palari linked to the
  goal but outside the execution workbench. Source and goal linkage permit
  exact advisory review; the absence of workbench execution membership and
  human capabilities prevents that identity from building the same run or
  satisfying final approval.
- Every active accepted record re-verifies its evidence manifest, artifact
  state, and bound receipt content even before work becomes terminal.
- `superseded` and `abandoned` are temporal storage boundaries. Prior linked
  proof remains readable, but later writes to the retired contract or its
  adopted proposal, attempts, receipts, evidence, reviews, decisions,
  acceptances, outcomes, and external-action records fail before the workspace
  or journal is replaced. The storage transaction creating retirement cannot
  append authority or proof, and successful terminal work cannot be relabeled
  as retired.
- Proof creation necessarily mutates `workspace.json` and the
  governance journal. When one of those projection files is itself a declared
  artifact, verification reads its bytes from the evidence's exact Git commit
  instead of the later live file, then independently requires the live journal
  to replay to the current workspace. Missing commits or blobs, hash mismatch,
  local Git replacement objects, malformed chains, pending transactions, and
  projection divergence fail closed. This exception does not apply to ordinary
  output artifacts, whose current bytes must still match their evidence hashes.
- Trust-record ordering normalizes timezone-bearing ISO timestamps to UTC
  instants, including acceptance `accepted_at`. Malformed or timezone-free
  values, missing times, UTC-normalization overflows, and equivalent-instant
  competitors fail closed, so offset spelling or caller-chosen ids cannot hide
  later adverse evidence, review, or revocation.

The local JSON and claim hashes detect mismatch and accidental tampering; they
are not signatures and do not authenticate a human identity against an
external identity provider. Git witnesses and supported harness hooks make
same-user tampering materially harder and fail closed for observed paths, but
they are not an OS sandbox: an unrestricted process running as the operator
can ultimately rewrite local files and Git metadata. Human attribution needs a
future protected harness or credential boundary before hostile same-principal
execution can be treated as cryptographically authenticated.

Palari's own source-repair exception is narrower than production governance and
is documented in [Self-Hosting Maintainer Mode](self-hosting-maintainer-mode.md).
The ignored, repository-bound live-state profile described there is not yet
implemented. Until it is, maintainers must not use this source checkout's
tracked root `workspace.json` or root `.palari` as live authorization state or
claim that dogfood operation leaves the source checkout clean.

PCAW v1 adds deterministic, offline tamper and policy-consistency checks for a
canonical governance statement and its named artifact bytes. It is deliberately
unsigned. Actor, reviewer, and human identities are declarations, not
cryptographically authenticated identities; PCAW does not prevent a hostile
process running as the same OS user from rewriting local governance files and
exporting a new statement. Signing, key custody, revocation, and protected
identity are deferred to a versioned future protocol.

PCAW v1 does not claim portable deletion-history proof. Local workspace
`delete` tombstones are checked against exact Git state, but the v1 statement
and verifier guarantees remain limited to their documented named subjects and
governance properties.

New workspaces and explicit restore points for existing workspaces without history
write v2 directly. Ordinary mutation of such a workspace fails closed until that
restore point exists.

V2 mutation prepares contain deterministic add/remove/replace values rather
than another full status snapshot. A restore point still contains one full
snapshot so replay has a trusted base. Record, transaction, before/after
project, and terminal digests remain fail-closed;
truncation, reordering, duplicate terminals, malformed or non-canonical deltas,
pending transactions, and workspace divergence are rejected. This does not
authenticate the operator who created the restore point against a hostile
same-user process that can rewrite local files.

PCAW distinguishes required `reviewer_authorities` from `humans`. A declared
Palari may supply an independent advisory review, but only identities in
`humans` can contribute human decisions or quorum. Statements without an
explicit reviewer-role list fail closed.

Approval Packs use the same declared-identity limitation. A canonical pack and
each member digest are persisted with the human decision. Pack-v3 actions
retain declared and effective final counts; the reader remains compatible with
pack v2. Both versions require and persist the digest of a strict canonical
decision presentation covering the pack, proof, boundaries, effects, available
actions, execution order, and relevant current decisions. Current bytes,
review, recursively bound dependency state, authority, effective final count,
and presentation currency are rechecked before local execution. The last
artifact check runs under Palari's workspace writer lock immediately before
the local workspace replacement. Palari does not lock every governed artifact
file, so an unrelated same-user process that ignores Palari could still race
after that final check; later operations treat any resulting artifact change
as new, unapproved state. A terminal dependency's changed artifact stales a
narrowed dependent pack, and a later relevant decision makes the earlier
presentation stale. These controls prevent accidental replay or transplant
inside Palari, but they do not cryptographically authenticate a human against
a hostile process running as the same OS user.

The presentation digest proves canonical artifact bytes. The bound CLI surface
supports the narrower claim that those bytes were made available to the
decision action. Neither claim proves browser pixels under compromised
software, human attention, understanding, or judgment.

Restore-point recovery is not part of the current product. Removed restoration
spellings remain denied by session hooks, and external compensation must always
be a separate governed action.

`human-decision pack` receives the same hard denial; agent Bash cannot record
approve, reject, or defer authority through a bare, reordered, path-qualified,
equals-form, or compound command.

Future broker, policy, deployment, or signed-gate work must preserve these
boundaries and must not expose raw credentials to AI models or chat context.
