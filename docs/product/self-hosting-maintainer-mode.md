# Self-Hosting Maintainer Mode

Palari must be repairable without making its own source candidate depend on a
broken instance of the workflow being repaired. This document defines the
temporary exception used to deliver that repair and the narrower mechanical
profile now available for later source maintenance.

## Current Status

Maintainer Profile v1 is implemented as an explicit, ignored,
repository-bound local storage profile:

```text
palari init --profile maintainer
```

It records assignments, checks, reviews, approvals, and local results beneath
the bound hidden state root while source identity remains the exact Git
candidate. Every emitted executable action selects the exact hidden workspace;
omitting that selector continues to resolve only an ordinary `workspace.json`.
The declared R1/R2 risk and intensity remain visible, but every maintainer task
has one authoritative `complete` verification profile, one independent agent
review, and at least one human approval. Maintainer Profile v1 never uses the
ordinary R1/light automatic-completion exemption.

The tracked root `workspace.json` and root `.palari` directory remain product
artifacts and historical evidence. Maintainer Profile v1 neither imports nor
mutates them. Tests that exercise profile state use temporary Git repositories
and temporary workspaces.

The source change that first implemented this profile used the bounded
procedural exception below. A feature cannot retroactively authorize its own
bootstrap candidate.

## Founder-Authorized Exception For This Repair

The current Self-Hosting Without Ceremony repair has an explicit, bounded
maintainer exception. It does not use Palari's live task, assignment, review,
Approval Pack, decision, acceptance, or completion workflow to authorize
changes to Palari itself.

For this repair:

- Git identifies the exact source candidate.
- Focused tests provide fast attributable feedback while the repair is being
  developed.
- The complete verification profile runs once when the candidate is coherent,
  with one attributable rerun only after a substantive repair.
- A fresh independent agent reviews the exact committed candidate.
- One real human performs the final acceptance action.
- The builder and reviewer remain distinct.
- An agent may present the final human action but must never execute it or
  manufacture the human's acceptance.
- Production governance behavior is exercised only in temporary workspaces.
- The tracked root `workspace.json` and root `.palari` state are not an
  acceptance prerequisite and are not changed as live state.

This exception authorizes local source repair and verification only. It does
not authorize:

- a push or pull request;
- a merge or release;
- deployment;
- provider calls or external writes;
- use of credentials or secrets;
- weakening exact checks, review independence, human authority, journal
  continuity, or task boundaries; or
- copying or continuing the recursively blocked state from another checkout.

The final human acceptance for this repair is an attributable maintainer
decision about one exact Git candidate. It is not a Palari acceptance record
and must not be described as one.

## Not A Customer-Workspace Bypass

The exception applies only when maintainers are repairing Palari's own
governance workflow and the production workflow cannot safely govern that
repair. It does not apply to customer workspaces, ordinary dogfood work,
provider actions, policy changes, deployments, or other repositories merely
because their normal workflow is inconvenient.

Ordinary workspaces continue to require their declared checks, independent
review, human approval, freshness checks, and external-action boundaries.
Maintainer mode must not relax those rules or reinterpret an agent review as
human approval.

## Required Maintainer Evidence

A maintainer candidate is eligible for final human inspection only when all of
the following are true:

1. The exact candidate is a named Git commit in the intended repository.
2. The worktree is clean apart from explicitly excluded local maintainer state.
3. Any focused checks used while developing the change are reported as
   attributable feedback; they are not separately persisted task authority.
4. The task's sole authoritative verification profile, `complete`, has passed
   by running `./scripts/verify.sh` against the exact candidate. That script
   already encompasses install and documentation checks.
5. A fresh reviewer who did not build the candidate has inspected that exact
   commit and returned a recorded recommendation.
6. No push, merge, deployment, release, provider call, or external write has
   been performed by the profile.
7. One qualified human inspects the candidate, verification result, review,
   remaining risks, and rollback information before accepting or rejecting it.

Tests and review are evidence. Only the final human action is acceptance.

## Mechanical Profile V1

The profile is selected explicitly rather than by repository name or silent
hidden-state discovery:

```text
palari init --profile maintainer
```

Ordinary current-directory workspace resolution and existing explicit
`--workspace FILE|DIR` behavior remain unchanged.

The smallest viable layout keeps the live workspace file at the repository
root so existing source, artifact, documentation, Git, MCP, and PCAW paths keep
the repository root as their boundary:

```text
.palari-company-os.json
.palari-company-os/
  binding.json
  .palari/
    governance-journal.v2.jsonl
    claims/
    packets/
    locks/
    verification/
```

Both root entries are local and ignored. The current tracked `workspace.json`
and root `.palari` directory remain untouched.

The optional `.palari-company-os/verification.json` consumed by the parked
external-maintainer status view may coexist with this layout. It is advisory
and is not profile binding, current check results, or approval authority.

Every generated action for this profile must select the exact live workspace,
for example:

```text
palari --workspace .palari-company-os.json ...
```

Omitting that selector is unsafe in a repository that also contains a tracked
root `workspace.json`. No emitted review, approval, recovery, or agent action
may silently fall back to the tracked workspace.

The successful initialization result emits only an exact, immediately
executable `work add ... --json` action. It does not emit `agent start` before
a task exists. A successful `work add` response may then emit the exact
maintainer-selected `agent start` action for that new bounded task.

### Exact Workspace And Control Paths

The implementation preserves two distinct internal facts:

- `Workspace.path` remains the canonical repository and artifact root.
- `Workspace.data_path` is the exact selected workspace file.

A single profile-aware resolver should derive the control root from the exact
data path and its validated binding:

- an ordinary `workspace.json` keeps its current sibling `.palari` layout;
- the maintainer file uses `.palari-company-os` as its bound control root.

Store locks, journal files, task briefs, session rules, assignments,
verification caches, and other local runtime records must use that resolver.
Callers must not reconstruct `workspace.json` from `Workspace.path` or assume
that every `.palari` directory is beside the repository root.

The workspace file, binding, journal, and task-runtime files remain ordinary
inspectable local files. Generated status views remain derived from them.

### Repository Binding

`binding.json` is a strict, versioned local format separate from workspace
schema v2. It binds:

- the `maintainer` profile;
- one random state identifier;
- one random repository identifier;
- the exact supported workspace filename and control-root layout; and
- a digest suitable for claim and compare-and-swap checks.

The repository identifier should also exist as a regular local file beneath
the exact Git common directory. It is not a secret, signature, human identity,
or source of approval. Its purpose is to prevent accidental state reuse by a
different clone or repository.

Every load and write must fail closed unless:

- Git resolves one exact canonical repository root and common directory;
- the workspace file is at the supported root-level location;
- the control directory is the exact expected child of that root;
- the binding and common-directory repository identifiers match;
- neither the workspace, binding, control path, nor relevant path component is
  a symlink;
- existing targets have the required regular-file or real-directory type;
- existing runtime regular files have exactly one hard link, and mutable
  append targets are rebound to the same unaliased inode after opening;
- both local-state paths are ignored from the source worktree;
- every exact runtime and workspace-staging target remains ignored even when
  repository ignore rules contain higher-precedence exceptions;
- no file beneath either local-state path is tracked; and
- the binding remains unchanged between load and mutation.

A whole-repository move may remain valid when the state directory and Git
repository identifier move together. Moving or copying state into another
repository must not silently rebind it.

The existing same-operating-system-user limitation remains: these local
identifiers and hashes detect mismatch and accidental tampering, but do not
authenticate a hostile process that can rewrite both state and Git metadata.

Initialization holds one token-owned lock in the Git common directory from
preflight through the first validated workspace write and either completion or
rollback. It binds that transaction to the original clean `HEAD` and status.
Rollback removes only objects still matching the initialization's ownership
witnesses, uses compare-and-swap handling for `info/exclude`, and preserves
concurrent operator files or ignore additions instead of recursively deleting
them.

### Journal Integrity

The current v2 transaction and replay rules remain unchanged:

- one prepared record is fsynced before workspace replacement;
- workspace replacement is staged, the exact workspace and source witnesses
  are checked again immediately before replacement, and the replacement is
  atomic and fsynced;
- a rejected final check records an abort instead of leaving a pending
  transaction;
- one commit record is fsynced afterward;
- pending, truncated, reordered, divergent, or corrupt history fails closed;
  and
- current workspace bytes must match the replayed projection.

Only the physical control root changes. The journal schema, record digests,
workspace schema, and continuity meaning do not.

The profile binding is an additional precondition. Its digest and the verified
journal head must be rechecked before a trusted mutation.

### Claim And Git Binding

An ignored workspace is intentionally absent from the candidate Git tree.
Palari must therefore never respond by force-adding or committing that
workspace.

For maintainer mode, the existing normalized all-agent execute/review authority
catalog is the mandatory immutable authority origin:

1. Capture the exact source Git head and dirty baseline.
2. Compile the current normalized authority catalog from strict live workspace
   bytes.
3. Bind the repository identifier and profile-binding digest into the hashed
   baseline.
4. Bind that baseline through the existing Git witness, oldest reflog entry,
   and repository-shared lease.
5. Compare the current authority digest before the lease and again while the
   workspace write lock is held.
6. Reject any changed actor, role, task, source, path, capability, completion
   rule, or reviewer authority.

The Git projection snapshot does not contain ignored workspace or journal
blobs. A maintainer claim therefore also contains a strict local-state witness
covering:

- the profile-binding digest;
- the exact workspace digest;
- the verified journal head and record count;
- the replay workspace digest; and
- the source Git head to which the claim is bound.

That witness must be rechecked on claim restart and before run reconciliation.
It grants no review, approval, external-write, merge, push, or deployment
authority.

Current evidence must also contain the exact built-in verification-command
binding and deterministic summary for the active attempt, base, head, and
changed paths. In Maintainer Profile v1, that binding contains exactly one
profile:

```text
complete: ./scripts/verify.sh
```

The script already runs the repository's install and documentation checks, so
they are not added as separate task profiles. Focused checks may be run during
development for fast attributable feedback, but they do not become a second
persisted evidence or authority surface. A manifest-valid record with different
command prose is not completion evidence.

### Authority Floor And Shared Enforcement

Maintainer `work add` preserves the caller's declared R1/R2 classification and
intensity. It raises `required_approval_count` to one when the caller supplies
zero and reports the change in `profile_adjustments`; it does not relabel R1 as
R2. Every maintainer task then requires:

1. the one current authoritative `complete` verification profile;
2. a current review by an eligible agent distinct from the builder; and
3. at least one qualified human approval, with any higher explicitly declared
   count preserved.

There is no low-risk automatic-completion exception for a maintainer task.
Automatic finishing may perform only the local bookkeeping already authorized
after the distinct review and human decision exist.

One shared static evaluator enforces the profile at assignment, evidence,
review-guide and review-record creation, acceptance, Approval Pack/Inbox, and
completion boundaries. It evaluates the complete current task contract,
including allowed actions, all linked run records, integration plans and
outbox state, selected-source sensitivity, protected paths, and the approval
floor. Passing an earlier boundary cannot launder a later-invalid task.

Review, Approval Inbox compilation, and final transaction prewrite also
revalidate the exact active attempt, authoritative command set and summary,
artifact hashes, clean source worktree, and exact Git `HEAD`. The final
prewrite check occurs after replacement bytes have been staged. Source or
evidence drift therefore removes executable authority actions or aborts before
the workspace and journal are terminalized.

### Profile Capability Limits

Maintainer Profile v1 rejects tasks or actions that allow, plan, queue, or
perform:

- push, merge, release, or deployment;
- provider or other external writes;
- credential or secret access;
- changes outside the exact source task boundary; or
- mutation of the profile's own workspace, binding, journal, assignments, or
  Git witnesses outside Palari's guarded commands.

For version 1, an execution task may declare no action capability or the
normalized capability `local_write`; any other `allowed_actions` value is
ineligible. This allowlist makes unfamiliar spellings and newly introduced
capabilities fail closed.

The direct `integration` and `linear` command families are unavailable when the
exact maintainer workspace is selected. Rejection occurs before credential
lookup, provider access, integration planning, queueing, or local integration
state mutation. Ordinary workspaces retain those command surfaces.

Host installation and isolated-worktree start are explicitly unsupported in
v1:

- host installation changes repository-local candidate files and would defeat
  the state-only initialization boundary;
- an ignored authority workspace is not present in a newly created Git
  worktree, so `agent start --isolate` cannot reconstruct its exact state from
  the candidate commit.

Both cases should fail before mutation with one clear next action. Ordinary
profiles retain their current host and isolation behavior.

## Compatibility

The profile is additive:

- workspace schema v2 remains unchanged;
- the governance journal schemas and record bytes remain unchanged;
- PCAW v1 remains unchanged;
- current authority formats remain supported (Approval Pack v3 with the v2
  reader, Approval Inbox v3, Review Guide v2, and presentation v1);
- Approval Inbox v3 replaces v2's executable-looking placeholder `actions`
  strings with structured `command_templates`. Each template is explicitly
  marked `executable: false` and contains argument metadata only. Concrete,
  current, exact-bound human actions remain in `approval_commands`. Approval
  Inbox output is derived rather than imported authority; the legacy reader
  applies only to Approval Pack v2, not to earlier Inbox output;
- ordinary `workspace.json` storage and current-directory resolution remain
  unchanged;
- existing explicit `--workspace FILE|DIR` invocations continue to work;
- lower-level Approval Pack commands remain available for compatible advanced
  workflows; and
- no repository-name, remote-name, or package-path heuristic selects
  maintainer mode.

The binding file is a new local safety format, not workspace schema growth and
not portable approval authority.

## Acceptance Tests

Temporary-repository tests cover:

- initialization leaves tracked root `workspace.json` and root `.palari`
  bytes unchanged;
- initialization refuses a tracked or conflicting local-state path;
- `git status --porcelain --untracked-files=all` stays empty after
  initialization, task creation, assignment, check reconciliation, review,
  approval, and completion;
- every emitted executable action immediately targets the exact maintainer
  workspace;
- an omitted `--workspace` selector never discovers hidden maintainer state;
- the exact source candidate, not the live state file, supplies Git and
  artifact identity;
- source-boundary, create/modify/delete, stale-review, and changed-artifact
  checks remain exact;
- journal corruption, truncation, pending transactions, and workspace
  divergence fail before review or approval;
- changing the binding, repository identifier, authority catalog, Git witness,
  or local-state witness fails closed;
- state from one repository cannot be used by another repository;
- repository movement either preserves the exact binding safely or produces
  one explicit rebind requirement;
- traversal, sibling-prefix confusion, and symlinks at the workspace, control,
  binding, journal, and repository-identifier paths fail before reads or
  writes;
- noncanonical protected paths, hard-linked runtime files, and non-regular
  runtime targets fail before a task becomes eligible or bytes are written;
- an interrupted workspace replacement leaves staging bytes only beneath the
  ignored bound runtime root, never as an unignored repository-root file;
- a changed binding or workspace during a command loses the compare-and-swap
  race and writes nothing;
- initialization rolls back its binding, runtime directory, ignore additions,
  and repository identifier even when failure occurs immediately after an
  atomic replacement;
- overlapping initialization, concurrent `info/exclude` edits, foreign
  replacement files, and source `HEAD` or status drift fail without deleting
  another actor's state;
- already-current proof with substituted verification commands cannot
  converge, and a source change injected after workspace staging is rejected
  before replacement with an abort record;
- R1 and R2 declarations remain unchanged while task creation enforces one
  human approval and all maintainer tasks run only the `complete` profile;
- focused development checks create no separate task authority, and R1/light
  maintainer work still stops for independent review and human approval;
- static policy violations and source/evidence drift block assignment,
  evidence, review, Approval Inbox, acceptance, and completion without
  executable authority guidance;
- simple local approval remains one real human action and performs no external
  effect;
- profile tasks with external or irreversible actions are ineligible;
- `--host` and `--isolate` fail without partial profile state in v1; and
- ordinary workspace, Git-hook, Approval Pack, evidence, and PCAW tests remain
  compatible.

The end-to-end test must cover one founder, one builder agent, one distinct
review-only agent, current exact checks, independent review, one founder
approval, automatic local completion, no copied digests, no external action,
and a clean source worktree at every boundary.

## Migration And Rollback

Maintainer Profile v1 does not automatically import, move, rewrite, or delete
an existing tracked workspace or journal. In particular, it does not copy this
repository's root state or historical dogfood state into the new profile.

Initial adoption should create a fresh, explicitly selected maintainer
workspace. Existing ordinary workspaces remain ordinary and continue to work
through their current paths.

Before a future migration feature is considered, it must define and test:

- an exact source workspace and journal backup;
- full source history verification;
- a dry-run showing the destination binding and files;
- refusal when claims, pending transactions, corruption, or repository
  identity are ambiguous;
- one explicit human-confirmed local copy;
- destination replay verification before use; and
- preservation of the original bytes until rollback is no longer needed.

Rollback from the future profile must also be local and explicit:

1. Stop before rollback when an assignment or journal transaction is active.
2. Verify and back up the workspace file, binding, and complete control
   directory together.
3. Stop selecting the maintainer workspace in emitted or operator commands.
4. Return to an explicitly named ordinary workspace without rewriting it.
5. Retain the ignored profile backup until its history is no longer required.

Reverting the source implementation must not delete ignored maintainer state.
An older Palari version that does not understand the binding and control-root
layout must refuse or leave those files untouched; it must not reinterpret
them as an ordinary workspace.

## Implemented Scope

The implementation is one bounded storage and lifecycle slice:

1. `Workspace.path` remains the repository root while `Workspace.data_path`
   retains the exact selected file.
2. One binding-aware resolver owns store locks, journal paths, task-runtime
   files, verification caches, and protected-path checks.
3. Initialization performs the Git-root, clean-candidate, ignore, tracking,
   path-type, and strict-binding preflights before use.
4. Claims bind the authority catalog, profile and repository identifiers, Git
   witness and lease, and exact local workspace/journal witness.
5. Work creation preserves R1/R2 classification while enforcing at least one human
   approval; `agent advance` binds exactly one authoritative `complete`
   profile, followed by independent agent review and human approval.
6. One shared evaluator protects assignment, evidence, review, acceptance,
   Approval Pack, and completion, with exact source/evidence revalidation at
   review, Inbox, and final prewrite.
7. Review, Approval Inbox, simple approval, evidence, PCAW, history, and status
   operations retain the exact selected workspace.
8. Negative path/security tests and the complete single-maintainer journey run
   only in temporary repositories.

The profile adds no workspace-schema or PCAW change, background service,
database, provider integration, secret, dashboard, or language rewrite.
