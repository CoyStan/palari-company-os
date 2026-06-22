# Schema And Validation

The first implementation has two layers of contract:

- typed Python models in `src/palari_company_os/models.py`
- a workspace JSON Schema in `schemas/workspace.schema.json`

The current workspace schema version is:

```text
1
```

Every current workspace must include:

```json
{
  "schema_version": 1
}
```

Large workspaces may keep records in additional collection files while
preserving `workspace.json` as the manifest:

```json
{
  "schema_version": 1,
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

Read-only commands such as `validate`, `queue`, `detail`, `state`, and
`dashboard` can read split workspaces. Authoring and lifecycle write commands
currently refuse split workspaces with a clear error instead of silently
collapsing or corrupting collection files.

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
- unique ids per collection
- work item goal and Palari references
- work item workbench, parent work item, and dependency references
- work item allowed source references
- work item source and output targets stay inside its workbench boundary when
  a workbench is declared
- parent workbench and parent work item graphs do not contain cycles
- workbench goal, Palari, human, source, and parent workbench references
- work item recommended playbooks reference declared playbook sources and
  included playbooks
- source owner human and allowed Palari references
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
- Palari owner, goal, active-work, and outcome references
- Palari memory sources reference existing source records
- decision human, goal, work, and Palari references
- attempt, evidence, review, human decision, receipt, and outcome references
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
- accepted human decisions are made by a human with the required approval
  capability
- completed work has fresh passing evidence, fresh accept-ready review, no open
  linked decision, and enough qualified human approvals

Validation is intentionally stricter than a permissive JSON reader. Extra fields
fail closed so typos and hidden state cannot quietly enter the source of truth.

Migration:

```bash
./bin/palari migrate
./bin/palari migrate --write
```

`migrate` adds `schema_version: 1` to old unversioned workspaces and ensures
required collections exist. Optional collections such as `playbook_sources`,
`workbenches`, `integrations`, and `integration_plans` may be absent from older
v1 workspaces; if present, they are still strictly validated. Workspaces with a
newer schema version fail closed until this code supports them.

The JSON Schema is kept as an inspectable machine contract for other tools and
future editors. It is intentionally local and dependency-free in this first
slice; the repo does not require a third-party JSON Schema validator yet.

Focused validation fixtures live in `tests/fixtures/workspaces/`. They include
valid workspaces and deliberately invalid workspaces for unknown fields,
unsupported schema versions, broken references, stale evidence, stale review,
unqualified human approval, invalid lifecycle state, invalid completed work,
source/receipt boundary failures, workbench graph failures, workbench boundary
failures, and valid accepted/completed work.
