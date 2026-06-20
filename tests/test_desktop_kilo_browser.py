from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.desktop_prototype import generate_desktop_prototype, load_desktop_demo_data
from palari_company_os.desktop_server import DesktopServerConfig, make_desktop_handler


BROWSER = (
    shutil.which("chromium")
    or shutil.which("chromium-browser")
    or shutil.which("google-chrome")
)


@unittest.skipUnless(BROWSER, "Chromium-compatible browser is not available")
class DesktopKiloBrowserTests(unittest.TestCase):
    def test_served_desktop_app_can_preview_and_run_kilo_from_ui(self) -> None:
        data = load_desktop_demo_data()
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            output = temp / "prototype"
            fake_kilo = temp / "kilo"
            capture = temp / "capture.json"
            fake_kilo.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "capture = os.environ.get('PALARI_FAKE_KILO_CAPTURE')\n"
                "if capture:\n"
                "    open(capture, 'w', encoding='utf-8').write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}))\n"
                "print('fake kilo from browser test')\n",
                encoding="utf-8",
            )
            fake_kilo.chmod(0o755)
            generate_desktop_prototype(output, data=data)
            config = DesktopServerConfig(
                output_dir=output,
                data=data,
                run_dir=REPO_ROOT,
                allow_execute=True,
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_desktop_handler(config))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            env = {
                "PALARI_KILO_BIN": str(fake_kilo),
                "PALARI_FAKE_KILO_CAPTURE": str(capture),
            }
            with patch.dict(os.environ, env, clear=False):
                thread.start()
                try:
                    base_url = f"http://127.0.0.1:{server.server_address[1]}"
                    result = run_browser_click_smoke(f"{base_url}/#kilo")
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)

            captured = json.loads(capture.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "Ready")
        self.assertIn("execution is enabled", result["note"])
        self.assertTrue(result["preview_contains_prompt"])
        self.assertTrue(result["preview_contains_work"])
        self.assertTrue(result["run_contains_fake_kilo"])
        self.assertEqual(captured["argv"][0], "run")
        self.assertIn("--dir", captured["argv"])
        self.assertIn("PRL-HOUS-001", captured["argv"][-1])
        self.assertEqual(captured["cwd"], str(REPO_ROOT))


def run_browser_click_smoke(url: str) -> dict[str, Any]:
    port = free_port()
    with tempfile.TemporaryDirectory() as profile:
        proc = subprocess.Popen(
            [
                str(BROWSER),
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile}",
                "--window-size=1440,900",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            page = wait_for_page(port)
            cdp = CDPWebSocket(page["webSocketDebuggerUrl"])
            try:
                cdp.request("Runtime.enable")
                time.sleep(1.0)
                status = cdp.evaluate("document.querySelector('[data-kilo-status]').textContent")
                note = cdp.evaluate("document.querySelector('[data-kilo-note]').textContent")
                preview = cdp.evaluate(
                    "new Promise(resolve => { "
                    "document.querySelector('[data-kilo-preview]').click(); "
                    "setTimeout(() => resolve(document.querySelector('[data-kilo-output]').textContent), 1200); "
                    "})"
                )
                run = cdp.evaluate(
                    "new Promise(resolve => { "
                    "document.querySelector('[data-kilo-run]').click(); "
                    "setTimeout(() => resolve(document.querySelector('[data-kilo-output]').textContent), 1200); "
                    "})"
                )
            finally:
                cdp.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return {
        "status": status,
        "note": note,
        "preview_contains_prompt": "You are Kilo Code being called from the Palari Desktop app." in preview,
        "preview_contains_work": "PRL-HOUS-001" in preview,
        "run_contains_fake_kilo": "fake kilo from browser test" in run,
    }


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_page(port: int) -> dict[str, Any]:
    deadline = time.time() + 10
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                pages = json.loads(response.read().decode("utf-8"))
            for page in pages:
                if page.get("type") == "page":
                    return page
        except Exception as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"timed out waiting for browser page: {last_error}")


class CDPWebSocket:
    def __init__(self, url: str):
        parsed = urlparse(url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 80
        self.path = parsed.path
        if parsed.query:
            self.path += "?" + parsed.query
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(response.decode("latin1", errors="replace"))
        self.next_id = 1

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float = 10) -> dict[str, Any]:
        message_id = self._send(method, params or {})
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = self._read_frame()
            if not frame:
                continue
            payload = json.loads(frame.decode("utf-8"))
            if payload.get("id") == message_id:
                if "error" in payload:
                    raise RuntimeError(payload["error"])
                return payload.get("result", {})
        raise TimeoutError(method)

    def evaluate(self, expression: str) -> Any:
        result = self.request(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        value = result.get("result", {})
        if "value" in value:
            return value["value"]
        return value.get("description", "")

    def close(self) -> None:
        self.sock.close()

    def _send(self, method: str, params: dict[str, Any]) -> int:
        message_id = self.next_id
        self.next_id += 1
        payload = json.dumps({"id": message_id, "method": method, "params": params}).encode("utf-8")
        self._send_frame(payload)
        return message_id

    def _send_frame(self, payload: bytes) -> None:
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(header + masked)

    def _read_frame(self) -> bytes:
        first, second = self._read_exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        masked = bool(second & 0x80)
        mask = self._read_exact(4) if masked else b""
        payload = self._read_exact(length)
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        if opcode == 0x8:
            raise EOFError("websocket closed")
        if opcode != 0x1:
            return b""
        return payload

    def _read_exact(self, count: int) -> bytes:
        data = b""
        while len(data) < count:
            chunk = self.sock.recv(count - len(data))
            if not chunk:
                raise EOFError("websocket closed")
            data += chunk
        return data


if __name__ == "__main__":
    unittest.main()
