from __future__ import annotations

import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .desktop_prototype import generate_desktop_prototype, load_desktop_demo_data
from .kilo_integration import kilo_status, run_kilo_for_desktop_data
from .workspace import WorkspaceError


@dataclass(frozen=True)
class DesktopServerConfig:
    output_dir: Path
    data: dict[str, Any]
    run_dir: Path
    allow_npx: bool = False
    allow_execute: bool = False
    model: str = ""
    agent: str = ""
    timeout: int | None = None


def serve_desktop_prototype(
    output_dir: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    fixture_path: str | Path | None = None,
    run_dir: str | Path | None = None,
    allow_npx: bool = False,
    allow_execute: bool = False,
    model: str = "",
    agent: str = "",
    timeout: int | None = None,
) -> dict[str, Any]:
    output = Path(output_dir).expanduser().resolve()
    data = load_desktop_demo_data(fixture_path)
    generate_desktop_prototype(output, data=data)
    config = DesktopServerConfig(
        output_dir=output,
        data=data,
        run_dir=Path(run_dir).expanduser().resolve() if run_dir else Path.cwd().resolve(),
        allow_npx=allow_npx,
        allow_execute=allow_execute,
        model=model,
        agent=agent,
        timeout=timeout,
    )
    handler = make_desktop_handler(config)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{server.server_address[0]}:{server.server_address[1]}/"
    print(f"Palari Desktop server: {url}", flush=True)
    print(f"Prototype files: {output}", flush=True)
    print(f"Kilo execute enabled: {'yes' if allow_execute else 'no'}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return {
        "url": url,
        "output_dir": str(output),
        "kilo_execute_enabled": allow_execute,
    }


def make_desktop_handler(config: DesktopServerConfig) -> type[SimpleHTTPRequestHandler]:
    class DesktopRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(config.output_dir), **kwargs)

        def do_GET(self) -> None:
            if self.path == "/api/kilo/status":
                payload = kilo_status(allow_npx=config.allow_npx)
                payload.update(
                    {
                        "execute_enabled": config.allow_execute,
                        "server": "palari desktop-serve",
                    }
                )
                self._send_json(HTTPStatus.OK, payload)
                return
            super().do_GET()

        def do_POST(self) -> None:
            if self.path != "/api/kilo/run":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
                return
            try:
                request = self._read_json_body()
                execute = bool(request.get("execute", False))
                if execute and not config.allow_execute:
                    self._send_json(
                        HTTPStatus.FORBIDDEN,
                        {
                            "error": "Kilo execution is disabled for this desktop server.",
                            "hint": "Restart with --allow-kilo-execute to enable explicit execution.",
                        },
                    )
                    return
                payload = run_kilo_for_desktop_data(
                    config.data,
                    str(request.get("work_id") or config.data["ui"]["default_work_item_id"]),
                    str(request.get("message") or ""),
                    execute=execute,
                    allow_npx=config.allow_npx,
                    model=config.model,
                    agent=config.agent,
                    run_dir=config.run_dir,
                    timeout=config.timeout,
                )
            except (WorkspaceError, KeyError, TypeError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._send_json(HTTPStatus.OK, payload)

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
