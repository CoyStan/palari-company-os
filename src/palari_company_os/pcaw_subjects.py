from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any


CHUNK_SIZE = 1024 * 1024
SAFE_DIRECTORY_WALK_SUPPORTED = (
    hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_DIRECTORY")
    and os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks
)


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
    """Hash a regular file beneath root through pinned directory descriptors."""

    safe_name = validate_subject_name(name)
    if not SAFE_DIRECTORY_WALK_SUPPORTED:
        raise SubjectError(
            "PCAW_SUBJECT_PLATFORM_UNSAFE",
            "platform cannot verify subjects without symlink races",
        )
    try:
        root_path = Path(root).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SubjectError(
            "PCAW_SUBJECT_ROOT_INVALID", "subject root does not exist or is unreadable"
        ) from exc
    if not root_path.is_dir():
        raise SubjectError("PCAW_SUBJECT_ROOT_INVALID", "subject root is not a directory")

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        directory_flags |= os.O_CLOEXEC
        file_flags |= os.O_CLOEXEC
    descriptors: list[int] = []
    try:
        try:
            current_descriptor = os.open(root_path, directory_flags)
        except OSError as exc:
            raise SubjectError(
                "PCAW_SUBJECT_ROOT_INVALID", "subject root cannot be opened safely"
            ) from exc
        descriptors.append(current_descriptor)
        parts = PurePosixPath(safe_name).parts
        for part in parts[:-1]:
            try:
                current_descriptor = os.open(
                    part,
                    directory_flags,
                    dir_fd=current_descriptor,
                )
            except FileNotFoundError as exc:
                raise SubjectError(
                    "PCAW_SUBJECT_MISSING",
                    f"subject path component is missing: {part}",
                ) from exc
            except OSError as exc:
                code = _component_error_code(descriptors[-1], part)
                message = (
                    f"subject path crosses a symbolic link: {part}"
                    if code == "PCAW_SUBJECT_SYMLINK"
                    else f"subject path component is not a safe directory: {part}"
                )
                raise SubjectError(code, message) from exc
            descriptors.append(current_descriptor)
        try:
            descriptor = os.open(
                parts[-1],
                file_flags,
                dir_fd=current_descriptor,
            )
        except FileNotFoundError as exc:
            raise SubjectError(
                "PCAW_SUBJECT_MISSING", f"subject is missing: {safe_name}"
            ) from exc
        except OSError as exc:
            code = _component_error_code(current_descriptor, parts[-1])
            message = (
                f"subject is a symbolic link: {safe_name}"
                if code == "PCAW_SUBJECT_SYMLINK"
                else f"subject cannot be opened safely: {safe_name}"
            )
            raise SubjectError(code, message) from exc
        descriptors.append(descriptor)

        try:
            digest = hashlib.sha256()
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise SubjectError(
                    "PCAW_SUBJECT_NOT_REGULAR",
                    f"subject is not a regular file: {safe_name}",
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
        except SubjectError:
            raise
        except OSError as exc:
            raise SubjectError(
                "PCAW_SUBJECT_UNREADABLE",
                f"subject failed during a safe read: {safe_name}",
            ) from exc
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass
    return digest.hexdigest()


def _component_error_code(directory_descriptor: int, name: str) -> str:
    try:
        item_stat = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except (OSError, TypeError, NotImplementedError):
        return "PCAW_SUBJECT_PATH_UNSAFE"
    return (
        "PCAW_SUBJECT_SYMLINK"
        if stat.S_ISLNK(item_stat.st_mode)
        else "PCAW_SUBJECT_PATH_UNSAFE"
    )


def subject_diagnostic(error: SubjectError, path: str) -> dict[str, Any]:
    return {
        "code": error.code,
        "path": path,
        "message": str(error),
        "next_action": "Restore the exact regular artifact beneath the subject root and verify again.",
    }
