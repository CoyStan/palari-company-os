from __future__ import annotations

from typing import Any

from .workspace import Workspace


def build_active_parallel_work(
    workspace: Workspace,
    work_by_id: dict[str, Any],
    workbenches_by_id: dict[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for attempt in workspace.attempts:
        if attempt.status != "active":
            continue
        work = work_by_id.get(attempt.work_item_id)
        if work is None:
            continue
        workbench = workbenches_by_id.get(work.workbench_id) if work.workbench_id else None
        entries.append(
            {
                "work_item_id": work.id,
                "work_item_title": work.title,
                "workbench_id": work.workbench_id,
                "workbench_label": workbench.label if workbench else "",
                "attempt_id": attempt.id,
                "actor": attempt.actor,
                "status": attempt.status,
                "branch": attempt.branch,
                "workspace_path": attempt.workspace_path,
                "started_at": attempt.started_at,
                "updated_at": attempt.updated_at,
                "output_targets": _attempt_targets(work, attempt),
            }
        )
    return sorted(entries, key=lambda item: (item["workbench_id"], item["work_item_id"]))


def build_coordination_warnings(
    workspace: Workspace,
    current_attempt_by_work: dict[str, Any],
) -> list[dict[str, Any]]:
    subjects = _coordination_subjects(workspace, current_attempt_by_work)
    warnings: list[dict[str, Any]] = []
    for index, left in enumerate(subjects):
        for right in subjects[index + 1 :]:
            if left["workbench_id"] != right["workbench_id"]:
                continue
            if "exclusive" not in {left["parallel_policy"], right["parallel_policy"]}:
                continue
            overlap = sorted(left["normalized_targets"] & right["normalized_targets"])
            if not overlap:
                continue
            warnings.append(
                {
                    "workbench_id": left["workbench_id"],
                    "target": overlap[0],
                    "targets": overlap,
                    "work_item_ids": [left["work_item_id"], right["work_item_id"]],
                    "message": (
                        f"{left['work_item_id']} and {right['work_item_id']} both target "
                        f"{overlap[0]} with exclusive coordination."
                    ),
                }
            )
    return warnings


def group_active_attempts(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(entry["work_item_id"], []).append(entry)
    return grouped


def group_warning_messages(warnings: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for warning in warnings:
        for work_id in warning["work_item_ids"]:
            grouped.setdefault(work_id, []).append(warning["message"])
    return grouped


def _coordination_subjects(
    workspace: Workspace,
    current_attempt_by_work: dict[str, Any],
) -> list[dict[str, Any]]:
    subjects: list[dict[str, Any]] = []
    for work in workspace.work_items:
        if not work.workbench_id or work.status in {"closed", "completed", "done", "blocked"}:
            continue
        attempt = current_attempt_by_work.get(work.id)
        has_active_attempt = attempt is not None and attempt.status == "active"
        has_active_work = attempt is None and work.status in {
            "proposed",
            "active",
            "in-review",
            "needs-human",
        }
        if not (has_active_attempt or has_active_work):
            continue
        targets = _conflict_targets(work)
        normalized_targets = {_normalize_target(target) for target in targets if target.strip()}
        if not normalized_targets:
            continue
        subjects.append(
            {
                "work_item_id": work.id,
                "workbench_id": work.workbench_id,
                "parallel_policy": work.parallel_policy,
                "normalized_targets": normalized_targets,
            }
        )
    return subjects


def _conflict_targets(work: Any) -> list[str]:
    if work.conflict_targets:
        return work.conflict_targets
    return work.output_targets


def _normalize_target(target: str) -> str:
    return " ".join(target.strip().lower().replace("\\", "/").split())


def _attempt_targets(work: Any, attempt: Any) -> list[str]:
    if attempt.output_targets:
        return attempt.output_targets
    if work.conflict_targets:
        return work.conflict_targets
    if work.output_targets:
        return work.output_targets
    return attempt.changed_files
