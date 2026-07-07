# Minimality Contract

Palari should stay small enough that a human can inspect it, run it locally, and
understand where authority lives. New work must protect that shape.

## Hard Rules

- No runtime dependency unless it is required for a concrete safety property
  that the standard library cannot reasonably provide.
- Workspace state stays local-first and files-first. Generated views are derived
  from inspectable source files.
- No background service by default. Local servers are explicit operator commands.
- No live provider write without approval. External writes must pass through a
  reviewable plan, human approval, and an outbox boundary.
- No OAuth by default. Personal/local credentials may be supported only through
  explicit environment references, never stored token values.
- No new public command unless it replaces confusion or exposes a core
  governance primitive. Helper workflows should start as docs.
- No schema growth without governance behavior. A new field must change a real
  boundary, authority rule, evidence link, receipt, or acceptance decision.
- README and Quickstart must remain API-key-free. Optional integrations belong
  in deeper docs.

## Preferred Shape

- Add examples before adding abstractions.
- Add read models before adding new storage.
- Add dry-run plans before live effects.
- Add narrow adapters before generic provider frameworks.
- Prefer one local file and one explicit command over hidden orchestration.

## Review Questions

Before merging a feature, ask:

- Can the demo still run without network access, API keys, databases, or a
  background service?
- Does this make acceptance, authority, evidence, or external side effects more
  legible?
- Could this be documentation or a fixture instead of a command, schema field,
  or service?
- Did we avoid storing raw secrets?
- Did we keep Palari as the source of truth instead of a provider?

If the answer is unclear, keep the change smaller.
