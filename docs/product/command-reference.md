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
intensity, evidence state, review state, receipt state, approval progress,
integration state, learning signal, and next action.

## Detail

```bash
./bin/palari detail WORK-0001
./bin/palari detail WORK-0001 --json
```

Assembles one work item with its goal, Palari, allowed sources, attempt,
receipt, evidence, review, linked decisions, human decisions, outcome, safety
state, and next action.

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

Validates the workspace source of truth. It fails closed when schema version,
record shape, unknown fields, lifecycle values, references, evidence freshness,
review freshness, human approval capability, or completion quorum are invalid.

## Scope

```bash
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json
./bin/palari scope WORK-0001 --changed secrets.env --action deploy
```

Checks paths and actions against a work item's declared allowed resources and
forbidden actions.

## Playbooks

```bash
./bin/palari playbooks sources
./bin/palari playbooks sources --json
./bin/palari playbooks recommend WORK-0003
./bin/palari playbooks recommend WORK-0003 --json
./bin/palari playbook-source create superpowers \
  --label "Superpowers skills" \
  --provider github \
  --uri https://github.com/obra/Superpowers \
  --ref main \
  --license MIT \
  --list included_playbooks=brainstorming,writing-plans,verification-before-completion
```

`playbooks sources` lists external playbook sources and the allowed skills from
each source. `playbooks recommend` combines user-selected playbooks from the
work item with Palari's state-based suggestions. External playbooks are
guidance only; Palari still owns goals, scope, sources, authority, receipts,
evidence, review, human decisions, and outcomes.

## Receipt-Ready Low-Risk Work

For light R1/R2 local work, a completed attempt plus a valid receipt can move
the queue to `receipt-ready` without requiring full evidence, independent
review, and human-decision ceremony. That state is deliberately human-facing:
review the output, undo it if needed, or continue. R3/R4/R5 work and receipts
that claim external writes still require the stricter governance path.

## History

```bash
./bin/palari history
./bin/palari history --limit 10 --json
```

Shows recent append-only audit events from `.palari/history.jsonl` beside the
workspace file. Mutating authoring and lifecycle commands append events only
after the workspace write validates and succeeds. Failed mutations do not append
success events.

## Dashboard

```bash
./bin/palari dashboard --out /tmp/palari-company-dashboard
./bin/palari --workspace workspaces/palari-company-os dashboard --out /tmp/palari-dogfood-dashboard --json
```

Generates a static read-only dashboard with local `index.html`, `styles.css`,
and `app.js` files. The dashboard reads `workspace.json` and
`.palari/history.jsonl`; it does not mutate the workspace, run broker actions,
connect external providers, or require a web server.

The first dashboard has five sections:

- Queue: attention counts, work cards, trust/evidence/review state, next action
- Work: lifecycle lanes and expandable work detail
- Trust: selected sources and human-facing receipts
- History: append-only event timeline
- Authority: humans, Palaris, open decisions, and human blockers

## Desktop Prototype

```bash
./bin/palari desktop-prototype --out /tmp/palari-desktop-prototype
./bin/palari desktop-serve --out /tmp/palari-desktop-prototype
./bin/palari desktop-serve --out /tmp/palari-desktop-prototype --allow-npx
./bin/palari desktop-serve --out /tmp/palari-desktop-prototype --allow-kilo-execute
./scripts/run_desktop_kilo_app.sh
```

`desktop-prototype` generates static read-only HTML, CSS, and JavaScript from
`examples/desktop-demo/workspace.json`.

`desktop-serve` generates the same files and serves them with local API
endpoints:

- `GET /api/kilo/status`
- `POST /api/kilo/run`

The browser can preview a bounded Kilo prompt for the selected desktop work
item. Real Kilo execution remains disabled unless the server is started with
`--allow-kilo-execute`. The server does not add `--auto`, bypass Kilo
permissions, connect Google Drive, or mutate the workspace model.

The Kilo endpoints are preserved as an archived optional runner spike. They are
not the current primary product path.

`scripts/run_desktop_kilo_app.sh` is the convenience wrapper for this app path.
It starts `desktop-serve` from the repo root. Useful environment flags:

- `PALARI_DESKTOP_OUT=/tmp/path`
- `PALARI_DESKTOP_PORT=0`
- `PALARI_KILO_ALLOW_NPX=1`
- `PALARI_KILO_ALLOW_EXECUTE=1`
- `PALARI_KILO_MODEL=provider/model`
- `PALARI_KILO_AGENT=name`
- `PALARI_KILO_TIMEOUT=120`

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

./bin/palari source create SOURCE-X --label "Launch note" --kind note --provider local_note --uri notes/launch.md --set selected=true --list allowed_palaris=PALARI-X
./bin/palari source update SOURCE-X --set last_read_at=2026-06-19T04:00:00Z

./bin/palari decision create DECISION-X --question "Which option should we choose?"
./bin/palari decision update DECISION-X --status decided --set "result=Use option A"

./bin/palari work create WORK-X --title "Draft note" --goal GOAL-X --palari PALARI-X
./bin/palari work update WORK-X --set current_attempt=ATTEMPT-X --list allowed_sources=SOURCE-X --list allowed_actions=local_write

./bin/palari attempt record ATTEMPT-X --work-item-id WORK-X --actor PALARI-X
./bin/palari receipt record RECEIPT-X --work-item-id WORK-X --attempt-id ATTEMPT-X --actor PALARI-X --list sources_used=SOURCE-X --list outputs_created=notes/summary.md
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

## Kilo Code

Status: archived optional runner spike. Keep these commands for deliberate
runner experiments, but do not treat Kilo as the default Palari Company OS
execution path.

```bash
./bin/palari kilo status
./bin/palari kilo status --allow-npx --json
./bin/palari kilo run WORK-0001 --message "Start this bounded work"
./bin/palari kilo run WORK-0001 --message "Start this bounded work" --execute
```

Builds a Kilo Code prompt from one Palari work item and the current workspace
boundary. The prompt includes the work item, goal, Palari, allowed resources,
selected sources, allowed actions, output targets, forbidden actions, queue
attention, next action, and human approval state.

Preview mode is the default. `--execute` is required before the command calls
`kilo run`. Palari does not add `--auto` or bypass Kilo permissions. Kilo
credentials, models, sessions, and provider setup stay in the user's Kilo
environment.

Kilo resolution order:

1. `PALARI_KILO_BIN`
2. `kilo` on `PATH`
3. `kilocode` on `PATH`
4. `npx --yes @kilocode/cli` only when `--allow-npx` is passed

## Verification

```bash
./scripts/verify.sh
```

Runs unit tests, Python compilation, JSON validity checks, and CLI smoke checks
for queue, detail, state, validate, scope, maintainer status, and the Kilo
preview bridge.

The GitHub Actions workflow at `.github/workflows/ci.yml` runs the same command
on pushes to `main` and on pull requests.
