# Security Notes

Palari Company OS is safe by default in this v0.2 local foundation.

It does not:

- require secrets for local verification
- perform broker or external side effects
- activate real policy acceptance
- deploy anything
- contact external systems during tests or examples

Authority rules:

- Human acceptance is separate from review.
- Required approval capability is checked before accepted decisions are
  recorded.
- Quorum is checked before work can be completed.
- Governed acceptance requires a terminal clean attempt, mandatory
  evidence/receipt integrity, and an exact-bound independent review matching
  the current attempt, head, and work contract.
- Each human's latest timezone-ordered decision for the exact review and
  evidence controls quorum; a later negative decision revokes an earlier
  approval, while contradictory or ambiguous records fail closed.
- A zero numeric quorum means no quorum is required; it does not make an
  explicit decision optional once an acceptance references that decision.
  Such acceptance still requires the current exact review/evidence binding and
  a declared human, and a later rejection revokes it.
- Bound reviews are immutable, and generic update commands cannot rewrite
  terminal work or attempt trust fields. Their aggregate hash covers reviewer
  identity, verdict, findings, inspected checks, residual risks, and timestamp.
- Scope checks use canonical repository paths and fail closed for traversal,
  sibling-prefix confusion, symlink escape, malformed Git output, unknown
  paths, and forbidden actions.
- Active claims hash their metadata-only dirty baseline. Unchanged pre-existing
  dirt is not attributed to the agent, while changes after claim are blocked.
- The baseline also records the claim-start commit. `agent done` checks the
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
  coordination; and static gates—not mutable proof records. Committed or uncommitted
  expansion, malformed or duplicate
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
  Catalog-free v1 witnesses remain valid only when the baseline already contains
  the work; a historical current-only baseline without a catalog requires a
  successor.
- Persisted witness ref/head/history is checked before restart lease acquisition
  and again before claim persistence. A legacy current-only active claim without
  a catalog is rejected by claim integrity and cannot reach advance or done.
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
- `agent advance` applies that same exact-range proof to every risk tier. Its
  planner is side-effect free; executable verification profiles are fixed
  argument vectors rather than workspace prose. Run records bind the head,
  base, changed-path digest, clean state, profile, source state, interpreter,
  and platform, but local cache files are advisory and a cached pass is rerun.
  Only current proof already reconciled into governed evidence is reusable.
  The command rechecks its plan and post-proof actor, claim, clean-tree, and
  scope boundaries, commits agent-owned proof as one journaled transaction,
  and stops before independent review or human authority. A pending prepare is
  aborted before a safe retry; an already-applied pending commit is completed
  only under the exact original execution authority.
- `agent start --next` does not introduce a second eligibility policy. It
  selects the first candidate already marked safe by `agent next`, then invokes
  the same packet, portable-contract, claim, baseline, witness, and lease path
  as explicit `agent start WORK-ID`. No-ready and ambiguous invocation states
  write nothing.
- Explicit path intent separates authorization from final-state proof. A
  `delete` intent authorizes only its exact normalized path and succeeds only
  when Git reports deletion and the path is absent. Create/modify mismatches,
  traversal, symlink escape, duplicate or prefix-overlapping intents, and
  undeclared changes fail closed. Legacy work without path intents keeps its
  presence-required output semantics.
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
  options precede the subcommand. Generic work updates are blocked
  while a claim is active, and active claims cannot be renewed against changed
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
  one. Both install or reuse the portable contract and claim-bound Git commit
  gate without granting authority. Claude and Codex have tested project-local session adapters;
  Codex hooks activate only after explicit host `/hooks` review. Cursor, Devin,
  GLM, and generic profiles are labeled advisory at session time. No profile is
  an OS sandbox, and an unrestricted same-user process can still rewrite local
  files or Git metadata. Existing `palari claude install` remains compatible.
- Every active accepted record re-verifies its evidence manifest, artifact
  state, and bound receipt content even before work becomes terminal.
- Proof creation necessarily mutates `workspace.json`, legacy history, and the
  governance journal. When one of those projection files is itself a declared
  artifact, verification reads its bytes from the evidence's exact Git commit
  instead of the later live file, then independently requires the live journal
  to replay to the current workspace. Missing commits or blobs, hash mismatch,
  local Git replacement objects, malformed chains, pending transactions, and
  projection divergence fail closed. This exception does not apply to ordinary
  output artifacts, whose current bytes must still match their evidence hashes.
- Trust-record ordering normalizes timezone-bearing ISO timestamps to UTC
  instants, including acceptance `accepted_at`. Malformed or timezone-free
  values, UTC-normalization overflows, and equivalent-instant competitors fail
  closed, so offset spelling or caller-chosen ids cannot hide later adverse
  evidence, review, or revocation.

The local JSON and claim hashes detect mismatch and accidental tampering; they
are not signatures and do not authenticate a human identity against an
external identity provider. Git witnesses and supported harness hooks make
same-user tampering materially harder and fail closed for observed paths, but
they are not an OS sandbox: an unrestricted process running as the operator
can ultimately rewrite local files and Git metadata. Human attribution needs a
future protected harness or credential boundary before hostile same-principal
execution can be treated as cryptographically authenticated.

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

Governance journal v1 remains strictly readable and appendable until an
operator explicitly runs another `history --checkpoint` against its valid,
fully committed head. That one-time activation verifies the complete v1 chain,
leaves its bytes untouched, and starts a compact v2 segment whose first
checkpoint binds the exact v1 file SHA-256, byte length, head record digest,
record count, replay digest, transaction counts, and continuity state. Every
later verification re-hashes the sealed v1 bytes and streams the strict v2
JSONL tail from its content-bound workspace checkpoint. It does not trust a
persistent advisory cache.

V2 mutation prepares contain deterministic add/remove/replace values rather
than another full workspace projection. A checkpoint still contains one full
projection so replay has an authoritative base. Record, transaction,
before/after workspace, predecessor, and terminal digests remain fail-closed;
truncation, reordering, duplicate terminals, malformed or non-canonical deltas,
changed predecessor bytes, pending transactions, and workspace divergence are
rejected. The sealed predecessor hash makes ordinary verification bounded in
memory and avoids reparsing historical v1 JSON, but it does not authenticate
the operator who created the checkpoint against a hostile same-user process
that can rewrite both local journals.

PCAW distinguishes optional `reviewer_authorities` from `humans`. A declared
Palari may supply an independent advisory review, but only identities in
`humans` can contribute human decisions or quorum. Legacy statements without
`reviewer_authorities` retain their original canonical bytes and verification
behavior.

Approval Packs use the same declared-identity limitation. A canonical pack and
each member digest are persisted with the human decision. New pack-v2 actions
also require and persist the digest of a strict canonical decision presentation
covering the pack, proof, boundaries, effects, available actions, execution
order, and relevant current decisions. Current bytes, review, recursively bound
dependency state, authority, quorum, and presentation currency are rechecked
before local execution. A terminal dependency's changed artifact stales a
narrowed dependent pack, and a later relevant decision makes the earlier
presentation stale. This prevents accidental replay or transplant inside
Palari, but it does not cryptographically authenticate a human against a
hostile process running as the same OS user.

The presentation digest proves canonical artifact bytes. The bound CLI surface
supports the narrower claim that those bytes were made available to the
decision action. Neither claim proves browser pixels under compromised
software, human attention, understanding, or judgment.

Checkpoint restoration is local state restoration, not external rollback.
Sent messages, filings, payments, access changes, and provider effects cannot
be reversed by replacing `workspace.json`. When effect-bearing receipt fields
or a sent/failed outbox transition show that an effect occurred or may have
occurred after the selected checkpoint, restoration fails closed before
changing local state. Detection scans all committed projections after the
earliest occurrence of the selected content digest, including when a later
projection removed the record or returned to the same bytes. Compensation must
be a separate governed action; it is never inferred from local restoration.

`history --restore` is human-only in the Claude shell enforcement boundary. A
declared human id is attribution, not authority delegation: agent Bash is
denied before the command can mutate the workspace.
`human-decision pack` receives the same hard denial; agent Bash cannot record
approve, reject, or defer authority through a bare, reordered, path-qualified,
equals-form, or compound command.

Future broker, policy, deployment, or signed-gate work must preserve these
boundaries and must not expose raw credentials to AI models or chat context.
