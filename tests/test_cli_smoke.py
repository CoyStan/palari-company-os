from __future__ import annotations

import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cli_output import print_review_guide
from palari_company_os.store import load_store, write_store
from tests.test_approval_packs import make_ready_workspace
from tests.workspace_fixture import write_current_agent_workspace


WORK_ID = "WORK-CLI"
PALARI_ID = "PALARI-STEWARD"


class CliSmokeTests(unittest.TestCase):
    """Public CLI wiring over one small, current, isolated workspace."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.workspace_file = self.root / "workspace.json"
        write_current_agent_workspace(self.workspace_file)
        (self.root / "README.md").write_text("current fixture\n", encoding="utf-8")
        self._seed_current_work()

    def test_operator_read_path_emits_current_json_shapes(self) -> None:
        validate = self.run_json("validate", "--json")
        state = self.run_json("state", "--json")
        queue = self.run_json("queue", "--json")
        detail = self.run_json("detail", WORK_ID, "--json")

        self.assertTrue(validate["valid"])
        self.assertEqual(validate["workspace"], "Current Agent Test Workspace")
        self.assertEqual(validate["counts"]["work_items"], 1)
        self.assertEqual(state["counts"]["work_items"], 1)
        self.assertEqual(state["queue"][0]["id"], WORK_ID)
        self.assertEqual(queue["queue"][0]["id"], WORK_ID)
        self.assertEqual(detail["work_item"]["id"], WORK_ID)
        self.assertEqual(detail["next_step_type"], "start-work")

    def test_plain_text_uses_simple_vocabulary_without_changing_json_contract(self) -> None:
        queue_json = self.run_json("queue", "--json")
        detail_json = self.run_json("detail", WORK_ID, "--json")
        queue_text = self.run_cli("queue").stdout
        detail_text = self.run_cli("detail", WORK_ID).stdout
        help_text = self.run_cli("--help").stdout

        self.assertIn("Palari Tasks:", queue_text)
        self.assertIn("status: Ready", queue_text)
        self.assertIn("project:", queue_text)
        self.assertIn("agent:", queue_text)
        self.assertNotIn("attention: ready-for-ai-work", queue_text)
        self.assertIn(f"Task {WORK_ID}:", detail_text)
        self.assertIn("Task limits", detail_text)
        self.assertIn("bounded task briefs", help_text)
        self.assertNotIn("work item", help_text.lower())

        self.assertEqual(queue_json["queue"][0]["attention"], "ready-for-ai-work")
        self.assertEqual(detail_json["attention"], "ready-for-ai-work")
        self.assertIn("work_item", detail_json)

    def test_scope_command_translates_allow_and_deny_decisions(self) -> None:
        allowed = self.run_json(
            "scope", WORK_ID, "--changed", "README.md", "--json"
        )
        denied = self.run_json(
            "scope",
            WORK_ID,
            "--changed",
            "outside.txt",
            "--action",
            "deploy",
            "--json",
        )

        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["violations"], [])
        self.assertFalse(denied["allowed"])
        self.assertIn("Path is outside allowed resources: outside.txt", denied["violations"])
        self.assertIn("Action is explicitly forbidden: deploy", denied["violations"])

    def test_work_add_translates_exact_current_boundary_contract(self) -> None:
        payload = self.run_json(
            "work",
            "add",
            "Create the CLI boundary artifact",
            "--id",
            "WORK-CLI-DEPENDENT",
            "--as",
            PALARI_ID,
            "--goal",
            "GOAL-REPO-0001",
            "--workbench",
            "WORKBENCH-REPO-FOUNDATION",
            "--create",
            "docs/cli-boundary.md",
            "--depends-on",
            WORK_ID,
            "--parallel-policy",
            "coordinate",
            "--json",
        )

        work = payload["work_item"]
        self.assertEqual(payload["schema_version"], "palari.work_add.v1")
        self.assertEqual(
            payload["path_intents"],
            [{"path": "docs/cli-boundary.md", "intent": "create"}],
        )
        self.assertEqual(work["dependency_ids"], [WORK_ID])
        self.assertEqual(work["parallel_policy"], "coordinate")
        self.assertEqual(work["allowed_sources"], ["SOURCE-REPO-FOUNDATION"])
        self.assertEqual(payload["workbench_outputs_added"], ["docs/cli-boundary.md"])

    def test_history_command_verifies_only_the_current_v2_fixture(self) -> None:
        payload = self.run_json("history", "--json")

        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["journal_schema_version"], "palari.governance-journal.v2"
        )
        self.assertGreaterEqual(payload["committed_transactions"], 2)

    def test_agent_parse_errors_remain_structured_json(self) -> None:
        result = self.run_cli(
            "agent", "brief", WORK_ID, "--as", "--json", check=False
        )
        payload = self.json_object(result)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "ARGUMENT_PARSE_ERROR")
        self.assertIn("--as", payload["error"]["message"])
        self.assertTrue(payload["next_allowed_commands"])

    def test_agent_errors_keep_an_exact_custom_workspace_selector(self) -> None:
        custom_workspace = self.root / "governance state.json"
        parse_result = self.run_cli_for(
            custom_workspace,
            "agent",
            "brief",
            WORK_ID,
            "--as",
            "--json",
            check=False,
        )
        runtime_result = self.run_cli_for(
            custom_workspace,
            "agent",
            "start",
            WORK_ID,
            "--as",
            PALARI_ID,
            "--json",
            check=False,
        )

        for result in (parse_result, runtime_result):
            payload = self.json_object(result)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, "")
            self.assertTrue(payload["next_allowed_commands"])
            for command in payload["next_allowed_commands"]:
                tokens = shlex.split(command)
                self.assertEqual(tokens[:3], ["palari", "--workspace", str(custom_workspace)])

    def test_agent_parse_error_with_malformed_workspace_has_no_recovery_command(
        self,
    ) -> None:
        environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                "--json",
                "agent",
            ],
            cwd=REPO_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = self.json_object(result)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["next_allowed_commands"], [])

    def test_review_guide_text_renders_concrete_commands_and_marks_template(
        self,
    ) -> None:
        agent_command = (
            "palari --workspace /tmp/example review record REVIEW-AGENT "
            "--work-item-id WORK-CLI --reviewed-head head-1 "
            "--reviewer PALARI-REVIEWER --verdict accept-ready --json"
        )
        human_command = (
            "palari --workspace /tmp/example review record REVIEW-HUMAN "
            "--work-item-id WORK-CLI --reviewed-head head-1 "
            "--reviewer HUMAN-REVIEWER --verdict blocked --json"
        )
        payload = {
            "schema_version": "palari.review_guide.v2",
            "guide_id": "REVIEW-GUIDE-WORK-CLI-V2",
            "status": "review-needed",
            "would_mutate": False,
            "work_item": {
                "id": WORK_ID,
                "title": "Review the current CLI boundary",
                "risk": "R2",
            },
            "attention": "needs-review",
            "why": "Current exact checks are ready for independent review.",
            "evidence": {
                "present": True,
                "head_sha": "head-1",
                "status": "passed",
            },
            "attempt": {
                "present": True,
                "changed_files": ["README.md"],
            },
            "receipt": {
                "present": True,
                "not_done": [],
            },
            "review_focus": ["Inspect the exact changed file."],
            "reviewer_candidates": [
                {
                    "id": "PALARI-REVIEWER",
                    "name": "Independent Reviewer",
                    "identity_type": "palari",
                    "reason": "Independent and source-authorized.",
                    "agent_may_execute": True,
                    "review_packet_command": (
                        "palari agent start WORK-CLI --as PALARI-REVIEWER "
                        "--mode review --json"
                    ),
                    "review_record_commands": [
                        {
                            "reviewer": "PALARI-REVIEWER",
                            "identity_type": "palari",
                            "agent_may_execute": True,
                            "verdict": "accept-ready",
                            "review_id": "REVIEW-AGENT",
                            "executable": True,
                            "command": agent_command,
                        }
                    ],
                },
                {
                    "id": "HUMAN-REVIEWER",
                    "name": "Human Reviewer",
                    "identity_type": "human",
                    "reason": "Independent human reviewer.",
                    "agent_may_execute": False,
                    "review_record_commands": [
                        {
                            "reviewer": "HUMAN-REVIEWER",
                            "identity_type": "human",
                            "agent_may_execute": False,
                            "verdict": "blocked",
                            "review_id": "REVIEW-HUMAN",
                            "executable": True,
                            "command": human_command,
                        }
                    ],
                },
            ],
            "suggested_verdicts": ["accept-ready", "blocked"],
            "review_record_command_template": (
                "palari review record REVIEW-ID --work-item-id WORK-CLI "
                "--reviewed-head head-1 --reviewer REVIEWER-ID "
                "--verdict VERDICT --json"
            ),
            "review_record_command_template_executable": False,
            "next_commands": [],
        }
        output = io.StringIO()

        with redirect_stdout(output):
            print_review_guide(payload, False)

        text = output.getvalue()
        self.assertIn("packet-bound executable verdict commands:", text)
        self.assertIn(f"accept-ready: {agent_command}", text)
        self.assertIn("human-only executable verdict commands:", text)
        self.assertIn(f"blocked: {human_command}", text)
        self.assertIn("Non-executable reference template:", text)
        self.assertIn("REVIEW-ID", text)
        self.assertNotIn("ready-to-edit", text)

    def test_approval_parse_and_runtime_errors_are_structured_json(self) -> None:
        parse_result = self.run_cli(
            "approve", WORK_ID, "--as", "--json", check=False
        )
        parse_payload = self.json_object(parse_result)

        self.assertEqual(parse_result.returncode, 2)
        self.assertEqual(parse_result.stderr, "")
        self.assertEqual(
            parse_payload["schema_version"],
            "palari.simple-approval-error.v1",
        )
        self.assertEqual(
            parse_payload["error"]["code"],
            "ARGUMENT_PARSE_ERROR",
        )
        self.assertEqual(parse_payload["error"]["work_item"], WORK_ID)
        self.assertTrue(parse_payload["next_action"])

        runtime_result = self.run_cli(
            "approve",
            WORK_ID,
            "--as",
            "HUMAN-OWNER",
            "--json",
            check=False,
        )
        runtime_payload = self.json_object(runtime_result)

        self.assertEqual(runtime_result.returncode, 2)
        self.assertEqual(runtime_result.stderr, "")
        self.assertEqual(
            runtime_payload["schema_version"],
            "palari.simple-approval-error.v1",
        )
        self.assertEqual(
            runtime_payload["error"]["code"],
            "APPROVAL_HUMAN_NOT_FOUND",
        )
        self.assertEqual(runtime_payload["error"]["human"], "HUMAN-OWNER")
        next_commands = runtime_payload["next_allowed_commands"]
        self.assertEqual(len(next_commands), 2)
        self.assertTrue(
            all(
                command.startswith(
                    f"palari --workspace {self.workspace_file.parent} "
                )
                for command in next_commands
            )
        )
        self.assertIn(f"detail {WORK_ID} --json", next_commands[0])
        self.assertIn(
            f"queue --approval-inbox --select {WORK_ID} --json",
            next_commands[1],
        )

    def test_simple_approval_cli_completes_once_and_retries_without_opaque_args(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = make_ready_workspace(
                Path(directory) / "approval",
                count=1,
            )

            first_result = self.run_cli_for(
                workspace_file,
                "approve",
                "WORK-001",
                "--as",
                "HUMAN-PRODUCT",
                "--reason",
                "Reviewed the exact local result.",
                "--json",
            )
            first = self.json_object(first_result)
            replay = self.json_object(
                self.run_cli_for(
                    workspace_file,
                    "approve",
                    "WORK-001",
                    "--as",
                    "HUMAN-PRODUCT",
                    "--json",
                )
            )
            plain = self.run_cli_for(
                workspace_file,
                "approve",
                "WORK-001",
                "--as",
                "HUMAN-PRODUCT",
            ).stdout
            final = load_store(workspace_file).data

        self.assertEqual(first["schema_version"], "palari.simple-approval-result.v1")
        self.assertTrue(first["approved"])
        self.assertTrue(first["completed"])
        self.assertFalse(first["idempotent"])
        self.assertFalse(first["performed_external_effects"])
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["status"], "already-approved")
        self.assertEqual(len(final["human_decisions"]), 1)
        self.assertEqual(len(final["acceptance_records"]), 1)
        self.assertEqual(final["work_items"][0]["status"], "completed")
        self.assertNotIn("sha256:", plain)
        self.assertIn("no approval authority was duplicated", plain)

    def test_generic_workspace_errors_use_stderr_and_nonzero_exit(self) -> None:
        result = self.run_cli("detail", "WORK-MISSING", "--json", check=False)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("unknown task WORK-MISSING", result.stderr)

    def _seed_current_work(self) -> None:
        store = load_store(self.workspace_file)
        store.data["work_items"] = [
            {
                "id": WORK_ID,
                "title": "Exercise the current CLI boundary",
                "goal": "GOAL-REPO-0001",
                "palari": PALARI_ID,
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R1",
                "intensity": "light",
                "required_approval_count": 0,
                "scope": "Modify only the declared local artifact.",
                "acceptance_target": "The bounded artifact is verified.",
                "status": "active",
                "allowed_resources": ["README.md", "AGENTS.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": ["README.md"],
                "path_intents": [{"path": "README.md", "intent": "modify"}],
                "conflict_targets": ["README.md"],
                "parallel_policy": "independent",
                "forbidden_actions": ["deploy"],
                "verification_expectations": ["focused CLI smoke passes"],
            }
        ]
        for palari in store.data["palaris"]:
            if palari["id"] == PALARI_ID:
                palari["active_work"] = [WORK_ID]
        write_store(store)

    def run_json(self, *args: str) -> dict[str, Any]:
        return self.json_object(self.run_cli(*args))

    def json_object(
        self, result: subprocess.CompletedProcess[str]
    ) -> dict[str, Any]:
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            self.fail(f"CLI output was not valid JSON: {error}\n{result.stdout}")
        if not isinstance(payload, dict):
            self.fail(f"CLI output was not a JSON object: {payload!r}")
        return payload

    def run_cli(
        self, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return self.run_cli_for(self.workspace_file, *args, check=check)

    def run_cli_for(
        self,
        workspace_file: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(workspace_file),
                *args,
            ],
            cwd=REPO_ROOT,
            env=environment,
            check=check,
            capture_output=True,
            text=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
