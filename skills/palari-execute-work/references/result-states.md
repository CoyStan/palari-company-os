# Result states

Use this reference only when a `start`, `status`, `advance`, or `release`
response needs interpretation. Prefer explicit machine fields over prose.

| Signal | Meaning | Execution-agent action |
| --- | --- | --- |
| `status: ready` | The current task brief permits bounded work. | Work only inside the declared limits. |
| `agent_may_execute: true` with an agent-owned exact command | Palari exposes a safe mechanical next step. | Run that exact command if it is not forbidden by the task brief. |
| `review_boundary: true` or reviewer ownership | Independent judgment is required. | Stop execution and hand off the exact current review action. |
| `human_boundary: true` or human ownership | Human authority is required. | Stop and show the human what Palari requests. Never execute the command. |
| A blocker with no agent-owned action | The task cannot safely progress. | Explain the blocker and stop. Release first if the assignment is still held and proof is not ready. |
| Closed or complete work | No task action remains. | Report the exact committed result and recorded verification state. |

Apply these rules in order:

1. Honor `human_action_boundary` and `human_action_commands` as human-only.
2. Honor `agent_action_boundary` and `agent_action_commands` only when the
   named owner is the current execution agent.
3. Prefer `next_allowed_commands` and `next_action.command` over commands
   reconstructed from messages or memory.
4. Treat missing, contradictory, or stale ownership information as a stop,
   never as permission.
5. Use `palari agent status WORK-ID --as PALARI-ID --mode execute --json` for a
   fresh canonical view when the previous response is ambiguous.

The skill does not define Palari's state machine. The current CLI response and
saved task brief remain authoritative.
