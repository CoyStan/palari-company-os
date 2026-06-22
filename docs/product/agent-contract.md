# Agent Contract

Palari Company OS is primarily an operating contract for AI agents. Humans use
the dashboard, receipts, blockers, and approval records to supervise work.
Agents use the CLI to discover one bounded task, receive context, act inside
scope, and stop when human authority is required.

## Canonical Loop

Agent work should start with one packet command:

```bash
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
```

`palari agent start` is currently a read-only alias for `agent brief`. It exists
so future versions can add claim/lease behavior without changing the agent
entry point.

The v1 loop is:

1. Run `palari agent brief WORK-ID --as PALARI-ID --mode execute --json`.
2. Continue only if the packet returns `status: ready`.
3. Read and write only the packet's allowed paths and sources.
4. Stop if the packet is blocked or a stop condition is reached.
5. Produce the required output and trust records.
6. Run `palari agent check WORK-ID --as PALARI-ID --json`.
7. Run `palari validate --json`.
8. Report the packet status, compliance checks, changed files, and remaining blockers.

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

- `palari agent brief WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent start WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent check WORK-ID --as PALARI-ID --json`
- compact ready/blocked packets
- machine-readable packet compliance checks
- deterministic blocker codes
- packet context hash
- direct work, goal, workbench, source, dependency, proof, and integration state

Not implemented yet:

- claim/lease files
- `palari agent finish`
- packet expansion
- review/planning/repair modes
- live connector execution
- memory providers or vector search

`agent check` rebuilds the packet, reports packet blockers, and then evaluates
the current workspace against the completion contract. It returns `ok: false`
when required receipt, evidence, review, human decision, source, dependency, or
external-write checks fail. Light low-risk work may satisfy its trust loop with
a valid receipt without requiring review or human approval.
