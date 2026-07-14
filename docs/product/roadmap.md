# Roadmap And Known Gaps

## North Star: Proof-Carrying AI Work

Palari's direction is a small, open, provider-neutral governance kernel: given
one PCAW statement and its named outputs, an independent implementation can
determine offline whether the work stayed bounded, evidence is current, review
is independent, human quorum is current, and acceptance still applies.

Implemented in the v0.2 local foundation:

- strict workspace schema, canonical path boundaries, agent packets, claims,
  receipts, evidence, exact review binding, human decisions, and acceptance;
- a pure deterministic governance evaluator shared by workspace validation,
  completion gating, proof export, and proof verification;
- PCAW v1 canonical statements, schemas, stable diagnostics, valid and invalid
  vectors, and a dependency-free black-box conformance runner;
- safe artifact verification with traversal, sibling-prefix, symlink, missing,
  changed-during-read, and digest-mismatch rejection;
- a staged hash-chained governance journal with explicit checkpoints, replay,
  continuity breaks, prepared/committed transactions, fsync, and crash recovery;
- focused, affected, complete, install, documentation, conformance, and
  network-free demonstration checks.

Deferred honestly:

- DSSE signatures, key custody, revocation, and cryptographically protected
  human identity;
- a second verifier implementation (portability is currently tested through
  the normative corpus);
- hosted multi-user service, background agent runner, and broker execution;
- live Slack, GitHub, Jira, email, Drive, or document connector execution;
- autonomous acceptance, merge, push, deployment, or external-write authority.

The next protocol work should be earned by conformance evidence: stabilize v1
through independent implementations, measure the verifier trusted-code base,
and design signatures only together with identity, revocation, and custody.
