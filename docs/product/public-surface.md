# Product Surface

This map separates Palari's central rules and checks from optional features. It
helps maintainers tell whether new work strengthens the product or adds another
way to look at the same information.

## Central rules and checks

One pure evaluator decides task status from normalized workspace records. It
checks allowed files, sources, and actions; current run records and check
results; independent review; required approvals; and completion. The durable
center also includes the workspace schema, tamper-evident history, guarded state
changes, the PCAW protocol, and the stop before an unapproved external action.

CLI commands, task briefs, status views, hooks, MCP, UIs, and provider adapters
translate those decisions. They do not own a second work process or approval
matrix.

## Current surface classes

| Surface | Class | Notes |
| --- | --- | --- |
| Pure evaluator and normalized task data | core | Decides status from exact checks, independent review, required approvals, and current approval records. |
| Workspace schema and validation | core | Local, inspectable source of truth. |
| Tamper-evident history and guarded state changes | core | Replayable history and hard stops for changes that affect trust. |
| Run records, check results, reviews, approvals, and results | core | Records needed to trust and complete a task. |
| Integration plans and outbox | core | Human-approved external-write boundary. |
| Agent home | agent adapter | Read-only Goals, Team, Work, Checks, and Limits view over current workspace facts; grants no permission. |
| Agent brief/check/start/advance/release flow | agent adapter | Primary bounded execution path over the central rules. Stored files retain the technical name `packet`. |
| Queue, detail, state | operator | Recorded status views for ordinary orientation; they do not recheck output bytes or all history. |
| History audit | operator | Explicit replay, continuity, and recovery inspection; not an ordinary status dependency. |
| PCAW export and verification | core | Deterministic, offline statements and output-integrity checks. |
| Work ideas, task creation, and exact review recording | operator | Agents may store authority-free bounded ideas; a human approves an idea before task creation. Proof records are produced by `agent advance`. |
| Linear issue/comment/webhook adapter | adapter | Checked adapter behavior; Linear is not Palari's source of truth. |
| Git commit boundary | adapter | Optional structural enforcement of a task's allowed file changes. |
| Cursor host profile | adapter | `init --host cursor` installs an advisory project rule; git commit gate is opt-in (`--strict-git` / `cursor install`). See [Cursor Integration](cursor-integration.md). |
| Claude and Codex session setup | adapter | Tested repository-local session enforcement using portable session rules. |
| MCP stdio | adapter | Bounded protocol translation with explicit capability limits. |
| Opaque provider declarations | core boundary | Provider-neutral previews only; no provider API shape or execution. |
| Mission Control and local serve | visual | Local supervision surface with guarded integration-plan decisions and one-task exact approve; not a second evaluator. |
| ACME workspace | example | Repository example only; it is not packaged data, a default workspace, or the source of truth for candidate tests. |
| Split collections | parked | A legacy reader remains pending a stored-format decision; it cannot approve or complete work. |
| Self-hosting maintainer state profile | deferred | The policy and migration plan are documented, but live governance state is not yet isolated from the source checkout. No runtime mode is shipped. |
| Roadmap | parked | Ambiguous strategy document that mixes shipped and unresolved work; not current product status. |
| Palari Blueprint | experimental | Prospective research inventory; not a supported product promise or backlog. |
| Agent-company landscape survey | experimental | July 2026 research snapshot scoring ~60 systems on five governed-company properties; not current product status or a backlog. See [agent-company-landscape.md](agent-company-landscape.md). |
| Drop-a-receipt verifier (`verify/`) | experimental | Static unsigned PCAW v1 integrity page (work-state/digest bindings). Not WRP-10 and not full CLI governance verify. |
| Distribution workstream | experimental | Measured external adoption notes; not a product feature surface. See [distribution.md](distribution.md). |

## Command surface

Current CLI command count from parser inspection: **82**. The August 2026
minimality pass removed 65 commands: generic record mutation, restore-point
recovery, and advisory data-map, maintainer, gate, and playbook views. The
ordinary journey, supported adapters, and safety boundaries remain.

The default help is intentionally narrow. It leads with `init`, `work`,
`agent`, `approve`, `queue`, `detail`, `proof`, `validate`, and `docs`, plus this ordinary
journey:

```text
init -> work add -> agent start --next -> agent advance
-> independent agent review -> approve -> proof verify
```

There is no blanket compatibility promise for pre-1.0 commands. Superseded
paths are removed when the current replacement is documented and committed
stored data does not require a migration boundary. In particular, `agent
advance` is the sole current check-and-finish command; the older `agent done`
shortcut and synthetic legacy-workspace `migrate` command are not retained.
New commands should remain rare and must expose a distinct current safety
capability.

The authority-free idea flow reuses `work add --idea` and `approve IDEA-ID`, so
it adds no parser command. An idea is not eligible agent work until a human
turns it into a task.

Historical `superseded` and `abandoned` records remain inspectable. They leave
the default queue, agent candidate list, and Approval Inbox; `queue
--include-closed` and `detail` preserve their reason and optional successor.

## Provider boundary

Generic integration records keep the provider name opaque. Palari can produce
one provider-neutral external-action preview and bind it through approval and
the outbox, but it does not model Slack, GitHub, Jira, email, or another
provider's API payload. Declaring a provider name does not make it a supported
adapter or enable execution.

Linear is the only current live provider path. It is limited to checked issue
reads/imports, approved comment sends, approved issue status updates, and
approved issue creation from local tasks, plus verified Issue webhooks. Every
live write requires a recorded plan, human approval, and queued outbox item
first. Palari remains the source of truth for permissions, allowed files,
sources and actions, check results, run records, and approval.
