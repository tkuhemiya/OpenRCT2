#!/usr/bin/env python3
"""Play with the heuristic (or random) policy and write a replay JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openrct2_agent import logging_util
from openrct2_agent.api import ParkSession
from openrct2_agent.players import heuristic_policy, play, random_policy
import random


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--scenario", default="gentle_intro")
    p.add_argument("--policy", choices=["heuristic", "random"], default="heuristic")
    p.add_argument("--max-steps", type=int, default=250)
    p.add_argument("--out", default="logs/replay.json")
    args = p.parse_args()
    logging_util.configure()
    session = ParkSession("play")
    session.reset(args.seed, args.scenario)
    rng = random.Random(args.seed)

    def pol(sess: ParkSession):
        if args.policy == "heuristic":
            return heuristic_policy(sess)
        return random_policy(sess, rng)

    frames: list[dict] = []

    def on_step(step, action, result):
        st = result.get("state") or {}
        frames.append(
            {
                "step": step,
                "action": action,
                "ok": result.get("ok"),
                "message": result.get("message"),
                "error": result.get("error"),
                "text": result.get("text"),
                "ascii": (st.get("map") or {}).get("ascii"),
                "guests": (st.get("guests") or {}).get("in_park"),
                "cash": (st.get("finance") or {}).get("cash"),
                "rating": st.get("rating"),
                "result": result.get("result"),
            }
        )

    summary = play(session, pol, max_steps=args.max_steps, on_step=on_step)
    blob = {
        "seed": args.seed,
        "scenario": args.scenario,
        "policy": args.policy,
        "result": summary["result"],
        "reason": summary["reason"],
        "steps": summary["steps"],
        "replay": summary["replay"],
        "frames": frames,
        "final_text": summary.get("text"),
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(blob, f)
    print(f"result={summary['result']} reason={summary['reason']} steps={summary['steps']} wrote {args.out}")


if __name__ == "__main__":
    main()
