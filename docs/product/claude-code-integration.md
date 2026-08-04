# Claude Code Integration

Palari's agent rules ask agents to run `palari agent check` before saying a
task is done. This integration also enforces that boundary mechanically. It
wires Palari into [Claude Code hooks](https://code.claude.com/docs/en/hooks) so
allowed file changes do not depend only on the agent following instructions.

Stored files use `packet` for a task brief and `claim` for an assignment. See
the [Glossary](glossary.md) for the full mapping.

## What it enforces

The hook checks use the saved assignment and task-brief files that `palari
agent start` writes under `.palari/`. Before granting execute permission, they
compare those files with the current workspace records:

- **PreToolUse** — before Claude writes a file with `Write`, `Edit`, or
  `NotebookEdit`, the target path is checked against the active assignment's
  write boundary. Outside the boundary, the tool call is **denied before the
  write happens** and Claude receives the blocked-change message with the next
  safe commands. Inside the boundary, the write is allowed without a permission
  prompt because the task brief already allows it.
- **PreToolUse for Bash** — shell commands are checked with a deliberately
  conservative heuristic (redirections and common mutating commands such as
  `rm`, `mv`, `cp`, `tee`, `sed -i`, `git rm`). A suspected out-of-boundary
  write escalates to a human **ask**, never a silent deny or allow, because a
  heuristic should not decide on its own. Opaque interpreters, unreviewed
  executables, dynamic shell expansion or indirection, and Git witness
  mutations also require a human ask; Git global options cannot hide a witness
  subcommand, and an earlier allowed write cannot mask a later unsafe shell
  segment. Command environment assignments, execution-capable `git -c` or diff
  options, and `rg --pre` also ask. Unquoted pathname expansion, recursive or
  tree-shaped copy semantics, backup-producing write options, path-qualified
  executable names, hook installation/removal, and Palari commands not on the
  explicit agent-safe command list also ask. Human-attributed review or
  approval, integration approval/cancel/enqueue/send, Linear adoption,
  final-status, `work accept`, and generic task-brief or permission changes are
  denied from agent Bash. Bash `|&`, assignment-position tilde expansion,
  abbreviated GNU write options, Git helper-option abbreviations, and Git pathspec-file
  imports are treated as indirect rather than inheriting a safe command label;
  read/write `<>` redirections are write targets too. Git pathspec magic and
  quoted pathspec globs require review, and an explicit `--` keeps subsequent
  dash-prefixed operands in write/destructive target analysis. Agent-safe
  Palari mutations must resolve to the workspace configured for the hook.
- **Stop** — when Claude tries to finish its turn, `git status` is compared
  against the boundary. Out-of-boundary changes block the stop and tell Claude
  to revert or hand off, so writes that slipped past the Bash heuristic are
  still caught before the human sees "done". Palari's own `.palari/` runtime
  state is exempt.
- **SessionStart** — the active assignment rules (task, allowed write paths,
  check command) are injected into Claude's context at session start. Sessions
  without an assignment are pointed at `palari agent next`.

Hook handlers read `.palari/claims/`, `.palari/packets/`, and the current
workspace to ensure a self-rehashed task brief cannot expand the task's allowed
files, sources, or actions. They never mutate the workspace, and unexpected
handler errors fail open: a Palari error degrades to "no decision" instead of
locking up an unrelated Claude session. A structurally invalid active
assignment is an ordinary checked state and blocks or escalates writes rather
than taking that error path.

## Install

From the repository root that Claude Code runs in:

```bash
palari --workspace workspaces/your-workspace claude install
palari --workspace workspaces/your-workspace claude status
```

`install` merges three Palari-managed entries into `.claude/settings.json`,
preserving hooks owned by other tools. It is idempotent; re-running reports
`unchanged`. Options:

- `--local` writes `.claude/settings.local.json` (gitignored) instead of the
  shared settings file.
- `--strict` also escalates writes that **no** active assignment covers, and
  writes that target paths outside the repository, to a human ask. `palari init
  --host claude` / host adoption installs strict hooks by default for dogfood.
  Without `--strict` on the hook-only `claude install` path, transparent file
  writes in sessions with no assigned task are left to Claude Code's normal
  permission flow. Opaque, indirect, or unreviewed shell execution still asks
  even without an assignment so hidden permission-changing commands cannot
  bypass the hook by releasing an assignment first. Direct writes to workspace records, split collection files,
  `.palari/`, and standard or linked-worktree Git metadata also remain
  protected, including `dd of=`, `-t`, and
  `--target-directory` destinations. Compact/newline shell separators and
  ordinary existing-directory copy/move/link/install destinations resolve to
  their effective paths. Git repository overrides and ripgrep helper-launching
  options ask rather than inheriting a read-only classification. Abbreviated
  global CLI options are rejected, protected command pairs are scanned
  defensively, destructive parent-directory targets remain protected, and new
  or unclassified Palari commands fail closed to a human ask. The standard
  Claude settings files that hold these hooks are protected from direct edits
  and destructive parent operations. `history --restore` is classified as a
  human-only permission-changing command even when its options are reordered
  or use `--restore=...`; an agent shell receives a deny before any local
  restoration.
- `--remove` deletes the Palari-managed entries and nothing else.

The installed commands use `$CLAUDE_PROJECT_DIR`, so the settings file stays
portable across checkouts. When the project has a local `bin/palari` wrapper
(this repository does), hooks use it and need no pip install; otherwise the
`palari` CLI must be on `PATH` in the hook environment, and `claude status`
warns when it is not.

## Runtime flow

```text
palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
  -> writes .palari/claims/WORK-0003.json and the task brief
Claude Code session:
  SessionStart  -> task rules injected into context
  Write inside boundary   -> allowed
  Write outside boundary  -> denied with the blocked-change message
  Bash write outside      -> human ask
  Stop with stray changes -> blocked until reverted or handed off
```

Review assignments grant no write paths: they are read-only, so file writes
under a review-only assignment escalate to a human.

When several assignments are active in one workspace, a target is allowed only
when exactly one execute assignment covers it; overlapping permission fails
closed. Pin one Claude session to one assignment with the `PALARI_AS` and
`PALARI_WORK_ID` environment variables.

## Boundaries and honest limits

- Hooks enforce the **write** boundary. Allowed reads (`allowed_sources` and
  task-brief read paths) remain session guidance; enforcing them would block the
  repo access agents legitimately need.
- The Bash heuristic is best-effort by design. Its misses are the reason the
  Stop hook exists; the pair gives pre-write blocking for file tools plus
  post-hoc detection for everything else.
- The Stop hook inspects `git status`, so uncommitted out-of-boundary changes
  that predate the session will also block a stop. The block message says how
  to proceed; start agent sessions from a clean tree to avoid it.
- The PreToolUse matcher includes `Bash`, so every shell command in a hooked
  session invokes `palari` once. The handler reads the assignment and task
  brief, then recalculates execute permission from current workspace records. If a hooked
  session ever feels sluggish, this is the first place to measure.
- This is enforcement for Claude Code specifically. Other harnesses keep the
  cooperative rules from [agent-contract.md](agent-contract.md) until they
  grow their own adapters.
