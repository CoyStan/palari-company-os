# Opaque Concurrent Work Completion Contract

This is the completion contract for
`WORK-AC8CE9E4197C4D57B6FA096F14F33A3F` on branch
`codex/opaque-concurrent-work-items`.

Baseline commit: `c72e034085e78550581910b1bc35c885c576b4a0` (equal to
`origin/main` when the work item was created). Baseline focused verification:
177 tests passed in 25.60 seconds.

IDs identify work; they do not grant priority, create a dependency, or constrain
review, acceptance, or integration order. Dependencies are explicit directed
edges. Git still serializes updates to a shared target branch, but independent
attempts may execute and reach review concurrently.

Every item below records the required outcome, objective evidence, verification
command or artifact, current status, and exact committed proof. A checkbox may
be marked complete only after its evidence is committed.

- [x] Opaque identity by default
  - Required outcome: `palari work add` creates a collision-resistant opaque
    work ID without reading or incrementing existing numeric IDs; explicit and
    legacy IDs remain compatible.
  - Objective evidence: focused tests prove format, uniqueness, collision retry,
    explicit-ID compatibility, and independence from existing numeric IDs.
  - Verification: `python3 -m unittest tests.test_onramp`.
  - Current status: complete; focused verification passed.
  - Exact committed proof: implementation and tests in
    `75b9bcd851a450a7f0a6a068d5e20f2fd8b840f8`.

- [x] Explicit dependency DAG
  - Required outcome: quick work creation accepts repeatable explicit
    dependencies, and workspace loading fails closed for missing, duplicate,
    self-referential, or cyclic dependency edges.
  - Objective evidence: CLI and workspace tests cover valid independent and
    dependent work plus every rejected graph shape.
  - Verification: `python3 -m unittest tests.test_onramp tests.test_validation`.
  - Current status: complete; focused verification passed.
  - Exact committed proof: implementation and tests in
    `75b9bcd851a450a7f0a6a068d5e20f2fd8b840f8`.

- [x] Cross-worktree single-owner lease
  - Required outcome: a work item can have at most one active execute/review
    claim across linked Git worktrees; acquisition, renewal, expiry replacement,
    integrity checking, and release use compare-and-swap behavior and fail
    closed on contradictory state.
  - Objective evidence: tests create linked worktrees, prove a second session is
    rejected, prove another work item remains independently claimable, and prove
    release/expiry permits safe reacquisition.
  - Verification: `python3 -m unittest tests.test_agent_packets`.
  - Current status: complete; focused and linked-worktree verification passed.
  - Exact committed proof: implementation and tests in
    `75b9bcd851a450a7f0a6a068d5e20f2fd8b840f8`.

- [x] Mechanical isolated start
  - Required outcome: `palari agent start WORK-ID --as PALARI-ID --isolate`
    creates or safely resumes a deterministic local branch/worktree, persists
    the packet and claim there, and returns a direct resume command without
    merging, pushing, reviewing, accepting, or deleting operator work.
  - Objective evidence: CLI tests prove clean creation, idempotent resume,
    uncommitted-work refusal, branch collision refusal, and actionable output.
  - Verification: `python3 -m unittest tests.test_agent_packets tests.test_cli_smoke`.
  - Current status: complete; focused verification passed.
  - Exact committed proof: implementation and tests in
    `75b9bcd851a450a7f0a6a068d5e20f2fd8b840f8`.

- [x] Order-independent operator diagnostics
  - Required outcome: agent-next output names explicit dependency blockers and
    active cross-worktree claims; an opaque ID is never described as priority or
    dependency evidence.
  - Objective evidence: JSON and text smoke tests cover ready independent work,
    dependency-blocked work, and work claimed in another worktree.
  - Verification: `python3 -m unittest tests.test_agent_packets tests.test_cli_smoke`.
  - Current status: complete; JSON and text smoke verification passed.
  - Exact committed proof: implementation and tests in
    `75b9bcd851a450a7f0a6a068d5e20f2fd8b840f8`.

- [ ] Compatibility, minimality, and authority preservation
  - Required outcome: schema v2 and arbitrary historical work IDs remain valid;
    no runtime dependency or background service is added; isolated execution
    grants no human review, acceptance, merge, push, deployment, or external
    write authority.
  - Objective evidence: schema fixtures, docs check, installed-package smoke,
    and full repository verification pass.
  - Verification: `./bin/palari docs check --json`, `./scripts/verify.sh`, and
    `./scripts/install_smoke.sh`.
  - Current status: implementation committed; exact-head complete verification
    pending.
  - Exact committed proof: compatibility implementation in
    `75b9bcd851a450a7f0a6a068d5e20f2fd8b840f8`; final verification evidence
    pending.

- [ ] Exact candidate and independent review
  - Required outcome: all implementation and contract evidence is committed;
    a fresh independent reviewer inspects that exact head and returns ACCEPT,
    with all substantive findings repaired and re-reviewed.
  - Objective evidence: exact commit, clean tracked worktree, complete gate
    results, review record, and human decision bound to current evidence.
  - Verification: `palari agent advance
    WORK-AC8CE9E4197C4D57B6FA096F14F33A3F --as PALARI-STEWARD --json`, followed
    by the human-only review/decision commands emitted by the handoff packet.
  - Current status: in progress; human authority not yet requested.
  - Exact committed proof: pending.

## Non-claims

- Opaque IDs do not make conflicting patches mergeable.
- An isolated worktree does not approve, review, merge, push, or deploy work.
- The Git-shared lease coordinates linked worktrees on one local repository; it
  is not a distributed network lock and does not authenticate a hostile process
  running as the same OS user.
- Integration into a shared branch remains a separately serialized operation.
