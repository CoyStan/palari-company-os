# AI Operations And Memory Roadmap Review

Source conversation:
`/home/quetza/.codex/attachments/d02f5562-fcb7-4bdc-9b6e-37362e2a384f/pasted-text.txt`

Date saved: 2026-06-21

This note preserves the product ideas from the GPT-5.5 conversation that are
worth keeping for future Palari Company OS work. It is not an implementation
commitment. The main conclusion is that Palari should stay lightweight and
provider-neutral while becoming stronger at governing human + AI operations.

## Main Product Thesis To Save

Palari Company OS should become a lightweight AI operations control plane.

It should not try to be a vector database, a full agent framework, a data lake,
or a replacement for Slack, Jira, GitHub, Drive, Zep, Mem0, Letta, LangGraph,
LlamaIndex, OpenAI, or Azure Foundry.

The differentiated role is:

- map what AI is allowed to use
- show what AI actually used
- freeze evidence and receipts
- keep human authority explicit
- govern memory promotion
- log retrieval and context bundles
- preserve accountability across humans, Palaris, workbenches, sources, and
  outcomes

Short version:

Memory engines remember. Retrieval engines search. Agent frameworks execute.
Palari governs.

## Changes Worth Saving As Future Work

### 1. Integration Registry Before Live Connectors

Add a first-class integration registry before adding real side effects.

Important fields:

- `id`
- `provider`
- `label`
- `mode`
- `owner_human`
- `enabled`
- `allowed_events`
- `allowed_actions`
- `secret_ref`
- `risk_level`

Initial commands worth considering:

- `palari integrations`
- `palari integration check INT-ID`
- `palari integration plan INT-ID --work WORK-ID --event approval_requested --action notify`
- `palari integration emit WORK-ID --event approval_requested --dry-run`

Why save it:

This is the safest path from local model to real operations. Palari can show
what it would send to Slack, Jira, GitHub, or email before it sends anything.
`secret_ref` must be metadata only; raw secrets must never be stored.

### 2. Data Plane Boundary

Save the distinction between durable workspace records and non-Git runtime
state.

Git-tracked:

- goals
- humans
- Palaris
- workbenches
- sources
- integration configuration
- policies
- evidence snapshots
- receipts
- human decisions
- outcomes
- approved memory

Not Git-tracked by default:

- sync cursors
- raw inbound events
- caches
- vector indexes
- search indexes
- raw Slack history
- raw customer data

Likely local runtime layout:

```text
.palari/
  state/
  cache/
  inbox/
  indexes/
```

Why save it:

This prevents Palari from becoming a dumped-data repo. Palari should own the
operating record, not every external system's data.

### 3. Source Readiness And Data Classification

Extend sources with optional readiness and data governance fields.

Useful fields:

- `data_class`
- `steward_human`
- `freshness_sla`
- `last_verified_at`
- `lineage_ref`
- `redaction_required`
- `may_leave_boundary`

Likely commands:

- `palari sources readiness`
- `palari source classify SRC-ID --data-class confidential`
- `palari source verify SRC-ID --head sha256:...`

Why save it:

Real companies need to know not only whether AI can read a source, but whether
it should trust, cite, redact, or avoid that source.

### 4. AI Use-Case Portfolio

Add an optional use-case layer above goals/work items to prevent random AI
pilot sprawl.

Useful fields:

- `id`
- `name`
- `owner_human`
- `linked_goals`
- `business_function`
- `risk_level`
- `status`
- `baseline_metric`
- `target_metric`
- `approved_tools`
- `data_classes`

Likely commands:

- `palari use-cases`
- `palari use-case create ...`
- `palari use-case value USECASE-ID --metric ...`

Why save it:

This makes Palari answer whether AI work is attached to real business value,
not just whether a task completed.

### 5. Retrieval Policy, Retrieval Event, And Context Bundle

Save this as one coherent future slice.

`RetrievalPolicy` says what a Palari may search:

- allowed Palaris
- allowed sources
- blocked sources
- allowed memory kinds
- required authority
- max context items
- stale-after rules
- logging requirement

`RetrievalEvent` records the search:

- work item
- Palari
- query
- provider
- policy
- searched sources
- blocked sources and reasons
- returned result refs
- timestamp

`ContextBundle` records the exact context sent to the model:

- retrieval event
- work item
- included excerpts or memory refs
- evidence refs
- redactions
- token estimate
- content hash

Why save it:

This is the core "show me what the AI saw" primitive. It also keeps retrieval
governed without forcing Palari to build its own retrieval engine.

### 6. Memory Governance Layer

Add memory as a governed object model, not as raw chat history.

Memory types to preserve:

- working memory: temporary per attempt
- episodic memory: what happened before
- semantic memory: approved company facts
- procedural memory: approved ways of doing work

Important rule:

Palaris may propose memory. Humans approve durable memory. Palari enforces
scope, expiry, provenance, and deletion.

Objects worth saving:

- `MemoryProvider`
- `MemoryRecord`
- `MemoryProposal`
- `MemoryReview`

Likely commands:

- `palari memory list`
- `palari memory explain MEM-ID`
- `palari memory propose WORK-ID`
- `palari memory approve MEMPROP-ID --by HUMAN-ID`
- `palari memory expire MEM-ID`
- `palari memory audit`

Why save it:

The strongest line in the conversation is: memory is not what the AI remembers;
memory is what the company has approved the AI may rely on.

### 7. Provider-Neutral Memory Adapters

Keep Palari provider-neutral and add adapters later.

Provider kinds worth preserving:

- `local_json`
- `local_sqlite`
- `mem0`
- `zep`
- `graphiti`
- `letta`
- `langgraph`
- `llamaindex`
- `openai_vector_store`
- `azure_foundry`

Recommended order:

1. Local JSON + SQLite FTS
2. Mem0
3. Zep/Graphiti
4. LlamaIndex
5. OpenAI vector store
6. Letta
7. LangGraph
8. Azure Foundry

Why save it:

Palari should not compete with specialized memory systems. It should govern
their use and keep a local audit ledger.

### 8. Document Network / Knowledge Map

Add a light document graph later, separate from memory.

Objects worth saving:

- `DocumentRef`
- `DocumentChunkRef`
- `KnowledgeEntity`
- `KnowledgeEdge`
- `SourceAuthority`
- `SupersedesEdge`

Checks to preserve:

- official vs informal source
- superseded document
- stale document
- owner/steward missing
- conflicting memory
- cross-boundary retrieval
- untrusted source promoted to durable memory

Why save it:

Palaris need to know which documents are current, authoritative, linked, and
allowed. A document network is not the same thing as memory.

### 9. Enriched Receipts As Agent Run Records

Extend receipts with optional run metadata.

Useful fields:

- `model_refs`
- `tool_calls`
- `mcp_server_refs`
- `input_data_classes`
- `redactions_applied`
- `estimated_cost`
- `latency_ms`
- `autonomy_level`
- `intervention_points`
- `retrieval_events`
- `context_bundles`

Why save it:

Receipts are already a strong Palari primitive. Enriching them turns them into
human-readable agent run records without adding heavy process ceremony.

### 10. Evals, Red-Team Records, And Incidents

Save these as later operational maturity slices.

Evals:

- target Palari
- rubric
- fixtures
- required score

Incidents:

- severity
- linked work item
- category
- opened by
- containment
- owner human
- status
- resolution

Likely commands:

- `palari eval list`
- `palari eval run EVAL-ID`
- `palari redteam run --risk prompt_injection --dry-run`
- `palari incident open --work WORK-ID --category unsafe_output`
- `palari incidents --open`
- `palari incident close INC-ID --resolution ...`

Why save it:

Companies need a way to record AI failures and human corrections. This should
be lightweight, but it is central to trust.

### 11. Responsibility Map And Metrics

Derived views worth saving:

- `palari responsibility map`
- `palari metrics --json`

Useful metrics:

- work items by risk/status
- AI-assisted cycle time
- human approval latency
- evidence/review pass rate
- stale evidence count
- sources missing data class
- incidents by category
- use cases missing value metrics
- retrievals blocked by policy
- memories pending approval

Why save it:

These make Palari legible as an operating console, not just a schema and CLI.

## What Not To Save As Immediate Implementation

Do not immediately build:

- full vector database
- full GraphRAG stack
- live Slack/Jira/GitHub writes
- raw Slack mirroring
- universal memory shared by all Palaris
- automatic permanent memory writes
- memory provider lock-in
- heavy enterprise administration
- heavy process ceremony

## Recommended Implementation Order

1. Integration registry and dry-run payload planner.
2. Source readiness and data classification.
3. Data map command showing systems, sources, stored evidence, cache status,
   and what is intentionally not stored.
4. Local memory governance model: memory providers, memory records, proposals,
   approvals, expiry, and audit.
5. Retrieval policy/event/context bundle with deterministic local search.
6. Enriched receipts linked to retrieval and context.
7. Evals/red-team records.
8. Incidents.
9. Optional provider adapters, starting with local SQLite FTS, then Mem0 or
   Zep/Graphiti.
10. Document network / knowledge map.

## Highest-Value Next Slice

The cleanest next product slice is:

Add an integration registry plus dry-run integration planner.

Reason:

It moves Palari from local governance model toward real company operations
without adding live side effects, secrets, or heavyweight memory machinery.

Second best next slice:

Add source readiness/data classification and `palari data map`.

Reason:

It clarifies what Palari owns, what external systems own, what is cached, what
is evidenced, and what AI is allowed to use.
