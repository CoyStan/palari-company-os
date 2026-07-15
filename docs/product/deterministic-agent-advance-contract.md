# Deterministic Agent Advance Contract

This is the completion contract for `WORK-REPO-0026` on branch
`codex/deterministic-agent-advance`. Its governing rule is: **automate
ceremony, never authority**. The implementation may deterministically advance
local proof state, but it must stop at semantic review, scope expansion, human
decision, acceptance, external effects, push, merge, or deployment.

Accepted dependency implementation: `WORK-REPO-0025`, terminal from exact
evidence head `1dc7d0679252531f4f2abccec24593c33812cbc2`.

Implementation baseline: `cdefca768685099f12a5e8ef384a429fd1550217`.

Baseline measurements:

- `agent loop` wall time over five runs: 0.38s, 0.38s, 0.39s, 0.40s, 0.35s.
- `./scripts/verify.sh`: 656 tests across 41 modules plus style and 18/18
  PCAW vectors passed in 43.56s.
- Slowest modules: dashboard 13.870s, agent packets 13.491s, integrations
  12.193s, governance completion 7.922s, and CLI smoke 7.487s.
- PCAW verifier trusted code: 5 files, 2,334 lines, zero runtime dependencies.

Status vocabulary: `pending`, `in progress`, `completed`, or `blocked`.

## Required Outcomes

- [ ] Pure deterministic advance planner
  - Required outcome: one pure planner consumes the current work, packet,
    claim, Git observation, proof state, and verification attestations and
    returns an ordered plan, blockers, expected state, and plan digest without
    mutation or subprocess execution.
  - Objective completion evidence: repeated and permuted-input tests produce
    byte-identical plans; stale packet, claim, head, or proof changes produce a
    different digest or a fail-closed blocker.
  - Verification command or artifact: `tests.test_agent_advance` planner and
    state-table tests.
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] One idempotent safe-advance command
  - Required outcome: `palari agent advance WORK-ID --as PALARI-ID` derives the
    committed change range, creates or resumes exact attempt/receipt/evidence
    records, evaluates the governed completion/handoff state, releases the
    claim, completes only eligible R1 work, and otherwise stops at the exact
    review or human boundary.
  - Objective completion evidence: R1 and R4 end-to-end tests need no manually
    supplied head SHA, changed paths, artifact hashes, proof commands, handoff,
    or claim release; repeated execution never duplicates records.
  - Verification command or artifact: focused CLI, lifecycle, and idempotence
    tests plus JSON/text snapshots.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Crash-safe proof reconciliation
  - Required outcome: verification occurs outside the workspace lock; before
    mutation the executor rechecks the plan digest, packet, claim, Git head,
    worktree, and workspace state; the ordered proof projection commits through
    the existing one-writer transaction and journal path.
  - Objective completion evidence: crash injection at every new boundary and
    concurrent mutation tests prove safe resume or actionable fail-closed
    diagnosis without partial false proof.
  - Verification command or artifact: advance crash/concurrency suite and
    journal replay verification.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Exact verification attestations and safe reuse
  - Required outcome: verification profiles are explicit argument vectors, not
    executable prose; results bind the exact head, clean tree, profile digest,
    runner/source state, platform, and interpreter. Passing exact-state results
    may be reused; any relevant drift invalidates them.
  - Objective completion evidence: cache-hit tests avoid subprocess execution;
    head, dirty state, profile, Python, platform, source, failure, timeout,
    malformed result, and contradictory-result changes miss or fail closed.
  - Verification command or artifact: attestation unit/adversarial tests and
    exact serialized fixtures.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Fast planning and non-repeated verification
  - Required outcome: planning stays independent of complete verification;
    repeated submission of an already verified exact state validates and reuses
    its attestation instead of rerunning the full gate.
  - Objective completion evidence: deterministic local benchmark records
    `agent advance --dry-run` p95 at or below 250ms and an exact cache-hit
    advance below 1s; affected-area verification targets a median below 5s when
    a safe mapping exists.
  - Verification command or artifact: performance test/measurement artifact,
    cache-spy tests, and before/after timing table.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Full verification remains authoritative
  - Required outcome: focused and cached results accelerate iteration without
    weakening the required complete gate before acceptance; failed or stale
    verification can never produce passing evidence.
  - Objective completion evidence: negative tests cover failed focused and
    complete profiles, cached failure, incomplete mapping, altered tests, and
    stale result rejection. Final complete-gate median does not exceed the
    43.56s baseline by more than 10% without explicit safety-value evidence.
  - Verification command or artifact: `./scripts/verify.sh`, three-run timing
    where required, and installed-package smoke.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Scope, source, authority, and protected-dirt boundaries remain closed
  - Required outcome: the reconciler never infers permission from changed
    files, widens packet authority, consumes unapproved sources, attributes
    unchanged pre-existing dirt, or performs review, decision, acceptance,
    external writes, push, merge, or deployment.
  - Objective completion evidence: traversal, symlink, sibling-prefix,
    out-of-boundary commit, pre-claim commit, release/reclaim laundering,
    protected-dirt mutation, identity collision, and human-command negatives
    all fail before proof mutation.
  - Verification command or artifact: filesystem, Git witness, transition,
    and agent-advance adversarial suites.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Existing agent surfaces remain compatible and simpler
  - Required outcome: `agent done` retains its R1 contract and shares the exact
    claim-range/scope preflight used by the advance engine;
    brief/start/check/finish/handoff/doctor/loop remain valid; `advance` is one
    nested command, not a new top-level group.
  - Objective completion evidence: existing public-surface snapshots and agent
    suites pass; a before/after command count proves the higher-risk happy path
    collapses from manual lifecycle commands to one advance invocation.
  - Verification command or artifact: compatibility suites, public command
    snapshot, docs examples, and deterministic ceremony measurement.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Minimal, documented, independently reviewed delivery
  - Required outcome: standard library only, no daemon, provider, hook, React,
    Rust/C++ rewrite, external write, or commercial application change; docs
    distinguish deterministic conformance from semantic and human review; a
    fresh independent reviewer returns ACCEPT on the exact committed head.
  - Objective completion evidence: docs check, schema/fixture validation,
    isolated install, trusted-code accounting, complete verification, exact
    review report, and founder packet.
  - Verification command or artifact: `./bin/palari docs check --json`,
    `./scripts/install_smoke.sh`, `./scripts/verify.sh`, and exact-head review.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

## Deferred

Codex hooks, Claude hook redesign, automatic staging or committing, AI-authored
semantic review, signing/key custody, live integrations, external effects, and
commercial UI remain separate future work. A later hook adapter should call
this deterministic engine rather than implement another policy copy.
