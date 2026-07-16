# Authority And Gates

Palari Company OS separates capability from authority.

AI workers can prepare, inspect, draft, summarize, test, and recommend. Humans
or organizations hold authority for acceptance, deployment, policy activation,
broker side effects, spending, credential use, and other high-impact actions.

## Human Authority

Human profiles should identify:

- identity and aliases
- role
- ownership areas
- approval capabilities
- availability or capacity signals

For high-risk work, quorum can require more than one qualified human. The
system should fail closed when authority is unclear.

## AI Roles

AI roles describe capability and bounds, not final authority. A Palari can ask a
model or tool to perform bounded work, but the Palari cannot convert that work
into an authority-bearing decision without the required human action.

## Capabilities

Capabilities describe usable power: repo writes, external tools, skill packs,
MCP-style adapters, integrations, playbook sources, or policy exports. A
capability can tell an adapter what it may read, write, or request.

Capabilities do not own the acceptance gate. The exported policy explicitly
says adapters may not accept work, expand scope, bypass evidence, or treat a
review recommendation as human authority.

Use:

```bash
palari capability list --json
palari capability check WORK-ID --json
palari capability export-policy WORK-ID --json
```

## Authority Profiles

Authority profiles describe how much human judgment a risk tier needs. Built-in
profiles:

- `solo-founder`: lightweight founder mode; R3+ work needs human acceptance.
- `team-safe`: default team mode; R3+ work needs human acceptance and R5 needs
  two approvals.
- `strict`: every risk tier needs human acceptance.

Use:

```bash
palari authority profiles --json
palari authority check WORK-ID --profile team-safe --json
```

The check is advisory until the work item declares the matching approval count,
but the acceptance and completion gates still enforce fresh evidence, review,
human decisions, open-decision blocking, and scope-overlap blocking.

## Memory Is Context, Not Authority

Shared memory, prior decisions, outcomes, and standards can guide a Palari.
They do not grant permission to accept, merge, deploy, spend money, change
policy, use secrets, or perform external side effects.

If memory conflicts with current explicit human instruction or authority
configuration, the system should fail closed and ask for a decision.

## Policy Simulation

Policy simulation is allowed as analysis. It can say what would happen under a
policy, identify missing controls, or recommend safer defaults.

Policy simulation is not real acceptance and does not activate authority. A
future policy engine must preserve the separation between simulated policy
output and human or organizational authority.

## Broker Boundaries

Broker/tool side effects are disabled by default in the first Palari Company OS
slice. The model can represent that a work item would need broker access, but
it must not imply that access is live.

Future broker integration should require:

- explicit resource/action permissions
- inspectable evidence
- fail-closed checks
- human approval for high-risk or external side effects
- no raw secret exposure to models

## Transition Checks

Hard gates live at trust-changing transitions, not around ordinary reading,
planning, or local analysis.

Transition checks are internal, deterministic predicates used by existing
mutation commands. They block proposal adoption, agent start, attempt closeout,
evidence and accept-ready review records, human acceptance decisions, work
acceptance/completion, integration enqueue, and live provider sends when the
required records are missing or stale.

This keeps Palari small: no policy DSL, background service, or new public
command is needed. The rule is simply that AI or adapters can prepare work, but
they cannot move trusted state forward unless Palari can verify the required
workspace records.

## Review Gate Profiles

Gate profiles are lightweight review contracts. They recover the useful part of
the older Palari v05 practice: a reviewer should know which failure mode they
are hunting before they inspect work.

Gate profiles do not create tickets, claims, leases, reviewer notes, acceptance
flows, or authority. They are read-only recommendations for the kind of review a
work item deserves.

Built-in gates:

- `prompt-authority`: untrusted source, OCR, image, or user text must not become
  system/developer prompt authority.
- `source-boundary`: work must use only selected or allowed sources, and receipts
  must report source use honestly.
- `external-write`: dry-run, planned, queued, and actual external writes must
  remain distinct.
- `human-approval`: review recommendations, approval quorum, and human authority
  must not be bypassed.
- `deploy-runtime`: production, beta, runtime data, storage, provider routing,
  secrets, and deploy boundaries require explicit evidence.
- `privacy-multimodal`: images, OCR, screenshots, uploads, audio, and video must
  stay minimized, bounded, and untrusted.
- `product-overclaim`: public or user-facing copy must not claim capabilities
  stronger than the implemented product.

Use:

```bash
palari gate profiles --json
palari gate recommend WORK-ID --json
```

The output includes a compact reviewer contract: reviewer role, what to inspect,
blocker checklist, required evidence, and the accept-ready standard. A gate
recommendation never means the work is accepted.

## Acceptance Records

`palari work accept` is the explicit final human acceptance command. It records
a human decision and an acceptance record after checking fresh evidence, fresh
accept-ready review, human capability, open decisions, scope overlap, and
mandatory evidence/receipt manifest integrity. The review must carry the
current `palari.review_binding.v1` binding for the exact attempt, evidence,
receipt, reviewed head, and work contract. A later contract, attempt, evidence,
or receipt change makes it stale. A later timezone-ordered negative decision by
the same human revokes that human's earlier approval from quorum. Approval is
counted only for the exact review and evidence references; contradictory or
ambiguously ordered decisions fail closed. The review proof hash also
covers reviewer-authored verdict context, and exact-bound terminal work
requires its matching acceptance record.

`palari human-decision pack` is an additional human-only acceptance surface,
not an agent shortcut. It binds one attributable action to an immutable pack
and derives one decision record per selected member. Each decision retains its
own proof references and exact member/subject digest. The governance kernel
counts `approval-pack` decisions under the same capability, reviewer
independence, currency, and quorum rules as individual human decisions.
Non-batchable and stale members cannot become approved through the bundle.
The Approval Inbox names its available approval modes. The normal
`approve-eligible` mode is one exact attributable action over independently
reviewed members. External or irreversible effects remain individual. A
combined review-and-accept mode is not available under the current policy:
independent review and acceptance remain distinct roles.

Independent review may be attributed to a declared Palari when that Palari is
not the builder, is linked to the work goal, and is allowed to read every
selected source. That verdict remains advisory. Palari reviewer identities are
never human approval candidates and never satisfy human quorum; acceptance,
rejection, and Approval Pack actions remain attributable human authority.

`palari work complete` keeps the terminal status gate. For non-receipt-ready
work, it can derive a missing acceptance record from the latest qualified human
decision. That record is projected before the complete gate and written in the
same successful mutation as terminal state, so invalid or stale authority does
not leave a partial acceptance behind. `agent advance` may invoke this
mechanical transition after authority exists; it does not create the review or
human decision.
Accepted human-decision and work-accept authoring functions invoke a shared,
bounded fixed-point driver after recording the human action. The driver applies
only the already-authorized completion transition, detects cycles and
no-progress, and stops at review, human authority, external state, iteration
exhaustion, or an error. A failed automatic transition does not erase the human
record; it returns an actionable safe stop and creates no partial derived
acceptance or terminal state.
Generic record updates cannot set terminal work state, rewrite attempt trust
fields, or mutate an exact-bound review.

## Gate And Key Custody

Gate keys are authority-bearing infrastructure, not convenience tokens.

Default stance:

- raw keys must not be exposed to AI models or chat context
- humans or organizations own custody
- AI workers can request bounded signing operations only through explicit tools
- rotation, revocation, auditability, and recovery matter for team use
- signed gates supplement human acceptance and quorum; they do not replace them

Complex key custody is intentionally out of scope for the first repo slice, but
the model leaves room for it.
