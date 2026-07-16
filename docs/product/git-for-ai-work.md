# Git, but for AI Work

The Palari Work Receipt Protocol — vision and implementation blueprint.

Status: design blueprint, 2026-07-16. This document records the protocol
direction and the concrete engineering plan to make it real. It is written to
be handed to a coding agent work item by work item. Companion documents:
[PCAW v1 specification](../../spec/pcaw/v1/README.md) (the shipped foundation),
[Competitive Landscape](competitive-landscape.md) (verified market context),
[Security Notes](security.md) (current threat boundary).

---

## 1. The thesis

**Accountability was never designed. It was a side effect of slowness.**

Every accountability system in working life — sign-off sheets, email trails,
"ask the person who handled it" — silently assumed human throughput: one
person, a few meaningful actions per day. At that speed, the truth of "who
approved this?" could always be reconstructed after the fact, because there
were few enough events for memory and inboxes to triangulate.

AI did not just speed work up. It invalidated that assumption. When one person
supervises a thousand executed tickets a day, "who approved erasing the
database", "who approved this patient receiving this medicine", "who accepted
this filing" stop being questions you can answer by asking around. The trail
must be a designed artifact, created at the moment of the act, or it never
exists at all.

There is a second-order effect: at AI velocity, the human's job silently
changes from doer to approver — and mass approval degrades into rubber-stamping
unless the record captures **what the approver actually saw**. A signature
alone proves someone clicked yes. Only a record of the presented evidence
proves what they clicked yes **to**.

The product is therefore one sentence:

> **Git, but for AI work.** A free protocol for signed receipts of AI-executed
> work — what was done, what the human saw, and who signed it — verifiable
> offline, forever, by anyone, without trusting the operator, the AI vendor,
> or Palari.

Git records **content history**: what bytes changed, who committed. Palari
records **authority history**: what the agent was allowed to do, what evidence
the human was shown, who approved, and when. That distinction is the answer to
"doesn't git already do this?" — and the reason the largest market is the
knowledge work that has no git at all: the nurse approving an AI-drafted
medication note, the paralegal accepting an AI-drafted filing, the accountant
signing AI-categorized transactions.

## 2. The machine in four primitives

Nothing in this protocol is novel cryptography. It composes four decades-old,
battle-tested primitives — the same ones that secure git, HTTPS, and app
stores. What is novel is the statement they attest to.

1. **Fingerprints (hashes).** SHA-256 turns any content into a short digest.
   Same content, same digest; one changed byte, different digest; the digest
   reveals nothing about the content. This is why receipts can reference
   patient data without containing any.
2. **Statements (canonical JSON).** The receipt is a small JSON document full
   of digests. It is serialized canonically (RFC 8785) so the same logical
   statement always produces the exact same bytes — which lets the statement
   itself be fingerprinted, signed, and logged.
3. **Signatures.** A private key produces a signature over the statement's
   bytes; anyone with the public key verifies it. Identity binding — proving
   the key belongs to a real person in a real organization — comes from the
   organization's existing login system, not from key files on laptops.
   Concretely: an OIDC login mints a short-lived signing certificate bound to
   the authenticated identity claim (the Sigstore pattern; §6.2).
4. **Append-only logs.** Each entry's hash chains to the previous one, so
   nothing can be inserted, backdated, or removed without visibly breaking the
   chain. This answers "since when?" and "can it quietly disappear?".

The verifier's job is three checks, offline, with standard tools: digests
match, signature verifies, log entry exists. If all pass, a stranger a decade
from now knows what was done, what the human saw, who signed, and when —
without the original workspace, provider, network, or source contents.

## 3. Anatomy of a receipt

Illustrative shape (the normative shape lives in the spec; see §5):

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
      "presented_digest": "sha256 of exactly what the approver saw",
      "human_decisions": "…who decided what, in what order…"
    },
    "subject_roles": {"work-state": "work-state",
                      "output-artifact-01": "output-artifact"},
    "security_limitations": ["…the honest non-claims, machine-readable…"]
  }
}
```

Wrapped, in v2, in a DSSE signature envelope (§6.1), optionally anchored to an
RFC 3161 timestamp (§6.3), and recorded in an append-only log (§6.5).

Field-by-field, the receipt answers:

| Question | Field |
| --- | --- |
| What was the agent allowed to do? | `governance_case.work_contract` |
| What did it actually produce? | `subject` digests (output artifacts) |
| What verification ran? | `governance_case` evidence records |
| What did the human see before deciding? | `presented_digest` (new in v2) |
| Who decided, and in what order? | `governance_case` human decisions |
| Who signs this whole statement? | DSSE envelope signature (new in v2) |
| When did this exist, provably? | RFC 3161 token / log entry (new in v2) |
| What does this NOT prove? | `security_limitations` |

Design invariant carried from v1: **digests, never content**. A receipt must
remain safe to retain, export, and show an auditor in a domain where the
underlying data (patient records, privileged filings) must not travel with it.
v2 extends the rule to names: filenames are metadata, and metadata leaks
("discharge-summary-4412.pdf" in a receipt is itself a disclosure). In
regulated contexts subject names MUST be pseudonymous role labels or digest
prefixes; the mapping from pseudonym to real artifact lives with the operator,
outside the receipt.

## 4. Why this wins: the verified market picture

Condensed from [Competitive Landscape](competitive-landscape.md), all claims
verified 2026-07-15:

- **Nobody has shipped this.** Microsoft's "Independently Verifiable
  Compliance Receipts" — the nearest analogue — is an unshipped draft proposal
  inside a .NET enterprise toolkit. Enterprise gateways offer operator-trusted
  SaaS logs. `agent-trace` (backed by Anthropic, OpenAI, Google) standardizes
  *attribution* (which lines were AI's), not *authorization* (who approved,
  having seen what).
- **Raw enforcement is commoditizing.** Claude Code, Codex, and Cursor all
  ship OS-level sandboxes natively. The enforcement layer is a subsidized
  substrate to ride, not a moat. The receipt layer is the moat.
- **The business model has an existence proof.** Git is a free protocol nobody
  pays for; GitHub built the business on hosting and services around it. The
  Sigstore / Let's Encrypt playbook is the same shape: protocol and verifier
  free forever; revenue in hosted transparency logs, organizational identity
  binding, and compliance packs.
- **The buyer lesson.** Vibe Kanban died at 27k stars; HumanLayer deprecated
  its approval SDK. Developer-experience governance does not monetize;
  compliance-driven governance can. Receipts have a compliance-driven buyer.

Adoption law, borrowed from git: the protocol must be useful to one team on
day one, alone, offline, with nobody else's permission. Network effects come
later. Palari's local-first, stdlib-only discipline is exactly this property.

## 5. What already exists (the shipped 70%)

PCAW v1 (`spec/pcaw/v1/`) is further along as a protocol than a casual reading
suggests. Already shipped and tested:

- **Standard envelope.** Statements are in-toto Statement v1 objects with
  `predicateType: https://palari.dev/pcaw/v1` — already the industry-standard
  attestation shape, ready for DSSE wrapping.
- **Canonical bytes.** Strict I-JSON + RFC 8785 canonicalization, floats
  forbidden, duplicate keys rejected, UTF-16 code-unit key ordering,
  deterministic export (no export time, no absolute paths, no locale text).
  Identical logical input produces identical bytes on any machine.
  A fortunate consequence of the no-floats rule: for integer-only documents,
  Python's stdlib `json.dumps(sort_keys=True, separators=(",", ":"),
  ensure_ascii=False)` is RFC 8785-conformant (the two stdlib divergences —
  ECMAScript float formatting and UTF-16 key ordering vs code points — arise
  only with floats and with keys mixing U+E000–U+FFFF against supplementary
  planes; guard the latter with `key=lambda k: k.encode("utf-16-be")`).
- **Offline verification with a stable contract.** `palari proof export` /
  `palari proof verify`, exit codes 0/1/2, a registry of ~35 stable diagnostic
  codes, independent lifecycle re-derivation, fail-closed on everything
  ambiguous.
- **A conformance corpus that tests other people's verifiers.** The
  dependency-free black-box runner (`spec/pcaw/v1/conformance.py`) accepts any
  verifier command. This is the protocol move — it already exists.
- **Honest machine-readable non-claims.** Every statement and report carries
  `security_limitations`. v1 explicitly does not sign, does not authenticate
  identities, and says so.
- **The upgrade path is reserved.** The v1 spec's "Future DSSE-compatible
  envelope" section both forbids fake signing in v1 and enumerates what a
  signing layer must specify: *algorithm agility, key identity, revocation,
  threshold policy, custody, and verification time*. That sentence is the v2
  requirements checklist, written before we knew we'd need it.

What v1 deliberately does not have — the v2 work: signatures and identity,
proof of what was presented to the approver, trusted time, non-file subjects,
and a shared append-only log.

## 6. PCAW v2 design: the five upgrades

Everything below was verified against primary sources on 2026-07-16 (OpenSSH
manual and release notes, DSSE and in-toto specifications, RFC 8785/3161,
Sigstore documentation, EU AI Act articles, 45 CFR). Per the v1 spec, adding
signing is a versioned protocol decision: this is `pcaw.v2` with
`predicateType: https://palari.dev/pcaw/v2`, never a bolt-on to v1. v1 stays
frozen; v1 statements remain verifiable forever.

### 6.1 Signatures: DSSE envelope

Wrap the exact canonical statement bytes in a DSSE (Dead Simple Signing
Envelope):

```json
{
  "payload": "<Base64(canonical statement bytes)>",
  "payloadType": "application/vnd.palari.pcaw+json; version=2",
  "signatures": [{"keyid": "<key identifier>", "sig": "<Base64(signature)>"}]
}
```

The signature is computed over DSSE's pre-authentication encoding, **not** the
raw payload:

```text
PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
SP = 0x20; LEN = ASCII decimal byte length, no leading zeros
```

Verifiers MUST verify against PAE output and MUST NOT re-parse the envelope
after verification. Multiple signatures are supported natively — that is the
threshold/quorum hook (e.g., approver + org witness). Empty envelopes,
placeholder signatures, and inferred signers remain forbidden.

### 6.2 Signing backends: ship two, in this order

**Backend A — OpenSSH signatures (`ssh-keygen -Y`): the zero-dependency
default.** Available since OpenSSH 8.1 (2019); the same machinery git uses for
`gpg.format=ssh` since Git 2.34. Every developer already has the binary and
most already have a key.

```bash
# Sign (namespace is mandatory and MUST be fixed by the protocol)
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
explicitly rather than hidden: no timestamp inside the signature (that is what
§6.3 is for), single-level CA only (`cert-authority` + SSH certificates),
revocation via a KRL file supplied at verification time.

**Backend B — Sigstore keyless: the identity-grade option.** Short-lived
signing certificate issued against an OIDC login (the org's existing SSO),
signature recorded in the Rekor transparency log. This is the strongest form
of "this key belonged to this authenticated person at this moment":

```bash
cosign sign-blob receipt.dsse --bundle receipt.sigstore.json
cosign verify-blob receipt.dsse --bundle receipt.sigstore.json \
  --certificate-identity=dr.osei@stmarys.org \
  --certificate-oidc-issuer=https://login.microsoftonline.com/...
```

Caveat to state plainly: the public-good Rekor instance makes signer
identities public. Regulated deployments use a private Sigstore stack (the
`sigstore/scaffold` Helm chart deploys Rekor + Fulcio + Trillian in-house).
Both backends are invoked as subprocesses — the stdlib-only rule holds.

**The trust topology, answered rather than gestured at.** Identity binding
raises three questions the protocol must answer explicitly:

- *Who operates the certificate authority?* Backend A: nobody — trust is the
  org's reviewable `allowed_signers` registry, governed like any other file.
  Backend B: the org's own Fulcio (private stack) rooted in its IdP, or the
  public Sigstore CA when signer identities may be public.
- *What is the revocation story?* Backend A: KRLs plus `valid-before` windows
  in the registry, checked at verification time. Backend B: certificates live
  minutes, so key revocation is largely moot; identity revocation is the
  IdP's account lifecycle, which the org already operates.
- *What does "without trusting Palari" mean if Palari runs the log?* It means
  Palari MUST NOT be the only holder of anything. Verification never calls a
  Palari service; logs are org-run or public, never Palari-only; and log
  operators are kept honest by **published witness heads** — the log's
  current head hash signed and published somewhere the operator cannot
  rewrite (a public log, another org's log, or simply a git repository
  others clone). The acceptable topologies are: per-org log with published
  witness heads, public transparency log, or user-run log. "Palari hosts
  your log" is a convenience tier, valid only because the witness heads make
  the host verifiable rather than trusted.

### 6.3 Presentation digest: proof of what the approver saw

The highest-value, least-built field in the industry. When an approval is
requested, Palari renders the evidence view (the Approval Pack content), emits
it as canonical bytes, digests it, and binds that digest into both the human
decision record and the receipt predicate. The claim upgrades from "she
approved the work" to "she approved the work **having been presented exactly
this**." Approval Packs already bind exact evidence to exact decisions; this
adds one canonical rendering step and one digest field. No verified competitor
records this.

Precision requirement, binding on every description of this field: the digest
proves what was **presented** — the bytes rendered available to the approver —
not what was read or understood. Attention is out of scope for v2. That is
still a categorical improvement over a bare signature, and auditors will find
the gap in minutes if the language overclaims; precision here is credibility
everywhere else.

### 6.4 Trusted time: RFC 3161 anchoring

SSHSIG carries no timestamp, and self-declared timestamps prove nothing. An
RFC 3161 Time-Stamp Authority token is a signed statement by a third party
that a given **hash** existed no later than a given time — only the digest is
sent, never content:

```bash
openssl ts -query -data receipt.dsse -sha256 -cert -no_nonce -out req.tsq
curl -s -H "Content-Type: application/timestamp-query" \
     --data-binary @req.tsq https://freetsa.org/tsr > receipt.tsr
openssl ts -verify -data receipt.dsse -in receipt.tsr \
     -CAfile cacert.pem -untrusted tsa.crt
```

Free endpoints verified available: freetsa.org/tsr, timestamp.digicert.com,
timestamp.sectigo.com, ts.ssl.com (liveness rechecked at deploy time).
Anchoring is the one optional network touch in the protocol; it MUST degrade
to a structured warning offline, never a hard failure, and the token travels
with the proof bundle so verification stays offline.

### 6.5 Abstract subjects and the shared log

**Abstract subjects.** v1 subjects are files plus the virtual work-state.
Knowledge work is EHR entries, drafted letters, claim decisions, database
mutations. v2 generalizes the subject to any content-addressed artifact via
typed subject roles (e.g. `record`, `message`, `decision-artifact`) while
keeping the same digest discipline. Files become one subject class among
several; the hospital receipt and the pull-request receipt are the same shape.

**Shared append-only log.** The local hash-chained journal already provides
tamper evidence on one machine. The protocol-level upgrade is publishing
receipt digests to an append-only log outside the operator's unilateral
control — a private Rekor, or initially even a dedicated git repository of
receipt digests (append-only by review policy, hash-chained by construction).
That entry is the permanent "this existed, then" record: the token that lives
forever, without any blockchain.

**Receipt lineage (Merkle DAG).** Receipts gain an optional
`parent_receipts` list of statement digests: a revision receipt cites the
receipt it supersedes; dependent work cites prerequisite receipts. This
upgrades the linear journal into git's actual structure — a content-addressed
DAG — so verifying one receipt transitively pins its ancestry, and parallel
workstreams merge verifiably instead of racing for one chain.

**Revocation, supersession, and the two guarantees.** The workspace model
already implements the semantics — a later negative decision revokes an
earlier approval, and contradictory records fail closed. The protocol must
lift them into statements: a **revocation/supersession statement** citing the
revoked receipt's digest, signed under the same authority rules, logged like
any receipt. Without it, a revoked acceptance verifies "valid forever." This
exposes a real tension the spec must state plainly rather than paper over:
**offline verification proves validity-at-signing** — the receipt was
well-formed, signed, and consistent when made; **freshness** — is this still
the latest decision, or was it superseded? — **requires a log query**. Two
different guarantees. A verifier report MUST name which one it is giving
(`validity: verified-offline`, `currency: not-checked | current-as-of-log`),
and marketing MUST NOT promise the second while delivering the first.

### 6.6 Design lessons carried from git and its sibling protocols

Since the positioning is "Git, but for AI work", hold the protocol to the
properties that actually made git unkillable, and learn from the protocols
that lived and died around it:

- **The format is the product; implementations are guests.** Git the C
  program is one of many (JGit, gitoxide, go-git, Dulwich, isomorphic-git)
  because the bytes are the spec. PCAW receipts must verify in 2056 with
  whatever runs then. WRP-8's independent verifier is this property made
  testable.
- **Plumbing vs. porcelain.** Git keeps low-level, forever-stable, scriptable
  commands (`hash-object`, `cat-file`) separate from friendly UX. GitHub and
  every IDE exist because plumbing was stable. Palari exposes `canonicalize`,
  `digest`, envelope, and single-proof verification as stable plumbing under
  the CLI porcelain, so other people's tools can script the protocol.
- **The SHA-1 lesson: agility before you need it.** Git hardcoded SHA-1 in
  2005; the SHA-256 migration has taken 15+ years and is unfinished. v2 must
  specify the dual-digest transition procedure for introducing a successor
  algorithm — not merely reject unknown ones (WRP-7). "Verifiable forever"
  additionally requires an **algorithm-suite identifier** on every envelope
  and a **re-anchoring procedure**: before a suite weakens, existing receipts
  are re-timestamped (RFC 3161 or fresh log witness heads) under a current
  suite, preserving the proof-of-existence chain across algorithm
  generations. One field and a paragraph now; a migration crisis avoided
  later.
- **Correctness first, efficiency later.** Git shipped loose objects and
  added packfiles years later without changing semantics. Receipt storage
  efficiency is deliberately out of scope until the format is settled.
- **Certificate Transparency: logs earn trust by being watched.** CT's
  append-only logs work because independent monitors audit them — and CT won
  adoption because browsers *required* it. Design the shared log for
  third-party monitors from day one, and note the adoption analogue: the
  forcing function in §11 (insurers, regulators), not developer enthusiasm.
- **TUF: assume key compromise, survive it.** The Update Framework's role
  separation, signature thresholds, rotation, and compromise-recovery design
  is the strongest prior art for the signer-registry and threshold-policy
  questions WRP-7 must answer. Crib it; do not invent.
- **JWT/JOSE: the ergonomics won, the flaws were forever.** JWT conquered the
  world on developer ergonomics, then bled for a decade from envelope design
  flaws (`alg: none`). DSSE exists because its authors studied those wounds —
  the reason it is the right envelope, and a warning that envelope mistakes
  cannot be patched later.
- **PGP: cryptographic soundness does not survive bad identity UX.** The web
  of trust failed socially. Identity must ride the organization's existing
  login (OIDC / Sigstore), never user-managed key ceremonies.
- **OpenTimestamps: a second, cert-free anchor.** Aggregates hashes into
  Bitcoin blocks via Merkle trees — verifiable forever without any timestamp
  authority's certificate chain surviving. A candidate second anchoring
  backend beside RFC 3161 for the longest-horizon receipts.
- **eIDAS: statutory weight is available.** EU-qualified electronic
  signatures carry a legal presumption of validity. If a signing backend can
  meet qualified-signature requirements, receipts gain evidentiary force in
  the EU by statute rather than by argument — future work, named in §10.

## 7. Beyond code: documents, spreadsheets, and forms

Code was the incubator because git-shaped tooling already existed there. The
protocol's real market is the knowledge work that has no git at all. Three
principles carry receipts across, then a worked example.

**1. The snapshot principle.** Git never versions a live file; it commits a
snapshot. Live cloud documents (Google Docs, Sheets, Office online) have no
stable bytes to digest — a Drive revision ID is a pointer into a mutable
service, not a proof. A receipt therefore binds to a **content-addressed
snapshot taken at decision time**: the exported bytes (PDF, `.docx`, `.xlsx`,
CSV) become the subject, and their digest is what the human's signature
covers. The snapshot is the commit. For spreadsheets, digest both the file
bytes and a canonical values export (CSV), so a verifier can distinguish "the
numbers changed" from "the formatting changed."

**2. The field map is the diff.** A line diff is meaningless for a form or a
structured document. The knowledge-work analog is a **field map** in the
predicate: field → filled value → source subject digest (and locator). "What
was done" becomes "which fields were filled, with what values, derived from
which source documents." The field map is itself canonical bytes with a
digest, so evidence checks (arithmetic, cross-field rules, eligibility
tables) can bind to it exactly.

**3. The case is the work item.** One person's matter — one tax return, one
discharge, one filing — is one work item. Sources are that person's
documents; the boundary is the named forms and fields the agent may fill;
evidence is the validation suite; the presentation is the review screen; the
decision is the signature. The entire existing lifecycle maps one-to-one; no
new concepts are needed, only new subject types (§6.5, WRP-6, WRP-11).

### Worked example: the international-student tax product

The concrete case this section is designed against: an app where AI helps
international students complete their tax filings (e.g. a US federal
nonresident return plus its required attachments), where an estimated 80–90%
of cases are mechanically simple form completion.

The flow, in protocol terms:

1. The student uploads source documents (wage statements, treaty forms,
   immigration documents). Each becomes a digested input subject. The work
   contract names exactly which forms and fields the AI may fill.
2. The AI extracts values and completes the forms. The field map records
   every filled field with its value and the digest of the source document it
   came from. Validation evidence runs: arithmetic checks, cross-field
   consistency, treaty-table lookups.
3. The student sees the review screen: each filled field beside its source.
   That rendered view is digested — the presentation digest. The student
   approves; the signature covers the receipt binding contract, sources,
   field map, evidence, presented view, and the completed PDF's digest.
4. The receipt is anchored and logged. The student keeps the completed
   return *and* the receipt; the operator keeps only digests.

Why this case is protocol-perfect and not merely protocol-compatible:

- **The liability structure demands it.** Consumer tax software operates on
  the self-preparation model: the taxpayer is the preparer and attests to the
  return. The receipt is the missing evidence layer for exactly that
  attestation — proof the student was shown each extracted value and its
  source and approved it. It protects the operator ("the AI filed it wrong"
  meets the record of what was shown and signed), and protects the student
  (a good-faith diligence record, with sources, if the return is questioned).
  This is §11 in miniature.
- **The risk tiers already fit.** The 80–90% simple cases are light-gate work
  (self-approval with full evidence); flagged cases — treaty edge cases,
  multiple states, unusual income — escalate to a credentialed human
  reviewer whose signature lands on the same receipt shape at a stricter
  gate. Palari's intensity/risk model maps without modification.
- **Privacy is by construction.** Receipts carry digests, never wage or
  immigration data — retainable and shareable with an auditor without
  exposing the underlying documents (§9's caveats still apply and are stated
  on every receipt).
- **It is the first product built on the protocol rather than a feature of
  this repository** — the design-partner requirement (§12) satisfied
  first-party: the app's real cases force WRP-6 and WRP-11's requirements
  before any external partner is needed.

One honest design obligation carries over from §1: at consumer scale, the
approval click is the weakest link. The presentation digest proves what was
shown, never what was read (§9). The review UX must therefore be designed
for meaningful assent — per-field confirmation for consequential values
rather than one global "approve" — because the receipt will faithfully
record whichever standard of review the product actually implements.

## 8. Implementation plan (written for a coding agent)

Ground rules for every work item: Python stdlib only (external tools invoked
as subprocesses: `ssh-keygen`, `openssl`, `cosign`); fail closed on anything
ambiguous; every new failure mode gets a stable diagnostic code; conformance
vectors land in the same work item as the feature; v1 behavior is never
modified — v2 is additive. Per §6.6, new primitives are exposed as stable
plumbing (canonicalize, digest, envelope, verify-one) beneath the porcelain
CLI, and their CLI contracts are frozen once shipped. Each item below is sized to be one bounded work
item with its own boundary, evidence, and review.

**WRP-1 — DSSE envelope module.**
New `src/palari_company_os/dsse.py`: canonical envelope
build/parse, exact PAE construction, base64 handling, multi-signature
support, rejection of empty/placeholder signatures.
Acceptance: round-trip property tests; PAE byte-exactness against the DSSE
spec test strings; malformed-envelope rejection vectors with new codes
(`ENVELOPE_INVALID`, `SIGNATURE_MISSING`).

**WRP-2 — OpenSSH signing backend.**
New `src/palari_company_os/signing_ssh.py`: subprocess wrappers for
`ssh-keygen -Y sign|verify|find-principals`, fixed namespace
`palari-work-receipt`, `allowed_signers` read/validate helpers, KRL
revocation pass-through, structured errors when `ssh-keygen` is absent or
older than OpenSSH 8.1.
Acceptance: sign→verify round trip in tests with a throwaway ed25519 key;
tampered-payload rejection; unknown-signer rejection (`SIGNER_UNTRUSTED`);
wrong-namespace rejection.

**WRP-3 — CLI: `proof sign` and signed verification.**
`palari proof sign FILE --key PATH --as HUMAN-ID` producing the DSSE bundle;
`palari proof verify` gains `--require-signature --allowed-signers FILE
--identity ID`. Unsigned v2 proofs verify structurally but report
`signature: absent` and set an explicit warning.
Acceptance: exit-code contract preserved (0/1/2); report schema extended with
`signature_status` and signer principal; CLI smoke tests.

**WRP-4 — Presentation digest.**
Canonical rendering of the Approval Pack evidence view to bytes; digest bound
into the human decision record and the v2 predicate
(`presented_digest`); verifier recomputes when the presented view is included
in the bundle, else reports `not-checked`.
Acceptance: two visually identical packs with one changed evidence byte yield
different digests; decision records missing a presentation digest fail closed
in v2 acceptance verification (`PCAW_PRESENTATION_MISSING`).

**WRP-5 — RFC 3161 anchoring.**
`palari proof anchor FILE [--tsa URL]` via `openssl ts` subprocess; token
stored alongside the proof; `proof verify` checks an included token when
present, warns (never fails) when absent; offline degradation is a structured
warning.
Acceptance: request/verify round trip mocked in tests (no network in test
suite); tampered-token rejection; documented endpoint list.

**WRP-6 — Abstract subject classes and receipt lineage.**
Extend subject roles beyond `work-state`/`output-artifact` with typed
content-addressed subjects; update statement schema and path-safety rules
(non-file subjects have no path, only digests). Add the optional
`parent_receipts` statement-digest list (§6.5) so receipts form a verifiable
DAG.
Acceptance: schema vectors for each new role; unknown role rejection;
lineage round trip (child receipt pins parent digest, tampered parent
rejected); v1 statements still verify byte-identically.

**WRP-7 — spec/pcaw/v2 + conformance corpus.**
`spec/pcaw/v2/README.md` in the exact normative style of v1, answering the
reserved checklist (algorithm agility, key identity, revocation, threshold
policy, custody, verification time); conformance vectors for signed, unsigned,
tampered, revoked, and threshold cases; the v1 black-box runner extended to
v2. Four design constraints from §6.5–6.6: the digest-agility section MUST
define the algorithm-suite identifier, the dual-digest transition procedure,
and the re-anchoring story (the git SHA-1 lesson); the threshold/role/rotation
design MUST be derived from TUF's model rather than invented; the
revocation/supersession statement type MUST be specified with the same
authority rules as receipts; and the report MUST separate the two guarantees
(validity-at-signing offline vs. currency via log query) as distinct typed
fields.
Acceptance: `conformance.py -- ./bin/palari proof verify` passes the full v2
manifest; every new diagnostic code pinned in the manifest.

**WRP-8 — Second verifier (the protocol proof point).**
A minimal independent verifier (different language, e.g. Go or TypeScript,
~300 lines, statement-only + signature check) living under `spec/pcaw/v2/`,
passing the same conformance corpus. A protocol with one implementation is a
schema; this makes it two.
Acceptance: the independent verifier passes the corpus with zero shared code.

**WRP-9 — Sigstore backend + shared log (after design-partner input).**
`signing_sigstore.py` subprocess wrappers (`cosign sign-blob/verify-blob
--bundle`), private-Rekor deployment notes, and the receipt-digest publication
command. Deliberately late: it is the piece whose requirements a real
regulated design partner should shape.

**WRP-10 — The demo wedge: drop-a-receipt verifier page.**
A single static HTML page (no server, no upload — verification runs
in-browser via WebCrypto) where anyone drops a receipt bundle and sees the
three checks go green: digests match, signature verifies, anchor intact.
Plus the README hero: emit a signed receipt from this repository's own
workflow, verify it on the page. The blocked-write demo carried the current
repo; this demo carries the protocol.
Acceptance: page is fully self-contained (works from `file://`); a tampered
byte flips the relevant check red with the stable diagnostic code; linked
from the README next to a `palari proof verify` one-liner.

**WRP-11 — Knowledge-work predicate: snapshots and field maps.**
The §7 extensions: snapshot subjects (exported-bytes digesting for live
documents, dual file-bytes + canonical-values digests for spreadsheets) and
the canonical field-map structure (field → value → source subject digest →
locator) with its own digest bound into the predicate and coverable by
evidence checks.
Acceptance: field-map canonicalization vectors; a change to one filled value
changes the field-map digest; a snapshot subject with no path verifies;
evidence bound to a stale field map fails closed
(`PCAW_FIELD_MAP_STALE`).

Dependency order: WRP-1 → WRP-2 → WRP-3 form the critical path; WRP-4 and
WRP-5 are independent after WRP-1; WRP-6 and WRP-7 close the spec; WRP-8
proves it; WRP-10 ships the public demo as soon as WRP-3 exists; WRP-11
(which depends on WRP-6) unlocks the knowledge-work products of §7; WRP-9
follows the first external conversation.

## 9. What a receipt does NOT prove (keep this section forever)

Extending the v1 non-guarantees honestly, in the same fail-closed spirit:

- A signature proves an authenticated identity approved the statement; it does
  not prove the judgment was good, the evidence was sufficient, or the work is
  semantically correct.
- The presentation digest proves what was rendered for the approver; it cannot
  prove the human read or understood it.
- Receipts record and attribute; they do not prevent. A bad approval still
  happens — it becomes permanently attributable, which changes behavior the
  way cameras change driving. In regulated domains, attributability is the
  product; do not oversell it as safety.
- Identity binding is as strong as the identity provider behind it. A key on
  a laptop proves possession of a laptop; an OIDC-bound short-lived
  certificate proves an authenticated login. State which one a receipt
  carries.
- Trusted timestamps prove existed-no-later-than; they do not prove
  existed-no-earlier-than.
- Offline verification proves validity-at-signing. Whether a receipt is still
  the latest word — not superseded or revoked — is a separate guarantee that
  requires querying a log (§6.5). Reports state each separately; neither is
  ever implied by the other.

## 10. Regulatory tailwinds (stated precisely, because everyone misquotes them)

- **EU AI Act.** Article 12 requires high-risk AI systems to technically allow
  automatic event logging; Article 19 (providers) and Article 26(6)
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
- **Design fit.** Digest-only receipts are retainable and exportable in these
  regimes precisely because they carry no protected content — privacy by
  construction, not by policy.
- **eIDAS (future work).** EU-qualified electronic signatures carry a
  statutory presumption of validity. A signing backend meeting
  qualified-signature requirements would give receipts evidentiary force in
  the EU by statute; named here so the v2 spec's custody section keeps the
  door open.

Adjacent prior art worth naming in conversations: C2PA binds signed provenance
manifests to media files (and its spec covers PDFs); nobody has applied that
pattern to work records — treat C2PA as the design analogy that proves the
pattern scales, not as a competitor.

## 11. The liability engine: why labs and insurers want this to exist

The strongest demand for this protocol may come from parties who never run a
single Palari command.

**The allocation already exists on paper; the evidence does not.** Every
provider's terms say the user is responsible for reviewing outputs.
Professional-responsibility rules already agree: bar guidance treats
generative AI like nonlawyer assistance the attorney must supervise, and when
AI-hallucinated citations reached a court, the sanctions fell on the lawyer,
not the model provider. Medicine, engineering, and accounting run on the same
rule — the professional answers for the work product. What is missing at AI
velocity is not the allocation of responsibility but the **evidence
infrastructure that makes the allocation provable**. A terms-of-service
disclaimer is weak protection when nobody can show whether a specific output
was meaningfully reviewed. A signed receipt with a presentation digest shows
it exactly: this human, under this contract, was shown this evidence, and
signed.

**Receipts do not transfer liability; they make the existing line crisp.**
Liability for model defects — a defective model, a misrepresented capability —
stays with the provider and cannot be contracted away. What the receipt
separates cleanly is the layer above: supervision and acceptance, which
provably rest with the professional who signed. Today every incident smears
those two layers together; both sides want the line crisp, because the fight
about where it falls is more expensive than either side's share of it.

**Neutrality is a legal requirement, not a positioning choice.** A
liability-relevant record system run by an interested party is worthless as
evidence — no court credits the fox's ledger of the henhouse. The record
layer must be free, open, and verifiable without trusting any provider,
operator, or Palari itself. The labs have already shown they will back
neutral formats they cannot own (agent-trace, jointly supported by Anthropic,
OpenAI, and Google); a neutral receipt protocol is the same move one layer
up, where the stakes are legal rather than attributional.

**The precedent is the professional engineer's stamp.** Society already
solved "one accountable human answers for work they did not personally
perform": the PE stamps the drawings, and the stamp is what makes bridges
buildable and insurable. A Palari receipt is the PE stamp for AI work, with
cryptographic teeth — the same social function, made verifiable offline by
strangers decades later.

**Insurers are the adoption engine.** Professional liability carriers must
price AI-assisted work today with no underwriting data and no defense
evidence. Receipts supply both: proof that a firm reviews what it signs, and
litigation-grade evidence of meaningful supervision. A carrier that discounts
premiums for receipt-governed AI work creates a forcing function stronger
than any developer marketing — the mechanism that spread seatbelts,
sprinklers, and secure-by-default IT. This also sharpens the design-partner
search: a malpractice carrier or a firm's general counsel may be a better
first partner than any single clinic or firm.

**Claim-language rules (bind the marketing to these).** Never claim the
protocol "removes" or "shields from" liability — it is not legally true, and
the buyers who matter (general counsel, insurers, regulators) will spot the
overclaim in one sentence and discount everything else. The receipt is
evidence in both directions: it protects the professional who genuinely
reviewed and exposes the one who rubber-stamped a thousand approvals in an
hour. That double edge is the honest product. The approved phrasing is:
*clean, provable allocation of responsibility — protection for the diligent,
by construction.*

## 12. Adoption strategy

The wedge, concretely: the **first emitter** is this repository's CLI (it
already produces receipts) plus the Claude Code hook layer; the **first
verifier** is `palari proof verify receipt.json` plus the static
drop-a-receipt page (WRP-10) where anyone sees the three checks go green.
That pair is the README hero — the blocked-write demo carried this repo, and
this demo carries the protocol.

1. **Verifier first.** The free, trivially installable artifact is `verify` —
   run it in CI, run it in an audit, exit 0 or 1. Producers follow verifiers,
   never the reverse. The v1 conformance runner already embodies this stance.
2. **Dogfood where the tooling already lives.** Every merged work item in this
   repository ships with its own signed receipt. Each receipt doubles as a
   demo. Code is not the biggest market, but it is the market where the first
   thousand users already run agents all day.
3. **One design partner in a regulated niche** — a clinic, a law firm, an
   accounting practice drowning in AI-assist documentation duties, or (per
   §11) a professional liability carrier or general counsel. Their auditor
   becomes the requirements document. Worth more than ten thousand stars, and
   it shapes WRP-9 before it is built.
4. **Second implementation, early** (WRP-8). The moment another codebase
   passes the conformance corpus, this stops being a feature of Palari and
   starts being a protocol.
5. **Interoperate, don't compete, on attribution.** Emit and ingest
   `agent-trace` records; receipts answer authorization, agent-trace answers
   authorship. Allies, not rivals.

**Business shape** (the win-win): the protocol, spec, verifier, and reference
implementation are free forever — the moment verification requires Palari's
servers or accounts, the git analogy becomes false and trust evaporates.
Revenue lives above the protocol: hosted transparency logs, organizational
identity binding against corporate IdPs, compliance report packs, and the
supervision surfaces. Let's Encrypt and Sigstore prove the shape; GitHub
proves the ceiling.

## 13. Naming and positioning rules

- The sentence is **"Git, but for AI work."** It is load-bearing: it names the
  object (permanent verifiable record), the architecture (content-addressed,
  offline, no central authority), the business model (free protocol, paid
  hosting), and the adoption path (useful to one person on day one).
- The atom is called a **receipt** — the word already carries "proof you keep,
  useful later, boring by design". Avoid "token": technically it is a
  content-addressed, signed statement anchored in an append-only log; calling
  it a token invites blockchain readings that add baggage and subtract trust.
- "PCAW" remains the spec lineage name (v1 → v2); "Palari Work Receipt" is the
  product name of the signed artifact. The pitch stays one sentence: *a free
  protocol for signed receipts of AI-executed work — what was done, what the
  human saw, and who signed it, verifiable offline forever.*

## 14. Risks

- **Platforms ship native signed session logs.** Anthropic, OpenAI, and Google
  jointly backing agent-trace shows appetite for shared formats. Mitigation:
  interoperate early; own the layer they structurally cannot — binding
  contract, presented evidence, and human authority across platforms.
- **Spec-in-a-vacuum.** A protocol with one implementer is a schema with a
  press release. Mitigation: WRP-8 and the design partner are scheduled work,
  not aspirations.
- **Identity is the hard part.** Signing is a weekend; deciding whose
  signature counts is governance. Mitigation: the `allowed_signers` registry
  is itself a governed Palari artifact, and the Sigstore path outsources
  identity to the org's existing IdP.
- **DX-buyer trap.** The research is unambiguous: this monetizes through
  compliance-driven buyers. Keep the developer wedge free and frictionless;
  aim the commercial layer at the people who must evidence their AI work.

## 15. The hospital vignette (the north star, end to end)

An AI drafts a discharge summary under a work contract: allowed sources, one
allowed output. Palari records the attempt, runs the evidence checks, and
assembles the Approval Pack. Dr. Osei reviews it; the exact rendered view is
digested. She approves; her org-issued identity signs the receipt; the
receipt's digest is anchored to a timestamp authority and appended to the
hospital's log. Total added human work: the review she was doing anyway.

Seven years later, an auditor holds three things: the receipt, the note, and
the log. On a laptop with no network, no Palari account, and no access to any
patient record beyond this note, they verify: digests match, signature chains
to the hospital's identity provider, log entry is intact and in sequence. They
now know what the AI was allowed to do, what it produced, what Dr. Osei saw,
that she approved it, and when — with mathematical certainty and zero trust in
the hospital's IT department, the AI vendor, or us.

That is the product. Work at AI speed, accountability at cryptographic
strength, and a record that outlives everyone's memory of the ticket.

## 16. Glossary (plain language)

| Term | Plain meaning |
| --- | --- |
| Digest / hash | A fingerprint of content: same content, same fingerprint; reveals nothing about the content. |
| Canonical JSON | One fixed way to write the bytes of a JSON document, so equal statements are byte-equal (RFC 8785). |
| DSSE | A minimal, standard JSON envelope that carries a payload plus one or more signatures over it. |
| in-toto Statement | The standard "these artifacts, this claim" attestation shape the receipt uses. |
| SSHSIG | The signature format behind `ssh-keygen -Y`; what git uses for SSH-signed commits. |
| allowed_signers | A reviewable text file listing which keys speak for which identities — the trust registry. |
| Keyless signing | Sigstore's pattern: your org login mints a minutes-lived certificate; no long-lived key files. |
| RFC 3161 token | A third party's signed statement that a given fingerprint existed no later than a given time. |
| Transparency log | An append-only, hash-chained record; nothing can be inserted, removed, or backdated invisibly. |
| Receipt | One signed, canonical statement binding contract, evidence, presented view, decision, and signer. |
| Snapshot | The exported bytes of a live document at decision time — the thing a receipt actually signs (the commit, for knowledge work). |
| Field map | The knowledge-work diff: which fields were filled, with what values, from which digested sources. |

## 17. Primary sources

- PCAW v1: `spec/pcaw/v1/README.md` (this repository)
- DSSE: github.com/secure-systems-lab/dsse (envelope.md, protocol.md)
- in-toto Statement v1: github.com/in-toto/attestation/blob/main/spec/v1/statement.md
- RFC 8785 (JCS): rfc-editor.org/rfc/rfc8785
- OpenSSH signatures: man.openbsd.org/ssh-keygen; PROTOCOL.sshsig; release notes 8.1/8.2
- Sigstore blobs: docs.sigstore.dev/cosign/signing/signing_with_blobs
- RFC 3161: rfc-editor.org/rfc/rfc3161
- EU AI Act Articles 12, 19, 26, 113: artificialintelligenceact.eu
- HIPAA: 45 CFR 164.312(b), 164.316(b)(2)(i) (law.cornell.edu)
- C2PA specification 2.4: spec.c2pa.org
- Certificate Transparency: rfc-editor.org/rfc/rfc6962
- The Update Framework: theupdateframework.io
- OpenTimestamps: opentimestamps.org
- eIDAS (Regulation 910/2014, amended 2024/1183): eur-lex.europa.eu
- Market claims: [Competitive Landscape](competitive-landscape.md)
