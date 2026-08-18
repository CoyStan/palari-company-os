# Agent Contract

Palari gives AI agents a clear task, limits, and completion checks. Humans use
status views, run records, blockers, and approval records to supervise the
work. Agents use the CLI to find one bounded task, receive a task brief, act
inside the allowed files and sources, and stop when a person must review or
approve something.

This document occasionally shows internal names such as `packet`, `claim`,
`receipt`, and `human_decision` because they are exact stored or command-line
interfaces. See [Plain Language](plain-language.md) for the words shown to
people and the compatibility boundary.

## Normal Work Process

Ordinary execution starts by selecting one safe task and assigning it to the
agent:

```bash
palari agent start --next --as PALARI-ID --json
```

Explicit inspection and selection remain available:

```bash
palari agent home --as PALARI-ID --json
palari agent next --as PALARI-ID --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --session-contract --json
palari agent start WORK-ID --as PALARI-ID --mode execute --json
palari agent brief WORK-ID --as PALARI-ID --mode review --json
```

`agent home` is the lasting relationship entry point. It shows current
workspace facts under Goals, Team, Work, Checks, and Limits. Any part may end
there or split into three to five child parts. At each split, the parts do not
overlap and leave nothing out. The view is read-only: it does not make up facts,
create work, claim a task, or widen permission. Concrete writes still require
a ready task brief and assignment.

`palari agent brief` is a read-only preview. `palari agent start` is the normal
entry point for ready work: it saves the exact task brief the agent received,
saves its portable session rules (stored as `session-contract`), and records a digest-bound local task
lock (stored internally as a `claim`). A blocked brief remains read-only and
does not receive a lock. `agent brief --session-contract` emits the portable
session rules instead of the full brief without writing runtime state. `agent
start --next` uses the same queue rules and brief compiler, then saves exactly
one ready brief and lock. It does not infer new permission or silently choose
blocked work. Use explicit `start WORK-ID --isolate` when a committed task
needs its own deterministic branch and worktree.

For first adoption in a Git worktree, `palari init` declares one builder and a
second review-only Palari, writes only missing agent-ready guidance, and makes
one path-limited local commit of the new local rules file plus those generated
docs. The reviewer is linked to the starter goal and source but is not in the
execution workbench; it cannot build, provide human approval, broaden scope, or
perform external writes. Add `--host claude`, `--host codex`, or
`--host cursor` in the same anchored action. Claude and Codex install the
portable session rules, task-lock-bound Git check, and tested repository-local
session hooks (strict no-claim on adoption). Cursor installs an advisory project
rule and the Git commit gate by default. Pass `--no-git-hook` to skip the gate.
Existing guidance, host
configuration, and unrelated staged or unstaged paths are preserved rather than
absorbed into the bootstrap commit. This is an immutable baseline bootstrap, not
review, approval, or authenticated human attribution.
`palari work add` idempotently recovers a missing starter anchor before changing
the work declaration. If a manually assembled workspace still has no committed
authority origin, `agent start` fails closed with one exact `git add` plus
path-limited `git commit --only` recovery action.

`palari work add TITLE --idea ...` is the narrow exception to task-authority
commands: an agent may store a bounded idea because it grants no permission and
creates no task or assignment. The human-only `palari approve IDEA-ID --as
HUMAN-ID` step creates active work with the same declared limits. This approval
accepts the plan only; it cannot stand in for checks, review, or final approval.

An existing Palari workspace uses the same idempotent action: `palari init
WORKSPACE-DIR --host HOST --as PALARI-ID --json`, where `HOST` is `claude`,
`codex`, or `cursor`. Without explicit `--host`, `init` still refuses an existing
workspace. Claude and Codex have tested structural session adapters; Codex
project hooks require explicit `/hooks` trust. Cursor has a tested host
profile with a default Git commit gate (`init --host cursor`; skip with
`--no-git-hook`, or later `cursor install --no-git-hook`). Other harnesses
may consume the provider-neutral session rules and host-neutral Git check
without a named session profile. Adoption grants no
review, approval, merge, push, deployment, provider, or external-write
permission.

The ordinary loop is deliberately short:

1. Run `palari agent start --next --as PALARI-ID --json` and continue only when
   the returned task brief is ready. Read and write only its allowed paths and
   sources.
2. Do the bounded work and commit it. Then run `palari agent advance WORK-ID
   --as PALARI-ID --json` once. It derives the complete change range since the
   task lock started, checks
   exact create/modify/delete intent, runs fixed verification profiles, and
   atomically records the run, run record, check results, and closeout state.
   R1 uses exact base-to-head `git diff --check` over the changed paths; task
   prose is never executed as a check.
   It stops at independent review, human approval, external state, or a
   concrete blocker; it never creates a review or a person's decision. Every
   completion requires current, passing checks tied to the exact version. Only
   R1/light work with zero required approvals and no allowed, planned, queued,
   or actual external writes may complete without independent review and human
   approval.
3. Follow the one command returned at that boundary. A distinct eligible
   reviewer starts the task in `--mode review`, inspects its read-only brief,
   and records an advisory result tied to the exact candidate. The local review
   assignment lets supported hooks bind the review command to that reviewer
   and task. Palari rejects that reviewer before recording if the choice would
   leave too few qualified final approvers.
4. After the separate current review, the human handoff shows the concise
   presentation and an exact command. A qualified human runs that emitted
   `palari approve ... --presented DIGEST` action once; the binding is supplied
   by Palari, not copied. Palari revalidates exact proof before deterministic
   local approval-and-completion bookkeeping. A bare command derives current
   state at invocation and is not bound to an earlier handoff. The Approval
   Inbox and digest-bound pack commands remain available for advanced or
   batched use.

`agent advance` is the sole current run-to-verification and closeout path. Use
`agent advance --dry-run` to inspect the plan and `agent status` for detailed
diagnosis and eligible review or human actions. Check refresh remains
an explicit recovery path without a task lock: `agent advance --refresh-verification --dry-run`
previews it, and the non-dry-run form creates fresh exact-head check results only when
ordinary task outputs remain byte-identical. Prior review and human
approval never carries forward.

If execution must stop before checks are ready, run:

```bash
palari agent release WORK-ID --as PALARI-ID \
  --reason "Why work stopped" --next-action "The next safe step" --json
```

Parking durably records one blocked run tied to the exact task brief, version,
and workspace, observed allowed and disallowed file changes, the reason, and the next
safe action before releasing the owned task lock. A retry after an
interrupted release is idempotent only for the same durable record and unchanged
repository state. Parking creates no run record, check results, review,
approval, or result. Use bare `agent release` only when no
durable interrupted-work record is required. Parking requires an activated,
writable tamper-evident history. A workspace without one fails before mutation
and cannot be upgraded in place.

For independent inspection work, use `--mode review` after a task is in
`needs-review`. The task brief is read-only with respect to outputs. It
includes the review focus, run, check results, run record, suggested review
results, the deterministic authority plan, viable reviewers, rejected
reviewers with smallest safe corrections, and the qualified human approvers
left by each choice. A matching agent reviewer may record only its advisory
result; it cannot create human approval.
`palari agent next --as PALARI-ID --mode review --json` ranks those reviewable
items as ready while keeping non-reviewable work blocked.

## What The Task Brief Contains

The task brief (stored internally as a `packet`) collects everything an agent
needs in one place. It prevents agents from reconstructing the work process
from many separate commands. A task brief answers:

- who the agent is
- which task is assigned
- why the work matters
- which files, sources, and actions are allowed
- source readiness details such as data class, permission, steward, freshness,
  and redaction requirement
- which actions are forbidden
- what output is required
- which run record, checks, review, approval, or integration status matters
- when the agent must stop
- which commands are safe to run next

The brief must not dump the whole workspace. It includes only directly related
records and explicit notes about omitted context.

Aggregate agent views share one request-local task brief, check, and directive. A
pure directive compiler turns that current check into state, owner, blocker
class, and next safe action. It has no clock, filesystem, mutation, review, or
human-approval access. Transition checks—not the directive—remain decisive.
Exact Approval Inbox and verification-binding operations own their
request-local history check, and a changed witness forces a new scan.

## Helpful Documentation

Task briefs include compact repository-documentation context:

- `documentation_state` says whether agent-ready repo docs are present,
  partial, or missing.
- `recommended_docs` points to committed docs likely to help with the selected
  task.
- `omitted_context` states that full documentation text was not loaded into the
  task brief.

This keeps briefs context-window-safe. Agents should read recommended docs only
when they need that orientation. Missing docs are low context, not a work
blocker; use `palari docs init --dry-run --json` to inspect the proposed starter
set.

## Review Focus

Task briefs and exact review guides identify the checks likely to matter for
the selected task:

- prompt permission
- source boundary
- external writes
- human approval
- deploy/runtime
- privacy/multimodal
- product overclaim

The guide includes the reviewer role, what to inspect, current run/check
context, and exact verdict actions. It does not review work or grant approval.

## Task Brief Status

`status: ready` means the agent may proceed inside the task brief's boundary.

`status: blocked` means the agent must not perform the work. It may run only the
commands listed in `next_allowed_commands`, or report the blockers to a human.

Finish, status, next, handoff, and Approval Inbox JSON classify the resolver as
`automatic-reconciliation`, `agent-action`, `independent-review`,
`human-authority`, `external-state`, or `terminal`. A human-looking blocker is
not retained after the required approval already exists: current post-decision
bookkeeping reports `converge-ready` and points back to `agent advance`.
Completed work reports `closed` with no remediation blocker.

Common blocker codes include:

- `MISSING_PALARI`
- `MISSING_WORK_ITEM`
- `PALARI_NOT_ASSIGNED`
- `DEPENDENCY_NOT_TERMINAL`
- `SOURCE_MISSING`
- `SOURCE_NOT_ALLOWED`
- `EXTERNAL_WRITE_REQUIRES_APPROVAL`
- `HUMAN_DECISION_REQUIRED`
- `WORK_BLOCKED`
- `WORK_CLOSED`
- `INTEGRATION_BOUNDARY`
- `REVIEW_REQUIRED`
- `REVIEWER_ROLE_MISSING`
- `REVIEWER_EXHAUSTS_APPROVERS`
- `APPROVER_ROLE_MISSING`

## Boundaries

Agents must never:

- read secrets or raw provider tokens
- read or write outside `allowed_paths`
- use sources not listed in `allowed_sources`
- ignore source readiness fields in `allowed_sources`
- perform external writes without an approved integration plan and queued
  outbox state
- create durable memory without a future approved memory contract
- treat an informal source as policy
- bypass approval, review, run-record, check-result, or permission boundaries
- run `palari approve` (for either an idea or a result) or a lower-level
  human-decision command

## Current Boundaries

Task Brief Contract v1 keeps provider actions read-only, but the local agent
runtime writes brief/assignment audit state and, when Git has a committed head, a
local Git witness for ready started work:

- `.palari/packets/PACKET-...json` stores the exact bounded task brief.
- `.palari/packets/session-contracts/SESSION-CONTRACT-...json` stores the
  deterministic provider-neutral view of task limits, obligations, permission
  binding, enforcement status, and limitations. Its identifier is derived from
  its canonical digest; repeated compilation of the same task rules produces
  identical bytes. The portable projection removes the local workspace selector
  from command guidance and replaces local workspace file/root fields with
  stable markers, while continuing to hash every other task-brief field. The
  persisted task brief and claim retain the exact selected workspace and the
  task brief's local context hash, so portability does not weaken local selector
  or authority binding.
- `.palari/claims/WORK-ID.json` stores claim schema v2, the Palari, mode, lease
  expiry, packet id,
  context hash, portable-contract path and digest, and a hashed metadata-only
  Git dirty baseline for the active local assignment. The baseline records
  path/status/stat metadata, never contents.
  Its `.baseline` companion survives assignment release/restart for the same
  task so an agent cannot reclassify its own later changes as pre-existing.
  For a committed claim-start head, `refs/palari/claims/...` and its oldest
  local reflog entry provide a separate Git-backed witness. All four views must
  agree before claim authority or `agent advance` attribution is accepted.
  For every complete Git-backed baseline, including a first claim and any
  restart or expiry recovery, Palari derives a canonical execution-authority
  digest from exact baseline workspace bytes and strict current workspace bytes
  before the lease, then repeats the comparison under the
  final workspace mutation lock and holds that lock through witness, baseline,
  packet, and claim persistence.
  It binds the acting Palari's identity, role, scope, worker, standards,
  input/memory boundaries and mode; reviewer goal linkage; work and dependency
  lifecycle authority; paths; selected-source provider/URI/external identity;
  capabilities; output contract; coordination policy; and static completion
  gates while deliberately
  excluding mutable proof records and current builder/reviewer proof context.
  An uncommitted or committed authority change or malformed workspace fails
  closed. A declared journal actor or `agent status`
  does not authorize a reset: preserve the original record and create a
  successor work item for a changed contract. `agent next` does not offer a
  saved task when this check already proves that it cannot restart. Unrelated
  read-model/journal projection may still be classified separately.
  When a first claim's current work declaration is absent from the baseline
  commit, Palari
  stores a normalized all-Palari execute/review digest catalog inside the hashed
  baseline instead of copying the workspace. The v2 Git witness's oldest reflog
  message binds the exact catalog digest. This keeps the no-extra-commit
  workflow while preventing release, expiry, another worktree, or a newly
  authorized reviewer from silently choosing a different authority origin.
  Every complete Git-backed claim uses the v2 witness and lease with a v3
  governance-projection snapshot. For every projection file, the snapshot binds
  both its session-Git digest and exact live digest at claim start and includes
  their differences in its changed-path classification. This lets a restarted
  claim retain its immutable proof base while excluding already-recorded Palari
  state from task output; a later projection change fails closed.
  An unchanged projection has an exact empty changed-path set. Legacy v1 claim
  witnesses and leases and v1/v2 projection snapshots are unsupported and are
  not upgraded in place. A historical current-only baseline without a catalog
  fails closed and requires a successor because no durable authority origin
  exists. Existing witness refs, heads, optional catalog messages, leases, and
  current projection snapshots are verified before a restart lease and again
  under the final lock before local claim persistence.
  Claims use schema v2 and require both portable-contract binding fields.
  Unsupported claim schemas fail closed and are not upgraded in place; the
  schema marker is declared local state, not authentication against a hostile
  same-user process.

Implemented:

- `palari agent next --json`
- `palari agent next --all --json`
- `palari agent next --as PALARI-ID --json`
- `palari agent brief WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent brief WORK-ID --as PALARI-ID --mode execute --session-contract --json`
- `palari agent start --next --as PALARI-ID --mode execute --json`
- `palari agent start WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent start WORK-ID --as PALARI-ID --mode execute --isolate --json`
- `palari agent release WORK-ID --as PALARI-ID --json`
- `palari agent release WORK-ID --as PALARI-ID --reason "..." --next-action "..." --json`
- `palari agent status WORK-ID --as PALARI-ID --json`
- `palari agent advance WORK-ID --as PALARI-ID --dry-run --json`
- `palari agent advance WORK-ID --as PALARI-ID --json`
- `palari git install` (IDE-agnostic pre-commit boundary enforcement)
- `palari git status`
- `palari git pre-commit`
- `palari init --host cursor` (advisory Cursor rule plus default git gate)
- `palari cursor install` (Cursor rule; git pre-commit gate on by default)
- `palari cursor status`
- compact agent-specific task discovery
- compact ready/blocked task briefs
- machine-readable task status with task-brief compliance checks
- local task-brief persistence and task-lock leases
- deterministic one-task selection and assignment through `agent start --next`
- durable, assignment-bound interrupted-work parking without completion permission
- deterministic portable session-contract compilation, inspection, persistence,
  and task-lock binding
- required create/modify/delete path rules with exact absent-path deletion
  tombstones
- unchanged pre-existing dirty-file attribution and tamper-checked Git baselines
- assignment-start commit-range verification for `agent advance`, preserved across release and
  restart so earlier out-of-boundary commits remain visible
- deterministic assignment-range planning and atomic check reconciliation
  through `agent advance`, with safe exact-check reuse, a permission stop, and
  deterministic post-decision completion
- machine-readable JSON failures for agent commands when `--json` is requested
- one canonical read-only agent status projection with completion guidance and
  review or human actions
- deterministic blocker codes
- task-brief context hash
- run-record `context_packet` and `context_hash` fields
- direct task, goal, project, source, dependency, checks, and integration status
- opaque default work identity whose value carries no execution-order meaning
- repository-shared compare-and-swap task locks across linked Git worktrees
- optional deterministic isolated branches/worktrees for concurrent sessions

Not implemented yet:

- task-brief expansion
- review/planning/repair modes
- an OS sandbox or tested session adapters beyond the separately documented
  Claude and Codex project-hook integrations
- generic live connector execution beyond the separately governed Linear
  adapter
- memory providers or vector search
- portable deletion-history proof in PCAW v1; workspace tombstones are enforced
  locally but are not exported as a new protocol guarantee

`agent status` rebuilds the task brief, reports its blockers, verifies the active
local task lock for ready briefs, carries the current `next_step_type`, and
evaluates the current workspace against the completion contract. Its check
section reports failures in required run-record, check, review, approval,
source, dependency, or external-write requirements. Light R1 work may omit
review and human approval only when it has zero required approvals, current
exact passing checks, and no allowed, planned, queued, or actual external
writes. Human-decision commands remain absent until prerequisite run records,
checks, and review are present. Commit hooks enforce the live write boundary;
`agent advance` checks the exact committed claim range and required outputs
before recording proof.
Every task declares `path_intents`; each exact normalized path is one of
`create`, `modify`, or `delete`. Create and modify require a regular file in the
expected Git change class; delete requires the exact path to be absent and the
Git observation to report deletion. That absent-path record is a local
deletion tombstone, not a missing-output exception. Unsafe, overlapping,
duplicate, symlinked, mismatched, or undeclared paths fail closed. Read paths
and output names never add write permission.
Execute-mode hooks additionally rebuild the current task brief from project
truth before granting writes, so coordinated edits to a brief and task lock
cannot expand the task limits. There is no generic public task-update command,
and `agent start` refuses to renew an active
lock when the current project would compile different permissions. After release or
expiry, a same-ID execution-contract change still cannot start: exact
baseline/current authority comparison fails before lease creation and final
claim write. A declared actor and `agent status` do not rebaseline the work;
preserve the record and create a successor task for the changed rules.
Opaque interpreters, unreviewed executables, dynamic shell expansion or
indirection, and Git witness mutations (including Git commands with global
`-C`, `--git-dir`, or `--work-tree` options) require a human hook decision.
That review applies to every shell segment even when an earlier segment has an
in-scope write target, and execution-capable command environments, `git -c`,
external diff/text-conversion options, and `rg --pre` cannot inherit a read-only
classification. Opaque or indirect commands still ask when no claim is active,
so releasing a claim cannot turn indirection into an authority bypass.
Direct writes to the workspace root, `.palari/`, or Git metadata are denied or
escalated even without an active
claim; option-encoded destinations such as `dd of=` and `--target-directory`
are inspected, and linked worktree Git/common directories are included. Those
surfaces must change through governed Palari/Git commands. Pager and filter
options that can launch helpers are not read-only Git operations. Compact or
newline-separated shell segments are tokenized identically, and ordinary
existing-directory destinations resolve the effective destination basename.
Repository overrides and ripgrep preprocessor/hostname helpers require review.
The CLI does not accept abbreviated long options at any parser nesting level,
and the hook still scans protected Palari command pairs defensively. Unquoted
pathname expansion, tree-shaped or backup-producing writes, path-qualified
trusted-command names, hook self-modification, and unclassified Palari commands
require review. The same applies to Bash `|&`, assignment-position tilde
expansion, abbreviated GNU write/Git helper options, and Git pathspec-file
imports. Destructive removal or move
targets include ancestors of workspace, runtime, Git truth, and the standard
Claude hook settings, so deleting a parent directory cannot bypass the
exact-file checks. Quoted Git pathspec magic/globs and dash-prefixed operands
after `--` remain reviewable. Agent-safe Palari mutations cannot point
`--workspace` at another workspace or silently use a different default.
Human-attributed review, decision, integration approval/cancel/enqueue/send,
Linear adoption, terminal lifecycle, work-accept, and generic packet-authority
mutation commands are denied from the supported agent shell.

Latest evidence, review, receipt, attempt, acceptance, outcome, and integration
records are ordered by timezone-normalized UTC instants. ISO offset spelling
cannot make an older pass or acceptance outrank a semantically later failure,
rejection, or revocation. Missing, malformed, timezone-free, and
equivalent-instant ordering claims fail closed; record ids never decide trust
authority.

Agent command failures are JSON when `--json` is requested. The payload uses
`ok: false`, a stable error code where possible, the message, target task and
agent when present, and next safe read commands.

Bare `agent next` returns the all-agent summary. `agent next --as PALARI-ID`
reads the current queue for one agent, puts safe-to-start candidates first,
keeps blocked or waiting visible with blocker codes, and omits closed work from
candidate lists. Waiting candidates include boundary guidance when the next
safe action is independent review, a human answer, or final approval. Those
candidates point first to `agent status`, then to the lower-level review or
decision guide. It does not
create a task lock, change state, or assign work. Candidates also include one
`status_command` field that opens the canonical `agent status` projection after
the first concrete next step.

`agent status` also provides final-report guidance and, only at a real boundary,
compact review, decision, or approval context. Review actions include focus,
run-record limits, and exact reviewer-specific commands. Human actions remain
separate under `human_action_commands` and are marked by
`human_action_boundary`; agents may present but never execute them. Eligible
agent review commands use `agent_action_commands` and an
`agent_action_boundary`. The projection is read-only and creates no review,
decision, run record, check result, task lock, or history change.

Review-mode task briefs separate `human_review_commands` from
`agent_review_commands`. The human boundary still forbids an agent from running
human-attributed review or decision commands. A distinct eligible agent may
run only the agent review command matching its brief identity. Builder
self-review, missing goal linkage, unapproved sources, and any attempt to turn
the advisory review result into a required human approval fail closed.

`agent status` is the canonical public read-only projection over the task brief,
current checks, and next-action directive. It reports task limits, stages,
ownership, blockers, missing and completed requirements, report guidance, and
exact review or human actions without adding permission or changing workspace
state. It is the only task status and recovery projection.

## Git Pre-Commit Enforcement

`palari git install` writes a pre-commit hook into `.git/hooks/pre-commit` that
checks staged files against active task-lock write boundaries. If any staged file is
outside the boundary, the commit is rejected with a message listing the
offending files and allowed paths. This provides IDE-agnostic boundary
enforcement that works in any environment — Windsurf, Cursor, Devin, terminal —
not just Claude Code.

Unlike Claude Code hooks (which intercept writes before they happen), the git
hook is reactive: it blocks the commit, not the edit. This means an agent can
write outside the boundary during a session, but the commit cannot land until
the out-of-boundary changes are reverted or the boundary is expanded by a human.

`palari git status` shows whether the hook is installed and lists active task locks
with their allowed write paths. `palari git pre-commit` is the check command the
hook calls; it can also be run manually before committing.

## Cursor Enforcement

`palari init --host cursor` installs an always-applied advisory Cursor project
rule (`.cursor/rules/palari-boundary.mdc`) and the git commit gate. Because
Cursor has no pre-write deny hook, structural enforcement is at commit time.
Pass `--no-git-hook` on `init` or `cursor install` to write only the rule; use
`--remove` to uninstall the managed rule and hook. `--strict-git` remains a
no-op alias. With no active claim, commits are allowed.
`palari cursor status` reports the rule, the git hook, and the active task locks
with their allowed write paths. See
[Cursor Integration](cursor-integration.md).

## Dogfood enforcement

On this repository, agent PRs are expected to follow
`start → edit → advance → review`. Claude/Codex adoption installs strict
session hooks so sessions with no active claim escalate before edits (Codex
maps unsupported ask decisions to deny). Use
`./scripts/dogfood_agent.sh PALARI-ID` to claim work and print
`allowed_paths.write`.

CI runs `scripts/check_dogfood.py` on pull requests. Known agent authors
(`Cursor Agent`, `Claude`) and PRs labeled `agent` / `cursor` must have
covering **passed** evidence ranges in `workspace.json`, or exact Git SHA
ranges in `.palari/dogfood/proof.json`. Floating tokens such as `@pr-head`
are rejected; bare attempts without passed evidence do not grant coverage.
Commits that only update the proof file are allowed for tip attestation.
Humans may still commit with no active claim; on labeled PRs they may add a
`skip-dogfood: <reason>` trailer. That trailer is rejected for known agent
authors.

## Historical adoption contracts

Early universal-adoption and invisible-surface completion contracts remain in
Git history. Current adoption behavior is defined by this document, the command
reference, and `palari init --host …` / host install commands.

The same local Git repository holds expiring task-lock leases under
`refs/palari/leases/`. They prevent two linked worktrees from treating the same
task as actively owned while allowing unrelated tasks to proceed. They are
local coordination records, not identity authentication or human permission.
`palari git status --work-id WORK-ID --target-ref REF` separately checks
the exact governed candidate against a current target and requires renewed
verification after any divergent merge view.
