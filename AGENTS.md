# Palari Agent Rules

Palari is a local system for bounded AI work and human supervision. Humans
should not need to drive every CLI command manually: agents use the CLI to stay
inside the task's allowed files, sources, and actions, while humans inspect
blockers, approvals, run records, check results, and final results.

For ordinary execution, select and take the next safe task in one command:

```bash
palari agent start --next --as PALARI-ID --json
```

Work only inside the returned task brief (`packet` in stored JSON and file
paths). After committing the bounded result, run one automatic finishing
command:

```bash
palari agent advance WORK-ID --as PALARI-ID --json
```

It derives deterministic check results and stops at the next real boundary:
independent review, exact human approval, an external action, or a concrete
blocker. It never creates the review result or approval. If work must stop
before check results are ready, record the interruption before releasing the
assignment:

```bash
palari agent release WORK-ID --as PALARI-ID \
  --reason "Why work stopped" --next-action "The next safe step" --json
```

Use the read-only and explicit-target commands below for inspection, recovery,
review, or when work selection must be controlled:

```bash
palari agent next --json
palari agent next --as PALARI-ID --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --session-contract --json
palari agent start WORK-ID --as PALARI-ID --mode execute --json
palari agent brief WORK-ID --as PALARI-ID --mode review --json
palari agent doctor WORK-ID --as PALARI-ID --mode execute --json
palari agent loop WORK-ID --as PALARI-ID --mode execute --json
```

Bare `agent next` shows the all-agent summary. Use `--as PALARI-ID` when you
already know which agent should take the next step. Candidate payloads include
`next_step_type` so you can distinguish task start, active checks, review
handoff, human approval, closed work, and inspect-only states without parsing
command strings.

`agent brief` is a read-only preview. `agent start` is the entry point for a
ready task: it saves the task brief under `.palari/packets/`, saves portable
session rules under `.palari/packets/session-contracts/`, and writes a
digest-bound local assignment under `.palari/claims/`. These directory names
remain stable for compatibility. If the task is blocked, `agent start` reports
the blockers and does not create an assignment. Add `--session-contract` to
`agent brief` to inspect the provider-neutral session rules without taking the
task. Those rules declare boundaries; they do not install a host sandbox or
grant permission.

`agent start --next` uses the same deterministic eligibility and task-brief
rules as `agent next` plus explicit `agent start`; it does not broaden the
allowed files, sources, or actions.
`agent release` with `--reason` and `--next-action` first records a blocked
run, the reason, repository observation, and next safe action, then releases
the assignment. It creates no run record, check results, review result,
approval, final result, or automatic-finishing permission. It requires writable
tamper-evident history; on a legacy workspace, run the exact returned
`history --checkpoint` command instead of assuming earlier continuity.

After independent review, `agent handoff` shows the current presentation and
an exact presentation-bound command. For one eligible reversible local task,
the human runs that emitted command once. Its readable form begins:

```bash
palari approve WORK-ID --as HUMAN-ID --json
```

The emitted command includes a machine-added `--presented` binding; the human
does not copy it or any other digest. A manually entered command without that
binding derives current state at invocation, so it is not a substitute for an
earlier inspected handoff. Palari revalidates current proof before approval and
local completion. The Approval Inbox and `human-decision pack` remain available
for advanced or batched decisions. Agents may quote a human command for the
supervisor; they must not execute `approve`, `human-decision`, or combine review
with approval.

Use `--mode review` only when work has current exact check results and is
waiting for independent review. Review task briefs are read-only: they include
review focus, run/check/run-record context, and review guide commands, but they
do not record a review result.

Follow the task brief:

- continue only when `status` is `ready`
- use only `allowed_paths` and `allowed_sources`
- satisfy declared `path_intents`: create/modify targets must exist in the
  matching Git change class, while delete targets must be absent and observed
  as deleted from the assignment base to the candidate
- respect each allowed source's data class, permission, steward, freshness, and
  redaction fields
- use `agent start`, not only `agent brief`, before doing ready execution work
- produce the declared output, run record, and check results
- stop for every blocker, missing source, human approval, or external write
- run `palari validate --json` before reporting work as done
- run `palari agent check WORK-ID --as PALARI-ID --mode execute --json` before claiming done
- add `--changed PATH` or `--git-diff` to `agent check` when file edits need to
  be compared against the task's write boundary
- run `palari agent finish WORK-ID --as PALARI-ID --json` for final report guidance
- run `palari agent doctor WORK-ID --as PALARI-ID --json` when you need a
  plain-language diagnosis of why work is safe, blocked, missing check results,
  or waiting on human approval
- run `palari agent loop WORK-ID --as PALARI-ID --json` when you need a compact
  read-only summary of brief, check, finish, and handoff status
- run `palari agent handoff WORK-ID --as PALARI-ID --json` when `agent next` or
  `finish` says the next step is independent review, a human answer, or final
  approval
- follow concrete run-record, check-results, review, and approval guidance before
  generic inspect or validate commands when a check fails
- treat `human-decision` commands as unavailable until prerequisite run records,
  check results, and review are present
- treat `approve` as human-only and never execute it from an agent session
- in review mode, `agent finish` means you may report a review recommendation;
  it does not authorize you to record a human review or say the original task
  is complete
- if a review task brief or handoff brief includes `human_action_boundary`,
  treat the referenced review or decision commands as human-only; you may quote
  them for a supervisor but must not run them yourself
- run `palari agent release WORK-ID --as PALARI-ID --json` when abandoning or
  handing off a local assignment
- add both `--reason` and `--next-action` to `agent release` when an
  interruption and its next action must remain durable

Never:

- read secrets or raw provider tokens
- write outside the task boundary
- use sources not listed in the task brief
- perform external writes without an approved integration plan
- invent durable memory or company policy
- bypass approvals, reviews, run records, check results, or required boundaries

The full agent rules are in `docs/product/agent-contract.md`. For a compact
command smoke that exercises `agent next`, `brief`, `check`, `finish`, and
`handoff`, see `docs/product/agent-loop-smoke.md`.

Fresh Git repositories may use `palari init --host HOST`; existing workspaces use
the same action as `palari init WORKSPACE-DIR --host HOST --as PALARI-ID`,
where `HOST` is `claude`, `codex`, or `cursor`. Claude and Codex install the
portable session rules, commit-time Git boundary, and tested session hooks
(strict no-claim behavior on adoption); Codex requires explicit `/hooks` trust.
Cursor installs an advisory project rule by default — the Git commit gate is
opt-in via `--strict-git`, `palari cursor install`, or `palari git install`.
`palari claude install` remains the Claude hook-only management surface; see
`docs/product/claude-code-integration.md` and
`docs/product/cursor-integration.md`.

## Dogfood on this repository

Agent edits to this repo should use a real claim/packet loop:

```bash
./scripts/dogfood_agent.sh PALARI-ID
# edit only allowed_paths.write, commit, then:
palari agent advance WORK-ID --as PALARI-ID --json
```

Claude/Codex host adoption installs **strict** session hooks (`no claim ⇒ ask`;
Codex maps ask to deny). Cursor remains advisory unless git gating is opted in.
CI's Agent dogfood gate checks agent-authored commits for covering **passed**
evidence ranges or exact-SHA entries in `.palari/dogfood/proof.json` (floating
`@pr-head` tokens and bare attempts do not count; proof-only commits may
attest an exact tip). Humans may use a `skip-dogfood: <reason>` trailer on
labeled PRs. Humans can still commit with no active claim.

## Code parts

Use `docs/agent/repo-tree.json` as the one ownership map. Normal code work has
one primary part: `base`, `work`, `checks`, `links`, or `views`. Edit its owned
files, use its listed doors, and run:

```bash
python3 -S scripts/check_repo_tree.py --part PART
```

If a listed door changes, also test the parts that use it. Keep one Git repo
and one Palari work list; do not add nested repos or separate ticket stores.

## Agent-Ready Repo Docs

Use these committed docs before rereading large parts of the repo:

- `docs/agent/repo-tree.json` for the checked place of every tracked file.
- `docs/agent/repo-map.md` for file ownership and orientation.
- `docs/agent/contracts-and-invariants.md` for boundaries that must not drift.
- `docs/agent/common-workflows.md` for common implementation patterns.
- `docs/agent/verification.md` for focused and full checks.
- `docs/agent/documentation-freshness.md` for when docs need updates.

Run `palari docs check --json` after changing public commands, schema, agent
behavior, required checks, integrations, examples, or documentation structure.
