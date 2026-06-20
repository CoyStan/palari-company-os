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

from palari_company_os.playbooks import available_playbooks, recommend_playbooks
from palari_company_os.workspace import Workspace, WorkspaceError


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class PlaybookTests(unittest.TestCase):
    def test_workspace_declares_superpowers_playbook_source(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        playbooks = {playbook.id: playbook for playbook in available_playbooks(workspace)}

        self.assertIn("superpowers:writing-plans", playbooks)
        self.assertIn("superpowers:verification-before-completion", playbooks)
        self.assertEqual(
            playbooks["superpowers:writing-plans"].uri,
            "https://github.com/obra/Superpowers/blob/main/skills/writing-plans/SKILL.md",
        )

    def test_manual_and_automatic_recommendations_are_merged(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        payload = recommend_playbooks(workspace, "WORK-0001")
        recommended = {item["id"]: item for item in payload["recommended"]}

        self.assertTrue(recommended["superpowers:verification-before-completion"]["selected_by_user"])
        self.assertTrue(recommended["superpowers:requesting-code-review"]["selected_by_user"])
        self.assertIn("Use or install", payload["next_action"])

    def test_missing_evidence_recommends_verification_skill(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        payload = recommend_playbooks(workspace, "WORK-0003")
        ids = [item["id"] for item in payload["recommended"]]

        self.assertEqual(ids, ["superpowers:verification-before-completion"])
        self.assertIn("without evidence", payload["recommended"][0]["reason"])

    def test_stale_evidence_recommends_verification_before_review(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        payload = recommend_playbooks(workspace, "WORK-0005")
        ids = [item["id"] for item in payload["recommended"]]

        self.assertEqual(ids, ["superpowers:verification-before-completion"])
        self.assertIn("stale", payload["recommended"][0]["reason"])

    def test_unknown_recommended_playbook_fails_closed(self) -> None:
        with self.modified_workspace(
            lambda data: data["work_items"][0].update(
                {"recommended_playbooks": ["superpowers:not-a-skill"]}
            )
        ) as workspace_file:
            with self.assertRaises(WorkspaceError) as error:
                Workspace.load(workspace_file)

        self.assertIn("not included by source superpowers", str(error.exception))

    def test_cli_playbook_recommend_json(self) -> None:
        result = self.run_cli("playbooks", "recommend", "WORK-0003", "--json")
        payload = json.loads(result.stdout)

        self.assertEqual(payload["work_item"], "WORK-0003")
        self.assertEqual(
            payload["recommended"][0]["id"], "superpowers:verification-before-completion"
        )

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

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "palari_company_os", "--workspace", str(WORKSPACE), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
