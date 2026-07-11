from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_checks import build_agent_check
from .agent_finish import build_agent_finish
from .agent_runtime import read_claim, release_agent, start_agent
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

    if work.get("status") in {"completed", "closed", "done"}:
        return {
            "schema_version": "palari.agent_done.v1",
            "status": "already-completed",
            "work_item": work_id,
            "workspace": workspace.name,
            "message": f"Work item {work_id} is already {work['status']}.",
            "can_done": False,
        }

    steps: list[dict[str, str]] = []
    attempt_id = f"ATTEMPT-DONE-{work_id}"
    receipt_id = f"RECEIPT-DONE-{work_id}"
    changed_paths = changed or work.get("output_targets", []) or []

    attempt_record = {
        "id": attempt_id,
        "work_item_id": work_id,
        "actor": palari_id,
        "status": "active",
        "cleanliness": "clean",
    }
    if model_or_worker:
        attempt_record["model_or_worker"] = model_or_worker
    create_record(
        workspace_path,
        "attempt",
        attempt_record,
        command="agent done",
        actor=palari_id,
    )
    steps.append({"step": "attempt-record", "id": attempt_id, "status": "created"})

    receipt_record = {
        "id": receipt_id,
        "work_item_id": work_id,
        "attempt_id": attempt_id,
        "actor": palari_id,
        "actions_taken": ["agent done shortcut"],
        "outputs_created": changed_paths,
        "not_done": ["No external writes", "No live integrations", "No secrets read"],
        "undo_refs": changed_paths,
    }
    create_record(
        workspace_path,
        "receipt",
        receipt_record,
        command="agent done",
        actor=palari_id,
    )
    steps.append({"step": "receipt-record", "id": receipt_id, "status": "created"})

    update_record(
        workspace_path,
        "work",
        work_id,
        {"current_attempt": attempt_id},
        command="agent done",
        actor=palari_id,
    )
    steps.append({"step": "work-update", "id": work_id, "status": "updated"})

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
        cwd=Path.cwd(),
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

    complete_work(
        workspace_path,
        work_id,
        "completed",
        command="agent done",
        actor=palari_id,
    )
    steps.append({"step": "lifecycle-complete", "id": work_id, "status": "completed"})

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
