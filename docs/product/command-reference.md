# Command Reference

Most commands are read-only. Workspace initialization, authoring, and lifecycle
commands intentionally write to `workspace.json` after validation. No command
merges, pushes, deploys, activates policy, executes broker side effects, uses
secrets, or bypasses human authority.

## Workspace Init

```bash
./bin/palari workspace init workspaces/new-company --name "New Company"
./bin/palari workspace init workspaces/new-company --name "New Company" --json
```

Creates a blank, single-file `workspace.json` with the current schema version
and all known collections present. The command validates the file before
writing success output and refuses to overwrite an existing workspace. It does
not create humans, Palaris, goals, authority records, receipts, or external
connections by itself.

## Queue

```bash
./bin/palari queue
./bin/palari queue --json
```

Shows the operator queue with attention state, `next_step_type`, goal, Palari,
owner, adaptive intensity, evidence state, review state, receipt state,
approval progress, integration state, learning signal, workbench context,
active attempts, coordination warnings, and next action. `next_step_type`
classifies intent for humans and agents without requiring them to parse the
command string.

## Detail

```bash
./bin/palari detail WORK-0001
./bin/palari detail WORK-0001 --json
```

Assembles one work item with its workbench, goal, Palari, parent/child work
items, dependencies, allowed sources, attempt, receipt, evidence, review,
linked decisions, human decisions, outcome, active parallel attempts,
coordination warnings, safety state, `next_step_type`, and next action. Active
work that is missing proof points `next_commands` toward `agent check` and
`agent finish` before review or human decision steps.

## State

```bash
./bin/palari state
./bin/palari state --json
```

Shows a compact operator state: record counts, attention counts, top attention
with its `next_step_type` and next command, queue items, active parallel work,
and coordination warnings. This is the first fast read model for the whole
workspace.

## Validate

```bash
./bin/palari validate
./bin/palari validate --json
```

Validates the workspace source of truth. It fails closed when schema version,
record shape, unknown fields, lifecycle values, references, evidence freshness,
review freshness, human approval capability, or completion quorum are invalid.
If `workspace.json` declares `collection_files`, validate reads and merges those
workspace-relative collection files before running the same checks.

## Scope

```bash
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json
./bin/palari scope WORK-0001 --changed secrets.env --action deploy
```

Checks paths and actions against a work item's declared allowed resources and
forbidden actions.

## Review Guide

```bash
./bin/palari review guide WORK-0001
./bin/palari review guide WORK-0001 --json
./bin/palari review record REVIEW-0001 --work-item-id WORK-0001 --reviewed-head HEAD --reviewer HUMAN-MAINTAINER --verdict accept-ready
```

`review guide` is read-only. It assembles the selected work item, workbench,
Palari, attempt, evidence, receipt, changed files, suggested review focus,
advisory reviewer candidates from the workbench humans, possible verdicts, and
a neutral review-record command template. Each reviewer candidate also includes
a ready-to-edit `review record` command with `VERDICT` and `REVIEW-ID`
placeholders. It does not record a review verdict, approve work, mutate
history, or replace human judgment.

`review record` is the explicit write path for a review verdict. Use it only
after inspecting the evidence and receipt.

## Decision Guide

```bash
./bin/palari decision guide DECISION-0001
./bin/palari decision guide WORK-0002 --json
./bin/palari decision update DECISION-0001 --status decided --set "result=Use option A"
```

`decision guide` is read-only. It assembles one decision, its linked work item,
required human, options, tradeoffs, recommendation, safe default, and a neutral
decision-update command template. It also includes ready-to-edit update commands
for each suggested result, such as the safe default or `defer`. It does not
decide, approve, mutate history, or authorize implementation. If the target is a
work item id, Palari resolves the open decision linked to that work item.

## Agent Packets

```bash
./bin/palari agent next --json
./bin/palari agent next --all --json
./bin/palari agent next --as PALARI-SOFIA --json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent finish WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent handoff WORK-0003 --as PALARI-SOFIA --json
```

`agent next` reads the current open queue for one Palari, ranks safe-to-start
candidates first, and includes blocked/waiting candidates with blocker codes.
Closed work remains visible through `queue` and `detail`, but is omitted from
agent candidate lists.
With no `--as` argument, `agent next` defaults to an operator rollup across
every Palari in the workspace. `--all` is still accepted as the explicit form.
The rollup includes a `top_candidate` field so agents can follow the first safe
or blocking next step without scanning every nested candidate. Candidates include
`next_step_type`, such as `start-work`, `check-active-proof`,
`human-decision`, or `review-handoff`, so tools do not have to infer intent from
the command string alone. Active work that already has an attempt and needs
proof points to `agent check` / `agent finish` instead of re-starting with
another brief. It is read-only and does not claim or assign work.

`agent brief` compiles one bounded, context-window-safe packet for an AI agent.
The packet is read-only in v1 and returns either `status: ready` or
`status: blocked`.
`agent start` is currently an alias for `agent brief`; future versions may add
claim/lease behavior to `start`.

The packet includes the acting Palari, work objective, goal/workbench context,
allowed paths, allowed sources, forbidden actions, required output, completion
contract, proof/integration state, stop conditions, blockers, and safe next
commands. Agents should treat this packet as their working boundary.

`agent check` rebuilds the current packet and verifies whether the workspace
state satisfies the packet's completion contract. It returns `ok`, packet id,
packet context hash, packet blockers, structured pass/fail/warn checks, and
`next_step_type` plus next safe commands. A ready-to-start packet can still
produce `ok: false` when the attempt is missing required receipt, evidence,
review, or human-decision records. Missing receipt and evidence checks include
concrete record-command templates for the current work item and attempt when
possible, and failed required check commands appear before generic
inspect/validate commands. Light low-risk receipt-ready work can satisfy the
receipt requirement without forcing review or human approval.

`agent finish` is a read-only final-report helper. It wraps `agent check` and
returns whether the agent may claim completion, whether the work should be
handed off to a human, `next_step_type`, missing requirements, completed
requirements, blockers, and report guidance. Handoff-ready receipt work points
to the review guide as the next human-facing command; missing approval points to
a human-decision record template when evidence and review are known. Missing
proof or approval templates appear before generic inspect/validate commands. It
does not close work, record receipts, mutate history, or perform external
actions.

`agent handoff` is read-only and meant for the moment after `agent finish`
identifies a human review or decision step. It returns the compact finish
summary plus relevant review-guide or decision-guide context, separates
agent-safe read commands from human action commands, and does not mutate the
workspace.

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
work item with Palari's state-based suggestions. It also prints a short
operating guidance section with practical one-sentence advice for the next agent
run. External playbooks are guidance only; Palari still owns goals, scope,
sources, authority, receipts, evidence, review, human decisions, and outcomes.

## Integrations

```bash
./bin/palari integrations
./bin/palari integrations --json
./bin/palari integration check INT-SLACK-OPS
./bin/palari integration check INT-SLACK-OPS --json
./bin/palari integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify
./bin/palari integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --json
./bin/palari integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --record --id PLAN-X
./bin/palari integration approve PLAN-X --by HUMAN-FOUNDER
./bin/palari integration reject PLAN-X --by HUMAN-FOUNDER --reason "wrong audience"
./bin/palari integration cancel PLAN-X --by HUMAN-FOUNDER --reason "no longer needed"
./bin/palari integration enqueue PLAN-X --by HUMAN-FOUNDER
./bin/palari integration outbox-cancel OUTBOX-X --by HUMAN-FOUNDER --reason "no longer needed"
```

Integrations declare possible external providers and boundaries before Palari
can ever use them. The v0 implementation is dry-run only: it validates provider,
owner, event, action, source, risk, and secret-reference metadata, then produces
a payload preview without reading secrets or calling Slack, GitHub, Jira, email,
or any other provider.

`secret_ref` values must be references such as `env:PALARI_SLACK_WEBHOOK_URL`.
Raw tokens or keys fail validation. Planning also fails closed when an
integration is disabled, when a requested event/action is not allowed, or when
the provider does not support the requested action.

By default, `integration plan` is a preview and does not write workspace state.
Use `--record` when the dry-run payload should become a reviewable integration
plan. Recorded plans are stored in `integration_plans`, appended to history,
shown in `queue` and `detail`, and still do not perform live provider calls.
Recorded plans start as `pending-approval`. A qualified human can approve,
reject, or cancel the plan; each decision updates the plan state and appends
history. Approval is still custody only: Palari records that the dry-run plan
is allowed for future execution wiring, but this v0 CLI still makes no provider
call and reads no secret value.

Approved plans can be placed into `integration_outbox` with `integration
enqueue`. The outbox is the explicit future-execution boundary: it preserves the
approved payload preview, source boundary, risk, and enqueuing human, but still
does not call providers or read secrets. Pending, rejected, canceled, or already
enqueued plans fail closed. Queued outbox items can be canceled by a qualified
human with `integration outbox-cancel`; cancellation is recorded in history,
keeps the dry-run boundary intact, and still performs no provider call.

## Receipt-Ready Low-Risk Work

For light R1/R2 local work, a completed attempt plus a valid receipt can move
the queue to `receipt-ready` without requiring full evidence, independent
review, and human-decision ceremony. That state is deliberately human-facing:
review the output, undo it if needed, or continue. R3/R4/R5 work and receipts
that claim actual external writes still require the stricter governance path. A
receipt may reference `planned_external_writes` only by approved integration
plan id, or `queued_external_writes` by integration outbox id, without claiming
that anything was sent or changed externally. `queued_external_writes` must
reference currently queued outbox items; canceled outbox items fail closed so a
receipt cannot imply a canceled write is still waiting to execute.

## History

```bash
./bin/palari history
./bin/palari history --limit 10 --json
```

Shows recent append-only audit events from `.palari/history.jsonl` beside the
workspace file. Mutating authoring and lifecycle commands append events only
after the workspace write validates and succeeds. Failed mutations do not append
success events.

## Receipts

```bash
./bin/palari receipt record RECEIPT-X \
  --work-item-id WORK-X \
  --attempt-id ATTEMPT-X \
  --actor PALARI-X \
  --list sources_used=SOURCE-X \
  --list outputs_created=notes/summary.md \
  --list queued_external_writes=OUTBOX-X
```

Receipts are human-facing trust records. `queued_external_writes` points to an
approved integration plan that has been placed in the outbox, not to a live
provider call. Use it when a human needs to see that an external write is queued
at the future execution boundary and can still be canceled or reviewed.

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
```

`desktop-prototype` generates static read-only HTML, CSS, and JavaScript from
`examples/desktop-demo/workspace.json`.

`desktop-serve` generates the same files and serves them locally for design
review. It does not expose external runner endpoints, connect Google Drive, or
mutate the workspace model.

## Migration

```bash
./bin/palari migrate
./bin/palari migrate --write
```

Adds `schema_version: 1` to legacy unversioned workspaces and ensures required
collections exist. Without `--write`, it previews changes.

## Authoring Commands

All authoring commands validate the full workspace before writing.
For now, authoring and lifecycle write commands support single-file workspaces
only. If a workspace declares non-empty `collection_files`, write commands fail
closed instead of rewriting `workspace.json` and risking data loss in split
collection files.

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

## Verification

```bash
./scripts/verify.sh
```

Runs unit tests, Python compilation, JSON validity checks, and CLI smoke checks
for queue, detail, state, validate, scope, maintainer status, playbooks,
dashboard generation, and the desktop prototype generator.

The GitHub Actions workflow at `.github/workflows/ci.yml` runs the same command
on pushes to `main` and on pull requests.
