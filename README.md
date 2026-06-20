# Palari Company OS

Palari Company OS is a repo-native operating layer for AI-assisted company
work. It helps a company define named **Palaris**, human roles, goals,
decisions, evidence, review, and authority boundaries without inheriting the
ceremony of the older Palari Orchestrator ticket workflow.

A **Palari** is the named face of a workflow or AI workstream. A Palari has a
name, scope, allowed inputs, standards, memory/context, evidence, outcomes, and
authority boundaries. Execution may be delegated to models, tools, workers, or
agents, but the Palari remains the stable human-facing work partner.

## Current Maturity

This repository is a v0.1 local CLI foundation. It is meant to be cloned,
installed, tested, reviewed, and extended like a normal Python project.

It does not yet include a web UI, production deployment, real broker execution,
real policy acceptance authority, enterprise administration, or signed key
custody. Those boundaries are intentional and documented in the roadmap and
security notes.

## Install

For local development, use an editable install from the repo root:

```bash
python3 -m pip install -e .
palari --help
```

You can also run the repo-local wrapper without installing:

```bash
./bin/palari --help
```

## Quickstart

From the repo root:

```bash
./bin/palari queue
./bin/palari detail WORK-0001
```

JSON output and operating commands are also available:

```bash
./bin/palari queue --json
./bin/palari detail WORK-0001 --json
./bin/palari validate
./bin/palari state
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json
./bin/palari history
./bin/palari dashboard --out /tmp/palari-company-dashboard
./bin/palari kilo status
./bin/palari kilo run WORK-0001 --message "Start this bounded work"
```

The default workspace is `examples/acme-company-os`. Use another workspace with:

```bash
./bin/palari --workspace /path/to/workspace queue
```

The repo also dogfoods itself with a real Palari Company OS workspace:

```bash
./bin/palari --workspace workspaces/palari-company-os queue
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0001
```

If you run the installed `palari` command from outside this repo, pass a
workspace path explicitly:

```bash
palari --workspace /path/to/workspace validate
palari --workspace /path/to/workspace queue
```

## Product Loop

```text
Human intent
  -> Palari preparation
    -> selected sources
      -> bounded AI/tool execution
        -> receipt
          -> evidence/review/human decision when risk requires it
            -> outcome and learning
```

The current implementation provides a local workspace CLI:

- `queue`: what needs attention now and why.
- `detail`: one coherent view of a work item and its related objects.
- `state`: a compact workspace read model.
- `validate`: fail-closed workspace validation.
- `scope`: declared path/action boundary checks.
- `history`: recent append-only audit events for mutating commands.
- `dashboard`: static read-only visual supervision over queue, work, trust,
  history, and authority.
- `desktop-prototype` and `desktop-serve`: a future desktop shell prototype,
  with `desktop-serve` exposing local Kilo preview/run endpoints.
- authoring commands for goals, Palaris, humans, decisions, work, attempts,
  sources, receipts, evidence, reviews, human decisions, and outcomes.
- lifecycle commands for evidence, review, human decision, completion, and
  outcome.
- `maintainer status`: lightweight external-maintainer repo status.
- `kilo`: optional Kilo Code bridge that builds a bounded Palari work prompt
  and can call `kilo run` with explicit `--execute`.

## Development

This repo intentionally uses ordinary software engineering. It does not use the
old Palari ticket ceremony.

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests
./bin/palari queue --json
./bin/palari detail WORK-0001 --json
./scripts/verify.sh
./scripts/install_smoke.sh
```

`./scripts/verify.sh` runs unit tests, the lightweight style checker, Python
compilation, JSON validity checks, and CLI smoke checks. `install_smoke.sh`
creates a temporary virtual environment, installs the package, imports it, and
checks the installed `palari` command.

## Documentation

- [Changelog](CHANGELOG.md)
- [License](LICENSE)
- [Product Model](docs/product/company-os.md)
- [Quickstart](docs/product/quickstart.md)
- [Core Objects](docs/product/core-objects.md)
- [Authority And Gates](docs/product/authority-and-gates.md)
- [Source Of Truth](docs/product/source-of-truth.md)
- [External Maintainer Mode](docs/product/external-maintainer-mode.md)
- [Kilo Code Integration](docs/product/kilo-code-integration.md)
- [Schema And Validation](docs/product/schema-and-validation.md)
- [Command Reference](docs/product/command-reference.md)
- [Lifecycle Guide](docs/product/lifecycle-guide.md)
- [Testing Guide](docs/product/testing-guide.md)
- [Troubleshooting](docs/product/troubleshooting.md)
- [Security Notes](docs/product/security.md)
- [Contributing](docs/product/contributing.md)
- [Roadmap](docs/product/roadmap.md)
- [Release And Operations](docs/product/release-and-operations.md)
- [Repo Completeness Definition](docs/product/repo-completeness-definition.md)
- [Repo Completeness Checklist](docs/product/repo-completeness-checklist.md)
- [Milestone Completion Report](docs/product/milestone-completion-report.md)
