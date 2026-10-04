#!/usr/bin/env python3
"""Brute-force play: many seeded games with random + heuristic policies.

Writes a JSON summary under logs/ and appends crash/illegal findings.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openrct2_agent import logging_util
from openrct2_agent.api import ParkSession
from openrct2_agent.players import heuristic_policy, play, random_policy
import random


def run_one(kind: str, seed: int, scenario: str, max_steps: int) -> dict:
    t0 = time.time()
    try:
        session = ParkSession(f"{kind}-{seed}")
        session.reset(seed, scenario)
        rng = random.Random(seed + 17)

        def pol(sess: ParkSession):
            if kind == "heuristic":
                return heuristic_policy(sess)
            return random_policy(sess, rng)

        summary = play(session, pol, max_steps=max_steps)
        elapsed = time.time() - t0
        st = session.state
        return {
            "ok": True,
            "kind": kind,
            "seed": seed,
            "scenario": scenario,
            "result": summary["result"],
            "reason": summary["reason"],
            "steps": summary["steps"],
            "elapsed_s": round(elapsed, 3),
            "guests": None if st is None else st.num_guests,
            "rating": None if st is None else st.rating,
            "cash": None if st is None else st.cash,
            "rides": None if st is None else len(st.rides),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "kind": kind,
            "seed": seed,
            "scenario": scenario,
            "result": "crash",
            "reason": str(exc),
            "steps": 0,
            "elapsed_s": round(time.time() - t0, 3),
            "error": traceback.format_exc(),
        }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=40)
    p.add_argument("--heuristic", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=120)
    p.add_argument("--scenario", default="gentle_intro")
    p.add_argument("--out", default=None)
    args = p.parse_args()
    logging_util.configure()
    rows = []
    for i in range(args.heuristic):
        rows.append(run_one("heuristic", 1000 + i, args.scenario, args.max_steps + 80))
        print(f"heuristic {i+1}/{args.heuristic} -> {rows[-1]['result']} guests={rows[-1].get('guests')}", flush=True)
    for i in range(args.games):
        rows.append(run_one("random", 2000 + i, args.scenario, args.max_steps))
        if (i + 1) % 5 == 0 or not rows[-1]["ok"]:
            print(f"random {i+1}/{args.games} -> {rows[-1]['result']} ok={rows[-1]['ok']}", flush=True)

    crashes = [r for r in rows if not r["ok"] or r["result"] == "crash"]
    wins = [r for r in rows if r["result"] == "success"]
    fails = [r for r in rows if r["result"] == "failure"]
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "scenario": args.scenario,
        "n": len(rows),
        "crashes": len(crashes),
        "wins": len(wins),
        "failures": len(fails),
        "undecided": sum(1 for r in rows if r["result"] == "undecided"),
        "heuristic_wins": sum(1 for r in rows if r["kind"] == "heuristic" and r["result"] == "success"),
        "rows": rows,
        "crash_details": crashes,
    }
    out = args.out or os.path.join("logs", f"brute-{args.scenario}-{int(time.time())}.json")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps({k: summary[k] for k in summary if k != "rows" and k != "crash_details"}, indent=2))
    print("wrote", out)
    if crashes:
        sys.exit(2)


if __name__ == "__main__":
    main()
