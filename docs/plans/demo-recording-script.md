# 90-Second Demo Recording Script

This is the human recording script for the launch GIF/video. Record from a
fresh terminal in a clean clone of `palari-company-os`. Use a 1440px-wide
window if possible. Keep the terminal font large enough to read after social
compression.

## Setup Before Recording

```bash
git clone https://github.com/CoyStan/palari-company-os.git
cd palari-company-os
```

If the repo is already cloned, start from the repo root:

```bash
git status --short
```

Expected: no output.

## Shot List

### 0:00-0:08 — Problem

Show the README first screen.

Caption:

```text
AI agents can move faster than review.
```

What the screen should show:

- Palari headline.
- Dashboard image.
- The blocked-write scenario text.

### 0:08-0:18 — Run The Demo

Type:

```bash
./bin/palari demo
```

Caption:

```text
One command creates a safe throwaway workspace.
```

What the screen should show:

- Demo starts.
- Queue/work context appears.
- Sofia gets a bounded task.

### 0:18-0:35 — Agent Boundary

Let the demo reach the packet/check section.

Caption:

```text
The agent receives what it may read and write.
```

What the screen should show:

- `agent start`.
- Allowed source/work context.
- Allowed write path: `docs/product/company-os.md`.

### 0:35-0:52 — The Blocked Write Moment

Pause when the demo prints the blocked change.

Caption:

```text
Palari blocks the out-of-bound file before it becomes a mess.
```

What the screen should show:

```text
*** BLOCKED: file change is outside Sofia's write boundary ***
changed: deploy/production.yml
allowed: docs/product/company-os.md
```

Hold this frame for at least four seconds.

### 0:52-1:04 — Safe Contrast

Let the demo continue to the in-bound check.

Caption:

```text
The same check passes inside the boundary.
```

What the screen should show:

- `agent check --changed docs/product/company-os.md`.
- Passing checks.

### 1:04-1:17 — Receipt

Let the demo record/finish the work.

Caption:

```text
The human gets a receipt of what happened.
```

What the screen should show:

- Receipt/evidence/finish output.
- What was read.
- What was changed.
- What was not done.

### 1:17-1:30 — Human Handoff

Let the demo end.

Caption:

```text
Approval stays human. The agent gets the next safe command.
```

What the screen should show:

- Human handoff command.
- The three plain-English sentences at the end of `palari demo`.
- The next commands to try.

## Optional Dashboard Cutaway

After the 90-second terminal demo, record a second short clip of the dashboard:

```bash
tmp="$(mktemp -d)"
./bin/palari --workspace examples/acme-company-os dashboard --out "$tmp"
python3 -m webbrowser "file://$tmp/index.html"
```

Caption:

```text
The static dashboard is the shareable view.
```

Show:

- "What needs attention now."
- Trust/receipt cards.
- The theme toggle.

## Human Finish Step

After recording:

1. Export the clip as a small GIF or MP4.
2. Place it under `docs/assets/`.
3. Replace the README screenshot with the GIF/MP4 link if GitHub renders it
   reliably.
4. Rerun `./scripts/make_demo_assets.sh` only when dashboard screenshots need
   regeneration.
