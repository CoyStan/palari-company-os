# Agent Contract

Palari Company OS is primarily an operating contract for AI agents. Humans use
the dashboard, receipts, blockers, and approval records to supervise work.
Agents use the CLI to discover one bounded task, receive context, act inside
scope, and stop when human authority is required.

## Canonical Loop

Agent work should start with one packet command:

```bash
palari agent next --as PALARI-ID --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
```

`palari agent start` is currently a read-only alias for `agent brief`. It exists
so future versions can add claim/lease behavior without changing the agent
entry point.

The v1 loop is:

1. Run `palari agent next --as PALARI-ID --json` to discover safe candidates.
2. Run `palari agent brief WORK-ID --as PALARI-ID --mode execute --json`.
3. Continue only if the packet returns `status: ready`.
4. Read and write only the packet's allowed paths and sources.
5. Stop if the packet is blocked or a stop condition is reached.
6. Produce the required output and trust records.
7. Run `palari agent check WORK-ID --as PALARI-ID --json`.
8. Run `palari agent finish WORK-ID --as PALARI-ID --json`.
9. If the result is a human review or decision handoff, run
   `palari agent handoff WORK-ID --as PALARI-ID --json`.
10. Run `palari validate --json`.
11. Report the packet status, finish guidance, changed files, checks, and blockers.

## Packet Purpose

The packet is a compact context compiler. It prevents agents from inferring a
workflow from many separate commands. A packet answers:

- who the agent is
- which work item is in scope
- why the work matters
- which paths, sources, and actions are allowed
- which actions are forbidden
- what output is required
- what receipt, evidence, review, human decision, or integration state matters
- when the agent must stop
- which commands are safe to run next

The packet must not dump the whole workspace. It includes only directly related
records and explicit omitted-context notes.

## Packet Status

`status: ready` means the agent may proceed inside the packet boundary.

`status: blocked` means the agent must not perform the work. It may run only the
commands listed in `next_allowed_commands`, or report the blockers to a human.

Common blocker codes include:

- `MISSING_PALARI`
- `MISSING_WORK_ITEM`
- `PALARI_NOT_ASSIGNED`
- `DEPENDENCY_NOT_TERMINAL`
- `SOURCE_MISSING`
- `SOURCE_NOT_ALLOWED`
- `EXTERNAL_WRITE_REQUIRES_APPROVAL`
- `HUMAN_DECISION_REQUIRED`
- `WORK_BLOCKED`
- `WORK_CLOSED`
- `INTEGRATION_BOUNDARY`
- `REVIEW_REQUIRED`
- `RECEIPT_READY_REVIEW`

## Boundaries

Agents must never:

- read secrets or raw provider tokens
- read or write outside `allowed_paths`
- use sources not listed in `allowed_sources`
- perform external writes without an approved integration plan and queued
  outbox state
- create durable memory without a future approved memory contract
- treat an informal source as policy
- bypass human decisions, review, receipts, evidence, or approval boundaries

## V1 Scope

Agent Packet Contract v1 is intentionally read-only.

Implemented:

- `palari agent next --json`
- `palari agent next --all --json`
- `palari agent next --as PALARI-ID --json`
- `palari agent brief WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent start WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent check WORK-ID --as PALARI-ID --json`
- `palari agent finish WORK-ID --as PALARI-ID --json`
- `palari agent handoff WORK-ID --as PALARI-ID --json`
- compact Palari-specific work candidate discovery
- compact ready/blocked packets
- machine-readable packet compliance checks
- read-only completion report guidance
- read-only human handoff packets
- deterministic blocker codes
- packet context hash
- direct work, goal, workbench, source, dependency, proof, and integration state

Not implemented yet:

- claim/lease files
- packet expansion
- review/planning/repair modes
- live connector execution
- memory providers or vector search

`agent check` rebuilds the packet, reports packet blockers, carries the current
`next_step_type`, and then evaluates the current workspace against the
completion contract. It returns `ok: false` when required receipt, evidence,
review, human decision, source, dependency, or external-write checks fail. Light
low-risk work may satisfy its trust loop with a valid receipt without requiring
review or human approval. Missing receipt and evidence checks include
record-command templates for the current work item and attempt when Palari can
infer them, and failed required check commands are listed before generic
inspect/validate commands.

Bare `agent next` returns the all-Palaris rollup. `agent next --as PALARI-ID`
reads the current queue for one Palari, puts safe-to-start candidates first,
keeps blocked or waiting visible with blocker codes, and omits closed work from
candidate lists. Waiting candidates include `handoff_guidance` when the next
safe action is a human review or decision guide. It does not create a claim,
mutate state, or assign work.

`agent finish` wraps `agent check` into final-report guidance. It never mutates
workspace state in v1. It carries the same `next_step_type`, distinguishes
missing proof from handoff-ready work, such as low-risk receipt-ready results
that should stop execution and move to a human review path. Its
`next_allowed_commands` prioritize missing proof or approval record templates
before generic inspect/validate commands.

When the next step is a human handoff, `agent finish` also returns
`handoff_guidance`. Review handoffs point to `review guide`, which includes
ready-to-edit review record commands. Decision handoffs point to `decision
guide`, which includes suggested decision update commands. The agent still does
not record those human actions itself.

`agent handoff` compiles the final handoff packet for that moment. It wraps the
`agent finish` result and includes compact `review guide` or `decision guide`
context when applicable. Agent-safe read commands remain separate from
`human_action_commands`, so a model can show the right review or decision
commands without pretending it is authorized to perform them. It is read-only in
v1 and does not create reviews, decisions, receipts, evidence, claims, or
history events.
