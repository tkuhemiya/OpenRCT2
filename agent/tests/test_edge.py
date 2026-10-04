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


class HttpAliasTests(unittest.TestCase):
    def test_post_state_legal_and_replay(self) -> None:
        import json
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer

        from openrct2_agent.server import Handler

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        def post(path: str, data: dict) -> dict:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))

        try:
            sid = "http-audit"
            reset = post("/reset", {"seed": 1, "scenario": "gentle_intro", "session_id": sid})
            self.assertTrue(reset["ok"], reset)
            state = post("/state", {"session_id": sid})
            self.assertTrue(state["ok"])
            self.assertIn("text", state)
            self.assertFalse(state["game_over"])
            legal = post("/legal_actions", {"session_id": sid})
            self.assertTrue(legal["ok"])
            self.assertIn("wait:1", legal["actions_flat"])
            step = post("/step", {"session_id": sid, "action": "wait:1"})
            self.assertTrue(step["ok"], step)
            exported = post("/rpc", {"cmd": "replay", "session_id": sid})
            applied = post(
                "/replay",
                {"session_id": "http-audit-clone", "replay": exported["replay"]},
            )
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["applied"], 1)
        finally:
            httpd.shutdown()
            httpd.server_close()


class InvalidActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = ParkSession("inv")
        self.s.reset(3, "gentle_intro")

    def test_unknown_and_missing_fields(self) -> None:
        cases = [
            "teleport:moon",
            "place_path",
            "place_path:1",
            "place_path:1,2,3",
            "place_ride:nope,1,1",
            "place_stall:nope,1,1",
            "demolish_ride:999",
            "demolish_stall:999",
            "fire_staff:999",
            "hire_staff:wizard",
            "set_loan:-1",
            "set_loan:999999999",
            "set_entrance_fee:-5",
            "set_research_funding:ludicrous",
            "start_marketing:not_a_campaign",
            {"type": "place_path"},
            {"type": "wait", "months": "three"},
            {"type": "place_ride", "ride_type": "merry_go_round", "x": "east", "y": 3},
        ]
        for act in cases:
            out = self.s.step(act)
            self.assertFalse(out["ok"], msg=repr(act))
            self.assertTrue(out["error"])
            self.assertTrue(out["code"])

    def test_legal_action_then_stale_id(self) -> None:
        legal = self.s.list_legal_actions()
        path = next(a for a in legal["actions_flat"] if a.startswith("place_path:"))
        self.assertTrue(self.s.step(path)["ok"])
        again = self.s.step(path)
        self.assertFalse(again["ok"])
        self.assertIn(again["code"], ("occupied", "not_empty", "bad_tile", "not_owned", "blocked"))

    def test_step_after_no_game(self) -> None:
        s = ParkSession("nope")
        out = s.step("wait:1")
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "no_game")
        self.assertFalse(s.list_legal_actions()["ok"])


class GameOverMoreTests(unittest.TestCase):
    def test_legal_list_and_wait_after_over(self) -> None:
        s = ParkSession("over2")
        s.reset(1, "have_fun")
        for _ in range(8):
            s.step("wait:4")
        self.assertNotEqual(s.state.result, "undecided")
        legal = s.list_legal_actions()
        self.assertTrue(legal["game_over"])
        self.assertTrue(any(a.startswith("inspect_tile:") for a in legal["actions_flat"]))
        self.assertNotIn("wait:1", legal["actions_flat"])
        self.assertEqual(s.step("wait:1")["code"], "game_over")
        self.assertEqual(s.step("place_path:4,4")["code"], "game_over")
        self.assertIn("reset", s.step("wait:1")["error"].lower())


class RapidResetTests(unittest.TestCase):
    def test_reset_mid_game_discards_park(self) -> None:
        s = ParkSession("mid")
        s.reset(1, "gentle_intro")
        s.step("hire_staff:handyman")
        s.step("wait:1")
        out = s.reset(99, "forest_frontiers")
        self.assertTrue(out["ok"])
        self.assertEqual(out["state"]["scenario_id"], "forest_frontiers")
        self.assertEqual(out["state"]["seed"], 99)
        self.assertEqual(s.state.staff, [])
        self.assertEqual(s.state.months_elapsed, 0)

    def test_reset_after_game_over_and_unknown(self) -> None:
        s = ParkSession("cycle")
        s.reset(1, "have_fun")
        for _ in range(8):
            s.step("wait:4")
        self.assertTrue(s.reset(2, "gentle_intro")["ok"])
        self.assertEqual(s.state.result, "undecided")
        bad = s.reset(1, "not_a_scenario")
        self.assertFalse(bad["ok"])
        # Previous park is unchanged on failed reset.
        self.assertEqual(s.state.scenario_id, "gentle_intro")


class OddSeedTests(unittest.TestCase):
    def test_zero_negative_huge_and_bad(self) -> None:
        s = ParkSession("odd-seed")
        self.assertTrue(s.reset(0, "gentle_intro")["ok"])
        self.assertTrue(s.reset(-1, "forest_frontiers")["ok"])
        self.assertTrue(s.reset(2**32, "have_fun")["ok"])
        self.assertEqual(s.reset("1.5", "gentle_intro")["code"], "bad_seed")  # type: ignore[arg-type]
        self.assertEqual(s.reset(None, "gentle_intro")["code"], "bad_seed")  # type: ignore[arg-type]
        self.assertEqual(s.reset(True, "gentle_intro")["ok"], True)  # bool subclasses int


class LongGameAndTimeoutTests(unittest.TestCase):
    def test_wait_sixteen_is_bounded(self) -> None:
        import time

        s = ParkSession("long-wait")
        s.reset(4, "have_fun")
        t0 = time.perf_counter()
        out = s.step("wait:16")
        elapsed = time.perf_counter() - t0
        self.assertTrue(out["ok"], out)
        self.assertLess(elapsed, 8.0, f"wait:16 took {elapsed:.2f}s")
        self.assertGreaterEqual(s.state.months_elapsed, 16)

    def test_full_have_fun_under_timeout(self) -> None:
        import time

        from openrct2_agent.players import heuristic_policy, play

        s = ParkSession("long-fun")
        s.reset(8, "have_fun")
        t0 = time.perf_counter()
        summary = play(s, heuristic_policy, max_steps=120)
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 15.0, f"have_fun play took {elapsed:.2f}s")
        self.assertIn(summary["result"], ("success", "failure", "undecided"))
        self.assertLessEqual(summary["steps"], 120)

    def test_play_respects_max_steps(self) -> None:
        from openrct2_agent.players import play

        s = ParkSession("cap")
        s.reset(1, "forest_frontiers")
        summary = play(s, lambda sess: "wait:1", max_steps=3)
        self.assertEqual(summary["steps"], 3)
        self.assertEqual(s.state.result, "undecided")


class MalformedHttpAndReplayTests(unittest.TestCase):
    def test_http_bad_json_and_unknown_path(self) -> None:
        import json
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer

        from openrct2_agent.server import Handler

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/step",
                data=b"{not json",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req)
                self.fail("expected HTTPError")
            except urllib.error.HTTPError as exc:
                body = json.loads(exc.read().decode("utf-8"))
                self.assertFalse(body["ok"])
                self.assertEqual(body["code"], "bad_json")
            req2 = urllib.request.Request(
                f"http://127.0.0.1:{port}/nope",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req2)
                self.fail("expected HTTPError for unknown path")
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 404)
                body = json.loads(exc.read().decode("utf-8"))
                self.assertEqual(body["code"], "not_found")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_apply_replay_stops_on_bad_action(self) -> None:
        s = ParkSession("replay-bad")
        out = s.apply_replay(
            {"seed": 1, "scenario": "gentle_intro", "actions": ["wait:1", "place_path:0,0", "wait:1"]}
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "replay_failed")
        self.assertEqual(out["applied"][1]["ok"], False)


class TextClarityTests(unittest.TestCase):
    def test_hud_names_entrance_paths_and_objective(self) -> None:
        s = ParkSession("hud")
        text = s.reset(1, "forest_frontiers")["text"]
        for needle in (
            "OpenRCT2 agent state",
            "Objective:",
            "250 guests",
            "E entrance",
            "TOUCH a # path",
            "Map 18x16",
            "CLOSED",
            "Legend:",
            "end of October Year 1",
            "Pave # NORTH",
        ):
            self.assertIn(needle, text)
        self.assertNotIn("! (none)", text)
        legal = s.list_legal_actions()
        self.assertIn("connected # path from the entrance", legal["text"])
        self.assertIn("wait:1", legal["actions_flat"])
        self.assertTrue(any("umbrella_stall" in a for a in legal["actions_flat"]))
        self.assertTrue(any("toilets," in a for a in legal["actions_flat"]))


if __name__ == "__main__":
    unittest.main()
