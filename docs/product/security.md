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
- Each human's latest decision for the reviewed head controls quorum; a later
  negative decision revokes an earlier approval.
- Bound reviews are immutable, and generic update commands cannot rewrite
  terminal work or attempt trust fields.
- Scope checks use canonical repository paths and fail closed for traversal,
  sibling-prefix confusion, symlink escape, malformed Git output, unknown
  paths, and forbidden actions.
- Active claims hash their metadata-only dirty baseline. Unchanged pre-existing
  dirt is not attributed to the agent, while changes after claim are blocked.
- Hook and packet checks reject ambiguous execute claims; review claims are
  read-only.

The local JSON and claim hashes detect mismatch and accidental tampering; they
are not signatures and do not authenticate a human identity against an
external identity provider.

Future broker, policy, deployment, or signed-gate work must preserve these
boundaries and must not expose raw credentials to AI models or chat context.
