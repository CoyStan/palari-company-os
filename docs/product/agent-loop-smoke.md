# Agent Loop Smoke

This is the smallest practical smoke path for an agent using Palari Company OS.
It is meant to prove the loop, not to mutate authority or simulate a human.

The loop is:

1. Find the next safe item.
2. Read one bounded packet.
3. Start ready work to persist the packet and local claim.
4. Check whether the packet contract is satisfied.
5. Ask for final report guidance.
6. Hand off to a human when review or decision authority is required.

## Execute-Mode Smoke

Use the ACME example when testing an agent that is doing work:

```bash
./bin/palari agent next --all
./bin/palari agent next --as PALARI-SOFIA --json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed docs/product/company-os.md --json
./bin/palari agent finish WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent doctor WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent loop WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent release WORK-0003 --as PALARI-SOFIA --json
```

Expected result:

- `agent next` points Sofia at the next active proof step.
- `agent brief` returns a compact packet with allowed sources, paths, stop
  conditions, and completion requirements.
- `agent start` persists that packet and writes a local claim for ready work.
- `agent check` reports whether receipt, evidence, review, or human decision
  records are still missing.
- `agent check --changed` reports whether observed edits are inside the packet
  write boundary and represented by current attempt or receipt records.
- `agent finish` tells the agent whether it may claim completion or must keep
  preparing proof or hand off to a human.
- `agent doctor` explains the current safety state in plainer language.
- `agent loop` summarizes the same read-only sequence and points to the detailed
  stage commands without dumping every payload.
- `agent release` removes the local claim when the smoke is complete.

Do not treat a ready packet as completion. Completion is only credible after
`agent check` and `agent finish` agree that the required trust records are
present.

## Review-Handoff Smoke

Use the dogfood workspace when testing a reviewer or supervisor handoff:

```bash
./bin/palari --workspace workspaces/palari-company-os agent next --all --mode review
./bin/palari --workspace workspaces/palari-company-os agent brief WORK-REPO-0003 --as PALARI-STEWARD --mode review --json
./bin/palari --workspace workspaces/palari-company-os agent check WORK-REPO-0003 --as PALARI-STEWARD --mode review --json
./bin/palari --workspace workspaces/palari-company-os agent finish WORK-REPO-0003 --as PALARI-STEWARD --mode review --json
./bin/palari --workspace workspaces/palari-company-os agent handoff WORK-REPO-0003 --as PALARI-STEWARD --json
./bin/palari --workspace workspaces/palari-company-os agent doctor WORK-REPO-0003 --as PALARI-STEWARD --mode review --json
./bin/palari --workspace workspaces/palari-company-os agent loop WORK-REPO-0003 --as PALARI-STEWARD --mode review --json
```

Expected result:

- Review-mode packets are read-only.
- `agent finish` means the agent can report a review recommendation.
- `agent handoff` packages the human review or decision context without
  recording the human action.
- If the payload includes `human_action_boundary`, commands under
  `human_action_commands` are for a human supervisor only. An agent may quote
  or summarize them, but must not run them.

## Dashboard Visibility

Generate the dashboard when you need a human-facing snapshot of the same
handoff state:

```bash
./bin/palari --workspace workspaces/palari-company-os dashboard --out /tmp/palari-company-dashboard-smoke
```

The dashboard should show agent-safe handoff bridges separately from human-only
review or decision actions.

## Done Means

An agent may report done only when:

- the packet is ready or its blockers are clearly reported
- `agent check` and `agent finish` have been read
- required receipt, evidence, review, and human-decision records are present or
  the missing records are explicitly listed
- human-only commands remain human-only
- ready execution work was started before completion was checked
- no external provider call, secret read, deployment, or live write was made

## Do Not

- Do not run human review or decision commands as an agent.
- Do not use unlisted sources or paths.
- Do not claim external writes from dry-run integration plans or outbox records.
- Do not deploy or call live providers from this smoke.
