"""Enumerate currently legal actions for a GameState."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from .catalog import MARKETING_CAMPAIGNS, RESEARCH_FUNDING, RIDES, SCENERY, STAFF_HIRE_COST, STALLS
from .engine import (
    GameState,
    adjacent_to_reachable_path,
    footprint_ok,
    money_str,
    neighbors,
    path_reachable,
)


def _tile_group_key(action: dict[str, Any]) -> str:
    aid = str(action.get("id", action.get("type")))
    typ = action.get("type")
    if typ in ("place_ride", "place_stall", "place_scenery"):
        return aid.rsplit(",", 2)[0]
    return str(typ)


def _trim_tile_actions(tile: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    """Keep path-adjacent-first order inside each type, but reserve ≥1 origin per group."""
    if len(tile) <= budget:
        return tile
    groups: dict[str, deque] = defaultdict(deque)
    order: list[str] = []
    for a in tile:
        key = _tile_group_key(a)
        if key not in groups:
            order.append(key)
        groups[key].append(a)
    out: list[dict[str, Any]] = []
    for key in order:
        if groups[key] and len(out) < budget:
            out.append(groups[key].popleft())
    progressed = True
    while len(out) < budget and progressed:
        progressed = False
        for key in order:
            if groups[key] and len(out) < budget:
                out.append(groups[key].popleft())
                progressed = True
    return out


def list_legal_actions(state: GameState, *, max_tile_actions: int = 800) -> dict[str, Any]:
    """Return grouped + flattened legal actions. Always includes wait / inspect / finance."""
    if state.result != "undecided":
        inspect = {
            "id": f"inspect_tile:{state.entrance[0]},{state.entrance[1]}",
            "type": "inspect_tile",
            "params": {"x": state.entrance[0], "y": state.entrance[1]},
            "description": f"Inspect a tile (game is over; reset() to start a new park)",
        }
        return {
            "game_over": True,
            "result": state.result,
            "result_reason": state.result_reason,
            "count": 1,
            "actions": [inspect],
            "actions_flat": [inspect["id"]],
            "action_types": [{"type": "inspect_tile", "params": {"x": "int", "y": "int"}}],
            "truncated": False,
            "text": (
                f"Game over ({state.result}): {state.result_reason}. "
                "Call reset() to start a new park. inspect_tile still works."
            ),
        }

    actions: list[dict[str, Any]] = []
    path_tiles: list[list[int]] = []
    remove_tiles: list[list[int]] = []
    buy_tiles: list[list[int]] = []
    empty_owned: list[list[int]] = []

    for y in range(state.map_h):
        for x in range(state.map_w):
            t = state.tile(x, y)
            if t.kind == "path":
                remove_tiles.append([x, y])
            if t.owned and t.kind in ("empty", "scenery") and t.kind != "entrance":
                if t.kind == "empty" or t.tree:
                    path_tiles.append([x, y])
                    empty_owned.append([x, y])
            if (not t.owned) and t.kind != "water":
                for nx, ny in neighbors(x, y):
                    if state.in_bounds(nx, ny) and state.tile(nx, ny).owned:
                        buy_tiles.append([x, y])
                        break

    def _near(p: list[int]) -> int:
        return abs(p[0] - state.entrance[0]) + abs(p[1] - state.entrance[1])

    reachable = path_reachable(state)

    def _path_rank(p: list[int]) -> tuple[int, int]:
        x, y = p
        adj = any((nx, ny) in reachable for nx, ny in neighbors(x, y))
        return (0 if adj else 1, _near(p))

    path_tiles.sort(key=_path_rank)
    remove_tiles.sort(key=_near)
    buy_tiles.sort(key=_near)
    empty_owned.sort(key=_path_rank)
    for x, y in path_tiles:
        actions.append(
            {
                "id": f"place_path:{x},{y}",
                "type": "place_path",
                "params": {"x": x, "y": y},
                "cost": 1000,
                "description": f"Place path at ({x},{y}) for {money_str(1000)}",
            }
        )
    for x, y in remove_tiles:
        actions.append(
            {
                "id": f"remove_path:{x},{y}",
                "type": "remove_path",
                "params": {"x": x, "y": y},
                "description": f"Remove path at ({x},{y})",
            }
        )
    for x, y in buy_tiles:
        actions.append(
            {
                "id": f"buy_land:{x},{y}",
                "type": "buy_land",
                "params": {"x": x, "y": y},
                "cost": state.land_price,
                "description": f"Buy land ({x},{y}) for {money_str(state.land_price)}",
            }
        )

    invented_rides = [RIDES[i] for i in state.invented if i in RIDES]
    invented_stalls = [STALLS[i] for i in state.invented if i in STALLS]
    ride_origins: dict[str, list[list[int]]] = {}
    for spec in invented_rides:
        if spec.build_cost > state.cash + 50_000:
            # still list a few so the agent knows it exists
            origins: list[list[int]] = []
        else:
            origins = []
            w, h = spec.footprint
            for y in range(state.map_h - h + 1):
                for x in range(state.map_w - w + 1):
                    ok, _ = footprint_ok(state, x, y, w, h)
                    if ok:
                        origins.append([x, y])
            origins.sort(
                key=lambda p, ww=spec.footprint[0], hh=spec.footprint[1]: (
                    0 if adjacent_to_reachable_path(state, p[0], p[1], ww, hh, reachable) else 1,
                    abs(p[0] - state.entrance[0]) + abs(p[1] - state.entrance[1]),
                )
            )
        ride_origins[spec.id] = origins
        # Cap per-ride origin listing in the flat list to keep it usable.
        for x, y in origins[:40]:
            actions.append(
                {
                    "id": f"place_ride:{spec.id},{x},{y}",
                    "type": "place_ride",
                    "params": {"ride_type": spec.id, "x": x, "y": y, "rotation": 0},
                    "cost": spec.build_cost,
                    "description": (
                        f"Build {spec.name} ({w}x{h}, {spec.category}) at ({x},{y}) "
                        f"for {money_str(spec.build_cost)} — E{spec.excitement/100:.2f} "
                        f"I{spec.intensity/100:.2f} N{spec.nausea/100:.2f}"
                    ),
                }
            )

    stall_origins: dict[str, list[list[int]]] = {}
    for spec in invented_stalls:
        origins = []
        w, h = spec.footprint
        for y in range(state.map_h - h + 1):
            for x in range(state.map_w - w + 1):
                ok, _ = footprint_ok(state, x, y, w, h)
                if ok:
                    origins.append([x, y])
        origins.sort(
            key=lambda p, ww=spec.footprint[0], hh=spec.footprint[1]: (
                0 if adjacent_to_reachable_path(state, p[0], p[1], ww, hh, reachable) else 1,
                abs(p[0] - state.entrance[0]) + abs(p[1] - state.entrance[1]),
            )
        )
        stall_origins[spec.id] = origins
        for x, y in origins[:30]:
            actions.append(
                {
                    "id": f"place_stall:{spec.id},{x},{y}",
                    "type": "place_stall",
                    "params": {"stall_type": spec.id, "x": x, "y": y},
                    "cost": spec.build_cost,
                    "description": f"Build {spec.name} at ({x},{y}) for {money_str(spec.build_cost)}",
                }
            )

    for spec in SCENERY.values():
        for x, y in empty_owned[:20]:
            actions.append(
                {
                    "id": f"place_scenery:{spec.id},{x},{y}",
                    "type": "place_scenery",
                    "params": {"scenery_type": spec.id, "x": x, "y": y},
                    "cost": spec.build_cost,
                    "description": f"Place {spec.name} at ({x},{y})",
                }
            )

    for ride in state.rides:
        actions.append(
            {
                "id": f"set_ride_status:{ride.id},open",
                "type": "set_ride_status",
                "params": {"ride_id": ride.id, "status": "open"},
                "description": f"Open {ride.spec.name} #{ride.id}",
            }
        )
        if ride.status != "closed":
            actions.append(
                {
                    "id": f"set_ride_status:{ride.id},closed",
                    "type": "set_ride_status",
                    "params": {"ride_id": ride.id, "status": "closed"},
                    "description": f"Close {ride.spec.name} #{ride.id}",
                }
            )
        for p in (0, 50, 80, 100, 120, 150, 200, 250, 300, 400):
            actions.append(
                {
                    "id": f"set_ride_price:{ride.id},{p}",
                    "type": "set_ride_price",
                    "params": {"ride_id": ride.id, "price": p},
                    "description": f"Set {ride.spec.name} #{ride.id} price to {money_str(p)}",
                }
            )
        actions.append(
            {
                "id": f"demolish_ride:{ride.id}",
                "type": "demolish_ride",
                "params": {"ride_id": ride.id},
                "description": f"Demolish {ride.spec.name} #{ride.id}",
            }
        )

    for stall in state.stalls:
        for p in (0, 50, 80, 90, 100, 120, 150):
            actions.append(
                {
                    "id": f"set_stall_price:{stall.id},{p}",
                    "type": "set_stall_price",
                    "params": {"stall_id": stall.id, "price": p},
                    "description": f"Set {stall.spec.name} #{stall.id} price to {money_str(p)}",
                }
            )
        actions.append(
            {
                "id": f"demolish_stall:{stall.id}",
                "type": "demolish_stall",
                "params": {"stall_id": stall.id},
                "description": f"Demolish {stall.spec.name} #{stall.id}",
            }
        )

    for kind in STAFF_HIRE_COST:
        actions.append(
            {
                "id": f"hire_staff:{kind}",
                "type": "hire_staff",
                "params": {"staff_type": kind},
                "cost": STAFF_HIRE_COST[kind],
                "description": f"Hire a {kind} for {money_str(STAFF_HIRE_COST[kind])}",
            }
        )
    for s in state.staff:
        actions.append(
            {
                "id": f"fire_staff:{s.id}",
                "type": "fire_staff",
                "params": {"staff_id": s.id},
                "description": f"Fire {s.kind} #{s.id}",
            }
        )

    actions.append(
        {
            "id": f"set_park_open:{str(not state.park_open).lower()}",
            "type": "set_park_open",
            "params": {"open": (not state.park_open)},
            "description": "Close the park" if state.park_open else "OPEN the park (guests can enter)",
        }
    )
    for fee in (0, 200, 500, 1000, 1500, 2000, 3000):
        actions.append(
            {
                "id": f"set_entrance_fee:{fee}",
                "type": "set_entrance_fee",
                "params": {"fee": fee},
                "description": f"Set entrance fee to {money_str(fee)}",
            }
        )
    for level in RESEARCH_FUNDING:
        actions.append(
            {
                "id": f"set_research_funding:{level}",
                "type": "set_research_funding",
                "params": {"level": level},
                "description": f"Research funding: {level}",
            }
        )
    for camp, spec in MARKETING_CAMPAIGNS.items():
        if not any(c.kind == camp for c in state.campaigns):
            actions.append(
                {
                    "id": f"start_marketing:{camp}",
                    "type": "start_marketing",
                    "params": {"campaign": camp},
                    "cost": spec["cost"],
                    "description": f"{spec['name']} ({money_str(spec['cost'])}, {spec['weeks']} weeks)",
                }
            )
    step = 100000
    for loan in range(0, state.max_loan + 1, step):
        if loan != state.loan:
            actions.append(
                {
                    "id": f"set_loan:{loan}",
                    "type": "set_loan",
                    "params": {"loan": loan},
                    "description": f"Set loan to {money_str(loan)}",
                }
            )

    for n in (1, 2, 3, 4):
        actions.append(
            {
                "id": f"wait:{n}",
                "type": "wait",
                "params": {"months": n},
                "description": f"Advance {n} month(s) of park simulation",
            }
        )
    actions.append(
        {
            "id": "wait_days:7",
            "type": "wait_days",
            "params": {"days": 7},
            "description": "Advance 1 week",
        }
    )
    actions.append(
        {
            "id": f"inspect_tile:{state.entrance[0]},{state.entrance[1]}",
            "type": "inspect_tile",
            "params": {"x": state.entrance[0], "y": state.entrance[1]},
            "description": f"Inspect the entrance tile {state.entrance} (any in-bounds x,y is legal)",
        }
    )

    TILE_TYPES = {"place_path", "remove_path", "buy_land", "place_ride", "place_stall", "place_scenery"}
    core = [a for a in actions if a["type"] not in TILE_TYPES]
    tile = [a for a in actions if a["type"] in TILE_TYPES]
    budget = max(0, max_tile_actions - len(core))
    truncated = len(tile) > budget
    if truncated:
        tile = _trim_tile_actions(tile, budget)
    actions = tile + core

    text_lines = [
        f"{len(actions)} legal actions. Build a connected # path from the entrance {state.entrance} FIRST.",
        "Place toilets/drinks/food and rides so they TOUCH a reachable # path, then hire handyman+mechanic, OPEN the park, wait.",
        "If you place a building on grass with no adjacent #, guests cannot use it (rating will collapse).",
        f"Path tiles you can pave (nearest-to-entrance first): {len(path_tiles)} (ids place_path:x,y).",
        f"Buyable land plots: {len(buy_tiles)}.",
        f"Invented rides: {', '.join(s.id for s in invented_rides)}.",
        f"Invented stalls: {', '.join(s.id for s in invented_stalls)}.",
        f"Walkable tiles from E (includes the entrance plus #): {len(reachable)}.",
        "You may also pass JSON: {\"type\":\"place_ride\",\"ride_type\":\"merry_go_round\",\"x\":7,\"y\":10} "
        "(or just use the id strings below).",
        "Suggested ride/stall origins in the flat list are sorted path-adjacent first; later ids of the same type may NOT touch a path.",
    ]
    if truncated:
        text_lines.append(
            f"Tile-placement ids were truncated (cap {max_tile_actions}; {len(core)} management actions kept). "
            "At least one origin per invented ride/stall type is reserved."
        )
    action_types = [
        {
            "type": "place_path",
            "params": {"x": "int", "y": "int"},
            "valid_tiles": path_tiles,
        },
        {
            "type": "place_ride",
            "params": {"ride_type": "str", "x": "int", "y": "int", "rotation": "0|90"},
            "rides": [
                {
                    "id": s.id,
                    "name": s.name,
                    "cost": s.build_cost,
                    "footprint": list(s.footprint),
                    "category": s.category,
                    "excitement": s.excitement,
                    "intensity": s.intensity,
                    "nausea": s.nausea,
                }
                for s in invented_rides
            ],
            "origins": ride_origins,
        },
        {
            "type": "place_stall",
            "params": {"stall_type": "str", "x": "int", "y": "int"},
            "stalls": [
                {"id": s.id, "name": s.name, "cost": s.build_cost, "kind": s.kind} for s in invented_stalls
            ],
            "origins": stall_origins,
        },
        {"type": "wait", "params": {"months": "1-16"}},
        {"type": "set_park_open", "params": {"open": "bool"}},
        {"type": "hire_staff", "params": {"staff_type": list(STAFF_HIRE_COST)}},
        {"type": "inspect_tile", "params": {"x": "int", "y": "int"}},
    ]
    return {
        "game_over": False,
        "result": state.result,
        "count": len(actions),
        "actions": actions,
        "actions_flat": [a["id"] for a in actions],
        "action_types": action_types,
        "truncated": truncated,
        "text": "\n".join(text_lines),
    }
