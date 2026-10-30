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

The operating rule is therefore:

> **Models propose. Deterministic gates dispose. Humans retain sovereignty.**

### Research update: how the evidence changed the thesis

The research strengthened the company-of-Palaris direction but changed the
proposed architecture in important ways:

| Earlier prior | Updated direction |
| --- | --- |
| Governance mainly inspects work after execution. | Palari should govern the whole loop: authority before action, enforcement during action, and proof after action. |
| PACT might become a separate token and authority subsystem. | The existing portable session contract is the root capability. Delegation creates a strictly narrower **derived session contract**, avoiding a second source of authority. PACT may remain a public protocol name for portable or signed representations. |
| One hierarchy could describe the company. | Three graphs are required: an authority tree, a work dependency DAG, and a cross-branch review graph. Conflating them makes independence and delegation ambiguous. |
| The strongest model naturally becomes a standing super-agent. | The orchestrator is an ordinary, replaceable Palari with broad planning context but a narrow pen: it may propose governance objects only within its charter and cannot grant itself authority. |
| Model identity and company role could be treated together. | A durable Palari role and a replaceable runtime descriptor are separate. Replacing Claude, Codex, a local model, or a deterministic program must not change the role's governed authority. |
| Budget primarily means money or compute. | Budget is an attenuating authority dimension covering money, compute, time, tool calls, external effects, and scarce human attention. |
| Agent memory could become institutional memory. | Models may suggest records, but only governed, attributed, reviewable company artifacts become institutional memory. |
| Palari should compete as another orchestration runtime. | Palari should own the provider-neutral authority, policy, evidence, and proof layer around runtimes such as agent teams, coding hosts, sandboxes, and deterministic tools. A small native orchestrator remains useful as a reference implementation, not the product moat. |

This is not a blockchain thesis. The valuable pattern is capability-style
attenuation: every descendant receives a smaller, inspectable envelope of
authority. Cryptographic signatures become valuable when a contract crosses a
process, machine, provider, or custody boundary, but cryptography cannot make a
bad policy good or turn an agent-accessible key into genuine human presence.

### Current state and target state

The roadmap must not present target architecture as shipped behavior:

| Property | Current foundation | Target direction |
| --- | --- | --- |
| Durable organizational identity | Palaris, work items, attempts, claims, and provider-neutral session contracts exist. | Add explicit runtime descriptors so changing models does not change role identity or authority. |
| Delegated authority | Packets and contracts bind one session; policy and transition gates fail closed in covered paths. | Derive child contracts mechanically with monotonic attenuation and bounded delegation depth. |
| Action enforcement | CLI gates, checks, and selected host hooks enforce known boundaries; coverage depends on the adapter. | Publish conformance-tested action-boundary profiles for every runtime and tool integration. |
| Verification | PCAW v1 can verify governance consistency and artifact bytes offline. | Preserve deterministic offline verification while adding portable delegation-chain properties. |
| Identity | Actor attribution is declared and local controls assume their documented trust boundary. | Signed envelopes and external human key custody provide authenticated trust profiles without placing founder keys in agent reach. |
| Human authority | Current policy can require explicit, current human decisions. | Budget human attention, bind consequential decisions to exact presentations, and reserve true human powers to externally controlled custody. |
| Company operation | Work DAGs, claims, receipts, reviews, decisions, and outcomes support bounded concurrent work. | Compile one charter into a temporary organization with derived contracts, runtime selection, chain-independent review, and concise capability/evidence read models. |

### Durable company, temporary organization

The company is durable; the organization instantiated for a charter is
temporary. Palari identities, policies, evidence, and history remain after an
individual model session ends. Each charter may create a different bounded
authority tree and work graph, then dissolve that temporary structure without
erasing its proof.

### The company hierarchy

The initial conceptual hierarchy is:

| Level | Governed role | Typical occupant | Maximum authority shape |
| --- | --- | --- | --- |
| L0 | Human authority | Founder or qualified human quorum | Charter goals, issue or revoke root authority, authorize consequential effects, and make reserved human decisions |
| L1 | Company orchestrator Palari | Highest-capability planning model appropriate to the work | Interpret a charter, propose governance objects, create a work graph, allocate bounded budgets, appoint subordinate Palaris inside the charter, and escalate uncertainty |
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

### Three graphs, not one org chart

Palari needs three related but distinct structures:

1. **Authority tree.** For one charter, every delegated contract has one
   parent and no child is more powerful than that parent. This graph answers
   “who may authorize this?”
2. **Work dependency DAG.** Work items may execute concurrently whenever their
   declared dependencies and write boundaries permit it. Opaque IDs do not
   imply order. This graph answers “what must finish before what?”
3. **Review graph.** Independent review crosses authority branches. A reviewer
   must not descend from the builder's delegation chain and receives only the
   read and verdict authority required for the exact candidate. This graph
   answers “who is sufficiently independent to assess this?”

The shared governed workspace is the information plane connecting these
graphs. Work items, claims, receipts, evidence, reviews, decisions, and journal
events should carry the necessary links. Palari does not need an informal
agent-to-agent message bus to establish company truth.

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

The candidate missing layer is **portable derived authority at the action
boundary**. The existing session contract is the root capability for a bounded
session. A parent Palari should be able to derive a child contract only through
a deterministic attenuation function. A participating tool can then require
exact, current authority before acting without trusting the model's narration.

Working protocol name: **PACT — Palari Attenuating Capability Tokens**. The
internal primitive should be called a **derived session contract**, not a new
token record or second authority database. “Token” is reserved for a compact
portable envelope used across a process, provider, host, or tool boundary. It
is not a cryptocurrency, financial instrument, tradable asset, blockchain
token, or source of human authority.

Within one local trusted control plane, the authoritative answer should be
re-derived from the current root contract and governed state. A portable child
envelope becomes useful only when the verifier cannot safely query that state.
Structural validity and current authorization are separate questions: a
well-formed derivation may still be stale, expired, revoked, exhausted, or
bound to the wrong current state.

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
tree rather than an informal chain of prompts.

### Candidate derived-contract extension

A future normative design should extend the current session-contract schema
before considering another object model. A portable envelope may later reuse
PCAW, DSSE, or an established capability format. The smallest useful derived
contract adds:

- schema and protocol version;
- contract identifier, parent digest, root digest, and derivation depth;
- issuer Palari, holder Palari, runtime session, and explicit trust profile;
- Palari identity, company role, work item, attempt, and session binding;
- exact work-contract and relevant workspace/checkpoint digests;
- allowed tools and normalized action classes;
- canonical readable and writable path boundaries;
- approved sources, data classes, freshness, and redaction constraints;
- argument and parameter constraints;
- monetary, compute, time, and external-effect budgets;
- human-attention budget and escalation obligations;
- allowed child roles and maximum delegation depth;
- required receipts, evidence, reviewer class, quorum, and human presence;
- issue, not-before, expiry, revocation, exhaustion, and verification-time
  semantics;
- nonce, request identifier, or another replay-control mechanism;
- optional signature suite and key identifier only under a defined trust
  profile;
- explicit security limitations and an honest enforcement profile.

The exact schema must be small, canonical, deterministic, reject unknown or
ambiguous fields, and have a language-independent conformance corpus. No field
should be added merely because it sounds comprehensive.

### Five product primitives to add

The strategic design now identifies five focused primitives rather than a new
agent framework:

1. **Derived session contracts** mechanically attenuate authority from an
   existing root contract.
2. **Runtime descriptors** record provider, model class, tool surface,
   sandbox/enforcement profile, cost class, and capability claims without
   making the runtime the durable company identity.
3. **Attenuating budgets** treat money, compute, time, retries, external
   effects, and human attention as bounded resources inherited by descendants.
4. **Chain-independent review** proves the reviewer is outside the builder's
   authority branch and binds the verdict to the exact candidate.
5. **Capability-evidence read models** answer, concisely and mechanically,
   what a Palari may do now, why, what it has spent, what proof is current, and
   what single safe action comes next.

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

### Strategic product boundary

The market already contains increasingly capable agent runtimes, coding hosts,
team coordinators, sandboxes, and “AI company” interfaces. Palari should not
win by reproducing every scheduler, chat surface, model adapter, or virtual
computer. It should make those systems governable and interchangeable.

The integration boundary is:

```text
human charter and custody
          ↓
Palari authority, policy, state, evidence, and proof
          ↓
replaceable orchestration and execution runtimes
          ↓
tools, sandboxes, repositories, and external systems
```

Palari may ship a small reference orchestrator so the protocol is usable and
testable without another framework. That orchestrator is evidence that the
control plane works, not the exclusive execution engine. External runtimes
remain subordinate to Palari's current contracts and enforcement profiles;
their internal conversation is never company truth by itself.

Current non-claims remain explicit:

- PCAW v1 verifies governance consistency and governed artifact bytes, but its
  declared actors are not cryptographically authenticated;
- host enforcement is only as complete as the documented adapter, sandbox, and
  action boundary;
- a process with the same OS-user privileges may remain inside the local trust
  boundary unless keys and effects are isolated externally;
- signed envelopes alone do not prove human understanding or presence; and
- Palari does not yet autonomously instantiate or operate the full temporary
  company described here.

### Staged roadmap

This report does not place implementation into the execution queue. If promoted
later, the safe sequence is:

1. **Terminology, threat model, and graph invariants.** Define Palari identity,
   runtime identity, capability versus authority, delegation, attenuation,
   custody, revocation, replay, and human presence. Specify the authority tree,
   work DAG, and review graph as separate structures.
2. **Derived session contract specification.** Extend the existing contract,
   define a deterministic monotonic-attenuation algorithm, and publish stable
   diagnostics, valid vectors, and adversarial invalid vectors. Do not create a
   parallel authority store.
3. **Runtime descriptors.** Record the replaceable runtime's capabilities,
   provider, tool surface, sandbox and enforcement profile, cost class, and
   limitations independently from its durable Palari role.
4. **Budget and attention accounting.** Define conserved or explicitly
   allocated descendant budgets for money, compute, time, retries, tool calls,
   external effects, and human attention. Deny oversubscription deterministically.
5. **Chain-independent review.** Mechanically reject a reviewer descended from
   the builder's authority branch, bind review to the exact candidate, and
   invalidate it after substantive change.
6. **Capability-evidence read models.** Add concise operator and agent views for
   current authority, consumed budget, proof currency, blockers, conflicts,
   and the one next safe action.
7. **Read-only charter simulation.** Compile a charter into a proposed
   temporary authority tree and work DAG, prove every child is a subset,
   estimate runtime and budget routing, and show escalations without launching
   agents or invoking tools.
8. **Local multi-runtime reference demonstration.** Use temporary workspaces to
   run independent workers, including a deterministic program, through one
   charter, narrow derived contracts, exact receipts, chain-independent review,
   runtime replacement, and one meaningful human decision. No external writes.
9. **Orchestration-runtime adapters.** Integrate coding hosts, agent teams, and
   sandboxes only when each publishes an honest enforcement profile and passes
   the same conformance corpus. Palari owns governance and proof; the adapter
   remains replaceable.
10. **Signed authority and authenticated proof.** Design external human key
    custody, issuer and holder proof, rotation, revocation, thresholds,
    recovery, and a possible authenticated PCAW successor. Unsigned contracts
    remain declaration and structural enforcement inside their stated trust
    boundary.
11. **External-effect gate.** Consider a broker only through a separate R5 work
    item after signed custody, audit, quorum, idempotence, and rollback or
    compensation semantics are proven.

### Flagship falsifiable demonstration

The architecture earns implementation cost only if a network-free reference
scenario can show all of the following with inspectable artifacts:

1. a human supplies one charter, authority budget, and risk boundary;
2. an ordinary orchestrator Palari proposes an authority tree and parallel work
   DAG without receiving founder, merge, deployment, or secret authority;
3. two interchangeable workers, at least one of them a deterministic program,
   receive narrower derived contracts and produce exact receipts;
4. an out-of-scope action is denied before its effect with a stable,
   actionable diagnostic;
5. one worker runtime is replaced without changing the durable Palari role or
   silently inheriting the former session's authority;
6. a chain-independent reviewer checks the exact candidate;
7. the human sees and decides one genuinely consequential question rather than
   performing routine ceremony; and
8. an offline verifier derives the final state and detects an altered governed
   artifact.

This scenario should measure supervision burden, denied unsafe actions,
recovery behavior, proof completeness, and runtime replaceability. A theatrical
multi-agent demo without these falsifiable properties is not sufficient.

### Falsifiable acceptance direction

A future implementation contract should require negative tests proving that:

- a child cannot broaden any parent permission;
- changed, expired, revoked, or replayed authority fails closed;
- a derived contract or portable envelope for another session, role, state, or
  request is rejected;
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

> **Give Palari a charter and an authority budget. It organizes a temporary,
> auditable company of interchangeable AI workers: authority flows down through
> derived contracts, proof flows up through verifiable receipts, and no member
> can grant itself power the human charter never contained.**
