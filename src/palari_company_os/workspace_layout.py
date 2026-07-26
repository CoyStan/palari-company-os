from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, overload
from uuid import UUID, uuid4

from .errors import WorkspaceError
from .pcaw_canonical import CanonicalJSONError, canonical_sha256, strict_json_loads
from .path_policy import resolve_workspace_path, validate_workspace_path


MAINTAINER_PROFILE = "maintainer"
ORDINARY_PROFILE = "ordinary"
MAINTAINER_WORKSPACE_FILENAME = ".palari-company-os.json"
MAINTAINER_STATE_ROOT = ".palari-company-os"
RUNTIME_ROOT = ".palari"
MAINTAINER_BINDING_FILENAME = "binding.json"
MAINTAINER_STATUS_FILENAME = "verification.json"
MAINTAINER_REPOSITORY_ID_FILENAME = "palari-maintainer-repository.json"
MAINTAINER_BINDING_SCHEMA = "palari.maintainer-binding.v1"
MAINTAINER_REPOSITORY_SCHEMA = "palari.maintainer-repository.v1"

_BINDING_FIELDS = {
    "schema_version",
    "profile",
    "state_id",
    "repository_id",
    "workspace_file",
    "state_root",
    "runtime_root",
    "repository_id_file",
    "binding_digest",
}
_REPOSITORY_ID_FIELDS = {"schema_version", "repository_id"}
_IGNORE_RULES = (
    f"/{MAINTAINER_WORKSPACE_FILENAME}",
    f"/{MAINTAINER_STATE_ROOT}/",
)


@dataclass(frozen=True)
class WorkspaceLayout:
    profile: str
    repository_root: Path
    data_path: Path
    state_root: Path
    runtime_root: Path
    binding_path: Path | None = None
    repository_common_dir: Path | None = None
    repository_id_path: Path | None = None
    state_id: str = ""
    repository_id: str = ""
    binding_digest: str = ""
    binding_witness: str = ""

    @property
    def maintainer(self) -> bool:
        return self.profile == MAINTAINER_PROFILE


@dataclass
class MaintainerInitialization:
    layout: WorkspaceLayout
    exclude_path: Path
    previous_exclude: bytes | None
    repository_id_created: bool
    state_root_created: bool
    active: bool = True

    def complete(self) -> WorkspaceLayout:
        layout = resolve_workspace_layout(
            self.layout.data_path,
            require_workspace=True,
        )
        self.active = False
        return layout

    def rollback(self) -> None:
        if not self.active:
            return
        self.active = False
        state_root = self.layout.repository_root / MAINTAINER_STATE_ROOT
        data_path = self.layout.repository_root / MAINTAINER_WORKSPACE_FILENAME
        if data_path.exists() and not data_path.is_symlink() and data_path.is_file():
            data_path.unlink()
        runtime_root = state_root / RUNTIME_ROOT
        binding_path = state_root / MAINTAINER_BINDING_FILENAME
        if (
            runtime_root.exists()
            and not runtime_root.is_symlink()
            and runtime_root.is_dir()
        ):
            shutil.rmtree(runtime_root)
        if (
            binding_path.exists()
            and not binding_path.is_symlink()
            and binding_path.is_file()
        ):
            binding_path.unlink()
        if (
            self.state_root_created
            and state_root.exists()
            and not state_root.is_symlink()
            and state_root.is_dir()
        ):
            try:
                state_root.rmdir()
            except OSError:
                # Preserve anything not created by this initialization attempt.
                pass
        if self.repository_id_created and self.layout.repository_id_path is not None:
            repository_id_path = self.layout.repository_id_path
            if (
                repository_id_path.exists()
                and not repository_id_path.is_symlink()
                and repository_id_path.is_file()
            ):
                repository_id_path.unlink()
        if self.previous_exclude is None:
            if (
                self.exclude_path.exists()
                and not self.exclude_path.is_symlink()
                and self.exclude_path.is_file()
            ):
                self.exclude_path.unlink()
        else:
            _atomic_replace_bytes(self.exclude_path, self.previous_exclude)


def workspace_data_path(path: Path | str) -> Path:
    """Return the exact workspace file without discovering hidden profile state."""

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if candidate.name == MAINTAINER_WORKSPACE_FILENAME:
        if candidate.is_dir():
            raise WorkspaceError(
                "maintainer workspace selector must name the exact regular file, "
                "not a directory"
            )
        _reject_lexical_parent(candidate)
        _reject_symlink(candidate, "maintainer workspace")
        if candidate.parent.resolve(strict=False) != candidate.parent:
            raise WorkspaceError(
                "maintainer workspace path components must not be symlinks"
            )
    elif candidate.is_dir():
        candidate = candidate / "workspace.json"
    return candidate.resolve(strict=False)


def is_maintainer_workspace(path: Path | str) -> bool:
    return workspace_data_path(path).name == MAINTAINER_WORKSPACE_FILENAME


def resolve_workspace_layout(
    path: Path | str,
    *,
    require_workspace: bool = True,
) -> WorkspaceLayout:
    data_path = workspace_data_path(path)
    if data_path.name != MAINTAINER_WORKSPACE_FILENAME:
        root = data_path.parent.resolve(strict=False)
        return WorkspaceLayout(
            profile=ORDINARY_PROFILE,
            repository_root=root,
            data_path=data_path,
            state_root=root,
            runtime_root=root / RUNTIME_ROOT,
        )
    return _resolve_maintainer_layout(
        data_path,
        require_workspace=require_workspace,
    )


def runtime_path(
    path: Path | str,
    relative: str,
    *,
    require_exists: bool = False,
    require_workspace: bool = True,
) -> Path:
    layout = resolve_workspace_layout(path, require_workspace=require_workspace)
    try:
        normalized = validate_workspace_path(relative)
    except ValueError as exc:
        raise WorkspaceError(f"unsafe Palari runtime path {relative}: {exc}") from exc
    if not normalized.startswith(f"{RUNTIME_ROOT}/") and normalized != RUNTIME_ROOT:
        raise WorkspaceError(
            f"unsafe Palari runtime path {relative}: path must be under {RUNTIME_ROOT}/"
        )
    candidate = _safe_state_path(
        layout.state_root,
        normalized,
        require_exists=require_exists,
        enforce_maintainer_types=layout.maintainer,
    )
    if layout.maintainer:
        _assert_path_ignored(
            layout.repository_root,
            candidate.relative_to(layout.repository_root).as_posix(),
        )
    return candidate


def runtime_relative_path(path: Path | str, target: Path) -> str:
    layout = resolve_workspace_layout(path)
    try:
        return target.relative_to(layout.state_root).as_posix()
    except ValueError:
        return target.name


def runtime_record_prefix(path: Path | str) -> str:
    resolve_workspace_layout(path)
    return RUNTIME_ROOT


def runtime_record_path(
    path: Path | str,
    suffix: str,
) -> str:
    clean = suffix.strip("/")
    prefix = runtime_record_prefix(path)
    return f"{prefix}/{clean}" if clean else prefix


def resolve_runtime_record_path(
    path: Path | str,
    relative: str,
    *,
    require_exists: bool = False,
) -> Path:
    layout = resolve_workspace_layout(path)
    try:
        normalized = validate_workspace_path(relative)
    except ValueError as exc:
        raise WorkspaceError(f"unsafe Palari runtime path {relative}: {exc}") from exc
    prefix = runtime_record_prefix(path)
    if normalized != prefix and not normalized.startswith(prefix + "/"):
        raise WorkspaceError(
            f"unsafe Palari runtime path {relative}: path must be under {prefix}/"
        )
    candidate = _safe_state_path(
        layout.state_root,
        normalized,
        require_exists=require_exists,
        enforce_maintainer_types=layout.maintainer,
    )
    if layout.maintainer:
        _assert_path_ignored(
            layout.repository_root,
            candidate.relative_to(layout.repository_root).as_posix(),
        )
    return candidate


def assert_layout_witness(
    path: Path | str,
    expected: str,
    *,
    require_workspace: bool = True,
) -> WorkspaceLayout:
    layout = resolve_workspace_layout(
        path,
        require_workspace=require_workspace,
    )
    if layout.maintainer and (
        not expected or layout.binding_witness != expected
    ):
        raise WorkspaceError(
            "maintainer profile binding changed since the workspace was loaded; "
            "retry the command"
        )
    return layout


def assert_runtime_file_descriptor(
    path: Path | str,
    target: Path,
    descriptor: int,
) -> None:
    """Bind an opened mutable runtime file to one unaliased maintainer inode."""

    data_path = workspace_data_path(path)
    layout = resolve_workspace_layout(
        data_path,
        require_workspace=data_path.exists(),
    )
    if not layout.maintainer:
        return
    try:
        relative = target.relative_to(layout.state_root).as_posix()
    except ValueError as exc:
        raise WorkspaceError(
            "maintainer runtime file escapes the bound state root"
        ) from exc
    checked = _safe_state_path(
        layout.state_root,
        relative,
        require_exists=True,
        enforce_maintainer_types=True,
    )
    if checked != target:
        raise WorkspaceError("maintainer runtime file path changed before write")
    try:
        path_stat = target.lstat()
        descriptor_stat = os.fstat(descriptor)
    except OSError as exc:
        raise WorkspaceError(
            f"maintainer runtime file cannot be verified before write: {exc}"
        ) from exc
    if (
        not stat.S_ISREG(path_stat.st_mode)
        or not stat.S_ISREG(descriptor_stat.st_mode)
        or path_stat.st_nlink != 1
        or descriptor_stat.st_nlink != 1
        or (path_stat.st_dev, path_stat.st_ino)
        != (descriptor_stat.st_dev, descriptor_stat.st_ino)
    ):
        raise WorkspaceError(
            "maintainer runtime writes require one exact unaliased regular file"
        )


def begin_maintainer_initialization(
    target: Path | str,
) -> MaintainerInitialization:
    raw_root = Path(target).expanduser()
    if not raw_root.is_absolute():
        raw_root = Path.cwd() / raw_root
    _reject_lexical_parent(raw_root)
    if raw_root.is_symlink():
        raise WorkspaceError("maintainer repository root must not be a symlink")
    try:
        root = raw_root.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceError(f"maintainer repository is unavailable: {exc}") from exc
    if root != raw_root:
        raise WorkspaceError(
            "maintainer repository path components must not be symlinks"
        )
    if not root.is_dir():
        raise WorkspaceError(f"maintainer repository is not a directory: {root}")

    git_root, common_dir = _git_repository_paths(root)
    if git_root != root:
        raise WorkspaceError(
            "maintainer profile must be initialized at the exact Git worktree root"
        )
    data_path = root / MAINTAINER_WORKSPACE_FILENAME
    state_root = root / MAINTAINER_STATE_ROOT
    if data_path.exists() or data_path.is_symlink():
        raise WorkspaceError(
            f"maintainer workspace already exists or conflicts: {data_path}"
        )
    state_root_created = not state_root.exists()
    if state_root.is_symlink():
        raise WorkspaceError(
            f"maintainer state root already exists or conflicts: {state_root}"
        )
    if state_root.exists():
        _validate_initial_state_root(state_root)
    dirty = [
        entry
        for entry in _git_status(root)
        if entry
        != f"?? {MAINTAINER_STATE_ROOT}/{MAINTAINER_STATUS_FILENAME}"
    ]
    if dirty:
        raise WorkspaceError(
            "maintainer profile initialization requires a clean Git worktree"
        )
    head = _git_output(root, "rev-parse", "--verify", "HEAD^{commit}")
    if not _exact_git_oid(head):
        raise WorkspaceError(
            "maintainer profile initialization requires an exact committed Git candidate"
        )
    _assert_untracked(root)

    exclude_path = _git_path(root, "info/exclude")
    _assert_regular_parent(exclude_path, common_dir, "Git exclude")
    previous_exclude = (
        exclude_path.read_bytes() if exclude_path.exists() else None
    )
    repository_id_path = common_dir / MAINTAINER_REPOSITORY_ID_FILENAME
    _assert_regular_parent(
        repository_id_path,
        common_dir,
        "maintainer repository identifier",
    )
    repository_id_created = False
    try:
        _install_ignore_rules(exclude_path)
        repository_id = ""
        if repository_id_path.exists():
            repository_id = _load_repository_id(repository_id_path)
        else:
            repository_id = str(uuid4())
            repository_id_created = True
            _atomic_replace_json(
                repository_id_path,
                {
                    "schema_version": MAINTAINER_REPOSITORY_SCHEMA,
                    "repository_id": repository_id,
                },
                mode=0o600,
            )
        _assert_ignored(root)

        if state_root_created:
            state_root.mkdir(mode=0o700)
        runtime_root = state_root / RUNTIME_ROOT
        runtime_root.mkdir(mode=0o700)
        binding_path = state_root / MAINTAINER_BINDING_FILENAME
        binding = {
            "schema_version": MAINTAINER_BINDING_SCHEMA,
            "profile": MAINTAINER_PROFILE,
            "state_id": str(uuid4()),
            "repository_id": repository_id,
            "workspace_file": MAINTAINER_WORKSPACE_FILENAME,
            "state_root": MAINTAINER_STATE_ROOT,
            "runtime_root": RUNTIME_ROOT,
            "repository_id_file": MAINTAINER_REPOSITORY_ID_FILENAME,
        }
        binding["binding_digest"] = _binding_digest(binding)
        _atomic_replace_json(binding_path, binding, mode=0o600)
        layout = _resolve_maintainer_layout(
            data_path,
            require_workspace=False,
        )
        return MaintainerInitialization(
            layout=layout,
            exclude_path=exclude_path,
            previous_exclude=previous_exclude,
            repository_id_created=repository_id_created,
            state_root_created=state_root_created,
        )
    except Exception:
        provisional = WorkspaceLayout(
            profile=MAINTAINER_PROFILE,
            repository_root=root,
            data_path=data_path,
            state_root=state_root,
            runtime_root=state_root / RUNTIME_ROOT,
            repository_common_dir=common_dir,
            repository_id_path=repository_id_path,
        )
        cleanup = MaintainerInitialization(
            layout=provisional,
            exclude_path=exclude_path,
            previous_exclude=previous_exclude,
            repository_id_created=repository_id_created,
            state_root_created=state_root_created,
        )
        cleanup.rollback()
        raise


def _resolve_maintainer_layout(
    data_path: Path,
    *,
    require_workspace: bool,
) -> WorkspaceLayout:
    _reject_lexical_parent(data_path)
    if data_path.is_symlink():
        raise WorkspaceError("maintainer workspace must be a regular file, not a symlink")
    root_hint = data_path.parent
    git_root, common_dir = _git_repository_paths(root_hint)
    expected_data = git_root / MAINTAINER_WORKSPACE_FILENAME
    if data_path != expected_data:
        raise WorkspaceError(
            "maintainer workspace must be the exact supported root-level file "
            f"{expected_data}"
        )
    _assert_no_symlink_below(git_root, expected_data, "maintainer workspace")
    if require_workspace:
        if not expected_data.exists() or not expected_data.is_file():
            raise WorkspaceError(f"workspace file not found: {expected_data}")
    elif expected_data.exists() and not expected_data.is_file():
        raise WorkspaceError(f"maintainer workspace must be a regular file: {expected_data}")

    state_root = git_root / MAINTAINER_STATE_ROOT
    binding_path = state_root / MAINTAINER_BINDING_FILENAME
    runtime_root = state_root / RUNTIME_ROOT
    for label, candidate, expected_type in (
        ("state root", state_root, "directory"),
        ("runtime root", runtime_root, "directory"),
        ("binding", binding_path, "file"),
    ):
        _assert_no_symlink_below(git_root, candidate, f"maintainer {label}")
        if candidate.is_symlink():
            raise WorkspaceError(f"maintainer {label} must not be a symlink: {candidate}")
        if expected_type == "directory" and not candidate.is_dir():
            raise WorkspaceError(f"maintainer {label} is not a real directory: {candidate}")
        if expected_type == "file" and not candidate.is_file():
            raise WorkspaceError(f"maintainer {label} is not a regular file: {candidate}")

    repository_id_path = common_dir / MAINTAINER_REPOSITORY_ID_FILENAME
    _assert_regular_parent(
        repository_id_path,
        common_dir,
        "maintainer repository identifier",
    )
    if repository_id_path.is_symlink() or not repository_id_path.is_file():
        raise WorkspaceError(
            "maintainer repository identifier is missing or is not a regular file"
        )
    binding, binding_bytes = _load_binding(binding_path)
    repository_id, repository_bytes = _load_repository_id(
        repository_id_path,
        include_bytes=True,
    )
    if binding["repository_id"] != repository_id:
        raise WorkspaceError(
            "maintainer binding belongs to a different Git repository"
        )
    _assert_untracked(git_root)
    _assert_ignored(git_root)
    witness = canonical_sha256(
        {
            "binding_digest": binding["binding_digest"],
            "binding_bytes": "sha256:" + hashlib.sha256(binding_bytes).hexdigest(),
            "repository_id_bytes": (
                "sha256:" + hashlib.sha256(repository_bytes).hexdigest()
            ),
        }
    )
    return WorkspaceLayout(
        profile=MAINTAINER_PROFILE,
        repository_root=git_root,
        data_path=expected_data,
        state_root=state_root,
        runtime_root=runtime_root,
        binding_path=binding_path,
        repository_common_dir=common_dir,
        repository_id_path=repository_id_path,
        state_id=str(binding["state_id"]),
        repository_id=repository_id,
        binding_digest=str(binding["binding_digest"]),
        binding_witness=witness,
    )


def _load_binding(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = strict_json_loads(raw)
    except (OSError, CanonicalJSONError, TypeError) as exc:
        raise WorkspaceError(f"maintainer binding is unreadable: {exc}") from exc
    if not isinstance(value, dict) or set(value) != _BINDING_FIELDS:
        raise WorkspaceError("maintainer binding has unexpected or missing fields")
    expected = {
        "schema_version": MAINTAINER_BINDING_SCHEMA,
        "profile": MAINTAINER_PROFILE,
        "workspace_file": MAINTAINER_WORKSPACE_FILENAME,
        "state_root": MAINTAINER_STATE_ROOT,
        "runtime_root": RUNTIME_ROOT,
        "repository_id_file": MAINTAINER_REPOSITORY_ID_FILENAME,
    }
    for field, expected_value in expected.items():
        if value.get(field) != expected_value:
            raise WorkspaceError(f"maintainer binding {field} is unsupported")
    for field in ("state_id", "repository_id"):
        _validate_uuid4(value.get(field), f"maintainer binding {field}")
    digest = value.get("binding_digest")
    if not isinstance(digest, str) or digest != _binding_digest(value):
        raise WorkspaceError("maintainer binding digest does not match its content")
    return value, raw


@overload
def _load_repository_id(
    path: Path,
    *,
    include_bytes: Literal[False] = False,
) -> str: ...


@overload
def _load_repository_id(
    path: Path,
    *,
    include_bytes: Literal[True],
) -> tuple[str, bytes]: ...


def _load_repository_id(
    path: Path,
    *,
    include_bytes: bool = False,
) -> str | tuple[str, bytes]:
    try:
        raw = path.read_bytes()
        value = strict_json_loads(raw)
    except (OSError, CanonicalJSONError, TypeError) as exc:
        raise WorkspaceError(
            f"maintainer repository identifier is unreadable: {exc}"
        ) from exc
    if not isinstance(value, dict) or set(value) != _REPOSITORY_ID_FIELDS:
        raise WorkspaceError("maintainer repository identifier has an invalid format")
    if value.get("schema_version") != MAINTAINER_REPOSITORY_SCHEMA:
        raise WorkspaceError("maintainer repository identifier schema is unsupported")
    repository_id = value.get("repository_id")
    _validate_uuid4(repository_id, "maintainer repository identifier")
    if include_bytes:
        return str(repository_id), raw
    return str(repository_id)


def _binding_digest(value: dict[str, Any]) -> str:
    payload = {
        key: item for key, item in value.items() if key != "binding_digest"
    }
    try:
        return canonical_sha256(payload)
    except CanonicalJSONError as exc:
        raise WorkspaceError(
            f"maintainer binding cannot be canonicalized: {exc}"
        ) from exc


def _validate_uuid4(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise WorkspaceError(f"{label} must be a UUIDv4")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise WorkspaceError(f"{label} must be a UUIDv4") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise WorkspaceError(f"{label} must be a canonical UUIDv4")


def _exact_git_oid(value: str) -> bool:
    return len(value) in {40, 64} and all(
        character in "0123456789abcdef" for character in value
    )


def _git_repository_paths(path: Path) -> tuple[Path, Path]:
    resolved = _git_output(
        path,
        "rev-parse",
        "--show-toplevel",
        "--git-common-dir",
    ).splitlines()
    if len(resolved) != 2 or not all(resolved):
        raise WorkspaceError(
            "maintainer profile requires one exact canonical Git worktree"
        )
    root_text, common_text = resolved
    root_lexical = Path(root_text).expanduser()
    if not root_lexical.is_absolute():
        root_lexical = path / root_lexical
    common_lexical = Path(common_text).expanduser()
    if not common_lexical.is_absolute():
        common_lexical = path / common_lexical
    normalized_root = Path(os.path.abspath(root_lexical))
    normalized_common = Path(os.path.abspath(common_lexical))
    try:
        root = normalized_root.resolve(strict=True)
        common_dir = normalized_common.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceError(f"Git repository paths are unavailable: {exc}") from exc
    if root != normalized_root or common_dir != normalized_common:
        raise WorkspaceError(
            "Git root and common directory paths must not contain symlinks"
        )
    if not root.is_dir() or not common_dir.is_dir():
        raise WorkspaceError("Git root and common directory must be real directories")
    _assert_no_symlink_below(root, normalized_common, "Git common directory")
    return root, common_dir


def _git_path(root: Path, relative: str) -> Path:
    raw = _git_output(root, "rev-parse", "--git-path", relative)
    if not raw:
        raise WorkspaceError(f"Git did not resolve {relative}")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = root / path
    return path


def _git_output(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "--no-replace-objects", *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            env=_safe_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(f"cannot inspect maintainer Git repository: {exc}") from exc
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _git_status(root: Path) -> list[str]:
    raw = _git_output(
        root,
        "status",
        "--porcelain",
        "--untracked-files=all",
    )
    return raw.splitlines() if raw else []


def _assert_ignored(root: Path) -> None:
    candidates = (
        MAINTAINER_WORKSPACE_FILENAME,
        f"{MAINTAINER_STATE_ROOT}/{MAINTAINER_BINDING_FILENAME}",
        f"{MAINTAINER_STATE_ROOT}/{RUNTIME_ROOT}/governance-journal.v2.jsonl",
        f"{MAINTAINER_STATE_ROOT}/{RUNTIME_ROOT}/claims/.ignore-probe.json",
        f"{MAINTAINER_STATE_ROOT}/{RUNTIME_ROOT}/packets/.ignore-probe.json",
        f"{MAINTAINER_STATE_ROOT}/{RUNTIME_ROOT}/locks/.ignore-probe",
        f"{MAINTAINER_STATE_ROOT}/{RUNTIME_ROOT}/verification/.ignore-probe.json",
    )
    _assert_paths_ignored(root, candidates)
    try:
        status = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "--no-replace-objects",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                MAINTAINER_WORKSPACE_FILENAME,
                MAINTAINER_STATE_ROOT,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            env=_safe_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(
            f"cannot verify maintainer local-state cleanliness: {exc}"
        ) from exc
    if status.returncode != 0:
        raise WorkspaceError("cannot verify maintainer local-state cleanliness")
    if status.stdout:
        raise WorkspaceError(
            "maintainer local state contains tracked or unignored paths: "
            + ", ".join(status.stdout.splitlines())
        )


def _assert_path_ignored(root: Path, candidate: str) -> None:
    _assert_paths_ignored(root, (candidate,))


def _assert_paths_ignored(root: Path, candidates: tuple[str, ...]) -> None:
    encoded = b"".join(os.fsencode(candidate) + b"\0" for candidate in candidates)
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "--no-replace-objects",
                "check-ignore",
                "--no-index",
                "-z",
                "--stdin",
            ],
            check=False,
            input=encoded,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            env=_safe_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(
            f"cannot verify maintainer ignore rules: {exc}"
        ) from exc
    if result.returncode not in {0, 1}:
        raise WorkspaceError("cannot verify maintainer ignore rules")
    ignored = {
        os.fsdecode(item)
        for item in result.stdout.split(b"\0")
        if item
    }
    missing = [candidate for candidate in candidates if candidate not in ignored]
    if missing:
        raise WorkspaceError(
            "maintainer local state path is not ignored: " + ", ".join(missing)
        )


def _assert_untracked(root: Path) -> None:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "--no-replace-objects",
                "ls-files",
                "-z",
                "--",
                MAINTAINER_WORKSPACE_FILENAME,
                MAINTAINER_STATE_ROOT,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            env=_safe_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(
            f"cannot inspect tracked maintainer state paths: {exc}"
        ) from exc
    if result.returncode != 0:
        raise WorkspaceError("cannot inspect tracked maintainer state paths")
    if result.stdout:
        paths = [
            os.fsdecode(item)
            for item in result.stdout.split(b"\0")
            if item
        ]
        raise WorkspaceError(
            "maintainer local state must not be tracked: " + ", ".join(paths)
        )


def _validate_initial_state_root(state_root: Path) -> None:
    if not state_root.is_dir():
        raise WorkspaceError(
            f"maintainer state root already exists or conflicts: {state_root}"
        )
    try:
        entries = list(state_root.iterdir())
    except OSError as exc:
        raise WorkspaceError(
            f"maintainer state root is unavailable: {exc}"
        ) from exc
    for entry in entries:
        if (
            entry.name != MAINTAINER_STATUS_FILENAME
            or entry.is_symlink()
            or not entry.is_file()
        ):
            raise WorkspaceError(
                f"maintainer state root already exists or conflicts: {entry}"
            )


def _install_ignore_rules(path: Path) -> None:
    current = path.read_bytes() if path.exists() else b""
    try:
        text = current.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceError("Git exclude file is not UTF-8") from exc
    existing = set(text.splitlines())
    missing = [rule for rule in _IGNORE_RULES if rule not in existing]
    if not missing:
        return
    prefix = "" if not text or text.endswith("\n") else "\n"
    addition = (
        prefix
        + "# Palari maintainer profile local state\n"
        + "\n".join(missing)
        + "\n"
    )
    _atomic_replace_bytes(path, current + addition.encode("utf-8"))


def _assert_regular_parent(path: Path, root: Path, label: str) -> None:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"{label} escapes the Git common directory") from exc
    _assert_no_symlink_below(root, path, label)
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise WorkspaceError(f"{label} parent must be a real directory: {parent}")
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise WorkspaceError(f"{label} must be a regular file: {path}")


def _assert_no_symlink_below(root: Path, target: Path, label: str) -> None:
    root = root.resolve(strict=True)
    lexical = target if target.is_absolute() else root / target
    try:
        relative = lexical.relative_to(root)
    except ValueError:
        # A linked-worktree common directory can live outside the worktree.
        if lexical.is_symlink():
            raise WorkspaceError(f"{label} must not be a symlink: {lexical}")
        return
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise WorkspaceError(f"{label} path contains a symlink: {cursor}")


def _reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise WorkspaceError(f"{label} must not be a symlink: {path}")


def _reject_lexical_parent(path: Path) -> None:
    if ".." in path.parts:
        raise WorkspaceError("maintainer profile paths must not contain '..'")


def _safe_state_path(
    root: Path,
    relative: str,
    *,
    require_exists: bool = False,
    enforce_maintainer_types: bool = False,
) -> Path:
    canonical_root = root.resolve(strict=False)
    candidate = canonical_root.joinpath(*relative.split("/"))
    current = canonical_root
    components = relative.split("/")
    for index, component in enumerate(components):
        current = current / component
        if not enforce_maintainer_types:
            if current.is_symlink():
                raise WorkspaceError(
                    f"unsafe Palari runtime path {relative}: "
                    "path contains a symlink"
                )
            continue
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise WorkspaceError(
                f"unsafe Palari runtime path {relative}: path is unavailable: {exc}"
            ) from exc
        if stat.S_ISLNK(current_stat.st_mode):
            raise WorkspaceError(
                f"unsafe Palari runtime path {relative}: path contains a symlink"
            )
        leaf = index == len(components) - 1
        if not leaf and not stat.S_ISDIR(current_stat.st_mode):
            raise WorkspaceError(
                f"unsafe Palari runtime path {relative}: "
                "existing intermediate components must be real directories"
            )
        if leaf and not (
            stat.S_ISDIR(current_stat.st_mode)
            or stat.S_ISREG(current_stat.st_mode)
        ):
            raise WorkspaceError(
                f"unsafe Palari runtime path {relative}: existing target must "
                "be a regular file or real directory"
            )
        if stat.S_ISREG(current_stat.st_mode) and current_stat.st_nlink != 1:
            raise WorkspaceError(
                f"unsafe Palari runtime path {relative}: existing regular "
                "files must have exactly one hard link"
            )
    try:
        resolved = resolve_workspace_path(
            canonical_root,
            relative,
            require_exists=require_exists,
        )
    except ValueError as exc:
        raise WorkspaceError(f"unsafe Palari runtime path {relative}: {exc}") from exc
    if resolved != candidate:
        raise WorkspaceError(
            f"unsafe Palari runtime path {relative}: path is not canonical"
        )
    return candidate


def _atomic_replace_json(path: Path, value: dict[str, Any], *, mode: int) -> None:
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    _atomic_replace_bytes(path, payload, mode=mode)


def _atomic_replace_bytes(
    path: Path,
    payload: bytes,
    *,
    mode: int | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        if mode is not None:
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = ""
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def _safe_git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
    ):
        environment.pop(key, None)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    return environment
