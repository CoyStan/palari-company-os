# Verification

Use focused checks while editing, then run the normal verification stack before
claiming the work is done.

## Normal Verification

```bash
./scripts/verify.sh
python3 -m unittest discover -s tests
./scripts/install_smoke.sh
```

## Useful Focused Checks

```bash
python3 -m unittest tests.test_agent_packets
python3 -m unittest tests.test_validation
python3 -m unittest tests.test_integrations
python3 -m unittest tests.test_docs
```

Use focused checks to iterate quickly. Do not treat a narrow focused check as
proof for a broad behavior change.

## CLI Smokes

```bash
./bin/palari validate --json
./bin/palari queue --json
./bin/palari docs check --json
./bin/palari --workspace examples/acme-company-os agent next --json
```

## Reporting

Report:

- checks run
- relevant focused tests
- any skipped checks and why
- changed files
- remaining risks
