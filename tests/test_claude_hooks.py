from __future__ import annotations

import io
import hashlib
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
from palari_company_os.agent_file_changes import capture_git_baseline
from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.agent_runtime import GIT_WITNESS_VERSION, _create_git_witness
from palari_company_os.workspace import Workspace


def _write_hook_workspace(workspace_dir: Path) -> None:
    work_ids = ("WORK-0001", "WORK-A", "WORK-B")
    data = {
        "schema_version": 2,
        "name": "Hook Test Workspace",
        "goals": [
            {
                "id": "GOAL-HOOK",
                "title": "Exercise hooks",
                "status": "active",
                "linked_work": list(work_ids),
            }
        ],
        "humans": [{"id": "HUMAN-HOOK", "name": "Hook Human"}],
        "palaris": [
            {
                "id": "PALARI-SOFIA",
                "name": "Sofia",
                "role": "Hook worker",
                "owner_human": "HUMAN-HOOK",
                "linked_goals": ["GOAL-HOOK"],
                "active_work": list(work_ids),
            }
        ],
        "sources": [
            {
                "id": "SOURCE-HOOK",
                "label": "Repository",
                "kind": "repo_files",
                "uri": ".",
                "allowed_palaris": ["PALARI-SOFIA"],
                "data_class": "internal",
                "authority": "company_owned",
                "access_mode": "read",
                "selected": True,
            }
        ],
        "work_items": [],
        "attempts": [],
        "evidence_runs": [],
        "review_verdicts": [],
        "human_decisions": [],
        "receipts": [],
        "decisions": [],
        "outcomes": [],
    }
    default_paths = {
        "WORK-0001": ["docs/notes.md"],
        "WORK-A": ["docs"],
        "WORK-B": ["docs"],
    }
    for work_id in work_ids:
        data["work_items"].append(
            {
                "id": work_id,
                "title": work_id,
                "goal": "GOAL-HOOK",
                "palari": "PALARI-SOFIA",
                "risk": "R1",
                "intensity": "light",
                "status": "active",
                "scope": "Exercise hook enforcement.",
                "acceptance_target": "Unsafe writes are blocked.",
                "allowed_resources": default_paths[work_id],
                "allowed_sources": ["SOURCE-HOOK"],
                "forbidden_actions": ["deploy"],
                "required_approval_count": 0,
            }
        )
    (workspace_dir / "workspace.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
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
    workspace_file = workspace_dir / "workspace.json"
    data = json.loads(workspace_file.read_text(encoding="utf-8"))
    work = next(item for item in data["work_items"] if item["id"] == work_id)
    expected_paths = list(allowed_write or [])
    if work["allowed_resources"] != expected_paths:
        work["allowed_resources"] = expected_paths
        workspace_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    packet = build_agent_brief(
        Workspace.load(workspace_dir), work_id, palari_id, "execute"
    )
    packet_id = str(packet["packet_id"])
    expires = datetime.now(timezone.utc) + timedelta(minutes=lease_minutes)
    if mode != "execute":
        packet["mode"] = mode
    context_hash = _packet_hash(packet)
    packet["context_hash"] = context_hash
    git_baseline = capture_git_baseline(workspace_dir)
    git_baseline_hash = _object_hash(git_baseline)
    git_witness_ref = _create_git_witness(work_id, git_baseline)
    claim = {
        "schema_version": "palari.agent_claim.v1",
        "work_item": work_id,
        "claimed_by": palari_id,
        "mode": mode,
        "lease_expires_at": expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "packet_id": packet_id,
        "context_hash": context_hash,
        "packet_path": f".palari/packets/{packet_id}.json",
        "git_baseline": git_baseline,
        "git_baseline_hash": git_baseline_hash,
        "git_baseline_path": f".palari/claims/{work_id}.baseline",
        "git_witness_version": GIT_WITNESS_VERSION if git_witness_ref else "",
        "git_witness_ref": git_witness_ref,
    }
    claims = workspace_dir / ".palari" / "claims"
    packets = workspace_dir / ".palari" / "packets"
    claims.mkdir(parents=True, exist_ok=True)
    packets.mkdir(parents=True, exist_ok=True)
    baseline = {
        "schema_version": "palari.persisted_git_baseline.v1",
        "work_item": work_id,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "git_baseline": git_baseline,
        "git_baseline_hash": git_baseline_hash,
        "git_witness_version": GIT_WITNESS_VERSION if git_witness_ref else "",
        "git_witness_ref": git_witness_ref,
    }
    (claims / f"{work_id}.json").write_text(json.dumps(claim), encoding="utf-8")
    (claims / f"{work_id}.baseline").write_text(
        json.dumps(baseline), encoding="utf-8"
    )
    (packets / f"{packet_id}.json").write_text(json.dumps(packet), encoding="utf-8")


def _packet_hash(packet: dict[str, Any]) -> str:
    stable = {
        key: value for key, value in packet.items() if key not in {"created_at", "context_hash"}
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _object_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


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
        _write_hook_workspace(self.workspace)

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

    def test_opaque_interpreter_bash_requires_human_review(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Bash",
            {"command": "python3 -c 'open(\".palari/claims/x\", \"w\").write(\"x\")'"},
            self.repo,
        )

        self.assertEqual(_decision(result), "ask")
        self.assertIn("opaque interpreter", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_unreviewed_executable_bash_requires_human_review(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Bash",
            {"command": "./docs/rewrite-runtime-state"},
            self.repo,
        )

        self.assertEqual(_decision(result), "ask")
        self.assertIn(
            "unreviewed executable",
            result["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_invalid_active_claim_cannot_fail_open_for_unreviewed_executable(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        packet_path = next((self.workspace / ".palari" / "packets").glob("*.json"))
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["context_hash"] = "sha256:tampered"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")

        result = _pre_tool_use(
            self.workspace,
            "Bash",
            {"command": "./docs/rewrite-runtime-state"},
            self.repo,
        )

        self.assertEqual(_decision(result), "ask")
        self.assertIn(
            "unreviewed executable",
            result["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_human_acceptance_command_is_denied_to_agent_shell(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Bash",
            {
                "command": (
                    "./bin/palari --workspace workspace.json work accept WORK-1 "
                    "--by HUMAN-FOUNDER --reviewed-head abc123 --json"
                )
            },
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")
        self.assertIn("human-only", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_dynamic_human_acceptance_command_requires_human_review(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Bash",
            {
                "command": (
                    "P=./bin/palari; $P --workspace workspace.json work accept WORK-1 "
                    "--by HUMAN-FOUNDER --reviewed-head abc123 --json"
                )
            },
            self.repo,
        )

        self.assertEqual(_decision(result), "ask")
        self.assertIn(
            "dynamic shell expansion",
            result["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_dynamic_human_acceptance_requires_review_without_active_claim(self) -> None:
        result = _pre_tool_use(
            self.workspace,
            "Bash",
            {
                "command": (
                    "P=./bin/palari; $P --workspace workspace.json work accept WORK-1 "
                    "--by HUMAN-FOUNDER --reviewed-head abc123 --json"
                )
            },
            self.repo,
        )

        self.assertEqual(_decision(result), "ask")

    def test_allowed_write_cannot_mask_later_authority_or_witness_command(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        commands = (
            (
                "touch docs/notes.md ; P=./bin/palari ; $P --workspace workspace.json "
                "work accept WORK-1 --by HUMAN-FOUNDER --reviewed-head abc123 --json"
            ),
            (
                f"touch docs/notes.md ; git -C {self.repo} update-ref "
                "refs/palari/claims/test abc123"
            ),
            (
                f"touch docs/notes.md ; git -C {self.repo} reflog expire "
                "--expire=now --all"
            ),
        )

        for command in commands:
            with self.subTest(command=command):
                result = _pre_tool_use(
                    self.workspace,
                    "Bash",
                    {"command": command},
                    self.repo,
                )
                self.assertEqual(_decision(result), "ask")

    def test_packet_authority_update_is_denied_to_agent_shell(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])

        result = _pre_tool_use(
            self.workspace,
            "Bash",
            {
                "command": (
                    "./bin/palari --workspace workspace.json work update WORK-0001 "
                    "--list allowed_resources=docs/notes.md,deploy"
                )
            },
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")
        self.assertIn("work update", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_git_global_options_do_not_hide_witness_mutations(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        commands = (
            f"git -C {self.repo} update-ref refs/palari/claims/test abc123",
            (
                f"git --git-dir={self.repo / '.git'} reflog expire "
                "--expire=now --all"
            ),
            (
                f"git --work-tree {self.repo} --git-dir {self.repo / '.git'} "
                "update-ref -d refs/palari/claims/test"
            ),
            f"git status\ngit -C {self.repo} reflog expire --expire=now --all",
        )

        for command in commands:
            with self.subTest(command=command):
                result = _pre_tool_use(
                    self.workspace,
                    "Bash",
                    {"command": command},
                    self.repo,
                )
                self.assertEqual(_decision(result), "ask")
                self.assertIn(
                    "Git metadata mutation",
                    result["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_git_config_and_environment_cannot_launch_safe_subcommand_helpers(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        commands = (
            (
                "git -c diff.external=./docs/rewrite-runtime-state diff "
                "-- docs/notes.md"
            ),
            "GIT_EXTERNAL_DIFF=./docs/rewrite-runtime-state git diff -- docs/notes.md",
            "git diff --ext-diff -- docs/notes.md",
            "rg --pre ./docs/rewrite-runtime-state pattern docs",
        )

        for command in commands:
            with self.subTest(command=command):
                result = _pre_tool_use(
                    self.workspace,
                    "Bash",
                    {"command": command},
                    self.repo,
                )
                self.assertEqual(_decision(result), "ask")

    def test_coordinated_witness_rewrite_sequence_never_auto_authorizes(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        commands = (
            "P=python3; $P -c 'rewrite claim and baseline'",
            f"git -C {self.repo} update-ref -d refs/palari/claims/test",
            f"git -C {self.repo} reflog expire --expire=now --all",
            f"git -C {self.repo} update-ref refs/palari/claims/test abc123",
        )

        for command in commands:
            with self.subTest(command=command):
                result = _pre_tool_use(
                    self.workspace,
                    "Bash",
                    {"command": command},
                    self.repo,
                )
                self.assertEqual(_decision(result), "ask")

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

    def test_workspace_truth_is_protected_even_without_active_claim(self) -> None:
        exact = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.workspace / "workspace.json")},
            self.repo,
        )
        shell = _pre_tool_use(
            self.workspace,
            "Bash",
            {"command": "cp docs/new-workspace.json ws/workspace.json"},
            self.repo,
        )

        self.assertEqual(_decision(exact), "deny")
        self.assertEqual(_decision(shell), "ask")
        self.assertIn(
            "workspace source of truth",
            exact["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_split_collection_truth_is_protected_without_active_claim(self) -> None:
        workspace_file = self.workspace / "workspace.json"
        data = json.loads(workspace_file.read_text(encoding="utf-8"))
        data["collection_files"] = {"goals": ["records/goals.json"]}
        workspace_file.write_text(json.dumps(data), encoding="utf-8")

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.workspace / "records" / "goals.json")},
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")
        self.assertIn(
            "workspace source of truth",
            result["hookSpecificOutput"]["permissionDecisionReason"],
        )

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

        self.assertEqual(_decision(result), "deny")
        self.assertIn("review-mode", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_path_outside_repo_is_undecided_unless_strict(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        outside = Path(self._tmp.name) / "elsewhere.txt"

        relaxed = _pre_tool_use(self.workspace, "Write", {"file_path": str(outside)}, self.repo)
        strict = _pre_tool_use(
            self.workspace, "Write", {"file_path": str(outside)}, self.repo, strict=True
        )

        self.assertEqual(_decision(relaxed), "deny")
        self.assertEqual(_decision(strict), "deny")

    def test_traversal_cannot_escape_the_boundary(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs"])

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "docs" / ".." / "deploy" / "production.yml")},
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")

    def test_symlink_cannot_escape_the_boundary(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs"])
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        (self.repo / "docs").symlink_to(outside, target_is_directory=True)

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "docs" / "secret.txt")},
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")

    def test_tampered_packet_context_blocks_write(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs"])
        packet_path = next((self.workspace / ".palari" / "packets").glob("*.json"))
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["context_hash"] = "sha256:tampered"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "docs" / "notes.md")},
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")
        self.assertIn("context_hash", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_coordinated_packet_and_claim_rehash_cannot_expand_scope(self) -> None:
        _write_claim_and_packet(self.workspace, allowed_write=["docs/notes.md"])
        packet_path = next((self.workspace / ".palari" / "packets").glob("*.json"))
        claim_path = self.workspace / ".palari" / "claims" / "WORK-0001.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["allowed_paths"] = {"read": ["deploy"], "write": ["deploy"]}
        packet["context_hash"] = _packet_hash(packet)
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        claim["context_hash"] = packet["context_hash"]
        claim_path.write_text(json.dumps(claim), encoding="utf-8")

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "deploy" / "production.yml")},
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")
        self.assertIn(
            "current workspace packet",
            result["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_overlapping_claims_do_not_union_authority(self) -> None:
        _write_claim_and_packet(self.workspace, work_id="WORK-A", allowed_write=["docs"])
        _write_claim_and_packet(self.workspace, work_id="WORK-B", allowed_write=["docs"])

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "docs" / "notes.md")},
            self.repo,
        )

        self.assertEqual(_decision(result), "deny")
        self.assertIn("multiple active execute claims", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_distinct_claim_selects_single_covering_context(self) -> None:
        _write_claim_and_packet(self.workspace, work_id="WORK-A", allowed_write=["docs/a"])
        _write_claim_and_packet(self.workspace, work_id="WORK-B", allowed_write=["docs/b"])

        result = _pre_tool_use(
            self.workspace,
            "Write",
            {"file_path": str(self.repo / "docs" / "a" / "notes.md")},
            self.repo,
        )

        self.assertEqual(_decision(result), "allow")
        self.assertIn("WORK-A", result["hookSpecificOutput"]["permissionDecisionReason"])


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
        _write_hook_workspace(self.workspace)
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

    def test_multiple_execute_claims_block_stop_until_pinned(self) -> None:
        _write_claim_and_packet(self.workspace, work_id="WORK-A", allowed_write=["docs"])
        _write_claim_and_packet(self.workspace, work_id="WORK-B", allowed_write=["docs"])

        result = self._stop()

        self.assertEqual(result.get("decision"), "block")
        self.assertIn("Multiple active execute claims", result["reason"])

    def test_review_mode_claim_blocks_stop_after_file_change(self) -> None:
        _write_claim_and_packet(
            self.workspace, mode="review", allowed_write=["docs/notes.md"]
        )
        (self.repo / "docs" / "notes.md").write_text("review changed\n", encoding="utf-8")

        result = self._stop()

        self.assertEqual(result.get("decision"), "block")
        self.assertIn("review-mode", result["reason"])


class SessionStartTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name) / "ws"
        self.workspace.mkdir()
        _write_hook_workspace(self.workspace)

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
        _write_hook_workspace(self.workspace)
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
