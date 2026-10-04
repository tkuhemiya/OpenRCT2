"""End-to-end: heuristic agent plays through gentle_intro (and a forest_frontiers smoke)."""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openrct2_agent.api import ParkSession  # noqa: E402
from openrct2_agent.players import heuristic_policy, play, random_policy  # noqa: E402
import random  # noqa: E402


class HeuristicE2E(unittest.TestCase):
    def test_heuristic_wins_gentle_intro(self) -> None:
        s = ParkSession("e2e-gentle")
        s.reset(11, "gentle_intro")
        summary = play(s, heuristic_policy, max_steps=250)
        self.assertEqual(
            summary["result"],
            "success",
            msg=f"reason={summary['reason']}\n{summary.get('text','')[-1500:]}",
        )
        self.assertGreaterEqual(s.state.num_guests, 80)
        self.assertGreaterEqual(s.state.rating, 600)

    def test_heuristic_wins_forest_frontiers(self) -> None:
        s = ParkSession("e2e-ff-win")
        s.reset(21, "forest_frontiers")
        summary = play(s, heuristic_policy, max_steps=220)
        self.assertEqual(
            summary["result"],
            "success",
            msg=f"reason={summary['reason']}\n{summary.get('text','')[-1500:]}",
        )
        self.assertGreaterEqual(s.state.num_guests, 250)
        self.assertGreaterEqual(s.state.rating, 600)

    def test_heuristic_wins_dynamite_dunes(self) -> None:
        s = ParkSession("e2e-dunes")
        s.reset(7, "dynamite_dunes")
        summary = play(s, heuristic_policy, max_steps=280)
        self.assertEqual(
            summary["result"],
            "success",
            msg=f"reason={summary['reason']}\n{summary.get('text','')[-1500:]}",
        )
        self.assertGreaterEqual(s.state.park_value, 2_500_000)

    def test_heuristic_survives_forest_frontiers_smoke(self) -> None:
        s = ParkSession("e2e-ff")
        s.reset(21, "forest_frontiers")
        summary = play(s, heuristic_policy, max_steps=180)
        # Need not always win the classic scenario, but must not crash or go illegal-state.
        self.assertIn(summary["result"], ("success", "failure", "undecided"))
        self.assertIsNotNone(s.state)
        self.assertGreaterEqual(len(s.state.rides) + len(s.state.stalls), 1)
        text = s.get_state()["text"]
        self.assertIn("OpenRCT2 agent state", text)
        self.assertIn("Map ", text)

    def test_random_agent_does_not_crash(self) -> None:
        rng = random.Random(123)
        s = ParkSession("e2e-rand")
        s.reset(8, "gentle_intro")

        def pol(sess: ParkSession):
            return random_policy(sess, rng)

        summary = play(s, pol, max_steps=80)
        self.assertIn(summary["result"], ("success", "failure", "undecided"))
        # Invalid actions may happen if the world changed between list and step; they must not crash.
        self.assertTrue(isinstance(summary["steps"], int))


if __name__ == "__main__":
    unittest.main()
