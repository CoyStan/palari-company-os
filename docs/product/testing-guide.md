# Testing Guide

Palari has one authoritative candidate command:

```bash
python3 -m pip install -e ".[dev]"
./scripts/verify.sh complete
```

`./scripts/verify.sh` defaults to `complete`. The gate runs the current test
suite once, static checks once, PCAW conformance once, and one isolated wheel
build/install smoke. CI invokes this command on Python 3.12. Python 3.10, 3.11,
3.13, and 3.14 run only source import, pure governance-kernel, and CLI-help
compatibility checks.

CI runs branch candidates through `pull_request` and runs `push` only on
`main`, so an open pull request is not evaluated again merely because its branch
was pushed. Superseded runs are cancelled.

## What the candidate proves

The complete profile includes:

1. exhaustive pure governance, scope, and canonicalization tests;
2. focused filesystem, symlink, journal, proof, and required stored-format
   reader tests;
3. one temporary-workspace CLI golden path and structured failures;
4. supported adapter contract tests separated from core authority tests;
5. repository text checks, Ruff, mypy, compilation, schema checks, agent-ready
   documentation checks, PCAW TCB accounting, and PCAW conformance; and
6. one wheel built and installed into an isolated temporary virtual environment.

The installed smoke initializes a temporary Git workspace without a host
profile, validates the installed CLI there, and verifies a copied PCAW bundle
with network sockets disabled. It does not depend on packaged example data and
does not exercise integration approval or human-decision ceremony.

The committed dogfood workspace is permanent historical/operator evidence. It
is excluded from candidate style, CLI, and package checks. Full dogfood audit is
an explicit human operator action, not a prerequisite for ordinary development.

## Focused iteration

Name the relevant test modules while changing a coherent slice:

```bash
./scripts/verify.sh focused tests.test_governance_kernel
./scripts/verify.sh focused tests.test_validation tests.test_transition_checks
./scripts/verify.sh focused tests.test_integrations tests.test_linear_adapter
```

Focused mode validates and runs only the named `tests.test_*` modules. It has no
changed-path registry and no hidden fallback to the complete suite. Run the
complete profile only after focused repairs stabilize.

For the package boundary alone:

```bash
./scripts/install_smoke.sh
```

This direct command is diagnostic; a successful complete profile has already
run the same smoke once.

## Performance and fixture rules

- Keep lifecycle matrices pure and deterministic.
- Use temporary current workspaces for CLI and mutation tests.
- Create Git repositories, spawn Palari, copy workspaces, scan journals, and
  build packages only when that operation is the behavior under test.
- Give each retained public surface one or two translation tests rather than a
  duplicate governance matrix.
- Profile only the slowest meaningful areas reported by the parallel runner.
- Never make persistent caches, the committed example, or dogfood history into
  acceptance authority.

When a candidate fails, reproduce the exact failure with focused tests, repair
it, and rerun the complete gate only after the focused checks are stable.
