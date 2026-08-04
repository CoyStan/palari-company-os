from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cli_dispatch import run_command
from palari_company_os.cli_parser import build_parser
from palari_company_os.playbooks import (
    CORE_DEFAULT_PLAYBOOK_IDS,
    available_playbooks,
    playbook_catalog,
    recommend_playbooks,
)
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.workspace_fixture import current_recommendation_data


def _workspace() -> Workspace:
    return Workspace.from_raw(
        current_recommendation_data(),
        Path("/tmp/current-recommendation-contract"),
    )


class ParkedPlaybookContractTests(unittest.TestCase):
    def test_catalog_projects_the_configured_source_and_core_defaults(self) -> None:
        workspace = _workspace()
        playbooks = {playbook.id: playbook for playbook in available_playbooks(workspace)}
        payload = playbook_catalog(workspace)

        self.assertEqual(
            playbooks["superpowers:writing-plans"].uri,
            "https://github.com/obra/Superpowers/blob/main/skills/writing-plans/SKILL.md",
        )
        self.assertEqual(
            [item["id"] for item in payload["core_defaults"]],
            list(CORE_DEFAULT_PLAYBOOK_IDS),
        )

    def test_manual_defaults_and_automatic_guidance_merge_once(self) -> None:
        payload = recommend_playbooks(_workspace(), "WORK-1")
        recommended = {item["id"]: item for item in payload["recommended"]}

        self.assertTrue(
            recommended["superpowers:verification-before-completion"]["selected_by_user"]
        )
        self.assertTrue(
            recommended["superpowers:requesting-code-review"]["selected_by_user"]
        )
        self.assertTrue(recommended["superpowers:executing-plans"]["core_default"])
        self.assertTrue(recommended["superpowers:systematic-debugging"]["core_default"])
        self.assertIn("superpowers:brainstorming", recommended)
        self.assertEqual(
            recommended["superpowers:verification-before-completion"]["action_guidance"],
            "Run focused tests and full verification before claiming done.",
        )

    def test_unknown_selected_playbook_fails_closed(self) -> None:
        data = current_recommendation_data()
        data["work_items"][0]["recommended_playbooks"] = ["superpowers:not-a-skill"]

        with self.assertRaisesRegex(WorkspaceError, "not included by source superpowers"):
            Workspace.from_raw(data, Path("/tmp/unknown-playbook"))

    def test_parser_and_dispatch_are_one_read_only_wiring_boundary(self) -> None:
        workspace = _workspace()
        args = build_parser().parse_args(
            ["--workspace", "/unused", "playbooks", "recommend", "WORK-1", "--json"]
        )

        with patch.object(Workspace, "load", return_value=workspace) as load:
            result = run_command(args)

        load.assert_called_once_with("/unused")
        self.assertEqual(result.kind, "playbook-recommendations")
        self.assertTrue(result.as_json)
        self.assertEqual(result.payload["work_item"], "WORK-1")


if __name__ == "__main__":
    unittest.main()
