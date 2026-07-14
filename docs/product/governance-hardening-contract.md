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

- [x] Exact-artifact review binding
  - Required outcome: an accept-ready review identifies the current attempt,
    evidence manifest, receipt, reviewed head, and bounded work contract;
    subsequent substantive drift makes it stale.
  - Objective completion evidence: negative tests change each bound input and
    prove review, acceptance, and completion fail closed.
  - Verification: focused governance/transition/validation tests plus the
    complete repository gate.
  - Current status: completed.
  - Exact committed evidence: implementation candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; binding implementation in
    `src/palari_company_os/governance_binding.py`; negative binding and
    completion coverage in `tests/test_validation.py`,
    `tests/test_review_guides.py`, and `tests/test_governance_completion.py`;
    review ledger `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

- [x] Independent-review enforcement
  - Required outcome: a required accept-ready review comes from a declared
    human reviewer who is distinct from the attempt and receipt actor, and its
    context is assembled from bounded records rather than builder narration.
  - Objective completion evidence: same-actor, unknown-reviewer, wrong-work,
    and mismatched-proof reviews are rejected by mutation and validation paths.
  - Verification: focused review-guide, transition, validation, and lifecycle
    tests plus the complete repository gate.
  - Current status: completed.
  - Exact committed evidence: candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; reviewer/actor separation and
    bounded review guides in `src/palari_company_os/validation.py`,
    `src/palari_company_os/review_guides.py`, and
    `src/palari_company_os/transition_checks.py`; exact review history at
    `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

- [x] Human authority remains explicit and current
  - Required outcome: decisions and acceptance records reference current exact
    evidence and review; negative, revoked, stale, or mismatched decisions do
    not count toward quorum; agents cannot surface or execute premature human
    acceptance commands.
  - Objective completion evidence: negative-decision, wrong-reference,
    stale-proof, insufficient-quorum, and premature-handoff tests fail closed.
  - Verification: focused authority, read-model, handoff, validation, and
    transition tests plus the complete repository gate.
  - Current status: completed.
  - Exact committed evidence: candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; current decision/quorum and
    `accepted_at` revocation enforcement in `validation.py`, `read_models.py`,
    `agent_handoff.py`, and `claude_hooks.py`; hostile authority tests in
    `test_validation.py`, `test_governance_completion.py`, and
    `test_claude_hooks.py`; review 15 ACCEPT recorded at
    `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

- [x] Evidence completeness and freshness
  - Required outcome: trust-changing gates require a valid manifest, current
    receipt binding, meaningful verification, and present contained artifacts;
    missing, unsafe, malformed, stale, or contradictory proof is ineligible.
  - Objective completion evidence: missing-artifact, symlink-artifact,
    absent-manifest, empty-proof, receipt-mismatch, and tamper tests fail closed
    with actionable diagnostics.
  - Verification: focused evidence/validation/lifecycle tests plus schema and
    fixture validation and the complete repository gate.
  - Current status: completed.
  - Exact committed evidence: candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; manifest, artifact, receipt,
    timestamp, and active-acceptance verification in `evidence_manifest.py`,
    `record_order.py`, and `validation.py`; negative evidence tests in
    `test_validation.py` and `test_governance_completion.py`; adversarial
    review confirmation at `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

- [x] Canonical scope and source boundaries
  - Required outcome: filesystem-backed checks contain canonical paths within
    the declared root; traversal, sibling-prefix, symlink escape, unsafe
    declarations, invalid observations, wrong-repository inspection, and
    unselected/unreadable sources fail closed.
  - Objective completion evidence: temporary-copy tests cover every named
    escape and show untouched pre-existing user dirt is not attributed to the
    attempt.
  - Verification: focused path, workspace, packet, hook, and validation tests
    plus security/boundary smokes and the complete repository gate.
  - Current status: completed.
  - Exact committed evidence: candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; canonical containment in
    `path_policy.py`, `agent_file_changes.py`, `git_hooks.py`, and
    `claude_hooks.py`; temporary-copy negative coverage in
    `test_filesystem_security.py`, `test_path_policy.py`, `test_git_hooks.py`,
    `test_claude_hooks.py`, and `test_agent_done.py`; reviews 3-10 in commit
    `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

- [x] Lifecycle consistency and safe repetition
  - Required outcome: work, attempt, receipt, evidence, review, decision, and
    completion transitions cannot bypass prerequisites; interrupted or repeated
    shortcut commands are preflighted, resumable, and do not fabricate proof.
  - Objective completion evidence: partial-failure and repeated-command tests
    preserve valid state and history; high-risk completion requires a terminal
    clean current attempt.
  - Verification: focused workflow, agent-done, history, transition, and
    lifecycle tests plus the complete repository gate.
  - Current status: completed.
  - Exact committed evidence: candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; guarded authoring and completion
    transitions in `authoring.py`, `transition_checks.py`, `agent_done.py`, and
    `validation.py`; partial/repeated command coverage in
    `test_transition_checks.py`, `test_history.py`, `test_agent_done.py`, and
    `test_governance_completion.py`; review ledger
    `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

- [x] Multi-agent, worktree, and handoff clarity
  - Required outcome: enforcement uses one validated claim/packet identity at a
    time, detects ambiguous ownership and mixed-claim changes, handles linked
    worktrees and deletions, and hands off exact branch/head/scope/proof/blocker
    state without granting human authority.
  - Objective completion evidence: tampered-packet, context-hash, multiple
    claim, worktree-hook, deletion, Git-error, and handoff-state tests fail
    closed with the next safe action.
  - Verification: focused runtime, Git hook, Claude hook, agent packet, and
    handoff tests plus CLI smokes and the complete repository gate.
  - Current status: completed.
  - Exact committed evidence: candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; current packet recomputation,
    immutable claim-start baseline, reflog-backed Git witness, claim conflict,
    linked-worktree handling, and exact handoff fields in `agent_runtime.py`,
    `agent_checks.py`, `agent_file_changes.py`, `agent_handoff.py`, and hooks;
    negative runtime/worktree tests and reviews 2-4 recorded at
    `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

- [x] Faster verification without a weaker final gate
  - Required outcome: maintainers have mechanical focused, affected-area, and
    authoritative complete profiles; the default complete gate remains
    deterministic and the documented release/acceptance gate is not weakened.
  - Objective completion evidence: before/after timings, profile self-tests,
    and proof that the complete profile runs all repository tests and required
    smokes.
  - Verification: verification-profile tests, the authoritative complete gate,
    and isolated wheel install smoke.
  - Current status: completed.
  - Exact committed evidence: profiles and self-tests at candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; baseline complete gate 419 tests
    in 64.08 seconds and duplicated documented sequence 136.15 seconds;
    accepted-candidate complete gate 555 tests in 81.84 seconds locally and
    78.28 seconds independently; install smoke 12.41 seconds locally; review
    evidence committed at `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

- [x] Concise actionable operator diagnostics
  - Required outcome: queue, detail, doctor, check, finish, handoff, and hook
    output distinguish blocked, stale, rejected, review-required, and
    human-decision states and name the exact missing proof and next safe action.
  - Objective completion evidence: JSON and text-output tests assert stable
    blocker codes, no premature authority commands, and actionable guidance.
  - Verification: focused CLI/operator tests plus command smoke tests and the
    complete repository gate.
  - Current status: completed.
  - Exact committed evidence: candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; actionable state and command
    routing in `agent_checks.py`, `agent_doctor.py` consumers, `agent_finish.py`,
    `agent_handoff.py`, `agent_loop.py`, `agent_next.py`, and `read_models.py`;
    JSON/text assertions across agent packet, completion, hook, and read-model
    tests; review ledger `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

- [x] Compatibility, migration, minimality, and documentation
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
  - Current status: completed.
  - Exact committed evidence: candidate
    `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903`; schema-v2 exact-binding
    migration, split-workspace atomicity, fixtures, synchronized packaged
    schemas/examples, and standard-library-only implementation; 12/12 docs
    checks, 555-test complete gate, and isolated install pass; compatibility
    review history at `6ef674f7047dafabfd5d5aadf1f83db5ca30bf21`.

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
