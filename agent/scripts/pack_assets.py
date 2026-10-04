#!/usr/bin/env python3
"""Pack generated park art into game-sized PNG sprites.

Source images live in /opt/cursor/artifacts/assets (or agent/assets/source).
Output is agent/assets/sprites — original pixel-art, not RCT2 data files.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SPRITE_DIR = ROOT / "assets" / "sprites"
SOURCE_CANDIDATES = [
    Path("/opt/cursor/artifacts/assets"),
    ROOT / "assets" / "source",
]


def _src_dir() -> Path:
    for p in SOURCE_CANDIDATES:
        if p.is_dir() and any(p.glob("*.jpg")):
            return p
    raise FileNotFoundError("No generated source art found")


def _open_any(src: Path, stem: str) -> Image.Image:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = src / f"{stem}{ext}"
        if p.exists():
            return Image.open(p).convert("RGBA")
    raise FileNotFoundError(stem)


def _crop_tile(im: Image.Image, size: int = 64) -> Image.Image:
    w, h = im.size
    # Take a repeating-looking patch from the centre-left so edges aren't framed.
    x = min(32, max(0, w // 8))
    y = min(32, max(0, h // 8))
    patch = im.crop((x, y, x + min(size * 4, w - x), y + min(size * 4, h - y)))
    return patch.resize((size, size), Image.Resampling.NEAREST)


def _key_light(im: Image.Image, thresh: int = 228) -> Image.Image:
    """Drop near-white / mint checkerboard so sprites sit on grass."""
    px = im.copy()
    pixels = list(px.getdata())
    out = []
    for r, g, b, a in pixels:
        if r >= thresh and g >= thresh and b >= thresh:
            out.append((r, g, b, 0))
        elif r > 200 and g > 210 and b > 190 and abs(r - g) < 40:
            out.append((r, g, b, 0))
        else:
            out.append((r, g, b, a))
    px.putdata(out)
    return px


def _key_dark(im: Image.Image, thresh: int = 28) -> Image.Image:
    px = im.copy()
    pixels = list(px.getdata())
    out = []
    for r, g, b, a in pixels:
        if r <= thresh and g <= thresh and b <= thresh:
            out.append((r, g, b, 0))
        else:
            out.append((r, g, b, a))
    px.putdata(out)
    return px


def _square_fit(im: Image.Image, size: int, key: bool | str = False) -> Image.Image:
    if key == "light" or key is True:
        im = _key_light(im)
    elif key == "dark":
        im = _key_dark(im)
    bbox = im.split()[-1].point(lambda p: 255 if p > 8 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    return im


def pack() -> Path:
    src = _src_dir()
    SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    tiles = {
        "grass": ("tile_grass", 64, False, True),
        "path": ("tile_path", 64, False, True),
        "water": ("tile_water", 64, False, True),
        "tree": ("tile_tree", 64, "dark", False),
        "entrance": ("tile_entrance", 96, "light", False),
        "guest": ("sprite_guest", 48, "light", False),
    }
    rides = {
        "merry_go_round": "ride_merry_go_round",
        "ferris_wheel": "ride_ferris_wheel",
        "spiral_slide": "ride_spiral_slide",
        "haunted_house": "ride_haunted_house",
        "car_ride": "ride_car_ride",
        "observation_tower": "ride_observation_tower",
        "twist": "ride_twist",
    }
    stalls = {
        "toilets": "stall_toilets",
        "drinks_stall": "stall_drinks",
        "burger_bar": "stall_burger",
        "ice_cream": "stall_ice_cream",
        "information_kiosk": "stall_info",
        "umbrella_stall": "stall_umbrella",
    }
    for name, (stem, size, key, is_tile) in tiles.items():
        im = _open_any(src, stem)
        if is_tile:
            out = _crop_tile(im, size)
        else:
            out = _square_fit(im, size, key=key)
        out.save(SPRITE_DIR / f"{name}.png")
    for spec, stem in rides.items():
        try:
            im = _open_any(src, stem)
        except FileNotFoundError:
            continue
        _square_fit(im, 160, key=False).save(SPRITE_DIR / f"ride_{spec}.png")
    for spec, stem in stalls.items():
        try:
            im = _open_any(src, stem)
        except FileNotFoundError:
            continue
        _square_fit(im, 80, key=False).save(SPRITE_DIR / f"stall_{spec}.png")
    # Keep a tiny source copy so the packer can be re-run from the repo.
    sourced = ROOT / "assets" / "source"
    if src.resolve() != sourced.resolve():
        sourced.mkdir(parents=True, exist_ok=True)
        for p in src.glob("*.jpg"):
            dest = sourced / p.name
            if not dest.exists():
                shutil.copy2(p, dest)
    print("packed sprites into", SPRITE_DIR)
    return SPRITE_DIR


if __name__ == "__main__":
    pack()
