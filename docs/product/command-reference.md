# Command Reference

Most commands are read-only. Initialization and setup commands intentionally
write to `workspace.json` after validation. No command merges, pushes, deploys,
activates policy, or bypasses human approval. Generic integration commands do
not call providers or read secrets. Linear is the one current live adapter; its
explicit commands may read the configured credential for bounded reads or send
an exact approved and queued comment, issue-status update, or issue creation.

Running `palari --help` shows the small ordinary surface and its golden journey.
Expert and recovery commands are intentionally omitted from
that first screen but remain available and parseable; use direct
`palari COMMAND --help` when operating below the ordinary loop.

This reference keeps exact command names, JSON keys, and stored values. Its
explanations use the plain product words in
[Plain Language](plain-language.md): task, run, run record, checks, review,
approval, result, and tamper-evident history.

Reachability is not a compatibility promise. Restore-point recovery, split
collections, broad manual planning/record authoring, and the data map,
maintainer, required-check, and playbook recommendation views remain parked
pending a product decision. They are outside the ordinary supported path and
cannot grant approval.

## Two-Minute Onramp

```bash
palari init --host codex
palari work add "Clean up launch notes" --write docs/notes.md
palari agent start --next --as PALARI-CLAUDE --json
```

`init` creates a starter workspace in an existing repository: one human (named
from `git config user.name` when available), one builder agent (Claude by
default; `--palari` is the exact compatibility flag), one distinct
review-only agent, one goal, one project record (stored as a `workbench`), and
one repository source. The reviewer is linked to the goal and selected source
but is not execution-capable through the project workbench. It can inspect
review-mode proof and record an advisory verdict; it cannot build the run or
provide human approval. Initialization refuses to overwrite an existing
`workspace.json`. When the current directory
contains a `workspace.json`, every command uses it as the default workspace,
so no `--workspace` flag is needed after `init`.

Add `--host claude` or `--host codex` to make first setup one anchored action.
Both profiles install or reuse the portable repository rules, install the
assignment-bound Git commit check, and add tested repository-local session hooks.
Codex requires explicit `/hooks` review before its hooks activate.
Existing workspaces use the same `init` action with an explicit path and host:

```bash
palari init WORKSPACE-DIR --host codex --as PALARI-ID --json
```

Without `--host`, `init` still refuses to overwrite an existing workspace.
Adoption preserves existing instructions and host configuration. It grants no
review, approval, merge, push, deployment, provider, or external-write
permission. A nested workspace adopts at its enclosing Git root.
If root instructions or selected-host configuration already exist, first
initialization preserves them outside the anchor and returns one separate
review/adoption action. Generated commands use an inspectable repository-local
launcher when present; otherwise they preserve the absolute Palari entrypoint
currently running or a validated `PATH` entry. A symlinked `workspace.json`,
escaping or malformed managed target, or unmanaged Git pre-commit hook blocks
before adoption writes; co-located foreign host hooks are preserved.
Palari-managed legacy Claude hooks are replaced by the current profile and can
be removed without leaving duplicates.

`work add` creates one agent-startable task from a title and its writable
files. `--write` paths become the enforced write boundary (and are declared on
the project record so the boundary stays consistent); `--read` paths stay
read-only. Defaults: the project's sole execution-capable agent, the sole goal
and project (`workbench` in stored data), risk R1, intensity light, and a
collision-resistant opaque `WORK-<UUID>` ID. A review-only agent does not make
builder selection ambiguous. The ID identifies a task and carries no priority, dependency,
review, approval, or
integration ordering meaning. Historical and explicit IDs remain valid. Pass
`--depends-on WORK-ID` repeatedly to declare real prerequisite edges and
`--parallel-policy independent|coordinate|exclusive` to declare overlap
coordination. Missing, repeated, self-referential, and cyclic dependencies fail
closed. Pass `--as`, `--goal`, `--workbench`, `--risk`, `--intensity`,
`--scope`, `--acceptance`, `--verify`,
`--id`, or `--approvals` to override.

`--write PATH` is the presence-required form. When the exact change type
matters, use repeatable `--create PATH`, `--modify PATH`, and
`--delete PATH` instead:

```bash
palari work add "Replace obsolete guidance" \
  --create docs/new.md --modify docs/current.md --delete docs/obsolete.md
```

Exact intents cannot be combined with `--write`, and one path cannot carry two
intents. The task brief requires create/modify targets to exist as regular
files in the matching Git change class. A delete target must be absent and must appear
as deleted across the assignment-base-to-candidate Git history; its check
manifest uses an explicit absent tombstone.

The command returned by `work add` is `agent start --next`: it selects exactly
one currently safe task using the same queue and task-brief rules, saves its
portable session rules, and assigns it. `agent next`, `brief`, and explicit
`start WORK-ID` remain optional inspection and controlled-selection surfaces.
`palari claude install` remains the supported Claude-only adapter command; it
is not a requirement for the provider-neutral loop.

## Queue

```bash
./bin/palari queue
./bin/palari queue --json
./bin/palari queue --include-closed --json
./bin/palari queue --approval-inbox --json
./bin/palari queue --approval-inbox --select WORK-0001 --json
```

Shows the current task queue with attention state, `next_step_type`, goal,
agent, owner, declared risk and intensity, check status, review status,
run-record status, approval progress, integration status, project context,
active runs, coordination warnings, and next action. Closed tasks are omitted
by default so the command stays focused on current attention. Use
`--include-closed` for audit/history-style inspection. `next_step_type`
classifies intent for humans and agents without requiring them to parse the
command string.

`--approval-inbox` compiles immutable, canonical Approval Packs from the
current committed history status. JSON retains one subject, output, run record
(`receipt`), check results (`evidence`), and review binding per member while
grouping the operator summary and approval interaction. It also emits one
strict canonical presentation file and digest per pack. Approval Inbox v2
emits only actor-specific executable commands. New packs use v3 and carry both
the declared numeric count and effective final human count; the reader remains
compatible with v2 packs. The exact advanced human command names both the pack
and presentation digests. Every direct dependency also carries a
recursive state digest over its current task rules, verification, outputs, and
own dependencies. `--select` narrows the pack without changing work. Each JSON pack
has an `approval_commands` entry containing its exact
digest and every required `--pack-member`; copying that command cannot silently
expand a narrowed selection. Parked, blocked, stale, and non-batchable items
remain unexecuted. `primary_action` states how many attributable human actions
are actually available, while each evaluated item carries a `resolution`
class and owner. `approval_modes` distinguishes automatic finishing (stored as
`automatic-reconciliation`), approve-eligible, approve-selected,
individual-effect, and unavailable modes.
The exact stored `review-and-accept` mode is unavailable in the current policy
because review and approval must come from distinct actors.

The Approval Inbox is the advanced and batched surface. It emits commands only
for named humans that can execute them against the current authority plan; it
does not emit an action that is already known to collide with the builder or
reviewer. If a state is stale, blocked, non-batchable, externally effectful,
missing required approvals, or has no viable actor arrangement, it remains
parked with an owner and smallest safe correction instead of receiving a
weaker or guaranteed-to-fail command.

## Detail

```bash
./bin/palari detail WORK-0001
./bin/palari detail WORK-0001 --json
```

Assembles one task with its project, goal, agent, parent/child tasks,
dependencies, allowed sources, run, run record, check results, review,
linked decisions, human approvals or rejections, result, active parallel runs,
coordination warnings, safety state, `next_step_type`, and next action. Active
work that is missing checks points `next_commands` toward `agent check` and
`agent finish` before review or approval steps.
Exact Approval Packs are compiled only at the explicit Approval Inbox
(`queue --approval-inbox`) or human-handoff boundary; ordinary detail does not inspect
output bytes or audit the tamper-evident history.

## Approve One Local Task

```bash
./bin/palari approve WORK-0001 --as HUMAN-FOUNDER --json
./bin/palari approve WORK-0001 --as HUMAN-FOUNDER \
  --reason "I inspected the exact reviewed result." --json
```

This is the ordinary final human action for one R1/R2 reversible local task.
The caller names only the task and acting declared human. Palari derives a
singleton Approval Pack and canonical presentation internally, verifies the
current journal, exact output, run record, checks, bound independent review,
human capability, actor separation, and effective final approval count, then
revalidates the state before mutation. For review-required work, that effective
count is at least one even if the stored numeric count is zero. Approval, its
acceptance record, and local completion share the existing crash-safe history
transaction.

The command does not perform an external action, relax the task policy, create
a review, add a missing vote, or accept external, irreversible, individual-only,
or multi-approval work that one vote cannot complete. A repeated invocation by
the same human for the exact already-completed decision reports a no-op instead
of duplicating authority. Stale proof, changed artifacts, invalid history,
identity collisions, and ambiguous selection return structured JSON with a
stable error code and next safe action.

The human handoff shows the concise current presentation and emits an exact,
explicit-workspace `approve ... --presented DIGEST` action for each viable
qualified human. The binding is inserted by Palari; the person runs the command
without copying it. If state changed after the handoff, the action fails with
`APPROVAL_STATE_CHANGED`. A manually entered command without `--presented`
derives current state at invocation and is not bound to an earlier handoff.
Agents may present the exact action, but supported hooks deny agent execution
of it. The lower-level pack surface below remains available for batching,
mixed decisions, explicit recovery, and other advanced workflows.

## Approve Or Reject An Approval Pack

```bash
./bin/palari human-decision pack \
  --pack-digest sha256:... \
  --presentation-digest sha256:... \
  --human-id HUMAN-ID \
  --approve-eligible \
  --pack-member WORK-1 \
  --pack-member WORK-2 \
  --reason "Morning review of the exact bundle" \
  --json
./bin/palari human-decision pack --pack-digest sha256:... \
  --presentation-digest sha256:... --human-id HUMAN-ID \
  --approve WORK-1 --reject WORK-2 --defer WORK-3 --json
```

This is a human-only approval surface. One command records task-by-task
decisions over one exact immutable manifest and the exact canonical
`palari.approval-presentation.v1` artifact emitted beside it. Here `artifact`
is the exact protocol word for the presentation file. Copy both digests
from the Approval Inbox; missing, altered, transplanted, or stale presentation
bindings fail closed. Relevant prior decisions and their current approval
status are part of the presentation, so each later required approval must use a
fresh presentation. Eligible local actions run in dependency order inside the
same crash-safe history transaction. The result reports the exact schema name
`palari.one-action-convergence.v1`; no later completion command is needed when
the required approvals are met. An incomplete approval count remains parked.
Changed subjects, artifacts, reviews, dependencies, or pack policies fail
closed. A non-empty `--pack-member` selection must cover the exact reviewed
manifest, and unfinished
dependencies outside a narrowed pack remain visible blockers. A completed
dependency whose exact output changes also stales the narrowed pack before
another approval can run. Approve, reject, and defer all require each task's
declared human approval capability. External,
access-expanding, financial, legal, security, and irreversible actions remain
individually gated.

The presentation digest proves the canonical artifact bytes, independent of
browser layout and fonts. The bound CLI surface records that those bytes were
made available to the action; it cannot prove what compromised software
displayed or that a person read, understood, or made a sound decision.

## Status

```bash
./bin/palari state
./bin/palari state --json
```

Shows a compact operator state: record counts, attention counts, top attention
with its `next_step_type`, agent handoff bridge when available, and next
command, queue items, active parallel work, and coordination warnings. This is
the first fast status view for the whole workspace.

## Stored Data Map

```bash
./bin/palari data map
./bin/palari data map --json
```

Shows where workspace data lives without adding a memory engine or live
connector. The map summarizes `workspace.json`, the active tamper-evident
history, collection counts, declared external providers, sources, integrations, Palari
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

Validates stored workspace structure and safety bindings. It fails closed when
the schema version, record shape, unknown fields, status values, references,
recorded checks/review currency, human approval capability, or required
approval count is invalid. It does not inspect live output bytes, run Git, or
audit the history. Trusted state changes and explicit verification or inbox
boundaries perform those checks. If `workspace.json` declares parked
`collection_files`, validate
reads and merges those workspace-relative files before the same stored checks.

## Allowed Files And Actions (`scope`)

```bash
./bin/palari scope WORK-0001 --changed docs/notes.md
./bin/palari scope WORK-0001 --changed secrets.env --action deploy
```

Checks paths and actions against a task's declared allowed resources and
forbidden actions.

## Review Guide

```bash
./bin/palari review guide WORK-0001
./bin/palari review guide WORK-0001 --json
./bin/palari review record REVIEW-0001 --work-item-id WORK-0001 --reviewed-head HEAD --reviewer HUMAN-MAINTAINER --verdict accept-ready
./bin/palari agent brief WORK-0001 --as PALARI-REVIEWER --mode review --json
./bin/palari review record REVIEW-0001-PALARI --work-item-id WORK-0001 --reviewed-head HEAD --reviewer PALARI-REVIEWER --verdict accept-ready --json
```

`review guide` v2 is read-only. It assembles the selected task, project, agent,
run, check results, run record, changed files, suggested review focus,
eligible advisory reviewers, possible review results, and concrete exact
commands. Human candidates come from the project. Agent candidates must be
distinct from the builder, linked to the work goal, and allowed for every
selected source. Each candidate receives one deterministic, binding-derived
`review record` action per supported verdict. These actions are executable
against the state that produced the guide. Each concrete action carries a
machine-supplied `--binding-digest`; the transition re-derives the current
proof binding and fails with `REVIEW_BINDING_STALE` if the inspected run,
check results, run record, or task contract changed. The retained
`REVIEW-ID`/`VERDICT` template is explicitly non-executable. A Palari review
result is advisory and never counts as a required human approval. The guide
itself does not record a result, approve work, change history, or replace human
judgment.

`review record` is the explicit write path for a review result. Use it only
after inspecting the check results and run record. Agent reviewers must first
open the matching `--mode review` task brief; self-review and
unapproved-source review are rejected. Human-attributed review and every
approval command remain human-only.

## Decision Guide

```bash
./bin/palari decision guide DECISION-0001
./bin/palari decision guide WORK-0002 --json
./bin/palari decision update DECISION-0001 --status decided --set "result=Use option A"
```

`decision guide` is read-only. It assembles one decision, its linked task,
required human, options, tradeoffs, recommendation, safe default, and a neutral
decision-update command template. It also includes ready-to-edit update commands
for each suggested result, such as the safe default or `defer`. It does not
decide, approve, change history, or authorize implementation. If the target is a
task ID, Palari resolves the open decision linked to that task.

## Suggested Review Checks (`gate`)

```bash
./bin/palari gate profiles
./bin/palari gate profiles --json
./bin/palari gate recommend WORK-0001
./bin/palari gate recommend WORK-0001 --json
```

`gate profiles` lists the built-in review checks Palari can recommend:
prompt permission, source boundary, external write, human approval,
deploy/runtime, privacy/multimodal, and product overclaim.

`gate recommend` is read-only. It inspects the selected task, risk, sources,
allowed actions, output targets, integration plans, outbox records, run record,
checks, review, and approval status. It returns the relevant checks, why
each applies, and compact reviewer rules with reviewer role, inspection
targets, blocker checklist, required check results, and accept-ready standard.

These recommendations do not execute reviews, change workspace state, create
task locks, record reviewer notes, or grant approval. Simple low-risk work may
return `no_special_gate_required: true`; that means no extra risk-specific
check was detected beyond the normal run-record/check/review loop.

## Capabilities And Permissions

```bash
./bin/palari capability list --json
./bin/palari capability check WORK-0001 --json
./bin/palari capability export-policy WORK-0001 --json
./bin/palari authority profiles --json
./bin/palari authority check WORK-0002 --profile team-safe --json
```

Capabilities describe adapters, skill packs, integrations, repo work, and other
power an agent may use. `capability check` returns the capabilities allowed for
one task. `capability export-policy` emits a compact adapter policy with
read/write paths, external-action boundaries, and the invariant that adapters
cannot approve work or expand its limits.

Permission profiles describe risk and required-approval posture. Built-ins are
`solo-founder`, `team-safe`, and `strict`. `authority check` shows whether the
task's declared approval count satisfies the profile. It does not waive exact
check results or create permission. The rules evaluator separately applies the
narrow R1/light/0-approval/no-external review and human-approval
exemption.

## Proposals And Expanded Limits

```bash
./bin/palari proposal create PROP-0001 --title "Draft note" --goal GOAL-0001 --palari PALARI-SOFIA
./bin/palari proposal adopt PROP-0001 --work-id WORK-0100 --by HUMAN-FOUNDER --json
./bin/palari proposal reject PROP-0001 --by HUMAN-FOUNDER --reason "Out of scope"
./bin/palari work expand-scope WORK-0100 --id DECISION-0100 --by PALARI-SOFIA --write docs/new.md --reason "Need another output"
```

Proposals are AI-safe planning records. An agent may propose work, but adoption
requires a real human ID and creates the task explicitly. The command remains
`work expand-scope` for compatibility. It does not change the task directly;
it creates an open question linked to the task so the queue blocks until a
human answers.

## Parked Expert Verification Authoring And Recovery

These low-level commands exist for explicit workspace repair, audit fixture
construction, and deterministic recovery. They are not the ordinary agent or
operator path. Agents derive check results with `agent advance`; humans provide
ordinary one-task approval through `approve`. The exact Approval Inbox action
remains the advanced and batched surface.

```bash
./bin/palari attempt closeout ATTEMPT-0001 --head-sha HEAD --cleanliness clean --changed docs/output.md
./bin/palari evidence verify EVIDENCE-0001 --json
./bin/palari work accept WORK-0001 --by HUMAN-FOUNDER --reviewed-head HEAD --json
./bin/palari work complete WORK-0001 --json
```

`attempt closeout` is the exact expert command for closing a run. It records
the commit SHA, changed paths, cleanliness, and closeout status. By default it
requires matching check results for that commit.

Stored check-result records use the exact name `evidence`. The CLI adds output
hashes and a manifest hash, and the manifest covers the exact run-record
(`receipt`) hash. `evidence verify` requires both records, recomputes the output
and run-record hashes, and fails on missing, changed, unsafe, or contradictory
data. New output-bound check results require a non-empty run-record output list
and output manifest, and fail when any listed output is absent from that
manifest. When a workspace file is nested below a run's recorded workspace
root, outputs (`artifacts` in the stored manifest) resolve from that root only
if the workspace is canonically contained there and every artifact stays inside
the run's explicit allowed paths; otherwise
the artifacts are marked unsafe without being read. Legacy runs without an
explicit parent-root boundary retain workspace-local resolution.
Pre-PCAW `evidence` without `output_binding_version` remains readable and
reports the legacy limitation, but every refreshed check-result record and
every new review or approval requires `palari.evidence_outputs.v1` coverage.

`work accept` is a parked single-task human recovery command. It requires
current passing check results, a current `accept-ready` review, a qualified
human, no open linked question, no allowed-file overlap warning, and a valid
exact check-result/run-record/review binding. New `accept-ready` reviews receive
that binding automatically and become immutable; substantive changes require a
new review record. It records both the human's choice and an approval record,
then runs bounded
automatic finishing. When the exact check results remain current, `work accept`
normally reaches final status in the same human action. `work complete` remains
an explicit, repeat-safe recovery command for the same required checks. When a
current qualified human choice exists, Palari derives the approval record in
memory, runs all completion checks, and writes approval plus final status only
if every check passes. Missing, stale, contradictory, or insufficient approval
never produces completed work.

## Supersede Or Abandon Obsolete Work

```bash
./bin/palari work update WORK-OLD --status superseded \
  --terminal-reason "WORK-NEW owns the narrower objective." \
  --successor-work-item-id WORK-NEW --json
./bin/palari work update WORK-OLD --status abandoned \
  --terminal-reason "This experiment will not continue." --json
```

`superseded` and `abandoned` are explicit audit-only final statuses. They do
not assert completion and do not manufacture completion records. Both require a
non-empty `terminal_reason`; `successor_work_item_id` is optional but must name
a distinct existing task. Cycles and dependencies that still point to a
retired prerequisite fail closed. Retirement is also rejected while the item
has an active run, open linked question, pending integration plan, or queued
external action. The retirement transaction may change only the final-status
fields; it cannot add check results or approval at the same time. Afterward,
the task rules, adopted proposal, and all linked records are immutable.

Default `queue`, `agent next`, and `queue --approval-inbox` views omit retired
work. `queue --include-closed` and `detail WORK-ID` retain its exact status,
reason, successor, and historical records. Existing successful final statuses
(`completed`, `closed`, and `done`) retain their check requirements.

## Task Briefs (`agent`)

### MCP Server

```bash
./bin/palari --workspace /path/to/workspace mcp serve
```

`mcp serve` runs a stdio MCP server for agents and MCP-speaking clients. It
exposes compact Palari tools for queue, state, detail, docs check, and the
agent loop: next, brief, start, check, advance, finish, handoff, doctor, loop,
and release. `palari_agent_brief` can return portable session rules (the exact
machine object is `session_contract`), and `palari_agent_start` can select and
assign the next safe task. Most tools are read-only. Start and release write
only local task-brief and assignment runtime state.
`palari_agent_advance` may record a deterministic run, run record, check
results, and eligible local closeout records, but stops before independent
review, human approval, or external effects. The server exposes no
review-record, `human-decision`, approval-record, merge, push, deployment,
provider, or external-write tool. It writes only JSON-RPC MCP messages to
stdout.

```bash
./bin/palari agent next --json
./bin/palari agent next --all --json
./bin/palari agent next --as PALARI-SOFIA --json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --session-contract --json
./bin/palari agent brief WORK-0007 --as PALARI-SOFIA --mode review --json
./bin/palari agent start --next --as PALARI-SOFIA --mode execute --json
./bin/palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --isolate --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed docs/output.md --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --git-diff --json
./bin/palari agent release WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent release WORK-0003 --as PALARI-SOFIA --reason "Blocked on product choice" --next-action "Ask the founder to choose A or B" --json
./bin/palari agent finish WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent handoff WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent doctor WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent loop WORK-0003 --as PALARI-SOFIA --json
./bin/palari agent advance WORK-0003 --as PALARI-SOFIA --dry-run --json
./bin/palari agent advance WORK-0003 --as PALARI-SOFIA --json
```

`agent next` reads the current open queue for one agent, ranks safe-to-start
candidates first, and includes blocked/waiting candidates with blocker codes.
Closed work remains visible through `queue` and `detail`, but is omitted from
agent candidate lists. With no `--as` argument, `agent next` defaults to an
operator rollup across
every agent in the workspace. `--all` is still accepted as the explicit form.
The rollup includes a `top_candidate` field so agents can follow the first safe
or blocking next step without scanning every nested candidate. Candidates
include
`next_step_type`, such as `start-work`, `check-active-proof`,
`human-decision`, or `review-handoff`, so tools do not have to infer intent from
the command string alone. Active work that already has a run and needs
verification points to `agent check` or `agent finish` instead of restarting with
another brief. Each candidate also includes `doctor_command`, a plain-language
safety diagnosis, and `loop_command`, a compact orientation helper that
summarizes task-brief/check/finish/handoff status without replacing the concrete
`next_command`. Candidate JSON names `dependency_ids`, unfinished
`blocked_by_dependency_ids`, and repository-shared assignment state directly.
Queue rank is presentation only and never substitutes for a dependency edge.
It is read-only and does not assign work.

`agent start --next` is the normal one-command entry. It evaluates the same
ordered candidates, selects the first `can_start` task, then calls the existing
task-brief/session-rules/assignment path for that exact task ID. If no task is
ready, it returns `status: no-ready-work`, one explanation, and the next safe
read action without writing an assignment. Supplying both `WORK-ID` and
`--next`, supplying neither, or combining `--next` with `--isolate` fails
closed. Use explicit
`start WORK-ID --isolate` when checkout isolation is required.

`agent brief` compiles one bounded, context-window-safe task brief for an AI
agent. It is a read-only preview and returns either `status: ready` or
`status: blocked`. Add `--session-contract` to emit deterministic,
provider-neutral session rules instead of the full task brief. That object
contains the exact brief binding, allowed files/sources/actions, selected
source and capability details, obligations, blockers, safe commands,
enforcement-property statuses, and
security limitations. It omits compilation time, absolute local paths, source
contents, and provider payloads. Ready session rules still grant no
execution permission; an active matching assignment is required.
`agent start` is the execution entry point for ready work. It saves the exact
task brief under `.palari/packets/`, saves the canonical session rules under
`.palari/packets/session-contracts/`, records its path and digest in the local
assignment record under `.palari/claims/`, and returns the task brief with
`start` metadata. Missing, malformed, duplicate-key, digest-mismatched,
path-mismatched, or current-brief-mismatched session rules invalidate the
assignment with restart guidance. Every stored `claim` uses schema v2 and requires both
session-rule fields, so deleting both fails closed; unsupported `claim` schemas
fail closed rather than being upgraded. The local schema marker does not
authenticate an assignment against a hostile same-user process. If the task
brief is blocked, `agent start` reports blockers and writes nothing. The
`agent release` command removes this agent's local assignment when work is
abandoned or handed off.

`agent release` with both `--reason` and `--next-action` is the durable
interruption path for an owned execution assignment. In one recorded local
transaction it records a blocked run, the reason, the exact next safe action,
and task-brief/Git/digest/change observations, then releases the assignment.
Bare `agent release` remains the non-durable assignment-only form. Durable
release creates no run
record, check results, review, approval, or result. If execution stops after
persistence but before release, rerunning the exact command resumes release
without duplicating the parking record. Status-bound recovery permits only the
recorded assignment epoch's
deterministic task-status change to `blocked`; it rechecks all other permissions
against the original task brief. Changed reason, action, assignment, brief, or
repository state fails closed.

Durable release requires an already active, writable tamper-evident history.
A legacy workspace without one fails before changing anything and returns the
exact one-command `history --checkpoint` activation action; Palari does not
silently claim that earlier history was continuous.

For Git worktrees, the assignment also stores a hashed, metadata-only baseline
of already-dirty paths. It does not read their contents. The ignored baseline
companion persists when an assignment is released and reused when that task is
started again, preventing release/restart from laundering later dirt. When the
baseline has a commit head, a dedicated local Git ref and its original reflog
entry witness that head independently of the ignored JSON files. An active
assignment may renew only while its freshly compiled task permissions remain
unchanged. If the first assignment's current task is absent from that baseline commit,
Palari records a small all-agent execute/review permission-digest catalog in
the hashed baseline. The v2 witness's original reflog message binds the catalog
digest. No manual pre-assignment commit is required, but later permission still requires a
successor.

Every complete Git-backed assignment uses the current v2 witness, v2 lease,
and v2 recorded-state (`governance-projection`) snapshot. An unchanged recorded
state is represented by an exact snapshot with no changed paths; it does not
fall back to a legacy lease. Legacy v1 witnesses, leases, and recorded-state
snapshots are unsupported and are not upgraded in place. A historical
current-only baseline has no safe automatic migration and requires a successor.
Restart validates the persisted v2 witness ref, head, optional catalog message,
lease, and recorded-state snapshot before acquiring a lease and again under the
final lock before writing an assignment.
Actor file limits, worker, standards, input boundaries, and stable source
locator identity are part of the immutable permission digest, not merely
presentation metadata. After release or expiry, a same-ID task-rule change
still cannot start: exact baseline/current permission comparison fails before
lease creation and again before the durable assignment write. A declared actor
and `agent handoff` do not reset that baseline. Preserve the original record
and create a successor task for the changed rules.

`agent start` holds a per-task assignment-update lock throughout its start path.
It acquires the shared workspace-write lock only for its final strict
re-read, permission/snapshot revalidation, and local task-brief/assignment
writes after the Git lease step. A concurrent workspace change gets the explicit
safe retry diagnostic; it does not serialize independent tasks while another
task is negotiating its lease. Git compare-and-swap remains the cross-worktree
same-task lock.

When Git is available, an active assignment also has a compare-and-swap lease
under `refs/palari/leases/`. Linked worktrees therefore cannot both take the
same task, while different tasks remain independently assignable. Lease records
contain local coordination metadata and expiry, not human approval.
Malformed, contradictory, or concurrently changed leases fail closed.

`agent start --isolate` requires the task definition to be committed, then
creates or safely resumes a deterministic `palari/work-*` branch in a sibling
`.palari-worktrees/` directory. The returned JSON includes the worktree,
workspace, branch, and exact resume command. It never removes an operator
worktree and grants no review, approval, merge, push, deployment, or external
write permission. Commit all intended task definitions first, then many
independent sessions may call `--isolate` concurrently.

The task brief includes the acting agent, work objective, goal/project context,
allowed paths, allowed sources, forbidden actions, required output, completion
rules, check/integration status, stop conditions, blockers, and safe next
commands. Agents should treat this brief as their working boundary. The
portable session rules do not configure or launch an agent harness.
Its `portable-declaration-v1` enforcement profile labels Palari transition
checks separately from properties that need a host adapter. File writes and
stop-time checks are `adapter-required`; allowed reads are `advisory`. A future
adapter must not promote either status unless its native controls are proven.
`--mode review` compiles a read-only review brief for a task already waiting on
review with current exact check results. It includes review focus and compact
run/check-results/run-record context and sets write paths to empty. For a
matching eligible agent, the brief exposes exactly one advisory review-record
action. `human-decision` and all other non-reviewable states remain blocked.

`agent check` rebuilds the current task brief and verifies whether workspace state
satisfies its completion rules. For ready briefs, it also checks that this
agent owns a matching local assignment. It returns `ok`, the task-brief ID and
context hash, blockers, structured pass/fail/warn checks, and `next_step_type`
plus next safe commands. A ready-to-start brief can still produce `ok: false`
when the assignment, run record, check results, review, or approval records are
missing. Missing-record checks include concrete next-command guidance when
possible, and failed required commands appear before generic inspect or
validate commands. `human-decision` record commands are not shown until the
required run record, checks, and review are present. R1/light/0-approval work
with current exact check results and no allowed,
planned, queued, or actual external writes may complete without independent
review or human approval. When blocked work is waiting on
review, `agent check` prioritizes `agent handoff` before generic detail
commands.

With `--changed PATH`, repeated as needed, or `--git-diff`, `agent check`
performs a lightweight file boundary audit. It reports modified, untracked, and
deleted files; which changed files are inside or outside `allowed_paths.write`;
missing file-backed required outputs; and changed files not represented by the
current run's `changed_files` or run record's `outputs_created`.
Unchanged paths captured as dirty before `agent start` are reported separately
as `preexisting_unchanged_files` and are not attributed to the agent. A new,
changed, malformed, or baseline-mismatched path fails closed. Path checks use
canonical repository paths and reject traversal and symlink escape.

When a task declares `path_intents`, each exact path has one final-state
intent: `create`, `modify`, or `delete`. Create and modify require a regular
file and the matching Git change class. Delete requires the exact path to be
absent and Git to report its deletion, so a declared tombstone satisfies the
rules instead of becoming a false missing-output error. Duplicate,
overlapping, unsafe, symlinked, undeclared, or mismatched paths fail closed.
Tasks that omit `path_intents` retain the historical presence-required output
rule.

Agent subcommands that receive `--json` return machine-readable failures on
workspace or command errors instead of plain text. The error payload includes
`ok: false`, an error code, the target task and agent when known, and next
safe read commands.

`agent finish` is a read-only final-report helper. It wraps `agent check` and
returns whether the agent may report completion, whether the work should be
handed off to a human, `next_step_type`, missing requirements, completed
requirements, blockers, and report guidance. Handoff-ready run-record work points
to `agent handoff` before the direct review guide. Review handoff is withheld
until its run-record and check-result prerequisites pass. Human approval is
withheld until the run record, check results, and exact review all pass.
Human-only change templates are
isolated in `agent handoff.human_action_commands`, not returned as agent-safe
finish commands. It does not close
work, record run records, change history, or perform external actions.
In review mode, `ready-to-report` means the agent can report a review
recommendation supported by check results, not record a human review or say the
original task is complete.

`agent handoff` is read-only and meant for the moment after `agent finish`
identifies a human review or decision step. It returns the compact finish
summary plus relevant review-guide or decision-guide context, separates
agent-safe read commands from human action commands, and does not change the
workspace. For an eligible local approval with valid journal continuity, it
shows the current singleton presentation and exposes one exact
`palari --workspace PATH approve WORK-ID --as HUMAN-ID --presented DIGEST
--json` action per viable qualified human. The digest is machine-supplied; it
is not a copied argument. The advanced presentation-bound pack actions remain
in the nested pack context and Approval Inbox. Legacy, invalid-journal,
non-batchable, or
authority-infeasible states stay blocked and expose no raw human-decision
fallback. The authority plan excludes the current builder and reviewer from
approval candidates. `agent next` and review-bound `agent finish` prefer this
command before lower-level direct guide commands.

`agent doctor` is read-only and explains why one task is or is not safe for an
agent right now. It summarizes task-brief readiness, completion checks, missing
records, human handoff boundaries, and recommended commands in plainer language.

`agent loop` is read-only and summarizes the current agent control flow for one
task. It includes stage status and exact commands for `brief`, `check`,
`finish`, and `handoff` when a handoff is available. It deliberately omits the
full stage payloads; run the listed command when you need the detailed task
brief, check, finish, or handoff output.

`agent advance` is the sole current run-to-check-results and closeout path for
Palari-managed Git work. `--dry-run` derives an ordered, content-addressed plan
without running verification or changing state. Execution derives the complete
assignment-start commit range, checks the task-brief boundary, runs built-in
argument-vector profiles (never task prose), and binds passing results to the
exact head, profile, source state, interpreter, and platform. R1 uses
`git --literal-pathspecs diff --check BASE HEAD -- CHANGED_PATHS`; higher risk
tiers retain their complete/install/documentation profiles. It then rechecks
the plan and
commits the run, run record, check results, and closeout as one tamper-evident
history transaction. Current exact passing checks are mandatory for every
completion.
Only R1/light/0-approval work with no allowed, planned, queued, or actual
external writes may complete without independent review and human approval;
all other work releases its assignment and stops at the next required boundary.
After a separate current review and qualified human approval exist, Palari
normally runs the same automatic-finishing driver immediately. A later
`agent advance` remains a repeat-safe recovery command: it
verifies the exact output bytes, derives any missing approval record, and
completes final bookkeeping without recording or impersonating a human. Checks
remain current across later commits only when every intervening committed or
dirty tracked path is a workspace governance projection (the exact machine
term for recorded Palari state); any substantive repository path fails closed.
A repeated exact-state call reuses current records without duplicating them or
rerunning profiles.

Local verification-cache files are advisory: even a structurally valid cached
pass is rerun before new check results are created. `--refresh-verification` ignores
the advisory record, including a prior failure, and reruns the profiles. When
later committed repository changes invalidate otherwise intact checks for a
completed task, the same explicit flag can perform a no-write verification
refresh: the old output bytes must still match their recorded checks, the
tracked worktree must be clean, no execute assignment may be active, and all
required profiles run again against current `HEAD`. The refresh creates a new
run, run record, and check-results binding, then stops for fresh independent
review and human approval; it never reuses the prior decision. Changed output
bytes fail closed and must return through an ordinary bounded execution flow.

Refresh diagnostics distinguish a changed task output
(`REFRESH_ARTIFACT_CHANGED`), dirty tracked context
(`REFRESH_DIRTY_WORKTREE`), an active execution assignment
(`REFRESH_ACTIVE_CLAIM`), and concurrent state drift
(`REFRESH_STATE_CHANGED`). The final safety check also asserts the exact
workspace digest, Git head, clean tracked state, and SHA-256 output hashes
that were verified before it starts its locked transaction. A workspace
compare-and-swap rejection uses the same state-changed diagnostic. These
failures occur before check records are written and retain the previous records
for inspection.

The command never records a review result or `human-decision` record. It may
write an approval record only by deterministically deriving it from an
already-current human-decision record. It never performs an external write,
push, merge, or deployment.

`git install` writes a Palari-managed pre-commit hook into `.git/hooks/pre-commit`
that checks staged files against active assignment write boundaries. If any
staged file is outside the boundary, the commit is rejected. This provides
IDE-agnostic
enforcement that works in any environment (Windsurf, Cursor, Devin, terminal).
Use `--remove` to uninstall. `git status` shows whether the hook is installed
and lists active assignments. `git pre-commit` is the check command the hook
calls; it can also be run manually.

Queue and detail status views keep `next_commands` oriented toward the human or
operator step, such as `review guide` or `decision guide`. When a task is
waiting on review or human approval, they also expose `agent_handoff_command`
so an AI agent can bridge to the same context without changing the workspace.
Queue, state, and detail JSON also expose `agent_loop_command` as a compact
agent orientation helper for the selected task. Detail agent command blocks add
review-mode task-brief/check commands when the selected task is awaiting review.

## Git Integration Readiness

```bash
./bin/palari git status --work-id WORK-ID --target-ref main --json
```

This read-only check separates Palari approval from compatibility with the
current target branch. It binds the current run's exact commit, determines
whether the task has current final approval and check records, compares
ancestry with the target, and simulates divergent merges in a temporary shared
clone. It reports `ready`, `integrated`, or `blocked` with stable blockers such as missing
candidate checks, incomplete runs, conflicts, and required
revalidation. A clean divergent projected merge is not called ready: because
its bytes differ from the reviewed candidate, the branch must be updated and
exact checks refreshed. The command does not merge, push, review, accept, or
deploy.

## Claude Code Enforcement

```bash
./bin/palari --workspace /path/to/workspace claude install
./bin/palari --workspace /path/to/workspace claude install --local --strict
./bin/palari --workspace /path/to/workspace claude install --remove
./bin/palari --workspace /path/to/workspace claude status
./bin/palari --workspace /path/to/workspace claude status --json
echo '{"tool_name":"Write","tool_input":{"file_path":"deploy/production.yml"}}' \
  | ./bin/palari --workspace /path/to/workspace claude hook pre-tool-use
```

`claude install` writes Palari-managed PreToolUse, Stop, and SessionStart hooks
into Claude Code settings so the task-brief write boundary is enforced by the
harness instead of agent goodwill. `claude hook` is the handler those hooks
invoke: it reads one hook payload from stdin, checks it against the active
assignments under `.palari/`, recalculates execute permission from the current
workspace, and prints a JSON decision. It denies human-attributed Palari
changes, integration enqueue/cancel/send, Linear adoption, and generic
task-brief or permission changes from agent Bash. Content-addressed
`history --restore` is also denied as human-only; supplying a declared human ID
does not let an agent shell borrow that permission. `human-decision pack` is
likewise a hard deny, including path-qualified and compound commands. It asks a
human before opaque interpreters, unreviewed or path-qualified executables,
unquoted pathname expansion, tree-shaped or backup-producing writes, hook self-modification,
unclassified Palari commands, or Git witness mutations, including `git -C` and
explicit Git-directory/worktree forms. Classification covers every shell
segment even when another segment has an allowed target. Command environment
assignments, `git -c`, external diff/text-conversion options, and `rg --pre` also require a
human ask. Opaque or indirect commands ask even without an active assignment.
Direct writes to workspace root/split files, `.palari/`, or Git metadata remain
protected after assignment release. Protection includes option-encoded
destinations,
ordinary directory/basename semantics, compact/newline shell segments,
linked-worktree/common Git directories, Git repository overrides, and
Git/ripgrep helper-launching options. Long-option abbreviations are rejected at
every Palari CLI nesting level; abbreviated GNU write/Git helper options,
assignment-position tilde expansion, Bash `|&`, and Git pathspec-file imports
ask rather than bypass target discovery. Destructive ancestor directories and
the standard Claude hook settings are protected too. It never changes workspace
records and fails open on handler errors. Quoted Git pathspec magic/globs and
dash-prefixed operands after `--` remain observable, and agent-safe Palari
changes must target the hook's configured workspace. `claude status` reports
installed hooks and active assignments. See
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
task with Palari's status-based suggestions. It also prints a short
operating guidance section with practical one-sentence advice for the next agent
run. External playbooks are guidance only; Palari still owns goals, allowed
files, sources and actions, permissions, run records, check results, reviews,
human approvals, and final results.

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

Integrations declare possible external-action boundaries before an adapter can
use them. The generic implementation is dry-run only: it validates an opaque
provider identifier, owner, event, action, source, risk, and secret-reference
metadata, then produces one provider-neutral preview without reading secrets or
calling any provider. A provider identifier is routing metadata, not a claim
that Palari implements that provider's API.

`secret_ref` values must be references such as `env:PALARI_SLACK_WEBHOOK_URL`.
Raw tokens or keys fail validation. Planning also fails closed when an
integration is disabled, when a requested event/action is not allowed, or when
the action exceeds the declared mode. Workspace validation applies the same
mode/action policy so hand-edited integration records cannot widen the
boundary. `notify` can only notify, `write` can plan write-style previews,
`read` and `webhook` declare no outbound actions, and `dry_run` can preview any
generic external action while still making no live call.

By default, `integration plan` is a preview and does not write workspace state.
Use `--record` when the dry-run payload should become a reviewable integration
plan. Recorded plans are stored in `integration_plans`, appended to the
tamper-evident history, shown in `queue` and `detail`, and still do not perform
live provider calls.
Recorded plans start as `pending-approval`. A qualified human can approve,
reject, or cancel the plan; each decision updates the plan state and journal.
Approval only records permission: Palari records that the dry-run plan is
allowed for future execution wiring, but this generic CLI still makes no provider
call and reads no secret value.

Use `integration enqueue` to place approved plans into `integration_outbox`.
The outbox is the explicit future-execution boundary: it preserves the approved
payload preview, source boundary, risk, and enqueuing human, but still
does not call providers or read secrets. Pending, rejected, canceled, or already
enqueued plans fail closed. Hand-edited outbox items must keep the exact payload
preview and source boundary that the human approved on the plan. Queued outbox
items can be canceled by a qualified human with `integration outbox-cancel`;
cancellation is recorded in the journal, keeps the dry-run boundary intact, and
still performs no provider call.

`integration outbox-check` is a read-only execution preflight for a queued
outbox item. It confirms that the item is still queued, the plan is approved,
the integration remains enabled, the event/action are allowed, and the payload
and source boundary still match what the human approved. It also reports
`execution_enabled: false` and `would_call_provider: false`; this command is
preparation for an adapter boundary, not provider execution.

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

`linear push` plans a bounded Linear issue creation for a local task, so
Palari-born tickets become visible in Linear. The plan embeds the task's
palari block in the issue description; after approval and queueing,
`linear send` creates the issue via `issueCreate` and stores the returned issue key,
ID, and URL as the task's `external_refs` in the same write. Already-linked
tasks are rejected. The Linear team ID is resolved live at send time from
`--team` (or the only visible team).

`linear connect` verifies `LINEAR_API_KEY` against Linear (viewer,
organization, and visible teams) and prepares the bounded integration record.
Without a key it still prepares the record and reports the missing credential
as a structured blocker with next steps. `linear issues` lists open issues for
one team, annotated with palari-block presence and local link state.
`linear sync` pull-refreshes one linked issue with the same non-destructive updates as
a verified webhook event — no tunnel required.

`linear post-gate --action update-issue` plans a bounded issue status update
instead of a comment. The plan stores the target workflow state by name or by
default state type (`work_started`/`review_requested` -> started,
`work_completed` -> completed; `work_blocked` requires `--to-state`); the
concrete Linear state ID is resolved live at send time. The same human
approval, queue, and `linear send` checks apply as for comments.

Linear can be the human-facing issue list while Palari retains the local task
rules, checks, approvals, and execution records. The adapter uses Linear's
stable GraphQL API with `LINEAR_API_KEY`; Palari stores only
`env:LINEAR_API_KEY`, never the token value. Inbound webhooks use
`LINEAR_WEBHOOK_SECRET`; Palari stores only
`env:LINEAR_WEBHOOK_SECRET`, never the secret value. `linear doctor`,
`linear linked`, `linear status`, `linear block-template`,
`linear webhook verify`, `linear webhook events`, and `linear post-gate` are
local status-view or plan-only commands. `linear connect`, `linear issue`,
`linear issues`, `linear import`, `linear start`, `linear inspect-block`,
`linear sync`, and `linear send` need live Linear GraphQL access.
`linear webhook serve` does not call
GraphQL, but it accepts verified inbound Linear
webhooks.

`linear issue` fetches and normalizes an issue without changing the workspace.
`linear import` creates or updates a Palari proposal linked to the issue. If the
issue description contains a valid fenced `palari` JSON block, the supported
task-rule fields are copied into the proposal. Missing or invalid task rules
never auto-start work; they leave a proposal requiring human adoption.

`linear doctor` reports whether the local environment has `LINEAR_API_KEY` and
`LINEAR_WEBHOOK_SECRET` present as booleans only, plus linked record counts,
supported runners, webhook event-log status, and which commands call Linear.
`linear linked` groups all Linear-linked proposals and tasks by issue key with
Palari refs, check summary, pending actions, outbox state, latest webhook
event, and next commands. `linear status` preserves the top-level `READY`,
`BLOCKED`, `NEEDS_EVIDENCE`, `NEEDS_HUMAN`, or `ACCEPTED` enum and adds
`link_state`, compact refs, pending actions, latest webhook event, and next
commands.

`linear block-template` emits ready-to-paste fenced `palari` JSON after
validating local Palari, goal, risk, intensity, source, conflict, and parallel
policy references. `linear inspect-block` fetches the issue, validates the
fenced block, and reports errors, warnings, unknown fields, missing recommended
fields, and whether adopt-start would be eligible. Unknown task-rule fields
fail closed instead of being guessed.

`linear webhook serve` runs a local private dogfood receiver with `GET /health`
and `POST /linear/webhook`. It verifies the raw payload HMAC signature,
timestamp, and `Linear-Delivery` ID before recording accepted Issue events to
`.palari/linear-events.jsonl`. Duplicate deliveries are ignored without
workspace changes. Unlinked issues are recorded with an import next command.
Linked proposals receive external refs, and non-adopted proposal title/summary
may sync from Linear. Linked tasks receive external refs only. Remove/archive
events never delete or rewrite Palari records.

`linear start` starts only adopted Palari tasks. Without an adopted task it
returns
`needs_adoption` and prints the exact adoption command. With `--adopt-by`, the
named ID must be a human with permission; Palari IDs cannot self-adopt.
`--runner` only labels the emitted task brief for the supported Codex or Claude
Code session adapter. It does not launch either tool.

`linear post-gate` records a pending Linear comment plan and still performs no
provider call. A qualified human must approve and enqueue that integration plan
before `linear send` can call Linear `commentCreate`. `linear send` requires a
queued outbox item, matching approved payload, valid human permission,
`--confirm`, and `LINEAR_API_KEY`; successful sends record the provider comment
ID and URL. Drift in provider, operation, issue ID, body payload, or linked
task target fails closed and records failed outbox metadata without storing
secrets.

## Fully Checked Low-Risk Work

Every completion requires a finished clean run, a bound run record, and
current passing checks tied to the exact commit and output files. The rules
evaluator may omit independent review and human approval only when the task is
R1, uses light intensity, requires zero approvals, and has no allowed, planned,
queued, or actual external writes. R2+ work and every task outside those exact
conditions follow the review and human-approval path. A run record may
reference `planned_external_writes` only by approved integration plan ID, or
`queued_external_writes` by integration outbox ID, without claiming
that anything was sent or changed externally. `queued_external_writes` must
reference currently queued outbox items; canceled outbox items fail closed so a
run record cannot imply a canceled write is still waiting to execute.

## History

```bash
./bin/palari history
./bin/palari history --json
./bin/palari history --checkpoint --actor HUMAN-ID --json
./bin/palari history --recover --json
./bin/palari history --checkpoints --json
./bin/palari history --restore sha256:... --actor HUMAN-ID \
  --reason "Return to reviewed S1" --json
```

Bare `history` verifies the tamper-evident history's hash chain and exact
current status. Changes and their command, actor, action, and affected objects
are recorded in the same atomic journal transaction; there is no second
operational audit-log writer. The committed `.palari/history.jsonl` file is a
historical record only and is never read, appended, or imported at runtime.
`--checkpoint --acknowledge-break` creates a visible restore point and records,
rather than hides, a legitimate continuity break after a manual edit.
`--recover` safely repeats or finishes a prepared transaction when the on-disk
recorded state makes the safe result unambiguous.

The v1 history file is a sealed read-only predecessor. An explicit valid-v1
restore point (`--checkpoint`) can activate compact v2 without rewriting its
predecessor: the v2 restore point seals the exact v1 bytes, replay digest, head,
and counts, then subsequent events use deterministic value deltas. Verification
streams the v2 restore point and tail with
bounded memory and validates the sealed predecessor. Request-local operation
contexts reuse one verified scan and pure path-normalization results only while
their exact witnesses remain unchanged; no persistent cache may grant
permission. Complete verification still reads authenticated journal bytes and
therefore does not claim constant time.

`--checkpoints` lists every committed recorded state (`projection` in the
journal format) by content digest.
`--restore` requires a declared human and reason, then appends a restoration
transition whose recorded state exactly matches the selected digest. It never
rewrites prior history. If a run record (`receipt`) gained an external write or
an existing
outbox item became sent or failed after the target, restoration stops before
mutation; local state is not rewound into a duplicate-send or ambiguous-retry
hazard. The check scans every committed recorded state after the earliest
matching checkpoint digest, so a later reset/removal—or already being back at the target
bytes—cannot hide an intervening effect. Record any external compensation
separately and create a new recorded restore point instead.

Restoration also respects non-success retirement as a temporal boundary. It
cannot rewind `superseded` or `abandoned` tasks to an active state, relabel
successfully completed work as retired, or change the retired task's linked
audit subgraph. Create explicit successor work when the old objective must be
continued.

## Proof-Carrying AI Work

```bash
./bin/palari --workspace WORKSPACE proof export WORK-ID --output proof.json --json
./bin/palari proof verify proof.json --subject-root WORKSPACE --json
./bin/palari proof verify proof.json --statement-only --json
```

`proof export` writes byte-deterministic PCAW v1 canonical JSON for accepted,
blocked, or incomplete tasks. `proof verify` loads no workspace and performs no
network or provider calls. Full verification checks every named artifact as a
safe regular file beneath the subject root. Statement-only verification checks
the work-state binding and governance consistency but never reports full or
acceptance verification. A rejected proof exits 1 and returns stable structured
diagnostics; usage or operational errors exit 2.

PCAW v1 verifies named artifact bytes and governance consistency, but it does
not carry a portable deletion-history proof. Workspace `delete` tombstones are
enforced locally against exact Git state; exporting them as a protocol
guarantee requires a future versioned PCAW extension.

## Parked Run-Record Authoring

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

Direct run-record authoring uses the exact `receipt record` command and is
reserved for expert repair and fixtures. The ordinary agent path creates run
records through `agent advance`. `queued_external_writes` points to an
approved integration plan that has been placed in the outbox, not to a live
provider call. Use it when a human needs to see that an external write is queued
at the future execution boundary and can still be canceled or reviewed.
`context_packet` and `context_hash` let the run record point back to the exact
task brief (`packet` in stored data) created by `agent start`, rather than a
brief recomputed after the workspace has changed.

## Mission Control

```bash
./bin/palari serve --as HUMAN-FOUNDER
./bin/palari --workspace /path/to/workspace serve --as HUMAN-FOUNDER --port 8787
./bin/palari demo --serve
```

`serve` starts a live local Mission Control UI for one human operator. It is the
clickable supervision surface: tasks needing human attention, boundary view,
recent activity, and run-record context in one browser page.

Important boundaries:

- It binds to `127.0.0.1` by default.
- `--host` values outside localhost print a warning because this v1 server has
  no login/auth layer.
- Tasks needing human approval are read-only in Mission Control. A qualified
  human runs the exact presentation-bound `approve` command emitted by the
  inspected handoff, or intentionally uses the advanced Approval Inbox action;
  Mission Control exposes no raw decision-record endpoint or form.
- Mutating requests require a per-session CSRF token embedded in the page.
- Integration-plan decisions go through the guarded integration service,
  including workspace validation, stale-write conflict checks, and the
  workspace write lock.
- Files remain the source of truth; `/state-hash` changes only when the
  workspace file content changes.
- The server uses polling rather than SSE/WebSockets so the implementation
  stays stdlib-only and easy to inspect.

`palari demo --serve` prepares the throwaway demo workspace, runs the blocked
write scenario, and opens the same local UI against that demo state.

## Parked Expert Authoring Commands

These record-by-record commands are retained as an explicit expert repair and
fixture surface. They are not a second supported work process, a compatibility
layer, or an agent fallback. All authoring commands validate the full workspace
before writing.
For now, authoring write commands support single-file workspaces
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

Raw `human-decision` authoring is not the supported approval path; ordinary
one-task human approval runs the presentation-bound `palari approve` command
emitted by handoff. A manually typed bare form derives current state at
invocation. The Approval Inbox emits the advanced presentation-bound pack
command.
When an expert uses the parked commands for recovery, accepted decisions still
fail closed if:

- the human lacks the required approval capability
- check results (`evidence`) are missing, failed, or stale
- review is missing, not accept-ready, or stale
- the decision head does not match the reviewed head

Completion fails closed unless current exact passing check results are bound to
the final clean run, run record, commit, and output files; dependencies are
final; and no linked question remains open. In addition, either independent
review and explicit human approval must be current, or the task must satisfy
the exact R1/light/0-approval/no-external exemption.

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

Runs the current unit suite, static and schema checks, PCAW conformance,
temporary CLI boundaries, and one isolated wheel build/install smoke. Use
`./scripts/verify.sh focused tests.test_MODULE` for explicit development
feedback without a hidden full-suite fallback.

The GitHub Actions workflow at `.github/workflows/ci.yml` runs the same command
once on Python 3.12 for pushes to `main` and pull requests. Other supported
interpreters receive thin import, central-rules, and CLI-help compatibility
checks.
