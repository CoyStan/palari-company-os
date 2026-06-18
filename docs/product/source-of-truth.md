# Source Of Truth Rules

Palari Company OS keeps source artifacts simple and inspectable. Fast operator
views are derived from those artifacts.

## Current First Slice

The first implementation uses a workspace JSON file:

```text
workspace.json
```

That file is the source of truth for the example workspace. The queue and
detail views are read models derived from it.

## Design Direction

Future workspaces may split records into multiple Markdown, YAML, or JSON
files. The rule should stay the same:

- source files are inspectable
- generated views are derived
- evidence is tied to a specific head or artifact state
- review and human decision are separate records
- queue/detail commands do not secretly mutate authority state

## What Must Not Become Implicit

These actions must remain explicit:

- acceptance
- merge
- push
- deploy
- policy activation
- broker side effects
- secret or credential use
- widening a Palari's authority boundary

