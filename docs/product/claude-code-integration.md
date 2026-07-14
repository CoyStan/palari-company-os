# Claude Code Integration

Palari's agent contract asks agents to run `palari agent check` before
claiming work is done. A well-behaved agent honors that. This integration is
for the moment it does not: it wires Palari into
[Claude Code hooks](https://code.claude.com/docs/en/hooks) so the packet write
boundary is enforced by the harness itself, not by the agent's goodwill.

New to the packet and claim vocabulary? Start with the
[Glossary](glossary.md).

## What It Enforces

Three hooks, derived from the persisted claim and packet files that `palari
agent start` writes under `.palari/` and reconciled with current workspace
truth before execute authority is granted:

- **PreToolUse** — before Claude writes a file with `Write`, `Edit`, or
  `NotebookEdit`, the target path is checked against the active claim's write
  boundary. Outside the boundary, the tool call is **denied before the write
  happens** and Claude receives the blocked-change message with the next safe
  commands. Inside the boundary, the write is allowed without a permission
  prompt: the packet is the permission surface.
- **PreToolUse for Bash** — shell commands are checked with a deliberately
  conservative heuristic (redirections and common mutating commands such as
  `rm`, `mv`, `cp`, `tee`, `sed -i`, `git rm`). A suspected out-of-boundary
  write escalates to a human **ask**, never a silent deny or allow, because a
  heuristic should not have deny authority. Opaque interpreters, unreviewed
  executables, dynamic shell expansion or indirection, and Git witness
  mutations also require a human ask; Git global options cannot hide a witness
  subcommand, and an earlier allowed write cannot mask a later unsafe shell
  segment. Command environment assignments, execution-capable `git -c` or diff
  options, and `rg --pre` also ask. Human-attributed review,
  decision, integration approval, terminal lifecycle, work-accept, and generic
  packet-authority mutations are denied from agent Bash.
- **Stop** — when Claude tries to finish its turn, `git status` is compared
  against the boundary. Out-of-boundary changes block the stop and tell Claude
  to revert or hand off, so writes that slipped past the Bash heuristic are
  still caught before the human sees "done". Palari's own `.palari/` runtime
  state is exempt.
- **SessionStart** — the active claim contract (work item, allowed write
  paths, check command) is injected into Claude's context at session start.
  Unclaimed sessions are pointed at `palari agent next`.

Hook handlers read `.palari/claims/`, `.palari/packets/`, and the current
workspace to ensure a self-rehashed runtime packet cannot expand current scope.
They never mutate the workspace, and unexpected handler errors fail open: a
Palari error degrades to "no decision" instead of locking up an unrelated
Claude session. A structurally invalid active claim is an ordinary checked
state and blocks or escalates writes rather than taking that error path.

## Install

From the project root that Claude Code runs in:

```bash
palari --workspace workspaces/your-workspace claude install
palari --workspace workspaces/your-workspace claude status
```

`install` merges three Palari-managed entries into `.claude/settings.json`,
preserving hooks owned by other tools. It is idempotent; re-running reports
`unchanged`. Options:

- `--local` writes `.claude/settings.local.json` (gitignored) instead of the
  shared settings file.
- `--strict` also escalates writes that **no** active claim covers, and writes
  that target paths outside the repository, to a human ask. Without it,
  transparent file writes in sessions with no claimed work item are left to
  Claude Code's normal permission flow. Opaque, indirect, or unreviewed shell
  execution still asks even without a claim so hidden authority commands cannot
  bypass the hook by releasing a claim first. Direct writes to workspace truth,
  split collection files, `.palari/`, and standard or linked-worktree Git
  metadata also remain protected, including `dd of=`, `-t`, and
  `--target-directory` destinations. Compact/newline shell separators and
  ordinary existing-directory copy/move/link/install destinations resolve to
  their effective paths. Git repository overrides and ripgrep helper-launching
  options ask rather than inheriting a read-only classification. Abbreviated
  global CLI options are rejected, protected command pairs are scanned
  defensively, and destructive parent-directory targets remain protected.
- `--remove` deletes the Palari-managed entries and nothing else.

The installed commands use `$CLAUDE_PROJECT_DIR`, so the settings file stays
portable across checkouts. When the project has a local `bin/palari` wrapper
(this repository does), hooks use it and need no pip install; otherwise the
`palari` CLI must be on `PATH` in the hook environment, and `claude status`
warns when it is not.

## Runtime Flow

```text
palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
  -> writes .palari/claims/WORK-0003.json and the packet
Claude Code session:
  SessionStart  -> packet contract injected into context
  Write inside boundary   -> allowed
  Write outside boundary  -> denied with the blocked-change message
  Bash write outside      -> human ask
  Stop with stray changes -> blocked until reverted or handed off
```

Review-mode claims grant no write paths: they are read-only by contract, so
file writes under a review-only claim escalate to a human.

When several claims are active in one workspace, a target is allowed only when
exactly one execute claim covers it; overlapping authority fails closed. Pin
one Claude session to one claim with the `PALARI_AS` and `PALARI_WORK_ID`
environment variables.

## Boundaries And Honest Limits

- Hooks enforce the **write** boundary. Read scope (`allowed_sources`, packet
  read paths) remains contract-level guidance; enforcing reads would block the
  repo access agents legitimately need.
- The Bash heuristic is best-effort by design. Its misses are the reason the
  Stop hook exists; the pair gives pre-write blocking for file tools plus
  post-hoc detection for everything else.
- The Stop hook inspects `git status`, so uncommitted out-of-boundary changes
  that predate the session will also block a stop. The block message says how
  to proceed; start agent sessions from a clean tree to avoid it.
- The PreToolUse matcher includes `Bash`, so every shell command in a hooked
  session invokes `palari` once. The handler reads the claim and packet and
  recompiles execute authority from workspace truth; if a hooked session ever
  feels sluggish, this is the first place to measure.
- This is enforcement for Claude Code specifically. Other harnesses keep the
  cooperative contract from [agent-contract.md](agent-contract.md) until they
  grow their own adapters.
