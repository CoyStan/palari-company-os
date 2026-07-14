# Testing Guide

The main verification command is:

```bash
./scripts/verify.sh
```

This is the authoritative `complete` profile. `./scripts/verify.sh complete`
is equivalent and is useful when a caller wants to name the profile explicitly.

It runs:

- unit tests
- style checks with `scripts/check_style.py`
- Python compilation
- JSON validity checks for example workspaces and schemas
- CLI smoke checks for core read models, agent packets, playbooks, dashboard,
  desktop prototype, documentation, integrations, and the demo
- validation and read-model smokes for the repo dogfood and split-workspace
  fixtures

For faster development feedback, name tests directly or select tests from
changed paths:

```bash
./scripts/verify.sh focused tests.test_agent_packets
./scripts/verify.sh focused tests.test_validation tests.test_transition_checks
./scripts/verify.sh affected src/palari_company_os/transition_checks.py
./scripts/verify.sh affected --git-diff
```

Add `--list` to a focused or affected command to print its deterministic test
selection. If an affected path has no safe mapping, the command runs the full
unit suite. These profiles are iteration tools only; final acceptance still
requires the complete profile.

The package install smoke command is:

```bash
./scripts/install_smoke.sh
```

It creates a unique temporary virtual environment, builds and installs a wheel,
imports `palari_company_os`, and runs the installed `palari` command against
temporary workspace copies. Logs and generated files are written only inside
that unique temporary directory and are removed at exit, so concurrent runs do
not share fixed `/tmp` paths.

Focused commands:

```bash
python3 -m pip install -e .
python3 -m unittest tests.test_agent_packets
python3 -m compileall -q src
python3 -m json.tool examples/acme-company-os/workspace.json
python3 -m json.tool workspaces/palari-company-os/workspace.json
python3 -m json.tool schemas/workspace.schema.json
./bin/palari --workspace workspaces/palari-company-os validate
./bin/palari --workspace workspaces/palari-company-os queue
./bin/palari --workspace tests/fixtures/workspaces/split-workspace validate
./bin/palari --workspace tests/fixtures/workspaces/split-workspace detail WORK-SPLIT
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
- read-only split workspace collection files
- write refusal for split workspaces
- in-place split-workspace migration with stale-proof invalidation
- coordinated claim/packet/baseline rehash rejection and Git witness history
- agent-shell denial for human-only and packet-authority commands, dynamic
  shell/Git-global-option approval, composed-command masking, helper-launching
  config/environment options, post-release workspace-truth protection, and
  option-encoded/linked-worktree metadata paths, pager/filter helpers, and
  compact/newline separators, ordinary directory destinations, repository or
  ripgrep helper overrides, global-option abbreviation rejection, destructive
  ancestor targets, and active-claim scope-change rejection
- nonterminal acceptance evidence/receipt tamper rejection
- external maintainer status
- dogfood workspace validation and read-model smoke checks
