# Release And Operations

Current version:

```text
0.2.0
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

Shipping a release:

1. Bump the version in `pyproject.toml`, `src/palari_company_os/__init__.py`,
   and this file; move the `[Unreleased]` changelog entries under a new
   `## [X.Y.Z] - date` heading.
2. Run the checklist above and merge to `main`.
3. Push a `vX.Y.Z` tag. The Release workflow
   (`.github/workflows/release.yml`) then verifies the tag matches the
   package version, builds and checks the distributions, publishes to PyPI,
   and creates a GitHub Release with the changelog section as notes.

One-time human setup before the first tagged release: PyPI publishing uses
[trusted publishing](https://docs.pypi.org/trusted-publishers/), so the
`palari-company-os` project on PyPI must have a trusted publisher configured
for this repository (owner `CoyStan`, repository `palari-company-os`,
workflow `release.yml`). No API token is stored in the repository.

Workspace backup guidance:

- `workspace.json` is the source of truth
- copy the workspace directory before migrations
- do not store secrets in workspace files
