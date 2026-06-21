from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .path_policy import path_allowed, validate_workspace_path
from .workspace import Workspace


@dataclass(frozen=True)
class ScopeCheck:
    work_item_id: str
    allowed: bool
    changed_paths: list[str]
    actions: list[str]
    violations: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_scope(
    workspace: Workspace,
    work_id: str,
    changed_paths: list[str] | None = None,
    actions: list[str] | None = None,
) -> ScopeCheck:
    work = workspace.work_item(work_id)
    if work is None:
        known = ", ".join(sorted(item.id for item in workspace.work_items))
        raise KeyError(f"unknown work item {work_id}; known work items: {known}")

    paths = changed_paths or []
    requested_actions = actions or []
    violations: list[str] = []
    notes: list[str] = []

    if paths and not work.allowed_resources:
        violations.append("No allowed resources are declared; path access fails closed.")

    for path in paths:
        if not _path_allowed(path, work.allowed_resources):
            violations.append(f"Path is outside allowed resources: {path}")

    forbidden = {action.lower() for action in work.forbidden_actions}
    for action in requested_actions:
        normalized = action.lower()
        if normalized in forbidden:
            violations.append(f"Action is explicitly forbidden: {action}")
        elif any(term in normalized for term in forbidden):
            violations.append(f"Action appears to include forbidden behavior: {action}")

    if not violations:
        notes.append("Scope check passed against declared allowed resources and forbidden actions.")

    return ScopeCheck(
        work_item_id=work.id,
        allowed=not violations,
        changed_paths=paths,
        actions=requested_actions,
        violations=violations,
        notes=notes,
    )


def _path_allowed(path: str, allowed_resources: list[str]) -> bool:
    return path_allowed(path, allowed_resources)


def _normalize_path(path: str) -> str:
    try:
        return validate_workspace_path(path)
    except ValueError:
        return ""

