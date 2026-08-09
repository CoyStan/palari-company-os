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

## No Overlap, No Gaps

Palari has five main parts:

- **Goals** — why the work matters.
- **Team** — who does or owns the work.
- **Work** — what is planned, active, or done.
- **Checks** — what shows the work is sound.
- **Limits** — what may and may not happen.

Use the same rule at every level:

- A part has no child parts, or it has three to five.
- Child parts do not overlap and together cover their whole parent.
- New public names use short, common words. Exact code and file names may stay
  technical, but the nearby text must explain them in plain words.
- A new part must fit under one current part. Split a part only when all of its
  contents can be placed once, with nothing left out.

Data fields inside an end part are not new parts. The checked
[Repo Tree](../agent/repo-tree.json) places every stored record and every repo
file once, and applies the same three-to-five rule to each split.

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
