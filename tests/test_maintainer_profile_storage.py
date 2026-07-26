from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os import workspace_layout as workspace_layout_module
from palari_company_os.onramp import initialize_maintainer_workspace
from palari_company_os.workspace import Workspace, WorkspaceError
from palari_company_os.workspace_layout import (
    MAINTAINER_BINDING_FILENAME,
    MAINTAINER_PROFILE,
    MAINTAINER_REPOSITORY_ID_FILENAME,
    MAINTAINER_STATE_ROOT,
    MAINTAINER_WORKSPACE_FILENAME,
    ORDINARY_PROFILE,
    RUNTIME_ROOT,
    begin_maintainer_initialization,
    resolve_workspace_layout,
)
from tests.maintainer_profile_fixture import (
    MaintainerProfileRepo,
    create_git_repository,
    git,
)


class MaintainerProfileStorageTests(unittest.TestCase):
    def test_init_is_ignored_clean_and_preserves_tracked_root_governance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_before = repo.root_governance_snapshot()

            result = repo.init_maintainer()

            self.assertEqual(result["schema_version"], "palari.init.v1")
            self.assertEqual(result["profile"], MAINTAINER_PROFILE)
            self.assertEqual(result["workspace_file"], str(repo.workspace_file))
            self.assertEqual(result["state_root"], str(repo.state_root))
            self.assertEqual(result["runtime_root"], str(repo.runtime_root))
            self.assertEqual(result["binding_file"], str(repo.binding_file))
            self.assertEqual(result["agent_docs"]["status"], "not-required")
            self.assertEqual(result["authority_anchor"]["status"], "not-required")
            self.assertEqual(result["adoption"]["status"], "not-requested")
            self.assertEqual(repo.root_governance_snapshot(), root_before)
            self.assertEqual(repo.status(), "")
            self.assertTrue(
                repo.path_is_ignored(MAINTAINER_WORKSPACE_FILENAME)
            )
            self.assertTrue(
                repo.path_is_ignored(
                    f"{MAINTAINER_STATE_ROOT}/{MAINTAINER_BINDING_FILENAME}"
                )
            )
            self.assertEqual(repo.tracked_profile_paths(), [])
            self.assertTrue(repo.workspace_file.is_file())
            self.assertTrue(repo.binding_file.is_file())
            self.assertTrue(repo.repository_id_file.is_file())
            self.assertTrue(repo.runtime_root.is_dir())
            commands = repo.assert_exact_commands(result)
            self.assertTrue(commands)

    def test_exact_layout_and_explicit_selector_never_change_default_discovery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()

            layout = resolve_workspace_layout(repo.workspace_file)
            explicit = Workspace.load(repo.workspace_file)
            ordinary = Workspace.load(repo.root)
            default_cli = repo.run_json("validate", "--json")
            explicit_cli = repo.profile_json("validate", "--json")

            self.assertTrue(layout.maintainer)
            self.assertEqual(layout.profile, MAINTAINER_PROFILE)
            self.assertEqual(layout.repository_root, repo.root.resolve())
            self.assertEqual(layout.data_path, repo.workspace_file)
            self.assertEqual(layout.state_root, repo.state_root)
            self.assertEqual(layout.runtime_root, repo.runtime_root)
            self.assertEqual(layout.binding_path, repo.binding_file)
            self.assertEqual(layout.repository_common_dir, repo.common_dir)
            self.assertEqual(layout.repository_id_path, repo.repository_id_file)
            self.assertEqual(explicit.path, repo.root.resolve())
            self.assertEqual(explicit.data_path, repo.workspace_file)
            self.assertEqual(ordinary.data_path, repo.root / "workspace.json")
            self.assertEqual(
                default_cli["workspace"],
                "Current Agent Test Workspace",
            )
            self.assertNotEqual(default_cli["workspace"], explicit_cli["workspace"])
            self.assertEqual(repo.status(), "")

        with tempfile.TemporaryDirectory() as directory:
            hidden_only = create_git_repository(
                Path(directory) / "source",
                ordinary_workspace=False,
            )
            hidden_only.init_maintainer()

            with self.assertRaisesRegex(
                WorkspaceError,
                "workspace file not found.*workspace.json",
            ):
                Workspace.load(hidden_only.root)
            self.assertTrue(Workspace.load(hidden_only.workspace_file).name)
            omitted = hidden_only.run_cli("validate", "--json", check=False)
            self.assertNotEqual(omitted.returncode, 0)
            self.assertIn("workspace.json", omitted.stderr + omitted.stdout)
            self.assertEqual(hidden_only.status(), "")

    def test_ordinary_custom_workspace_and_repository_name_do_not_select_profile(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(
                Path(directory) / "palari-company-os",
            )
            custom = repo.root / "governance-state.json"
            custom.write_text(
                (repo.root / "workspace.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            root_layout = resolve_workspace_layout(repo.root)
            custom_layout = resolve_workspace_layout(custom)

            self.assertEqual(root_layout.profile, ORDINARY_PROFILE)
            self.assertEqual(root_layout.data_path, repo.root / "workspace.json")
            self.assertEqual(custom_layout.profile, ORDINARY_PROFILE)
            self.assertEqual(custom_layout.data_path, custom)
            self.assertEqual(custom_layout.runtime_root, repo.root / ".palari")
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.state_root.exists())

    def test_init_requires_git_and_the_exact_worktree_root_without_partial_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "not-git"
            root.mkdir()
            (root / "README.md").write_text("not a repository\n", encoding="utf-8")
            repo = MaintainerProfileRepo(root)

            result = repo.run_cli(
                "init",
                str(root),
                "--profile",
                "maintainer",
                "--json",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Git",
                result.stdout + result.stderr,
            )
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.state_root.exists())

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            nested = repo.root / "nested"
            nested.mkdir()
            (nested / "tracked.txt").write_text("nested invocation\n", encoding="utf-8")
            git(repo.root, "add", "nested/tracked.txt")
            git(repo.root, "commit", "-qm", "add nested directory")
            before = repo.safety_snapshot()

            result = repo.run_cli(
                "init",
                str(nested),
                "--profile",
                "maintainer",
                "--json",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "exact Git worktree root",
                result.stdout + result.stderr,
            )
            self.assertEqual(repo.safety_snapshot(), before)
            self.assertFalse(
                (nested / MAINTAINER_WORKSPACE_FILENAME).exists()
            )
            self.assertFalse((nested / MAINTAINER_STATE_ROOT).exists())

    def test_init_requires_clean_committed_source_and_profile_rejects_split_collections(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "dirty")
            (repo.root / "untracked.txt").write_text(
                "uncommitted source state\n",
                encoding="utf-8",
            )
            before = repo.safety_snapshot()

            result = repo.run_cli(
                "init",
                str(repo.root),
                "--profile",
                "maintainer",
                "--json",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("clean Git worktree", result.stdout + result.stderr)
            self.assertEqual(repo.safety_snapshot(), before)
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.state_root.exists())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "unborn"
            root.mkdir()
            git(root, "init", "-q", "-b", "main")
            repo = MaintainerProfileRepo(root)
            before = repo.safety_snapshot()

            result = repo.run_cli(
                "init",
                str(root),
                "--profile",
                "maintainer",
                "--json",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "exact committed Git candidate",
                result.stdout + result.stderr,
            )
            self.assertEqual(repo.safety_snapshot(), before)

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "split")
            repo.init_maintainer()
            raw = json.loads(repo.workspace_file.read_text(encoding="utf-8"))
            raw["collection_files"] = {"goals": "collections/goals.json"}
            repo.workspace_file.write_text(
                json.dumps(raw, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            before = repo.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "does not support split collection files",
            ):
                Workspace.load(repo.workspace_file)

            self.assertEqual(repo.safety_snapshot(), before)

    def test_sha256_git_repository_is_a_valid_exact_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            try:
                repo = create_git_repository(
                    Path(directory) / "sha256",
                    object_format="sha256",
                )
            except subprocess.CalledProcessError as exc:
                self.skipTest(f"installed Git does not support SHA-256 repositories: {exc}")

            result = repo.init_maintainer()
            head = git(repo.root, "rev-parse", "HEAD").stdout.strip()
            added = repo.profile_json(
                "work",
                "add",
                "Exercise SHA-256 claim binding",
                "--create",
                "artifacts/sha256.txt",
                "--risk",
                "R1",
                "--intensity",
                "light",
                "--approvals",
                "0",
                "--verify",
                "Exact SHA-256 candidate binding passes.",
                "--json",
            )
            started = repo.emitted_json(added["next_commands"][0])

            self.assertEqual(len(head), 64)
            self.assertEqual(result["profile"], MAINTAINER_PROFILE)
            self.assertEqual(started["start"]["status"], "claimed")
            self.assertEqual(repo.status(), "")

    def test_existing_advisory_verification_log_is_preserved_on_init_and_rollback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "coexist")
            repo.state_root.mkdir()
            verification = repo.state_root / "verification.json"
            verification.write_bytes(b'{"commands":[]}\n')

            repo.init_maintainer()

            self.assertEqual(verification.read_bytes(), b'{"commands":[]}\n')
            self.assertEqual(repo.status(), "")

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "rollback")
            repo.state_root.mkdir()
            verification = repo.state_root / "verification.json"
            verification.write_bytes(b'{"commands":["focused"]}\n')
            before_exclude = repo.exclude_file.read_bytes()

            with (
                patch(
                    "palari_company_os.onramp.write_store",
                    side_effect=RuntimeError("injected initialization failure"),
                ),
                self.assertRaisesRegex(RuntimeError, "initialization failure"),
            ):
                initialize_maintainer_workspace(repo.root)

            self.assertEqual(
                verification.read_bytes(),
                b'{"commands":["focused"]}\n',
            )
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.binding_file.exists())
            self.assertFalse(repo.runtime_root.exists())
            self.assertEqual(repo.exclude_file.read_bytes(), before_exclude)

    def test_repository_identifier_is_rolled_back_after_post_replace_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            before = repo.safety_snapshot()
            original_replace = workspace_layout_module._atomic_replace_json

            def replace_then_fail(
                path: Path,
                value: dict[str, object],
                *,
                mode: int,
            ) -> None:
                original_replace(path, value, mode=mode)
                if path == repo.repository_id_file:
                    raise OSError("injected post-replace durability failure")

            with (
                patch.object(
                    workspace_layout_module,
                    "_atomic_replace_json",
                    side_effect=replace_then_fail,
                ),
                self.assertRaisesRegex(OSError, "post-replace durability failure"),
            ):
                begin_maintainer_initialization(repo.root)

            self.assertEqual(repo.safety_snapshot(), before)
            self.assertFalse(repo.repository_id_file.exists())
            self.assertFalse(repo.workspace_file.exists())
            self.assertFalse(repo.state_root.exists())

    def test_init_refuses_existing_or_tracked_profile_paths_without_overwrite(
        self,
    ) -> None:
        cases = ("workspace", "state-root")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                repo = create_git_repository(Path(directory) / "source")
                if case == "workspace":
                    repo.workspace_file.write_text(
                        "tracked conflicting state\n",
                        encoding="utf-8",
                    )
                    tracked = MAINTAINER_WORKSPACE_FILENAME
                else:
                    repo.state_root.mkdir()
                    repo.binding_file.write_text(
                        "tracked conflicting binding\n",
                        encoding="utf-8",
                    )
                    tracked = (
                        f"{MAINTAINER_STATE_ROOT}/"
                        f"{MAINTAINER_BINDING_FILENAME}"
                    )
                git(repo.root, "add", "-f", "--", tracked)
                git(repo.root, "commit", "-qm", f"track conflicting {case}")
                before = repo.safety_snapshot()
                self.assertIn(tracked, repo.tracked_profile_paths())

                result = repo.run_cli(
                    "init",
                    str(repo.root),
                    "--profile",
                    "maintainer",
                    "--json",
                    check=False,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "already exists or conflicts",
                    result.stdout + result.stderr,
                )
                self.assertEqual(repo.safety_snapshot(), before)

    def test_whole_repository_move_preserves_binding_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            original = create_git_repository(parent / "before-move")
            original.init_maintainer()
            binding_before = original.binding_file.read_bytes()
            repository_id_before = original.repository_id_file.read_bytes()
            root_governance_before = original.root_governance_snapshot()
            moved_root = parent / "after-move"

            original.root.rename(moved_root)
            moved = MaintainerProfileRepo(moved_root)
            workspace = Workspace.load(moved.workspace_file)
            layout = moved.layout()
            validated = moved.profile_json("validate", "--json")

            self.assertEqual(workspace.path, moved_root.resolve())
            self.assertEqual(workspace.data_path, moved.workspace_file)
            self.assertEqual(layout.repository_root, moved_root.resolve())
            self.assertEqual(moved.binding_file.read_bytes(), binding_before)
            self.assertEqual(
                moved.repository_id_file.read_bytes(),
                repository_id_before,
            )
            self.assertEqual(
                moved.root_governance_snapshot(),
                root_governance_before,
            )
            self.assertTrue(validated["valid"])
            self.assertEqual(moved.status(), "")
            self.assertEqual(moved.tracked_profile_paths(), [])

    def test_binding_and_repository_identifier_use_strict_versioned_shapes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            binding = json.loads(repo.binding_file.read_text(encoding="utf-8"))
            repository = json.loads(
                repo.repository_id_file.read_text(encoding="utf-8")
            )

            self.assertEqual(
                set(binding),
                {
                    "schema_version",
                    "profile",
                    "state_id",
                    "repository_id",
                    "workspace_file",
                    "state_root",
                    "runtime_root",
                    "repository_id_file",
                    "binding_digest",
                },
            )
            self.assertEqual(binding["profile"], MAINTAINER_PROFILE)
            self.assertEqual(
                binding["workspace_file"],
                MAINTAINER_WORKSPACE_FILENAME,
            )
            self.assertEqual(binding["state_root"], MAINTAINER_STATE_ROOT)
            self.assertEqual(binding["runtime_root"], RUNTIME_ROOT)
            self.assertEqual(
                binding["repository_id_file"],
                MAINTAINER_REPOSITORY_ID_FILENAME,
            )
            self.assertEqual(
                repository,
                {
                    "schema_version": "palari.maintainer-repository.v1",
                    "repository_id": binding["repository_id"],
                },
            )


if __name__ == "__main__":
    unittest.main()
