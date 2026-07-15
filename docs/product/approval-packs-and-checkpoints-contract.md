# Approval Packs And Reversible Checkpoints Contract

This is the completion contract for `WORK-REPO-0025` on branch
`codex/approval-packs-checkpoints`. Its governing principle is: **compress the
interaction, not the evidence**. A checkbox may be marked complete only when
its objective evidence is committed and the named verification passes.

Accepted dependency head: `b24b644ca8a6df26eb5a3fadb246d3a11093ccea`.

Implementation setup head: `342db2bf716b4e8db0c4df326bfa787178085df0`.

Initial implementation head: `9f297661ded33debb155cc85e77ebff470a704e5`.

Independent-review repair head: `fd3121a2253b4d7a20cfa86d46702107235753d0`.

## Baseline

The first pre-change `./scripts/verify.sh` run exposed a state-coupled test
fixture after WORK-REPO-0024 received real human acceptance. Two test modules
relocated the live dogfood `workspace.json`; its exact artifact-root binding
correctly failed outside the repository. Production validation was not
weakened. The test fixture now copies only the two portable legacy records the
tests exercise.

- `python3 -m unittest tests.test_agent_done tests.test_git_hooks`: 32 tests
  passed in 3.662 seconds.
- `./scripts/verify.sh`: 624 tests across 39 modules, style, trusted-code
  manifest, and 18/18 PCAW vectors passed.
- PCAW trusted-code baseline: 5 files, 2,334 source lines, zero runtime
  dependencies.
- Existing individual approval-interaction counts for 1, 10, and 100 eligible
  items: 1, 10, and 100 attributable commands. Approval Pack counts: one
  review session and one attributable action for each size while retaining 1,
  10, and 100 item proof records.
- Three successful complete-gate timings: 42.96s, 42.77s, and 42.98s; median
  42.96s versus the 78.88s baseline (45.5% lower). No timing optimization or
  assertion weakening was introduced by this work.
- Current PCAW trusted code: unchanged at 5 files, 2,334 source lines, and zero
  runtime dependencies. Approval Pack/checkpoint code is outside the offline
  PCAW verifier TCB.
- Post-review authoritative gate: 651 tests across 41 modules, style,
  schema/fixture/CLI/docs checks, and 18/18 PCAW vectors passed in 42.76
  seconds. The isolated installed-wheel smoke passed in 12.73 seconds.

## Independent Review History

- Exact head `be8050b065f0b4d20b3bcb683a3ac783cefcddab`: **REJECT**. The fresh
  reviewer found that a stored pack could reuse an older batch policy, a
  narrowed `--pack-member` request could expand through a stored manifest,
  same-id receipt/outbox transitions could hide external effects, and a
  dependency omitted from a narrowed pack was not represented as blocked.
- Repair head `fd3121a2253b4d7a20cfa86d46702107235753d0`: all four findings repaired,
  with additional strict nested manifest validation, qualified authority for
  approve/reject/defer, exact per-pack operator commands, stale-decision
  rejection, sent/failed external-effect blocking, and adversarial regressions.
  A fresh exact-head verdict remains required.

Status vocabulary: `pending`, `in progress`, `completed`, or `blocked`.

## Required Outcomes

- [x] Immutable canonical Approval Pack manifests
  - Required outcome: a pack binds the exact base workspace/checkpoint digest,
    ordered members, subjects and outputs, dependencies, risk, reversibility,
    authority, receipts, evidence, reviews, cumulative effects, external
    effects, bounded resources, lifecycle state, and its own content digest.
  - Objective completion evidence: deterministic canonicalization tests prove
    identical logical packs are byte-identical and any governed member change
    changes the pack digest.
  - Verification command or artifact: focused pack model and canonicalization
    tests plus schema validation.
  - Current status: completed.
  - Exact committed evidence when completed: `9f297661ded33debb155cc85e77ebff470a704e5`
    plus repair `fd3121a2253b4d7a20cfa86d46702107235753d0`
    (`approval_packs.py`, strict nested canonical manifest validation, and
    1/10/100 plus malformed-manifest tests).

- [x] Item-granular eligibility and dependency-aware staleness
  - Required outcome: the evaluator derives each member as eligible, stale,
    blocked, rejected, deferred, or non-batchable without discarding unrelated
    valid approval; dependency mutation or rejection blocks descendants.
  - Objective completion evidence: positive and negative graph tests, including
    changed members, changed dependencies, partial decisions, and independent
    unchanged siblings.
  - Verification command or artifact: focused approval-pack evaluator tests.
  - Current status: completed.
  - Exact committed evidence when completed: `9f297661ded33debb155cc85e77ebff470a704e5`
    plus repair `fd3121a2253b4d7a20cfa86d46702107235753d0`
    (policy-drift staleness, outside-pack dependency blocking, changed sibling,
    and rejection propagation tests).

- [x] One attributable human action with exact per-item authorization
  - Required outcome: one human decision over an exact immutable pack may
    derive authorization only for the selected eligible members; agents cannot
    create, replay, or transplant that decision, and every item retains its
    own proof and journal record.
  - Objective completion evidence: one-decision 1/10/100-member tests,
    actor-boundary tests, pack-transplant rejection, repeated-command
    idempotence, and exact member authorization reports.
  - Verification command or artifact: focused human-decision, transition, and
    approval-pack tests.
  - Current status: completed.
  - Exact committed evidence when completed: `9f297661ded33debb155cc85e77ebff470a704e5`
    plus repair `fd3121a2253b4d7a20cfa86d46702107235753d0`
    (exact selection equality, durable manifest/member bindings, qualified
    approve/reject/defer authority, transplant, and idempotence tests).

- [x] Parked execution and risk-based batch policy
  - Required outcome: bounded preparation may continue while governed effects
    remain parked; batch policy distinguishes local drafts, memory proposals,
    edits, communications, access expansion, and financial/legal/security or
    irreversible effects. Pack approval never widens declared authority.
  - Objective completion evidence: policy vectors and transition tests prove
    parked is neither approved nor executed, non-batchable actions remain
    individually gated, and external effects are never called rollback-safe.
  - Verification command or artifact: focused policy, boundary, and negative
    execution tests.
  - Current status: completed.
  - Exact committed evidence when completed: `9f297661ded33debb155cc85e77ebff470a704e5`
    (`test_risk_friction_policy_keeps_governed_effects_individually_gated` and
    pending-quorum artifact-mutation rejection).

- [x] Approval Inbox operator experience
  - Required outcome: existing queue/detail/human-decision surfaces provide a
    concise machine-readable inbox with pack/item counts, cumulative summaries,
    risk/reversibility groups, dependencies, conflicts, stale or blocked
    members, exact post-approval actions, and approve-eligible/select/reject/
    narrow/defer guidance.
  - Objective completion evidence: stable JSON/text snapshots for empty, mixed,
    1-item, 10-item, and 100-item inboxes with concise actionable diagnostics.
  - Verification command or artifact: CLI/read-model tests and public-surface
    snapshots.
  - Current status: completed.
  - Exact committed evidence when completed: `9f297661ded33debb155cc85e77ebff470a704e5`
    plus repair `fd3121a2253b4d7a20cfa86d46702107235753d0`
    (`queue --approval-inbox` exact `approval_commands`, enriched `detail`,
    `human-decision pack`, CLI JSON/text tests, and 154-command public snapshot).

- [x] Content-addressed chained checkpoints and append-only restoration
  - Required outcome: tentative state chains bind exact transitions; approving
    through a checkpoint authorizes only that exact prefix; restoration appends
    a new transition whose governed projection exactly matches the selected
    checkpoint without erasing later history or effects.
  - Objective completion evidence: exact projection replay, chain-prefix,
    restoration, reason-attribution, and history-preservation tests.
  - Verification command or artifact: focused checkpoint and journal tests.
  - Current status: completed.
  - Exact committed evidence when completed: `9f297661ded33debb155cc85e77ebff470a704e5`
    plus repair `fd3121a2253b4d7a20cfa86d46702107235753d0`
    (`checkpoints.py`, `history --checkpoints/--restore`, exact projection,
    same-id effect detection, pre-mutation external-effect refusal, and
    append-only history tests).

- [x] Crash-safe, idempotent approval and execution journaling
  - Required outcome: interrupted approval, per-member authorization,
    execution, and restoration transitions recover idempotently or fail closed;
    the journal retains every member decision and execution result.
  - Objective completion evidence: crash injection at every new transaction
    boundary plus truncation, fork, duplicate, reorder, and divergence tests.
  - Verification command or artifact: journal crash suite and prefix replay.
  - Current status: completed.
  - Exact committed evidence when completed: `9f297661ded33debb155cc85e77ebff470a704e5`
    (approval and restoration crash injection plus existing 21-test journal
    corruption/replay suite).

- [x] Filesystem, source, identity, and authority boundaries remain closed
  - Required outcome: path traversal, sibling-prefix, symlink escape,
    unapproved sources, builder/reviewer/human collisions, copied approval, and
    authority expansion fail before effects.
  - Objective completion evidence: adversarial negative tests prove no unsafe
    bytes or actions are consumed and diagnostics name the next safe action.
  - Verification command or artifact: filesystem security, transition, pack,
    and validation suites.
  - Current status: completed.
  - Exact committed evidence when completed: `9f297661ded33debb155cc85e77ebff470a704e5`
    plus repair `fd3121a2253b4d7a20cfa86d46702107235753d0`
    (identity/capability/transplant negatives, strict nested path validation,
    18 filesystem security tests, exact human restore actor, and unchanged
    source/path validation).

- [x] Measurement proves interaction compression without hidden proof loss
  - Required outcome: record commands/actions needed for 1, 10, and 100 items,
    time-to-understand proxy, complete-gate duration, and trusted-code growth;
    the target is one review session and one attributable approval action for a
    coherent eligible pack.
  - Objective completion evidence: deterministic measurement fixture and
    before/after table with per-item proof-count equality.
  - Verification command or artifact: measurement script/test and timing logs.
  - Current status: completed.
  - Exact committed evidence when completed: `9f297661ded33debb155cc85e77ebff470a704e5`
    (`approval_pack_measure.py`, deterministic 1/10/100 measurement test,
    42.96s complete-gate median, unchanged 2,334-line PCAW TCB).

- [ ] Compatibility, minimality, documentation, and final independent review
  - Required outcome: existing CLI/schema/PCAW/history behavior remains
    compatible; no runtime dependency, background service, provider call, or
    autonomous authority is added; canonical docs are current; full verification
    and fresh exact-head independent review return ACCEPT before human handoff.
  - Objective completion evidence: public-surface snapshots, schema/fixture
    checks, docs/examples, isolated install, complete verification, trusted-code
    accounting, exact review history, and founder packet.
  - Verification command or artifact: `./scripts/verify.sh`,
    `./scripts/install_smoke.sh`, `./bin/palari docs check --json`, focused
    security/pack/checkpoint tests, and exact-head review report.
  - Current status: first exact-head review REJECT repaired at
    `fd3121a2253b4d7a20cfa86d46702107235753d0`; authoritative verification and
    isolated install pass; fresh exact-head review remains.
  - Exact committed evidence when completed: pending.

## Human Boundary

Agents may create, refresh, summarize, and recommend Approval Packs. They may
not record a human pack decision, execute external effects, widen authority,
push, merge, deploy, call providers, access secrets, or describe irreversible
effects as locally rollback-safe.
