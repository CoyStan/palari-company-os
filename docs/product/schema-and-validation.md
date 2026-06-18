# Schema And Validation

The first implementation has two layers of contract:

- typed Python models in `src/palari_company_os/models.py`
- a workspace JSON Schema in `schemas/workspace.schema.json`

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

The JSON Schema is kept as an inspectable machine contract for other tools and
future editors. It is intentionally local and dependency-free in this first
slice; the repo does not require a third-party JSON Schema validator yet.

