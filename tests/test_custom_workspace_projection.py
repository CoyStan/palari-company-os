from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_checks import build_agent_check
from palari_company_os.agent_advance import (
    _pending_scope_authority_workspace,
    _projection_artifact_paths,
)
from palari_company_os.agent_runtime import (
    _capture_governance_projection_snapshot,
    start_agent,
)
from palari_company_os.evidence_manifest import (
    _verification_artifact_hashes,
)
from palari_company_os.store import load_store, write_store
from palari_company_os.workspace import Workspace
from tests.workspace_fixture import write_current_agent_workspace


class CustomWorkspaceProjectionTests(unittest.TestCase):
    def test_projection_paths_and_pending_workspace_keep_custom_filename(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            default_path = root / "workspace.json"
            custom_path = root / "governance-state.json"
            write_current_agent_workspace(default_path)
            raw = load_store(default_path).data
            default_path.rename(custom_path)

            projection_paths = _projection_artifact_paths(custom_path, root)
            pending_workspace, error = _pending_scope_authority_workspace(
                {"before_projection": raw},
                custom_path,
            )

            self.assertEqual(
                projection_paths,
                {
                    "governance-state.json",
                    ".palari/governance-journal.v1.jsonl",
                    ".palari/governance-journal.v2.jsonl",
                },
            )
            self.assertEqual(error, "")
            self.assertIsNotNone(pending_workspace)
            self.assertEqual(pending_workspace.data_path, custom_path)

    def test_custom_file_claim_remains_valid_during_agent_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            default_path = root / "workspace.json"
            custom_path = root / "governance-state.json"
            write_current_agent_workspace(default_path)
            store = load_store(default_path)
            store.data["work_items"] = [
                {
                    "id": "WORK-CUSTOM",
                    "title": "Check an exact custom workspace claim",
                    "goal": "GOAL-REPO-0001",
                    "palari": "PALARI-STEWARD",
                    "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                    "risk": "R1",
                    "intensity": "light",
                    "required_approval_count": 0,
                    "scope": "Modify only README.md.",
                    "acceptance_target": "The custom-file claim remains valid.",
                    "status": "active",
                    "allowed_resources": ["README.md"],
                    "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                    "output_targets": ["README.md"],
                    "path_intents": [{"path": "README.md", "intent": "modify"}],
                    "forbidden_actions": ["deploy"],
                    "verification_expectations": ["custom claim check passes"],
                }
            ]
            for palari in store.data["palaris"]:
                if palari["id"] == "PALARI-STEWARD":
                    palari["active_work"] = ["WORK-CUSTOM"]
            write_store(store)
            default_path.rename(custom_path)
            (root / "README.md").write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"],
                check=True,
            )
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "custom claim"],
                check=True,
            )
            workspace = Workspace.load(custom_path)

            started = start_agent(
                workspace,
                custom_path,
                "WORK-CUSTOM",
                "PALARI-STEWARD",
            )
            checked = build_agent_check(
                Workspace.load(custom_path),
                "WORK-CUSTOM",
                "PALARI-STEWARD",
                changed_paths=["README.md"],
            )

            claim = next(
                item for item in checked["checks"] if item["code"] == "CLAIM_OWNED"
            )
            self.assertEqual(started["start"]["status"], "claimed")
            self.assertEqual(claim["status"], "pass")

    def test_snapshot_verifies_journal_against_exact_workspace_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "governance-state.json"
            data_path.write_text("{}\n", encoding="utf-8")
            baseline = {
                "git_root": str(root),
                "head_sha": "a" * 40,
            }
            report = {
                "ok": True,
                "status": "valid",
                "chain_valid": True,
                "pending": None,
                "current_workspace_digest": "sha256:" + "1" * 64,
                "replay_workspace_digest": "sha256:" + "1" * 64,
                "head_record_digest": "sha256:" + "2" * 64,
                "record_count": 1,
                "committed_transactions": 0,
                "continuity": {
                    "historical_continuity": True,
                    "break_sequences": [],
                },
            }
            scope_authority = {
                "baseline_digest": "sha256:" + "3" * 64,
                "current_digest": "sha256:" + "3" * 64,
            }

            with (
                patch(
                    "palari_company_os.agent_runtime._git_output",
                    return_value="b" * 40,
                ),
                patch(
                    "palari_company_os.agent_runtime._git_ancestor",
                    return_value=True,
                ),
                patch(
                    "palari_company_os.agent_runtime._git_range_paths",
                    return_value=["governance-state.json"],
                ),
                patch(
                    "palari_company_os.agent_runtime._governance_journal_history_error",
                    return_value="",
                ),
                patch(
                    "palari_company_os.agent_runtime._git_blob_bytes",
                    side_effect=lambda _root, _head, path: (
                        b"{}\n" if path == "governance-state.json" else None
                    ),
                ),
                patch(
                    "palari_company_os.agent_runtime.governance_projection_snapshot_error",
                    return_value="",
                ),
                patch(
                    "palari_company_os.governance_journal.verify_workspace_journal",
                    return_value=report,
                ) as verify_journal,
            ):
                snapshot = _capture_governance_projection_snapshot(
                    data_path,
                    baseline,
                    {"required_output": {}},
                    scope_authority=scope_authority,
                )

            self.assertIsNotNone(snapshot)
            verify_journal.assert_called_once_with(data_path)

    def test_evidence_classifies_exact_custom_workspace_file_as_projection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "governance-state.json"
            data_path.write_text('{"schema_version": 2}\n', encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"],
                check=True,
            )
            subprocess.run(["git", "-C", str(root), "add", data_path.name], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "custom workspace"],
                check=True,
            )
            head_sha = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True,
            ).strip()
            workspace = SimpleNamespace(
                path=root,
                data_path=data_path,
                attempts=[],
            )
            evidence = SimpleNamespace(
                artifacts=[data_path.name],
                attempt_id="",
                head_sha=head_sha,
            )

            hashes, exact_head_artifacts = _verification_artifact_hashes(
                workspace,
                evidence,
            )

            self.assertEqual(exact_head_artifacts, [data_path.name])
            self.assertEqual(hashes[0]["path"], data_path.name)
            self.assertEqual(hashes[0]["status"], "present")


if __name__ == "__main__":
    unittest.main()
