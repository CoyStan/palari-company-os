from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_advance import (
    _governed_artifacts,
    _projection_artifact_paths,
)
from palari_company_os.agent_parking import _control_projection_paths
from palari_company_os.authoring import (
    _prepare_record_for_create,
    _prepare_record_for_update,
)
from palari_company_os.claude_hooks import (
    _protected_governance_target,
    _without_palari_runtime,
)
from palari_company_os.data_map import build_data_map
from palari_company_os.evidence_manifest import (
    _governance_projection_artifacts,
    _governance_projection_paths,
)
from palari_company_os.governance_convergence import (
    _governance_projection_paths as _convergence_projection_paths,
)
from palari_company_os.linear_webhook import linear_webhook_event_log_path
from palari_company_os.mcp_server import McpContext, call_tool
from palari_company_os.store import load_store
from palari_company_os.verification_attestations import _cache_directory
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.maintainer_profile_fixture import create_git_repository


class MaintainerProfileRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.repo = create_git_repository(
            Path(self._temporary.name) / "repo",
            ordinary_workspace=True,
        )
        self.repo.init_maintainer()
        self.layout = self.repo.layout()

    def test_runtime_records_use_bound_hidden_state_root(self) -> None:
        cache = _cache_directory(self.repo.workspace_file, create=True)
        webhook_log = linear_webhook_event_log_path(self.repo.workspace_file)

        self.assertEqual(
            cache,
            self.repo.state_root / ".palari" / "verification",
        )
        self.assertEqual(
            webhook_log,
            self.repo.state_root / ".palari" / "linear-events.jsonl",
        )
        self.assertFalse((self.repo.root / ".palari" / "verification").exists())
        self.assertEqual(self.repo.status(), "")

    def test_maintainer_mcp_rejects_ordinary_workspace_override_before_start(
        self,
    ) -> None:
        root_governance_before = self.repo.root_governance_snapshot()
        context = McpContext(
            workspace=str(self.repo.workspace_file),
            repo=str(self.repo.root),
        )

        with self.assertRaisesRegex(
            WorkspaceError,
            "bound to its exact workspace",
        ):
            call_tool(
                "palari_agent_start",
                {
                    "workspace": str(self.repo.root / "workspace.json"),
                    "next": True,
                    "palari_id": "PALARI-STEWARD",
                },
                context,
            )

        self.assertEqual(
            self.repo.root_governance_snapshot(),
            root_governance_before,
        )

    def test_hidden_state_is_never_a_git_projection_or_governed_output(self) -> None:
        state_journal = (
            ".palari-company-os/.palari/governance-journal.v2.jsonl"
        )
        candidates = [
            "README.md",
            ".palari-company-os.json",
            ".palari-company-os/binding.json",
            state_journal,
        ]

        self.assertEqual(
            _projection_artifact_paths(
                self.repo.workspace_file,
                self.repo.root,
            ),
            set(),
        )
        self.assertEqual(
            _governance_projection_paths(
                self.repo.root,
                self.repo.workspace_file,
            ),
            set(),
        )
        self.assertEqual(
            _governance_projection_artifacts(
                self.repo.root,
                self.repo.workspace_file,
                candidates,
            ),
            [],
        )
        self.assertEqual(
            _convergence_projection_paths(
                self.repo.workspace_file,
                self.repo.root,
            ),
            [],
        )
        self.assertEqual(
            _governed_artifacts(
                candidates,
                self.repo.workspace_file,
                self.repo.root,
            ),
            ["README.md"],
        )
        self.assertEqual(
            _governed_artifacts(
                ["workspace.json"],
                self.repo.workspace_file,
                self.repo.root,
            ),
            ["workspace.json"],
        )

    def test_physical_hidden_state_is_ignored_bookkeeping_and_protected(self) -> None:
        ignored = _control_projection_paths(
            self.repo.workspace_file,
            self.repo.root,
        )
        runtime_claim = ".palari-company-os/.palari/claims/WORK-1.json"

        self.assertEqual(
            ignored,
            [
                ".palari-company-os.json",
                ".palari-company-os/**",
            ],
        )
        self.assertEqual(
            _without_palari_runtime(
                [runtime_claim, "README.md"],
                self.repo.workspace_file,
                self.repo.root,
            ),
            ["README.md"],
        )
        self.assertEqual(
            _protected_governance_target(
                str(self.repo.binding_file),
                self.repo.root,
                self.repo.root,
                self.repo.workspace_file,
            ),
            "Palari maintainer state",
        )
        self.assertEqual(
            _protected_governance_target(
                str(self.repo.workspace_file),
                self.repo.root,
                self.repo.root,
                self.repo.workspace_file,
            ),
            "workspace source of truth",
        )

    def test_data_map_reports_exact_physical_paths(self) -> None:
        payload = build_data_map(Workspace.load(self.repo.workspace_file))

        self.assertEqual(
            payload["storage"]["workspace_file"],
            ".palari-company-os.json",
        )
        self.assertEqual(
            payload["storage"]["journal_file"],
            ".palari-company-os/.palari/governance-journal.v2.jsonl",
        )
        self.assertTrue(payload["storage"]["journal_enabled"])

    def test_manual_evidence_stamping_uses_exact_governance_selector(self) -> None:
        store = load_store(self.repo.workspace_file)
        record = {
            "id": "EVIDENCE-ROUTING",
            "work_item_id": "WORK-ROUTING",
            "attempt_id": "ATTEMPT-ROUTING",
        }
        with patch(
            "palari_company_os.evidence_manifest.stamp_evidence_record",
            return_value=record,
        ) as stamp:
            _prepare_record_for_create(store, "evidence", record)
            stamp.assert_called_once()
            self.assertEqual(
                stamp.call_args.kwargs["governance_workspace_path"],
                self.repo.workspace_file,
            )

        with patch(
            "palari_company_os.evidence_manifest.stamp_evidence_record",
            return_value=record,
        ) as stamp:
            _prepare_record_for_update(
                store,
                "evidence",
                record,
                {"artifacts": ["README.md"]},
            )
            stamp.assert_called_once()
            self.assertEqual(
                stamp.call_args.kwargs["governance_workspace_path"],
                self.repo.workspace_file,
            )


class OrdinaryCustomRoutingCompatibilityTests(unittest.TestCase):
    def test_exact_custom_file_keeps_sibling_runtime_and_git_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "governance-state.json"
            data_path.write_text("{}\n", encoding="utf-8")

            self.assertEqual(
                _cache_directory(data_path, create=True),
                root / ".palari" / "verification",
            )
            self.assertEqual(
                linear_webhook_event_log_path(data_path),
                root / ".palari" / "linear-events.jsonl",
            )
            self.assertEqual(
                _projection_artifact_paths(data_path, root),
                {
                    "governance-state.json",
                    ".palari/governance-journal.v1.jsonl",
                    ".palari/governance-journal.v2.jsonl",
                },
            )


if __name__ == "__main__":
    unittest.main()
