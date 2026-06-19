# Testing Guide

The main verification command is:

```bash
./scripts/verify.sh
```

It runs:

- unit tests
- style checks with `scripts/check_style.py`
- Python compilation
- JSON validity checks for example workspaces and schemas
- CLI smoke checks for `validate`, `state`, `queue`, `detail`, `scope`,
  `history`, and `maintainer status`
- validation and queue/detail/history smoke checks for the repo dogfood
  workspace at `workspaces/palari-company-os`

The package install smoke command is:

```bash
./scripts/install_smoke.sh
```

It creates a temporary virtual environment, installs the package in editable
mode, imports `palari_company_os`, and runs the installed `palari` command
against the example workspace.

Focused commands:

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests
python3 -m compileall -q src
python3 -m json.tool examples/acme-company-os/workspace.json
python3 -m json.tool workspaces/palari-company-os/workspace.json
python3 -m json.tool schemas/workspace.schema.json
./bin/palari --workspace workspaces/palari-company-os validate
./bin/palari --workspace workspaces/palari-company-os queue
```

The test suite covers:

- model loading
- strict validation fixtures
- unknown-field rejection
- unsupported schema version rejection
- cross-reference validation
- invalid lifecycle state rejection
- queue state
- detail assembly
- stale evidence
- stale review
- scope allow/block behavior
- append-only history events for successful mutations
- failed mutations do not append history events
- human authority and approval capability
- quorum completion gates
- valid accepted/completed work
- authoring commands
- lifecycle commands
- migration from legacy unversioned workspaces
- external maintainer status
- dogfood workspace validation and read-model smoke checks
