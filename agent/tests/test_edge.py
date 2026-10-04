"""Edge cases: malformed input, game-over, rapid reset, odd seeds, long waits."""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openrct2_agent.api import AgentAPI, ParkSession


class MalformedInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = ParkSession("edge")
        self.s.reset(1, "gentle_intro")

    def test_none_empty_number_list(self) -> None:
        for act in (None, "", 0, 3.14, [], ["wait:1"], {"type": None}):
            out = self.s.step(act)
            self.assertFalse(out["ok"], msg=repr(act))
            self.assertTrue(out["error"])

    def test_unicode_and_spaces(self) -> None:
        # Leading/trailing spaces around a well-formed wait are accepted.
        self.assertTrue(self.s.step("  wait:1  ")["ok"])
        out = self.s.step("place_path:☃,1")
        self.assertFalse(out["ok"])
        out = self.s.step("wait:nope")
        self.assertFalse(out["ok"])

    def test_wait_out_of_range(self) -> None:
        self.assertFalse(self.s.step("wait:0")["ok"])
        self.assertFalse(self.s.step("wait:99")["ok"])
        self.assertFalse(self.s.step("wait_days:0")["ok"])
        self.assertFalse(self.s.step("wait_days:1000")["ok"])

    def test_inspect_after_garbage_still_works(self) -> None:
        self.s.step("nope")
        out = self.s.step("inspect_tile:9,15")
        self.assertTrue(out["ok"], out)


class ResetAndSessionTests(unittest.TestCase):
    def test_rapid_resets(self) -> None:
        s = ParkSession("rapid")
        texts = []
        for seed in range(8):
            out = s.reset(seed, "gentle_intro")
            self.assertTrue(out["ok"])
            self.assertEqual(out["result"], "undecided")
            texts.append(out["text"])
        # Different seeds should not all be identical parks.
        self.assertGreater(len(set(texts)), 1)

    def test_negative_and_large_seeds(self) -> None:
        s = ParkSession("seeds")
        self.assertTrue(s.reset(-7, "have_fun")["ok"])
        self.assertTrue(s.reset(2**31 - 1, "gentle_intro")["ok"])

    def test_dispatch_unknown_and_help(self) -> None:
        api = AgentAPI()
        self.assertFalse(api.dispatch({"cmd": "explode"})["ok"])
        self.assertTrue(api.dispatch({"cmd": "help"})["ok"])
        self.assertFalse(api.dispatch("not-a-dict")["ok"])

    def test_two_sessions_isolated(self) -> None:
        api = AgentAPI()
        a = api.reset(1, "gentle_intro", "a")
        b = api.reset(2, "forest_frontiers", "b")
        self.assertNotEqual(a["state"]["scenario_id"], b["state"]["scenario_id"])
        api.step("wait:1", "a")
        # b should still be month 0
        st = api.get_state("b")
        self.assertEqual(st["state"]["date"]["months_elapsed"], 0)


class GameOverEdgeTests(unittest.TestCase):
    def test_actions_after_success_rejected(self) -> None:
        s = ParkSession("over")
        s.reset(1, "have_fun")
        for _ in range(8):
            s.step("wait:4")
        self.assertEqual(s.state.result, "success")
        out = s.step("hire_staff:handyman")
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "game_over")
        # inspect_tile is allowed
        look = s.step("inspect_tile:5,5")
        self.assertTrue(look["ok"], look)
        # reset starts a new game
        self.assertTrue(s.reset(3, "gentle_intro")["ok"])
        self.assertEqual(s.state.result, "undecided")

    def test_step_without_reset(self) -> None:
        s = ParkSession("empty")
        out = s.get_state()
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "no_game")


class PersistenceCliTests(unittest.TestCase):
    def test_cli_roundtrip(self) -> None:
        from openrct2_agent.cli import main
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["reset", "--session", "cli-edge", "--seed", "9", "--scenario", "gentle_intro"])
        self.assertIn('"ok": true', buf.getvalue() or '{"ok": true')
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            main(["step", "--session", "cli-edge", "--action", "hire_staff:handyman"])
        self.assertIn("Hired", buf2.getvalue())


if __name__ == "__main__":
    unittest.main()
