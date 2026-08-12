from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_status import build_agent_status


class _Workspace:
    name = "Status Test Workspace"
    data_path = Path("/tmp/palari-status-workspace/workspace.json")


class _Operation:
    def __init__(self, workspace: _Workspace) -> None:
        self.workspace = workspace
        self.work_id = "WORK-STATUS"
        self.palari_id = "PALARI-STATUS"
        self.mode = "execute"
        self.calls = {"brief": 0, "check": 0, "directive": 0}
        self.handoff_ready = False

    def brief(self) -> dict[str, Any]:
        self.calls["brief"] += 1
        return {
            "workspace": self.workspace.name,
            "status": "ready",
            "packet_id": "PACKET-STATUS",
            "context_hash": "sha256:packet",
            "one_sentence_instruction": "Make one bounded change.",
            "agent": {"id": self.palari_id},
            "work_item": {"id": self.work_id, "title": "Status projection"},
            "allowed_paths": {"read": ["README.md"], "write": ["README.md"]},
            "allowed_resources": ["README.md"],
            "allowed_sources": [{"id": "SOURCE-REPO"}],
            "allowed_capabilities": [{"id": "repo-code"}],
            "forbidden_actions": ["deploy"],
            "stop_conditions": ["Stop at human approval."],
            "dependencies": [],
            "completion_contract": {"requires_evidence": True},
            "blockers": [],
        }

    def check(self) -> dict[str, Any]:
        self.calls["check"] += 1
        return {
            "check_id": "CHECK-STATUS",
            "ok": False,
            "next_step_type": "run-checks",
            "checks": [
                {
                    "code": "EVIDENCE_PRESENT",
                    "required": True,
                    "status": "fail",
                }
            ],
        }

    def directive(self) -> dict[str, Any]:
        self.calls["directive"] += 1
        return {
            "status": "missing-proof",
            "owner": "agent",
            "agent_may_execute": True,
            "next_step_type": "run-checks",
            "next_action": {
                "type": "missing-proof",
                "owner": "agent",
                "agent_may_execute": True,
                "command": "palari agent advance WORK-STATUS --as PALARI-STATUS --json",
                "message": "Run deterministic verification.",
            },
            "review_boundary": False,
            "human_boundary": False,
            "blockers": [
                {
                    "code": "EVIDENCE_PRESENT",
                    "resolution": {
                        "class": "automatic-reconciliation",
                        "owner": "system",
                        "automatic": True,
                    },
                }
            ],
            "resolution_summary": {
                "primary_class": "automatic-reconciliation",
                "state": "action-required",
            },
            "missing_requirements": [{"code": "EVIDENCE_PRESENT"}],
            "completed_requirements": [{"code": "PACKET_READY"}],
            "automatic_transitions": [],
            "handoff_guidance": (
                [{"code": "REVIEW_HANDOFF"}]
                if self.handoff_ready
                else []
            ),
            "report_guidance": "Inspect current status.",
            "next_allowed_commands": [
                "palari agent advance WORK-STATUS --as PALARI-STATUS --json"
            ],
        }


class AgentStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = _Workspace()
        self.operation = _Operation(self.workspace)

    def build_status(self) -> dict[str, Any]:
        return build_agent_status(
            self.workspace,  # type: ignore[arg-type]
            self.operation.work_id,
            self.operation.palari_id,
            operation=self.operation,  # type: ignore[arg-type]
        )

    def test_status_uses_one_request_local_observation(self) -> None:
        status = self.build_status()

        self.assertEqual(
            self.operation.calls,
            {"brief": 1, "check": 1, "directive": 1},
        )
        self.assertEqual(status["schema_version"], "palari.agent_status.v1")
        self.assertFalse(status["would_mutate"])
        self.assertEqual(status["status"], "missing-proof")
        self.assertEqual(status["owner"], "agent")
        self.assertTrue(status["agent_may_execute"])
        self.assertEqual(status["next_step_type"], "run-checks")
        self.assertIn("--workspace", status["next_action"]["command"])

    def test_status_preserves_limits_checks_and_directive_state(self) -> None:
        status = self.build_status()

        self.assertEqual(
            status["task_limits"]["allowed_paths"],
            {"read": ["README.md"], "write": ["README.md"]},
        )
        self.assertEqual(status["task_limits"]["forbidden_actions"], ["deploy"])
        self.assertEqual(status["check"]["check_id"], "CHECK-STATUS")
        self.assertFalse(status["check"]["ok"])
        self.assertEqual(status["check"]["requirements"][0]["code"], "EVIDENCE_PRESENT")
        self.assertEqual(
            [stage["name"] for stage in status["stages"]],
            ["brief", "check", "next"],
        )
        self.assertEqual(status["blockers"][0]["code"], "EVIDENCE_PRESENT")
        self.assertEqual(
            status["resolution"]["primary_class"],
            "automatic-reconciliation",
        )
        self.assertEqual(status["missing_requirements"], [{"code": "EVIDENCE_PRESENT"}])
        self.assertEqual(status["completed_requirements"], [{"code": "PACKET_READY"}])

    def test_status_includes_boundary_actions_when_they_are_eligible(self) -> None:
        self.operation.handoff_ready = True
        action_projection = {
            "review_handoff": {"status": "review-needed"},
            "decision_handoff": None,
            "human_approval_handoff": None,
            "agent_action_commands": [{"command": "palari review record ..."}],
            "agent_action_boundary": {"agent_may_execute": True},
            "human_action_commands": [],
            "human_action_boundary": {"agent_may_execute": False},
            "next_allowed_commands": ["palari review guide WORK-STATUS --json"],
        }
        with patch(
            "palari_company_os.agent_status.build_agent_handoff",
            return_value=action_projection,
        ) as build_actions:
            status = self.build_status()

        build_actions.assert_called_once()
        self.assertEqual(status["review"], {"status": "review-needed"})
        self.assertEqual(
            status["agent_action_commands"],
            action_projection["agent_action_commands"],
        )
        self.assertFalse(status["human_action_boundary"]["agent_may_execute"])
        self.assertEqual(
            status["next_allowed_commands"],
            action_projection["next_allowed_commands"],
        )


if __name__ == "__main__":
    unittest.main()
