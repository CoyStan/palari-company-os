# Linear Operating Loop

Linear can be the human-facing work surface while Palari remains the local
governance and runtime layer. This loop is optional; the first-run Palari demo
does not require Linear, API keys, OAuth, or a hosted service.

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

This slice does not add OAuth, Linear status writes, Linear label writes,
Linear Agent Sessions, background runners, hosted sync, or provider writes
beyond already-approved Linear comments. Palari remains the source of truth for
authority, scope, evidence, receipts, and acceptance.
