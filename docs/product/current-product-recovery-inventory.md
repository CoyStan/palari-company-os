# Current Product Recovery Inventory

Status: baseline and reduction ledger for Current Product Recovery and
Architectural Reduction v1. Final candidate metrics remain pending.

This ledger records the repository as recovered at
`b71494fee2c94722261d4f2a199806a93aa9a87a`. It is evidence for reduction, not
a compatibility promise. The current product definition is maintained
separately in `current-product.md`.

## Protected baseline

- Branch: `codex/current-product-reduction`.
- Starting commit: `b71494fee2c94722261d4f2a199806a93aa9a87a`.
- Worktree: clean before inventory.
- Hooks: no local `core.hooksPath` and no active file in `.git/hooks/`.
- Remote use: local orientation only; no remote write was performed.
- Rollback: the immutable starting commit above is the exact rollback target;
  repository history was not rewritten.
- Baseline verification: `./scripts/verify.sh complete` ran once from an
  isolated local clone so its CLI smokes could not touch this cleanroom or its
  dogfood workspace. It passed 950 tests and 18 PCAW vectors in 147.66 seconds
  wall time (335.67 user, 36.21 system).

The counts below use tracked files at the starting commit. “Source” means the
Python package unless a broader count is explicitly named.

| Measure | Baseline |
| --- | ---: |
| Tracked files | 266 |
| Package Python source files | 84 |
| Package Python source lines | 53,196 |
| Product Python/shell entry source files, including scripts and PCAW runner | 91 |
| Product source lines under that broader definition | 54,177 |
| Package functions and methods | 1,702 |
| Package classes | 86 |
| Public CLI command paths | 154 |
| Test modules | 47 |
| Test methods | 950 |
| Test lines | 29,914 |
| Product documentation files under `docs/` | 51 |
| Product documentation lines under `docs/` | 14,192 |

Static test inspection found 326 direct subprocess call sites in 35 modules,
195 temporary-directory allocation sites in 36 modules, 24 copy sites in 13
modules, and 283 Git command literals in 11 modules. The committed dogfood
workspace contains an approximately 64 MB governance journal, a 1.2 MB legacy
history log, and an 870 KB workspace projection. Those artifacts are retained
as historical evidence, but they are not suitable ordinary test fixtures.

The slowest areas reported by the one timed gate were:

| Test module | Baseline duration |
| --- | ---: |
| `tests.test_agent_packets` | 65.814 s |
| `tests.test_agent_advance` | 64.347 s |
| `tests.test_workspace_read_models` | 61.543 s |
| `tests.test_review_guides` | 27.381 s |
| `tests.test_integrations` | 23.636 s |

These are aggregate module durations from the parallel gate, not a request to
benchmark every module. Static inspection explains them: full workspaces,
journals, Git repositories, claims, lifecycle records, and CLI subprocesses
are repeatedly reconstructed above the kernel boundary.

## Capability ledger

Every row is one classification. `CURRENT-CORE` is reserved for behavior
required by the current thesis. `CURRENT-ADAPTER` is supported but optional.
`REQUIRED-MIGRATION` requires committed real stored data. `AMBIGUOUS` parks a
decision; it does not promote the item into the supported product.

| Class | Surface | Objective evidence and reduction boundary |
| --- | --- | --- |
| CURRENT-CORE | Pure governance case and evaluator: `governance_case.py`, `governance_kernel.py` | `evaluate_governance_case` is used by PCAW export/verification and terminal transition checks, and is named in the five-file verifier TCB. It is the authoritative implementation of lifecycle, exact proof, independent review, human quorum, and acceptance currency. |
| CURRENT-CORE | Workspace v2 model, loader, validation, and store: `models.py`, `workspace.py`, `validation.py`, `store.py`, root schema | Runtime requires schema version 2 and fails closed on malformed state, unknown fields, unsafe references, and concurrent writes. Version 2 is the only committed workspace format used by current example and dogfood workspaces. |
| CURRENT-CORE | Scope, path, and exact artifact boundaries: `path_policy.py`, `scope.py`, `agent_file_changes.py`, `evidence_manifest.py`, `governance_binding.py`, `record_order.py` | Current packets, hooks, evidence, review, PCAW, transitions, and acceptance call these boundaries. They implement traversal, symlink, canonical-path, artifact-binding, and temporal-order guarantees. |
| CURRENT-CORE | Compact governance journal v2 writer/replay/tamper path in `governance_journal.py` and journaled store writes | Replay, continuity, crash recovery, and tamper detection are essential guarantees. New operational writes should have one current format and one writer. |
| REQUIRED-MIGRATION | Governance journal v1 reader/verifier | `workspaces/palari-company-os/.palari/governance-journal.v1.jsonl` is a committed real predecessor (about 64 MB and 230 records). Keep only the narrow reader/activation boundary required to authenticate that data; v1 must not remain the default writer. |
| AMBIGUOUS | Content-addressed checkpoint restoration in `checkpoints.py` | Current docs describe append-only restoration, but restoration is outside the essential work lifecycle. Preserve it while its current product purpose is decided; it must not expand the core gate by default. |
| CURRENT-CORE | PCAW v1 canonicalization, subjects, export, verifier, schemas, vectors, and TCB | `proof export` and `proof verify` are reachable; the 18-vector corpus is provider-neutral and offline. `spec/pcaw/v1/` is the normative supported proof format. |
| CURRENT-CORE | Ordinary agent execution: `init`, `work add`, `agent start --next`, `agent advance`, and durable `agent release` | README, Quickstart, root contract, and focused help agree on this route. Start binds scope and claim state; advance records exact attempt, receipt, and evidence and stops at authority boundaries. |
| CURRENT-CORE | Portable session contract, claims, Git witness, leases, and file-change observation | `agent_session_contract.py`, `agent_runtime.py`, `agent_file_changes.py`, and current start/advance paths bind an agent to exact scope and repository state. |
| CURRENT-CORE | Independent review and exact human authority: approval inbox, presentations, packs, transition gates, and convergence | The current operator path is `queue --approval-inbox` followed by one exact presentation-bound human action. Agents cannot record the review or decision. |
| CURRENT-CORE | Queue, detail, state, and approval read projections | These are the ordinary inspectable views. Their lifecycle fields must become translations of the kernel result; their current independent authority matrix is not authoritative. |
| CURRENT-CORE | Provider-neutral external-effect plan and outbox boundary | Generic plans and outbox records are local governed state and do not execute providers. They preserve the stop-before-external-effect guarantee. |
| CURRENT-ADAPTER | CLI parser, dispatch, output, and installed entry point | The CLI is the supported local translation boundary. Its 154-path snapshot is a measurement, not a retention requirement. |
| CURRENT-ADAPTER | MCP stdio server | Current MCP tools expose bounded read/agent operations without review, human-decision, acceptance, deploy, push, or external-write authority. Retain protocol and capability-limit wiring only. |
| CURRENT-ADAPTER | Git commit gate | The Git hook is an optional structural enforcement boundary over the same packet/path decisions. Retain boundary wiring, not a second governance matrix. |
| CURRENT-ADAPTER | Claude and Codex session adoption | Current docs identify these as the two tested session adapters. They may enforce the portable contract but grant no review or human authority. |
| HISTORICAL-ONLY | Removed Cursor, Devin, GLM, and generic session-profile aliases | No native adapter, committed configuration fixture, or stored workspace field distinguished these labels. They duplicated the host-neutral contract and Git gate while exposing an unsupported compatibility surface; Git preserves their history. |
| CURRENT-ADAPTER | Linear issue/comment/webhook adapter | `linear-operating-loop.md` is an explicit current adapter contract. Provider writes are downstream of the core plan/approval/outbox boundary. Adapter tests should cover translation, redaction, signature/deduplication, and capability limits only. |
| EXPERIMENTAL | Slack, GitHub, Jira, and email provider preview shapes | `public-surface.md` labels them future and no live adapter exists. Generic plan/outbox behavior does not require permanent provider-specific pseudo-support. |
| CURRENT-ADAPTER | Local Mission Control | Current Quickstart presents `serve` as optional local human supervision. It projects current read models and delegates integration-plan decisions to the governed integration service. Its duplicate raw decision synthesis was removed; exact human acceptance remains exclusive to the Approval Inbox action. |
| EXPERIMENTAL | Static desktop prototype, desktop server, assets, desktop demo, and Pages deployment | The desktop contract explicitly calls this a static prototype rather than a supported backend or schema. It is not part of the thesis and creates a separate visual compatibility obligation. |
| CURRENT-ADAPTER | Agent-ready repository docs (`docs check/init/map`) | This reachable optional adapter produces and validates repository orientation used by adoption. It must not govern product state. |
| CURRENT-ADAPTER | Network-free demo and ACME example | The primary first-run path exercises the current route in a temporary Git workspace. It is a boundary smoke/example, not a second lifecycle. |
| DUPLICATE | `lifecycle evidence/review/decide/complete/outcome` command family | These six paths call the same authoring functions as direct evidence, review, human-decision, work-complete, and outcome commands. They add a second grammar, not a second capability. |
| SUPERSEDED | `agent done` | Docs identify it as the older R1 shortcut; `agent advance` is the current deterministic path. Production calls come only from dispatch. Reusable Git preflight helpers must move to a current boundary before deletion. |
| SUPERSEDED | Receipt-only R1/R2 completion | `_legacy_receipt_completion` plus parallel branches in read models, packets, validation, authoring, transitions, authority profiles, and advance allow completion without exact evidence. That contradicts the current guarantee that completion requires current exact evidence. |
| SUPERSEDED | `workspace init` | Only dispatch/tests call the empty-workspace constructor. Top-level `init` creates the current starter contract, journal, identities, docs, and optional host profile. |
| SUPERSEDED | Old standalone Claude installer in `claude_hooks.py` | Current dispatch uses the adoption implementation. The older installer and installer-only helpers have test callers but no production caller. |
| DUPLICATE | Operational `.palari/history.jsonl` writer and reader | Every mutation is already journaled. `history.py` appends a second, non-replayable, non-hash-chained log after authoritative writes, and default `history` reads that duplicate log. |
| HISTORICAL-ONLY | Committed `.palari/history.jsonl` artifact | Dogfood commits about 569 events. Preserve the bytes as historical evidence; runtime need not keep producing or importing this older operational architecture. |
| DUPLICATE | Lifecycle/authority derivation outside the kernel | `read_models`, `validation`, `transition_checks`, `authoring`, `approval_packs`, `governance_convergence`, and `agent_checks` independently calculate stale evidence, review currency, quorum, and acceptance. Consumers must translate one normalized kernel evaluation instead. |
| DUPLICATE | State-to-next-action derivation across read models, packets, checks, directive, and candidate selection | Several layers classify the same lifecycle state and generate overlapping commands. `AgentOperation` only partially consolidates them. One pure directive projection should serve retained surfaces. |
| HISTORICAL-ONLY | Removed packaged schema/example byte copies | The root schema and example remain the repository sources. Identical package-data copies and the hidden ACME default-workspace fallback created a second executable authority with no migration need, so Git preserves their history instead. |
| UNREACHABLE | Private helpers `_git_status`, `_git_root`, `_staged_files`, `_allowed_write_paths`, `_review_binding_dict`, `_normalize_path`, `_matching_fresh_passed_evidence`, and `_read_records` | Static caller inspection found no production caller; `_read_records` is referenced only by a test patch. Delete after focused import/caller confirmation instead of refactoring them. |
| SUPERSEDED | Workspace v0/v1 migration and `migrate` command | No committed real v0/v1 workspace fixture exists; migration tests synthesize old input by editing v2 data. The task explicitly disallows compatibility for hypothetical stored data. |
| SUPERSEDED | Historical claim-v1 and approval-pack-v1 compatibility branches | No committed claim, packet, witness, lease, pack-v1 manifest, or pack-v1 decision fixture establishes these branches. Tests synthesize them. They cannot justify keeping old operational architecture alive. |
| REQUIRED-MIGRATION | Schema-v2 work items without `path_intents` | 66 of 67 dogfood work items and all seven ACME work items use the older `output_targets` presence contract. Keep one narrow reader/normalizer for those committed records; newly authored work should use exact create/modify/delete intents when mutation class matters. |
| REQUIRED-MIGRATION | Historical evidence without `output_binding_version` | 21 of 70 dogfood evidence records and all four ACME evidence records omit the additive version. They must remain inspectable but cannot gain stronger output-coverage authority by inference. |
| REQUIRED-MIGRATION | Unbound negative/non-accepting reviews | 23 of 48 dogfood reviews are historical unbound records, while every committed accept-ready review is bound. Retain read-only inspection of negative history; an unbound record must never count toward acceptance. |
| CURRENT-CORE | Exact review binding v1 | 25 committed dogfood reviews use the current binding and every committed accept-ready review is bound. This is current proof, not legacy compatibility. |
| AMBIGUOUS | Split `collection_files` support | Current docs and a synthetic fixture exist, but neither the current example nor dogfood workspace uses it. Park deletion until its supported-product purpose is decided. |
| AMBIGUOUS | Explicit agent inspection/recovery helpers (`next`, `brief`, `check`, `finish`, `handoff`, `loop`, `doctor`) | They are reachable and documented, but the ordinary path no longer requires their multi-command ceremony. Keep while consumers are reduced; do not count them as core by default. |
| AMBIGUOUS | Maintainer status, external playbooks, gate recommendations, and capability/authority recommendation views | Each is reachable and documented but not required by the lifecycle thesis. Retention requires an explicit optional-adapter contract. |
| AMBIGUOUS | Goals, workbenches, proposals, and broad generic create/update grammar | Actor, source, and work contracts have clear current consumers. The broader planning/coordination object model is not proven necessary by mere schema and test existence, so destructive action is parked. |
| AMBIGUOUS | `docs/product/roadmap.md` | README previously treated it as current status, but it mixes unresolved strategy with named work that has already shipped. Park deletion and remove it as product authority until a human resolves its purpose. |
| EXPERIMENTAL | `docs/product/palari-blueprint.md` | Its own header identifies a dated strategy proposal and candidate PCAW v2 work, not a normative specification or execution backlog. Retain only as explicitly unsupported research. |
| HISTORICAL-ONLY | Dogfood workspace as an executable test dependency | Its files are evidence and must remain unchanged. Ordinary verification must stop scanning its complete history to preserve old operational behavior. |
| HISTORICAL-ONLY | Completed implementation contracts and reviews under `docs/product/` | The `approval-packs-*`, `compact-journal-*`, `deterministic-agent-*`, `golden-path-*`, `governance-hardening-*`, `invisible-*`, `opaque-*`, `portable-*`, `presentation-*`, `proof-carrying-governance-*`, and `universal-agent-*` documents record work IDs, statuses, commits, and past completion evidence. Current invariants belong in concise normative docs; Git retains the historical implementations. |
| HISTORICAL-ONLY | `docs/archive/` | Existing public-surface documentation already classifies these plans and research notes as archive. No runtime consumer exists. |
| EXPERIMENTAL | `docs/showcase/` | Optional narrative examples have no runtime consumer and are not part of the supported contract. |
| CURRENT-ADAPTER | Packaging and release workflow | A dependency-free wheel and installed CLI are supported distribution boundaries. Release publication remains human/external infrastructure and is not run by candidate verification. |

### Public command evidence

The 154-path snapshot contains 44 top-level paths and 110 nested paths. The
largest groups are `linear` (19 paths), `agent` (12), `integration` plus
`integrations` (10), `work` (7), `lifecycle` (6), `capability` (6), and
`proposal` (6). Default help exposes only `init`, `work`, `agent`, `queue`,
`detail`, `proof`, `validate`, and `docs`.

The statement in `public-surface.md` that all 154 paths remain parseable for
compatibility is historical policy and conflicts with this recovery's explicit
compatibility rule. Reachability proves that a surface exists; it does not
prove that the surface belongs to the current product.

## Test inventory

The disposition column names the current invariant or explains why the test is
not authoritative. “Thin” means one or two translation/wiring cases after the
kernel owns the state matrix. “System boundary” means real filesystem, Git,
journal, subprocess, or installation work is justified.

| Test module | Layer and authoritative implementation | Disposition and expensive work |
| --- | --- | --- |
| `test_governance_kernel.py` | Core lifecycle; `governance_kernel`/`governance_case` | Retain and expand as the exhaustive pure table-driven authority. No system fixture is needed. |
| `test_governance_explorer.py` | Core lifecycle reachability; real evaluator | Retain pure deterministic state exploration and substantive-mutation invalidation. |
| `test_one_action_convergence.py` | Zero-quorum kernel cases | Fold its three cases into the kernel matrix; it is not a separate invariant. |
| `test_transition_checks.py` | Mutation choke-point translation | Retain thin wiring for trusted transitions. Remove its duplicate lifecycle matrix and public-command count assertion. |
| `test_validation.py` | Workspace structure, references, locks, and schema | Retain structural/parser/store cases. Move lifecycle semantics to the kernel and remove synthetic legacy migration cases. Uses temporary files and some subprocesses. |
| `test_governance_completion.py` | Older manual capability/proposal/attempt/receipt/evidence/review ceremony | Replace roughly 39 CLI-helper calls with one current golden path; proof and authority cases belong to their kernels. |
| `test_workspace_read_models.py` | Queue/detail/state translation | Retain deterministic projection cases and minimal CLI wiring. Remove the duplicate lifecycle matrix and dogfood dependency. Baseline: 61.543 s. |
| `test_path_policy.py` | Pure lexical/canonical path rules | Retain as cheap authoritative scope input validation. |
| `test_filesystem_security.py` | Symlink, canonical-path, descriptor/artifact, and Git observation | Retain a focused real filesystem boundary set; keep pure cases with path policy. |
| `test_agent_file_changes.py` | Path-intent/tombstone translation | Move pure intent cases to the scope boundary and retain one Git observation case. Delete compatibility-only legacy packet-shape coverage. |
| `test_canonical_json.py` | PCAW strict canonical JSON | Retain pure edge cases. |
| `test_pcaw_protocol.py` | PCAW serialization/export/offline verification | Retain protocol logic and one CLI boundary. Remove cases already made normative by the 18-vector corpus. Uses subprocess and temporary subject roots. |
| `test_governance_journal.py` | Current replay, continuity, delta, tamper, request-local reuse | Retain current-v2 behavior; isolate the real required v1 reader. Synthetic v1 creation is not proof of broader compatibility. |
| `test_governance_journal_crash.py` | Prepare/commit/recovery crash boundaries | Retain the genuine current transaction matrix and only fixture-justified predecessor activation. |
| `test_store_journal_integration.py` | Store-to-journal wiring and immutable retirement | Retain a small integration set after lifecycle decisions move to the kernel. |
| `test_history.py` | Separate legacy history implementation | Delete with the duplicate runtime writer/reader; committed historical bytes remain. |
| `test_reversible_checkpoints.py` | Checkpoint restoration and crash matrix | Park with the ambiguous capability; if retained, keep outside the essential candidate gate or reduce to its unique guarantees. |
| `test_agent_advance.py` | Current claim-to-proof convergence | Retain pure planning/fixed-point/attestation cases and a small exact end-to-end path. Its 94-test integration class creates a workspace, journal, Git repo, claim, baseline commit, and output commit for each test. Baseline: 64.347 s. |
| `test_agent_packets.py` | Packet/claim/witness plus next/brief/check/finish/handoff/loop/doctor translations | Retain claim/witness integrity and thin translations. Remove repeated lifecycle matrices and output wording checks. Baseline: 65.814 s. |
| `test_agent_done.py` | Superseded R1 shortcut | Delete after shared Git preflight helpers move to a current module. Fourteen Git-heavy tests protect a retired command. |
| `test_agent_session_contract.py` | Portable deterministic scope and exact claim binding | Retain current contract tests; remove synthesized claim-v1 compatibility. |
| `test_onramp.py` | Current `init`/`work add` construction and anchoring | Retain current construction plus limited Git anchoring. Move host installation matrices to adapter tests. |
| `test_operator_journeys.py` | Current end-to-end operator/agent path and durable release | Retain one golden path and genuinely distinct interruption/retry behavior. Uses Git, journals, CLI, and temp workspaces. |
| `test_cli_smoke.py` | CLI translation | Reduce about 40 CLI invocations to one current golden path and one machine-readable failure boundary. |
| `test_approval_packs.py` | Exact batch human authority and journaled decision | Retain aggregation, binding, staleness, and unique transaction boundaries. Move per-item lifecycle validity to the kernel; keep scale checks selective. |
| `test_approval_presentations.py` | Exact presentation projection/digest | Merge into approval-pack coverage and remove synthetic pack-v1 compatibility. |
| `test_review_guides.py` | Read-only review presentation | Retain at most thin translation tests if the guide remains supported; delete receipt-ready and lifecycle repetition. Baseline: 27.381 s. |
| `test_decision_guides.py` | Read-only human-decision presentation | Retain at most thin translation tests if supported. |
| `test_gate_profiles.py` | Optional recommendation UX | Keep outside core only if explicitly retained as an adapter; it is not authority. |
| `test_git_hooks.py` | Commit-boundary adapter | Retain a small integration suite. All 22 tests currently initialize and commit a Git repository; pure scope decisions belong in the kernel. |
| `test_claude_hooks.py` | Claude shell/tool classifier and session wiring | Retain valuable pure adversarial classification plus a few current adapter integrations; remove old installer compatibility. |
| `test_agent_adoption.py` | Claude and Codex host installation | Retain meaningful configuration, symlink, rollback, executable-binding, and translation boundaries; reject removed profile labels without preserving their advisory behavior. |
| `test_mcp_server.py` | JSON-RPC and capability translation | Retain protocol and authority-limit wiring only; remove lifecycle matrices. |
| `test_integrations.py` | Generic external plan/outbox | Retain core external-boundary cases, but remove its parallel human-approval lifecycle and route decisions through core authority. Baseline: 23.636 s. |
| `test_linear_adapter.py` | Linear normalization and governed translation | Retain normalization, redaction, capability limits, and one plan/outbox translation; avoid core lifecycle repetition. |
| `test_linear_webhook.py` | Signature, deduplication, and event translation | Retain security and one mapping path as optional adapter tests. |
| `test_workspace_init.py` | Duplicate initialization command | Delete with `workspace init`; top-level onramp tests own initialization. |
| `test_data_map.py` | Optional legacy-history visualization | Delete or park with the unsupported view; it currently depends on the duplicate history log. |
| `test_playbooks.py` | Optional recommendation UX | Keep outside core only if the adapter receives an explicit current contract. |
| `test_mission_control.py` | Local read-only UI plus integration-plan server/CSRF/CAS | Retain as optional adapter wiring tests only while the UI remains supported; exact human acceptance stays outside this surface. |
| `test_desktop_prototype.py` | Static prototype rendering/JavaScript | Delete with the experimental prototype. |
| `test_demo.py` | Temporary first-run story | Retain one boundary smoke outside the kernel suite if the demo remains the first-run path. |
| `test_docs.py` | Normative documentation and generated agent docs | Retain a narrower current-doc contract after historical completion documents are removed. |
| `test_public_surface.py` | Public command/schema/dependency snapshot | Retain as the single deliberate public-surface authority and update it for removals. |
| `test_packaging.py` | Removed duplicate package-data synchronization | The isolated wheel smoke is the packaging boundary; a unit test no longer protects deleted schema/example copies. |
| `test_verification_profiles.py` | Focused/affected verification routing | Rewrite after reduction. The current map names 37 source modules and falls back to all tests for the rest. |
| `test_workflows.py` | Pages/release workflow strings | Delete Pages assertions with the prototype; retain only meaningful release/candidate wiring if still supported. |

`tests/workspace_fixture.py` explicitly constructs a “stable legacy slice” from
dogfood records for agent and hook tests. That coupling is not migration proof;
current tests should build minimal current contracts directly.

## CI and verification inventory

The baseline CI is structurally duplicative:

- `push` runs on every branch and `pull_request` runs against `main`, so a PR
  branch push evaluates the same candidate twice.
- The complete job is multiplied across Python 3.10, 3.12, 3.13, and 3.14.
- Each job runs unit discovery directly, then invokes `verify.sh`, which runs
  all 47 modules again.
- Each job builds and installs a wheel, then `install_smoke.sh` creates another
  environment, rebuilds, and reinstalls it.
- Installed CLI smokes overlap `install_smoke.sh` and the complete gate's CLI
  smokes.
- `verify.sh` runs CLI reads against the repo root and dogfood workspace. The
  recovered gate must use temporary current fixtures instead.
- The Pages workflow exists solely to publish the experimental desktop
  prototype.

The candidate gate should therefore run the complete invariant suite once on
one canonical Python, run only an import/kernel/CLI compatibility smoke on the
other supported interpreters, build and install one wheel once, and avoid
simultaneous branch-push and PR evaluation of an identical candidate. The
complete gate must include:

1. pure governance/path/canonicalization tests;
2. focused filesystem, journal, proof, and current migration boundaries;
3. one current CLI golden path and structured failure path;
4. supported adapter contracts separated from core authority tests;
5. static/style/schema/PCAW conformance checks; and
6. one isolated installed-wheel smoke.

Full dogfood audit remains an explicit operator action, not an ordinary
candidate prerequisite. Persistent caches never become authority.

## Reduction order implied by the evidence

1. Define the current product and compatibility policy.
2. Remove receipt-only completion and `agent done`; completion always requires
   current exact evidence.
3. Remove the duplicate lifecycle grammar and duplicate initialization path.
4. Stop writing and reading the legacy history log at runtime while preserving
   its committed bytes.
5. Make journal v2 the sole current writer and isolate the fixture-required v1
   reader.
6. Route lifecycle, review, quorum, and acceptance projections through the
   governance kernel.
7. Delete experimental prototype and historical implementation documentation.
8. Reconstruct tests around pure invariants and genuine system boundaries.
9. Rebuild one authoritative verification/CI gate.

Ambiguous surfaces remain parked until the current product definition or new
objective evidence resolves them. They do not block the unambiguous reductions
above.

## Reduction result

The capability and test tables above describe the recovered baseline and the
evidence used to choose each slice. The reduction produced these dispositions:

- `agent done`, receipt-only completion, the duplicate `lifecycle` grammar,
  `workspace init`, the synthetic workspace `migrate` command, the operational
  `.palari/history.jsonl` implementation, claim schema v1, and Approval Pack v1
  were deleted. Current completion requires exact evidence and routes through
  the governance evaluator and trusted transition boundary.
- Governance-journal v2 is the sole current writer. The strict v1 journal is
  retained only as a sealed predecessor proven by committed data. Historical
  schema-v2 records without `path_intents` or `output_binding_version`, plus
  unbound non-accepting reviews, remain behind narrow read-only boundaries and
  gain no stronger authority by inference.
- Cursor, Devin, GLM, and generic session-profile aliases were removed. Claude
  and Codex remain the two tested session adapters over the same portable
  contract and host-neutral Git boundary.
- Speculative provider-specific preview shapes were removed. The generic
  external-action path is opaque and non-executing; Linear remains the only
  supported live provider adapter.
- The static dashboard/desktop prototype stack, demo schema, showcase, Pages
  workflow, historical implementation contracts, and archive documents were
  deleted. Git remains their historical record; Mission Control is the one
  supported local human UI.
- Identical packaged schema and ACME workspace copies, the hidden default
  fallback, and their synchronization tests were deleted. The root schema is
  authoritative, the ACME workspace is a repository example only, and package
  verification uses one isolated temporary wheel smoke.
- Packet, read-model, transition, validation, hook, MCP, integration,
  recommendation, Mission Control, and CLI tests were rebuilt around pure
  kernel decisions or genuine system boundaries. The committed example and
  dogfood workspace are not executable candidate fixtures.
- Exact human acceptance is exposed through the digest-bound Approval Inbox
  action, not a raw Mission Control decision form. Approval Pack batching now
  derives in the kernel only from declared risk, canonical external-write
  authority, and recorded external effects; prose keywords grant no authority.
- CI now has one authoritative complete candidate on Python 3.12, thin
  compatibility checks on the other supported interpreters, and one wheel
  build/install. Focused verification runs only explicitly named modules; the
  affected-path registry and hidden full-suite fallback were removed.

The parked decisions remain parked: checkpoint restoration, split collection
files, broad planning/coordination objects, and optional recommendation/status
views are not promoted into `CURRENT-CORE` merely because their code remains.
They may be resolved only with new objective product evidence.

### Final candidate evidence

These measurements were taken from the committed candidate immediately before
its authoritative complete gate. Counts use the same definitions as the
baseline inventory.

| Measure | Baseline | Final candidate |
| --- | ---: | ---: |
| Candidate commit | `b71494fee2c94722261d4f2a199806a93aa9a87a` | `7ab453d18204a26dae9bfa360ffa2bebd871abfd` |
| Tracked files | 266 | 220 |
| Package Python source files | 84 | 78 |
| Package Python source lines | 53,196 | 49,464 |
| Package functions and methods | 1,702 | 1,576 |
| Package classes | 86 | 90 |
| Public CLI command paths | 154 | 142 |
| Test modules | 47 | 41 |
| Test methods | 950 | 560 |
| Test lines | 29,914 | 18,805 |
| Product documentation files under `docs/` | 51 | 32 |
| Product documentation lines under `docs/` | 14,192 | 7,762 |
| Complete-gate result | pass | pass: 560 tests, 18 PCAW vectors, wheel smoke |
| Complete-gate wall time | 147.66 s | 37.97 s |
| PCAW conformance vectors | 18 | 18 |

Final verification command: `./scripts/verify.sh complete`.

The verified commit was on `codex/current-product-reduction` with a clean
worktree. No repository, Claude, or Palari hooks were installed. A byte diff of
`workspaces/palari-company-os/` against the protected baseline was empty. The
evidence-only ledger commit that follows changes no product, test, proof, or
dogfood bytes.
