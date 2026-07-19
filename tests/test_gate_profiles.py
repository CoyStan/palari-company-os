from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cli_dispatch import run_command
from palari_company_os.cli_parser import build_parser
from palari_company_os.gate_profiles import GATE_PROFILES, gate_profile_catalog, recommend_gates
from palari_company_os.workspace import Workspace
from tests.workspace_fixture import current_recommendation_data


def _workspace() -> Workspace:
    return Workspace.from_raw(
        current_recommendation_data(),
        Path("/tmp/current-recommendation-contract"),
    )


class ParkedGateProfileContractTests(unittest.TestCase):
    def test_catalog_is_read_only_and_exposes_the_exact_profile_set(self) -> None:
        payload = gate_profile_catalog(_workspace())

        self.assertEqual(payload["schema_version"], "palari.gate_profiles.v1")
        self.assertFalse(payload["would_mutate"])
        self.assertEqual(
            [profile["id"] for profile in payload["profiles"]],
            [
                "prompt-authority",
                "source-boundary",
                "external-write",
                "human-approval",
                "deploy-runtime",
                "privacy-multimodal",
                "product-overclaim",
            ],
        )
        self.assertEqual(len(payload["profiles"]), len(GATE_PROFILES))

    def test_recommendations_remain_advisory_and_deterministic(self) -> None:
        workspace = _workspace()

        first = recommend_gates(workspace, "WORK-1")
        second = recommend_gates(workspace, "WORK-1")

        self.assertEqual(first, second)
        self.assertFalse(first["would_mutate"])
        self.assertEqual(
            [item["id"] for item in first["recommended_gates"]],
            ["source-boundary"],
        )
        self.assertEqual(first["review_contracts"][0]["gate_id"], "source-boundary")

        data = current_recommendation_data()
        data["sources"] = []
        data["work_items"][0]["allowed_sources"] = []
        local_only = Workspace.from_raw(data, Path("/tmp/local-only-recommendation"))
        no_gate = recommend_gates(local_only, "WORK-1")
        self.assertTrue(no_gate["no_special_gate_required"])
        self.assertEqual(no_gate["recommended_gates"], [])

    def test_parser_and_dispatch_are_one_read_only_wiring_boundary(self) -> None:
        workspace = _workspace()
        args = build_parser().parse_args(
            ["--workspace", "/unused", "gate", "recommend", "WORK-1", "--json"]
        )

        with patch.object(Workspace, "load", return_value=workspace) as load:
            result = run_command(args)

        load.assert_called_once_with("/unused")
        self.assertEqual(result.kind, "gate-recommendations")
        self.assertTrue(result.as_json)
        self.assertEqual(result.payload["work_item"]["id"], "WORK-1")


if __name__ == "__main__":
    unittest.main()
