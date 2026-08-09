# Minimality Contract

Palari should stay small enough that a person can inspect it, run it locally,
and understand who may do or approve what. New work must protect that shape.

Use the [Public Surface](public-surface.md) map to check whether a change
strengthens the core rules and checks or adds optional surface area.

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
- No new public command unless it replaces confusion or exposes a core rule or
  check. Helper workflows should start as docs.
- No schema growth without changed safety behavior. A new field must change a
  real boundary, permission rule, check link, run record, or approval decision.
- README and Quickstart must remain API-key-free. Optional integrations belong
  in deeper docs.

## Preferred Shape

- Add examples before adding abstractions.
- Add status views before adding new storage.
- Add dry-run plans before live effects.
- Add narrow adapters before generic provider frameworks.
- Prefer one local file and one explicit command over hidden orchestration.

## Recursive MECE Rule Of Three

- The product framework has three roots: **Memory**, **Initiative**, and
  **Control**. Every conceptual component belongs to exactly one root.
- Any component may have zero to three child components. The same limit applies
  recursively at every depth.
- Sibling components must be mutually exclusive and collectively exhaustive of
  their parent. Merge, rename, or move overlaps before adding another child.

Ordinary data fields inside a leaf are not new conceptual components.

## Size Budget

The August 2026 baseline was 56,122 production Python lines and 146 parser
commands. The first minimality pass reduced that to at most 53,100 lines and 82
commands without removing the supported lifecycle or adapters. `check_style.py`
enforces the production ceiling.

An 80% reduction would mean roughly 11,224 production lines. That remains a
useful architecture challenge, not a license to compress safety logic or remove
supported behavior. Further cuts must first prove equivalent init → bounded
work → advance → independent review → human approval → proof behavior.

## Review Questions

Before merging a feature, ask:

- Can the demo still run without network access, API keys, databases, or a
  background service?
- Does this make approval, permissions, checks, or external side effects easier
  to understand?
- Could this be documentation or a fixture instead of a command, schema field,
  or service?
- Did we avoid storing raw secrets?
- Did we keep Palari as the source of truth instead of a provider?

If the answer is unclear, keep the change smaller.
