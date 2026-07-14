# Command Reference

Most commands are read-only. Workspace initialization, authoring, and lifecycle
commands intentionally write to `workspace.json` after validation. No command
merges, pushes, deploys, activates policy, executes broker side effects, uses
secrets, or bypasses human authority.

## Two-Minute Onramp

```bash
palari init
palari work add "Clean up launch notes" --write docs/notes.md
palari claude install
```

`init` creates a starter workspace in an existing project: one human (named
from `git config user.name` when available), one Palari (Claude by default,
`--palari` to rename), one goal, one workbench, and one repo source. It
refuses to overwrite an existing `workspace.json`. When the current directory
contains a `workspace.json`, every command uses it as the default workspace,
so no `--workspace` flag is needed after `init`.

`work add` creates one agent-startable work item from a title and its write
paths. `--write` paths become the enforced write boundary (and are declared on
the workbench so the boundary stays consistent); `--read` paths stay
read-only. Defaults: the workspace's only Palari, goal, and workbench, risk
R1, intensity light, and the next `WORK-NNNN` id. Pass `--as`, `--goal`,
`--workbench`, `--risk`, `--intensity`, `--scope`, `--acceptance`, `--verify`,
`--id`, or `--approvals` to override.

## Workspace Init

```bash
./bin/palari workspace init workspaces/new-company --name "New Company"
./bin/palari workspace init workspaces/new-company --name "New Company" --json
```

Creates a blank, single-file `workspace.json` with the current schema version
and all known collections present. The command validates the file before
writing success output and refuses to overwrite an existing workspace. It does
not create humans, Palaris, goals, authority records, receipts, or external
connections by itself.

## Queue

```bash
./bin/palari queue
./bin/palari queue --json
./bin/palari queue --include-closed --json
```

Shows the current operator queue with attention state, `next_step_type`, goal,
Palari, owner, adaptive intensity, evidence state, review state, receipt state,
approval progress, integration state, learning signal, workbench context,
active attempts, coordination warnings, and next action. Closed work is omitted
by default so the command stays focused on current attention. Use
`--include-closed` for audit/history-style inspection. `next_step_type`
classifies intent for humans and agents without requiring them to parse the
command string.

## Detail

```bash
./bin/palari detail WORK-0001
./bin/palari detail WORK-0001 --json
```

Assembles one work item with its workbench, goal, Palari, parent/child work
items, dependencies, allowed sources, attempt, receipt, evidence, review,
linked decisions, human decisions, outcome, active parallel attempts,
coordination warnings, safety state, `next_step_type`, and next action. Active
work that is missing proof points `next_commands` toward `agent check` and
`agent finish` before review or human decision steps.

## State

```bash
./bin/palari state
./bin/palari state --json
```

Shows a compact operator state: record counts, attention counts, top attention
with its `next_step_type`, agent handoff bridge when available, and next
command, queue items, active parallel work, and coordination warnings. This is
the first fast read model for the whole workspace.

## Data Map

```bash
./bin/palari data map
./bin/palari data map --json
```

Shows where workspace data lives without adding a memory engine or live
connector. The map summarizes `workspace.json`, `.palari/history.jsonl`,
collection counts, declared external providers, sources, integrations, Palari
memory-source references, dry-run integration activity, and what Palari does
not store, such as raw tokens, provider responses, OAuth state, vector indexes,
or autonomous approvals.

## Docs

```bash
./bin/palari docs check
./bin/palari docs check --json
./bin/palari docs map
./bin/palari docs map --json
./bin/palari docs init --dry-run --json
./bin/palari docs init --write
```

`docs check` inspects agent-ready repository documentation. It checks for a
compact `AGENTS.md`, canonical `docs/agent/` files, local documentation links,
major command-reference coverage, schema/core-object coverage, README links,
and stale old-orchestrator terminology. Missing agent docs are a warning, not a
work blocker.

`docs map` prints the current documentation surfaces and canonical agent docs.
It is read-only.

`docs init` inspects the repository and proposes starter agent-ready docs. It is
dry-run by default. Use `--write` to create missing files. Existing files are
skipped unless `--overwrite` is also provided, so the command does not silently
replace committed repo truth.

## Validate

```bash
./bin/palari validate
./bin/palari validate --json
```

Validates the workspace source of truth. It fails closed when schema version,
record shape, unknown fields, lifecycle values, references, evidence freshness,
review freshness, human approval capability, or completion quorum are invalid.
If `workspace.json` declares `collection_files`, validate reads and merges those
workspace-relative collection files before running the same checks.

## Scope

```bash
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json
./bin/palari scope WORK-0001 --changed secrets.env --action deploy
```

Checks paths and actions against a work item's declared allowed resources and
forbidden actions.

## Review Guide

```bash
./bin/palari review guide WORK-0001
./bin/palari review guide WORK-0001 --json
./bin/palari review record REVIEW-0001 --work-item-id WORK-0001 --reviewed-head HEAD --reviewer HUMAN-MAINTAINER --verdict accept-ready
```

`review guide` is read-only. It assembles the selected work item, workbench,
Palari, attempt, evidence, receipt, changed files, suggested review focus,
advisory reviewer candidates from the workbench humans, possible verdicts, and
a neutral review-record command template. Each reviewer candidate also includes
a ready-to-edit `review record` command with `VERDICT` and `REVIEW-ID`
placeholders. It does not record a review verdict, approve work, mutate
history, or replace human judgment.

`review record` is the explicit write path for a review verdict. Use it only
after inspecting the evidence and receipt.

## Decision Guide

```bash
./bin/palari decision guide DECISION-0001
./bin/palari decision guide WORK-0002 --json
./bin/palari decision update DECISION-0001 --status decided --set "result=Use option A"
```

`decision guide` is read-only. It assembles one decision, its linked work item,
required human, options, tradeoffs, recommendation, safe default, and a neutral
decision-update command template. It also includes ready-to-edit update commands
for each suggested result, such as the safe default or `defer`. It does not
decide, approve, mutate history, or authorize implementation. If the target is a
work item id, Palari resolves the open decision linked to that work item.

## Gate Profiles

```bash
./bin/palari gate profiles
./bin/palari gate profiles --json
./bin/palari gate recommend WORK-0001
./bin/palari gate recommend WORK-0001 --json
```

`gate profiles` lists the built-in review contracts Palari can recommend:
prompt authority, source boundary, external write, human approval,
deploy/runtime, privacy/multimodal, and product overclaim.

`gate recommend` is read-only. It inspects the selected work item, risk, sources,
allowed actions, output targets, integration plans, outbox records, receipt,
evidence, review, and human-decision state. It returns the relevant gates, why
each applies, and a compact reviewer contract with reviewer role, inspection
targets, blocker checklist, required evidence, and accept-ready standard.

Gate recommendations do not execute reviews, mutate workspace state, create
claims, record reviewer notes, or grant acceptance authority. Simple low-risk
work may return `no_special_gate_required: true`; that means no extra
risk-specific gate was detected beyond the normal receipt/evidence/review loop.

## Capabilities And Authority

```bash
./bin/palari capability list --json
./bin/palari capability check WORK-0001 --json
./bin/palari capability export-policy WORK-0001 --json
./bin/palari authority profiles --json
./bin/palari authority check WORK-0002 --profile team-safe --json
```

Capabilities describe adapters, skill packs, integrations, repo work, and other
power a Palari may use. `capability check` returns the capabilities allowed for
one work item. `capability export-policy` emits a compact adapter policy with
read/write paths, external-action boundaries, and the invariant that adapters
cannot accept work or expand scope.

Authority profiles describe risk/quorum posture. Built-ins are
`solo-founder`, `team-safe`, and `strict`. `authority check` shows whether the
work item's declared approval count satisfies the profile and whether
receipt-ready completion is allowed for that risk tier.

## Proposals And Scope Expansion

```bash
./bin/palari proposal create PROP-0001 --title "Draft note" --goal GOAL-0001 --palari PALARI-SOFIA
./bin/palari proposal adopt PROP-0001 --work-id WORK-0100 --by HUMAN-FOUNDER --json
./bin/palari proposal reject PROP-0001 --by HUMAN-FOUNDER --reason "Out of scope"
./bin/palari work expand-scope WORK-0100 --id DECISION-0100 --by PALARI-SOFIA --write docs/new.md --reason "Need another output"
```

Proposals are AI-safe planning objects. A Palari may propose work, but adoption
requires a real human id and creates the work item explicitly. Scope expansion
does not mutate a work item; it creates an open decision linked to the work so
the queue blocks until a human answers.

## Evidence, Attempts, And Acceptance

```bash
./bin/palari attempt closeout ATTEMPT-0001 --head-sha HEAD --cleanliness clean --changed docs/output.md
./bin/palari evidence verify EVIDENCE-0001 --json
./bin/palari work accept WORK-0001 --by HUMAN-FOUNDER --reviewed-head HEAD --json
./bin/palari work complete WORK-0001 --json
```

`attempt closeout` records explicit head SHA, changed paths, cleanliness, and
closeout status. By default it requires matching evidence for the head.

Evidence records automatically get artifact hashes and a manifest hash when
recorded through the CLI. The manifest covers the exact receipt hash. Receipts
automatically get a receipt hash. `evidence verify` requires the manifest and a
matching receipt, recomputes artifact and receipt hashes, and fails on missing,
changed, unsafe, or contradictory proof.

`work accept` is the explicit human acceptance gate. It requires fresh passing
evidence, fresh accept-ready review, qualified human authority, no open linked
decision, no scope-overlap warning, and a valid exact evidence/receipt/review
binding. New accept-ready reviews receive that binding automatically and become
immutable; substantive changes require a new review record.
It records both a human decision and an acceptance record. `work complete` keeps
the terminal status gate and records a missing acceptance record from the latest
qualified human decision when needed.

## Agent Packets

### MCP Server

```bash
./bin/palari --workspace examples/acme-company-os mcp serve
```

`mcp serve` runs a stdio MCP server for agents and MCP-speaking clients. It
exposes compact Palari tools for queue, state, detail, docs check, and the
agent loop: next, brief, start, check, finish, handoff, doctor, loop, and
release. Most tools are read-only. `palari_agent_start` and
`palari_agent_release` only write or remove local `.palari/packets` and
`.palari/claims` runtime files; they do not change workspace records, call
providers, read secrets, or perform external writes. The server writes only
JSON-RPC MCP messages to stdout.

```bash
./bin/palari agent next --json
./bin/palari agent next --all --json
./bin/palari agent next --as PALARI-SOFIA --json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent brief WORK-0007 --as PALARI-SOFIA --mode review --json
./bin/palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed docs/output.md --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --git-diff --json
./bin/palari agent release WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent finish WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent handoff WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent doctor WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent loop WORK-0003 --as PALARI-SOFIA --json
```

`agent next` reads the current open queue for one Palari, ranks safe-to-start
candidates first, and includes blocked/waiting candidates with blocker codes.
Closed work remains visible through `queue` and `detail`, but is omitted from
agent candidate lists.
With no `--as` argument, `agent next` defaults to an operator rollup across
every Palari in the workspace. `--all` is still accepted as the explicit form.
The rollup includes a `top_candidate` field so agents can follow the first safe
or blocking next step without scanning every nested candidate. Candidates include
`next_step_type`, such as `start-work`, `check-active-proof`,
`human-decision`, or `review-handoff`, so tools do not have to infer intent from
the command string alone. Active work that already has an attempt and needs
proof points to `agent check` / `agent finish` instead of re-starting with
another brief. Each candidate also includes `doctor_command`, a plain-language
safety diagnosis, and `loop_command`, a compact orientation helper that
summarizes brief/check/finish/handoff status without replacing the concrete
`next_command`. It is read-only and does not claim or assign work.

`agent brief` compiles one bounded, context-window-safe packet for an AI agent.
It is a read-only preview and returns either `status: ready` or
`status: blocked`.
`agent start` is the execution entry point for ready work. It persists the exact
packet under `.palari/packets/`, records a local lease claim under
`.palari/claims/`, and returns the same packet with `start` metadata. If the
packet is blocked, `agent start` reports blockers and writes nothing. `agent
release` removes this Palari's local claim when work is abandoned or handed off.
For Git worktrees, the claim also stores a hashed, metadata-only baseline of
already-dirty paths. It does not read their contents. The ignored baseline
companion persists when a claim is released and reused when that work item is
started again, preventing release/restart from laundering later dirt. When the
baseline has a commit head, a dedicated local Git ref and its original reflog
entry witness that head independently of the ignored JSON files. An active
claim may renew only while its freshly compiled packet authority is unchanged;
generic `work update` is blocked until the claim is released and the change is
routed through an authorized handoff into a new claim epoch.

The packet includes the acting Palari, work objective, goal/workbench context,
allowed paths, allowed sources, forbidden actions, required output, completion
contract, proof/integration state, stop conditions, blockers, and safe next
commands. Agents should treat this packet as their working boundary.
`--mode review` compiles a read-only reviewer packet for work already waiting on
review or marked receipt-ready. It includes review focus and compact
attempt/evidence/receipt context, sets write paths to empty, and points to the
review guide without recording a verdict.
`agent next --mode review` treats `needs-review` and `receipt-ready` work as
ready review candidates while leaving other states blocked.

`agent check` rebuilds the current packet and verifies whether the workspace
state satisfies the packet's completion contract. For ready packets, it also
checks that this Palari owns an active matching local claim. It returns `ok`,
packet id, packet context hash, packet blockers, structured pass/fail/warn
checks, and `next_step_type` plus next safe commands. A ready-to-start packet
can still produce `ok: false` when the claim, receipt, evidence, review, or
human-decision records are missing. Missing receipt, evidence, and review
checks include concrete next-command guidance when possible, and failed
required check commands appear before generic inspect/validate commands.
Human-decision record commands are not surfaced until prerequisite proof is
present. Light low-risk receipt-ready work can satisfy the receipt requirement
without forcing review or human approval. When blocked work is waiting on
review, `agent check` prioritizes `agent handoff` before generic detail
commands.

With `--changed PATH`, repeated as needed, or `--git-diff`, `agent check`
performs a lightweight file boundary audit. It reports modified, untracked, and
deleted files; which changed files are inside or outside `allowed_paths.write`;
missing file-backed required outputs; and changed files not represented by the
current attempt `changed_files` or receipt `outputs_created`.
Unchanged paths captured as dirty before `agent start` are reported separately
as `preexisting_unchanged_files` and are not attributed to the agent. A new,
changed, malformed, or baseline-mismatched path fails closed. Path checks use
canonical repository paths and reject traversal and symlink escape.

Agent subcommands that receive `--json` return machine-readable failures on
workspace or command errors instead of plain text. The error payload includes
`ok: false`, an error code, the target work item and Palari when known, and next
safe read commands.

`agent finish` is a read-only final-report helper. It wraps `agent check` and
returns whether the agent may claim completion, whether the work should be
handed off to a human, `next_step_type`, missing requirements, completed
requirements, blockers, and report guidance. Handoff-ready receipt work points
to `agent handoff` before the direct review guide. Review handoff is withheld
until its receipt/evidence prerequisites pass. Human approval is withheld until
receipt, evidence, and exact review all pass. Human-only mutation templates are
isolated in `agent handoff.human_action_commands`, not returned as agent-safe
finish commands. It does not close
work, record receipts, mutate history, or perform external actions.
In review mode, `ready-to-report` means the agent can report a review
recommendation with evidence, not record a human review or claim the original
work item is complete.

`agent handoff` is read-only and meant for the moment after `agent finish`
identifies a human review or decision step. It returns the compact finish
summary plus relevant review-guide or decision-guide context, separates
agent-safe read commands from human action commands, and does not mutate the
workspace. `agent next` and receipt-ready `agent finish` prefer this command
before lower-level direct guide commands.

`agent doctor` is read-only and explains why one work item is or is not safe for
an agent right now. It summarizes packet readiness, completion checks, missing
proof, human handoff boundaries, and recommended commands in plainer language.

`agent loop` is read-only and summarizes the current agent control flow for one
work item. It includes stage status and exact commands for `brief`, `check`,
`finish`, and `handoff` when a handoff is available. It deliberately omits the
full stage payloads; run the listed command when you need the detailed packet,
check, finish, or handoff output.

`agent done` is a shortcut for R1/light/0-approval work items only. It
auto-records a minimal attempt, receipt, and work update; releases and
re-claims the work item; runs the full check/finish loop; closes out the
attempt; and completes the work item — all in one command. For R2+ or
non-light work, it rejects with guidance to use the full proof lifecycle.
Pass `--changed PATH` for each changed file, `--head-sha` for attempt
closeout, and `--model-or-worker` to label the attempt.

`git install` writes a Palari-managed pre-commit hook into `.git/hooks/pre-commit`
that checks staged files against active claim write boundaries. If any staged
file is outside the boundary, the commit is rejected. This provides IDE-agnostic
enforcement that works in any environment (Windsurf, Cursor, Devin, terminal).
Use `--remove` to uninstall. `git status` shows whether the hook is installed
and lists active claims. `git pre-commit` is the check command the hook calls;
it can also be run manually.

Queue and detail read models keep `next_commands` oriented toward the human or
operator step, such as `review guide` or `decision guide`. When a work item is
waiting on review or a human decision, they also expose `agent_handoff_command`
so an AI agent can bridge to the same context without mutating the workspace.
Queue, state, and detail JSON also expose `agent_loop_command` as a compact
agent orientation helper for the selected work item.
Detail and dashboard agent command blocks add review-mode packet/check commands
when the selected work item is in a review handoff state.

## Claude Code Enforcement

```bash
./bin/palari --workspace workspaces/palari-company-os claude install
./bin/palari --workspace workspaces/palari-company-os claude install --local --strict
./bin/palari --workspace workspaces/palari-company-os claude install --remove
./bin/palari --workspace workspaces/palari-company-os claude status
./bin/palari --workspace workspaces/palari-company-os claude status --json
echo '{"tool_name":"Write","tool_input":{"file_path":"deploy/production.yml"}}' \
  | ./bin/palari --workspace workspaces/palari-company-os claude hook pre-tool-use
```

`claude install` writes Palari-managed PreToolUse, Stop, and SessionStart hooks
into Claude Code settings so the packet write boundary is enforced by the
harness instead of agent goodwill. `claude hook` is the handler those hooks
invoke: it reads one hook payload from stdin, checks it against the active
claims under `.palari/`, recompiles execute authority from the current
workspace, and prints a JSON decision. It denies human-attributed Palari
mutations and generic packet-authority changes from agent Bash, and asks a
human before opaque interpreters, unreviewed executables, dynamic shell
indirection, or Git witness mutations, including `git -C` and explicit
Git-directory/worktree forms. Classification covers every shell segment even
when another segment has an in-scope target; command environment assignments,
`git -c`, external diff/text-conversion options, and `rg --pre` also require a
human ask. Opaque or indirect commands ask even without an active claim, and
direct writes to workspace root/split files, `.palari/`, or Git metadata remain
protected after claim release. Protection includes option-encoded destinations,
linked-worktree/common Git directories, and Git pager/filter helper options. It
never mutates workspace records and fails open on handler errors. `claude
status` reports installed hooks and active claims. See
[Claude Code Integration](claude-code-integration.md) for the full flow.

## Playbooks

```bash
./bin/palari playbooks sources
./bin/palari playbooks sources --json
./bin/palari playbooks recommend WORK-0003
./bin/palari playbooks recommend WORK-0003 --json
./bin/palari playbook-source create superpowers \
  --label "Superpowers skills" \
  --provider github \
  --uri https://github.com/obra/Superpowers \
  --ref main \
  --license MIT \
  --list included_playbooks=brainstorming,writing-plans,verification-before-completion
```

`playbooks sources` lists external playbook sources and the allowed skills from
each source. `playbooks recommend` combines user-selected playbooks from the
work item with Palari's state-based suggestions. It also prints a short
operating guidance section with practical one-sentence advice for the next agent
run. External playbooks are guidance only; Palari still owns goals, scope,
sources, authority, receipts, evidence, review, human decisions, and outcomes.

## Integrations

```bash
./bin/palari integrations
./bin/palari integrations --json
./bin/palari integration check INT-SLACK-OPS
./bin/palari integration check INT-SLACK-OPS --json
./bin/palari integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify
./bin/palari integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --json
./bin/palari integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --record --id PLAN-X
./bin/palari integration approve PLAN-X --by HUMAN-FOUNDER
./bin/palari integration reject PLAN-X --by HUMAN-FOUNDER --reason "wrong audience"
./bin/palari integration cancel PLAN-X --by HUMAN-FOUNDER --reason "no longer needed"
./bin/palari integration enqueue PLAN-X --by HUMAN-FOUNDER
./bin/palari integration outbox-check OUTBOX-X --json
./bin/palari integration outbox-cancel OUTBOX-X --by HUMAN-FOUNDER --reason "no longer needed"
```

Integrations declare possible external providers and boundaries before Palari
can ever use them. The v0 implementation is dry-run only: it validates provider,
owner, event, action, source, risk, and secret-reference metadata, then produces
a payload preview without reading secrets or calling Slack, GitHub, Jira,
Linear, email, or any other provider.

`secret_ref` values must be references such as `env:PALARI_SLACK_WEBHOOK_URL`.
Raw tokens or keys fail validation. Planning also fails closed when an
integration is disabled, when a requested event/action is not allowed, or when
the provider does not support the requested action. Workspace validation applies
the same provider/action matrix so hand-edited integration records cannot
declare unsupported actions. `mode` is also enforced: `notify` can only notify,
`write` can plan write-style previews, `read` and `webhook` declare no outbound
actions, and `dry_run` can preview any action supported by the provider while
still making no live call.

By default, `integration plan` is a preview and does not write workspace state.
Use `--record` when the dry-run payload should become a reviewable integration
plan. Recorded plans are stored in `integration_plans`, appended to history,
shown in `queue` and `detail`, and still do not perform live provider calls.
Recorded plans start as `pending-approval`. A qualified human can approve,
reject, or cancel the plan; each decision updates the plan state and appends
history. Approval is still custody only: Palari records that the dry-run plan
is allowed for future execution wiring, but this v0 CLI still makes no provider
call and reads no secret value.

Approved plans can be placed into `integration_outbox` with `integration
enqueue`. The outbox is the explicit future-execution boundary: it preserves the
approved payload preview, source boundary, risk, and enqueuing human, but still
does not call providers or read secrets. Pending, rejected, canceled, or already
enqueued plans fail closed. Hand-edited outbox items must keep the exact payload
preview and source boundary that the human approved on the plan. Queued outbox
items can be canceled by a qualified human with `integration outbox-cancel`;
cancellation is recorded in history, keeps the dry-run boundary intact, and
still performs no provider call.

`integration outbox-check` is a read-only execution preflight for a queued
outbox item. It confirms that the item is still queued, the plan is approved,
the integration remains enabled, the event/action are allowed, and the payload
and source boundary still match what the human approved. It also reports
`execution_enabled: false` and `would_call_provider: false`; this command is
preparation for future executor wiring, not live Slack/GitHub/Jira/Linear/email
execution.

## Linear Adapter

For the short end-to-end operating path, see
[Linear Operating Loop](linear-operating-loop.md).

```bash
./bin/palari linear doctor --json
./bin/palari linear connect --json
./bin/palari linear issues --team ENG --json
./bin/palari linear sync ENG-123 --json
./bin/palari linear linked --json
./bin/palari linear issue ENG-123 --json
./bin/palari linear import ENG-123 --as PALARI-SOFIA --json
./bin/palari linear start ENG-123 --runner codex --as PALARI-SOFIA --json
./bin/palari linear start ENG-123 --runner codex --as PALARI-SOFIA --adopt-by HUMAN-FOUNDER --json
./bin/palari linear status ENG-123 --json
./bin/palari linear block-template --as PALARI-SOFIA --goal GOAL-0001 --risk R1 --intensity light --scope "Tighten copy" --acceptance-target "Copy is clearer" --verification ./scripts/verify.sh --json
./bin/palari linear inspect-block ENG-123 --as PALARI-SOFIA --json
./bin/palari linear webhook serve --host 127.0.0.1 --port 0 --json
./bin/palari linear webhook verify --payload-file payload.json --signature HEX --timestamp MS --json
./bin/palari linear webhook events --limit 20 --json
./bin/palari linear post-gate ENG-123 --record --event review_requested --actor PALARI-SOFIA --json
./bin/palari linear post-gate ENG-123 --record --event work_completed --action update-issue --actor PALARI-SOFIA --json
./bin/palari linear push WORK-0002 --as PALARI-SOFIA --team ENG --record --json
./bin/palari linear send OUTBOX-ID --by HUMAN-FOUNDER --confirm --json
```

`linear push` plans a governed Linear issue creation for a local work item, so
Palari-born tickets become visible in Linear. The plan embeds the work item's
palari block in the issue description; after approval and enqueue, `linear
send` creates the issue via `issueCreate` and stores the returned issue key,
id, and url as the work item's external refs in the same write. Already-linked
work items are rejected. The Linear team id is resolved live at send time from
`--team` (or the only visible team).

`linear connect` verifies `LINEAR_API_KEY` against Linear (viewer,
organization, and visible teams) and prepares the governed integration record.
Without a key it still prepares the record and reports the missing credential
as a structured blocker with next steps. `linear issues` lists open issues for
one team, annotated with palari-block presence and local link state. `linear
sync` pull-refreshes one linked issue with the same non-destructive updates as
a verified webhook event — no tunnel required.

`linear post-gate --action update-issue` plans a governed issue status update
instead of a comment. The plan stores the target workflow state by name or by
default state type (`work_started`/`review_requested` -> started,
`work_completed` -> completed; `work_blocked` requires `--to-state`); the
concrete Linear state id is resolved live at send time. The same human
approval, enqueue, and `linear send` gates apply as for comments.

Linear can be the human-facing issue surface while Palari remains the
governance and runtime layer. The adapter uses Linear's stable GraphQL API with
`LINEAR_API_KEY`; Palari stores only `env:LINEAR_API_KEY`, never the token
value. Inbound webhooks use `LINEAR_WEBHOOK_SECRET`; Palari stores only
`env:LINEAR_WEBHOOK_SECRET`, never the secret value. `linear doctor`, `linear
linked`, `linear status`, `linear block-template`, `linear webhook verify`,
`linear webhook events`, and `linear post-gate` are local/read-model or
plan-only commands. `linear connect`, `linear issue`, `linear issues`, `linear
import`, `linear start`, `linear inspect-block`, `linear sync`, and `linear
send` need live Linear GraphQL access. `linear
webhook serve` does not call GraphQL, but it accepts verified inbound Linear
webhooks.

`linear issue` fetches and normalizes an issue without mutating the workspace.
`linear import` creates or updates a Palari proposal linked to the issue. If the
issue description contains a valid fenced `palari` JSON block, the supported
governance fields are copied into the proposal. Missing or invalid governance
never auto-starts work; it leaves a proposal requiring human adoption.

`linear doctor` reports whether the local environment has `LINEAR_API_KEY` and
`LINEAR_WEBHOOK_SECRET` present as booleans only, plus linked record counts,
supported runners, webhook event-log status, and which commands call Linear.
`linear linked` groups all Linear-linked proposals and work items by issue key
with Palari refs, gate summary, pending actions, outbox state, latest webhook
event, and next commands. `linear status` preserves the top-level `READY`,
`BLOCKED`, `NEEDS_EVIDENCE`, `NEEDS_HUMAN`, or `ACCEPTED` enum and adds
`link_state`, compact refs, pending actions, latest webhook event, and next
commands.

`linear block-template` emits ready-to-paste fenced `palari` JSON after
validating local Palari, goal, risk, intensity, source, conflict, and parallel
policy references. `linear inspect-block` fetches the issue, validates the
fenced block, and reports errors, warnings, unknown fields, missing recommended
fields, and whether adopt-start would be eligible. Unknown governance fields
fail closed instead of being guessed.

`linear webhook serve` runs a local private dogfood receiver with `GET /health`
and `POST /linear/webhook`. It verifies the raw payload HMAC signature,
timestamp, and `Linear-Delivery` id before recording accepted Issue events to
`.palari/linear-events.jsonl`. Duplicate deliveries are ignored without
workspace mutation. Unlinked issues are recorded with an import next command.
Linked proposals receive external refs, and non-adopted proposal title/summary
may sync from Linear. Linked work receives external refs only. Remove/archive
events never delete or rewrite Palari records.

`linear start` starts only adopted Palari work. Without adopted work it returns
`needs_adoption` and prints the exact adoption command. With `--adopt-by`, the
named id must be a human with authority; Palari ids cannot self-adopt. `--runner`
only labels the emitted governed packet for Codex, Claude Code, Cursor, or a
generic harness. It does not launch those tools.

`linear post-gate` records a pending Linear comment plan and still performs no
provider call. A qualified human must approve and enqueue that integration plan
before `linear send` can call Linear `commentCreate`. `linear send` requires a
queued outbox item, matching approved payload, valid human authority,
`--confirm`, and `LINEAR_API_KEY`; successful sends record the provider comment
id and URL. Drift in provider, operation, issue id, body payload, or linked work
target fails closed and records failed outbox metadata without storing secrets.

## Receipt-Ready Low-Risk Work

For light R1/R2 local work, a completed attempt plus a valid receipt can move
the queue to `receipt-ready` without requiring full evidence, independent
review, and human-decision ceremony. That state is deliberately human-facing:
review the output, undo it if needed, or continue. R3/R4/R5 work and receipts
that claim actual external writes still require the stricter governance path. A
receipt may reference `planned_external_writes` only by approved integration
plan id, or `queued_external_writes` by integration outbox id, without claiming
that anything was sent or changed externally. `queued_external_writes` must
reference currently queued outbox items; canceled outbox items fail closed so a
receipt cannot imply a canceled write is still waiting to execute.

## History

```bash
./bin/palari history
./bin/palari history --limit 10 --json
```

Shows recent append-only audit events from `.palari/history.jsonl` beside the
workspace file. Mutating authoring and lifecycle commands append events only
after the workspace write validates and succeeds. Failed mutations do not append
success events.

## Receipts

```bash
./bin/palari receipt record RECEIPT-X \
  --work-item-id WORK-X \
  --attempt-id ATTEMPT-X \
  --actor PALARI-X \
  --set context_packet=PACKET-WORK-X-PALARI-X-EXECUTE-V1 \
  --set context_hash=sha256:... \
  --list sources_used=SOURCE-X \
  --list outputs_created=notes/summary.md \
  --list queued_external_writes=OUTBOX-X
```

Receipts are human-facing trust records. `queued_external_writes` points to an
approved integration plan that has been placed in the outbox, not to a live
provider call. Use it when a human needs to see that an external write is queued
at the future execution boundary and can still be canceled or reviewed.
`context_packet` and `context_hash` let the receipt point back to the exact
agent packet created by `agent start`, rather than a packet recomputed after the
workspace has changed.

## Mission Control

```bash
./bin/palari serve --as HUMAN-FOUNDER
./bin/palari --workspace examples/acme-company-os serve --as HUMAN-FOUNDER --port 8787
./bin/palari demo --serve
```

`serve` starts a live local Mission Control UI for one human operator. It is the
clickable supervision surface: work needing human attention, boundary view,
recent activity, and receipt context in one browser page.

Important boundaries:

- It binds to `127.0.0.1` by default.
- `--host` values outside localhost print a warning because this v1 server has
  no login/auth layer.
- Mutating requests require a per-session CSRF token embedded in the page.
- Every write goes through the normal authoring/store path, including workspace
  validation, stale-write conflict checks, and the workspace write lock.
- Files remain the source of truth; `/state-hash` changes only when the
  workspace file content changes.
- The server uses polling rather than SSE/WebSockets so the implementation
  stays stdlib-only and easy to inspect.

`palari demo --serve` prepares the throwaway demo workspace, runs the blocked
write scenario, and opens the same local UI against that demo state.

## Dashboard

```bash
./bin/palari dashboard --out /tmp/palari-company-dashboard
./bin/palari --workspace workspaces/palari-company-os dashboard --out /tmp/palari-dogfood-dashboard --json
```

Generates the static export/share format with local `index.html`, `styles.css`,
and `app.js` files. The dashboard reads `workspace.json` and
`.palari/history.jsonl`; it does not mutate the workspace, run broker actions,
connect external providers, or require a web server.

The first dashboard has five sections:

- Queue: attention counts, work cards, trust/evidence/review state, next action
- Work: lifecycle lanes and expandable work detail
- Trust: selected sources and human-facing receipts
- History: append-only event timeline
- Authority: humans, Palaris, open decisions, and human blockers

Dashboard agent handoff commands are read-only bridges. The UI labels them as
agent-safe and keeps human review or decision actions human-only.

## Desktop Prototype

```bash
./bin/palari desktop-prototype --out /tmp/palari-desktop-prototype
./bin/palari desktop-serve --out /tmp/palari-desktop-prototype
```

`desktop-prototype` generates static read-only HTML, CSS, and JavaScript from
`examples/desktop-demo/workspace.json`.

`desktop-serve` generates the same files and serves them locally for design
review. It does not expose external runner endpoints, connect Google Drive, or
mutate the workspace model.

## Migration

```bash
./bin/palari migrate
./bin/palari migrate --write
```

Upgrades unversioned, v0, and v1 workspaces to schema v2 and ensures required
collections exist. Legacy unbound accept-ready proof is blocked, its dependent
acceptance is revoked, and affected governed terminal work is reopened for a
fresh exact review. Split workspaces are migrated in place without collapsing
included collections: included files are written before the root version is
advanced, and any concurrent root or included-file change blocks the write.
Without `--write`, the command previews all changes.

## Authoring Commands

All authoring commands validate the full workspace before writing.
For now, authoring and lifecycle write commands support single-file workspaces
only. If a workspace declares non-empty `collection_files`, write commands fail
closed instead of rewriting `workspace.json` and risking data loss in split
collection files.

```bash
./bin/palari goal create GOAL-X --title "Improve onboarding"
./bin/palari goal update GOAL-X --status active

./bin/palari human create HUMAN-X --name "X Human" --list approval_capabilities=product
./bin/palari human update HUMAN-X --role "Reviewer"

./bin/palari palari create PALARI-X --name Xena --role "Onboarding partner" --owner-human HUMAN-X
./bin/palari palari update PALARI-X --scope "Prepare onboarding work"

./bin/palari source create SOURCE-X --label "Launch note" --kind note --provider local_note --uri notes/launch.md --set selected=true --list allowed_palaris=PALARI-X
./bin/palari source update SOURCE-X --set last_read_at=2026-06-19T04:00:00Z

./bin/palari decision create DECISION-X --question "Which option should we choose?"
./bin/palari decision update DECISION-X --status decided --set "result=Use option A"

./bin/palari work create WORK-X --title "Draft note" --goal GOAL-X --palari PALARI-X
./bin/palari work update WORK-X --set current_attempt=ATTEMPT-X --list allowed_sources=SOURCE-X --list allowed_actions=local_write

./bin/palari attempt record ATTEMPT-X --work-item-id WORK-X --actor PALARI-X
./bin/palari receipt record RECEIPT-X --work-item-id WORK-X --attempt-id ATTEMPT-X --actor PALARI-X --list sources_used=SOURCE-X --list outputs_created=notes/summary.md
./bin/palari evidence record EVIDENCE-X --work-item-id WORK-X --attempt-id ATTEMPT-X --head-sha head-x --status passed
./bin/palari review record REVIEW-X --work-item-id WORK-X --reviewed-head head-x --reviewer HUMAN-X --verdict accept-ready
./bin/palari human-decision record HUMAN-DECISION-X --work-item-id WORK-X --human-id HUMAN-X --reviewed-head head-x --decision accepted --status accepted
./bin/palari outcome record OUTCOME-X --work-item-id WORK-X --summary "Useful result."
```

Use `--set FIELD=VALUE` for scalar fields and `--list FIELD=A,B,C` for list
fields. The authoring surface is intentionally simple and dependency-free.

## Lifecycle Commands

Lifecycle commands are aliases around evidence, review, decision, completion,
and outcome records.

```bash
./bin/palari lifecycle evidence EVIDENCE-X --work-item-id WORK-X --attempt-id ATTEMPT-X --head-sha head-x --status passed
./bin/palari lifecycle review REVIEW-X --work-item-id WORK-X --reviewed-head head-x --reviewer HUMAN-X --verdict accept-ready
./bin/palari lifecycle decide HUMAN-DECISION-X --work-item-id WORK-X --human-id HUMAN-X --reviewed-head head-x --decision accepted --status accepted
./bin/palari lifecycle complete WORK-X
./bin/palari lifecycle outcome OUTCOME-X --work-item-id WORK-X --summary "What happened."
```

Accepted human decisions fail closed if:

- the human lacks the required approval capability
- evidence is missing, failed, or stale
- review is missing, not accept-ready, or stale
- the decision head does not match the reviewed head

Completion fails closed unless one of these is true:

- the queue integration state is `ready`, meaning evidence, review, and any
  required human approval are complete
- the work is receipt-ready local R1/R2 work with `required_approval_count: 0`,
  terminal dependencies, no open linked decisions, and no actual, planned, or
  queued external writes

## External Maintainer Status

```bash
./bin/palari maintainer status
./bin/palari maintainer status --json
```

Reports repo path, branch, head, upstream, divergence, dirty files, focused
tests run if known, and PR readiness.

Focused tests are known only if an optional local verification log exists at:

```text
.palari-company-os/verification.json
```

This file is intentionally ignored by git.

## Verification

```bash
./scripts/verify.sh
```

Runs unit tests, Python compilation, JSON validity checks, and CLI smoke checks
for queue, detail, state, validate, scope, maintainer status, playbooks,
dashboard generation, and the desktop prototype generator.

The GitHub Actions workflow at `.github/workflows/ci.yml` runs the same command
on pushes to `main` and on pull requests.
