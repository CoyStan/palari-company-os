# Competitive Landscape

Verified survey of products and projects adjacent to Palari Company OS, and
what Palari should adapt, ignore, or defend. All repositories, star counts,
and product claims below were verified by direct fetch on 2026-07-15. Star
counts drift; treat them as order-of-magnitude signals.

This document exists so roadmap decisions can cite real competitors instead
of vibes. It complements [Public Surface](public-surface.md) (what Palari is)
and [Roadmap](roadmap.md) (what Palari does next).

## Summary

- Palari's two core bets — per-work-item task contracts and offline-verifiable
  proof of governed work — have **no shipped competitor** as of this survey.
- Raw file-write boundary enforcement is being **commoditized by the agent
  platforms themselves** (Claude Code, Codex, Cursor all ship OS-level
  sandboxing natively).
- The durable differentiation is the **enforcement-to-evidence bridge**:
  platforms enforce but emit no portable evidence; provenance tools record
  but do not enforce. Palari does both in one loop.
- The two most instructive market failures are HumanLayer (deprecated its
  approval SDK after platforms absorbed simple approval gates) and Vibe
  Kanban (27k stars, company shut down — developer-experience governance did
  not monetize).

## Categories and Verified Players

### Native platform controls (the commoditization front)

| Product | What it ships | Signal for Palari |
| --- | --- | --- |
| Claude Code (Anthropic) | OS-enforced sandbox (Seatbelt / bubblewrap + seccomp), network proxy isolation, declarative permission rules, pre/post tool-call hooks. Sandbox runtime open-sourced as `anthropic-experimental/sandbox-runtime`. | The enforcement substrate Palari rides on is free and improving. Do not compete with it; compile into it. |
| OpenAI Codex CLI | `sandbox_mode` (read-only / workspace-write / danger-full-access) and independent `approval_policy` dials, enforced via Seatbelt / bwrap / Landlock. | Same packet, second target platform. |
| Cursor | Agent sandboxing since 2.0; by 2.5, "Auto-review" routes Shell/MCP/Fetch through allowlist, sandbox, then a classifier subagent that decides allow/retry/ask-human. Config via `permissions.json` + `sandbox.json`. | Cursor is automating the human approver itself. Simple HITL prompts are a shrinking product. |

Sources: anthropic.com/engineering/claude-code-sandboxing,
code.claude.com/docs/en/sandboxing,
developers.openai.com/codex/concepts/sandboxing,
cursor.com/docs/agent/security/run-modes, cursor.com/changelog/2-5.

### Human-in-the-loop approval layers

| Product | Traction | Design idea | Signal |
| --- | --- | --- | --- |
| HumanLayer (`humanlayer/humanlayer`, YC F24) | 11.1k stars | Approval-before-sensitive-tool-call over Slack/email; "contact human as a tool". | **Original SDK deprecated**; company pivoted to CodeLayer (Claude Code orchestration). Standalone approval APIs got squeezed by framework-native HITL. |
| gotoHuman | Modest / SMB | Reviews as structured forms (approve/edit/reject templates) rather than chat approvals. | Structured review beats free-text approval. |
| LangChain Agent Inbox (`langchain-ai/agent-inbox`) | Framework-native | Gmail-style inbox over LangGraph `interrupt()`; interrupts as a first-class runtime primitive. | HITL is commoditizing into frameworks too. |
| impri (`sekera-radim/impri`) | New (July 2026) | Approval inbox with bulk decisions (up to 50) and Slack/Discord/Telegram/email notifications; agents report results back. | Push notifications are table stakes for an inbox. |

### Agent action firewalls, policy engines, MCP gateways

| Product | Traction | Design idea | Signal |
| --- | --- | --- | --- |
| Microsoft Agent Governance Toolkit (`microsoft/agent-governance-toolkit`) | 4.9k stars, public preview | `govern()` middleware intercepting every tool call against YAML/OPA-Rego/Cedar policy; zero-trust agent identity (SPIFFE, DIDs); Merkle tamper-evident audit logs mapped to OWASP Agentic Top 10 / NIST AI RMF / EU AI Act / SOC 2. | The enterprise heavyweight. Its "Independently Verifiable Compliance Receipts" — the nearest analogue to PCAW — is a **draft proposal, not shipped**. |
| Cordum (`cordum-io/cordum`) | 490 stars | Pre-execution YAML policy gating with a **policy simulator against historical data**; approval provenance bound to executed actions; local "Edge" daemon for Claude Code. | Policy simulation over recorded history is worth copying — Palari already has the journal to power it. |
| Invariant Labs Guardrails / mcp-scan | Acquired by Snyk (June 2025) | Guardrail proxy for agent/LLM traffic; coined "tool poisoning". | Agent-firewall tech is being absorbed into incumbent security platforms. |
| Docker MCP Gateway, IBM ContextForge, Lasso, AWS AgentCore | 0.4k–4.1k stars | Containerized MCP isolation, RBAC, federation, enterprise infra. | All require containers, proxies, or servers. Zero-infra local-first is structurally differentiated against this tier. |

### Audit, receipts, and provenance for AI work

| Product | Traction | Design idea | Signal |
| --- | --- | --- | --- |
| Git AI (`git-ai-project/git-ai`) | ~2k stars, Thoughtworks Radar "Assess" | Line-level AI attribution in Git Notes; survives rebase/squash/cherry-pick; local, free, no login. | Records *who wrote what*, not *whether the work was governed*. Complementary, not competitive. |
| Agent Trace spec (`cursor/agent-trace`) | 772 stars; Anthropic, OpenAI, Google, Vercel, Cognition listed as supporters | Open specification for tracing AI-generated code (model, line ranges, conversation links). | The attribution *format* is being standardized by the platforms jointly. Interop with it; do not compete on it. |
| soma (`radotsvetkov/soma`) | 2 stars, Rust | SHA-256 hash-chained JSONL journal with RFC 3161 timestamp anchoring; portable evidence bundles; in-toto attestations and EU AI Act Article 12 docs generated from the journal. | Closest philosophical neighbor. Timestamp anchoring and standards-shaped export are worth copying. |
| agent-receipts (`webaesbyamin/agent-receipts`) | 1 star, TypeScript | Ed25519-signed receipts per action with hashed inputs/outputs (prove-without-expose). Explicitly no prevention — proof only. | Signing is the norm the field is converging on. |
| SLSA / in-toto / Sigstore / GitHub attestations | Mature | DSSE envelopes, keyless signing, transparency logs — for build artifacts, not agent actions. | The obvious substrate to adapt rather than reinvent. |

### Agent work orchestration and task isolation

| Product | Traction | Design idea | Signal |
| --- | --- | --- | --- |
| Vibe Kanban (`BloopAI/vibe-kanban`) | 27.4k stars | Kanban issues, one git worktree per agent task, diff review. | Category-defining adoption; company shut down April 2026. Orchestration alone did not monetize. |
| Claude Squad (`smtg-ai/claude-squad`) | 8.1k stars | tmux + git worktrees per agent, change review. | Worktree-per-task is what developers demonstrably want. |
| Conductor (conductor.build) | Commercial Mac app | Parallel agents, worktree per workspace, fast diff/PR review. | Same lesson, plus an Enterprise tier. |

None of these carries an enforceable task contract — a machine-readable
assignment boundary tied to briefs, approvals, and required evidence. That
remains Palari's unoccupied ground.

## Commoditized vs. Open

Being commoditized by the platforms (do not compete here):

1. OS-level file-write and network boundaries.
2. Basic approval gates, allowlists, and permission prompts.
3. Hook and policy insertion points (now stable native surfaces — good news:
   Palari's enforcement rides a subsidized substrate).
4. AI-code attribution formats (`agent-trace` with platform backing).

Open gaps an independent tool can own:

1. **Offline-verifiable proof of governed work** — signed, hash-chained,
   third-party-verifiable receipts binding policy, approval, action, and
   result. Microsoft's version is an unshipped draft; enterprise gateways
   offer operator-trusted SaaS logs only. EU AI Act Article 12 record-keeping
   (enforceable August 2026) is an active tailwind.
2. **Task-contract semantics** — per-work-item scoped boundaries portable
   across Claude Code, Codex, and Cursor.
3. **The enforcement-to-evidence bridge** — enforcing and emitting portable
   evidence in one loop.
4. **Local-first, zero-infra deployment** — every policy and gateway
   competitor requires containers, a proxy, a database, or a SaaS tenant.

## What Palari Should Adapt

Ordered by leverage:

1. **Become the contract compiler, not just the enforcer.** Compile the
   packet write boundary into each platform's native controls (Claude Code
   permission rules and sandbox settings, Codex `workspace-write`
   configuration, Cursor `permissions.json`/`sandbox.json`). Keep hooks as
   the evidence recorder and governance protector; let the OS sandbox block.
   This retires the shell-parsing arms race documented in
   [Security Notes](security.md).
2. **Sign PCAW statements.** Hashes prove integrity; signatures prove
   authority. A zero-dependency path exists via `ssh-keygen -Y sign/verify`,
   with room for real key custody later. This is the single largest gap
   between PCAW and what a compliance buyer needs. (Precedents: soma,
   agent-receipts, Microsoft's draft receipts proposal.)
3. **Export standards-shaped evidence.** Wrap PCAW statements in DSSE /
   in-toto envelopes so existing verifiers can consume them; emit and ingest
   `agent-trace` attribution records; add an EU AI Act Article 12 mapping to
   the proof export. (Precedent: soma.)
4. **Worktree isolation per work item.** An `agent start --worktree` mode
   that materializes the claim in an isolated git worktree binds the boundary
   physically and matches the one pattern in this space with mass adoption.
5. **Push notifications for the approval inbox.** Approval Packs already
   exceed competitor bulk-approval semantics, but `serve` is local-pull-only.
   A webhook notifier for pending human decisions closes most of the UX gap.
   (Precedents: impri, gotoHuman.)
6. **Boundary simulation against the journal.** Replay a proposed boundary or
   authority change against recorded history before adopting it.
   (Precedent: Cordum's policy simulator.)

## What Palari Should Not Adopt

- **Memory systems** (openloomi, agent-receipts' memory graph, clawcompany's
  layered memory). Different product category.
- **Autonomy-first role simulation** (clawcompany's AI executive roster).
  Opposite governance posture.
- **Enterprise gateway infrastructure** (ContextForge-class federation,
  containers, RBAC servers). Zero-infra is the differentiation, not a gap.
- **A proprietary attribution format.** `agent-trace` won that race.

## Risks

- Platforms could begin signing their own session logs natively; joint
  backing of `agent-trace` shows appetite for shared formats. Mitigation:
  interop early, own the contract-and-approval binding layer above raw logs.
- Developer-experience governance has not monetized (Vibe Kanban shut down
  at 27k stars; HumanLayer pivoted). Verifiable receipts likely need a
  compliance-driven buyer, not a DX-driven one.

## Method

Landscape assembled from two independent research passes on 2026-07-15: one
verifying an externally supplied candidate list repo-by-repo against GitHub,
one surveying platform documentation, changelogs, and adoption signals.
Products that could not be verified to exist were excluded.
