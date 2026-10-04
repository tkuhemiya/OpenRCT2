#!/usr/bin/env python3
"""File-backed session client so an LLM can play across multiple shell calls."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openrct2_agent import logging_util
from openrct2_agent.persist import load_session, save_session


def main() -> None:
    logging_util.configure()
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["reset", "state", "legal", "step", "replay"])
    p.add_argument("--session", default="llm")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--scenario", default="gentle_intro")
    p.add_argument("--action", default=None)
    p.add_argument("--text", action="store_true")
    args = p.parse_args()
    session = load_session(args.session)
    if args.cmd == "reset":
        out = session.reset(args.seed, args.scenario)
    elif args.cmd == "state":
        out = session.get_state()
    elif args.cmd == "legal":
        out = session.list_legal_actions()
    elif args.cmd == "step":
        if args.action is None:
            print(json.dumps({"ok": False, "error": "--action required"}))
            sys.exit(2)
        try:
            action = json.loads(args.action)
        except json.JSONDecodeError:
            action = args.action
        out = session.step(action)
    else:
        out = {"ok": True, "replay": session.export_replay()}
    save_session(session)
    if args.text and "text" in out:
        # Keep legal lists usable: print text plus a compact action sample.
        sys.stdout.write(out["text"] + "\n")
        if "actions_flat" in out:
            flat = out["actions_flat"]
            sys.stdout.write("\n--- legal action ids (first 80) ---\n")
            sys.stdout.write("\n".join(flat[:80]) + "\n")
            sys.stdout.write(f"... total {len(flat)}\n")
        return
    # Drop huge origin maps from stdout for LLM context; keep counts + sample.
    if isinstance(out, dict) and "actions" in out and not args.text:
        out = dict(out)
        out["actions"] = out["actions"][:120]
        if "action_types" in out:
            types = []
            for t in out["action_types"]:
                t2 = dict(t)
                if "origins" in t2:
                    t2["origins"] = {k: v[:8] for k, v in t2["origins"].items()}
                if "valid_tiles" in t2:
                    t2["valid_tiles"] = t2["valid_tiles"][:40]
                types.append(t2)
            out["action_types"] = types
    json.dump(out, sys.stdout, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
