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
| Queue, detail, state, history | operator | Derived read models for humans and agents. |
| Authoring and lifecycle commands | operator | Explicit local mutations of workspace records. |
| Linear issue/comment/webhook adapter | adapter | Governed adapter behavior; Linear is not Palari's source of truth. |
| Claude Code hook enforcement | adapter | Structural write-boundary enforcement inside Claude Code sessions. |
| Slack/GitHub/Jira/email providers | future | Dry-run planning only; no live provider execution. |
| Dashboard and local serve | visual | Visual supervision surface, not core kernel. |
| Desktop prototype and desktop serve | visual | Product prototype surface, not core kernel. |
| ACME and desktop demo workspaces | example | Fixtures and examples for local use. |
| AI Work Vignettes | example | Optional narrative examples. |
| Archived plans and research | archive | Historical context, not active operator guidance. |

## Command Surface

Current CLI command count from parser inspection: **139**.

The command surface is intentionally broad because Palari exposes primitive
record operations directly. New commands should be rare. Prefer docs, examples,
or an existing command shape unless the command exposes a core governance
primitive or removes repeated operator confusion.

## Provider Boundary

Slack, GitHub, Jira, and email are dry-run planning providers only. They may
produce reviewable payload previews and approved outbox records, but this CLI
does not execute live provider calls for them.

Linear is the only current live provider path. It is limited to governed issue
reads/imports, approved comment sends, and verified Issue webhooks. Palari
remains the source of truth for authority, scope, evidence, receipts, and
acceptance.
