from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.store import load_store, write_store
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

    def test_generic_workspace_errors_use_stderr_and_nonzero_exit(self) -> None:
        result = self.run_cli("detail", "WORK-MISSING", "--json", check=False)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("unknown work item WORK-MISSING", result.stderr)

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
        environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(self.workspace_file),
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
