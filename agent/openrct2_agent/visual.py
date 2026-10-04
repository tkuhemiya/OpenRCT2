"""Isometric park camera drawn entirely in code.

The agent loop stays text-only. This module is the human-facing view.
"""

from __future__ import annotations

from typing import Optional

from PIL import Image, ImageDraw

from .art import (
    IsoLayout,
    layout_for,
    paint_entrance,
    paint_ghost,
    paint_highlight,
    paint_hud,
    paint_peep,
    paint_ride,
    paint_scenery,
    paint_stall,
    paint_ticker,
    paint_tile,
    paint_tree,
    pixel_to_tile,
)
from .catalog import RIDES, STALLS
from .engine import GameState


class VisualPark:
    """Renders a GameState as an RCT-style isometric bitmap."""

    def render(
        self,
        state: GameState,
        *,
        caption: str = "",
        tick: int = 0,
        highlight: Optional[tuple[int, int, int, int]] = None,
        ghost: Optional[tuple[str, str, int, int]] = None,
        hud: bool = True,
    ) -> Image.Image:
        lay = layout_for(state.map_w, state.map_h, hud=hud)
        frame = Image.new("RGBA", (lay.width, lay.height), (18, 40, 16, 255))
        draw = ImageDraw.Draw(frame)
        # Sky wash behind the isometric diamond.
        draw.rectangle([0, lay.hud, lay.width, lay.height], fill=(22, 48, 22))

        occupied_trees: set[tuple[int, int]] = set()
        for r in state.rides:
            for yy in range(r.y, r.y + r.h):
                for xx in range(r.x, r.x + r.w):
                    occupied_trees.add((xx, yy))
        for s in state.stalls:
            for yy in range(s.y, s.y + s.h):
                for xx in range(s.x, s.x + s.w):
                    occupied_trees.add((xx, yy))

        # Ground, back to front.
        for diag in range(state.map_w + state.map_h - 1):
            for x in range(state.map_w):
                y = diag - x
                if y < 0 or y >= state.map_h:
                    continue
                t = state.tile(x, y)
                paint_tile(draw, x, y, t.kind, t.owned, t.litter, tick, lay)

        for diag in range(state.map_w + state.map_h - 1):
            for x in range(state.map_w):
                y = diag - x
                if y < 0 or y >= state.map_h:
                    continue
                t = state.tile(x, y)
                if (x, y) in occupied_trees:
                    continue
                if t.tree or (t.kind == "scenery" and t.scenery_id == "tree"):
                    if t.kind in ("path", "entrance", "ride", "stall", "water"):
                        continue
                    paint_tree(draw, x, y, lay, x * 17 + y * 9)
                elif t.kind == "scenery" and t.scenery_id:
                    paint_scenery(draw, x, y, t.scenery_id, lay)

        buildings: list[tuple[int, object, str]] = []
        for s in state.stalls:
            buildings.append((s.x + s.y, s, "stall"))
        for r in state.rides:
            buildings.append((r.x + r.y, r, "ride"))
        buildings.sort(key=lambda it: it[0])
        for _, obj, kind in buildings:
            if kind == "stall":
                paint_stall(draw, obj, lay)  # type: ignore[arg-type]
            else:
                paint_ride(draw, obj, lay, tick)  # type: ignore[arg-type]

        ex, ey = state.entrance
        paint_entrance(draw, ex, ey, lay, state.park_open)

        people: list[tuple[int, int, int, str]] = []
        for g in state.guests[:90]:
            people.append((g.x + g.y, g.x, g.y, f"g{g.id}"))
        for st in state.staff:
            people.append((st.x + st.y, st.x, st.y, st.kind))
        people.sort(key=lambda p: p[0])
        for _, gx, gy, tag in people:
            if tag.startswith("g"):
                paint_peep(draw, gx, gy, lay, int(tag[1:]), tick, "guest")
            else:
                paint_peep(draw, gx, gy, lay, hash(tag) % 50, tick, tag)

        if ghost:
            gkind, gid, gx, gy = ghost
            gw, gh = 1, 1
            if gkind == "ride" and gid in RIDES:
                gw, gh = RIDES[gid].footprint
            elif gkind == "stall" and gid in STALLS:
                gw, gh = STALLS[gid].footprint
            ok = gx >= 0 and gy >= 0 and gx + gw <= state.map_w and gy + gh <= state.map_h
            paint_ghost(draw, gx, gy, gw, gh, lay, ok)

        if highlight:
            hx, hy, hw, hh = highlight
            paint_highlight(draw, hx, hy, hw, hh, lay)

        if hud:
            paint_hud(draw, state, lay, caption)
            paint_ticker(draw, state, lay)
        return frame.convert("RGB")

    def layout(self, state: GameState, *, hud: bool = True) -> IsoLayout:
        return layout_for(state.map_w, state.map_h, hud=hud)


def caption_for(action: str) -> str:
    a = str(action)
    if a.startswith("place_path"):
        return "Paving a path"
    if a.startswith("remove_path"):
        return "Removing a path"
    if a.startswith("buy_land"):
        return "Buying land"
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
    if a.startswith("demolish"):
        return "Demolishing"
    return "Running the park"


def tile_from_pixel(state: GameState, px: float, py: float, *, hud: bool = True) -> tuple[int, int]:
    lay = layout_for(state.map_w, state.map_h, hud=hud)
    return pixel_to_tile(px, py, lay)
