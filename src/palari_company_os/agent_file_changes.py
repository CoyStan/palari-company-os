from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .path_policy import path_allowed, validate_workspace_path


def inspect_file_changes(
    packet: dict[str, Any],
    *,
    changed_paths: list[str] | None = None,
    git_diff: bool = False,
    cwd: Path | str | None = None,
) -> dict[str, Any] | None:
    if not changed_paths and not git_diff:
        return None

    root = _git_root(Path(cwd or Path.cwd()))
    observed = _observed_changes(changed_paths or [], root=root, git_diff=git_diff)
    allowed_write = packet.get("allowed_paths", {}).get("write", [])
    required_output = packet.get("required_output", {})
    output_targets = required_output.get("output_targets", []) or required_output.get(
        "fallback_write_paths", []
    )
    attempt = packet.get("proof_state", {}).get("attempt") or {}
    receipt = packet.get("proof_state", {}).get("receipt") or {}
    recorded = sorted(
        set(_strings(attempt.get("changed_files", [])))
        | set(_strings(receipt.get("outputs_created", [])))
    )
    changed = [item["path"] for item in observed]
    outside = [path for path in changed if not _path_allowed(path, allowed_write)]
    inside = [path for path in changed if path not in outside]
    unrecorded = [path for path in changed if path not in recorded]
    missing_outputs = [
        path
        for path in _strings(output_targets)
        if path and root is not None and not (root / path).exists()
    ]
    return {
        "enabled": True,
        "source": "git-diff" if git_diff else "changed-args",
        "git_root": str(root) if root else "",
        "changed_files": changed,
        "modified_files": [item["path"] for item in observed if item["status"] == "modified"],
        "untracked_files": [item["path"] for item in observed if item["status"] == "untracked"],
        "deleted_files": [item["path"] for item in observed if item["status"] == "deleted"],
        "inside_write_boundary": inside,
        "outside_write_boundary": outside,
        "allowed_write_paths": _strings(allowed_write),
        "required_outputs": _strings(output_targets),
        "missing_required_outputs": missing_outputs,
        "recorded_changed_files": recorded,
        "unrecorded_changed_files": unrecorded,
    }


def _observed_changes(
    explicit_paths: list[str],
    *,
    root: Path | None,
    git_diff: bool,
) -> list[dict[str, str]]:
    changes: dict[str, str] = {}
    for path in explicit_paths:
        normalized = _normalize_path(path)
        if normalized:
            changes[normalized] = "modified"
    if git_diff and root is not None:
        for item in _git_status(root):
            changes[item["path"]] = item["status"]
    return [{"path": path, "status": status} for path, status in sorted(changes.items())]


def _git_status(root: Path) -> list[dict[str, str]]:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return []
    changes: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        marker = line[:2]
        raw_path = line[3:]
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        path = _normalize_path(raw_path.strip())
        if not path:
            continue
        status = "untracked" if marker == "??" else "deleted" if "D" in marker else "modified"
        changes.append({"path": path, "status": status})
    return changes


def git_repo_root(cwd: Path) -> Path | None:
    """Return the enclosing git repository root, or None outside a repo."""
    return _git_root(cwd)


def _git_root(cwd: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return Path(value) if value else None


def _path_allowed(path: str, allowed_paths: list[str]) -> bool:
    return path_allowed(path, allowed_paths)


def _normalize_path(path: str) -> str:
    try:
        return validate_workspace_path(path)
    except ValueError:
        return ""


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []
