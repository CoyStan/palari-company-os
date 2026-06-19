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
- CLI smoke checks for `validate`, `state`, `queue`, `detail`, `scope`, and
  `maintainer status`

Focused commands:

```bash
python3 -m unittest discover -s tests
python3 -m compileall -q src
python3 -m json.tool examples/acme-company-os/workspace.json
python3 -m json.tool schemas/workspace.schema.json
```

The test suite covers:

- model loading
- cross-reference validation
- queue state
- detail assembly
- stale evidence
- stale review
- scope allow/block behavior
- human authority and approval capability
- quorum completion gates
- authoring commands
- lifecycle commands
- migration from legacy unversioned workspaces
- external maintainer status
