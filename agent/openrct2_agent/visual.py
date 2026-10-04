"""Top-down game view of a ParkSession using generated sprites.

This is the human-facing park camera. The agent still only sees text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from .catalog import RIDES, STALLS
from .engine import GameState, money_str


TILE = 44
HUD = 70
SPRITE_DIR = Path(__file__).resolve().parents[1] / "assets" / "sprites"

_FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf"),
    Path("/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in _FONT_CANDIDATES:
        if p.is_file():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


class VisualPark:
    def __init__(self) -> None:
        self.sprites: dict[str, Image.Image] = {}
        if SPRITE_DIR.is_dir():
            for p in SPRITE_DIR.glob("*.png"):
                self.sprites[p.stem] = Image.open(p).convert("RGBA")
        self.font = _font(16)
        self.font_sm = _font(13)
        self.font_lg = _font(20)

    def _tile(self, name: str) -> Image.Image:
        im = self.sprites.get(name)
        if im is None:
            color = {
                "grass": (62, 140, 48),
                "path": (176, 142, 78),
                "water": (40, 150, 170),
            }.get(name, (80, 80, 80))
            im = Image.new("RGBA", (TILE, TILE), color)
        return im.resize((TILE, TILE), Image.Resampling.NEAREST)

    def _stamp(self, name: str, w: int, h: int) -> Optional[Image.Image]:
        im = self.sprites.get(name)
        if im is None:
            return None
        return im.resize((w * TILE, h * TILE), Image.Resampling.LANCZOS)

    def render(
        self,
        state: GameState,
        *,
        caption: str = "",
        tick: int = 0,
        highlight: Optional[tuple[int, int, int, int]] = None,
    ) -> Image.Image:
        mw, mh = state.map_w, state.map_h
        W, H = mw * TILE, mh * TILE + HUD
        W += W % 2
        H += H % 2
        frame = Image.new("RGBA", (W, H), (18, 22, 16, 255))
        draw = ImageDraw.Draw(frame)

        grass = self._tile("grass")
        path = self._tile("path")
        water = self._tile("water")
        dark_grass = ImageEnhance.Brightness(grass).enhance(0.55)

        for y in range(mh):
            for x in range(mw):
                t = state.tile(x, y)
                px, py = x * TILE, HUD + y * TILE
                if t.kind == "water":
                    tile_im = water
                elif t.kind == "path" or t.kind == "entrance":
                    tile_im = path
                    if t.litter:
                        tile_im = ImageEnhance.Brightness(path).enhance(max(0.55, 1 - 0.12 * t.litter))
                elif not t.owned:
                    tile_im = dark_grass
                else:
                    tile_im = grass
                frame.paste(tile_im, (px, py))

        # Trees / scenery under buildings.
        tree = self.sprites.get("tree")
        if tree:
            tree_s = tree.resize((TILE, TILE), Image.Resampling.LANCZOS)
            for y in range(mh):
                for x in range(mw):
                    t = state.tile(x, y)
                    if t.tree or (t.kind == "scenery" and t.scenery_id == "tree"):
                        if t.kind in ("ride", "stall", "path", "entrance"):
                            continue
                        frame.alpha_composite(tree_s, (x * TILE, HUD + y * TILE))

        # Stalls then rides (rides are larger).
        for s in state.stalls:
            spr = self._stamp(f"stall_{s.spec_id}", s.w, s.h)
            dest = (s.x * TILE, HUD + s.y * TILE)
            if spr is None:
                self._fallback_building(frame, dest, s.w, s.h, (80, 140, 210), s.spec.name[:8])
            else:
                frame.alpha_composite(spr, dest)

        for r in state.rides:
            spr = self._stamp(f"ride_{r.spec_id}", r.w, r.h)
            dest = (r.x * TILE, HUD + r.y * TILE)
            if spr is None:
                col = (200, 80, 70) if r.status == "open" else (120, 90, 90)
                self._fallback_building(frame, dest, r.w, r.h, col, r.spec.name[:10])
            else:
                if r.status != "open":
                    spr = ImageEnhance.Color(spr).enhance(0.35)
                    spr = ImageEnhance.Brightness(spr).enhance(0.8)
                frame.alpha_composite(spr, dest)

        # Entrance overlay last so the booth sits on the path.
        ent = self.sprites.get("entrance")
        ex, ey = state.entrance
        if ent:
            eim = ent.resize((TILE + 8, TILE + 8), Image.Resampling.LANCZOS)
            frame.alpha_composite(eim, (ex * TILE - 4, HUD + ey * TILE - 8))
        else:
            draw.rectangle(
                [ex * TILE + 8, HUD + ey * TILE + 8, ex * TILE + TILE - 8, HUD + ey * TILE + TILE - 8],
                fill=(240, 200, 40),
            )

        if highlight:
            hx, hy, hw, hh = highlight
            x0, y0 = hx * TILE, HUD + hy * TILE
            draw.rectangle([x0, y0, x0 + hw * TILE - 1, y0 + hh * TILE - 1], outline=(255, 230, 80), width=2)

        self._draw_people(frame, state, tick)

        # HUD
        draw.rectangle([0, 0, W, HUD], fill=(42, 28, 18))
        draw.rectangle([0, HUD - 3, W, HUD], fill=(210, 170, 70))
        park = state.park_name
        date = f"{state.day} {state.month_name} Y{state.year}"
        status = "OPEN" if state.park_open else "CLOSED"
        if state.result == "success":
            status = "SUCCESS"
        elif state.result == "failure":
            status = "FAILED"
        line1 = f"{park}   {status}   {date}"
        line2 = (
            f"{money_str(state.cash)}   guests {state.num_guests}   "
            f"rating {state.rating}   {state.weather}"
        )
        gold = (255, 220, 120)
        cream = (240, 232, 210)
        draw.text((12, 8), line1, font=self.font_lg, fill=gold)
        draw.text((12, 34), line2, font=self.font, fill=cream)
        if caption:
            tw = draw.textlength(caption, font=self.font_sm)
            bx = W - int(tw) - 24
            draw.rounded_rectangle([bx - 8, 10, W - 8, 58], radius=8, fill=(20, 14, 10))
            draw.text((bx, 22), caption[:48], font=self.font_sm, fill=(255, 240, 180))
        return frame.convert("RGB")

    def _fallback_building(
        self,
        frame: Image.Image,
        dest: tuple[int, int],
        w: int, h: int,
        color: tuple[int, int, int],
        label: str,
    ) -> None:
        x, y = dest
        d = ImageDraw.Draw(frame)
        d.rectangle([x + 4, y + 4, x + w * TILE - 5, y + h * TILE - 5], fill=color, outline=(30, 20, 10))
        d.text((x + 6, y + 8), label, font=self.font_sm, fill=(255, 255, 240))

    def _draw_people(self, frame: Image.Image, state: GameState, tick: int) -> None:
        guest_spr = self.sprites.get("guest")
        if guest_spr:
            gbase = guest_spr.resize((22, 28), Image.Resampling.NEAREST)
        else:
            gbase = None
        rng_offsets = ((4, 6), (16, 8), (8, 18), (22, 12), (6, 24), (18, 26), (12, 4), (26, 16))
        shown = state.guests[:80]
        d = ImageDraw.Draw(frame)
        for i, g in enumerate(shown):
            ox, oy = rng_offsets[(i + tick) % len(rng_offsets)]
            wobble = ((tick * 3 + g.id * 7) % 11) - 5
            px = max(0, min(state.map_w * TILE - 12, g.x * TILE + ox + wobble))
            py = max(HUD, min(HUD + state.map_h * TILE - 12, HUD + g.y * TILE + oy))
            # Shadow so guests read against path and grass.
            d.ellipse([px + 4, py + 22, px + 16, py + 28], fill=(20, 20, 10, 90))
            if gbase is not None:
                frame.alpha_composite(gbase, (px, py))
            else:
                d.ellipse([px, py, px + 10, py + 10], fill=(240, 210, 80))
        for s in state.staff:
            px = s.x * TILE + 16
            py = HUD + s.y * TILE + 10
            d = ImageDraw.Draw(frame)
            color = {
                "handyman": (80, 200, 80),
                "mechanic": (80, 140, 220),
                "entertainer": (220, 80, 200),
                "security": (60, 60, 60),
            }.get(s.kind, (200, 200, 200))
            d.rectangle([px, py, px + 10, py + 14], fill=color, outline=(20, 20, 20))


def caption_for(action: str) -> str:
    a = str(action)
    if a.startswith("place_path"):
        return "Paving a path"
    if a.startswith("place_ride:"):
        rid = a.split(":")[1].split(",")[0]
        spec = RIDES.get(rid)
        return f"Building {spec.name if spec else rid}"
    if a.startswith("place_stall:"):
        sid = a.split(":")[1].split(",")[0]
        spec = STALLS.get(sid)
        return f"Building {spec.name if spec else sid}"
    if a.startswith("set_ride_status") and a.endswith("open"):
        return "Opening a ride"
    if a.startswith("set_park_open:true"):
        return "Opening the gates!"
    if a.startswith("hire_staff:"):
        return f"Hiring a {a.split(':', 1)[1]}"
    if a.startswith("wait"):
        return "Guests arrive as time passes"
    if a.startswith("set_entrance_fee"):
        return "Setting the entry fee"
    if a.startswith("start_marketing"):
        return "Starting a marketing campaign"
    if a.startswith("set_loan"):
        return "Arranging a loan"
    return "Running the park"
