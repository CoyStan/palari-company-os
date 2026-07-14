# Model-Independent Governance Hardening Contract

This is the completion contract for `WORK-REPO-0023` on branch
`codex/model-independent-governance-hardening`. It is an active product-safety
contract, not a roadmap. A checkbox may be marked complete only after its
objective evidence is committed and the named verification passes.

Baseline source commit: `2eea39e9d3d70baa69d987dba50decbcb63bc51e`.

Baseline verification on 2026-07-14:

- `./scripts/verify.sh`: 419 tests passed; 64.08 seconds wall time.
- `python3 -m unittest discover -s tests`: 419 tests passed; 59.96 seconds wall time.
- `./scripts/install_smoke.sh`: passed; 12.11 seconds wall time.
- Documented sequence total: 136.15 seconds; the first two commands duplicate
  the same complete unit suite.
- `./bin/palari docs check --json`: 12 checks passed, no warnings or failures.

Status vocabulary: `pending`, `in progress`, `completed`, or `blocked`.

## Required Outcomes

- [ ] Exact-artifact review binding
  - Required outcome: an accept-ready review identifies the current attempt,
    evidence manifest, receipt, reviewed head, and bounded work contract;
    subsequent substantive drift makes it stale.
  - Objective completion evidence: negative tests change each bound input and
    prove review, acceptance, and completion fail closed.
  - Verification: focused governance/transition/validation tests plus the
    complete repository gate.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Independent-review enforcement
  - Required outcome: a required accept-ready review comes from a declared
    human reviewer who is distinct from the attempt and receipt actor, and its
    context is assembled from bounded records rather than builder narration.
  - Objective completion evidence: same-actor, unknown-reviewer, wrong-work,
    and mismatched-proof reviews are rejected by mutation and validation paths.
  - Verification: focused review-guide, transition, validation, and lifecycle
    tests plus the complete repository gate.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Human authority remains explicit and current
  - Required outcome: decisions and acceptance records reference current exact
    evidence and review; negative, revoked, stale, or mismatched decisions do
    not count toward quorum; agents cannot surface or execute premature human
    acceptance commands.
  - Objective completion evidence: negative-decision, wrong-reference,
    stale-proof, insufficient-quorum, and premature-handoff tests fail closed.
  - Verification: focused authority, read-model, handoff, validation, and
    transition tests plus the complete repository gate.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Evidence completeness and freshness
  - Required outcome: trust-changing gates require a valid manifest, current
    receipt binding, meaningful verification, and present contained artifacts;
    missing, unsafe, malformed, stale, or contradictory proof is ineligible.
  - Objective completion evidence: missing-artifact, symlink-artifact,
    absent-manifest, empty-proof, receipt-mismatch, and tamper tests fail closed
    with actionable diagnostics.
  - Verification: focused evidence/validation/lifecycle tests plus schema and
    fixture validation and the complete repository gate.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Canonical scope and source boundaries
  - Required outcome: filesystem-backed checks contain canonical paths within
    the declared root; traversal, sibling-prefix, symlink escape, unsafe
    declarations, invalid observations, wrong-repository inspection, and
    unselected/unreadable sources fail closed.
  - Objective completion evidence: temporary-copy tests cover every named
    escape and show untouched pre-existing user dirt is not attributed to the
    attempt.
  - Verification: focused path, workspace, packet, hook, and validation tests
    plus security/boundary smokes and the complete repository gate.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Lifecycle consistency and safe repetition
  - Required outcome: work, attempt, receipt, evidence, review, decision, and
    completion transitions cannot bypass prerequisites; interrupted or repeated
    shortcut commands are preflighted, resumable, and do not fabricate proof.
  - Objective completion evidence: partial-failure and repeated-command tests
    preserve valid state and history; high-risk completion requires a terminal
    clean current attempt.
  - Verification: focused workflow, agent-done, history, transition, and
    lifecycle tests plus the complete repository gate.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Multi-agent, worktree, and handoff clarity
  - Required outcome: enforcement uses one validated claim/packet identity at a
    time, detects ambiguous ownership and mixed-claim changes, handles linked
    worktrees and deletions, and hands off exact branch/head/scope/proof/blocker
    state without granting human authority.
  - Objective completion evidence: tampered-packet, context-hash, multiple
    claim, worktree-hook, deletion, Git-error, and handoff-state tests fail
    closed with the next safe action.
  - Verification: focused runtime, Git hook, Claude hook, agent packet, and
    handoff tests plus CLI smokes and the complete repository gate.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Faster verification without a weaker final gate
  - Required outcome: maintainers have mechanical focused, affected-area, and
    authoritative complete profiles; the default complete gate remains
    deterministic and the documented release/acceptance gate is not weakened.
  - Objective completion evidence: before/after timings, profile self-tests,
    and proof that the complete profile runs all repository tests and required
    smokes.
  - Verification: verification-profile tests, the authoritative complete gate,
    and isolated wheel install smoke.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Concise actionable operator diagnostics
  - Required outcome: queue, detail, doctor, check, finish, handoff, and hook
    output distinguish blocked, stale, rejected, review-required, and
    human-decision states and name the exact missing proof and next safe action.
  - Objective completion evidence: JSON and text-output tests assert stable
    blocker codes, no premature authority commands, and actionable guidance.
  - Verification: focused CLI/operator tests plus command smoke tests and the
    complete repository gate.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Compatibility, migration, minimality, and documentation
  - Required outcome: public CLI compatibility is preserved; any stricter
    durable schema contract has an explicit versioned migration; no runtime
    dependency, provider call, secret access, autonomous acceptance, push,
    merge, or deployment is added; active docs and examples match behavior.
  - Objective completion evidence: legacy/current/newer schema tests,
    migration idempotency tests, public-command fixture checks, docs validation,
    example validation, and isolated package installation all pass.
  - Verification: migration/schema/public-surface/docs tests,
    `./bin/palari docs check --json`, authoritative complete verification, and
    `./scripts/install_smoke.sh`.
  - Current status: in progress.
  - Exact committed evidence: pending.

- [ ] Exact-head independent review and founder packet
  - Required outcome: a fresh independent reviewer inspects the exact clean
    committed candidate and returns `ACCEPT`; any rejection is repaired and
    re-reviewed; the final founder packet contains baseline/final commits,
    checks/timings, review history, compatibility, paths, risks, deferrals, and
    rollback instructions while founder acceptance remains human-only.
  - Objective completion evidence: committed review record or report names the
    exact candidate head and the final `palari agent check`, `finish`, `doctor`,
    `loop`, and `handoff` artifacts agree on the remaining human boundary.
  - Verification: clean-tree exact-head review, authoritative complete gate,
    install smoke, docs check, dogfood validate/check/finish/handoff.
  - Current status: in progress.
  - Exact committed evidence: pending.

## Known Human Boundary

This work may prepare a founder acceptance packet and may quote the human-only
review or decision commands Palari emits. It must not record founder review,
founder acceptance, merge, push, deploy, call providers, or use secrets.
