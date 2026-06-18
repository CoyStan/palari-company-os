from __future__ import annotations

import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class MaintainerStatus:
    repo: str
    branch: str
    head: str
    upstream: str
    divergence: str
    dirty_files: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def status(repo: Path | str) -> MaintainerStatus:
    repo_path = Path(repo).resolve()
    branch = _git(repo_path, "branch", "--show-current") or "(detached)"
    head = _git(repo_path, "rev-parse", "--short", "HEAD")
    upstream = _git(repo_path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    divergence = "no upstream"
    if upstream:
        counts = _git(repo_path, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
        if counts:
            behind, ahead = counts.split()
            divergence = f"ahead {ahead}, behind {behind}"
    dirty_files = _git(repo_path, "status", "--short").splitlines()
    return MaintainerStatus(
        repo=str(repo_path),
        branch=branch,
        head=head,
        upstream=upstream,
        divergence=divergence,
        dirty_files=dirty_files,
    )


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.stdout.strip()

