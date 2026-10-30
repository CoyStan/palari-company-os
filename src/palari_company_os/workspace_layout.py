from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
import time
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, overload
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
MAINTAINER_INITIALIZATION_LOCK_FILENAME = "palari-maintainer-initialization.lock"
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
_MAX_PROCESS_ID = 4_194_304
_MALFORMED_LOCK_RECOVERY_SECONDS = 300.0


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


@dataclass(frozen=True)
class _FileWitness:
    device: int
    inode: int
    mode: int
    links: int
    size: int
    digest: str


@dataclass(frozen=True)
class _DirectoryWitness:
    device: int
    inode: int
    mode: int


@dataclass(frozen=True)
class _InitializationLock:
    path: Path
    parent_descriptor: int
    token: str
    witness: _FileWitness
    process_start: str
    payload: bytes


@dataclass(frozen=True)
class _ExcludeAppend:
    witness: _FileWitness
    addition: bytes
    offset: int
    separator_size: int
    created: bool


@dataclass(frozen=True)
class _NewFilePublication:
    path: Path
    parent_descriptor: int
    name: str
    capture: Callable[[_FileWitness], None]


_NEW_FILE_PUBLICATION: ContextVar[_NewFilePublication | None] = ContextVar(
    "palari_maintainer_new_file_publication",
    default=None,
)


@dataclass
class MaintainerInitialization:
    layout: WorkspaceLayout
    exclude_path: Path
    previous_exclude: bytes | None
    repository_id_created: bool
    state_root_created: bool
    expected_head: str
    initialization_lock: _InitializationLock
    repository_root_descriptor: int
    common_directory_descriptor: int
    exclude_directory_descriptor: int
    state_root_descriptor: int | None = None
    runtime_root_descriptor: int | None = None
    locks_root_descriptor: int | None = None
    exclude_append: _ExcludeAppend | None = None
    repository_id_payload: bytes | None = None
    repository_id_witness: _FileWitness | None = None
    binding_payload: bytes | None = None
    binding_file_witness: _FileWitness | None = None
    workspace_payload: bytes | None = None
    workspace_file_witness: _FileWitness | None = None
    journal_projection_digest: str = ""
    journal_file_witness: _FileWitness | None = None
    state_root_witness: _DirectoryWitness | None = None
    runtime_root_witness: _DirectoryWitness | None = None
    locks_root_witness: _DirectoryWitness | None = None
    lock_released: bool = False
    active: bool = True

    def assert_source_unchanged(self) -> None:
        _assert_initialization_source_state(
            self.layout.repository_root,
            self.expected_head,
        )

    def prepare_workspace_outputs(self, data: dict[str, Any]) -> None:
        """Register expected initial outputs before the store can publish them."""

        self.workspace_payload = (
            json.dumps(data, indent=2, sort_keys=False) + "\n"
        ).encode(
            "utf-8"
        )
        self.journal_projection_digest = canonical_sha256(data)
        if self.runtime_root_descriptor is None:
            raise WorkspaceError(
                "maintainer runtime directory is unavailable during initialization"
            )
        workspace_record = _read_regular_file_at(
            self.repository_root_descriptor,
            MAINTAINER_WORKSPACE_FILENAME,
        )
        journal_record = _read_regular_file_at(
            self.runtime_root_descriptor,
            "governance-journal.v2.jsonl",
        )
        if workspace_record is not None or journal_record is not None:
            raise WorkspaceError(
                "maintainer initial workspace outputs appeared before publication"
            )

    def prewrite_check(self) -> None:
        """Bind the journal inode and revalidate source before workspace publish."""

        self.assert_source_unchanged()
        if self.runtime_root_descriptor is None:
            raise WorkspaceError(
                "maintainer runtime directory is unavailable during initialization"
            )
        try:
            record = _read_regular_file_at(
                self.runtime_root_descriptor,
                "governance-journal.v2.jsonl",
            )
        except WorkspaceError as exc:
            raise WorkspaceError(
                "maintainer governance journal changed during initialization"
            ) from exc
        if self.journal_file_witness is None:
            if record is not None:
                raise WorkspaceError(
                    "maintainer initialization journal appeared before publication"
                )
            _publish_new_bytes_at(
                self.runtime_root_descriptor,
                "governance-journal.v2.jsonl",
                b"",
                mode=0o600,
                capture=lambda witness: setattr(
                    self,
                    "journal_file_witness",
                    witness,
                ),
            )
            return
        if (
            record is None
            or not _same_file_identity(
                record[0],
                self.journal_file_witness,
            )
            or (
                record[1]
                and not _initial_journal_matches(
                    record[1],
                    self.journal_projection_digest,
                )
            )
        ):
            raise WorkspaceError(
                "maintainer initialization journal proof is invalid"
            )

    def capture_workspace_publication(self, published: os.stat_result) -> None:
        """Capture the workspace inode inside its no-replace publication helper."""

        if self.workspace_payload is None:
            raise WorkspaceError(
                "maintainer initial workspace output was not registered"
            )
        self.workspace_file_witness = _file_witness_from_stat(
            published,
            self.workspace_payload,
        )

    def capture_workspace_outputs(self) -> None:
        """Validate that publication callbacks captured the exact owned outputs."""

        if self.workspace_payload is None or not self.journal_projection_digest:
            raise WorkspaceError(
                "maintainer initial workspace outputs were not registered"
            )
        if self.workspace_file_witness is None:
            raise WorkspaceError(
                "maintainer workspace publication ownership was not captured"
            )
        witness = _capture_exact_regular_file_at(
            self.repository_root_descriptor,
            MAINTAINER_WORKSPACE_FILENAME,
            self.workspace_payload,
        )
        if witness != self.workspace_file_witness:
            raise WorkspaceError(
                "maintainer workspace changed while initialization was publishing it"
            )
        if self.runtime_root_descriptor is None or self.journal_file_witness is None:
            raise WorkspaceError(
                "maintainer governance journal publication ownership was not captured"
            )
        journal_witness = _capture_initial_journal_at(
            self.runtime_root_descriptor,
            "governance-journal.v2.jsonl",
            self.journal_projection_digest,
        )
        if (
            journal_witness is None
            or not _same_file_identity(
                journal_witness,
                self.journal_file_witness,
            )
        ):
            raise WorkspaceError(
                "maintainer initialization did not publish its governance journal"
            )

    def complete(self) -> WorkspaceLayout:
        if not self.active:
            raise WorkspaceError("maintainer initialization is no longer active")
        self.assert_source_unchanged()
        layout = resolve_workspace_layout(
            self.layout.data_path,
            require_workspace=True,
        )
        _assert_ignored(layout.repository_root)
        self.assert_source_unchanged()
        _release_initialization_lock(self.initialization_lock)
        self.lock_released = True
        self.assert_source_unchanged()
        self.active = False
        self._close_descriptors()
        return layout

    def rollback(self) -> tuple[str, ...]:
        if not self.active:
            return ()
        notes: list[str] = []

        _rollback_owned_file_at(
            self.repository_root_descriptor,
            MAINTAINER_WORKSPACE_FILENAME,
            self.workspace_file_witness,
            "maintainer workspace",
            notes,
            expected_payload=self.workspace_payload,
            report_unowned=True,
        )
        _rollback_owned_journal_at(
            self.runtime_root_descriptor,
            "governance-journal.v2.jsonl",
            self.journal_file_witness,
            self.journal_projection_digest,
            "maintainer governance journal",
            notes,
        )
        _rollback_owned_file_at(
            self.state_root_descriptor,
            MAINTAINER_BINDING_FILENAME,
            self.binding_file_witness,
            "maintainer binding",
            notes,
            expected_payload=self.binding_payload,
            report_unowned=self.binding_payload is not None,
        )
        _rollback_owned_directory_at(
            self.runtime_root_descriptor,
            "locks",
            self.locks_root_witness,
            "maintainer lock directory",
            notes,
        )
        _rollback_owned_directory_at(
            self.state_root_descriptor,
            RUNTIME_ROOT,
            self.runtime_root_witness,
            "maintainer runtime directory",
            notes,
        )
        if self.state_root_created:
            _rollback_owned_directory_at(
                self.repository_root_descriptor,
                MAINTAINER_STATE_ROOT,
                self.state_root_witness,
                "maintainer state directory",
                notes,
            )
        if self.repository_id_created and self.layout.repository_id_path is not None:
            _rollback_owned_file_at(
                self.common_directory_descriptor,
                MAINTAINER_REPOSITORY_ID_FILENAME,
                self.repository_id_witness,
                "maintainer repository identifier",
                notes,
                expected_payload=self.repository_id_payload,
                report_unowned=self.repository_id_payload is not None,
            )
        _rollback_exclude(self, notes)
        if not self.lock_released:
            lock_note = _release_initialization_lock_safely(
                self.initialization_lock
            )
            if lock_note:
                notes.append(lock_note)
        self.active = False
        self._close_descriptors()
        return tuple(notes)

    def _close_descriptors(self) -> None:
        descriptors = (
            self.initialization_lock.parent_descriptor,
            self.locks_root_descriptor,
            self.runtime_root_descriptor,
            self.state_root_descriptor,
            self.exclude_directory_descriptor,
            self.common_directory_descriptor,
            self.repository_root_descriptor,
        )
        self.locks_root_descriptor = None
        self.runtime_root_descriptor = None
        self.state_root_descriptor = None
        for descriptor in descriptors:
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except OSError:
                pass


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
    initialization_lock_path = (
        common_dir / MAINTAINER_INITIALIZATION_LOCK_FILENAME
    )
    _assert_regular_parent(
        initialization_lock_path,
        common_dir,
        "maintainer initialization lock",
    )
    repository_root_descriptor = _open_exact_directory(root)
    common_directory_descriptor = _open_exact_directory(common_dir)
    exclude_directory_descriptor: int | None = None
    try:
        exclude_directory_descriptor = _open_directory_at(
            common_directory_descriptor,
            "info",
            "Git exclude directory",
        )
        initialization_lock = _acquire_initialization_lock(
            initialization_lock_path,
            common_directory_descriptor,
        )
    except Exception:
        for descriptor in (
            exclude_directory_descriptor,
            common_directory_descriptor,
            repository_root_descriptor,
        ):
            if descriptor is not None:
                os.close(descriptor)
        raise
    initialization: MaintainerInitialization | None = None
    try:
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
        dirty = _initialization_dirty_paths(root)
        if dirty:
            raise WorkspaceError(
                "maintainer profile initialization requires a clean Git worktree"
            )
        try:
            head = _git_output(
                root,
                "rev-parse",
                "--verify",
                "HEAD^{commit}",
            )
        except WorkspaceError as exc:
            raise WorkspaceError(
                "maintainer profile initialization requires an exact committed "
                "Git candidate"
            ) from exc
        if not _exact_git_oid(head):
            raise WorkspaceError(
                "maintainer profile initialization requires an exact committed "
                "Git candidate"
            )
        _assert_untracked(root)

        exclude_path = _git_path(root, "info/exclude")
        _assert_regular_parent(exclude_path, common_dir, "Git exclude")
        exclude_record = _read_regular_file_at(
            exclude_directory_descriptor,
            exclude_path.name,
        )
        previous_exclude = (
            exclude_record[1] if exclude_record is not None else None
        )
        repository_id_path = (
            common_dir / MAINTAINER_REPOSITORY_ID_FILENAME
        )
        _assert_regular_parent(
            repository_id_path,
            common_dir,
            "maintainer repository identifier",
        )
        provisional = WorkspaceLayout(
            profile=MAINTAINER_PROFILE,
            repository_root=root,
            data_path=data_path,
            state_root=state_root,
            runtime_root=state_root / RUNTIME_ROOT,
            binding_path=state_root / MAINTAINER_BINDING_FILENAME,
            repository_common_dir=common_dir,
            repository_id_path=repository_id_path,
        )
        initialization = MaintainerInitialization(
            layout=provisional,
            exclude_path=exclude_path,
            previous_exclude=previous_exclude,
            repository_id_created=False,
            state_root_created=state_root_created,
            expected_head=head,
            initialization_lock=initialization_lock,
            repository_root_descriptor=repository_root_descriptor,
            common_directory_descriptor=common_directory_descriptor,
            exclude_directory_descriptor=exclude_directory_descriptor,
        )

        exclude_after = _ignore_rules_payload(previous_exclude)
        if exclude_after != (previous_exclude or b""):
            addition = exclude_after[len(previous_exclude or b"") :]
            _install_ignore_rules(
                exclude_directory_descriptor,
                exclude_path.name,
                exclude_record[0] if exclude_record is not None else None,
                previous_exclude,
                addition,
                capture=lambda owned: setattr(
                    initialization,
                    "exclude_append",
                    owned,
                ),
            )

        repository_id = ""
        repository_id_record = _read_regular_file_at(
            common_directory_descriptor,
            repository_id_path.name,
        )
        if repository_id_record is not None:
            repository_id = _load_repository_id_payload(
                repository_id_record[1]
            )
        else:
            repository_id = str(uuid4())
            initialization.repository_id_created = True
            repository_id_value = {
                "schema_version": MAINTAINER_REPOSITORY_SCHEMA,
                "repository_id": repository_id,
            }
            initialization.repository_id_payload = _json_payload(
                repository_id_value
            )
            _atomic_publish_json(
                repository_id_path,
                repository_id_value,
                mode=0o600,
                parent_descriptor=common_directory_descriptor,
                name=repository_id_path.name,
                capture=lambda witness: setattr(
                    initialization,
                    "repository_id_witness",
                    witness,
                ),
            )
            if initialization.repository_id_witness is None:
                raise WorkspaceError(
                    "maintainer repository identifier ownership was not captured"
                )
        _assert_ignored(root)

        (
            initialization.state_root_descriptor,
            initialization.state_root_witness,
            state_root_was_created,
        ) = _open_or_create_directory_at(
            repository_root_descriptor,
            MAINTAINER_STATE_ROOT,
            "maintainer state directory",
            allow_existing=not state_root_created,
        )
        if state_root_was_created != state_root_created:
            raise WorkspaceError(
                "maintainer state root changed while initialization was creating it"
            )
        (
            initialization.runtime_root_descriptor,
            initialization.runtime_root_witness,
            runtime_created,
        ) = _open_or_create_directory_at(
            initialization.state_root_descriptor,
            RUNTIME_ROOT,
            "maintainer runtime directory",
            allow_existing=False,
        )
        if not runtime_created:
            raise WorkspaceError(
                "maintainer runtime directory appeared during initialization"
            )
        (
            initialization.locks_root_descriptor,
            initialization.locks_root_witness,
            locks_created,
        ) = _open_or_create_directory_at(
            initialization.runtime_root_descriptor,
            "locks",
            "maintainer lock directory",
            allow_existing=False,
        )
        if not locks_created:
            raise WorkspaceError(
                "maintainer lock directory appeared during initialization"
            )
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
        initialization.binding_payload = _json_payload(binding)
        _atomic_publish_json(
            binding_path,
            binding,
            mode=0o600,
            parent_descriptor=initialization.state_root_descriptor,
            name=MAINTAINER_BINDING_FILENAME,
            capture=lambda witness: setattr(
                initialization,
                "binding_file_witness",
                witness,
            ),
        )
        if initialization.binding_file_witness is None:
            raise WorkspaceError(
                "maintainer binding ownership was not captured"
            )
        layout = _resolve_maintainer_layout(
            data_path,
            require_workspace=False,
        )
        initialization.layout = layout
        initialization.assert_source_unchanged()
        return initialization
    except Exception as exc:
        notes: tuple[str, ...]
        if initialization is None:
            note = _release_initialization_lock_safely(
                initialization_lock
            )
            notes = (note,) if note else ()
            try:
                os.close(initialization_lock.parent_descriptor)
            except OSError:
                pass
            for descriptor in (
                exclude_directory_descriptor,
                common_directory_descriptor,
                repository_root_descriptor,
            ):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        else:
            notes = initialization.rollback()
        if notes:
            _add_exception_note(
                exc,
                "Maintainer initialization cleanup preserved concurrent changes: "
                + "; ".join(notes),
            )
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


def _load_repository_id_payload(raw: bytes) -> str:
    try:
        value = strict_json_loads(raw)
    except (CanonicalJSONError, TypeError) as exc:
        raise WorkspaceError(
            f"maintainer repository identifier is unreadable: {exc}"
        ) from exc
    if not isinstance(value, dict) or set(value) != _REPOSITORY_ID_FIELDS:
        raise WorkspaceError("maintainer repository identifier has an invalid format")
    if value.get("schema_version") != MAINTAINER_REPOSITORY_SCHEMA:
        raise WorkspaceError("maintainer repository identifier schema is unsupported")
    repository_id = value.get("repository_id")
    _validate_uuid4(repository_id, "maintainer repository identifier")
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
        detail = result.stderr.strip()
        suffix = f": {detail}" if detail else ""
        raise WorkspaceError(
            "cannot inspect maintainer Git repository"
            f" (git {' '.join(arguments)} exited {result.returncode}){suffix}"
        )
    return result.stdout.strip()


def _git_status(root: Path) -> list[str]:
    raw = _git_output(
        root,
        "status",
        "--porcelain",
        "--untracked-files=all",
    )
    return raw.splitlines() if raw else []


def _initialization_dirty_paths(root: Path) -> list[str]:
    return [
        entry
        for entry in _git_status(root)
        if entry
        != f"?? {MAINTAINER_STATE_ROOT}/{MAINTAINER_STATUS_FILENAME}"
    ]


def _assert_initialization_source_state(
    root: Path,
    expected_head: str,
) -> None:
    current_head = _git_output(
        root,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
    )
    if current_head != expected_head:
        raise WorkspaceError(
            "maintainer initialization source Git HEAD changed; retry from the "
            "current clean candidate"
        )
    if _initialization_dirty_paths(root):
        raise WorkspaceError(
            "maintainer initialization source Git status changed; retry from a "
            "clean candidate"
        )
    _assert_untracked(root)


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


def _validate_initial_state_root_at(descriptor: int) -> None:
    try:
        entries = os.listdir(descriptor)
    except OSError as exc:
        raise WorkspaceError(
            f"maintainer state root is unavailable: {exc}"
        ) from exc
    for name in entries:
        try:
            metadata = os.stat(
                name,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise WorkspaceError(
                "maintainer state root changed while it was inspected"
            ) from exc
        if (
            name != MAINTAINER_STATUS_FILENAME
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
        ):
            raise WorkspaceError(
                "maintainer state root already exists or conflicts: "
                + name
            )


def _ignore_rules_payload(current: bytes | None) -> bytes:
    payload = current or b""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceError("Git exclude file is not UTF-8") from exc
    existing = set(text.splitlines())
    missing = [rule for rule in _IGNORE_RULES if rule not in existing]
    if not missing:
        return payload
    prefix = "" if not text or text.endswith("\n") else "\n"
    addition = (
        prefix
        + "# Palari maintainer profile local state\n"
        + "\n".join(missing)
        + "\n"
    )
    return payload + addition.encode("utf-8")


def _install_ignore_rules(
    parent_descriptor: int,
    name: str,
    expected_witness: _FileWitness | None,
    expected_payload: bytes | None,
    addition: bytes,
    *,
    capture: Callable[[_ExcludeAppend], None],
) -> None:
    if not addition:
        return
    if expected_payload is None:
        witness = _publish_new_bytes_at(
            parent_descriptor,
            name,
            addition,
            mode=0o600,
        )
        owned = _ExcludeAppend(
            witness=witness,
            addition=addition,
            offset=0,
            separator_size=0,
            created=True,
        )
        capture(owned)
        return
    flags = os.O_RDWR | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(
            name,
            flags,
            dir_fd=parent_descriptor,
        )
    except OSError as exc:
        raise WorkspaceError(f"Git exclude cannot be appended safely: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            expected_witness is None
            or not _same_file_identity(
                _file_witness_from_stat(opened, expected_payload),
                expected_witness,
            )
        ):
            raise WorkspaceError(
                "Git exclude changed while maintainer initialization was preparing it"
            )
        os.lseek(descriptor, 0, os.SEEK_SET)
        before = _read_descriptor_bytes(descriptor)
        if before != expected_payload:
            raise WorkspaceError(
                "Git exclude changed while maintainer initialization was preparing it"
            )
        written = os.write(descriptor, addition)
        if written != len(addition):
            raise WorkspaceError(
                "Git exclude append was incomplete; cleanup will preserve uncertainty"
            )
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        after = _read_descriptor_bytes(descriptor)
        metadata = os.fstat(descriptor)
        entry_stat = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    finally:
        os.close(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (
            metadata.st_dev,
            metadata.st_ino,
        )
        != (entry_stat.st_dev, entry_stat.st_ino)
    ):
        raise WorkspaceError(
            "Git exclude changed while maintainer ignore rules were installed"
        )
    offsets = _all_offsets(after, addition, start=len(expected_payload))
    if not after.startswith(expected_payload) or len(offsets) != 1:
        raise WorkspaceError(
            "Git exclude append ownership could not be determined safely"
        )
    owned = _ExcludeAppend(
        witness=_file_witness_from_stat(metadata, after),
        addition=addition,
        offset=offsets[0],
        separator_size=(
            1
            if expected_payload
            and not expected_payload.endswith((b"\n", b"\r"))
            and addition.startswith(b"\n")
            else 0
        ),
        created=False,
    )
    capture(owned)
    _fsync_directory_descriptor(parent_descriptor)


def _read_descriptor_bytes(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _all_offsets(payload: bytes, needle: bytes, *, start: int = 0) -> list[int]:
    offsets: list[int] = []
    cursor = start
    while True:
        offset = payload.find(needle, cursor)
        if offset < 0:
            return offsets
        offsets.append(offset)
        cursor = offset + 1


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


def _json_payload(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _file_witness_from_stat(
    metadata: os.stat_result,
    payload: bytes,
) -> _FileWitness:
    return _FileWitness(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=metadata.st_mode,
        links=metadata.st_nlink,
        size=len(payload),
        digest=hashlib.sha256(payload).hexdigest(),
    )


def _same_file_identity(left: _FileWitness, right: _FileWitness) -> bool:
    return (
        left.device,
        left.inode,
        stat.S_IFMT(left.mode),
    ) == (
        right.device,
        right.inode,
        stat.S_IFMT(right.mode),
    )


def _open_exact_directory(path: Path) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        descriptor_stat = os.fstat(descriptor)
        path_stat = path.lstat()
    except OSError as exc:
        if "descriptor" in locals():
            os.close(descriptor)
        raise WorkspaceError(f"cannot open exact directory {path}: {exc}") from exc
    if (
        not stat.S_ISDIR(descriptor_stat.st_mode)
        or (
            descriptor_stat.st_dev,
            descriptor_stat.st_ino,
        )
        != (path_stat.st_dev, path_stat.st_ino)
    ):
        os.close(descriptor)
        raise WorkspaceError(f"exact directory changed while opened: {path}")
    return descriptor


def _open_directory_at(
    parent_descriptor: int,
    name: str,
    label: str,
) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
        descriptor_stat = os.fstat(descriptor)
        entry_stat = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        if "descriptor" in locals():
            os.close(descriptor)
        raise WorkspaceError(f"{label} is unavailable: {exc}") from exc
    if (
        not stat.S_ISDIR(descriptor_stat.st_mode)
        or (
            descriptor_stat.st_dev,
            descriptor_stat.st_ino,
        )
        != (entry_stat.st_dev, entry_stat.st_ino)
    ):
        os.close(descriptor)
        raise WorkspaceError(f"{label} changed while it was opened")
    return descriptor


def _open_or_create_directory_at(
    parent_descriptor: int,
    name: str,
    label: str,
    *,
    allow_existing: bool,
) -> tuple[int, _DirectoryWitness, bool]:
    created = False
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
        created = True
        os.fsync(parent_descriptor)
    except FileExistsError:
        if not allow_existing:
            raise WorkspaceError(f"{label} already exists or conflicts")
    except OSError as exc:
        raise WorkspaceError(f"cannot create {label}: {exc}") from exc
    descriptor = _open_directory_at(parent_descriptor, name, label)
    metadata = os.fstat(descriptor)
    witness = _DirectoryWitness(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=metadata.st_mode,
    )
    if not created and label == "maintainer state directory":
        _validate_initial_state_root_at(descriptor)
    return descriptor, witness, created


def _read_regular_file_at(
    parent_descriptor: int,
    name: str,
) -> tuple[_FileWitness, bytes] | None:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WorkspaceError(f"cannot inspect exact file {name}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise WorkspaceError(
                f"exact file must be one unaliased regular file: {name}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        entry_stat = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError as exc:
        raise WorkspaceError(f"exact file changed while inspected: {name}") from exc
    finally:
        os.close(descriptor)
    identity = (before.st_dev, before.st_ino, before.st_mode, before.st_nlink)
    if identity != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
    ) or identity != (
        entry_stat.st_dev,
        entry_stat.st_ino,
        entry_stat.st_mode,
        entry_stat.st_nlink,
    ):
        raise WorkspaceError(f"exact file changed while inspected: {name}")
    payload = b"".join(chunks)
    return _file_witness_from_stat(before, payload), payload


def _read_regular_file(path: Path) -> tuple[_FileWitness, bytes] | None:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WorkspaceError(f"cannot inspect exact file {path}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise WorkspaceError(
                f"exact file must be one unaliased regular file: {path}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        path_stat = path.lstat()
    except OSError as exc:
        raise WorkspaceError(f"exact file changed while inspected: {path}") from exc
    identity = (before.st_dev, before.st_ino, before.st_mode, before.st_nlink)
    if identity != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
    ) or identity != (
        path_stat.st_dev,
        path_stat.st_ino,
        path_stat.st_mode,
        path_stat.st_nlink,
    ):
        raise WorkspaceError(f"exact file changed while inspected: {path}")
    payload = b"".join(chunks)
    return (
        _FileWitness(
            device=before.st_dev,
            inode=before.st_ino,
            mode=before.st_mode,
            links=before.st_nlink,
            size=len(payload),
            digest=hashlib.sha256(payload).hexdigest(),
        ),
        payload,
    )


def _capture_exact_regular_file(
    path: Path,
    expected: bytes,
) -> _FileWitness | None:
    try:
        record = _read_regular_file(path)
    except WorkspaceError:
        return None
    if record is None or record[1] != expected:
        return None
    return record[0]


def _capture_exact_regular_file_at(
    parent_descriptor: int,
    name: str,
    expected: bytes,
) -> _FileWitness | None:
    try:
        record = _read_regular_file_at(parent_descriptor, name)
    except WorkspaceError:
        return None
    if record is None or record[1] != expected:
        return None
    return record[0]


def _capture_initial_journal(
    path: Path,
    expected_projection_digest: str,
) -> _FileWitness | None:
    try:
        record = _read_regular_file(path)
    except WorkspaceError:
        return None
    if record is None:
        return None
    lines = record[1].splitlines()
    if len(lines) not in {1, 2}:
        return None
    try:
        parsed = [strict_json_loads(line) for line in lines]
    except (CanonicalJSONError, TypeError):
        return None
    if not all(isinstance(item, dict) for item in parsed):
        return None
    prepared = parsed[0]
    if (
        prepared.get("schema_version") != "palari.governance-journal.v2"
        or prepared.get("record_type") != "prepare"
        or prepared.get("sequence") != 0
        or prepared.get("event_kind") != "checkpoint"
        or prepared.get("coverage") != "complete"
        or prepared.get("before_workspace_digest") is not None
        or prepared.get("expected_before_workspace_digest") is not None
        or prepared.get("after_workspace_digest")
        != expected_projection_digest
    ):
        return None
    projection = prepared.get("checkpoint_projection")
    try:
        projection_digest = canonical_sha256(projection)
    except CanonicalJSONError:
        return None
    if projection_digest != expected_projection_digest:
        return None
    if len(parsed) == 2:
        terminal = parsed[1]
        if (
            terminal.get("schema_version") != "palari.governance-journal.v2"
            or terminal.get("record_type") not in {"commit", "abort"}
            or terminal.get("sequence") != 1
            or terminal.get("transaction_id")
            != prepared.get("transaction_id")
            or terminal.get("prepared_record_digest")
            != prepared.get("record_digest")
        ):
            return None
    return record[0]


def _capture_initial_journal_at(
    parent_descriptor: int,
    name: str,
    expected_projection_digest: str,
) -> _FileWitness | None:
    try:
        record = _read_regular_file_at(parent_descriptor, name)
    except WorkspaceError:
        return None
    if record is None or not _initial_journal_matches(
        record[1],
        expected_projection_digest,
    ):
        return None
    return record[0]


def _initial_journal_matches(
    payload: bytes,
    expected_projection_digest: str,
) -> bool:
    lines = payload.splitlines()
    if len(lines) not in {1, 2}:
        return False
    try:
        parsed = [strict_json_loads(line) for line in lines]
    except (CanonicalJSONError, TypeError):
        return False
    if not all(isinstance(item, dict) for item in parsed):
        return False
    prepared = parsed[0]
    if (
        prepared.get("schema_version") != "palari.governance-journal.v2"
        or prepared.get("record_type") != "prepare"
        or prepared.get("sequence") != 0
        or prepared.get("event_kind") != "checkpoint"
        or prepared.get("coverage") != "complete"
        or prepared.get("before_workspace_digest") is not None
        or prepared.get("expected_before_workspace_digest") is not None
        or prepared.get("after_workspace_digest")
        != expected_projection_digest
    ):
        return False
    try:
        projection_digest = canonical_sha256(
            prepared.get("checkpoint_projection")
        )
    except CanonicalJSONError:
        return False
    if projection_digest != expected_projection_digest:
        return False
    if len(parsed) == 2:
        terminal = parsed[1]
        if (
            terminal.get("schema_version") != "palari.governance-journal.v2"
            or terminal.get("record_type") not in {"commit", "abort"}
            or terminal.get("sequence") != 1
            or terminal.get("transaction_id")
            != prepared.get("transaction_id")
            or terminal.get("prepared_record_digest")
            != prepared.get("record_digest")
        ):
            return False
    return True


def _directory_witness(path: Path) -> _DirectoryWitness:
    try:
        path_stat = path.lstat()
    except OSError as exc:
        raise WorkspaceError(f"cannot inspect exact directory {path}: {exc}") from exc
    if not stat.S_ISDIR(path_stat.st_mode):
        raise WorkspaceError(f"exact directory must be a real directory: {path}")
    return _DirectoryWitness(
        device=path_stat.st_dev,
        inode=path_stat.st_ino,
        mode=path_stat.st_mode,
    )


def _directory_matches(path: Path, expected: _DirectoryWitness) -> bool:
    try:
        return _directory_witness(path) == expected
    except WorkspaceError:
        return False


def _path_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory_descriptor(descriptor: int) -> None:
    try:
        os.fsync(descriptor)
    except OSError as exc:
        raise WorkspaceError(f"cannot durably update exact directory: {exc}") from exc


def _restore_quarantined_entry_at(
    parent_descriptor: int,
    quarantine_name: str,
    name: str,
) -> bool:
    try:
        os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        try:
            os.rename(
                quarantine_name,
                name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
            )
            _fsync_directory_descriptor(parent_descriptor)
            return True
        except OSError:
            return False
    except OSError:
        return False
    return False


def _detach_regular_entry_at(
    parent_descriptor: int,
    name: str,
    expected: _FileWitness,
    validator: Callable[[bytes], bool],
) -> tuple[str, _FileWitness, bytes] | None:
    try:
        preliminary = _read_regular_file_at(parent_descriptor, name)
    except WorkspaceError:
        return None
    if (
        preliminary is None
        or not _same_file_identity(preliminary[0], expected)
        or not validator(preliminary[1])
    ):
        return None
    quarantine_name = f".{name}.palari-rollback-{uuid4().hex}"
    try:
        os.rename(
            name,
            quarantine_name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
    except OSError:
        return None
    try:
        captured = _read_regular_file_at(parent_descriptor, quarantine_name)
    except WorkspaceError:
        captured = None
    if (
        captured is None
        or not _same_file_identity(captured[0], expected)
        or not validator(captured[1])
    ):
        _restore_quarantined_entry_at(
            parent_descriptor,
            quarantine_name,
            name,
        )
        return None
    return quarantine_name, captured[0], captured[1]


def _unlink_quarantined_file_at(
    parent_descriptor: int,
    quarantine_name: str,
    expected: _FileWitness,
    expected_payload: bytes,
) -> bool:
    try:
        current = _read_regular_file_at(parent_descriptor, quarantine_name)
    except WorkspaceError:
        return False
    if (
        current is None
        or current[0] != expected
        or current[1] != expected_payload
    ):
        return False
    try:
        os.unlink(quarantine_name, dir_fd=parent_descriptor)
        _fsync_directory_descriptor(parent_descriptor)
    except OSError:
        return False
    return True


def _rollback_owned_file_at(
    parent_descriptor: int | None,
    name: str,
    expected: _FileWitness | None,
    label: str,
    notes: list[str],
    *,
    expected_payload: bytes | None,
    report_unowned: bool,
) -> None:
    if parent_descriptor is None:
        if report_unowned:
            notes.append(f"{label} parent identity is unavailable; state was preserved")
        return
    try:
        current = _read_regular_file_at(parent_descriptor, name)
    except WorkspaceError:
        current = None
    if current is None:
        return
    if expected is None or expected_payload is None:
        if report_unowned:
            notes.append(f"{label} was replaced or could not be owned")
        return
    detached = _detach_regular_entry_at(
        parent_descriptor,
        name,
        expected,
        lambda payload: payload == expected_payload,
    )
    if detached is None:
        notes.append(f"{label} changed concurrently and was preserved")
        return
    quarantine_name, captured_witness, captured_payload = detached
    if not _unlink_quarantined_file_at(
        parent_descriptor,
        quarantine_name,
        captured_witness,
        captured_payload,
    ):
        if not _restore_quarantined_entry_at(
            parent_descriptor,
            quarantine_name,
            name,
        ):
            notes.append(
                f"{label} changed during cleanup and was preserved as "
                f"{quarantine_name}"
            )


def _rollback_owned_journal_at(
    parent_descriptor: int | None,
    name: str,
    expected: _FileWitness | None,
    expected_projection_digest: str,
    label: str,
    notes: list[str],
) -> None:
    if parent_descriptor is None or expected is None:
        return
    detached = _detach_regular_entry_at(
        parent_descriptor,
        name,
        expected,
        lambda payload: not payload
        or _initial_journal_matches(
            payload,
            expected_projection_digest,
        ),
    )
    if detached is None:
        try:
            current = _read_regular_file_at(parent_descriptor, name)
        except WorkspaceError:
            current = None
        if current is not None:
            notes.append(f"{label} changed concurrently and was preserved")
        return
    quarantine_name, captured_witness, captured_payload = detached
    if not _unlink_quarantined_file_at(
        parent_descriptor,
        quarantine_name,
        captured_witness,
        captured_payload,
    ):
        if not _restore_quarantined_entry_at(
            parent_descriptor,
            quarantine_name,
            name,
        ):
            notes.append(
                f"{label} changed during cleanup and was preserved as "
                f"{quarantine_name}"
            )


def _rollback_owned_directory_at(
    parent_descriptor: int | None,
    name: str,
    expected: _DirectoryWitness | None,
    label: str,
    notes: list[str],
) -> None:
    if parent_descriptor is None or expected is None:
        return
    try:
        current = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    except OSError:
        notes.append(f"{label} identity is uncertain and was preserved")
        return
    if (
        current.st_dev,
        current.st_ino,
        current.st_mode,
    ) != (expected.device, expected.inode, expected.mode):
        notes.append(f"{label} changed concurrently and was preserved")
        return
    quarantine_name = f".{name}.palari-rollback-{uuid4().hex}"
    try:
        os.rename(
            name,
            quarantine_name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        captured = os.stat(
            quarantine_name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError:
        return
    if (
        captured.st_dev,
        captured.st_ino,
        captured.st_mode,
    ) != (expected.device, expected.inode, expected.mode):
        _restore_quarantined_entry_at(
            parent_descriptor,
            quarantine_name,
            name,
        )
        notes.append(f"{label} changed during cleanup and was preserved")
        return
    try:
        os.rmdir(quarantine_name, dir_fd=parent_descriptor)
        _fsync_directory_descriptor(parent_descriptor)
    except OSError:
        restored = _restore_quarantined_entry_at(
            parent_descriptor,
            quarantine_name,
            name,
        )
        if restored:
            notes.append(
                f"{label} contains concurrent or residual state and was preserved"
            )
        else:
            notes.append(
                f"{label} contains concurrent or residual state and was preserved "
                f"as {quarantine_name}"
            )


def _unlink_if_witness(path: Path, expected: _FileWitness) -> bool:
    try:
        record = _read_regular_file(path)
    except WorkspaceError:
        return False
    if record is None:
        return True
    if record[0] != expected:
        return False
    try:
        path.unlink()
        _fsync_directory(path.parent)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def _rollback_owned_file(
    path: Path,
    expected: _FileWitness | None,
    label: str,
    notes: list[str],
    *,
    report_unowned: bool,
) -> None:
    if not _path_exists(path):
        return
    if expected is None:
        if report_unowned:
            notes.append(f"{label} was replaced or could not be owned at {path}")
        return
    if not _unlink_if_witness(path, expected):
        notes.append(f"{label} changed concurrently and was preserved at {path}")


def _rollback_owned_directory(
    path: Path,
    expected: _DirectoryWitness | None,
    label: str,
    notes: list[str],
) -> None:
    if expected is None or not _path_exists(path):
        return
    if not _directory_matches(path, expected):
        notes.append(f"{label} changed concurrently and was preserved at {path}")
        return
    try:
        path.rmdir()
        _fsync_directory(path.parent)
    except FileNotFoundError:
        return
    except OSError:
        notes.append(
            f"{label} contains concurrent or residual state and was preserved at {path}"
        )


def _replace_if_witness(
    path: Path,
    expected: _FileWitness,
    payload: bytes | None,
) -> bool:
    try:
        record = _read_regular_file(path)
    except WorkspaceError:
        return False
    if record is None or record[0] != expected:
        return False
    try:
        if payload is None:
            path.unlink()
            _fsync_directory(path.parent)
        else:
            _atomic_replace_bytes(path, payload)
    except OSError:
        return False
    return True


def _rollback_exclude(
    initialization: MaintainerInitialization,
    notes: list[str],
) -> None:
    owned = initialization.exclude_append
    if owned is None:
        return
    parent_descriptor = initialization.exclude_directory_descriptor

    def owns_append(payload: bytes) -> bool:
        end = owned.offset + len(owned.addition)
        return (
            end <= len(payload)
            and payload[owned.offset:end] == owned.addition
        )

    detached = _detach_regular_entry_at(
        parent_descriptor,
        initialization.exclude_path.name,
        owned.witness,
        owns_append,
    )
    if detached is None:
        try:
            current_record = _read_regular_file_at(
                parent_descriptor,
                initialization.exclude_path.name,
            )
        except WorkspaceError:
            current_record = None
        if current_record is not None:
            notes.append(
                "Git exclude changed concurrently and its current state was preserved "
                f"at {initialization.exclude_path}"
            )
        return
    quarantine_name, quarantine_witness, current_payload = detached
    end = owned.offset + len(owned.addition)
    prefix = current_payload[: owned.offset]
    suffix = current_payload[end:]
    shared_separator = (
        owned.addition[: owned.separator_size]
        if suffix and owned.separator_size
        else b""
    )
    replacement = prefix + shared_separator + suffix
    replacement_witness: _FileWitness | None = None
    if replacement or not owned.created:
        try:
            replacement_witness = _publish_new_bytes_at(
                parent_descriptor,
                initialization.exclude_path.name,
                replacement,
                mode=stat.S_IMODE(quarantine_witness.mode),
            )
        except Exception:
            _restore_quarantined_entry_at(
                parent_descriptor,
                quarantine_name,
                initialization.exclude_path.name,
            )
            notes.append(
                "Git exclude changed during rollback and was preserved at "
                f"{initialization.exclude_path}"
            )
            return
    try:
        rechecked = _read_regular_file_at(
            parent_descriptor,
            quarantine_name,
        )
    except WorkspaceError:
        rechecked = None
    if (
        rechecked is None
        or rechecked[0] != quarantine_witness
        or rechecked[1] != current_payload
    ):
        if replacement_witness is not None:
            _rollback_owned_file_at(
                parent_descriptor,
                initialization.exclude_path.name,
                replacement_witness,
                "Git exclude rollback replacement",
                notes,
                expected_payload=replacement,
                report_unowned=True,
            )
        _restore_quarantined_entry_at(
            parent_descriptor,
            quarantine_name,
            initialization.exclude_path.name,
        )
        notes.append(
            "Git exclude changed during rollback and was preserved "
            f"at {initialization.exclude_path}"
        )
        return
    if not _unlink_quarantined_file_at(
        parent_descriptor,
        quarantine_name,
        quarantine_witness,
        current_payload,
    ):
        notes.append(
            "Git exclude changed during rollback and was preserved at "
            f"{initialization.exclude_path}"
        )


def _initialization_lock_record(
    payload: bytes,
) -> tuple[int, str, int, str] | None:
    try:
        value = strict_json_loads(payload)
    except (CanonicalJSONError, TypeError):
        return None
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "pid",
        "process_start",
        "created_unix_seconds",
        "token",
    }:
        return None
    if value.get("schema_version") != "palari.maintainer-init-lock.v1":
        return None
    pid = value.get("pid")
    process_start = value.get("process_start")
    created_unix_seconds = value.get("created_unix_seconds")
    token = value.get("token")
    if (
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or not 0 < pid <= _MAX_PROCESS_ID
        or not isinstance(process_start, str)
        or not process_start
        or not isinstance(created_unix_seconds, int)
        or isinstance(created_unix_seconds, bool)
        or created_unix_seconds <= 0
        or not isinstance(token, str)
        or len(token) != 32
        or any(character not in "0123456789abcdef" for character in token)
    ):
        return None
    return pid, process_start, created_unix_seconds, token


def _process_start_witness(pid: int) -> str | None:
    if not 0 < pid <= _MAX_PROCESS_ID:
        return None
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    closing = raw.rfind(")")
    if closing < 0:
        return None
    fields = raw[closing + 1 :].split()
    if len(fields) <= 19 or not fields[19].isdigit():
        return None
    return fields[19]


def _pid_is_alive(pid: int) -> bool:
    if not 0 < pid <= _MAX_PROCESS_ID:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OverflowError, ValueError):
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _same_live_process(pid: int, expected_start: str) -> bool:
    if not _pid_is_alive(pid):
        return False
    current_start = _process_start_witness(pid)
    return current_start is None or current_start == expected_start


def _lock_old_enough_for_malformed_recovery(
    parent_descriptor: int,
    name: str,
) -> bool:
    try:
        metadata = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError:
        return False
    age_seconds = max(0.0, (time.time_ns() - metadata.st_mtime_ns) / 1e9)
    return age_seconds >= _MALFORMED_LOCK_RECOVERY_SECONDS


def _remove_exact_regular_file_at(
    parent_descriptor: int,
    name: str,
    expected: _FileWitness,
    payload: bytes,
) -> bool:
    detached = _detach_regular_entry_at(
        parent_descriptor,
        name,
        expected,
        lambda current: current == payload,
    )
    if detached is None:
        return False
    quarantine_name, witness, captured = detached
    if _unlink_quarantined_file_at(
        parent_descriptor,
        quarantine_name,
        witness,
        captured,
    ):
        return True
    _restore_quarantined_entry_at(
        parent_descriptor,
        quarantine_name,
        name,
    )
    return False


def _create_initialization_lock(
    path: Path,
    parent_descriptor: int,
    payload: bytes,
) -> _FileWitness:
    try:
        return _publish_new_bytes_at(
            parent_descriptor,
            path.name,
            payload,
            mode=0o600,
        )
    except FileExistsError:
        raise
    except OSError as exc:
        raise WorkspaceError(
            f"cannot create maintainer initialization lock: {exc}"
        ) from exc


def _acquire_initialization_lock(
    path: Path,
    parent_descriptor: int,
) -> _InitializationLock:
    token = uuid4().hex
    pid = os.getpid()
    process_start = _process_start_witness(pid)
    if process_start is None:
        raise WorkspaceError(
            "cannot capture the current process start for maintainer initialization"
        )
    payload = _json_payload(
        {
            "schema_version": "palari.maintainer-init-lock.v1",
            "pid": pid,
            "process_start": process_start,
            "created_unix_seconds": time.time_ns() // 1_000_000_000,
            "token": token,
        }
    )
    for attempt in range(2):
        try:
            witness = _create_initialization_lock(
                path,
                parent_descriptor,
                payload,
            )
        except FileExistsError as exc:
            try:
                current = _read_regular_file_at(
                    parent_descriptor,
                    path.name,
                )
            except WorkspaceError:
                current = None
            if current is None or attempt > 0:
                raise WorkspaceError(
                    "maintainer initialization is already in progress; retry shortly"
                ) from exc
            record = _initialization_lock_record(current[1])
            reclaimable = (
                (
                    record is not None
                    and not _same_live_process(record[0], record[1])
                )
                or (
                    record is None
                    and _lock_old_enough_for_malformed_recovery(
                        parent_descriptor,
                        path.name,
                    )
                )
            )
            if not reclaimable or not _remove_exact_regular_file_at(
                parent_descriptor,
                path.name,
                current[0],
                current[1],
            ):
                raise WorkspaceError(
                    "maintainer initialization is already in progress; retry shortly"
                ) from exc
            continue
        return _InitializationLock(
            path=path,
            parent_descriptor=os.dup(parent_descriptor),
            token=token,
            witness=witness,
            process_start=process_start,
            payload=payload,
        )
    raise WorkspaceError(
        "maintainer initialization is already in progress; retry shortly"
    )


def _release_initialization_lock(lock: _InitializationLock) -> None:
    record = _read_regular_file_at(
        lock.parent_descriptor,
        lock.path.name,
    )
    parsed = (
        _initialization_lock_record(record[1])
        if record is not None
        else None
    )
    if (
        record is None
        or record[0] != lock.witness
        or record[1] != lock.payload
        or parsed is None
        or parsed[1] != lock.process_start
        or parsed[3] != lock.token
        or not _remove_exact_regular_file_at(
            lock.parent_descriptor,
            lock.path.name,
            lock.witness,
            lock.payload,
        )
    ):
        raise WorkspaceError(
            "maintainer initialization lock ownership changed before release"
        )


def _release_initialization_lock_safely(
    lock: _InitializationLock,
) -> str:
    try:
        _release_initialization_lock(lock)
    except WorkspaceError as exc:
        return str(exc)
    return ""


def _add_exception_note(error: BaseException, note: str) -> None:
    add_note = getattr(error, "add_note", None)
    if callable(add_note):
        add_note(note)
        return
    existing = list(getattr(error, "__notes__", ()))
    existing.append(note)
    setattr(error, "__notes__", existing)


def _publish_new_bytes_at(
    parent_descriptor: int,
    name: str,
    payload: bytes,
    *,
    mode: int,
    capture: Callable[[_FileWitness], None] | None = None,
) -> _FileWitness:
    stage_name = f".{name}.palari-stage-{uuid4().hex}"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(
        stage_name,
        flags,
        mode,
        dir_fd=parent_descriptor,
    )
    stage_witness: _FileWitness | None = None
    linked_witness: _FileWitness | None = None
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write while staging a new file")
            view = view[written:]
        os.fsync(descriptor)
        stage_metadata = os.fstat(descriptor)
        stage_witness = _file_witness_from_stat(stage_metadata, payload)
        os.link(
            stage_name,
            name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        linked_metadata = os.fstat(descriptor)
        linked_witness = _file_witness_from_stat(linked_metadata, payload)
        if capture is not None:
            capture(linked_witness)
        if not _retire_staging_entry_at(
            parent_descriptor,
            stage_name,
            descriptor,
        ):
            raise WorkspaceError(
                f"cannot retire staging inode after publishing exact file {name}"
            )
        final = _read_regular_file_at(parent_descriptor, name)
        if (
            final is None
            or final[1] != payload
            or not _same_file_identity(final[0], linked_witness)
            or final[0].links != 1
        ):
            raise WorkspaceError(
                f"new exact file changed while it was published: {name}"
            )
        if capture is not None:
            capture(final[0])
        _fsync_directory_descriptor(parent_descriptor)
        return final[0]
    except Exception:
        if stage_witness is not None:
            _retire_staging_entry_at(
                parent_descriptor,
                stage_name,
                descriptor,
            )
        if linked_witness is not None:
            _remove_exact_regular_file_at(
                parent_descriptor,
                name,
                linked_witness,
                payload,
            )
        raise
    finally:
        os.close(descriptor)


def _retire_staging_entry_at(
    parent_descriptor: int,
    name: str,
    file_descriptor: int,
) -> bool:
    try:
        expected = os.fstat(file_descriptor)
        current = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError:
        return False
    if (
        current.st_dev,
        current.st_ino,
        stat.S_IFMT(current.st_mode),
    ) != (
        expected.st_dev,
        expected.st_ino,
        stat.S_IFMT(expected.st_mode),
    ):
        return False
    quarantine_name = f".{name}.retire-{uuid4().hex}"
    try:
        os.rename(
            name,
            quarantine_name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        captured = os.stat(
            quarantine_name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError:
        return False
    if (
        captured.st_dev,
        captured.st_ino,
        stat.S_IFMT(captured.st_mode),
    ) != (
        expected.st_dev,
        expected.st_ino,
        stat.S_IFMT(expected.st_mode),
    ):
        _restore_quarantined_entry_at(
            parent_descriptor,
            quarantine_name,
            name,
        )
        return False
    try:
        os.unlink(quarantine_name, dir_fd=parent_descriptor)
        return True
    except OSError:
        _restore_quarantined_entry_at(
            parent_descriptor,
            quarantine_name,
            name,
        )
        return False


def _atomic_publish_json(
    path: Path,
    value: dict[str, Any],
    *,
    mode: int,
    parent_descriptor: int,
    name: str,
    capture: Callable[[_FileWitness], None],
) -> None:
    publication = _NewFilePublication(
        path=path,
        parent_descriptor=parent_descriptor,
        name=name,
        capture=capture,
    )
    token = _NEW_FILE_PUBLICATION.set(publication)
    try:
        _atomic_replace_json(path, value, mode=mode)
    finally:
        _NEW_FILE_PUBLICATION.reset(token)


def _atomic_replace_json(path: Path, value: dict[str, Any], *, mode: int) -> None:
    payload = _json_payload(value)
    publication = _NEW_FILE_PUBLICATION.get()
    if publication is not None and publication.path == path:
        _publish_new_bytes_at(
            publication.parent_descriptor,
            publication.name,
            payload,
            mode=mode,
            capture=publication.capture,
        )
        return
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
