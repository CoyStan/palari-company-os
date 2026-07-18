# Universal Agent Adoption v1 — Completion Contract

Work item: `WORK-BF48A3D891A7428FB91AA80BF53856AA`

Integration owner: `WORK-3B7821F3452B40B283784832E86234C3`

Baseline: `f6e2cf9b3f59e4074ca459368103d802a4eb3b81`

Status vocabulary is `pending`, `in progress`, `completed`, or `blocked`.
Every completed checkbox names exact committed proof. The product rule is:
**one adoption action, no invented host guarantees**.

## Required Outcomes

- [ ] **One provider-neutral adoption action**
  - Required outcome: one `palari agent adopt` action installs the portable
    repository contract and strongest honest local enforcement profile for
    Claude Code, Codex, Cursor, Devin, GLM, or a generic agent host.
  - Objective evidence: isolated-project tests prove each named profile,
    deterministic output, idempotent retry, preservation of existing
    instructions, and refusal to overwrite malformed or foreign configuration.
  - Verification command or artifact: `python3 -m unittest
    tests.test_agent_adoption` and installed-package CLI smoke.
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] **Portable contract plus structural commit boundary**
  - Required outcome: adoption writes a bounded, managed `AGENTS.md` block and
    installs the existing claim-bound Git pre-commit gate for every host. It
    never overwrites non-Palari hooks or treats instructions as a sandbox.
  - Objective evidence: preservation, malformed-marker, unmanaged-hook,
    out-of-boundary staged-file, traversal, and symlink tests fail closed.
  - Verification command or artifact: agent-adoption and Git-hook suites.
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] **Proven native session adapters only**
  - Required outcome: Claude keeps its existing structural hook adapter; Codex
    receives project-local SessionStart, PreToolUse, and Stop hooks using its
    documented protocol. Codex `apply_patch` targets are exact, unsupported
    `ask` decisions become deny, and project trust remains an explicit human
    activation step. Hosts without a tested hook protocol remain advisory plus
    commit-gated, visibly and without security theater.
  - Objective evidence: exact-path allow/deny, opaque-shell, human-authority,
    stop-time dirt, configuration merge, trust-state, and unsupported-host
    tests.
  - Verification command or artifact: adoption and existing Claude-hook suites;
    current official Codex hook contract recorded in product docs.
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] **Complete agent loop over MCP**
  - Required outcome: MCP clients can select/start the next work item, request
    the provider-neutral session contract, check it, and invoke deterministic
    `agent advance`; the server exposes no review, human-decision, acceptance,
    merge, push, deployment, provider, or external-write authority.
  - Objective evidence: black-box MCP tests prove structured compatibility,
    local claim lifecycle, exact dry-run, and authority annotations.
  - Verification command or artifact: `python3 -m unittest
    tests.test_mcp_server` and stdio smoke.
  - Current status: in progress.
  - Exact committed evidence when completed: pending.

- [ ] **Minimal, compatible, and independently reviewed delivery**
  - Required outcome: standard library only; no global config, credential,
    network, provider, daemon, autonomous review, or human acceptance; existing
    CLI/MCP/session-contract behavior remains compatible. A fresh independent
    review accepts the exact integrated candidate.
  - Objective evidence: focused suites, docs/schema checks, complete gate,
    isolated install smoke, changed-path check, and exact-head review.
  - Verification command or artifact: `./bin/palari docs check --json`,
    `./scripts/verify.sh`, `./scripts/install_smoke.sh`, and review artifact.
  - Current status: pending.
  - Exact committed evidence when completed: pending.

## Non-claims

- Git hooks are commit-time enforcement, not a filesystem sandbox.
- Project-local Codex hooks do not activate until the user reviews and trusts
  them in the host.
- Cursor, Devin, GLM, and generic-host profiles are portable-contract plus
  commit-gate profiles until their native protocols are separately proven.
- Declared Palari actor IDs do not authenticate a human or agent against a
  hostile process running as the same OS user.

