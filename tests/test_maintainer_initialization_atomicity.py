from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.maintainer_profile_fixture import create_git_repository, git

import palari_company_os.onramp as onramp_module
import palari_company_os.store as store_module
import palari_company_os.workspace_layout as workspace_layout_module
from palari_company_os.errors import WorkspaceError
from palari_company_os.onramp import initialize_maintainer_workspace
from palari_company_os.workspace_layout import (
    MAINTAINER_BINDING_FILENAME,
    MAINTAINER_INITIALIZATION_LOCK_FILENAME,
    MAINTAINER_REPOSITORY_ID_FILENAME,
    MAINTAINER_WORKSPACE_FILENAME,
    begin_maintainer_initialization,
)


class MaintainerInitializationAtomicityTests(unittest.TestCase):
    def test_exclude_append_race_preserves_bytes_before_and_after_owned_block(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            before = repo.exclude_file.read_bytes()
            exclude_inode = repo.exclude_file.stat().st_ino
            concurrent = b"/operator-raced-before-palari/\n"
            original_write = os.write
            injected = False

            def append_before_owned_write(
                descriptor: int,
                payload: bytes | memoryview,
            ) -> int:
                nonlocal injected
                if (
                    not injected
                    and os.fstat(descriptor).st_ino == exclude_inode
                ):
                    injected = True
                    with repo.exclude_file.open("ab") as handle:
                        handle.write(concurrent)
                return original_write(descriptor, payload)

            with mock.patch.object(
                workspace_layout_module.os,
                "write",
                side_effect=append_before_owned_write,
            ):
                initialization = begin_maintainer_initialization(repo.root)

            self.assertTrue(injected)
            self.assertIn(concurrent, repo.exclude_file.read_bytes())
            self.assertEqual(initialization.rollback(), ())
            self.assertEqual(repo.exclude_file.read_bytes(), before + concurrent)

    def test_new_binding_and_repository_id_never_overwrite_racing_files(
        self,
    ) -> None:
        for target_name in (
            MAINTAINER_REPOSITORY_ID_FILENAME,
            MAINTAINER_BINDING_FILENAME,
        ):
            with self.subTest(target=target_name), tempfile.TemporaryDirectory() as directory:
                repo = create_git_repository(
                    Path(directory) / "source",
                    ordinary_workspace=False,
                )
                foreign = b"foreign file published in the no-replace window\n"
                original_publish = workspace_layout_module._publish_new_bytes_at

                def publish_with_race(
                    parent_descriptor: int,
                    name: str,
                    payload: bytes,
                    *,
                    mode: int,
                    capture: Any = None,
                ) -> Any:
                    if name == target_name:
                        target = (
                            repo.repository_id_file
                            if name == MAINTAINER_REPOSITORY_ID_FILENAME
                            else repo.binding_file
                        )
                        target.write_bytes(foreign)
                    return original_publish(
                        parent_descriptor,
                        name,
                        payload,
                        mode=mode,
                        capture=capture,
                    )

                with (
                    mock.patch.object(
                        workspace_layout_module,
                        "_publish_new_bytes_at",
                        side_effect=publish_with_race,
                    ),
                    self.assertRaises(FileExistsError),
                ):
                    begin_maintainer_initialization(repo.root)

                target = (
                    repo.repository_id_file
                    if target_name == MAINTAINER_REPOSITORY_ID_FILENAME
                    else repo.binding_file
                )
                self.assertEqual(target.read_bytes(), foreign)

    def test_initial_workspace_publication_never_overwrites_racing_file(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            foreign = b'{"foreign":"workspace"}\n'
            original_link = os.link
            injected = False

            def link_with_race(
                source: str,
                destination: str,
                *args: Any,
                **kwargs: Any,
            ) -> None:
                nonlocal injected
                if (
                    destination == MAINTAINER_WORKSPACE_FILENAME
                    and not injected
                ):
                    injected = True
                    repo.workspace_file.write_bytes(foreign)
                original_link(source, destination, *args, **kwargs)

            with (
                mock.patch.object(
                    store_module.os,
                    "link",
                    side_effect=link_with_race,
                ),
                self.assertRaises(FileExistsError),
            ):
                initialize_maintainer_workspace(repo.root)

            self.assertTrue(injected)
            self.assertEqual(repo.workspace_file.read_bytes(), foreign)

    def test_initial_journal_publication_never_overwrites_racing_file(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            foreign = b"foreign journal appeared before prepare\n"
            original_publish = workspace_layout_module._publish_new_bytes_at

            def publish_with_race(
                parent_descriptor: int,
                name: str,
                payload: bytes,
                *,
                mode: int,
                capture: Any = None,
            ) -> Any:
                if name == "governance-journal.v2.jsonl":
                    (repo.runtime_root / name).write_bytes(foreign)
                return original_publish(
                    parent_descriptor,
                    name,
                    payload,
                    mode=mode,
                    capture=capture,
                )

            with (
                mock.patch.object(
                    workspace_layout_module,
                    "_publish_new_bytes_at",
                    side_effect=publish_with_race,
                ),
                self.assertRaises(FileExistsError),
            ):
                initialize_maintainer_workspace(repo.root)

            self.assertEqual(
                (repo.runtime_root / "governance-journal.v2.jsonl").read_bytes(),
                foreign,
            )

    def test_state_root_symlink_swap_cannot_write_or_cleanup_outside_repo(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = create_git_repository(
                root / "source",
                ordinary_workspace=False,
            )
            outside = root / "outside"
            outside.mkdir()
            sentinel = outside / "sentinel.txt"
            sentinel.write_bytes(b"outside must be untouched\n")
            detached_state = repo.root / ".palari-company-os-detached"
            original_replace = workspace_layout_module._atomic_replace_json

            def swap_parent_then_publish(
                path: Path,
                value: dict[str, object],
                *,
                mode: int,
            ) -> None:
                if path == repo.binding_file:
                    repo.state_root.rename(detached_state)
                    repo.state_root.symlink_to(outside, target_is_directory=True)
                original_replace(path, value, mode=mode)

            with (
                mock.patch.object(
                    workspace_layout_module,
                    "_atomic_replace_json",
                    side_effect=swap_parent_then_publish,
                ),
                self.assertRaises(WorkspaceError),
            ):
                begin_maintainer_initialization(repo.root)

            self.assertEqual(sentinel.read_bytes(), b"outside must be untouched\n")
            self.assertFalse((outside / MAINTAINER_BINDING_FILENAME).exists())
            self.assertTrue(repo.state_root.is_symlink())

    def test_identical_binding_replacement_is_never_adopted_by_rollback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            original_replace = workspace_layout_module._atomic_replace_json
            primary = RuntimeError("failure after foreign inode replacement")
            foreign_inode = 0
            foreign_payload = b""

            def replace_inode_then_fail(
                path: Path,
                value: dict[str, object],
                *,
                mode: int,
            ) -> None:
                nonlocal foreign_inode, foreign_payload
                original_replace(path, value, mode=mode)
                if path != repo.binding_file:
                    return
                foreign_payload = path.read_bytes()
                replacement = path.with_name("foreign-binding.tmp")
                replacement.write_bytes(foreign_payload)
                os.replace(replacement, path)
                foreign_inode = path.stat().st_ino
                raise primary

            with (
                mock.patch.object(
                    workspace_layout_module,
                    "_atomic_replace_json",
                    side_effect=replace_inode_then_fail,
                ),
                self.assertRaisesRegex(RuntimeError, "foreign inode") as caught,
            ):
                begin_maintainer_initialization(repo.root)

            self.assertIs(caught.exception, primary)
            self.assertEqual(repo.binding_file.read_bytes(), foreign_payload)
            self.assertEqual(repo.binding_file.stat().st_ino, foreign_inode)

    def test_git_status_failure_fails_closed_without_initialization_outputs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            before = repo.safety_snapshot()
            original_run = workspace_layout_module.subprocess.run

            def fail_status(
                command: list[str],
                **kwargs: Any,
            ) -> Any:
                if "status" in command:
                    return workspace_layout_module.subprocess.CompletedProcess(
                        command,
                        128,
                        stdout="",
                        stderr="fatal: injected status failure",
                    )
                return original_run(command, **kwargs)

            with (
                mock.patch.object(
                    workspace_layout_module.subprocess,
                    "run",
                    side_effect=fail_status,
                ),
                self.assertRaisesRegex(
                    WorkspaceError,
                    "cannot inspect maintainer Git repository",
                ),
            ):
                begin_maintainer_initialization(repo.root)

            self.assertEqual(repo.safety_snapshot(), before)

    def test_lock_publication_is_complete_and_stage_failure_leaves_no_lock(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            original_link = os.link

            def fail_lock_link(
                source: str,
                destination: str,
                *args: Any,
                **kwargs: Any,
            ) -> None:
                if destination == MAINTAINER_INITIALIZATION_LOCK_FILENAME:
                    raise OSError("injected lock publication crash")
                original_link(source, destination, *args, **kwargs)

            with (
                mock.patch.object(
                    workspace_layout_module.os,
                    "link",
                    side_effect=fail_lock_link,
                ),
                self.assertRaisesRegex(
                    WorkspaceError,
                    "cannot create maintainer initialization lock",
                ),
            ):
                begin_maintainer_initialization(repo.root)

            self.assertFalse(
                (
                    repo.common_dir
                    / MAINTAINER_INITIALIZATION_LOCK_FILENAME
                ).exists()
            )
            self.assertFalse(
                any(
                    "palari-stage" in path.name
                    for path in repo.common_dir.iterdir()
                )
            )

    def test_lock_error_cleanup_never_deletes_identical_foreign_inode(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            lock_path = (
                repo.common_dir
                / MAINTAINER_INITIALIZATION_LOCK_FILENAME
            )
            original_create = (
                workspace_layout_module._create_initialization_lock
            )
            primary = RuntimeError("failure after foreign lock replacement")
            published_payload = b""
            original_inode = 0

            def replace_lock_inode_then_fail(
                path: Path,
                parent_descriptor: int,
                payload: bytes,
            ) -> Any:
                nonlocal published_payload, original_inode
                original_create(path, parent_descriptor, payload)
                published_payload = payload
                original_inode = path.stat().st_ino
                replacement = path.with_name("foreign-lock.tmp")
                replacement.write_bytes(payload)
                os.replace(replacement, path)
                raise primary

            with (
                mock.patch.object(
                    workspace_layout_module,
                    "_create_initialization_lock",
                    side_effect=replace_lock_inode_then_fail,
                ),
                self.assertRaisesRegex(RuntimeError, "foreign lock") as caught,
            ):
                begin_maintainer_initialization(repo.root)

            self.assertIs(caught.exception, primary)
            self.assertEqual(lock_path.read_bytes(), published_payload)
            self.assertNotEqual(lock_path.stat().st_ino, original_inode)

    def test_malformed_lock_requires_age_and_pid_reuse_witness_is_reclaimed(
        self,
    ) -> None:
        for malformed in (b"pid=-1\n", b"pid=999999999999999999999\n"):
            with self.subTest(malformed=malformed), tempfile.TemporaryDirectory() as directory:
                repo = create_git_repository(
                    Path(directory) / "source",
                    ordinary_workspace=False,
                )
                lock_path = (
                    repo.common_dir
                    / MAINTAINER_INITIALIZATION_LOCK_FILENAME
                )
                lock_path.write_bytes(malformed)
                with self.assertRaisesRegex(
                    WorkspaceError,
                    "already in progress",
                ):
                    begin_maintainer_initialization(repo.root)
                self.assertEqual(lock_path.read_bytes(), malformed)
                old = time.time() - 600
                os.utime(lock_path, (old, old))
                initialization = begin_maintainer_initialization(repo.root)
                self.assertEqual(initialization.rollback(), ())

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            lock_path = (
                repo.common_dir
                / MAINTAINER_INITIALIZATION_LOCK_FILENAME
            )
            lock_path.write_text(
                json.dumps(
                    {
                        "schema_version": "palari.maintainer-init-lock.v1",
                        "pid": os.getpid(),
                        "process_start": "0",
                        "created_unix_seconds": int(time.time()),
                        "token": "a" * 32,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            initialization = begin_maintainer_initialization(repo.root)
            self.assertEqual(initialization.rollback(), ())

    def test_post_release_commit_is_detected_and_owned_outputs_roll_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            before_exclude = repo.exclude_file.read_bytes()
            original_release = (
                workspace_layout_module._release_initialization_lock
            )

            def release_then_commit(lock: Any) -> None:
                original_release(lock)
                (repo.root / "POST-RELEASE.md").write_text(
                    "foreign clean commit after lock release\n",
                    encoding="utf-8",
                )
                git(repo.root, "add", "POST-RELEASE.md")
                git(repo.root, "commit", "-qm", "post-release concurrent commit")

            with (
                mock.patch.object(
                    workspace_layout_module,
                    "_release_initialization_lock",
                    side_effect=release_then_commit,
                ),
                self.assertRaisesRegex(WorkspaceError, "Git HEAD changed"),
            ):
                initialize_maintainer_workspace(repo.root)

            self.assertTrue((repo.root / "POST-RELEASE.md").is_file())
            self.assertEqual(repo.status(), "")
            self.assertEqual(repo.exclude_file.read_bytes(), before_exclude)
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.state_root.exists())
            self.assertFalse(repo.repository_id_file.exists())

    def test_overlapping_initializer_cannot_mutate_or_rollback_the_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            before = repo.safety_snapshot()
            first = begin_maintainer_initialization(repo.root)
            active = repo.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "initialization is already in progress",
            ):
                begin_maintainer_initialization(repo.root)

            self.assertEqual(repo.safety_snapshot(), active)
            self.assertTrue(
                (
                    repo.common_dir
                    / MAINTAINER_INITIALIZATION_LOCK_FILENAME
                ).is_file()
            )
            self.assertEqual(first.rollback(), ())
            self.assertEqual(repo.safety_snapshot(), before)
            self.assertFalse(
                (
                    repo.common_dir
                    / MAINTAINER_INITIALIZATION_LOCK_FILENAME
                ).exists()
            )

    def test_rollback_three_way_preserves_appended_exclude_after_no_newline(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            previous = b"/operator-rule-without-newline"
            repo.exclude_file.write_bytes(previous)
            initialization = begin_maintainer_initialization(repo.root)

            concurrent = b"/concurrent-operator-cache/\n"
            with repo.exclude_file.open("ab") as handle:
                handle.write(concurrent)

            self.assertEqual(initialization.rollback(), ())
            self.assertEqual(
                repo.exclude_file.read_bytes(),
                previous + b"\n" + concurrent,
            )
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.state_root.exists())
            self.assertFalse(repo.repository_id_file.exists())

    def test_failed_init_preserves_replaced_exclude_and_primary_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            foreign = b"# concurrent full replacement\n/concurrent-only/\n"
            primary = RuntimeError("primary initialization failure")

            def fail_after_replacement(*args: Any, **kwargs: Any) -> Any:
                repo.exclude_file.write_bytes(foreign)
                raise primary

            with mock.patch.object(
                onramp_module,
                "write_store",
                side_effect=fail_after_replacement,
            ), self.assertRaisesRegex(
                RuntimeError,
                "primary initialization failure",
            ) as caught:
                initialize_maintainer_workspace(repo.root)

            self.assertIs(caught.exception, primary)
            self.assertEqual(repo.exclude_file.read_bytes(), foreign)
            self.assertTrue(
                any(
                    "cleanup preserved concurrent changes" in note
                    and "Git exclude" in note
                    for note in getattr(caught.exception, "__notes__", ())
                )
            )
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.state_root.exists())
            self.assertFalse(repo.repository_id_file.exists())

    def test_prewrite_source_status_drift_blocks_and_preserves_foreign_file(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            before_exclude = repo.exclude_file.read_bytes()
            original_write_store = onramp_module.write_store

            def drift_then_write(*args: Any, **kwargs: Any) -> Any:
                (repo.root / "CONCURRENT.txt").write_text(
                    "foreign dirty source\n",
                    encoding="utf-8",
                )
                return original_write_store(*args, **kwargs)

            with (
                mock.patch.object(
                    onramp_module,
                    "write_store",
                    side_effect=drift_then_write,
                ),
                self.assertRaisesRegex(WorkspaceError, "Git status changed"),
            ):
                initialize_maintainer_workspace(repo.root)

            self.assertEqual(
                (repo.root / "CONCURRENT.txt").read_text(encoding="utf-8"),
                "foreign dirty source\n",
            )
            self.assertEqual(repo.status(), "?? CONCURRENT.txt\n")
            self.assertEqual(repo.exclude_file.read_bytes(), before_exclude)
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.state_root.exists())
            self.assertFalse(repo.repository_id_file.exists())

    def test_complete_rejects_clean_head_drift_and_rolls_back_owned_outputs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            before_exclude = repo.exclude_file.read_bytes()
            initial_head = git(repo.root, "rev-parse", "HEAD").stdout.strip()
            original_write_store = onramp_module.write_store

            def write_then_commit(*args: Any, **kwargs: Any) -> Any:
                result = original_write_store(*args, **kwargs)
                (repo.root / "CONCURRENT.md").write_text(
                    "foreign committed source\n",
                    encoding="utf-8",
                )
                git(repo.root, "add", "CONCURRENT.md")
                git(repo.root, "commit", "-qm", "concurrent clean commit")
                return result

            with (
                mock.patch.object(
                    onramp_module,
                    "write_store",
                    side_effect=write_then_commit,
                ),
                self.assertRaisesRegex(WorkspaceError, "Git HEAD changed"),
            ):
                initialize_maintainer_workspace(repo.root)

            self.assertNotEqual(
                git(repo.root, "rev-parse", "HEAD").stdout.strip(),
                initial_head,
            )
            self.assertEqual(repo.status(), "")
            self.assertTrue((repo.root / "CONCURRENT.md").is_file())
            self.assertEqual(repo.exclude_file.read_bytes(), before_exclude)
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.state_root.exists())
            self.assertFalse(repo.repository_id_file.exists())

    def test_post_replace_store_failure_cleans_registered_workspace_and_journal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            before = repo.safety_snapshot()
            original_replace = store_module._atomic_replace_text

            def replace_then_fail(
                path: Path,
                text: str,
                **kwargs: Any,
            ) -> None:
                original_replace(path, text, **kwargs)
                raise OSError("injected post-workspace-replace failure")

            with (
                mock.patch.object(
                    store_module,
                    "_atomic_replace_text",
                    side_effect=replace_then_fail,
                ),
                self.assertRaisesRegex(
                    OSError,
                    "post-workspace-replace failure",
                ),
            ):
                initialize_maintainer_workspace(repo.root)

            self.assertEqual(repo.safety_snapshot(), before)
            self.assertFalse(
                (
                    repo.common_dir
                    / MAINTAINER_INITIALIZATION_LOCK_FILENAME
                ).exists()
            )

    def test_rollback_preserves_foreign_profile_replacements_and_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            initialization = begin_maintainer_initialization(repo.root)
            foreign_workspace = b'{"foreign":"workspace"}\n'
            foreign_binding = b'{"foreign":"binding"}\n'
            foreign_repository = b'{"foreign":"repository"}\n'
            repo.workspace_file.write_bytes(foreign_workspace)
            repo.binding_file.write_bytes(foreign_binding)
            repo.repository_id_file.write_bytes(foreign_repository)
            sentinel = repo.runtime_root / "foreign-sentinel.txt"
            sentinel.write_bytes(b"foreign runtime\n")

            notes = initialization.rollback()

            self.assertEqual(repo.workspace_file.read_bytes(), foreign_workspace)
            self.assertEqual(repo.binding_file.read_bytes(), foreign_binding)
            self.assertEqual(
                repo.repository_id_file.read_bytes(),
                foreign_repository,
            )
            self.assertEqual(sentinel.read_bytes(), b"foreign runtime\n")
            self.assertTrue(any("workspace" in note for note in notes))
            self.assertTrue(any("binding" in note for note in notes))
            self.assertTrue(
                any("repository identifier" in note for note in notes)
            )
            self.assertTrue(any("runtime directory" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
