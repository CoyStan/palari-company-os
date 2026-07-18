# Palari Current Product

Palari Company OS is a local, provider-neutral governance kernel for bounded,
human-supervised AI work. It is not an agent runner, provider broker, project
manager, or compatibility layer for every earlier Palari experiment.

## The product in one minute

Palari turns one declared work contract into a fail-closed lifecycle:

```text
contract and scope
-> attempt
-> receipt and exact evidence
-> independent review when required
-> human decision when required
-> outcome
```

The governance kernel derives the lifecycle state. Storage, CLI, packets,
hooks, MCP, read models, UIs, and provider adapters translate that result; they
MUST NOT implement their own lifecycle or authority policy.

Palari guarantees that:

1. an agent cannot read or write outside declared scope;
2. completion always requires current evidence bound to the exact attempt and
   artifact state;
3. required review is independent and bound to the same exact proof;
4. only a qualified human can supply required human authority;
5. stale, malformed, contradictory, ambiguous, or mismatched proof fails
   closed;
6. governance history is replayable and tamper-evident;
7. proof can be verified locally and offline; and
8. ordinary operation is deterministic and understandable.

Risk changes which authority is required, never whether evidence is required.
R1/light work with zero required approvals and no external effect may complete
after current exact evidence without independent review or human acceptance.
All other work stops at the independent-review boundary. The work contract and
kernel determine whether a later qualified human decision is required.

## Ordinary paths

An operator initializes a repository once, creates bounded work, and inspects
derived state:

```text
palari init [--host claude|codex]
palari work add TITLE --create PATH | --modify PATH | --delete PATH
palari queue
palari detail WORK-ID
```

An executing agent has one ordinary path:

```text
palari agent start --next --as PALARI-ID --json
# work only inside the returned scope and commit the bounded result
palari agent advance WORK-ID --as PALARI-ID --json
```

`agent advance` records the current attempt, receipt, and evidence, then stops
at completion, independent review, human authority, an external effect, or a
concrete blocker. If work is interrupted, `agent release` durably records the
blocker and next safe action before releasing the claim. Inspection helpers are
optional recovery surfaces, not mandatory ceremony.

An independent reviewer inspects the exact evidence and records a separate
review. When human authority is required, a qualified human uses:

```text
palari queue --approval-inbox --json
```

The human inspects the exact presentation and executes its one digest-bound
action. An agent may display that action but cannot execute it, create the
review, or manufacture acceptance.

## Supported proof and storage

The supported portable proof is PCAW v1: canonical, no-float I-JSON in an
in-toto Statement v1 envelope with SHA-256 subjects and a normalized governance
case. Full verification reads artifact bytes beneath an explicit subject root
and needs no network, credentials, provider, or original workspace. PCAW v1 is
unsigned and does not authenticate declared identities, authorize external
effects, or provide portable deletion-history proof.

The supported current durable workspace format is:

- `workspace.json` with `schema_version: 2`; and
- `.palari/governance-journal.v2.jsonl` as the sole current mutation journal.

New workspaces write v2 directly. Existing unjournaled workspaces require an
explicit v2 checkpoint before mutation. The v1 filename accepts only strict
legacy records and is never a compatibility path for v2 output.

Packet, claim, session-contract, cache, and Git-witness files are local runtime
state, not alternate company truth. `.palari/history.jsonl` is a preserved
historical artifact, not a current writer or authority. Full journal audit is
explicit; ordinary queue and status operations may reuse one request-local
verification witness but never a persistent authority cache.

The only supported historical inputs are those proven by committed data:

- the sealed governance-journal v1 predecessor, verified by a narrow read-only
  boundary before current activation;
- schema-v2 work items without additive `path_intents`, interpreted only with
  their older presence contract;
- historical evidence without `output_binding_version`, which remains
  inspectable without gaining stronger inferred authority; and
- unbound negative or non-accepting reviews, which remain inspectable but can
  never satisfy review or acceptance.

There is no supported migration from unversioned, v0, or v1 workspaces, legacy
agent claims, or Approval Pack v1 because no committed real stored fixture
requires it. Split `collection_files` support is parked pending a product
decision and is not part of the ordinary storage contract.

## Optional adapters

Supported adapters are thin consumers of the kernel:

- the local CLI;
- the Git commit boundary;
- tested Claude and Codex session adoption;
- MCP stdio with explicit capability limits;
- Linear issue/comment/webhook translation through the governed
  plan/approval/outbox boundary;
- local Mission Control for an exact human action; and
- agent-ready repository documentation plus the network-free demo.

An adapter cannot widen scope, accept work, combine builder and reviewer,
create human authority, bypass evidence, or turn a queued external action into
an executed one.

The former advisory Cursor/Devin/GLM/generic session-profile aliases and the
provider-specific Slack/GitHub/Jira/email preview shapes were removed as
unsupported experiments. The separate desktop prototype, demo schema,
showcase narrative, and Pages deployment were also removed; Mission Control is
the one supported local human UI. Historical completion contracts do not
define the current product.

## Non-goals and compatibility

Palari does not provide a hosted multi-user service, background agent runner,
secret manager, authenticated identity system, automatic merge/deploy, generic
live provider execution, or autonomous review or acceptance. It has no runtime
dependency or network requirement for core governance and proof verification.

Palari is pre-1.0. Compatibility is retained only for a committed real stored
format and only behind one explicit reader or migration boundary. Public
commands, aliases, schemas, fixtures, tests, and documents are not retained
merely because they existed in version 0.2.0. Deliberate removals receive no
alias, wrapper, or shim. Historical artifacts stay immutable in Git; historical
implementations do not remain executable forever.
