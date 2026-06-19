# Quickstart

## Requirements

- Python 3.10 or newer
- Git

No secrets, cloud credentials, external services, old Palari Orchestrator
worktrees, or hidden local state are required.

## Clone And Verify

```bash
git clone git@github.com:CoyStan/palari-company-os.git
cd palari-company-os
./scripts/verify.sh
```

## Inspect The Example Workspace

```bash
./bin/palari validate
./bin/palari queue
./bin/palari detail WORK-0001
./bin/palari state
```

## Try A Scope Check

```bash
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json
./bin/palari scope WORK-0001 --changed secrets.env --action deploy
```

The first command should pass. The second should fail closed because the path
and action are outside the work item's declared boundary.

## Try Authoring In A Copy

```bash
cp -R examples/acme-company-os /tmp/palari-company-os-demo
./bin/palari --workspace /tmp/palari-company-os-demo goal create GOAL-DEMO --title "Demo goal"
./bin/palari --workspace /tmp/palari-company-os-demo validate
```

