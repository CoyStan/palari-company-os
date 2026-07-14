from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any


CHUNK_SIZE = 1024 * 1024


class SubjectError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_subject_name(name: str) -> str:
    """Return a safe, portable PCAW artifact subject name."""

    if not isinstance(name, str) or not name:
        raise SubjectError("PCAW_SUBJECT_PATH_UNSAFE", "subject name must be non-empty")
    if "\\" in name or "\x00" in name:
        raise SubjectError(
            "PCAW_SUBJECT_PATH_UNSAFE",
            "subject names must use relative POSIX path syntax",
        )
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise SubjectError(
            "PCAW_SUBJECT_PATH_UNSAFE",
            "subject name must be a normalized relative path without dot segments",
        )
    normalized = path.as_posix()
    if normalized != name or name.startswith("//"):
        raise SubjectError(
            "PCAW_SUBJECT_PATH_UNSAFE",
            "subject name must already be a normalized relative POSIX path",
        )
    return normalized


def hash_subject(root: Path | str, name: str) -> str:
    """Hash a regular file beneath root without following symbolic links."""

    safe_name = validate_subject_name(name)
    root_path = Path(root).expanduser().resolve(strict=True)
    if not root_path.is_dir():
        raise SubjectError("PCAW_SUBJECT_ROOT_INVALID", "subject root is not a directory")

    current = root_path
    parts = PurePosixPath(safe_name).parts
    for part in parts[:-1]:
        current = current / part
        try:
            item_stat = current.lstat()
        except FileNotFoundError as exc:
            raise SubjectError(
                "PCAW_SUBJECT_MISSING", f"subject path component is missing: {part}"
            ) from exc
        if stat.S_ISLNK(item_stat.st_mode):
            raise SubjectError(
                "PCAW_SUBJECT_SYMLINK", f"subject path crosses a symbolic link: {part}"
            )
        if not stat.S_ISDIR(item_stat.st_mode):
            raise SubjectError(
                "PCAW_SUBJECT_PATH_UNSAFE", f"subject path component is not a directory: {part}"
            )

    target = current / parts[-1]
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target, flags)
    except FileNotFoundError as exc:
        raise SubjectError("PCAW_SUBJECT_MISSING", f"subject is missing: {safe_name}") from exc
    except OSError as exc:
        if target.is_symlink():
            raise SubjectError(
                "PCAW_SUBJECT_SYMLINK", f"subject is a symbolic link: {safe_name}"
            ) from exc
        raise SubjectError(
            "PCAW_SUBJECT_UNREADABLE", f"subject cannot be opened safely: {safe_name}"
        ) from exc

    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SubjectError(
                "PCAW_SUBJECT_NOT_REGULAR", f"subject is not a regular file: {safe_name}"
            )
        while True:
            chunk = os.read(descriptor, CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise SubjectError(
                "PCAW_SUBJECT_CHANGED_DURING_READ",
                f"subject changed while it was being verified: {safe_name}",
            )
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def subject_diagnostic(error: SubjectError, path: str) -> dict[str, Any]:
    return {
        "code": error.code,
        "path": path,
        "message": str(error),
        "next_action": "Restore the exact regular artifact beneath the subject root and verify again.",
    }
