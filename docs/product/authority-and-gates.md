# Permissions, Reviews, and Approvals

Palari separates what an agent or tool can do from what only a person may
approve. The stored model calls this the separation of capability and
authority.

Agents may prepare, inspect, draft, summarize, test, and recommend. People or
organizations keep final approval for deployments, policy changes, external
actions, spending, credential use, and other high-impact work.

## Human Approval

A person (`human`) record identifies:

- identity and aliases
- role
- ownership areas
- approval capabilities
- availability or capacity signals

High-risk work may require more than one qualified person's approval (a
`quorum` in stored records). Palari stops safely when the required people or
permissions are unclear.

The ordinary one-task approval surface is:

```bash
palari approve WORK-ID --as HUMAN-ID --json
```

The human first inspects the concise current handoff and runs its exact emitted
command. Palari supplies a `--presented` binding in that action, then derives
the singleton immutable Approval Pack and uses the existing transition and
journal machinery. It is eligible only for reversible local R1/R2 work when
one qualified person's action completes the effective final approval count.
For review-required work that count is at least one even when the stored
numeric count is zero; the R1/light/no-external automatic exemption remains
zero. This shortens navigation and local recordkeeping; it does not combine
review with approval, weaken final human authority, approve external actions,
or give an agent human permission. A manually entered bare command derives
current state at invocation rather than binding an earlier handoff.

`queue --approval-inbox` remains the advanced and batched surface. It names
only commands whose human actor is viable for every selected member. A task
with no feasible builder/reviewer/approver arrangement receives a diagnostic
and smallest safe correction, never a command already guaranteed to fail.

## Agents Can Prepare, Not Approve

An agent (`Palari`) record describes capabilities and limits, not final human
permission. An agent may ask a model or tool to perform a bounded task. It
cannot convert that run or its review into a human approval.

## Authority Plan

Before execution and review, Palari deterministically evaluates the task's
builder, every eligible independent reviewer, the required human capability,
and the number of distinct qualified final approvers left by each choice.

- A builder cannot review its own run.
- A Palari reviewer must be linked to the task goal and allowed to read every
  selected source.
- A human reviewer must be active and eligible for the task's project.
- A reviewer who would consume a required final approver is rejected.
- Final approvers exclude both the builder and selected reviewer.
- Missing roles fail before work or review with the smallest safe correction.

The starter workspace includes a review-only Palari so its sole human remains
available for final approval. That Palari has advisory review authority only:
it is outside the execution workbench and cannot provide human acceptance or
perform external writes.

## Allowed Tools and Actions (`capabilities`)

Capabilities describe usable power: repository writes, external tools, skill
packs, MCP-style adapters, integrations, playbooks, and policy exports. They
tell an adapter what it may read, write, or request.

A capability cannot approve a task. Exported policy explicitly forbids an
adapter from accepting work, expanding task limits, bypassing current checks,
or treating a review recommendation as human approval.

Use:

```bash
palari capability list --json
palari capability check WORK-ID --json
palari capability export-policy WORK-ID --json
```

## Approval Rules (`authority_profiles`)

An authority profile is the stored set of approval rules for each risk tier:

- `solo-founder`: R3+ work needs one counted human approval.
- `team-safe`: R3+ work needs one counted human approval; R5 needs two.
- `strict`: every risk tier needs a counted human approval.

Use:

```bash
palari authority profiles --json
palari authority check WORK-ID --profile team-safe --json
```

This command is advisory until the task declares the matching approval count.
Completion always requires current, exact, passing check results. Independent
review and human approval may both be omitted only for R1/light/0-approval work
with no allowed, planned, queued, or actual external write. Every other task
still requires independent review, explicit human approval, no open human
question, and no unsafe overlap with another task.

## Prior Context Is Not Permission

Shared context, prior decisions, results, and standards may guide an agent.
They never grant permission to approve, merge, deploy, spend money, change
policy, use secrets, or perform an external action.

When prior context conflicts with a current human instruction or approval rule,
Palari stops and asks a person.

## Test Rules Without Applying Them

Policy simulation may explain what a rule would do, identify missing checks,
or recommend safer defaults. A simulation is never real approval and never
activates a permission. Any future policy engine must keep simulated output
separate from human or organizational approval.

## External Action Boundaries

Generic tool execution is disabled. Provider-neutral integration commands only
preview, approve, and queue local records. Linear is the one current live
provider adapter. Its explicit send path executes only an exact approved and
queued action; a provider label alone never means live access.

Any additional live adapter must require:

- explicit resource and action permissions
- inspectable check results
- checks that stop safely when check results are missing
- human approval for high-risk or external actions
- no raw secret exposure to models

## Required Checks (`transition_checks`)

Palari runs deterministic checks before a trusted state change, not around
ordinary reading, planning, or local analysis.

These checks block proposal adoption, agent start, run closeout, check-results
creation, an `accept-ready` review, a human approval, task acceptance or
completion, external-action enqueue, and a live provider send when required
records are missing, stale, or mismatched.

No policy language, background service, or extra public command is needed. An
agent or adapter may prepare work, but Palari changes trusted state only after
it verifies the required workspace records.

The agent directive compiler is a display-only status-to-action view. It may
name the next owner and safe command, but it cannot perform a trusted change.
`agent start --next`, `agent advance`, and durable `agent release` still pass
the existing start, check-results, history, file-boundary, and task-lock
checks. None may create an independent review or human decision.

## Review Checklists (`gate_profiles`)

Gate profiles are parked, read-only review checklists rather than part of the
normal work path. They help a reviewer name the failure mode to inspect. They
do not create tasks, task locks, reviewer notes, approval flows, or authority.

Built-in profiles retain their exact IDs:

- `prompt-authority`: untrusted source, OCR, image, or user text must not become
  system or developer prompt authority.
- `source-boundary`: work must use only selected or allowed sources, and run
  records must report source use honestly.
- `external-write`: dry-run, planned, queued, and actual external writes must
  remain distinct.
- `human-approval`: review recommendations, required approval count, and human
  permission must not be bypassed.
- `deploy-runtime`: production, beta, runtime data, storage, provider routing,
  secrets, and deployment boundaries require explicit check results.
- `privacy-multimodal`: images, OCR, screenshots, uploads, audio, and video must
  remain minimized, bounded, and untrusted.
- `product-overclaim`: public copy must not claim more than the implemented
  product can do.

Use:

```bash
palari gate profiles --json
palari gate recommend WORK-ID --json
```

The output contains the reviewer role, inspection focus, blocker checklist,
required check results, and `accept-ready` standard. A recommendation never
means the task is approved.

## Final Approval Records (`acceptance_records`)

`palari approve WORK-ID --as HUMAN-ID` is the readable ordinary
final-human-approval surface for one eligible reversible local task; the
handoff emits it with a presentation binding. It composes the pack transaction
described below and writes a decision record (`human_decision`) plus approval
record only after checking current results, a current `accept-ready` review,
the person's capability, open questions, task overlap, effective final count,
and the required check-results/run-record (`evidence`/`receipt`) manifest
integrity. `palari work accept` remains the parked lower-level single-task
recovery surface.

The exact protocol and field names remain important here. The review must carry
the current `palari.review_binding.v1` binding for the exact `attempt`,
`evidence`, `receipt`, `reviewed_head`, and task rules (`work_contract`). Changing the task
rules, run, check results, or run record makes the review stale. A later
timezone-ordered negative decision from the same person revokes that person's
earlier approval. Approval counts only for the exact review and evidence
references; contradictory or ambiguously ordered decisions stop safely. The
review proof hash also covers the reviewer-authored verdict context, and an
exact-bound completed task requires its matching approval record
(`acceptance_record`).

`palari human-decision pack` is the advanced human-only approval surface, not
an agent shortcut. It ties one attributable action to an immutable Approval Pack
and the exact presentation the person inspected, then creates one decision
record per selected task. Pack v3 adds both declared and effective final
approval counts to each exact member. The reader remains compatible with pack
v2; v1 is unsupported. Decision records retain proof references, member and
subject digests, presentation schema, surface, and digest, with one canonical
presentation artifact per action. Missing or unsupported presentation-bound
permission stops safely instead of being upgraded.

The same rules for reviewer independence, current check results, human
capability, and required approval count apply to individual and `approval-pack`
decisions. Stale or individual-only tasks cannot become approved through a
bundle. The Approval Inbox names the available modes. `approve-eligible` is one
exact, attributable action over separately reviewed tasks.

Batch eligibility comes only from structured facts. R1/R2 local tasks without
external-write permission or current external-action records may be batched.
R3/R4/R5, unknown risk, and every external action require individual approval.
Titles and descriptions cannot change those rules. There is no combined
review-and-approve mode: independent review and final approval remain separate
roles.

The human command records approval and performs only the deterministic local
completion that approval already permits. Both changes share one crash-safe
history transaction. Missing approvals remain blocked; the command creates no
review, extra vote, external action, or wider permission.

Independent review may be attributed to a declared agent when that agent did
not build the work, is linked to its goal, and may read every selected source.
The result remains advisory. An agent reviewer can never count as a human
approver; approval, rejection, and Approval Pack actions remain attributable
to a person.

`palari work complete` retains the final status check. Outside the narrow
R1/light/0-approval/no-external-action exception, it may derive a missing
approval record from the latest qualified human-decision record. Palari prepares that
record before checking completion and writes both in one successful change, so
invalid or stale approval leaves no partial record. `agent advance` may invoke
this mechanical completion after approval exists; it never creates the review
or human-decision record. The exception waives only review and human approval, never
current exact check results.

After a `human_decision` record or `work accept`, one bounded automatic-finishing loop
may apply only the completion already authorized. It detects cycles and lack of
progress and stops at review, human approval, external state, an iteration
limit, or an error. A failed automatic step keeps the human record, reports the
next safe action, and creates no partial derived approval or final status.

Generic record updates cannot set a final task status, rewrite trusted run
fields, or change a review tied to an exact version.

## Signing-Key Custody

Signing keys carry real permission; they are not convenience tokens.

- Never expose raw keys to an AI model or chat context.
- People or organizations own key custody.
- Agents may request only bounded signing operations through explicit tools.
- Team use needs rotation, revocation, auditability, and recovery.
- Signed checks may supplement required human approval; they never replace it.

Complex key custody remains outside the current product, but the stored model
leaves room for it.
