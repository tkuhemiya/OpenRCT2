"""Human-readable text renderer for a park. No images — ASCII + HUD only."""

from __future__ import annotations

from .catalog import MONTH_COUNT, MONTHS, RIDES, STALLS
from .engine import GameState, money_str, path_reachable, rating_str


LEGEND = (
    "E entrance  # clean path  ; light litter  % dirty path  "
    "R ride  T toilets  D drinks  F food  I info  + first-aid  B balloon  U umbrella  $ other stall  "
    "^ tree  ~ water  . owned grass  , unowned  o bin  * garden  h bench"
)


def render_text(state: GameState) -> str:
    obj = state.objective
    deadline = obj.get("month_deadline", obj.get("year", 1) * MONTH_COUNT)
    remaining = max(0, deadline - state.months_elapsed)
    obj_line = _objective_line(state)
    date_line = (
        f"Date: {state.day} {state.month_name}, Year {state.year}   "
        + (
            f"(GAME OVER — {state.result}; this is the finish date, not a live deadline)"
            if state.result != "undecided"
            else (
                f"(month {state.months_elapsed + 1}/{deadline or '?'} of scenario, "
                f"{remaining} months left; last scoring month is {_deadline_name(deadline)})"
            )
        )
    )
    warn_lines = [f"  WARN: {w}" for w in state.warnings] if state.warnings else ["  (none)"]
    lines = [
        "=== OpenRCT2 agent state (text only) ===",
        f"Scenario: {state.park_name} ({state.scenario_id})   seed={state.seed}",
        date_line,
        f"Status: {state.result.upper()}" + (f" — {state.result_reason}" if state.result_reason else ""),
        f"Objective: {obj_line}",
        "",
        f"Park: {state.park_name!r}   {'OPEN' if state.park_open else 'CLOSED'}   weather={state.weather}",
        f"Cash: {money_str(state.cash)}   Loan: {money_str(state.loan)} / max {money_str(state.max_loan)}   "
        f"Interest {state.interest_rate}%/yr",
        f"Park value: {money_str(state.park_value)}   Company value: {money_str(state.company_value)}   "
        f"Entry fee: {money_str(state.entrance_fee)}",
        f"Guests in park: {state.num_guests}   Admissions: {state.total_admissions}   "
        f"Admission income: {money_str(state.admission_income)}   Suggested max: {state.suggested_guest_max}",
        f"Park rating: {state.rating}/999   Guest-gen/day score: {state.guest_generation_probability}   "
        f"Avg happiness: {_avg_happy(state)}/255   Litter: {_litter(state)}",
        f"Last month: ride income {money_str(state.last_month_ride_income)}   "
        f"shop income {money_str(state.last_month_food_income)}",
        "",
        _rides_block(state),
        _stalls_block(state),
        _staff_block(state),
        _research_block(state),
        _campaigns_block(state),
        "",
        "News (latest last):",
        *("  - " + n.text for n in state.news[-8:]),
        "",
        "Warnings / coach notes:",
        "  TIP: Rides and stalls only work if they TOUCH a # path connected to E. Isolated buildings are useless.",
        "  TIP: E is on the south edge. Pave # NORTH (smaller y). x grows east.",
        *warn_lines,
        "",
        f"Map {state.map_w}x{state.map_h}  (x grows east, y grows south; entrance at {state.entrance})",
        f"Legend: {LEGEND}",
        *render_map(state),
        "",
        f"Walkable from entrance: {len(path_reachable(state))} tiles (includes E plus connected # paths).",
        _guest_sample(state),
    ]
    return "\n".join(lines)


def render_map(state: GameState) -> list[str]:
    tens = "    " + "".join(str(x // 10) for x in range(state.map_w))
    ones = "y\\x " + "".join(str(x % 10) for x in range(state.map_w))
    rows = [tens, ones]
    for y in range(state.map_h):
        cells = []
        for x in range(state.map_w):
            cells.append(_glyph(state, x, y))
        rows.append(f"{y:3d} " + "".join(cells))
    return rows


def _glyph(state: GameState, x: int, y: int) -> str:
    t = state.tile(x, y)
    if t.kind == "entrance":
        return "E"
    if t.kind == "path":
        return "#" if t.litter == 0 else (";" if t.litter == 1 else "%")
    if t.kind == "ride":
        return "R"
    if t.kind == "stall":
        stall = next((s for s in state.stalls if s.id == t.stall_id), None)
        if stall:
            return stall.spec.symbol
        return "$"
    if t.kind == "water":
        return "~"
    if t.kind == "scenery" or t.tree:
        sid = t.scenery_id or "tree"
        if sid == "tree":
            return "^"
        if sid == "garden":
            return "*"
        if sid == "bench":
            return "h"
        if sid == "lamp":
            return "!"
        if sid == "bin":
            return "o"
        return "*"
    return "." if t.owned else ","


def _deadline_name(deadline: int) -> str:
    if not deadline:
        return "the time cap"
    idx = (deadline - 1) % MONTH_COUNT
    year = (deadline - 1) // MONTH_COUNT + 1
    return f"{MONTHS[idx]} Year {year}"


def _objective_line(state: GameState) -> str:
    obj = state.objective
    typ = obj.get("type")
    deadline = obj.get("month_deadline", obj.get("year", 1) * MONTH_COUNT)
    when = _deadline_name(deadline)
    if typ == "guests_by":
        return (
            f"Attract {obj['num_guests']} guests with rating ≥ {obj['min_rating']} "
            f"by the end of {when} (now {state.num_guests} guests, rating {state.rating})."
        )
    if typ == "park_value_by":
        gap = max(0, obj["currency"] - state.park_value)
        return (
            f"Reach park value {money_str(obj['currency'])} by the end of {when} "
            f"(now {money_str(state.park_value)}, short {money_str(gap)})."
        )
    if typ == "have_fun":
        return f"Have fun (sandbox). Avoid bankruptcy until {when}."
    if typ == "guests_and_rating":
        return f"Maintain {obj['num_guests']} guests and rating ≥ 700 by {when}."
    if typ == "repay_loan_and_park_value":
        return (
            f"Repay the loan and reach park value {money_str(obj.get('currency', 0))} by {when}."
        )
    return str(obj)


def _avg_happy(state: GameState) -> int:
    if not state.guests:
        return 0
    return sum(g.happiness for g in state.guests) // len(state.guests)


def _litter(state: GameState) -> int:
    return sum(t.litter for row in state.tiles for t in row)


def _rides_block(state: GameState) -> str:
    if not state.rides:
        return "Rides: (none)"
    lines = [f"Rides ({len(state.rides)}):"]
    for r in state.rides:
        lines.append(
            f"  #{r.id} {r.name or r.spec.name} [{r.spec_id}] {r.status.upper()}  "
            f"{r.w}x{r.h}@({r.x},{r.y})  "
            f"E {rating_str(r.excitement)}  I {rating_str(r.intensity)}  N {rating_str(r.nausea)}  "
            f"price {money_str(r.price)}  downtime {r.downtime}%  "
            f"customers {r.customers_total} (month {r.customers_month})  "
            f"income {money_str(r.income_total)}  breakdowns {r.breakdowns}"
        )
    return "\n".join(lines)


def _stalls_block(state: GameState) -> str:
    if not state.stalls:
        return "Stalls: (none)"
    lines = [f"Stalls ({len(state.stalls)}):"]
    for s in state.stalls:
        lines.append(
            f"  #{s.id} {s.name or s.spec.name} [{s.spec_id}/{s.spec.kind}] @({s.x},{s.y})  "
            f"price {money_str(s.price)}  customers {s.customers_total}  income {money_str(s.income_total)}"
        )
    return "\n".join(lines)


def _staff_block(state: GameState) -> str:
    if not state.staff:
        return "Staff: (none)"
    bits = [f"{s.kind} #{s.id}" for s in state.staff]
    return "Staff (" + str(len(state.staff)) + "): " + ", ".join(bits)


def _research_block(state: GameState) -> str:
    nxt = state.research_next
    nxt_name = RIDES[nxt].name if nxt in RIDES else (STALLS[nxt].name if nxt in STALLS else nxt)
    invented_rides = [f"{RIDES[i].name} [{i}]" for i in sorted(state.invented) if i in RIDES]
    invented_stalls = [f"{STALLS[i].name} [{i}]" for i in sorted(state.invented) if i in STALLS]
    return (
        f"Research: funding={state.research_funding}  progress={state.research_progress}/100  "
        f"next={nxt_name}\n"
        f"  Invented rides: {', '.join(invented_rides)}\n"
        f"  Invented stalls: {', '.join(invented_stalls)}"
    )


def _campaigns_block(state: GameState) -> str:
    if not state.campaigns:
        return "Marketing: (none)"
    return "Marketing: " + ", ".join(f"{c.kind} ({c.weeks_left}w left)" for c in state.campaigns)


def _guest_sample(state: GameState) -> str:
    if not state.guests:
        return "Guest sample: (park empty)"
    sample = state.guests[:6]
    bits = [
        f"#{g.id} $={g.cash} hap={g.happiness} hun={g.hunger} thi={g.thirst} toi={g.toilet} nau={g.nausea}"
        for g in sample
    ]
    lost = sum(1 for g in state.guests if g.lost)
    return f"Guest sample ({len(sample)}/{state.num_guests}, lost={lost}): " + " | ".join(bits)


def structured_state(state: GameState) -> dict:
    reachable = sorted(path_reachable(state))
    return {
        "seed": state.seed,
        "scenario_id": state.scenario_id,
        "park_name": state.park_name,
        "date": {
            "day": state.day,
            "month": state.month_name,
            "month_index": state.month_index,
            "year": state.year,
            "months_elapsed": state.months_elapsed,
            "ticks": state.ticks,
        },
        "result": state.result,
        "result_reason": state.result_reason,
        "game_over": state.result != "undecided",
        "park_open": state.park_open,
        "weather": state.weather,
        "finance": {
            "cash": state.cash,
            "loan": state.loan,
            "max_loan": state.max_loan,
            "interest_rate": state.interest_rate,
            "entrance_fee": state.entrance_fee,
            "park_value": state.park_value,
            "company_value": state.company_value,
            "admission_income": state.admission_income,
            "last_month_ride_income": state.last_month_ride_income,
            "last_month_food_income": state.last_month_food_income,
        },
        "guests": {
            "in_park": state.num_guests,
            "admissions": state.total_admissions,
            "avg_happiness": _avg_happy(state),
            "lost": sum(1 for g in state.guests if g.lost),
            "suggested_max": state.suggested_guest_max,
            "generation_score": state.guest_generation_probability,
        },
        "rating": state.rating,
        "objective": dict(state.objective),
        "rides": [
            {
                "id": r.id,
                "spec_id": r.spec_id,
                "name": r.name or r.spec.name,
                "status": r.status,
                "x": r.x,
                "y": r.y,
                "w": r.w,
                "h": r.h,
                "price": r.price,
                "excitement": r.excitement,
                "intensity": r.intensity,
                "nausea": r.nausea,
                "downtime": r.downtime,
                "customers_total": r.customers_total,
                "income_total": r.income_total,
                "breakdowns": r.breakdowns,
                "is_coaster": r.spec.is_coaster,
                "track_length": r.spec.track_length,
            }
            for r in state.rides
        ],
        "stalls": [
            {
                "id": s.id,
                "spec_id": s.spec_id,
                "name": s.name or s.spec.name,
                "kind": s.spec.kind,
                "x": s.x,
                "y": s.y,
                "price": s.price,
                "customers_total": s.customers_total,
                "income_total": s.income_total,
            }
            for s in state.stalls
        ],
        "staff": [{"id": s.id, "kind": s.kind, "x": s.x, "y": s.y, "orders": s.orders} for s in state.staff],
        "research": {
            "funding": state.research_funding,
            "progress": state.research_progress,
            "next": state.research_next,
            "invented": sorted(state.invented),
            "queue": list(state.research_queue[:12]),
        },
        "campaigns": [{"kind": c.kind, "weeks_left": c.weeks_left} for c in state.campaigns],
        "map": {
            "width": state.map_w,
            "height": state.map_h,
            "entrance": list(state.entrance),
            "ascii": render_map(state),
            "reachable_path_count": len(reachable),
            "litter": _litter(state),
        },
        "warnings": list(state.warnings),
        "news": [n.text for n in state.news[-12:]],
    }
