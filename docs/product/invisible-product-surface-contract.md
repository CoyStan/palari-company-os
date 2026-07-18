# Invisible Product Surface v1 Completion Contract

Work item: `WORK-31D9DD73A7A045BC8236FA561291D064`

Baseline: `4881dd853ebcec73ce7a69ff7acefd4b637e2a21`

This contract makes the common operating journey obvious without deleting the
expert surface or laundering unfinished work into completion. Exact candidate
commit evidence is filled only after the implementation is committed.

## Completion Outcomes

- [ ] **Focused default surface** — `palari --help` leads with adoption, bounded
  work, start/advance, approval inbox, and offline verification while all 154
  existing command paths remain parseable. Objective evidence: parser snapshot
  remains 154 and focused-help assertions pass. Verification:
  `python3 -m unittest tests.test_public_surface`. Status: implemented,
  awaiting committed proof. Exact committed proof: pending candidate commit.

- [ ] **Explicit non-success retirement** — obsolete work can be recorded as
  `superseded` or `abandoned` with a mandatory reason and optional successor,
  without creating completion proof. Objective evidence: model/schema parity
  and positive CLI round trip. Verification:
  `python3 -m unittest tests.test_validation tests.test_workspace_read_models`.
  Status: implemented, awaiting committed proof. Exact committed proof: pending
  candidate commit.

- [ ] **Fail-closed authority graph** — missing/self/cyclic successors, active
  attempts, open decisions, unresolved external actions, and dependencies on
  retired work are rejected. Objective evidence: focused negative tests and
  validation diagnostics. Verification:
  `python3 -m unittest tests.test_validation`. Status: implemented, awaiting
  committed proof. Exact committed proof: pending candidate commit.

- [ ] **Quiet defaults, complete audit** — retired work is absent from default
  queue, agent-next, and Approval Inbox views; explicit start cannot claim it;
  include-closed and detail retain status, reason, successor, and history.
  Objective evidence: end-to-end temporary-workspace test. Verification:
  `python3 -m unittest tests.test_workspace_read_models`. Status: implemented,
  awaiting committed proof. Exact committed proof: pending candidate commit.

- [ ] **Compatibility and documentation** — both shipped schemas are identical,
  detailed JSON remains additive, successful terminal proof semantics remain
  unchanged, and operator docs describe the focused and expert surfaces.
  Objective evidence: schema comparison, public command snapshot, docs check,
  complete verification, and install smoke. Verification: `cmp
  schemas/workspace.schema.json
  src/palari_company_os/data/schemas/workspace.schema.json && ./bin/palari docs
  check --json && ./scripts/verify.sh && ./scripts/install_smoke.sh`. Status:
  implemented, awaiting committed proof. Exact committed proof: pending
  candidate commit.

## Non-Claims

- Retirement is not completion, acceptance, rejection, or proof revocation.
- An optional successor is an audit pointer, not an implicit dependency rewrite.
- Focused help does not remove or deprecate expert command paths.
- No external write, provider call, merge, push, or human decision is authorized.
