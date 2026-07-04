from __future__ import annotations

import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .desktop_prototype import generate_desktop_prototype, load_desktop_demo_data


@dataclass(frozen=True)
class DesktopServerConfig:
    output_dir: Path
    data: dict[str, Any]


def serve_desktop_prototype(
    output_dir: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    fixture_path: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output_dir).expanduser().resolve()
    data = load_desktop_demo_data(fixture_path)
    generate_desktop_prototype(output, data=data)
    config = DesktopServerConfig(
        output_dir=output,
        data=data,
    )
    handler = make_desktop_handler(config)
    server = ThreadingHTTPServer((host, port), handler)
    bound_host = server.server_address[0]
    if isinstance(bound_host, bytes):
        bound_host = bound_host.decode("utf-8")
    url = f"http://{bound_host}:{server.server_address[1]}/"
    print(f"Palari Desktop server: {url}", flush=True)
    print(f"Prototype files: {output}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return {
        "url": url,
        "output_dir": str(output),
    }


def make_desktop_handler(config: DesktopServerConfig) -> type[SimpleHTTPRequestHandler]:
    class DesktopRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(config.output_dir), **kwargs)

        def do_GET(self) -> None:
            super().do_GET()

        def do_POST(self) -> None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            return payload

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    return DesktopRequestHandler
