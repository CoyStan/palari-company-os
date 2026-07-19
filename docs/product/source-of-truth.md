# Source Of Truth Rules

Palari Company OS keeps source artifacts simple and inspectable. Fast operator
views are derived from those artifacts.

## Current Durable Contract

The current-state projection is:

```text
workspace.json
```

That file is the authoritative current-state projection for each local
workspace. The ACME repository example lives at
`examples/acme-company-os/workspace.json`; the repository dogfood evidence lives
at `workspaces/palari-company-os/workspace.json`.

Queue, detail, and state are recorded-only read models derived from that
projection. They do not inspect artifact bytes or scan journal history.
`validate` checks stored structure and bindings, while `scope` checks an
explicit observed path set; neither mutates authority state.

The sole current mutation history is:

```text
.palari/governance-journal.v2.jsonl
```

The hash-chained journal is replayable. Its prepared record is
fsynced before the atomic workspace replacement and its commit marker is
fsynced afterward. It detects pending transactions, corruption, truncation,
reordering, forks, and workspace divergence. A manual-repair checkpoint keeps
the continuity break visible instead of rewriting history.

A committed `.palari/governance-journal.v1.jsonl` is accepted only as a sealed,
strictly verified predecessor for explicit v2 activation. A committed
`.palari/history.jsonl` is historical evidence only; current runtime code never
reads, appends, or imports it.

New workspaces create v2 directly. Existing workspaces without a journal reject
ordinary writes until an explicit checkpoint creates v2; the v1 path never
accepts a v2 record.

Writes to `workspace.json` use an ownership-bound local lock plus optimistic
change detection. Fsynced atomic replace prevents partial files; the loaded-file
hash prevents stale read-modify-write commands from overwriting newer workspace
changes. When a second writer wins first, the stale command fails closed and
should be retried
after reloading the workspace.

Together, `workspace.json` and the v2 journal are the supported durable storage
contract: current projection plus replayable, tamper-evident mutation history.

## Design Direction

Future workspaces may add richer authoring for split records or support other
inspectable source formats. The rule should stay the same:

- source files are inspectable
- generated views are derived
- evidence is tied to a specific head or artifact state
- review and human decision are separate records
- successful mutations leave one append-only journal transaction
- queue/detail commands do not secretly mutate authority state

Current authoring commands intentionally refuse split workspaces so they do not
silently collapse or corrupt external collection files. The retained split-file
reader accepts a declared `collection_files` list, merges those files in memory,
and validates the result. It is parked compatibility, not a supported scaling
path; there is no current split-file writer or schema migration exception.

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
