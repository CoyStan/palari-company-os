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

- [x] Pure deterministic advance planner
  - Required outcome: one pure planner consumes the current work, packet,
    claim, Git observation, proof state, and verification attestations and
    returns an ordered plan, blockers, expected state, and plan digest without
    mutation or subprocess execution.
  - Objective completion evidence: repeated and permuted-input tests produce
    byte-identical plans; stale packet, claim, head, or proof changes produce a
    different digest or a fail-closed blocker.
  - Verification command or artifact: `tests.test_agent_advance` planner and
    state-table tests.
  - Current status: completed.
  - Exact committed evidence when completed:
    `0dded80ab52016c4b3fb548c6c6d769e8516b6c7` adds the pure planner and
    deterministic/permuted-input state-table tests; planner p95 over 10,000
    in-process calls was 0.0372ms.

- [x] One idempotent safe-advance command
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
  - Current status: completed. The dogfood invocation derived the full
    `cdefca7...8ed4dbf` range, ran all required profiles, created exact R4
    receipt/evidence, released its claim, and stopped at independent review.
  - Exact committed evidence when completed:
    `e3264cca10059a2e2d252c7b78a2949d88de650d` commits
    `ATTEMPT-REPO-0026-R4`,
    `RECEIPT-ADVANCE-WORK-REPO-0026-8ED4DBF98355`, and
    `EVIDENCE-ADVANCE-WORK-REPO-0026-8ED4DBF98355`, whose manifest, artifact
    bytes, receipt chain, output coverage, and current binding all verify.

- [x] Crash-safe proof reconciliation
  - Required outcome: verification occurs outside the workspace lock; before
    mutation the executor rechecks the plan digest, packet, claim, Git head,
    worktree, and workspace state; the ordered proof projection commits through
    the existing one-writer transaction and journal path.
  - Objective completion evidence: crash injection at every new boundary and
    concurrent mutation tests prove safe resume or actionable fail-closed
    diagnosis without partial false proof.
  - Verification command or artifact: advance crash/concurrency suite and
    journal replay verification.
  - Current status: completed.
  - Exact committed evidence when completed:
    `0dded80ab52016c4b3fb548c6c6d769e8516b6c7` adds one journaled proof
    transaction plus injected pre-replace abort/retry and post-replace
    commit-recovery tests in `tests/test_agent_advance.py`;
    `609821a851cb3d535c5786b306a7d2238bba8ef8` moves claim/Git/scope
    preflight before recovery and proves rejected recovery does not append;
    `55791a179e34396902745c5c2ddf033382e6df57` additionally authenticates
    the pending transaction's command, action, actor, exact proof objects, and
    exclusive before/after object delta before commit or abort recovery;
    `105ab4b37b0274139c71784959a0494bcfe3093c` derives the exact deterministic
    object IDs and field projection from the claim-range preflight, rejects
    work-authority expansion and proof-ID substitution, validates projected
    evidence, and proves both pending states remain byte-unchanged on mismatch;
    `6c43a62d628e04a16297cf74f1f68b0b91f302f6` rejects ungenerated worker,
    claim, boundary, external-write, context, action, and summary metadata in
    a proof-like recovery projection; `94cf1ca852148f51047910dd8215105d4e5db7a7`
    also derives the exact receipt-chain predecessor and required built-in
    verification-profile command identities before recovery;
    `f60bd7f3cb5feb6648c979a4139fe3bffeb58909` binds factual receipt narration
    into transaction metadata, rejects authority/external-action claims, and
    matches the exact deterministic attestation IDs and cache keys;
    `6d9edef9871276e94a3912a6622fa1888abe40cf` freshly reruns every built-in
    profile before interrupted proof recovery, compares the actual results,
    and binds the exact commit list; `27fb8bafe90430d39b091612e25906022f53c9fe`
    replaces free-form governed narration with one deterministic action and
    rechecks claim, Git, scope, and pending identity after recovery profiles;
    `2990eaf0e3dc11deccda9137b34547fd3edec1f0` binds every generated proof
    timestamp to the exact Git candidate's immutable commit timestamp and
    requires current output-binding semantics; and
    `ff18c451f958ba8102ab02a7808ce3f85e2c171c` holds the final workspace,
    pending-transaction comparison, and terminal append behind the existing
    one-writer lock, with exact mismatch and lock-ownership tests.
    `d9d1b5bd60d5c971eaade1c584ed6f28568234e5` additionally proves both
    legacy-claim pending states remain byte-identical under `--dry-run`.

- [x] Exact verification records and governed-proof reuse
  - Required outcome: verification profiles are explicit argument vectors, not
    executable prose; run records bind the exact head, clean tree, profile
    digest, runner/source state, platform, and interpreter. Editable local cache
    files are advisory and can never authorize new evidence; only current proof
    already reconciled into governed evidence may skip subprocess verification.
  - Objective completion evidence: exact governed-proof resume avoids subprocess
    execution; forged cached passes are rerun and cannot create passing evidence;
    head, dirty state, profile, Python, platform, source, failure, timeout,
    malformed result, and contradictory-result changes rerun or fail closed.
  - Verification command or artifact: attestation unit/adversarial tests and
    exact serialized fixtures.
  - Current status: completed.
  - Exact committed evidence when completed:
    `0dded80ab52016c4b3fb548c6c6d769e8516b6c7` adds strict exact-state run
    records; `bb9e5bad61fd438cac17e8a9f848000b0b6d2398` binds validated workspace
    bytes into the claim fast path; `ba274a232593b244513f509217084b1082bb4099`
    makes the file cache advisory, reruns forged passes, and proves symlink
    rejection creates no outside directory;
    `e3041ff45329c4a368ab5a896cd3253376675b2f` aligns public CLI help with
    the advisory-cache contract and adds a regression assertion for that text.

- [x] Fast planning and non-repeated verification
  - Required outcome: planning stays independent of complete verification;
    repeated submission of an already reconciled exact proof validates and
    reuses governed evidence instead of rerunning the full gate. An ungoverned
    cache file is never sufficient.
  - Objective completion evidence: deterministic local benchmark records the
    pure planner p95 below 10ms, public cold-process `agent advance --dry-run`
    no slower than the 0.40s original loop baseline, and an exact-proof resume
    advance below 1s; affected-area verification targets a median below 5s when
    a safe mapping exists. Public cold-process time is reported separately from
    planner time so Python/parser startup is visible rather than misattributed.
  - Verification command or artifact: performance test/measurement artifact,
    subprocess-spy tests, and before/after timing table.
  - Current status: completed. Planner p95 is 0.0372ms; the exact-claim fast
    path reduced 20-run cold dry-run median to 0.29s and p95 to 0.33s versus the
    0.35-0.40s loop baseline. The final deterministic affected mapping runs 96
    tests across advance, completion, transitions, and read models in 23.85s;
    it remains intentionally broader than a single-module focused check. Five
    dogfood exact-proof resumes ran in 0.53s, 0.52s, 0.57s, 0.58s, and 0.58s:
    median 0.57s without subprocess verification or proof duplication.
  - Exact committed evidence when completed:
    `29d20dd7d75a2f8edd85f91e5ce3b53dcbf7f563` contains the accepted planner,
    fast path, advisory-cache behavior, and focused mappings;
    `e3264cca10059a2e2d252c7b78a2949d88de650d` contains the exact governed
    proof used by the sub-second resume measurement.

- [x] Full verification remains authoritative
  - Required outcome: focused checks and governed exact-proof resume accelerate iteration without
    weakening the required complete gate before acceptance; advisory cache
    contents, failed verification, or stale proof can never produce passing
    evidence.
  - Objective completion evidence: negative tests cover failed focused and
    complete profiles, cached failure, incomplete mapping, altered tests, and
    stale result rejection. Final complete-gate median does not exceed the
    43.56s baseline by more than 10% without explicit safety-value evidence.
  - Verification command or artifact: `./scripts/verify.sh`, three-run timing
    where required, and installed-package smoke.
  - Current status: completed. The unoptimized repaired gate passed at
    49.08s, 47.88s, and 48.76s (48.76s median, 11.94% over baseline). Exact
    parallelization of the existing read-only CLI smokes in isolated temporary
    outputs preserved every command. The exact `d9d1b5bd...` candidate passed
    at 42.22s, 43.74s, and 42.30s: median 42.30s, 2.89% faster than the 43.56s
    baseline and inside the 10% ceiling. Exact-head independent review of
    `29d20dd7...` ran the later 700-test gate across 42 modules plus style,
    schemas/fixtures, CLI smokes, trusted-code accounting, and 18/18 PCAW
    vectors. Dogfood then recorded complete in 43.347s, installed-package smoke
    in 11.695s, and docs check in 0.258s, all passed.
  - Exact committed evidence when completed:
    `29d20dd7d75a2f8edd85f91e5ce3b53dcbf7f563` received exact-head ACCEPT with
    the 700-test complete gate, install smoke, and docs check passing;
    `e3264cca10059a2e2d252c7b78a2949d88de650d` commits the independently
    verifiable dogfood attestations for candidate `8ed4dbf9835582b839206aa68bf185e0a04b0339`.

- [x] Scope, source, authority, and protected-dirt boundaries remain closed
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
  - Current status: completed.
  - Exact committed evidence when completed:
    `0dded80ab52016c4b3fb548c6c6d769e8516b6c7` preserves the original
    claim/witness preflight and adds fail-closed planner/cache/integration
    negatives; `9f4c7bf0f175fc76bb864ca9df2a12cf1ea1a96e` safely prefilters lexical
    candidates before canonical boundary resolution, with filesystem,
    path-policy, packet, advance, and done suites passing.

- [x] Existing agent surfaces remain compatible and simpler
  - Required outcome: `agent done` retains its R1 contract and shares the exact
    claim-range/scope preflight used by the advance engine;
    brief/start/check/finish/handoff/doctor/loop remain valid; `advance` is one
    nested command, not a new top-level group.
  - Objective completion evidence: existing public-surface snapshots and agent
    suites pass; a before/after command count proves the higher-risk happy path
    collapses from manual lifecycle commands to one advance invocation.
  - Verification command or artifact: compatibility suites, public command
    snapshot, docs examples, and deterministic ceremony measurement.
  - Current status: completed.
  - Exact committed evidence when completed:
    `0dded80ab52016c4b3fb548c6c6d769e8516b6c7` adds only nested command
    155, keeps legacy `agent done` IDs/behavior, and updates the exact public
    snapshot; `8a903b430952e2bef334c51c2a8794b14b572fb8` removes duplicate packet
    compilation from shared preflight.

- [x] Minimal, documented, independently reviewed delivery
  - Required outcome: standard library only, no daemon, provider, hook, React,
    Rust/C++ rewrite, external write, or commercial application change; docs
    distinguish deterministic conformance from semantic and human review; a
    fresh independent reviewer returns ACCEPT on the exact committed head.
  - Objective completion evidence: docs check, schema/fixture validation,
    isolated install, trusted-code accounting, complete verification, exact
    review report, and founder packet.
  - Verification command or artifact: `./bin/palari docs check --json`,
    `./scripts/install_smoke.sh`, `./scripts/verify.sh`, and exact-head review.
  - Current status: completed. Runtime dependencies remain empty and current
    docs/style checks pass. Exact review of `df4fb862...` rejected unsafe resume,
    cache authority, and symlink ordering; exact review of `ba274a232...`
    confirmed those repairs but rejected recovery-before-scope ordering and
    terminal journal bypass. `609821a851cb3d535c5786b306a7d2238bba8ef8`
    preflights before journal mutation, proves rejected recovery leaves journal
    bytes unchanged, and restores terminal continuity validation; its fresh
    review rejected recovery of a valid but unrelated pending transaction.
    `55791a179e34396902745c5c2ddf033382e6df57` binds recovery to the exact
    agent-proof transaction and rejects unrelated commit and abort recovery
    without changing journal bytes; its fresh review then rejected arbitrary
    bound-record fields and proof-ID substitution. Exact repair
    `105ab4b37b0274139c71784959a0494bcfe3093c` binds the deterministic IDs,
    permitted field delta, base/head/change range, artifacts, sources, outputs,
    and projected evidence before recovery; its fresh review then rejected
    substituted new-attempt claim and worker fields. Exact repair
    `6c43a62d628e04a16297cf74f1f68b0b91f302f6` rejects all ungenerated attempt
    attribution/boundary fields and external or ungenerated receipt claims;
    its fresh review then rejected contradictory receipt narration and forged
    verifier commands. `94cf1ca852148f51047910dd8215105d4e5db7a7` binds receipt
    continuity and built-in profile identities; exact repair
    `f60bd7f3cb5feb6648c979a4139fe3bffeb58909` binds the transaction's receipt
    action, rejects authority/external-action summaries, and derives exact
    attestation IDs and cache keys; its fresh review correctly rejected that
    predictable strings still did not prove execution and that commit/timestamp
    auxiliaries remained open. Exact repair
    `6d9edef9871276e94a3912a6622fa1888abe40cf` requires fresh profile execution
    before either recovery mutation, compares actual attestations, and validates
    the exact commit list. Its fresh review rejected a post-verification race,
    free-form narration, coherent timestamp substitution, and downgraded output
    binding. Exact repair `2990eaf0e3dc11deccda9137b34547fd3edec1f0`
    closed those four findings with deterministic candidate-bound fields; its
    fresh review then rejected the remaining gap between the final state recheck
    and terminal journal append. Exact repair
    `ff18c451f958ba8102ab02a7808ce3f85e2c171c` serializes that comparison and
    append through the workspace writer lock and proves mismatch leaves the
    journal unchanged. Its fresh review then found a legacy-claim dry-run path
    that entered recovery; `d9d1b5bd60d5c971eaade1c584ed6f28568234e5`
    returns every dry-run before verification or mutation and proves both
    pending states byte-identical. Review of that exact commit found the
    implementation correct but rejected stale `--refresh-verification` help;
    `e3041ff45329c4a368ab5a896cd3253376675b2f` aligns the public text with
    advisory cache behavior. Fresh review of coherent exact head
    `29d20dd7d75a2f8edd85f91e5ce3b53dcbf7f563` returned ACCEPT after 101
    focused tests, the 700-test complete gate, install smoke, docs check, and
    independent recovery/authority inspection. Dogfood proof at `e3264cca...`
    then mechanically reproduced the complete/install/docs profile and stopped
    at the human review boundary.
  - Exact committed evidence when completed:
    `29d20dd7d75a2f8edd85f91e5ce3b53dcbf7f563` is the exact independently
    accepted coherent implementation/documentation head;
    `e3264cca10059a2e2d252c7b78a2949d88de650d` is the exact committed dogfood
    proof record. Standard-library runtime dependencies remain zero.

## Deferred

Codex hooks, Claude hook redesign, automatic staging or committing, AI-authored
semantic review, signing/key custody, live integrations, external effects, and
commercial UI remain separate future work. A later hook adapter should call
this deterministic engine rather than implement another policy copy.
