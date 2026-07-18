# Universal Agent Adoption v1 — Completion Contract

Work item: `WORK-BF48A3D891A7428FB91AA80BF53856AA`

Integration owner: `WORK-3B7821F3452B40B283784832E86234C3`

Baseline: `f6e2cf9b3f59e4074ca459368103d802a4eb3b81`

Status vocabulary is `pending`, `in progress`, `completed`, or `blocked`.
Every completed checkbox names exact committed proof. The product rule is:
**one adoption action, no invented host guarantees**.

## Required Outcomes

- [x] **One provider-neutral adoption action**
  - Required outcome: one `palari init WORKSPACE-DIR --host HOST` action installs the portable
    repository contract and strongest honest local enforcement profile for
    Claude Code, Codex, Cursor, Devin, GLM, or a generic agent host.
  - Objective evidence: isolated-project tests prove each named profile,
    deterministic output, idempotent retry, preservation of existing
    instructions, and refusal to overwrite malformed or foreign configuration.
  - Verification command or artifact: `python3 -m unittest
    tests.test_agent_adoption` and installed-package CLI smoke.
  - Current status: completed; focused adoption and CLI tests pass.
  - Exact committed evidence when completed: foundation and boundary hardening
    at `92bca37449246ba9f34d301028157640d96794e4`,
    `3bf74e9a874df0cac4a999fc921836ca5c3078ac`, and
    `bd1dde8506ef83974bf7f3419ed5f0e3bbb3ab10`; the same `init --host`
    surface is committed at `06551e64c4d056a6c55fbbcb1ba960e63e599710`.

- [x] **Portable contract plus structural commit boundary**
  - Required outcome: adoption writes a bounded, managed `AGENTS.md` block and
    installs the existing claim-bound Git pre-commit gate for every host. It
    never overwrites non-Palari hooks or treats instructions as a sandbox.
  - Objective evidence: preservation, malformed-marker, unmanaged-hook,
    out-of-boundary staged-file, traversal, and symlink tests fail closed.
  - Verification command or artifact: agent-adoption and Git-hook suites.
  - Current status: completed; negative Git/adoption tests pass.
  - Exact committed evidence when completed: `3bf74e9a874df0cac4a999fc921836ca5c3078ac`,
    executable-wrapper proof at `bd1dde8506ef83974bf7f3419ed5f0e3bbb3ab10`,
    and atomic executable-hook/foreign-command repairs at
    `53400beeb3ab833b22fc3eb056ae0d7549874141` and
    `f9620da7a8d6728c35e27e09b0c2d820c214f80a`.

- [x] **Proven native session adapters only**
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
  - Current status: completed; Claude/Codex adversarial tests pass and other
    hosts remain explicitly advisory.
  - Exact committed evidence when completed: `92bca37449246ba9f34d301028157640d96794e4`,
    integrated native routing at `8ea7816fee11fe753345f122f23c48a5f89771d0`,
    and duplicate-workspace/compound-hook hardening at
    `53400beeb3ab833b22fc3eb056ae0d7549874141`, with exact executable-token
    classification at `f9620da7a8d6728c35e27e09b0c2d820c214f80a`.

- [x] **Complete agent loop over MCP**
  - Required outcome: MCP clients can select/start the next work item, request
    the provider-neutral session contract, check it, and invoke deterministic
    `agent advance`; the server exposes no review, human-decision, acceptance,
    merge, push, deployment, provider, or external-write authority.
  - Objective evidence: black-box MCP tests prove structured compatibility,
    local claim lifecycle, exact dry-run, and authority annotations.
  - Verification command or artifact: `python3 -m unittest
    tests.test_mcp_server` and stdio smoke.
  - Current status: completed; MCP and session-contract suites pass.
  - Exact committed evidence when completed: `485cb7bb4b85f4364e6fe1e19f4e05be975b75b8`.

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
