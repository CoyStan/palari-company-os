# Verification

Use focused checks while editing, then run the normal verification stack before
claiming the work is done.

## Normal Verification

```bash
./scripts/verify.sh
./scripts/install_smoke.sh
python3 spec/pcaw/v1/conformance.py -- ./bin/palari proof verify
./scripts/pcaw_demo.sh
```

`verify.sh` defaults to the authoritative `complete` profile. It always runs
the full unit suite, static checks, fixture and schema validation, and the
documented CLI smokes. The install smoke is a separate package-boundary check.

## Useful Focused Checks

```bash
./scripts/verify.sh focused tests.test_agent_packets
./scripts/verify.sh focused tests.test_validation tests.test_integrations
./scripts/verify.sh affected src/palari_company_os/agent_finish.py
./scripts/verify.sh affected --git-diff
```

The `affected` profile maps known paths to deterministic test modules. An
unknown path fails safe by running the full unit suite. Use `--list` after a
focused or affected command to inspect the selection without running it.

Focused and affected profiles shorten iteration only. They are not acceptance
proof and never replace the complete profile.

## CLI Smokes

```bash
./bin/palari validate --json
./bin/palari queue --json
./bin/palari docs check --json
./bin/palari --workspace examples/acme-company-os agent next --json
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
