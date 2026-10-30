from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os import cli_dispatch, integrations, linear_adapter
from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.approval_packs import _work_member
from palari_company_os.authoring import create_record, update_record
from palari_company_os.cli_dispatch import run_command
from palari_company_os.cli_parser import build_parser
from palari_company_os.workspace import Workspace, WorkspaceError
from palari_company_os.transition_checks import check_transition
from tests.maintainer_profile_fixture import create_git_repository


class MaintainerExternalSurfaceRegressionTests(unittest.TestCase):
    def test_generic_authoring_cannot_manufacture_human_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            before = repo.safety_snapshot()
            for kind in ("human-decision", "acceptance"):
                with self.subTest(kind=kind), self.assertRaisesRegex(
                    WorkspaceError,
                    "dedicated human-authority command",
                ):
                    create_record(
                        str(repo.workspace_file),
                        kind,
                        {
                            "id": f"{kind.upper()}-FORGED",
                            "work_item_id": "WORK-FORGED",
                            "human_id": "HUMAN-FOUNDER",
                            "decision": "accepted",
                            "status": "accepted",
                        },
                        command="test forged human authority",
                        actor="PALARI-CLAUDE",
                    )
            bypass: Any = {"_authority_checked": True}
            with self.assertRaisesRegex(TypeError, "_authority_checked"):
                create_record(
                    str(repo.workspace_file),
                    "human-decision",
                    {
                        "id": "HUMAN-DECISION-FORGED-BYPASS",
                        "work_item_id": "WORK-FORGED",
                        "human_id": "HUMAN-FOUNDER",
                        "decision": "accepted",
                        "status": "accepted",
                    },
                    command="test removed authority bypass",
                    actor="PALARI-CLAUDE",
                    **bypass,
                )
            self.assertEqual(repo.safety_snapshot(), before)

    def test_embedded_push_action_is_denied_by_local_only_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()
            added = repo.profile_json(
                "work",
                "add",
                "Reject an embedded push action",
                "--modify",
                "README.md",
                "--risk",
                "R1",
                "--intensity",
                "light",
                "--approvals",
                "0",
                "--verify",
                "Local-only action policy holds.",
                "--json",
            )
            work_id = str(added["work_item"]["id"])
            for action in (
                "force_push_branch",
                "force.push.branch",
                "forcepushbranch",
                "send_email",
                "provider-read",
            ):
                with self.subTest(action=action):
                    update_record(
                        str(repo.workspace_file),
                        "work",
                        work_id,
                        {"allowed_actions": ["local_write", action]},
                        command="test denied action spelling",
                        actor="HUMAN-FOUNDER",
                    )

                    packet = build_agent_brief(
                        Workspace.load(repo.workspace_file),
                        work_id,
                        "PALARI-CLAUDE",
                        "execute",
                    )

                    self.assertEqual(packet["status"], "blocked", packet)
                    blockers = {item["code"]: item for item in packet["blockers"]}
                    denial = blockers[
                        "MAINTAINER_PROFILE_CAPABILITY_DENIED"
                    ]["message"]
                    self.assertIn(action, denial)

                    workspace = Workspace.load(repo.workspace_file)
                    completion = check_transition(
                        workspace,
                        "work_complete",
                        work_id,
                    )
                    self.assertIn(
                        "MAINTAINER_PROFILE_CAPABILITY_DENIED",
                        {item.code for item in completion.blockers},
                    )
                    forged_start = check_transition(
                        workspace,
                        "agent_start",
                        work_id,
                        actor="PALARI-CLAUDE",
                        context={"packet": {"status": "ready"}},
                    )
                    self.assertIn(
                        "MAINTAINER_PROFILE_CAPABILITY_DENIED",
                        {item.code for item in forged_start.blockers},
                    )
                    member = _work_member(workspace, workspace.work_item(work_id))
                    self.assertEqual(
                        member["batch_policy"]["class"],
                        "maintainer-policy-denied",
                    )
                    self.assertFalse(member["batch_policy"]["batchable"])
                    self.assertEqual(
                        member["reversibility"]["class"],
                        "capability-denied",
                    )
                    self.assertTrue(
                        any(
                            action in message
                            for message in member["eligibility"]["errors"]
                        )
                    )
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_approval_inbox_templates_are_explicitly_non_executable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_governance_before = repo.root_governance_snapshot()
            repo.init_maintainer()

            inbox = repo.profile_json("queue", "--approval-inbox", "--json")

            self.assertNotIn("actions", inbox)
            templates = inbox["command_templates"]
            self.assertEqual(len(templates), 5)
            self.assertTrue(
                all(
                    template["executable"] is False
                    and template["arguments"]
                    and template["arguments"][0] != "palari"
                    for template in templates.values()
                )
            )
            repo.assert_exact_commands(inbox)
            self.assertEqual(repo.status(), "")
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_exact_selector_rejects_integration_and_linear_before_side_effects(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            before = repo.safety_snapshot()
            root_governance_before = repo.root_governance_snapshot()
            blocked_calls = {
                "record_plan": Mock(
                    side_effect=AssertionError("integration plan state was reached")
                ),
                "enqueue": Mock(
                    side_effect=AssertionError("integration queue state was reached")
                ),
                "connect": Mock(
                    side_effect=AssertionError("credential/provider access was reached")
                ),
                "issues": Mock(
                    side_effect=AssertionError("provider read was reached")
                ),
                "push": Mock(
                    side_effect=AssertionError("Linear plan state was reached")
                ),
                "send": Mock(
                    side_effect=AssertionError("provider write was reached")
                ),
            }
            commands = (
                (
                    "integration-plan-record",
                    [
                        "integration",
                        "plan",
                        "INTEGRATION-TEST",
                        "--work",
                        "WORK-TEST",
                        "--event",
                        "work_completed",
                        "--action",
                        "write",
                        "--record",
                        "--actor",
                        "HUMAN-FOUNDER",
                        "--json",
                    ],
                ),
                (
                    "integration-enqueue",
                    [
                        "integration",
                        "enqueue",
                        "PLAN-TEST",
                        "--by",
                        "HUMAN-FOUNDER",
                        "--json",
                    ],
                ),
                (
                    "linear-connect",
                    ["linear", "connect", "--as", "HUMAN-FOUNDER", "--json"],
                ),
                (
                    "linear-issues",
                    ["linear", "issues", "--team", "ENG", "--json"],
                ),
                (
                    "linear-push-record",
                    [
                        "linear",
                        "push",
                        "WORK-TEST",
                        "--as",
                        "PALARI-CLAUDE",
                        "--record",
                        "--json",
                    ],
                ),
                (
                    "linear-send",
                    [
                        "linear",
                        "send",
                        "OUTBOX-TEST",
                        "--by",
                        "HUMAN-FOUNDER",
                        "--confirm",
                        "--json",
                    ],
                ),
            )
            with (
                patch.object(
                    cli_dispatch.Workspace,
                    "load",
                    side_effect=AssertionError(
                        "maintainer external surface loaded workspace state"
                    ),
                ),
                patch.object(
                    integrations,
                    "record_integration_plan",
                    blocked_calls["record_plan"],
                ),
                patch.object(
                    integrations,
                    "enqueue_integration_plan",
                    blocked_calls["enqueue"],
                ),
                patch.object(
                    linear_adapter,
                    "linear_connect",
                    blocked_calls["connect"],
                ),
                patch.object(
                    linear_adapter,
                    "linear_issues",
                    blocked_calls["issues"],
                ),
                patch.object(
                    linear_adapter,
                    "linear_push",
                    blocked_calls["push"],
                ),
                patch.object(
                    linear_adapter,
                    "linear_send",
                    blocked_calls["send"],
                ),
            ):
                for label, command in commands:
                    with self.subTest(command=label):
                        args = build_parser().parse_args(
                            [
                                "--workspace",
                                str(repo.workspace_file),
                                *command,
                            ]
                        )
                        with self.assertRaisesRegex(
                            WorkspaceError,
                            "maintainer profile v1 permits reversible local source work only",
                        ):
                            run_command(args)

            for blocked in blocked_calls.values():
                blocked.assert_not_called()
            self.assertEqual(repo.safety_snapshot(), before)
            self.assertEqual(
                repo.root_governance_snapshot(),
                root_governance_before,
            )

    def test_ordinary_selectors_still_reach_integration_and_linear_dispatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "ordinary")
            integration_result = {"status": "ordinary-integration-reached"}
            linear_result = {"status": "ordinary-linear-reached"}
            integration_check = Mock(return_value=integration_result)
            linear_doctor = Mock(return_value=linear_result)

            with (
                patch.object(
                    integrations,
                    "check_integration",
                    integration_check,
                ),
                patch.object(
                    linear_adapter,
                    "linear_doctor",
                    linear_doctor,
                ),
            ):
                integration_args = build_parser().parse_args(
                    [
                        "--workspace",
                        str(repo.root / "workspace.json"),
                        "integration",
                        "check",
                        "INTEGRATION-TEST",
                        "--json",
                    ]
                )
                linear_args = build_parser().parse_args(
                    [
                        "--workspace",
                        str(repo.root / "workspace.json"),
                        "linear",
                        "doctor",
                        "--json",
                    ]
                )
                checked = run_command(integration_args)
                diagnosed = run_command(linear_args)

            self.assertEqual(checked.payload, integration_result)
            self.assertEqual(diagnosed.payload, linear_result)
            integration_check.assert_called_once()
            linear_doctor.assert_called_once_with(
                str(repo.root / "workspace.json")
            )

    def test_linear_errors_never_recommend_unbound_maintainer_escape(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            commands = (
                ("linear", "doctor", "--json"),
                ("linear", "doctor", "--unsupported", "--json"),
            )

            for command in commands:
                with self.subTest(command=command):
                    result = repo.run_cli(
                        "--workspace",
                        str(repo.workspace_file),
                        *command,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2, result)
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload["next_allowed_commands"], [])
                    self.assertIn(
                        "select an explicit ordinary workspace",
                        payload["next_action"],
                    )
                    self.assertNotIn(
                        "palari linear",
                        json.dumps(payload),
                    )


if __name__ == "__main__":
    unittest.main()
