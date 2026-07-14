from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_file_changes import capture_git_baseline, inspect_file_changes
from palari_company_os.agent_runtime import claims_dir, load_active_claim_contexts
from palari_company_os.evidence_manifest import _artifact_hashes, verify_evidence
from palari_company_os.workspace import WorkspaceError, _collection_file_path


class FilesystemReadBoundaryTests(unittest.TestCase):
    def test_split_collection_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as outside_name:
            root = Path(root_name)
            (root / "records").symlink_to(Path(outside_name), target_is_directory=True)

            with self.assertRaisesRegex(WorkspaceError, "workspace-relative"):
                _collection_file_path(root, "work_items", "records/work-items.json")

    def test_runtime_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as outside_name:
            root = Path(root_name)
            (root / "workspace.json").write_text("{}", encoding="utf-8")
            (root / ".palari").symlink_to(Path(outside_name), target_is_directory=True)

            with self.assertRaisesRegex(WorkspaceError, "unsafe Palari runtime path"):
                claims_dir(root)

    def test_claim_file_symlink_escape_is_reported_without_loading(self) -> None:
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as outside_name:
            root = Path(root_name)
            outside = Path(outside_name)
            (root / "workspace.json").write_text("{}", encoding="utf-8")
            claims = root / ".palari" / "claims"
            claims.mkdir(parents=True)
            external_claim = outside / "claim.json"
            external_claim.write_text("{}", encoding="utf-8")
            (claims / "WORK-1.json").symlink_to(external_claim)

            state = load_active_claim_contexts(root)

            self.assertEqual(state["contexts"], [])
            self.assertIn("escapes workspace root", state["errors"][0])

    def test_missing_artifact_never_verifies_even_when_declared_hash_matches(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            hashes = _artifact_hashes(root, ["artifacts/missing.json"])
            evidence = SimpleNamespace(
                id="EVIDENCE-1",
                work_item_id="WORK-1",
                attempt_id="ATTEMPT-1",
                head_sha="abc",
                status="passed",
                base_ref="main",
                commands=[],
                artifacts=["artifacts/missing.json"],
                artifact_hashes=hashes,
                summary="",
                freshness="current",
                timestamp="2026-01-01T00:00:00Z",
                manifest_hash="",
                receipt_hash="",
                previous_receipt_hash="",
            )
            workspace = SimpleNamespace(
                evidence_runs=[evidence], receipts=[], path=root, name="test"
            )

            result = verify_evidence(workspace, "EVIDENCE-1")

            self.assertFalse(result["ok"])
            self.assertFalse(result["artifact_hashes_ok"])
            self.assertFalse(result["manifest_hash_ok"])
            self.assertFalse(result["receipt_checks"][0]["ok"])
            self.assertEqual(result["computed_artifact_hashes"][0]["status"], "missing")

    def test_artifact_symlink_escape_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as outside_name:
            root = Path(root_name)
            outside = Path(outside_name)
            (outside / "secret.txt").write_text("secret", encoding="utf-8")
            (root / "artifacts").symlink_to(outside, target_is_directory=True)

            result = _artifact_hashes(root, ["artifacts/secret.txt"])

            self.assertEqual(result[0]["status"], "unsafe")

    def test_unreadable_artifact_is_a_failed_state_not_an_exception(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            artifact = root / "artifact.txt"
            artifact.write_text("proof", encoding="utf-8")
            with patch.object(Path, "read_bytes", side_effect=OSError("read failed")):
                result = _artifact_hashes(root, ["artifact.txt"])

            self.assertEqual(result[0]["status"], "unreadable")


class FileChangeObservationTests(unittest.TestCase):
    def test_invalid_explicit_changed_path_is_retained_and_fails_closed(self) -> None:
        packet = {"allowed_paths": {"write": ["docs"]}, "required_output": {}}

        result = inspect_file_changes(packet, changed_paths=["../secret.txt"])

        assert result is not None
        self.assertEqual(result["invalid_changed_paths"], ["../secret.txt"])
        self.assertIn("../secret.txt", result["outside_write_boundary"])
        self.assertFalse(result["observation_complete"])

    def test_noncanonical_explicit_changed_path_is_retained_and_fails_closed(self) -> None:
        packet = {"allowed_paths": {"write": ["docs.txt"]}, "required_output": {}}

        result = inspect_file_changes(packet, changed_paths=[" docs.txt"])

        assert result is not None
        self.assertEqual(result["invalid_changed_paths"], [" docs.txt"])
        self.assertIn(" docs.txt", result["outside_write_boundary"])
        self.assertFalse(result["observation_complete"])

    def test_git_observation_error_is_retained_and_fails_closed(self) -> None:
        packet = {"allowed_paths": {"write": ["docs"]}, "required_output": {}}
        with patch(
            "palari_company_os.agent_file_changes.subprocess.run",
            side_effect=OSError("git unavailable"),
        ):
            result = inspect_file_changes(packet, git_diff=True)

        assert result is not None
        self.assertFalse(result["observation_complete"])
        self.assertIn("git unavailable", result["observation_errors"][0])
        self.assertTrue(
            any(path.startswith("[observation-error]") for path in result["outside_write_boundary"])
        )

    def test_nul_git_status_preserves_newline_filename_and_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            self._git(root, "init", "-q")
            self._git(root, "config", "user.email", "test@example.com")
            self._git(root, "config", "user.name", "Test")
            unusual = "docs/old\nname.txt"
            (root / "docs").mkdir()
            (root / unusual).write_text("old", encoding="utf-8")
            self._git(root, "add", "-A")
            self._git(root, "commit", "-qm", "initial")
            (root / unusual).unlink()

            packet = {"allowed_paths": {"write": ["docs"]}, "required_output": {}}
            result = inspect_file_changes(packet, git_diff=True, cwd=root)

            assert result is not None
            self.assertIn(unusual, result["deleted_files"])
            self.assertEqual(result["observation_errors"], [])

    def test_required_output_symlink_escape_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as outside_name:
            root = Path(root_name)
            self._git(root, "init", "-q")
            outside = Path(outside_name)
            (outside / "result.txt").write_text("external", encoding="utf-8")
            (root / "out").symlink_to(outside, target_is_directory=True)
            packet = {
                "allowed_paths": {"write": ["out"]},
                "required_output": {"output_targets": ["out/result.txt"]},
            }

            result = inspect_file_changes(packet, changed_paths=["out/result.txt"], cwd=root)

            assert result is not None
            self.assertIn("out/result.txt", result["missing_required_outputs"])
            self.assertIn("out/result.txt", result["outside_write_boundary"])

    def test_noncanonical_git_filename_fails_observation(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            self._git(root, "init", "-q")
            (root / " docs.txt").write_text("ambiguous", encoding="utf-8")
            packet = {"allowed_paths": {"write": ["docs.txt"]}, "required_output": {}}

            result = inspect_file_changes(packet, git_diff=True, cwd=root)

            assert result is not None
            self.assertFalse(result["observation_complete"])
            self.assertIn("canonical repository form", result["observation_errors"][0])

    def test_unchanged_preexisting_dirty_file_is_not_attributed_to_claim(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            self._git(root, "init", "-q")
            (root / "user-note.txt").write_text("pre-existing\n", encoding="utf-8")
            baseline = capture_git_baseline(root)
            packet = {"allowed_paths": {"write": ["src"]}, "required_output": {}}

            result = inspect_file_changes(
                packet,
                git_diff=True,
                cwd=root,
                git_baseline=baseline,
            )

            assert result is not None
            self.assertTrue(result["observation_complete"])
            self.assertEqual(result["changed_files"], [])
            self.assertEqual(result["preexisting_unchanged_files"], ["user-note.txt"])

    def test_changed_preexisting_dirty_file_is_attributed_and_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            self._git(root, "init", "-q")
            note = root / "user-note.txt"
            note.write_text("pre-existing\n", encoding="utf-8")
            baseline = capture_git_baseline(root)
            note.write_text("changed after claim with a new size\n", encoding="utf-8")
            packet = {"allowed_paths": {"write": ["src"]}, "required_output": {}}

            result = inspect_file_changes(
                packet,
                git_diff=True,
                cwd=root,
                git_baseline=baseline,
            )

            assert result is not None
            self.assertIn("user-note.txt", result["changed_files"])
            self.assertIn("user-note.txt", result["outside_write_boundary"])
            self.assertEqual(result["preexisting_unchanged_files"], [])

    def test_explicit_changed_path_is_never_hidden_by_git_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            self._git(root, "init", "-q")
            (root / "user-note.txt").write_text("pre-existing\n", encoding="utf-8")
            baseline = capture_git_baseline(root)
            packet = {"allowed_paths": {"write": ["src"]}, "required_output": {}}

            result = inspect_file_changes(
                packet,
                changed_paths=["user-note.txt"],
                git_diff=True,
                cwd=root,
                git_baseline=baseline,
            )

            assert result is not None
            self.assertIn("user-note.txt", result["changed_files"])
            self.assertIn("user-note.txt", result["outside_write_boundary"])

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "LC_ALL": "C"},
        )


if __name__ == "__main__":
    unittest.main()
