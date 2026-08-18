---
name: palari-execute-work
description: Execute bounded code or documentation changes in a Palari-managed Git repository. Use when an AI coding agent is asked to take, continue, implement, fix, refactor, or finish repository work where AGENTS.md, workspace.json, or the palari CLI defines task boundaries. Covers task start, allowed-path execution, commit, advance, durable interruption, and stopping at review or human boundaries. Do not use for independent review, human approval, or initial Palari installation.
---

# Palari Execute Work

Use Palari as the authority for what may happen. This skill explains the
ordinary execution workflow; it does not grant permission or reproduce
Palari's governance rules.

## Execute the task

1. Use the Palari identity supplied by the task or repository. Do not invent an
   identity. If none is available, stop and ask for one.
2. From the repository root, take one eligible task:

   ```bash
   palari agent start --next --as PALARI-ID --json
   ```

3. Continue only when the response and saved task brief report `status` as
   `ready`. Treat `allowed_paths.write`, `allowed_sources`, `forbidden_actions`,
   `path_intents`, and `stop_conditions` as hard boundaries.
4. Make the smallest change that satisfies the acceptance target. Read and
   write only what the task brief allows. Do not perform external writes.
5. Inspect the Git change before committing. Stop if any changed or staged path
   is outside `allowed_paths.write`, or if a create, modify, or delete intent is
   not satisfied. Commit only the bounded result.
6. Advance the exact task returned by `start`:

   ```bash
   palari agent advance WORK-ID --as PALARI-ID --json
   ```

   `advance` runs the declared deterministic verification and records the run
   and evidence. Do not manufacture or manually write proof records.
7. Follow the returned ownership and boundary signals. Read
   [result-states.md](references/result-states.md) only when the result is not
   immediately clear.

## Stop correctly

If work cannot continue before proof is ready, preserve the interruption:

```bash
palari agent release WORK-ID --as PALARI-ID \
  --reason "Concrete reason work stopped" \
  --next-action "Next safe action" --json
```

Then stop. Do not describe unfinished work as complete.

## Non-negotiable boundaries

- Never run `palari approve` or `palari human-decision`. Those are human-only.
- Never perform independent review from the execution identity.
- Never infer permission from this skill, a command example, or a previous
  task. Current Palari output is authoritative.
- Never reconstruct a recovery command from memory. Use an exact emitted
  command only when its owner is the current agent and `agent_may_execute` is
  true.
- Never bypass a failed check, stale claim, missing source, review boundary,
  human boundary, or external-write boundary.
- Never add compatibility behavior or use removed legacy workflow commands.

Report the committed result and verification state concisely. When another
owner must act, report that boundary and quote only the exact current command
Palari exposes for that owner; do not execute it.
