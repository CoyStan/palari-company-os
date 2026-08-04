"""Graduated dogfood check for agent-authored commit ranges.

Humans can always land emergency fixes with no active claim. Agent-authored
commits (or commits on PRs labeled ``agent`` / ``cursor``) must either be
covered by a recorded advance/evidence range in the dogfood workspace, or —
for human authors only — carry an explicit ``skip-dogfood: <reason>`` trailer.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .store import workspace_file_path
from .workspace import Workspace


SKIP_TRAILER = "skip-dogfood"
AGENT_LABELS = frozenset({"agent", "cursor"})
AGENT_EMAILS = frozenset(
    {
        "cursoragent@cursor.com",
        "noreply@anthropic.com",
    }
)
AGENT_NAMES = frozenset(
    {
        "cursor agent",
        "claude",
    }
)
PROOF_RELATIVE_PATH = ".palari/dogfood/proof.json"


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    author_name: str
    author_email: str
    subject: str
    body: str

    @property
    def trailers(self) -> dict[str, str]:
        found: dict[str, str] = {}
        for line in self.body.splitlines():
            match = re.match(r"^([A-Za-z0-9][A-Za-z0-9-]*)\s*:\s*(.+)$", line.strip())
            if match:
                found[match.group(1).lower()] = match.group(2).strip()
        return found

    def skip_reason(self) -> str:
        return self.trailers.get(SKIP_TRAILER, "").strip()

    def is_agent_author(self) -> bool:
        email = self.author_email.strip().lower()
        name = self.author_name.strip().lower()
        return email in AGENT_EMAILS or name in AGENT_NAMES


def check_dogfood_range(
    repo: Path | str,
    *,
    base: str,
    head: str,
    workspace_path: Path | str = "workspace.json",
    labels: set[str] | frozenset[str] | None = None,
    git_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Evaluate whether ``base..head`` satisfies graduated dogfood policy."""
    root = Path(repo).expanduser().resolve()
    label_set = {str(item).strip().lower() for item in (labels or set()) if str(item).strip()}
    labeled = bool(label_set & AGENT_LABELS)
    commits = list_commits(root, base=base, head=head, git_runner=git_runner)
    ranges = load_coverage_ranges(root, workspace_path, pr_head=head)
    findings: list[dict[str, Any]] = []
    for commit in commits:
        agentish = commit.is_agent_author() or labeled
        if not agentish:
            findings.append(
                {
                    "sha": commit.sha,
                    "status": "allow",
                    "reason": "human commit outside agent dogfood gate",
                }
            )
            continue
        covered = covering_range(root, commit.sha, ranges, git_runner=git_runner)
        if covered is not None:
            findings.append(
                {
                    "sha": commit.sha,
                    "status": "allow",
                    "reason": "covered by recorded dogfood range",
                    "coverage": covered,
                }
            )
            continue
        skip = commit.skip_reason()
        if skip and not commit.is_agent_author():
            findings.append(
                {
                    "sha": commit.sha,
                    "status": "allow",
                    "reason": f"human skip-dogfood: {skip}",
                }
            )
            continue
        if skip and commit.is_agent_author():
            findings.append(
                {
                    "sha": commit.sha,
                    "status": "deny",
                    "reason": (
                        "skip-dogfood is reserved for human authors; "
                        "agent commits need claim-bound advance/evidence coverage"
                    ),
                }
            )
            continue
        findings.append(
            {
                "sha": commit.sha,
                "status": "deny",
                "reason": (
                    "agent/labeled commit lacks covering advance/evidence range; "
                    "run agent start → edit → advance, or (humans only) add "
                    f"{SKIP_TRAILER}: <reason>"
                ),
            }
        )
    denied = [item for item in findings if item["status"] == "deny"]
    return {
        "schema_version": "palari.dogfood_check.v1",
        "ok": not denied,
        "base": base,
        "head": head,
        "labeled": labeled,
        "labels": sorted(label_set),
        "commit_count": len(commits),
        "denials": denied,
        "findings": findings,
        "coverage_ranges": ranges,
        "message": (
            "Dogfood check passed."
            if not denied
            else f"Dogfood check failed for {len(denied)} commit(s)."
        ),
    }


def list_commits(
    repo: Path,
    *,
    base: str,
    head: str,
    git_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> list[CommitInfo]:
    runner = git_runner or subprocess.run
    separator = "\x1e"
    result = runner(
        [
            "git",
            "-C",
            str(repo),
            "log",
            f"{base}..{head}",
            f"--format=%H{separator}%an{separator}%ae{separator}%s{separator}%b%x1f",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git log failed")
    commits: list[CommitInfo] = []
    for chunk in result.stdout.split("\x1f"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        parts = chunk.split(separator, 4)
        if len(parts) != 5:
            continue
        sha, name, email, subject, body = parts
        commits.append(
            CommitInfo(
                sha=sha.strip(),
                author_name=name.strip(),
                author_email=email.strip(),
                subject=subject.strip(),
                body=body.strip(),
            )
        )
    return commits


def load_coverage_ranges(
    repo: Path,
    workspace_path: Path | str,
    *,
    pr_head: str = "",
) -> list[dict[str, str]]:
    ranges: list[dict[str, str]] = []
    proof_path = repo / PROOF_RELATIVE_PATH
    if proof_path.is_file():
        try:
            payload = json.loads(proof_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict):
            for item in payload.get("ranges") or []:
                if not isinstance(item, dict):
                    continue
                base = str(item.get("base") or "").strip()
                head = str(item.get("head") or "").strip()
                if head == "@pr-head":
                    head = pr_head.strip()
                if base and head:
                    ranges.append(
                        {
                            "base": base,
                            "head": head,
                            "source": "proof-file",
                            "work_id": str(item.get("work_id") or ""),
                        }
                    )
    data_path = workspace_file_path(
        workspace_path if Path(workspace_path).is_absolute() else repo / str(workspace_path)
    )
    if not data_path.is_file():
        return ranges
    try:
        workspace = Workspace.load(data_path)
    except Exception:  # noqa: BLE001 - dogfood check fails open to empty coverage
        return ranges
    attempts = {item.id: item for item in workspace.attempts}
    for evidence in workspace.evidence_runs:
        if str(evidence.status).lower() not in {"passed", "pass", "ok"}:
            continue
        head = str(evidence.head_sha or "").strip()
        base = str(evidence.base_ref or "").strip()
        if not base:
            attempt = attempts.get(evidence.attempt_id)
            base = str(getattr(attempt, "base_sha", "") or "").strip()
        if base and head:
            ranges.append(
                {
                    "base": base,
                    "head": head,
                    "source": f"evidence:{evidence.id}",
                    "work_id": str(evidence.work_item_id or ""),
                }
            )
    for attempt in workspace.attempts:
        base = str(attempt.base_sha or "").strip()
        head = str(attempt.head_sha or "").strip()
        if base and head:
            ranges.append(
                {
                    "base": base,
                    "head": head,
                    "source": f"attempt:{attempt.id}",
                    "work_id": str(attempt.work_item_id or ""),
                }
            )
    return ranges


def covering_range(
    repo: Path,
    commit: str,
    ranges: list[dict[str, str]],
    *,
    git_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, str] | None:
    for item in ranges:
        if is_ancestor(repo, item["base"], commit, git_runner=git_runner) and is_ancestor(
            repo,
            commit,
            item["head"],
            git_runner=git_runner,
        ):
            return item
    return None


def is_ancestor(
    repo: Path,
    ancestor: str,
    descendant: str,
    *,
    git_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> bool:
    if not ancestor or not descendant:
        return False
    if ancestor == descendant:
        return True
    runner = git_runner or subprocess.run
    result = runner(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
