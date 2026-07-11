# Linear Operating Loop

Linear can be the human-facing work surface while Palari remains the local
governance and runtime layer. This loop is optional; the first-run Palari demo
does not require Linear, API keys, OAuth, or a hosted service.

## Connect Once

Create a personal API key at <https://linear.app/settings/api>, export it, and
verify the connection. `connect` also prepares the local integration record
(allowed events and actions), so it is safe to run before the key exists — it
reports the missing credential as a structured blocker instead of failing.

```bash
export LINEAR_API_KEY=...
./bin/palari linear connect --json
```

Discover work directly from Linear. Each issue is annotated with whether it
carries a `palari` block and which local proposal or work item it links to:

```bash
./bin/palari linear issues --team ENG --json
```

## Minimal Issue Loop

Check local readiness:

```bash
./bin/palari linear doctor --json
```

Create a governed block to paste into the Linear issue description:

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

After pasting the fenced `palari` block into Linear, inspect it:

```bash
./bin/palari linear inspect-block ENG-123 --as PALARI-SOFIA --json
```

Import the issue as a Palari proposal:

```bash
./bin/palari linear import ENG-123 --as PALARI-SOFIA --json
```

Start only after a human adopts the work:

```bash
./bin/palari linear start ENG-123 \
  --runner codex \
  --as PALARI-SOFIA \
  --adopt-by HUMAN-FOUNDER \
  --json
```

Then use the normal Palari work loop: agent packet, bounded changes, evidence,
review, receipts, and acceptance. Linear does not replace those gates.

When Palari has a status worth posting back, plan the comment first:

```bash
./bin/palari linear post-gate ENG-123 \
  --record \
  --event review_requested \
  --actor PALARI-SOFIA \
  --json
```

A human approves and enqueues the integration plan with the existing
`integration approve` and `integration enqueue` commands. Only then send the
approved comment:

```bash
./bin/palari linear send OUTBOX-ID --by HUMAN-FOUNDER --confirm --json
```

## Governed Status Write-Back

The same plan/approve/enqueue/send gates can move the Linear issue itself.
Plan a status update instead of a comment (plans are offline previews; the
concrete Linear state id is resolved live at send time):

```bash
./bin/palari linear post-gate ENG-123 \
  --record \
  --event work_completed \
  --action update-issue \
  --actor PALARI-SOFIA \
  --json
```

Events map to workflow state types by default (`work_started` and
`review_requested` -> started, `work_completed` -> completed). Pass
`--to-state "In Review"` to target an exact state name; `work_blocked` always
requires an explicit `--to-state`. After human approval and enqueue, the same
`linear send` command executes the state change through `issueUpdate` and
records the provider response on the outbox item.

## Publish Local Work To Linear

Work items born inside Palari (for example from `palari work add` during an
agent session) can be published to Linear so every ticket is visible on the
board and on your phone, wherever it was born. `push` plans a governed
`issueCreate`; the description embeds the work item's `palari` block so the
round trip through `inspect-block` and `import` stays valid:

```bash
./bin/palari linear push WORK-0002 --as PALARI-SOFIA --team ENG --record --json
```

After the usual `integration approve` and `integration enqueue`, the same
`linear send` command creates the issue and links it back to the work item
(external refs are stored in the same write). From then on the pushed issue
behaves exactly like a Linear-born one: status write-back moves it and
`linear sync` refreshes it.

## Pull Sync Without Webhooks

Refresh linked records from Linear on demand — the same non-destructive
updates as a verified webhook event (external refs always; title/summary only
for pre-adoption proposals):

```bash
./bin/palari linear sync ENG-123 --json
```

## Webhook Dogfood Loop

Inbound webhooks are for private local dogfooding. Set the webhook secret in the
environment; Palari records only `env:LINEAR_WEBHOOK_SECRET`.

```bash
export LINEAR_WEBHOOK_SECRET=...
./bin/palari linear webhook serve --host 127.0.0.1 --port 0 --json
```

Expose the printed webhook URL through a tunnel such as ngrok or Cloudflare
Tunnel, and configure Linear to send Issue events to the `/linear/webhook` path.
Palari accepts only verified Issue events. Duplicate deliveries do not mutate
the workspace.

Verify a captured payload without mutating the workspace:

```bash
./bin/palari linear webhook verify \
  --payload-file payload.json \
  --signature HEX \
  --timestamp MS \
  --json
```

Inspect local webhook events and linked work:

```bash
./bin/palari linear webhook events --limit 20 --json
./bin/palari linear status ENG-123 --json
./bin/palari linear linked --json
```

Linked proposals may receive external refs and pre-adoption title/summary
updates. Linked work receives external refs only. Linear webhook events do not
rewrite scope, risk, evidence, review, receipts, or acceptance.

## Intentional Non-Goals

Linear status writes exist only through the approved plan/outbox path above —
there is no autonomous or unattended write. Beyond that, this slice does not
add OAuth, Linear label writes, Linear Agent Sessions, background runners,
hosted sync, or provider writes beyond already-approved Linear comments and
status updates. Palari remains the source of truth for authority, scope,
evidence, receipts, and acceptance.
