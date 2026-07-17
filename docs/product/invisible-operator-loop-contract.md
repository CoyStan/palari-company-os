# Invisible Operator Loop v1 — Completion Contract

Work item: `WORK-D18949EABBAC41AA9C0FB3D57BD4B88F`

Branch: `codex/invisible-operator-loop`

Merged baseline: `1e3649da22c7b053d1471bb1ce98112c0289ef67`

Work-item setup head: `c528f2aa39227ad4bcdc269540446fe73f0d42d9`

Status vocabulary is `pending`, `in progress`, `completed`, or `blocked`.
Every completed checkbox must name exact committed proof. The product rule is:
**derive ceremony; preserve judgment**.

## Baseline

- `./scripts/verify.sh`: 792 tests across 44 modules, style, trusted-code
  manifest, and 18/18 PCAW vectors passed in 92.08 seconds.
- GitHub Actions exposed one environment-coupled assertion: a clean checkout
  has no activated dogfood journal, while the test required exactly one journal
  read. The production behavior was not implicated.
- Dogfood journal: 39,889,344 bytes, 150 records, 75 committed transactions.
  Three exact verification runs had a 4.88-second median and approximately
  278 MB peak RSS. One journaled mutation currently performs roughly two full
  scans.
- Existing opaque IDs and independent claims already permit unrelated work to
  proceed without chronological merge order.

## Before Interaction Counts

Counts are Palari invocations, excluding editing, tests, and Git commands.

| Journey | Before | Judgment that must remain |
| --- | ---: | --- |
| Adopt a repository | 1 (`init`) | none |
| Join an existing repository | 1 read-only orientation command | none |
| Select and start ready work | 2–3 | none |
| Complete R2+ bounded work | 5–6 after editing | none until review |
| Independent review | 2 | one independent verdict |
| Accept a reversible result | 2 | one human decision |
| Narrow, reject, or defer | 2 | one human decision |
| Diagnose a blocker | 1, but 24 lines and five alternatives | none |
| Enable legacy journal continuity | 1 | explicit operator opt-in |
| Complete ten unrelated R2 items | about 80–90 before review | one review per item |

## Required Outcomes

- [ ] **One authoritative directive compiler**
  - Required outcome: one pure deterministic function returns lifecycle state,
    owner, automatic transitions, human/reviewer boundary, one safe action,
    concise diagnostics, and optional proof detail from current workspace truth.
  - Objective evidence: parity tests cover ready, active, blocked, stale,
    review-required, human-decision-required, accepted, and completed states;
    existing transition checks remain the mutation authority.
  - Verification: focused directive, kernel, read-model, and transition tests.
  - Current status: in progress.
  - Exact committed proof: pending exact commit.

- [ ] **One entry action**
  - Required outcome: `palari agent start --next --as PALARI-ID` selects exactly
    one safe item, compiles its packet and portable contract, and claims it in
    one idempotent command. Explicit `start WORK-ID` remains compatible.
  - Objective evidence: ready, no-ready, ambiguous, review-only, foreign-claim,
    repeated, and parallel-unrelated interaction tests.
  - Verification: agent runtime/packet/CLI tests and golden terminal transcript.
  - Current status: pending.
  - Exact committed proof: pending exact commit.

- [ ] **One convergence action**
  - Required outcome: `palari agent advance WORK-ID` is the ordinary agent-safe
    fixed-point action. It derives deterministic attempt, receipt, evidence,
    verification, handoff, and terminal bookkeeping, then stops only for an
    independent verdict, exact human authority, external effects, or a blocker.
  - Objective evidence: R1 and R2+ journeys require no copied IDs/digests and
    post-quorum completion requires no follow-up command; retries are idempotent.
  - Verification: advance, convergence, authority, crash, and interaction tests.
  - Current status: pending.
  - Exact committed proof: pending exact commit.

- [ ] **Deletion and parking are first-class**
  - Required outcome: declared create/modify/delete intent is enforced against
    exact Git state; a deletion is proof, not a missing output. `agent park`
    durably records why work stopped and its next safe action before releasing
    the claim, and repeated recovery is safe.
  - Objective evidence: legacy presence-required behavior is unchanged;
    traversal, symlink, undeclared deletion, fake tombstone, foreign claim,
    interrupted park, and retry cases fail closed or recover safely.
  - Verification: schema parity, file-boundary, proof, journal-crash, and park
    interaction tests.
  - Current status: pending.
  - Exact committed proof: pending exact commit.

- [ ] **One concise human surface and one exact action**
  - Required outcome: default inbox/handoff output states what is happening,
    whether it is safe, who owns the next judgment, and exactly one bound action.
    Explain/JSON views retain every digest and proof detail. Existing one-action
    convergence remains atomic and fail-closed.
  - Objective evidence: approve, narrow, reject, defer, stale presentation,
    non-batchable, changed evidence, and partial quorum tests; no autonomous
    review or human decision is introduced.
  - Verification: approval pack/presentation/read-model interaction tests.
  - Current status: pending.
  - Exact committed proof: pending exact commit.

- [ ] **Activation and legacy continuity stay one command**
  - Required outcome: new repository initialization activates the operating
    contract and journal once; legacy checkpoint activation remains explicit,
    idempotent, and one command; provider-specific hooks remain optional.
  - Objective evidence: install/init and checkpoint interaction tests, with no
    new hook or provider dependency.
  - Verification: onramp, journal, install-smoke, and docs tests.
  - Current status: pending.
  - Exact committed proof: pending exact commit.

- [ ] **Progressive disclosure and shared diagnostics**
  - Required outcome: the default blocked view fits within 12 lines and exposes
    exactly state, safety, owner, explanation, and one next action. JSON and
    explicit detail retain the complete current proof and alternatives.
  - Objective evidence: text/JSON semantic-parity snapshots for ready, blocked,
    stale, review, human, and completed states.
  - Verification: CLI output, public-surface, and docs tests.
  - Current status: pending.
  - Exact committed proof: pending exact commit.

- [ ] **Performance follows the interaction**
  - Required outcome: small-workspace reads remain below 0.5-second median;
    the 40 MB fixture verifies at or below 1.0-second median and 100 MB RSS, or
    the contract records why a staged journal-format migration is safer. One
    successful metadata mutation targets no more than 2 seconds of journal
    overhead. Complete verification may not exceed 101.29 seconds (10% over
    this merged baseline) without exact safety justification.
  - Objective evidence: repeatable three-run medians, slowest-module report,
    and before/after interaction counts for all ten journeys.
  - Verification: timing harness plus complete gate.
  - Current status: pending.
  - Exact committed proof: pending exact commit.

- [ ] **Compatibility, security, documentation, and review**
  - Required outcome: existing commands, schemas, fixtures, PCAW v1, authority,
    scope, journal, and Claude adapter behavior remain compatible unless an
    explicit versioned migration is proven necessary. No dependency, provider,
    external write, push, merge, deployment, autonomous review, or human
    acceptance is added. Three journey-first documents replace ceremony-first
    guidance without removing the advanced reference.
  - Objective evidence: focused security tests, schemas/fixtures, public CLI,
    docs/examples, full verification, isolated wheel smoke, exact changed-path
    audit, and a fresh independent exact-head ACCEPT.
  - Verification: `palari docs check --json`, `./scripts/verify.sh`,
    `./scripts/install_smoke.sh`, and independent review report.
  - Current status: pending.
  - Exact committed proof: pending exact commit.

## Explicit Human And Reviewer Boundary

The implementation may derive, verify, summarize, checkpoint where policy
already permits, and execute deterministic local transitions. It may not create
an independent verdict, a human decision, scope expansion, an external effect,
a push, merge, deployment, release, signature, or key-custody action.

## Deliberate Deferrals

- Broader Codex, Cursor, Devin, and new Claude hook integration.
- Removal or deprecation of advanced compatibility commands.
- A PCAW protocol revision for portable deletion-history proofs.
- Persistent caches that can authorize governance decisions.
- External integrations, deployment, autonomous merge, or release authority.
