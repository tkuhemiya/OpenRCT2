"""Stdio JSON-lines and one-shot CLI for the agent API."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import logging_util
from .api import AgentAPI, dumps


def _print(obj: Any) -> None:
    sys.stdout.write(dumps(obj) + "\n")
    sys.stdout.flush()


def run_stdio() -> None:
    logging_util.configure()
    api = AgentAPI()
    _print({"ok": True, "service": "openrct2-agent-stdio", "log": str(logging_util.log_path())})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            _print({"ok": False, "error": f"Invalid JSON: {exc}", "code": "bad_json"})
            continue
        if isinstance(payload, dict) and payload.get("cmd") in ("quit", "exit"):
            _print({"ok": True, "message": "bye"})
            return
        _print(api.dispatch(payload if isinstance(payload, dict) else {"cmd": None}))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="OpenRCT2 text agent CLI")
    p.add_argument("cmd", nargs="?", help="reset|state|legal|step|stdio|serve|help")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--scenario", default="forest_frontiers")
    p.add_argument("--action", default=None)
    p.add_argument("--session", default="default")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--text", action="store_true", help="Print only the readable text field")
    args = p.parse_args(argv)
    logging_util.configure()
    if args.cmd in (None, "help"):
        print(
            "Usage:\n"
            "  python -m openrct2_agent.cli stdio\n"
            "  python -m openrct2_agent.cli serve --port 8765\n"
            "  python -m openrct2_agent.cli reset --seed 42 --scenario gentle_intro\n"
            "  python -m openrct2_agent.cli state --text\n"
            "  python -m openrct2_agent.cli legal\n"
            "  python -m openrct2_agent.cli step --action wait:1\n"
        )
        return
    if args.cmd == "stdio":
        run_stdio()
        return
    if args.cmd == "serve":
        from .server import serve

        serve(args.host, args.port)
        return
    api = AgentAPI()
    if args.cmd == "reset":
        out = api.reset(args.seed, args.scenario, args.session)
    elif args.cmd in ("state", "get_state"):
        out = api.get_state(args.session)
    elif args.cmd in ("legal", "list_legal_actions"):
        out = api.list_legal_actions(args.session)
    elif args.cmd == "step":
        if not args.action:
            _print({"ok": False, "error": "Pass --action", "code": "bad_params"})
            return
        try:
            action: Any = json.loads(args.action)
        except json.JSONDecodeError:
            action = args.action
        out = api.step(action, args.session)
    else:
        _print({"ok": False, "error": f"Unknown cmd {args.cmd}", "code": "unknown_cmd"})
        return
    if args.text and isinstance(out, dict) and "text" in out:
        sys.stdout.write(out["text"] + "\n")
        return
    _print(out)


if __name__ == "__main__":
    main()
