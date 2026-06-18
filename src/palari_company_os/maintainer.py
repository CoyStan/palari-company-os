from __future__ import annotations

import subprocess
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MaintainerStatus:
    repo: str
    branch: str
    head: str
    upstream: str
    divergence: str
    dirty_files: list[str]
    focused_tests_run: list[str]
    focused_tests_source: str
    pr_readiness: str
    pr_readiness_reason: str

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
    focused_tests_run, focused_tests_source = _focused_tests(repo_path)
    pr_readiness, pr_readiness_reason = _pr_readiness(branch, head, upstream, divergence, dirty_files)
    return MaintainerStatus(
        repo=str(repo_path),
        branch=branch,
        head=head,
        upstream=upstream,
        divergence=divergence,
        dirty_files=dirty_files,
        focused_tests_run=focused_tests_run,
        focused_tests_source=focused_tests_source,
        pr_readiness=pr_readiness,
        pr_readiness_reason=pr_readiness_reason,
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


def _focused_tests(repo: Path) -> tuple[list[str], str]:
    log_path = repo / ".palari-company-os" / "verification.json"
    if not log_path.exists():
        return [], "unknown"
    try:
        payload = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], f"unreadable:{log_path}"
    commands = payload.get("commands", [])
    if not isinstance(commands, list):
        return [], f"invalid:{log_path}"
    focused_tests: list[str] = []
    for item in commands:
        if isinstance(item, str):
            focused_tests.append(item)
        elif isinstance(item, dict):
            command = item.get("command")
            status_text = _status_text(item)
            if isinstance(command, str):
                focused_tests.append(f"{command}{status_text}")
    return focused_tests, str(log_path)


def _status_text(item: dict[str, Any]) -> str:
    status = item.get("status")
    if isinstance(status, str) and status:
        return f" [{status}]"
    return ""


def _pr_readiness(
    branch: str,
    head: str,
    upstream: str,
    divergence: str,
    dirty_files: list[str],
) -> tuple[str, str]:
    if not head:
        return "not-ready", "Repository has no commits yet."
    if dirty_files:
        return "not-ready", "Worktree has uncommitted changes."
    if branch == "(detached)":
        return "not-ready", "Repository is in detached HEAD state."
    if not upstream:
        return "needs-upstream", "Clean local branch has no upstream remote configured."
    if "behind " in divergence and not divergence.endswith("behind 0"):
        # Expected format is "ahead N, behind M".
        try:
            behind = int(divergence.split("behind ")[1])
        except (IndexError, ValueError):
            behind = 0
        if behind > 0:
            return "needs-sync", "Branch is behind upstream."
    return "ready", "Clean branch can be reviewed or proposed as a PR."
