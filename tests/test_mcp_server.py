from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.mcp_server import McpContext, handle_mcp_message, tool_definitions


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class McpServerTests(unittest.TestCase):
    def test_initialize_declares_read_only_tools_capability(self) -> None:
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

    def test_tools_list_exposes_expected_read_only_tools(self) -> None:
        names = {tool["name"] for tool in tool_definitions()}

        self.assertEqual(
            names,
            {
                "palari_queue",
                "palari_state",
                "palari_detail",
                "palari_agent_next",
                "palari_agent_brief",
                "palari_agent_check",
                "palari_docs_check",
            },
        )
        for tool in tool_definitions():
            self.assertEqual(tool["annotations"]["readOnlyHint"], True)
            self.assertEqual(tool["annotations"]["destructiveHint"], False)

    def test_tools_call_returns_structured_content_and_text_fallback(self) -> None:
        response = handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "palari_agent_brief",
                    "arguments": {
                        "work_id": "WORK-0003",
                        "palari_id": "PALARI-SOFIA",
                        "mode": "execute",
                    },
                },
            },
            self.context(),
        )

        self.assertIsNotNone(response)
        result = response["result"]
        structured = result["structuredContent"]
        text = json.loads(result["content"][0]["text"])
        self.assertEqual(result["isError"], False)
        self.assertEqual(structured["status"], "ready")
        self.assertEqual(structured["packet_id"], "PACKET-WORK-0003-PALARI-SOFIA-EXECUTE-V1")
        self.assertEqual(text["packet_id"], structured["packet_id"])

    def test_tool_execution_error_stays_inside_tool_result(self) -> None:
        response = handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "palari_detail",
                    "arguments": {"work_id": "WORK-MISSING"},
                },
            },
            self.context(),
        )

        self.assertIsNotNone(response)
        result = response["result"]
        self.assertEqual(result["isError"], True)
        self.assertEqual(result["structuredContent"]["ok"], False)
        self.assertIn("unknown work item", result["structuredContent"]["error"]["message"])

    def test_unknown_tool_returns_protocol_error(self) -> None:
        response = handle_mcp_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "palari_write_everything", "arguments": {}},
            },
            self.context(),
        )

        self.assertIsNotNone(response)
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("Unknown tool", response["error"]["message"])

    def test_stdio_server_speaks_newline_delimited_json_rpc(self) -> None:
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
                "params": {
                    "name": "palari_queue",
                    "arguments": {"include_closed": False},
                },
            },
        ]
        result = self.run_mcp(messages)
        responses = [json.loads(line) for line in result.stdout.splitlines()]

        self.assertEqual(result.stderr, "")
        self.assertEqual([response["id"] for response in responses], [1, 2, 3])
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "palari-company-os")
        self.assertIn("palari_queue", {tool["name"] for tool in responses[1]["result"]["tools"]})
        self.assertEqual(responses[2]["result"]["isError"], False)
        self.assertIn("queue", responses[2]["result"]["structuredContent"])

    def context(self) -> McpContext:
        return McpContext(workspace=str(WORKSPACE), repo=str(REPO_ROOT))

    def run_mcp(self, messages: list[dict[str, object]]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        payload = "\n".join(json.dumps(message, separators=(",", ":")) for message in messages)
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(WORKSPACE),
                "mcp",
                "serve",
                "--repo",
                str(REPO_ROOT),
            ],
            cwd=REPO_ROOT,
            env=env,
            input=f"{payload}\n",
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
