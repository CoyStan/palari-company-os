from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .agent_checks import build_agent_check
from .agent_file_changes import git_repo_root, inspect_file_changes
from .agent_finish import build_agent_finish
from .agent_packets import build_agent_brief
from .agent_runtime import claim_is_active, read_claim, release_agent, start_agent
from .authoring import closeout_attempt, complete_work, create_record, update_record
from .read_models import detail
from .workspace import Workspace, WorkspaceError


def agent_done(
    workspace: Workspace,
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    *,
    changed: list[str] | None = None,
    head_sha: str = "",
    model_or_worker: str = "",
) -> dict[str, Any]:
    work_detail = detail(workspace, work_id)
    work = work_detail["work_item"]
    risk = work.get("risk", "")
    intensity = work.get("intensity", "")
    approvals = work.get("required_approval_count", 0)

    if risk not in {"R1"} or intensity not in {"light"} or approvals != 0:
        return {
            "schema_version": "palari.agent_done.v1",
            "status": "rejected",
            "work_item": work_id,
            "workspace": workspace.name,
            "message": (
                f"agent done is only for R1/light/0-approval work items. "
                f"This work item is {risk}/{intensity}/{approvals}-approvals. "
                f"Use the full proof lifecycle: attempt record, receipt record, "
                f"agent check, agent finish, attempt closeout, lifecycle complete."
            ),
            "can_done": False,
        }

    attempt_id = f"ATTEMPT-DONE-{work_id}"
    receipt_id = f"RECEIPT-DONE-{work_id}"
    prior_attempt = next((item for item in workspace.attempts if item.id == attempt_id), None)
    if work.get("status") in {"completed", "closed", "done"}:
        if prior_attempt is not None:
            claim = read_claim(workspace_path, work_id)
            if claim and claim.get("claimed_by") == palari_id:
                release_agent(workspace, workspace_path, work_id, palari_id)
            return {
                "schema_version": "palari.agent_done.v1",
                "status": "done",
                "work_item": work_id,
                "workspace": workspace.name,
                "message": f"Work item {work_id} was already completed by agent done.",
                "can_done": True,
                "steps": [{"step": "resume", "status": "already-completed"}],
                "attempt_id": attempt_id,
                "receipt_id": receipt_id,
            }
        return {
            "schema_version": "palari.agent_done.v1",
            "status": "already-completed",
            "work_item": work_id,
            "workspace": workspace.name,
            "message": f"Work item {work_id} is already {work['status']}.",
            "can_done": False,
        }

    preflight = _preflight(workspace, workspace_path, work_id, palari_id, changed)
    if not preflight["ok"]:
        return {
            "schema_version": "palari.agent_done.v1",
            "status": "blocked",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_done": False,
            "message": preflight["message"],
            "preflight": preflight,
        }
    if head_sha and head_sha != preflight["head_sha"]:
        return {
            "schema_version": "palari.agent_done.v1",
            "status": "blocked",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_done": False,
            "message": "declared head does not match the verified Git HEAD",
            "preflight": preflight,
        }
    changed_paths = preflight["changed_files"]
    head_sha = preflight["head_sha"]
    resume_error = _resume_error(workspace, work_id, palari_id, attempt_id, receipt_id)
    if resume_error:
        return {
            "schema_version": "palari.agent_done.v1",
            "status": "blocked",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_done": False,
            "message": resume_error,
        }

    steps: list[dict[str, str]] = []

    attempt_record = {
        "id": attempt_id,
        "work_item_id": work_id,
        "actor": palari_id,
        "status": "active",
        "base_sha": preflight["base_sha"],
    }
    if model_or_worker:
        attempt_record["model_or_worker"] = model_or_worker
    if prior_attempt is None:
        create_record(
            workspace_path,
            "attempt",
            attempt_record,
            command="agent done",
            actor=palari_id,
        )
        steps.append({"step": "attempt-record", "id": attempt_id, "status": "created"})
    else:
        steps.append({"step": "attempt-record", "id": attempt_id, "status": "resumed"})

    receipt_record = {
        "id": receipt_id,
        "work_item_id": work_id,
        "attempt_id": attempt_id,
        "actor": palari_id,
        "actions_taken": ["agent done shortcut"],
        "outputs_created": changed_paths,
        "not_done": ["External writes were not authorized by this work item."],
        "undo_refs": changed_paths,
    }
    prior_receipt = next((item for item in workspace.receipts if item.id == receipt_id), None)
    if prior_receipt is None:
        create_record(
            workspace_path,
            "receipt",
            receipt_record,
            command="agent done",
            actor=palari_id,
        )
        steps.append({"step": "receipt-record", "id": receipt_id, "status": "created"})
    else:
        steps.append({"step": "receipt-record", "id": receipt_id, "status": "resumed"})

    if work.get("current_attempt") != attempt_id:
        update_record(
            workspace_path,
            "work",
            work_id,
            {"current_attempt": attempt_id},
            command="agent done",
            actor=palari_id,
        )
        steps.append({"step": "work-update", "id": work_id, "status": "updated"})
    else:
        steps.append({"step": "work-update", "id": work_id, "status": "resumed"})

    claim = read_claim(workspace_path, work_id)
    if claim:
        workspace = Workspace.load(workspace_path)
        release_agent(workspace, workspace_path, work_id, palari_id)
        steps.append({"step": "claim-release", "status": "released"})

    workspace = Workspace.load(workspace_path)
    start_result = start_agent(workspace, workspace_path, work_id, palari_id, "execute")
    if start_result.get("start", {}).get("status") != "claimed":
        return {
            "schema_version": "palari.agent_done.v1",
            "status": "blocked",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_done": False,
            "steps": steps,
            "message": "Could not re-claim after recording proof. Inspect the start result.",
            "start_result": start_result,
        }
    steps.append({"step": "claim-start", "status": "claimed"})

    workspace = Workspace.load(workspace_path)
    check = build_agent_check(
        workspace,
        work_id,
        palari_id,
        "execute",
        changed_paths=changed_paths,
        cwd=Path(preflight["git_root"]),
    )
    if not check.get("ok", False):
        return {
            "schema_version": "palari.agent_done.v1",
            "status": "check-failed",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_done": False,
            "steps": steps,
            "checks": check.get("checks", []),
            "message": "agent check failed. Fix the issue and re-run agent done.",
        }
    steps.append({"step": "agent-check", "status": "pass"})

    finish = build_agent_finish(workspace, work_id, palari_id, "execute")
    if not finish.get("can_finish", False):
        return {
            "schema_version": "palari.agent_done.v1",
            "status": "finish-blocked",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_done": False,
            "steps": steps,
            "blockers": finish.get("blockers", []),
            "message": "agent finish reports blockers. Resolve them and re-run agent done.",
        }
    steps.append({"step": "agent-finish", "status": "can-finish"})

    workspace = Workspace.load(workspace_path)
    current_attempt = next(item for item in workspace.attempts if item.id == attempt_id)
    if current_attempt.status not in {"complete", "completed"}:
        closeout_attempt(
            workspace_path,
            attempt_id,
            status="completed",
            head_sha=head_sha,
            cleanliness="clean",
            changed_files=changed_paths,
            output_targets=work.get("output_targets", []),
            allow_missing_evidence=True,
            command="agent done",
            actor=palari_id,
        )
        steps.append({"step": "attempt-closeout", "id": attempt_id, "status": "closed-out"})
    else:
        steps.append({"step": "attempt-closeout", "id": attempt_id, "status": "resumed"})

    complete_work(
        workspace_path,
        work_id,
        "completed",
        command="agent done",
        actor=palari_id,
    )
    steps.append({"step": "lifecycle-complete", "id": work_id, "status": "completed"})

    workspace = Workspace.load(workspace_path)
    release_agent(workspace, workspace_path, work_id, palari_id)
    steps.append({"step": "claim-release", "status": "released"})

    return {
        "schema_version": "palari.agent_done.v1",
        "status": "done",
        "work_item": work_id,
        "workspace": workspace.name,
        "can_done": True,
        "steps": steps,
        "attempt_id": attempt_id,
        "receipt_id": receipt_id,
        "message": f"Work item {work_id} completed via agent done shortcut.",
    }


def _preflight(
    workspace: Workspace,
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    declared_changed: list[str] | None,
) -> dict[str, Any]:
    claim = read_claim(workspace_path, work_id)
    if not claim:
        return _blocked_preflight("agent done requires an active execute claim")
    if claim.get("claimed_by") != palari_id:
        return _blocked_preflight(
            f"work is claimed by {claim.get('claimed_by', 'unknown')}, not {palari_id}"
        )
    if claim.get("mode") != "execute" or not claim_is_active(claim):
        return _blocked_preflight("agent done requires a current execute-mode claim")

    root = git_repo_root(workspace.path) or git_repo_root(Path.cwd())
    if root is None:
        return _blocked_preflight("agent done requires a Git repository for exact change proof")
    status_inspection = inspect_file_changes(
        {"allowed_paths": {"write": []}},
        git_diff=True,
        cwd=root,
        git_baseline=claim.get("git_baseline"),
    )
    if status_inspection is None or not status_inspection.get("observation_complete"):
        return _blocked_preflight("Git status failed; agent done cannot prove repository state")
    dirty = [
        path
        for path in status_inspection.get("changed_files", [])
        if not _is_agent_runtime_path(path, root, workspace.path)
    ]
    if dirty:
        return _blocked_preflight(
            "agent done requires a clean committed worktree; commit the bounded output first"
        )

    head_sha = _git_value(root, ["rev-parse", "HEAD"])
    if not head_sha:
        return _blocked_preflight("Git HEAD is unavailable; agent done cannot bind the attempt")
    baseline = claim.get("git_baseline")
    if not isinstance(baseline, dict):
        return _blocked_preflight("claim has no Git baseline; restart the claim")
    base_sha = str(baseline.get("head_sha") or "")
    if not base_sha:
        return _blocked_preflight("claim baseline has no exact Git HEAD; restart the claim")
    if baseline.get("git_root") != str(root):
        return _blocked_preflight("claim baseline belongs to a different Git repository")
    if not _git_ok(root, ["merge-base", "--is-ancestor", base_sha, head_sha]):
        return _blocked_preflight(
            "current Git HEAD does not descend from the claim-start commit"
        )
    committed = _git_lines(
        root,
        ["log", "--format=", "--name-only", "-z", "--no-renames", f"{base_sha}..{head_sha}"],
    )
    if committed is None:
        return _blocked_preflight("Git commit inspection failed; agent done cannot prove changes")
    changed_files = sorted(path for path in committed if path)
    declared = sorted(dict.fromkeys(declared_changed or []))
    if declared and declared != changed_files:
        return _blocked_preflight(
            "declared --changed paths do not exactly match the committed HEAD artifact"
        )
    if not changed_files:
        return _blocked_preflight("no committed changes exist since the claim started")

    packet = build_agent_brief(workspace, work_id, palari_id, "execute")
    inspection = inspect_file_changes(packet, changed_paths=changed_files, cwd=root)
    if inspection is None:
        return _blocked_preflight("file change inspection was unavailable")
    outside = inspection.get("outside_write_boundary", [])
    if outside:
        return _blocked_preflight(
            "claim commit range contains paths outside the write boundary: "
            + ", ".join(outside)
        )
    missing = inspection.get("missing_required_outputs", [])
    if missing:
        return _blocked_preflight("required outputs are missing: " + ", ".join(missing))
    return {
        "ok": True,
        "message": (
            "Active claim, clean worktree, exact claim-start range, and write boundary verified."
        ),
        "git_root": str(root),
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed_files": changed_files,
    }


def _resume_error(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    attempt_id: str,
    receipt_id: str,
) -> str:
    attempt = next((item for item in workspace.attempts if item.id == attempt_id), None)
    if attempt is not None and (
        attempt.work_item_id != work_id or attempt.actor != palari_id
    ):
        return f"existing {attempt_id} does not match this work and Palari"
    receipt = next((item for item in workspace.receipts if item.id == receipt_id), None)
    if receipt is not None and (
        receipt.work_item_id != work_id
        or receipt.attempt_id != attempt_id
        or receipt.actor != palari_id
    ):
        return f"existing {receipt_id} does not match this work, attempt, and Palari"
    work = workspace.work_item(work_id)
    if work is not None and work.current_attempt not in {"", attempt_id}:
        return f"work {work_id} already points to different attempt {work.current_attempt}"
    return ""


def _blocked_preflight(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "message": message,
        "git_root": "",
        "base_sha": "",
        "head_sha": "",
        "changed_files": [],
    }


def _is_agent_runtime_path(path: str, git_root: Path, workspace_root: Path) -> bool:
    try:
        relative_workspace = workspace_root.resolve().relative_to(git_root.resolve()).as_posix()
    except ValueError:
        return False
    base = f"{relative_workspace}/" if relative_workspace != "." else ""
    return any(
        path.startswith(f"{base}.palari/{name}/")
        for name in ("claims", "packets", "locks")
    )


def _git_lines(root: Path, arguments: list[str]) -> list[str] | None:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        timeout=10,
    )
    if result.returncode != 0:
        return None
    separator = b"\0" if "-z" in arguments else None
    if separator:
        return [os.fsdecode(field) for field in result.stdout.split(separator) if field]
    return [os.fsdecode(field).strip() for field in result.stdout.splitlines() if field.strip()]


def _git_value(root: Path, arguments: list[str]) -> str:
    lines = _git_lines(root, arguments)
    return lines[0] if lines else ""


def _git_ok(root: Path, arguments: list[str]) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
    )
    return result.returncode == 0
