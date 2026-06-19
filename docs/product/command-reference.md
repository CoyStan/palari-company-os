# Command Reference

Most commands are read-only. Authoring and lifecycle commands intentionally
write to `workspace.json` after validation. No command merges, pushes, deploys,
activates policy, executes broker side effects, uses secrets, or bypasses human
authority.

## Queue

```bash
./bin/palari queue
./bin/palari queue --json
```

Shows the operator queue with attention state, goal, Palari, owner, adaptive
intensity, evidence state, review state, approval progress, integration state,
learning signal, and next action.

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

## Migration

```bash
./bin/palari migrate
./bin/palari migrate --write
```

Adds `schema_version: 1` to legacy unversioned workspaces and ensures required
collections exist. Without `--write`, it previews changes.

## Authoring Commands

All authoring commands validate the full workspace before writing.

```bash
./bin/palari goal create GOAL-X --title "Improve onboarding"
./bin/palari goal update GOAL-X --status active

./bin/palari human create HUMAN-X --name "X Human" --list approval_capabilities=product
./bin/palari human update HUMAN-X --role "Reviewer"

./bin/palari palari create PALARI-X --name Xena --role "Onboarding partner" --owner-human HUMAN-X
./bin/palari palari update PALARI-X --scope "Prepare onboarding work"

./bin/palari decision create DECISION-X --question "Which option should we choose?"
./bin/palari decision update DECISION-X --status decided --set "result=Use option A"

./bin/palari work create WORK-X --title "Draft note" --goal GOAL-X --palari PALARI-X
./bin/palari work update WORK-X --set current_attempt=ATTEMPT-X

./bin/palari attempt record ATTEMPT-X --work-item-id WORK-X --actor PALARI-X
./bin/palari evidence record EVIDENCE-X --work-item-id WORK-X --attempt-id ATTEMPT-X --head-sha head-x --status passed
./bin/palari review record REVIEW-X --work-item-id WORK-X --reviewed-head head-x --reviewer HUMAN-X --verdict accept-ready
./bin/palari human-decision record HUMAN-DECISION-X --work-item-id WORK-X --human-id HUMAN-X --reviewed-head head-x --decision accepted --status accepted
./bin/palari outcome record OUTCOME-X --work-item-id WORK-X --summary "Useful result."
```

Use `--set FIELD=VALUE` for scalar fields and `--list FIELD=A,B,C` for list
fields. The authoring surface is intentionally simple and dependency-free.

## Lifecycle Commands

Lifecycle commands are aliases around evidence, review, decision, completion,
and outcome records.

```bash
./bin/palari lifecycle evidence EVIDENCE-X --work-item-id WORK-X --attempt-id ATTEMPT-X --head-sha head-x --status passed
./bin/palari lifecycle review REVIEW-X --work-item-id WORK-X --reviewed-head head-x --reviewer HUMAN-X --verdict accept-ready
./bin/palari lifecycle decide HUMAN-DECISION-X --work-item-id WORK-X --human-id HUMAN-X --reviewed-head head-x --decision accepted --status accepted
./bin/palari lifecycle complete WORK-X
./bin/palari lifecycle outcome OUTCOME-X --work-item-id WORK-X --summary "What happened."
```

Accepted human decisions fail closed if:

- the human lacks the required approval capability
- evidence is missing, failed, or stale
- review is missing, not accept-ready, or stale
- the decision head does not match the reviewed head

Completion fails closed unless the queue integration state is `ready`.

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

The GitHub Actions workflow at `.github/workflows/ci.yml` runs the same command
on pushes to `main` and on pull requests.
