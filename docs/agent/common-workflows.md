# Common Workflows

Use these as short recipes, not ceremony. The current task and task brief remain
the assignment boundary. Exact stored names appear in backticks when needed.

## Operate Ordinary Bounded Work

1. Initialize once with `palari init`, add bounded work with `palari work add`,
   then let the assigned agent run `palari agent start --next --as PALARI-ID
   --json`.
2. Work only inside the returned task brief, commit the bounded result, and run
   `palari agent advance WORK-ID --as PALARI-ID --json`.
3. Stop at the returned independent-review, human, external, or blocker
   boundary. A distinct review-only agent may record the advisory review after
   starting and inspecting its exact `--mode review` brief. Review remains a
   separate attributable act.
4. The human handoff shows the current presentation and one exact
   presentation-bound command. For one eligible local task, a qualified human
   runs that emitted `palari approve ... --presented DIGEST` command once; the
   digest is machine-supplied and is not copied. A manually typed bare
`approve` derives current state at invocation. The Approval Inbox remains
the advanced/batched path.

## Change One Code Part

1. Find the part in `docs/agent/repo-tree.json` and edit only its owned files by
   default.
2. Use its listed doors when another part needs it.
3. Run `python3 -S scripts/check_repo_tree.py --part PART` while working.
4. If a door changed, also test the parts that use it. Run the complete check
   before the final candidate when the task requires it.

There is one Git repo and one Palari work list. A part is a small work area,
not a nested repo or a separate ticket store.

Use `work add --write PATH` when only final presence matters. Use
repeatable `--create`, `--modify`, and `--delete` instead when the exact final
mutation class matters; do not mix exact intents with `--write`.

To let an agent grow a goal without granting itself work, use `palari work add
TITLE --idea` with the same file, project, dependency, check, and approval
options. Stop after the emitted human step. A human may run `palari approve
IDEA-ID --as HUMAN-ID --json`; the new task then enters the normal bounded-work
flow.

If execution is interrupted before the check results are ready, run `palari agent release
WORK-ID --as PALARI-ID --reason "..." --next-action "..." --json`. Durable release
records blocked status and the next action before releasing the task lock. It
does not create a run record or check results, and it grants no permission. It
requires writable tamper-evident history; a legacy workspace must first run the
exact returned `history --checkpoint`
action. Use `next`, `brief`, explicit `start`, `check`,
`finish`, `handoff`, `doctor`, and `loop` as optional inspection and recovery
surfaces rather than mandatory ceremony.

`agent brief` includes an authority plan. Do not start or review work when it
reports that the proposed reviewer would exhaust the qualified final approvers.
Use its smallest safe correction; do not manufacture extra identities for one
person.

## Add Or Change A CLI Command

1. Update `src/palari_company_os/cli_parser.py`.
2. Route behavior in `src/palari_company_os/cli_dispatch.py`.
3. Add or update text/JSON output in `src/palari_company_os/cli_output.py`.
4. Add focused tests for JSON shape and useful text output.
5. Update `docs/product/command-reference.md`.
6. Run focused tests and the normal verification stack.

## Change Stored Data Or Validation

1. Update `src/palari_company_os/models.py` and validation code.
2. Update `schemas/workspace.schema.json` when the JSON contract changes.
3. Update examples or fixtures only when needed.
4. Update `docs/product/schema-and-validation.md` and
   `docs/product/core-objects.md`.
5. Add tests for valid and fail-closed cases.

## Change Agent Behavior

1. Keep task briefs compact and deterministic.
2. Add explicit blockers and next safe commands.
3. Avoid dumping full workspace records or docs into task briefs.
4. Update `docs/product/agent-contract.md` and agent docs.
5. Add tests for ready and blocked states.

## Change Source, Run Record, Or Integration Behavior

1. Preserve source boundaries and no-raw-secret rules.
2. Keep run records human-facing.
3. Keep generic integrations dry-run; any live adapter must preserve the
   explicit plan, approval, outbox, and send boundaries.
4. Update relevant product docs and tests.

## Change Public Docs Or README

1. Keep claims aligned with implemented behavior.
2. Avoid overclaiming maturity.
3. Keep links local and current.
4. Run `palari docs check --json` once docs checks exist.
