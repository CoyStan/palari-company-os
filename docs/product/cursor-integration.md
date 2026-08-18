# Cursor Integration

Palari's agent rules ask agents to inspect `palari agent status` before saying a
task is done. Cursor does not expose a Claude-style pre-write deny hook, so this
integration is honest about what it can enforce:

- **Session boundary:** an always-applied project rule at
  `.cursor/rules/palari-boundary.mdc` that tells the agent how to start work,
  stay inside `allowed_paths.write`, and recover from a stuck claim.
- **Commit boundary (default):** the same IDE-agnostic git pre-commit gate used
  by other hosts. It rejects commits that stage files outside an active claim.
  With no active claim, commits are allowed.

Stored files use `packet` for a task brief and `claim` for an assignment. See
the [Glossary](glossary.md) for the full mapping.

## Safe first setup

```bash
palari init --host cursor
```

That installs the portable `AGENTS.md` contract, the advisory Cursor rule, and
the git pre-commit hook. Humans are not bricked: with no active claim, commits
are allowed.

Skip the commit gate when a Cloud/agent environment must not install hooks:

```bash
palari init --host cursor --no-git-hook
```

`--strict-git` is kept as a no-op alias for the default gate. On an existing
workspace:

```bash
palari cursor install
palari git install
```

`palari cursor install --no-git-hook` writes/updates only the project rule.
`palari cursor install --remove` removes the managed rule and, unless
`--no-git-hook`, the Palari-managed git hook.

## What it enforces

| Layer | Default for `init --host cursor` | Behavior |
| --- | --- | --- |
| Project rule | on | Advisory instructions always applied in Cursor |
| Git pre-commit | on | Structural commit gate; skip with `--no-git-hook` |
| Pre-write deny | unavailable | Cursor has no Claude-style PreToolUse deny |

When the git hook is installed:

- staged files outside an active execute claim's write boundary fail the commit
- invalid active claim context fails closed
- **no active claim ⇒ commits allowed** (humans and emergency fixes stay unblocked)

## Recovery

If a claim is stuck and the git gate is installed:

```bash
palari agent release WORK-ID --as PALARI-ID --json
palari cursor status
```

To remove Cursor adoption artifacts:

```bash
palari cursor install --remove
# or only the commit gate:
palari git install --remove
```

## Status

```bash
palari cursor status
palari cursor status --json
```

Reports whether the managed rule is present, whether the git hook is installed,
and any active claims with their allowed write paths.

## Boundaries and honest limits

- Cursor cannot deny an edit before it happens. Treat the project rule as
  advisory guidance, not a sandbox.
- Structural enforcement is at **commit** time only.
- Adoption grants no review, approval, merge, push, deployment, provider, or
  external-write authority.
- For Claude Code's structural pre-write hooks, see
  [Claude Code Integration](claude-code-integration.md).
- For the shared agent operating contract, see [Agent Contract](agent-contract.md).
