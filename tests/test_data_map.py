from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.data_map import build_data_map
from palari_company_os.workspace import Workspace


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class DataMapTests(unittest.TestCase):
    def test_data_map_summarizes_sources_integrations_and_memory(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        payload = build_data_map(workspace)

        self.assertEqual(payload["workspace"]["name"], "Acme Company OS Example")
        self.assertEqual(payload["storage"]["workspace_file"], "workspace.json")
        self.assertEqual(payload["storage"]["cache_index_status"], "none")
        self.assertIn("raw provider tokens or secrets", payload["not_stored"])

        source_ids = [source["id"] for source in payload["sources"]]
        self.assertEqual(source_ids, ["SOURCE-0001", "SOURCE-0002", "SOURCE-0003"])
        source_by_id = {source["id"]: source for source in payload["sources"]}
        self.assertEqual(source_by_id["SOURCE-0001"]["data_class"], "internal")
        self.assertEqual(source_by_id["SOURCE-0001"]["authority"], "company_owned")
        self.assertEqual(source_by_id["SOURCE-0003"]["steward_human"], "HUMAN-OPS")
        self.assertTrue(source_by_id["SOURCE-0003"]["redaction_required"])

        provider_names = [provider["provider"] for provider in payload["external_systems"]]
        self.assertIn("local_note", provider_names)
        self.assertIn("slack", provider_names)

        memory_by_palari = {
            item["palari_id"]: item["source_ids"]
            for item in payload["memory"]["palari_memory_sources"]
        }
        self.assertEqual(memory_by_palari["PALARI-SOFIA"], ["SOURCE-0001", "SOURCE-0002"])
        self.assertEqual(payload["integration_activity"]["live_provider_calls"], "disabled")

    def test_cli_data_map_text_names_boundaries(self) -> None:
        result = self.run_cli("data", "map")

        self.assertEqual(result.returncode, 0)
        self.assertIn("Palari Data Map: Acme Company OS Example", result.stdout)
        self.assertIn("history: .palari/history.jsonl", result.stdout)
        self.assertIn("readiness: data=internal", result.stdout)
        self.assertIn("redaction required", result.stdout)
        self.assertIn("live execution: disabled", result.stdout)
        self.assertIn("Not Stored", result.stdout)

    def test_cli_data_map_json_is_machine_readable(self) -> None:
        result = self.run_cli("data", "map", "--json")

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["workspace"]["schema_version"], 1)
        self.assertEqual(payload["memory"]["memory_provider_adapters"], "not implemented")

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(WORKSPACE),
                *args,
            ],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
