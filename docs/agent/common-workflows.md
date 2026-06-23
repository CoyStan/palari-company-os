# Common Workflows

Use these as short recipes, not ceremony. The current work item and agent packet
remain the assignment boundary.

## Add Or Change A CLI Command

1. Update `src/palari_company_os/cli_parser.py`.
2. Route behavior in `src/palari_company_os/cli_dispatch.py`.
3. Add or update text/JSON output in `src/palari_company_os/cli_output.py`.
4. Add focused tests for JSON shape and useful text output.
5. Update `docs/product/command-reference.md`.
6. Run focused tests and the normal verification stack.

## Change Workspace Schema Or Validation

1. Update `src/palari_company_os/models.py` and validation code.
2. Update `schemas/workspace.schema.json` when the JSON contract changes.
3. Update examples or fixtures only when needed.
4. Update `docs/product/schema-and-validation.md` and
   `docs/product/core-objects.md`.
5. Add tests for valid and fail-closed cases.

## Change Agent Behavior

1. Keep packets compact and deterministic.
2. Add explicit blockers and next safe commands.
3. Avoid dumping full workspace records or docs into packets.
4. Update `docs/product/agent-contract.md` and agent docs.
5. Add tests for ready and blocked states.

## Change Source, Receipt, Or Integration Behavior

1. Preserve source boundaries and no-raw-secret rules.
2. Keep receipts human-facing.
3. Keep integrations dry-run unless live execution is explicitly designed.
4. Update relevant product docs and tests.

## Change Public Docs Or README

1. Keep claims aligned with implemented behavior.
2. Avoid overclaiming maturity.
3. Keep links local and current.
4. Run `palari docs check --json` once docs checks exist.
