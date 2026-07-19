# Public Surface

This map separates Palari's core kernel from optional surfaces. It exists so
new work can stay honest about whether it is strengthening the center or adding
another way to look at it.

## Core Kernel

The governance kernel is the normalized governance case, pure evaluator, and
exact scope/proof/review/authority bindings. The durable product core adds the
workspace schema, replayable journal, trusted transition gates, PCAW protocol,
and local external-effect stop boundary.

CLI commands, packets, read models, hooks, MCP, UIs, and provider adapters
translate those decisions. They do not own a second lifecycle or authority
matrix.

## Current Surface Classes

| Surface | Class | Notes |
| --- | --- | --- |
| Pure governance case and evaluator | core | Authoritative lifecycle, exact proof, independent review, quorum, and acceptance derivation. |
| Workspace schema and validation | core | Local, inspectable source of truth. |
| Governance journal and trusted transitions | core | Replayable history and hard stops for trust-changing mutations. |
| Receipts, evidence, reviews, decisions, acceptance | core | Trust and completion records. |
| Integration plans and outbox | core | Human-approved external-write boundary. |
| Agent packet/check/start/advance/release flow | agent adapter | Primary bounded execution path over the kernel. |
| Queue, detail, state, history | operator | Derived read models and replayable journal checks for humans and agents. |
| PCAW proof export and verification | core | Deterministic, offline proof statements and artifact integrity checks. |
| Lifecycle authoring commands | operator | Explicit local mutations of current proof and authority records. |
| Linear issue/comment/webhook adapter | adapter | Governed adapter behavior; Linear is not Palari's source of truth. |
| Git commit gate | adapter | Optional structural enforcement of the packet path boundary. |
| Claude and Codex session adoption | adapter | Tested project-local session enforcement over the portable contract. |
| MCP stdio | adapter | Bounded protocol translation with explicit capability limits. |
| Opaque provider declarations | core boundary | Provider-neutral previews only; no provider API shape or execution. |
| Mission Control and local serve | visual | Local supervision surface, not core kernel. |
| ACME workspace | example | Repository example only; it is not packaged data, a default workspace, or candidate-test authority. |
| Checkpoint restoration and split collections | parked | Reachable local recovery/read surfaces pending a product decision; neither is core lifecycle authority. |
| Data map, maintainer, gate, and playbook recommendations | parked | Advisory views with no authority or pre-1.0 compatibility promise. |
| Broad generic planning/record authoring | parked | Retained while classification is ambiguous; the ordinary onramp does not depend on it. |

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
