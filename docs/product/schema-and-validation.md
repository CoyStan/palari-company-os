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

The CLI validation path currently uses the Python models and cross-reference
checks:

```bash
./bin/palari validate
./bin/palari validate --json
```

Validation checks:

- required record ids
- basic field types
- unique ids per collection
- work item goal and Palari references
- Palari owner, goal, active-work, and outcome references
- decision human, goal, work, and Palari references
- attempt, evidence, review, human decision, and outcome references
- non-negative approval quorum counts

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
