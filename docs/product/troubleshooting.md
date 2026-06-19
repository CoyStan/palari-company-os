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

Completion is gated by queue integration state. Use:

```bash
./bin/palari detail WORK-ID
```

Then follow the `next` action shown by the CLI.

