"""Unit tests for the OpenRCT2 text agent API."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openrct2_agent.api import AgentAPI, ParkSession  # noqa: E402
from openrct2_agent.catalog import PATH_COST, SCENARIOS  # noqa: E402
from openrct2_agent.engine import money_str, new_game  # noqa: E402
from openrct2_agent.legal import list_legal_actions  # noqa: E402


class ResetTests(unittest.TestCase):
    def test_unknown_scenario(self) -> None:
        s = ParkSession()
        out = s.reset(1, "nope")
        self.assertFalse(out["ok"])
        self.assertIn("Unknown scenario", out["error"])

    def test_bad_seed(self) -> None:
        s = ParkSession()
        out = s.reset("banana", "gentle_intro")  # type: ignore[arg-type]
        self.assertFalse(out["ok"])

    def test_reset_fields(self) -> None:
        s = ParkSession()
        out = s.reset(7, "forest_frontiers")
        self.assertTrue(out["ok"])
        self.assertIn("text", out)
        self.assertIn("Forest Frontiers", out["text"])
        self.assertFalse(out["game_over"])
        self.assertEqual(out["result"], "undecided")
        self.assertEqual(out["state"]["seed"], 7)


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_map(self) -> None:
        a = ParkSession().reset(99, "forest_frontiers")
        b = ParkSession().reset(99, "forest_frontiers")
        self.assertEqual(a["text"], b["text"])
        self.assertEqual(a["state"]["map"]["ascii"], b["state"]["map"]["ascii"])

    def test_replay_matches(self) -> None:
        actions = [
            "place_path:9,11",
            "place_path:8,12",
            "place_stall:toilets,8,11",
            "hire_staff:handyman",
            "set_park_open:true",
            "wait:1",
        ]
        s1 = ParkSession()
        s1.reset(3, "gentle_intro")
        for a in actions:
            s1.step(a)
        s2 = ParkSession()
        s2.reset(3, "gentle_intro")
        for a in actions:
            s2.step(a)
        self.assertEqual(s1.get_state()["text"], s2.get_state()["text"])
        self.assertEqual(s1.state.cash, s2.state.cash)
        self.assertEqual(s1.state.num_guests, s2.state.num_guests)
        self.assertEqual(s1.state.rating, s2.state.rating)

    def test_different_seeds_differ(self) -> None:
        a = ParkSession().reset(1, "forest_frontiers")
        b = ParkSession().reset(2, "forest_frontiers")
        # Trees are scattered by RNG; seeds should not be identical parks.
        self.assertNotEqual(a["state"]["map"]["ascii"], b["state"]["map"]["ascii"])


class ActionErrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = ParkSession()
        self.s.reset(1, "gentle_intro")

    def test_no_crash_on_garbage(self) -> None:
        for act in [None, "", 123, {"foo": 1}, "not_a_real_action:1", "place_path:nope", "place_ride:bogus,0,0"]:
            out = self.s.step(act)
            self.assertFalse(out["ok"], msg=repr(act))
            self.assertTrue(out["error"])
            self.assertEqual(out["result"], "undecided")

    def test_path_off_map(self) -> None:
        out = self.s.step("place_path:99,99")
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "oob")

    def test_path_on_entrance(self) -> None:
        ex, ey = self.s.state.entrance
        out = self.s.step(f"place_path:{ex},{ey}")
        self.assertFalse(out["ok"])

    def test_unowned_land(self) -> None:
        out = self.s.step("place_path:0,0")
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "unowned")

    def test_unknown_ride(self) -> None:
        out = self.s.step("place_ride:space_mountain,5,5")
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "unknown_ride")

    def test_not_researched(self) -> None:
        out = self.s.step("place_ride:looping_coaster,4,4")
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "not_researched")

    def test_step_before_reset(self) -> None:
        s = ParkSession()
        out = s.step("wait:1")
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "no_game")


class ConstructionTests(unittest.TestCase):
    def test_place_path_costs_money(self) -> None:
        s = ParkSession()
        s.reset(1, "gentle_intro")
        cash = s.state.cash
        # Find a legal path tile from the API.
        legal = s.list_legal_actions()
        path = next(a for a in legal["actions_flat"] if a.startswith("place_path:"))
        out = s.step(path)
        self.assertTrue(out["ok"], out)
        self.assertEqual(s.state.cash, cash - PATH_COST)

    def test_place_and_open_ride(self) -> None:
        s = ParkSession()
        s.reset(1, "gentle_intro")
        legal = s.list_legal_actions()
        ride_act = next(a for a in legal["actions_flat"] if a.startswith("place_ride:merry_go_round,"))
        out = s.step(ride_act)
        self.assertTrue(out["ok"], out)
        self.assertEqual(len(s.state.rides), 1)
        self.assertEqual(s.state.rides[0].status, "closed")
        out = s.step("set_ride_status:0,open")
        self.assertTrue(out["ok"])
        self.assertEqual(s.state.rides[0].status, "open")

    def test_overlap_rejected(self) -> None:
        s = ParkSession()
        s.reset(1, "gentle_intro")
        legal = s.list_legal_actions()
        act = next(a for a in legal["actions_flat"] if a.startswith("place_ride:observation_tower,"))
        self.assertTrue(s.step(act)["ok"])
        out = s.step(act)
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "placement")


class GuestAndTimeTests(unittest.TestCase):
    def test_closed_park_no_guests(self) -> None:
        s = ParkSession()
        s.reset(5, "gentle_intro")
        s.step("wait:1")
        self.assertEqual(s.state.num_guests, 0)
        self.assertFalse(s.state.park_open)

    def test_open_park_with_rides_gets_guests(self) -> None:
        s = ParkSession()
        s.reset(5, "gentle_intro")
        legal = s.list_legal_actions()
        # Pave several paths.
        paths = [a for a in legal["actions_flat"] if a.startswith("place_path:")][:12]
        for a in paths:
            s.step(a)
        legal = s.list_legal_actions()
        stall = next(a for a in legal["actions_flat"] if a.startswith("place_stall:toilets,"))
        s.step(stall)
        legal = s.list_legal_actions()
        ride = next(a for a in legal["actions_flat"] if a.startswith("place_ride:merry_go_round,"))
        s.step(ride)
        s.step("set_ride_status:0,open")
        s.step("hire_staff:handyman")
        s.step("set_park_open:true")
        s.step("wait:1")
        self.assertGreater(s.state.total_admissions, 0)
        self.assertGreater(s.state.rating, 0)

    def test_disconnected_ride_warned(self) -> None:
        s = ParkSession()
        s.reset(1, "gentle_intro")
        # Place a ride far from the entrance path if possible.
        legal = s.list_legal_actions()
        far = [a for a in legal["actions_flat"] if a.startswith("place_ride:observation_tower,")]
        # Take the origin with smallest y (north, away from south entrance).
        def y_of(aid: str) -> int:
            return int(aid.split(",")[-1])

        act = sorted(far, key=y_of)[0]
        s.step(act)
        s.step("set_ride_status:0,open")
        s.step("set_park_open:true")
        text = s.get_state()["text"]
        self.assertTrue("No path from the entrance" in text or "CLOSED" in text or "Warnings" in text)


class ObjectiveTests(unittest.TestCase):
    def test_have_fun_time_cap(self) -> None:
        s = ParkSession()
        s.reset(1, "have_fun")
        # 4 years * 8 months = 32 waits of 1 month — do it in chunks.
        for _ in range(8):
            s.step("wait:4")
            if s.state.result != "undecided":
                break
        self.assertEqual(s.state.result, "success")
        self.assertIn("fun", s.state.result_reason.lower())

    def test_game_over_blocks_build(self) -> None:
        s = ParkSession()
        s.reset(1, "have_fun")
        for _ in range(8):
            s.step("wait:4")
        out = s.step("place_path:5,5")
        self.assertFalse(out["ok"])
        self.assertEqual(out["code"], "game_over")


class LegalActionTests(unittest.TestCase):
    def test_legal_contains_wait_and_open(self) -> None:
        s = ParkSession()
        s.reset(1, "gentle_intro")
        legal = s.list_legal_actions()
        self.assertTrue(legal["ok"])
        self.assertGreater(legal["count"], 10)
        flat = legal["actions_flat"]
        self.assertIn("wait:1", flat)
        self.assertTrue(any(a.startswith("place_path:") for a in flat))
        self.assertTrue(any(a.startswith("hire_staff:") for a in flat))
        # First suggested path should be near the entrance, not the NW corner.
        first_path = next(a for a in flat if a.startswith("place_path:"))
        xy = first_path.split(":", 1)[1]
        x, y = (int(p) for p in xy.split(","))
        ex, ey = s.state.entrance
        self.assertLessEqual(abs(x - ex) + abs(y - ey), 6)

    def test_money_str(self) -> None:
        self.assertEqual(money_str(1000), "£10.00")
        self.assertEqual(money_str(-250), "-£2.50")
        self.assertEqual(money_str(0), "£0.00")

    def test_scenarios_exist(self) -> None:
        for name in ("gentle_intro", "forest_frontiers", "dynamite_dunes", "have_fun"):
            self.assertIn(name, SCENARIOS)


class LoggingTests(unittest.TestCase):
    def test_logs_api_calls(self) -> None:
        from openrct2_agent import logging_util

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "t.jsonl")
            logging_util.configure(path)
            s = ParkSession()
            s.reset(1, "gentle_intro")
            s.step("wait:1")
            with open(path, encoding="utf-8") as f:
                lines = f.read().strip().splitlines()
            self.assertGreaterEqual(len(lines), 2)
            self.assertTrue(any("api.reset" in ln for ln in lines))
            self.assertTrue(any("api.step" in ln for ln in lines))
            self.assertTrue(any('"kind": "game.start"' in ln for ln in lines))
            self.assertTrue(any('"kind": "game.event"' in ln for ln in lines))
            self.assertTrue(any('"kind": "game.month"' in ln for ln in lines))
            self.assertTrue(any('"topic": "start"' in ln for ln in lines))
            self.assertTrue(any('"topic": "month"' in ln for ln in lines))
        logging_util.configure()


class ReplayApplyTests(unittest.TestCase):
    def test_apply_replay_matches_live_play(self) -> None:
        live = ParkSession("live")
        live.reset(5, "gentle_intro")
        legal = live.list_legal_actions()
        path = next(a for a in legal["actions_flat"] if a.startswith("place_path:"))
        actions = [path, "hire_staff:handyman", "set_park_open:true", "wait:1"]
        for a in actions:
            self.assertTrue(live.step(a)["ok"], a)
        exported = live.export_replay()
        self.assertEqual(exported["actions"], actions)
        clone = ParkSession("clone")
        out = clone.apply_replay(exported)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["applied"], len(actions))
        self.assertEqual(clone.get_state()["text"], live.get_state()["text"])
        self.assertEqual(clone.state.cash, live.state.cash)

    def test_apply_replay_bad_payload(self) -> None:
        s = ParkSession("bad-replay")
        self.assertFalse(s.apply_replay("nope")["ok"])
        self.assertEqual(s.apply_replay({"seed": 1, "scenario": "gentle_intro"})["code"], "bad_replay")

    def test_dispatch_apply_replay(self) -> None:
        api = AgentAPI()
        api.dispatch({"cmd": "reset", "seed": 4, "scenario": "gentle_intro", "session_id": "r1"})
        api.dispatch({"cmd": "step", "action": "wait:1", "session_id": "r1"})
        exported = api.dispatch({"cmd": "replay", "session_id": "r1"})
        out = api.dispatch({"cmd": "apply_replay", "session_id": "r2", "replay": exported["replay"]})
        self.assertTrue(out["ok"], out)
        self.assertEqual(api.get_state("r2")["state"]["date"]["months_elapsed"], 1)


class LegalCapTests(unittest.TestCase):
    def test_max_tile_actions_keeps_wait(self) -> None:
        s = ParkSession()
        s.reset(1, "forest_frontiers")
        uncapped = list_legal_actions(s.state, max_tile_actions=10_000)
        capped = list_legal_actions(s.state, max_tile_actions=40)
        self.assertTrue(capped["truncated"])
        self.assertGreater(uncapped["count"], capped["count"])
        self.assertIn("wait:1", capped["actions_flat"])
        self.assertIn("set_park_open:true", capped["actions_flat"])
        self.assertTrue(any(a.startswith("hire_staff:") for a in capped["actions_flat"]))

    def test_inspect_tile_is_listed(self) -> None:
        s = ParkSession()
        s.reset(1, "gentle_intro")
        legal = s.list_legal_actions()
        self.assertTrue(any(a.startswith("inspect_tile:") for a in legal["actions_flat"]))
        self.assertIn("wait:1", legal["actions_flat"])


class DispatchTests(unittest.TestCase):
    def test_rpc(self) -> None:
        api = AgentAPI()
        out = api.dispatch({"cmd": "reset", "seed": 2, "scenario": "gentle_intro", "session_id": "t"})
        self.assertTrue(out["ok"])
        out = api.dispatch({"cmd": "step", "action": "wait:1", "session_id": "t"})
        self.assertTrue(out["ok"])
        out = api.dispatch({"cmd": "bogus"})
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
