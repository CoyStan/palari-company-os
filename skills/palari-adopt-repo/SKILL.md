---
name: palari-adopt-repo
description: Adopt a Git repository into Palari through the existing palari init action. Use when a user asks to initialize, set up, install, or adopt Palari; add agent-ready repository boundaries; or attach a supported Claude, Codex, or Cursor host profile to an existing Palari workspace. Covers repository preflight, explicit host choice, first adoption versus idempotent host setup, result verification, and human trust boundaries. Do not use for normal task execution, independent review, uninstallation, or migration.
---

# Palari Adopt Repo

Use one `palari init` action to create or refresh the repository-local adoption
contract. Palari owns the generated files and bounded bootstrap commit; do not
reimplement them in the skill.

## Adopt the repository

1. Work from the intended Git repository. Inspect its root and existing changes
   without staging, cleaning, or rewriting anything:

   ```bash
   git rev-parse --show-toplevel
   git status --short
   ```

2. Determine whether this is first adoption or an existing valid Palari
   workspace. Use Palari's read-only validation when `workspace.json` exists;
   do not infer validity from the filename alone.
3. Select exactly one supported host: `claude`, `codex`, or `cursor`. Honor the
   user's choice. If it is ambiguous, stop and ask because host selection changes
   local enforcement. Read [hosts.md](references/hosts.md) when choosing or
   explaining the profile.
4. For first adoption, use the requested starter-agent name, or `Agent` when no
   name was requested:

   ```bash
   palari init --palari Agent --host HOST --json
   ```

5. For an existing workspace, target the exact directory that contains its
   `workspace.json` and use an existing Palari identity supplied by the user or
   shown by current Palari output. The Git root and `WORKSPACE-DIR` may differ;
   never collapse one into the other. Never invent the identity:

   ```bash
   palari init WORKSPACE-DIR --host HOST --as PALARI-ID --json
   ```

   Add `--strict-git` only with `--host cursor` and only when structural commit
   gating was explicitly selected.
6. Inspect the JSON result. Confirm the reported files and any bootstrap commit
   exclude unrelated pre-existing changes and preserve existing instructions.
   Do not assume the current `HEAD` was created by adoption unless Palari says so.
7. Verify the adopted workspace and re-inspect Git state:

   ```bash
   palari --workspace WORKSPACE-DIR validate --json
   git status --short
   ```

8. Report the chosen host, generated paths, commit result, validation result,
   preserved pre-existing changes, and any remaining owner boundary. For Codex,
   stop and ask the human to review `/hooks`; Palari cannot grant that trust.

## Non-negotiable boundaries

- Never overwrite or hand-edit generated adoption files to force success.
- Never stage or absorb unrelated changes into the bootstrap commit.
- Never run an alternate installer, legacy setup command, or compatibility path.
- Never remove existing adoption, migrate state, push, merge, deploy, approve,
  or perform another external write.
- Never claim a host hook is active when human trust or an explicit option is
  still required.

If `init` refuses the repository or existing workspace, report its exact blocker
and next action. Do not create missing governance state by hand.
