# The Palari Blueprint — Git, but for AI Work

Status: **strategy proposal, not a normative specification, product contract,
legal opinion, or execution authority**. It consolidates the thesis, research
snapshot, protocol direction, and candidate implementation sequence that
Claude developed on `claude/repo-evaluation-7s05hw` at `8da6d46`, reviewed for
integration on 2026-07-16 against repository head `682cfe9`. Repository code,
schemas, `AGENTS.md`, agent packets, and canonical product documentation remain
authoritative. If this document conflicts with them, this document is wrong.

Market, product, endpoint, and regulatory facts are a dated research snapshot,
not durable invariants; recheck primary sources before relying on them. Each
WRP item in §16 is only a candidate. It requires its own authorized Palari work
item, current source review, bounded packet, evidence, independent review, and
human authority. This document alone never authorizes an agent to implement one.

Companion: the shipped [PCAW v1 specification](../../spec/pcaw/v1/README.md).

---

# Part I — The idea

## 1. The thesis

**Accountability was never designed. It was a side effect of slowness.**

Every accountability system in working life — sign-off sheets, email trails,
"ask the person who handled it" — silently assumed human throughput: one
person, a few meaningful actions per day. At that speed, "who approved this?"
could always be reconstructed after the fact; there were few enough events
for memory and inboxes to triangulate.

AI did not just speed work up. It invalidated that assumption. When one
person supervises a thousand executed tickets a day, "who approved erasing
the database", "who approved this patient receiving this medicine", "who
accepted this filing" stop being questions you can answer by asking around.
The trail must be a designed artifact, created at the moment of the act, or
it never exists at all.

Second-order effect: at AI velocity the human's job silently changes from
doer to approver — and mass approval degrades into rubber-stamping unless the
record captures **what the approver was actually presented**. A signature
alone proves someone clicked yes. Only a record of the presented evidence
proves what they clicked yes **to**.

The product is one sentence:

> **Git, but for AI work.** A free protocol for portable receipts of
> AI-executed work — what was authorized, what happened, what evidence and
> review were current, and what a human decided — independently verifiable
> offline against explicit trust inputs, without requiring a Palari service.

That sentence is the target. Shipped PCAW v1 proofs are deterministic and
offline-verifiable but unsigned: actor attribution is declared, not
cryptographically authenticated. The signed receipt, identity, trusted-time,
and shared-log design in this document is proposed PCAW v2 work, not a current
product claim.

Git records **content history**: what bytes changed, who committed. Palari
records **authority history**: what the agent was allowed to do, what
evidence the human was presented, who approved, and when. That distinction
answers "doesn't git already do this?" — and points at the largest market:
the knowledge work that has no git at all. The nurse approving an AI-drafted
medication note, the paralegal accepting an AI-drafted filing, the student
signing an AI-completed tax return.

The sentence is load-bearing. It names the object (durable verifiable record),
the architecture (content-addressed, offline-capable, explicit trust roots),
the business model (free protocol, paid hosting — the GitHub move), and the
adoption path (useful to one person on day one, network effects later).

## 2. The machine in four primitives

Nothing here is novel cryptography. It composes four decades-old,
battle-tested primitives — the same ones securing git, HTTPS, and app stores.
What is novel is the statement they attest to.

1. **Fingerprints (hashes).** SHA-256 turns content into a short digest. Same
   content, same digest; a changed byte should produce a different digest.
   A digest is an integrity identifier, not encryption: predictable or
   low-entropy content can be guessed and hashed, and metadata can remain
   identifying. Receipts can omit source bytes, but digest-only is not by
   itself a confidentiality guarantee.
2. **Statements (canonical JSON).** The receipt is a small JSON document full
   of digests, serialized canonically (RFC 8785) so the same logical
   statement always produces the exact same bytes — which lets the statement
   itself be fingerprinted, signed, and logged.
3. **Signatures.** A private key produces a signature over the statement's
   bytes; a verifier with the corresponding public key can verify key
   possession and integrity. Mapping that key to a person, role, or
   organization requires an explicit trusted identity binding. OIDC-bound
   short-lived certificates are one proposed option (§8.2), not an intrinsic
   property of a signature.
4. **Tamper-evident logs.** Each entry can chain to the previous digest.
   Rewriting is detectable to a verifier that holds or trusts an earlier
   checkpoint or independently witnessed head. A local chain alone does not
   stop an operator from replacing the entire history for a new verifier, and
   self-declared event time does not prevent backdating.

A future v2 verifier therefore has more than three responsibilities: verify
subjects, the DSSE signature, the signer against supplied trust policy, trusted
time when claimed, and log inclusion/consistency against a trusted checkpoint.
The result is reproducible evidence under stated assumptions, not trust-free
knowledge.

## 3. Anatomy of a receipt

Illustrative shape (the normative shape lives in the spec):

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {"name": "work-state", "digest": {"sha256": "…"}},
    {"name": "output-artifact-01", "digest": {"sha256": "…"}}
  ],
  "predicateType": "https://palari.dev/pcaw/v2",
  "predicate": {
    "schema_version": "pcaw.v2",
    "claimed_state": "accepted",
    "governance_case": {
      "work_contract": "…what the agent was allowed to read and write…",
      "attempt": "…what was actually executed…",
      "evidence": "…verification bound to the attempt head…",
      "presented_digest": "sha256 of exactly what the approver was shown",
      "human_decisions": "…who decided what, in what order…"
    },
    "parent_receipts": ["…optional digests of superseded/prerequisite receipts…"],
    "subject_roles": {"work-state": "work-state",
                      "output-artifact-01": "output-artifact"},
    "security_limitations": ["…the honest non-claims, machine-readable…"]
  }
}
```

Wrapped, in v2, in a DSSE signature envelope (§8.1), optionally anchored to a
trusted timestamp (§8.4), and recorded in an append-only log (§8.6).

| Question | Field |
| --- | --- |
| What was the agent allowed to do? | `governance_case.work_contract` |
| What did it actually produce? | `subject` digests (output artifacts) |
| What verification ran? | `governance_case` evidence records |
| What was the human presented before deciding? | `presented_digest` (v2) |
| Who decided, and in what order? | `governance_case` human decisions |
| What does this revise or depend on? | `parent_receipts` (v2) |
| Who signs this whole statement? | DSSE envelope signature (v2) |
| When did this exist, provably? | RFC 3161 token / log entry (v2) |
| What does this NOT prove? | `security_limitations` |

**Privacy design rule.** Prefer digests over source content, but do not call a
digest anonymous or confidential. Receipts must be assessed for guessing,
linkability, size, ordering, timestamp, and identifier leakage before they are
safe to retain or export. v2 extends that caution to names: filenames are
metadata, and metadata leaks
("discharge-summary-4412.pdf" in a receipt is itself a disclosure). In
regulated contexts subject names MUST be pseudonymous role labels or digest
prefixes; the pseudonym-to-artifact mapping lives with the operator, outside
the receipt.

## 4. What a receipt does NOT prove (keep this section forever)

- A signature verifies that the corresponding private key approved the
  statement. It proves only key possession until a verifier validates the certificate or
  signer registry and its trust roots. It does not prove the judgment was good,
  the evidence sufficient, or the work semantically correct.
- A presentation digest proves the bytes of a presentation artifact. A trusted
  decision surface must separately bind its action to that artifact before the
  system can claim those bytes were made available. Neither proves what was
  displayed by compromised client software, read, or understood.
- Receipts record and attribute; they do not prevent. A bad approval still
  happens — it becomes permanently attributable, which changes behavior the
  way cameras change driving. In regulated domains attributability *is* the
  product; do not oversell it as safety.
- Identity binding is as strong as the identity provider behind it. A key on
  a laptop proves possession of a laptop; an OIDC-bound short-lived
  certificate proves an authenticated login. State which one a receipt
  carries.
- Trusted timestamps prove existed-no-later-than, not existed-no-earlier-than.
- Public hashes do not conceal guessable inputs. A digest can be personal or
  sensitive data when it remains linkable to a person or small input domain.
- A hash chain proves continuity only relative to a trusted earlier head or
  witness; it does not independently prove completeness or honest event time.
- **Two guarantees, never conflated:** offline verification proves
  **validity-at-signing** (well-formed, signed, consistent when made).
  **Currency** — is this still the latest decision, or was it superseded or
  revoked? — requires a log query (§8.6). Verifier reports state each
  separately; neither is ever implied by the other, and marketing MUST NOT
  promise the second while delivering the first.

---

# Part II — The evidence

## 5. Where Palari stands today

From the code-level evaluation and subsequent integration work (2026-07-15/16):
the engineering is real — 732 tests in the current complete gate, zero runtime
dependencies, a working
offline demo, live hook enforcement (it blocked the evaluating agent's own
out-of-contract command mid-evaluation), and unusually honest threat-model
documentation. The weaknesses are equally real: shell-parsing enforcement in
Claude hooks should be defense in depth rather than the only boundary, while
the governance ontology can obscure the receipt wedge. Native platform
sandboxes reduce parser dependence where available and correctly configured;
they do not eliminate the need for Palari's evidence and authority checks.

PCAW v1 (`spec/pcaw/v1/`) is further along as a protocol than a casual
reading suggests. Already shipped and tested:

- **Standard envelope.** Statements are in-toto Statement v1 objects with
  `predicateType: https://palari.dev/pcaw/v1` — the industry-standard
  attestation shape, ready for DSSE wrapping.
- **Canonical bytes.** Strict I-JSON + RFC 8785 canonicalization, floats
  forbidden, duplicate keys rejected, deterministic export (no export time,
  no absolute paths, no locale text). Identical logical input produces
  identical bytes on any machine. Palari's tested canonicalizer is the
  authority. Stock `json.dumps(sort_keys=True)` is not a general RFC 8785
  implementation because JCS has exact string escaping, invalid-Unicode,
  number, and UTF-16 property-ordering requirements; do not replace the
  canonicalizer with that shortcut.
- **Offline verification with a stable contract.** `palari proof export` /
  `palari proof verify`, exit codes 0/1/2, stable diagnostic codes,
  independent lifecycle re-derivation, fail-closed on everything ambiguous.
- **A conformance corpus that tests other people's verifiers.** The
  dependency-free black-box runner (`spec/pcaw/v1/conformance.py`) accepts
  any verifier command. The protocol move already exists.
- **Honest machine-readable non-claims.** Every statement and report carries
  `security_limitations`; v1 explicitly does not sign and says so.
- **The upgrade path is reserved.** v1's "Future DSSE-compatible envelope"
  section forbids fake signing and enumerates what a signing layer must
  specify: *algorithm agility, key identity, revocation, threshold policy,
  custody, and verification time*. That sentence is the v2 requirements
  checklist, written before we knew we'd need it.
- **Concurrent bounded work** (merged 2026-07-16, PR #13): opaque
  collision-resistant work IDs, an explicit dependency DAG between work items
  (missing/duplicate/self-referential/cyclic edges fail closed),
  cross-worktree single-owner claim leases with compare-and-swap semantics,
  `palari agent start --isolate` (deterministic branch + worktree per work
  item), and worktree-portable evidence verification. Several agents can now
  execute independent bounded work in parallel on one repository without
  racing each other's claims.
- **Deterministic convergence.** Current integration work centralizes routine
  post-decision acceptance and terminal bookkeeping in a bounded fixed-point
  driver. It can finish locally eligible work in the same human action while
  preserving review, evidence, identity, external-write, and authority gates;
  an agent still cannot manufacture the human decision.

What v1 deliberately lacks — the v2 work: signatures and identity, proof of
what was presented to the approver, trusted time, non-file subjects,
revocation statements, and a shared append-only log.

## 6. Competitive landscape snapshot

This is a 2026-07-16 snapshot, not an exhaustive market claim. Projects move
quickly; exact popularity, maturity, feature, and company-status claims must be
rechecked before publication or strategy decisions.

**Native platform controls — the commoditization front.** Claude Code ships
an OS-enforced sandbox (Seatbelt / bubblewrap + seccomp; runtime open-sourced
as `anthropic-experimental/sandbox-runtime`), declarative permission rules,
and pre/post tool-call hooks. OpenAI Codex has independent `sandbox_mode` and
`approval_policy` dials with platform-specific sandbox enforcement. Cursor
documents agent run modes, permissions, and sandboxing. Exact controls,
defaults, and guarantees change by version and operating system. Native
write/network boundaries are increasingly common substrate, but Palari must
test rather than assume each integration's coverage.

**Human-in-the-loop approval layers.** HumanLayer built
approval-before-sensitive-tool-calls over Slack/email and now labels the SDK
documentation as legacy while focusing its top-level product on coding-agent
orchestration. Framework-native HITL also covers many basic approval cases.
gotoHuman does structured review forms; impri (new, 2026) does an approval
inbox with bulk decisions and push notifications. Lesson: simple approval
gates commoditize; structured, evidence-bound review does not.

**Action firewalls / policy engines / gateways.** Microsoft Agent Governance
Toolkit is a public-preview policy, identity, sandboxing, audit, and compliance
stack. Its documentation now includes an implemented offline-verifiable
decision-receipt path for governed MCP calls using Ed25519, RFC 8785, hash
chaining, and SLSA emission. The earlier "unshipped draft" conclusion is stale.
That narrows any cryptographic-receipt novelty claim and makes semantic
interoperability or comparative conformance important future research. Cordum
offers pre-execution policy gating and simulation over historical data.
Invariant Labs was acquired by Snyk within a year — firewall tech is being
absorbed into incumbents. Docker MCP Gateway, IBM ContextForge, Lasso: all
require containers, proxies, or servers. Zero-infra local-first is
structurally differentiated against this entire tier.

**Audit / receipts / provenance.** Git AI provides line-level AI attribution
in Git Notes — records *who wrote what*, not *whether the work was governed*;
complementary. Agent Trace is an early vendor-neutral RFC for AI code
attribution; evaluate interoperability without assuming it has already won or
that every named vendor implements it. soma is a Rust project combining a
hash-chained journal, RFC 3161 anchoring,
in-toto attestations, EU AI Act Article 12 exports — the closest
philosophical neighbor, worth studying. agent-receipts provides Ed25519-signed
per-action receipts, explicitly proof-not-prevention. SLSA / in-toto /
Sigstore: mature signed provenance for *build artifacts* — the substrate to
adapt, not reinvent.

**Work orchestration / task isolation.** Vibe Kanban: kanban issues
→ one git worktree per agent task → diff review; category-defining adoption,
the company announced a 2026 sunset while keeping the repository available.
Claude Squad and Conductor use related worktree-per-task patterns. The reviewed
orchestration examples emphasize isolation and diff review more than Palari's
full work-contract → evidence → independent review → human-authority lifecycle;
that is a plausible differentiation, not a universal claim that no competitor
has enforceable contracts.

**Commoditized (do not compete):** OS-level write/network boundaries; basic
approval prompts; hook/policy insertion points; AI-code attribution formats.

**Open gaps an independent tool can own:**

1. **Portable proof of the complete governed-work lifecycle** — receipts that
   bind scope, attempt, current evidence, independent review, presented
   decision context, authority, and result across providers. Signed per-action
   receipts now exist elsewhere; Palari must prove stronger lifecycle semantics
   and conformance rather than claim the receipt category is empty.
2. **Task-contract semantics** — per-work-item scoped boundaries portable
   across Claude Code, Codex, and Cursor.
3. **The enforcement-to-evidence bridge** — native controls, policy engines,
   and provenance tools cover overlapping parts. Palari's opportunity is a
   simple provider-neutral loop with exact, independently testable bindings.
4. **Local-first, minimal-infrastructure deployment** — many policy and
   gateway products introduce services, containers, or databases. Palari
   should retain a useful local path while comparing current deployment
   requirements rather than claiming every competitor needs infrastructure.

**Two hypotheses that shape strategy:** Vibe Kanban's sunset and HumanLayer's
pivot warn that popularity and developer experience alone do not prove a
durable governance business. They do not prove that compliance will monetize,
either; validate that with design partners. The adoption lesson borrowed from
git is stronger: the protocol should be useful to one team on day one, alone,
offline, with nobody else's permission.

---

# Part III — The design

## 7. Adaptations into the current product (pre-protocol)

Ordered by leverage; independent of the v2 protocol work:

1. **Become the contract compiler, not just the enforcer.** Compile the
   packet write boundary into each platform's native controls (Claude Code
   permission rules and sandbox settings, Codex `workspace-write` config,
   Cursor `permissions.json`/`sandbox.json`) where each platform exposes a
   stable, documented mapping. Hooks remain the evidence recorder and fallback
   protector; native sandboxes add another boundary. Unsupported or ambiguous
   mappings fail closed rather than pretending the parser has been retired.
2. **Worktree isolation per work item** — SHIPPED as
   `palari agent start --isolate` (PR #13, 2026-07-16), with cross-worktree
   single-owner leases and worktree-portable evidence on top of it. The
   blueprint recommendation stands validated; remaining work is adoption in
   the daily loop, not construction.
3. **Push notifications for the approval inbox** — a notifier may close a UX
   gap, but it is an external write and therefore needs a separately approved
   integration plan, redaction contract, and human authority.
4. **Boundary simulation against the journal** — replay a proposed boundary
   or authority change against recorded history before adopting it (Cordum's
   best idea, powered by a journal Palari already has).

Not adopted, deliberately: memory systems, autonomy-first role simulation,
enterprise gateway infrastructure, or a proprietary attribution format.
Agent Trace is a promising early RFC to evaluate for emit/ingest compatibility.

## 8. Proposed PCAW v2 upgrades

Per v1, adding signing requires a versioned protocol decision. The candidate is
`pcaw.v2` with `predicateType: https://palari.dev/pcaw/v2`, not a bolt-on.
PCAW v1 compatibility must remain supported, but long-horizon verification
still depends on retaining the proof bytes, artifacts, algorithms, trust
material, and usable verifier implementations. Nothing below is normative
until a separately reviewed v2 specification and conformance corpus ship.

### 8.1 Signatures: DSSE envelope

Wrap the exact canonical statement bytes in a DSSE envelope:

```json
{
  "payload": "<Base64(canonical statement bytes)>",
  "payloadType": "application/vnd.palari.pcaw+json; version=2",
  "signatures": [{"keyid": "<key identifier>", "sig": "<Base64(signature)>"}]
}
```

The signature is computed over DSSE's pre-authentication encoding, **not**
the raw payload:

```text
PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
SP = 0x20; LEN = ASCII decimal byte length, no leading zeros
```

Verifiers MUST verify against PAE output and MUST NOT re-parse the envelope
after verification. Multiple signatures are supported natively — the
threshold/quorum hook (approver + org witness). Empty envelopes, placeholder
signatures, and inferred signers remain forbidden. The PCAW profile must bind
an **algorithm-suite identifier** inside the signed payload (or another
normatively signed location); the base DSSE envelope does not define one.

### 8.2 Signing backends and the trust topology

**Backend A — OpenSSH signatures (`ssh-keygen -Y`): a no-Python-dependency
candidate.** Lightweight signature operations were introduced experimentally
in OpenSSH 8.1; the `find-principals` operation used here arrived in 8.2. The
full proposed backend therefore requires OpenSSH 8.2 or newer. Git has supported
SSH commit signatures since Git 2.34.

```bash
# Sign (namespace is mandatory and fixed by the protocol)
ssh-keygen -Y sign -f ~/.ssh/id_ed25519 -n palari-work-receipt receipt.dsse

# Verify (exit 0 = verified)
ssh-keygen -Y verify -f allowed_signers -I dr.osei@stmarys.org \
  -n palari-work-receipt -s receipt.dsse.sig < receipt.dsse

# Who signed this?
ssh-keygen -Y find-principals -s receipt.dsse.sig -f allowed_signers
```

The trust root is an `allowed_signers` file — one line per identity:

```text
dr.osei@stmarys.org namespaces="palari-work-receipt",valid-after="20260101" ssh-ed25519 AAAAC3...
```

This file is the organization's signer registry: versionable, reviewable,
diffable — governable by Palari itself. Known SSHSIG limits, handled
explicitly: no timestamp inside the signature (§8.4 exists for that),
single-level CA only (`cert-authority` + SSH certificates), revocation via a
KRL file supplied at verification time.

**Backend B — Sigstore keyless: the identity-grade option.** OIDC login →
Fulcio issues a short-lived (~10 min) certificate binding an ephemeral key to
the identity claim → signature + certificate logged in Rekor:

```bash
cosign sign-blob receipt.dsse --bundle receipt.sigstore.json
cosign verify-blob receipt.dsse --bundle receipt.sigstore.json \
  --certificate-identity=dr.osei@stmarys.org \
  --certificate-oidc-issuer=https://login.microsoftonline.com/...
```

Caveat: public transparency services can expose signer identity metadata;
regulated deployments need an explicit privacy and trust design. A private
Sigstore-compatible deployment is one option, but it adds substantial
operational and key-custody responsibilities. Subprocess integration preserves
Palari's Python runtime dependency policy; it does not make the external tools
or services dependency-free.

**The trust topology, answered rather than gestured at:**

- *Who operates the certificate authority?* Backend A: nobody — trust is the
  org's reviewable `allowed_signers` registry. Backend B: the org's own
  Fulcio rooted in its IdP, or the public Sigstore CA when identities may be
  public.
- *What is the revocation story?* Backend A: KRLs plus `valid-before` windows
  checked under an explicit verification-time policy. Backend B: short-lived
  certificates reduce exposure but do not make compromise or revocation moot;
  verification still needs trusted issuance time, certificate/log evidence,
  identity policy, and a defined response to compromised IdP accounts.
- *What does "without trusting Palari" mean if Palari runs the log?* Palari
  MUST NOT be the only holder of anything. Log operators become auditable
  through authenticated inclusion and consistency proofs plus independently
  retained **witness heads**. Merely publishing a head is insufficient if the
  same operator controls every copy. Possible topologies include per-org logs
  with independent witnesses, public transparency logs, or user-run logs whose
  checkpoints are exported to other trust domains. A hosted Palari log would
  remain part of the trust model; the protocol should make equivocation
  detectable rather than claim the host is no longer trusted.

### 8.3 Presentation digest: proof of what the approver was shown

When approval is requested, Palari can create a canonical presentation
artifact from the Approval Pack, require the decision surface to bind its
action to that artifact, and record the digest in both the human decision and
receipt predicate. The digest alone proves the artifact bytes, not that a UI
rendered them. A "presented" claim additionally depends on the trusted decision
surface enforcing and recording that binding. Approval Packs already bind
exact evidence to exact decisions; this proposal adds the canonical projection
and presentation record. Competitive research must be refreshed before making
an exclusivity claim.

Precision requirement, binding on every description of this field: the digest
proves the presentation-artifact bytes. The trusted UI record supports a claim
that they were made available; neither proves what was displayed by compromised
client software, read, or understood. Attention is out of scope (§4).

### 8.4 Trusted time

SSHSIG carries no timestamp and self-declared timestamps prove nothing. An
RFC 3161 Time-Stamp Authority token is a third party's signed statement that
a given **hash** existed no later than a given time — only the digest is
sent, never content:

```bash
openssl ts -query -data receipt.dsse -sha256 -cert -no_nonce -out req.tsq
curl -s -H "Content-Type: application/timestamp-query" \
     --data-binary @req.tsq https://freetsa.org/tsr > receipt.tsr
openssl ts -verify -data receipt.dsse -in receipt.tsr \
     -CAfile cacert.pem -untrusted tsa.crt
```

Endpoint availability and policy change, so no public TSA is a protocol trust
default. Issuing a token requires a network call; validating an included token
can be offline when the bundle and verifier have the required certificate
chain and trust policy. Whether a missing token warns or fails is a declared
profile requirement, never a silent downgrade. OpenTimestamps is a possible
alternative trust model, not a "forever" guarantee; its verification and
availability assumptions must be stated explicitly.

### 8.5 Abstract subjects, lineage, revocation, agility

**Abstract subjects.** v1 subjects are files plus the virtual work-state.
Knowledge work is EHR entries, drafted letters, claim decisions, database
mutations. v2 generalizes the subject to any content-addressed artifact via
typed subject roles (e.g. `record`, `message`, `decision-artifact`), same
digest discipline. The hospital receipt and the pull-request receipt become
the same shape.

**Receipt lineage (Merkle DAG).** Optional `parent_receipts` list of
statement digests: a revision receipt cites what it supersedes; dependent
work cites prerequisites. The linear journal upgrades into git's actual
structure — a content-addressed DAG. A child pins parent digests, but a
verifier can validate ancestry only when the referenced parent statements are
also supplied or retrievable from a trusted store. The workspace
already models the sibling concept since PR #13: work items carry an explicit
fail-closed dependency DAG. WRP-6 lifts the same shape into the protocol
layer, so receipt lineage should mirror those dependency edges where they
exist.

**Revocation and supersession.** The workspace model already implements the
semantics — a later negative decision revokes an earlier approval,
contradictions fail closed. The protocol lifts them into statements: a
**revocation/supersession statement** citing the revoked receipt's digest,
signed under the same authority rules, logged like any receipt. Without current
revocation evidence, the old signature may remain cryptographically valid while
the decision's currency is unknown. This is the source of the
two-guarantees rule in §4: validity-at-signing offline; currency via log
query; reports name each separately.

**Algorithm agility.** Git hardcoded SHA-1 in 2005; the SHA-256 migration
has taken 15+ years and is unfinished. v2 specifies: the algorithm-suite
identifier in signed protocol data, the dual-digest transition procedure for a
successor algorithm, and the **re-anchoring procedure** — before a suite
weakens, retained original receipt bytes are re-anchored under a current suite.
Re-anchoring after the old primitive is already practically broken cannot
restore evidence that may already have been forged.

### 8.6 The shared append-only log

The local hash-chained journal provides tamper evidence relative to a trusted
checkpoint. A protocol upgrade could publish receipt digests to a transparency
log with authenticated inclusion and consistency proofs plus independent
witnesses. A git repository may be useful distribution and checkpoint
infrastructure, but review policy alone is not a cryptographic append-only
guarantee. The durable claim is narrower: supplied evidence can prove that a
receipt was included no later than a witnessed log state under the log's stated
trust assumptions.

## 9. Design lessons from git and its sibling protocols

Hold the protocol to the properties that made git unkillable; learn from the
protocols that lived and died around it:

- **The format is the product; implementations are guests.** Git the C
  program is one of many (JGit, gitoxide, go-git, Dulwich, isomorphic-git)
  because the bytes are the spec. Receipts should remain implementable from
  retained normative bytes and vectors. A future independent verifier would
  make portability testable; a year such as 2056 is an aspiration, not proof.
- **Plumbing vs. porcelain.** Git keeps low-level, forever-stable, scriptable
  commands separate from friendly UX; GitHub and every IDE exist because
  plumbing was stable. Palari exposes `canonicalize`, `digest`, envelope, and
  single-proof verification as stable plumbing under the CLI porcelain.
- **Correctness first, efficiency later.** Git shipped loose objects and
  added packfiles years later without changing semantics. Receipt storage
  efficiency is out of scope until the format is settled.
- **Certificate Transparency: logs earn trust by being watched.** CT works
  because independent monitors audit the logs — and CT won because browsers
  *required* it. Design the shared log for third-party monitors from day one;
  the adoption analogue of the browser mandate is §12's insurers and
  regulators, not developer enthusiasm.
- **TUF: assume key compromise, survive it.** The Update Framework's role
  separation, thresholds, rotation, and compromise recovery is the prior art
  for the signer-registry questions. Crib it; do not invent.
- **JWT/JOSE: ergonomics won, flaws were forever.** JWT conquered on
  developer ergonomics, then bled for a decade from envelope flaws
  (`alg: none`). DSSE exists because its authors studied those wounds — the
  reason it's the right envelope, and a warning that envelope mistakes cannot
  be patched later.
- **PGP: cryptographic soundness does not survive bad identity UX.** The web
  of trust illustrates the adoption cost of user-managed identity ceremonies.
  Organizational login is the preferred identity-grade path; local-key modes
  remain possible only with their weaker, explicit attribution semantics.
- **eIDAS: statutory effect is available under defined conditions.** Article
  25 gives a qualified electronic signature the equivalent legal effect of a
  handwritten signature. A generic SSH or Sigstore signature is not thereby a
  QES. Any qualifying backend would need separate legal, conformity, identity,
  and custody design.

## 10. Beyond code: documents, spreadsheets, and forms

Code was the incubator because git-shaped tooling already existed there. The
protocol's largest potential market may be knowledge work that has no git at
all. Three candidate principles carry receipts across:

**1. The snapshot principle.** Git never versions a live file; it commits a
snapshot. Live cloud documents (Google Docs, Sheets, Office online) have no
stable bytes — a Drive revision ID is a pointer into a mutable service, not a
proof. A receipt binds to a **content-addressed snapshot taken at decision
time**: the exported bytes (PDF, `.docx`, `.xlsx`, CSV) are the subject, and
their digest is what the signature covers. The snapshot is the commit. For
spreadsheets, digest both the file bytes and a canonical values export (CSV),
so a verifier can distinguish "the numbers changed" from "the formatting
changed."

**2. The field map is the diff.** A line diff is meaningless for a form. The
knowledge-work analog is a **field map** in the predicate: field → filled
value → source subject digest (and locator). "What was done" becomes "which
fields were filled, with what values, derived from which source documents."
The field map is itself canonical bytes with a digest, so evidence checks
(arithmetic, cross-field rules, eligibility tables) bind to it exactly.

**3. The case is the work item.** One person's matter — one tax return, one
discharge, one filing — is one work item. Sources are that person's
documents; the boundary is the named forms and fields the agent may fill;
evidence is the validation suite; the presentation is the review screen; the
decision is the signature. The existing lifecycle maps one-to-one; only new
subject types are needed (§8.5, WRP-6, WRP-11).

### Worked example: the international-student tax product

The concrete thought experiment this section is designed against is an app
where AI helps international students complete tax filings (for example, a US
federal nonresident return plus required attachments). No percentage of cases
is assumed simple without product-specific evidence. Building or integrating
that application is outside this repository and requires separate authority.

1. The student uploads source documents (wage statements, treaty forms,
   immigration documents). Each becomes a digested input subject. The work
   contract names exactly which forms and fields the AI may fill.
2. The AI extracts values and completes the forms. The field map records
   every filled field with its value and the digest of its source document.
   Validation evidence runs: arithmetic, cross-field consistency,
   treaty-table lookups.
3. The student sees the review screen: each filled field beside its source.
   The rendered view is digested — the presentation digest. The student
   approves; the signature covers the receipt binding contract, sources,
   field map, evidence, presented view, and the completed PDF's digest.
4. The receipt is anchored and logged. The student keeps the completed
   return *and* the receipt; the operator keeps only digests.

Why this case is a demanding protocol test rather than a product commitment:

- **The legal structure must be researched, not assumed.** Preparer status,
  attestation, professional duties, consumer-protection rules, and liability
  vary by jurisdiction and product behavior. A receipt may preserve useful
  evidence; it does not decide those questions or protect either party by
  itself.
- **The risk tiers may fit.** Mechanically bounded cases could use lighter
  gates only when validated evidence supports that classification; flagged
  cases — treaty edge cases,
  multiple states, unusual income — escalate to a credentialed human reviewer
  whose signature lands on the same receipt shape at a stricter gate.
- **Privacy is a design obligation, not a consequence of hashing.** Receipts
  should omit wage and immigration content, but their digests and metadata may
  remain guessable or linkable and require a domain privacy assessment.
- **It is intentionally outside this repository.** A real design partner or
  separately governed product could later test WRP-6 and WRP-11 assumptions;
  this blueprint creates no integration authority.

One honest design obligation: at consumer scale, the approval click is the
weakest link. The presentation digest proves what was shown, never what was
read (§4). The review UX must earn meaningful assent — per-field confirmation
for consequential values rather than one global "approve" — because the
receipt will faithfully record whichever standard of review the product
actually implements.

---

# Part IV — The strategy

## 11. Liability evidence: a design-partner hypothesis

The strongest demand for this protocol may come from parties who never run a
single Palari command, but that remains a hypothesis to test.

**Evidence is useful; allocation is jurisdiction-specific.** Provider terms
and professional duties often require human supervision, but their exact
effect varies by contract, profession, facts, and law. A presentation digest
can prove which bytes were made available; it cannot prove meaningful review,
attention, causation, or the legal allocation of responsibility.

**Receipts do not transfer or settle liability.** Model defects, operator
conduct, professional supervision, product claims, and contract terms may all
matter, and some duties may or may not be waivable. The protocol's narrower
job is to preserve tamper-evident facts that qualified counsel, courts,
regulators, insurers, and parties can evaluate.

**Neutrality can strengthen evidentiary credibility.** An open format,
independent verifier, explicit trust roots, and witnessed checkpoints reduce
the amount an auditor must accept from an interested operator. They do not make
the record automatically admissible, complete, or legally dispositive.

**Professional stamps are an analogy, not equivalence.** A professional
engineer's stamp operates inside licensing and legal regimes that a Palari
receipt does not create. The useful lesson is that explicit accountable assent
can make delegated work inspectable; the legal effect must never be borrowed
by metaphor.

**Insurers are a design-partner hypothesis.** Carriers and general counsel may
value consistent supervision evidence and may help define requirements. No
premium discount, underwriting value, or "litigation-grade" status is assumed
until validated by qualified partners and counsel.

**Claim-language rules (bind the marketing to these).** Never claim the
protocol removes, transfers, or shields from liability; proves meaningful
review; or makes evidence automatically admissible. The receipt is evidence in
both directions: it may support a diligent professional and may expose mass
approval. Approved phrasing: *tamper-evident, independently checkable evidence
of the governed work and recorded decision, under explicit trust assumptions.*

## 12. Regulatory tailwinds (stated precisely, because everyone misquotes them)

- **EU AI Act.** Article 12 requires high-risk AI systems to technically allow
  automatic event logging over the system lifetime. Article 19 requires
  providers to retain automatically generated logs under their control for an
  appropriate period of at least six months, unless other law provides
  otherwise; Article 26(6) gives deployers a similar minimum for logs under
  their control. The Regulation generally applies from **August 2, 2026**;
  Article 6(1) and corresponding obligations for Annex I product-safety
  systems apply from **August 2, 2027**. Classification and transitional rules
  are fact-specific. Palari can claim design alignment only after mapping the
  exact regulated role and requirement; it must not imply current users are
  automatically in scope or compliant.
- **HIPAA.** 45 CFR 164.312(b) requires mechanisms that "record and examine
  activity" in systems containing ePHI; the six-year retention clock in
  45 CFR 164.316(b)(2)(i) formally covers required documentation, and its
  extension to every audit log is an interpretation, not the literal text.
  A Palari receipt neither establishes HIPAA applicability nor compliance.
- **eIDAS** (§9): Article 25 states that a qualified electronic signature has
  the equivalent legal effect of a handwritten signature. Ordinary SSH and
  Sigstore signatures are not QES merely because they are cryptographic.
- **Design fit.** Omitting source content can reduce exposure, but hashes and
  metadata can remain personal, sensitive, or linkable. Retention and export
  require a domain-specific privacy, records, and legal assessment.

Adjacent prior art worth naming: C2PA binds signed provenance manifests to
content assets and its specification covers PDFs. It is a useful design
analogy, not proof that work receipts are novel or that the same security and
legal properties transfer automatically.

## 13. Adoption strategy and business model

The current emitter is this repository's CLI: it produces deterministic,
unsigned PCAW v1 proof statements. The current verifier is `palari proof
verify proof.json`. Signed v2 bundles and a static drop-a-receipt page are
proposals; the README must not present them as shipped until their conformance
and security limitations are proven.

1. **Verifier first.** The free, trivially installable artifact is `verify` —
   run it in CI, run it in an audit, exit 0 or 1. Producers follow verifiers,
   never the reverse.
2. **Dogfood where the tooling already lives.** The v2 target is for governed
   repository work to emit a signed receipt once signing and trust policy
   ship. Until then, dogfood must call the artifact an unsigned PCAW v1 proof.
3. **One design partner in a regulated niche** — a clinic, a law firm, an
   accounting practice, or (per §11) a professional liability carrier or
   general counsel. Any such work needs separate data, legal, privacy, and
   external-integration authority; this repository does not create it.
4. **Second implementation, early** (WRP-8). The moment another codebase
   passes the conformance corpus, this stops being a feature of Palari and
   becomes a protocol.
5. **Interoperate on attribution** — emit and ingest agent-trace; receipts
   answer authorization, agent-trace answers authorship.

**Business hypothesis:** keep the protocol, spec, verifier, and reference
implementation openly available, and keep basic verification independent of a
Palari account or service. Potential paid layers include hosted transparency
infrastructure, organizational identity policy, report packs, and supervision
surfaces. Comparable public-good infrastructure makes this shape plausible;
it does not prove Palari's demand, pricing, or ceiling.

## 14. Naming and positioning rules

- The sentence is **"Git, but for AI work."** (§1 explains why it is
  load-bearing.)
- The atom is a **receipt** — proof you keep, useful later, boring by design.
  Avoid "token": the v2 target is a content-addressed, signed statement with
  optional trusted-time and transparency evidence; "token" invites unrelated
  blockchain assumptions.
- "PCAW" remains the proposed spec lineage (v1 → v2); "Palari Work Receipt"
  is the candidate product name for a future signed artifact. Until v2 ships,
  call the current artifact an unsigned PCAW v1 proof. The target pitch is:
  *portable receipts of governed AI work, independently verifiable offline
  against explicit trust inputs.*

## 15. Risks

- **Platforms and governance toolkits ship overlapping receipts.** Microsoft's
  implemented receipt path already invalidates a category-empty claim.
  Mitigation: interoperate where possible and prove Palari's full-lifecycle
  semantics through conformance rather than relying on exclusivity.
- **Spec-in-a-vacuum.** A protocol with one implementer is a schema with a
  press release. Mitigation: independently authorize and validate WRP-8 and a
  design-partner program; neither is scheduled merely by appearing here.
- **Identity is the hard part.** Implementing a signature call is much easier
  than designing custody, recovery, verification time, and deciding whose
  signature counts is governance. Mitigation: the `allowed_signers` registry
  is itself a governed Palari artifact; the Sigstore path outsources identity
  to the org's existing IdP; the trust topology is specified (§8.2), not
  improvised.
- **Unproven buyer.** Open-source popularity does not establish a compliance
  buyer, and two company pivots do not prove a universal monetization rule.
  Validate buyer, budget, and evidence requirements before building hosted
  infrastructure.

---

# Part V — The build

## 16. Candidate implementation sequence

These entries are planning inputs, not agent instructions. Each must be
re-scoped against current repository truth and authorized as a separate work
item before code changes. Candidate ground rules: preserve the standard-library
Python core where justified (external executables are still dependencies);
fail closed on ambiguity; give failure modes stable diagnostic codes; land
conformance vectors with features; and preserve PCAW v1 compatibility. Expose
stable plumbing only after its contract is proven, and do not freeze an
unreviewed API prematurely.

**WRP-1 — DSSE envelope module.**
New `src/palari_company_os/dsse.py`: canonical envelope build/parse, exact
PAE construction, base64 handling, multi-signature support, algorithm-suite
identifier, rejection of empty/placeholder signatures.
Acceptance: round-trip property tests; PAE byte-exactness against the DSSE
spec strings; malformed-envelope rejection vectors with new codes
(`ENVELOPE_INVALID`, `SIGNATURE_MISSING`).

**WRP-2 — OpenSSH signing backend.**
New `src/palari_company_os/signing_ssh.py`: subprocess wrappers for
`ssh-keygen -Y sign|verify|find-principals`, fixed namespace
`palari-work-receipt`, `allowed_signers` read/validate helpers, KRL
revocation pass-through, structured errors when `ssh-keygen` is absent or
older than OpenSSH 8.2.
Acceptance: sign→verify round trip with a throwaway ed25519 key;
tampered-payload rejection; unknown-signer rejection (`SIGNER_UNTRUSTED`);
wrong-namespace rejection.

**WRP-3 — CLI: `proof sign` and signed verification.**
`palari proof sign FILE --key PATH --as HUMAN-ID` producing the DSSE bundle;
`palari proof verify` gains `--require-signature --allowed-signers FILE
--identity ID`. Unsigned v2 proofs verify structurally but report
`signature: absent` with an explicit warning. Structural inspection of an
unsigned v2 statement must never be reported as signed, authenticated, or
acceptance-valid under a profile that requires signatures.
Acceptance: exit-code contract preserved (0/1/2); report schema extended with
`signature_status`, signer principal, and the validity/currency split (§4);
CLI smoke tests.

**WRP-4 — Presentation digest.**
Define a canonical Approval Pack projection independent of browser layout and
font rendering; bind its digest
into the human decision record and the v2 predicate (`presented_digest`);
the verifier recomputes when that potentially sensitive projection is included
in the bundle, else reports `not-checked`. Bundle inclusion needs an explicit
privacy policy; the digest alone cannot prove the projection's contents to a
third party that does not possess them.
Acceptance: two visually identical packs with one changed evidence byte yield
different digests; v2 acceptance verification fails closed on decisions
missing a presentation digest (`PCAW_PRESENTATION_MISSING`).

**WRP-5 — RFC 3161 anchoring.**
`palari proof anchor FILE [--tsa URL]` via `openssl ts` subprocess; token
stored alongside the proof; `proof verify` checks an included token when
present. Absence warns only in an optional-time profile and fails in a profile
that requires trusted time; offline validation reports missing trust material
without silently downgrading.
Acceptance: request/verify round trip mocked in tests (no network in the test
suite); tampered-token rejection; documented trust-profile configuration with
no silently trusted public endpoint default.

**WRP-6 — Abstract subject classes and receipt lineage.**
Extend subject roles beyond `work-state`/`output-artifact` with typed
content-addressed subjects; update statement schema and path-safety rules
(non-file subjects have no path, only digests); pseudonymous-name rule for
regulated contexts (§3). Add the optional `parent_receipts` statement-digest
list (§8.5).
Acceptance: schema vectors per new role; unknown role rejection; lineage
round trip (child pins parent digest, tampered parent rejected); v1
statements still verify byte-identically.

**WRP-7 — spec/pcaw/v2 + conformance corpus.**
`spec/pcaw/v2/README.md` in the exact normative style of v1, answering the
reserved checklist (algorithm agility, key identity, revocation, threshold
policy, custody, verification time). Constraints: the digest-agility section
MUST define the algorithm-suite identifier, dual-digest transition, and
re-anchoring story; threshold/role/rotation MUST derive from TUF's model;
the revocation/supersession statement type MUST be specified under the same
authority rules as receipts; the report MUST separate validity-at-signing
from currency as distinct typed fields. Conformance vectors for signed,
unsigned, tampered, revoked, superseded, and threshold cases; the v1
black-box runner extended to v2.
Acceptance: `conformance.py -- ./bin/palari proof verify` passes the full v2
manifest; every new diagnostic code pinned in the manifest.

**WRP-8 — Second verifier (the protocol proof point).**
A separately maintained verifier in another language, sharing no Palari
implementation code and passing the applicable conformance corpus. Its scope
and size should follow the normative profile rather than an arbitrary line
budget, and its toolchain must not become a runtime dependency of Palari.

**WRP-9 — Sigstore backend + shared log (after design-partner input).**
`signing_sigstore.py` subprocess wrappers (`cosign sign-blob/verify-blob
--bundle`), private-Rekor deployment notes, witness-head publication, and the
receipt-digest publication command. Deliberately late: the piece a real
regulated design partner should shape.

**WRP-10 — The demo wedge: drop-a-receipt verifier page.**
First run a browser-compatibility spike against the chosen DSSE signature
suite, SSHSIG parsing, certificate policy, and RFC 3161 validation. WebCrypto
does not by itself guarantee portable support for the complete CLI profile.
Then build a static, no-upload verifier using only mechanisms that pass the
same vectors; unsupported checks must be explicit, never green by omission.
Acceptance: a self-contained `file://` page only if browser security policies
and the selected algorithms permit it; a tampered byte flips the relevant
check red; every unsupported or unchecked property is visible; parity claims
require the shared conformance corpus.

**WRP-11 — Knowledge-work predicate: snapshots and field maps.**
The §10 extensions: snapshot subjects (exported-bytes digesting for live
documents, dual file-bytes + canonical-values digests for spreadsheets) and
the canonical field-map structure (field → value → source subject digest →
locator) with its own digest bound into the predicate and coverable by
evidence checks.
Acceptance: field-map canonicalization vectors; changing one filled value
changes the field-map digest; a snapshot subject with no path verifies;
evidence bound to a stale field map fails closed (`PCAW_FIELD_MAP_STALE`).

Dependency order: WRP-1 → WRP-2 → WRP-3 form the critical path; WRP-4 and
WRP-5 are independent after WRP-1; WRP-6 and WRP-7 close the spec; WRP-8
tests portability; WRP-10 follows the compatibility spike and relevant
conformance work rather than automatically shipping after WRP-3; WRP-11
(depends on WRP-6) unlocks the knowledge-work products of §10; WRP-9 follows
the first external conversation.

---

# Appendices

## 17. The hospital vignette (the north star, end to end)

An AI drafts a discharge summary under a work contract: allowed sources, one
allowed output. Palari records the attempt, runs the evidence checks, and
assembles the Approval Pack. Dr. Osei reviews it; the exact rendered view is
digested. She approves; her org-issued identity signs the receipt; the
receipt's digest is anchored to a timestamp authority and appended to the
hospital's log. Total added human work: the review she was doing anyway.

Seven years later, an auditor holds the receipt, note, log proofs, retained
trust roots, and verification policy. On a laptop with no network or Palari
account, they can check artifact integrity, the signature and identity binding,
trusted-time evidence, and witnessed log consistency. Those checks provide
strong evidence of the recorded authorization, presentation, and decision.
They still rely on the trust roots, identity provider and log policy as of the
relevant time, retained bytes, and the truth of the source assertions; they do
not create mathematical certainty about clinical correctness or human
attention.

That is the target: work at AI speed with independently checkable
accountability evidence whose guarantees and trust assumptions survive the
ticket's surrounding context.

## 18. Glossary (plain language)

| Term | Plain meaning |
| --- | --- |
| Digest / hash | A public integrity fingerprint. It does not encrypt content and may reveal guessable or linkable inputs. |
| Canonical JSON | One fixed way to write the bytes of a JSON document, so equal statements are byte-equal (RFC 8785). |
| DSSE | A minimal, standard JSON envelope carrying a payload plus one or more signatures over it. |
| in-toto Statement | The standard "these artifacts, this claim" attestation shape the receipt uses. |
| SSHSIG | The signature format behind `ssh-keygen -Y`; what git uses for SSH-signed commits. |
| allowed_signers | A reviewable text file listing which keys speak for which identities — the trust registry. |
| Keyless signing | Sigstore's pattern: your org login mints a minutes-lived certificate; no long-lived key files. |
| RFC 3161 token | A third party's signed statement that a given fingerprint existed no later than a given time. |
| Transparency log | A log designed to provide authenticated inclusion and consistency evidence; equivocation detection requires independent checkpoints or witnesses. |
| Witness head | A retained, authenticated log checkpoint held in another trust domain and used to detect inconsistent histories. |
| Receipt | In proposed v2, a signed canonical statement binding contract, evidence, presented view, decision, and signer. PCAW v1 proofs are unsigned. |
| Snapshot | The exported bytes of a live document at decision time — what a receipt actually signs (the commit, for knowledge work). |
| Field map | The knowledge-work diff: which fields were filled, with what values, from which digested sources. |
| Presentation digest | The fingerprint of a canonical presentation artifact. A separate trusted UI record is needed to claim it was made available. |

## 19. Primary sources

Protocol and cryptography:

- PCAW v1: `spec/pcaw/v1/README.md` (this repository)
- DSSE: `github.com/secure-systems-lab/dsse` (`envelope.md`, `protocol.md`)
- in-toto Statement v1: `github.com/in-toto/attestation/spec/v1/statement.md`
- RFC 8785 (JCS): `rfc-editor.org/rfc/rfc8785`
- OpenSSH signatures: `man.openbsd.org/ssh-keygen`, `PROTOCOL.sshsig`, and
  official OpenSSH 8.1/8.2 release notes
- Sigstore blobs: `docs.sigstore.dev/cosign/signing/signing_with_blobs`
- RFC 3161: `rfc-editor.org/rfc/rfc3161`
- Certificate Transparency: `rfc-editor.org/rfc/rfc6962`
- The Update Framework: `theupdateframework.io`
- OpenTimestamps: `opentimestamps.org`

Regulatory:

- EU AI Act Articles 12, 19, 26, 113: official Regulation (EU) 2024/1689
  at `eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689`
- HIPAA: official HHS audit-control guidance and eCFR 45 CFR 164.312(b),
  164.316(b)(2)(i)
- eIDAS Article 25: consolidated Regulation 910/2014 at `eur-lex.europa.eu`
- C2PA specification 2.4: `spec.c2pa.org`

Market snapshot (last checked 2026-07-16; recheck before reliance):

- `microsoft/agent-governance-toolkit`, especially its official
  "Offline-Verifiable Decision Receipts" tutorial
- cordum-io/cordum; humanlayer/humanlayer; langchain-ai/agent-inbox
- git-ai-project/git-ai; cursor/agent-trace; radotsvetkov/soma;
  webaesbyamin/agent-receipts
- BloopAI/vibe-kanban; smtg-ai/claude-squad; conductor.build
- anthropic.com/engineering/claude-code-sandboxing;
  developers.openai.com/codex/concepts/sandboxing;
  cursor.com/docs/agent/security/run-modes
