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
- Every active accepted record re-verifies its evidence manifest, artifact
  state, and bound receipt content even before work becomes terminal.
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

Approval Packs use the same declared-identity limitation. A canonical pack and
each member digest are persisted with the human decision, and current bytes,
review, dependencies, authority, and quorum are rechecked before local
execution. This prevents accidental replay or transplant inside Palari, but it
does not cryptographically authenticate a human against a hostile process
running as the same OS user.

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

Future broker, policy, deployment, or signed-gate work must preserve these
boundaries and must not expose raw credentials to AI models or chat context.
