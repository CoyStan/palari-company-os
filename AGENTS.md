# Palari Agent Contract

Palari Company OS is a local operating contract for AI agents and human
supervisors. Humans should not need to drive every CLI command manually; agents
use the CLI to stay inside company boundaries, and humans inspect blockers,
approvals, receipts, and outcomes.

For ordinary execution, select and claim the next safe item in one command:

```bash
palari agent start --next --as PALARI-ID --json
```

Work only inside the returned packet. After committing the bounded result, run
one convergence command:

```bash
palari agent advance WORK-ID --as PALARI-ID --json
```

It derives deterministic proof and stops at the next real boundary: independent
review, exact human authority, an external effect, or a concrete blocker. It
never creates the review or human decision. If work must stop before proof is
ready, preserve the interruption before releasing ownership:

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

Bare `agent next` shows the all-Palaris rollup. Use `--as PALARI-ID` when you
already know which Palari should take the next step. Candidate payloads include
`next_step_type` so you can distinguish start work, active proof checks, review
handoff, human decisions, closed work, and inspect-only states without parsing
command strings.

`agent brief` is a read-only preview. `agent start` is the operational entry
point for ready execution work: it persists the packet under `.palari/packets/`
and its deterministic portable session contract under
`.palari/packets/session-contracts/`, then writes a digest-bound local claim
under `.palari/claims/`. If the packet is blocked, `agent start` reports the
blockers and does not write a claim. Add `--session-contract` to `agent brief`
to inspect the provider-neutral contract without claiming work. The portable
contract declares boundaries; it does not install a host sandbox or grant
execution authority.

`agent start --next` uses the same deterministic eligibility and packet rules
as `agent next` plus explicit `agent start`; it does not broaden scope.
`agent release` with `--reason` and `--next-action` first records a blocked
attempt, the reason, repository
observation, and next safe action in governed state, then releases the owned
execute claim. It creates no receipt, evidence, review, decision, acceptance,
outcome, or convergence authority. It requires a writable governance journal;
on a legacy workspace, run the exact returned `history --checkpoint` command
instead of assuming earlier continuity.

After independent review, the normal human path is `palari queue
--approval-inbox --json`. A qualified human inspects the exact presentation and
may run its emitted `human-decision pack` action once. Agents may quote that
command for the supervisor; they must not execute it or combine review with
acceptance.

Use `--mode review` only when work is already waiting for review or is
receipt-ready. Review packets are read-only: they include review focus,
attempt/evidence/receipt context, and review guide commands, but they do not
record a verdict.

Follow the packet:

- continue only when `status` is `ready`
- use only `allowed_paths` and `allowed_sources`
- satisfy declared `path_intents`: create/modify targets must exist in the
  matching Git change class, while delete targets must be absent and observed
  as deleted from claim base to candidate
- respect each allowed source's data class, authority, steward, freshness, and
  redaction fields
- use `agent start`, not only `agent brief`, before doing ready execution work
- produce the declared output and receipt/evidence state
- stop for every blocker, missing source, human decision, or external write
- run `palari validate --json` before reporting work as done
- run `palari agent check WORK-ID --as PALARI-ID --mode execute --json` before claiming done
- add `--changed PATH` or `--git-diff` to `agent check` when file edits need to
  be compared against the packet write boundary
- run `palari agent finish WORK-ID --as PALARI-ID --json` for final report guidance
- run `palari agent doctor WORK-ID --as PALARI-ID --json` when you need a
  plain-language diagnosis of why work is safe, blocked, missing proof, or
  waiting on human authority
- run `palari agent loop WORK-ID --as PALARI-ID --json` when you need a compact
  read-only summary of brief, check, finish, and handoff status
- run `palari agent handoff WORK-ID --as PALARI-ID --json` when `agent next` or
  `finish` says the next step is human review or human decision
- follow concrete receipt, evidence, review, and approval guidance before
  generic inspect or validate commands when a check fails
- treat human-decision commands as unavailable until prerequisite proof, such as
  receipt, evidence, and review, is present
- in review mode, `agent finish` means you may report a review recommendation;
  it does not authorize you to record a human review or claim the original work
  item is complete
- if a review-mode packet or handoff packet includes `human_action_boundary`,
  treat the referenced review or decision commands as human-only; you may quote
  them for a supervisor but must not run them yourself
- run `palari agent release WORK-ID --as PALARI-ID --json` when abandoning or
  handing off a local claim
- add both `--reason` and `--next-action` to `agent release` when an
  interruption and its next action must remain durable

Never:

- read secrets or raw provider tokens
- write outside the packet boundary
- use sources not listed in the packet
- perform external writes without an approved integration plan
- invent durable memory or company policy
- bypass human decisions, reviews, receipts, or approval boundaries

The canonical contract is in `docs/product/agent-contract.md`. For a compact
command smoke that exercises `agent next`, `brief`, `check`, `finish`, and
`handoff`, see `docs/product/agent-loop-smoke.md`.

Claude Code users may optionally add structural enforcement with `palari
claude install`. Those hooks deny out-of-boundary file writes and block turn
completion while the working tree escapes the packet boundary; they are a
secondary host adapter, not a requirement for the provider-neutral loop. See
`docs/product/claude-code-integration.md`.

## Agent-Ready Repo Docs

Use these committed docs before rereading large parts of the repo:

- `docs/agent/repo-map.md` for file ownership and orientation.
- `docs/agent/contracts-and-invariants.md` for boundaries that must not drift.
- `docs/agent/common-workflows.md` for common implementation patterns.
- `docs/agent/verification.md` for focused and full checks.
- `docs/agent/documentation-freshness.md` for when docs need updates.

Run `palari docs check --json` after changing public commands, schema,
agent behavior, gates, integrations, examples, or documentation structure.
