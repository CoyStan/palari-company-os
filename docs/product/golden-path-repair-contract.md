# Golden Path Repair v1 Completion Contract

Work item: `WORK-C11EE25A4D42414BBAD382121E89E070`

Baseline commit: `4881dd853ebcec73ce7a69ff7acefd4b637e2a21`

Baseline reproduction in a real temporary Git repository:

```text
palari init --palari Agent --json
palari work add "First task" --write docs/notes.md --json
palari agent start --next --as PALARI-AGENT --json

IMMUTABLE_SCOPE_AUTHORITY_WORKSPACE_GIT_BLOB
immutable scope authority workspace Git blob is unreadable
```

The completion condition is every outcome below being mechanically proven. A
count of changes is not a completion condition.

- [x] The documented fresh committed Git-repository flow reaches a valid claim
  without an undocumented operator step.
  - Required outcome: `init -> work add -> agent start --next` succeeds for the
    identity returned by initialization.
  - Objective evidence: a real temporary Git repository creates a committed
    authority origin and returns `start.status: claimed` for the opaque work ID.
  - Verification: `python3 -m unittest
    tests.test_operator_journeys.OperatorJourneyTests.test_fresh_committed_repo_runs_init_start_and_advance_without_proof_ids`
  - Status: complete; focused and complete verification passed.
  - Exact committed proof: `ed877ed1c03179ce5895fa6533a4c628dcf2d787` in
    `src/palari_company_os/onramp.py` and `tests/test_operator_journeys.py`.

- [x] First-adoption authority is anchored without laundering unrelated work.
  - Required outcome: one explicitly invoked, local, path-limited bootstrap
    commit contains the starter governance projection and only newly generated
    agent guidance; it grants no review or human authority.
  - Objective evidence: the anchor commit excludes a separately staged file,
    leaves that file staged, and reports its exact commit and paths. A later
    retry observes the existing blob and does not rewrite it.
  - Verification: `python3 -m unittest
    tests.test_onramp.InitTests.test_init_anchors_only_generated_adoption_files_in_a_committed_repo
    tests.test_onramp.WorkAddTests.test_work_add_idempotently_recovers_an_unanchored_git_workspace`
  - Status: complete; focused and complete verification passed.
  - Exact committed proof: `ed877ed1c03179ce5895fa6533a4c628dcf2d787` in
    `src/palari_company_os/onramp.py` and `tests/test_onramp.py`.

- [x] A newly adopted repository has useful agent-facing instructions before a
  claim is granted.
  - Required outcome: missing `AGENTS.md` and the five canonical `docs/agent/`
    files are created, while existing project instructions are preserved.
  - Objective evidence: the start packet reports documentation state `ready`;
    preservation tests prove existing `AGENTS.md` bytes are unchanged.
  - Verification: `python3 -m unittest tests.test_onramp.InitTests
    tests.test_operator_journeys.OperatorJourneyTests.test_fresh_committed_repo_runs_init_start_and_advance_without_proof_ids`
  - Status: complete; focused and complete verification passed.
  - Exact committed proof: `ed877ed1c03179ce5895fa6533a4c628dcf2d787` in
    `src/palari_company_os/onramp.py`, `tests/test_onramp.py`, and
    `tests/test_operator_journeys.py`; generated-path preflight that rejects a
    non-directory parent before any bootstrap write is committed at
    `1c3664c0de12c5eb8eed5f718a168b66d904288a` in
    `src/palari_company_os/onramp.py` and `tests/test_onramp.py`.

- [x] A manually assembled unanchored workspace fails closed with the real
  recovery action.
  - Required outcome: missing immutable authority never falls back to mutable
    current state and the diagnostic contains one exact, path-limited Git
    command.
  - Objective evidence: the stable error code remains
    `IMMUTABLE_SCOPE_AUTHORITY_WORKSPACE_GIT_BLOB`; its message contains one
    `next action`, exact projection paths, `git add -f`, and `commit --only`.
  - Verification: `python3 -m unittest
    tests.test_operator_journeys.OperatorJourneyTests.test_unanchored_manual_workspace_fails_with_one_exact_recovery_action`
  - Status: complete; focused and complete verification passed.
  - Exact committed proof: `ed877ed1c03179ce5895fa6533a4c628dcf2d787` in
    `src/palari_company_os/agent_runtime.py` and
    `tests/test_operator_journeys.py`.

- [x] The network-free demo teaches the actual operator loop rather than
  manual proof-record ceremony.
  - Required outcome: the demo runs `start --next`, shows an unsafe path being
    rejected, commits one allowed path, then runs one `agent advance` that
    deterministically records proof and completes R1/light local work.
  - Objective evidence: the transcript ends with `Status: completed`, contains
    no copied `RECEIPT-ID` or `EVIDENCE-ID` command, and never reports
    `Docs: missing`.
  - Verification: `python3 -m unittest tests.test_demo` and
    `palari demo --no-pause --json`.
  - Status: complete; focused and complete verification passed.
  - Exact committed proof: `ed877ed1c03179ce5895fa6533a4c628dcf2d787` in
    `src/palari_company_os/demo.py` and `tests/test_demo.py`.

- [x] Public guidance describes the mechanical bootstrap and its authority
  limitations honestly.
  - Required outcome: README, quickstart, and agent contract present the same
    no-extra-ceremony path and state that the anchor is not review, acceptance,
    or authenticated human attribution.
  - Objective evidence: `palari docs check --json` reports no blocking docs
    failure and public examples use `start --next` followed by `advance`.
  - Verification: `palari docs check --json` and complete repository
    verification.
  - Status: complete; documentation and complete verification passed.
  - Exact committed proof: `ed877ed1c03179ce5895fa6533a4c628dcf2d787` in `README.md`,
    `docs/product/quickstart.md`, and `docs/product/agent-contract.md`.

## Non-claims

- The bootstrap commit is local. It does not push, merge, deploy, or perform an
  external write.
- Git commit identity is attribution metadata, not authenticated human
  authority.
- Existing guidance is never rewritten automatically.
- A repository already carrying committed workspace authority is never
  silently re-anchored from mutable current bytes.

## Candidate Verification

The exact implementation commit above passed:

- `python3 -m unittest tests.test_onramp tests.test_demo
  tests.test_operator_journeys tests.test_agent_packets` — 140 focused tests;
- `./scripts/verify.sh complete` — 882 tests across 46 modules, style, schemas,
  CLI smokes, trusted-code manifest, and 18 PCAW conformance vectors;
- `./scripts/install_smoke.sh` — isolated wheel installation passed;
- `palari docs check --json` — 12 checks passed with no warnings;
- `palari demo --no-pause --json` — final deterministic advance reported
  `Status: completed`.
