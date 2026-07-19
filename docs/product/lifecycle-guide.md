# Lifecycle Guide

Palari Company OS models this loop:

```text
Goal -> Palari -> Work -> Attempt -> Receipt -> Evidence -> Review -> Human Decision -> Outcome
```

For asynchronous preparation, multiple reviewed items may be compiled into a
parked Approval Inbox:

```text
bounded preparation -> parked item proofs -> canonical Approval Pack
-> one exact human pack decision -> eligible local execution -> outcome
```

The interaction is compressed; each item keeps its own scope, attempt,
receipt, evidence, review, decision, and journal result. A dependency change
stales descendants—even when a narrowed pack omits the dependency—while
unrelated current members retain their valid state. A changed risk or batch
policy also stales the exact pack. Recursive dependency bindings make a changed
terminal dependency artifact stale rather than treating terminal status as
sufficient. External or irreversible effects remain parked for their native
individual gate.

## Normal Operator Path

The normal path derives mechanical records instead of asking an agent to copy
their ids and digests:

```bash
palari init --host codex
palari work add "Draft onboarding note" --write docs/onboarding.md
palari agent start --next --as PALARI-ID --json
# work inside the packet and commit the bounded result
palari agent advance WORK-ID --as PALARI-ID --json
```

`--host` accepts `claude` or `codex` and folds new portable instructions, the
claim-bound Git gate, and a tested session-hook adapter into the starter
anchor. Existing workspaces use `palari init WORKSPACE-DIR --host HOST --as
PALARI-ID --json`; without an explicit host, initialization still refuses an
existing workspace. Other harnesses can consume the provider-neutral contract
without being advertised as supported session profiles.

The presence-only `--write` form requires an output to exist. Use repeatable
`--create`, `--modify`, and `--delete` instead when exact mutation class
matters; exact intents cannot be mixed with `--write`.

`start --next` selects exactly one item already considered safe by the queue,
persists its packet and portable session contract, and claims it. `advance`
derives the exact claim range, checks declared path intent, runs verification,
and records deterministic attempt, receipt, evidence, and closeout state. It
then completes eligible low-risk work or stops at independent review, exact
human authority, external state, or a concrete blocker. Neither command creates
an independent verdict or human decision.

After a separate current review, a qualified human uses one inbox and one exact
action:

```bash
palari queue --approval-inbox --json
# inspect the emitted presentation, then run its exact
# `palari human-decision pack ...` command once
```

The action binds the current pack and presentation digests. Stale proof,
incomplete quorum, non-batchable work, and external effects remain parked with
an explicit owner and next step. Review and acceptance stay attributable to
distinct actors.

When execution stops before proof is ready, preserve that fact before releasing
ownership:

```bash
palari agent release WORK-ID --as PALARI-ID \
  --reason "Waiting for product direction" \
  --next-action "Ask the founder to choose the final wording" --json
```

Parking records one blocked attempt and the exact next safe action, then
releases the owned claim. It creates no completion proof or authority. The
workspace must already have a writable governance journal; legacy work receives
the exact explicit `history --checkpoint` activation action and no retroactive
continuity claim. The commands below remain available as lower-level authoring
and recovery surfaces; they are not the ordinary agent ceremony.

## Retire Obsolete Work Without Pretending It Completed

When an unclaimed item is genuinely obsolete, close attention explicitly
through the existing governed update path:

```bash
palari work update WORK-OLD \
  --status superseded \
  --terminal-reason "A narrower contract now owns the objective." \
  --successor-work-item-id WORK-NEW --json

palari work update WORK-EXPERIMENT \
  --status abandoned \
  --terminal-reason "The experiment no longer earns operator attention." --json
```

These dispositions are audit terminalization, not successful completion. They
create no attempt, receipt, evidence, review, human decision, acceptance, or
outcome. A reason is mandatory and the successor is optional, but any successor
must be an existing distinct work item. Successor cycles, retirement with an
active attempt, open decision, or unresolved external action, and dependencies
that still point at retired work all fail closed. Rebind a dependent to the
explicit successor before retiring its old prerequisite.

Retired work is absent from the ordinary queue, `agent next`, and Approval
Inbox. It remains visible through `queue --include-closed` and `detail`, and an
explicit `agent start` cannot claim it. Historical proof and review records are
preserved rather than rewritten.

## Parked Expert Authoring

The broad record-by-record authoring commands remain available for explicit
workspace repair and expert fixture construction. They are parked surfaces,
not a second supported lifecycle, an agent fallback, or a compatibility
promise. The command reference lists them separately from the ordinary path.

Supported agent hooks may prepare a proposal or scope-expansion decision, but
they cannot directly manufacture attempts, receipts, evidence, reviews,
acceptance, human decisions, or outcomes. Use `agent advance` to derive agent
proof and the exact Approval Inbox action for human authority.

Every current terminal transition is evaluated by the same governance kernel:
proof must be complete and current, artifact and contract bindings must match,
required review must be independent, required human authority must be exact,
and dependencies and external effects must be safe. A substantive mutation
invalidates derived acceptance and completion.

PCAW v1 is the supported portable proof format. `proof export` creates a
canonical statement, and `proof verify` derives its state locally and offline
without trusting the claimed result. Workspace `create`, `modify`, and `delete`
path intents remain local proof: PCAW v1 does not claim portable deletion
history.

Journal restoration and full continuity audit are explicit recovery actions.
They append history rather than rewriting it, and fail closed when restoration
could replay an external effect.
