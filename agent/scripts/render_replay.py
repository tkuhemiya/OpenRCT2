#!/usr/bin/env python3
"""Render a replay JSON to an ASCII transcript and an MP4 (ffmpeg + PNG frames).

Uses a system monospace TTF via Pillow when available so the HUD is actually
readable. Falls back to a tiny stroke font if Pillow/fonts are missing.
The agent loop itself never sees these frames.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import textwrap
from io import BytesIO
from pathlib import Path


FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"),
    Path("/usr/share/fonts/truetype/macos/JetBrainsMono-Regular.ttf"),
]

FONT_SIZE = 13
WRAP = 118
PAD_X = 16
PAD_Y = 10
BG = (12, 18, 14)
FG = (220, 230, 210)
HUD = (240, 210, 90)
HEADER = (180, 220, 160)
PATH = (90, 160, 90)
RIDE = (200, 80, 70)
STALL = (80, 140, 210)
ENT = (250, 220, 80)
MUTED = (140, 150, 130)


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


def _find_font_path() -> Path | None:
    for p in FONT_CANDIDATES:
        if p.is_file():
            return p
    return None


def _load_pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    path = _find_font_path()
    if path is None:
        return None
    font = ImageFont.truetype(str(path), FONT_SIZE)
    probe = "M"
    bbox = font.getbbox(probe)
    cell_w = max(6, bbox[2] - bbox[0])
    ascent, descent = font.getmetrics()
    cell_h = max(12, ascent + descent + 1)
    return {
        "Image": Image,
        "ImageDraw": ImageDraw,
        "font": font,
        "cell_w": cell_w,
        "cell_h": cell_h,
        "path": path,
    }


def wrap_hud(text: str, width: int = WRAP) -> list[str]:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        if not raw:
            lines.append("")
            continue
        if len(raw) <= width:
            lines.append(raw)
            continue
        # Keep map rows intact (they start with two spaces + a y index).
        if raw[:2] == "  " and len(raw) >= 4 and raw[2].isdigit():
            lines.append(raw)
            continue
        indent = "  " if raw.startswith("  ") else ""
        wrapped = textwrap.wrap(
            raw.strip() if indent else raw,
            width=width - len(indent),
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        lines.extend(indent + w for w in wrapped)
    return lines


def _in_map_block(lines: list[str], idx: int) -> bool:
    # Colour glyphs from the "Map WxH" header through the last map row.
    map_at = None
    end_at = None
    for i, line in enumerate(lines):
        if line.startswith("Map ") and "x" in line:
            map_at = i
        elif map_at is not None and line.startswith("Walkable"):
            end_at = i
            break
    if map_at is None:
        return False
    if end_at is None:
        end_at = len(lines)
    return map_at + 3 <= idx < end_at  # skip Map/Legend/ruler headers


def render_frame_pil(pil: dict, header: str, lines: list[str], cols: int, rows: int) -> bytes:
    Image = pil["Image"]
    ImageDraw = pil["ImageDraw"]
    font = pil["font"]
    cw, ch = pil["cell_w"], pil["cell_h"]
    w = PAD_X * 2 + cols * cw
    h = PAD_Y * 2 + rows * ch
    # h264 wants even dimensions
    w += w % 2
    h += h % 2
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    y = PAD_Y
    draw.text((PAD_X, y), header[:cols], font=font, fill=HEADER)
    y += ch
    for i, line in enumerate(lines[: rows - 1]):
        x = PAD_X
        clipped = line[:cols]
        if _in_map_block(lines, i):
            for chs in clipped:
                draw.text((x, y), chs, font=font, fill=color_for(chs))
                x += cw
        else:
            fill = HUD if i == 0 or clipped.startswith("Status: SUCCESS") else FG
            if clipped.startswith("WARN:"):
                fill = (240, 160, 80)
            elif clipped.startswith("TIP:"):
                fill = MUTED
            draw.text((x, y), clipped, font=font, fill=fill)
        y += ch
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --- bitmap fallback (no Pillow / no TTF) ---------------------------------


FONT_W = 8
FONT_H = 14
COLS_BM = 92
ROWS_BM = 72  # tall enough for HUD + 18x16 map on a winning park
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
        "B": "11110 10001 10001 11110 10001 10001 11110",
        "C": "01110 10001 10000 10000 10000 10001 01110",
        "D": "11110 10001 10001 10001 10001 10001 11110",
        "E": "11111 10000 10000 11110 10000 10000 11111",
        "F": "11111 10000 10000 11110 10000 10000 10000",
        "G": "01110 10001 10000 10111 10001 10001 01110",
        "H": "10001 10001 10001 11111 10001 10001 10001",
        "I": "11111 00100 00100 00100 00100 00100 11111",
        "J": "00111 00010 00010 00010 00010 10010 01100",
        "K": "10001 10010 10100 11000 10100 10010 10001",
        "L": "10000 10000 10000 10000 10000 10000 11111",
        "M": "10001 11011 10101 10101 10001 10001 10001",
        "N": "10001 11001 10101 10011 10001 10001 10001",
        "O": "01110 10001 10001 10001 10001 10001 01110",
        "P": "11110 10001 10001 11110 10000 10000 10000",
        "Q": "01110 10001 10001 10001 10101 10010 01101",
        "R": "11110 10001 10001 11110 10100 10010 10001",
        "S": "01111 10000 10000 01110 00001 00001 11110",
        "T": "11111 00100 00100 00100 00100 00100 00100",
        "U": "10001 10001 10001 10001 10001 10001 01110",
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
        "h": "10000 10000 10110 11001 10001 10001 10001",
        "i": "00100 00000 01100 00100 00100 00100 01110",
        "j": "00010 00000 00110 00010 00010 10010 01100",
        "k": "10000 10000 10010 10100 11000 10100 10010",
        "l": "01100 00100 00100 00100 00100 00100 01110",
        "m": "00000 00000 11010 10101 10101 10101 10101",
        "n": "00000 00000 10110 11001 10001 10001 10001",
        "o": "00000 00000 01110 10001 10001 10001 01110",
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
    for ch, blob in {**raw, **letters}.items():
        rows = blob.split()
        while len(rows) < 9:
            rows.append("00000")
        _PATTERNS[ch] = tuple(rows[:9])


def _dot(px: bytearray, w: int, h: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < w and 0 <= y < h:
        i = (y * w + x) * 3
        px[i : i + 3] = bytes(color)


def _put_char(px: bytearray, w: int, h: int, cx: int, cy: int, ch: str, color: tuple[int, int, int]) -> None:
    patterns = _PATTERNS.get(ch) or _PATTERNS.get(ch.lower()) or _PATTERNS.get(ch.upper())
    ox, oy = cx * FONT_W, cy * FONT_H
    if patterns is None:
        _dot(px, w, h, ox + 3, oy + 6, color)
        return
    for row, bits in enumerate(patterns):
        for col, bit in enumerate(bits):
            if bit == "1":
                _dot(px, w, h, ox + col + 1, oy + row + 2, color)


def render_frame_bitmap(text: str, header: str, w: int, h: int, cols: int, rows: int) -> bytes:
    _init_font()
    px = bytearray(bytes(BG) * (w * h))
    lines = wrap_hud(text)[: rows - 1]
    for x, ch in enumerate(header[:cols]):
        _put_char(px, w, h, x, 0, ch, HEADER)
    for y, line in enumerate(lines):
        row = y + 1
        for x, ch in enumerate(line[:cols]):
            col = color_for(ch) if _in_map_block(lines, y) else (HUD if y == 0 else FG)
            _put_char(px, w, h, x, row, ch, col)
    return bytes(px)


def write_ppm(path: Path, w: int, h: int, data: bytes) -> None:
    with path.open("wb") as f:
        f.write(f"P6\n{w} {h}\n255\n".encode("ascii"))
        f.write(data)


def _header(blob: dict, fr: dict, idx: int, n: int) -> str:
    action = fr.get("action") or ""
    result = blob.get("result") or ""
    guests = fr.get("guests")
    rating = fr.get("rating")
    extra = ""
    if guests is not None:
        extra = f"  guests={guests} rating={rating}"
    return (
        f"OpenRCT2 agent replay  {idx + 1}/{n}  {blob.get('scenario')} seed={blob.get('seed')}  "
        f"{action}  {result}{extra}   (text-only agent; this frame is for humans)"
    )


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
    transcript = [
        f"# Replay scenario={blob.get('scenario')} seed={blob.get('seed')} result={blob.get('result')}\n",
        f"# reason={blob.get('reason')} steps={blob.get('steps')}\n\n",
    ]
    if not frames:
        transcript.append(blob.get("final_text") or "(no frames)")
        Path(args.transcript).parent.mkdir(parents=True, exist_ok=True)
        Path(args.transcript).write_text("".join(transcript), encoding="utf-8")
        print("no frames; wrote transcript only")
        return

    pil = _load_pil()
    wrapped_frames = [wrap_hud(fr.get("text") or "") for fr in frames]
    cols = min(WRAP, max((len(line) for lines in wrapped_frames for line in lines), default=80))
    cols = max(cols, 80)
    rows = max((len(lines) for lines in wrapped_frames), default=24) + 2  # + header

    png_dir = Path(tempfile.mkdtemp(prefix="rct-frames-"))
    try:
        for i, fr in enumerate(frames):
            text = fr.get("text") or ""
            transcript.append(
                f"\n\n===== step {fr.get('step')} action={fr.get('action')} ok={fr.get('ok')} =====\n"
            )
            if fr.get("error"):
                transcript.append("ERROR: " + str(fr["error"]) + "\n")
            transcript.append(text)
            header = _header(blob, fr, i, len(frames))
            if pil:
                png = render_frame_pil(pil, header, wrapped_frames[i], cols, rows)
                (png_dir / f"frame_{i:05d}.png").write_bytes(png)
                if i == 0 or i == len(frames) - 1 or i % 8 == 0:
                    (out_dir / f"frame_{i:05d}.png").write_bytes(png)
            else:
                w, h = COLS_BM * FONT_W, ROWS_BM * FONT_H
                w += w % 2
                h += h % 2
                data = render_frame_bitmap(text, header, w, h, COLS_BM, ROWS_BM)
                write_ppm(png_dir / f"frame_{i:05d}.ppm", w, h, data)
                if i == 0 or i == len(frames) - 1 or i % 8 == 0:
                    write_ppm(out_dir / f"frame_{i:05d}.ppm", w, h, data)

        Path(args.transcript).parent.mkdir(parents=True, exist_ok=True)
        Path(args.transcript).write_text("".join(transcript), encoding="utf-8")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            print("ffmpeg not found; transcript written to", args.transcript)
            return
        glob = "frame_%05d.png" if pil else "frame_%05d.ppm"
        Path(args.mp4).parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg,
            "-y",
            "-framerate",
            str(args.fps),
            "-i",
            str(png_dir / glob),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            args.mp4,
        ]
        subprocess.check_call(cmd)
        mode = f"PIL {pil['path'].name}" if pil else "bitmap fallback"
        print("wrote", args.mp4, "and", args.transcript, f"({mode}, {cols}x{rows} cells)")
    finally:
        shutil.rmtree(png_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
