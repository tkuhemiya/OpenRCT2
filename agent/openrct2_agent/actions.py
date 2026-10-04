"""Query/execute player actions. Invalid actions return errors; they never raise to the API."""

from __future__ import annotations

from typing import Any, Optional

from . import logging_util
from .catalog import (
    MARKETING_CAMPAIGNS,
    PATH_COST,
    PATH_REMOVE_COST,
    RESEARCH_FUNDING,
    RIDES,
    SCENERY,
    STAFF_HIRE_COST,
    STAFF_WAGE_MONTH,
    STALLS,
)
from .engine import (
    Campaign,
    GameState,
    RideInstance,
    Staff,
    StallInstance,
    adjacent_to_reachable_path,
    charge,
    clear_footprint,
    footprint_ok,
    money_str,
    neighbors,
    occupy,
    path_reachable,
    release,
    simulate_days,
    simulate_months,
    _recalculate,
)


def parse_action(action: Any) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Accept a dict, or strings like 'place_path:3,4' / 'wait:1' / 'set_park_open:true'."""
    if action is None:
        return None, "Action is empty. Pass a dict or an id from list_legal_actions."
    if isinstance(action, dict):
        if "type" not in action:
            return None, "Action dict must include 'type'."
        return dict(action), None
    if not isinstance(action, str):
        return None, f"Action must be a string or object, got {type(action).__name__}."
    raw = action.strip()
    if not raw:
        return None, "Action is an empty string."
    if ":" not in raw:
        return {"type": raw}, None
    typ, rest = raw.split(":", 1)
    typ = typ.strip()
    rest = rest.strip()
    parsed: dict[str, Any] = {"type": typ}
    if typ in ("place_path", "remove_path", "buy_land", "inspect_tile"):
        parts = rest.split(",")
        if len(parts) != 2:
            return None, f"{typ} needs x,y (got {rest!r})."
        try:
            parsed["x"], parsed["y"] = int(parts[0]), int(parts[1])
        except ValueError:
            return None, f"{typ} coordinates must be integers, got {rest!r}."
    elif typ in ("place_ride", "place_stall", "place_scenery"):
        # ride_type,x,y[,rotation]
        parts = [p.strip() for p in rest.split(",")]
        if len(parts) < 3:
            return None, f"{typ} needs name,x,y[,rotation]. Got {rest!r}."
        parsed["ride_type" if typ == "place_ride" else "stall_type" if typ == "place_stall" else "scenery_type"] = parts[0]
        try:
            parsed["x"], parsed["y"] = int(parts[1]), int(parts[2])
        except ValueError:
            return None, f"{typ} x,y must be integers."
        if len(parts) >= 4 and parts[3] != "":
            try:
                parsed["rotation"] = int(parts[3])
            except ValueError:
                return None, "rotation must be 0 or 90."
    elif typ in ("demolish_ride", "set_ride_status", "set_ride_price", "set_ride_name"):
        parts = rest.split(",", 1)
        try:
            parsed["ride_id"] = int(parts[0])
        except ValueError:
            return None, f"{typ} needs ride_id as int."
        if typ == "set_ride_status":
            if len(parts) < 2:
                return None, "set_ride_status needs ride_id,status."
            parsed["status"] = parts[1].strip()
        elif typ == "set_ride_price":
            if len(parts) < 2:
                return None, "set_ride_price needs ride_id,price_pence."
            try:
                parsed["price"] = int(parts[1])
            except ValueError:
                return None, "price must be integer pence."
        elif typ == "set_ride_name":
            if len(parts) < 2:
                return None, "set_ride_name needs ride_id,name."
            parsed["name"] = parts[1]
    elif typ in ("demolish_stall", "set_stall_price"):
        parts = rest.split(",", 1)
        try:
            parsed["stall_id"] = int(parts[0])
        except ValueError:
            return None, f"{typ} needs stall_id as int."
        if typ == "set_stall_price" and len(parts) >= 2:
            try:
                parsed["price"] = int(parts[1])
            except ValueError:
                return None, "price must be integer pence."
    elif typ == "hire_staff":
        parsed["staff_type"] = rest
    elif typ == "fire_staff":
        try:
            parsed["staff_id"] = int(rest)
        except ValueError:
            return None, "fire_staff needs staff_id."
    elif typ == "set_park_open":
        parsed["open"] = rest.lower() in ("1", "true", "yes", "open")
    elif typ == "set_entrance_fee":
        try:
            parsed["fee"] = int(rest)
        except ValueError:
            return None, "set_entrance_fee needs integer pence."
    elif typ == "set_loan":
        try:
            parsed["loan"] = int(rest)
        except ValueError:
            return None, "set_loan needs integer pence."
    elif typ == "set_research_funding":
        parsed["level"] = rest
    elif typ == "start_marketing":
        parsed["campaign"] = rest
    elif typ == "set_park_name":
        parsed["name"] = rest
    elif typ in ("wait", "wait_months"):
        try:
            parsed["months"] = int(rest)
        except ValueError:
            return None, "wait needs integer months."
    elif typ == "wait_days":
        try:
            parsed["days"] = int(rest)
        except ValueError:
            return None, "wait_days needs integer days."
    elif typ == "wait_weeks":
        try:
            parsed["weeks"] = int(rest)
        except ValueError:
            return None, "wait_weeks needs integer weeks."
    else:
        parsed["raw"] = rest
    return parsed, None


def execute(state: GameState, action: Any) -> dict[str, Any]:
    parsed, err = parse_action(action)
    if err:
        return _fail("parse_error", err)
    assert parsed is not None
    typ = parsed["type"]
    if state.result != "undecided" and typ not in ("inspect_tile",):
        return _fail(
            "game_over",
            f"Game is over ({state.result}): {state.result_reason}. Call reset() for a new park.",
        )
    handler = ACTIONS.get(typ)
    if handler is None:
        known = ", ".join(sorted(ACTIONS))
        return _fail("unknown_action", f"Unknown action type {typ!r}. Known types: {known}.")
    try:
        result = handler(state, parsed)
        if result.get("ok"):
            _recalculate(state)
        return result
    except Exception as exc:  # noqa: BLE001 — API must never crash the agent
        return _fail("internal_error", f"Internal error executing {typ}: {exc}")


def _ok(message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": True, "error": None, "code": None, "message": message, **extra}


def _fail(code: str, error: str) -> dict[str, Any]:
    return {"ok": False, "error": error, "code": code, "message": error}


def _need_int(parsed: dict[str, Any], key: str) -> tuple[Optional[int], Optional[str]]:
    if key not in parsed:
        return None, f"Missing parameter '{key}'."
    try:
        return int(parsed[key]), None
    except (TypeError, ValueError):
        return None, f"Parameter '{key}' must be an integer."


def _dims(w: int, h: int, rotation: int) -> tuple[int, int]:
    if rotation in (90, 270, 1):
        return h, w
    return w, h


def act_place_path(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    x, err = _need_int(parsed, "x")
    y, err2 = _need_int(parsed, "y")
    if err or err2:
        return _fail("bad_params", err or err2 or "")
    assert x is not None and y is not None
    if not state.in_bounds(x, y):
        return _fail("oob", f"({x},{y}) is off the {state.map_w}x{state.map_h} map.")
    t = state.tile(x, y)
    if t.kind == "path":
        return _fail("occupied", f"({x},{y}) already has a path.")
    if t.kind == "entrance":
        return _fail("occupied", "Cannot pave over the park entrance.")
    if t.kind in ("ride", "stall"):
        return _fail("occupied", f"({x},{y}) is occupied by a building.")
    if t.kind == "water":
        return _fail("terrain", f"({x},{y}) is water.")
    if not t.owned:
        return _fail("unowned", f"({x},{y}) is not owned. buy_land:{x},{y} first.")
    extra = 0
    if t.tree:
        if state.forbid_tree_removal:
            return _fail("trees", "Tree removal is forbidden on this scenario.")
        extra = 200
        t.tree = False
        t.scenery_id = None
    ok, msg = charge(state, PATH_COST + extra, why=f"path at ({x},{y})")
    if not ok:
        return _fail("no_cash", msg)
    t.kind = "path"
    t.scenery_id = None
    return _ok(f"Placed path at ({x},{y}) for {money_str(PATH_COST + extra)}.")


def act_remove_path(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    x, err = _need_int(parsed, "x")
    y, err2 = _need_int(parsed, "y")
    if err or err2:
        return _fail("bad_params", err or err2 or "")
    assert x is not None and y is not None
    if not state.in_bounds(x, y):
        return _fail("oob", f"({x},{y}) is off the map.")
    t = state.tile(x, y)
    if t.kind != "path":
        return _fail("not_path", f"({x},{y}) is {t.kind}, not a path.")
    ok, msg = charge(state, PATH_REMOVE_COST, why="remove path")
    if not ok:
        return _fail("no_cash", msg)
    t.kind = "empty"
    return _ok(f"Removed path at ({x},{y}).")


def act_buy_land(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    x, err = _need_int(parsed, "x")
    y, err2 = _need_int(parsed, "y")
    if err or err2:
        return _fail("bad_params", err or err2 or "")
    assert x is not None and y is not None
    if not state.in_bounds(x, y):
        return _fail("oob", f"({x},{y}) is off the map.")
    t = state.tile(x, y)
    if t.owned:
        return _fail("owned", f"({x},{y}) is already owned.")
    if t.kind == "water":
        return _fail("terrain", "Cannot buy a water tile.")
    # Must be adjacent to owned land (RCT land-buy rule, simplified).
    adj = False
    for nx, ny in neighbors(x, y):
        if state.in_bounds(nx, ny) and state.tile(nx, ny).owned:
            adj = True
            break
    if not adj:
        return _fail("not_adjacent", f"({x},{y}) is not adjacent to owned land.")
    ok, msg = charge(state, state.land_price, why=f"buy land ({x},{y})")
    if not ok:
        return _fail("no_cash", msg)
    t.owned = True
    t.construction_rights = True
    return _ok(f"Bought land at ({x},{y}) for {money_str(state.land_price)}.")


def act_place_ride(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    rid = parsed.get("ride_type") or parsed.get("id")
    if not rid or rid not in RIDES:
        known = ", ".join(sorted(RIDES))
        return _fail("unknown_ride", f"Unknown ride_type {rid!r}. Known: {known}.")
    if rid not in state.invented:
        nxt = state.research_next or "nothing"
        return _fail("not_researched", f"{RIDES[rid].name} is not invented yet. Currently researching {nxt}.")
    x, err = _need_int(parsed, "x")
    y, err2 = _need_int(parsed, "y")
    if err or err2:
        return _fail("bad_params", err or err2 or "")
    assert x is not None and y is not None
    spec = RIDES[rid]
    rotation = int(parsed.get("rotation") or 0)
    if rotation not in (0, 90, 180, 270):
        return _fail("bad_params", "rotation must be 0, 90, 180 or 270.")
    w, h = _dims(spec.footprint[0], spec.footprint[1], rotation)
    okf, msg = footprint_ok(state, x, y, w, h)
    if not okf:
        return _fail("placement", msg)
    extra = clear_footprint(state, x, y, w, h)
    cost = spec.build_cost + extra
    ok, msg = charge(state, cost, why=f"build {spec.name}")
    if not ok:
        return _fail("no_cash", msg)
    occupy(state, x, y, w, h, "ride", ride_id=state.next_ride_id)
    ride = RideInstance(
        id=state.next_ride_id,
        spec_id=rid,
        x=x,
        y=y,
        w=w,
        h=h,
        rotation=rotation,
        status="closed",
        price=spec.default_price,
        excitement=spec.excitement,
        intensity=spec.intensity,
        nausea=spec.nausea,
        name=spec.name,
    )
    state.next_ride_id += 1
    state.rides.append(ride)
    reachable = path_reachable(state)
    connected = adjacent_to_reachable_path(state, x, y, w, h, reachable)
    hint = "" if connected else " WARNING: no path from the entrance touches this ride yet."
    return _ok(
        f"Built {spec.name} #{ride.id} at ({x},{y}) {w}x{h} for {money_str(cost)}. "
        f"It is CLOSED. Open it with set_ride_status:{ride.id},open then set_park_open:true.{hint}",
        ride_id=ride.id,
        cost=cost,
    )


def act_place_stall(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    sid = parsed.get("stall_type") or parsed.get("id")
    if not sid or sid not in STALLS:
        return _fail("unknown_stall", f"Unknown stall_type {sid!r}. Known: {', '.join(sorted(STALLS))}.")
    if sid not in state.invented:
        return _fail("not_researched", f"{STALLS[sid].name} is not invented yet.")
    x, err = _need_int(parsed, "x")
    y, err2 = _need_int(parsed, "y")
    if err or err2:
        return _fail("bad_params", err or err2 or "")
    assert x is not None and y is not None
    spec = STALLS[sid]
    w, h = spec.footprint
    okf, msg = footprint_ok(state, x, y, w, h)
    if not okf:
        return _fail("placement", msg)
    extra = clear_footprint(state, x, y, w, h)
    cost = spec.build_cost + extra
    ok, cmsg = charge(state, cost, why=f"build {spec.name}")
    if not ok:
        return _fail("no_cash", cmsg)
    occupy(state, x, y, w, h, "stall", stall_id=state.next_stall_id)
    stall = StallInstance(
        id=state.next_stall_id,
        spec_id=sid,
        x=x,
        y=y,
        w=w,
        h=h,
        price=spec.default_price,
        name=spec.name,
    )
    state.next_stall_id += 1
    state.stalls.append(stall)
    return _ok(f"Built {spec.name} #{stall.id} at ({x},{y}) for {money_str(cost)}.", stall_id=stall.id)


def act_place_scenery(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    sid = parsed.get("scenery_type") or parsed.get("id")
    if not sid or sid not in SCENERY:
        return _fail("unknown_scenery", f"Unknown scenery_type {sid!r}.")
    x, err = _need_int(parsed, "x")
    y, err2 = _need_int(parsed, "y")
    if err or err2:
        return _fail("bad_params", err or err2 or "")
    assert x is not None and y is not None
    if not state.in_bounds(x, y):
        return _fail("oob", "Off map.")
    t = state.tile(x, y)
    if not t.owned:
        return _fail("unowned", "Not owned.")
    if t.kind not in ("empty", "scenery"):
        return _fail("occupied", f"Tile is {t.kind}.")
    spec = SCENERY[sid]
    ok, msg = charge(state, spec.build_cost, why=spec.name)
    if not ok:
        return _fail("no_cash", msg)
    t.kind = "scenery"
    t.scenery_id = sid
    t.tree = sid == "tree"
    return _ok(f"Placed {spec.name} at ({x},{y}).")


def act_demolish_ride(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    rid, err = _need_int(parsed, "ride_id")
    if err:
        return _fail("bad_params", err)
    ride = _find_ride(state, rid)
    if ride is None:
        return _fail("not_found", f"No ride #{rid}.")
    refund = ride.spec.build_cost // 4
    release(state, ride.x, ride.y, ride.w, ride.h)
    state.rides = [r for r in state.rides if r.id != ride.id]
    charge(state, -refund, why="demolish refund")
    return _ok(f"Demolished {ride.spec.name} #{ride.id}. Refund {money_str(refund)}.")


def act_demolish_stall(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    sid, err = _need_int(parsed, "stall_id")
    if err:
        return _fail("bad_params", err)
    stall = _find_stall(state, sid)
    if stall is None:
        return _fail("not_found", f"No stall #{sid}.")
    refund = stall.spec.build_cost // 4
    release(state, stall.x, stall.y, stall.w, stall.h)
    state.stalls = [s for s in state.stalls if s.id != stall.id]
    charge(state, -refund, why="demolish refund")
    return _ok(f"Demolished {stall.spec.name} #{stall.id}. Refund {money_str(refund)}.")


def act_set_ride_status(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    rid, err = _need_int(parsed, "ride_id")
    if err:
        return _fail("bad_params", err)
    status = str(parsed.get("status", "")).lower()
    if status not in ("open", "closed", "testing"):
        return _fail("bad_params", "status must be open, closed, or testing.")
    ride = _find_ride(state, rid)
    if ride is None:
        return _fail("not_found", f"No ride #{rid}.")
    ride.status = status  # type: ignore[assignment]
    if status == "testing":
        ride.tested = False
    if status == "open":
        ride.tested = True
    return _ok(f"{ride.spec.name} #{ride.id} is now {status}.")


def act_set_ride_price(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    rid, err = _need_int(parsed, "ride_id")
    price, err2 = _need_int(parsed, "price")
    if err or err2:
        return _fail("bad_params", err or err2 or "")
    assert price is not None
    if price < 0 or price > 2000:
        return _fail("bad_params", "Ride price must be 0–2000 pence (£0–£20.00).")
    ride = _find_ride(state, rid)
    if ride is None:
        return _fail("not_found", f"No ride #{rid}.")
    ride.price = price
    return _ok(f"{ride.spec.name} #{ride.id} price set to {money_str(price)}.")


def act_set_ride_name(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    rid, err = _need_int(parsed, "ride_id")
    if err:
        return _fail("bad_params", err)
    ride = _find_ride(state, rid)
    if ride is None:
        return _fail("not_found", f"No ride #{rid}.")
    name = str(parsed.get("name") or "").strip()[:32]
    if not name:
        return _fail("bad_params", "Name is empty.")
    ride.name = name
    return _ok(f"Ride #{ride.id} renamed to {name!r}.")


def act_set_stall_price(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    sid, err = _need_int(parsed, "stall_id")
    price, err2 = _need_int(parsed, "price")
    if err or err2:
        return _fail("bad_params", err or err2 or "")
    assert price is not None
    if price < 0 or price > 1000:
        return _fail("bad_params", "Stall price must be 0–1000 pence.")
    stall = _find_stall(state, sid)
    if stall is None:
        return _fail("not_found", f"No stall #{sid}.")
    stall.price = price
    return _ok(f"{stall.spec.name} #{stall.id} price set to {money_str(price)}.")


def act_hire_staff(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    kind = str(parsed.get("staff_type") or parsed.get("kind") or "").lower()
    if kind not in STAFF_HIRE_COST:
        return _fail("bad_params", f"staff_type must be one of {list(STAFF_HIRE_COST)}.")
    if sum(1 for s in state.staff if s.kind == kind) >= 12:
        return _fail("limit", f"Already have the maximum number of {kind}s.")
    cost = STAFF_HIRE_COST[kind]
    ok, msg = charge(state, cost, why=f"hire {kind}")
    if not ok:
        return _fail("no_cash", msg)
    ex, ey = state.entrance
    staff = Staff(
        id=state.next_staff_id,
        kind=kind,  # type: ignore[arg-type]
        x=ex,
        y=max(0, ey - 1),
        orders=_default_orders(kind),
        name=f"{kind.title()} {state.next_staff_id}",
    )
    state.next_staff_id += 1
    state.staff.append(staff)
    return _ok(
        f"Hired {kind} #{staff.id} for {money_str(cost)}. Monthly wage {money_str(STAFF_WAGE_MONTH[kind])}.",
        staff_id=staff.id,
    )


def _default_orders(kind: str) -> dict[str, bool]:
    if kind == "handyman":
        return {"sweeping": True, "watering": True, "emptying_bins": True, "mowing": True}
    if kind == "mechanic":
        return {"inspecting": True, "repairing": True}
    return {}


def act_fire_staff(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    sid, err = _need_int(parsed, "staff_id")
    if err:
        return _fail("bad_params", err)
    staff = next((s for s in state.staff if s.id == sid), None)
    if staff is None:
        return _fail("not_found", f"No staff #{sid}.")
    state.staff = [s for s in state.staff if s.id != sid]
    return _ok(f"Fired {staff.kind} #{sid}.")


def act_set_park_open(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    if "open" in parsed:
        open_ = bool(parsed["open"])
    else:
        open_ = True
    state.park_open = open_
    return _ok("Park is now OPEN." if open_ else "Park is now CLOSED.")


def act_set_entrance_fee(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    fee, err = _need_int(parsed, "fee")
    if err:
        return _fail("bad_params", err)
    assert fee is not None
    if fee < 0 or fee > 99900:
        return _fail("bad_params", "Entrance fee must be 0–99900 pence.")
    state.entrance_fee = fee
    return _ok(f"Entrance fee set to {money_str(fee)}.")


def act_set_loan(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    loan, err = _need_int(parsed, "loan")
    if err:
        return _fail("bad_params", err)
    assert loan is not None
    if loan < 0 or loan > state.max_loan:
        return _fail("bad_params", f"Loan must be between 0 and {money_str(state.max_loan)}.")
    # Loan is quantized to £1000 like RCT.
    loan = (loan // 100000) * 100000
    delta = loan - state.loan
    state.loan = loan
    charge(state, -delta, why="loan")
    return _ok(f"Loan set to {money_str(loan)}. Cash is now {money_str(state.cash)}.")


def act_set_research_funding(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    level = str(parsed.get("level") or "").lower()
    if level not in RESEARCH_FUNDING:
        return _fail("bad_params", f"level must be one of {list(RESEARCH_FUNDING)}.")
    state.research_funding = level
    return _ok(f"Research funding set to {level} ({money_str(RESEARCH_FUNDING[level])}/month).")


def act_start_marketing(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    kind = str(parsed.get("campaign") or parsed.get("kind") or "")
    if kind not in MARKETING_CAMPAIGNS:
        return _fail("bad_params", f"campaign must be one of {list(MARKETING_CAMPAIGNS)}.")
    if any(c.kind == kind for c in state.campaigns):
        return _fail("duplicate", f"{kind} campaign is already running.")
    spec = MARKETING_CAMPAIGNS[kind]
    ok, msg = charge(state, spec["cost"], why=spec["name"])
    if not ok:
        return _fail("no_cash", msg)
    state.campaigns.append(Campaign(kind=kind, weeks_left=spec["weeks"]))
    return _ok(f"Started {spec['name']} for {money_str(spec['cost'])} ({spec['weeks']} weeks).")


def act_set_park_name(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    name = str(parsed.get("name") or "").strip()[:48]
    if not name:
        return _fail("bad_params", "Name is empty.")
    state.park_name = name
    return _ok(f"Park renamed to {name!r}.")


def _positive_int(parsed: dict[str, Any], key: str, default: int) -> int:
    if key not in parsed or parsed[key] is None or parsed[key] == "":
        return default
    return int(parsed[key])


def act_wait(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    months = _positive_int(parsed, "months", 1)
    if months < 1 or months > 16:
        return _fail("bad_params", "wait months must be 1–16.")
    before = (state.months_elapsed, state.num_guests, state.cash, state.rating)
    simulate_months(state, months)
    logging_util.log_event(
        "game.wait",
        session=state.session_id,
        requested_months=months,
        months_elapsed=state.months_elapsed,
        day=state.day,
        guests=state.num_guests,
        cash=state.cash,
        rating=state.rating,
        result=state.result,
    )
    return _ok(
        f"Advanced {months} month(s) to {state.day} {state.month_name} Year {state.year} "
        f"(months_elapsed {before[0]}→{state.months_elapsed}). "
        f"Guests {before[1]}→{state.num_guests}, cash {money_str(before[2])}→{money_str(state.cash)}, "
        f"rating {before[3]}→{state.rating}. Result={state.result}.",
        months=months,
        months_elapsed=state.months_elapsed,
    )


def act_wait_days(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    days = _positive_int(parsed, "days", 1)
    if days < 1 or days > 62:
        return _fail("bad_params", "wait_days must be 1–62.")
    simulate_days(state, days)
    return _ok(f"Advanced {days} day(s) to {state.day} {state.month_name} Year {state.year}. Result={state.result}.")


def act_wait_weeks(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    weeks = _positive_int(parsed, "weeks", 1)
    if weeks < 1 or weeks > 16:
        return _fail("bad_params", "wait_weeks must be 1–16.")
    simulate_days(state, weeks * 7)
    return _ok(f"Advanced {weeks} week(s). Result={state.result}.")


def act_inspect_tile(state: GameState, parsed: dict[str, Any]) -> dict[str, Any]:
    x, err = _need_int(parsed, "x")
    y, err2 = _need_int(parsed, "y")
    if err or err2:
        return _fail("bad_params", err or err2 or "")
    assert x is not None and y is not None
    if not state.in_bounds(x, y):
        return _fail("oob", "Off map.")
    t = state.tile(x, y)
    info = {
        "x": x,
        "y": y,
        "kind": t.kind,
        "owned": t.owned,
        "litter": t.litter,
        "tree": t.tree,
        "scenery_id": t.scenery_id,
        "ride_id": t.ride_id,
        "stall_id": t.stall_id,
        "height": t.height,
    }
    return _ok(f"Tile ({x},{y}): {info}", tile=info)


def _find_ride(state: GameState, rid: Optional[int]) -> Optional[RideInstance]:
    if rid is None:
        return None
    return next((r for r in state.rides if r.id == rid), None)


def _find_stall(state: GameState, sid: Optional[int]) -> Optional[StallInstance]:
    if sid is None:
        return None
    return next((s for s in state.stalls if s.id == sid), None)


ACTIONS = {
    "place_path": act_place_path,
    "remove_path": act_remove_path,
    "buy_land": act_buy_land,
    "place_ride": act_place_ride,
    "place_stall": act_place_stall,
    "place_scenery": act_place_scenery,
    "demolish_ride": act_demolish_ride,
    "demolish_stall": act_demolish_stall,
    "set_ride_status": act_set_ride_status,
    "set_ride_price": act_set_ride_price,
    "set_ride_name": act_set_ride_name,
    "set_stall_price": act_set_stall_price,
    "hire_staff": act_hire_staff,
    "fire_staff": act_fire_staff,
    "set_park_open": act_set_park_open,
    "set_entrance_fee": act_set_entrance_fee,
    "set_loan": act_set_loan,
    "set_research_funding": act_set_research_funding,
    "start_marketing": act_start_marketing,
    "set_park_name": act_set_park_name,
    "wait": act_wait,
    "wait_months": act_wait,
    "wait_days": act_wait_days,
    "wait_weeks": act_wait_weeks,
    "inspect_tile": act_inspect_tile,
}
