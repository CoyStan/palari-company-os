# Repo Map

This map helps agents find the right files before scanning the whole repository.
Keep it concise and update it when file ownership changes.

The checked [Repo Tree](repo-tree.json) places every stored record and every
tracked file in one branch. Each split has three to five plain-named parts,
with no overlap and no gaps. Run `python3 -S scripts/check_repo_tree.py` after
changing a record type or adding, moving, or removing a file.

## Code Parts

The `app/code` branch has five parts: `base`, `work`, `checks`, `links`, and
`views`. Each part lists three facts in the same checked tree:

- `files`: the source files it owns;
- `door`: the files other parts should use; and
- `check`: the focused tests for that part.

Run one part without scanning or testing unrelated code:

```bash
python3 -S scripts/check_repo_tree.py --part work
```

The files remain in one Python package for now. The map creates a clear work
boundary without nested repos, a second work list, or empty folders.

Descriptions use the plain product words from
[Plain Language](../product/plain-language.md). Python modules and stored field
names stay exact because this is also a source-code map.

## Core Package

- `src/palari_company_os/models.py`: typed workspace objects.
- `src/palari_company_os/validation.py`: fail-closed workspace validation.
- `src/palari_company_os/workspace.py`: workspace loading and record lookup.
- `src/palari_company_os/store.py`: validated writes to `workspace.json`.
- `src/palari_company_os/governance_journal.py`: replayable, tamper-evident
  v2 history, checkpoints, verification, and crash recovery.
- `src/palari_company_os/approval_packs.py`: canonical Approval Inbox manifests,
  item/resolution evaluation, approval modes, risk policy, and exact human pack
  decisions.
- `src/palari_company_os/simple_approval.py`: one-task human approval front
  door, fail-closed diagnostics, and exact safe-retry validation over the pack
  transaction.
- `src/palari_company_os/approval_presentations.py`: strict, deterministic
  approval view, validation, and exact presentation digest.
- `src/palari_company_os/workspace_read_models.py`: product-facing exact
  Approval Inbox adapter over workspace truth.
- `src/palari_company_os/governance_case.py` and `governance_kernel.py`: pure,
  provider-neutral rules normalization and evaluator.
- `src/palari_company_os/pcaw_protocol.py`: offline PCAW statement verifier.
- `src/palari_company_os/pcaw_workspace.py` and `pcaw_export.py`: workspace-state
  normalization and deterministic PCAW proof export (outside the verifier TCB).
- `src/palari_company_os/transition_checks.py`: hard checks for trust-changing
  state transitions.
- `src/palari_company_os/authority_plan.py`: pure builder/reviewer/final-human
  role feasibility and smallest-correction diagnostics.
- `src/palari_company_os/authoring.py`: atomic proof reconciliation, exact
  review recording, and completion helpers.
- `src/palari_company_os/onramp.py`: journal-activated `init`, bounded task
  creation, and authority-free work ideas for existing repos.
- `src/palari_company_os/proposals.py`: human approval of an idea into active
  work, plus older proposal decisions and scope questions.
- `src/palari_company_os/work_identity.py`: opaque UUIDv4-backed task and idea
  identity generation with no lifecycle ordering semantics.

## CLI

- `src/palari_company_os/cli_parser.py`: argparse command shape.
- `src/palari_company_os/cli_dispatch.py`: command routing and result kinds.
- `src/palari_company_os/cli_output.py`: text and JSON output printers.
- `src/palari_company_os/cli.py`: top-level CLI error handling.
- `bin/palari`: local wrapper used in docs and tests.

When adding a command, update parser, dispatch, output, tests, and
`docs/product/command-reference.md`.

## Agent Runtime

- `src/palari_company_os/agent_home.py`: read-only Goals, Team, Work, Checks,
  and Limits view; it grants no task permission.
- `src/palari_company_os/agent_packets.py`: `agent brief` task-brief contract.
- `src/palari_company_os/agent_session_contract.py`: pure deterministic
  provider-neutral session-contract projection, strict validation, digest, and
  honest enforcement profile.
- `src/palari_company_os/agent_runtime.py`: task-brief persistence and local
  task locks.
- `src/palari_company_os/agent_directive.py`: pure state-to-owner/action
  compiler shared by agent read surfaces.
- `src/palari_company_os/agent_operation.py`: request-local brief, check, and
  directive reuse.
- `src/palari_company_os/agent_status.py`: canonical read-only task limits,
  checks, ownership, blockers, and next-action projection from one request-local
  operation.
- `src/palari_company_os/agent_parking.py`: durable blocked-run parking and
  exact idempotent task-lock release without permission to approve.
- `src/palari_company_os/agent_isolation.py`: isolated Git worktree start,
  exact-target integration readiness, and non-authority diagnostics.
- `src/palari_company_os/agent_file_changes.py`: canonical Git change
  observation, start-time dirty baselines, and task-brief write-boundary checks.
- `src/palari_company_os/agent_checks.py`: task-brief compliance checks.
- `src/palari_company_os/agent_next.py`: candidate discovery.
- `src/palari_company_os/agent_finish.py`: completion guidance and resolver
  classification.
- `src/palari_company_os/agent_handoff.py`: read-only human handoff briefs and
  simple human approval routing plus advanced pack context when eligible.
- `src/palari_company_os/agent_doctor.py`: plain-language safety diagnosis.
- `src/palari_company_os/agent_loop.py`: compact loop summary.
- `src/palari_company_os/agent_advance.py`: pure advance planning and the
  deterministic verification reconciler that stops at approval boundaries and
  finishes mechanically after current approval exists.
- `src/palari_company_os/governance_convergence.py`: bounded fixed-point driver,
  verification-relative status-file check, and automatic completion using only
  approval that already exists.
- `src/palari_company_os/verification_attestations.py`: exact-state,
  content-addressed verification profiles and advisory local run records.
- `src/palari_company_os/mcp_server.py`: read-only MCP stdio adapter for
  agent-facing Palari tools.
- `src/palari_company_os/mission_control.py`: optional local read-only
  supervision plus guarded integration-plan decisions. Exact human approval
  remains bound to the Approval Inbox action.
- `src/palari_company_os/claude_hooks.py`: optional Claude Code host enforcement
  of the task-brief write boundary (PreToolUse deny, Stop backstop, SessionStart
  context); the core operating loop is provider-neutral.
- `src/palari_company_os/git_hooks.py`: IDE-agnostic git pre-commit enforcement
  of the task-brief write boundary (blocks commits staging out-of-boundary files).
- `src/palari_company_os/cursor_rules.py`: Cursor integration that writes an
  always-applied `.cursor/rules` boundary rule and wires the git pre-commit hook.

## Review And Safety

- `src/palari_company_os/integrations.py`: dry-run integration plans, decisions,
  and outbox records.
- `src/palari_company_os/review_guides.py`: read-only review guides.
- `src/palari_company_os/governance_binding.py`: exact attempt, receipt,
  evidence, work-contract, and review proof binding.
- `src/palari_company_os/record_order.py`: timezone-normalized deterministic
  ordering for evidence, review, receipt, attempt, outcome, and integration
  records.
- `src/palari_company_os/decision_guides.py`: read-only decision guides.
- `src/palari_company_os/scope.py`: declared scope checks.
- `spec/pcaw/v1/`: normative PCAW v1 schemas, vectors, and black-box runner.

## Docs And Agent Orientation

- `AGENTS.md`: compact root agent entrypoint.
- `CLAUDE.md`: thin Claude adapter that points to shared repo truth.
- `docs/product/current-product.md`: normative supported-product boundary,
  lifecycle, storage, adapters, and compatibility policy.
- `docs/product/self-hosting-maintainer-mode.md`: bounded source-repair
  exception, current isolation limitation, and the exact ignored-state
  follow-up design.
- `docs/agent/`: agent-ready repo documentation.
- `docs/product/`: current product and operator documentation. Completed
  implementation contracts remain available through Git history rather than as
  supported runtime documentation.
- `docs/product/agent-company-landscape.md`: experimental July 2026 research
  survey (~60 systems scored on five governed-company properties); not product
  status. Companion short snapshot lives in `palari-blueprint.md` §6.
- `verify/`: experimental unsigned PCAW integrity drop-a-receipt page (not
  WRP-10). See `verify/README.md`.
- `docs/product/distribution.md`: experimental external-adoption measurements.

## Examples And Workspaces

- `examples/acme-company-os/`: small example workspace.

Keep examples portable. Do not commit machine-local absolute paths, secrets, or
runtime state.

## Tests

- `tests/test_agent_packets.py`: agent packet/check/loop behavior.
- `tests/test_agent_status.py`: canonical status projection and request-local
  observation reuse.
- `tests/test_agent_advance.py`: deterministic planning, verification cache,
  atomic proof reconciliation, crash recovery, and idempotence.
- `tests/test_operator_journeys.py`: short entry/convergence/parking journeys,
  interruption recovery, and interaction-count evidence.
- `tests/test_agent_file_changes.py`: explicit path-intent and deletion
  tombstone enforcement plus the committed presence-contract reader boundary.
- `tests/test_validation.py`: schema and boundary validation.
- `tests/test_workspace_read_models.py`: queue/detail/state behavior.
- `tests/test_integrations.py`: dry-run integration trust loop.
- `tests/test_docs.py`: docs and agent-ready documentation behavior.
- `tests/test_approval_packs.py`: batching, staleness, authority, policy, and
  crash recovery.

Prefer focused regression tests for a discovered failure mode, then run the full
verification stack before claiming done.
