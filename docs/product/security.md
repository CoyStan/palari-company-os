# Security Notes

Palari Company OS is safe by default in this v0.1 local foundation.

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
  commands, and require human approval for opaque interpreters, unreviewed
  executables, dynamic shell indirection, and Git witness mutations even when
  Git global options precede the subcommand. Generic work updates are blocked
  while a claim is active, and active claims cannot be renewed against changed
  packet authority.
- Every active accepted record re-verifies its evidence manifest, artifact
  state, and bound receipt content even before work becomes terminal.

The local JSON and claim hashes detect mismatch and accidental tampering; they
are not signatures and do not authenticate a human identity against an
external identity provider. Git witnesses and supported harness hooks make
same-user tampering materially harder and fail closed for observed paths, but
they are not an OS sandbox: an unrestricted process running as the operator
can ultimately rewrite local files and Git metadata. Human attribution needs a
future protected harness or credential boundary before hostile same-principal
execution can be treated as cryptographically authenticated.

Future broker, policy, deployment, or signed-gate work must preserve these
boundaries and must not expose raw credentials to AI models or chat context.
