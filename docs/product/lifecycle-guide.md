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
palari work add "Draft onboarding note" --create docs/onboarding.md
palari agent start --next --as PALARI-ID --json
# work inside the packet and commit the bounded result
palari agent advance WORK-ID --as PALARI-ID --json
```

The comment says `packet` because that is the stored machine name; operators
can read it as the task brief.

`--host` accepts `claude`, `codex`, or `cursor`. Claude and Codex install
portable instructions, the task-lock Git check, and a tested session-hook
adapter (strict no-claim on adoption). Cursor installs an advisory project rule
by default; pass `--strict-git` (or later `cursor install` / `git install`) for
the commit gate. Existing workspaces use
`palari init WORKSPACE-DIR --host HOST --as PALARI-ID --json`; initialization
still refuses an existing workspace when no host is given. Other unnamed agent
hosts may consume the provider-neutral session rules without a named profile.

Use repeatable `--create`, `--modify`, and `--delete` paths so every task says
what kind of file change it will make.

`start --next` chooses one task the queue already considers safe, writes its
task brief and portable session rules, and acquires its task lock (`claim`).
`advance` identifies the exact committed change range, checks each declared
create/modify/delete intent, runs verification, and records the run (`attempt`),
run record (`receipt`), check results (`evidence_run`), and closeout state.

It then completes eligible low-risk work or stops at independent review, human
approval, an external action, or a concrete blocker. Neither command creates an
independent review result or approval/rejection record (`human_decision`).

After the builder stops at review, a distinct review-only agent inspects the
current proof and records an advisory result. Palari rejects a reviewer choice
that would leave too few distinct qualified final approvers. After that review,
the human handoff presents the exact current task and a qualified person takes
one ordinary, presentation-bound action:

```bash
palari agent handoff WORK-ID --as PALARI-REVIEWER --mode review --json
# A human runs the exact emitted human_action_commands[].command.
```

The emitted `approve` command contains a machine-supplied presentation binding;
no record ID or digest is copied. It rechecks the current output, run record,
checks, review, journal, qualified actor, and effective final approval count
before its crash-safe decision-and-completion transaction. Review-required
work has an effective final count of at least one even if its stored numeric
count is zero; only the narrow automatic R1 exemption remains zero. Stale check
results, changed artifacts, missing required approvals, identity collisions,
individual-only work, and external actions remain blocked with a clear owner
and next step. Review and final approval stay attributable to different actors.

`queue --approval-inbox` and its digest-bound `human-decision pack` actions
remain available when a person intentionally uses the advanced or batched
surface.

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
`governance_journal`). A workspace without it is unsupported and cannot be
upgraded in place.

## Historical Retired Tasks

Stored `superseded` and `abandoned` tasks remain inspectable and never count as
completed work. The generic task-update command was removed in the minimality
pass; create an explicit successor task for new work.

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
agent's records and, when needed, the review or human handoff. Hooks deny both
the simple `approve` command and lower-level human-decision commands when they
are recognized in an agent session.

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
