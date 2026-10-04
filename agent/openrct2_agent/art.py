"""Programmatic RCT-style isometric pixel art.

Every tile, ride, stall, tree, and peep is drawn with ImageDraw. Adding a
catalog entry does not require a new PNG — painters key off spec id / category.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .catalog import RIDES, STALLS
from .engine import GameState, RideInstance, StallInstance, money_str


TW = 64
TH = 32
HUD = 78
PAD = 28

Color = tuple[int, int, int]

# Chris Sawyer–ish greens, tans, and saturated ride primaries.
GRASS_A = (86, 172, 54)
GRASS_B = (68, 148, 40)
GRASS_EDGE = (48, 112, 28)
UNOWNED_A = (46, 92, 38)
UNOWNED_B = (36, 74, 30)
PATH_A = (198, 160, 98)
PATH_B = (172, 132, 74)
PATH_EDGE = (128, 92, 48)
WATER_A = (42, 154, 186)
WATER_B = (28, 118, 156)
WATER_EDGE = (18, 78, 118)
WOOD = (42, 28, 16)
GOLD = (236, 200, 72)
CREAM = (244, 232, 208)
INK = (28, 18, 10)
STEEL = (156, 164, 176)
STEEL_D = (96, 104, 118)

CAT_FACE = {
    "gentle": ((206, 72, 68), (156, 44, 48), (232, 128, 96)),
    "thrill": ((96, 72, 176), (62, 42, 132), (156, 124, 214)),
    "water": ((48, 132, 196), (28, 88, 150), (96, 196, 226)),
    "transport": ((72, 140, 72), (44, 96, 48), (148, 188, 96)),
    "rollercoaster": ((210, 158, 48), (150, 96, 28), (236, 206, 92)),
    "shop": ((204, 84, 58), (148, 52, 36), (232, 148, 86)),
}

STALL_FACE = {
    "food": ((214, 86, 54), (160, 48, 32), (240, 196, 92)),
    "drink": ((54, 110, 196), (32, 70, 148), (140, 196, 236)),
    "souvenir": ((196, 72, 160), (140, 40, 112), (236, 160, 196)),
    "facility": ((186, 168, 132), (132, 112, 84), (228, 216, 176)),
}

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
]


def font(size: int) -> ImageFont.ImageFont:
    for p in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def shade(c: Color, f: float) -> Color:
    return tuple(max(0, min(255, int(ch * f))) for ch in c)  # type: ignore[return-value]


def mix(a: Color, b: Color, t: float) -> Color:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


@dataclass
class IsoLayout:
    tw: int = TW
    th: int = TH
    ox: int = 0
    oy: int = 0
    hud: int = HUD
    width: int = 0
    height: int = 0
    map_w: int = 18
    map_h: int = 16


def layout_for(map_w: int, map_h: int, *, hud: bool = True) -> IsoLayout:
    tw, th = TW, TH
    hud_h = HUD if hud else 10
    ox = PAD + (map_h - 1) * (tw // 2) + tw // 2
    oy = hud_h + PAD + 4
    width = ox + (map_w - 1) * (tw // 2) + tw // 2 + PAD
    height = oy + (map_w + map_h) * (th // 2) + 48
    width += width % 2
    height += height % 2
    return IsoLayout(tw, th, ox, oy, hud_h, width, height, map_w, map_h)


def iso(x: float, y: float, lay: IsoLayout) -> tuple[int, int]:
    sx = lay.ox + (x - y) * (lay.tw / 2)
    sy = lay.oy + (x + y) * (lay.th / 2)
    return int(round(sx)), int(round(sy))


def pixel_to_tile(px: float, py: float, lay: IsoLayout) -> tuple[int, int]:
    dx = (px - lay.ox) / (lay.tw / 2)
    dy = (py - lay.oy) / (lay.th / 2)
    return math.floor((dx + dy) / 2), math.floor((dy - dx) / 2)


def diamond(tx: int, ty: int, lay: IsoLayout) -> list[tuple[int, int]]:
    top = iso(tx, ty, lay)
    tw2, th2 = lay.tw // 2, lay.th // 2
    return [
        top,
        (top[0] + tw2, top[1] + th2),
        (top[0], top[1] + lay.th),
        (top[0] - tw2, top[1] + th2),
    ]


def footprint_corners(tx: int, ty: int, bw: int, bh: int, lay: IsoLayout) -> tuple[tuple[int, int], ...]:
    n = iso(tx, ty, lay)
    e = (iso(tx + bw - 1, ty, lay)[0] + lay.tw // 2, iso(tx + bw - 1, ty, lay)[1] + lay.th // 2)
    s = (iso(tx + bw - 1, ty + bh - 1, lay)[0], iso(tx + bw - 1, ty + bh - 1, lay)[1] + lay.th)
    w = (iso(tx, ty + bh - 1, lay)[0] - lay.tw // 2, iso(tx, ty + bh - 1, lay)[1] + lay.th // 2)
    return n, e, s, w


def _up(pts: tuple[tuple[int, int], ...], h: int) -> tuple[tuple[int, int], ...]:
    return tuple((p[0], p[1] - h) for p in pts)


def draw_box(
    draw: ImageDraw.ImageDraw,
    corners: tuple[tuple[int, int], ...],
    height: int,
    left: Color,
    right: Color,
    top: Color,
    outline: Color = (42, 26, 12),
) -> tuple[tuple[int, int], ...]:
    n, e, s, w = corners
    nr, er, sr, wr = _up(corners, height)
    draw.polygon([w, s, sr, wr], fill=left, outline=outline)
    draw.polygon([e, s, sr, er], fill=right, outline=outline)
    draw.polygon([nr, er, sr, wr], fill=top, outline=outline)
    return nr, er, sr, wr


def paint_tile(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    kind: str,
    owned: bool,
    litter: int,
    tick: int,
    lay: IsoLayout,
) -> None:
    pts = diamond(x, y, lay)
    n, e, s, w = pts
    if kind == "water":
        a, b, edge = WATER_A, WATER_B, WATER_EDGE
        phase = (tick + x * 3 + y * 5) % 6
        fill = mix(a, b, 0.35 + 0.08 * phase)
        draw.polygon(pts, fill=fill)
        draw.line([w, s], fill=edge, width=1)
        draw.line([e, s], fill=mix(a, (255, 255, 255), 0.25), width=1)
        mx, my = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2
        draw.arc([mx - 10, my - 4 + phase, mx + 10, my + 6 + phase], 200, 340, fill=mix(a, (255, 255, 255), 0.4))
        return
    if kind in ("path", "entrance"):
        fill = PATH_A if (x + y) % 2 == 0 else PATH_B
        if litter:
            fill = shade(fill, max(0.55, 1 - 0.12 * litter))
        draw.polygon(pts, fill=fill)
        draw.line([w, s], fill=PATH_EDGE, width=1)
        draw.line([e, s], fill=mix(PATH_A, (255, 255, 255), 0.2), width=1)
        # grout so paths read as paving, not dirt photos
        cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2
        draw.line([(cx - 8, cy), (cx + 8, cy)], fill=shade(fill, 0.85), width=1)
        return
    if not owned:
        fill = UNOWNED_A if (x + y) % 2 == 0 else UNOWNED_B
        draw.polygon(pts, fill=fill)
        draw.line([w, s], fill=shade(fill, 0.7), width=1)
        return
    fill = GRASS_A if (x + y) % 2 == 0 else GRASS_B
    draw.polygon(pts, fill=fill)
    draw.line([n, w], fill=mix(fill, (255, 255, 255), 0.18), width=1)
    draw.line([w, s], fill=GRASS_EDGE, width=1)
    draw.line([e, s], fill=shade(GRASS_EDGE, 1.15), width=1)


def paint_tree(draw: ImageDraw.ImageDraw, x: int, y: int, lay: IsoLayout, seed: int = 0) -> None:
    top = iso(x, y, lay)
    cx, cy = top[0], top[1] + 14
    h = 10 + (seed % 5)
    draw.rectangle([cx - 2, cy, cx + 2, cy + 12], fill=(96, 62, 28), outline=(60, 36, 14))
    for i, (dx, dy, r, col) in enumerate(
        (
            (0, -h, 11, (46, 140, 42)),
            (-6, -h + 4, 8, (36, 118, 34)),
            (6, -h + 5, 8, (70, 168, 52)),
            (0, -h - 4, 7, (88, 186, 64)),
        )
    ):
        draw.ellipse([cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r], fill=col, outline=(24, 80, 22))


def paint_scenery(draw: ImageDraw.ImageDraw, x: int, y: int, scenery_id: str, lay: IsoLayout) -> None:
    top = iso(x, y, lay)
    cx, cy = top[0], top[1] + 16
    if scenery_id == "tree":
        paint_tree(draw, x, y, lay, x * 13 + y)
        return
    if scenery_id == "garden":
        for i, col in enumerate(((196, 64, 90), (236, 196, 64), (64, 140, 196), (236, 120, 48))):
            dx = (-6, 6, -2, 4)[i]
            dy = (2, 0, -4, 4)[i]
            draw.ellipse([cx + dx - 3, cy + dy - 3, cx + dx + 3, cy + dy + 3], fill=col)
        return
    if scenery_id == "bench":
        draw.rectangle([cx - 10, cy + 2, cx + 10, cy + 8], fill=(132, 86, 40), outline=INK)
        draw.rectangle([cx - 10, cy - 2, cx + 10, cy + 2], fill=(168, 118, 62))
        return
    if scenery_id == "lamp":
        draw.rectangle([cx - 1, cy - 10, cx + 1, cy + 10], fill=(70, 70, 78))
        draw.ellipse([cx - 5, cy - 16, cx + 5, cy - 6], fill=(255, 220, 90), outline=(180, 140, 40))
        return
    if scenery_id == "bin":
        draw.rectangle([cx - 5, cy, cx + 5, cy + 10], fill=(70, 86, 70), outline=INK)
        draw.rectangle([cx - 6, cy - 2, cx + 6, cy + 1], fill=(40, 48, 40))
        return
    paint_tree(draw, x, y, lay, 1)


def paint_entrance(draw: ImageDraw.ImageDraw, x: int, y: int, lay: IsoLayout, open_park: bool) -> None:
    corners = footprint_corners(x, y, 1, 1, lay)
    roof = draw_box(draw, corners, 16, (196, 48, 48), (148, 28, 28), (236, 196, 64))
    nr, er, sr, wr = roof
    peak = ((nr[0] + er[0]) // 2, nr[1] - 10)
    draw.polygon([nr, er, peak], fill=(220, 40, 40), outline=INK)
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2 - 8
    draw.rectangle([cx - 5, cy - 2, cx + 5, cy + 8], fill=(40, 28, 16) if not open_park else (40, 120, 48))
    draw.rectangle([cx - 12, cy + 8, cx - 8, cy + 16], fill=GOLD)
    draw.rectangle([cx + 8, cy + 8, cx + 12, cy + 16], fill=GOLD)


def _faces(cat: str, closed: bool) -> tuple[Color, Color, Color]:
    left, right, top = CAT_FACE.get(cat, CAT_FACE["gentle"])
    if closed:
        return shade(left, 0.55), shade(right, 0.55), shade(top, 0.65)
    return left, right, top


def _height(spec_id: str, category: str, bw: int, bh: int) -> int:
    special = {
        "observation_tower": 84,
        "ferris_wheel": 18,
        "spiral_slide": 46,
        "haunted_house": 28,
        "circus": 22,
        "crooked_house": 24,
        "gravitron": 36,
        "enterprise": 32,
        "top_spin": 30,
        "swinging_ship": 20,
    }
    if spec_id in special:
        return special[spec_id]
    if category == "rollercoaster":
        return 16 + min(22, bw * 3)
    if category == "water":
        return 12
    return 12 + min(22, (bw + bh) * 3)


def paint_generic_ride(
    draw: ImageDraw.ImageDraw,
    ride: RideInstance,
    lay: IsoLayout,
    tick: int,
    closed: bool,
) -> None:
    spec = ride.spec
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    h = _height(spec.id, spec.category, ride.w, ride.h)
    left, right, top = _faces(spec.category, closed)
    roof = draw_box(draw, corners, h, left, right, top)
    n, e, s, w = corners
    cx = (n[0] + s[0]) // 2
    cy = (roof[0][1] + roof[2][1]) // 2
    # little flag so every building reads as a named ride
    draw.rectangle([cx, roof[0][1] - 12, cx + 1, roof[0][1]], fill=(240, 240, 240))
    draw.polygon([(cx + 1, roof[0][1] - 12), (cx + 8, roof[0][1] - 8), (cx + 1, roof[0][1] - 4)], fill=(220, 40, 40))
    _ = (tick, cy)


def paint_ferris(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    left, right, top = _faces("gentle", closed)
    draw_box(draw, corners, 10, STEEL_D, shade(STEEL_D, 0.8), STEEL)
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2 - 40
    rx, ry = 30, 18
    col = shade(STEEL, 0.7) if closed else STEEL
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=col, width=3)
    draw.ellipse([cx - 4, cy - 3, cx + 4, cy + 3], fill=(200, 48, 48))
    draw.line([(cx, cy), (s[0], s[1] - 8)], fill=col, width=2)
    draw.line([(cx, cy), ((n[0] + w[0]) // 2, s[1] - 6)], fill=col, width=2)
    gondolas = ((220, 48, 48), (48, 96, 220), (48, 176, 64), (236, 196, 48), (196, 64, 180), (40, 40, 48))
    for i in range(8):
        ang = math.radians(tick * 6 + i * 45)
        gx = cx + int(math.cos(ang) * (rx - 2))
        gy = cy + int(math.sin(ang) * (ry - 2))
        gcol = shade(gondolas[i % len(gondolas)], 0.5) if closed else gondolas[i % len(gondolas)]
        draw.rectangle([gx - 3, gy, gx + 3, gy + 6], fill=gcol, outline=INK)


def paint_mgr(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2 - 6
    deck = shade((168, 112, 56), 0.6) if closed else (168, 112, 56)
    draw.ellipse([cx - 26, cy - 10, cx + 26, cy + 14], fill=deck, outline=INK)
    red, gold = ((196, 40, 40), (228, 188, 56))
    if closed:
        red, gold = shade(red, 0.55), shade(gold, 0.55)
    for i in range(12):
        ang0 = math.radians(tick * 8 + i * 30)
        ang1 = math.radians(tick * 8 + (i + 1) * 30)
        p0 = (cx + int(math.cos(ang0) * 24), cy - 18 + int(math.sin(ang0) * 9))
        p1 = (cx + int(math.cos(ang1) * 24), cy - 18 + int(math.sin(ang1) * 9))
        draw.polygon([(cx, cy - 20), p0, p1], fill=red if i % 2 == 0 else gold)
    draw.ellipse([cx - 4, cy - 24, cx + 4, cy - 16], fill=GOLD, outline=INK)
    for i in range(6):
        ang = math.radians(tick * 8 + i * 60)
        hx = cx + int(math.cos(ang) * 14)
        hy = cy + int(math.sin(ang) * 6)
        draw.ellipse([hx - 3, hy - 2, hx + 3, hy + 3], fill=(240, 240, 230), outline=(120, 80, 40))


def paint_tower(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    left, right, top = _faces("gentle", closed)
    draw_box(draw, corners, 8, STEEL_D, shade(STEEL_D, 0.85), STEEL)
    n, e, s, w = corners
    cx = (n[0] + s[0]) // 2
    base_y = s[1] - 8
    lift = 8 + (tick * 2 % 40)
    draw.rectangle([cx - 4, base_y - 78, cx + 4, base_y], fill=STEEL if not closed else shade(STEEL, 0.6), outline=INK)
    cab_y = base_y - lift - 10
    draw.ellipse([cx - 12, cab_y - 8, cx + 12, cab_y + 8], fill=left, outline=INK)
    draw.rectangle([cx - 3, cab_y - 14, cx + 3, cab_y - 8], fill=GOLD)


def paint_slide(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    left, right, top = _faces("gentle", closed)
    roof = draw_box(draw, corners, 44, (220, 180, 48), (180, 130, 28), (240, 210, 80))
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2
    col = shade((220, 48, 48), 0.5) if closed else (220, 48, 48)
    for i in range(7):
        t = i / 6
        ang = t * 4.5 * math.pi + tick * 0.05
        r = 6 + t * 16
        x = cx + int(math.cos(ang) * r)
        y = roof[0][1] + 6 + int(t * 36) + int(math.sin(ang) * 4)
        draw.ellipse([x - 3, y - 2, x + 3, y + 2], fill=col)
    _ = (left, right, top)


def paint_house(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    left, right, top = ((82, 58, 110), (54, 36, 80), (124, 96, 150))
    if closed:
        left, right, top = shade(left, 0.6), shade(right, 0.6), shade(top, 0.65)
    roof = draw_box(draw, corners, 26, left, right, top)
    nr, er, sr, wr = roof
    peak = ((nr[0] + er[0]) // 2, min(nr[1], er[1]) - 16)
    draw.polygon([nr, er, peak], fill=(40, 28, 52), outline=INK)
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2 - 18
    glow = (255, 210, 80) if (tick // 4) % 2 == 0 else (180, 80, 40)
    draw.rectangle([cx - 6, cy - 4, cx - 1, cy + 4], fill=glow)
    draw.rectangle([cx + 1, cy - 4, cx + 6, cy + 4], fill=glow)


def paint_circus(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2
    for i in range(10):
        ang0 = math.radians(i * 36)
        ang1 = math.radians((i + 1) * 36)
        p0 = (cx + int(math.cos(ang0) * 34), cy + int(math.sin(ang0) * 14))
        p1 = (cx + int(math.cos(ang1) * 34), cy + int(math.sin(ang1) * 14))
        col = (220, 40, 40) if i % 2 == 0 else (240, 240, 230)
        if closed:
            col = shade(col, 0.55)
        draw.polygon([(cx, cy - 36), p0, p1], fill=col, outline=INK)
    draw.polygon([(cx, cy - 44), (cx - 3, cy - 36), (cx + 3, cy - 36)], fill=GOLD)
    _ = tick


def paint_maze(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    top = shade((48, 128, 48), 0.6) if closed else (48, 128, 48)
    draw_box(draw, corners, 10, (32, 96, 36), (24, 78, 28), top)
    n, e, s, w = corners
    for i in range(3):
        y = n[1] + 8 + i * 8
        draw.line([(w[0] + 8, y), (e[0] - 8, y + 4)], fill=(28, 90, 30), width=3)
    _ = tick


def paint_spin(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    left, right, top = _faces("thrill", closed)
    draw_box(draw, corners, 12, left, right, top)
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2 - 18
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=STEEL, outline=INK)
    arms = 3 if ride.spec_id in ("twist", "scrambler") else 4
    reach = 10 + ride.w * 6
    cars = ((220, 48, 48), (48, 120, 220), (48, 176, 72), (236, 196, 48))
    for i in range(arms):
        ang = math.radians(tick * 10 + i * (360 / arms))
        x2 = cx + int(math.cos(ang) * reach)
        y2 = cy + int(math.sin(ang) * reach * 0.45)
        draw.line([(cx, cy), (x2, y2)], fill=STEEL, width=2)
        col = shade(cars[i % 4], 0.5) if closed else cars[i % 4]
        draw.ellipse([x2 - 5, y2 - 4, x2 + 5, y2 + 5], fill=col, outline=INK)


def paint_track_ride(
    draw: ImageDraw.ImageDraw,
    ride: RideInstance,
    lay: IsoLayout,
    tick: int,
    closed: bool,
    rail: Color,
    car: Color,
) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    asphalt = shade((72, 76, 82), 0.7) if closed else (72, 76, 82)
    roof = draw_box(draw, corners, 8, STEEL_D, shade(STEEL_D, 0.85), asphalt)
    nr, er, sr, wr = roof
    pts = [nr, er, sr, wr, nr]
    draw.line(pts, fill=shade(rail, 0.5) if closed else rail, width=3)
    t = (tick % 20) / 20
    # car travels nr -> er -> sr
    path = [nr, er, sr, wr]
    seg = int(t * 4) % 4
    local = (t * 4) % 1
    a, b = path[seg], path[(seg + 1) % 4]
    cx = int(a[0] + (b[0] - a[0]) * local)
    cy = int(a[1] + (b[1] - a[1]) * local)
    ccol = shade(car, 0.5) if closed else car
    draw.rectangle([cx - 4, cy - 3, cx + 4, cy + 3], fill=ccol, outline=INK)


def paint_coaster(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    left, right, top = _faces("rollercoaster", closed)
    draw_box(draw, corners, 10, (120, 78, 36), (90, 56, 24), (168, 124, 64))
    n, e, s, w = corners
    rail = (210, 48, 48) if "steel" in ride.spec_id or "loop" in ride.spec_id or "mini" in ride.spec_id else (196, 150, 64)
    if "inverted" in ride.spec_id or "corkscrew" in ride.spec_id:
        rail = (64, 96, 196)
    if closed:
        rail = shade(rail, 0.5)
    xs = [w[0] + 6, (w[0] + n[0]) // 2, n[0], (n[0] + e[0]) // 2, e[0] - 6]
    base = (n[1] + s[1]) // 2
    hills = [8, 28, 12, 36, 10]
    pts = [(xs[i], base - hills[i]) for i in range(5)]
    draw.line(pts, fill=rail, width=3)
    for p in pts:
        draw.line([(p[0], p[1]), (p[0], s[1] - 4)], fill=shade(left, 0.8), width=1)
    t = (tick % 16) / 16
    idx = min(3, int(t * 4))
    local = (t * 4) % 1
    a, b = pts[idx], pts[idx + 1]
    cx = int(a[0] + (b[0] - a[0]) * local)
    cy = int(a[1] + (b[1] - a[1]) * local)
    draw.rectangle([cx - 5, cy - 4, cx + 5, cy], fill=(40, 40, 48) if closed else (220, 40, 40), outline=INK)
    _ = (right, top, e)


def paint_water_ride(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    draw_box(draw, corners, 8, WATER_EDGE, shade(WATER_EDGE, 0.85), WATER_A if not closed else shade(WATER_A, 0.6))
    n, e, s, w = corners
    draw.line([w, n, e, s, w], fill=mix(WATER_A, (255, 255, 255), 0.3), width=2)
    t = (tick % 18) / 18
    cx = int(w[0] + (e[0] - w[0]) * t)
    cy = int(w[1] + (e[1] - w[1]) * t) - 6
    hull = shade((168, 112, 48), 0.6) if closed else (196, 132, 56)
    draw.polygon([(cx - 8, cy), (cx + 8, cy), (cx + 5, cy + 5), (cx - 5, cy + 5)], fill=hull, outline=INK)


def paint_ship(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    draw_box(draw, corners, 10, STEEL_D, shade(STEEL_D, 0.8), STEEL)
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2 - 16
    swing = int(math.sin(tick * 0.2) * 10)
    col = shade((140, 72, 40), 0.55) if closed else (160, 82, 44)
    draw.polygon(
        [(cx - 22 + swing, cy), (cx + 22 + swing, cy), (cx + 14 + swing, cy + 10), (cx - 14 + swing, cy + 10)],
        fill=col,
        outline=INK,
    )
    draw.line([(cx, cy - 18), (cx + swing, cy)], fill=STEEL, width=2)


def paint_cinema(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int, closed: bool) -> None:
    corners = footprint_corners(ride.x, ride.y, ride.w, ride.h, lay)
    left, right, top = _faces("thrill", closed)
    roof = draw_box(draw, corners, 22, left, right, top)
    nr, er, sr, wr = roof
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, (n[1] + s[1]) // 2 - 18
    screen = (80, 220, 255) if (tick // 3) % 2 == 0 else (40, 80, 160)
    if closed:
        screen = (40, 40, 50)
    draw.rectangle([cx - 10, cy - 8, cx + 10, cy + 6], fill=screen, outline=INK)
    _ = (er, sr, wr)


RIDE_PAINTERS = {
    "ferris_wheel": paint_ferris,
    "merry_go_round": paint_mgr,
    "observation_tower": paint_tower,
    "spiral_slide": paint_slide,
    "haunted_house": paint_house,
    "crooked_house": paint_house,
    "circus": paint_circus,
    "maze": paint_maze,
    "twist": paint_spin,
    "scrambler": paint_spin,
    "gravitron": paint_spin,
    "top_spin": paint_spin,
    "enterprise": paint_spin,
    "swinging_ship": paint_ship,
    "cinema_3d": paint_cinema,
    "motion_simulator": paint_cinema,
    "boat_hire": paint_water_ride,
    "dinghy_slide": paint_water_ride,
    "log_flume": paint_water_ride,
    "river_rapids": paint_water_ride,
}


def paint_ride(draw: ImageDraw.ImageDraw, ride: RideInstance, lay: IsoLayout, tick: int) -> None:
    closed = ride.status != "open"
    fn = RIDE_PAINTERS.get(ride.spec_id)
    if fn:
        fn(draw, ride, lay, tick, closed)
        return
    if ride.spec.category == "rollercoaster" or ride.spec.is_coaster:
        paint_coaster(draw, ride, lay, tick, closed)
        return
    if ride.spec.category in ("transport",) or ride.spec_id in ("car_ride", "ghost_train", "dodgems", "go_karts"):
        rail = (40, 40, 48) if ride.spec_id != "miniature_railway" else (120, 72, 32)
        car = (220, 48, 48) if ride.spec.category != "transport" else (48, 120, 48)
        paint_track_ride(draw, ride, lay, tick, closed, rail, car)
        return
    if ride.spec.category == "water":
        paint_water_ride(draw, ride, lay, tick, closed)
        return
    if ride.spec.category == "thrill":
        paint_spin(draw, ride, lay, tick, closed)
        return
    paint_generic_ride(draw, ride, lay, tick, closed)


def paint_stall(draw: ImageDraw.ImageDraw, stall: StallInstance, lay: IsoLayout) -> None:
    kind = stall.spec.kind
    left, right, top = STALL_FACE.get(kind, STALL_FACE["facility"])
    corners = footprint_corners(stall.x, stall.y, stall.w, stall.h, lay)
    roof = draw_box(draw, corners, 14, left, right, top)
    nr, er, sr, wr = roof
    # striped awning on the front edge
    stripe_a, stripe_b = (240, 240, 230), left
    for i in range(6):
        t0, t1 = i / 6, (i + 1) / 6
        a = (int(wr[0] + (er[0] - wr[0]) * t0), int(wr[1] + (er[1] - wr[1]) * t0))
        b = (int(wr[0] + (er[0] - wr[0]) * t1), int(wr[1] + (er[1] - wr[1]) * t1))
        drop_a = (a[0], a[1] + 7)
        drop_b = (b[0], b[1] + 7)
        draw.polygon([a, b, drop_b, drop_a], fill=stripe_a if i % 2 == 0 else stripe_b)
    n, e, s, w = corners
    cx, cy = (n[0] + s[0]) // 2, nr[1] - 2
    sid = stall.spec_id
    if sid == "burger_bar":
        draw.ellipse([cx - 5, cy - 10, cx + 5, cy - 2], fill=(196, 132, 48), outline=INK)
        draw.rectangle([cx - 5, cy - 6, cx + 5, cy - 3], fill=(48, 148, 48))
    elif sid == "drinks_stall":
        draw.rectangle([cx - 3, cy - 10, cx + 3, cy - 1], fill=(48, 96, 220), outline=INK)
        draw.polygon([(cx - 3, cy - 10), (cx + 3, cy - 10), (cx, cy - 14)], fill=(240, 80, 80))
    elif sid == "ice_cream":
        draw.polygon([(cx - 4, cy - 6), (cx + 4, cy - 6), (cx, cy - 1)], fill=(232, 180, 96), outline=INK)
        draw.ellipse([cx - 5, cy - 14, cx + 5, cy - 5], fill=(255, 160, 196))
    elif sid == "toilets":
        draw.rectangle([cx - 6, cy - 10, cx + 6, cy - 1], fill=(240, 240, 230), outline=INK)
        draw.ellipse([cx - 3, cy - 8, cx + 3, cy - 3], fill=(80, 140, 200))
    elif sid == "information_kiosk":
        draw.ellipse([cx - 6, cy - 12, cx + 6, cy], fill=(48, 96, 200), outline=INK)
        draw.text((cx - 3, cy - 11), "?", font=font(10), fill=(255, 255, 255))
    elif sid == "umbrella_stall":
        draw.polygon([(cx - 8, cy - 4), (cx + 8, cy - 4), (cx, cy - 12)], fill=(48, 120, 220), outline=INK)
        draw.rectangle([cx - 1, cy - 4, cx + 1, cy], fill=INK)
    elif sid == "first_aid":
        draw.rectangle([cx - 6, cy - 10, cx + 6, cy], fill=(240, 240, 240), outline=INK)
        draw.rectangle([cx - 2, cy - 8, cx + 2, cy - 2], fill=(200, 32, 32))
        draw.rectangle([cx - 5, cy - 6, cx + 5, cy - 4], fill=(200, 32, 32))
    elif sid == "balloon_stall":
        draw.ellipse([cx - 5, cy - 14, cx + 5, cy - 4], fill=(220, 48, 64), outline=INK)
        draw.line([(cx, cy - 4), (cx, cy)], fill=INK, width=1)
    else:
        draw.rectangle([cx - 5, cy - 8, cx + 5, cy], fill=top, outline=INK)


def paint_peep(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    lay: IsoLayout,
    gid: int,
    tick: int,
    kind: str = "guest",
) -> None:
    top = iso(x, y, lay)
    wobble = ((tick * 3 + gid * 7) % 9) - 4
    ox = ((gid * 13) % 17) - 8
    oy = 10 + ((gid * 7) % 9)
    px, py = top[0] + ox + wobble, top[1] + oy
    shirts = ((48, 120, 220), (220, 64, 64), (48, 168, 72), (236, 196, 48), (196, 72, 168), (240, 140, 48))
    if kind == "handyman":
        shirt = (48, 176, 64)
    elif kind == "mechanic":
        shirt = (48, 96, 220)
    elif kind == "entertainer":
        shirt = (220, 64, 180)
    elif kind == "security":
        shirt = (50, 50, 55)
    else:
        shirt = shirts[gid % len(shirts)]
    # RCT peeps are tiny: head + body + 2 legs
    draw.ellipse([px - 3, py - 2, px + 4, py + 5], fill=(20, 20, 12))  # shadow
    draw.rectangle([px - 2, py + 2, px + 3, py + 9], fill=shirt)
    draw.ellipse([px - 3, py - 5, px + 4, py + 3], fill=(236, 198, 156), outline=(80, 50, 30))
    hair = ((60, 40, 24), (32, 24, 16), (196, 160, 64), (200, 80, 48))[gid % 4]
    draw.rectangle([px - 3, py - 6, px + 4, py - 3], fill=hair)
    step = (tick + gid) % 4
    draw.line([(px - 1, py + 9), (px - 2 - (1 if step < 2 else 0), py + 13)], fill=(40, 30, 24), width=1)
    draw.line([(px + 2, py + 9), (px + 3 + (1 if step >= 2 else 0), py + 13)], fill=(40, 30, 24), width=1)


def paint_ghost(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    lay: IsoLayout,
    ok: bool,
) -> None:
    n, e, s, west = footprint_corners(x, y, w, h, lay)
    col = (80, 220, 80, 140) if ok else (220, 60, 60, 140)
    draw.polygon([n, e, s, west], outline=(255, 230, 80) if ok else (220, 40, 40), width=2)
    _ = col


def paint_highlight(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, lay: IsoLayout) -> None:
    n, e, s, west = footprint_corners(x, y, w, h, lay)
    draw.polygon([n, e, s, west], outline=GOLD, width=2)


def paint_hud(draw: ImageDraw.ImageDraw, state: GameState, lay: IsoLayout, caption: str) -> None:
    W, H = lay.width, lay.hud
    draw.rectangle([0, 0, W, H], fill=(58, 38, 20))
    draw.rectangle([2, 2, W - 3, H - 4], fill=(92, 62, 32))
    draw.rectangle([4, 4, W - 5, 26], fill=(228, 188, 48))
    draw.rectangle([4, 26, W - 5, H - 6], fill=(72, 48, 26))
    draw.rectangle([0, H - 3, W, H], fill=GOLD)
    title = f"{state.park_name}"
    status = "OPEN" if state.park_open else "CLOSED"
    if state.result == "success":
        status = "SUCCESS"
    elif state.result == "failure":
        status = "FAILED"
    date = f"{state.day} {state.month_name} Year {state.year}"
    draw.text((10, 6), f"{title}   —   {status}", font=font(14), fill=INK)
    line2 = (
        f"{money_str(state.cash)}    Guests {state.num_guests}    "
        f"Rating {state.rating // 100}.{state.rating % 100:02d}    "
        f"{date}    {state.weather}"
    )
    draw.text((10, 34), line2, font=font(13), fill=CREAM)
    obj = state.objective
    if obj:
        need = obj.get("num_guests") or 0
        extra = f"  Goal: {need} guests" if need else ""
        if obj.get("type") == "park_value_by":
            extra = f"  Goal: park value {money_str(int(obj.get('currency') or 0))}"
        draw.text((10, 54), extra.strip() or "Have fun", font=font(12), fill=GOLD)
    if caption:
        tw = int(draw.textlength(caption, font=font(12)))
        bx = W - tw - 28
        draw.rounded_rectangle([bx - 8, 8, W - 8, 50], radius=6, fill=(24, 16, 10))
        draw.text((bx, 20), caption[:42], font=font(12), fill=GOLD)


def paint_ticker(draw: ImageDraw.ImageDraw, state: GameState, lay: IsoLayout) -> None:
    y0 = lay.height - 22
    draw.rectangle([0, y0, lay.width, lay.height], fill=(36, 24, 14))
    news = state.news[-1].text if state.news else "Welcome to the park. Build paths, rides, and stalls, then open the gates."
    draw.text((8, y0 + 4), news[:110], font=font(12), fill=GOLD)


def ensure_all_painters_registered() -> list[str]:
    """Used by tests: every catalog ride has a drawing path (explicit or category)."""
    missing = []
    dummy_lay = layout_for(8, 8, hud=False)
    im = Image.new("RGBA", (dummy_lay.width, dummy_lay.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    for spec in RIDES.values():
        ride = RideInstance(
            id=0,
            spec_id=spec.id,
            x=1,
            y=1,
            w=spec.footprint[0],
            h=spec.footprint[1],
            rotation=0,
            status="open",
        )
        try:
            paint_ride(draw, ride, dummy_lay, 3)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{spec.id}: {exc}")
    for spec in STALLS.values():
        stall = StallInstance(id=0, spec_id=spec.id, x=1, y=1, w=spec.footprint[0], h=spec.footprint[1])
        try:
            paint_stall(draw, stall, dummy_lay)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{spec.id}: {exc}")
    return missing
