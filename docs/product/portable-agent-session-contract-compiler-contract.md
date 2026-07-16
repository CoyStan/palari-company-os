# Portable Agent Session Contract Compiler v1 — Completion Contract

Work item: `WORK-DDDCF6BD8DB248CFA51B68FC6CC167BC`

Baseline: `a4d0c8c33e2d1233e96b8453b5222220da706283`

Status values are `pending`, `in progress`, `blocked`, or `completed`. A
completed item must replace `pending exact commit` with the exact committed
proof. No checkbox is complete merely because code or prose exists.

- [ ] **Outcome:** Preserve the approved five-stage blueprint execution
  sequence in the canonical roadmap, with dependencies, deferrals, non-goals,
  and actionability requirements.
  **Objective evidence:** roadmap text names all five stages and explicitly
  separates deferred infrastructure.
  **Verification:** `palari docs check --json` and roadmap inspection.
  **Status:** in progress; implemented and verified, awaiting exact commit.
  **Exact committed proof:** pending exact commit.

- [ ] **Outcome:** Compile a deterministic provider-neutral session contract
  from the current bounded agent packet without timestamps, absolute paths,
  secrets, provider content, or newly granted authority.
  **Objective evidence:** focused determinism, canonicalization, blocked-packet,
  and data-minimization tests.
  **Verification:** `python3 -m unittest tests.test_agent_session_contract`.
  **Status:** in progress; implemented and verified, awaiting exact commit.
  **Exact committed proof:** pending exact commit.

- [ ] **Outcome:** Expose the portable contract through one justified existing
  `agent` command group surface and persist the exact contract when ready work
  is claimed.
  **Objective evidence:** JSON/text CLI smokes plus a claim that binds the
  contract digest and workspace-relative contract path.
  **Verification:** focused session-contract and agent-packet tests.
  **Status:** in progress; implemented and verified, awaiting exact commit.
  **Exact committed proof:** pending exact commit.

- [ ] **Outcome:** Detect missing, malformed, tampered, or authority-stale
  persisted contracts and fail closed with a concise next safe action.
  **Objective evidence:** negative tests mutate contract bytes, authority
  fields, paths, and packet scope and observe failed claim/check status.
  **Verification:** focused session-contract, runtime, and packet tests.
  **Status:** in progress; the first exact-head review found and the repair now
  closes a missing-field downgrade from new claims into legacy compatibility.
  **Exact committed proof:** pending exact commit.

- [ ] **Outcome:** Report enforcement honestly so a portable declaration is
  never described as native sandbox enforcement, while existing Claude hooks
  remain compatible.
  **Objective evidence:** stable enforcement-property statuses and limitation
  tests; unchanged Claude hook suite.
  **Verification:** session-contract tests and `tests.test_claude_hooks`.
  **Status:** in progress; implemented and verified, awaiting exact commit.
  **Exact committed proof:** pending exact commit.

- [ ] **Outcome:** Preserve package minimality, existing workspace/schema and
  CLI compatibility, concurrency semantics, and zero new runtime dependencies.
  **Objective evidence:** no dependency or workspace-schema additions; existing
  packet/claim fixtures still load; unrelated workspace mutations do not widen
  a contract's authority.
  **Verification:** focused compatibility tests, install smoke, and complete
  repository verification.
  **Status:** in progress; implemented and verified, awaiting exact commit.
  **Exact committed proof:** pending exact commit.

- [ ] **Outcome:** Publish operator and agent documentation that explains the
  contract lifecycle, enforcement levels, limitations, inspection command, and
  safe adapter boundary.
  **Objective evidence:** agent contract, command reference, repo map, invariant
  docs, and root agent guidance agree with implemented behavior.
  **Verification:** `./bin/palari docs check --json` and documentation tests.
  **Status:** in progress; implemented and verified, awaiting exact commit.
  **Exact committed proof:** pending exact commit.

- [ ] **Outcome:** Prove the exact committed candidate through focused tests,
  affected tests, schema/fixture validation, CLI smokes, documentation checks,
  complete verification, isolated installation smoke, and fresh independent
  review.
  **Objective evidence:** recorded commands, timing, exact head, and ACCEPT or
  repaired review history.
  **Verification:** repository-required verification stack.
  **Status:** in progress. Exact head
  `f464a7420b6aaee69ab2cb089843046e88f7a6c1` passed the complete profile in
  53.22 seconds, isolated install smoke in 11.76 seconds, and docs check in
  0.24 seconds. Independent review correctly returned changes-requested; the
  repair needs a new exact commit, proof run, and review.
  **Exact committed proof:** pending exact commit.

## Independent Review History

1. `f464a7420b6aaee69ab2cb089843046e88f7a6c1`: changes-requested in
   `REVIEW-SESSION-CONTRACT-ARCHITECT-F464A7420B6A-REJECT`. A new claim could
   lose both contract fields and be mistaken for a historical claim, and this
   completion contract still contained pre-commit placeholders. Claim schema
   v2 and this evidence refresh repair those findings; fresh exact-head review
   remains required.
