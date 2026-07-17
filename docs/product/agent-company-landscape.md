# The Agent-Company Landscape

A verified survey of systems that build "companies / organizations / teams of
AI agents", assessed against the five properties that define Palari's
governed-company concept. Compiled 2026-07-18 from three parallel research
passes (open-source frameworks, commercial products, academic research);
every repository, star count, and product claim was verified by direct fetch
or clone on 2026-07-15 through 2026-07-17. Star counts and funding drift —
treat them as order-of-magnitude signals and recheck before relying on them.

Status: **research snapshot, not a normative or product document.** It exists
so positioning and roadmap decisions can cite real competitors instead of
vibes. Companion: the [Palari Blueprint](palari-blueprint.md) (protocol and
strategy) and the PACT and Company-of-Palaris memoranda (architecture).

## The five properties

Every system below is scored against the properties that, combined, define
Palari's concept — not against orchestration quality, which many do well:

1. **Durable role identity** — is an agent role a persistent, accountable
   identity with cross-run history, or a prompt persona re-instantiated each
   run?
2. **Authority separated from capability** — is what an agent MAY cause
   distinct from what its model CAN do, and enforced by something other than
   its prompt?
3. **Enforced boundaries** — are write/tool/action limits structurally
   enforced (hooks, sandbox, policy), or advisory?
4. **Verifiable evidence** — is there an audit record verifiable *without
   trusting the operator* (signed/hash-chained/offline), or only logs?
5. **Human decision gates** — are approvals enforced and on by default, or
   optional and off by default?

## Executive finding

Across ~60 verified systems, **no project combines all five properties, and
none produces operator-independent verifiable evidence.** The field splits
into three camps, each holding one or two organs of the concept:

- **Company-semantics products with soft governance** — org charts, roles,
  budgets, kanban; enforcement advisory (paperclip, OpenOPC, clawcompany,
  squad, alook, tinyagi, Auto-Company, agent-teams-ai, Wegent).
- **Hard-enforcement middleware with no organizational model** — policy
  engines, sandboxes, tamper-evident logs; no roles, work items, or company
  semantics (Microsoft Agent Governance Toolkit; AgentScope 2.0 and OpenHands
  as strong partials).
- **Orchestration substrates** — graphs, handoffs, teams; no authority or
  evidence layer (LangGraph, AutoGen/Agent Framework, CrewAI, CAMEL,
  Claude Code native Agent Teams).

Two independent forces are worth naming. **Orchestration is commoditizing**:
Claude Code shipped native Agent Teams (shared task list, mailboxes, tool
allowlists, untrusted inter-agent consent), absorbing the category that
third-party orchestrators occupied. And **the fastest-growing projects are
removing safety layers**, not adding them — several ship
`bypassPermissions`/`--dangerously-skip-permissions` as their default.

The integrated cell — durable governed roles + authority separated from
capability + enforced boundaries + offline-verifiable receipts + mandatory
human gates — remains unoccupied by every surveyed system except Palari.

## Camp 1 — the strongest "AI company" products

| System | Stars | What it is | 5-property read |
| --- | --- | --- | --- |
| **paperclip** (paperclipai) | ~74k | The category-defining "company for agents": org charts (COMPANY.md→TEAM.md→AGENTS.md), stable agent slugs, budgets, board-approval workflows, bring-your-own-runtime ("if it can receive a heartbeat, it's hired"). | Role id: **yes** (registry rows). Authority: **partial** — budgets/approvals gate assignment server-side, but the companies spec is explicitly advisory ("registries are optional discovery layers, not authorities") and local CLI adapters "run unsandboxed on the host." Boundaries: **weak** (timeout + cwd). Evidence: **no** (claimed-immutable server logs, nothing cryptographic). Gates: **yes**. |
| **OpenOPC** (HKUDS) | ~0.9k | "Personal AI-native company"; recruiter agent chooses reuse-vs-fresh-hire; dependency-DAG work; five-phase state machine. Two weeks old at survey time. | Role id: **yes-partial** (durable employees with accumulated profiles). Authority: **partial** — tiered risk approval (auto/LLM-review/human) enforced at command level, but risk tiers are heuristic, no per-role write boundary. Boundaries: **partial**. Evidence: **no**. Gates: **yes**. |
| **squad** (bradygaster) | ~3.0k | GitHub Copilot CLI/SDK; git-committed per-agent `charter.md` + growing `history.md` ("clone the repo, get the team with accumulated knowledge"); coordinator routing; Ralph watch mode. | Role id: **best durable-identity pattern in the survey** (git chain of custody). Authority: **split** — markdown mode is prompt-only with `--yolo` default; the SDK has real pre-tool hooks/file guards but is "experimental." Evidence: **no** (plain-text breadcrumbs). Gates: human-led rhetoric undercut by `--yolo` quickstart. |
| **agent-teams-ai** (777genius) | ~1.6k | Electron desktop app; teams of 9 CLI runtimes over an app-owned kanban; teammates message/review each other. | Role id: partial (task context persists, identity re-provisioned). Authority: **real** — RuntimeToolApprovalCoordinator + safe-command allowlist + optional worktree isolation. Evidence: strong logging/attribution, not cryptographic. Gates: configurable. |
| **Wegent** (wecode-ai) | ~0.7k | Most platform-like: Kubernetes-style YAML CRDs (Ghost+Shell+Model=Bot, Team, Collaboration, Task); FastAPI+Next.js+Tauri; sandboxed executors. | Role id: durable *definitions*, per-task execution. Authority: infrastructure-flavored (E2B-compatible sandbox, MCP-scoped capability). Evidence: "traceable executions" = logs + PRs. Gates: task-granularity. High engineering substance per star. |
| **AppGenesisForge** (pcliangx) | ~0.7k | **Closest philosophical cousin to Palari.** Scaffold over Claude Code Agent Teams; 19 roles from a `roles.yaml` SSOT; 7-stage gated pipeline. | Role id: no (personas per run). Authority: **strongest enforcement in the survey** — blocking PreToolUse hooks enforce per-role `write_scope`, a hook recomputes reviewer verdicts and rejects "has Critical but wrote approve," deny-list tamper detection, gate-strength self-audit. Evidence: **only project treating evidence as first-class and machine-checked** (SIT-evidence audits, verdict recomputation). Gates: **yes** (mandatory tech-stack + UAT sign-off). Solo-maintained; admits its write-scope hook fails open without jq. |
| **clawcompany** (Claw-Company) | ~0.6k | Local-first "AI company OS": 38 roles, 6 templates, 4-layer memory ("remembers everything, locally"). | Role id: partial (durable role rows + shared company memory). Authority: weak (tool allowlist + budget tier, no sandbox). Evidence: **no** (cost tracking only). Gates: lifecycle exists but `approvalRequired` defaults to **false**. |
| **alook** (alookai) | ~1.0k | Local daemon gives each agent an email address; 9 runtime drivers; org chart; append-only per-agent timeline. | Role id: durable (email + workdir + timeline). Authority: **none — explicitly bypassed** (launches with `--dangerously-skip-permissions`). Evidence: append-only timelines + DB audit = logs. Gates: fire-and-forget. Depends on hosted Cloudflare infra despite "local-first." |
| **tinyagi** (fka TinyClaw) | ~3.6k | Multi-channel chat-routing daemon; per-agent persistent workspaces; SQLite message queue; hourly heartbeats. Dormant since March 2026. | Role id: partial (persistent workspaces + CLI history). Authority: weak (inbound sender allowlists only). Evidence: logs. Gates: fire-and-forget. |
| **Auto-Company** (MaxMiksa) | ~1.3k | ~740-line bash loop invoking Claude Code/Codex with a shared `consensus.md`. Dormant since May 2026. | Role id: no (one shared markdown file is the only cross-cycle state). Authority: **none — ships `bypassPermissions`**. Evidence: logs. Gates: fire-and-forget. "5-layer MAS" = shell script + prompts. |

## Camp 2 — enforcement middleware and strong partials

| System | Stars | 5-property read |
| --- | --- | --- |
| **Microsoft Agent Governance Toolkit** | ~4.9k | The credibility threat, as middleware not a company OS. Authority: **yes** — deterministic policy engine (YAML/OPA/Cedar) with allow/deny/require-approval, the only major project architecturally separating authority from capability. Boundaries: **yes** (denies + sandbox privilege rings). Evidence: **closest to yes** — Merkle/hash-chained tamper-evident audit, still server-side not offline-verifiable. Gates: **yes**. Lacks: work items, durable governed roles, org semantics, local-first receipts. Public preview. |
| **OpenHands** (fka OpenDevin) | ~81k | Strongest autonomous-execution product; V1 SDK rewrite. Role id: no (immutable single-agent spec). Authority: **partial** — Docker/remote sandbox + `SecurityAnalyzer` risk rating + enforced `WAITING_FOR_CONFIRMATION` gate. Evidence: **best pre-crypto** — immutable append-only event log with deterministic replay, still unsigned. Gates: enforced when enabled. Fully model-agnostic incl. mid-run model switching (live proof of "any model occupies the session"). |
| **AgentScope 2.0** (Alibaba) | ~28k | Strongest authority story among general frameworks. Authority: **partial** — 2.0 permission system decides allow/deny/escalate from rules + tool type + actual inputs; real sandbox backends (Docker/E2B/K8s). Evidence: OpenTelemetry traces. Gates: permission escalation, permissive by default. No durable identity, no receipts. |
| **VERITAS OS** | ~34 | Negligible adoption, but conceptually Palari-like: hash-chained Ed25519-signed TrustLog. Named to show the *idea* has independent instances; the *integration* does not. |

## Camp 3 — orchestration substrates (no authority/evidence layer)

| System | Stars | Note |
| --- | --- | --- |
| **Claude Code native Agent Teams** | (Anthropic) | The commoditization event. Shared file-locked task list + mailboxes; teammates honor tool allowlists, permission prompts bubble to the human, and a teammate **cannot approve permissions or relay consent** (untrusted). Ephemeral identity, no receipts. This is also the delegation execution model the Company-of-Palaris memo named as the missing consumer for derived session contracts — now built by the platform. |
| **LangGraph** | ~34k | Best-enforced HITL primitive (`interrupt()` + durable checkpoints); checkpointed threads are the nearest OSS analog to model-agnostic session continuity. No roles, authority, or evidence. |
| **OpenHands** | (above) | Also the strongest substrate for durable conversation state. |
| **AutoGen / Microsoft Agent Framework / AG2** | ~50k | Merged with Semantic Kernel into `agent-framework` (Oct 2025). Docker code-exec sandbox available; approval middleware hooks; OTel traces. No authority/role/evidence model. |
| **CrewAI** | ~53k | Largest framework adoption; Agent(role/goal/backstory)+Task+Crew. Scores no/no/no/no/optional on the governance axes — adoption ≠ governance. |
| **CAMEL / Workforce / OWL** | ~17k (+20k OWL) | Task-decompose + coordinator assignment; per-agent toolkit allowlists; sandboxed interpreters; `WorkforceLogger` JSON; pause/snapshot human API. Best model-swap continuity of the classic libraries. No durable identity, no receipts. |
| **OpenAI Agents SDK** | ~13k | Code-enforced guardrails + per-agent tool allowlists. No roles, no gates, no evidence. |
| **agency-swarm** | ~4.5k | Notable: enforced directional communication topology (an agent cannot address undeclared peers). No sandbox, no receipts. |
| **AgentScope / swarms / PraisonAI** | 28k / 7k / 8.5k | swarms and PraisonAI are hype-forward READMEs over standard orchestration libraries; PraisonAI has a real in-process dangerous-tool approval registry. |
| **ruflo** (fka claude-flow) | ~65k | High stars, low substance: a repo issue documents ~85% of its MCP tools as alleged mocks; docs encourage `--dangerously-skip-permissions`. It *removes* the enforcement layer. The clearest case of stars measuring narrative, not depth. |
| **oh-my-claudecode** | ~38k | Dominant community orchestration layer; staged team pipelines + quality gates riding Claude Code's permissions. Adds quality gates, not policy. |
| **harness** (revfactory) | ~8.4k | 35 markdown files: a meta-prompt that generates Claude Code teams. Zero runtime code, zero enforcement, author-measured "+60% quality" (n=15) with prescribed citation phrasing. Highest star-to-substance ratio in the survey. |
| **MetaGPT** | ~69k | Dormant as OSS since Jan 2026; makers pivoted to the commercial "Atoms" product. Budget cap is the only enforced control. |
| **ChatDev** | ~34k | Deleted its virtual-software-company core to a legacy branch (Jan 2026); rewrote as a generic YAML workflow engine. Per-node tool allowlists; optional `human` graph node. |

**The pioneers' verdict:** MetaGPT and ChatDev — the two projects that
*founded* the company-of-agents metaphor — both walked away from it in early
2026, toward commercial app-builders and generic workflow tooling. Neither
replaced the metaphor with governance.

## Commercial products (the "AI workforce" category)

No vendor offers operator-independent verifiable evidence — the entire field
is vendor-attested SaaS logs. The nearest fragments, each holding one organ:

- **Maisa** — "Chain-of-Work": structured auditable record of logic +
  execution designed for regulator inspection. The closest pitch to receipts;
  still vendor-hosted attestation, not offline proof. Watch closely.
- **Cognition (Devin)** — durable-ish worker (persistent Knowledge,
  playbooks, org machine identity), per-task audit logs exportable to the
  customer's SIEM (customer custody of vendor-generated logs). Code review IS
  the human gate; git gives coding agents identity + evidence + gates for
  free — exactly what Palari generalizes to non-code work.
- **Ema** — "universal AI employee," EmaFusion routes 100+ models under a
  stable role persona: validates "any model occupies the role."
- **Relevance AI** — sells the org-chart metaphor with first-class
  approval/escalation paths as configured objects.
- **Lindy** — best granular HITL (per-side-effect confirmation, "graduated
  autonomy" — start gated, loosen with trust).
- **Sierra** — supervision-by-agent (an independent watcher per worker);
  same-vendor, same-infrastructure, so not independent review in Palari's
  sense. **11x** — the cautionary tale: fabricated customer logos and
  inflated ARR, founder ousted; the market's own proof that self-reported
  AI-worker performance can't be trusted, even by the vendor's investors.

**Governance-layer startups** betting agent identity is a standalone company:
NewCore ($66M seed, split-key credential architecture — customer holds half),
Runlayer (MCP chokepoint enforcement), Valarian ("sovereign control layer"
for governments, closest to local-first in spirit).

## The commoditization threat (enterprise platforms)

The hyperscalers are converging on **agent identity + policy + audit
dashboards** as bundled platform features, shipping now:

- **Microsoft** — Entra Agent ID (GA): agents get directory identities
  governed "like employees" (conditional access, lifecycle, access reviews);
  Agent 365 (~$15/user/mo): registry + access control + observability,
  including third-party agents.
- **Google** — Gemini Enterprise Agent Platform: Agent Identity + Agent
  Gateway (central tool-call policy) + Agent Registry.
- **ServiceNow** — AI Control Tower expanded to Discover/Observe/Govern/
  Secure/Measure across any vendor's agents (30 integrations); acquired
  Traceloop (observability) + Veza (authorization graph).
- **Salesforce** — Agentforce records every action against process
  "blueprints" as a permanent audit trail (a receipts-shaped idea).
- **Okta** — Cross App Access (OAuth for agents), "verifiable credentials"
  language entering the identity-fabric roadmap.

Within 12–18 months, "agent identity + permissions + audit log" is table
stakes bundled with the suite. What the platforms are structurally unlikely
to commoditize, because their model is "trust our cloud": (a) evidence
verifiable *without* trusting the platform operator; (b) local-first/offline
operation; (c) cross-organizational proof portability; (d) role identity that
survives *across* model vendors (each hyperscaler's agent identity is captive
to its own directory). Those four cells are where a local-first governance
layer isn't competing with the giants — it's positioned to audit them.

## What the research says

Independent of the products, the 2026 research literature supports the
governed-organization thesis and is converging on Palari's exact primitives:

- **Structure beats scale.** MAST (Berkeley, 150+ annotated traces) finds
  ~63% of multi-agent failures are organizational-design failures, not model
  failures; adding multi-level verification to ChatDev gained +15.6% task
  success with the same model. Encoded process beats freeform collaboration
  (MetaGPT's SOP results; Anthropic's orchestrator+subagent research system
  +90.2% on breadth-first evals, at ~15× token cost).
- **The orchestrator is the highest-risk role** — studies attribute most
  long-horizon failures to it, not the workers; hidden orchestration
  measurably suppresses safety behavior (argument for *legible* authority).
- **The empirical ceiling is real.** On TheAgentCompany (CMU), 2026's best
  systems complete only ~33–42% of realistic company tasks at ~$4/task, and
  are worst at exactly the collegial communication a company runs on — direct
  evidence that human decision gates are the bridge, not overhead.
- **Roles emerge but drift.** Project Sid (1000+ agents) shows roles and
  institutions arise spontaneously but stay fragile — argument for making
  roles durable infrastructure rather than emergent behavior.
- **Convergence on Palari's primitives, still fragmented.** A COINE 2026
  paper ("Agent Contracts") independently derives budget-conservation laws
  (Σ child budgets ≤ parent); an "Organizational Control Layer" paper does
  execution-boundary governance with receipts and human gates; a governance
  study finds institutional structure predicts outcomes better than model
  identity. All prototype-stage papers; none integrated into a deployable
  system.
- **Identity rails are industrializing without the governance layer.**
  A2A v1.0 (150+ orgs) ships Signed Agent Cards; Entra Agent ID is GA; OIDF
  is drafting delegated-approval profiles (AARP). Durable agent identity is
  being standardized model-independently — Palari should anchor to these
  rails, not reinvent identity.

## Ideas worth adapting into Palari

The survey surfaced two concrete mechanisms worth folding into the roadmap
when it is next groomed (as governed work items, not merged on sight):

1. **Verdict-consistency validation** (from AppGenesisForge): a review whose
   recorded verdict contradicts its own recorded findings ("has Critical
   findings but wrote approve") should fail closed. This is a cheap, powerful
   extension to Palari's existing review-binding checks.
2. **Gate-strength self-audit** (from AppGenesisForge): a mechanism that
   verifies every documented enforcement gate actually exists and reports its
   real strength honestly — a direct rhyme with Palari's enforcement-honesty
   profile (`palari-enforced`/`adapter-required`/`advisory`), applied to the
   whole system rather than one contract.

Two patterns already validated by adoption that Palari implements or plans:
git-committed identity with accumulated history (squad — Palari's governed
records generalize it), and model-agnostic mid-run occupancy (OpenHands, Ema —
Palari's session-contract-over-claim model formalizes it with authority the
others lack).

## Verdict

Better *products* than Palari exist today, by a wide margin — paperclip owns
the company narrative at ~74k stars, OpenHands owns autonomous execution at
~81k, Microsoft AGT owns enforcement credibility. Better *concept* than
Palari's does not exist: the integrated combination of durable governed
roles, authority separated from capability, enforced boundaries,
offline-verifiable receipts, and mandatory human gates is occupied by exactly
one repository. The gap between Palari and the field's leaders is not quality
— it is distribution and packaging — and the four defensible cells
(operator-independent evidence, local-first, cross-org proof portability,
cross-vendor role identity) are on a commoditization clock the platforms are
already running. The concept survived an exhaustive adversarial search; the
work that remains is making the wedge visible before the clock runs out.

## Method

Three parallel research passes (2026-07-15 to 2026-07-17): open-source
frameworks (~40 systems, GitHub API + shallow clones of the ten 2026
entrants), commercial products (~20, funding/traction verified against
primary sources), and academic research + benchmarks + identity standards.
Systems that could not be verified to exist were excluded; unverified funding
or traction claims are marked as such in the source research. Star counts are
live as of the fetch dates and will drift.
