# Public Surface

This map separates Palari's core kernel from optional surfaces. It exists so
new work can stay honest about whether it is strengthening the center or adding
another way to look at it.

## Core Kernel

Palari core kernel = workspace schema + agent packets + boundary checks +
receipts/evidence/review/acceptance + integration outbox.

Those pieces define authority, scope, proof, review, and external-write
boundaries. Everything else should serve that kernel.

## Current Surface Classes

| Surface | Class | Notes |
| --- | --- | --- |
| Workspace schema and validation | core | Local, inspectable source of truth. |
| Transition checks | core | Hard stops for trust-changing mutations. |
| Agent packet/check/start/release flow | core | Bounded AI work contract. |
| Receipts, evidence, reviews, decisions, acceptance | core | Trust and completion records. |
| Integration plans and outbox | core | Human-approved external-write boundary. |
| Queue, detail, state, history | operator | Derived read models and replayable journal checks for humans and agents. |
| PCAW proof export and verification | core | Deterministic, offline proof statements and artifact integrity checks. |
| Authoring commands | operator | Explicit local mutations of workspace records. |
| Linear issue/comment/webhook adapter | adapter | Governed adapter behavior; Linear is not Palari's source of truth. |
| Claude Code hook enforcement | adapter | Structural write-boundary enforcement inside Claude Code sessions. |
| Opaque provider declarations | core boundary | Provider-neutral previews only; no provider API shape or execution. |
| Mission Control and local serve | visual | Local supervision surface, not core kernel. |
| ACME workspace | example | Current local example and packaged starter data. |

## Command Surface

Current CLI command count from parser inspection: **142**.

The default help is intentionally narrow. It leads with `init`, `work`,
`agent`, `queue`, `detail`, `proof`, `validate`, and `docs`, plus this ordinary
journey:

```text
init -> work add -> agent start --next -> agent advance
-> queue --approval-inbox -> proof verify
```

There is no blanket compatibility promise for pre-1.0 commands. Superseded
paths are removed when the current replacement is documented and committed
stored data does not require a migration boundary. In particular, `agent
advance` is the sole current proof-reconciliation command; the older `agent
done` shortcut and the synthetic legacy-workspace `migrate` surface are not
retained. New commands should remain rare and must expose a distinct current
governance primitive.

`superseded` and `abandoned` are explicit non-success dispositions, not aliases
for completion. They leave the default queue, agent candidate list, and Approval
Inbox, while `queue --include-closed` and `detail` preserve their reason and
optional successor for audit. Once recorded, the retired work contract and all
linked proposal, attempt, proof, review, decision, acceptance, outcome, and
external-action records are storage-level immutable; follow-up belongs in
explicit successor work. The retirement transaction itself may change only the
terminal fields and cannot bundle new proof or authority.

## Provider Boundary

Generic integration records keep the provider name opaque. Palari can produce
one provider-neutral external-action preview and bind it through approval and
the outbox, but it does not model Slack, GitHub, Jira, email, or another
provider's API payload. Declaring a provider name does not make it a supported
adapter or enable execution.

Linear is the only current live provider path. It is limited to governed issue
reads/imports, approved comment sends, approved issue status updates, and
approved issue creation from local work items, plus verified Issue webhooks.
Every live write requires a recorded plan, a human approval, and a queued
outbox item first. Palari remains the source of truth for authority, scope,
evidence, receipts, and acceptance.
