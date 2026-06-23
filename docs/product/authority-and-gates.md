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
