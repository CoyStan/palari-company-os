from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.workspace import Workspace


class WorkspaceInitTests(unittest.TestCase):
    def test_workspace_init_creates_valid_blank_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_dir = Path(directory) / "new-workspace"
            result = self.run_cli(
                "workspace",
                "init",
                str(workspace_dir),
                "--name",
                "New Workspace",
                "--json",
            )

            payload = json.loads(result.stdout)
            workspace_file = workspace_dir / "workspace.json"
            workspace = Workspace.load(workspace_dir)

            self.assertEqual(payload["workspace"], "New Workspace")
            self.assertEqual(Path(payload["workspace_file"]), workspace_file)
            self.assertTrue(payload["valid"])
            self.assertEqual(workspace.name, "New Workspace")
            self.assertEqual(len(workspace.goals), 0)
            self.assertEqual(len(workspace.workbenches), 0)
            self.assertIn(f"palari --workspace {workspace_file} validate", payload["next_commands"])

    def test_workspace_init_refuses_to_overwrite_existing_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_dir = Path(directory) / "new-workspace"
            self.run_cli("workspace", "init", str(workspace_dir), "--name", "New Workspace")

            result = subprocess.run(
                [
                    str(REPO_ROOT / "bin" / "palari"),
                    "workspace",
                    "init",
                    str(workspace_dir),
                    "--name",
                    "Replacement",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("workspace file already exists", result.stderr)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(REPO_ROOT / "bin" / "palari"), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
