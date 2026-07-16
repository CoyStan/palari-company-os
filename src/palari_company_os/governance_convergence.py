from __future__ import annotations

import subprocess
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from .evidence_manifest import verify_evidence
from .governance_journal import journal_file_path, workspace_digest
from .read_models import detail
from .store import load_store, validate_data
from .workspace import WorkspaceError


SCHEMA_VERSION = "palari.governance_convergence.v1"
_TERMINAL = {"completed", "closed", "done"}


@dataclass(frozen=True)
class ConvergenceObservation:
    digest: str
    status: str
    boundary: str
    message: str
    action: str = ""
    code: str = ""
    proof: dict[str, Any] = field(default_factory=dict)


def run_fixed_point(
    observe: Callable[[], ConvergenceObservation],
    apply: Callable[[str], None],
    *,
    max_steps: int = 8,
) -> dict[str, Any]:
    """Apply deterministic transitions until a true boundary or terminal state.

    The driver is deliberately generic and bounded. It detects repeated plans,
    mutations that make no logical progress, and iteration exhaustion. The
    caller supplies both the observer and the transition implementation, so
    this function grants no authority by itself.
    """

    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    current = observe()
    steps: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index in range(max_steps):
        if current.status == "blocked" or not current.action:
            return _result(current, steps)
        plan_key = (current.digest, current.action)
        if plan_key in seen:
            return _blocked_result(
                current,
                steps,
                "CONVERGENCE_CYCLE",
                "Automatic reconciliation repeated the same state and action.",
            )
        seen.add(plan_key)
        before = current
        try:
            apply(current.action)
        except WorkspaceError as exc:
            return _blocked_result(
                current,
                steps,
                "TRANSITION_REJECTED",
                f"The authoritative transition gate rejected {current.action}: {exc}",
            )
        current = observe()
        if not current.proof and before.proof:
            current = replace(current, proof=before.proof)
        step = {
            "index": index + 1,
            "action": before.action,
            "before_digest": before.digest,
            "after_digest": current.digest,
            "status": "applied",
        }
        steps.append(step)
        if current.digest == before.digest:
            return _blocked_result(
                current,
                steps,
                "CONVERGENCE_NO_PROGRESS",
                f"Automatic reconciliation action {before.action} changed no governed state.",
            )
    if current.action:
        return _blocked_result(
            current,
            steps,
            "CONVERGENCE_ITERATION_LIMIT",
            f"Automatic reconciliation exceeded its {max_steps}-step safety limit.",
        )
    return _result(current, steps)


def converge_work_item(
    workspace_path: Path | str,
    work_id: str,
    *,
    actor: str = "",
    max_steps: int = 8,
) -> dict[str, Any]:
    """Converge one work item without manufacturing authority.

    V1 has one automatic transition: current exact proof plus current qualified
    human authority may be projected through the existing completion gate. All
    other states are reported as boundaries without mutation.
    """

    path = Path(workspace_path)

    def observe() -> ConvergenceObservation:
        return _observe_work(path, work_id, actor)

    def apply(action: str) -> None:
        if action != "complete-work":
            raise WorkspaceError(f"unsupported automatic transition: {action}")
        from .authoring import complete_work

        complete_work(
            str(path),
            work_id,
            "completed",
            command="governance convergence",
            actor=actor,
        )

    return run_fixed_point(observe, apply, max_steps=max_steps)


def verify_proof_projection(
    workspace_path: Path | str,
    proof_root: Path | str,
    proof_head: str,
) -> dict[str, Any]:
    """Verify that post-proof Git changes contain governance projection only."""

    root = Path(proof_root).expanduser().resolve()
    current_head = _git_text(root, ("rev-parse", "HEAD"))
    base = {
        "proof_head": proof_head,
        "current_head": current_head,
        "governance_paths": [],
        "committed_paths": [],
        "dirty_tracked_paths": [],
        "substantive_paths": [],
    }
    if not proof_head or not current_head:
        return {
            **base,
            "ok": False,
            "code": "PROOF_HEAD_UNAVAILABLE",
            "message": "The exact proof head or current Git head is unavailable.",
        }
    git_root_text = _git_text(root, ("rev-parse", "--show-toplevel"))
    if not git_root_text:
        return {
            **base,
            "ok": False,
            "code": "PROOF_REPOSITORY_UNAVAILABLE",
            "message": "The attempt workspace is not inside a readable Git repository.",
        }
    git_root = Path(git_root_text).resolve()
    try:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", proof_head, current_head],
            cwd=git_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            **base,
            "ok": False,
            "code": "PROOF_CHANGE_OBSERVATION_FAILED",
            "message": f"Cannot inspect proof-head ancestry: {exc}",
        }
    if ancestor.returncode != 0:
        return {
            **base,
            "ok": False,
            "code": "PROOF_HEAD_NOT_ANCESTOR",
            "message": "The reviewed proof head is not an ancestor of current HEAD.",
        }
    try:
        governance_paths = _governance_projection_paths(workspace_path, git_root)
        committed = _git_paths(
            git_root,
            (
                "diff",
                "--no-ext-diff",
                "--name-only",
                "-z",
                f"{proof_head}..{current_head}",
                "--",
            ),
        )
        dirty = sorted(
            set(
                _git_paths(
                    git_root,
                    ("diff", "--no-ext-diff", "--name-only", "-z", "--"),
                )
            )
            | set(
                _git_paths(
                    git_root,
                    ("diff", "--cached", "--no-ext-diff", "--name-only", "-z", "--"),
                )
            )
        )
    except WorkspaceError as exc:
        return {
            **base,
            "ok": False,
            "code": "PROOF_CHANGE_OBSERVATION_FAILED",
            "message": str(exc),
        }
    substantive = sorted((set(committed) | set(dirty)) - set(governance_paths))
    payload = {
        **base,
        "governance_paths": governance_paths,
        "committed_paths": committed,
        "dirty_tracked_paths": dirty,
        "substantive_paths": substantive,
    }
    if substantive:
        return {
            **payload,
            "ok": False,
            "code": "SUBSTANTIVE_CHANGE_AFTER_PROOF",
            "message": (
                "Substantive repository state changed after the reviewed proof head: "
                + ", ".join(substantive)
            ),
        }
    return {
        **payload,
        "ok": True,
        "code": "",
        "message": "Only governed workspace projection changed after the proof head.",
    }


def _observe_work(path: Path, work_id: str, actor: str) -> ConvergenceObservation:
    try:
        store = load_store(path)
        workspace = validate_data(store.data_path, store.data)
    except WorkspaceError as exc:
        return ConvergenceObservation(
            digest="",
            status="blocked",
            boundary="error",
            code="WORKSPACE_INVALID",
            message=str(exc),
        )
    digest = workspace_digest(store.data)
    if digest is None:
        return ConvergenceObservation(
            digest="",
            status="blocked",
            boundary="error",
            code="WORKSPACE_DIGEST_UNAVAILABLE",
            message="The workspace projection cannot be hashed safely.",
        )
    work = workspace.work_item(work_id)
    if work is None:
        return ConvergenceObservation(
            digest=digest,
            status="blocked",
            boundary="error",
            code="WORK_NOT_FOUND",
            message=f"Work item {work_id} does not exist.",
        )
    if actor and work.palari and actor != work.palari:
        return ConvergenceObservation(
            digest=digest,
            status="blocked",
            boundary="error",
            code="ACTOR_NOT_ASSIGNED",
            message=f"Automatic reconciliation actor {actor} is not assigned to {work_id}.",
        )
    if work.status in _TERMINAL:
        return ConvergenceObservation(
            digest=digest,
            status="completed",
            boundary="terminal",
            message=f"Work item {work_id} is already terminal.",
        )
    if not work.current_attempt:
        return _waiting(digest, "agent-action", "No completed proof attempt exists yet.")
    attempt = next(
        (item for item in workspace.attempts if item.id == work.current_attempt),
        None,
    )
    if attempt is None or attempt.status not in {"complete", "completed"}:
        return _waiting(digest, "agent-action", "The current proof attempt is not complete.")
    if attempt.actor != work.palari:
        return ConvergenceObservation(
            digest=digest,
            status="blocked",
            boundary="error",
            code="ATTEMPT_ACTOR_MISMATCH",
            message="The current proof attempt belongs to a different Palari.",
        )
    proof_head = attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")
    evidence = next(
        (
            item
            for item in reversed(workspace.evidence_runs)
            if item.work_item_id == work_id
            and item.attempt_id == attempt.id
            and item.head_sha == proof_head
            and item.status == "passed"
        ),
        None,
    )
    if evidence is None:
        return _waiting(digest, "agent-action", "Current passing evidence is missing.")
    projection = verify_proof_projection(path, attempt.workspace_path or path, proof_head)
    if not projection["ok"]:
        return ConvergenceObservation(
            digest=digest,
            status="blocked",
            boundary="error",
            code="CURRENT_PROOF_INVALID",
            message=str(projection["message"]),
            proof=projection,
        )
    try:
        verification = verify_evidence(
            workspace,
            evidence.id,
            require_output_coverage=True,
        )
    except WorkspaceError as exc:
        return ConvergenceObservation(
            digest=digest,
            status="blocked",
            boundary="error",
            code="CURRENT_PROOF_INVALID",
            message=f"The recorded exact proof cannot be verified: {exc}",
            proof=projection,
        )
    if not verification["ok"]:
        errors = "; ".join(str(item) for item in verification.get("errors", [])[:3])
        return ConvergenceObservation(
            digest=digest,
            status="blocked",
            boundary="error",
            code="CURRENT_PROOF_INVALID",
            message=(
                "The recorded exact proof no longer verifies"
                + (f": {errors}" if errors else ".")
            ),
            proof=projection,
        )
    try:
        work_detail = detail(workspace, work_id)
    except WorkspaceError as exc:
        return ConvergenceObservation(
            digest=digest,
            status="blocked",
            boundary="error",
            code="LIFECYCLE_STATE_INVALID",
            message=f"The lifecycle state cannot be derived safely: {exc}",
            proof=projection,
        )
    safety = work_detail.get("safety", {})
    acceptance_state = str(safety.get("acceptance_state") or "")
    proof = {**projection, "evidence_id": evidence.id, "proof_current": True}
    if acceptance_state in {"ready-to-record", "accepted"}:
        return ConvergenceObservation(
            digest=digest,
            status="ready",
            boundary="automatic-reconciliation",
            action="complete-work",
            message="Current exact proof and qualified human authority allow completion.",
            proof=proof,
        )
    attention = str(work_detail.get("attention") or "")
    next_step = str(work_detail.get("next_step_type") or "")
    if attention in {"needs-review", "receipt-ready"} or next_step == "review-handoff":
        boundary = "independent-review"
    elif attention == "needs-human-decision" or next_step == "human-decision":
        boundary = "human-authority"
    elif "integration" in attention or next_step == "external-state":
        boundary = "external-state"
    else:
        boundary = "agent-action"
    return ConvergenceObservation(
        digest=digest,
        status="waiting",
        boundary=boundary,
        message=str(work_detail.get("next_action") or "No automatic transition is currently safe."),
        proof=proof,
    )


def _waiting(digest: str, boundary: str, message: str) -> ConvergenceObservation:
    return ConvergenceObservation(
        digest=digest,
        status="waiting",
        boundary=boundary,
        message=message,
    )


def _result(
    observation: ConvergenceObservation,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": observation.status,
        "boundary": observation.boundary,
        "code": observation.code,
        "message": observation.message,
        "would_mutate": bool(steps),
        "performed_human_authority": False,
        "steps": steps,
        "proof": observation.proof,
    }


def _blocked_result(
    observation: ConvergenceObservation,
    steps: list[dict[str, Any]],
    code: str,
    message: str,
) -> dict[str, Any]:
    return _result(
        ConvergenceObservation(
            digest=observation.digest,
            status="blocked",
            boundary="error",
            code=code,
            message=message,
            proof=observation.proof,
        ),
        steps,
    )


def _governance_projection_paths(workspace_path: Path | str, git_root: Path) -> list[str]:
    data_path = load_store(workspace_path).data_path.resolve()
    candidates = {
        data_path,
        data_path.parent / ".palari" / "history.jsonl",
        journal_file_path(data_path),
    }
    paths: list[str] = []
    for candidate in candidates:
        try:
            relative = candidate.resolve().relative_to(git_root).as_posix()
        except ValueError:
            continue
        paths.append(_safe_git_path(relative))
    return sorted(set(paths))


def _git_text(root: Path, args: tuple[str, ...]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        return ""


def _git_paths(root: Path, args: tuple[str, ...]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(f"cannot inspect proof-relative Git paths: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise WorkspaceError(
            "cannot inspect proof-relative Git paths" + (f": {message}" if message else "")
        )
    try:
        values = result.stdout.decode("utf-8").split("\0")
    except UnicodeDecodeError as exc:
        raise WorkspaceError("proof-relative Git paths are not valid UTF-8") from exc
    return sorted({_safe_git_path(value) for value in values if value})


def _safe_git_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value in {"", "."}:
        raise WorkspaceError(f"unsafe proof-relative Git path: {value!r}")
    return path.as_posix()
