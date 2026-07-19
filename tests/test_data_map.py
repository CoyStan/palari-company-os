from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.data_map import build_data_map, format_data_map
from palari_company_os.store import load_store, write_store
from palari_company_os.workspace import Workspace
from tests.workspace_fixture import write_current_agent_workspace


class DataMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.workspace_file = self.root / "workspace.json"
        write_current_agent_workspace(self.workspace_file)
        self._seed_mapping_records()

    def test_data_map_projects_storage_source_and_integration_boundaries(self) -> None:
        payload = build_data_map(Workspace.load(self.workspace_file))

        self.assertEqual(payload["workspace"], {
            "name": "Current Agent Test Workspace",
            "schema_version": 2,
        })
        self.assertEqual(payload["storage"]["workspace_file"], "workspace.json")
        self.assertTrue(payload["storage"]["journal_enabled"])
        self.assertEqual(payload["storage"]["cache_index_status"], "none")
        self.assertIn("raw provider tokens or secrets", payload["not_stored"])

        sources = {item["id"]: item for item in payload["sources"]}
        local = sources["SOURCE-REPO-FOUNDATION"]
        self.assertEqual(local["data_class"], "internal")
        self.assertEqual(local["authority"], "company_owned")
        self.assertEqual(local["used_by_work_items"], ["WORK-DATA-MAP"])
        self.assertEqual(
            local["used_by_workbenches"],
            ["WORKBENCH-REPO-FOUNDATION"],
        )
        self.assertEqual(
            local["memory_for_palaris"],
            ["PALARI-ARCHITECT", "PALARI-STEWARD"],
        )
        self.assertTrue(sources["SOURCE-REDACTED"]["redaction_required"])

        providers = {
            item["provider"]: item["declared_by"]
            for item in payload["external_systems"]
        }
        self.assertEqual(providers, {
            "linear": ["integration"],
            "local": ["source"],
        })
        integration = payload["integrations"][0]
        self.assertEqual(integration["provider"], "linear")
        self.assertEqual(integration["secret_ref"], "env_reference")
        self.assertEqual(integration["live_execution"], "disabled")
        self.assertEqual(payload["integration_activity"]["live_provider_calls"], "disabled")

    def test_text_formatter_names_the_same_read_only_boundaries(self) -> None:
        lines = format_data_map(build_data_map(Workspace.load(self.workspace_file)))
        rendered = "\n".join(lines)

        self.assertIn("Palari Data Map: Current Agent Test Workspace", rendered)
        self.assertIn("journal: .palari/governance-journal.v2.jsonl (enabled)", rendered)
        self.assertIn("readiness: data=internal", rendered)
        self.assertIn("redaction required", rendered)
        self.assertIn("live execution: disabled", rendered)
        self.assertIn("Not Stored", rendered)

    def _seed_mapping_records(self) -> None:
        store = load_store(self.workspace_file)
        store.data["sources"].append(
            {
                "id": "SOURCE-REDACTED",
                "label": "Redacted local note",
                "kind": "note",
                "provider": "local",
                "uri": "notes/redacted.md",
                "access_mode": "read",
                "selected": True,
                "owner_human": "HUMAN-FOUNDER",
                "allowed_palaris": ["PALARI-STEWARD"],
                "data_class": "restricted",
                "authority": "company_owned",
                "steward_human": "HUMAN-FOUNDER",
                "redaction_required": True,
            }
        )
        store.data["work_items"] = [
            {
                "id": "WORK-DATA-MAP",
                "title": "Map declared data boundaries",
                "goal": "GOAL-REPO-0001",
                "palari": "PALARI-STEWARD",
                "risk": "R1",
                "intensity": "light",
                "status": "active",
                "scope": "Read the declared sources only.",
                "allowed_resources": ["README.md"],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": ["README.md"],
                "forbidden_actions": ["external_write"],
                "required_approval_count": 0,
            }
        ]
        store.data["integrations"] = [
            {
                "id": "INTEGRATION-DATA-MAP",
                "provider": "linear",
                "label": "Declared issue notification",
                "mode": "notify",
                "owner_human": "HUMAN-FOUNDER",
                "enabled": True,
                "allowed_events": ["approval_requested"],
                "allowed_actions": ["notify"],
                "secret_ref": "env:LINEAR_API_KEY",
                "risk_level": "standard",
                "source_ids": ["SOURCE-REDACTED"],
            }
        ]
        write_store(store)


if __name__ == "__main__":
    unittest.main()
