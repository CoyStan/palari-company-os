# Which Files Palari Trusts

Palari keeps its saved state in ordinary, inspectable local files. Fast status
views are calculated from those files.

## Current State

Each local workspace stores authoritative current state in one exact selected
file:

| Storage profile | Exact current-state file | Control root |
| --- | --- | --- |
| Ordinary | `workspace.json`, or another explicitly selected file | the workspace directory |
| Maintainer | repository-root `.palari-company-os.json` | repository-root `.palari-company-os/` |

The technical name for this file's role is the current-state `projection`.
The ACME example lives at `examples/acme-company-os/workspace.json`; this
repository's committed historical dogfood records live at
`workspaces/palari-company-os/workspace.json`.

Queue, detail, and state are display-only status views (`read_models`) derived
from the exact selected current-state file. They do not inspect output bytes or
scan history. `validate` checks stored structure and bindings, while `scope`
checks an explicit set of observed paths. Neither changes permissions or
approvals.

Maintainer state is selected only by explicitly passing
`--workspace .palari-company-os.json` (or its exact absolute path). A directory
or omitted selector continues to look only for ordinary `workspace.json`; no
repository-name or package-path heuristic discovers hidden state.

## Maintainer Binding

Maintainer Profile v1 adds two strict local binding records without changing
workspace schema v2:

```text
.palari-company-os/binding.json
<Git common directory>/palari-maintainer-repository.json
```

The binding contains one random state identifier, the matching random
repository identifier, the exact supported workspace/control layout, and a
canonical digest. The Git-common-directory record carries the repository
identifier independently. Palari verifies both, the Git root and common
directory, exact path types, ignore rules, tracking state, and absence of
symlinks before loading or changing maintainer state.

These identifiers detect mismatch and accidental state transplant. They are
not secrets, signatures, authenticated human identity, approval, or protection
against a hostile process running as the same operating-system user.

The hidden workspace, binding, journal, assignments, packets, and caches are
local control state and never source-candidate Git projections or task outputs.
Palari does not force-add them. The exact Git commit remains source and artifact
identity; maintainer claims bind it separately to the authority catalog and
local workspace/journal witness.

An optional `.palari-company-os/verification.json` belongs to the parked
external-maintainer repository-status view. It is advisory and does not become
profile binding, current check results, or approval authority.

## Tamper-Evident History

The only current change-history format is
`governance-journal.v2.jsonl`. Its physical location follows the selected
profile:

```text
# ordinary
.palari/governance-journal.v2.jsonl

# maintainer
.palari-company-os/.palari/governance-journal.v2.jsonl
```

The filename keeps the exact machine term `governance-journal`; operators can
read it as tamper-evident history. It is hash-chained and replayable. Palari
fsyncs a prepared record before atomically replacing the exact selected
current-state file, then fsyncs the commit marker. Verification detects
unfinished changes, corruption, truncation, reordering, forks, and disagreement
with the current workspace. A manual-repair restore point keeps a visible
continuity break instead of rewriting history.

A committed `.palari/governance-journal.v1.jsonl` is accepted only as a sealed,
strictly verified predecessor during explicit v2 activation. A committed
`.palari/history.jsonl` is historical evidence only; current code never reads,
appends, or imports it.

New workspaces create v2 directly. Existing workspaces without this history
reject ordinary writes until an explicit checkpoint creates v2. The v1 path
never accepts a v2 record.

## Safe Concurrent Writes

Writes to the selected current-state file use an ownership-bound local lock and
optimistic change detection. Ordinary locks live under sibling
`.palari/locks/`; maintainer locks live under
`.palari-company-os/.palari/locks/`. An fsynced atomic replace prevents partial
files. A hash of the loaded file prevents an older command from overwriting a
newer change. Maintainer writes additionally recheck the immutable binding
witness. When another writer finishes first, or either selected file or binding
changes, the stale command stops and should be retried only after the workspace
is reloaded and the mismatch is understood.

Together, the selected current-state file and its v2 journal are Palari's
durable workspace storage: current state plus replayable, tamper-evident change
history. Maintainer `binding.json` and the matching Git repository identifier
are required local identity preconditions for that storage, not alternate
workspace truth.

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
