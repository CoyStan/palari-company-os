# Palari Company OS Dogfood Workspace

This workspace uses Palari Company OS to track real work on this repository.
It is separate from the small ACME demo workspace and should grow as the repo
does.

The workspace is repo-local dogfooding, not the old Palari Orchestrator ticket
workflow. It records goals, Palaris, humans, work, evidence, review, human
decisions, and outcomes using the same model the CLI exposes to other users.

The completed foundation work item is a retrospective record of repo work that
had already been reviewed, accepted, committed, and pushed outside this
workspace. Its human decision record documents that provenance; it is not an
autonomous founder approval and does not give the CLI authority to accept future
work by itself.

The source and receipt on `WORK-REPO-0001` are also retrospective dogfood
records. They demonstrate the local source/receipt trust loop using repo-local
files only; they do not imply live external access, deployment, or autonomous
acceptance.

Committed paths in this workspace should be repo-relative or workspace-relative.
Avoid machine-local absolute paths so the workspace remains portable across
clones.

Useful commands:

```bash
./bin/palari --workspace workspaces/palari-company-os validate
./bin/palari --workspace workspaces/palari-company-os queue
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0001
./bin/palari --workspace workspaces/palari-company-os agent next --as PALARI-STEWARD --json
./bin/palari --workspace workspaces/palari-company-os history
```
