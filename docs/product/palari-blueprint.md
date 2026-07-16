# The Palari Blueprint — Git, but for AI Work

One file, everything: the thesis, the verified evidence, the protocol design,
the strategy, and the implementation plan. Consolidated 2026-07-16 and
current against `main` at `0574b50` (opaque concurrent work items); this
document supersedes the earlier `competitive-landscape.md` and
`git-for-ai-work.md`. All market and technical claims were verified against
primary sources on 2026-07-15/16 (§19); star counts and endpoint liveness
drift — treat them as order-of-magnitude signals and recheck at deploy time.

Written to be handed to a coding agent work item by work item (§16).
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

> **Git, but for AI work.** A free protocol for signed receipts of
> AI-executed work — what was done, what the human was shown, and who signed
> it — verifiable offline, forever, by anyone, without trusting the operator,
> the AI vendor, or Palari.

Git records **content history**: what bytes changed, who committed. Palari
records **authority history**: what the agent was allowed to do, what
evidence the human was presented, who approved, and when. That distinction
answers "doesn't git already do this?" — and points at the largest market:
the knowledge work that has no git at all. The nurse approving an AI-drafted
medication note, the paralegal accepting an AI-drafted filing, the student
signing an AI-completed tax return.

The sentence is load-bearing. It names the object (permanent verifiable
record), the architecture (content-addressed, offline, no central authority),
the business model (free protocol, paid hosting — the GitHub move), and the
adoption path (useful to one person on day one, network effects later).

## 2. The machine in four primitives

Nothing here is novel cryptography. It composes four decades-old,
battle-tested primitives — the same ones securing git, HTTPS, and app stores.
What is novel is the statement they attest to.

1. **Fingerprints (hashes).** SHA-256 turns any content into a short digest.
   Same content, same digest; one changed byte, different digest; the digest
   reveals nothing about the content. This is why receipts can reference
   patient data without containing any.
2. **Statements (canonical JSON).** The receipt is a small JSON document full
   of digests, serialized canonically (RFC 8785) so the same logical
   statement always produces the exact same bytes — which lets the statement
   itself be fingerprinted, signed, and logged.
3. **Signatures.** A private key produces a signature over the statement's
   bytes; anyone with the public key verifies it. Identity binding — proving
   the key belongs to a real person in a real organization — comes from the
   organization's existing login system, not key files on laptops.
   Concretely: an OIDC login mints a short-lived signing certificate bound to
   the authenticated identity claim (the Sigstore pattern, §8.2).
4. **Append-only logs.** Each entry's hash chains to the previous one, so
   nothing can be inserted, backdated, or removed without visibly breaking
   the chain. This answers "since when?" and "can it quietly disappear?".

The verifier's job is three checks, offline, with standard tools: digests
match, signature verifies, log entry intact. If all pass, a stranger a decade
from now knows what was done, what the human was shown, who signed, and when
— without the original workspace, provider, network, or source contents.
Trust comes from math anyone can re-run, not from an institution's word.

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

**Privacy invariants.** Digests, never content: a receipt must remain safe to
retain, export, and show an auditor in a domain where the underlying data
(patient records, privileged filings) must not travel with it. v2 extends the
rule to names: filenames are metadata, and metadata leaks
("discharge-summary-4412.pdf" in a receipt is itself a disclosure). In
regulated contexts subject names MUST be pseudonymous role labels or digest
prefixes; the pseudonym-to-artifact mapping lives with the operator, outside
the receipt.

## 4. What a receipt does NOT prove (keep this section forever)

- A signature proves an authenticated identity approved the statement; it
  does not prove the judgment was good, the evidence sufficient, or the work
  semantically correct.
- The presentation digest proves what was **presented** — bytes rendered
  available to the approver — never what was read or understood. Attention is
  out of scope for v2. Auditors find overclaims in minutes; precision here is
  credibility everywhere else.
- Receipts record and attribute; they do not prevent. A bad approval still
  happens — it becomes permanently attributable, which changes behavior the
  way cameras change driving. In regulated domains attributability *is* the
  product; do not oversell it as safety.
- Identity binding is as strong as the identity provider behind it. A key on
  a laptop proves possession of a laptop; an OIDC-bound short-lived
  certificate proves an authenticated login. State which one a receipt
  carries.
- Trusted timestamps prove existed-no-later-than, not existed-no-earlier-than.
- **Two guarantees, never conflated:** offline verification proves
  **validity-at-signing** (well-formed, signed, consistent when made).
  **Currency** — is this still the latest decision, or was it superseded or
  revoked? — requires a log query (§8.6). Verifier reports state each
  separately; neither is ever implied by the other, and marketing MUST NOT
  promise the second while delivering the first.

---

# Part II — The evidence

## 5. Where Palari stands today

From the full code-level evaluation of this repository (2026-07-15): the
engineering is real — 719 passing tests, zero runtime dependencies, a working
offline demo, live hook enforcement (it blocked the evaluating agent's own
out-of-contract command mid-evaluation), and unusually honest threat-model
documentation. The weaknesses are equally real: the shell-parsing enforcement
in the Claude hooks is an arms race the OS sandbox wins categorically, and
the governance ontology buries the wedge. Both weaknesses are answered by
this blueprint: ride the platforms' native sandboxes (§8, §9) and lead with
the receipt protocol.

PCAW v1 (`spec/pcaw/v1/`) is further along as a protocol than a casual
reading suggests. Already shipped and tested:

- **Standard envelope.** Statements are in-toto Statement v1 objects with
  `predicateType: https://palari.dev/pcaw/v1` — the industry-standard
  attestation shape, ready for DSSE wrapping.
- **Canonical bytes.** Strict I-JSON + RFC 8785 canonicalization, floats
  forbidden, duplicate keys rejected, deterministic export (no export time,
  no absolute paths, no locale text). Identical logical input produces
  identical bytes on any machine. Fortunate consequence of the no-floats
  rule: for integer-only documents, Python's stdlib
  `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)` is
  RFC 8785-conformant (the two stdlib divergences — ECMAScript float
  formatting, and UTF-16 vs code-point key ordering — arise only with floats
  and with keys mixing U+E000–U+FFFF against supplementary planes; guard the
  latter with `key=lambda k: k.encode("utf-16-be")`).
- **Offline verification with a stable contract.** `palari proof export` /
  `palari proof verify`, exit codes 0/1/2, ~35 stable diagnostic codes,
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

What v1 deliberately lacks — the v2 work: signatures and identity, proof of
what was presented to the approver, trusted time, non-file subjects,
revocation statements, and a shared append-only log.

## 6. The verified competitive landscape

Two independent research passes (2026-07-15), every repository and product
verified to exist; unverifiable candidates excluded.

**Native platform controls — the commoditization front.** Claude Code ships
an OS-enforced sandbox (Seatbelt / bubblewrap + seccomp; runtime open-sourced
as `anthropic-experimental/sandbox-runtime`), declarative permission rules,
and pre/post tool-call hooks. OpenAI Codex has independent `sandbox_mode` and
`approval_policy` dials, enforced via Seatbelt / bwrap / Landlock. Cursor 2.5
sandboxes Shell/MCP/Fetch and routes them through an allowlist → sandbox →
classifier-subagent pipeline — automating the human approver itself. Raw
write-boundary enforcement is free, native, and improving: a substrate to
ride, not a moat.

**Human-in-the-loop approval layers.** HumanLayer (11.1k★, YC F24) built
approval-before-sensitive-tool-calls over Slack/email — then **deprecated its
SDK** and pivoted to Claude Code orchestration; standalone approval APIs got
squeezed by framework-native HITL (LangGraph interrupts, OpenAI Agents SDK).
gotoHuman does structured review forms; impri (new, 2026) does an approval
inbox with bulk decisions and push notifications. Lesson: simple approval
gates commoditize; structured, evidence-bound review does not.

**Action firewalls / policy engines / gateways.** Microsoft Agent Governance
Toolkit (4.9k★, public preview): YAML/OPA/Cedar policies intercepting every
tool call, zero-trust agent identity, Merkle audit logs mapped to OWASP/NIST/
EU-AI-Act/SOC 2 — and its "Independently Verifiable Compliance Receipts," the
nearest analogue to PCAW, is an **unshipped draft proposal**. Cordum (490★):
pre-execution YAML gating with a policy simulator over historical data.
Invariant Labs was acquired by Snyk within a year — firewall tech is being
absorbed into incumbents. Docker MCP Gateway, IBM ContextForge, Lasso: all
require containers, proxies, or servers. Zero-infra local-first is
structurally differentiated against this entire tier.

**Audit / receipts / provenance.** Git AI (~2k★): line-level AI attribution
in Git Notes — records *who wrote what*, not *whether the work was governed*;
complementary. Agent Trace spec (cursor/agent-trace, 772★, supported by
Anthropic, OpenAI, Google, Vercel, Cognition): the attribution *format* is
being standardized jointly by the platforms — interoperate with it, never
compete on it. soma (2★, Rust): hash-chained journal, RFC 3161 anchoring,
in-toto attestations, EU AI Act Article 12 exports — the closest
philosophical neighbor, worth studying. agent-receipts (1★): Ed25519-signed
per-action receipts, explicitly proof-not-prevention. SLSA / in-toto /
Sigstore: mature signed provenance for *build artifacts* — the substrate to
adapt, not reinvent.

**Work orchestration / task isolation.** Vibe Kanban (27.4k★): kanban issues
→ one git worktree per agent task → diff review; category-defining adoption,
company shut down April 2026. Claude Squad (8.1k★), Conductor (commercial):
same worktree-per-task pattern. **None carries an enforceable task contract**
— a machine-readable assignment boundary tied to briefs, approvals, and
required evidence. That is Palari's unoccupied ground.

**Commoditized (do not compete):** OS-level write/network boundaries; basic
approval prompts; hook/policy insertion points; AI-code attribution formats.

**Open gaps an independent tool can own:**

1. **Offline-verifiable proof of governed work** — signed, hash-chained,
   third-party-verifiable receipts binding policy → approval → action →
   result. Nothing shipped; Microsoft's is a draft; gateways offer
   operator-trusted SaaS logs.
2. **Task-contract semantics** — per-work-item scoped boundaries portable
   across Claude Code, Codex, and Cursor.
3. **The enforcement-to-evidence bridge** — platforms enforce but emit no
   portable evidence; provenance tools record but don't enforce. Nobody does
   both in one loop.
4. **Local-first, zero-infra deployment** — every competitor in the policy/
   gateway tier requires containers, a database, or a SaaS tenant.

**The two market lessons that shape strategy:** Vibe Kanban died at 27k stars
and HumanLayer pivoted away from its own SDK — developer-experience
governance does not monetize; compliance-driven governance can. And adoption
law, borrowed from git: the protocol must be useful to one team on day one,
alone, offline, with nobody else's permission.

---

# Part III — The design

## 7. Adaptations into the current product (pre-protocol)

Ordered by leverage; independent of the v2 protocol work:

1. **Become the contract compiler, not just the enforcer.** Compile the
   packet write boundary into each platform's native controls (Claude Code
   permission rules and sandbox settings, Codex `workspace-write` config,
   Cursor `permissions.json`/`sandbox.json`). Hooks remain the evidence
   recorder and governance protector; the OS sandbox blocks. This retires
   the shell-parsing arms race.
2. **Worktree isolation per work item** — SHIPPED as
   `palari agent start --isolate` (PR #13, 2026-07-16), with cross-worktree
   single-owner leases and worktree-portable evidence on top of it. The
   blueprint recommendation stands validated; remaining work is adoption in
   the daily loop, not construction.
3. **Push notifications for the approval inbox** — Approval Packs already
   exceed competitors' bulk-approval semantics; a webhook notifier for
   pending decisions closes the UX gap.
4. **Boundary simulation against the journal** — replay a proposed boundary
   or authority change against recorded history before adopting it (Cordum's
   best idea, powered by a journal Palari already has).

Not adopted, deliberately: memory systems, autonomy-first role simulation,
enterprise gateway infrastructure, or a proprietary attribution format
(agent-trace won that race — emit and ingest it instead).

## 8. PCAW v2: the upgrades

Per v1, adding signing is a versioned protocol decision: this is `pcaw.v2`
with `predicateType: https://palari.dev/pcaw/v2`, never a bolt-on. v1 stays
frozen; v1 statements remain verifiable forever. All technical details below
verified against primary sources.

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
signatures, and inferred signers remain forbidden. Every envelope carries an
**algorithm-suite identifier** (§8.5).

### 8.2 Signing backends and the trust topology

**Backend A — OpenSSH signatures (`ssh-keygen -Y`): the zero-dependency
default.** Available since OpenSSH 8.1 (2019); the machinery git itself uses
for `gpg.format=ssh` since Git 2.34.

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

Caveat: the public-good Rekor makes signer identities public; regulated
deployments run a private stack (`sigstore/scaffold` deploys Rekor + Fulcio +
Trillian in-house). Both backends run as subprocesses — stdlib-only holds.

**The trust topology, answered rather than gestured at:**

- *Who operates the certificate authority?* Backend A: nobody — trust is the
  org's reviewable `allowed_signers` registry. Backend B: the org's own
  Fulcio rooted in its IdP, or the public Sigstore CA when identities may be
  public.
- *What is the revocation story?* Backend A: KRLs plus `valid-before` windows
  checked at verification time. Backend B: certificates live minutes, so key
  revocation is largely moot; identity revocation is the IdP's account
  lifecycle, which the org already operates.
- *What does "without trusting Palari" mean if Palari runs the log?* Palari
  MUST NOT be the only holder of anything. Verification never calls a Palari
  service; logs are org-run or public, never Palari-only; log operators are
  kept honest by **published witness heads** — the log's current head hash
  signed and published where the operator cannot rewrite it (a public log,
  another org's log, or a git repository others clone). Acceptable
  topologies: per-org log with published witness heads, public transparency
  log, or user-run log. "Palari hosts your log" is a convenience tier, valid
  only because witness heads make the host verifiable rather than trusted.

### 8.3 Presentation digest: proof of what the approver was shown

The highest-value, least-built field in the industry. When approval is
requested, Palari renders the evidence view (the Approval Pack content),
emits it as canonical bytes, digests it, and binds that digest into both the
human decision record and the receipt predicate. The claim upgrades from "she
approved the work" to "she approved the work **having been presented exactly
this**." Approval Packs already bind exact evidence to exact decisions; this
adds one canonical rendering step and one digest field. No verified
competitor records this.

Precision requirement, binding on every description of this field: the
digest proves what was **presented** — bytes rendered available — not what
was read or understood. Attention is out of scope for v2 (§4).

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

Free endpoints verified: freetsa.org/tsr, timestamp.digicert.com,
timestamp.sectigo.com, ts.ssl.com. Anchoring is the one optional network
touch in the protocol; it MUST degrade to a structured warning offline, and
the token travels with the proof bundle so verification stays offline.
Candidate second backend for the longest horizons: OpenTimestamps (hashes
aggregated into Bitcoin blocks — verifiable forever with no TSA certificate
chain that must survive decades).

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
structure — a content-addressed DAG — so verifying one receipt transitively
pins its ancestry, and parallel workstreams merge verifiably. The workspace
already models the sibling concept since PR #13: work items carry an explicit
fail-closed dependency DAG. WRP-6 lifts the same shape into the protocol
layer, so receipt lineage should mirror those dependency edges where they
exist.

**Revocation and supersession.** The workspace model already implements the
semantics — a later negative decision revokes an earlier approval,
contradictions fail closed. The protocol lifts them into statements: a
**revocation/supersession statement** citing the revoked receipt's digest,
signed under the same authority rules, logged like any receipt. Without it, a
revoked acceptance verifies "valid forever." This is the source of the
two-guarantees rule in §4: validity-at-signing offline; currency via log
query; reports name each separately.

**Algorithm agility.** Git hardcoded SHA-1 in 2005; the SHA-256 migration
has taken 15+ years and is unfinished. v2 specifies: the algorithm-suite
identifier on every envelope, the dual-digest transition procedure for a
successor algorithm, and the **re-anchoring procedure** — before a suite
weakens, existing receipts are re-timestamped under a current suite,
preserving proof-of-existence across algorithm generations.

### 8.6 The shared append-only log

The local hash-chained journal already provides tamper evidence on one
machine. The protocol upgrade publishes receipt digests to an append-only log
outside the operator's unilateral control — a private Rekor, or initially a
dedicated git repository of receipt digests (append-only by review policy,
hash-chained by construction) — with witness heads per §8.2. That entry is
the permanent "this existed, then" record: the token that lives forever,
without any blockchain.

## 9. Design lessons from git and its sibling protocols

Hold the protocol to the properties that made git unkillable; learn from the
protocols that lived and died around it:

- **The format is the product; implementations are guests.** Git the C
  program is one of many (JGit, gitoxide, go-git, Dulwich, isomorphic-git)
  because the bytes are the spec. Receipts must verify in 2056 with whatever
  runs then. WRP-8's independent verifier makes this testable.
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
  of trust failed socially. Identity rides the org's existing login, never
  user-managed key ceremonies.
- **eIDAS: statutory weight is available.** EU-qualified electronic
  signatures carry a legal presumption of validity; a qualifying backend
  would give receipts evidentiary force in the EU by statute. Future work;
  the custody section keeps the door open.

## 10. Beyond code: documents, spreadsheets, and forms

Code was the incubator because git-shaped tooling already existed there. The
protocol's real market is the knowledge work that has no git at all. Three
principles carry receipts across:

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

The concrete case this section is designed against: an app where AI helps
international students complete their tax filings (e.g. a US federal
nonresident return plus required attachments), where an estimated 80–90% of
cases are mechanically simple form completion.

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

Why this case is protocol-perfect rather than merely protocol-compatible:

- **The liability structure demands it.** Consumer tax software operates on
  the self-preparation model: the taxpayer is the preparer and attests to the
  return. The receipt is the missing evidence layer for exactly that
  attestation — protecting the operator ("the AI filed it wrong" meets the
  record of what was shown and signed) and the student (a good-faith
  diligence record, with sources). §11 in miniature.
- **The risk tiers already fit.** The 80–90% simple cases are light-gate
  self-approval with full evidence; flagged cases — treaty edge cases,
  multiple states, unusual income — escalate to a credentialed human reviewer
  whose signature lands on the same receipt shape at a stricter gate.
- **Privacy is by construction.** Receipts carry digests, never wage or
  immigration data.
- **It is the first product built on the protocol rather than a feature of
  this repository** — the design-partner requirement satisfied first-party:
  the app's real cases force WRP-6 and WRP-11's requirements before any
  external partner is needed.

One honest design obligation: at consumer scale, the approval click is the
weakest link. The presentation digest proves what was shown, never what was
read (§4). The review UX must earn meaningful assent — per-field confirmation
for consequential values rather than one global "approve" — because the
receipt will faithfully record whichever standard of review the product
actually implements.

---

# Part IV — The strategy

## 11. The liability engine: why labs and insurers want this to exist

The strongest demand for this protocol may come from parties who never run a
single Palari command.

**The allocation already exists on paper; the evidence does not.** Every
provider's terms say the user is responsible for reviewing outputs.
Professional-responsibility rules agree: bar guidance treats generative AI
like nonlawyer assistance the attorney must supervise, and when
AI-hallucinated citations reached a court, sanctions fell on the lawyer, not
the model provider. Medicine, engineering, and accounting run on the same
rule. What is missing at AI velocity is not the allocation of responsibility
but the **evidence infrastructure that makes it provable**. A
terms-of-service disclaimer is weak protection when nobody can show whether a
specific output was meaningfully reviewed. A signed receipt with a
presentation digest shows it exactly.

**Receipts do not transfer liability; they make the existing line crisp.**
Liability for model defects — a defective model, a misrepresented capability
— stays with the provider and cannot be contracted away. What the receipt
separates cleanly is the layer above: supervision and acceptance, which
provably rest with the professional who signed. Today every incident smears
those layers together; both sides want the line crisp, because the fight
about where it falls costs more than either side's share of it.

**Neutrality is a legal requirement, not a positioning choice.** A
liability-relevant record system run by an interested party is worthless as
evidence — no court credits the fox's ledger of the henhouse. The record
layer must be free, open, and verifiable without trusting any provider,
operator, or Palari itself. The labs have already shown they will back
neutral formats they cannot own (agent-trace); a neutral receipt protocol is
the same move one layer up, where the stakes are legal rather than
attributional.

**The precedent is the professional engineer's stamp.** Society already
solved "one accountable human answers for work they did not personally
perform": the PE stamps the drawings, and the stamp is what makes bridges
buildable and insurable. A Palari receipt is the PE stamp for AI work, with
cryptographic teeth.

**Insurers are the adoption engine.** Professional liability carriers must
price AI-assisted work today with no underwriting data and no defense
evidence. Receipts supply both: proof that a firm reviews what it signs, and
litigation-grade evidence of meaningful supervision. A carrier that discounts
premiums for receipt-governed AI work creates a forcing function stronger
than any developer marketing — the mechanism that spread seatbelts,
sprinklers, and secure-by-default IT. It also sharpens the design-partner
search: a malpractice carrier or a firm's general counsel may be a better
first partner than any single clinic or firm.

**Claim-language rules (bind the marketing to these).** Never claim the
protocol "removes" or "shields from" liability — it is not legally true, and
the buyers who matter (general counsel, insurers, regulators) spot the
overclaim in one sentence and discount everything else. The receipt is
evidence in both directions: it protects the professional who genuinely
reviewed and exposes the one who rubber-stamped a thousand approvals in an
hour. That double edge is the honest product. Approved phrasing: *clean,
provable allocation of responsibility — protection for the diligent, by
construction.*

## 12. Regulatory tailwinds (stated precisely, because everyone misquotes them)

- **EU AI Act.** Article 12 requires high-risk AI systems to technically
  allow automatic event logging; Article 19 (providers) and Article 26(6)
  (deployers) require keeping those logs at least six months. Applicability:
  the general high-risk regime for Annex III systems applies from
  **August 2, 2026**; high-risk AI embedded in Annex I regulated products
  (medical devices, machinery) from **August 2, 2027**. Honesty note: a
  general-purpose coding agent is unlikely to be classified high-risk — cite
  Article 12 as an alignment target the protocol satisfies by construction,
  not as an obligation Palari's current users bear.
- **HIPAA.** 45 CFR 164.312(b) requires mechanisms that "record and examine
  activity" in systems containing ePHI; the six-year retention clock in
  45 CFR 164.316(b)(2)(i) formally covers required documentation, and its
  extension to audit logs is standard industry interpretation — phrase it
  that way.
- **eIDAS** (§9): qualified electronic signatures carry statutory presumption
  of validity in the EU — a future signing-backend target.
- **Design fit.** Digest-only receipts are retainable and exportable in these
  regimes precisely because they carry no protected content.

Adjacent prior art worth naming: C2PA binds signed provenance manifests to
media files (its spec covers PDFs); nobody has applied the pattern to work
records — a design analogy proving the pattern scales, not a competitor.

## 13. Adoption strategy and business model

The wedge, concretely: the **first emitter** is this repository's CLI (it
already produces receipts) plus the Claude Code hook layer; the **first
verifier** is `palari proof verify receipt.json` plus the static
drop-a-receipt page (WRP-10) where anyone sees the three checks go green.
That pair is the README hero — the blocked-write demo carried this repo, and
this demo carries the protocol.

1. **Verifier first.** The free, trivially installable artifact is `verify` —
   run it in CI, run it in an audit, exit 0 or 1. Producers follow verifiers,
   never the reverse.
2. **Dogfood where the tooling already lives.** Every merged work item in
   this repository ships with its own signed receipt; each receipt doubles as
   a demo. Code is not the biggest market, but it is where the first thousand
   users already run agents all day.
3. **One design partner in a regulated niche** — a clinic, a law firm, an
   accounting practice, or (per §11) a professional liability carrier or
   general counsel; the tax product (§10) fills this role first-party. Their
   auditor becomes the requirements document.
4. **Second implementation, early** (WRP-8). The moment another codebase
   passes the conformance corpus, this stops being a feature of Palari and
   becomes a protocol.
5. **Interoperate on attribution** — emit and ingest agent-trace; receipts
   answer authorization, agent-trace answers authorship.

**Business shape:** the protocol, spec, verifier, and reference
implementation are free forever — the moment verification requires Palari's
servers or accounts, the git analogy becomes false and trust evaporates.
Revenue lives above the protocol: hosted transparency logs (kept honest by
witness heads), organizational identity binding against corporate IdPs,
compliance report packs, and supervision surfaces. Let's Encrypt and Sigstore
prove the shape; GitHub proves the ceiling.

## 14. Naming and positioning rules

- The sentence is **"Git, but for AI work."** (§1 explains why it is
  load-bearing.)
- The atom is a **receipt** — proof you keep, useful later, boring by design.
  Avoid "token": technically it is a content-addressed, signed statement
  anchored in an append-only log; "token" invites blockchain readings that
  add baggage and subtract trust.
- "PCAW" remains the spec lineage (v1 → v2); "Palari Work Receipt" is the
  product name of the signed artifact. The pitch stays one sentence: *a free
  protocol for signed receipts of AI-executed work — what was done, what the
  human was shown, and who signed it, verifiable offline forever.*

## 15. Risks

- **Platforms ship native signed session logs.** Their joint backing of
  agent-trace shows appetite for shared formats. Mitigation: interoperate
  early; own the layer they structurally cannot — binding contract, presented
  evidence, and human authority across platforms, held by a neutral party
  (§11 makes neutrality a feature they need, not a weakness).
- **Spec-in-a-vacuum.** A protocol with one implementer is a schema with a
  press release. Mitigation: WRP-8 and the design partner are scheduled work.
- **Identity is the hard part.** Signing is a weekend; deciding whose
  signature counts is governance. Mitigation: the `allowed_signers` registry
  is itself a governed Palari artifact; the Sigstore path outsources identity
  to the org's existing IdP; the trust topology is specified (§8.2), not
  improvised.
- **DX-buyer trap.** Developer-experience governance does not monetize (Vibe
  Kanban, HumanLayer). Keep the developer wedge free and frictionless; aim
  the commercial layer at those who must evidence their AI work.

---

# Part V — The build

## 16. Implementation plan (written for a coding agent)

Ground rules for every work item: Python stdlib only (external tools invoked
as subprocesses: `ssh-keygen`, `openssl`, `cosign`); fail closed on anything
ambiguous; every new failure mode gets a stable diagnostic code; conformance
vectors land in the same work item as the feature; v1 behavior is never
modified — v2 is additive. New primitives are exposed as stable plumbing
(canonicalize, digest, envelope, verify-one) beneath the porcelain CLI, and
their CLI contracts are frozen once shipped. Each item is sized to be one
bounded work item with its own boundary, evidence, and review.

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
older than OpenSSH 8.1.
Acceptance: sign→verify round trip with a throwaway ed25519 key;
tampered-payload rejection; unknown-signer rejection (`SIGNER_UNTRUSTED`);
wrong-namespace rejection.

**WRP-3 — CLI: `proof sign` and signed verification.**
`palari proof sign FILE --key PATH --as HUMAN-ID` producing the DSSE bundle;
`palari proof verify` gains `--require-signature --allowed-signers FILE
--identity ID`. Unsigned v2 proofs verify structurally but report
`signature: absent` with an explicit warning.
Acceptance: exit-code contract preserved (0/1/2); report schema extended with
`signature_status`, signer principal, and the validity/currency split (§4);
CLI smoke tests.

**WRP-4 — Presentation digest.**
Canonical rendering of the Approval Pack evidence view to bytes; digest bound
into the human decision record and the v2 predicate (`presented_digest`);
verifier recomputes when the presented view is included in the bundle, else
reports `not-checked`.
Acceptance: two visually identical packs with one changed evidence byte yield
different digests; v2 acceptance verification fails closed on decisions
missing a presentation digest (`PCAW_PRESENTATION_MISSING`).

**WRP-5 — RFC 3161 anchoring.**
`palari proof anchor FILE [--tsa URL]` via `openssl ts` subprocess; token
stored alongside the proof; `proof verify` checks an included token when
present, warns (never fails) when absent; offline degradation is a structured
warning.
Acceptance: request/verify round trip mocked in tests (no network in the test
suite); tampered-token rejection; documented endpoint list.

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
A minimal independent verifier (different language, e.g. Go or TypeScript,
~300 lines, statement-only + signature check) under `spec/pcaw/v2/`, passing
the same conformance corpus with zero shared code. A protocol with one
implementation is a schema; this makes it two.

**WRP-9 — Sigstore backend + shared log (after design-partner input).**
`signing_sigstore.py` subprocess wrappers (`cosign sign-blob/verify-blob
--bundle`), private-Rekor deployment notes, witness-head publication, and the
receipt-digest publication command. Deliberately late: the piece a real
regulated design partner should shape.

**WRP-10 — The demo wedge: drop-a-receipt verifier page.**
A single static HTML page (no server, no upload — verification runs
in-browser via WebCrypto) where anyone drops a receipt bundle and sees the
three checks go green: digests match, signature verifies, anchor intact. Plus
the README hero: emit a signed receipt from this repository's own workflow,
verify it on the page.
Acceptance: page fully self-contained (works from `file://`); a tampered byte
flips the relevant check red with the stable diagnostic code; linked from the
README next to a `palari proof verify` one-liner.

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
proves it; WRP-10 ships the public demo as soon as WRP-3 exists; WRP-11
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

Seven years later, an auditor holds three things: the receipt, the note, and
the log. On a laptop with no network, no Palari account, and no access to any
patient record beyond this note, they verify: digests match, signature chains
to the hospital's identity provider, log entry intact and in sequence. They
now know what the AI was allowed to do, what it produced, what Dr. Osei was
presented, that she approved it, and when — with mathematical certainty and
zero trust in the hospital's IT department, the AI vendor, or us.

That is the product. Work at AI speed, accountability at cryptographic
strength, and a record that outlives everyone's memory of the ticket.

## 18. Glossary (plain language)

| Term | Plain meaning |
| --- | --- |
| Digest / hash | A fingerprint of content: same content, same fingerprint; reveals nothing about the content. |
| Canonical JSON | One fixed way to write the bytes of a JSON document, so equal statements are byte-equal (RFC 8785). |
| DSSE | A minimal, standard JSON envelope carrying a payload plus one or more signatures over it. |
| in-toto Statement | The standard "these artifacts, this claim" attestation shape the receipt uses. |
| SSHSIG | The signature format behind `ssh-keygen -Y`; what git uses for SSH-signed commits. |
| allowed_signers | A reviewable text file listing which keys speak for which identities — the trust registry. |
| Keyless signing | Sigstore's pattern: your org login mints a minutes-lived certificate; no long-lived key files. |
| RFC 3161 token | A third party's signed statement that a given fingerprint existed no later than a given time. |
| Transparency log | An append-only, hash-chained record; nothing can be inserted, removed, or backdated invisibly. |
| Witness head | The log's current head hash, signed and published where the log operator cannot rewrite it. |
| Receipt | One signed, canonical statement binding contract, evidence, presented view, decision, and signer. |
| Snapshot | The exported bytes of a live document at decision time — what a receipt actually signs (the commit, for knowledge work). |
| Field map | The knowledge-work diff: which fields were filled, with what values, from which digested sources. |
| Presentation digest | The fingerprint of exactly what was rendered to the approver at decision time. |

## 19. Primary sources

Protocol and cryptography:

- PCAW v1: `spec/pcaw/v1/README.md` (this repository)
- DSSE: github.com/secure-systems-lab/dsse (envelope.md, protocol.md)
- in-toto Statement v1: github.com/in-toto/attestation (spec/v1/statement.md)
- RFC 8785 (JCS): rfc-editor.org/rfc/rfc8785
- OpenSSH signatures: man.openbsd.org/ssh-keygen; PROTOCOL.sshsig; release
  notes 8.1/8.2
- Sigstore blobs: docs.sigstore.dev/cosign/signing/signing_with_blobs
- RFC 3161: rfc-editor.org/rfc/rfc3161
- Certificate Transparency: rfc-editor.org/rfc/rfc6962
- The Update Framework: theupdateframework.io
- OpenTimestamps: opentimestamps.org

Regulatory:

- EU AI Act Articles 12, 19, 26, 113: artificialintelligenceact.eu
- HIPAA: 45 CFR 164.312(b), 164.316(b)(2)(i) (law.cornell.edu)
- eIDAS (Regulation 910/2014, amended 2024/1183): eur-lex.europa.eu
- C2PA specification 2.4: spec.c2pa.org

Market (all verified by direct fetch, 2026-07-15):

- microsoft/agent-governance-toolkit; its verifiable-compliance-receipts
  draft proposal (microsoft.github.io/agent-governance-toolkit/proposals/)
- cordum-io/cordum; humanlayer/humanlayer; langchain-ai/agent-inbox
- git-ai-project/git-ai; cursor/agent-trace; radotsvetkov/soma;
  webaesbyamin/agent-receipts
- BloopAI/vibe-kanban; smtg-ai/claude-squad; conductor.build
- anthropic.com/engineering/claude-code-sandboxing;
  developers.openai.com/codex/concepts/sandboxing;
  cursor.com/docs/agent/security/run-modes
