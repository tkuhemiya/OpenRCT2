#!/usr/bin/env python3
"""Record a gameplay video of the heuristic agent using the isometric camera.

The park is drawn in code (openrct2_agent.art). The agent loop stays text-only.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openrct2_agent import logging_util
from openrct2_agent.api import ParkSession
from openrct2_agent.players import heuristic_policy, play, random_policy
from openrct2_agent.visual import VisualPark, caption_for
import random

SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
try:
    from pack_assets import SPRITE_DIR, pack
except Exception:  # noqa: BLE001
    SPRITE_DIR = None
    pack = None


def _highlight_for(action: str):
    try:
        typ, rest = str(action).split(":", 1)
    except ValueError:
        return None
    parts = rest.split(",")
    if typ in ("place_path", "remove_path", "buy_land") and len(parts) == 2:
        return int(parts[0]), int(parts[1]), 1, 1
    if typ in ("place_ride", "place_stall", "place_scenery") and len(parts) >= 3:
        return int(parts[1]), int(parts[2]), 1, 1
    return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--scenario", default="gentle_intro")
    p.add_argument("--policy", choices=["heuristic", "random"], default="heuristic")
    p.add_argument("--max-steps", type=int, default=250)
    p.add_argument("--mp4", default="recordings/agent_play_gameplay.mp4")
    p.add_argument("--fps", type=int, default=10)
    args = p.parse_args()

    if SPRITE_DIR is not None and pack is not None and not (SPRITE_DIR / "grass.png").exists():
        try:
            pack()
        except Exception:
            pass

    logging_util.configure()
    session = ParkSession("gameplay")
    session.reset(args.seed, args.scenario)
    rng = random.Random(args.seed)
    vis = VisualPark()
    tmp = Path(tempfile.mkdtemp(prefix="rct-game-"))
    n = [0]

    def pol(sess: ParkSession):
        if args.policy == "heuristic":
            return heuristic_policy(sess)
        return random_policy(sess, rng)

    def emit(state, caption: str, frames: int, highlight=None) -> None:
        assert state is not None
        for i in range(frames):
            img = vis.render(state, caption=caption, tick=n[0] + i, highlight=highlight)
            img.save(tmp / f"frame_{n[0]:05d}.png")
            n[0] += 1

    # Opening establishing shot.
    emit(session.state, "A new park", 8)

    def on_step(step, action, result):
        cap = caption_for(action)
        hl = _highlight_for(action) if result.get("ok") else None
        hold = 12 if str(action).startswith("wait") else 5
        if str(action).startswith("set_park_open"):
            hold = 10
        emit(session.state, cap, hold, highlight=hl)

    summary = play(session, pol, max_steps=args.max_steps, on_step=on_step)
    final_cap = "Scenario complete!" if summary["result"] == "success" else summary.get("reason") or ""
    emit(session.state, final_cap, 16)

    out = Path(args.mp4)
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg missing; frames in", tmp)
        return
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(args.fps),
        "-i",
        str(tmp / "frame_%05d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        str(out),
    ]
    subprocess.check_call(cmd)
    shutil.rmtree(tmp, ignore_errors=True)
    still_start = out.with_name(out.stem + "_start.png")
    still_end = out.with_name(out.stem + "_end.png")
    # Re-render just start/end for the PR.
    session2 = ParkSession("stills")
    session2.reset(args.seed, args.scenario)
    vis.render(session2.state, caption="A new park", tick=0).save(still_start)
    vis.render(session.state, caption=final_cap, tick=99).save(still_end)
    print(
        f"result={summary['result']} reason={summary['reason']} "
        f"steps={summary['steps']} frames={n[0]} wrote {out}"
    )


if __name__ == "__main__":
    main()
