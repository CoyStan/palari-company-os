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
after current exact checks without independent review or human approval. Every
other task stops for independent review. The task rules determine whether a
qualified human must approve it afterward.

## Ordinary paths

An operator initializes a repository once, creates a bounded task, and checks
its status:

```text
palari init [--host claude|codex]
palari work add TITLE --create PATH | --modify PATH | --delete PATH
palari queue
palari detail WORK-ID
```

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

After the independent reviewer records the exact result, the human handoff
shows the current presentation and an exact presentation-bound action. For one
reversible local task whose effective final approval count can be completed by
one person, the human runs the emitted command. Its readable form begins:

```text
palari approve WORK-ID --as HUMAN-ID --json
```

Palari appends the presentation binding to that command; the person does not
copy proof or presentation digests. It rechecks the artifact, evidence, review,
journal, capability, effective final count, and exact state, and records
approval plus local completion in one transaction. For review-required work,
the effective final count is at least one even when the stored numeric count is
zero. The sole exception is R1/light/zero-count work with no external effects.
An agent may display the human action, but cannot execute it, create a human
decision, or manufacture approval.

`queue --approval-inbox` and `human-decision pack` remain the advanced surfaces
for batching, mixed decisions, and explicit recovery. They emit executable
commands only for viable named human actors. Current machine outputs are
Approval Inbox v2, Approval Pack v3 (with a v2 reader), and Review Guide v2.

### Single-maintainer interaction measurement

The reproduced legacy path took four post-build governance commands to reach
the guaranteed failure (review guide, human review record, Approval Inbox, and
the emitted pack action). Recovery then required at least five more
role/review/presentation interactions before asking the founder again. That is
a lower bound of nine post-build interactions and three human authority
invocations: review, failed approval, and repeated approval.

The converged path takes four post-build commands: start the review-only agent,
run one concrete review verdict action, inspect its handoff, and run the exact
human approval action. Only the last command is human authority. Including
builder start and advance, the ordinary task lifecycle is five agent commands
and one human command. No opaque ID or digest is copied.

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

New projects write v2 directly. Existing projects without journal continuity
need an explicit v2 checkpoint before mutation. The v1 filename accepts only
strict legacy records and is never a compatibility path for v2 output.

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

The only supported historical inputs are those proven by committed data:

- the sealed governance-journal v1 predecessor, checked through a narrow
  read-only boundary before current activation;
- schema-v2 `work_items` records without additive `path_intents`, interpreted
  only with their older presence rules;
- historical `evidence` records without `output_binding_version`, which remain
  inspectable without gaining stronger permission; and
- unbound negative or non-accepting review records, which remain inspectable
  but can never satisfy a required review or approval.

The code-shaped names above are retained only where they identify exact stored
fields or formats. There is no supported migration from unversioned, v0, or v1
workspaces, legacy agent claims, or Approval Pack v1 because no committed real
fixture requires it. Split `collection_files` support is parked pending a
product decision and is not part of ordinary storage.

## Optional connections

Supported connections consume the same central decisions:

- the local CLI;
- the Git commit boundary;
- tested Claude and Codex session setup;
- MCP stdio with explicit capability limits;
- Linear issue, comment, and webhook translation through the required
  plan, approval, and outbox steps;
- local Mission Control for supervision, guarded integration-plan decisions,
  and one-task exact approval for eligible reversible local work; and
- agent-ready repository documentation plus the network-free demo.

A connection cannot widen a task's allowed files, sources, or actions; approve
work; combine builder and reviewer; create human permission; bypass checks; or
turn a queued external action into an executed one.

## Parked features

Several reachable features remain parked because maintainers could not safely
delete or promote them: restore-point recovery, the split-collection reader,
broad manual planning and record authoring beyond the ordinary first-use path,
and the data-map, maintainer, gate, and playbook recommendation views. They are
not part of the current core, do not grant permission, and carry no pre-1.0
compatibility promise. Ordinary work must not depend on them.

The large roadmap is also parked as `AMBIGUOUS`: it mixes unresolved strategy
with work that has since shipped, so it is neither current status nor an
execution backlog. The Palari Blueprint is `EXPERIMENTAL` research for possible
future protocol work, not a supported product promise.

Unsupported Cursor, Devin, GLM, and generic session aliases have been removed.
So have the provider-specific Slack, GitHub, Jira, and email preview shapes,
the desktop prototype, its demo schema and showcase, and Pages deployment.
Mission Control is the one supported local human UI. Historical completion
documents do not define today's product.

## Non-goals and compatibility

Palari does not provide a hosted multi-user service, background agent runner,
secret manager, authenticated identity system, automatic merge or deployment,
generic live provider execution, or autonomous review or approval. Its core
rules and offline verification need neither the network nor runtime packages
beyond the Python standard library.

Palari is pre-1.0. Compatibility is retained only for a real committed stored
format and only behind one explicit reader or migration boundary. Public
commands, aliases, schemas, fixtures, tests, and documents are not retained
merely because they existed in version 0.2.0. Deliberate removals receive no
alias, wrapper, or shim. Historical records stay immutable in Git; historical
implementations do not remain executable forever.
