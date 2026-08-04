# Documentation Freshness

Documentation should stay close to behavior without turning every small refactor
into a process ritual.

## Update Docs When Work Changes

- public CLI commands or JSON output
- workspace schema, validation, or collection semantics
- agent task-brief, start, check, finish, handoff, doctor, or loop behavior
- source, run-record, check-result, review, or approval semantics
- integration plan, approval, outbox, or external-write boundaries
- required-check profile recommendations
- examples, quickstarts, installation, or verification commands
- public README or example claims
- PCAW schemas, diagnostics, conformance vectors, verifier TCB, or tamper-evident
  history semantics

## Usually No Docs Update Needed

- tiny internal refactors
- private helper renames
- test-only fixture cleanup
- formatting-only changes

## Canonical Destinations

- Command behavior: `docs/product/command-reference.md`
- Agent behavior: `docs/product/agent-contract.md`
- Schema/model behavior: `docs/product/schema-and-validation.md` and
  `docs/product/core-objects.md`
- Required checks and approval: `docs/product/authority-and-gates.md`
- Verification: `docs/agent/verification.md` and `docs/product/testing-guide.md`
- Repo orientation: `docs/agent/repo-map.md`
- PCAW protocol: `spec/pcaw/v1/README.md` and its schemas/vectors

When unsure, prefer a short truthful doc update over leaving future agents to
rediscover the behavior from code.
