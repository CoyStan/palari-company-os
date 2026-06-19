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
- Evidence and review must match the current attempt head.
- Scope checks fail closed for unknown paths and forbidden actions.

Future broker, policy, deployment, or signed-gate work must preserve these
boundaries and must not expose raw credentials to AI models or chat context.
