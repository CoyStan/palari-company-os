# Presentation-Bound Human Decisions & One-Action Convergence v1

Work item: `WORK-66351C3AD0334E78AFE962F06A0BF9CA`
Branch: `codex/presentation-bound-human-decisions`
Baseline: `8128e6f2326f3de4507318eab58077385a1c2934`
Authority owner: `HUMAN-FOUNDER`
Builder: `PALARI-STEWARD`
Risk / intensity: R4 / high

This contract promotes stage 2 of the approved roadmap into bounded local
implementation. It does not change PCAW v1, add signing, authenticate an OS
user, perform an external effect, or let an agent invoke human authority.

## Completion Contract

- [x] **Canonical presentation artifact.** Outcome: every new Approval Pack
  exposes a strict, layout-independent `palari.approval-presentation.v1`
  artifact and SHA-256 digest covering the exact pack, per-item proof,
  boundaries, effects, available action, execution order, and current relevant
  decision context. Objective evidence: deterministic-byte and changed-byte
  tests. Verification: `python3 -m unittest -q
  tests.test_approval_presentations`. Status: complete; 6 focused presentation
  tests passed, including blocked and non-batchable negative cases. Exact
  committed proof: `82636f4` introduced the artifact; `c9da7e4` binds its
  available and primary actions to the current evaluated member states.

- [x] **Decision-surface binding.** Outcome: `human-decision pack` requires the
  exact presentation digest emitted by the Approval Inbox; missing, stale,
  malformed, or transplanted bindings fail closed. New pack-v2 decisions
  persist the schema, surface, digest, and one canonical artifact while legacy
  pack-v1 records remain readable. Objective evidence: CLI, validation,
  downgrade, transplant, and stale-context negative tests. Verification:
  `python3 -m unittest -q tests.test_approval_presentations
  tests.test_approval_packs tests.test_validation`. Status: complete; the
  presentation/pack suites passed 27 tests and the validation/CLI/agent packet
  group passed 183 tests. Exact committed proof: `82636f4`, corrected by
  `c9da7e4` after independent review.

- [x] **One-action convergence.** Outcome: one attributable pack action records
  item-granular decisions, derives acceptance only after current quorum, and
  terminalizes every authorized reversible-local member in the same journal
  transaction. No review, additional human authority, external effect, or
  follow-up completion command is manufactured. Objective evidence:
  single/multi-item, quorum, dependency, idempotence, and crash-boundary tests
  plus structured `palari.one-action-convergence.v1` output. Verification:
  `python3 -m unittest -q tests.test_approval_presentations
  tests.test_approval_packs`. Status: complete; the presentation/pack suites
  passed 27 tests, including quorum refresh, terminalization, idempotence, and
  crash retry coverage. Exact committed proof: `82636f4` and `c9da7e4`.

- [x] **Operator clarity and honest limits.** Outcome: queue text/JSON and
  handoff surfaces expose the exact presentation digest and one safe human
  command, while stating that the digest proves canonical artifact bytes—not
  browser rendering, reading, understanding, judgment, or cryptographic actor
  identity. Objective evidence: CLI/handoff tests and documentation checks.
  Verification: `python3 -m unittest -q tests.test_cli_smoke
  tests.test_agent_packets && ./bin/palari docs check --json`. Status:
  complete; documentation freshness passed 12/12 and the validation/CLI/agent
  packet group passed 183 tests. Exact committed proof: `82636f4`.

- [x] **Compatibility and complete gate.** Outcome: historical workspaces and
  Approval Pack v1 decisions still load; PCAW v1 remains unchanged; schema
  copies agree; complete and installed-package gates pass without a new runtime
  dependency. Objective evidence: affected tests, schema/fixture validation,
  PCAW conformance, complete verification, and isolated install smoke.
  Verification: `./scripts/verify.sh && ./scripts/install_smoke.sh && python3
  spec/pcaw/v1/conformance.py -- ./bin/palari proof verify`. Status: complete;
  the repaired head passed 773 tests across 44 modules, style, trusted-code
  check, PCAW conformance 18/18, and isolated install smoke; schema copies are
  byte-identical; Ruff and mypy also passed. Exact committed proof: `c9da7e4`.

- [ ] **Independent exact-head acceptance.** Outcome: a reviewer distinct from
  the builder inspects the exact committed candidate, all substantive findings
  are repaired, attributable checks are rerun, and a qualified human decision
  remains a separate authority act. Objective evidence: immutable review,
  evidence, receipt, and decision records tied to the candidate head.
  Verification: `palari agent finish` / `handoff` plus exact review and decision
  artifacts. Status: review `REVIEW-PRESENTATION-ARCHITECT-835A031-REJECT`
  rejected `835a031` because a blocked presentation misstated available
  actions and the contract misstated the focused test count; both findings are
  repaired in `c9da7e4`. Fresh exact-head review is pending. Exact committed
  proof: the rejection record is committed in `c9da7e4`; acceptance pending.

## Explicit Non-Claims

- A presentation digest proves the canonical artifact bytes only.
- The bound local CLI surface supports a claim that those bytes were made
  available to the decision action; compromised software could render
  different bytes.
- No record proves that a person read, understood, or made a good decision.
- Same-user actor attribution remains declared, not cryptographically
  authenticated.
- PCAW v1 carries no presentation property; portable proof remains future
  protocol work.
