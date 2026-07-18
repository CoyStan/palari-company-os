# Troubleshooting

## `workspace schema_version is missing`

The workspace is from an older unversioned format. Preview the migration:

```bash
./bin/palari --workspace /path/to/workspace migrate
```

Write it:

```bash
./bin/palari --workspace /path/to/workspace migrate --write
```

## `references missing id`

One record points to another record that does not exist. Run:

```bash
./bin/palari validate
```

Then inspect the field named in the error.

## `evidence is stale`

The latest attempt commit does not match the evidence head. Record fresh
evidence for the current attempt head before review or acceptance.

## `review is stale`

The latest review does not match the latest evidence head. Record a fresh
review before human decision or completion.

If the diagnostic names `attempt_hash`, `evidence_manifest_hash`,
`receipt_hash`, or `work_contract_hash`, the exact-bound review no longer
matches current proof. Refresh the receipt/evidence as needed and record a new
review; exact-bound reviews are immutable.

## `evidence manifest verification failed`

Run `palari evidence verify EVIDENCE-ID --json`. A missing manifest, missing or
mismatched exact receipt, changed artifact, unsafe artifact path, or receipt
whose contents no longer match its hash fails closed. Record a fresh receipt
first, then fresh evidence for the current attempt head.

## `Git baseline ...` or unexpected file-boundary failure

Restart the claim if its hashed baseline is malformed or belongs to another
repository. `agent start` captures already-dirty path/status/stat metadata
without reading contents. `agent check --git-diff` lists unchanged entries as
`preexisting_unchanged_files`; any path or metadata change after start is
attributed to the claim and checked against its write boundary.

The baseline persists across `agent release` and a later `agent start` for the
same work item. If a work item is deliberately moved to a different repository
root, a human operator must inspect the old dirt before removing the local
`.baseline` companion and starting a new claim.

Traversal, non-canonical paths, symlink escape, malformed Git output, or an
incomplete observation always fail closed.

## `lacks required approval capability`

The human decision is being recorded by a human profile that does not have the
work item's `required_approval_capability`.

## `cannot be completed`

Completion always requires current exact passing evidence for the terminal
attempt, receipt, head, and output artifacts. Only R1/light work with zero
required approvals, terminal dependencies, no open linked decisions, and no
allowed, planned, queued, or actual external writes may omit independent review
and human acceptance. Every other item must also have a current exact review
and the required human authority. After committing bounded work, use `agent
advance` as the sole execution-to-proof path. For diagnosis, use:

```bash
./bin/palari detail WORK-ID
```

Then follow the `next` action shown by the CLI.

## `workspace write is already in progress`

Palari protects `workspace.json` writes with a small lock file under
`.palari/locks/`. Normal commands remove that lock as soon as the write finishes.

If a process is killed during the write, Palari now reclaims a stale lock when
the recorded `pid=` is no longer running or the lock file is older than 30
seconds. A fresh lock owned by a live process still fails closed with:

```text
workspace write is already in progress; retry shortly
```

If that message persists and you have confirmed no Palari write command is still
running, remove the stale lock manually:

```bash
rm .palari/locks/*.lock
```

Then rerun the original command.
