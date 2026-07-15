# Proof-Carrying Governance Contract

This is the completion contract for `WORK-REPO-0024` on branch
`codex/proof-carrying-ai-work-kernel`. It is an active product-safety contract,
not a roadmap. A checkbox may be marked complete only when its objective
evidence is committed and the named verification passes.

Accepted dependency head: `5727fa4cc99396229db3c392f0227db225989cc2`.

Repository comparison base: `2eea39e9d3d70baa69d987dba50decbcb63bc51e`.

Pre-work authoritative verification on 2026-07-14:

- `./scripts/verify.sh`: 555 tests and style passed in 77.934 seconds.
- `./scripts/install_smoke.sh`: passed.
- `./bin/palari docs check --json`: 12 checks passed.
- Dogfood workspace validation: passed.

Status vocabulary: `pending`, `in progress`, `completed`, or `blocked`.

## Required Outcomes

- [x] One deterministic governance kernel
  - Required outcome: workspace validation, lifecycle gates, proof export, and
    proof verification normalize into one pure governance case and derive the
    same bounded lifecycle state without wall-clock, locale, path, provider, or
    process dependence.
  - Objective completion evidence: equivalence tests compare existing workspace
    behavior with normalized PCAW predicates; a deterministic finite-state
    explorer reaches a fixed point and proves that accepted/completed states
    imply current receipt, evidence, review, human quorum, and acceptance.
  - Verification command or artifact: `python3 -m unittest
    tests.test_governance_kernel tests.test_governance_explorer` and the
    complete repository gate.
  - Current status: completed.
  - Exact committed evidence when completed: implementation and fixed-point
    explorer in `d23f047ddf47de38a859d399040bcfb7aa9c4169`; exact-proof and
    state-claim corrections in `cc7a4f66c8781901cd2039cb3389d98811eb1e8b`;
    retained and reverified at final implementation head
    `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`.

- [x] Deterministic PCAW v1 statement export
  - Required outcome: `palari proof export WORK-ID --output FILE --json`
    exports blocked, incomplete, and accepted work as an in-toto Statement v1
    whose subjects bind the exact normalized work state and declared output
    artifacts; identical logical input produces byte-identical output.
  - Objective completion evidence: repeated exports match across absolute
    paths, time zones, locales, and process runs and contain no export time,
    absolute paths, source contents, provider payloads, or secrets.
  - Verification command or artifact: `python3 -m unittest
    tests.test_pcaw_protocol` plus valid conformance vectors under
    `spec/pcaw/v1/vectors/valid/`.
  - Current status: completed.
  - Exact committed evidence when completed: exporter, path/time-zone/locale
    determinism tests, and valid vectors in
    `d23f047ddf47de38a859d399040bcfb7aa9c4169`; stale stored-binding and
    claimed-state repairs in `cc7a4f66c8781901cd2039cb3389d98811eb1e8b`.

- [x] Strict offline PCAW v1 verification
  - Required outcome: `palari proof verify FILE [--subject-root DIR]
    [--statement-only] --json` derives lifecycle state independently, verifies
    subjects by default, fails closed on unsafe or contradictory proof, and
    emits stable diagnostics with codes, JSON paths, messages, next safe
    actions, and explicit security limitations.
  - Objective completion evidence: an isolated installed wheel verifies valid
    and invalid bundles without repository access, network, credentials,
    providers, or mutable workspace state; statement-only mode clearly reports
    that artifact integrity and acceptance are not fully verified.
  - Verification command or artifact: `python3 -m unittest
    tests.test_pcaw_protocol` and
    `./scripts/install_smoke.sh`.
  - Current status: completed.
  - Exact committed evidence when completed: verifier and isolated-wheel smoke
    in `d23f047ddf47de38a859d399040bcfb7aa9c4169`; structured proof/root
    failures in `bc4b4418d4ff95114dc2cd12d9f9bf68ba523dd3`; contained subject
    read failures in `50594e93fe4412791d99cace97937c1f5fe704c3`, retained and
    reverified at final implementation head
    `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`. Final isolated install
    smoke passed in 12.69 seconds.

- [x] Strict canonical JSON and protocol schema
  - Required outcome: PCAW inputs and outputs obey the supported I-JSON/RFC
    8785 subset and reject duplicate keys, floats, unsafe integers, invalid
    Unicode, ambiguous timestamps, unsafe paths, unknown fields, and unsupported
    algorithms.
  - Objective completion evidence: canonicalization vectors include Unicode
    ordering and escaping; negative vectors name the exact rejected JSON path
    and stable diagnostic code; semantically identical statements hash equally.
  - Verification command or artifact: `python3 -m unittest
    tests.test_canonical_json tests.test_pcaw_protocol` and
    `spec/pcaw/v1/statement.schema.json`.
  - Current status: completed.
  - Exact committed evidence when completed: canonicalizer, schema, and
    positive/negative vectors in
    `d23f047ddf47de38a859d399040bcfb7aa9c4169`; all 18 conformance vectors
    passed at final implementation head
    `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`.

- [x] Exact proof, review, and human-authority verification
  - Required outcome: every verified accepted result proves terminal attempt
    state, current receipt/evidence binding, independent reviewer identity,
    current review proof, qualified human quorum, current acceptance, source
    boundary compliance, and absence of contradictory or revoked authority.
  - Objective completion evidence: negative tests and vectors reject stale or
    contradictory decisions, builder/reviewer collision, changed contracts,
    missing receipts, stale manifests, insufficient quorum, and revoked or
    mismatched acceptance.
  - Verification command or artifact: `python3 -m unittest
    tests.test_governance_kernel tests.test_pcaw_protocol` and the conformance
    corpus.
  - Current status: completed.
  - Exact committed evidence when completed: one-to-one evidence subjects,
    qualified acceptance ownership, reviewer independence, human quorum,
    current exact bindings, and negative tests in
    `cc7a4f66c8781901cd2039cb3389d98811eb1e8b`; non-vacuous v1 output
    coverage, bounded artifact roots, and version-derived terminal validation
    in `021e23e6ec7454bff278537f3c648b428228cbfc`,
    `e77122048768fe4b96630b199b004deb0842d777`, and final implementation
    head `2379ba46d21f9ff7d6d9e9816a892d0d5c304af0`; nested-workspace
    governance normalization and revocation-safe repair startup in final
    implementation head `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`.

- [x] Safe subject and source boundaries
  - Required outcome: artifact verification uses canonical relative paths and
    rejects traversal, absolute paths, sibling-prefix confusion, symlink escape,
    missing/unreadable subjects, changed bytes, duplicate subjects, and
    unsupported digests.
  - Objective completion evidence: temporary-copy negative tests prove every
    named boundary fails closed without reading outside the selected subject
    root or mutating operator files.
  - Verification command or artifact: `python3 -m unittest
    tests.test_pcaw_protocol tests.test_filesystem_security`.
  - Current status: completed.
  - Exact committed evidence when completed: descriptor-pinned traversal,
    symlink and parent-swap tests in
    `cc7a4f66c8781901cd2039cb3389d98811eb1e8b`; cyclic path handling in
    `bc4b4418d4ff95114dc2cd12d9f9bf68ba523dd3`; `fstat`/read failure
    containment in `50594e93fe4412791d99cace97937c1f5fe704c3`; bounded-attempt
    root/allow/forbid failures stamp artifacts unsafe without fallback reads in
    `021e23e6ec7454bff278537f3c648b428228cbfc`, independently reverified at
    `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`.

- [x] Normative specification and portable conformance corpus
  - Required outcome: `spec/pcaw/v1/` contains the normative statement and
    predicate specification, schema, valid vectors, invalid vectors, stable
    diagnostic contract, falsifiable guarantees/non-guarantees, DSSE-compatible
    future envelope, and a dependency-free black-box conformance runner.
  - Objective completion evidence: the runner passes the installed Palari
    verifier and every vector declares its expected verified properties or
    diagnostic codes; the specification makes no mathematical-formalization or
    authenticated-identity claim.
  - Verification command or artifact: `python3
    spec/pcaw/v1/conformance.py -- ./bin/palari proof verify` and
    `python3 -m unittest tests.test_pcaw_protocol`.
  - Current status: completed.
  - Exact committed evidence when completed: normative specification, schema,
    dependency-free runner, and corpus in
    `d23f047ddf47de38a859d399040bcfb7aa9c4169`; exact evidence/subject
    mismatch vector in `cc7a4f66c8781901cd2039cb3389d98811eb1e8b`; final corpus is
    18/18 passing at `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`.

- [x] Staged replayable governance journal
  - Required outcome: legacy `.palari/history.jsonl` remains compatible while a
    separate versioned hash-chained journal begins at an explicit checkpoint;
    prepared events are fsynced before atomic workspace replacement and commit
    markers are fsynced afterward through one centralized transaction path.
  - Objective completion evidence: replaying every committed prefix yields its
    recorded logical workspace digest; truncation, forks, duplicate commits,
    reordering, workspace divergence, and continuity breaks fail closed; manual
    checkpoints acknowledge rather than erase discontinuity.
  - Verification command or artifact: `python3 -m unittest
    tests.test_governance_journal tests.test_store_journal_integration
    tests.test_history` and `palari history
    --verify --json` against temporary workspaces.
  - Current status: completed.
  - Exact committed evidence when completed: hash-chained journal, centralized
    store transaction integration, prefix replay, corruption cases, and
    history checkpoint/verify modes in
    `d23f047ddf47de38a859d399040bcfb7aa9c4169`, passing the final complete
    gate at `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`.

- [x] Crash-safe, idempotent journal recovery
  - Required outcome: interruption at every prepared/write/replace/commit
    boundary is detectable and either safely retryable or reported with an
    actionable fail-closed diagnosis; repeated recovery never duplicates a
    committed mutation.
  - Objective completion evidence: deterministic crash injection covers every
    transaction boundary and proves workspace/journal agreement or an explicit
    prepared-event recovery state.
  - Verification command or artifact: `python3 -m unittest
    tests.test_governance_journal_crash`.
  - Current status: completed.
  - Exact committed evidence when completed: prepared/apply/commit crash
    injection and retry/recovery tests in
    `d23f047ddf47de38a859d399040bcfb7aa9c4169`, passing the final complete
    gate at `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`.

- [x] Operator clarity and two-minute offline demonstration
  - Required outcome: proof and history commands explain valid, incomplete,
    blocked, stale, altered, statement-only, discontinuous, and unsupported
    states concisely; a network-free demo verifies a valid accepted artifact,
    alters one governed byte, and receives a precise rejection.
  - Objective completion evidence: JSON/text CLI tests assert stable messages
    and safe next actions; the documented demo runs successfully from an
    isolated installation.
  - Verification command or artifact: `python3 -m unittest
    tests.test_pcaw_protocol tests.test_history` and `./scripts/pcaw_demo.sh`.
  - Current status: completed.
  - Exact committed evidence when completed: structured diagnostics, CLI
    rendering, history guidance, and `scripts/pcaw_demo.sh` in
    `d23f047ddf47de38a859d399040bcfb7aa9c4169`; operational-path corrections
    in `bc4b4418d4ff95114dc2cd12d9f9bf68ba523dd3` and
    `50594e93fe4412791d99cace97937c1f5fe704c3`.

- [x] Compatibility, minimality, and trusted-code accounting
  - Required outcome: existing CLI/schema/examples/adapters remain compatible;
    no runtime dependency, provider call, secret access, signing key, background
    service, autonomous authority, push, merge, or deployment is added; verifier
    trusted-code size and import graph are published and justified.
  - Objective completion evidence: public-command snapshot, existing fixtures,
    isolated package smoke, dependency checks, docs validation, and complete
    verification pass; package version remains `0.2.0` while maturity language
    is aligned honestly.
  - Verification command or artifact: `./scripts/verify.sh`,
    `./scripts/install_smoke.sh`, `./bin/palari docs check --json`, and trusted
    code report under `spec/pcaw/v1/`.
  - Current status: completed.
  - Exact committed evidence when completed: compatibility snapshots, docs,
    install smoke, and trusted-code manifest in
    `d23f047ddf47de38a859d399040bcfb7aa9c4169`; final manifest at
    `50594e93fe4412791d99cace97937c1f5fe704c3` accounts for 5 files, 2,334
    source lines, and zero runtime dependencies. Package version remains
    `0.2.0`; the final implementation head is
    `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`.

- [x] Verification timing, independent exact-head review, and founder packet
  - Required outcome: the authoritative complete gate remains singular and
    equivalent; three-run median is compared with 77.934 seconds and any
    regression over 10% is corrected or explicitly justified by safety value;
    fresh reviewers inspect each repaired exact committed head until ACCEPT;
    the founder packet reports all required commits, properties, timings,
    reviews, compatibility, changed paths, non-claims, risks, deferrals, and
    rollback instructions.
  - Objective completion evidence: attributable focused/full test logs, exact
    review history, final ACCEPT recommendation, and a complete local founder
    packet with no push, PR, merge, deployment, or manufactured acceptance.
  - Verification command or artifact: three `./scripts/verify.sh` runs,
    `./scripts/install_smoke.sh`, schema/fixture/CLI/security/docs/conformance
    checks, and final exact-head review report.
  - Current status: completed locally with independent ACCEPT after the R3
    completion-path repair; fresh Palari human review and founder acceptance
    remain explicitly pending.
  - Exact committed evidence when completed: final implementation head
    `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`; 624 tests, style, 18/18
    conformance vectors, schemas/fixtures, CLI, security, docs/examples,
    dogfood, and demo passed in the authoritative complete gate at 42.92
    seconds. Three earlier exact-head complete-gate samples were
    51.91, 43.87, and 44.58 seconds (44.58-second median, 42.8% faster than
    the 77.934-second baseline). Isolated install smoke passed in 12.69
    seconds. Fresh review of exact head `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`
    returned ACCEPT after independently reproducing output coverage,
    attempt-boundary enforcement, nested-workspace completion, and safe repair
    after a revoked decision. The founder packet records no current human
    acceptance.

## Independent Exact-Head Review History

These are independent agent review recommendations. They do not substitute for
the required Palari human review or human decision.

1. `d23f047ddf47de38a859d399040bcfb7aa9c4169`: REJECT. Findings covered
   evidence/subject contradictions, qualified acceptance ownership,
   parent-symlink time-of-check/time-of-use exposure, manufactured current
   bindings/derived claimed state, and unstructured missing-root failure.
2. `cc7a4f66c8781901cd2039cb3389d98811eb1e8b`: REJECT. Prior findings closed;
   cyclic proof/subject paths and operational exit classification remained.
3. `bc4b4418d4ff95114dc2cd12d9f9bf68ba523dd3`: REJECT. Prior findings closed;
   injected artifact `os.read` failure still escaped the structured verifier.
4. `50594e93fe4412791d99cace97937c1f5fe704c3`: ACCEPT. The fresh reviewer
   reproduced structured `SUBJECT_UNREADABLE` handling for injected `os.read`
   and `os.fstat` failures, reran focused protocol tests, checked all repaired
   invariants, confirmed the trusted-code manifest, and found no release-blocking
   issue. The declared same-OS-user identity limitation remains non-blocking.
5. `56577687ba8a77385e8a854fbf04f911b403f7b4`: REJECT. The final-metadata
   reviewer found that receipt `RECEIPT-REPO-0024` declared three outputs while
   evidence `EVIDENCE-REPO-0024` had an empty artifact manifest. The governance
   kernel correctly emitted `PCAW_EVIDENCE_OUTPUT_UNHASHED`, but `evidence
   verify` passed the empty lists vacuously. The evidence was marked failed and
   repair attempt `ATTEMPT-REPO-0024-R2` opened; completion remains pending a
   bounded-root artifact fix, exact-head verification, and fresh review.
6. `7f84a8565cd2d6c811f32a894041cf0c4a5aecb7`: REJECT. The first
   output-coverage repair made failed evidence exit nonzero and versioned the
   legacy boundary, but new v1 evidence could still pass with both receipt
   outputs and artifacts empty. An explicit attempt boundary violation also
   fell back to a usable nested workspace root. The next repair must require a
   non-empty v1 output manifest and mark invalid-root, unallowed, or forbidden
   artifacts unsafe without reading them.
7. `e77122048768fe4b96630b199b004deb0842d777`: REJECT. Empty v1 evidence and
   invalid bounded roots were closed, but canonical terminal validation still
   forced legacy compatibility for versioned evidence. A recomputed,
   internally consistent empty-v1 accepted fixture incorrectly validated.
8. `2379ba46d21f9ff7d6d9e9816a892d0d5c304af0`: ACCEPT. The fresh reviewer
   independently proved that the recomputed empty-v1 terminal fixture fails,
   genuinely unversioned legacy evidence remains readable with an explicit
   limitation, new review and acceptance paths reject empty v1 proof, and
   invalid-root, unallowed, and forbidden artifacts remain unread and unsafe.
   The focused review suite passed 125 tests in 8.582 seconds; the authoritative
   complete gate passed 622 tests and all 18 vectors in 41.26 seconds.
9. `cfd45b7e504ce882329d511ecbbfe968ff5cbb14`: ACCEPT. A real human
   completion attempt exposed that governance subject hashing still used the
   nested dogfood directory instead of the bounded attempt root. The accepted
   decision was revoked, a changes-requested review opened R3, and the repair
   unified governance normalization with evidence artifact-root resolution.
   The reviewer independently completed a nested high-risk lifecycle, proved
   invalid roots still fail before reads, and verified that revoked acceptance
   remains historical while current acceptance cannot cross attempts. The
   focused suite passed 154 tests; the complete gate passed 624 tests and all
   18 vectors in 42.92 seconds.

## Security Non-Claims

PCAW v1 detects supported statement, artifact, policy, and journal
inconsistency. It does not authenticate a declared actor against a hostile
process running as the same OS user. Signature envelopes, key custody,
revocation infrastructure, protected identity, a second verifier
implementation, autonomous merge/push/deploy, and external writes remain
deferred.

## Human Boundary

This work may prepare proof, reviews, and a founder packet. It may quote
human-only review or decision commands emitted by Palari. It must not record
founder review, founder acceptance, merge, push, deploy, call providers, use
secrets, or introduce signing/key custody.
