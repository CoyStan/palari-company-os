# Agent Workflow Smoke

Use this smoke test to exercise the public agent workflow in a disposable copy
of the ACME example. It is deliberately read-only around review and approval:
the commands below may expose a human boundary, but they never cross it.

## Prepare a disposable workspace

```bash
PALARI_SMOKE_ROOT="$(mktemp -d)"
cp -R examples/acme-company-os "$PALARI_SMOKE_ROOT/workspace"
```

Every command must keep the explicit `--workspace` argument. The repository,
committed example, and dogfood workspace are not smoke-test targets.

## Exercise execution

Run the selection and task commands in order:

```bash
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent next --all
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent next --as PALARI-SOFIA --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent check WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed docs/product/company-os.md --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent finish WORK-0003 --as PALARI-SOFIA --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent status WORK-0003 --as PALARI-SOFIA --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent release WORK-0003 --as PALARI-SOFIA --json
```

This sequence should select bounded work, save its packet and claim, evaluate
the declared file boundary, explain unfinished trust records, present the
canonical task status, and finally release the claim. A ready brief is not a
completion result. Only the check and finish projections can establish whether
the required run record, evidence, review, and approval exist.

## Exercise review handoff

The example intentionally lacks complete proof, so a fail-closed response is a
valid result. Inspect it without creating review or approval records:

```bash
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent next --all --mode review
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent brief WORK-0001 --as PALARI-ALFRED --mode review --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent check WORK-0001 --as PALARI-ALFRED --mode review --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent finish WORK-0001 --as PALARI-ALFRED --mode review --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent handoff WORK-0001 --as PALARI-ALFRED --json
./bin/palari --workspace "$PALARI_SMOKE_ROOT/workspace" agent status WORK-0001 --as PALARI-ALFRED --mode review --json
```

Review briefs remain read-only. `agent handoff` may present commands under a
`human_action_boundary`; any `human_action_commands` belong to the human
supervisor. An agent may report them but must not execute them.

The smoke is successful when all observations stay inside the copied workspace,
missing prerequisites remain explicit, and no provider call, deployment,
secret read, external write, review record, or human decision is fabricated.
