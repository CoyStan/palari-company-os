from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.desktop_prototype import generate_desktop_prototype, load_desktop_demo_data
from palari_company_os.desktop_server import DesktopServerConfig, make_desktop_handler
from palari_company_os.kilo_integration import (
    build_kilo_prompt,
    build_kilo_prompt_from_desktop_data,
    resolve_kilo_command,
    run_kilo_for_desktop_data,
    run_kilo_for_work,
)
from palari_company_os.workspace import Workspace, WorkspaceError


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

    def test_kilo_execute_fails_closed_on_zero_code_stderr_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_kilo = temp / "kilo"
            fake_kilo.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "print('\\x1b[91mError: provider credits exhausted\\x1b[0m', file=sys.stderr)\n",
                encoding="utf-8",
            )
            fake_kilo.chmod(0o755)

            with patch.dict(os.environ, {"PALARI_KILO_BIN": str(fake_kilo)}, clear=False):
                with self.assertRaises(WorkspaceError) as error:
                    run_kilo_for_work(
                        EXAMPLE_WORKSPACE,
                        "WORK-0001",
                        "Execute through fake Kilo",
                        execute=True,
                        run_dir=temp,
                    )

        self.assertIn("provider credits exhausted", str(error.exception))

    def test_kilo_execute_fails_closed_on_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_kilo = temp / "kilo"
            fake_kilo.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "print('provider refused request', file=sys.stderr)\n"
                "raise SystemExit(7)\n",
                encoding="utf-8",
            )
            fake_kilo.chmod(0o755)

            with patch.dict(os.environ, {"PALARI_KILO_BIN": str(fake_kilo)}, clear=False):
                with self.assertRaises(WorkspaceError) as error:
                    run_kilo_for_work(
                        EXAMPLE_WORKSPACE,
                        "WORK-0001",
                        "Execute through fake Kilo",
                        execute=True,
                        run_dir=temp,
                    )

        self.assertIn("provider refused request", str(error.exception))

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

    def test_desktop_fixture_kilo_prompt_uses_visible_boundaries(self) -> None:
        data = load_desktop_demo_data()

        prompt = build_kilo_prompt_from_desktop_data(data, "comment", "Tighten the draft.")

        self.assertIn("You are Kilo Code being called from the Palari Desktop app.", prompt)
        self.assertIn("Workspace: Public Policy Demo Workspace", prompt)
        self.assertIn("Workbench: Public Policy / Housing", prompt)
        self.assertIn("Work item: PRL-HOUS-001 - Draft public comment", prompt)
        self.assertIn("Palari: Maya (Policy Researcher)", prompt)
        self.assertIn("Allowed sources:", prompt)
        self.assertIn("California HCD - 2025 Housing Plan", prompt)
        self.assertIn("Output targets:", prompt)
        self.assertIn("Oakland Planning Dept - Comment Portal", prompt)
        self.assertIn("Blocked sources visible in the UI:", prompt)
        self.assertIn("Private constituent email thread", prompt)
        self.assertIn("Do not read blocked sources.", prompt)
        self.assertIn("Tighten the draft.", prompt)

    def test_desktop_fixture_kilo_preview_does_not_require_installed_kilo(self) -> None:
        data = load_desktop_demo_data()

        with patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}, clear=False):
            os.environ.pop("PALARI_KILO_BIN", None)
            payload = run_kilo_for_desktop_data(
                data,
                "comment",
                "Preview from desktop",
                run_dir=REPO_ROOT,
            )

        self.assertFalse(payload["execute"])
        self.assertEqual(payload["work_id"], "comment")
        self.assertEqual(payload["work_title"], "Draft public comment on Housing Element")
        self.assertIn("Preview from desktop", payload["prompt"])
        self.assertEqual(payload["command"][0], "kilo")

    def test_desktop_server_exposes_kilo_preview_and_blocks_execution_by_default(self) -> None:
        data = load_desktop_demo_data()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate_desktop_prototype(output, data=data)
            config = DesktopServerConfig(output_dir=output, data=data, run_dir=REPO_ROOT)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_desktop_handler(config))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                status = self.fetch_json(f"{base_url}/api/kilo/status")
                preview = self.post_json(
                    f"{base_url}/api/kilo/run",
                    {"work_id": "comment", "message": "Preview through local API"},
                )
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.post_json(
                        f"{base_url}/api/kilo/run",
                        {"work_id": "comment", "message": "Execute through local API", "execute": True},
                    )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertFalse(status["execute_enabled"])
        self.assertEqual(status["server"], "palari desktop-serve")
        self.assertEqual(preview["work_id"], "comment")
        self.assertFalse(preview["execute"])
        self.assertIn("Preview through local API", preview["prompt"])
        self.assertEqual(error.exception.code, 403)

    def fetch_json(self, url: str) -> dict[str, object]:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, url: str, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

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
