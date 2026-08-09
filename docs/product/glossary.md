# Plain-Language Glossary

Palari uses familiar words in instructions and explanations. Parentheses show
the exact machine term used by JSON records, protocol fields, or older commands.
For the stored data model, see [Stored Records](core-objects.md).

All terms fit under Goals, Team, Work, Checks, or Limits. New labels use short,
common words; exact old machine names appear only when a reader needs them.

## Goal

The reason a piece of work exists.

## Agent (`Palari`)

A named AI work partner with a clear job and limits. An agent may do and review
work when allowed, but it cannot supply human approval.

## Person (`human`)

A real person who owns, reviews, or approves work. Palari uses `human` in stored
records and commands because it must distinguish people from agents.

## Question for a Person (`decision`)

A choice that needs an explicit human answer before work can continue.

## Source

A selected file, note, document, or other context that a task is allowed to
read.

## Playbook (`playbook_source`)

Outside operating guidance that Palari may recommend. It can explain how to
work, but it cannot grant permission or approval.

## Allowed Tool or Action (`capability`)

Something an agent or adapter is allowed to use within stated limits. A
capability does not grant permission to approve completed work.

## Approval Rules (`authority_profile`)

The rules connecting risk to the number and kind of human approvals a task
needs. Stored profiles include `solo-founder`, `team-safe`, and `strict`.

## External Connection (`integration`)

A declared boundary for an external service. Its provider identifier is opaque;
the record alone does not call the service.

## External Action Preview (`integration_plan`)

A dry-run record showing the exact external action Palari would request. It
does not perform that action.

## Queued External Action (`integration_outbox_item`)

An approved external action waiting at the send boundary. Queued does not mean
sent, and only a supported adapter may execute it.

## Project (`workbench`)

A group of related goals, tasks, agents, people, sources, and output targets.

## Task (`work_item`)

One assignment with an objective, allowed files, sources, and actions, expected
outputs, required checks, and stop conditions.

## Proposed Task (`proposal`)

Planned work that has not become an active task. A person must adopt it before
an agent can treat it as assigned work.

## Task Brief (`packet`)

The bounded instructions returned when an agent starts a task. A task brief
tells the agent what it may read, change, and do.

## Session Rules (`session_contract`)

A portable, provider-neutral form of the task limits. It declares boundaries;
it is not an operating-system sandbox.

## Task Lock (`claim`)

A local, expiring assignment that prevents two linked worktrees from owning the
same task at once.

## Run (`attempt`)

One concrete try at completing a task. It records the actor, repository state,
changed files, and task limits.

## Run Record (`receipt`)

A human-readable account of what a run read, changed, skipped, left undoable,
planned externally, or actually sent externally.

## Check Results (`evidence_run`)

The commands, results, output hashes, run-record hash, and exact commit checked
for one task. Current check results are required before completion.

## Review Result (`review_verdict`)

An independent review tied to the exact run and check results. The stored
values remain `accept-ready`, `changes-requested`,
`needs-human-decision`, and `blocked`.

## Approval or Rejection (`human_decision`)

A human choice tied to the exact reviewed version. It may approve, reject, or
block work, depending on the stored `decision` and `status` values.

## Approval Record (`acceptance_record`)

The audit record showing which qualified person approved which exact review and
check results under which approval rules.

## Approval Bundle (`Approval Pack`)

An immutable group of separately checked and reviewed tasks prepared for one
short human approval session. Bundling attention never combines evidence,
widens task limits, or makes blocked work eligible.

## Approval Inbox

The status view that shows tasks awaiting human attention. It may present one
exact action for eligible tasks while listing stale, blocked, or individual-only
tasks separately.

## Result (`outcome`)

What was learned after a task closes, including whether the work helped,
failed, or created follow-up work.

## Status (`lifecycle_state`)

Where a task currently stands. Operator-facing status should normally be one of
ready, in progress, blocked, needs review, needs approval, or complete. Stored
enum values remain unchanged.

## Required Check (`transition_gate`)

A deterministic rule Palari evaluates before a trusted state change, such as
starting, accepting, completing, queuing, or sending work.

## Status View (`projection` or `read_model`)

A derived explanation of recorded state. A status view may show the next safe
action, but it cannot approve work or change trusted state.

## Tamper-Evident History (`governance_journal`)

The append-only, hash-chained record of successful workspace changes. It can be
replayed and checked for corruption, missing entries, reordering, and
divergence.

## Restore Point (`governed_checkpoint`)

A content-addressed saved workspace state in the tamper-evident history.
Restoring it appends a new history entry; it never erases later history.

## Verification Report (`proof`)

A portable statement that another party can check offline. PCAW v1 uses exact
protocol terms such as subject, artifact, digest, predicate, and attestation;
those terms remain unchanged in protocol documentation and data.
