# Proof-Carrying AI Work Protocol v1

Status: implementation candidate for Palari Company OS 0.2.0. This directory is
the normative, provider-neutral contract for PCAW v1. Normative requirements use
the words MUST, MUST NOT, SHOULD, and MAY as described by RFC 2119.

PCAW makes a bounded AI-work claim independently checkable from a statement,
its named output artifacts, and an offline verifier. A valid proof demonstrates
that the included governance records are internally consistent and that any
checked subjects match their declared digests. It does not turn declared actor
names into authenticated identities.

## Statement envelope

A PCAW v1 proof is an in-toto Statement v1 JSON object with exactly four fields:

- `_type` MUST be `https://in-toto.io/Statement/v1`.
- `subject` MUST be an array of uniquely named subjects. Every subject has one
  `sha256` digest containing 64 lowercase hexadecimal characters.
- `predicateType` MUST be `https://palari.dev/pcaw/v1`.
- `predicate` MUST be a PCAW v1 predicate.

The predicate has exactly these top-level fields:

- `schema_version`, fixed to `pcaw.v1`;
- `claimed_state`, the lifecycle state claimed by the exporting workspace;
- `governance_case`, the normalized work contract and current proof records;
- `subject_roles`, one exact role for every statement subject;
- `security_limitations`, the required PCAW v1 non-claims.

`subject_roles` distinguishes the virtual `work-state` subject from
`output-artifact` subjects. The work-state digest is the SHA-256 digest of the
canonical `governance_case` bytes. Output artifact names are safe relative POSIX
paths. An output subject name MUST NOT be absolute, empty, contain `.` or `..`
segments, contain a backslash, or resolve outside the selected subject root.
Subject names and role entries are unique, and their sets MUST match exactly.

The detailed predicate shape is defined by `statement.schema.json`. Unknown
fields are rejected at every protocol-defined object boundary.

## Canonical JSON and digests

Statements and all values hashed by PCAW MUST use strict I-JSON and the JSON
Canonicalization Scheme in RFC 8785, with one PCAW v1 restriction: floating
point numbers are forbidden. Integers MUST be exactly representable in the
I-JSON interoperable range. Implementations MUST reject:

- duplicate object member names at any depth;
- floats, NaN, positive or negative infinity, and integers outside the safe
  interoperable range;
- invalid UTF-8, lone surrogate code points, and Unicode noncharacters;
- unknown fields, unsupported digest algorithms, or ambiguous timestamps;
- non-canonical statement bytes, including a byte-order mark or trailing data.

Object member names are ordered by their UTF-16 code units as required by RFC
8785. Canonical output is UTF-8 with no leading or trailing whitespace and no
terminal newline. The statement digest reported by a verifier is SHA-256 over
those exact canonical statement bytes.

Timestamps in the predicate MUST be normalized UTC RFC 3339 strings ending in
`Z`. A timezone-free timestamp or a timestamp whose spelling does not meet the
schema is ambiguous and fails closed. Export MUST NOT include export time,
absolute local paths, locale-derived text, provider responses, source contents,
secrets, or credentials. Identical logical input therefore produces identical
statement bytes regardless of process, absolute workspace path, timezone, or
locale.

## Verification levels

Default verification checks both governance consistency and output artifact
bytes. Subject paths are resolved relative to the proof file unless the caller
supplies `--subject-root`. Missing artifacts, digest mismatches, unsafe paths,
and symlink escapes fail verification.

`--statement-only` verifies canonical syntax, schema, the work-state subject,
and internal governance consistency without reading output artifacts. A
statement-only report MUST set `verification_level` to `statement-only`, set
`subject_digest_status` to `not-checked` when output subjects exist, set
`fully_verified` and `acceptance_verified` to false, and emit the
`ARTIFACT_CHECKS_SKIPPED` warning. Statement-only success is not acceptance
proof.

A blocked or incomplete work statement can be exported and structurally
inspected, but missing required proof remains a fail-closed verification error.
`verified` means that the requested verification level passed; it does not mean
the derived lifecycle state is `accepted`. A verifier MUST derive lifecycle
state independently and compare it with `claimed_state`. A mismatch is an
error.

The command contract is:

```text
palari proof export WORK-ID --output FILE --json
palari proof verify FILE [--subject-root DIR] [--statement-only] --json
```

Verification success exits 0. A well-formed verification that rejects a proof
exits 1 and still emits a complete report. Command usage or operational failure
exits 2. Export MUST support blocked and incomplete work and MUST never convert
their state into acceptance.

## Verification report

`verification-result.schema.json` defines the stable JSON report. Diagnostics
are sorted by JSON path and code. Each diagnostic includes a stable code, JSON
path, concise message, and next safe action. Messages may add detail, but callers
MUST branch on codes and typed status fields rather than prose.

The initial stable diagnostic code registry is:

| Code | Kind | Meaning |
| --- | --- | --- |
| `INVALID_UTF8` | error | The proof is not strict UTF-8. |
| `INVALID_JSON` | error | The proof is not valid JSON. |
| `DUPLICATE_KEY` | error | An object repeats a member name. |
| `FLOAT_FORBIDDEN` | error | A float or non-finite number is present. |
| `INTEGER_OUT_OF_RANGE` | error | An integer is outside the I-JSON interoperable range. |
| `INVALID_UNICODE` | error | A string contains a surrogate or noncharacter. |
| `NON_CANONICAL_JSON` | error | Statement bytes are not the canonical encoding. |
| `SCHEMA_INVALID` | error | A required field, type, value, or relation is invalid. |
| `UNKNOWN_FIELD` | error | A protocol-defined object contains an unknown field. |
| `UNSUPPORTED_SCHEMA_VERSION` | error | The PCAW version is unsupported. |
| `UNSUPPORTED_DIGEST_ALGORITHM` | error | A digest algorithm other than SHA-256 is declared. |
| `AMBIGUOUS_TIMESTAMP` | error | A timestamp is missing or is not normalized UTC RFC 3339. |
| `SUBJECT_ROLE_MISMATCH` | error | Subjects and role declarations do not match one-to-one. |
| `SUBJECT_PATH_UNSAFE` | error | An artifact name is not a safe relative POSIX path. |
| `SUBJECT_ROOT_INVALID` | error | The selected artifact root is missing or cannot be opened safely. |
| `SUBJECT_MISSING` | error | A required artifact cannot be read. |
| `SUBJECT_SYMLINK_ESCAPE` | error | An artifact resolves outside the subject root. |
| `SUBJECT_PLATFORM_UNSAFE` | error | The platform lacks race-safe descriptor traversal support. |
| `SUBJECT_DIGEST_MISMATCH` | error | Artifact bytes do not match the statement digest. |
| `PCAW_EVIDENCE_SUBJECT_MISMATCH` | error | Evidence artifact digests contradict output subjects. |
| `WORK_STATE_DIGEST_MISMATCH` | error | The governance case does not match its virtual subject. |
| `CLAIMED_STATE_MISMATCH` | error | Claimed and independently derived lifecycle states differ. |
| `PCAW_SCOPE_OUTSIDE_BOUNDARY` | error | A changed path is outside the contract boundary. |
| `PCAW_EVIDENCE_MISSING` | error | Required evidence is absent. |
| `PCAW_EVIDENCE_STALE` | error | Evidence is not bound to the current attempt head. |
| `PCAW_RECEIPT_MISSING` | error | A terminal attempt has no receipt. |
| `PCAW_REVIEW_BINDING_STALE` | error | Review is bound to different contract, attempt, receipt, or evidence. |
| `PCAW_REVIEWER_NOT_INDEPENDENT` | error | Builder and reviewer identities collide. |
| `PCAW_HUMAN_QUORUM_INCOMPLETE` | error | Current qualified human decisions do not satisfy quorum. |
| `PCAW_ACCEPTANCE_HUMAN_UNQUALIFIED` | error | Acceptance is attributed outside the qualified quorum. |
| `PCAW_ACCEPTANCE_BINDING_STALE` | error | Acceptance is bound to stale or mismatched proof. |
| `PCAW_JOURNAL_CONTINUITY_FAILED` | error | Included journal continuity evidence reports corruption or divergence. |
| `ARTIFACT_CHECKS_SKIPPED` | warning | Statement-only mode did not check output bytes. |

The evaluator uses additional stable `PCAW_` codes to distinguish exact missing,
stale, contradictory, and out-of-order lifecycle records. The conformance
manifest pins the critical rejection codes. New diagnostic codes may be added
compatibly within v1; existing code meanings MUST NOT change. Security
limitations are structured report fields, not diagnostics.

## Verified properties

The report names these properties independently: `scope_compliance`,
`subject_integrity`, `evidence_freshness`, `receipt_binding`,
`independent_review`, `human_quorum`, `acceptance_currency`, and
`journal_continuity`. Each property has one of `verified`, `failed`,
`not-applicable`, or `not-checked`. Acceptance verification requires every
property required by the normalized case to be `verified`; optional journal
continuity remains a separately reported property for legacy workspaces.

## Guarantees

For supported PCAW v1 input, a conforming verifier provides falsifiable checks
for canonical statement bytes, exact work-state binding, safe artifact paths,
artifact SHA-256 integrity, normalized governance consistency, evidence and
receipt currency, independent review, current qualified human quorum,
acceptance currency, and any included journal continuity claim. Verification is
deterministic and needs no network, provider, credential, or source content.

The repository may use deterministic finite-state exploration and crash
injection to test the real implementation. Those tests are bounded software
verification, not mathematical formal verification.

## Non-guarantees and threat boundary

PCAW v1 does not:

- authenticate a named human, builder, or reviewer against a hostile process
  running as the same operating-system user;
- prove that a declared identity maps to a real person;
- sign statements, manage keys, provide non-repudiation, or protect key custody;
- make source contents true, complete, unbiased, or safe;
- prove semantic quality beyond the recorded contract and evidence;
- prevent an unrestricted local process from rewriting both artifacts and local
  governance files before a fresh proof is exported;
- authorize acceptance, merge, push, deployment, provider calls, or external
  writes.

Every predicate and verification report repeats these limitations in structured
form. A verifier must not describe declared attribution as authenticated.

## Future DSSE-compatible envelope

PCAW v1 ships unsigned in-toto statements. A future version may wrap the exact
canonical statement bytes in a DSSE envelope whose `payloadType` identifies
PCAW and whose signatures cover DSSE pre-authentication encoding. That future
layer must specify algorithm agility, key identity, revocation, threshold
policy, custody, and verification time. Implementations MUST NOT emit an empty
DSSE envelope, placeholder signature, inferred signer, or claim of
authentication in v1. Adding signing requires a versioned protocol decision; it
is not an implementation detail of this unsigned format.

## Conformance corpus

`vectors/manifest.json` lists valid and invalid statements and their expected
report properties or diagnostic codes. `conformance.py` is a dependency-free
black-box runner. It does not import Palari. The verifier command follows the
PCAW CLI contract and is supplied after `--`:

```bash
python3 spec/pcaw/v1/conformance.py -- ./bin/palari proof verify
python3 spec/pcaw/v1/conformance.py -- another-pcaw-verifier
```

For each case the runner appends the statement path, `--subject-root`, and
`--json`, then checks process status and the stable report fields. Vector
validity is normative even when a JSON Schema cannot express a lexical rule
such as duplicate-key or canonical-byte rejection.

Run the two-minute, network-free tamper demonstration with:

```bash
./scripts/pcaw_demo.sh
```

It verifies the accepted bundle, changes one governed artifact byte in a
temporary copy, and requires the verifier to reject it with
`SUBJECT_DIGEST_MISMATCH`.

## Trusted code manifest

`trusted-code.json` records the verifier modules, source hashes, source line
counts, and direct dependency graph. Regenerate it with
`python3 scripts/update_pcaw_tcb.py`; use `--check` in verification. The manifest
is transparency evidence, not a signature. Growth requires a concrete safety
justification in the work completion contract.
