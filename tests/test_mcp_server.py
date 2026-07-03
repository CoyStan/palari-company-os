from __future__ import annotations

from contextlib import contextmanager
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Iterator

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

    def test_tools_list_exposes_expected_lifecycle_tools(self) -> None:
        names = {tool["name"] for tool in tool_definitions()}

        self.assertEqual(
            names,
            {
                "palari_queue",
                "palari_state",
                "palari_detail",
                "palari_agent_next",
                "palari_agent_brief",
                "palari_agent_start",
                "palari_agent_check",
                "palari_agent_finish",
                "palari_agent_handoff",
                "palari_agent_loop",
                "palari_agent_doctor",
                "palari_agent_release",
                "palari_docs_check",
            },
        )
        mutating_local_tools = {"palari_agent_start", "palari_agent_release"}
        for tool in tool_definitions():
            self.assertEqual(
                tool["annotations"]["readOnlyHint"],
                tool["name"] not in mutating_local_tools,
            )
            self.assertEqual(tool["annotations"]["destructiveHint"], False)
            self.assertEqual(
                tool["annotations"]["idempotentHint"],
                tool["name"] not in mutating_local_tools,
            )

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

    def test_agent_start_and_release_tools_manage_local_runtime_files(self) -> None:
        with self.temporary_workspace() as workspace_file:
            start_response = handle_mcp_message(
                {
                    "jsonrpc": "2.0",
                    "id": 10,
                    "method": "tools/call",
                    "params": {
                        "name": "palari_agent_start",
                        "arguments": {
                            "work_id": "WORK-0003",
                            "palari_id": "PALARI-SOFIA",
                            "mode": "execute",
                            "lease_minutes": 5,
                        },
                    },
                },
                self.context(workspace_file),
            )

            self.assertIsNotNone(start_response)
            start_result = start_response["result"]
            start_payload = start_result["structuredContent"]
            self.assertEqual(start_result["isError"], False)
            self.assertEqual(start_payload["start"]["status"], "claimed")
            packet_path = workspace_file.parent / start_payload["start"]["packet_path"]
            claim_path = workspace_file.parent / start_payload["start"]["claim_path"]
            self.assertTrue(packet_path.exists())
            self.assertTrue(claim_path.exists())

            release_response = handle_mcp_message(
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {
                        "name": "palari_agent_release",
                        "arguments": {
                            "work_id": "WORK-0003",
                            "palari_id": "PALARI-SOFIA",
                        },
                    },
                },
                self.context(workspace_file),
            )

            self.assertIsNotNone(release_response)
            release_result = release_response["result"]
            release_payload = release_result["structuredContent"]
            self.assertEqual(release_result["isError"], False)
            self.assertEqual(release_payload["status"], "released")
            self.assertFalse(claim_path.exists())
            self.assertTrue(packet_path.exists())

    def test_agent_lifecycle_read_only_tools_return_structured_packets(self) -> None:
        expected_versions = {
            "palari_agent_finish": "palari.agent_finish.v1",
            "palari_agent_handoff": "palari.agent_handoff.v1",
            "palari_agent_loop": "palari.agent_loop.v1",
            "palari_agent_doctor": "palari.agent_doctor.v1",
        }

        for tool_name, schema_version in expected_versions.items():
            with self.subTest(tool_name=tool_name):
                response = handle_mcp_message(
                    {
                        "jsonrpc": "2.0",
                        "id": 20,
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": {
                                "work_id": "WORK-0007",
                                "palari_id": "PALARI-SOFIA",
                                "mode": "execute",
                            },
                        },
                    },
                    self.context(),
                )

                self.assertIsNotNone(response)
                result = response["result"]
                self.assertEqual(result["isError"], False)
                self.assertEqual(result["structuredContent"]["schema_version"], schema_version)
                self.assertEqual(result["structuredContent"]["would_mutate"], False)

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

    def context(self, workspace: Path | None = None) -> McpContext:
        return McpContext(workspace=str(workspace or WORKSPACE), repo=str(REPO_ROOT))

    @contextmanager
    def temporary_workspace(self) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            workspace_file.write_text(
                (WORKSPACE / "workspace.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            yield workspace_file

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
