# Invisible Adoption Foundation v1 — Integration Contract

Integration work item: `WORK-3B7821F3452B40B283784832E86234C3`

Bounded precursors:

- Golden Path Repair: `WORK-C11EE25A4D42414BBAD382121E89E070`
- Compact Journal v2: `WORK-A06D321334B74BFD878154776F299E57`
- Invisible Product Surface: `WORK-31D9DD73A7A045BC8236FA561291D064`
- Universal Agent Adoption: `WORK-BF48A3D891A7428FB91AA80BF53856AA`

Baseline: `f6e2cf9b3f59e4074ca459368103d802a4eb3b81`

Setup head: `bfec21a2044d4aa53943b5331502c761bc98c72c`

Baseline verification: `./scripts/verify.sh` passed 876 tests across 46
modules, style, trusted-code accounting (5 files / 2,405 SLOC), and 18/18 PCAW
vectors in 113.59 seconds with 358,556 KB peak RSS.

Status vocabulary is `pending`, `in progress`, `completed`, or `blocked`.
Every completed checkbox names exact committed proof. One integrated claim owns
the final Git range so the founder receives one presentation-bound action,
not four branch-specific approval ceremonies.

## Required Outcomes

- [ ] **Golden path is truthful and executable**
  - Required outcome: a clean repository follows init, bounded work creation,
    start-next, one bounded commit, and advance without an undocumented Git
    bootstrap failure or copied proof IDs.
  - Objective evidence: isolated real-Git transcript completes R1 and preserves
    immutable authority, unrelated staged work, existing instructions, and
    fail-closed unusual states.
  - Verification command or artifact: onramp, demo, operator-journey, runtime,
    and install smokes.
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] **Journal cost is proportional to logical change**
  - Required outcome: compact v2 checkpoint/delta history remains strict,
    replayable, crash-safe, and backward-compatible without loading or copying
    the full historical projection on ordinary reads and writes.
  - Objective evidence: v1/v2 continuity, prefix replay, corruption, crash,
    retry, bounded-memory, compactness, and three-run timing evidence.
  - Verification command or artifact: journal/crash/store suites and recorded
    dogfood-copy timings.
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] **Ordinary product surface exposes concepts, not ceremony**
  - Required outcome: default help and operator views foreground init, work,
    agent start/advance/doctor, queue/detail, and proof; advanced compatibility
    commands remain parseable. Superseded/abandoned work is explicit,
    attributable, auditable, and absent from ordinary active queues.
  - Objective evidence: help snapshots, terminal-state schema/validation,
    successor-cycle, active-attempt, authority, queue/inbox, explicit-start,
    compatibility, and migration tests.
  - Verification command or artifact: public-surface, validation, read-model,
    packet, docs, and schema suites.
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] **Any supported agent can adopt the same bounded loop**
  - Required outcome: one honest host adoption action installs portable
    instructions, a structural Git gate, proven native hooks where available,
    and a complete agent-safe MCP loop without granting human authority.
  - Objective evidence: the universal adoption contract is fully satisfied.
  - Verification command or artifact:
    `docs/product/universal-agent-adoption-contract.md` and its focused suites.
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] **One coherent, verified, review-accepted candidate**
  - Required outcome: all four slices compose on one exact committed head,
    precursor work is terminalized without erased history, all attributable
    checks pass, performance is honestly compared, and a fresh independent
    reviewer returns ACCEPT before one founder action is requested.
  - Objective evidence: clean changed-path check; docs/schema/fixture, CLI,
    security, PCAW conformance, affected, complete, and isolated-install gates;
    timing table; review artifact; Approval Pack bound to exact presentation.
  - Verification command or artifact: `./bin/palari validate --json`,
    `./bin/palari docs check --json`, PCAW conformance, `./scripts/verify.sh`,
    `./scripts/install_smoke.sh`, agent check/advance/handoff, and review history.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

