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
- deterministic Approval Inbox manifests with exact item proof, dependency
  ordering, risk-based batching, one attributable human pack action, quorum,
  staleness, and parked external effects;
- content-addressed committed projections and append-only human restoration
  transitions with explicit external-effect non-guarantees;
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

The next protocol work should be earned by conformance and operator evidence:
stabilize PCAW v1 through independent implementations, exercise Approval Packs
in real bounded knowledge-work sessions, measure verifier trusted code and
review comprehension, and design signatures only together with identity,
revocation, and custody.

## Approved Blueprint Execution Sequence

The [Palari Blueprint](palari-blueprint.md) remains the strategy and research
inventory. It is not an implementation backlog. The following sequence is the
approved bridge from that strategy to bounded repository work. Each stage needs
its own opaque work-item identity, packet, completion contract, evidence,
independent review, and human authority where required.

### 1. Portable Agent Session Contract Compiler

Compile one ready or blocked agent packet into a deterministic,
provider-neutral session contract. The contract exposes exact read/write scope,
capabilities, forbidden effects, obligations, stop conditions, proof
requirements, authority binding, enforcement status, and honest limitations.

The portable contract is the common input for future harness adapters. A target
may claim structural enforcement only for properties its documented native
controls actually enforce. Unsupported mappings stay explicit and advisory.
Compilation and inspection add no agent-launch, human-decision, provider,
network, or external-write authority.

Current work: `WORK-DDDCF6BD8DB248CFA51B68FC6CC167BC`.

### 2. Presentation-Bound Human Decisions

Canonicalize the exact Approval Pack projection offered at a human decision
surface and bind the decision to its digest. Any current evidence, review,
artifact, scope, or decision-input change must invalidate the binding. The
digest proves presentation-artifact bytes; it does not prove what compromised
software displayed or what a person read or understood.

This stage should strengthen local authority semantics without silently adding
fields to PCAW v1. A future PCAW version may carry the property portably after
its normative schema and privacy rules exist.

Current work: `WORK-66351C3AD0334E78AFE962F06A0BF9CA`.

### 3. Boundary-Change Simulation

Replay a proposed scope, capability, or authority-policy change against the
replayable journal before adoption. Report which historical actions would have
changed classification, which accepted states would become invalid, and whether
the proposal widens access or creates a bypass. Simulation is read-only and
cannot adopt the proposed policy.

### 4. Independent PCAW v1 Verifier

Build a separately maintained verifier that shares no Palari implementation
code and passes the normative PCAW v1 conformance corpus. This is the protocol
proof point: the format, vectors, and verifier contract must be sufficient for
an independent implementation. Its toolchain must not become a Palari runtime
dependency.

### 5. PCAW v2 Specification And Signatures

Design the protocol before its signing implementation. The required order is:

1. threat model, trust profiles, and identity/non-identity claims;
2. custody, rotation, revocation, threshold, and verification-time rules;
3. normative v2 statement/envelope schema and conformance vectors;
4. exact DSSE pre-authentication encoding and envelope implementation;
5. an OpenSSH signing backend and signed-verification CLI;
6. additional backends only when a concrete trust profile earns them.

A signature primitive alone does not authenticate a person or solve key
custody. Palari must not add signing ceremony while leaving those properties
ambiguous.

## Deliberately Deferred Blueprint Ideas

The following ideas remain valuable research, but do not enter the execution
queue until their stated dependency exists:

- approval-inbox notifications: after a separately approved external-write and
  redaction design;
- trusted-time anchoring: after a concrete profile requires it and defines its
  trust material and offline behavior;
- Sigstore and a shared transparency log: after design-partner input on
  identity privacy, operation, witnessing, and compromise recovery;
- a browser verifier: after the selected signature suite passes a browser
  compatibility spike and the shared conformance vectors;
- knowledge-work field maps and non-file subjects: after a bounded real-world
  document workflow validates the model;
- hosted services and connector execution: outside the local kernel until
  separately authorized.

## Actionability Contract

Every stage promoted from this roadmap into implementation must name:

- the current implemented behavior and the exact gap;
- the safety invariant the change makes mechanical;
- bounded paths, sources, dependencies, and authority owner;
- positive and fail-closed acceptance tests;
- compatibility and explicit non-goals;
- focused and complete verification commands;
- exact committed evidence and an independent review of that commit.

Roadmap ordering is dependency guidance, not merge ordering. Opaque work-item
IDs carry no chronology, and independent stages may run in parallel when their
declared dependencies and write boundaries do not overlap.
