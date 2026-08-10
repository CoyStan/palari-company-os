# Command Reference

Palari has one supported lifecycle: create bounded work, let an agent produce
current proof, obtain independent review when required, and stop for exact
human approval. Run `palari COMMAND --help` for the complete option grammar.

Use `--workspace PATH` before the command to select a workspace. Use `--json`
for automation. Runtime behavior is local and dependency-free unless an
explicit Linear command performs a provider read or an approved queued write.

## First Run

```bash
palari demo
palari demo --journey --no-pause
palari init [REPOSITORY] [--host claude|codex|cursor]
```

`demo` uses a throwaway workspace and no network. `init` creates
`workspace.json`, the current tamper-evident journal, a builder, a distinct
reviewer, and a founder. A host selection also installs its tested local
boundary. Cursor's Git gate remains opt-in with `--strict-git`.

## Tasks

```bash
palari work add "Update the guide" --modify docs/guide.md --json
palari work add "Create a note" --create notes/new.md --approvals 1 --json
palari work add "Draft the next note" --idea --create notes/next.md --json
```

Use repeatable `--create`, `--modify`, and `--delete` options for exact path
intent. Other task options include `--read`, `--as`, `--goal`, `--workbench`,
`--risk`, `--intensity`, `--scope`, `--acceptance`, `--verify`, `--depends-on`,
`--parallel-policy`, and `--approvals`.

`--idea` stores the same bounded plan without creating a task or granting
authority. The response emits `palari approve IDEA-ID --as HUMAN-ID --json` for
a human to create the active task. Agents may add and show ideas; they may not
approve them.

Generic record creation and update commands are deliberately absent. Palari
creates run, run-record, and check-result records through `agent advance` so
they cannot drift apart.

Existing workspaces that lack an independent reviewer receive an exact focused
repair command from `agent next`:

```bash
palari reviewer add PALARI-REVIEWER --goal GOAL-ID --owner HUMAN-ID --json
```

## Agent Work

Resume one agent without choosing a task first:

```bash
palari agent home --as PALARI-ID [--json]
```

The read-only response uses five plain parts: Goals, Team, Work, Checks, and
Limits. Work holds projects, ideas, tasks, and runs; Tasks has now, next, and
later. Limits holds sources, guides, tools, rules, and outside links; Rules has
allowed, ask, and never. It shows current workspace facts and safe next
commands; it grants no permission. JSON output uses `palari.agent_home.v2`.

The ordinary agent path is two commands around the bounded implementation:

```bash
palari agent start --next --as PALARI-ID --json
# edit only allowed paths and commit the bounded result
palari agent advance WORK-ID --as PALARI-ID --json
```

`start` writes the task brief, portable session rules, and a digest-bound local
assignment. `advance` runs required verification and performs every safe local
mechanical step. It stops at independent review, human approval, an external
action, or a concrete blocker.

If work stops before proof is ready:

```bash
palari agent release WORK-ID --as PALARI-ID \
  --reason "Why work stopped" --next-action "The next safe step" --json
```

Read-only recovery and inspection commands remain available:

```bash
palari agent home --as PALARI-ID --json
palari agent next [--as PALARI-ID|--all] --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
palari agent check WORK-ID --as PALARI-ID --git-diff --json
palari agent finish WORK-ID --as PALARI-ID --json
palari agent handoff WORK-ID --as PALARI-ID --mode review --json
palari agent status WORK-ID --as PALARI-ID --json
palari agent advance WORK-ID --as PALARI-ID --dry-run --json
```

`agent status` is the canonical public read-only projection for task limits,
checks, ownership, blockers, stages, and the next safe action. The former public
`agent doctor` and `agent loop` aliases are no longer part of the CLI surface.

These helpers do not create approval. `advance` is the sole supported
check-and-finish mutation path.

## Independent Review

```bash
palari review guide WORK-ID --json
palari review record REVIEW-ID \
  --work-item-id WORK-ID \
  --reviewed-head GIT-SHA \
  --reviewer PALARI-REVIEWER \
  --binding-digest sha256:DIGEST \
  --verdict accept-ready \
  --json
```

The exact command emitted by a review-mode handoff contains the binding digest.
Valid verdicts are `accept-ready`, `changes-requested`,
`needs-human-decision`, and `blocked`. A builder cannot qualify as its own
independent reviewer.

Open decision questions have one read-only view:

```bash
palari decision guide DECISION-ID --json
```

## Human Approval

Approve a bounded idea before it becomes a task:

```bash
palari approve IDEA-ID --as HUMAN-ID --json
```

Idea approval accepts the plan, not a result. Work still has to pass its own
checks, independent review, and final approval rules.

For one eligible reversible local task, use the exact presentation-bound
command emitted by the handoff:

```bash
palari approve WORK-ID --as HUMAN-ID --json
```

The emitted command includes its presentation digest. The human must inspect
the current presentation before running it. Agents may display this command;
they may not execute it.

The advanced batch path remains:

```bash
palari queue --approval-inbox --json
palari queue --approval-inbox --select WORK-ID --json
palari human-decision pack --pack-digest DIGEST \
  --presentation-digest DIGEST --human-id HUMAN-ID \
  --approve-eligible --json
```

`human-decision pack` also supports explicit repeatable `--approve`, `--reject`,
`--defer`, and `--pack-member` selections.

## Operator Views

```bash
palari queue [--include-closed] [--json]
palari detail WORK-ID [--json]
palari state [--json]
palari validate [--json]
palari scope WORK-ID --changed PATH --action ACTION [--json]
```

Queue, detail, and state summarize recorded data. They do not replace exact
proof verification or a full history audit.

## Tamper-Evident History

```bash
palari history --json
palari history --checkpoint --acknowledge-break --actor HUMAN-ID \
  --reason "Record a manual repair" --json
palari history --recover --actor HUMAN-ID --json
```

Plain `history` verifies continuity. `--checkpoint --acknowledge-break` makes a
manual history break visible in a current journal. It cannot add history to an
unjournaled workspace. `--recover` resolves a prepared local transaction when
safe. Content-addressed restore-point browsing and restoration were removed.

## Portable Proof

```bash
palari proof export WORK-ID --output proof.json --json
palari proof verify proof.json --subject-root ARTIFACT-ROOT --json
palari proof verify proof.json --statement-only --json
```

PCAW verification is offline and does not load the original workspace.
`--statement-only` checks governance consistency without reading artifact
subjects.

## Generic Integration Boundary

```bash
palari integrations --json
palari integration check INTEGRATION-ID --json
palari integration plan INTEGRATION-ID --work WORK-ID \
  --event EVENT --action ACTION [--record] --json
palari integration approve PLAN-ID --by HUMAN-ID --json
palari integration reject PLAN-ID --by HUMAN-ID --reason REASON --json
palari integration cancel PLAN-ID --by HUMAN-ID --reason REASON --json
palari integration enqueue PLAN-ID --by HUMAN-ID --json
palari integration outbox-check OUTBOX-ID --json
palari integration outbox-cancel OUTBOX-ID --by HUMAN-ID --reason REASON --json
```

The generic boundary records provider-neutral plans and queued actions. It does
not execute an arbitrary provider API.

## Linear

Linear is the one live provider adapter. It supports checked issue reads and
imports, plus comments, issue status updates, and issue creation only after the
normal plan, human approval, and outbox steps. See the
[Linear Operating Loop](linear-operating-loop.md) for exact commands and the
webhook contract.

## Host Boundaries

`init --host` is the preferred setup. Explicit repair and inspection commands
remain available:

```bash
palari claude install [--strict] [--local] [--remove] --json
palari claude status --json
palari git install [--remove] --json
palari git status --json
palari cursor install [--no-git-hook] [--remove] --json
palari cursor status --json
```

`claude hook` and `git pre-commit` are installed enforcement entrypoints, not
ordinary interactive commands. Host boundaries reject observed writes or
commits outside the active task; they are not an operating-system sandbox.

## Agent-Ready Docs and MCP

```bash
palari docs check --json
palari docs map
palari docs init --dry-run --json
palari mcp serve [--repo REPOSITORY]
```

MCP exposes bounded Palari translations over local stdio. It does not grant
new capability or authority.

## Mission Control

```bash
palari serve --as HUMAN-ID
palari demo --serve
```

Mission Control is a local supervision view. Its state-changing actions use
the same central evaluator, CSRF guard, workspace compare-and-swap, review
binding, approval, and integration-plan rules as the CLI.
