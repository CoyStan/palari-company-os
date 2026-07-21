# Work Process

Palari uses one understandable path:

```text
goal
-> task and limits
-> run
-> run record and checks
-> independent review when required
-> human approval when required
-> result
```

The JSON schema retains the machine terms `work_item`, `attempt`, `receipt`,
`evidence_run`, `review_verdict`, `human_decision`, and `outcome`. Commands and
protocol files continue to use those exact names where compatibility requires
them.

## Approve Several Ready Tasks Together

Palari can prepare several separately reviewed tasks for one short human
approval session:

```text
bounded preparation -> separately checked and reviewed tasks
-> immutable Approval Pack -> one exact human approval action
-> eligible local completion -> result
```

The Approval Pack is an approval bundle, not shared proof. Every task keeps its
own limits, run, run record, check results, review, decision, and history entry.
A dependency change makes affected tasks stale even when a smaller pack omits
that dependency; unrelated current tasks remain valid. A risk or batch-policy
change also makes the exact pack stale. External or irreversible actions always
keep their individual approval step.

## Normal Path

Palari creates and links the required records instead of asking an agent to
copy IDs and digests by hand:

```bash
palari init --host codex
palari work add "Draft onboarding note" --write docs/onboarding.md
palari agent start --next --as PALARI-ID --json
# work inside the packet and commit the bounded result
palari agent advance WORK-ID --as PALARI-ID --json
```

The comment says `packet` because that is the stored machine name; operators
can read it as the task brief.

`--host` accepts `claude` or `codex`. Initialization installs portable
instructions, the task-lock Git check, and a tested session-hook adapter.
Existing workspaces use `palari init WORKSPACE-DIR --host HOST --as PALARI-ID
--json`; initialization still refuses an existing workspace when no host is
given. Other agent hosts may consume the provider-neutral session rules without
being advertised as supported profiles.

The presence-only `--write` form requires an output to exist. Use repeatable
`--create`, `--modify`, and `--delete` when the exact change type matters; exact
intents cannot be mixed with `--write`.

`start --next` chooses one task the queue already considers safe, writes its
task brief and portable session rules, and acquires its task lock (`claim`).
`advance` identifies the exact committed change range, checks each declared
create/modify/delete intent, runs verification, and records the run (`attempt`),
run record (`receipt`), check results (`evidence_run`), and closeout state.

It then completes eligible low-risk work or stops at independent review, human
approval, an external action, or a concrete blocker. Neither command creates an
independent review result or approval/rejection record (`human_decision`).

After a separate current review, a qualified person uses one inbox and one
exact action:

```bash
palari queue --approval-inbox --json
# inspect the emitted presentation, then run its exact
# `palari human-decision pack ...` command once
```

The action is tied to the exact pack and presentation digests. Stale check
results, missing required approvals, individual-only work, and external actions
remain blocked with a clear owner and next step. Review and final approval stay
attributable to different actors.

## Stop Safely

When a run stops before check results are ready, record why before releasing
the task lock:

```bash
palari agent release WORK-ID --as PALARI-ID \
  --reason "Waiting for product direction" \
  --next-action "Ask the founder to choose the final wording" --json
```

This records one blocked run and its next safe action, then releases ownership.
It creates no run record, check results, review, approval, completion, or result.
The workspace must already have writable tamper-evident history (the
`governance_journal`). A legacy workspace receives the exact explicit `history
--checkpoint` activation action; Palari does not pretend the earlier history is
continuous.

## Retire Obsolete Tasks Without Calling Them Complete

When an unclaimed task is genuinely obsolete, give it an explicit final status
through the existing update command:

```bash
palari work update WORK-OLD \
  --status superseded \
  --terminal-reason "A narrower contract now owns the objective." \
  --successor-work-item-id WORK-NEW --json

palari work update WORK-EXPERIMENT \
  --status abandoned \
  --terminal-reason "The experiment no longer earns operator attention." --json
```

`superseded` and `abandoned` close the task without claiming success. They do
not create a run, run record, check results, review, human-decision record,
approval, or result. A reason is required. A successor is optional, but it must name a
different existing task.

Palari rejects successor cycles, retirement during an active run, retirement
with an open decision or unresolved external action, and retirement while other
tasks still depend on the old task. Point each dependent task to the explicit
successor first.

Retired tasks disappear from the ordinary queue, `agent next`, and Approval
Inbox. They remain visible through `queue --include-closed` and `detail`, and an
explicit `agent start` cannot claim them. Historical check and review records
remain unchanged.

## Lower-Level Repair Commands

The record-by-record authoring commands remain available for explicit workspace
repair and expert fixture construction. They are parked tools, not a second
normal work process, an agent fallback, or a compatibility promise. The command
reference lists them separately.

Supported agent hooks may prepare a proposed task or ask a person to expand a
task's limits. They cannot create runs, run records, check results, reviews,
approvals, human decisions, or results directly. `agent advance` derives the
agent's records and, when needed, the exact Approval Inbox action for a person.

Every successful completion uses the same shared rules and checks: check
results must be complete and current, output and task-rule bindings must match,
required review must be independent, required human approval must match the
exact version, dependencies must be complete, and external actions must be
safe. A substantive change invalidates earlier derived approval and completion.

PCAW v1 remains the portable verification format. `proof export` creates its
canonical statement, and `proof verify` calculates the real state locally and
offline instead of trusting the claimed result. The protocol keeps exact terms
such as subject, artifact, digest, and predicate. Workspace `create`, `modify`,
and `delete` intents are local verification facts; PCAW v1 does not claim to
prove deletion history across machines.

Restoring a point in the tamper-evident history and running a full continuity
audit are explicit recovery actions. Restoration appends history instead of
rewriting it and stops safely if it could repeat an external action.
