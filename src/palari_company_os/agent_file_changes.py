from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any

from .path_policy import canonical_path_allowed, path_allowed, resolve_workspace_path


def inspect_file_changes(
    packet: dict[str, Any],
    *,
    changed_paths: list[str] | None = None,
    git_diff: bool = False,
    cwd: Path | str | None = None,
    git_baseline: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not changed_paths and not git_diff:
        return None

    root, root_error = _git_root_result(Path(cwd or Path.cwd()))
    observed, invalid_paths, observation_errors = _observed_changes(
        changed_paths or [], root=root, git_diff=git_diff
    )
    if git_diff and root_error:
        observation_errors.append(root_error)
    preexisting_unchanged: list[str] = []
    if git_diff and root is not None and git_baseline is not None:
        observed_before_baseline = {item["path"]: item for item in observed}
        observed, preexisting_unchanged, baseline_errors = _subtract_git_baseline(
            root, observed, git_baseline
        )
        observation_errors.extend(baseline_errors)
        retained_paths = {item["path"] for item in observed}
        for explicit in changed_paths or []:
            try:
                normalized = _normalize_path(explicit)
            except ValueError:
                continue
            if normalized not in retained_paths:
                observed.append(
                    observed_before_baseline.get(
                        normalized, {"path": normalized, "status": "modified"}
                    )
                )
                retained_paths.add(normalized)
            if normalized in preexisting_unchanged:
                preexisting_unchanged.remove(normalized)
        observed.sort(key=lambda item: item["path"])

    allowed_write = _strings(packet.get("allowed_paths", {}).get("write", []))
    required_output = packet.get("required_output", {})
    path_intents = _path_intents(required_output.get("path_intents", []))
    output_targets = (
        required_output.get("output_targets", [])
        if path_intents
        else required_output.get("output_targets", [])
        or required_output.get("fallback_write_paths", [])
    )
    attempt = packet.get("proof_state", {}).get("attempt") or {}
    receipt = packet.get("proof_state", {}).get("receipt") or {}
    recorded = sorted(
        set(_strings(attempt.get("changed_files", [])))
        | set(_strings(receipt.get("outputs_created", [])))
    )
    changed = [item["path"] for item in observed]
    outside = [
        path
        for path in changed
        if path in invalid_paths or not _path_allowed(path, allowed_write, root=root)
    ]
    # Existing consumers fail the boundary check when this list is non-empty.
    # Retain an explicit marker so Git observation failures cannot masquerade as
    # an unchanged, valid worktree before every consumer learns the richer field.
    outside.extend(
        marker for marker in (_observation_error_marker(item) for item in observation_errors)
        if marker not in outside
    )
    inside = [path for path in changed if path not in outside]
    unrecorded = [path for path in changed if path not in recorded]
    missing_outputs: list[str] = []
    for path in _strings(output_targets):
        if not path or root is None:
            continue
        try:
            output_path = resolve_workspace_path(root, path)
        except ValueError as exc:
            missing_outputs.append(path)
            observation_errors.append(f"required output path is unsafe: {path}: {exc}")
            continue
        if not output_path.exists():
            missing_outputs.append(path)
    intent_mismatches: list[dict[str, str]] = []
    observed_status = {item["path"]: item["status"] for item in observed}
    for item in path_intents:
        path = item["path"]
        intent = item["intent"]
        if root is None:
            intent_mismatches.append(
                {
                    "path": path,
                    "intent": intent,
                    "actual": "unobserved",
                    "reason": "Git root is unavailable; final path state cannot be verified.",
                }
            )
            continue
        try:
            intent_path = resolve_workspace_path(root, path)
        except ValueError as exc:
            intent_mismatches.append(
                {
                    "path": path,
                    "intent": intent,
                    "actual": "unsafe",
                    "reason": f"Path cannot be resolved inside the repository: {exc}",
                }
            )
            observation_errors.append(f"path intent is unsafe: {path}: {exc}")
            if path not in missing_outputs:
                missing_outputs.append(path)
            continue
        present = intent_path.exists() or intent_path.is_symlink()
        regular_file = present and intent_path.is_file()
        satisfied = not present if intent == "delete" else regular_file
        if git_diff and satisfied:
            actual_change = observed_status.get(path, "unchanged")
            accepted_changes = {
                "create": {"created", "untracked"},
                "modify": {"modified"},
                "delete": {"deleted"},
            }[intent]
            satisfied = actual_change in accepted_changes
            if not satisfied:
                intent_mismatches.append(
                    {
                        "path": path,
                        "intent": intent,
                        "actual": actual_change,
                        "reason": (
                            f"{intent.title()} intent does not match the observed Git "
                            f"change type {actual_change}."
                        ),
                    }
                )
                if path not in missing_outputs:
                    missing_outputs.append(path)
                continue
        if satisfied:
            continue
        intent_mismatches.append(
            {
                "path": path,
                "intent": intent,
                "actual": "present" if present else "absent",
                "reason": (
                    "Delete intent requires the exact path to be absent."
                    if intent == "delete"
                    else f"{intent.title()} intent requires the exact path to be a file."
                ),
            }
        )
        if path not in missing_outputs:
            missing_outputs.append(path)

    return {
        "enabled": True,
        "source": "git-diff" if git_diff else "changed-args",
        "git_root": str(root) if root else "",
        "observation_complete": not observation_errors and not invalid_paths,
        "observation_errors": observation_errors,
        "invalid_changed_paths": invalid_paths,
        "changed_files": changed,
        "preexisting_unchanged_files": preexisting_unchanged,
        "modified_files": [item["path"] for item in observed if item["status"] == "modified"],
        "created_files": [item["path"] for item in observed if item["status"] == "created"],
        "untracked_files": [item["path"] for item in observed if item["status"] == "untracked"],
        "deleted_files": [item["path"] for item in observed if item["status"] == "deleted"],
        "inside_write_boundary": inside,
        "outside_write_boundary": outside,
        "allowed_write_paths": allowed_write,
        "required_outputs": _strings(output_targets),
        "missing_required_outputs": missing_outputs,
        "path_intents": path_intents,
        "path_intent_mismatches": intent_mismatches,
        "path_intents_ok": not intent_mismatches,
        "recorded_changed_files": recorded,
        "unrecorded_changed_files": unrecorded,
    }


def capture_git_baseline(cwd: Path | str) -> dict[str, Any]:
    """Capture dirty path metadata without reading file contents."""

    root, root_error = _git_root_result(Path(cwd))
    if root is None:
        return {
            "schema_version": "palari.git_baseline.v1",
            "git_root": "",
            "head_sha": "",
            "observation_complete": False,
            "observation_errors": [root_error or "Git root is unavailable"],
            "entries": [],
        }
    changes, status_error = _git_status_result(root)
    head_sha, head_error = _git_head_result(root)
    errors = [status_error] if status_error else []
    entries: list[dict[str, Any]] = []
    for item in changes:
        fingerprint, error = _path_fingerprint(root, item["path"])
        if error:
            errors.append(error)
        entries.append({**item, "fingerprint": fingerprint})
    return {
        "schema_version": "palari.git_baseline.v1",
        "git_root": str(root),
        "head_sha": head_sha,
        "head_observation_error": head_error,
        "observation_complete": not errors,
        "observation_errors": errors,
        "entries": entries,
    }


def _observed_changes(
    explicit_paths: list[str],
    *,
    root: Path | None,
    git_diff: bool,
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    changes: dict[str, str] = {}
    invalid_paths: list[str] = []
    errors: list[str] = []
    for path in explicit_paths:
        try:
            normalized = _normalize_path(path)
        except ValueError:
            raw = str(path)
            if raw not in invalid_paths:
                invalid_paths.append(raw)
            changes[raw] = "invalid"
            continue
        changes[normalized] = "modified"
    if git_diff and root is not None:
        git_changes, git_error = _git_status_result(root)
        if git_error:
            errors.append(git_error)
        for item in git_changes:
            changes[item["path"]] = item["status"]
    return (
        [{"path": path, "status": status} for path, status in sorted(changes.items())],
        invalid_paths,
        errors,
    )


def _git_status_result(root: Path) -> tuple[list[dict[str, str]], str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"could not inspect Git worktree: {exc}"
    if result.returncode != 0:
        detail = os.fsdecode(result.stderr).strip() or f"git exited {result.returncode}"
        return [], f"could not inspect Git worktree: {detail}"

    fields = result.stdout.split(b"\0")
    changes: list[dict[str, str]] = []
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4 or entry[2:3] != b" ":
            return [], "could not parse NUL-delimited Git status output"
        marker = os.fsdecode(entry[:2])
        raw_path = os.fsdecode(entry[3:])
        try:
            path = _normalize_git_path(raw_path)
        except ValueError as exc:
            return [], f"Git reported an unsafe path {raw_path!r}: {exc}"
        status = (
            "untracked"
            if marker == "??"
            else "deleted"
            if "D" in marker
            else "created"
            if "A" in marker
            else "modified"
        )
        changes.append({"path": path, "status": status})

        if "R" in marker or "C" in marker:
            if index >= len(fields) or not fields[index]:
                return [], "could not parse rename/copy in NUL-delimited Git status output"
            old_raw = os.fsdecode(fields[index])
            index += 1
            if "R" in marker:
                try:
                    old_path = _normalize_git_path(old_raw)
                except ValueError as exc:
                    return [], f"Git reported an unsafe path {old_raw!r}: {exc}"
                changes.append({"path": old_path, "status": "deleted"})
    return changes, ""


def _subtract_git_baseline(
    root: Path,
    observed: list[dict[str, str]],
    baseline: dict[str, Any],
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    errors: list[str] = []
    if baseline.get("schema_version") != "palari.git_baseline.v1":
        return observed, [], ["Git baseline has an unsupported or missing schema_version"]
    if baseline.get("git_root") != str(root):
        return observed, [], ["Git baseline belongs to a different repository root"]
    if not baseline.get("observation_complete"):
        declared = baseline.get("observation_errors", [])
        detail = "; ".join(str(item) for item in declared) or "capture was incomplete"
        return observed, [], [f"Git baseline is incomplete: {detail}"]
    raw_entries = baseline.get("entries")
    if not isinstance(raw_entries, list):
        return observed, [], ["Git baseline entries must be a list"]

    baseline_by_path: dict[str, dict[str, Any]] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict):
            errors.append("Git baseline contains a malformed entry")
            continue
        path = entry.get("path")
        status_value = entry.get("status")
        fingerprint = entry.get("fingerprint")
        if (
            not isinstance(path, str)
            or not path
            or status_value not in {"created", "modified", "untracked", "deleted"}
            or not isinstance(fingerprint, dict)
        ):
            errors.append("Git baseline contains a malformed path, status, or fingerprint")
            continue
        if path in baseline_by_path:
            errors.append(f"Git baseline contains duplicate path: {path}")
            continue
        baseline_by_path[path] = entry

    retained: list[dict[str, str]] = []
    unchanged: list[str] = []
    for item in observed:
        previous = baseline_by_path.get(item["path"])
        if previous is None or previous.get("status") != item["status"]:
            retained.append(item)
            continue
        fingerprint, error = _path_fingerprint(root, item["path"])
        if error:
            errors.append(error)
            retained.append(item)
            continue
        if fingerprint == previous.get("fingerprint"):
            unchanged.append(item["path"])
        else:
            retained.append(item)
    return retained, sorted(unchanged), errors


def _path_fingerprint(root: Path, path: str) -> tuple[dict[str, Any], str]:
    try:
        normalized = _normalize_git_path(path)
        resolve_workspace_path(root, normalized)
    except ValueError as exc:
        return {}, f"cannot fingerprint unsafe Git path {path!r}: {exc}"
    candidate = root / normalized
    try:
        metadata = candidate.lstat()
    except FileNotFoundError:
        return {"exists": False}, ""
    except OSError as exc:
        return {}, f"cannot fingerprint Git path {path!r}: {exc}"
    fingerprint: dict[str, Any] = {
        "exists": True,
        "mode": metadata.st_mode,
        "size": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
    }
    if stat.S_ISLNK(metadata.st_mode):
        try:
            fingerprint["symlink_target"] = os.readlink(candidate)
        except OSError as exc:
            return {}, f"cannot fingerprint Git symlink {path!r}: {exc}"
    return fingerprint, ""


def git_repo_root(cwd: Path) -> Path | None:
    """Return the enclosing git repository root, or None outside a repo."""
    root, _error = _git_root_result(cwd)
    return root


def _git_root_result(cwd: Path) -> tuple[Path | None, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"could not locate Git repository: {exc}"
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        return None, f"could not locate Git repository: {detail}"
    value = result.stdout.strip()
    if not value:
        return None, "could not locate Git repository: git returned an empty root"
    return Path(value).resolve(), ""


def _git_head_result(root: Path) -> tuple[str, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", f"could not inspect Git HEAD: {exc}"
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        return "", f"could not inspect Git HEAD: {detail}"
    value = result.stdout.strip()
    if not value:
        return "", "could not inspect Git HEAD: git returned an empty revision"
    return value, ""


def _path_allowed(path: str, allowed_paths: list[str], *, root: Path | None) -> bool:
    if root is not None:
        possible_boundaries = [
            allowed for allowed in allowed_paths if path_allowed(path, [allowed])
        ]
        return canonical_path_allowed(path, possible_boundaries, root=root)
    return path_allowed(path, allowed_paths)


def _normalize_path(path: str) -> str:
    from .path_policy import validate_workspace_path

    normalized = validate_workspace_path(path)
    if normalized != path:
        raise ValueError("path is not in canonical repository form")
    return normalized


def _normalize_git_path(path: str) -> str:
    return _normalize_path(path)


def _observation_error_marker(message: str) -> str:
    return f"[observation-error] {message}"


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def _path_intents(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [
        {"path": item["path"], "intent": item["intent"]}
        for item in value
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and item.get("path")
        and item.get("intent") in {"create", "modify", "delete"}
    ]
