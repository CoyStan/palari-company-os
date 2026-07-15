"""Provider-neutral isolated Git worktrees for concurrent agent sessions."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from shlex import quote
from typing import Any

from .agent_runtime import start_agent
from .read_models import detail
from .store import workspace_file_path
from .workspace import Workspace, WorkspaceError


def start_isolated_agent(
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    *,
    lease_minutes: int = 30,
    base_ref: str = "HEAD",
) -> dict[str, Any]:
    """Create or resume one deterministic local worktree, then claim there."""

    if not base_ref or base_ref.startswith("-") or any(
        character in base_ref for character in ("\x00", "\n", "\r")
    ):
        raise WorkspaceError("--base-ref must be a non-option Git revision")
    source_data_path = workspace_file_path(workspace_path)
    source_workspace = Workspace.load(source_data_path)
    if source_workspace.work_item(work_id) is None:
        raise WorkspaceError(f"work item not found: {work_id}")

    source_root = _required_git_output(source_data_path.parent, ["rev-parse", "--show-toplevel"])
    root_path = Path(source_root).resolve()
    try:
        workspace_relative = source_data_path.resolve().relative_to(root_path)
    except ValueError as exc:
        raise WorkspaceError("workspace must be inside the Git repository for --isolate") from exc

    branch = isolation_branch(work_id)
    current_branch = _git_output(root_path, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if current_branch == branch:
        return _start_in_worktree(
            root_path,
            workspace_relative,
            work_id,
            palari_id,
            mode,
            lease_minutes,
            branch,
            base_ref,
            created=False,
        )

    base_sha = _required_git_output(
        root_path,
        ["rev-parse", "--verify", f"{base_ref}^{{commit}}"],
    )
    _require_committed_workspace(
        root_path,
        source_data_path,
        workspace_relative,
        base_sha,
        work_id,
    )
    worktree_root = isolation_worktree_path(root_path, work_id)
    created = False
    if worktree_root.exists():
        _require_matching_worktree(worktree_root, branch)
    else:
        if _git_output(root_path, ["show-ref", "--verify", f"refs/heads/{branch}"]):
            raise WorkspaceError(
                f"isolated branch {branch} already exists without its expected worktree; "
                "inspect it before retrying"
            )
        worktree_root.parent.mkdir(parents=True, exist_ok=True)
        result = _run_git(
            root_path,
            ["worktree", "add", "-b", branch, str(worktree_root), base_sha],
        )
        if result.returncode != 0:
            raise WorkspaceError(
                f"cannot create isolated worktree: "
                f"{result.stderr.strip() or 'git worktree add failed'}"
            )
        created = True

    return _start_in_worktree(
        worktree_root,
        workspace_relative,
        work_id,
        palari_id,
        mode,
        lease_minutes,
        branch,
        base_sha,
        created=created,
    )


def isolation_branch(work_id: str) -> str:
    digest = hashlib.sha256(work_id.encode("utf-8")).hexdigest()[:16]
    return f"palari/work-{digest}"


def isolation_worktree_path(repo_root: Path, work_id: str) -> Path:
    digest = hashlib.sha256(work_id.encode("utf-8")).hexdigest()[:16]
    return repo_root.parent / ".palari-worktrees" / repo_root.name / digest


def git_integration_readiness(
    workspace_path: Path | str,
    work_id: str,
    *,
    target_ref: str = "main",
) -> dict[str, Any]:
    """Assess one exact candidate against a target without mutating either checkout."""

    if not target_ref or target_ref.startswith("-") or any(
        character in target_ref for character in ("\x00", "\n", "\r")
    ):
        raise WorkspaceError("--target-ref must be a non-option Git revision")
    workspace = Workspace.load(workspace_path)
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work item not found: {work_id}")
    root = Path(
        _required_git_output(workspace.path, ["rev-parse", "--show-toplevel"])
    ).resolve()
    target_sha = _required_git_output(
        root,
        ["rev-parse", "--verify", f"{target_ref}^{{commit}}"],
    )
    attempt = next(
        (item for item in workspace.attempts if item.id == work.current_attempt),
        None,
    )
    candidate_sha = ""
    if attempt is not None:
        candidate_sha = attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")
    payload: dict[str, Any] = {
        "schema_version": "palari.git_integration_readiness.v1",
        "work_item": work_id,
        "target": {"ref": target_ref, "sha": target_sha},
        "candidate": {
            "attempt_id": attempt.id if attempt else "",
            "sha": candidate_sha,
            "attempt_status": attempt.status if attempt else "missing",
        },
        "ready": False,
        "status": "blocked",
        "relationship": "unknown",
        "merge_simulation": {"status": "not-run", "tree_sha": "", "conflicts": []},
        "governance": {},
        "working_tree_clean": not bool(
            _git_output(root, ["status", "--porcelain", "--untracked-files=no"])
        ),
        "blockers": [],
        "warnings": [],
        "limitations": [
            "This command does not merge, push, review, accept, or deploy work.",
            "A clean simulation does not preserve proof after governed bytes change.",
            "Declared local actor identity is not cryptographically authenticated.",
        ],
    }
    read_detail = detail(workspace, work_id)
    safety = read_detail["safety"]
    governance_ready = work.status in {"completed", "closed", "done"} or (
        safety["acceptance_state"] == "accepted"
    )
    attempt_complete = attempt is not None and attempt.status in {"complete", "completed"}
    payload["governance"] = {
        "work_status": work.status,
        "attention": read_detail["attention"],
        "acceptance_state": safety["acceptance_state"],
        "evidence_state": safety["evidence_state"],
        "review_state": safety["review_state"],
        "proof_ready": governance_ready and attempt_complete,
    }
    if not candidate_sha:
        payload["blockers"].append(
            _integration_blocker(
                "CANDIDATE_COMMIT_MISSING",
                "The current attempt has no exact candidate commit.",
                "Commit the bounded attempt and reconcile its exact proof before integration.",
            )
        )
        return payload
    candidate_sha = _git_output(
        root,
        ["rev-parse", "--verify", f"{candidate_sha}^{{commit}}"],
    )
    if not candidate_sha:
        payload["blockers"].append(
            _integration_blocker(
                "CANDIDATE_COMMIT_UNAVAILABLE",
                "The recorded candidate commit is not available in this repository.",
                "Fetch or restore the exact local commit, then verify again.",
            )
        )
        return payload
    payload["candidate"]["sha"] = candidate_sha

    if candidate_sha == target_sha or _is_ancestor(root, candidate_sha, target_sha):
        payload["relationship"] = "already-integrated"
        payload["merge_simulation"]["status"] = "not-needed"
    elif _is_ancestor(root, target_sha, candidate_sha):
        payload["relationship"] = "candidate-contains-target"
        payload["merge_simulation"]["status"] = "fast-forward"
    else:
        payload["relationship"] = "diverged"
        payload["merge_simulation"] = _simulate_merge(root, target_sha, candidate_sha)

    if not governance_ready:
        payload["blockers"].append(
            _integration_blocker(
                "GOVERNANCE_PROOF_NOT_READY",
                "The work has not reached accepted or valid terminal governance state.",
                "Complete evidence, independent review, and human authority where required.",
            )
        )
    if not attempt_complete:
        payload["blockers"].append(
            _integration_blocker(
                "ATTEMPT_NOT_TERMINAL",
                "The exact candidate attempt is not complete.",
                "Finish the bounded attempt and reconcile its receipt and evidence.",
            )
        )
    simulation_status = payload["merge_simulation"]["status"]
    if simulation_status == "conflict":
        payload["blockers"].append(
            _integration_blocker(
                "TARGET_CONFLICT",
                "The candidate conflicts with the current target projection.",
                "Repair the conflict in the isolated branch and rerun attributable verification.",
            )
        )
    elif simulation_status == "unavailable":
        payload["blockers"].append(
            _integration_blocker(
                "MERGE_SIMULATION_UNAVAILABLE",
                "Git could not construct an isolated merge projection.",
                "Inspect Git compatibility and rerun the check without changing authority gates.",
            )
        )
    elif payload["relationship"] == "diverged":
        payload["blockers"].append(
            _integration_blocker(
                "REVALIDATION_REQUIRED",
                "A clean merge projection would differ from the reviewed candidate commit.",
                "Update the candidate onto the target, then refresh exact proof and review.",
            )
        )
    if not payload["working_tree_clean"]:
        payload["warnings"].append(
            {
                "code": "TRACKED_WORKTREE_DIRTY",
                "message": "Tracked local changes are excluded from this commit-only assessment.",
            }
        )

    if payload["blockers"]:
        payload["status"] = "blocked"
    elif payload["relationship"] == "already-integrated":
        payload["status"] = "integrated"
        payload["ready"] = True
    else:
        payload["status"] = "ready"
        payload["ready"] = True
    return payload


def _start_in_worktree(
    worktree_root: Path,
    workspace_relative: Path,
    work_id: str,
    palari_id: str,
    mode: str,
    lease_minutes: int,
    branch: str,
    base_ref: str,
    *,
    created: bool,
) -> dict[str, Any]:
    isolated_data_path = worktree_root / workspace_relative
    workspace = Workspace.load(isolated_data_path)
    if workspace.work_item(work_id) is None:
        raise WorkspaceError(
            f"isolated worktree does not contain {work_id}; commit the work definition first"
        )
    payload = start_agent(
        workspace,
        isolated_data_path,
        work_id,
        palari_id,
        mode,
        lease_minutes=lease_minutes,
    )
    workspace_argument = workspace_relative.as_posix()
    command = (
        f"cd {quote(str(worktree_root))} && ./bin/palari --workspace "
        f"{quote(workspace_argument)} agent loop {quote(work_id)} --as "
        f"{quote(palari_id)} --mode {quote(mode)} --json"
    )
    payload["isolation"] = {
        "status": "created" if created else "resumed",
        "worktree_path": str(worktree_root),
        "workspace_path": str(isolated_data_path),
        "branch": branch,
        "base_ref": base_ref,
        "resume_command": command,
        "authority": {
            "merge": False,
            "push": False,
            "review": False,
            "acceptance": False,
            "external_writes": False,
        },
    }
    payload["one_sentence_instruction"] = (
        f"Continue {work_id} only in isolated worktree {worktree_root}; "
        "the claim grants no review, acceptance, merge, push, or deployment authority."
    )
    start = payload.get("start")
    if isinstance(start, dict):
        start["worktree_path"] = str(worktree_root)
        start["workspace_path"] = str(isolated_data_path)
        start["branch"] = branch
        start["resume_command"] = command
    return payload


def _require_committed_workspace(
    repo_root: Path,
    source_data_path: Path,
    workspace_relative: Path,
    base_sha: str,
    work_id: str,
) -> None:
    result = _run_git(repo_root, ["show", f"{base_sha}:{workspace_relative.as_posix()}"])
    if result.returncode != 0:
        raise WorkspaceError(
            "workspace definition is not committed at the selected base ref; commit it first"
        )
    try:
        current = source_data_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkspaceError(f"cannot read workspace definition: {exc}") from exc
    if current != result.stdout:
        raise WorkspaceError(
            "workspace definition has uncommitted changes; commit the work items before "
            "starting isolated sessions"
        )
    try:
        committed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WorkspaceError("committed workspace definition is invalid JSON") from exc
    work_items = committed.get("work_items", []) if isinstance(committed, dict) else []
    if not any(isinstance(item, dict) and item.get("id") == work_id for item in work_items):
        raise WorkspaceError(f"{work_id} is not committed at the selected base ref")


def _require_matching_worktree(worktree_root: Path, branch: str) -> None:
    if worktree_root.is_symlink() or not worktree_root.is_dir():
        raise WorkspaceError(f"isolated worktree path is not a real directory: {worktree_root}")
    actual_root = _required_git_output(worktree_root, ["rev-parse", "--show-toplevel"])
    if Path(actual_root).resolve() != worktree_root.resolve():
        raise WorkspaceError(f"isolated worktree path belongs to another repository: {worktree_root}")
    actual_branch = _required_git_output(
        worktree_root,
        ["symbolic-ref", "--quiet", "--short", "HEAD"],
    )
    if actual_branch != branch:
        raise WorkspaceError(
            f"isolated worktree uses branch {actual_branch}, expected {branch}"
        )


def _simulate_merge(root: Path, target_sha: str, candidate_sha: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="palari-merge-readiness-") as directory:
        clone = _run_git(
            root,
            ["clone", "--quiet", "--shared", "--no-checkout", str(root), directory],
        )
        if clone.returncode != 0:
            return {"status": "unavailable", "tree_sha": "", "conflicts": []}
        result = _run_git(
            Path(directory),
            ["merge-tree", "--write-tree", target_sha, candidate_sha],
        )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        conflicts = [line for line in lines if line.startswith("CONFLICT ")]
        if result.returncode == 0 and lines:
            return {"status": "clean", "tree_sha": lines[0], "conflicts": []}
        if conflicts or result.returncode == 1:
            return {"status": "conflict", "tree_sha": "", "conflicts": conflicts}
        return {"status": "unavailable", "tree_sha": "", "conflicts": []}


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return _run_git(
        root,
        ["merge-base", "--is-ancestor", ancestor, descendant],
    ).returncode == 0


def _integration_blocker(code: str, message: str, next_action: str) -> dict[str, str]:
    return {"code": code, "message": message, "next_safe_action": next_action}


def _required_git_output(directory: Path, arguments: list[str]) -> str:
    value = _git_output(directory, arguments)
    if not value:
        raise WorkspaceError(
            f"Git command returned no usable result: git {' '.join(arguments)}"
        )
    return value


def _git_output(directory: Path, arguments: list[str]) -> str:
    result = _run_git(directory, arguments)
    return result.stdout.strip() if result.returncode == 0 else ""


def _run_git(directory: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(directory), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkspaceError(f"cannot run Git command: {exc}") from exc
