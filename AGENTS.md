# Palari Agent Contract

Palari Company OS is a local operating contract for AI agents and human
supervisors. Humans should not need to drive every CLI command manually; agents
use the CLI to stay inside company boundaries, and humans inspect blockers,
approvals, receipts, and outcomes.

Before changing files, either ask for the next safe work item or run a packet
command for a known work item:

```bash
palari agent next --json
palari agent next --as PALARI-ID --json
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
palari agent brief WORK-ID --as PALARI-ID --mode review --json
```

Bare `agent next` shows the all-Palaris rollup. Use `--as PALARI-ID` when you
already know which Palari should take the next step. Candidate payloads include
`next_step_type` so you can distinguish start work, active proof checks, review
handoff, human decisions, closed work, and inspect-only states without parsing
command strings.

In v1, `palari agent start` is a read-only alias for `agent brief`. It does not
claim work yet.

Use `--mode review` only when work is already waiting for review or is
receipt-ready. Review packets are read-only: they include review focus,
attempt/evidence/receipt context, and review guide commands, but they do not
record a verdict.

Follow the packet:

- continue only when `status` is `ready`
- use only `allowed_paths` and `allowed_sources`
- respect each allowed source's data class, authority, steward, freshness, and
  redaction fields
- produce the declared output and receipt/evidence state
- stop for every blocker, missing source, human decision, or external write
- run `palari validate --json` before reporting work as done
- run `palari agent check WORK-ID --as PALARI-ID --mode execute --json` before claiming done
- run `palari agent finish WORK-ID --as PALARI-ID --json` for final report guidance
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
