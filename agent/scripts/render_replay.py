#!/usr/bin/env python3
"""Render a replay JSON to an ASCII transcript and an MP4 (ffmpeg + PPM frames)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


FONT_W = 8
FONT_H = 14
COLS = 92
ROWS = 48
FG = (220, 230, 210)
BG = (12, 18, 14)
HUD = (240, 210, 90)
PATH = (90, 160, 90)
RIDE = (200, 80, 70)
STALL = (80, 140, 210)
ENT = (250, 220, 80)


def _glyph_bitmap() -> dict[str, list[str]]:
    """Minimal 5x7 glyphs packed into FONT cells; unknown chars -> block."""
    # Enough for HUD + map symbols.
    return {}


def _put_char(px: bytearray, w: int, h: int, cx: int, cy: int, ch: str, color: tuple[int, int, int]) -> None:
    # 8x14 bitmap via a tiny stroke font.
    patterns = _PATTERNS.get(ch, _PATTERNS.get(ch.upper()))
    ox, oy = cx * FONT_W, cy * FONT_H
    if patterns is None:
        # filled pixel in center so unknown chars are visible
        _dot(px, w, h, ox + 3, oy + 6, color)
        return
    for row, bits in enumerate(patterns):
        for col, bit in enumerate(bits):
            if bit == "1":
                _dot(px, w, h, ox + col + 1, oy + row + 2, color)


def _dot(px: bytearray, w: int, h: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < w and 0 <= y < h:
        i = (y * w + x) * 3
        px[i : i + 3] = bytes(color)


# 5x9 binary patterns for the characters we actually print.
def _p(*rows: str) -> tuple[str, ...]:
    return rows


_PATTERNS: dict[str, tuple[str, ...]] = {}


def _init_font() -> None:
    if _PATTERNS:
        return
    raw = {
        " ": "00000 " * 9,
        ".": "00000 00000 00000 00000 00000 00000 00100 00000 00000",
        ",": "00000 00000 00000 00000 00000 00000 00100 01000 00000",
        ":": "00000 00000 00100 00000 00000 00100 00000 00000 00000",
        ";": "00000 00000 00100 00000 00000 00100 01000 00000 00000",
        "-": "00000 00000 00000 00000 11111 00000 00000 00000 00000",
        "+": "00000 00100 00100 11111 00100 00100 00000 00000 00000",
        "=": "00000 00000 11111 00000 11111 00000 00000 00000 00000",
        "/": "00001 00010 00010 00100 00100 01000 01000 10000 00000",
        "\\": "10000 01000 01000 00100 00100 00010 00010 00001 00000",
        "#": "01010 11111 01010 11111 01010 00000 00000 00000 00000",
        "%": "11001 11010 00100 01011 10011 00000 00000 00000 00000",
        "!": "00100 00100 00100 00100 00100 00000 00100 00000 00000",
        "?": "01110 10001 00010 00100 00100 00000 00100 00000 00000",
        "'": "00100 00100 00000 00000 00000 00000 00000 00000 00000",
        '"': "01010 01010 00000 00000 00000 00000 00000 00000 00000",
        "(": "00010 00100 01000 01000 01000 00100 00010 00000 00000",
        ")": "01000 00100 00010 00010 00010 00100 01000 00000 00000",
        "[": "01110 01000 01000 01000 01000 01000 01110 00000 00000",
        "]": "01110 00010 00010 00010 00010 00010 01110 00000 00000",
        "{": "00110 01000 01000 10000 01000 01000 00110 00000 00000",
        "}": "01100 00010 00010 00001 00010 00010 01100 00000 00000",
        "<": "00010 00100 01000 10000 01000 00100 00010 00000 00000",
        ">": "01000 00100 00010 00001 00010 00100 01000 00000 00000",
        "_": "00000 00000 00000 00000 00000 00000 00000 11111 00000",
        "*": "00000 01010 00100 11111 00100 01010 00000 00000 00000",
        "^": "00100 01010 10001 00000 00000 00000 00000 00000 00000",
        "~": "00000 00000 01000 10101 00010 00000 00000 00000 00000",
        "&": "01100 10010 10100 01000 10101 10010 01101 00000 00000",
        "@": "01110 10001 10111 10101 10111 10000 01110 00000 00000",
        "£": "00110 01000 11110 01000 01000 11111 00000 00000 00000",
        "E": "11111 10000 10000 11110 10000 10000 11111 00000 00000",
        "R": "11110 10001 10001 11110 10100 10010 10001 00000 00000",
        "T": "11111 00100 00100 00100 00100 00100 00100 00000 00000",
        "D": "11110 10001 10001 10001 10001 10001 11110 00000 00000",
        "F": "11111 10000 10000 11110 10000 10000 10000 00000 00000",
        "I": "11111 00100 00100 00100 00100 00100 11111 00000 00000",
        "B": "11110 10001 10001 11110 10001 10001 11110 00000 00000",
        "U": "10001 10001 10001 10001 10001 10001 01110 00000 00000",
        "o": "00000 00000 01110 10001 10001 10001 01110 00000 00000",
        "h": "10000 10000 10110 11001 10001 10001 10001 00000 00000",
        "0": "01110 10001 10011 10101 11001 10001 01110 00000 00000",
        "1": "00100 01100 00100 00100 00100 00100 01110 00000 00000",
        "2": "01110 10001 00001 00010 00100 01000 11111 00000 00000",
        "3": "01110 10001 00001 00110 00001 10001 01110 00000 00000",
        "4": "00010 00110 01010 10010 11111 00010 00010 00000 00000",
        "5": "11111 10000 11110 00001 00001 10001 01110 00000 00000",
        "6": "01110 10000 11110 10001 10001 10001 01110 00000 00000",
        "7": "11111 00001 00010 00100 01000 01000 01000 00000 00000",
        "8": "01110 10001 10001 01110 10001 10001 01110 00000 00000",
        "9": "01110 10001 10001 01111 00001 00001 01110 00000 00000",
    }
    letters = {
        "A": "01110 10001 10001 11111 10001 10001 10001",
        "C": "01110 10001 10000 10000 10000 10001 01110",
        "G": "01110 10001 10000 10111 10001 10001 01110",
        "H": "10001 10001 10001 11111 10001 10001 10001",
        "J": "00111 00010 00010 00010 00010 10010 01100",
        "K": "10001 10010 10100 11000 10100 10010 10001",
        "L": "10000 10000 10000 10000 10000 10000 11111",
        "M": "10001 11011 10101 10101 10001 10001 10001",
        "N": "10001 11001 10101 10011 10001 10001 10001",
        "O": "01110 10001 10001 10001 10001 10001 01110",
        "P": "11110 10001 10001 11110 10000 10000 10000",
        "Q": "01110 10001 10001 10001 10101 10010 01101",
        "S": "01111 10000 10000 01110 00001 00001 11110",
        "V": "10001 10001 10001 10001 10001 01010 00100",
        "W": "10001 10001 10001 10101 10101 10101 01010",
        "X": "10001 01010 00100 00100 00100 01010 10001",
        "Y": "10001 10001 01010 00100 00100 00100 00100",
        "Z": "11111 00001 00010 00100 01000 10000 11111",
        "a": "00000 00000 01110 00001 01111 10001 01111",
        "b": "10000 10000 11110 10001 10001 10001 11110",
        "c": "00000 00000 01110 10000 10000 10001 01110",
        "d": "00001 00001 01111 10001 10001 10001 01111",
        "e": "00000 00000 01110 10001 11111 10000 01110",
        "f": "00110 01000 11100 01000 01000 01000 01000",
        "g": "00000 00000 01111 10001 01111 00001 01110",
        "i": "00100 00000 01100 00100 00100 00100 01110",
        "j": "00010 00000 00110 00010 00010 10010 01100",
        "k": "10000 10000 10010 10100 11000 10100 10010",
        "l": "01100 00100 00100 00100 00100 00100 01110",
        "m": "00000 00000 11010 10101 10101 10101 10101",
        "n": "00000 00000 10110 11001 10001 10001 10001",
        "p": "00000 00000 11110 10001 11110 10000 10000",
        "q": "00000 00000 01111 10001 01111 00001 00001",
        "r": "00000 00000 10110 11000 10000 10000 10000",
        "s": "00000 00000 01111 10000 01110 00001 11110",
        "t": "01000 01000 11100 01000 01000 01001 00110",
        "u": "00000 00000 10001 10001 10001 10011 01101",
        "v": "00000 00000 10001 10001 10001 01010 00100",
        "w": "00000 00000 10001 10101 10101 10101 01010",
        "x": "00000 00000 10001 01010 00100 01010 10001",
        "y": "00000 00000 10001 10001 01111 00001 01110",
        "z": "00000 00000 11111 00010 00100 01000 11111",
    }
    for ch, blob in {**raw, **{k: v for k, v in letters.items()}}.items():
        rows = blob.split()
        # pad to 9
        while len(rows) < 9:
            rows.append("00000")
        _PATTERNS[ch] = tuple(rows[:9])
    for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if d not in _PATTERNS and d in letters:
            pass


def color_for(ch: str) -> tuple[int, int, int]:
    return {
        "E": ENT,
        "#": PATH,
        ";": (160, 160, 70),
        "%": (180, 120, 50),
        "R": RIDE,
        "$": STALL,
        "T": (180, 180, 220),
        "D": (80, 180, 220),
        "F": (220, 140, 70),
        "I": (200, 200, 120),
        "+": (220, 80, 80),
        "^": (40, 120, 50),
        "~": (40, 90, 160),
        ".": (50, 90, 40),
        ",": (40, 50, 40),
        "o": (90, 90, 90),
        "*": (70, 140, 70),
        "h": (140, 100, 60),
        "!": (240, 220, 80),
        "£": HUD,
        "B": (180, 80, 180),
        "U": (100, 160, 220),
    }.get(ch, FG)


def render_frame(text: str, w: int, h: int) -> bytes:
    _init_font()
    px = bytearray(bytes(BG) * (w * h))
    lines = text.splitlines()[: ROWS - 1]
    for y, line in enumerate(lines):
        for x, ch in enumerate(line[:COLS]):
            _put_char(px, w, h, x, y, ch, color_for(ch) if y > 24 else FG if y > 0 else HUD)
    header = "OpenRCT2 agent replay (text-only agent; this frame is for humans)"
    for x, ch in enumerate(header[:COLS]):
        _put_char(px, w, h, x, 0, ch, HUD)
    return bytes(px)


def write_ppm(path: Path, w: int, h: int, data: bytes) -> None:
    with path.open("wb") as f:
        f.write(f"P6\n{w} {h}\n255\n".encode("ascii"))
        f.write(data)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("replay", help="replay JSON from play_and_record.py")
    p.add_argument("--out-dir", default="logs/replay_render")
    p.add_argument("--mp4", default="logs/agent_play.mp4")
    p.add_argument("--transcript", default="logs/agent_play_transcript.txt")
    p.add_argument("--fps", type=int, default=4)
    args = p.parse_args()
    with open(args.replay, encoding="utf-8") as f:
        blob = json.load(f)
    frames = blob.get("frames") or []
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = COLS * FONT_W, ROWS * FONT_H
    transcript = []
    transcript.append(f"# Replay scenario={blob.get('scenario')} seed={blob.get('seed')} result={blob.get('result')}\n")
    transcript.append(f"# reason={blob.get('reason')} steps={blob.get('steps')}\n\n")
    if not frames:
        # Still write the final text.
        transcript.append(blob.get("final_text") or "(no frames)")
        Path(args.transcript).write_text("".join(transcript), encoding="utf-8")
        print("no frames; wrote transcript only")
        return
    ppm_dir = Path(tempfile.mkdtemp(prefix="rct-frames-"))
    try:
        for i, fr in enumerate(frames):
            text = fr.get("text") or ""
            transcript.append(f"\n\n===== step {fr.get('step')} action={fr.get('action')} ok={fr.get('ok')} =====\n")
            if fr.get("error"):
                transcript.append("ERROR: " + str(fr["error"]) + "\n")
            transcript.append(text)
            data = render_frame(text, w, h)
            write_ppm(ppm_dir / f"frame_{i:05d}.ppm", w, h, data)
            if i == 0 or i == len(frames) - 1 or i % 8 == 0:
                write_ppm(out_dir / f"frame_{i:05d}.ppm", w, h, data)
        Path(args.transcript).write_text("".join(transcript), encoding="utf-8")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            print("ffmpeg not found; transcript written to", args.transcript)
            return
        cmd = [
            ffmpeg,
            "-y",
            "-framerate",
            str(args.fps),
            "-i",
            str(ppm_dir / "frame_%05d.ppm"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            args.mp4,
        ]
        subprocess.check_call(cmd)
        print("wrote", args.mp4, "and", args.transcript)
    finally:
        shutil.rmtree(ppm_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
