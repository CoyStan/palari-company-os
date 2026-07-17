# Quickstart

This path is for a first run. It shows Palari blocking an AI agent from
changing a file outside its boundary, without needing API keys or cloud setup.

For plain definitions of Palari-specific terms, keep the
[Glossary](glossary.md) nearby.

## Requirements

- Python 3.10 or newer
- Git

## Run The Demo

```bash
git clone https://github.com/CoyStan/palari-company-os.git && cd palari-company-os
./bin/palari demo
```

The demo uses a temporary copy of example files. It does not touch your repo
or call any external service.

You should see:

```text
*** BLOCKED: file change is outside Sofia's write boundary ***
changed: deploy/production.yml
allowed: docs/product/company-os.md
```

That is the main idea: the AI partner can work, but Palari checks the boundary.

## Govern Your First Change

The ordinary path is provider-neutral. Initialize one named agent identity, add
one bounded item, and let Palari select and claim the next safe item:

```bash
cd your-project
palari init --palari Agent --json
palari work add "Clean up launch notes" --write docs/notes.md --json
palari agent start --next --as PALARI-AGENT --json
```

`init` creates a starter workspace and reports the declared Palari identity;
`--palari Agent` produces `PALARI-AGENT` in this example. `work add` returns a
collision-resistant opaque work ID. `start --next` selects one eligible item,
persists its packet and portable session contract, and claims it. It does not
assign an identity or grant new authority: `--as` must name the Palari already
declared by `init`.

The agent follows the returned packet, changes only its allowed paths, runs the
declared checks, and commits the bounded change. It then uses the opaque
`WORK-...` ID returned by `start` to converge all deterministic proof steps:

```bash
palari agent advance WORK-RETURNED-BY-START --as PALARI-AGENT --json
```

Do not infer IDs such as `WORK-0001`, and do not wait for another work item's
number. Unrelated opaque work IDs can be claimed and completed in parallel.
`advance` stops at the first genuine independent-review, human-authority,
external-effect, or safety boundary; it never manufactures that judgment.

## Optional Host Hooks

Palari's packet, claim, scope, proof, review, and authority flow does not require
a provider adapter. Claude Code users may additionally run `palari claude
install` to deny out-of-boundary writes through host hooks. The hooks strengthen
runtime enforcement, but they are optional and do not replace Palari's
provider-neutral governance checks. See [Claude Code
Integration](claude-code-integration.md).

## Optional Local Desk

```bash
./bin/palari serve --as HUMAN-FOUNDER
```

This local supervision view is optional; it is not part of the provider-neutral
adoption or proof path.

## Verify The Repo

```bash
./scripts/verify.sh
```

This runs the same local checks used in development.

## Try A Safe Copy

```bash
rm -rf /tmp/palari-company-os-demo
cp -R examples/acme-company-os /tmp/palari-company-os-demo
./bin/palari --workspace /tmp/palari-company-os-demo queue
./bin/palari --workspace /tmp/palari-company-os-demo detail WORK-0001
```

The `--workspace` flag points Palari at the copy, so experiments do not change
the committed example.

## Check One Boundary Yourself

This path is allowed:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed docs/product/company-os.md --json
```

This path is blocked:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed deploy/production.yml --json
```

## Next Reading

- [Glossary](glossary.md) for the short version of every Palari noun.
- [Command Reference](command-reference.md) for CLI details.
- [Agent Contract](agent-contract.md) for the packet/check loop used by agents.
- [Core Objects](core-objects.md) for the full data model.
- [Minimality Contract](minimality-contract.md) for the rules that keep Palari small.
- [Linear Operating Loop](linear-operating-loop.md) for optional Linear dogfooding.
