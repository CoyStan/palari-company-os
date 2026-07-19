from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cli_dispatch import run_command
from palari_company_os.cli_parser import build_parser
from palari_company_os.decision_guides import build_decision_guide
from palari_company_os.validation import COLLECTION_FILE_KEYS
from palari_company_os.workspace import Workspace


def _workspace() -> Workspace:
    raw: dict[str, object] = {
        "schema_version": 2,
        "name": "Decision Guide Contract",
    }
    for collection in COLLECTION_FILE_KEYS:
        raw[collection] = []
    raw["goals"] = [
        {
            "id": "GOAL-1",
            "title": "Keep authority explicit",
            "owner": "HUMAN-OWNER",
            "status": "active",
        }
    ]
    raw["humans"] = [
        {
            "id": "HUMAN-OWNER",
            "name": "Product Owner",
            "role": "Product authority",
            "approval_capabilities": ["product"],
        }
    ]
    raw["palaris"] = [
        {
            "id": "PALARI-1",
            "name": "Bounded Worker",
            "role": "Implementer",
            "owner_human": "HUMAN-OWNER",
            "linked_goals": ["GOAL-1"],
        }
    ]
    raw["work_items"] = [
        {
            "id": "WORK-1",
            "title": "Resolve one bounded product choice",
            "goal": "GOAL-1",
            "palari": "PALARI-1",
            "risk": "R2",
            "intensity": "standard",
            "status": "blocked",
            "scope": "Wait for the named product owner.",
            "allowed_resources": ["notes/decision.md"],
            "allowed_actions": ["local_write"],
            "output_targets": ["notes/decision.md"],
            "forbidden_actions": ["external_write"],
            "acceptance_target": "The choice is explicit.",
            "required_approval_count": 1,
            "required_approval_capability": "product",
        }
    ]
    raw["decisions"] = [
        {
            "id": "DECISION-1",
            "question": "Which local-only option should be used?",
            "status": "open",
            "context": "No external effect is authorized.",
            "options": ["Keep local", "Defer until evidence exists"],
            "tradeoffs": ["Local is reversible", "Deferral preserves uncertainty"],
            "recommendation": "Keep local",
            "safe_default": "Defer until evidence exists",
            "required_human": "HUMAN-OWNER",
            "required_role": "Product authority",
            "linked_goal": "GOAL-1",
            "linked_work": "WORK-1",
            "linked_palari": "PALARI-1",
        }
    ]
    return Workspace.from_raw(raw, Path("/tmp/palari-decision-guide-contract"))


class DecisionGuideTests(unittest.TestCase):
    def test_open_decision_projects_only_exact_linked_context(self) -> None:
        payload = build_decision_guide(_workspace(), "DECISION-1")

        self.assertEqual(payload["schema_version"], "palari.decision_guide.v1")
        self.assertEqual(payload["status"], "open")
        self.assertFalse(payload["would_mutate"])
        self.assertEqual(payload["linked_work"]["id"], "WORK-1")
        self.assertEqual(payload["required_human"]["id"], "HUMAN-OWNER")
        self.assertIn("safe default", " ".join(payload["decision_focus"]))
        self.assertIn('--set "result=..."', payload["decision_update_command_template"])
        commands = {
            item["result"]: item["command"] for item in payload["decision_update_commands"]
        }
        self.assertIn(
            "--set 'result=Defer until evidence exists'",
            commands["Defer until evidence exists"],
        )

    def test_linked_work_resolves_the_same_open_decision(self) -> None:
        payload = build_decision_guide(_workspace(), "WORK-1")

        self.assertEqual(payload["decision"]["id"], "DECISION-1")

    def test_parser_and_dispatch_are_one_read_only_translation_boundary(self) -> None:
        workspace = _workspace()
        args = build_parser().parse_args(
            ["--workspace", "/unused", "decision", "guide", "WORK-1", "--json"]
        )

        with patch.object(Workspace, "load", return_value=workspace) as load:
            result = run_command(args)

        load.assert_called_once_with("/unused")
        self.assertEqual(result.kind, "decision-guide")
        self.assertTrue(result.as_json)
        self.assertEqual(result.payload["decision"]["id"], "DECISION-1")


if __name__ == "__main__":
    unittest.main()
