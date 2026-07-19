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
- focused and complete verification, isolated install, documentation,
  conformance, and network-free demonstration checks.

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

## Architecture Research Report: A Company Of Palaris

Status: **approved direction for documentation and safety design, not execution
authority or an implementation contract**. This report records the product
thesis and research questions discussed on 2026-07-17. Founder decision
`DECISION-REPO-0001` selected `design signed gate first`. It does not enable a
broker, model runner, external writes, autonomous acceptance, or access to
signing keys. Every implementation slice still requires its own opaque work
item, bounded packet, tests, evidence, independent review, and human authority.

### Product thesis

Palari Company OS is intended to become an operating system for a complete,
model-agnostic company made of governed AI work partners. Claude, Codex, Devin,
GLM, local models, deterministic programs, and future providers are execution
runtimes. They are not the durable company identity and do not own company
authority.

A **Palari** is the stable governed company role. A model or tool may occupy
that role for one bounded session. The Palari's goal, authority, contract,
sources, current state, delegation history, receipts, and outcomes remain in
Company OS when the runtime changes.

The organizing rule is:

> **Authority flows downward. Proof flows upward. No Palari can promote
> itself.**

The intended experience is that a human provides a goal, budget, risk
tolerance, and authority boundary once. Palari may then construct a temporary
organization, route work to suitable models, delegate bounded assignments,
collect proof, replace failed workers, and return only decisions that genuinely
require human judgment.

This extends the current queue and work-item lifecycle; it does not replace
them with an autonomous agent framework. The deterministic control plane
remains authoritative. Models propose plans and perform bounded work, while
ordinary code decides whether a requested transition or action is permitted.

### The company hierarchy

The initial conceptual hierarchy is:

| Level | Governed role | Typical occupant | Maximum authority shape |
| --- | --- | --- | --- |
| L0 | Human authority | Founder or qualified human quorum | Charter goals, issue or revoke root authority, authorize consequential effects, and make reserved human decisions |
| L1 | Company orchestrator Palari | Highest-capability planning model appropriate to the work | Interpret a charter, create a work graph, allocate bounded budgets, appoint subordinate Palaris, and escalate uncertainty |
| L2 | Domain-lead Palari | Strong specialist model | Design and coordinate work inside one delegated domain, and create narrower executor assignments |
| L3 | Executor Palari | Smaller or cheaper model suited to a bounded task | Read and write exact resources, run declared checks, and produce receipts without expanding scope |
| L4 | Tool action | Deterministic function or tightly constrained tool | Perform one normalized operation authorized by one current capability |

These levels describe organizational authority, not cryptographic strength.
Every signing key must use an approved secure primitive. A lower-level key is
not mathematically weaker; it is attached to less authority.

Model capability and company authority must remain independent dimensions:

- **capability profile** describes what reasoning, context, modalities, cost,
  and reliability a runtime is suitable for;
- **authority profile** describes what the session is allowed to read, change,
  delegate, spend, approve, or cause externally.

A more capable or expensive model is not automatically more trustworthy. It
may receive a broader planning problem while still lacking human-decision,
secret, merge, deployment, or external-write authority. A small model may
receive exact write authority for a narrow task. Runtime selection is an
operational decision; authority is a governance decision.

### The missing layer

Current Palari primitives already cover much of the organizational foundation:

- goals express company intent;
- workbenches bound shared arenas of work;
- Palaris name stable AI work partners;
- work items, attempts, and claims establish bounded assignments and ownership;
- portable session contracts declare provider-neutral boundaries;
- hooks and checks can enforce selected host boundaries;
- receipts and evidence record what happened;
- review separates inspection from building;
- human decisions preserve reserved authority;
- the governance journal and PCAW statements make history and results
  independently inspectable.

The candidate missing layer is **portable pre-action authorization**. A session
contract declares what an agent should be able to do, and current adapters
enforce some of those declarations. A portable capability would let a
participating tool require exact, current, mechanically verifiable authority
before performing an action, without trusting the model's narration.

Working research name: **PACT — Palari Attenuating Capability Tokens**. This is
not a cryptocurrency, financial instrument, tradable asset, blockchain token,
or source of human authority. “Token” means a compact authorization object.
The name remains provisional until comparison with existing capability systems
shows that it is accurate and not misleading.

### Delegation and attenuation

A root capability begins at a legitimate authority boundary. Each delegated
child must be no more powerful than its parent:

```text
child authority ⊆ parent authority
```

A child may:

- remove tools or action classes;
- narrow readable and writable paths;
- narrow permitted sources and data classes;
- constrain command arguments or normalized parameters;
- reduce time, money, compute, or external-effect budgets;
- shorten expiration;
- reduce remaining delegation depth;
- add proof, review, or human-presence requirements.

A child must never:

- add an authority absent from its parent;
- expand a path through traversal, symlink, or sibling-prefix ambiguity;
- extend expiration or delegation depth beyond its parent;
- remove a mandatory review, evidence, or human gate;
- convert model capability into human authority;
- authorize its own acceptance, promotion, key issuance, merge, deployment, or
  external effect unless the parent explicitly held that delegable authority
  and policy permits delegation of it.

Every child should identify its parent digest. Revocation or expiry of a parent
must invalidate its descendants unless a future specification explicitly and
safely defines another result. Delegation should form an inspectable authority
graph rather than an informal chain of prompts.

### Candidate capability statement

A future normative design should determine whether to reuse the PCAW envelope,
DSSE, an established capability-token format, or a separate canonical object.
The candidate semantic content includes:

- schema and protocol version;
- capability identifier and parent digest;
- issuer and holder/session public-key identities under an explicit trust
  profile;
- Palari identity, company role, work item, attempt, and session binding;
- exact work-contract and relevant workspace/checkpoint digests;
- allowed tools and normalized action classes;
- canonical readable and writable path boundaries;
- approved sources, data classes, freshness, and redaction constraints;
- argument and parameter constraints;
- monetary, compute, time, and external-effect budgets;
- allowed child roles and maximum delegation depth;
- required receipts, evidence, reviewer class, quorum, and human presence;
- issue, not-before, expiry, revocation, and verification-time semantics;
- nonce, request identifier, or another replay-control mechanism;
- signature suite, key identifier, and explicit security limitations.

The exact schema must be small, canonical, deterministic, reject unknown or
ambiguous fields, and have a language-independent conformance corpus. No field
should be added merely because it sounds comprehensive.

### Action-boundary evaluation

The desired deterministic interface is conceptually:

```text
capability
+ normalized requested action
+ current governed state
+ local policy and trust inputs
-> allow or deny with stable diagnostics
```

Enforcement belongs as close as possible to the consequential action. A prompt
or session contract alone cannot stop a hostile runtime. Candidate boundaries
include:

- Palari CLI mutations;
- provider or agent-host hooks;
- an MCP or tool proxy;
- filesystem and process sandboxes;
- connector and external-write brokers;
- repository, merge, deployment, or payment gateways.

No single adapter will enforce every property. Each integration must publish an
honest enforcement profile naming which constraints are structural, which are
checked at runtime, which are advisory, and which are unavailable. Native OS
sandboxing and tool-boundary checks should complement each other.

Executed actions and receipts should bind the capability digest, exact
normalized request, relevant state digest, result or artifact digest, journal
event, and outcome. This connects **permission before action** to **proof after
action**.

### Orchestration model

The L1 orchestrator's job is to compile a human charter into a bounded work
graph, not to inherit unlimited company authority. It may:

1. classify risk, ambiguity, blast radius, and required capability;
2. decompose the goal into independently claimable work items;
3. select provider-neutral capability profiles rather than hard-coded model
   brands;
4. route ambiguous architecture work to stronger models and mechanical work to
   cheaper executors;
5. issue child assignments only inside its authority and budget;
6. monitor claims, leases, proof freshness, failures, and conflicts;
7. retry idempotently or replace an executor without changing the contract;
8. escalate when scope, cost, uncertainty, authority, or risk crosses a gate;
9. assemble current evidence and independent review for the human surface.

The routing policy should be measurable. Model escalation may consider task
uncertainty, failed attempts, security sensitivity, context size, proof quality,
and expected cost. It must not silently weaken verification to save money or
assume a provider's marketing label proves competence.

### Independent review in the organization

The builder and reviewer should normally be sibling authority branches:

```text
Company orchestrator
├── Builder lead
│   └── Executor Palaris
└── Independent reviewer
```

The reviewer receives bounded, usually read-only authority to inspect the exact
candidate, contract, receipt, and evidence. A descendant of the builder must
not satisfy independent-review requirements. If a reviewer modifies the
candidate, that creates a new builder action and invalidates or restarts the
review relationship. Higher organizational rank must not bypass separation of
duties.

### Human key custody and identity boundary

A signature proves control of a private key under stated verification rules.
It does not prove that a particular person understood or approved the action.
If an agent running as the same OS user can read or invoke the human signing
key without human presence, the agent can manufacture apparently human
authority.

Real human authority therefore requires a trust profile whose signing key is
outside the ordinary agent process, for example:

- hardware-backed signing with presence or confirmation;
- a phone approval surface;
- a separately isolated local authority service;
- an organizational quorum service with explicit custody and revocation.

The design must specify enrollment, rotation, loss, compromise, revocation,
threshold policy, verification time, recovery, and audit. “Signed” must never
be presented as equivalent to “human-authenticated” without those assumptions.
Unsigned capability objects may support simulation and structural validation,
but must not grant real broker or external-effect authority.

### Threats and required failures

Any future protocol must address at least:

- an honest but fallible orchestrator that delegates excessive scope;
- a compromised child that tries to broaden its capability;
- a malicious or confused-deputy tool;
- a child presenting a token intended for another role, session, or action;
- replay of a previously valid request;
- stale contract, workspace, evidence, review, or human-decision bindings;
- expiry, revocation, clock ambiguity, and offline verification;
- path traversal, sibling-prefix confusion, and symlink escape;
- duplicate JSON keys, unknown fields, invalid Unicode, and ambiguous time;
- stolen human or orchestrator keys;
- a hostile process running as the same OS user;
- forged, forked, truncated, or replaced journal history;
- budget exhaustion and delegation explosions;
- correlated builder and reviewer identities;
- a powerful model treated as inherently authorized;
- a malicious human who legitimately holds authority.

Palari can bound, attribute, and expose authorized human actions. It cannot
guarantee that an authorized human makes a good decision.

### Research inventory

The following sources were identified as a research watchlist during the
architecture discussion. They are not Palari dependencies or endorsed claims.
Many are recent preprints or evolving drafts; titles, versions, maturity, and
security claims must be revalidated from primary sources before a work item
relies on them.

Direct agent governance and enforcement:

- [Attenuating Authorization Tokens for Agentic Delegation Chains](https://datatracker.ietf.org/doc/draft-niyikiza-oauth-attenuating-agent-tokens/00/)
- [Before the Tool Call: Origin-Anchored Authorization for Agentic Systems](https://arxiv.org/abs/2603.20953)
- [Governing Dynamic Capabilities in Agentic Systems](https://arxiv.org/abs/2603.14332)
- [Proof of Execution](https://arxiv.org/abs/2607.05397)
- [Agent-C: Temporal Constraints for Agentic Systems](https://arxiv.org/abs/2512.23738)
- [Formal Methods Meet LLM Agents](https://arxiv.org/abs/2605.16198)
- [Formalizing LLM Agent Security](https://arxiv.org/abs/2603.19469)
- [VeriGuard](https://arxiv.org/abs/2510.05156)
- [A2AS](https://arxiv.org/abs/2510.13825)
- [Agent Audit](https://arxiv.org/abs/2603.22853)
- [ProvenanceGuard](https://arxiv.org/abs/2607.01236)
- [Security Challenges in AI Agent Systems](https://arxiv.org/abs/2507.20526)
- [Toward Secure LLM Agents](https://arxiv.org/abs/2606.10749)
- [Falsifiable Release Gates](https://arxiv.org/abs/2607.13070)
- [AGENTSAFE](https://arxiv.org/abs/2512.03180)
- [Cryptographic Runtime Governance](https://arxiv.org/abs/2603.16938)
- [The Aegis Protocol](https://arxiv.org/abs/2508.19267)

Identity, delegation, and authorization tokens:

- [AI Agents with Decentralized Identifiers and Verifiable Credentials](https://arxiv.org/abs/2511.02841)
- [Identity Management for Agentic AI](https://arxiv.org/abs/2510.25819)
- [Binding Agent Identity](https://arxiv.org/abs/2512.17538)
- [Secure Autonomous Agent Payments](https://arxiv.org/abs/2511.15712)
- [A Blockchain Reference Architecture for Autonomous Agents](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6650658)
- [Zero-Trust Token Authorization](https://doi.org/10.1016/j.future.2025.108227)
- [Delegated Authority with Self-Sovereign Identity](https://doi.org/10.3390/math13182971)
- [SchoCo Extensible Authorization Tokens](https://www.sciencedirect.com/science/article/pii/S2214212625003631)

Proof, provenance, privacy, and tamper-evident logging:

- [Nitro Tamper-Evident Logging](https://arxiv.org/abs/2509.03821)
- [MAIF Artifact Provenance](https://arxiv.org/abs/2511.15097)
- [Who Audits the Auditor?](https://arxiv.org/abs/2604.22096)
- [Zero-Knowledge Verifiable Inference](https://arxiv.org/abs/2511.19902)
- [NANOZK](https://arxiv.org/abs/2603.18046)
- [Confidential LLM Inference with TEEs](https://arxiv.org/abs/2509.18886)
- [Trustless Provenance](https://eprint.iacr.org/2025/1024)
- [Private SCT Auditing](https://eprint.iacr.org/2025/556)
- [Verifiable Streaming Computation](https://eprint.iacr.org/2025/251)
- [Anonymous Credentials with Partial Disclosure](https://eprint.iacr.org/2025/041)
- [Homomorphic Signatures for Streams](https://eprint.iacr.org/2025/110)
- [Hierarchical Identity-Based Encryption and Delegation](https://eprint.iacr.org/2025/291)

Established systems that should be compared before inventing a format include
Macaroons, Biscuit authorization tokens, UCAN, OAuth Rich Authorization
Requests, OAuth DPoP, GNAP, SPIFFE/SPIRE, W3C Verifiable Credentials, in-toto,
SLSA, DSSE, RFC 8785 canonical JSON, and transparency-log designs.

The strongest transferable pattern is not blockchain or zero-knowledge proof.
It is the combination of monotonic attenuation, proof of possession,
pre-action authorization, exact-state binding, replay protection, and
post-action receipts. Blockchain, shared consensus, TEEs, zero-knowledge
proofs, or zkVMs should be considered only after a concrete adversary and
deployment profile requires their cost.

### Staged roadmap

This report does not place implementation into the execution queue. If promoted
later, the safe sequence is:

1. **Terminology and threat model.** Define Palari identity, runtime identity,
   role, capability profile, authority profile, delegation, attenuation,
   custody, revocation, replay, and human presence. Decide whether PACT is the
   right name.
2. **Comparative design.** Map current session contracts and claims to
   Macaroons, Biscuit, UCAN, OAuth, and the emerging IETF agent-delegation work.
   Reuse an established format when it satisfies Palari's deterministic,
   offline, minimal-dependency contract.
3. **Normative structural specification.** Publish canonical schemas, an
   attenuation algorithm, stable diagnostics, valid vectors, and adversarial
   invalid vectors. Any unsigned form is declaration or simulation only.
4. **Signed-gate and custody design.** Specify issuer and holder proof,
   algorithms, external human custody, rotation, revocation, threshold policy,
   verification time, recovery, and explicit trust profiles before enabling
   authority-bearing execution.
5. **Read-only delegation simulation.** Compile a human charter into a proposed
   authority tree, prove every child is a subset, estimate model and budget
   routing, and show escalations without launching agents or invoking tools.
6. **Local action-boundary prototype.** Enforce a tiny reversible set of local
   operations in fixtures or temporary workspaces. Bind each operation to a
   capability and receipt. No external writes.
7. **Bounded orchestration pilot.** Run an L1 orchestrator with L2/L3 workers on
   independent local work items, sibling review, deterministic recovery, and a
   single human charter. Keep merge, push, deployment, payments, and providers
   outside the pilot.
8. **Provider and tool adapters.** Add integrations only when each can publish
   an honest enforcement profile and pass the same conformance corpus.
9. **External-effect gate.** Consider a broker only through a separate R5 work
   item after signed custody, revocation, audit, quorum, idempotence, and
   rollback or compensation semantics are proven.

### Falsifiable acceptance direction

A future implementation contract should require negative tests proving that:

- a child cannot broaden any parent permission;
- changed, expired, revoked, or replayed authority fails closed;
- a token for another session, role, state, or request is rejected;
- stale review, evidence, contract, or human authority cannot authorize action;
- canonical path checks reject traversal, symlink escape, and sibling prefixes;
- the builder's delegation branch cannot satisfy independent review;
- replacing the model preserves the Palari contract but does not inherit an
  earlier session's holder key;
- retries do not duplicate effects or silently consume authority twice;
- every allowed action produces a receipt bound to permission and result;
- human-only powers remain unavailable without an external human-presence trust
  profile;
- complete verification remains offline, deterministic, and provider-neutral
  for all properties that do not require a currency or revocation service.

The architecture should be abandoned or narrowed if it cannot provide
materially stronger pre-action enforcement than current session contracts, if
key custody merely moves human credentials into agent reach, if it requires a
large trusted runtime or speculative cryptography, or if its ceremony costs
more than the unsafe actions it mechanically prevents.

### Durable product sentence

The long-term product promise captured by this report is:

> **Give Palari a goal and an authority budget. It organizes a temporary,
> auditable company of model-agnostic AI workers to accomplish it, while no
> descendant can gain more power than the human charter granted.**
