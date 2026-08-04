# Acme Company OS Example

This example workspace demonstrates Palari's basic work process with one JSON source
file:

Some saved example values intentionally retain older wording so compatibility
tests can prove that current commands render legacy work clearly. New records
should follow the [plain-language guide](../../docs/product/plain-language.md).

```text
Goal -> agent -> allowed sources -> task -> run -> run record -> check results
  -> independent review when required -> human approval when required -> result
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
- two agents
- one selected local source
- seven tasks
- one human-facing run record for a low-risk local output that still needs
  current check results
- one open decision question
- check results and review for one task that is ready for approval
- one completed task with a recorded result
- required-approval and approver-capability fields
- allowed-file boundaries for changed paths and forbidden actions
- adaptive intensity signals
- stale check results
- stale review
- a task with a run record but missing exact check results, which therefore
  cannot complete

Every completion requires current exact check results. Only R1/light work with
zero required approvals and no allowed, planned, queued, or actual external
writes may omit independent review and human approval.

The queue should make the point of the redesign visible: the operator sees the
next thing that needs attention without reconciling separate task, branch,
check-results, review, and approval files by hand.
