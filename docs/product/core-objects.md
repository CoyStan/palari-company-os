# Stored Records

Palari stores a small set of explicit records as JSON and represents them in
Python with dataclasses. Familiar names come first below; parentheses show the
machine term used by the schema, protocol, or existing commands.

Every record has one place in the five-part product map:

- **Goals**: goals.
- **Team**: people and agents, including their roles.
- **Work**: projects, ideas, tasks, and runs. Tasks group their view data into
  now, next, and later. Files are task data, not a new part.
- **Checks**: records, tests, reviews, choices, and results.
- **Limits**: sources, guides, tools, rules, and outside links. Rules split into
  allowed, ask, and never. Outside links split into apps, plans, and the send
  queue.

These groups have no overlap and cover all current record types. Exact stored
names remain below for code and JSON work.

## Goal

Why work exists.

## Agent (`Palari`)

A named AI worker or workflow identity. The record defines its allowed work,
inputs, standards, memory sources, owner, and forbidden actions. The identity
can stay stable when a different model or tool performs a run.

## Person (`human`)

An identity and accountability record for a real person. People may hold
approval capabilities; AI roles never inherit them silently.

## Question for a Person (`decision`)

A structured request for human judgment. It keeps an important choice and its
answer out of vague status text.

## Allowed Source (`source`)

Input selected by a person for an agent to read. A source records its label,
provider, generic URI or external ID, access mode, owner, allowed agents,
selection state, readiness, and last-read information. Readiness covers the
data class, authority, steward, freshness expectation, and whether redaction is
required.

A source marks what context was available for a task. This record does not by
itself connect to a provider.

## Playbook (`playbook_source`)

Parked, non-authoritative outside guidance that Palari may recommend while a
task is prepared. It records the label, provider, URI, pinned ref, license,
enabled state, and included playbooks. Superpowers compatibility can point to
allowed `SKILL.md` files without turning them into Palari permissions or human
approval.

## Allowed Tool or Action (`capability`)

Power an agent or adapter may use inside defined limits. A capability can
describe repository work, external tools, skill packs, MCP-style adapters,
integrations, playbooks, or policy exports. It exposes allowed actions and
risk; it never grants final approval.

## Approval Rules (`authority_profile`)

The risk and approval requirements for a workspace or operating mode. Built-in
profiles are `solo-founder`, `team-safe`, and `strict`. Custom profiles can map
risk to a required approval count.

Approval rules never waive current check results. Independent review and human
approval may both be omitted only for R1/light/0-approval work with no allowed,
planned, queued, or actual external write. Other local R1/R2 work omits only
independent review and still requires one human.

## External Connection (`integration`)

A declaration for an optional external-service adapter. It stores an opaque
provider identifier, mode, owner, enabled state, allowed events and actions,
secret reference, risk, source boundary, and notes. A secret reference must be
indirect, such as `env:NAME`; the generic boundary does not read the value,
model provider API payloads, or call a provider.

Only a separately supported adapter may execute an exact approved and queued
action. Linear is the sole current example.

## External Action Preview (`integration_plan`)

A dry-run record for one external connection, task, event, and action. It keeps
the planned payload, source boundary, risk, actor, time, and approval
requirement visible before any supported adapter may execute it.

Recording or approving this preview updates only local history. It does not
read a secret or call the provider. A qualified person may mark it approved,
rejected, or canceled without sending it.

## Queued External Action (`integration_outbox_item`)

An approved external action waiting at the execution boundary. It copies the
approved payload preview, source boundary, risk, task, external connection,
event, action, enqueuing person, time, and status into an auditable record.
Queued means waiting, not sent.

Duplicate queue entries for one plan fail closed. A qualified person may cancel
a queued item. The record keeps `canceled_by`, `canceled_at`, and
`cancel_reason`, remains visible in history and detail views, and cannot support
a run record's claim that an external write was queued.

## Project (`workbench`)

A group of related goals, tasks, agents, people, sources, and output targets.
Projects help teams coordinate parallel work without making task IDs
chronological.

## Task (`work_item`)

One assignment with risk, operating intensity, allowed files and resources,
allowed sources and actions, output targets, forbidden actions, an acceptance
target, expected checks, explicit dependencies, a parallel policy, and optional
playbooks.

New quick-created tasks use opaque UUIDv4-backed IDs. An ID identifies a task;
it does not set priority or order. Explicit dependency edges determine order.
Historical and externally assigned IDs remain compatible.

## Work Idea (`proposal`)

An agent-safe plan that becomes a task only when a person approves it. It keeps
the proposed goal, owner, project, dependencies, file limits, checks, and
approval count, but grants no authority and stays out of the task queue. The
stable stored name remains `proposal`. A request to expand allowed work creates
a human question instead of silently widening those limits.

## Task Brief and Lock (`packet` and `claim`)

A task brief is the bounded instruction set created when an agent starts work.
Its portable session rules describe allowed and forbidden activity without
claiming to install an operating-system sandbox.

The accompanying task lock records local ownership. It uses an expiring
compare-and-swap Git lease so linked worktrees cannot own the same task at the
same time. An isolated worktree is only an execution boundary; it grants no
human approval or external-service permission.

## Run (`attempt`)

One execution session for a task. It records the actor, branch or workspace,
worker or model, base and head SHAs, changed files, allowed and forbidden
paths, task-lock lease information, and cleanliness.

## Run Record (`receipt`)

A human-readable account of a run: which sources it used, which actions it
took, which outputs it created, which external writes were only planned or
actually performed, what it did not do, and how to undo reversible changes.

A run record is not check results (`evidence`). It helps a person inspect,
undo, or continue work, and its exact hash becomes part of later check and
review bindings. A task cannot complete from a run record alone.

Planned external writes must name approved action previews, and queued writes
must name active queued actions. Pending, rejected, or canceled plans and
canceled queue items cannot support external-write claims. CLI-created run
records include a hash and may link to the previous run record for the task.

## Check Results (`evidence_run`)

Verification tied to one task and run. It records commands, status, head SHA,
outputs, output hashes, manifest hash, exact run-record hash, summary, and time.

Every record includes `output_binding_version`, requires at least one output, and
give every run-record output either its present digest or the exact absent
tombstone required by a declared delete intent. The manifest covers the
run-record hash, output-binding version, outputs, and verification fields, so a
change on either side invalidates the results.

Records without that version are rejected. Checks must be rerun to create a
current evidence record.

## Review Result (`review_verdict`)

An independent inspection. The stored verdicts remain:

- `accept-ready`
- `changes-requested`
- `needs-human-decision`
- `blocked`

A new `accept-ready` result is tied to the exact run state, check-results
manifest, run record, reviewed head, and task rules. Its proof hash also covers
the reviewer, verdict, findings, inspected checks, remaining risks, and time.
The result is immutable; any substantive change requires a new review.

Schema v2 rejects every unbound review result. All verdicts name and hash the
exact attempt, evidence, run record, task contract, proof, reviewed head, and
time they describe.

## Approval or Rejection (`human_decision`)

A human action tied to reviewed check results. It is separate from the review.
Its timezone-bearing timestamp establishes order, and its `decision` and
`status` must agree. Approval counts only for the exact review and evidence
references named in the record.

A decision made through an Approval Bundle also keeps the exact canonical pack
manifest, pack digest, member digest, subject digest, request digest, per-task
action, and canonical presentation schema, surface, and digest. One decision
record retains each manifest and presentation; every derived task decision
remains attributable and appears in the tamper-evident history. Copying a
member or presentation binding to another task fails validation. Approval Pack
v1 is unsupported and is not upgraded in place.

## Approval Bundle (`Approval Pack`)

An immutable status view that batches human attention without batching check
results. A bundle ties together the committed workspace restore point and
history head, ordered members, exact subjects and outputs, dependencies,
conflicts, risk, reversibility, approval requirements, proof references,
effects, resource estimates, status claim, and its own digest.

The manifest begins `parked`; evaluation derives each current task status.
Dependency bindings cover exact task rules, outputs, and the dependency chain.
Changing a dependency makes affected tasks stale even when a narrower bundle
omits that dependency. Changing an expected dependency, risk, or batch policy
also makes the bundle stale. Bundle approval never widens task limits.

The Approval Inbox adds display-only resolution information: current state,
owner, approval mode, and next safe action. Its primary action summarizes the
eligible group while leaving blocked, stale, and individual-only tasks visible.
These status views cannot grant approval or change the canonical manifest.

## Restore Point (`governed_checkpoint`)

A parked, human-only local recovery surface outside the ordinary work process.
Each committed tamper-evident-history state has a content-addressed restore
point. Restoration appends a `restoration` transaction containing the older
state; it never erases the original chain, later work, decisions, or reason.

Only effect-free local history can be restored. A later external write or sent
queued action blocks restoration before local state changes. Compensation must
be a new bounded task.

## Approval Record (`acceptance_record`)

The audit record for final human approval. It links the task, person, reviewed
head, check results, review, run-record hash, approval rules, required-approval
state, and reason.

Its timezone-aware `accepted_at` orders later approval or revocation records.
Approval for unfinished work must still match current output bytes before
execution. A completed task keeps and validates the exact stored proof for its
historical version; later authorized work does not make that older version the
current checkout.

## Result (`outcome`)

A learning record created after a task completes. It preserves what was useful,
what failed, and what follow-up is needed.
