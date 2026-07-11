from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.claude_hooks import (
    bash_write_targets,
    handle_hook_event,
    hooks_status,
    install_hooks,
    run_hook,
)


def _write_claim_and_packet(
    workspace_dir: Path,
    *,
    work_id: str = "WORK-0001",
    palari_id: str = "PALARI-SOFIA",
    mode: str = "execute",
    allowed_write: list[str] | None = None,
    lease_minutes: int = 30,
) -> None:
    packet_id = f"PACKET-{work_id}-{palari_id}-{mode.upper()}-V1"
    expires = datetime.now(timezone.utc) + timedelta(minutes=lease_minutes)
    claim = {
        "schema_version": "palari.agent_claim.v1",
        "work_item": work_id,
        "claimed_by": palari_id,
        "mode": mode,
        "lease_expires_at": expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "packet_id": packet_id,
        "packet_path": f".palari/packets/{packet_id}.json",
    }
    packet = {
        "packet_id": packet_id,
        "allowed_paths": {
            "read": list(allowed_write or []),
            "write": list(allowed_write or []),
        },
    }
    claims = workspace_dir / ".palari" / "claims"
    packets = workspace_dir / ".palari" / "packets"
    claims.mkdir(parents=True, exist_ok=True)
    packets.mkdir(parents=True, exist_ok=True)
    (claims / f"{work_id}.json").write_text(json.dumps(claim), encoding="utf-8")
    (packets / f"{packet_id}.json").write_text(json.dumps(packet), encoding="utf-8")


def _git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)


def _pre_tool_use(
    workspace_dir: Path,
    tool_name: str,
    tool_input: dict[str, Any],
    cwd: Path,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    payload = {"tool_name": tool_name, "tool_input": tool_input, "cwd": str(cwd)}
    return handle_hook_event("pre-tool-use", payload, workspace_dir, strict=strict)


def _decision(result: dict[str, Any]) -> str:
    return result.get("hookSpecificOutput", {}).get("permissionDecision", "")


class PreToolUseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        _git_repo(self.repo)
        self.workspace = self.repo / "ws"
        self.workspace.mkdir()
        (self.workspace / "workspace.json").write_text("{}", encoding="utf-8")

    def test_denies_exact_write_outside_boundary(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "deploy" / "production.yml")},
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("deploy/production.yml", reason)
        self.assertIn("docs/notes.md", reason)
        self.assertIn("WORK-0001", reason)

    def test_allows_exact_write_inside_boundary(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Edit",
            {"file_path": str(self.repo / "docs" / "notes.md")},
            self.repo,
        )

        self.assertEqual(_decision(result), "allow")

    def test_notebook_edit_uses_notebook_path(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs"])

        result = _pre_tool_use(
            self.workspace,
            "NotebookEdit",
            {"notebook_path": str(self.repo / "analysis.ipynb")},
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")

    def test_relative_path_resolves_against_cwd(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        (self.repo / "docs").mkdir()

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": "notes.md"},
            self.repo / "docs",
        )

        self.assertEqual(_decision(result), "allow")

    def test_bash_write_outside_boundary_asks(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Bash",
            {"command": "echo oops >> deploy/production.yml"},
            self.repo,
        )

        self.assertEqual(_decision(result), "ask")

    def test_benign_bash_gets_no_decision(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Bash",
            {"command": "git status && grep -r foo docs"},
            self.repo,
        )

        self.assertEqual(result, {})

    def test_read_tools_get_no_decision(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Read",
            {"file_path": str(self.repo / "deploy" / "production.yml")},
            self.repo,
        )

        self.assertEqual(result, {})

    def test_no_claim_is_undecided_unless_strict(self) -> None:
        tool_input = {"file_path": str(self.repo / "docs" / "notes.md")}

        relaxed = _pre_tool_use(self.workspace, "Write", tool_input, self.repo)
        strict = _pre_tool_use(self.workspace, "Write", tool_input, self.repo, strict=True)

        self.assertEqual(relaxed, {})
        self.assertEqual(_decision(strict), "ask")
        self.assertIn("palari agent start", strict["hookSpecificOutput"]["permissionDecisionReason"])

    def test_expired_lease_counts_as_no_claim(self) -> None:
        _write_claim_and_packet(
            self.workspace, allowed_write=["docs/notes.md"], lease_minutes=-5
        )

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "deploy" / "production.yml")},
            self.repo,
        )

        self.assertEqual(result, {})

    def test_review_mode_claim_grants_no_writes(self) -> None:
        _write_claim_and_packet(self.workspace, mode="review", allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "docs" / "notes.md")},
            self.repo,
        )

        self.assertEqual(_decision(result), "ask")
        self.assertIn("review-mode", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_path_outside_repo_is_undecided_unless_strict(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        outside = Path(self._tmp.name) / "elsewhere.txt"

        relaxed = _pre_tool_use(self.workspace, "Write", {"file_path": str(outside)}, self.repo)
        strict = _pre_tool_use(
            self.workspace, "Write", {"file_path": str(outside)}, self.repo, strict=True
        )

        self.assertEqual(relaxed, {})
        self.assertEqual(_decision(strict), "ask")

    def test_traversal_cannot_escape_the_boundary(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs"])

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "docs" / ".." / "deploy" / "production.yml")},
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")


class BashWriteTargetTests(unittest.TestCase):
    def test_redirection_targets(self) -> None:
        self.assertEqual(bash_write_targets("echo x > out.txt"), ["out.txt"])
        self.assertEqual(bash_write_targets("echo x >>logs/run.log"), ["logs/run.log"])
        self.assertEqual(bash_write_targets("cmd 2> err.log"), ["err.log"])

    def test_fd_duplication_is_not_a_target(self) -> None:
        self.assertEqual(bash_write_targets("cmd > out.txt 2>&1"), ["out.txt"])

    def test_mutating_commands(self) -> None:
        self.assertEqual(bash_write_targets("rm -f a.txt b.txt"), ["a.txt", "b.txt"])
        self.assertEqual(bash_write_targets("mv src.txt dst.txt"), ["src.txt", "dst.txt"])
        self.assertEqual(bash_write_targets("git rm docs/old.md"), ["docs/old.md"])
        self.assertEqual(bash_write_targets("sed -i s/a/b/ docs/x.md"), ["docs/x.md"])

    def test_read_only_commands_have_no_targets(self) -> None:
        self.assertEqual(bash_write_targets("git status"), [])
        self.assertEqual(bash_write_targets("grep -r foo docs"), [])
        self.assertEqual(bash_write_targets("sed s/a/b/ docs/x.md"), [])

    def test_separators_reset_command_state(self) -> None:
        self.assertEqual(
            bash_write_targets("git status && rm out.txt"),
            ["out.txt"],
        )


class StopHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        _git_repo(self.repo)
        self.workspace = self.repo / "ws"
        self.workspace.mkdir()
        (self.workspace / "workspace.json").write_text("{}", encoding="utf-8")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "notes.md").write_text("notes\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "init"],
            check=True,
        )

    def _stop(self, *, stop_hook_active: bool = False) -> dict[str, Any]:
        payload = {"cwd": str(self.repo), "stop_hook_active": stop_hook_active}
        return handle_hook_event("stop", payload, self.workspace)

    def test_blocks_stop_when_changes_escape_boundary(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        (self.repo / "rogue.txt").write_text("oops\n", encoding="utf-8")

        result = self._stop()

        self.assertEqual(result.get("decision"), "block")
        self.assertIn("rogue.txt", result["reason"])
        self.assertIn("palari agent check WORK-0001", result["reason"])

    def test_allows_stop_when_tree_is_inside_boundary(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        (self.repo / "docs" / "notes.md").write_text("edited\n", encoding="utf-8")

        self.assertEqual(self._stop(), {})

    def test_palari_runtime_state_does_not_block_stop(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        self.assertEqual(self._stop(), {})

    def test_respects_stop_hook_active_loop_guard(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        (self.repo / "rogue.txt").write_text("oops\n", encoding="utf-8")

        self.assertEqual(self._stop(stop_hook_active=True), {})

    def test_no_active_claim_allows_stop(self) -> None:
        (self.repo / "rogue.txt").write_text("oops\n", encoding="utf-8")

        self.assertEqual(self._stop(), {})


class SessionStartTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name) / "ws"
        self.workspace.mkdir()
        (self.workspace / "workspace.json").write_text("{}", encoding="utf-8")

    def _context(self) -> str:
        result = handle_hook_event("session-start", {"source": "startup"}, self.workspace)
        return result["hookSpecificOutput"]["additionalContext"]

    def test_injects_active_claim_contract(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        context = self._context()

        self.assertIn("WORK-0001", context)
        self.assertIn("docs/notes.md", context)
        self.assertIn("palari agent check WORK-0001", context)

    def test_points_unclaimed_sessions_at_agent_next(self) -> None:
        context = self._context()

        self.assertIn("palari agent next --json", context)
        self.assertIn("palari agent start WORK-ID", context)


class RunHookFailureTests(unittest.TestCase):
    def test_malformed_stdin_fails_open(self) -> None:
        result = run_hook("pre-tool-use", "/nonexistent", stdin=io.StringIO("not json"))

        self.assertNotIn("hookSpecificOutput", result)
        self.assertIn("systemMessage", result)

    def test_missing_workspace_fails_open(self) -> None:
        payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "x"}})

        result = run_hook("pre-tool-use", "/nonexistent", stdin=io.StringIO(payload))

        self.assertEqual(result, {})


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "project"
        self.workspace = self.project / "ws"
        self.workspace.mkdir(parents=True)
        (self.workspace / "workspace.json").write_text("{}", encoding="utf-8")
        self.settings = self.project / ".claude" / "settings.json"

    def _settings_data(self) -> dict[str, Any]:
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def test_install_writes_all_three_hooks(self) -> None:
        result = install_hooks(self.project, self.workspace)

        self.assertEqual(result["status"], "installed")
        data = self._settings_data()
        self.assertEqual(set(data["hooks"]), {"PreToolUse", "Stop", "SessionStart"})
        pre = data["hooks"]["PreToolUse"][0]
        self.assertEqual(pre["matcher"], "Write|Edit|NotebookEdit|Bash")
        self.assertIn(
            'palari --workspace "$CLAUDE_PROJECT_DIR/ws" claude hook pre-tool-use',
            pre["hooks"][0]["command"],
        )

    def test_install_is_idempotent(self) -> None:
        install_hooks(self.project, self.workspace)
        before = self.settings.read_text(encoding="utf-8")

        result = install_hooks(self.project, self.workspace)

        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(self.settings.read_text(encoding="utf-8"), before)

    def test_strict_flag_is_baked_into_pre_tool_use(self) -> None:
        install_hooks(self.project, self.workspace, strict=True)

        pre = self._settings_data()["hooks"]["PreToolUse"][0]
        self.assertIn("--strict", pre["hooks"][0]["command"])

    def test_install_preserves_foreign_hooks_and_settings(self) -> None:
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(
            json.dumps(
                {
                    "permissions": {"allow": ["Bash(npm test)"]},
                    "hooks": {
                        "PreToolUse": [
                            {"matcher": "Bash", "hooks": [{"type": "command", "command": "lint"}]}
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )

        install_hooks(self.project, self.workspace)

        data = self._settings_data()
        self.assertEqual(data["permissions"], {"allow": ["Bash(npm test)"]})
        commands = [
            hook["command"]
            for entry in data["hooks"]["PreToolUse"]
            for hook in entry["hooks"]
        ]
        self.assertIn("lint", commands)
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 2)

    def test_remove_deletes_only_palari_hooks(self) -> None:
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [{"hooks": [{"type": "command", "command": "notify-send done"}]}]
                    }
                }
            ),
            encoding="utf-8",
        )
        install_hooks(self.project, self.workspace)

        result = install_hooks(self.project, self.workspace, remove=True)

        self.assertEqual(result["status"], "removed")
        data = self._settings_data()
        self.assertEqual(set(data["hooks"]), {"Stop"})
        self.assertEqual(data["hooks"]["Stop"][0]["hooks"][0]["command"], "notify-send done")

    def test_local_writes_settings_local_json(self) -> None:
        install_hooks(self.project, self.workspace, local=True)

        self.assertTrue((self.project / ".claude" / "settings.local.json").exists())
        self.assertFalse(self.settings.exists())

    def test_workspace_at_project_root_uses_bare_placeholder(self) -> None:
        (self.project / "workspace.json").write_text("{}", encoding="utf-8")

        install_hooks(self.project, self.project)

        pre = self._settings_data()["hooks"]["PreToolUse"][0]
        self.assertIn('--workspace "$CLAUDE_PROJECT_DIR"', pre["hooks"][0]["command"])

    def test_project_local_wrapper_is_preferred(self) -> None:
        wrapper = self.project / "bin" / "palari"
        wrapper.parent.mkdir(parents=True)
        wrapper.write_text("#!/bin/sh\n", encoding="utf-8")

        install_hooks(self.project, self.workspace)

        pre = self._settings_data()["hooks"]["PreToolUse"][0]
        self.assertTrue(
            pre["hooks"][0]["command"].startswith('"$CLAUDE_PROJECT_DIR/bin/palari"')
        )

    def test_invalid_settings_json_is_not_clobbered(self) -> None:
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text("{broken", encoding="utf-8")

        result = install_hooks(self.project, self.workspace)

        self.assertEqual(result["status"], "error")
        self.assertEqual(self.settings.read_text(encoding="utf-8"), "{broken")

    def test_status_reports_install_and_claims(self) -> None:
        install_hooks(self.project, self.workspace, strict=True)
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        status = hooks_status(self.project, self.workspace)

        self.assertTrue(status["installed"])
        shared = status["settings_files"][0]
        self.assertEqual(
            shared["palari_hook_events"], ["PreToolUse", "SessionStart", "Stop"]
        )
        self.assertTrue(shared["strict"])
        self.assertEqual(status["active_claims"][0]["work_item"], "WORK-0001")
        self.assertEqual(
            status["active_claims"][0]["allowed_write_paths"], ["docs/notes.md"]
        )


if __name__ == "__main__":
    unittest.main()
