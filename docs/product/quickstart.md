# Quickstart

This first run shows Palari stopping an AI agent from changing a file outside
its task. It needs no API keys or cloud setup.

The [Glossary](glossary.md) explains both the plain words used here and the
older names that remain in stable commands or stored JSON.

## Requirements

- Python 3.10 or newer
- Git

## Run the demo

```bash
git clone https://github.com/CoyStan/palari-company-os.git && cd palari-company-os
./bin/palari demo
```

The demo creates a temporary local Git repository. It does not touch your repo
or call an external service. It shows the real path: take a bounded task,
commit an allowed change, and let `agent advance` record the run and checks.
You do not have to copy record IDs by hand.

You should see:

```text
*** BLOCKED: file change is outside Sofia's allowed files ***
changed: deploy/production.yml
allowed: docs/product/company-os.md
```

That is the main idea: the agent can work, but Palari checks its limits.

## Run your first checked change

The ordinary path works with any AI provider. Create one named agent, add one
task with exact allowed files, and let Palari take the next safe task:

```bash
cd your-repository
palari init --palari Agent --host codex --json
palari work add "Clean up launch notes" --create docs/notes.md --json
palari agent start --next --as PALARI-AGENT --json
```

`init` creates the starter workspace records and returns the declared builder
agent ID; `--palari Agent` produces `PALARI-AGENT` here. It also creates a
distinct review-only `PALARI-REVIEWER` linked to the starter goal but not to
the execution workbench. That trio is the solo-maintainer guarantee: one
founder can finish reviewed (R2) work with ordinary product commands—builder
start/advance, review-only accept-ready, then one founder `approve`—without
adding identities first. Run `palari demo --journey --no-pause` to see the
full closeout. `work add` returns an opaque, collision-resistant task ID.
`start --next` selects one eligible task, first verifies that a viable
reviewer and qualified final approver remain, saves its task brief and portable
session rules, and creates a local assignment. The stored files retain the
technical names `packet`, `session-contract`, and `claim` for compatibility.

`start` does not invent an identity or grant permission. `--as` must name an
agent already declared by `init`.

In a Git worktree, `init` also creates missing agent guidance and one
path-limited local commit that anchors the exact starter workspace records. It
does not overwrite existing `AGENTS.md` or `docs/agent/` files, and it excludes
unrelated staged and unstaged work. `--host codex` installs the portable
session rules, the assignment-bound Git check, and repository-local Codex hooks.
It includes new host configuration in the same anchor so the first task does
not inherit unexplained setup changes.

That mechanical anchor is not review or human approval. If setup is
interrupted, `work add` recovers it safely. If Git cannot provide an immutable
starting point, `agent start` returns one exact path-limited anchor command
instead of unrelated queue or validation commands.

The agent follows the returned task brief, changes only allowed files, and may
run task-specific checks while editing. After it commits the bounded change,
Palari uses fixed built-in verification profiles for authoritative evidence
(R1 is exact base-to-head `git diff --check` over changed paths). The agent then
uses the opaque `WORK-...` ID returned by `start`:

```bash
palari agent advance WORK-RETURNED-BY-START --as PALARI-AGENT --json
```

`advance` records the run, run record, and check results, then finishes every
safe deterministic step. It stops for independent review, human approval, an
external action, or a concrete safety blocker; it never invents those
judgments.

When review is required, the distinct review-only agent opens the returned
review handoff, inspects the exact candidate, and runs one concrete advisory
verdict command emitted by the review guide. The founder then sees the concise
human presentation and performs one action:

```bash
palari agent start WORK-ID --as PALARI-REVIEWER --mode review --json
# inspect the exact proof and run one emitted review_record_commands[].command
palari agent status WORK-ID --as PALARI-REVIEWER --mode review --json
# a human runs the exact emitted human_action_commands[].command
```

The simple action accepts no pack digest, review ID, evidence ID, or commit hash
from the human. Palari inserts a presentation digest into the emitted command,
so no opaque value is copied and any post-presentation change fails safely.
`approve` revalidates the one-task approval presentation before one crash-safe
local transaction. A manually entered bare command derives current state at
invocation. Stale or changed proof, identity collisions, invalid history,
incomplete effective approval counts, and external or irreversible work remain
blocked. The Approval Inbox and `human-decision pack` commands remain available
for advanced or batched decisions.

Do not infer IDs such as `WORK-0001`, and do not wait for another task's number.
Unrelated opaque task IDs can run in parallel.

## One-action host setup

Fresh repositories can pass `--host claude`, `--host codex`, or
`--host cursor` to `init`. Existing Palari workspaces use the same explicit
action:

```bash
palari init WORKSPACE-DIR --host codex --as PALARI-AGENT --json
```

Claude and Codex install the portable repository rules, structural Git commit
boundary, and tested session hooks (strict no-claim on adoption). Codex requires
one native `/hooks` review before its repository hooks activate. Cursor installs
an advisory project rule and the Git commit gate. Skip the Git gate with
`--no-git-hook`. Other unnamed agent tools can consume the
provider-neutral rules and Git boundary without a named session profile.

No profile grants review, human approval, merge, push, deployment, provider,
or external-write permission. Nested workspaces install at the enclosing Git
root. Existing root instructions or host configuration remain outside the
starter commit and require the one returned review/setup action. `palari claude
install` remains available for Claude hook-only setup, repair, and removal. See
[Claude Code Integration](claude-code-integration.md) and
[Cursor Integration](cursor-integration.md).

## Optional local desk

```bash
palari serve --as HUMAN-FOUNDER
```

Run this inside the repository initialized above. This local Mission Control
view is optional; it is not part of provider-neutral setup or verification. For
one eligible reversible local task it can offer a guarded one-click Approve
(`POST /approve-work`) on the same presentation-bound authority path as
`palari human-decision approve --presented …`.

## Verify The Repo

```bash
./scripts/verify.sh
```

This runs the same local checks used in development.

## Try a safe copy

```bash
rm -rf /tmp/palari-company-os-demo
cp -R examples/acme-company-os /tmp/palari-company-os-demo
./bin/palari --workspace /tmp/palari-company-os-demo queue
./bin/palari --workspace /tmp/palari-company-os-demo detail WORK-0001
```

The `--workspace` flag points Palari at the copy, so experiments do not change
the committed example.

## Check one boundary yourself

This path is allowed:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent status WORK-0003 --as PALARI-SOFIA --mode execute --json
```

This path is blocked:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo scope WORK-0003 --changed deploy/production.yml --json
```

## Next reading

- [Glossary](glossary.md) for plain names and stable technical names.
- [Command Reference](command-reference.md) for CLI details.
- [Agent Contract](agent-contract.md) for the task-brief and check loop used by agents.
- [Core Objects](core-objects.md) for the full stored data model.
- [Minimality Contract](minimality-contract.md) for the rules that keep Palari small.
- [Linear Operating Loop](linear-operating-loop.md) for optional Linear use.
