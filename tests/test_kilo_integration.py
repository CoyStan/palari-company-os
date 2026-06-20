from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.kilo_integration import (
    build_kilo_prompt,
    resolve_kilo_command,
    run_kilo_for_work,
)
from palari_company_os.workspace import Workspace


EXAMPLE_WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class KiloIntegrationTests(unittest.TestCase):
    def test_kilo_prompt_uses_palari_work_boundary(self) -> None:
        workspace = Workspace.load(EXAMPLE_WORKSPACE)

        prompt = build_kilo_prompt(workspace, "WORK-0001", "Start with the safest useful step.")

        self.assertIn("You are Kilo Code being called from Palari Company OS.", prompt)
        self.assertIn("Work item: WORK-0001 - Prepare beta launch checklist", prompt)
        self.assertIn("Palari: Sofia (Workspace lead)", prompt)
        self.assertIn("Allowed resources:", prompt)
        self.assertIn("examples/acme-company-os/workspace.json", prompt)
        self.assertIn("Allowed sources:", prompt)
        self.assertIn("SOURCE-0001: Beta launch note", prompt)
        self.assertIn("Forbidden actions:", prompt)
        self.assertIn("deploy", prompt)
        self.assertIn("AI safe to proceed:", prompt)
        self.assertIn("Start with the safest useful step.", prompt)

    def test_kilo_preview_does_not_require_installed_kilo(self) -> None:
        with patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}, clear=False):
            os.environ.pop("PALARI_KILO_BIN", None)
            payload = run_kilo_for_work(
                EXAMPLE_WORKSPACE,
                "WORK-0001",
                "Preview only",
                run_dir=REPO_ROOT,
            )

        self.assertFalse(payload["execute"])
        self.assertEqual(payload["command"][0], "kilo")
        self.assertIn("run", payload["command"])
        self.assertIn("--dir", payload["command"])
        self.assertIn("Preview only", payload["prompt"])
        self.assertNotIn("returncode", payload)

    def test_kilo_execute_uses_configured_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            capture = temp / "capture.json"
            fake_kilo = temp / "kilo"
            fake_kilo.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                f"open({str(capture)!r}, 'w', encoding='utf-8').write(json.dumps({{'argv': sys.argv[1:], 'cwd': os.getcwd()}}))\n"
                "print('fake kilo executed')\n",
                encoding="utf-8",
            )
            fake_kilo.chmod(0o755)

            with patch.dict(os.environ, {"PALARI_KILO_BIN": str(fake_kilo)}, clear=False):
                payload = run_kilo_for_work(
                    EXAMPLE_WORKSPACE,
                    "WORK-0001",
                    "Execute through fake Kilo",
                    execute=True,
                    run_dir=temp,
                )

            captured = json.loads(capture.read_text(encoding="utf-8"))

        self.assertTrue(payload["execute"])
        self.assertTrue(payload["available"])
        self.assertEqual(payload["returncode"], 0)
        self.assertIn("fake kilo executed", payload["stdout"])
        self.assertEqual(captured["cwd"], str(temp))
        self.assertEqual(captured["argv"][0], "run")
        self.assertIn("--dir", captured["argv"])
        self.assertIn(str(temp), captured["argv"])
        self.assertIn("Execute through fake Kilo", captured["argv"][-1])
        self.assertIn("WORK-0001", captured["argv"][-1])

    def test_kilo_command_resolution_can_use_npx_fallback(self) -> None:
        command = resolve_kilo_command(allow_npx=True, env={"PATH": os.environ.get("PATH", "")})

        if command.source == "npx":
            self.assertIn("@kilocode/cli", command.argv)
        else:
            self.assertIn(command.source, {"PATH:kilo", "PATH:kilocode", "missing"})

    def test_cli_kilo_run_preview_json(self) -> None:
        result = self.run_cli(
            "kilo",
            "run",
            "WORK-0001",
            "--message",
            "Preview from CLI",
            "--dir",
            str(REPO_ROOT),
            "--json",
        )
        payload = json.loads(result.stdout)

        self.assertFalse(payload["execute"])
        self.assertEqual(payload["work_id"], "WORK-0001")
        self.assertEqual(payload["cwd"], str(REPO_ROOT))
        self.assertIn("Preview from CLI", payload["prompt"])
        self.assertIn("kilo", payload["command"][0])

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env.pop("PALARI_KILO_BIN", None)
        return subprocess.run(
            [sys.executable, "-m", "palari_company_os", "--workspace", str(EXAMPLE_WORKSPACE), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
