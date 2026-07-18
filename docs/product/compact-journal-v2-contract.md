# Compact Replayable Journal v2 Completion Contract

Work item: `WORK-A06D321334B74BFD878154776F299E57`

Baseline: `4881dd853ebcec73ce7a69ff7acefd4b637e2a21`

The contract distinguishes journal cost from the complete operator command.
Safety requirements are gates; performance targets are measured claims and are
not permission to skip validation.

## Exact Predecessor Safety Amendment

The timing claims below remain exact measurements of their cited historical
heads. They are not claims about the later predecessor-state repair. Exact v2
verification must derive the sealed v1 journal's declared state rather than
trusting a self-reported summary merely because the file bytes still match.

- [x] **Outcome:** all eight v1 state-summary fields in a v2 predecessor
  binding are recomputed from strict sealed history; a rehashed v2 statement
  cannot substitute false head, count, replay, transaction, coverage, or
  continuity claims. **Objective evidence:** one negative subtest independently
  changes and rehashes each field; every case fails at its exact JSON path with
  `JOURNAL_PREDECESSOR_STATE_MISMATCH`. **Verification:** `python3 -m unittest
  tests.test_governance_journal tests.test_governance_journal_crash
  tests.test_store_journal_integration`. **Status:** implemented; 42 focused
  tests pass. **Exact committed proof:**
  `cb67ab67c48a49b238936b87d3b02cd36dfd5bde`.

- [x] **Outcome:** the correctness cost of exact legacy verification is
  measured and attributed rather than hidden or optimized by trusting a
  persisted cache. **Objective evidence:** the 61 MB / 222-record dogfood v1
  journal verifies directly in 9.29 seconds / 32,288 KB RSS; after activation
  on a temporary copy, linked-v2 verification takes 9.83 seconds / 36,356 KB
  RSS. **Verification:** `/usr/bin/time` around `palari history --verify
  --json`, before and after `history --checkpoint` on the temporary copy.
  **Status:** safety repair intentionally supersedes the historical subsecond
  linked-v2 claim; full parsing is required to reject a fabricated but
  internally rehashed summary. No persisted cache authorizes governance.
  **Exact committed proof:** implementation
  `cb67ab67c48a49b238936b87d3b02cd36dfd5bde`; measurement applies to that
  exact code.

- [x] **Outcome:** v2 mutations store deterministic value deltas instead of a
  repeated full `after_projection`, while every checkpoint remains an
  authoritative content-bound replay base. **Objective evidence:** compactness,
  exact replay, non-canonical delta, digest, reorder, duplicate-terminal, and
  truncation tests. **Verification:** `python3 -m unittest
  tests.test_governance_journal`. **Status:** implemented and focused tests pass.
  **Exact committed proof:** `13c7be140e8adaf2dba90a9aa26a33314696a45f`,
  with canonical counterexample repairs at
  `af4412597dcd1000010ef082b05a07cc55ed2106` and
  `53400beeb3ab833b22fc3eb056ae0d7549874141`.

- [x] **Outcome:** verification is streaming and bounded by one workspace
  projection plus one record, not the complete journal payload or record list.
  **Objective evidence:** v2 verification succeeds while the v1 record-list
  materializer is patched to fail; dogfood peak RSS is below 100 MB.
  **Verification:** focused tests and three-run `/usr/bin/time` measurements.
  **Status:** implemented; measured agent-next 84 MB, queue 83 MB, state 83 MB.
  **Exact committed proof:** `13c7be140e8adaf2dba90a9aa26a33314696a45f`.

- [x] **Outcome:** strict v1 behavior remains readable and appendable, and v2
  activation is explicit, idempotent, continuity-preserving, and never rewrites
  the predecessor. **Objective evidence:** exact sealed v1 bytes are unchanged;
  the v2 checkpoint binds their SHA-256, length, head, replay digest, counts, and
  continuity. **Verification:** focused migration and predecessor-tamper tests.
  **Status:** implemented. **Exact committed proof:**
  `13c7be140e8adaf2dba90a9aa26a33314696a45f`.

- [x] **Outcome:** crash boundaries, pending retries, every committed prefix,
  corruption, fork/reorder, predecessor changes, and workspace divergence fail
  closed or recover idempotently. **Objective evidence:** focused negative and
  crash-injection suite. **Verification:** `python3 -m unittest
  tests.test_governance_journal_crash tests.test_governance_journal`.
  **Status:** 34 focused journal/store tests pass. **Exact committed proof:**
  `13c7be140e8adaf2dba90a9aa26a33314696a45f`, with prefix and
  canonical-delta repairs at `af4412597dcd1000010ef082b05a07cc55ed2106`
  and `53400beeb3ab833b22fc3eb056ae0d7549874141`.

- [x] **Outcome:** compact journaled mutation overhead remains below two
  seconds. **Objective evidence:** 20 mutations of an 800 KB projection after
  v2 activation measured median 0.1563 s and maximum 0.2118 s.
  **Verification:** deterministic local stdlib benchmark recorded in the work
  packet evidence. **Status:** target met. **Exact committed proof:**
  `13c7be140e8adaf2dba90a9aa26a33314696a45f`.

- [x] **Outcome:** complete dogfood `agent next`, `queue`, and `state` medians
  are below one second. **Objective evidence:** three-run wall/RSS measurement.
  **Verification:** `/usr/bin/time` around each command. **Status:** met after
  compact v2 plus bounded request-local pure path normalization: medians are
  0.75 s, 0.65 s, and 0.63 s respectively. Raw journal verification remains
  about 0.30 s/28 MB and no persisted cache authorizes governance. **Exact
  committed proof:** compact journal `13c7be140e8adaf2dba90a9aa26a33314696a45f`,
  canonical-delta repairs `af4412597dcd1000010ef082b05a07cc55ed2106`
  and `53400beeb3ab833b22fc3eb056ae0d7549874141`, and bounded pure cache
  `a2b99fbdcb3c0e2b3f5e0a11f06b4eef6d08a2f2`.

- [x] **Outcome:** complete repository, package-install, docs, schema/fixture,
  security, and CLI verification pass at the exact candidate head. **Objective
  evidence:** authoritative verification logs. **Verification:**
  `./scripts/verify.sh`, `./scripts/install_smoke.sh`, and `palari docs check
  --json`. **Status:** `verify.sh` passed 883 tests across 46 modules, style,
  schema/fixtures, CLI smokes, and 18 PCAW vectors; wheel install smoke, docs
  check, and dogfood validation passed. **Exact committed proof:**
  `1b09120d01c9804d30844f7091c46f8887a30675`.
