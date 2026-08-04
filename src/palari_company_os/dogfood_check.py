"""Graduated dogfood check for agent-authored commit ranges.

Humans can always land emergency fixes with no active claim. Agent-authored
commits (or commits on PRs labeled ``agent`` / ``cursor``) must either be
covered by a recorded advance/evidence range in the dogfood workspace, or —
for human authors only — carry an explicit ``skip-dogfood: <reason>`` trailer.

Coverage is intentionally strict:

- workspace coverage comes only from **passed** evidence runs (bare attempts
  do not count);
- ``.palari/dogfood/proof.json`` ranges must use immutable exact Git object
  SHAs — floating tokens such as ``@pr-head`` are rejected;
- commits that only update the proof file itself are allowed so an exact tip
  SHA can be attested after the bounded work lands.
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
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)


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
    loaded = load_coverage_ranges(root, workspace_path)
    ranges = loaded["ranges"]
    proof_errors = loaded["proof_errors"]
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
        if is_proof_only_commit(root, commit.sha, git_runner=git_runner):
            findings.append(
                {
                    "sha": commit.sha,
                    "status": "allow",
                    "reason": "proof attestation commit (only updates dogfood proof file)",
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
    if proof_errors:
        denied = [
            {
                "sha": "",
                "status": "deny",
                "reason": error["reason"],
                "proof_entry": error,
            }
            for error in proof_errors
        ] + denied
    ok = not denied
    return {
        "schema_version": "palari.dogfood_check.v1",
        "ok": ok,
        "base": base,
        "head": head,
        "labeled": labeled,
        "labels": sorted(label_set),
        "commit_count": len(commits),
        "denials": denied,
        "findings": findings,
        "coverage_ranges": ranges,
        "proof_errors": proof_errors,
        "message": (
            "Dogfood check passed."
            if ok
            else f"Dogfood check failed for {len(denied)} finding(s)."
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
) -> dict[str, Any]:
    """Load exact coverage ranges from proof file and passed evidence only."""
    ranges: list[dict[str, str]] = []
    proof_errors: list[dict[str, str]] = []
    proof_path = repo / PROOF_RELATIVE_PATH
    if proof_path.is_file():
        try:
            payload = json.loads(proof_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            payload = {}
            proof_errors.append(
                {
                    "base": "",
                    "head": "",
                    "reason": (
                        f"{PROOF_RELATIVE_PATH} is not valid JSON; "
                        "fix it or remove invalid ranges"
                    ),
                }
            )
        if isinstance(payload, dict):
            for item in payload.get("ranges") or []:
                if not isinstance(item, dict):
                    continue
                raw_base = str(item.get("base") or "").strip()
                raw_head = str(item.get("head") or "").strip()
                base = normalize_exact_sha(raw_base)
                head = normalize_exact_sha(raw_head)
                if base is None or head is None:
                    proof_errors.append(
                        {
                            "base": raw_base,
                            "head": raw_head,
                            "work_id": str(item.get("work_id") or ""),
                            "reason": (
                                "dogfood proof ranges must use immutable exact "
                                "Git SHAs (7–40 hex); floating tokens such as "
                                "@pr-head are rejected"
                            ),
                        }
                    )
                    continue
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
        return {"ranges": ranges, "proof_errors": proof_errors}
    try:
        workspace = Workspace.load(data_path)
    except Exception:  # noqa: BLE001 - dogfood check fails open to empty coverage
        return {"ranges": ranges, "proof_errors": proof_errors}
    attempts = {item.id: item for item in workspace.attempts}
    for evidence in workspace.evidence_runs:
        if str(evidence.status).lower() not in {"passed", "pass", "ok"}:
            continue
        head = normalize_exact_sha(str(evidence.head_sha or "").strip())
        base = normalize_exact_sha(str(evidence.base_ref or "").strip())
        if base is None:
            attempt = attempts.get(evidence.attempt_id)
            base = normalize_exact_sha(str(getattr(attempt, "base_sha", "") or "").strip())
        if base and head:
            ranges.append(
                {
                    "base": base,
                    "head": head,
                    "source": f"evidence:{evidence.id}",
                    "work_id": str(evidence.work_item_id or ""),
                }
            )
    # Bare attempts without passed evidence intentionally do not grant coverage.
    return {"ranges": ranges, "proof_errors": proof_errors}


def normalize_exact_sha(value: str) -> str | None:
    """Return a hex Git object name, or None for floating/non-SHA tokens."""
    text = str(value or "").strip()
    if not text or text.startswith("@"):
        return None
    if not _SHA_RE.fullmatch(text):
        return None
    return text.lower()


def is_proof_only_commit(
    repo: Path,
    commit: str,
    *,
    git_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> bool:
    """True when the commit only updates the dogfood proof attestation file."""
    runner = git_runner or subprocess.run
    result = runner(
        [
            "git",
            "-C",
            str(repo),
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return bool(paths) and set(paths) == {PROOF_RELATIVE_PATH}


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
