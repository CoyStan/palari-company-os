# Kilo Code Integration

Palari Company OS can prepare a bounded work-item prompt and call Kilo Code through the Kilo CLI.

This is an optional external-tool bridge. Palari does not vendor Kilo, store Kilo credentials, manage Kilo sessions, or bypass Kilo permissions.

## Requirements

Install Kilo Code CLI separately:

```bash
npm install -g @kilocode/cli
```

or provide a command with:

```bash
PALARI_KILO_BIN=/path/to/kilo
```

When Kilo is not installed, `--allow-npx` can use:

```bash
npx --yes @kilocode/cli
```

## Commands

Check availability:

```bash
palari kilo status
palari kilo status --allow-npx
```

Preview a Kilo call for a Palari work item:

```bash
palari kilo run WORK-0001 --message "Start with the checklist"
```

Execute the call:

```bash
palari kilo run WORK-0001 --message "Start with the checklist" --execute
```

The command builds a prompt from:

- workspace name
- work item title, risk, intensity, status, and scope
- goal and Palari identity
- allowed resources
- selected sources
- allowed actions
- output targets
- forbidden actions
- queue attention and next action
- safety and approval state

## Boundaries

- Preview mode is the default.
- `--execute` is required before Palari launches Kilo.
- Palari does not add `--auto` or `--dangerously-skip-permissions`.
- Kilo runs with its own authentication, model configuration, and permission behavior.
- Palari passes `--dir` so Kilo runs in the intended project directory.
- Palari does not claim that Kilo completed, approved, merged, deployed, or wrote externally. Those outcomes still need receipts/evidence/review/human decisions in the workspace model.

## Current Limit

This is a CLI bridge. The static desktop prototype does not yet call Kilo from a browser button because it has no backend process or mutation channel. A future desktop app/backend can call the same bridge instead of inventing another Kilo path.
