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
| Authoring and lifecycle commands | operator | Explicit local mutations of workspace records. |
| Linear issue/comment/webhook adapter | adapter | Governed adapter behavior; Linear is not Palari's source of truth. |
| Claude Code hook enforcement | adapter | Structural write-boundary enforcement inside Claude Code sessions. |
| Slack/GitHub/Jira/email providers | future | Dry-run planning only; no live provider execution. |
| Mission Control and local serve | visual | Local supervision surface, not core kernel. |
| Desktop prototype and desktop serve | visual | Product prototype surface, not core kernel. |
| ACME and desktop demo workspaces | example | Fixtures and examples for local use. |
| AI Work Vignettes | example | Optional narrative examples. |
| Archived plans and research | archive | Historical context, not active operator guidance. |

## Command Surface

Current CLI command count from parser inspection: **154**.

The default help is intentionally narrow. It leads with `init`, `work`,
`agent`, `queue`, `detail`, `proof`, `validate`, and `docs`, plus this ordinary
journey:

```text
init -> work add -> agent start --next -> agent advance
-> queue --approval-inbox -> proof verify
```

All 154 prior command paths remain parseable for compatibility and expert
recovery. The existing `init` action also installs the portable agent contract
and strongest honestly supported local host profile when `--host` is explicit,
so universal adoption does not add another permanent command. The broad
primitive surface is therefore secondary without being removed or silently
deprecated. New commands should remain rare. Prefer an existing command shape
unless a new command exposes a core governance primitive or removes repeated
operator confusion.

`superseded` and `abandoned` are explicit non-success dispositions, not aliases
for completion. They leave the default queue, agent candidate list, and Approval
Inbox, while `queue --include-closed` and `detail` preserve their reason and
optional successor for audit.

The bounded implementation evidence is tracked in the
[Invisible Product Surface v1 Completion Contract](invisible-product-surface-contract.md).

## Provider Boundary

Slack, GitHub, Jira, and email are dry-run planning providers only. They may
produce reviewable payload previews and approved outbox records, but this CLI
does not execute live provider calls for them.

Linear is the only current live provider path. It is limited to governed issue
reads/imports, approved comment sends, approved issue status updates, and
approved issue creation from local work items, plus verified Issue webhooks.
Every live write requires a recorded plan, a human approval, and a queued
outbox item first. Palari remains the source of truth for authority, scope,
evidence, receipts, and acceptance.
