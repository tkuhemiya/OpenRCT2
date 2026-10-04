"""Human park client + programmatic art + agent-driven visual updates."""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openrct2_agent.api import AgentAPI, ParkSession
from openrct2_agent.art import ensure_all_painters_registered, layout_for, pixel_to_tile
from openrct2_agent.audio import sfx, sfx_for_action
from openrct2_agent.catalog import RIDES, STALLS
from openrct2_agent.play import action_from_click, click_park
from openrct2_agent.server import Handler
from openrct2_agent.visual import VisualPark, caption_for


def _png_hash(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return hashlib.sha256(buf.getvalue()).hexdigest()


class PainterCoverageTests(unittest.TestCase):
    def test_every_ride_and_stall_paints(self) -> None:
        missing = ensure_all_painters_registered()
        self.assertEqual(missing, [], msg=missing)
        self.assertGreaterEqual(len(RIDES), 20)
        self.assertGreaterEqual(len(STALLS), 8)


class IsoMathTests(unittest.TestCase):
    def test_pixel_roundtrip_centre_of_diamond(self) -> None:
        lay = layout_for(18, 16, hud=True)
        from openrct2_agent.art import iso

        for x, y in ((0, 0), (8, 15), (9, 12), (4, 4)):
            top = iso(x, y, lay)
            # Centre of the tile diamond sits half a tile down from the top vertex.
            cx, cy = top[0], top[1] + lay.th / 2
            tx, ty = pixel_to_tile(cx, cy, lay)
            self.assertEqual((tx, ty), (x, y), msg=f"tile {x},{y} mapped to {tx},{ty}")


class HumanClickTests(unittest.TestCase):
    def test_path_click_paves_tile(self) -> None:
        api = AgentAPI()
        sid = "human-path"
        api.reset(11, "gentle_intro", sid)
        st = api.session(sid).state
        assert st is not None
        ex, ey = st.entrance
        # Tile just north of the welcome path is owned grass on gentle_intro.
        x, y = ex, ey - 4
        before = st.tile(x, y).kind
        self.assertNotEqual(before, "path")
        action, err = action_from_click(st, "path", "", x, y)
        self.assertIsNone(err)
        self.assertEqual(action, f"place_path:{x},{y}")
        out = click_park(api, {"session_id": sid, "tool": "path", "x": x, "y": y})
        self.assertTrue(out["ok"], out)
        self.assertEqual(api.session(sid).state.tile(x, y).kind, "path")

    def test_invalid_water_click_errors(self) -> None:
        api = AgentAPI()
        sid = "human-bad"
        api.reset(11, "gentle_intro", sid)
        st = api.session(sid).state
        assert st is not None
        water = None
        for yy in range(st.map_h):
            for xx in range(st.map_w):
                if st.tile(xx, yy).kind == "water":
                    water = (xx, yy)
                    break
            if water:
                break
        if water is None:
            self.skipTest("this seed has no water")
        out = click_park(api, {"session_id": sid, "tool": "path", "x": water[0], "y": water[1]})
        self.assertFalse(out["ok"])
        self.assertEqual(out["sfx"], "error")

    def test_off_map_click(self) -> None:
        s = ParkSession("oob")
        s.reset(1, "gentle_intro")
        action, err = action_from_click(s.state, "path", "", -1, 0)
        self.assertIsNone(action)
        self.assertIn("off the map", err or "")


class AgentVisualTests(unittest.TestCase):
    def test_agent_step_changes_pixels(self) -> None:
        vis = VisualPark()
        s = ParkSession("viz")
        s.reset(11, "gentle_intro")
        before = vis.render(s.state, caption="start", tick=0)
        h0 = _png_hash(before)
        out = s.step("place_path:9,11")
        self.assertTrue(out["ok"], out)
        after = vis.render(s.state, caption="path", tick=1, highlight=(9, 11, 1, 1))
        h1 = _png_hash(after)
        self.assertNotEqual(h0, h1)
        # A ride placement must also change the bitmap.
        r = s.step("place_ride:merry_go_round,7,10")
        self.assertTrue(r["ok"], r)
        after2 = vis.render(s.state, caption="ride", tick=2)
        self.assertNotEqual(_png_hash(after), _png_hash(after2))

    def test_open_park_caption(self) -> None:
        self.assertEqual(caption_for("set_park_open:true"), "Opening the gates!")
        self.assertEqual(sfx_for_action("place_path:1,1"), "place")


class AudioTests(unittest.TestCase):
    def test_wav_header(self) -> None:
        raw = sfx("open")
        self.assertGreater(len(raw), 100)
        self.assertTrue(raw.startswith(b"RIFF"))
        self.assertIn(b"WAVE", raw[:16])


class HttpPlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _post(self, path: str, data: dict) -> dict:
        req = urllib.request.Request(
            self._url(path),
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_play_page_and_click_and_agent(self) -> None:
        with urllib.request.urlopen(self._url("/play")) as resp:
            html = resp.read().decode("utf-8")
        self.assertIn("OpenRCT2", html)
        self.assertIn("Construction", html)
        reset = self._post("/play/reset", {"session_id": "web1", "seed": 11, "scenario": "gentle_intro"})
        self.assertTrue(reset["ok"], reset)
        with urllib.request.urlopen(self._url("/play/frame.png?session_id=web1")) as resp:
            png = resp.read()
        self.assertTrue(png.startswith(b"\x89PNG"), png[:8])
        h0 = hashlib.sha256(png).hexdigest()
        click = self._post("/play/click", {"session_id": "web1", "tool": "path", "x": 9, "y": 11})
        self.assertTrue(click["ok"], click)
        with urllib.request.urlopen(self._url("/play/frame.png?session_id=web1&tick=2")) as resp:
            png2 = resp.read()
        self.assertNotEqual(h0, hashlib.sha256(png2).hexdigest())
        agent = self._post("/play/agent_step", {"session_id": "web1", "n": 3})
        self.assertTrue(agent["ok"], agent)
        self.assertGreaterEqual(agent["count"], 1)
        with urllib.request.urlopen(self._url("/play/frame.png?session_id=web1&tick=9")) as resp:
            png3 = resp.read()
        self.assertNotEqual(hashlib.sha256(png2).hexdigest(), hashlib.sha256(png3).hexdigest())
        with urllib.request.urlopen(self._url("/play/sfx/place.wav")) as resp:
            wav = resp.read()
        self.assertTrue(wav.startswith(b"RIFF"))
        # Agent API still works on the same session.
        st = self._post("/state", {"session_id": "web1"})
        self.assertTrue(st["ok"])
        self.assertIn("text", st)
        self.assertGreaterEqual(st["state"]["map"]["reachable_path_count"], 1)


if __name__ == "__main__":
    unittest.main()
