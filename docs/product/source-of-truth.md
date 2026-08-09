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
repository's live records are the root `workspace.json`. Frozen older dogfood
records are packed in `workspaces/palari-company-os/past.tgz` and can be
unpacked for read-only inspection.

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

A committed `.palari/governance-journal.v1.jsonl` is accepted only as a sealed,
strictly verified predecessor during explicit v2 activation. A committed
`.palari/history.jsonl` is historical evidence only; current code never reads,
appends, or imports it.

New workspaces create v2 directly. Existing workspaces without this history
reject ordinary writes until an explicit checkpoint creates v2. The v1 path
never accepts a v2 record.

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

Current authoring commands reject split workspaces so they cannot collapse or
corrupt external collection files. The retained split-file reader accepts a
declared `collection_files` list, combines those files in memory, and validates
the result. It is parked compatibility, not a supported scaling path. There is
no current split-file writer or schema-migration exception.

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
