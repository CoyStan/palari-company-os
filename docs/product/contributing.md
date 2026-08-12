# Contributing

Use ordinary software engineering.

Do:

- keep changes scoped
- update docs when commands or data contracts change
- add regression tests for task status, permissions, allowed files, checks, and
  review behavior
- install the pinned development tools with `python3 -m pip install -e ".[dev]"`
- run `./scripts/verify.sh`
- use `./scripts/verify.sh focused tests.test_MODULE` while iterating; the
  complete check already runs Ruff and mypy once

## CLI Structure

Keep `src/palari_company_os/cli.py` as the thin entrypoint. New command-line
work should usually fit into one of these modules:

- `cli_parser.py`: argparse setup and command flags.
- `cli_dispatch.py`: command execution and CLI-to-domain record assembly.
- `cli_output.py`: dispatch and shared human-readable/JSON rendering.
- `cli_output_agent.py`: agent home, packet, status, and lifecycle output.
- `cli_output_integrations.py`: integration registry, plan, outbox, and
  preflight output.
- `cli_output_utils.py`: small shared output helpers.
- `authoring.py`: workspace mutations and lifecycle safety gates.

Avoid adding business rules directly to `cli.py`.

Do not:

- import unrelated legacy ticket history
- import old evidence bundles, reports, claims, worktrees, caches, or runtime
  state
- add secrets
- add a live provider path without explicit adapter rules and approval
- turn policy simulation into real permission
- introduce heavy process ceremony as the default workflow
