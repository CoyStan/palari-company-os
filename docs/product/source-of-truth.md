# Which Files Palari Trusts

Palari keeps its saved state in ordinary, inspectable local files. Fast status
views are calculated from those files.

## Current State

Each local workspace stores its authoritative current state in:

```text
workspace.json
```

The technical name for this file's role is the current-state `projection`.
The ACME example lives at `examples/acme-company-os/workspace.json`; this
repository's live records are the root `workspace.json`.

Queue, detail, and state are display-only status views (`read_models`) derived
from `workspace.json`. They do not inspect output bytes or scan history.
`validate` checks stored structure and bindings, while `scope` checks an
explicit set of observed paths. Neither changes permissions or approvals.

## Tamper-Evident History

The only current change history is:

```text
.palari/governance-journal.v2.jsonl
```

The filename keeps the exact machine term `governance-journal`; operators can
read it as tamper-evident history. It is hash-chained and replayable. Palari
fsyncs a prepared record before atomically replacing `workspace.json`, then
fsyncs the commit marker. Verification detects unfinished changes, corruption,
truncation, reordering, forks, and disagreement with the current workspace.
A manual-repair restore point keeps a visible continuity break instead of
rewriting history.

New workspaces create v2 directly. Workspaces without this history reject all
writes and cannot add it in place.

## Safe Concurrent Writes

Writes to `workspace.json` use an ownership-bound local lock and optimistic
change detection. An fsynced atomic replace prevents partial files. A hash of
the loaded file prevents an older command from overwriting a newer change.
When another writer finishes first, the stale command stops and should be
retried after the workspace is reloaded.

Together, `workspace.json` and the v2 journal are Palari's durable storage:
current state plus replayable, tamper-evident change history.

## Rules for Future Storage

Future workspaces may support richer authoring or other inspectable source
formats. These rules must remain true:

- saved source files are inspectable
- generated status views are derived
- check results are tied to an exact commit or output version
- independent review and human approval remain separate records
- every successful change appends one history transaction
- queue and detail never silently change permissions or approvals

## Actions That Must Stay Explicit

Palari must never infer or silently perform:

- final human approval (`acceptance`)
- merge
- push
- deploy
- policy activation
- an external-service action (`broker` side effect)
- secret or credential use
- wider permissions for an agent
