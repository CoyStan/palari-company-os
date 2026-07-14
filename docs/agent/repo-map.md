# Repo Map

This map helps agents find the right files before scanning the whole repository.
Keep it concise and update it when file ownership changes.

## Core Package

- `src/palari_company_os/models.py`: typed workspace objects.
- `src/palari_company_os/validation.py`: fail-closed workspace validation.
- `src/palari_company_os/workspace.py`: workspace loading and split collection files.
- `src/palari_company_os/store.py`: validated writes to `workspace.json`.
- `src/palari_company_os/transition_checks.py`: hard checks for trust-changing
  state transitions.
- `src/palari_company_os/authoring.py`: create/update lifecycle records.
- `src/palari_company_os/onramp.py`: `init` starter workspace and `work add`
  quick-create for existing repos.

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
- `src/palari_company_os/agent_runtime.py`: packet persistence and local claims.
- `src/palari_company_os/agent_file_changes.py`: canonical Git change
  observation, start-time dirty baselines, and packet write-boundary checks.
- `src/palari_company_os/agent_checks.py`: packet compliance checks.
- `src/palari_company_os/agent_next.py`: candidate discovery.
- `src/palari_company_os/agent_finish.py`: completion guidance.
- `src/palari_company_os/agent_handoff.py`: read-only human handoff packets.
- `src/palari_company_os/agent_doctor.py`: plain-language safety diagnosis.
- `src/palari_company_os/agent_loop.py`: compact loop summary.
- `src/palari_company_os/mcp_server.py`: read-only MCP stdio adapter for
  agent-facing Palari tools.
- `src/palari_company_os/claude_hooks.py`: Claude Code hook enforcement of the
  packet write boundary (PreToolUse deny, Stop backstop, SessionStart context).

## Trust Objects

- `src/palari_company_os/integrations.py`: dry-run integration plans, decisions,
  and outbox records.
- `src/palari_company_os/gate_profiles.py`: read-only review gate profiles.
- `src/palari_company_os/playbooks.py`: external playbook recommendations.
- `src/palari_company_os/review_guides.py`: read-only review guides.
- `src/palari_company_os/governance_binding.py`: exact attempt, receipt,
  evidence, work-contract, and review proof binding.
- `src/palari_company_os/decision_guides.py`: read-only decision guides.
- `src/palari_company_os/scope.py`: declared scope checks.
- `src/palari_company_os/history.py`: append-only workspace history.

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
- `tests/test_validation.py`: schema and boundary validation.
- `tests/test_workspace_read_models.py`: queue/detail/state behavior.
- `tests/test_integrations.py`: dry-run integration trust loop.
- `tests/test_gate_profiles.py`: review gate recommendations.
- `tests/test_docs.py`: docs and agent-ready documentation behavior.

Prefer focused regression tests for a discovered failure mode, then run the full
verification stack before claiming done.
