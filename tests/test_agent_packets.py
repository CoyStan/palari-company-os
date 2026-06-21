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

from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.workspace import Workspace


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class AgentPacketTests(unittest.TestCase):
    def test_ready_execute_packet_is_compact_and_actionable(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["schema_version"], "palari.agent_packet.v1")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "execute")
        self.assertEqual(packet["agent"]["id"], "PALARI-SOFIA")
        self.assertEqual(packet["work_item"]["id"], "WORK-0003")
        self.assertEqual(packet["workbench"]["id"], "WORKBENCH-BETA")
        self.assertEqual(packet["allowed_paths"]["read"], ["docs/product/company-os.md"])
        self.assertEqual(packet["allowed_paths"]["write"], ["docs/product/company-os.md"])
        self.assertEqual(packet["completion_contract"]["requires_receipt"], True)
        self.assertEqual(packet["completion_contract"]["requires_evidence"], True)
        self.assertIn("palari scope WORK-0003 --json", packet["next_allowed_commands"])
        self.assertIn("Stop if you need to read or write outside allowed_paths.", packet["stop_conditions"])
        self.assertEqual(packet["blockers"], [])
        self.assertTrue(packet["context_hash"].startswith("sha256:"))

    def test_blocked_packet_names_dependency_and_receipt_review_blockers(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0007", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["status"], "blocked")
        codes = {blocker["code"] for blocker in packet["blockers"]}
        self.assertIn("DEPENDENCY_NOT_TERMINAL", codes)
        self.assertIn("RECEIPT_READY_REVIEW", codes)
        self.assertEqual(packet["dependencies"][0]["id"], "WORK-0003")
        self.assertEqual(packet["allowed_sources"][0]["id"], "SOURCE-0001")
        self.assertEqual(packet["completion_contract"]["requires_evidence"], False)
        self.assertEqual(
            packet["next_allowed_commands"],
            [
                "palari detail WORK-0007 --json",
                "palari queue --json",
                "palari validate --json",
            ],
        )

    def test_invalid_work_or_palari_returns_blocked_packet(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        missing_work = build_agent_brief(workspace, "WORK-MISSING", "PALARI-SOFIA", "execute")
        missing_palari = build_agent_brief(workspace, "WORK-0003", "PALARI-MISSING", "execute")

        self.assertEqual(missing_work["status"], "blocked")
        self.assertEqual(missing_work["blockers"][0]["code"], "MISSING_WORK_ITEM")
        self.assertEqual(missing_palari["status"], "blocked")
        self.assertEqual(missing_palari["blockers"][0]["code"], "MISSING_PALARI")

    def test_wrong_palari_and_external_write_are_blocked(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        wrong_palari = build_agent_brief(workspace, "WORK-0003", "PALARI-ALFRED", "execute")

        self.assertEqual(wrong_palari["status"], "blocked")
        self.assertIn(
            "PALARI_NOT_ASSIGNED",
            {blocker["code"] for blocker in wrong_palari["blockers"]},
        )

        external_write = self.modified_workspace(
            lambda data: data["work_items"][2].update({"allowed_actions": ["external_write"]})
        )
        packet = build_agent_brief(external_write, "WORK-0003", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "EXTERNAL_WRITE_REQUIRES_APPROVAL",
            {blocker["code"] for blocker in packet["blockers"]},
        )

    def test_packet_does_not_dump_unrelated_workspace_records(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")
        encoded = json.dumps(packet, sort_keys=True)

        self.assertNotIn("WORK-0001", encoded)
        self.assertNotIn("Prepare beta launch checklist", encoded)
        self.assertIn("omitted_context", packet)
        self.assertEqual(packet["omitted_context"][0]["counts"]["work_items"], 7)

    def test_cli_agent_brief_and_start_alias_emit_json(self) -> None:
        brief = json.loads(
            self.run_cli("agent", "brief", "WORK-0003", "--as", "PALARI-SOFIA", "--mode", "execute", "--json").stdout
        )
        start = json.loads(
            self.run_cli("agent", "start", "WORK-0003", "--as", "PALARI-SOFIA", "--mode", "execute", "--json").stdout
        )

        self.assertEqual(brief["status"], "ready")
        self.assertEqual(start["status"], "ready")
        self.assertEqual(brief["packet_id"], start["packet_id"])

    def modified_workspace(self, mutate: object) -> Workspace:
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        mutate(source)
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            workspace_file.write_text(json.dumps(source), encoding="utf-8")
            return Workspace.load(workspace_file)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(WORKSPACE), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
