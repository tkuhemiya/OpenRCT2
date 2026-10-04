"""Every vanilla RCT2 ride, shop, scenery group, terrain, weather, and sound is in the sim."""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openrct2_agent.art import TERRAIN_PALETTE, ensure_all_painters_registered, paint_sky, layout_for
from openrct2_agent.audio import sfx
from openrct2_agent.catalog import (
    ENTERTAINER_COSTUMES,
    PATH_TYPES,
    RIDE_MUSIC,
    RIDES,
    SCENERY,
    STAFF_HIRE_COST,
    STALLS,
    TERRAIN_SURFACES,
    WEATHER_TYPES,
    invented_at_start,
    SCENARIOS,
)
from openrct2_agent.engine import new_game
from openrct2_agent.rct2 import (
    RCT2_ENTERTAINER_COSTUMES,
    RCT2_MUSIC,
    RCT2_PATHS,
    RCT2_RIDES,
    RCT2_SCENERY,
    RCT2_SHOPS,
    RCT2_SOUNDS,
    RCT2_STAFF,
    RCT2_TERRAIN,
    RCT2_WEATHER,
)
from PIL import Image, ImageDraw


class RCT2CoverageTests(unittest.TestCase):
    def test_every_rct2_ride_is_in_the_catalog(self) -> None:
        missing = [rid for rid in RCT2_RIDES if rid not in RIDES]
        self.assertEqual(missing, [], msg=missing)
        self.assertGreaterEqual(len(RIDES), len(RCT2_RIDES))

    def test_every_rct2_shop_is_in_the_catalog(self) -> None:
        missing = [sid for sid in RCT2_SHOPS if sid not in STALLS]
        self.assertEqual(missing, [], msg=missing)

    def test_every_rct2_scenery_group_is_in_the_catalog(self) -> None:
        missing = [sid for sid in RCT2_SCENERY if sid not in SCENERY]
        self.assertEqual(missing, [], msg=missing)

    def test_terrain_weather_paths_music_staff(self) -> None:
        self.assertEqual(set(RCT2_TERRAIN), set(TERRAIN_SURFACES))
        self.assertEqual(set(RCT2_WEATHER), set(WEATHER_TYPES))
        self.assertEqual(set(RCT2_PATHS), set(PATH_TYPES))
        self.assertEqual(set(RCT2_MUSIC), set(RIDE_MUSIC))
        for kind in RCT2_STAFF:
            self.assertIn(kind, STAFF_HIRE_COST)
        self.assertEqual(set(RCT2_ENTERTAINER_COSTUMES), set(ENTERTAINER_COSTUMES))

    def test_every_rct2_sound_renders_wav(self) -> None:
        for name in RCT2_SOUNDS:
            raw = sfx(name)
            self.assertTrue(raw.startswith(b"RIFF"), name)
            self.assertGreater(len(raw), 100, name)

    def test_painters_cover_the_full_catalog(self) -> None:
        missing = ensure_all_painters_registered()
        self.assertEqual(missing, [], msg=missing)

    def test_every_weather_paints_sky(self) -> None:
        lay = layout_for(8, 8, hud=True)
        im = Image.new("RGB", (lay.width, lay.height), (0, 0, 0))
        draw = ImageDraw.Draw(im)
        for weather in RCT2_WEATHER:
            paint_sky(draw, lay, weather)

    def test_every_terrain_has_a_palette(self) -> None:
        for surface in RCT2_TERRAIN:
            self.assertIn(surface, TERRAIN_PALETTE)

    def test_dunes_uses_sand_and_gentle_uses_grass(self) -> None:
        dunes = new_game(11, SCENARIOS["dynamite_dunes"])
        glen = new_game(11, SCENARIOS["gentle_intro"])
        self.assertEqual(SCENARIOS["dynamite_dunes"].terrain, "sand")
        self.assertEqual(SCENARIOS["dynamite_dunes"].path_type, "tarmac")
        self.assertTrue(any((t.surface or "").startswith("sand") or t.surface == "rock" for row in dunes.tiles for t in row))
        self.assertTrue(any(t.surface == "grass" for row in glen.tiles for t in row))

    def test_starting_invented_includes_path_scenery(self) -> None:
        invented = invented_at_start(SCENARIOS["gentle_intro"])
        for sid in ("tree", "bench", "lamp", "bin", "garden"):
            self.assertIn(sid, invented)
        self.assertNotIn("martian", invented)


if __name__ == "__main__":
    unittest.main()
