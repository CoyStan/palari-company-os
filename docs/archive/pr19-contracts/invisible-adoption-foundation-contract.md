# Invisible Adoption Foundation v1 — Integration Contract

Integration work item: `WORK-E6AE25B296B340F89F24380B209DC64B`

Superseded pre-expansion item: `WORK-3B7821F3452B40B283784832E86234C3`

Bounded precursors:

- Golden Path Repair: `WORK-C11EE25A4D42414BBAD382121E89E070`
- Compact Journal v2: `WORK-A06D321334B74BFD878154776F299E57`
- Invisible Product Surface: `WORK-31D9DD73A7A045BC8236FA561291D064`
- Universal Agent Adoption: `WORK-BF48A3D891A7428FB91AA80BF53856AA`

Baseline: `f6e2cf9b3f59e4074ca459368103d802a4eb3b81`

Setup head: `bfec21a2044d4aa53943b5331502c761bc98c72c`

Baseline verification: `./scripts/verify.sh` passed 876 tests across 46
modules, style, trusted-code accounting (5 files / 2,405 SLOC), and 18/18 PCAW
vectors in 113.59 seconds with 358,556 KB peak RSS.

Status vocabulary is `pending`, `in progress`, `completed`, or `blocked`.
Every completed checkbox names exact committed proof. The approved immutable
successor owns final proof; the earlier claim and its narrower contract remain
auditable rather than being silently rebaselined. The founder still receives
one final presentation-bound acceptance action, not four branch-specific
approval ceremonies.

## Required Outcomes

- [x] **Golden path is truthful and executable**
  - Required outcome: a clean repository follows init, bounded work creation,
    start-next, one bounded commit, and advance without an undocumented Git
    bootstrap failure or copied proof IDs.
  - Objective evidence: isolated real-Git transcript completes R1 and preserves
    immutable authority, unrelated staged work, existing instructions, and
    fail-closed unusual states.
  - Verification command or artifact: onramp, demo, operator-journey, runtime,
    and install smokes.
  - Current status: completed; isolated journey, demo, docs, and install checks pass.
  - Exact committed evidence when completed: `ed877ed1c03179ce5895fa6533a4c628dcf2d787`
    with verification record `ded82cd0efdeb09b42a09b6e8019b2c621a2e994`.

- [x] **Journal cost is proportional to logical change**
  - Required outcome: compact v2 checkpoint/delta history remains strict,
    replayable, crash-safe, and backward-compatible without loading or copying
    the full historical projection on ordinary reads and writes.
  - Objective evidence: v1/v2 continuity, prefix replay, corruption, crash,
    retry, bounded-memory, compactness, and three-run timing evidence.
  - Verification command or artifact: journal/crash/store suites and recorded
    dogfood-copy timings.
  - Current status: completed; compactness, crash, corruption, canonicality,
    product-flow, and timing tests pass. A later exact-predecessor repair
    streams and validates every sealed v1 state claim instead of trusting the
    v2 summary; its deliberately attributed legacy-history cost is recorded in
    the compact-journal safety amendment.
  - Exact committed evidence when completed: `13c7be140e8adaf2dba90a9aa26a33314696a45f`,
    `af4412597dcd1000010ef082b05a07cc55ed2106`,
    `a2b99fbdcb3c0e2b3f5e0a11f06b4eef6d08a2f2`, and
    `53400beeb3ab833b22fc3eb056ae0d7549874141`, with exact predecessor-state
    enforcement at `cb67ab67c48a49b238936b87d3b02cd36dfd5bde`.

- [x] **Ordinary product surface exposes concepts, not ceremony**
  - Required outcome: default help and operator views foreground init, work,
    agent start/advance/doctor, queue/detail, and proof; advanced compatibility
    commands remain parseable. Superseded/abandoned work is explicit,
    attributable, auditable, and absent from ordinary active queues.
  - Objective evidence: help snapshots, terminal-state schema/validation,
    successor-cycle, active-attempt, authority, queue/inbox, explicit-start,
    compatibility, and migration tests.
  - Verification command or artifact: public-surface, validation, read-model,
    packet, docs, and schema suites.
  - Current status: completed; 154-command compatibility, read-model,
    retirement, storage-terminal, schema, and docs checks pass.
  - Exact committed evidence when completed: `974121cac0fca752151de684caf4488b9e292829`,
    `0e72d370c9fede44361340e60e1f2f97f032612c`,
    `54bb18e117208932da05617315b0ec2ded53a3c8`,
    `06551e64c4d056a6c55fbbcb1ba960e63e599710`, and
    `44597e83a27797ae81067dc8f3f94e31bbdef3c6`, with atomic retirement
    transition and proposal sealing at
    `ef22a65d11a60b362a7cd959d54f7444b24ba267`.

- [x] **Any supported agent can adopt the same bounded loop**
  - Required outcome: one honest host adoption action installs portable
    instructions, a structural Git gate, proven native hooks where available,
    and a complete agent-safe MCP loop without granting human authority.
  - Objective evidence: the universal adoption contract is fully satisfied.
  - Verification command or artifact:
    `docs/product/universal-agent-adoption-contract.md` and its focused suites.
  - Current status: completed; the provider profiles, native hooks, commit
    gate, portable contract, and agent-safe MCP loop pass focused tests.
  - Exact committed evidence when completed: `92bca37449246ba9f34d301028157640d96794e4`,
    `485cb7bb4b85f4364e6fe1e19f4e05be975b75b8`,
    `8ea7816fee11fe753345f122f23c48a5f89771d0`,
    `06551e64c4d056a6c55fbbcb1ba960e63e599710`, and
    `53400beeb3ab833b22fc3eb056ae0d7549874141`, with foreign-command
    preservation at `f9620da7a8d6728c35e27e09b0c2d820c214f80a`, installed and legacy-host
    compatibility at `6c2d70324e97326397478c336fb047d5d750c32a`, executable ownership at
    `4ced628bfcc6988c914db81b0cf2bd69b05b5cd4`, and final symlink-boundary
    compatibility at `c5e148abc4bfef7cd2d57d1cb57d25d386e50e2d`. Exact installed-executable
    binding for the structural Git gate is committed at
    `5358cdef47336515694de7df2fbf61c5a607d37e`.

- [ ] **One coherent, verified, review-accepted candidate**
  - Required outcome: all four slices compose on one exact committed head,
    precursor work is terminalized without erased history, all attributable
    checks pass, performance is honestly compared, and a fresh independent
    reviewer returns ACCEPT before one founder action is requested.
  - Objective evidence: clean changed-path check; docs/schema/fixture, CLI,
    security, PCAW conformance, affected, complete, and isolated-install gates;
    timing table; review artifact; Approval Pack bound to exact presentation.
  - Verification command or artifact: `./bin/palari validate --json`,
    `./bin/palari docs check --json`, PCAW conformance, `./scripts/verify.sh`,
    `./scripts/install_smoke.sh`, agent check/advance/handoff, and review history.
  - Current status: in progress. Human decision
    `DECISION-FOUNDATION-AUTHORING-SCOPE` approved the exact additional path.
    Palari then refused to rewrite the already-claimed contract, so the old item
    was restored to its original boundary, auditably superseded, and linked to
    immutable successor `WORK-E6AE25B296B340F89F24380B209DC64B`. The successor
    is claimed and ready for deterministic proof derivation; durable lifecycle
    review and human acceptance remain pending.
  - Exact committed evidence when completed: not yet complete. Candidate code
    is exact head `1c3664c0de12c5eb8eed5f718a168b66d904288a`; installed-hook and
    generated-documentation preflight repairs pass focused tests. A fresh
    independent implementation reviewer returned ACCEPT for exact head
    `54b0995d26470c103316b46b1787ab3009cb021a`. All four precursors are
    auditably superseded by the integration lineage
    at `cc96d088d42ac1b3bf4bb4565c3496d87b3aff11`; the fail-closed scope
    decision and approved scope are committed at
    `8b02b87f09bae6bd91b4bfe54874434136d49fd2`; immutable successor creation
    and old-item retirement are committed at
    `a3f203a1699dcde3190550401502466da56ee289`. Final proof and presentation
    remain unavailable until the successor completes normal durable review.
    Durable review at `313f482bfb940df81e4d0943258174d561e46fff`
    requested exact sealed-v1 summary validation; the repair and eight-field
    negative coverage are committed at
    `cb67ab67c48a49b238936b87d3b02cd36dfd5bde` and await attributable complete
    verification plus fresh review.

## Complete-Gate Timing

| Candidate | Tests | Recorded wall time | Peak RSS | Comparison |
| --- | ---: | ---: | ---: | --- |
| Baseline `f6e2cf9` | 876 | 113.59 s | 358,556 KB | single recorded baseline |
| Implementation `6c2d703` | 946 | 111.86 s | 218,180 KB | three-run median; 1.52% lower wall time and 39.2% lower RSS than the recorded baseline |
| Exact reviewed code `54b0995` | 949 | 110.83 s | 224,248 KB | single exact-head run; 2.43% lower wall time and 37.46% lower RSS than the recorded baseline |

The exact reviewed code adds 73 tests while remaining inside the performance
budget. Because the baseline and exact-head values are individual runs while
the middle row is a three-run median, these comparisons are directional rather
than like-for-like distributions. The authoritative gate is still
`./scripts/verify.sh`; focused profiles exist only to shorten development
feedback, not to replace acceptance checks.
