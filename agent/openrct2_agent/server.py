"""HTTP JSON API for the OpenRCT2 agent.

Endpoints:
  POST /reset              JSON {seed, scenario, session_id?}
  GET  /state              ?session_id=
  GET  /legal_actions      ?session_id=
  POST /step               JSON {action, session_id?}
  POST /rpc                JSON {cmd, ...}
  GET  /health
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .api import AgentAPI, dumps
from . import logging_util

API = AgentAPI()


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return {"_parse_error": f"Invalid JSON: {exc}"}
    if not isinstance(data, dict):
        return {"_parse_error": "JSON body must be an object."}
    return data


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenRCT2Agent/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        logging_util.log_event("http", message=fmt % args, client=self.address_string())

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        sid = (qs.get("session_id") or [None])[0]
        if parsed.path in ("/health", "/"):
            self._send(200, {"ok": True, "service": "openrct2-agent", "docs": "/help"})
            return
        if parsed.path in ("/help", "/api"):
            self._send(
                200,
                {
                    "ok": True,
                    "endpoints": {
                        "POST /reset": "{seed, scenario, session_id?}",
                        "GET /state": "?session_id=",
                        "GET /legal_actions": "?session_id=",
                        "POST /step": "{action, session_id?}",
                        "POST /rpc": "{cmd, ...}",
                    },
                    "scenarios": ["gentle_intro", "forest_frontiers", "dynamite_dunes", "have_fun"],
                },
            )
            return
        if parsed.path in ("/state", "/get_state"):
            self._send(200, API.get_state(sid))
            return
        if parsed.path in ("/legal_actions", "/actions", "/list_legal_actions"):
            self._send(200, API.list_legal_actions(sid))
            return
        if parsed.path == "/replay":
            self._send(200, {"ok": True, "replay": API.session(sid).export_replay()})
            return
        self._send(404, {"ok": False, "error": f"Unknown GET {parsed.path}", "code": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        body = _read_json(self)
        if "_parse_error" in body:
            self._send(400, {"ok": False, "error": body["_parse_error"], "code": "bad_json"})
            return
        sid = body.get("session_id")
        if parsed.path in ("/reset", "/new_game"):
            self._send(200, API.reset(body.get("seed", 1), body.get("scenario", "forest_frontiers"), sid))
            return
        if parsed.path in ("/step", "/act"):
            self._send(200, API.step(body.get("action"), sid))
            return
        if parsed.path in ("/rpc", "/dispatch"):
            self._send(200, API.dispatch(body))
            return
        self._send(404, {"ok": False, "error": f"Unknown POST {parsed.path}", "code": "not_found"})


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    logging_util.configure()
    httpd = ThreadingHTTPServer((host, port), Handler)
    logging_util.log_event("http.listen", host=host, port=port, log=str(logging_util.log_path()))
    print(f"OpenRCT2 agent API on http://{host}:{port}  log={logging_util.log_path()}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        httpd.server_close()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="OpenRCT2 text agent HTTP API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--log", default=None, help="JSONL log path")
    args = p.parse_args(argv)
    if args.log:
        logging_util.configure(args.log)
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
