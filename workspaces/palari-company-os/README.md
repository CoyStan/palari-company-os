# Palari Company OS Dogfood Workspace

This workspace uses Palari Company OS to track real work on this repository.
It is separate from the small ACME demo workspace and should grow as the repo
does.

The workspace is repo-local dogfooding, not the old Palari Orchestrator ticket
workflow. It records goals, Palaris, humans, work, evidence, review, human
decisions, and outcomes using the same model the CLI exposes to other users.

Useful commands:

```bash
./bin/palari --workspace workspaces/palari-company-os validate
./bin/palari --workspace workspaces/palari-company-os queue
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0001
./bin/palari --workspace workspaces/palari-company-os history
```
