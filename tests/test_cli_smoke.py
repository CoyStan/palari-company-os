from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ACME = REPO_ROOT / "examples" / "acme-company-os"
DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"
SPLIT_WORKSPACE = REPO_ROOT / "tests" / "fixtures" / "workspaces" / "split-workspace"


class CliSmokeTests(unittest.TestCase):
    def test_core_workspace_json_commands_return_structured_payloads(self) -> None:
        validate = self.run_json("validate", "--json")
        dogfood_validate = self.run_json(
            "--workspace", str(DOGFOOD), "validate", "--json"
        )
        split_validate = self.run_json(
            "--workspace", str(SPLIT_WORKSPACE), "validate", "--json"
        )
        state = self.run_json("state", "--json")
        queue = self.run_json("queue", "--json")
        detail = self.run_json("detail", "WORK-0001", "--json")
        split_detail = self.run_json(
            "--workspace", str(SPLIT_WORKSPACE), "detail", "WORK-SPLIT", "--json"
        )

        self.assertTrue(validate["valid"])
        self.assertEqual(validate["workspace"], "Acme Company OS Example")
        self.assertTrue(dogfood_validate["valid"])
        self.assertTrue(split_validate["valid"])
        self.assertIn("attention", state)
        self.assertIn("counts", state)
        self.assertGreaterEqual(len(queue["queue"]), 1)
        self.assertEqual(detail["work_item"]["id"], "WORK-0001")
        self.assertEqual(split_detail["work_item"]["id"], "WORK-SPLIT")

    def test_agent_lifecycle_json_commands_return_expected_states(self) -> None:
        next_payload = self.run_json("agent", "next", "--as", "PALARI-SOFIA", "--json")
        brief = self.run_json(
            "agent", "brief", "WORK-0003", "--as", "PALARI-SOFIA", "--mode", "execute", "--json"
        )
        blocked_start = self.run_json(
            "agent", "start", "WORK-0007", "--as", "PALARI-SOFIA", "--mode", "execute", "--json"
        )
        check_missing_proof = self.run_json(
            "agent", "check", "WORK-0003", "--as", "PALARI-SOFIA", "--json"
        )
        check_blocked = self.run_json(
            "agent", "check", "WORK-0007", "--as", "PALARI-SOFIA", "--json"
        )
        finish_missing_proof = self.run_json(
            "agent", "finish", "WORK-0003", "--as", "PALARI-SOFIA", "--json"
        )
        finish_handoff = self.run_json(
            "agent", "finish", "WORK-0007", "--as", "PALARI-SOFIA", "--json"
        )

        self.assertEqual(next_payload["schema_version"], "palari.agent_next.v1")
        self.assertEqual(next_payload["candidates"][0]["work_item_id"], "WORK-0003")
        self.assertEqual(brief["status"], "ready")
        self.assertEqual(brief["packet_id"], "PACKET-WORK-0003-PALARI-SOFIA-EXECUTE-V1")
        self.assertEqual(blocked_start["status"], "blocked")
        self.assertIn("DEPENDENCY_NOT_TERMINAL", json.dumps(blocked_start))
        self.assertEqual(check_missing_proof["schema_version"], "palari.agent_check.v1")
        self.assertFalse(check_missing_proof["ok"])
        self.assertIn("RECEIPT_PRESENT", json.dumps(check_missing_proof))
        self.assertIn("DEPENDENCY_NOT_TERMINAL", json.dumps(check_blocked))
        self.assertEqual(finish_missing_proof["schema_version"], "palari.agent_finish.v1")
        self.assertEqual(finish_missing_proof["status"], "missing-proof")
        self.assertEqual(finish_handoff["status"], "handoff-ready")

    def test_agent_start_check_and_release_use_temp_workspace(self) -> None:
        with self.temp_workspace() as workspace_file:
            start = self.run_json(
                "--workspace",
                str(workspace_file),
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
                "--json",
            )
            check = self.run_json(
                "--workspace",
                str(workspace_file),
                "agent",
                "check",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
                "--changed",
                "docs/product/company-os.md",
                "--json",
            )
            release = self.run_json(
                "--workspace",
                str(workspace_file),
                "agent",
                "release",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--json",
            )

            self.assertEqual(start["start"]["status"], "claimed")
            self.assertEqual(start["start"]["packet_path"], ".palari/packets/PACKET-WORK-0003-PALARI-SOFIA-EXECUTE-V1.json")
            self.assertIn("FILE_CHANGES_WITHIN_WRITE_BOUNDARY", json.dumps(check))
            self.assertEqual(release["status"], "released")

    def test_playbook_and_integration_json_smokes(self) -> None:
        sources = self.run_json("playbooks", "sources", "--json")
        recommendations = self.run_json("playbooks", "recommend", "WORK-0003", "--json")
        integrations = self.run_json("integrations", "--json")
        integration_check = self.run_json("integration", "check", "INT-SLACK-OPS", "--json")
        plan = self.run_json(
            "integration",
            "plan",
            "INT-SLACK-OPS",
            "--work",
            "WORK-0001",
            "--event",
            "approval_requested",
            "--action",
            "notify",
            "--json",
        )

        self.assertGreaterEqual(len(sources["sources"]), 1)
        self.assertIn("superpowers:verification-before-completion", json.dumps(recommendations))
        self.assertEqual(integrations["integrations"][0]["id"], "INT-SLACK-OPS")
        self.assertEqual(integration_check["integration"]["provider"], "slack")
        self.assertFalse(plan["would_call_provider"])

    def test_integration_plan_approval_outbox_and_cancel_flow(self) -> None:
        with self.temp_workspace() as workspace_file:
            recorded = self.run_json(
                "--workspace",
                str(workspace_file),
                "integration",
                "plan",
                "INT-SLACK-OPS",
                "--work",
                "WORK-0001",
                "--event",
                "approval_requested",
                "--action",
                "notify",
                "--record",
                "--id",
                "PLAN-SMOKE",
                "--json",
            )
            approved = self.run_json(
                "--workspace",
                str(workspace_file),
                "integration",
                "approve",
                "PLAN-SMOKE",
                "--by",
                "HUMAN-FOUNDER",
                "--reason",
                "verification smoke",
                "--json",
            )
            enqueued = self.run_json(
                "--workspace",
                str(workspace_file),
                "integration",
                "enqueue",
                "PLAN-SMOKE",
                "--by",
                "HUMAN-FOUNDER",
                "--json",
            )
            outbox_id = enqueued["integration_outbox_item"]["id"]
            preflight = self.run_json(
                "--workspace",
                str(workspace_file),
                "integration",
                "outbox-check",
                outbox_id,
                "--json",
            )
            canceled = self.run_json(
                "--workspace",
                str(workspace_file),
                "integration",
                "outbox-cancel",
                outbox_id,
                "--by",
                "HUMAN-FOUNDER",
                "--reason",
                "verification smoke cancel",
                "--json",
            )
            queue = self.run_json("--workspace", str(workspace_file), "queue", "--json")
            detail = self.run_json(
                "--workspace", str(workspace_file), "detail", "WORK-0001", "--json"
            )
            history = self.run_json("--workspace", str(workspace_file), "history", "--json")

        self.assertTrue(recorded["recorded"])
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(enqueued["integration_outbox_item"]["status"], "queued")
        self.assertEqual(preflight["status"], "queued-preflight-ready")
        self.assertFalse(preflight["execution_enabled"])
        self.assertFalse(preflight["would_call_provider"])
        self.assertEqual(canceled["integration_outbox_item"]["status"], "canceled")
        self.assertIn("outbox-canceled", json.dumps(queue))
        self.assertIn("PLAN-SMOKE", json.dumps(detail))
        self.assertIn("PLAN-SMOKE", json.dumps(history))
        self.assertIn("canceled", json.dumps(history))

    def test_scope_history_and_generated_html_smokes(self) -> None:
        allowed = self.run_json(
            "scope", "WORK-0001", "--changed", "examples/acme-company-os/workspace.json", "--json"
        )
        blocked = self.run_json(
            "scope", "WORK-0001", "--changed", "secrets.env", "--action", "deploy", "--json"
        )
        history = self.run_json("history", "--json")
        dogfood_history = self.run_json("--workspace", str(DOGFOOD), "history", "--json")
        maintainer = self.run_json("maintainer", "status", "--json")

        self.assertTrue(allowed["allowed"])
        self.assertFalse(blocked["allowed"])
        self.assertIn("events", history)
        self.assertIn("events", dogfood_history)
        self.assertIn("repo", maintainer)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            dashboard = self.run_json(
                "--workspace",
                str(ACME),
                "dashboard",
                "--out",
                str(output / "dashboard-acme"),
                "--json",
            )
            dogfood_dashboard = self.run_json(
                "--workspace",
                str(DOGFOOD),
                "dashboard",
                "--out",
                str(output / "dashboard-dogfood"),
                "--json",
            )
            prototype = self.run_json(
                "desktop-prototype", "--out", str(output / "desktop-prototype"), "--json"
            )
            acme_html = Path(dashboard["index_path"]).read_text(encoding="utf-8")
            dogfood_html = Path(dogfood_dashboard["index_path"]).read_text(encoding="utf-8")
            prototype_html = Path(prototype["index_path"]).read_text(encoding="utf-8")

        for marker in (
            'data-tab-panel="queue"',
            'data-tab-panel="work"',
            'data-tab-panel="trust"',
            'data-tab-panel="history"',
            'data-tab-panel="authority"',
            "palari agent finish WORK-0007 --as PALARI-SOFIA",
            "RECEIPT-0001",
        ):
            self.assertIn(marker, acme_html)
        self.assertIn("RECEIPT-REPO-0001", dogfood_html)
        self.assertIn("Palari Desktop Shell Prototype", prototype_html)
        self.assertIn("External writes", prototype_html)
        self.assertIn('data-mobile-target="chat"', prototype_html)

    def run_json(self, *args: str) -> dict[str, object]:
        result = self.run_cli(*args)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            self.fail(f"CLI output was not valid JSON for {args}: {error}\n{result.stdout}")
        if not isinstance(payload, dict):
            self.fail(f"CLI output was not a JSON object for {args}: {payload!r}")
        return payload

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def temp_workspace(self):
        return _TempWorkspace()


class _TempWorkspace:
    def __enter__(self) -> Path:
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name) / "workspace.json"
        self.path.write_text((ACME / "workspace.json").read_text(encoding="utf-8"), encoding="utf-8")
        return self.path

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._directory.cleanup()


if __name__ == "__main__":
    unittest.main()
