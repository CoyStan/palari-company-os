# Repo Map

This map helps agents find the right files before scanning the whole repository.
Keep it concise and update it when file ownership changes.

## Core Package

- `src/palari_company_os/models.py`: typed workspace objects.
- `src/palari_company_os/validation.py`: fail-closed workspace validation.
- `src/palari_company_os/workspace.py`: workspace loading and split collection files.
- `src/palari_company_os/store.py`: validated writes to `workspace.json`.
- `src/palari_company_os/governance_journal.py`: replayable prepare/commit
  journal, checkpoints, verification, and crash recovery.
- `src/palari_company_os/approval_packs.py`: canonical Approval Inbox manifests,
  item/resolution evaluation, approval modes, risk policy, and exact human pack
  decisions.
- `src/palari_company_os/approval_presentations.py`: strict, deterministic
  human-decision projection, canonical bytes, and exact presentation digest.
- `src/palari_company_os/checkpoints.py`: content-addressed checkpoint listing
  and append-only human restoration.
- `src/palari_company_os/workspace_read_models.py`: product-facing approval
  inbox/detail adapters over workspace truth.
- `src/palari_company_os/governance_case.py` and `governance_kernel.py`: pure,
  provider-neutral governance normalization contract and evaluator.
- `src/palari_company_os/pcaw_protocol.py`: offline PCAW statement verifier.
- `src/palari_company_os/pcaw_workspace.py` and `pcaw_export.py`: workspace
  normalization and deterministic proof export (outside the verifier TCB).
- `src/palari_company_os/transition_checks.py`: hard checks for trust-changing
  state transitions.
- `src/palari_company_os/authoring.py`: create/update lifecycle records.
- `src/palari_company_os/onramp.py`: journal-activated `init` starter workspace
  and atomic `work add` quick-create for existing repos.
- `src/palari_company_os/work_identity.py`: opaque UUIDv4-backed work identity
  generation with no lifecycle ordering semantics.

## CLI

- `src/palari_company_os/cli_parser.py`: argparse command shape.
- `src/palari_company_os/cli_dispatch.py`: command routing and result kinds.
- `src/palari_company_os/cli_output.py`: text and JSON output printers.
- `src/palari_company_os/cli.py`: top-level CLI error handling.
- `bin/palari`: local wrapper used in docs and tests.

When adding a command, update parser, dispatch, output, tests, and
`docs/product/command-reference.md`.

## Agent Runtime

- `src/palari_company_os/agent_packets.py`: `agent brief` packet contract.
- `src/palari_company_os/agent_session_contract.py`: pure deterministic
  provider-neutral session-contract projection, strict validation, digest, and
  honest enforcement profile.
- `src/palari_company_os/agent_runtime.py`: packet persistence and local claims.
- `src/palari_company_os/agent_directive.py`: pure state-to-owner/action
  compiler shared by agent read surfaces.
- `src/palari_company_os/agent_operation.py`: request-local packet, check,
  directive, and journal-observation reuse.
- `src/palari_company_os/agent_parking.py`: durable blocked-attempt parking and
  exact idempotent claim-release recovery without proof authority.
- `src/palari_company_os/agent_isolation.py`: isolated Git worktree start,
  exact-target integration readiness, and non-authority diagnostics.
- `src/palari_company_os/agent_file_changes.py`: canonical Git change
  observation, start-time dirty baselines, and packet write-boundary checks.
- `src/palari_company_os/agent_checks.py`: packet compliance checks.
- `src/palari_company_os/agent_next.py`: candidate discovery.
- `src/palari_company_os/agent_finish.py`: completion guidance and resolver
  classification.
- `src/palari_company_os/agent_handoff.py`: read-only human handoff packets and
  exact Approval Pack routing when eligible.
- `src/palari_company_os/agent_doctor.py`: plain-language safety diagnosis.
- `src/palari_company_os/agent_loop.py`: compact loop summary.
- `src/palari_company_os/agent_advance.py`: pure advance planning and the
  deterministic proof reconciler that stops at authority boundaries and
  terminalizes mechanically after current authority exists.
- `src/palari_company_os/governance_convergence.py`: bounded fixed-point driver,
  proof-relative governance-projection check, and automatic terminalization
  using only authority that already exists.
- `src/palari_company_os/verification_attestations.py`: exact-state,
  content-addressed verification profiles and advisory local run records.
- `src/palari_company_os/mcp_server.py`: read-only MCP stdio adapter for
  agent-facing Palari tools.
- `src/palari_company_os/claude_hooks.py`: optional Claude Code host enforcement
  of the packet write boundary (PreToolUse deny, Stop backstop, SessionStart
  context); the core operating loop is provider-neutral.

## Trust Objects

- `src/palari_company_os/integrations.py`: dry-run integration plans, decisions,
  and outbox records.
- `src/palari_company_os/gate_profiles.py`: read-only review gate profiles.
- `src/palari_company_os/playbooks.py`: external playbook recommendations.
- `src/palari_company_os/review_guides.py`: read-only review guides.
- `src/palari_company_os/governance_binding.py`: exact attempt, receipt,
  evidence, work-contract, and review proof binding.
- `src/palari_company_os/record_order.py`: timezone-normalized deterministic
  ordering for evidence, review, receipt, attempt, outcome, and integration
  records.
- `src/palari_company_os/decision_guides.py`: read-only decision guides.
- `src/palari_company_os/scope.py`: declared scope checks.
- `src/palari_company_os/history.py`: append-only workspace history.
- `spec/pcaw/v1/`: normative PCAW v1 schemas, vectors, and black-box runner.

## Docs And Agent Orientation

- `AGENTS.md`: compact root agent entrypoint.
- `CLAUDE.md`: thin Claude adapter that points to shared repo truth.
- `docs/agent/`: agent-ready repo documentation.
- `docs/product/`: product and operator documentation.
- `docs/showcase/`: public-facing examples and vignettes.

## Examples And Workspaces

- `examples/acme-company-os/`: small example workspace.
- `workspaces/palari-company-os/`: dogfood workspace for this repo.
- `src/palari_company_os/data/examples/`: packaged example data.

Keep examples portable. Do not commit machine-local absolute paths, secrets, or
runtime state.

## Tests

- `tests/test_agent_packets.py`: agent packet/check/loop behavior.
- `tests/test_agent_advance.py`: deterministic planning, verification cache,
  atomic proof reconciliation, crash recovery, and idempotence.
- `tests/test_operator_journeys.py`: short entry/convergence/parking journeys,
  interruption recovery, and interaction-count evidence.
- `tests/test_agent_file_changes.py`: explicit path-intent and deletion
  tombstone enforcement plus legacy compatibility.
- `tests/test_validation.py`: schema and boundary validation.
- `tests/test_workspace_read_models.py`: queue/detail/state behavior.
- `tests/test_integrations.py`: dry-run integration trust loop.
- `tests/test_gate_profiles.py`: review gate recommendations.
- `tests/test_docs.py`: docs and agent-ready documentation behavior.
- `tests/test_approval_packs.py`: batching, staleness, authority, policy, and
  crash recovery.
- `tests/test_reversible_checkpoints.py`: exact projection restoration,
  append-only history, non-guarantees, and crash recovery.

Prefer focused regression tests for a discovered failure mode, then run the full
verification stack before claiming done.
