from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.authoring import create_record
from palari_company_os.mcp_server import McpContext, handle_mcp_message, tool_definitions
from tests.workspace_fixture import write_current_agent_workspace


WORK_ID = "WORK-MCP"
PALARI_ID = "PALARI-STEWARD"


class McpServerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.workspace_file = self.root / "workspace.json"
        write_current_agent_workspace(self.workspace_file)
        create_record(
            str(self.root),
            "work",
            {
                "id": WORK_ID,
                "title": "Inspect bounded MCP translation",
                "goal": "GOAL-REPO-0001",
                "palari": PALARI_ID,
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R3",
                "intensity": "standard",
                "status": "active",
                "scope": "Read and write one declared file.",
                "allowed_resources": ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": ["README.md"],
                "forbidden_actions": ["deploy"],
                "acceptance_target": "Exact proof is reviewable.",
                "required_approval_count": 1,
                "required_approval_capability": "product",
            },
            command="MCP contract fixture",
        )

    def test_initialize_and_tool_catalog_expose_bounded_capabilities(self) -> None:
        response = handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            },
            self.context(),
        )

        self.assertIsNotNone(response)
        result = response["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertEqual(result["capabilities"], {"tools": {"listChanged": False}})
        self.assertEqual(result["serverInfo"]["name"], "palari-company-os")

        tools = {tool["name"]: tool for tool in tool_definitions()}
        self.assertEqual(
            set(tools),
            {
                "palari_queue",
                "palari_state",
                "palari_detail",
                "palari_agent_next",
                "palari_agent_brief",
                "palari_agent_start",
                "palari_agent_check",
                "palari_agent_advance",
                "palari_agent_finish",
                "palari_agent_handoff",
                "palari_agent_loop",
                "palari_agent_doctor",
                "palari_agent_release",
                "palari_docs_check",
            },
        )
        for name, tool in tools.items():
            self.assertNotIn("human", name)
            self.assertNotIn("accept", name)
            self.assertFalse(tool["annotations"]["destructiveHint"])
            self.assertEqual(
                tool["annotations"]["readOnlyHint"],
                name not in {"palari_agent_start", "palari_agent_advance", "palari_agent_release"},
            )

    def test_agent_brief_is_a_structured_translation_with_text_fallback(self) -> None:
        response = self.call(
            "palari_agent_brief",
            {
                "work_id": WORK_ID,
                "palari_id": PALARI_ID,
                "mode": "execute",
                "session_contract": True,
            },
        )

        result = response["result"]
        structured = result["structuredContent"]
        self.assertFalse(result["isError"])
        self.assertEqual(structured["schema_version"], "palari.agent_session_contract.v1")
        self.assertEqual(json.loads(result["content"][0]["text"]), structured)
        self.assertIn("contract_digest", structured)

    def test_start_advance_dry_run_and_release_manage_only_local_runtime_files(self) -> None:
        start = self.call(
            "palari_agent_start",
            {
                "work_id": WORK_ID,
                "palari_id": PALARI_ID,
                "mode": "execute",
                "lease_minutes": 5,
            },
        )["result"]
        self.assertFalse(start["isError"])
        start_payload = start["structuredContent"]["start"]
        self.assertEqual(start_payload["status"], "claimed")
        packet_path = self.root / start_payload["packet_path"]
        claim_path = self.root / start_payload["claim_path"]
        self.assertTrue(packet_path.is_file())
        self.assertTrue(claim_path.is_file())

        advance = self.call(
            "palari_agent_advance",
            {"work_id": WORK_ID, "palari_id": PALARI_ID, "dry_run": True},
        )["result"]
        self.assertFalse(advance["isError"])
        self.assertTrue(advance["structuredContent"]["dry_run"])

        release = self.call(
            "palari_agent_release",
            {"work_id": WORK_ID, "palari_id": PALARI_ID},
        )["result"]
        self.assertFalse(release["isError"])
        self.assertEqual(release["structuredContent"]["status"], "released")
        self.assertFalse(claim_path.exists())
        self.assertTrue(packet_path.is_file())

    def test_tool_and_execution_errors_stay_inside_protocol_boundaries(self) -> None:
        missing = self.call("palari_detail", {"work_id": "WORK-MISSING"})["result"]
        self.assertTrue(missing["isError"])
        self.assertFalse(missing["structuredContent"]["ok"])
        self.assertIn("unknown work item", missing["structuredContent"]["error"]["message"])

        unknown = handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "palari_write_everything", "arguments": {}},
            },
            self.context(),
        )
        self.assertIsNotNone(unknown)
        self.assertEqual(unknown["error"]["code"], -32602)

    def test_stdio_transport_speaks_newline_delimited_json_rpc(self) -> None:
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "palari_queue", "arguments": {"include_closed": False}},
            },
        ]
        payload = "\n".join(json.dumps(message, separators=(",", ":")) for message in messages)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(self.workspace_file),
                "mcp",
                "serve",
                "--repo",
                str(REPO_ROOT),
            ],
            cwd=self.root,
            env=env,
            input=f"{payload}\n",
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        responses = [json.loads(line) for line in result.stdout.splitlines()]

        self.assertEqual(result.stderr, "")
        self.assertEqual([response["id"] for response in responses], [1, 2, 3])
        self.assertIn("palari_queue", {tool["name"] for tool in responses[1]["result"]["tools"]})
        self.assertFalse(responses[2]["result"]["isError"])

    def call(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        response = handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            self.context(),
        )
        self.assertIsNotNone(response)
        return response

    def context(self) -> McpContext:
        return McpContext(workspace=str(self.workspace_file), repo=str(REPO_ROOT))


if __name__ == "__main__":
    unittest.main()
