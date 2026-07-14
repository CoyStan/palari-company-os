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

- [ ] One deterministic governance kernel
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
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] Deterministic PCAW v1 statement export
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
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Strict offline PCAW v1 verification
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
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Strict canonical JSON and protocol schema
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
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Exact proof, review, and human-authority verification
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
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Safe subject and source boundaries
  - Required outcome: artifact verification uses canonical relative paths and
    rejects traversal, absolute paths, sibling-prefix confusion, symlink escape,
    missing/unreadable subjects, changed bytes, duplicate subjects, and
    unsupported digests.
  - Objective completion evidence: temporary-copy negative tests prove every
    named boundary fails closed without reading outside the selected subject
    root or mutating operator files.
  - Verification command or artifact: `python3 -m unittest
    tests.test_pcaw_protocol tests.test_filesystem_security`.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Normative specification and portable conformance corpus
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
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Staged replayable governance journal
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
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Crash-safe, idempotent journal recovery
  - Required outcome: interruption at every prepared/write/replace/commit
    boundary is detectable and either safely retryable or reported with an
    actionable fail-closed diagnosis; repeated recovery never duplicates a
    committed mutation.
  - Objective completion evidence: deterministic crash injection covers every
    transaction boundary and proves workspace/journal agreement or an explicit
    prepared-event recovery state.
  - Verification command or artifact: `python3 -m unittest
    tests.test_governance_journal_crash`.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Operator clarity and two-minute offline demonstration
  - Required outcome: proof and history commands explain valid, incomplete,
    blocked, stale, altered, statement-only, discontinuous, and unsupported
    states concisely; a network-free demo verifies a valid accepted artifact,
    alters one governed byte, and receives a precise rejection.
  - Objective completion evidence: JSON/text CLI tests assert stable messages
    and safe next actions; the documented demo runs successfully from an
    isolated installation.
  - Verification command or artifact: `python3 -m unittest
    tests.test_pcaw_protocol tests.test_history` and `./scripts/pcaw_demo.sh`.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Compatibility, minimality, and trusted-code accounting
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
  - Current status: pending.
  - Exact committed evidence when completed: pending.

- [ ] Verification timing, independent exact-head review, and founder packet
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
  - Current status: pending.
  - Exact committed evidence when completed: pending.

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
