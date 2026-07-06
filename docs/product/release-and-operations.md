# Release And Operations

Current version:

```text
0.1.2
```

Supported Python:

```text
Python 3.10+
```

Compatibility:

- workspace schema v1 is the current supported schema
- unversioned legacy workspaces can be migrated to v1 with `palari migrate`
- newer schema versions fail closed until the code supports them

Release checklist:

```bash
python3 -m pip install -e .
./scripts/verify.sh
./scripts/install_smoke.sh
python -m build
twine check dist/*
git status --short
```

Workspace backup guidance:

- `workspace.json` is the source of truth
- copy the workspace directory before migrations
- do not store secrets in workspace files
