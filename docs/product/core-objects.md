# Core Objects

Palari Company OS starts with a small set of explicit objects. The first
implementation keeps them as Python dataclasses and JSON records so the model
is easy to inspect and cheap to change.

## Goal

Company intent. Goals answer why work exists.

## Palari

Named AI work partner or workflow identity. A Palari has a scope, allowed
inputs, standards, memory sources, owner human, and forbidden actions.

## Human

Authority and accountability profile. Humans hold approval capabilities; AI
roles do not silently inherit them.

## Decision

Structured request for human judgment. Decisions keep important questions out
of vague status text.

## Source

Human-selected input that a Palari may use. Sources record label, provider,
generic URI or external id, access mode, owner human, allowed Palaris, selected
state, source readiness metadata, and last-read metadata. Readiness metadata
currently covers data class, authority, steward human, freshness expectation,
and whether redaction is required. Sources model the boundary of what was
available to the Palari; this v0 object does not connect to real providers yet.

## Playbook Source

External operating guidance that Palari may recommend while preparing work.
Playbook sources record label, provider, URI, pinned ref, license, enabled
state, and the explicit list of included playbooks. Superpowers compatibility
uses this object to link to allowed `SKILL.md` playbooks without making them
Palari authority.

## Capability

Governed power that a Palari or adapter may use. Capabilities can describe repo
work, external tools, skill packs, MCP-style adapters, integrations, playbooks,
or policy exports. They expose allowed actions and risk, but they do not grant
acceptance authority.

## Authority Profile

Risk and quorum posture for a workspace or operating mode. Built-in profiles
include `solo-founder`, `team-safe`, and `strict`; custom profiles can make the
relationship between risk and approval count explicit. Profiles never waive
current exact evidence. Independent review and human acceptance may both be
omitted only for R1/light/0-approval work with no allowed, planned, queued, or
actual external writes.

## Integration

Dry-run declaration for a possible external provider such as Slack, GitHub,
Jira, or email. Integrations record provider, mode, owner human, enabled state,
allowed events, allowed actions, secret reference, risk level, source boundary,
and notes. Secret references must be references such as `env:NAME`; Palari does
not read secret values or call providers in the v0 foundation.

## Integration Plan

Recorded dry-run payload preview for one integration, work item, event, and
action. Integration plans keep the exact planned payload, source boundary, risk,
actor, timestamp, and approval requirement reviewable before any future live
connector exists. Recording a plan appends history but still performs no live
provider call and reads no secret value. A qualified human may later mark the
plan approved, rejected, or canceled; that decision is history/audit state only
and still does not execute the external provider action.

## Integration Outbox Item

Queued dry-run boundary for an approved integration plan. An outbox item copies
the approved payload preview, source boundary, risk, work item, integration,
event, action, enqueuing human, timestamp, and status into an auditable record.
It means "this approved external action is waiting at the future execution
boundary," not "the external provider was called." Duplicate outbox entries for
the same plan fail closed. A qualified human can cancel a queued outbox item;
canceled items keep `canceled_by`, `canceled_at`, and `cancel_reason`, remain in
history/detail views, and cannot be used by receipts as queued external writes.

## Work Item

Scoped unit of work. It has risk, adaptive intensity, scope, allowed resources,
allowed sources, allowed actions, output targets, forbidden actions, acceptance
target, verification expectations, explicit dependency ids, parallel policy,
and optional recommended playbooks. New quick-created work uses an opaque
UUIDv4-backed ID. The ID is identity only: dependencies are explicit DAG edges,
and no numeric or lexical ID order grants priority or constrains execution,
review, acceptance, or integration. Historical and externally assigned IDs
remain compatible.

## Proposal

AI-safe planning record that can become a work item only when a human adopts it.
Proposals carry most work-item boundaries, but adoption creates the actual work
record explicitly. Scope expansion requests create decisions rather than
silently broadening a work item.

## Attempt

Concrete execution session for a work item. Attempts record actor, branch or
workspace, worker/model, base SHA, head SHA, changed files, allowed paths,
forbidden paths, claim lease metadata, and cleanliness. Local runtime claims
use an expiring compare-and-swap Git lease so linked worktrees cannot
simultaneously own the same work item. An isolated worktree is an execution
boundary only; it conveys no human or integration authority.

## Evidence Run

Proof attached to a work item and attempt. Evidence records commands, status,
head SHA, artifacts, artifact hashes, manifest hash, exact receipt hash,
summary, and timestamp. New records carry `output_binding_version`, require a
non-empty output/artifact set, and give every receipt output a present digest.
The manifest covers the
receipt hash, output-binding version, artifacts, and verification fields, so
changing either side invalidates proof. Pre-PCAW records without that version
remain readable but cannot support a new strict review or acceptance until
their evidence is refreshed.

## Review Verdict

Independent inspection. Verdicts are intentionally small:

- `accept-ready`
- `changes-requested`
- `needs-human-decision`
- `blocked`

New `accept-ready` verdicts are bound to the exact attempt state, evidence
manifest, receipt, reviewed head, and work contract. The binding has its own
proof hash, which also covers the reviewer, verdict, findings, inspected
checks, residual risks, and timestamp. Bound verdicts are immutable; a reviewer
records a new verdict after any substantive change. Schema v2 rejects an
unbound `accept-ready` verdict. Migration keeps legacy unbound non-accepting
verdicts inspectable and blocks any legacy accept-ready authority.

## Human Decision

Authority-bearing human action tied to reviewed evidence. This is separate from
the review verdict. Its timezone-bearing timestamp establishes ordering, while
its decision and status must agree. Approval counts only for the exact review
and evidence references it names.

Pack-bound decisions additionally retain the exact canonical pack manifest,
pack digest, member digest, subject digest, request digest, and per-item action.
Exactly one decision record retains the manifest; every derived member
decision remains independently attributable and journaled. Copying a member
binding to another item fails validation.

## Approval Pack

Immutable read model for batching human attention without batching evidence.
A pack binds the committed workspace/checkpoint and journal head, canonically
ordered members, exact subjects and outputs, dependencies, conflicts, risk,
reversibility, authority, proof references, effects, resource estimates,
lifecycle claim, and its own digest. The manifest begins `parked`; evaluation
derives current item states. Dependency bindings recursively cover the exact
contract, proof/artifact state, and dependency closure, so narrowing a pack
does not reduce dependency freshness. Expected in-pack completion remains
stable; later dependency mutation stales the pack. Pack approval cannot widen
any member boundary.

Inbox evaluation adds non-authoritative resolution metadata: the current
state, resolver class and owner, approval mode, and next safe action. A primary
action summarizes the eligible batch while keeping blocked, stale, and
non-batchable exceptions visible. These read models reduce ceremony; they do
not grant authority or alter the canonical pack manifest.

## Governed Checkpoint

Every committed governance-journal projection is a content-addressed
checkpoint. Restoring one creates a new `restoration` transaction with the old
projection; it does not delete the original chain, later work, decisions, or
the restoration reason. Only effect-free local chains are restorable. A later
external write or sent outbox transition blocks restoration before mutation;
compensation must be modeled as new governed work.

## Acceptance Record

Audit record for the final human acceptance gate. It links work, human,
reviewed head, evidence, review, receipt hash, authority profile, quorum state,
and reason so acceptance is visible beyond a status toggle. Its timezone-aware
`accepted_at` orders later acceptance or revocation records. Nonterminal
acceptance must still match current artifact bytes before execution. Terminal
acceptance retains and validates the exact stored proof for its historical
subject, so later authorized work does not pretend the old artifact version is
the current checkout.

## Receipt

Human-facing trust record for an attempt. A receipt says which sources were
used, what actions were taken, what outputs were created, which external writes
were only planned, what external writes actually occurred, what was not done,
and what undo references exist. Receipts are not governance evidence; they help
the user review, undo, or continue bounded work. The receipt hash is also part
of exact evidence/review proof for governed acceptance. A receipt without
current exact evidence cannot complete work. Planned external writes must
reference approved integration plans; queued external writes must reference
queued integration outbox items; rejected, canceled, or pending plans cannot be
used as receipt-backed external-write claims. Canceled outbox items also cannot
be used as receipt-backed queued-write claims. CLI-created receipts include a
receipt hash and can chain to the previous receipt for the same work item.

## Outcome

Learning record after work completes. Outcomes preserve what was useful, what
failed, and what follow-up is needed.
