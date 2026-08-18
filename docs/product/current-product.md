# Palari Today

Palari makes AI work reviewable. It is a local, provider-neutral system that
gives an agent a task, limits what it may use and change, checks the result, and
keeps required approval with a human.

It is not an agent runner, model provider, project manager, or compatibility
layer for every earlier Palari experiment.

## The product in one minute

Palari turns one task with clear limits into this work process:

```text
task and allowed files, sources, and actions
-> run
-> run record and current check results
-> independent review when required
-> human approval when required
-> result
```

One central evaluator determines the status and required next step. Storage,
CLI commands, task briefs, hooks, MCP, status views, UIs, and provider adapters
only translate that decision. They MUST NOT create competing rules for whether
work is complete or approved.

For work managed by Palari, the system guarantees that:

1. an agent cannot gain permission to read or write outside the task's allowed
   files, sources, and actions;
2. completion always requires current check results tied to the exact run and
   output version;
3. a required review is independent and tied to those same exact results;
4. only a qualified human can provide a required approval;
5. missing, stale, malformed, contradictory, ambiguous, or mismatched records
   stop the task safely;
6. work history is replayable and tamper-evident;
7. verification can run locally and offline; and
8. ordinary operation is deterministic and understandable.

These are permission and approval boundaries, not an OS sandbox. Palari rejects
undeclared sources, disallowed outputs, and disallowed commits observed by its
supported adapters. An unrestricted process running as the same OS user can
still access or alter host files before those checks. Preventing arbitrary host
access requires a separately proven sandbox. Access that bypasses Palari never
becomes a valid run record, check result, or approval.

Risk changes which approvals are required, never whether checks are required.
R1/light work with zero required approvals and no external action may complete
after current exact checks without independent review or human approval. Other
local R1/R2 work skips independent agent review and still stops for one human.
R3+ work and any external-write surface keep independent review. The task rules
determine the remaining human approval count.

## Ordinary paths

An agent can resume its ongoing relationship before entering task mechanics:

```text
palari agent home --as PALARI-ID
```

The read-only home has five plain parts: Goals, Team, Work, Checks, and Limits.
Work holds projects, ideas, tasks, and runs; Tasks split into now, next, and
later. Limits hold sources, guides, tools, rules, and outside links; Rules split
into allowed, ask, and never. The view grants no permission and creates no new
stored facts; current workspace records remain the truth.

An operator initializes a repository once, creates a bounded task, and checks
its status:

```text
palari init [--host claude|codex|cursor]
palari do TITLE PATH
palari inbox
palari detail WORK-ID
```

Between a goal and a task, an agent may add a bounded idea:

```text
palari work add TITLE --idea PATH
```

The idea keeps the proposed owner, project, file limits, dependencies, checks,
and approval count, but grants no authority and does not enter the task queue.
A human may turn it into active work with the emitted `palari approve IDEA-ID
--as HUMAN-ID --json` command. That choice does not approve the later result.

An agent normally needs two commands:

```text
palari agent start --next --as PALARI-ID --json
# work only inside the returned limits and commit the bounded result
palari agent advance WORK-ID --as PALARI-ID --json
```

`agent start` saves a task brief and creates a local assignment. `agent advance`
records the run, run record, and current check results, then finishes what can
be finished mechanically. It stops for independent review, human approval, an
external action, or a concrete blocker. If work is interrupted, `agent release`
records the blocker and next safe action before releasing the assignment.
Inspection helpers exist for recovery; they are not mandatory ceremony.

Initialization creates a distinct review-only agent for the starter goal. It
may inspect the exact review-mode task brief and record an advisory result, but
it is not execution-capable through the workbench and has no human authority.
Before execution and again before review, Palari derives an authority plan so a
reviewer cannot consume the only qualified final approver.

After checks are current, the human handoff shows the presentation and an exact
presentation-bound action. Local R1/R2 work without an external-write surface
skips independent review and still uses this human step. When review is
required, it happens first and remains advisory. For one reversible local task
whose effective final approval count can be completed by one person, the human
runs the emitted command. Its readable form begins:

```text
palari approve WORK-ID --as HUMAN-ID --json
```

Palari appends the presentation binding to that command; the person does not
copy proof or presentation digests. It rechecks the artifact, evidence, review
when required, journal, capability, effective final count, and exact state, and
records approval plus local completion in one transaction. The effective final
count is at least one even when the stored numeric count is zero, except for
R1/light/zero-count work with no external effects. Local R1/R2 work without an
external-write surface may skip agent review and still use this human step.
An agent may display the human action, but cannot execute it, create a human
decision, or manufacture approval.

`inbox` is the ordinary human view of work waiting for a yes or no.
`queue --approval-inbox` and `human-decision pack` remain the advanced surfaces
for batching, mixed decisions, and explicit recovery. They emit executable
commands only for viable named human actors. Current machine outputs are
Approval Inbox v2, Approval Pack v3, and Review Guide v2.

### Single-maintainer interaction measurement

The reproduced legacy path took four post-build governance commands to reach
the guaranteed failure (review guide, human review record, Approval Inbox, and
the emitted pack action). Recovery then required at least five more
role/review/presentation interactions before asking the founder again. That is
a lower bound of nine post-build interactions and three human authority
invocations: review, failed approval, and repeated approval.

The ordinary local R2 path takes two post-build agent commands (start and
advance), one inbox look, and one founder approve. Independent review is not
on that path. Only approve is human authority. Including builder start and
advance, the ordinary task lifecycle is two agent commands and one human
command. No opaque ID or digest is copied. R3+ and any external write still
stop for independent review before that human step.

**Current guarantee:** `palari init` seeds `HUMAN-FOUNDER`, a builder Palari,
and `PALARI-REVIEWER`. The first R2 task for that builder has a viable authority
plan out of the box. CI covers the product-command closeout
(init → do → start → advance → inbox → approve). Operators can replay
the narration with `palari demo --journey --no-pause`.

## Supported verification and storage

The supported portable verification format is PCAW v1: canonical, no-float
I-JSON in an in-toto Statement v1 envelope with SHA-256 subjects and a
normalized governance case. Full verification reads artifact bytes beneath an
explicit subject root and needs no network, credentials, provider, or original
workspace. Those protocol terms are retained because another PCAW
implementation must use them exactly.

PCAW v1 is unsigned. It does not authenticate declared identities, authorize
external actions, or provide portable deletion-history proof.

The current durable workspace format is:

- `workspace.json` with `schema_version: 2`; and
- `.palari/governance-journal.v2.jsonl`, the file that stores tamper-evident
  history for current changes.

New projects write v2 directly. A workspace without current journal continuity
is unsupported and cannot be upgraded in place.

Task briefs (`packets`), assignments (`claims`), session rules
(`session-contracts`), caches, and Git-witness files are local runtime state,
not alternate workspace truth. These parenthetical names explain stable JSON and
file paths; ordinary UI text uses the plain terms. `.palari/history.jsonl` is a
preserved historical file, not a current writer or source of permission.

A full history audit is explicit. Ordinary `queue`, `detail`, and `state`
commands translate recorded data into status views; they do not re-read output
bytes or scan all history. Commands that change trusted state and explicit
Approval Inbox or handoff steps perform the required current verification.

Palari's own source-maintenance exception and the not-yet-implemented ignored
live-state profile are documented in
[Self-Hosting Maintainer Mode](self-hosting-maintainer-mode.md). The current
product does not yet claim that live dogfood governance can remain isolated
while this source checkout stays clean.

Proof records have one current shape. Evidence requires exact output, manifest,
run-record, and time bindings. Every review requires an exact attempt, evidence,
run-record, task-contract, proof, and time binding. Missing fields fail closed;
Palari does not load an older proof shape for inspection.

The code-shaped names above are retained only where they identify exact stored
fields or formats. There is no supported migration from unversioned, v0, or v1
workspaces, legacy agent claims, or old Approval Packs.

## Optional connections

Supported connections consume the same central decisions:

- the local CLI;
- the Git commit boundary;
- tested Claude and Codex session setup (structural hooks + git gate);
- tested Cursor host setup (advisory session rule plus default git gate; skip
  with `--no-git-hook` / `cursor install --no-git-hook`);
- MCP stdio with explicit capability limits;
- Linear issue, comment, and webhook translation through the required
  plan, approval, and outbox steps;
- local Mission Control for supervision, guarded integration-plan decisions,
  and one-task exact approval for eligible reversible local work; and
- agent-ready repository documentation plus the network-free demo.

A connection cannot widen a task's allowed files, sources, or actions; approve
work; combine builder and reviewer; create human permission; bypass checks; or
turn a queued external action into an executed one.

## Parked and removed features

The August 2026 minimality pass deleted restore-point recovery, broad manual
record authoring, and the data-map, maintainer, gate, and playbook recommendation
commands. Git history retains them; the installed product does not. Ordinary
work never depended on those paths.

The large roadmap is also parked as `AMBIGUOUS`: it mixes unresolved strategy
with work that has since shipped, so it is neither current status nor an
execution backlog. The Palari Blueprint is `EXPERIMENTAL` research for possible
future protocol work, not a supported product promise.

Unsupported Devin, GLM, and generic session aliases have been removed. A
current Cursor host profile remains (`init --host cursor`: advisory session
rule plus default git gate; skip with `--no-git-hook`). Provider-specific Slack, GitHub, Jira, and email
preview shapes, the desktop prototype, its demo schema and showcase, and Pages
deployment are also removed. Mission Control is the one supported local human
UI, including guarded one-task Approve for eligible reversible local work.
Historical completion documents do not define today's product. Superseded PR
#19 implementation contracts remain available in Git history rather than the
current checkout.

## Non-goals and compatibility

Palari does not provide a hosted multi-user service, background agent runner,
secret manager, authenticated identity system, automatic merge or deployment,
generic live provider execution, or autonomous review or approval. Its core
rules and offline verification need neither the network nor runtime packages
beyond the Python standard library.

Palari is pre-1.0 and supports only its current stored formats. Old commands,
aliases, schemas, and stored formats fail closed; there are no upgrade readers,
wrappers, or shims. Historical records stay immutable in Git; historical
implementations do not remain executable forever.
