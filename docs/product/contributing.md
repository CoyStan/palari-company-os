# Contributing

Use ordinary software engineering.

Do:

- keep changes scoped
- update docs when commands or data contracts change
- add regression tests for lifecycle, authority, scope, evidence, and review
  behavior
- run `./scripts/verify.sh`
- for lint parity with CI, install `.[dev]` in a virtual environment and run
  `ruff check .` and `mypy`

## CLI Structure

Keep `src/palari_company_os/cli.py` as the thin entrypoint. New command-line
work should usually fit into one of these modules:

- `cli_parser.py`: argparse setup and command flags.
- `cli_dispatch.py`: command execution and CLI-to-domain record assembly.
- `cli_output.py`: dispatch and shared human-readable/JSON rendering.
- `cli_output_agent.py`: agent packet, check, lifecycle, handoff, loop, and
  doctor output.
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
- enable real broker side effects
- turn policy simulation into real authority
- introduce heavy process ceremony as the default workflow
