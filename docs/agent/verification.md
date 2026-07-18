# Verification

Use focused checks while editing, then run the normal verification stack before
claiming the work is done.

## Normal Verification

```bash
./scripts/verify.sh
./scripts/install_smoke.sh
python3 spec/pcaw/v1/conformance.py -- ./bin/palari proof verify
./scripts/pcaw_demo.sh
python3 -m unittest discover -s tests -p 'test_approval_packs.py'
python3 -m unittest discover -s tests -p 'test_reversible_checkpoints.py'
```

`verify.sh` defaults to the authoritative `complete` profile. It always runs
the full unit suite, static checks, fixture and schema validation, and the
documented CLI smokes. The install smoke is a separate package-boundary check.

## Useful Focused Checks

```bash
./scripts/verify.sh focused tests.test_agent_packets
./scripts/verify.sh focused tests.test_operator_journeys tests.test_agent_file_changes
./scripts/verify.sh focused tests.test_validation tests.test_integrations
./scripts/verify.sh affected src/palari_company_os/agent_finish.py
./scripts/verify.sh affected --git-diff
```

The `affected` profile maps known paths to deterministic test modules. An
unknown path fails safe by running the full unit suite. Use `--list` after a
focused or affected command to inspect the selection without running it.

Focused and affected profiles shorten iteration only. They are not acceptance
proof and never replace the complete profile.

For operator-loop changes, verify all three journeys: initialize/add/start-next,
advance to independent review, and approval-inbox presentation to one exact
human action. Include durable `agent release` success, foreign/malformed/missing claim,
interrupted-release retry, and changed-state rejection. Record interaction
counts separately from test-process time.

For host-adoption or MCP-loop changes run:

```bash
python3 -m unittest tests.test_agent_adoption tests.test_git_hooks \
  tests.test_mcp_server tests.test_agent_session_contract
```

Exercise every declared host profile in an isolated Git repository. Preserve
existing instructions/configuration, reject malformed or foreign managed
state, and keep hosts without a proven native session protocol explicitly
advisory. MCP tests must prove deterministic advance stops before review,
human authority, and external effects.

For governance-journal changes run:

```bash
python3 -m unittest tests.test_governance_journal \
  tests.test_governance_journal_crash tests.test_store_journal_integration
./bin/palari history --verify --json
```

Active v1 verification still parses linearly. Compact v2 verification hashes
and state-validates the sealed v1 predecessor without retaining its record
payloads (transaction-identity sets still scale with transaction count), then
streams the v2 checkpoint/tail. A
request-local context should keep one aggregate operation to one verified scan,
but performance assertions must include predecessor continuity and current
workspace comparison; they must not promote a persistent cache into authority.
Report raw journal verification separately from full `agent next`, `queue`, and
`state` time so unrelated workspace validation/read-model cost is attributable.

## CLI Smokes

```bash
./bin/palari validate --json
./bin/palari queue --json
./bin/palari queue --approval-inbox --json
./bin/palari history --checkpoints --json
./bin/palari docs check --json
./bin/palari --workspace examples/acme-company-os agent next --json
./bin/palari --workspace examples/acme-company-os agent brief WORK-0003 \
  --as PALARI-SOFIA --mode execute --json
./bin/palari proof verify spec/pcaw/v1/vectors/valid/accepted/statement.json \
  --subject-root spec/pcaw/v1/vectors/valid/accepted --json
```

## Reporting

Report:

- checks run
- relevant focused tests
- any skipped checks and why
- changed files
- remaining risks
