# Permissions, Reviews, and Approvals

Palari separates capability—what an agent or adapter may do—from authority—what
only a qualified person may approve. A task never gains authority from a model,
a tool, a review recommendation, or prior context.

## Authority Plan

Before execution and review, Palari evaluates the task's builder, eligible
independent reviewers, required human capability, and distinct final approvers.

- A builder cannot review its own run.
- An agent reviewer must be linked to the goal and allowed to read every
  selected source.
- A human reviewer must be active and eligible for the project.
- A reviewer cannot consume the only required final approver.
- Final approvers exclude the builder and selected reviewer.
- Missing roles stop work with the smallest safe correction.

`palari init` creates a review-only agent so a solo maintainer can preserve the
builder → independent reviewer → founder separation. Older workspaces receive a
focused `palari reviewer add ...` correction from `agent next` when needed.

## Current Checks

Every completion requires passing check results tied to the exact run and
output version. Risk changes review and approval requirements; it never waives
checks.

Only R1/light work with zero required approvals and no external action may
complete directly after current exact checks. Other local R1/R2 work skips
independent agent review and still stops for one human. R3+ work and any
external-write surface keep independent review.

`agent advance` owns run, run-record, and check-result creation. It checks the
Git head, repository cleanliness, exact path intents, output bytes, task
contract, source/action limits, and configured verification profiles before it
records proof atomically.

## Independent Review

The reviewer starts a review-mode assignment, inspects its handoff, and runs one
exact emitted `review record` action. An `accept-ready` result is bound to:

- the run and reviewed Git head;
- check results and their artifact manifest;
- the run record;
- the task contract; and
- the reviewer's verdict context.

Changing any bound input makes the review stale. Exact-bound reviews are
immutable; record a new review for a changed result.

```bash
palari agent start WORK-ID --as PALARI-REVIEWER --mode review --json
palari agent status WORK-ID --as PALARI-REVIEWER --mode review --json
# run one exact agent_action_commands[].command from that status projection
```

An agent reviewer remains advisory. It cannot count as a human approver.

## Human Approval

The ordinary one-task surface is the exact presentation-bound command emitted
by a handoff:

```bash
palari approve WORK-ID --as HUMAN-ID --json
```

Before writing, Palari rechecks current artifacts, check results, run record,
review, journal continuity, capability, approval count, and exact presentation.
The command records the human decision and approval, then performs only local
completion that the decision already permits. It creates no review, extra vote,
external action, or wider permission.

`queue --approval-inbox` and `human-decision pack` are the advanced batch and
recovery surfaces. A pack binds one attributable action to one immutable member
set and one exact human presentation. Mixed approve/reject/defer decisions are
explicit. Agents may show pack actions but must not run them.

## Effective Approval Count

For ordinary local work, the effective final approval count is at least one,
even when the stored numeric count is zero. Independent agent review is skipped
for local R1/R2 with no external-write surface. The only zero-person completion
is the narrow R1/light/no-external-action case.

High-risk work may require multiple distinct qualified people. A person's
stored approval capabilities must cover the task's required capability, and
availability or project eligibility can disqualify them. Missing or ambiguous
authority fails closed.

## External Actions

No review or task approval directly executes an external write. The action must
also have:

1. a provider-neutral integration plan;
2. explicit human approval of that plan;
3. a queued outbox item; and
4. a provider adapter that rechecks the queued item before sending.

An adapter cannot widen allowed files, sources, or actions. Linear is the only
current live provider path.

## Tamper-Evident Decisions

Approval and review mutations go through the v2 governance journal. Prepared
and committed records bind the before/after workspace digests, actor, command,
affected objects, and timestamp. Corruption, a partial transaction, changed
workspace bytes, stale presentation, or missing history continuity stops the
operation.

PCAW export makes the final governance case independently verifiable offline.
PCAW v1 is unsigned: it verifies consistency and artifact integrity, not real-
world identity or key custody.
