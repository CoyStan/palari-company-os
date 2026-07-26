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

- workspace schema v2 is the current supported schema
- unversioned, v0, and v1 workspaces fail closed; no runtime migration is supported
- newer schema versions fail closed until the code supports them

Release checklist:

```bash
python3 -m pip install -e ".[dev]"
./scripts/verify.sh
python -m build
twine check dist/*
git status --short
```

The complete verification command already builds and installs one isolated
candidate wheel. The later distribution build creates the files intended
for an explicitly authorized release.

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

- For ordinary storage, the exact selected workspace file is current state and
  sibling `.palari/governance-journal.v2.jsonl` is replayable change history.
  Back up the complete workspace directory, including both, together.
- For Maintainer Profile v1, one coherent backup includes
  `.palari-company-os.json`, the complete `.palari-company-os/` tree, the
  matching `palari-maintainer-repository.json` beneath the Git common
  directory, the applicable `.git/info/exclude` rules, and the source
  repository's Git history. The binding and repository identifier are a pair;
  do not regenerate or copy one without the other.
- Before either backup, stop Palari writers, ensure no execution assignment is
  active, and run the exact selected workspace's `history --json` check. A
  pending, corrupt, truncated, divergent, or continuity-broken journal is a
  blocker, not a backup point.
- Restore a maintainer backup only into the same bound repository, or move the
  complete repository and its Git common directory, hidden workspace, and
  control state together. Copying hidden state into another clone fails closed
  on repository identity. Maintainer Profile v1 has no import, automatic
  migration, or rebind command.
- `history --restore` appends a human-attributed local state restoration; it is
  not a filesystem, Git, provider, or external-effect rollback. A later
  external effect remains a blocker.
- Reverting or downgrading the Palari source must leave ignored maintainer state
  untouched. An older version that does not understand the profile should be
  pointed at an explicitly named ordinary workspace, not allowed to reinterpret
  or delete the hidden state.
- Do not store secrets in workspace or binding files.
