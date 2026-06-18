# Command Reference

All commands are read-only in the first implementation. They do not accept,
merge, push, deploy, activate policy, execute broker side effects, use secrets,
or mutate authority state.

## Queue

```bash
./bin/palari queue
./bin/palari queue --json
```

Shows the operator queue with attention state, goal, Palari, owner, adaptive
intensity, evidence state, review state, approval progress, integration state,
and next action.

## Detail

```bash
./bin/palari detail WORK-0001
./bin/palari detail WORK-0001 --json
```

Assembles one work item with its goal, Palari, attempt, evidence, review,
linked decisions, human decisions, outcome, safety state, and next action.

## State

```bash
./bin/palari state
./bin/palari state --json
```

Shows a compact operator state: record counts, attention counts, and queue
items. This is the first fast read model for the whole workspace.

## Validate

```bash
./bin/palari validate
./bin/palari validate --json
```

Validates model shape and cross-references. It fails closed when required ids,
types, references, or approval counts are invalid.

## Scope

```bash
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json
./bin/palari scope WORK-0001 --changed secrets.env --action deploy
```

Checks paths and actions against a work item's declared allowed resources and
forbidden actions.

## External Maintainer Status

```bash
./bin/palari maintainer status
./bin/palari maintainer status --json
```

Reports repo path, branch, head, upstream, divergence, dirty files, focused
tests run if known, and PR readiness.

Focused tests are known only if an optional local verification log exists at:

```text
.palari-company-os/verification.json
```

This file is intentionally ignored by git.

## Verification

```bash
./scripts/verify.sh
```

Runs unit tests, Python compilation, JSON validity checks, and CLI smoke checks
for queue, detail, state, validate, scope, and maintainer status.

