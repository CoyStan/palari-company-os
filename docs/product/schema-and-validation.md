# Schema And Validation

The first implementation has two layers of contract:

- typed Python models in `src/palari_company_os/models.py`
- a workspace JSON Schema in `schemas/workspace.schema.json`

The current workspace schema version is:

```text
2
```

Every current workspace must include:

```json
{
  "schema_version": 2
}
```

Large workspaces may keep records in additional collection files while
preserving `workspace.json` as the manifest:

```json
{
  "schema_version": 2,
  "name": "Example",
  "collection_files": {
    "workbenches": ["records/workbenches.json"],
    "work_items": ["records/work-items.json"]
  },
  "work_items": []
}
```

Collection files are read at load time, merged in memory with the matching root
collection, and then validated through the same strict checks as single-file
workspaces. The root `workspace.json` must still declare all required
collections; split files add records to those collections.

Collection file paths must be workspace-relative. Absolute paths and paths that
contain `..` fail closed. Each collection file contains a JSON array of records
for the collection named in the manifest.

Read-only commands such as `validate`, `queue`, `detail`, and `state` can read
split workspaces. Authoring and lifecycle write commands
currently refuse split workspaces with a clear error instead of silently
collapsing or corrupting collection files. Schema migration is the narrow
exception: it validates the consolidated records, preserves each record's root
or included-file placement, writes included files first, and advances the root
schema version last so an interrupted migration remains fail closed and
retryable.

The CLI validation path uses the Python models and strict workspace checks:

```bash
./bin/palari validate
./bin/palari validate --json
```

Validation checks:

- supported `schema_version`
- required root fields and required collections
- optional `collection_files` manifest shape
- split collection file path safety and JSON array shape
- unknown root or record fields
- required record ids
- basic field types
- supported lifecycle values for statuses, risk, intensity, evidence status,
  review verdicts, human decision values, and outcome status
- optional evidence `output_binding_version`; newly authored evidence uses
  `palari.evidence_outputs.v1` to bind every receipt output to an artifact digest
- unique ids per collection
- work item goal and Palari references
- work item workbench, parent work item, and dependency references
- work item allowed source references
- work item source and output targets stay inside its workbench boundary when
  a workbench is declared
- optional work-item `path_intents` use only exact canonical repository paths
  and `create`, `modify`, or `delete`; paths must be unique, prefix-disjoint,
  and inside the declared write boundary
- parent workbench and parent work item graphs do not contain cycles
- workbench goal, Palari, human, source, and parent workbench references
- work item recommended playbooks reference declared playbook sources and
  included playbooks
- source owner human and allowed Palari references
- source readiness metadata uses supported data class and authority values
- source steward humans reference existing human records
- integration owner human and source references
- integration allowed actions are supported by the declared provider
- integration allowed actions are supported by the declared mode
- integration plans reference enabled integrations and existing work items
- integration plans use events and actions allowed by the referenced
  integration
- integration plan payload previews must not contain raw secret-looking values
- integration plans require human approval before any future external action
- approved, rejected, and canceled integration plans record the qualified human
  reviewer and review timestamp
- integration outbox items reference approved integration plans and qualified
  enqueueing humans
- integration outbox payload previews and source boundaries must match the
  approved plan
- duplicate integration outbox items for the same plan fail closed
- integration outbox payload previews must not contain raw secret-looking values
- canceled integration outbox items require qualified `canceled_by`,
  `canceled_at`, and `cancel_reason` metadata
- optional playbook source record shape
- capability record kind, status, risk level, owner, source, and allowed Palari
  references
- built-in and custom authority profile risk/quorum settings
- proposal status, risk, intensity, scope boundary references, adoption link,
  and human decision metadata
- Palari owner, goal, active-work, and outcome references
- Palari memory sources reference existing source records
- decision human, goal, work, and Palari references
- attempt, evidence, review, human decision, receipt, and outcome references
- attempt isolation metadata such as explicit head SHA, allowed paths,
  forbidden paths, and claim lease fields
- evidence manifest hash shape, exact receipt binding, artifact presence, and
  artifact hash path safety
- an evidence artifact with `status: absent` uses exactly `sha256:absent`, is
  declared as an artifact, and corresponds to an exact work-item delete intent;
  no other artifact may use the absent digest
- receipt hash, previous receipt hash, and evidence manifest hash shape
- mandatory exact review-binding fields for every `accept-ready` verdict,
  covering the attempt, evidence, receipt, work contract, and aggregate proof
  hash including reviewer-authored verdict context
- non-negative approval quorum counts
- receipts use only sources allowed by the work item
- receipt actor matches the attempt actor or work Palari
- planned external writes in a receipt reference approved integration plans for
  the same work item
- queued external writes in a receipt reference queued integration outbox items
  for the same work item
- canceled integration outbox items cannot be referenced as queued external
  writes in receipts
- external writes in a receipt require an explicit external-write action
- accepted human decisions reference fresh passing evidence and fresh
  accept-ready review
- latest attempt, evidence, review, acceptance, receipt, outcome, and
  integration ordering compares timezone-bearing timestamps as normalized UTC
  instants, not lexical timestamp spellings; malformed or timezone-free values
  and instants outside the UTC-normalizable datetime range fail closed, and two
  records for the same work item cannot claim the same instant because their
  latest-state order would be ambiguous. For schema-v2 compatibility, one
  undated record remains loadable only when no ordering choice exists; once a
  work item has multiple records of that kind, every record must be dated
- human decisions have timezone-bearing, unambiguous timestamps; decision and
  status must agree before an acceptance can count
- pack-bound human decisions require a complete exact pack/member/subject/
  request binding, one retained canonical manifest per pack, and an action
  consistent with decision and status; copied or incomplete member bindings
  fail closed. New pack-v2 decisions additionally require the supported
  presentation schema and surface, an exact presentation digest, and exactly
  one retained canonical artifact per presentation. The artifact must project
  its exact pack members and current relevant decision context; missing,
  downgraded, malformed, or transplanted presentation bindings fail closed,
  while historical pack-v1 decisions remain readable
- accepted human decisions are made by a human with the required approval
  capability
- acceptance records reference fresh passing evidence, fresh accept-ready
  exact-bound review, qualified human authority, matching receipt hash, and a
  matching human-decision record; nonterminal acceptance recomputes current
  artifact bytes before execution, while terminal acceptance validates its
  immutable stored proof rather than rebinding history to a later checkout;
  `accepted_at` orders acceptance and revocation records, and the latest status controls
- completed work has fresh passing evidence, fresh accept-ready review, no open
  linked decision, current exact proof, a terminal clean attempt, and enough
  qualified human approvals; each human's latest decision for that exact
  review, evidence, and reviewed head controls whether their approval counts
- terminal work with an exact-bound review also requires the matching
  acceptance record; removing it fails closed

### Exact Path Intents And Deletion Tombstones

`path_intents` is additive. Historical work items may omit it and keep the
existing `output_targets` presence contract. When present, it becomes the exact
mutation contract:

```json
{
  "path_intents": [
    {"path": "docs/new.md", "intent": "create"},
    {"path": "docs/current.md", "intent": "modify"},
    {"path": "docs/obsolete.md", "intent": "delete"}
  ]
}
```

The packet write boundary is the listed exact paths. Git-aware checking
requires the matching change class. Create and modify must end as regular
files; delete must end absent and be observed as deleted. Evidence for the
delete uses `{ "path": "docs/obsolete.md", "sha256": "sha256:absent",
"status": "absent" }`. A missing ordinary output remains an error, and a fake
absent record without the matching delete intent fails closed. This local
tombstone is not a PCAW v1 portable deletion-history guarantee.

Validation is intentionally stricter than a permissive JSON reader. Extra fields
fail closed so typos and hidden state cannot quietly enter the source of truth.

## Governance Journal Formats

`palari.governance-journal.v1` remains a supported strict JSONL format. Its
prepare records retain complete `after_projection` values so existing tools and
workspaces remain readable and crash-recoverable without an implicit rewrite.

`palari.governance-journal.v2` is a staged compact format. Its first committed
prepare is a full content-bound checkpoint. Later mutation prepares replace
the repeated projection with a canonical, prefix-disjoint JSON Pointer delta:
`add` and `replace` carry the exact value; `remove` carries no value. Applying
the delta must reproduce the recorded workspace digest and the delta must equal
the deterministic minimal diff, otherwise verification fails closed.

An already-journaled v1 workspace activates v2 only through an explicit,
idempotent `history --checkpoint`. The v2 checkpoint seals the exact verified
v1 file as a predecessor and does not edit or rename it. A workspace with no
journal first creates the ordinary v1 checkpoint; a second explicit checkpoint
performs the v2 activation. This staged rule preserves existing raw-journal and
Git artifact compatibility. New v2 records may retain the established v1
filename only in isolated test/API construction; the record schema, never the
filename, determines validation behavior.

V2 verification reads one JSONL record at a time and retains only the current
workspace projection, pending prepare, and fixed-size chain state. When a v1
predecessor exists, its bytes are streamed through SHA-256 on every verification
and compared with the authoritative binding in the v2 checkpoint; they are not
reparsed and no advisory cache can authorize a transition.

Migration:

```bash
./bin/palari migrate
./bin/palari migrate --write
```

`migrate` upgrades unversioned, v0, and v1 workspaces to schema v2 and ensures
known collections exist, including optional governance collections such as
`capabilities`, `authority_profiles`, `proposals`, and `acceptance_records`.
Migration fails safe: legacy unbound `accept-ready` reviews become `blocked`,
accepting decisions tied to them become blocked, matching acceptance records
are revoked, and governed terminal work is reopened for a fresh exact-bound
review. Missing or ambiguous human-decision timestamps are assigned stable,
UTC-normalized values. Split workspaces retain their collection-file layout;
concurrent changes to the root or any included file block the write. A preview
lists every migration action before `--write` persists it. Workspaces with a
newer schema version fail closed until this code supports them.

Schema v2 deliberately makes the exact review binding non-optional for
`accept-ready`. Historical unbound non-accepting verdicts remain inspectable,
but no legacy marker can manufacture acceptance authority.

The JSON Schema is kept as an inspectable machine contract for other tools and
future editors. It is intentionally local and dependency-free in this first
slice; the repo does not require a third-party JSON Schema validator yet.

Focused validation fixtures live in `tests/fixtures/workspaces/`. They include
valid workspaces and deliberately invalid workspaces for unknown fields,
unsupported schema versions, broken references, stale evidence, stale review,
unqualified human approval, invalid lifecycle state, invalid completed work,
source/receipt boundary failures, workbench graph failures, workbench boundary
failures, and valid accepted/completed work.
