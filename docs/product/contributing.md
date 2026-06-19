# Contributing

Use ordinary software engineering.

Do:

- keep changes scoped
- update docs when commands or data contracts change
- add regression tests for lifecycle, authority, scope, evidence, and review
  behavior
- run `./scripts/verify.sh`

## CLI Structure

Keep `src/palari_company_os/cli.py` as the thin entrypoint. New command-line
work should usually fit into one of these modules:

- `cli_parser.py`: argparse setup and command flags.
- `cli_dispatch.py`: command execution and CLI-to-domain record assembly.
- `cli_output.py`: human-readable and JSON rendering.
- `authoring.py`: workspace mutations and lifecycle safety gates.

Avoid adding business rules directly to `cli.py`.

Do not:

- import old Palari Orchestrator POS ticket history
- import old evidence bundles, reports, claims, worktrees, caches, or runtime
  state
- add secrets
- enable real broker side effects
- turn policy simulation into real authority
- reintroduce the old ticket ceremony as the default workflow
