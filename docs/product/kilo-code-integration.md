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

## CLI Commands

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

From a repo checkout, `scripts/kilo_real_smoke.sh` runs the same path as a
safe smoke:

```bash
./scripts/kilo_real_smoke.sh
PALARI_KILO_ALLOW_NPX=1 ./scripts/kilo_real_smoke.sh
PALARI_KILO_SMOKE_EXECUTE=1 PALARI_KILO_TIMEOUT=120 ./scripts/kilo_real_smoke.sh
PALARI_KILO_MODEL=openrouter/deepseek/deepseek-v4-flash ./scripts/kilo_real_smoke.sh
```

The smoke previews by default. It calls the real Kilo CLI only when
`PALARI_KILO_SMOKE_EXECUTE=1` is set. Use `PALARI_KILO_TIMEOUT` to keep the
real execution bounded. Use `PALARI_KILO_MODEL` or `PALARI_KILO_AGENT` to test
a non-default Kilo route.

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

## Desktop App Bridge

The static desktop prototype remains read-only when opened from generated
files. To let the browser call Kilo through Palari, run the local server:

```bash
palari desktop-serve --out /tmp/palari-desktop-prototype
```

From a repo checkout, the convenience script is:

```bash
./scripts/run_desktop_kilo_app.sh
```

The served desktop prototype calls local endpoints:

- `GET /api/kilo/status`
- `POST /api/kilo/run`

By default, the app can preview the Kilo prompt for the selected desktop work
item. Execution is disabled unless the server starts with:

```bash
palari desktop-serve --out /tmp/palari-desktop-prototype --allow-kilo-execute
```

`--allow-npx`, `--model`, `--agent`, `--dir`, and `--timeout` are also available
on `desktop-serve`. The desktop prompt is built from the committed demo fixture
and includes visible source permissions, blocked sources, output targets,
receipt state, and authority requirements.

The wrapper exposes the same choices as environment flags:

```bash
PALARI_KILO_ALLOW_NPX=1 ./scripts/run_desktop_kilo_app.sh
PALARI_KILO_ALLOW_EXECUTE=1 ./scripts/run_desktop_kilo_app.sh
PALARI_KILO_MODEL=provider/model PALARI_KILO_AGENT=name ./scripts/run_desktop_kilo_app.sh
```

## Boundaries

- Preview mode is the default.
- `--execute` is required before Palari launches Kilo.
- Palari does not add `--auto` or `--dangerously-skip-permissions`.
- Kilo runs with its own authentication, model configuration, and permission behavior.
- Palari passes `--dir` so Kilo runs in the intended project directory.
- Palari does not claim that Kilo completed, approved, merged, deployed, or wrote externally. Those outcomes still need receipts/evidence/review/human decisions in the workspace model.

## Current Limit

This is still a local developer bridge. It does not create a cloud backend,
persist Kilo results into a workspace, connect Google Drive, or turn Kilo output
into receipts/evidence automatically.
