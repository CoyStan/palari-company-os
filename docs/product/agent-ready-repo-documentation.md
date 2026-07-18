# Agent-Ready Repo Documentation

This document defines the target system for making Palari Company OS repositories
easy for AI agents to understand, change, verify, and hand back without
re-reading the whole codebase on every task.

It is a roadmap, not a claim that every future phase exists today.

## Implementation Status

The first implementation provides:

- canonical `docs/agent/` orientation files
- compact root `AGENTS.md` links to those docs
- `palari docs check`
- `palari docs map`
- `palari docs init` dry-run and explicit write behavior
- `documentation_state` and `recommended_docs` hints in agent packets and
  checks

Still future:

- path-specific nested `AGENTS.md` files
- budgeted context packs
- importing external skills as documentation sources
- hard documentation freshness gates

## Purpose

Palari Company OS should treat repo documentation as operational context for
agents. The goal is not more ceremony. The goal is to keep the important truth
of a repository close to the work so an agent can start faster, stay inside
scope, and avoid rediscovering the same architecture and safety constraints from
raw code every time.

The system should answer:

- What is this repo?
- How should an agent work here?
- Which files and commands matter?
- Which invariants must not be broken?
- Which docs should be updated when behavior changes?
- Which context should be loaded now, and which can stay out of the context
  window until needed?

## External Patterns To Learn From

Several agent ecosystems are converging on the same idea: short persistent
instructions plus deeper context loaded only when relevant.

| Pattern | Examples | Useful Feature | Risk To Avoid |
| --- | --- | --- | --- |
| Single agent entrypoint | `AGENTS.md` | One predictable place for setup, checks, conventions, and constraints. | It can become a giant prompt dump. |
| Tool-specific instructions | `CLAUDE.md`, `GEMINI.md`, Copilot instructions | Better fit for a specific agent or host tool. | Duplicated truth can drift across files. |
| Path-specific instructions | Copilot instructions, Cursor/Cline/Continue rules | Different guidance for source, tests, docs, examples, and frontend. | Too many rule files become invisible process. |
| Progressive skills | Agent Skills, `SKILL.md` | Lightweight metadata first, detailed instructions only when needed. | Skills can become a parallel truth system outside the repo. |
| Context providers | File/code/diff/current-file providers | Pull only relevant context instead of loading everything. | Bad retrieval can omit important constraints. |
| Memory systems | Claude memory-style topic files | Recurring lessons can survive across sessions. | Machine-local memory is not shared repo truth. |

Palari should borrow the useful parts while keeping repo truth committed,
portable, and verifiable.

## Design Principles

### 1. Repo Truth Beats Machine Memory

Machine-local memory can help an agent, but it must not be required to
understand the project. Shared operating knowledge belongs in the repository.

### 2. Small Always-Loaded Context

The root `AGENTS.md` should stay compact. It should orient the agent and point
to the relevant deeper docs. It should not become a full manual.

### 3. Progressive Disclosure

The agent should load context in layers:

1. Root agent entrypoint.
2. Work-item packet from Palari.
3. Relevant repo map or invariant docs.
4. Relevant code and tests.

This protects context windows and reduces token cost without hiding important
boundaries.

### 4. Documentation Follows Behavior

Docs should be updated when a change alters public commands, schema semantics,
agent behavior, source/receipt behavior, gates, integrations, examples, or
operator workflows.

Docs should not require a ritual for every tiny internal refactor.

### 5. Guidance, Not Ceremony

Agent-ready docs should not reintroduce old Palari Orchestrator process objects.
No tickets, claims, reviewer notes, worktrees, ADP, or acceptance ceremonies are
needed for documentation itself.

### 6. Verifiable Freshness

Documentation cannot be trusted if it silently drifts. Palari should eventually
provide lightweight checks that catch obvious mismatch between code, commands,
schema, examples, and docs.

## Target Documentation Model

### Root Entry Points

#### `AGENTS.md`

The root agent entrypoint should remain short and practical:

- repository purpose
- safest starting commands
- verification commands
- strict boundaries
- links to canonical docs
- how to use Palari agent packet commands

It should avoid detailed architecture and long policy explanations.

#### Tool-Specific Files

Files such as `CLAUDE.md` may exist only as thin adapters. They should point
back to the canonical `AGENTS.md` and product docs instead of duplicating
rules.

### Canonical Agent Docs

The target structure should be:

```text
docs/agent/
  repo-map.md
  contracts-and-invariants.md
  common-workflows.md
  verification.md
  documentation-freshness.md
```

These docs should be written for agents first, but remain readable by humans.

#### `docs/agent/repo-map.md`

Purpose: help an agent find the right files without scanning the whole repo.

It should include:

- source package structure
- CLI parser/dispatch/output locations
- schema and validation locations
- examples and dogfood workspace locations
- test organization
- Mission Control/prototype locations
- docs that must be updated for common changes

#### `docs/agent/contracts-and-invariants.md`

Purpose: preserve the system's safety and trust semantics.

It should include:

- unknown fields fail closed
- no raw secrets in workspace data
- integrations are dry-run unless explicitly upgraded
- external writes require explicit approval/outbox boundary
- receipts are human-facing trust records
- evidence and review are different from receipts
- gates recommend review focus but do not grant authority
- agent packets define allowed paths, sources, actions, and stop conditions
- `agent start` persists the packet and claim; `agent brief` is read-only
- `agent check` verifies proof state and observed changes

#### `docs/agent/common-workflows.md`

Purpose: describe recurring work patterns without creating workflow ceremony.

Examples:

- add a CLI command
- add a schema field
- add a validation rule
- add a source or receipt behavior
- add an integration dry-run action
- update examples and tests
- update docs when behavior changes

Each workflow should be short and command-oriented.

#### `docs/agent/verification.md`

Purpose: make "done" easy to verify.

It should include:

- normal full verification commands
- focused test patterns
- install smoke
- JSON smoke expectations
- when browser/prototype verification matters
- how to report skipped checks honestly

#### `docs/agent/documentation-freshness.md`

Purpose: define when docs must be updated.

It should include:

- command changes update command reference
- schema/model changes update schema docs and core object docs
- agent command changes update agent contract
- source/receipt changes update source-of-truth or relevant product docs
- gate changes update authority-and-gates
- example behavior changes update quickstart and example docs where needed

## Path-Specific Guidance

Palari can later add sparse path-specific instructions, but only where the
guidance is materially different.

Possible files:

```text
src/palari_company_os/AGENTS.md
tests/AGENTS.md
examples/AGENTS.md
docs/AGENTS.md
```

These should be short. They should not duplicate root instructions. They should
answer, "What is different when working in this part of the repo?"

Examples:

- source code: keep CLI behavior deterministic and JSON-friendly
- tests: prefer regression fixtures for boundary failures
- examples: avoid machine-local paths and raw secrets
- docs: keep claims current and avoid overclaiming maturity

## Palari Workspace Integration

Agent-ready documentation should become part of the Palari Company OS model
without becoming a new ceremony layer.

### Work Items

Work items may eventually reference relevant docs:

```json
{
  "id": "WORK-1234",
  "recommended_docs": [
    "docs/agent/repo-map.md",
    "docs/agent/contracts-and-invariants.md"
  ]
}
```

This is advisory context, not authority.

### Agent Packets

`palari agent brief` and `palari agent start` should eventually include compact
documentation hints:

```json
{
  "recommended_docs": [
    {
      "path": "docs/agent/contracts-and-invariants.md",
      "why": "This work changes receipt and integration boundary behavior."
    }
  ],
  "omitted_context": [
    "Full repo map omitted; read docs/agent/repo-map.md if file ownership is unclear."
  ]
}
```

The packet should not dump full docs unless explicitly requested. It should
point to the right docs.

### Gates

Gate recommendations can reference docs as review aids:

- source-boundary -> source and receipt docs
- external-write -> integration and outbox docs
- deploy-runtime -> release and operations docs
- product-overclaim -> README/example/docs maturity guidance

The gate still remains read-only and advisory.

### Receipts

Receipts should not become documentation records, but they can reference changed
docs when a work item updates public behavior:

```json
{
  "actions_taken": [
    "Updated command reference for new gate commands."
  ],
  "outputs_created": [
    "docs/product/command-reference.md"
  ]
}
```

## Future CLI Support

### Missing Documentation Behavior

A newly installed repository may not have agent-ready documentation yet. That
should be normal. Missing docs should mean "low context," not "blocked."

When Palari cannot find `AGENTS.md` or the canonical `docs/agent/` set, it
should:

- continue to allow normal workspace inspection and safe agent packet commands
- report that agent-ready docs are missing
- explain that orientation may be slower or less precise
- avoid pretending inferred structure is committed repo truth
- recommend `palari docs init` as the next setup action

Example status:

```json
{
  "documentation_state": {
    "status": "missing",
    "message": "No agent-ready repo documentation found.",
    "impact": "Agents can still inspect the repo, but orientation may require more code reading.",
    "recommended_next_command": "palari docs init"
  }
}
```

Missing documentation should not block work unless a specific work item requires
documentation as an output or evidence record.

### `palari docs init`

Target behavior:

- inspect the repo shape
- propose a starter documentation set
- generate a draft repo map from observed files, scripts, packages, tests, and
  examples
- clearly label inferred content as a draft
- ask for explicit user approval before creating files
- never overwrite existing docs without explicit approval
- avoid adding ceremony, tickets, claims, reviews, or acceptance flows

Starter output should usually include:

```text
AGENTS.md
docs/agent/repo-map.md
docs/agent/contracts-and-invariants.md
docs/agent/common-workflows.md
docs/agent/verification.md
docs/agent/documentation-freshness.md
```

The command should favor small useful files over exhaustive documentation. A new
repo can start with only `AGENTS.md` and `docs/agent/repo-map.md` if that is all
the project needs.

Recommended interactive flow:

1. Inspect repo structure.
2. Print proposed files and short summaries.
3. Ask the user whether to create them.
4. Create only approved files.
5. Report next verification command, usually `palari docs check`.

The important distinction is:

- before approval: inferred orientation is temporary guidance
- after approval: created docs become committed repo truth once reviewed and
  checked in

### `palari docs check`

Target behavior:

- read-only
- deterministic
- no external services
- no markdown lint dependency required at first
- catches obvious stale docs

Possible checks:

- root `AGENTS.md` exists and links to canonical agent docs
- command reference mentions major CLI command groups
- schema docs mention major collections
- docs do not contain stale references to old Palari Orchestrator ceremony
- README links to current quickstart and command reference
- referenced docs paths exist

It should report warnings and failures separately. It should not pretend to
prove documentation quality.

### `palari docs map`

Target behavior:

- print a compact map of documentation surfaces
- explain which docs matter for a given change type
- optional JSON output for agent packets

### `palari agent brief --include-docs`

Target behavior:

- include selected doc excerpts only when requested
- respect a token or character budget
- always report omitted context

## What This System Should Not Do

Agent-ready documentation should not:

- create tickets
- create claims
- create reviewer notes
- require acceptance workflows
- replace source code as truth
- replace tests as proof
- store canonical knowledge only in machine-local memory
- auto-generate docs that humans and agents cannot trust
- require huge always-loaded instruction files
- duplicate the same rules across many tool-specific files

## Documentation Freshness Rule

At the end of meaningful work, the agent should ask:

Did this change alter any of these?

- public CLI commands
- JSON output shape
- workspace schema or validation
- agent packet/check/start behavior
- sources, receipts, evidence, review, or human decision semantics
- integration/outbox behavior
- gate recommendations
- examples or quickstarts
- installation or verification commands

If yes, update the relevant canonical docs.

If no, no docs update is needed.

This rule should remain a judgment call, not a ceremony checklist.

## Phased Roadmap

### Phase 1: Documentation Foundation

Create the canonical `docs/agent/` set:

- `repo-map.md`
- `contracts-and-invariants.md`
- `common-workflows.md`
- `verification.md`
- `documentation-freshness.md`

Update root `AGENTS.md` to point to them and stay compact.

Success criteria:

- a new agent can orient from docs before reading code
- docs do not overclaim implementation maturity
- no new process objects are introduced

### Phase 2: Lightweight Freshness Checks

Add `palari docs check`.

Success criteria:

- catches broken links to local docs
- catches missing command-reference coverage for major command groups
- catches stale old-orchestrator terminology
- runs inside normal verification
- does not require new dependencies

### Phase 3: Agent Packet Doc Hints

Add `recommended_docs` to agent brief/start/check outputs.

Success criteria:

- doc hints are compact and deterministic
- packet does not dump whole docs
- omitted context is explicit
- agents can find the right docs faster

### Phase 4: Path-Specific Agent Guidance

Add sparse nested `AGENTS.md` files only where needed.

Success criteria:

- each nested file is shorter than the root file
- no duplicated canonical rules
- instructions differ materially by path

### Phase 5: Budgeted Context Packs

Add optional budget-aware context support.

Possible command:

```bash
palari context pack WORK-ID --as PALARI-ID --budget 4000 --json
```

Success criteria:

- includes only relevant docs, sources, and repo map entries
- reports omitted context
- does not replace packet boundaries

## Compatibility With Current Palari Company OS

This system fits the current model:

- work items remain the unit of intended work
- attempts remain concrete executions
- receipts remain human-facing trust records
- evidence/review/human decisions remain separate governance records
- integrations remain dry-run until future live execution is explicitly designed
- gates remain read-only review recommendations
- agent packets remain bounded execution contracts

Agent-ready docs should make those primitives easier to use. They should not
replace or weaken them.

## Open Questions

- Should doc freshness become a hard validation failure or start as warnings?
- Should `recommended_docs` live on work items, packets, or both?
- Should path-specific guidance use nested `AGENTS.md` files or only
  `docs/agent/` references?
- How large should root `AGENTS.md` be allowed to get before it fails a docs
  check?
- Should Palari support importing external skills as documentation sources, or
  only link to committed repo docs in v1?

The default answer should favor simplicity: committed docs first, warnings
before hard failures, and no new ceremony unless it prevents real repeated
failures.
