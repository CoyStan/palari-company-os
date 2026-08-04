# Self-Hosting Maintainer Mode

> **Status: design note, not a shipped feature.** The ergonomic maintainer
> profile described below (`palari init --profile maintainer`, ignored local
> live state, a bound control root) is **not implemented**. Only the bounded
> "Founder-Authorized Exception For This Repair" procedure is in effect today.
> Read the "Proposed Mechanical Profile" and later sections as future design,
> not current behavior.

Palari must be repairable without making its own source candidate depend on a
broken instance of the workflow being repaired. This document defines the
temporary exception used for the current repair and the narrower mechanical
profile that should replace that exception.

## Current Status

The maintainer policy in this document is partly procedural and partly a
follow-up design.

The current repair uses the procedural exception below. Palari now retains the
exact explicitly selected workspace filename so emitted commands do not fall
back to a sibling `workspace.json`, but an ignored, bound live-state profile is
**not implemented yet**. Palari must not claim that
assignments, checks, reviews, or approvals can currently be recorded in an
isolated local workspace while keeping this source checkout clean.

The tracked root `workspace.json` and root `.palari` directory remain product
artifacts and historical evidence. For the current repair they may be
inspected, but they must not be used or changed as live governance state.
Tests that exercise workspace changes must use temporary repositories,
temporary workspaces, or existing fixtures.

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
3. Focused checks attributable to the change have passed.
4. The complete repository verification profile has passed against the exact
   candidate.
5. A fresh reviewer who did not build the candidate has inspected that exact
   commit and returned a recorded recommendation.
6. No push, merge, deployment, release, provider call, or external write has
   been performed by the profile.
7. One qualified human inspects the candidate, verification result, review,
   remaining risks, and rollback information before accepting or rejecting it.

Tests and review are evidence. Only the final human action is acceptance.

## Proposed Mechanical Profile V1

The follow-up should add one explicit profile rather than discover Palari by
repository name or silently select hidden state:

```text
palari init --profile maintainer
```

The exact CLI remains subject to implementation review, but the profile must
be explicit. Ordinary current-directory workspace resolution and existing
explicit `--workspace FILE|DIR` behavior must remain unchanged.

The smallest viable layout keeps the live workspace file at the repository
root so existing source, artifact, documentation, Git, MCP, and PCAW paths keep
the repository root as their boundary:

```text
.palari-company-os.json
.palari-company-os/
  binding.json
  verification.json
  .palari/
    governance-journal.v2.jsonl
    claims/
    packets/
    locks/
    verification/
```

Both root entries are local and ignored. The current tracked `workspace.json`
and root `.palari` directory remain untouched.

Every generated action for this profile must select the exact live workspace,
for example:

```text
palari --workspace .palari-company-os.json ...
```

Omitting that selector is unsafe in a repository that also contains a tracked
root `workspace.json`. No emitted review, approval, recovery, or agent action
may silently fall back to the tracked workspace.

### Exact Workspace And Control Paths

The implementation should preserve two distinct internal facts:

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

`binding.json` should be a strict, versioned local format separate from
workspace schema v2. It should bind at least:

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
- both local-state paths are ignored from the source worktree;
- no file beneath either local-state path is tracked; and
- the binding remains unchanged between load and mutation.

A whole-repository move may remain valid when the state directory and Git
repository identifier move together. Moving or copying state into another
repository must not silently rebind it.

The existing same-operating-system-user limitation remains: these local
identifiers and hashes detect mismatch and accidental tampering, but do not
authenticate a hostile process that can rewrite both state and Git metadata.

### Journal Integrity

The current v2 transaction and replay rules should remain unchanged:

- one prepared record is fsynced before workspace replacement;
- workspace replacement is atomic and fsynced;
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
catalog should become the mandatory immutable authority origin:

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

The current Git projection snapshot will not contain ignored workspace or
journal blobs. A maintainer claim therefore also needs a strict local-state
witness containing:

- the profile-binding digest;
- the exact workspace digest;
- the verified journal head and record count;
- the replay workspace digest; and
- the source Git head to which the claim is bound.

That witness must be rechecked on claim restart and before run reconciliation.
It grants no review, approval, external-write, merge, push, or deployment
authority.

### Profile Capability Limits

Maintainer profile v1 must reject tasks or actions that allow, plan, queue, or
perform:

- push, merge, release, or deployment;
- provider or other external writes;
- credential or secret access;
- changes outside the exact source task boundary; or
- mutation of the profile's own workspace, binding, journal, assignments, or
  Git witnesses outside Palari's guarded commands.

Host installation and isolated-worktree start should be explicitly unsupported
in v1:

- host installation changes repository-local candidate files and would defeat
  the state-only initialization boundary;
- an ignored authority workspace is not present in a newly created Git
  worktree, so `agent start --isolate` cannot reconstruct its exact state from
  the candidate commit.

Both cases should fail before mutation with one clear next action. Ordinary
profiles retain their current host and isolation behavior.

## Compatibility

The follow-up should be additive:

- workspace schema v2 remains unchanged;
- the governance journal schemas and record bytes remain unchanged;
- PCAW v1 remains unchanged;
- current authority formats remain supported (Approval Pack v3 with the v2
  reader, Approval Inbox v2, Review Guide v2, and presentation v1);
- ordinary `workspace.json` storage and current-directory resolution remain
  unchanged;
- existing explicit `--workspace FILE|DIR` invocations continue to work;
- lower-level Approval Pack commands remain available for compatible advanced
  workflows; and
- no repository-name, remote-name, or package-path heuristic selects
  maintainer mode.

The binding file is a new local safety format, not workspace schema growth and
not portable approval authority.

## Acceptance Tests For The Follow-Up

The profile is not complete until temporary-repository tests prove:

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
- a changed binding or workspace during a command loses the compare-and-swap
  race and writes nothing;
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

Maintainer profile v1 should not automatically import, move, rewrite, or
delete an existing tracked workspace or journal. In particular, it must not
copy this repository's root state or historical dogfood state into the new
profile.

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

## Tightly Scoped Delivery Plan

The follow-up should remain one bounded storage and lifecycle slice:

1. Extend the retained exact `Workspace.data_path` into the profile-aware
   control-root resolver while keeping `Workspace.path` as the repository root.
2. Add and test one binding-aware control-root resolver used by store locks,
   journal paths, task runtime files, verification caches, and protected-path
   checks.
3. Add explicit maintainer initialization, local ignore preflight, strict
   binding, and command selection without host installation.
4. Add catalog-bound claim authority and the local workspace/journal witness;
   remove the force-add recovery path only for a valid maintainer profile.
5. Route review, Approval Inbox, simple approval, evidence, PCAW, history, and
   status operations through the exact data path.
6. Add the negative path/security tests and the complete single-maintainer
   journey above.
7. Update current-product, security, source-of-truth, command, backup, and
   agent-contract documentation only after the behavior is mechanically true.

This plan does not require a new workspace schema, background service,
database, provider integration, secret, dashboard, or language rewrite.
