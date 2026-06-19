# Acme Company OS Example

This workspace demonstrates the first Palari Company OS loop with one JSON
source file:

```text
Goals -> Palaris -> Work -> Evidence -> Review -> Human Decision -> Outcome
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
- six work items
- one open human decision
- evidence and review for one accept-ready work item
- one completed work item with a recorded outcome
- quorum and approval capability fields
- scope boundaries for changed paths and forbidden actions
- adaptive intensity signals
- stale evidence
- stale review

The queue should make the point of the redesign visible: the operator sees the
next thing that needs attention without reconciling separate ticket, branch,
evidence, review, and acceptance files by hand.
