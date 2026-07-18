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
- At work-item setup head `c528f2a`, dogfood journal: 39,889,344 bytes, 150
  records, 75 committed transactions.
  Three exact verification runs had a 4.88-second median and approximately
  278 MB peak RSS. One journaled mutation currently performs roughly two full
  scans.
- Existing opaque IDs and independent claims already permit unrelated work to
  proceed without chronological merge order.

## Design Interaction Budget

These are intended operator-call budgets, not completion evidence. Counts are
Palari invocations, excluding editing, tests, and Git commands; final evidence
must name measured transcript fixtures for any acceptance claim.

| Journey | Before | Target after | Judgment that must remain |
| --- | ---: | ---: | --- |
| Adopt a repository | 1 (`init`) | 1 (`init`) | none |
| Claim safe work as a known Palari | 2–3 | 1 (`start --next`) | identity selection remains explicit |
| Select and start ready work | 2–3 | 1 (`start --next`) | none |
| Complete R2+ bounded work | 5–6 after editing | 1 (`advance`) | none until review |
| Independent review | 2 | 2 | one independent verdict |
| Accept a reversible result | 2 | 1 inbox read + 1 human action | one human decision |
| Narrow, reject, or defer | 2 | 1 inbox read + 1 human action | one human decision |
| Diagnose a blocker | 1, 24 lines/five alternatives | 1, at most 9 lines/one action | none |
| Enable legacy journal continuity | 1 | 1 explicit checkpoint | explicit operator opt-in |
| Complete ten unrelated R2 items | about 80–90 before review | 20, parallel-safe | one review per item |

The one-invocation claim count assumes the session already knows a Palari ID
declared in the workspace. `start --next` does not discover a real-world actor,
auto-assign identity, elevate authority, or decide which Palari a session should
impersonate. Initialization or an operator supplies that identity explicitly;
the command only selects and claims eligible work for it.

## Required Outcomes

- [x] **One authoritative directive compiler**
  - Required outcome: one pure deterministic function returns lifecycle state,
    owner, automatic transitions, human/reviewer boundary, one safe action,
    concise diagnostics, and optional proof detail from current workspace truth.
  - Objective evidence: parity tests cover ready, active, blocked, stale,
    review-required, human-decision-required, accepted, and completed states;
    existing transition checks remain the mutation authority.
  - Verification: focused directive, kernel, read-model, and transition tests.
  - Current status: completed.
  - Exact committed proof: `25967792ccceec3f4b1c9b319f9087c5cf1d73d0`
    (`agent_directive.py`, `agent_operation.py`, and directive/read-model parity tests).

- [x] **One entry action**
  - Required outcome: given an already-declared Palari identity, `palari agent
    start --next --as PALARI-ID` selects exactly one safe item, compiles its
    packet and portable contract, and claims it in one idempotent command. It
    does not assign identity or authority. Explicit `start WORK-ID` remains
    compatible.
  - Objective evidence: ready, no-ready, ambiguous, review-only, foreign-claim,
    repeated, and parallel-unrelated interaction tests.
  - Verification: agent runtime/packet/CLI tests and golden terminal transcript.
  - Current status: completed.
  - Exact committed proof: `25967792ccceec3f4b1c9b319f9087c5cf1d73d0`;
    repeated start and atomic multi-agent contention tests pass.

- [ ] **One convergence action**
  - Required outcome: `palari agent advance WORK-ID` is the ordinary agent-safe
    fixed-point action. It derives deterministic attempt, receipt, evidence,
    verification, handoff, and terminal bookkeeping, then stops only for an
    independent verdict, exact human authority, external effects, or a blocker.
  - Objective evidence: R1 and R2+ journeys require no copied IDs/digests and
    post-quorum completion requires no follow-up command; retries are idempotent.
  - Verification: advance, convergence, authority, crash, and interaction tests.
  - Current status: in progress.
  - Current evidence (not completion proof):
    `25967792ccceec3f4b1c9b319f9087c5cf1d73d0` established the original
    convergence implementation. Its later pre-claim composition needs final
    integration verification and fresh exact-head review.

- [x] **Deletion and parking are first-class**
  - Required outcome: declared create/modify/delete intent is enforced against
    exact Git state; a deletion is proof, not a missing output. Durable
    `agent release --reason ... --next-action ...` records why work stopped and
    its next safe action before releasing the claim, and repeated recovery is safe.
  - Objective evidence: legacy presence-required behavior is unchanged;
    traversal, symlink, undeclared deletion, fake tombstone, foreign claim,
    interrupted park, and retry cases fail closed or recover safely.
  - Verification: schema parity, file-boundary, proof, journal-crash, and park
    interaction tests.
  - Current status: completed.
  - Exact committed proof: `25967792ccceec3f4b1c9b319f9087c5cf1d73d0`
    adds exact ancestry/tombstone/parking enforcement;
    `591702bbe4ec19c18fc06275682a58b19a3137f7` keeps durable parking inside
    compatible `agent release` instead of adding a 155th public command.

- [ ] **One concise human surface and one exact action**


  - Required outcome: default inbox/handoff output states what is happening,
    whether it is safe, who owns the next judgment, and exactly one bound action.
    Explain/JSON views retain every digest and proof detail. Existing one-action
    convergence remains atomic and fail-closed.
  - Objective evidence: approve, narrow, reject, defer, stale presentation,
    non-batchable, changed evidence, and partial quorum tests; no autonomous
    review or human decision is introduced.
  - Verification: approval pack/presentation/read-model interaction tests.
  - Current status: in progress.
  - Current evidence (not completion proof):
    `25967792ccceec3f4b1c9b319f9087c5cf1d73d0` proves the approval-inbox
    surface. The handoff composition and its fresh exact-head review remain
    pending final verification.

- [ ] **Pre-claim control plane and immutable execution authority**
  - Required outcome: a pre-session, committed Palari workspace projection may
    be identified separately from product output without widening the packet,
    session contract, hook boundary, reviewed source range, or acceptance
    authority. For every complete Git-backed baseline, including a first claim
    and release or expiry recovery, a same-ID execution contract cannot be
    changed: actor/mode, reviewer linkage,
    lifecycle/dependency authority, paths, sources, capabilities, outputs,
    coordination, and static gates require a successor work item.
  - Objective evidence: the claim carries a Git-lease-bound snapshot of exact
    workspace, legacy-history, and journal bytes plus valid journal replay at
    claim creation; its v2 binding compares canonical baseline/current
    authority from strict root/split bytes before lease and again under the
    final workspace lock, which remains held through witness, baseline, packet,
    and claim persistence. A first current-only declaration
    receives a normalized all-Palari execute/review authority catalog whose
    canonical digest is fixed by the oldest v2 witness reflog message. No claim
    survives a changed contract, malformed/unsafe collection, cross-worktree
    anchor mismatch, coordinated catalog rehash, or phase-A/phase-C race.
  - Verification: committed, uncommitted, expired-claim, reviewer-link,
    actor-boundary, source-locator, missing/changed witness, v2 catalog-message,
    parent/leaf symlink, replacement-ref, snapshot-digest, projection-bound
    park-crash recovery, and two-phase lease-race negative tests; full
    packet/advance modules; dogfood dry run against the retained `c528f2a`
    witness.
  - Current status: in progress.
  - Current evidence (not completion proof):
    `43cc159d44ed01ee662c834ba05275cf64108989` introduced the versioned
    snapshot/classifier. The rejected `9ad22e4` review required this repair.
    The retained `c528f2a` baseline correctly rejected renewal after the
    original work contract later added `docs/product/quickstart.md`; repair
    therefore continues under immutable successor
    `WORK-1E6CC071418B42709B60CDA3FED2D952`, not a same-ID rebaseline.
    Candidate `e4c9fb38d18ece6ea501a93e903ecd5e354bedcc` adds the complete
    authority catalog/witness, restart, race, and exact parking-recovery repair.
    Focused verification passed 111 advance, 229 packet/session/hook, and 61
    filesystem/journal/PCAW tests; exact dogfood proof and fresh exact-head
    review remain required.

- [x] **Activation and legacy continuity stay one command**
  - Required outcome: new repository initialization activates the operating
    contract and journal once; legacy checkpoint activation remains explicit,
    idempotent, and one command; provider-specific hooks remain optional.
  - Objective evidence: install/init and checkpoint interaction tests, with no
    new hook or provider dependency.
  - Verification: onramp, journal, install-smoke, and docs tests.
  - Current status: completed.
  - Exact committed proof: `25967792ccceec3f4b1c9b319f9087c5cf1d73d0`;
    onramp and parking tests prove explicit legacy checkpoint behavior.

- [ ] **Progressive disclosure and shared diagnostics**
  - Required outcome: the default blocked view fits within 12 lines and exposes
    exactly state, safety, owner, explanation, and one next action. JSON and
    explicit detail retain the complete current proof and alternatives.
  - Objective evidence: text/JSON semantic-parity snapshots for ready, blocked,
    stale, review, human, and completed states.
  - Verification: CLI output, public-surface, and docs tests.
  - Current status: in progress.
  - Current evidence (not completion proof):
    `25967792ccceec3f4b1c9b319f9087c5cf1d73d0` proves doctor at most nine
    lines, durable release five, start-next six, and approval inbox eight.
    Exact handoff parity and fresh review remain pending final verification.

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
  - Current status: in progress.
  - Current evidence (not completion proof): at
    `591702bbe4ec19c18fc06275682a58b19a3137f7`, three-run medians were 0.23
    seconds/24.8 MB for small `agent next`, 5.27 seconds/293.8 MB for raw 40 MB
    journal verification, and 11.45 seconds/410.6 MB for one temporary-copy
    journaled mutation. The 1-second/100 MB and 2-second mutation targets are
    unmet. A versioned checkpoint/tail-index migration remains deferred because
    a persistent advisory cache must not become transition authority. Final
    candidate `e4c9fb38d18ece6ea501a93e903ecd5e354bedcc` passed three complete
    gates in 93.68, 93.33, and 93.36 seconds (93.36-second median, 1.4% over the
    92.08-second baseline and below the 101.29-second ceiling); median peak RSS
    was 335,956 KB. Fresh exact-head review remains required.

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
  - Current status: in progress.
  - Current evidence (not completion proof):
    `591702bbe4ec19c18fc06275682a58b19a3137f7` is historical verification
    evidence. Candidate `e4c9fb38d18ece6ea501a93e903ecd5e354bedcc`
    passed 876 tests across 46 modules, style, the trusted-code manifest, all
    18 PCAW vectors, 12 documentation checks, exact nine-path packet audit, and
    isolated wheel installation. Fresh exact-head ACCEPT remains due.

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
