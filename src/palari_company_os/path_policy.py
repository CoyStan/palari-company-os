from __future__ import annotations

import re
from pathlib import Path, PurePosixPath


WINDOWS_DRIVE_SEPARATOR_INDEX = 1
_PATH_TOKEN_RE = re.compile(
    r"(?<![\w./-])(?:\.?[\w.-]+/)+[\w.@%+=:,~-]+"
    r"|(?<![\w./-])[\w.@%+=:,~-]+\.[A-Za-z0-9]{1,12}(?![\w./-])"
)


def normalize_workspace_path(path: str) -> str:
    """Return a safe normalized workspace-relative POSIX path.

    This raises ``ValueError`` for absolute paths, empty paths, Windows drive
    paths, and traversal segments. Callers that need a fail-closed boolean
    should use ``path_allowed``.
    """
    return validate_workspace_path(path)


def validate_workspace_path(path: str) -> str:
    raw = path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path must not be empty")
    if raw.startswith("/"):
        raise ValueError("path must be workspace-relative")

    parts: list[str] = []
    for part in PurePosixPath(raw).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("path must not contain '..'")
        if _looks_like_windows_drive(part):
            raise ValueError("path must be workspace-relative")
        parts.append(part)

    if not parts:
        raise ValueError("path must not be empty")
    return "/".join(parts)


def path_allowed(path: str, allowed_resources: list[str]) -> bool:
    try:
        normalized = validate_workspace_path(path)
    except ValueError:
        return False

    for allowed in allowed_resources:
        try:
            allowed_path = validate_workspace_path(allowed)
        except ValueError:
            continue
        if normalized == allowed_path or normalized.startswith(f"{allowed_path}/"):
            return True
    return False


def resolve_workspace_path(
    root: Path | str,
    path: str,
    *,
    require_exists: bool = False,
) -> Path:
    """Resolve a workspace-relative path without allowing a symlink escape.

    ``validate_workspace_path`` protects the lexical namespace. This helper is
    for callers that will touch the filesystem: it additionally resolves
    existing symlink components and requires the result to remain below the
    canonical root. ``strict=False`` still resolves existing parents, so a new
    file below a symlink that points outside the root is rejected before use.
    """

    normalized = validate_workspace_path(path)
    canonical_root = Path(root).expanduser().resolve()
    candidate = canonical_root.joinpath(*PurePosixPath(normalized).parts)
    try:
        resolved = candidate.resolve(strict=require_exists)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"path cannot be resolved safely: {path}") from exc
    try:
        resolved.relative_to(canonical_root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace root through a symlink: {path}") from exc
    return resolved


def canonical_path_allowed(
    path: str,
    allowed_resources: list[str],
    *,
    root: Path | str,
) -> bool:
    """Return whether a filesystem path is canonically inside a boundary."""

    try:
        candidate = resolve_workspace_path(root, path)
    except ValueError:
        return False
    for allowed in allowed_resources:
        try:
            if validate_workspace_path(allowed) != allowed:
                continue
            boundary = resolve_workspace_path(root, allowed)
        except ValueError:
            continue
        if candidate == boundary:
            return True
        try:
            candidate.relative_to(boundary)
        except ValueError:
            continue
        return True
    return False


def path_candidates(value: str) -> list[str]:
    """Return path-like tokens from prose, preserving order."""
    candidates: list[str] = []
    for token in re.split(r"\s+", value):
        candidate = token.strip("'\"`()[]{}<>,;:.")
        if not candidate:
            continue
        looks_path_like = (
            "/" in candidate
            or "\\" in candidate
            or bool(re.search(r"\.[A-Za-z0-9]{1,12}$", candidate))
            or _looks_like_windows_drive(candidate)
        )
        if looks_path_like and candidate not in candidates:
            candidates.append(candidate)
    for match in _PATH_TOKEN_RE.finditer(value):
        candidate = match.group(0).strip("'\"`()[]{}<>,;:.")
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _looks_like_windows_drive(part: str) -> bool:
    return (
        len(part) > WINDOWS_DRIVE_SEPARATOR_INDEX
        and part[WINDOWS_DRIVE_SEPARATOR_INDEX] == ":"
        and part[0].isalpha()
    )
