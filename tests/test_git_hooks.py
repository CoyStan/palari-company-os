from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_session_contract import compile_agent_session_contract
from palari_company_os.git_hooks import (
    git_hook_status,
    install_git_hook,
    pre_commit,
)
from palari_company_os.workspace import Workspace as Ws
from tests.workspace_fixture import write_portable_agent_workspace


DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


def _packet_hash(packet: dict[str, object]) -> str:
    stable = {
        key: value for key, value in packet.items() if key not in {"created_at", "context_hash"}
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class GitHooksTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.workspace_path = Path(self._tmp) / "ws"
        self.workspace_path.mkdir()
        write_portable_agent_workspace(
            DOGFOOD / "workspace.json",
            self.workspace_path / "workspace.json",
        )
        palari_dir = self.workspace_path / ".palari"
        if palari_dir.exists():
            shutil.rmtree(palari_dir)

        self._git_init()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _git_init(self) -> None:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
        }
        subprocess.run(["git", "init"], cwd=self._tmp, check=True, env=env, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=self._tmp, check=True, env=env, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=self._tmp,
            check=True,
            env=env,
            capture_output=True,
        )
        (Path(self._tmp) / "README.md").write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self._tmp, check=True, env=env, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=self._tmp, check=True, env=env, capture_output=True
        )

    def _start_claim(
        self,
        work_id: str = "WORK-TEST-GIT",
        allowed_resources: list[str] | None = None,
    ) -> None:
        from palari_company_os.agent_runtime import start_agent

        if Ws.load(self.workspace_path).work_item(work_id) is None:
            self._create_work(work_id, allowed_resources)
        ws = Ws.load(self.workspace_path)
        result = start_agent(ws, self.workspace_path, work_id, "PALARI-STEWARD", "execute")
        assert result.get("start", {}).get("status") == "claimed", f"Claim failed: {result.get('start', {})}"
        claims_dir = self.workspace_path / ".palari" / "claims"
        assert claims_dir.exists() and any(claims_dir.glob("*.json")), "No claim file created"

    def _create_work(
        self,
        work_id: str,
        allowed_resources: list[str] | None = None,
    ) -> None:
        from palari_company_os.authoring import create_record

        create_record(
            str(self.workspace_path),
            "work",
            {
                "id": work_id,
                "title": "Test git hooks",
                "palari": "PALARI-STEWARD",
                "goal": "GOAL-REPO-0001",
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R1",
                "intensity": "light",
                "required_approval_count": 0,
                "scope": "Test scope",
                "acceptance_target": "Test acceptance",
                "status": "active",
                "allowed_resources": allowed_resources or ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": allowed_resources or ["README.md"],
                "forbidden_actions": ["deploy"],
                "verification_expectations": ["echo ok"],
            },
            command="test",
        )

    def test_install_creates_pre_commit_hook(self) -> None:
        result = install_git_hook(self._tmp, self.workspace_path)
        self.assertEqual(result["status"], "installed")
        self.assertTrue(result["changed"])
        hook_path = Path(self._tmp) / ".git" / "hooks" / "pre-commit"
        self.assertTrue(hook_path.exists())
        content = hook_path.read_text()
        self.assertIn("palari git hook", content)
        self.assertIn("git pre-commit", content)
        self.assertTrue(os.access(hook_path, os.X_OK))

    def test_install_is_idempotent(self) -> None:
        install_git_hook(self._tmp, self.workspace_path)
        result = install_git_hook(self._tmp, self.workspace_path)
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["changed"])

    def test_install_then_remove(self) -> None:
        install_git_hook(self._tmp, self.workspace_path)
        result = install_git_hook(self._tmp, self.workspace_path, remove=True)
        self.assertEqual(result["status"], "removed")
        self.assertTrue(result["changed"])
        hook_path = Path(self._tmp) / ".git" / "hooks" / "pre-commit"
        self.assertFalse(hook_path.exists())

    def test_install_honors_core_hooks_path(self) -> None:
        subprocess.run(
            ["git", "config", "core.hooksPath", ".custom-hooks"],
            cwd=self._tmp,
            check=True,
            capture_output=True,
        )

        result = install_git_hook(self._tmp, self.workspace_path)

        self.assertEqual(result["status"], "installed")
        self.assertEqual(Path(result["hook_path"]), Path(self._tmp) / ".custom-hooks" / "pre-commit")
        self.assertTrue((Path(self._tmp) / ".custom-hooks" / "pre-commit").is_file())

    def test_install_rejects_core_hooks_path_outside_repository(self) -> None:
        outside = Path(self._tmp).parent / f"{Path(self._tmp).name}-hooks"
        self.addCleanup(shutil.rmtree, outside, True)
        subprocess.run(
            ["git", "config", "core.hooksPath", str(outside)],
            cwd=self._tmp,
            check=True,
            capture_output=True,
        )

        result = install_git_hook(self._tmp, self.workspace_path)

        self.assertEqual(result["status"], "error")
        self.assertIn("outside this repository", result["message"])
        self.assertFalse((outside / "pre-commit").exists())

    def test_remove_when_not_installed(self) -> None:
        result = install_git_hook(self._tmp, self.workspace_path, remove=True)
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["changed"])

    def test_install_refuses_to_overwrite_unmanaged_hook(self) -> None:
        hook_path = Path(self._tmp) / ".git" / "hooks" / "pre-commit"
        hook_path.parent.mkdir(parents=True, exist_ok=True)
        hook_path.write_text("# custom hook\nexit 0\n", encoding="utf-8")
        result = install_git_hook(self._tmp, self.workspace_path)
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["changed"])

    def test_status_shows_installed(self) -> None:
        install_git_hook(self._tmp, self.workspace_path)
        result = git_hook_status(self._tmp, self.workspace_path)
        self.assertTrue(result["installed"])
        self.assertEqual(result["schema_version"], "palari.git_status.v1")

    def test_status_shows_not_installed(self) -> None:
        result = git_hook_status(self._tmp, self.workspace_path)
        self.assertFalse(result["installed"])

    def test_pre_commit_passes_no_active_claim(self) -> None:
        result = pre_commit(self.workspace_path, cwd=self._tmp)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "no-active-claim")

    def test_pre_commit_blocks_out_of_boundary_files(self) -> None:
        self._start_claim()
        outside_file = Path(self._tmp) / "random_file.txt"
        outside_file.write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "add", "random_file.txt"], cwd=self._tmp, check=True, capture_output=True)
        result = pre_commit(self.workspace_path, cwd=self._tmp)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("random_file.txt", result["outside"])

    def test_pre_commit_passes_in_boundary_files(self) -> None:
        self._start_claim()
        in_boundary = Path(self._tmp) / "README.md"
        in_boundary.write_text("updated\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self._tmp, check=True, capture_output=True)
        result = pre_commit(self.workspace_path, cwd=self._tmp)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "pass")
        self.assertIn("README.md", result["staged"])
        self.assertEqual(result["outside"], [])

    def test_pre_commit_includes_staged_deletions(self) -> None:
        outside_file = Path(self._tmp) / "tracked-outside.txt"
        outside_file.write_text("tracked\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked-outside.txt"], cwd=self._tmp, check=True)
        subprocess.run(["git", "commit", "-m", "track outside"], cwd=self._tmp, check=True)
        self._start_claim()
        outside_file.unlink()
        subprocess.run(["git", "add", "-A"], cwd=self._tmp, check=True)

        result = pre_commit(self.workspace_path, cwd=self._tmp)

        self.assertFalse(result["ok"])
        self.assertIn("tracked-outside.txt", result["staged"])
        self.assertIn("tracked-outside.txt", result["outside"])

    def test_pre_commit_rejects_noncanonical_staged_filename(self) -> None:
        self._start_claim()
        ambiguous = Path(self._tmp) / " README.md"
        ambiguous.write_text("ambiguous\n", encoding="utf-8")
        subprocess.run(["git", "add", " README.md"], cwd=self._tmp, check=True)

        result = pre_commit(self.workspace_path, cwd=self._tmp)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "git-observation-error")
        self.assertIn("canonical Git form", result["errors"][0])

    def test_pre_commit_rejects_tampered_packet_context(self) -> None:
        self._start_claim()
        claim_path = next((self.workspace_path / ".palari" / "claims").glob("*.json"))
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        packet_path = self.workspace_path / claim["packet_path"]
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["context_hash"] = "sha256:tampered"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")

        result = pre_commit(self.workspace_path, cwd=self._tmp)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "invalid-claim")
        self.assertIn("context_hash", result["errors"][0])

    def test_pre_commit_recomputes_packet_context_hash(self) -> None:
        self._start_claim()
        claim_path = next((self.workspace_path / ".palari" / "claims").glob("*.json"))
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        packet_path = self.workspace_path / claim["packet_path"]
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["allowed_paths"]["write"] = ["random_file.txt"]
        packet_path.write_text(json.dumps(packet), encoding="utf-8")

        result = pre_commit(self.workspace_path, cwd=self._tmp)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "invalid-claim")
        self.assertIn("packet content", result["errors"][0])

    def test_pre_commit_rejects_changes_under_review_mode_claim(self) -> None:
        self._start_claim()
        claim_path = next((self.workspace_path / ".palari" / "claims").glob("*.json"))
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        packet_path = self.workspace_path / claim["packet_path"]
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        claim["mode"] = "review"
        packet["mode"] = "review"
        packet["allowed_paths"]["write"] = []
        packet["context_hash"] = _packet_hash(packet)
        claim["context_hash"] = packet["context_hash"]
        contract = compile_agent_session_contract(packet)
        contract_path = (
            self.workspace_path
            / ".palari"
            / "packets"
            / "session-contracts"
            / f"{contract['contract_id']}.json"
        )
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        claim["session_contract_path"] = contract_path.relative_to(
            self.workspace_path
        ).as_posix()
        claim["session_contract_digest"] = contract["contract_digest"]
        claim_path.write_text(json.dumps(claim), encoding="utf-8")
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        (Path(self._tmp) / "README.md").write_text("review edit\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self._tmp, check=True)

        result = pre_commit(self.workspace_path, cwd=self._tmp)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "read-only-claim")

    def test_pre_commit_does_not_union_overlapping_claim_authority(self) -> None:
        self._create_work("WORK-TEST-GIT-A")
        self._create_work("WORK-TEST-GIT-B")
        self._start_claim("WORK-TEST-GIT-A")
        self._start_claim("WORK-TEST-GIT-B")
        (Path(self._tmp) / "README.md").write_text("overlap\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self._tmp, check=True)

        result = pre_commit(self.workspace_path, cwd=self._tmp)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "ambiguous-claim")

    def test_cli_prints_rejection_before_nonzero_exit(self) -> None:
        self._start_claim()
        outside_file = Path(self._tmp) / "random_file.txt"
        outside_file.write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "add", "random_file.txt"], cwd=self._tmp, check=True)

        result = subprocess.run(
            [
                str(REPO_ROOT / "bin" / "palari"),
                "--workspace",
                str(self.workspace_path),
                "git",
                "pre-commit",
            ],
            cwd=self._tmp,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("random_file.txt", result.stderr)

    def test_pre_commit_no_git_repo(self) -> None:
        no_git = tempfile.mkdtemp()
        try:
            result = pre_commit(self.workspace_path, cwd=no_git)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "no-git-repo")
        finally:
            shutil.rmtree(no_git, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
