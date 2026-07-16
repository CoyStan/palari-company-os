# Invisible Governance Convergence Contract

This is the completion contract for
`WORK-397A2E4DC50B47B098A008DBA2E9A32E` on branch
`codex/invisible-governance-convergence`.

The governing principle is: **automate mechanically knowable transitions and
stop only for genuine independent review, human authority, or external state**.
The work may compress interactions, but it must not synthesize evidence,
review, identity, authority, or external effects.

Baseline commit: `0574b5092adae1c6f747d0f3521667d4ea2d117e`, equal to
`origin/main` when the work item was created. Baseline verification:

- Approval Pack suite: 20 tests in 7.60 seconds.
- Agent advance suite: 41 tests in 8.17 seconds.
- Workspace read-model suite: 39 tests in 9.09 seconds.
- Complete gate: 719 tests across 42 modules plus 18/18 PCAW vectors in
  45.99 seconds.

Every checkbox names the required outcome, objective evidence, verification,
current status, and exact committed proof. A checkbox becomes complete only
after its evidence is committed.

## Required Outcomes

- [ ] Machine-readable resolution classes
  - Required outcome: agent finish/loop and Approval Inbox states distinguish
    automatic reconciliation, ordinary agent work, independent review, human
    authority, external state, and terminal state without treating them as
    equivalent blockers.
  - Objective evidence: focused JSON/text tests prove stable resolution class,
    owner, automatic flag, and next safe action for representative states.
  - Verification: focused agent packet, read-model, Approval Pack, and CLI
    tests.
  - Current status: implemented; affected tests and text/JSON assertions pass.
  - Exact committed proof: pending.

- [ ] Deterministic post-decision convergence
  - Required outcome: repeated `agent advance` over exact current proof safely
    completes accepted work after a current qualified human decision, creates
    any derived acceptance record, releases only its own claim, and is
    idempotent. It never records review or a human decision.
  - Objective evidence: positive, replay, stale-decision, changed-artifact,
    missing-review, actor, and crash/retry tests.
  - Verification: `python3 -m unittest tests.test_agent_advance`.
  - Current status: implemented; current-decision, replay, later-negative-
    decision, changed-artifact, invalid-projection, and existing crash/recovery
    coverage pass.
  - Exact committed proof: pending.

- [ ] One exact routine human action
  - Required outcome: the normal human handoff points to an immutable Approval
    Pack whose existing `approve-eligible` transaction records item-level
    decisions, derives acceptance, and terminalizes every eligible local member
    in one attributable action. Blocked, stale, non-batchable, external, or
    irreversible members remain excluded and parked.
  - Objective evidence: 1/10/100-member tests retain independent proof counts
    while requiring one approval action; handoff and inbox tests expose the
    exact primary command and concise exceptions.
  - Verification: `python3 -m unittest tests.test_approval_packs
    tests.test_agent_packets tests.test_workspace_read_models`.
  - Current status: implemented; 1/10/100 interaction, handoff, inbox, and
    legacy fallback tests pass.
  - Exact committed proof: pending.

- [ ] Honest approval modes
  - Required outcome: operator output differentiates auto-finish,
    approve-eligible, approve-selected, independent-review, individual-effect,
    and policy-decision paths. A combined review/accept interaction is offered
    only when it can preserve separate exact records and the applicable
    independence policy permits the same human to hold both roles.
  - Objective evidence: policy tests prove no profile widens declared authority
    or batches external, irreversible, financial, legal, access, security, or
    deployment effects.
  - Verification: focused Approval Pack and transition tests.
  - Current status: implemented; unsafe combined review-and-accept is reported
    unavailable and existing reviewer/approver collision tests remain passing.
  - Exact committed proof: pending.

- [ ] Terminal states are not blockers
  - Required outcome: closed work reports a terminal loop/status with no
    remediation demand; no-ready, waiting, and blocked remain distinct.
  - Objective evidence: JSON/text regression tests cover completed work and
    preserve fail-closed behavior for genuinely unsafe states.
  - Verification: focused agent loop and CLI smoke tests.
  - Current status: implemented; terminal finish/loop regression test passes.
  - Exact committed proof: pending.

- [ ] Minimality, compatibility, performance, and exact review
  - Required outcome: existing CLI invocations and schema v2 remain compatible;
    no runtime dependency, provider call, background service, autonomous human
    authority, external write, push, merge, or deployment is added; affected,
    complete, install, docs, and conformance checks pass; median complete-gate
    performance does not regress more than 10% without attributable evidence;
    a fresh independent reviewer accepts the exact candidate.
  - Objective evidence: public CLI snapshots, compatibility and negative tests,
    three complete-gate timings, install smoke, docs check, PCAW conformance,
    exact-head review, and dogfood proof records.
  - Verification: `./scripts/verify.sh`, `./scripts/install_smoke.sh`,
    `./bin/palari docs check --json`, and
    `python3 spec/pcaw/v1/conformance.py -- ./bin/palari proof verify`.
  - Current status: implementation verification passed: 725 tests across 42
    modules; three complete gates were 44.86, 44.83, and 44.72 seconds (44.83
    median versus 45.99 baseline); 18/18 conformance vectors, docs check,
    style, schema/fixture smokes, and isolated wheel install pass. Exact commit
    and independent review remain pending.
  - Exact committed proof: pending.

## Non-claims

- Deterministic verification is not semantic independent review.
- One approval action is exact-state authorization, not a standing override.
- “Approve eligible” never approves a stale, blocked, non-batchable, external,
  irreversible, or authority-expanding member.
- Palari still does not cryptographically authenticate a hostile process
  running as the same operating-system user.
- Git integration, push, merge, deployment, and live external effects remain
  separate authority boundaries.
