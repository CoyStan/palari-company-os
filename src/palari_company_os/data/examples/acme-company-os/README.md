# Acme Company OS Example

This workspace demonstrates the first Palari Company OS loop with one JSON
source file:

```text
Goals -> Palaris -> Sources -> Work -> Attempt -> Receipt -> Evidence/Review -> Outcome
```

Run:

```bash
../../bin/palari --workspace . queue
../../bin/palari --workspace . detail WORK-0001
../../bin/palari --workspace . validate
../../bin/palari --workspace . state
../../bin/palari --workspace . scope WORK-0001 --changed examples/acme-company-os/workspace.json
```

The example includes:

- two goals
- two humans
- two Palaris
- one selected local source
- seven work items
- one human-facing receipt for a low-risk local output
- one open human decision
- evidence and review for one accept-ready work item
- one completed work item with a recorded outcome
- quorum and approval capability fields
- scope boundaries for changed paths and forbidden actions
- adaptive intensity signals
- stale evidence
- stale review
- a receipt-ready item that can be reviewed, undone, or continued without
  pretending it has gone through full governance ceremony

The queue should make the point of the redesign visible: the operator sees the
next thing that needs attention without reconciling separate ticket, branch,
evidence, review, and acceptance files by hand.
