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

The CLI validation path uses the Python models and strict workspace checks:

```bash
./bin/palari validate
./bin/palari validate --json
```

Validation checks:

- supported `schema_version`
- required root fields and required collections
- unknown root or record fields
- required record ids
- basic field types
- supported lifecycle values for statuses, risk, intensity, evidence status,
  review verdicts, human decision values, and outcome status
- unique ids per collection
- work item goal and Palari references
- Palari owner, goal, active-work, and outcome references
- decision human, goal, work, and Palari references
- attempt, evidence, review, human decision, and outcome references
- non-negative approval quorum counts
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
required collections exist. Workspaces with a newer schema version fail closed
until this code supports them.

The JSON Schema is kept as an inspectable machine contract for other tools and
future editors. It is intentionally local and dependency-free in this first
slice; the repo does not require a third-party JSON Schema validator yet.

Focused validation fixtures live in `tests/fixtures/workspaces/`. They include
valid workspaces and deliberately invalid workspaces for unknown fields,
unsupported schema versions, broken references, stale evidence, stale review,
unqualified human approval, invalid lifecycle state, invalid completed work, and
valid accepted/completed work.
