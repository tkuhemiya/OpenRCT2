"""Built-in agents used for tests, brute-force play, and replay capture.

These are NOT the LLM. They exist so the environment can be exercised
without a model: a constructive heuristic and a noisy random legal-action picker.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Optional

from .api import ParkSession
from .catalog import RIDES, STALLS


def _ids(legal: dict[str, Any], prefix: str) -> list[str]:
    return [a["id"] for a in legal.get("actions", []) if str(a.get("id", "")).startswith(prefix)]


def heuristic_policy(session: ParkSession) -> Optional[str]:
    """Greedy park builder: paths, facilities, gentle rides, staff, open, wait."""
    st = session.get_state()
    if not st.get("ok") or st.get("game_over"):
        return None
    legal = session.list_legal_actions()
    if legal.get("game_over"):
        return None
    data = st["state"]
    cash = data["finance"]["cash"]
    rides = data["rides"]
    stalls = data["stalls"]
    staff = data["staff"]
    open_park = data["park_open"]
    invented = set(data["research"]["invented"])

    path_ids = _ids(legal, "place_path:")
    ex, ey = data["map"]["entrance"]

    def path_key(aid: str) -> tuple[int, int, int]:
        _, xy = aid.split(":", 1)
        x, y = (int(p) for p in xy.split(","))
        return (abs(x - ex) + abs(y - ey), -y, x)

    if path_ids and cash > 20_000 and data["map"]["reachable_path_count"] < 36:
        return sorted(path_ids, key=path_key)[0]

    stall_want = ["toilets", "drinks_stall", "burger_bar", "information_kiosk", "umbrella_stall", "ice_cream"]
    have_stall = {s["spec_id"] for s in stalls}
    for sid in stall_want:
        if sid in have_stall or sid not in invented:
            continue
        opts = _ids(legal, f"place_stall:{sid},")
        if opts and cash > STALLS[sid].build_cost + 8_000:
            return _prefer_near_path(opts, data)

    ride_want = [
        "merry_go_round",
        "spiral_slide",
        "observation_tower",
        "ferris_wheel",
        "car_ride",
        "haunted_house",
        "twist",
        "side_friction",
        "miniature_railway",
        "junior_coaster",
        "ghost_train",
        "dodgems",
        "circus",
        "log_flume",
        "wooden_coaster",
    ]
    have_ride = {r["spec_id"] for r in rides}
    for rid in ride_want:
        if rid in have_ride or rid not in invented:
            continue
        spec = RIDES[rid]
        if cash < spec.build_cost + 12_000:
            continue
        opts = _ids(legal, f"place_ride:{rid},")
        if opts:
            return _prefer_near_path(opts, data)

    kinds = {s["kind"] for s in staff}
    if "handyman" not in kinds:
        return "hire_staff:handyman"
    if rides and "mechanic" not in kinds:
        return "hire_staff:mechanic"
    if sum(1 for s in staff if s["kind"] == "handyman") < 2 and cash > 40_000:
        return "hire_staff:handyman"
    if len(rides) >= 3 and "entertainer" not in kinds and cash > 80_000:
        return "hire_staff:entertainer"

    for r in rides:
        if r["status"] != "open":
            return f"set_ride_status:{r['id']},open"

    if not open_park and (rides or stalls):
        return "set_park_open:true"

    if data["finance"]["entrance_fee"] > 500 and data["guests"]["in_park"] < 40:
        return "set_entrance_fee:200"

    # Expand paths once park is running and we still have land.
    if path_ids and cash > 100_000 and data["map"]["reachable_path_count"] < 50:
        return path_ids[0]

    if cash < 30_000 and data["finance"]["loan"] < data["finance"]["max_loan"]:
        return f"set_loan:{min(data['finance']['max_loan'], data['finance']['loan'] + 100000)}"

    return "wait:1"


def _prefer_near_path(opts: list[str], data: dict[str, Any]) -> str:
    ex, ey = data["map"]["entrance"]

    def key(aid: str) -> int:
        parts = aid.split(",")
        try:
            x, y = int(parts[-2]), int(parts[-1])
        except (IndexError, ValueError):
            return 99
        return abs(x - ex) + abs(y - (ey - 4))

    return sorted(opts, key=key)[0]


def random_policy(session: ParkSession, rng: random.Random) -> Optional[str]:
    legal = session.list_legal_actions()
    if legal.get("game_over") or not legal.get("actions_flat"):
        return None
    st = session.state
    assert st is not None
    # Weighted: construction early, waiting later.
    buckets = {
        "place_path": 8 if st.months_elapsed < 3 else 3,
        "place_stall": 5,
        "place_ride": 6,
        "hire_staff": 2,
        "set_ride_status": 4,
        "set_park_open": 3,
        "wait": 4 if st.park_open else 1,
        "buy_land": 1,
        "set_entrance_fee": 1,
        "start_marketing": 1,
        "set_research_funding": 1,
        "place_scenery": 1,
    }
    weighted: list[str] = []
    for aid in legal["actions_flat"]:
        typ = aid.split(":", 1)[0]
        w = buckets.get(typ, 0)
        if w:
            weighted.extend([aid] * w)
    if not weighted:
        weighted = [a for a in legal["actions_flat"] if a.startswith("wait")]
    if not weighted:
        return None
    return rng.choice(weighted)


def play(
    session: ParkSession,
    policy: Callable[[ParkSession], Optional[str]],
    *,
    max_steps: int = 400,
    on_step: Optional[Callable[[int, str, dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    steps = 0
    invalid = 0
    history: list[dict[str, Any]] = []
    while steps < max_steps:
        st = session.state
        if st is None or st.result != "undecided":
            break
        action = policy(session)
        if action is None:
            break
        result = session.step(action)
        steps += 1
        rec = {
            "step": steps,
            "action": action,
            "ok": result.get("ok"),
            "message": result.get("message"),
            "error": result.get("error"),
            "result": result.get("result"),
        }
        history.append(rec)
        if on_step:
            on_step(steps, action, result)
        if not result.get("ok"):
            invalid += 1
            if invalid > 25:
                break
        else:
            invalid = 0
    state = session.get_state()
    return {
        "steps": steps,
        "invalid_streak_stop": invalid > 25,
        "result": None if session.state is None else session.state.result,
        "reason": None if session.state is None else session.state.result_reason,
        "history": history,
        "final": state.get("state"),
        "text": state.get("text"),
        "replay": session.export_replay(),
    }
