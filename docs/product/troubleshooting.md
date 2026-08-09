# Troubleshooting

Error text and commands below use exact machine terms. The explanations use
the plain operator vocabulary: task, run, run record, checks, review, approval,
and result.

## `workspace schema_version is missing` or `older than supported`

Palari accepts only workspace schema v2. Unversioned, v0, and v1 workspaces
stop safely, and Palari has no in-place migration command. Restore a current
backup or convert the data outside Palari. Then validate the complete v2
workspace before ordinary use:

```bash
./bin/palari --workspace /path/to/workspace validate
```

## `references missing id`

One stored record points to another record that does not exist. Run:

```bash
./bin/palari validate
```

Then inspect the field named in the error.

## `evidence is stale`

The check results (`evidence`) are for an older commit than the latest run
(`attempt`). Run the required checks again for the current run version before
review or approval.

## `review is stale`

The latest review is for older check results. Record a new independent review
for the current exact version before human approval or completion.

If the message names `attempt_hash`, `evidence_manifest_hash`, `receipt_hash`,
or `work_contract_hash`, the review no longer matches the current run, checks,
run record, or task rules. Refresh the run record and checks as needed, then
record a new review. Reviews tied to an exact version are immutable.

## `evidence manifest verification failed`

Rerun the supported reconciler for the task:

```bash
palari agent advance WORK-ID --as PALARI-ID --refresh-verification --json
```

Palari stops when the manifest is missing, the exact run record is missing or
mismatched, an output changed, an output path is unsafe, or the run record no
longer matches its hash. `agent advance` regenerates the coupled run record and
check results for the current run version when that is safe.

## `Git baseline ...` or unexpected file-boundary failure

Restart the task lock (`claim`) when its hashed starting state is malformed or
belongs to another repository. `agent start` records the path, status, and stat
information for files that were already dirty without reading their contents.
`agent check --git-diff` lists unchanged entries as
`preexisting_unchanged_files`. Any path or metadata change after start belongs
to the current task and must fit its write boundary.

The starting state remains after `agent release` and a later `agent start` for
the same task. If a task is deliberately moved to another repository root, a
person must inspect the old dirty state before removing the local `.baseline`
companion and starting a new task lock.

Path traversal, non-canonical paths, a symlink escape, malformed Git output, or
an incomplete observation always stops safely.

## `agent next` shows no ready work with `AUTHORITY_PLAN_UNSATISFIABLE`

Every visible task is blocked because the workspace has no reviewer distinct
from both the builder and the final human approver. A one-agent workspace hits
this: the single agent is the builder, so it cannot independently review its own
work, which would force the only qualified human to be the reviewer and leave no
one to approve.

`palari agent next` prints the smallest safe correction and a ready-to-run
`fix:` command that adds a review-only agent linked to the task goal:

```bash
palari agent next --as PALARI-ID
```

Run the printed `fix:` command (a `palari reviewer add ...` that adds an
independent review-only agent), then re-run `agent next`. `palari init` seeds
this review-only agent for new workspaces, so a freshly initialized workspace
does not hit this.

**Solo-maintainer guarantee:** after a normal `palari init`, the first R2 task
added for the seeded builder has a viable authority plan (builder +
`PALARI-REVIEWER` + `HUMAN-FOUNDER`). Product commands can carry that task
through advance, independent review, and one founder approval without hitting
`AUTHORITY_PLAN_UNSATISFIABLE`. See `palari demo --journey --no-pause`.

## `lacks required approval capability`

The person named by the human-decision command does not have the task's
`required_approval_capability`. Use a qualified person; do not widen the profile
to bypass the check.

## `cannot be completed`

Completion always needs current, exact, passing check results for the final
run, run record, commit, and outputs. Only R1/light work with zero required
approvals, completed dependencies, no open linked questions, and no allowed,
planned, queued, or actual external write may omit independent review and human
approval. Every other task needs both a current exact review and the required
human approvals.

After committing work within the task limits, use `agent advance` as the normal
run-to-checks path. For a diagnosis, use:

```bash
./bin/palari detail WORK-ID
```

Then follow the `next` action shown by the CLI.

## `workspace write is already in progress`

Palari protects `workspace.json` writes with a small lock file under
`.palari/locks/`. Normal commands remove the lock as soon as the write finishes.

If a process dies during a write, Palari reclaims the stale lock when its
recorded `pid=` no longer runs or the lock file is older than 30 seconds. A
fresh lock owned by a live process still stops with:

```text
workspace write is already in progress; retry shortly
```

If the message persists and you have confirmed that no Palari write command is
running, remove the stale lock manually:

```bash
rm .palari/locks/*.lock
```

Then rerun the original command.
