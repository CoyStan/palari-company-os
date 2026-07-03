# Source Of Truth Rules

Palari Company OS keeps source artifacts simple and inspectable. Fast operator
views are derived from those artifacts.

## Current First Slice

The first implementation uses a workspace manifest:

```text
workspace.json
```

That file is the source of truth for each local workspace. The ACME demo lives at
`examples/acme-company-os/workspace.json`; the repository dogfood workspace lives
at `workspaces/palari-company-os/workspace.json`.

For larger workspaces, `workspace.json` may also declare `collection_files`.
Those files are read, merged in memory, and validated as one workspace. They are
not a second authority layer; they are just maintainable storage for records that
would otherwise make one JSON file too large.

The queue and detail views are read models derived from workspace data. They
may surface workbench context, active parallel attempts, and coordination
warnings, but those warnings are still derived from declared records. `state`,
`validate`, and `scope` are also derived views/checks; they do not mutate
authority state.

Mutating commands also append audit events to:

```text
.palari/history.jsonl
```

The history file is append-only local audit evidence for successful mutations.
It is not yet the source for rebuilding `workspace.json`; event-sourced
projection is intentionally future work.

Writes to `workspace.json` use a local lock plus optimistic change detection.
Atomic replace prevents partial files; the loaded-file hash prevents stale
read-modify-write commands from overwriting newer workspace changes. When a
second writer wins first, the stale command fails closed and should be retried
after reloading the workspace.

## Design Direction

Future workspaces may add richer authoring for split records or support other
inspectable source formats. The rule should stay the same:

- source files are inspectable
- generated views are derived
- evidence is tied to a specific head or artifact state
- review and human decision are separate records
- successful mutations leave an append-only audit event
- queue/detail commands do not secretly mutate authority state

Current authoring commands intentionally refuse split workspaces so they do not
silently collapse or corrupt external collection files.

## What Must Not Become Implicit

These actions must remain explicit:

- acceptance
- merge
- push
- deploy
- policy activation
- broker side effects
- secret or credential use
- widening a Palari's authority boundary
