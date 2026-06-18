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
```

The example includes:

- two goals
- two humans
- two Palaris
- four work items
- one open human decision
- evidence and review for one accept-ready work item
- one completed work item with a recorded outcome

The queue should make the point of the redesign visible: the operator sees the
next thing that needs attention without reconciling separate ticket, branch,
evidence, review, and acceptance files by hand.

