# Agent Contract

Palari Company OS is primarily an operating contract for AI agents. Humans use
the dashboard, receipts, blockers, and approval records to supervise work.
Agents use the CLI to discover one bounded task, receive context, act inside
scope, and stop when human authority is required.

## Canonical Loop

Agent work should start with one packet command:

```bash
palari agent next --as PALARI-ID --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
palari agent start WORK-ID --as PALARI-ID --mode execute --json
palari agent brief WORK-ID --as PALARI-ID --mode review --json
```

`palari agent brief` is a read-only preview. `palari agent start` is the
operational entry point for ready execution work: it persists the exact packet
the agent received and records a local lease claim. Blocked packets remain
read-only and are not claimed.

The v1 loop is:

1. Run `palari agent next --as PALARI-ID --json` to discover safe candidates.
2. Run `palari agent brief WORK-ID --as PALARI-ID --mode execute --json` to preview scope.
3. Run `palari agent start WORK-ID --as PALARI-ID --mode execute --json` to persist the packet and claim the work.
4. Continue only if the packet returns `status: ready`.
5. Read and write only the packet's allowed paths and sources.
6. Stop if the packet is blocked or a stop condition is reached.
7. Run `palari gate recommend WORK-ID --json` when the work crosses source,
   prompt-authority, external-write, human-approval, deploy/runtime,
   multimodal/privacy, or product-claim boundaries.
8. Produce the required output and trust records.
9. Run `palari agent check WORK-ID --as PALARI-ID --mode execute --changed PATH --json`
   or `--git-diff` to compare observed edits with the packet boundary.
10. Run `palari agent check WORK-ID --as PALARI-ID --mode execute --json` for the normal proof-state check.
11. Run `palari agent finish WORK-ID --as PALARI-ID --json`.
12. If the result is a human review or decision handoff, run
   `palari agent handoff WORK-ID --as PALARI-ID --json`.
13. Run `palari agent doctor WORK-ID --as PALARI-ID --json` when you need a
    plain-language diagnosis of the current safety state.
14. Run `palari agent loop WORK-ID --as PALARI-ID --json` when you need a
    compact summary of the current brief/check/finish/handoff state.
15. For R1/light/0-approval work items only, `palari agent done WORK-ID --as
    PALARI-ID --json` auto-records proof, runs check/finish, closes out, and
    completes the work item in one step. It requires a clean worktree and
    attributes the complete committed range from the persisted claim-start
    head through current `HEAD`; a commit made before the claim does not count.
    For R2+ work, use the full lifecycle above.
16. Run `palari validate --json`.
17. Run `palari agent release WORK-ID --as PALARI-ID --json` if abandoning or
    handing off the local claim before completion.
18. Report the packet status, finish guidance, changed files, checks, gates, and blockers.

For independent inspection work, use `--mode review` only after a work item is
already in `needs-review` or `receipt-ready`. A review packet is read-only. It
includes the review guide focus, attempt, evidence, receipt, suggested verdicts,
and reviewer candidates, but it does not record a review verdict or mutate the
workspace.
`palari agent next --as PALARI-ID --mode review --json` ranks those reviewable
items as ready while keeping non-reviewable work blocked.

## Packet Purpose

The packet is a compact context compiler. It prevents agents from inferring a
workflow from many separate commands. A packet answers:

- who the agent is
- which work item is in scope
- why the work matters
- which paths, sources, and actions are allowed
- source readiness metadata such as data class, authority, steward, freshness,
  and redaction requirement
- which actions are forbidden
- what output is required
- what receipt, evidence, review, human decision, or integration state matters
- when the agent must stop
- which commands are safe to run next

The packet must not dump the whole workspace. It includes only directly related
records and explicit omitted-context notes.

## Documentation Hints

Agent packets include compact repo-documentation context:

- `documentation_state` says whether agent-ready repo docs are present,
  partial, or missing.
- `recommended_docs` points to committed docs likely to help with the selected
  work item.
- `omitted_context` states that full documentation text was not loaded into the
  packet.

This keeps packets context-window-safe. Agents should read recommended docs only
when they need that orientation. Missing docs are low context, not a work
blocker; use `palari docs init --dry-run --json` to inspect the proposed starter
set.

## Gate Recommendations

`palari gate recommend WORK-ID --json` is a read-only companion to packets and
review guides. It does not review work and does not grant acceptance authority.
It chooses the review contracts likely to matter for the selected work item:

- prompt authority
- source boundary
- external writes
- human approval
- deploy/runtime
- privacy/multimodal
- product overclaim

Each recommended gate includes a reviewer role, what to inspect, blocker
checklist, required evidence, and accept-ready standard. Simple low-risk work can
return `no_special_gate_required: true`; that means use the normal
receipt/evidence/review loop, not that review is waived where the work item
requires it.

## Packet Status

`status: ready` means the agent may proceed inside the packet boundary.

`status: blocked` means the agent must not perform the work. It may run only the
commands listed in `next_allowed_commands`, or report the blockers to a human.

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
- `RECEIPT_READY_REVIEW`

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
- bypass human decisions, review, receipts, evidence, or approval boundaries

## V1 Scope

Agent Packet Contract v1 keeps provider actions read-only, but the local agent
runtime writes packet/claim audit state and, when Git has a committed head, a
local Git witness for ready started work:

- `.palari/packets/PACKET-...json` stores the exact bounded packet.
- `.palari/claims/WORK-ID.json` stores the Palari, mode, lease expiry, packet id,
  context hash, and a hashed metadata-only Git dirty baseline for the active
  local claim. The baseline records path/status/stat metadata, never contents.
  Its `.baseline` companion survives claim release/restart for the same work
  item so an agent cannot reclassify its own later changes as pre-existing.
  For a committed claim-start head, `refs/palari/claims/...` and its oldest
  local reflog entry provide a separate Git-backed witness. All four views must
  agree before claim authority or `agent done` attribution is accepted.

Implemented:

- `palari agent next --json`
- `palari agent next --all --json`
- `palari agent next --as PALARI-ID --json`
- `palari agent brief WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent start WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent check WORK-ID --as PALARI-ID --mode execute --json`
- `palari agent check WORK-ID --as PALARI-ID --mode execute --changed PATH --json`
- `palari agent check WORK-ID --as PALARI-ID --mode execute --git-diff --json`
- `palari agent release WORK-ID --as PALARI-ID --json`
- `palari agent finish WORK-ID --as PALARI-ID --json`
- `palari agent handoff WORK-ID --as PALARI-ID --json`
- `palari agent doctor WORK-ID --as PALARI-ID --json`
- `palari agent done WORK-ID --as PALARI-ID --json` (R1/light/0-approval only)
- `palari agent loop WORK-ID --as PALARI-ID --json`
- `palari git install` (IDE-agnostic pre-commit boundary enforcement)
- `palari git status`
- `palari git pre-commit`
- compact Palari-specific work candidate discovery
- compact ready/blocked packets
- machine-readable packet compliance checks
- local packet persistence and local claim leases
- optional changed-file boundary checks
- unchanged pre-existing dirty-file attribution and tamper-checked Git baselines
- claim-start commit-range proof for `agent done`, preserved across release and
  restart so earlier out-of-boundary commits remain visible
- machine-readable JSON failures for agent commands when `--json` is requested
- read-only completion report guidance
- read-only human handoff packets
- plain-language read-only agent safety diagnoses
- compact read-only agent loop summaries
- deterministic blocker codes
- packet context hash
- receipt `context_packet` and `context_hash` fields
- direct work, goal, workbench, source, dependency, proof, and integration state

Not implemented yet:

- packet expansion
- review/planning/repair modes
- live connector execution
- memory providers or vector search

`agent check` rebuilds the packet, reports packet blockers, verifies the active
local claim for ready packets, carries the current
`next_step_type`, and then evaluates the current workspace against the
completion contract. It returns `ok: false` when required receipt, evidence,
review, human decision, source, dependency, or external-write checks fail. Light
low-risk work may satisfy its trust loop with a valid receipt without requiring
review or human approval. Missing receipt, evidence, and review checks include
the next safe command Palari can infer for the current work item. Human-decision
record commands are held back until prerequisite proof, such as receipt,
evidence, and review, is present, so agents do not jump from missing review
straight to approval. When a blocked packet is already waiting on review,
`agent check` points to `agent handoff` before lower-level inspect commands.

When `--changed PATH` or `--git-diff` is supplied, `agent check` also compares
observed file changes against the packet's writable paths and required outputs.
It reports changed files inside and outside the write boundary, missing file
outputs, and changed files not represented by the current attempt/receipt
records. For claims started in Git, unchanged dirty paths captured at start are
listed separately and not attributed to the agent; a changed fingerprint is
attributed normally. This is intentionally content-blind: Palari compares Git
status and file metadata, rejects traversal/symlink escape and incomplete
observations, and never treats the baseline as cryptographic provenance.
Execute-mode hooks additionally rebuild the current packet from workspace truth
before granting writes, so coordinated edits to a packet and claim cannot
expand scope. A generic `work update` cannot mutate a work item while any local
claim is active, and `agent start` refuses to renew an active claim when the
current workspace would compile different packet authority. Scope changes must
therefore cross a release and authorized handoff into a new claim epoch.
Opaque interpreters, unreviewed executables, dynamic shell expansion or
indirection, and Git witness mutations (including Git commands with global
`-C`, `--git-dir`, or `--work-tree` options) require a human hook decision.
That review applies to every shell segment even when an earlier segment has an
in-scope write target, and execution-capable command environments, `git -c`,
external diff/text-conversion options, and `rg --pre` cannot inherit a read-only
classification. Opaque or indirect commands still ask when no claim is active,
so releasing a claim cannot turn indirection into an authority bypass.
Direct writes to the workspace root, declared split collection files,
`.palari/`, or Git metadata are denied or escalated even without an active
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

Latest evidence, review, receipt, attempt, outcome, and integration records are
ordered by timezone-normalized UTC instants with stable id tie-breaking. ISO
offset spelling cannot make an older pass or acceptance outrank a semantically
later failure or rejection.

Agent command failures are JSON when `--json` is requested. The payload uses
`ok: false`, a stable error code where possible, the message, target work item
and Palari when present, and next safe read commands.

Bare `agent next` returns the all-Palaris rollup. `agent next --as PALARI-ID`
reads the current queue for one Palari, puts safe-to-start candidates first,
keeps blocked or waiting visible with blocker codes, and omits closed work from
candidate lists. Waiting candidates include `handoff_guidance` when the next
safe action is a human review or decision. Those candidates point first to
`agent handoff`, then to the lower-level review or decision guide. It does not
create a claim, mutate state, or assign work. Candidates also include
`loop_command` so an agent can open the compact loop summary after seeing the
first concrete next step.

`agent finish` wraps `agent check` into final-report guidance. It never mutates
workspace state in v1. It carries the same `next_step_type`, distinguishes
missing proof from handoff-ready work, such as low-risk receipt-ready results
that should stop execution and move to a human review path. Its
`next_allowed_commands` prioritize missing proof or approval record templates
before generic inspect/validate commands. For receipt-ready review handoffs and
work that already has evidence but still needs review, `agent handoff` is
listed before the direct review guide command. Approval commands appear only
after the earlier proof required for approval is present. In review mode,
`agent finish` means the agent may report a review recommendation; it does not
mean the agent may record a human review or claim the original work item is
complete.

When the next step is a human handoff, `agent finish` also returns
`handoff_guidance`. Review handoffs point to `review guide`, which includes
review focus, receipt limits, and ready-to-edit review record commands.
Decision handoffs point to `decision guide`, which includes suggested decision
update commands. The agent still does not record those human actions itself.

`agent handoff` compiles the final handoff packet for that moment. It wraps the
`agent finish` result and includes compact `review guide` or `decision guide`
context when applicable. Text handoff output surfaces the same review focus and
receipt claims so a human can inspect the right thing without parsing JSON
first. Agent-safe read commands remain separate from `human_action_commands`, so
a model can show the right review or decision commands without pretending it is
authorized to perform them. It is read-only in v1 and does not create reviews,
decisions, receipts, evidence, claims, or history events. Handoff packets also
include `human_action_boundary`, which marks every `human_action_commands`
entry as human-only.

Review-mode `agent brief` packets may include ready-to-copy review record
commands inside `review_context` because those are useful to the supervising
human. They also include `human_action_boundary`, which states that the agent
may quote or summarize those commands but must not execute them, claim to be the
reviewer, or convert a recommendation into human acceptance.

`agent loop` is a compact read-only control surface over the same commands. It
summarizes `brief`, `check`, `finish`, and handoff status, includes the exact
stage commands, and omits detailed payloads so agents can orient quickly without
receiving the whole workspace.

`agent doctor` is a plain-language read-only diagnosis over the same loop. It
answers whether the work is agent-safe, missing proof, blocked, or waiting for a
human handoff, and lists the next recommended commands without adding authority
or mutating workspace state.

## Git Pre-Commit Enforcement

`palari git install` writes a pre-commit hook into `.git/hooks/pre-commit` that
checks staged files against active claim write boundaries. If any staged file is
outside the boundary, the commit is rejected with a message listing the
offending files and allowed paths. This provides IDE-agnostic boundary
enforcement that works in any environment — Windsurf, Cursor, Devin, terminal —
not just Claude Code.

Unlike Claude Code hooks (which intercept writes before they happen), the git
hook is reactive: it blocks the commit, not the edit. This means an agent can
write outside the boundary during a session, but the commit cannot land until
the out-of-boundary changes are reverted or the boundary is expanded by a human.

`palari git status` shows whether the hook is installed and lists active claims
with their allowed write paths. `palari git pre-commit` is the check command the
hook calls; it can also be run manually before committing.
