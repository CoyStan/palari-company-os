# Palari Company OS Dogfood Workspace (historical)

This directory is **historical, non-live dogfood evidence** for Palari Company
OS. It is separate from the small ACME demo workspace. Do not treat it as the
live self-hosting workspace for current repository work.

Live dogfood on this repository is the CI **Agent dogfood gate**
(`scripts/check_dogfood.py`), optional claim bootstrap via
`scripts/dogfood_agent.sh`, and exact-SHA / passed-evidence coverage — not
growing this workspace as if it were the active queue.

The records below remain useful for inspection of the same model the CLI
exposes to other users (goals, Palaris, humans, work, evidence, review, human
decisions, and outcomes). They are frozen operator evidence, not a mandate to
keep landing new live work here.

The completed foundation work item is a retrospective record of repo work that
had already been reviewed, accepted, committed, and pushed outside this
workspace. Its human decision record documents that provenance; it is not an
autonomous founder approval and does not give the CLI authority to accept future
work by itself.

The source and receipt on `WORK-REPO-0001` are also retrospective dogfood
records. They demonstrate the local source/receipt trust loop using repo-local
files only; they do not imply live external access, deployment, or autonomous
acceptance.

`WORK-REPO-0006` records the lightweight agent-loop polish that made
`agent next`, `agent check`, `agent finish`, and the dashboard show the same
next-step language. It is intentionally receipt-ready rather than accepted: the
receipt and evidence are present, and the next step is human review, not more
autonomous execution.

`WORK-REPO-0007` records the follow-on handoff packet work. It added
`agent handoff` as the compact bridge from an agent's final check to human
review or decision, while keeping human action commands separate from
agent-safe read commands. It is also receipt-ready rather than accepted.

`WORK-REPO-0008` records the follow-on agent command ergonomics pass. It made
review-mode packet/check commands visible in detail and dashboard, made
execute-mode check commands explicit, and made CLI text output print its mode.
It is receipt-ready rather than accepted.

The workspace keeps two workbenches in the frozen record: `Repo Foundation` for
ordinary implementation and maintenance work, and `Product Architecture` for
authority, broker, policy, and task-sizing decisions.

Committed paths in this workspace should be repo-relative or workspace-relative.
Avoid machine-local absolute paths so the workspace remains portable across
clones.

Useful inspection commands (read-only against frozen evidence):

```bash
./bin/palari --workspace workspaces/palari-company-os validate
./bin/palari --workspace workspaces/palari-company-os queue
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0001
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0006
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0007
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0008
./bin/palari --workspace workspaces/palari-company-os agent next --as PALARI-STEWARD --json
./bin/palari --workspace workspaces/palari-company-os agent finish WORK-REPO-0006 --as PALARI-STEWARD --json
./bin/palari --workspace workspaces/palari-company-os agent handoff WORK-REPO-0007 --as PALARI-STEWARD --json
./bin/palari --workspace workspaces/palari-company-os history
```
