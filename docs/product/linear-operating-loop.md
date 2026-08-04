# Linear Operating Loop

Linear can be the human-facing task list while Palari keeps the local task
rules, check results, approvals, and execution records. Linear is optional: the
first-run Palari demo needs no Linear account, API key, OAuth, or hosted
service.

## Connect once

Create a personal API key at <https://linear.app/settings/api>, export it, and
verify the connection. `connect` also prepares the local integration record
with its allowed events and actions. It is safe to run before the key exists:
a missing credential is reported as a structured blocker, not a crash.

```bash
export LINEAR_API_KEY=...
./bin/palari linear connect --json
```

List Linear issues. Each result says whether the description contains a
`palari` block and which local proposal or task it links to:

```bash
./bin/palari linear issues --team ENG --json
```

## Minimal issue loop

Check local readiness:

```bash
./bin/palari linear doctor --json
```

Create a bounded block to paste into the Linear issue description:

```bash
./bin/palari linear block-template \
  --as PALARI-SOFIA \
  --goal GOAL-0001 \
  --risk R1 \
  --intensity light \
  --scope "Tighten onboarding copy without product behavior changes." \
  --acceptance-target "Copy is clearer and tests still pass." \
  --verification ./scripts/verify.sh \
  --json
```

The flags remain `--scope` and `--acceptance-target` for CLI compatibility;
they mean the task's allowed work and its required result.

After pasting the fenced `palari` block into Linear, inspect it:

```bash
./bin/palari linear inspect-block ENG-123 --as PALARI-SOFIA --json
```

Import the issue as a proposed Palari task:

```bash
./bin/palari linear import ENG-123 --as PALARI-SOFIA --json
```

Start only after a human adopts the task:

```bash
./bin/palari linear start ENG-123 \
  --runner codex \
  --as PALARI-SOFIA \
  --adopt-by HUMAN-FOUNDER \
  --json
```

Then use the normal Palari path: task brief, bounded changes, run record,
current check results, independent review when required, and human approval
when required. Linear does not replace any required check or approval.

When Palari has a status worth posting, first create an offline preview:

```bash
./bin/palari linear post-gate ENG-123 \
  --record \
  --event review_requested \
  --actor PALARI-SOFIA \
  --json
```

A human approves and queues that integration plan with the existing
`integration approve` and `integration enqueue` commands. Only then send the
approved comment:

```bash
./bin/palari linear send OUTBOX-ID --by HUMAN-FOUNDER --confirm --json
```

## Approved status updates

The same preview, approval, queue, and send steps can move the Linear issue
itself. Create a status-update preview instead of a comment. The exact Linear
state ID is resolved live only at the send step:

```bash
./bin/palari linear post-gate ENG-123 \
  --record \
  --event work_completed \
  --action update-issue \
  --actor PALARI-SOFIA \
  --json
```

Events map to Linear workflow-state types by default: `work_started` and
`review_requested` map to `started`, while `work_completed` maps to
`completed`. Pass `--to-state "In Review"` to name an exact state.
`work_blocked` always requires an explicit `--to-state`.

After human approval and queueing, the same `linear send` command runs
`issueUpdate` and stores the provider response on the outbox item.

## Publish a local task to Linear

A task created inside Palari, for example with `palari work add`, can be
published to Linear so it appears on the board and phone. `push` creates an
offline `issueCreate` preview. The description includes the task's `palari`
block so a later `inspect-block` and `import` round trip remains valid:

```bash
./bin/palari linear push WORK-0002 --as PALARI-SOFIA --team ENG --record --json
```

After `integration approve` and `integration enqueue`, the same `linear send`
command creates the issue and links it to the task. The exact external links
remain stored in `external_refs`. A pushed issue then behaves like a
Linear-born issue: status updates can move it, and `linear sync` can refresh it.

## Pull updates without webhooks

Refresh linked records from Linear on demand. This makes the same
non-destructive changes as a verified webhook event: it always refreshes
`external_refs`, but changes title and summary only for proposals that have not
been adopted.

```bash
./bin/palari linear sync ENG-123 --json
```

## Local webhook loop

Inbound webhooks are for private local use. Put the webhook secret in the
environment; Palari stores only `env:LINEAR_WEBHOOK_SECRET`.

```bash
export LINEAR_WEBHOOK_SECRET=...
./bin/palari linear webhook serve --host 127.0.0.1 --port 0 --json
```

Expose the printed URL through a tunnel such as ngrok or Cloudflare Tunnel,
then configure Linear to send Issue events to `/linear/webhook`. Palari accepts
only verified Issue events. Duplicate delivery does not change workspace records.

Verify a captured payload without changing workspace records:

```bash
./bin/palari linear webhook verify \
  --payload-file payload.json \
  --signature HEX \
  --timestamp MS \
  --json
```

Inspect local webhook events and linked tasks:

```bash
./bin/palari linear webhook events --limit 20 --json
./bin/palari linear status ENG-123 --json
./bin/palari linear linked --json
```

Linked proposals may receive `external_refs` plus pre-adoption title and
summary updates. Linked tasks receive only `external_refs`. Linear webhook
events cannot change allowed files, sources, or actions; risk; check results;
run records; reviews; or approvals.

## Intentional non-goals

Linear status writes exist only through the approved plan and outbox steps
above. There is no autonomous or unattended write. This feature also does not
add OAuth, Linear label writes, Linear Agent Sessions, background runners,
hosted sync, or provider writes beyond approved Linear comments, status
updates, and issue creation. Palari remains the source of truth for task
permissions, check results, run records, reviews, and approvals.
