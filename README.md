# Palari Company OS

[![CI](https://github.com/CoyStan/palari-company-os/actions/workflows/ci.yml/badge.svg)](https://github.com/CoyStan/palari-company-os/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-v0.1%20alpha-8a6d3b.svg)](docs/product/roadmap.md)

Palari Company OS is a local, file-backed control plane for AI-assisted work.
It helps humans and AI agents agree on:

- what the agent is trying to do
- which sources it may read
- which files or outputs it may change
- what it actually used, created, skipped, or left undoable
- when a human must review or approve the work

It is not another chatbot. It is the operating contract around AI work: goals,
workbenches, named AI partners, bounded work items, receipts, evidence, review,
human decisions, and outcomes.

## Who This Is For

This repo is for people experimenting with serious AI work:

- founders and operators using AI across messy company tasks
- developers giving coding agents clearer boundaries
- teams that want parallel AI work without losing human authority
- researchers or builders exploring how agent work should be recorded

If you have ever asked "what did the AI actually read or change?", Palari is
about making that answer inspectable.

## What You Can Try Today

This is a **v0.1 alpha local CLI**. It runs from local files, has no runtime
package dependencies beyond the Python standard library, and does not require
API keys, cloud accounts, databases, Slack, GitHub apps, Google Drive, or a
background service.

Implemented now:

- strict workspace schema and validation
- goals, humans, Palaris, workbenches, sources, work items, attempts, receipts,
  evidence, reviews, human decisions, outcomes, and history
- queue, detail, state, history, dashboard, and desktop prototype views
- agent packets for bounded AI-agent context
- local packet persistence and lightweight claims for `agent start`
- file-change boundary checks for `agent check --changed` and `--git-diff`
- source and receipt trust records
- parallel workbench modeling and conflict warnings
- dry-run integration plans, approvals, and cancelable outbox records
- external playbook recommendations as lightweight guidance
- example and dogfood workspaces
- CI, local verification, and install smoke tests

Not implemented yet:

- live Slack, GitHub, Jira, email, Google Drive, or document connector execution
- hosted web app or multi-user server
- background agent runner
- real broker execution
- real policy acceptance
- secret manager or signed key custody
- autonomous acceptance, merge, push, deploy, or live external writes

## Quickstart

Requirements:

- Python 3.10 or newer
- Git

Clone the repo:

```bash
git clone https://github.com/CoyStan/palari-company-os.git
cd palari-company-os
```

Use the repo-local CLI wrapper:

```bash
./bin/palari --help
```

Or install it in editable mode:

```bash
python3 -m pip install -e .
palari --help
```

Run the local verification:

```bash
./scripts/verify.sh
```

Copy the demo workspace into `/tmp` so experiments do not modify the committed
example files:

```bash
rm -rf /tmp/palari-company-os-demo
cp -R examples/acme-company-os /tmp/palari-company-os-demo
```

Inspect the work queue:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo queue
```

Open one work item:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo detail WORK-0001
```

Generate a static dashboard:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo dashboard --out /tmp/palari-company-dashboard
```

Then open:

```text
/tmp/palari-company-dashboard/index.html
```

Generate the standalone desktop prototype:

```bash
./bin/palari desktop-prototype --out /tmp/palari-desktop-prototype
```

Then open:

```text
/tmp/palari-desktop-prototype/index.html
```

## Agent Workflow

The `agent` commands are mostly meant for coding agents or AI operators. Humans
can run them to inspect the contract, but the normal idea is that an agent asks
Palari what work is safe, reads one compact packet, starts a bounded local
attempt, checks its file changes, and releases or finishes cleanly.

Find the next useful item:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent next --as PALARI-SOFIA --json
```

Read the packet the agent would receive:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
```

Start the copied demo work item. This persists the packet and creates a local
claim in the `/tmp` demo workspace:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
```

Check whether an observed file change stays inside the allowed boundary:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed docs/product/company-os.md --json
```

Release the local claim:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent release WORK-0003 --as PALARI-SOFIA --json
```

In plain language:

```text
find safe work -> read the packet -> claim the local attempt
  -> compare changes against the boundary -> release, finish, or ask for help
```

## Core Concepts

| Concept | Plain meaning |
| --- | --- |
| Goal | Why the work exists. |
| Human | A person with ownership, review, or approval authority. |
| Palari | A named AI work partner with scope and standards. |
| Workbench | A bounded arena of sources, people, Palaris, targets, and parallel work. |
| Source | Selected context the work may read. |
| Work item | One bounded unit of intended work. |
| Attempt | One concrete execution of that work. |
| Receipt | Human-facing record of what was used, created, skipped, and left undoable. |
| Evidence | Verification tied to the attempt or artifact state. |
| Review | Independent inspection of the result or evidence. |
| Human decision | Explicit approval, rejection, or blocker. |
| Outcome | What was learned after the work closed. |

The product loop is:

```text
goal -> workbench -> selected sources -> work item -> attempt
  -> receipt -> evidence or review when needed
    -> human decision when needed -> outcome
```

## Useful Commands

```bash
# Read models
./bin/palari queue
./bin/palari detail WORK-0001
./bin/palari state
./bin/palari history

# Safety and boundaries
./bin/palari validate
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json

# Agent contract
./bin/palari agent next --as PALARI-SOFIA --json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json

# Lightweight process guidance
./bin/palari playbooks sources
./bin/palari playbooks recommend WORK-0003

# Agent-ready repo docs
./bin/palari docs check --json
./bin/palari docs map
./bin/palari docs init --dry-run --json

# Static visual surfaces
./bin/palari dashboard --out /tmp/palari-company-dashboard
./bin/palari desktop-prototype --out /tmp/palari-desktop-prototype
./bin/palari desktop-serve --out /tmp/palari-desktop-prototype --port 8787
```

Use `--json` when wiring Palari into agents, scripts, or other tools.

## Repository Layout

```text
bin/palari                         CLI wrapper
src/palari_company_os/             Python package
schemas/workspace.schema.json      Workspace schema
examples/acme-company-os/          Small example workspace
workspaces/palari-company-os/      Repo dogfood workspace
docs/product/                      Product and operator documentation
docs/agent/                        Agent-ready repo orientation and invariants
docs/showcase/                     Public-facing examples and vignettes
scripts/verify.sh                  Full local verification
scripts/install_smoke.sh           Isolated package install smoke
tests/                             Unit and fixture tests
```

## Documentation

Start here:

- [AI Work Vignettes](docs/showcase/ai-work-vignettes.md) for friendly examples
- [Quickstart](docs/product/quickstart.md) for the shortest command path
- [Product Model](docs/product/company-os.md) for the larger concept
- [Agent Contract](docs/product/agent-contract.md) for AI-agent packet behavior
- [Agent Loop Smoke](docs/product/agent-loop-smoke.md) for an end-to-end agent command walkthrough
- [Command Reference](docs/product/command-reference.md) for CLI details
- [Agent Repo Map](docs/agent/repo-map.md) for implementation orientation
- [Agent Contracts And Invariants](docs/agent/contracts-and-invariants.md) for boundaries agents must preserve

Then go deeper:

- [Core Objects](docs/product/core-objects.md)
- [Authority And Gates](docs/product/authority-and-gates.md)
- [Schema And Validation](docs/product/schema-and-validation.md)
- [Lifecycle Guide](docs/product/lifecycle-guide.md)
- [External Playbooks](docs/product/playbooks.md)
- [Testing Guide](docs/product/testing-guide.md)
- [Security Notes](docs/product/security.md)
- [Roadmap](docs/product/roadmap.md)
- [Changelog](CHANGELOG.md)

## Verification

Run the normal local verification stack:

```bash
./scripts/verify.sh
python3 -m unittest discover -s tests
./scripts/install_smoke.sh
```

`./scripts/verify.sh` runs unit tests, Python compilation, JSON validity checks,
the lightweight style checker, and CLI smoke checks. `install_smoke.sh` creates
a temporary virtual environment, builds and installs a wheel, imports it, checks
the installed `palari` command, and confirms packaged default fixtures work.

GitHub Actions runs the core checks on Python 3.10 and 3.12.

## Design Principles

- **Human authority stays explicit.** AI can prepare and explain work; it does
  not silently accept, merge, deploy, activate policy, or expand its own scope.
- **Sources are selected.** A Palari should know what it can read and what it
  cannot read.
- **Receipts are for trust.** Receipts explain what happened in human terms;
  they are not a replacement for governance evidence.
- **Risk changes intensity.** Low-risk local work can stay light. Higher-risk
  work still requires stronger proof and human decisions.
- **Read models do not mutate authority.** Queue, detail, state, dashboard, and
  prototypes are derived from workspace data.
- **Ordinary software maintenance wins.** The repo should stay simple,
  inspectable, dependency-light, and easy for humans and agents to work on.

## Contributing

This project is early and still changing quickly. Small, focused improvements
are preferred. Good first contributions include documentation fixes, failing
fixture reductions, command examples, and tests around existing behavior.

See [Contributing](docs/product/contributing.md) for local development notes.

## License

MIT. See [LICENSE](LICENSE).
