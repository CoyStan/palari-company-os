# Invisible Product Surface v1 Completion Contract

Work item: `WORK-31D9DD73A7A045BC8236FA561291D064`

Baseline: `4881dd853ebcec73ce7a69ff7acefd4b637e2a21`

Initial implementation commit:
`974121cac0fca752151de684caf4488b9e292829`.

Committed verification record:
`07cdfbf7f1567d11851a47e7b0c2cff31fd485d9`.

This contract makes the common operating journey obvious without deleting the
expert surface or laundering unfinished work into completion.

## Completion Outcomes

- [x] **Focused default surface** — `palari --help` leads with adoption, bounded
  work, start/advance, approval inbox, and offline verification while all 154
  existing command paths remain parseable. Objective evidence: parser snapshot
  remains 154 and focused-help assertions pass. Verification:
  `python3 -m unittest tests.test_public_surface`. Status: proven. Exact
  committed proof: parser and public-surface tests at
  `974121cac0fca752151de684caf4488b9e292829`, with the no-additive-command
  consolidation at `06551e64c4d056a6c55fbbcb1ba960e63e599710`.

- [x] **Explicit non-success retirement** — obsolete work can be recorded as
  `superseded` or `abandoned` with a mandatory reason and optional successor,
  without creating completion proof. Objective evidence: model/schema parity
  and positive CLI round trip. Verification:
  `python3 -m unittest tests.test_validation tests.test_workspace_read_models`.
  Status: proven. Exact committed proof: model, schema, CLI, and end-to-end tests
  at `974121cac0fca752151de684caf4488b9e292829`, with non-success and
  temporal-storage repairs at `54bb18e117208932da05617315b0ec2ded53a3c8`
  and `44597e83a27797ae81067dc8f3f94e31bbdef3c6`, plus atomic retirement
  transition and linked-proposal sealing at
  `ef22a65d11a60b362a7cd959d54f7444b24ba267`.

- [x] **Fail-closed authority graph** — missing/self/cyclic successors, active
  attempts, open decisions, unresolved external actions, and dependencies on
  retired work are rejected. Objective evidence: focused negative tests and
  validation diagnostics. Verification:
  `python3 -m unittest tests.test_validation`. Status: proven. Exact committed
  proof: retirement validation and negative tests at
  `54bb18e117208932da05617315b0ec2ded53a3c8`, with later-lifecycle
  immutability at `44597e83a27797ae81067dc8f3f94e31bbdef3c6` and storage-transaction
  immutability at `ef22a65d11a60b362a7cd959d54f7444b24ba267`.

- [x] **Quiet defaults, complete audit** — retired work is absent from default
  queue, agent-next, and Approval Inbox views; explicit start cannot claim it;
  include-closed and detail retain status, reason, successor, and history.
  Objective evidence: end-to-end temporary-workspace test. Verification:
  `python3 -m unittest tests.test_workspace_read_models`. Status: proven. Exact
  committed proof: queue/inbox/detail and direct-start tests at
  `974121cac0fca752151de684caf4488b9e292829`, unresolved-external-state
  repair at `0e72d370c9fede44361340e60e1f2f97f032612c`, and terminal advance/proof
  containment at `44597e83a27797ae81067dc8f3f94e31bbdef3c6` and
  `ef22a65d11a60b362a7cd959d54f7444b24ba267`.

- [x] **Compatibility and documentation** — both shipped schemas are identical,
  detailed JSON remains additive, successful terminal proof semantics remain
  unchanged, and operator docs describe the focused and expert surfaces.
  Objective evidence: schema comparison, public command snapshot, docs check,
  complete verification, and install smoke. Verification: `cmp
  schemas/workspace.schema.json
  src/palari_company_os/data/schemas/workspace.schema.json && ./bin/palari docs
  check --json && ./scripts/verify.sh && ./scripts/install_smoke.sh`. Status:
  proven. Exact committed proof: both schemas, snapshot test, and documentation
  at `07cdfbf7f1567d11851a47e7b0c2cff31fd485d9`, with integrated compatibility
  retained through `ef22a65d11a60b362a7cd959d54f7444b24ba267`.

## Verification Evidence

All slice checks below ran against exact verification record
`07cdfbf7f1567d11851a47e7b0c2cff31fd485d9`; later integrated repairs have
their own focused evidence above and are covered by the integration gate:

- affected contract suite: 268 tests passed;
- complete gate: 889 tests across 46 modules, style pass, trusted-code manifest
  current, and 18/18 PCAW conformance vectors passed;
- dogfood `validate --json`: valid;
- `docs check --json`: 12 checks passed, zero warnings or failures;
- isolated wheel installation smoke: passed;
- public command snapshot: 154 command paths, unchanged.

## Non-Claims

- Retirement is not completion, acceptance, rejection, or proof revocation.
- An optional successor is an audit pointer, not an implicit dependency rewrite.
- Focused help does not remove or deprecate expert command paths.
- No external write, provider call, merge, push, or human decision is authorized.
