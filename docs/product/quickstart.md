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

## Open The Live Local Desk

```bash
./bin/palari serve --as HUMAN-FOUNDER
```

This starts a local browser UI for the example workspace. It shows what needs
human attention, the allowed boundary, recent activity, and the receipt for the
selected work. It binds to `127.0.0.1` by default and writes through the same
local files as the CLI.

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

## Export The Static Dashboard

```bash
./bin/palari --workspace /tmp/palari-company-os-demo dashboard --out /tmp/palari-company-dashboard
```

Then open:

```text
/tmp/palari-company-dashboard/index.html
```

Use the static dashboard when you want a read-only artifact to share or publish.
Use `palari serve` when you want clickable local supervision.

## Next Reading

- [Glossary](glossary.md) for the short version of every Palari noun.
- [Command Reference](command-reference.md) for CLI details.
- [Agent Contract](agent-contract.md) for the packet/check loop used by agents.
- [Core Objects](core-objects.md) for the full data model.
- [Linear Operating Loop](linear-operating-loop.md) for optional Linear dogfooding.
