# Palari Company OS

Palari Company OS is a repo-native operating layer for AI-assisted company
work. It helps a company define named **Palaris**, human roles, goals,
decisions, evidence, review, and authority boundaries without inheriting the
ceremony of the older Palari Orchestrator ticket workflow.

A **Palari** is the named face of a workflow or AI workstream. A Palari has a
name, scope, allowed inputs, standards, memory/context, evidence, outcomes, and
authority boundaries. Execution may be delegated to models, tools, workers, or
agents, but the Palari remains the stable human-facing work partner.

## First Success

From the repo root:

```bash
./bin/palari queue
./bin/palari detail WORK-0001
```

JSON output is also available:

```bash
./bin/palari queue --json
./bin/palari detail WORK-0001 --json
./bin/palari validate
./bin/palari state
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json
```

The default workspace is `examples/acme-company-os`. Use another workspace with:

```bash
./bin/palari --workspace /path/to/workspace queue
```

## Product Loop

```text
Human intent
  -> Palari preparation
    -> bounded AI/tool execution
      -> evidence
        -> review
          -> human decision
            -> outcome and learning
```

The first implementation focuses on fast read models:

- `queue`: what needs attention now and why.
- `detail`: one coherent view of a work item and its related objects.
- `state`: a compact workspace read model.
- `validate`: fail-closed workspace validation.
- `scope`: declared path/action boundary checks.
- `maintainer status`: lightweight external-maintainer repo status.

## Development

This repo intentionally uses ordinary software engineering. It does not use the
old Palari ticket ceremony.

```bash
python3 -m unittest discover -s tests
./bin/palari queue --json
./bin/palari detail WORK-0001 --json
```

## Documentation

- [Product Model](docs/product/company-os.md)
- [Core Objects](docs/product/core-objects.md)
- [Authority And Gates](docs/product/authority-and-gates.md)
- [Source Of Truth](docs/product/source-of-truth.md)
- [External Maintainer Mode](docs/product/external-maintainer-mode.md)
- [Schema And Validation](docs/product/schema-and-validation.md)
- [Command Reference](docs/product/command-reference.md)
- [Milestone Completion Report](docs/product/milestone-completion-report.md)
