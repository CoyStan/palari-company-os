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

## `lacks required approval capability`

The human decision is being recorded by a human profile that does not have the
work item's `required_approval_capability`.

## `cannot be completed`

Completion is gated by the work's safety state. High-risk or approval-required
work must reach the normal `ready` state with evidence, review, and approvals.
Light local work may complete from `receipt-ready` only when it has no required
approval, no unfinished dependencies, no open linked decisions, and no actual,
planned, or queued external writes. Use:

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
