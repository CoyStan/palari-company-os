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

from palari_company_os.gate_profiles import GATE_PROFILES, gate_profile_catalog, recommend_gates
from palari_company_os.workspace import Workspace


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"
DOGFOOD_WORKSPACE = REPO_ROOT / "workspaces" / "palari-company-os"


class GateProfileTests(unittest.TestCase):
    def test_profiles_include_initial_builtin_gates(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        payload = gate_profile_catalog(workspace)

        self.assertEqual(payload["schema_version"], "palari.gate_profiles.v1")
        self.assertFalse(payload["would_mutate"])
        self.assertEqual(
            [profile["id"] for profile in payload["profiles"]],
            [
                "prompt-authority",
                "source-boundary",
                "external-write",
                "human-approval",
                "deploy-runtime",
                "privacy-multimodal",
                "product-overclaim",
            ],
        )
        self.assertEqual(len(payload["profiles"]), len(GATE_PROFILES))

    def test_low_risk_local_work_recommends_no_special_gate(self) -> None:
        with self.modified_workspace(self._make_work_0007_simple_local) as workspace_file:
            workspace = Workspace.load(workspace_file)

            payload = recommend_gates(workspace, "WORK-0007")

        self.assertTrue(payload["no_special_gate_required"])
        self.assertEqual(payload["recommended_gates"], [])
        self.assertIn("normal receipt/evidence/review flow", payload["next_action"])

    def test_source_heavy_work_recommends_source_boundary(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        payload = recommend_gates(workspace, "WORK-0007")
        ids = self.gate_ids(payload)

        self.assertEqual(ids, ["source-boundary"])
        contract = payload["review_contracts"][0]
        self.assertEqual(contract["gate_id"], "source-boundary")
        self.assertIn("allowed_sources", " ".join(contract["inspect"]))

    def test_integration_outbox_work_recommends_external_write_and_human_approval(self) -> None:
        with self.modified_workspace(self._add_approved_plan_and_outbox) as workspace_file:
            workspace = Workspace.load(workspace_file)

            payload = recommend_gates(workspace, "WORK-0003")
            ids = self.gate_ids(payload)

        self.assertIn("external-write", ids)
        self.assertIn("human-approval", ids)
        self.assertNotIn("deploy-runtime", ids)

    def test_multimodal_source_recommends_privacy_and_prompt_authority(self) -> None:
        with self.modified_workspace(self._make_image_source_work) as workspace_file:
            workspace = Workspace.load(workspace_file)

            payload = recommend_gates(workspace, "WORK-0007")
            ids = self.gate_ids(payload)

        self.assertIn("source-boundary", ids)
        self.assertIn("privacy-multimodal", ids)
        self.assertIn("prompt-authority", ids)

    def test_deploy_runtime_work_recommends_deploy_runtime(self) -> None:
        with self.modified_workspace(self._make_deploy_runtime_work) as workspace_file:
            workspace = Workspace.load(workspace_file)

            payload = recommend_gates(workspace, "WORK-0003")
            ids = self.gate_ids(payload)

        self.assertEqual(ids, ["deploy-runtime"])

    def test_public_product_copy_work_recommends_product_overclaim(self) -> None:
        with self.modified_workspace(self._make_product_copy_work) as workspace_file:
            workspace = Workspace.load(workspace_file)

            payload = recommend_gates(workspace, "WORK-0003")
            ids = self.gate_ids(payload)

        self.assertEqual(ids, ["product-overclaim"])
        self.assertIn("public", payload["recommended_gates"][0]["reason"])

    def test_json_output_is_deterministic_and_compact(self) -> None:
        first = json.loads(self.run_cli("gate", "recommend", "WORK-0007", "--json").stdout)
        second = json.loads(self.run_cli("gate", "recommend", "WORK-0007", "--json").stdout)

        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], "palari.gate_recommendations.v1")
        self.assertEqual(self.gate_ids(first), ["source-boundary"])
        self.assertLessEqual(len(json.dumps(first)), 5000)

    def test_cli_gate_profiles_json(self) -> None:
        payload = json.loads(self.run_cli("gate", "profiles", "--json").stdout)

        self.assertEqual(payload["schema_version"], "palari.gate_profiles.v1")
        self.assertEqual(payload["profiles"][0]["id"], "prompt-authority")

    def test_dogfood_smoke_recommends_human_approval(self) -> None:
        result = self.run_cli(
            "gate",
            "recommend",
            "WORK-REPO-0003",
            "--json",
            workspace=DOGFOOD_WORKSPACE,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["work_item"]["id"], "WORK-REPO-0003")
        self.assertEqual(self.gate_ids(payload), ["human-approval"])

    def gate_ids(self, payload: dict[str, Any]) -> list[str]:
        return [item["id"] for item in payload["recommended_gates"]]

    def modified_workspace(self, mutate: object):
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        mutate(source)
        directory = tempfile.TemporaryDirectory()
        workspace_file = Path(directory.name) / "workspace.json"
        workspace_file.write_text(json.dumps(source), encoding="utf-8")

        class WorkspaceFixture:
            def __enter__(self) -> Path:
                return workspace_file

            def __exit__(self, *args: object) -> None:
                directory.cleanup()

        return WorkspaceFixture()

    def run_cli(
        self,
        *args: str,
        workspace: Path = WORKSPACE,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(workspace),
                *args,
            ],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    @staticmethod
    def _make_work_0007_simple_local(data: dict[str, Any]) -> None:
        work = _work(data, "WORK-0007")
        work["allowed_sources"] = []
        work["scope"] = "Summarize local notes already present in the work item."
        work["required_approval_count"] = 0
        receipt = data["receipts"][0]
        receipt["sources_used"] = []

    @staticmethod
    def _add_approved_plan_and_outbox(data: dict[str, Any]) -> None:
        data["integration_plans"] = [
            {
                "id": "PLAN-GATE",
                "integration_id": "INT-SLACK-OPS",
                "work_item_id": "WORK-0003",
                "event": "approval_requested",
                "action": "notify",
                "actor": "PALARI-SOFIA",
                "status": "approved",
                "payload_preview": {
                    "provider": "slack",
                    "operation": "post_message",
                    "webhook_ref": "env:PALARI_SLACK_WEBHOOK_URL",
                },
                "source_boundary": {},
                "risk": "standard",
                "approval_required": True,
                "reviewed_by": "HUMAN-FOUNDER",
                "reviewed_at": "2026-06-23T00:00:00Z",
            }
        ]
        data["integration_outbox"] = [
            {
                "id": "OUTBOX-GATE",
                "plan_id": "PLAN-GATE",
                "integration_id": "INT-SLACK-OPS",
                "work_item_id": "WORK-0003",
                "event": "approval_requested",
                "action": "notify",
                "enqueued_by": "HUMAN-FOUNDER",
                "status": "queued",
                "payload_preview": {
                    "provider": "slack",
                    "operation": "post_message",
                    "webhook_ref": "env:PALARI_SLACK_WEBHOOK_URL",
                },
                "source_boundary": {},
                "risk": "standard",
            }
        ]

    @staticmethod
    def _make_image_source_work(data: dict[str, Any]) -> None:
        source = _source(data, "SOURCE-0001")
        source["label"] = "Uploaded support screenshot with OCR"
        source["kind"] = "uploaded_file"
        source["provider"] = "image_upload"
        source["uri"] = "examples/acme-company-os/uploads/support-screenshot.png"
        work = _work(data, "WORK-0007")
        work["title"] = "Summarize selected support screenshot"
        work["scope"] = "Use the image OCR text as untrusted visual evidence."

    @staticmethod
    def _make_deploy_runtime_work(data: dict[str, Any]) -> None:
        work = _work(data, "WORK-0003")
        work["title"] = "Prepare deploy runtime config smoke"
        work["scope"] = "Review deploy runtime config without changing production."
        work["acceptance_target"] = "Runtime boundaries are clear and unchanged."
        work["allowed_resources"] = [
            "docs/product/company-os.md",
            "infra/prod/deploy.sh",
            "runtime-data/config.json",
        ]

    @staticmethod
    def _make_product_copy_work(data: dict[str, Any]) -> None:
        work = _work(data, "WORK-0003")
        work["title"] = "Polish public README copy"
        work["scope"] = "Update public README copy without overclaiming AI capabilities."
        work["allowed_resources"] = [
            "docs/product/company-os.md",
            "README.md",
            "docs/product/quickstart.md",
        ]


def _work(data: dict[str, Any], work_id: str) -> dict[str, Any]:
    for work in data["work_items"]:
        if work["id"] == work_id:
            return work
    raise AssertionError(f"missing work item {work_id}")


def _source(data: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in data["sources"]:
        if source["id"] == source_id:
            return source
    raise AssertionError(f"missing source {source_id}")


if __name__ == "__main__":
    unittest.main()
