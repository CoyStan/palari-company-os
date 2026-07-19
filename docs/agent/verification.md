# Verification

## Candidate gate

Install the pinned development tools once, then run the same authoritative gate
used by CI:

```bash
python3 -m pip install -e ".[dev]"
./scripts/verify.sh complete
```

The `complete` profile runs each candidate boundary once:

- the full current unittest suite through the parallel module runner;
- the repository text check, Ruff, mypy, and Python compilation;
- current example and schema syntax checks;
- PCAW trusted-code accounting and the normative conformance corpus;
- the agent-ready documentation check; and
- one wheel build and isolated installed-package smoke.

The installed-package smoke creates its own temporary Git project, initializes a
current workspace without installing a host profile, validates it, and verifies
a copied PCAW bundle with network sockets disabled. It never executes against
the committed example or dogfood workspace.

The complete gate is acceptance proof. Do not run its unit suite, wheel build,
or CLI boundaries separately and then invoke the complete profile again.

## Focused development checks

During implementation, name only the modules attributable to the current slice:

```bash
./scripts/verify.sh focused tests.test_governance_kernel
./scripts/verify.sh focused tests.test_validation tests.test_transition_checks
./scripts/verify.sh focused tests.test_agent_packets tests.test_agent_file_changes
```

Focused mode is a thin explicit unittest runner. It does not infer tests from
changed paths and never silently expands into the complete suite. It is useful
feedback, not candidate acceptance.

Useful direct boundaries include:

```bash
python3 -S -m unittest tests.test_governance_journal \
  tests.test_governance_journal_crash tests.test_store_journal_integration
python3 -S -m unittest tests.test_pcaw_protocol tests.test_canonical_json
python3 -S -m unittest tests.test_cli_smoke
./scripts/install_smoke.sh
```

Run `install_smoke.sh` directly only while repairing the package boundary; the
complete profile already includes it once.

## Test architecture

- Governance decisions belong in pure kernel tests.
- Filesystem, symlink, Git, journal, and subprocess work belongs only at genuine
  system boundaries.
- CLI, packet, hook, MCP, read-model, and adapter tests verify translation and
  capability limits rather than replaying the lifecycle matrix.
- CLI tests use temporary current workspaces.
- PCAW conformance uses the committed normative proof corpus and performs no
  network or workspace mutation.
- The committed dogfood workspace is historical/operator evidence, not a
  candidate fixture. A deliberate human audit of it is outside this gate.

## Reporting

Report the focused checks run, the final candidate command and result, changed
files, any skipped checks, and remaining risks.
