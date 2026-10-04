"""Deterministic RCT2-style park simulation.

Mirrors OpenRCT2 `GameState_t`, `Park::ParkData`, `CalculateParkRating`,
scenario objectives, and the March–October calendar in Date.h.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from .catalog import (
    DAYS_IN_MONTH,
    MARKETING_CAMPAIGNS,
    MONTH_COUNT,
    MONTHS,
    PATH_COST,
    RESEARCH_FUNDING,
    RESEARCH_PROGRESS,
    RIDES,
    SCENERY,
    STAFF_HIRE_COST,
    STAFF_WAGE_MONTH,
    STALLS,
    ScenarioSpec,
    invented_at_start,
    research_queue,
)

TileKind = Literal["empty", "path", "entrance", "ride", "stall", "scenery", "water"]
StaffType = Literal["handyman", "mechanic", "security", "entertainer"]
RideStatus = Literal["closed", "testing", "open"]
ResultStatus = Literal["undecided", "success", "failure"]


def money_str(pence: int) -> str:
    sign = "-" if pence < 0 else ""
    pence = abs(pence)
    return f"{sign}£{pence // 100:,}.{pence % 100:02d}"


def rating_str(hundredths: int) -> str:
    return f"{hundredths // 100}.{hundredths % 100:02d}"


@dataclass
class Tile:
    kind: TileKind = "empty"
    owned: bool = False
    construction_rights: bool = False
    height: int = 2  # RCT-style, unused visually but in structured state
    litter: int = 0  # 0-3
    scenery_id: Optional[str] = None
    ride_id: Optional[int] = None
    stall_id: Optional[int] = None
    tree: bool = False


@dataclass
class RideInstance:
    id: int
    spec_id: str
    x: int
    y: int
    w: int
    h: int
    rotation: int
    status: RideStatus = "closed"
    price: int = 100
    excitement: int = 0
    intensity: int = 0
    nausea: int = 0
    downtime: int = 0  # 0-100
    breakdowns: int = 0
    customers_total: int = 0
    income_total: int = 0
    customers_month: int = 0
    income_month: int = 0
    tested: bool = False
    last_inspection_day: int = 0
    queue: int = 0
    name: str = ""

    @property
    def spec(self):
        return RIDES[self.spec_id]


@dataclass
class StallInstance:
    id: int
    spec_id: str
    x: int
    y: int
    w: int
    h: int
    price: int = 100
    customers_total: int = 0
    income_total: int = 0
    customers_month: int = 0
    income_month: int = 0
    name: str = ""

    @property
    def spec(self):
        return STALLS[self.spec_id]


@dataclass
class Staff:
    id: int
    kind: StaffType
    x: int
    y: int
    orders: dict[str, bool] = field(default_factory=dict)
    name: str = ""


@dataclass
class Guest:
    id: int
    cash: int
    happiness: int = 128  # 0-255
    energy: int = 200
    hunger: int = 80
    thirst: int = 80
    toilet: int = 40
    nausea: int = 0
    rides_today: int = 0
    days_in_park: int = 0
    umbrellas: int = 0
    map_bought: bool = False
    leaving: bool = False
    lost: bool = False
    x: int = 0
    y: int = 0
    rides_ridden: set[int] = field(default_factory=set)


@dataclass
class Campaign:
    kind: str
    weeks_left: int


@dataclass
class NewsItem:
    month: int
    text: str


@dataclass
class GameState:
    seed: int
    scenario_id: str
    rng: random.Random = field(repr=False)
    map_w: int = 18
    map_h: int = 16
    tiles: list[list[Tile]] = field(default_factory=list)
    months_elapsed: int = 0
    day: int = 1
    ticks: int = 0
    park_name: str = "Park"
    park_open: bool = False
    cash: int = 0
    loan: int = 0
    max_loan: int = 0
    interest_rate: int = 10
    entrance_fee: int = 1000
    rating: int = 500
    park_value: int = 0
    company_value: int = 0
    guests: list[Guest] = field(default_factory=list)
    next_guest_id: int = 1
    total_admissions: int = 0
    admission_income: int = 0
    rides: list[RideInstance] = field(default_factory=list)
    stalls: list[StallInstance] = field(default_factory=list)
    staff: list[Staff] = field(default_factory=list)
    next_ride_id: int = 0
    next_stall_id: int = 0
    next_staff_id: int = 0
    invented: set[str] = field(default_factory=set)
    research_queue: list[str] = field(default_factory=list)
    research_funding: str = "normal"
    research_progress: int = 0
    research_next: Optional[str] = None
    campaigns: list[Campaign] = field(default_factory=list)
    news: list[NewsItem] = field(default_factory=list)
    weather: str = "sunny"
    result: ResultStatus = "undecided"
    result_reason: str = ""
    casualties: int = 0
    rating_casualty_penalty: int = 0
    monthly_ride_income: int = 0
    monthly_food_income: int = 0
    last_month_ride_income: int = 0
    last_month_food_income: int = 0
    suggested_guest_max: int = 400
    guest_generation_probability: int = 0
    land_price: int = 9000
    forbid_tree_removal: bool = False
    no_money: bool = False
    guest_initial_cash: int = 5000
    entrance: tuple[int, int] = (8, 15)
    objective: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    month_start_cash: int = 0
    weekly_profit: int = 0

    @property
    def year(self) -> int:
        return self.months_elapsed // MONTH_COUNT + 1

    @property
    def month_index(self) -> int:
        return self.months_elapsed % MONTH_COUNT

    @property
    def month_name(self) -> str:
        return MONTHS[self.month_index]

    @property
    def num_guests(self) -> int:
        return len(self.guests)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.map_w and 0 <= y < self.map_h

    def tile(self, x: int, y: int) -> Tile:
        return self.tiles[y][x]


def new_game(seed: int, scenario: ScenarioSpec) -> GameState:
    rng = random.Random(seed)
    w, h = scenario.map_w, scenario.map_h
    entrance_x = w // 2
    entrance_y = h - 1
    tiles = [[Tile() for _ in range(w)] for _ in range(h)]
    margin = scenario.owned_margin
    for y in range(h):
        for x in range(w):
            t = tiles[y][x]
            owned = margin <= x < w - margin and margin <= y < h - 1
            t.owned = owned
            t.construction_rights = owned
            # Scatter trees on unowned and a few owned tiles (Forest Frontiers feel).
            if rng.random() < (0.18 if not owned else 0.06):
                t.tree = True
                t.kind = "scenery"
                t.scenery_id = "tree"
            if rng.random() < 0.04 and y < h - 3:
                t.kind = "water"
                t.owned = False
                t.tree = False
                t.scenery_id = None

    # Park entrance + a short welcome path.
    tiles[entrance_y][entrance_x] = Tile(kind="entrance", owned=True, construction_rights=True)
    for dy in range(1, 4):
        yy = entrance_y - dy
        if 0 <= yy < h:
            tiles[yy][entrance_x] = Tile(kind="path", owned=True, construction_rights=True)

    invented = invented_at_start(scenario)
    queue = research_queue(invented)
    state = GameState(
        seed=seed,
        scenario_id=scenario.id,
        rng=rng,
        map_w=w,
        map_h=h,
        tiles=tiles,
        park_name=scenario.name,
        park_open=scenario.park_open,
        cash=scenario.starting_cash,
        loan=scenario.starting_loan,
        max_loan=scenario.max_loan,
        interest_rate=scenario.interest_rate,
        entrance_fee=scenario.entrance_fee,
        invented=invented,
        research_queue=queue,
        research_next=queue[0] if queue else None,
        suggested_guest_max=scenario.suggested_guest_max,
        land_price=scenario.land_price,
        forbid_tree_removal=scenario.forbid_tree_removal,
        no_money=scenario.no_money,
        guest_initial_cash=scenario.guest_initial_cash,
        entrance=(entrance_x, entrance_y),
        objective={
            "type": scenario.objective_type,
            "year": scenario.year,
            "num_guests": scenario.num_guests,
            "currency": scenario.currency,
            "min_rating": 600,
        },
        month_start_cash=scenario.starting_cash,
    )
    # Gentle intro: 4-month deadline (end of June Year 1) encoded as year=0.
    if scenario.id == "gentle_intro":
        state.objective["month_deadline"] = 4
    else:
        state.objective["month_deadline"] = scenario.year * MONTH_COUNT
    _recalculate(state)
    _push_news(state, f"Welcome to {scenario.name}. {scenario.details}")
    return state


def _push_news(state: GameState, text: str) -> None:
    state.news.append(NewsItem(month=state.months_elapsed, text=text))
    if len(state.news) > 24:
        state.news = state.news[-24:]


def footprint_ok(state: GameState, x: int, y: int, w: int, h: int, *, allow_trees: bool = False) -> tuple[bool, str]:
    if w <= 0 or h <= 0:
        return False, "Footprint must be positive."
    if not state.in_bounds(x, y) or not state.in_bounds(x + w - 1, y + h - 1):
        return False, f"Footprint ({x},{y}) {w}x{h} is off the map ({state.map_w}x{state.map_h})."
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            t = state.tile(xx, yy)
            if not t.owned:
                return False, f"Tile ({xx},{yy}) is not owned. Buy land first."
            if t.kind == "entrance":
                return False, f"Cannot build on the park entrance at ({xx},{yy})."
            if t.kind in ("ride", "stall"):
                return False, f"Tile ({xx},{yy}) is occupied by an existing building."
            if t.kind == "path":
                return False, f"Tile ({xx},{yy}) has a path. Remove it first."
            if t.kind == "water":
                return False, f"Tile ({xx},{yy}) is water."
            if t.tree and not allow_trees:
                if state.forbid_tree_removal:
                    return False, f"Tree removal is forbidden; ({xx},{yy}) has a tree."
                # Trees can be cleared as part of construction (cost applied by caller).
    return True, ""


def clear_footprint(state: GameState, x: int, y: int, w: int, h: int) -> int:
    """Clear scenery/trees in footprint. Returns extra cost in pence."""
    extra = 0
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            t = state.tile(xx, yy)
            if t.tree or t.kind == "scenery":
                extra += SCENERY.get(t.scenery_id or "tree", SCENERY["tree"]).build_cost // 4
                t.tree = False
                t.scenery_id = None
                t.kind = "empty"
            t.litter = 0
    return extra


def occupy(state: GameState, x: int, y: int, w: int, h: int, kind: TileKind, **ids: int) -> None:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            t = state.tile(xx, yy)
            t.kind = kind
            t.tree = False
            t.scenery_id = None
            t.ride_id = ids.get("ride_id")
            t.stall_id = ids.get("stall_id")


def release(state: GameState, x: int, y: int, w: int, h: int) -> None:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            t = state.tile(xx, yy)
            t.kind = "empty"
            t.ride_id = None
            t.stall_id = None
            t.scenery_id = None
            t.tree = False


def neighbors(x: int, y: int) -> list[tuple[int, int]]:
    return [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]


def path_reachable(state: GameState) -> set[tuple[int, int]]:
    """BFS from entrance across path/entrance tiles."""
    ex, ey = state.entrance
    start = (ex, ey)
    seen = {start}
    q = [start]
    i = 0
    while i < len(q):
        x, y = q[i]
        i += 1
        for nx, ny in neighbors(x, y):
            if not state.in_bounds(nx, ny) or (nx, ny) in seen:
                continue
            k = state.tile(nx, ny).kind
            if k in ("path", "entrance"):
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def adjacent_to_reachable_path(state: GameState, x: int, y: int, w: int, h: int, reachable: set[tuple[int, int]]) -> bool:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            for nx, ny in neighbors(xx, yy):
                if (nx, ny) in reachable:
                    return True
    return False


def charge(state: GameState, amount: int, *, why: str) -> tuple[bool, str]:
    if state.no_money or amount == 0:
        return True, ""
    if amount > 0 and state.cash < amount:
        return False, f"Not enough cash for {why}: need {money_str(amount)}, have {money_str(state.cash)}."
    state.cash -= amount
    return True, ""


def _ride_value_for_money(ride: RideInstance) -> int:
    # Rough OpenRCT2-inspired value: excitement-driven, reduced by downtime.
    base = ride.excitement * 2 + ride.spec.capacity
    return max(0, int(base * (100 - ride.downtime) / 100))


def calculate_park_rating(state: GameState) -> int:
    """Port of OpenRCT2 Park.cpp CalculateParkRating (simplified inputs)."""
    result = 1150
    # Guests: -150 to +3 based on 0..2000 guests
    result -= 150 - (min(2000, state.num_guests) // 13)

    happy = sum(1 for g in state.guests if g.happiness > 128)
    lost = sum(1 for g in state.guests if g.lost)
    result -= 500
    if state.num_guests > 0:
        result += 2 * min(250, (happy * 300) // state.num_guests)

    if lost > 25:
        result -= (lost - 25) * 7

    ride_count = 0
    exciting = 0
    total_uptime = 0
    total_int = 0
    total_exc = 0
    for ride in state.rides:
        if ride.status == "open":
            ride_count += 1
            total_uptime += 100 - ride.downtime
            if ride.tested or ride.status == "open":
                total_exc += ride.excitement // 8
                total_int += ride.intensity // 8
                exciting += 1
    result -= 200
    if ride_count > 0:
        result += (total_uptime // ride_count) * 2
    result -= 100
    if exciting > 0:
        avg_e = total_exc // exciting
        avg_i = total_int // exciting
        avg_e = min(abs(avg_e - 46) // 2, 50)
        avg_i = min(abs(avg_i - 65) // 2, 50)
        result += 100 - avg_e - avg_i
    total_exc = min(1000, total_exc)
    total_int = min(1000, total_int)
    result -= 200 - ((total_exc + total_int) // 10)

    litter = sum(t.litter for row in state.tiles for t in row)
    # OpenRCT2 only penalises *old* litter heavily. Scale gently so a busy park
    # with a couple of dirty tiles does not instantly drop 600 rating points.
    result -= min(180, litter * 6)
    result -= state.rating_casualty_penalty
    return max(0, min(999, result))


def calculate_park_value(state: GameState) -> int:
    result = 0
    for ride in state.rides:
        result += ride.spec.build_cost // 4
        result += ride.excitement * 80
    for stall in state.stalls:
        result += stall.spec.build_cost // 5
    result += state.num_guests * 700  # £7.00 per guest
    return result


def _recalculate(state: GameState) -> None:
    state.rating = calculate_park_rating(state)
    state.park_value = calculate_park_value(state)
    state.company_value = state.park_value - state.loan + state.cash
    open_rides = [r for r in state.rides if r.status == "open"]
    ride_value = sum(_ride_value_for_money(r) for r in open_rides if r.downtime < 85)
    # Guest generation: OpenRCT2 uses a 0..65535 probability per tick.
    # We convert to "guests per day" later. Store a 0-1000 score here.
    rating_factor = max(0, state.rating - 200)
    fee_penalty = 0
    if state.entrance_fee > 0:
        # Overpriced entry vs ride value.
        if ride_value > 0 and state.entrance_fee > ride_value * 4:
            fee_penalty = 40
        elif state.entrance_fee > 2500:
            fee_penalty = 25
    weather_mod = {"sunny": 10, "cloudy": 0, "rain": -20, "storm": -45}.get(state.weather, 0)
    campaign_bonus = sum(MARKETING_CAMPAIGNS[c.kind]["guest_bonus"] for c in state.campaigns if c.kind in MARKETING_CAMPAIGNS)
    path_ok = 1 if len(path_reachable(state)) > 3 else 0
    gen = 0
    if state.park_open and path_ok:
        gen = 14 + rating_factor // 16 + ride_value // 45 + campaign_bonus + weather_mod - fee_penalty
        if state.num_guests > state.suggested_guest_max:
            gen = gen // 3
        gen = max(0, min(120, gen))
    state.guest_generation_probability = gen
    _update_warnings(state, open_rides, ride_value)


def _update_warnings(state: GameState, open_rides: list[RideInstance], ride_value: int) -> None:
    w: list[str] = []
    if not state.park_open:
        w.append("The park is CLOSED. Guests will not enter. Use set_park_open:true.")
    reachable = path_reachable(state)
    unreachable = []
    for ride in state.rides:
        if not adjacent_to_reachable_path(state, ride.x, ride.y, ride.w, ride.h, reachable):
            unreachable.append(f"{ride.name or ride.spec.name} #{ride.id}")
    for stall in state.stalls:
        if not adjacent_to_reachable_path(state, stall.x, stall.y, stall.w, stall.h, reachable):
            unreachable.append(f"{stall.name or stall.spec.name} #{stall.id}")
    if unreachable:
        w.append("No path from the entrance to: " + ", ".join(unreachable[:8]) + ". Guests cannot use them.")
    if not any(s.spec.kind == "food" for s in state.stalls):
        w.append("No food stall. Hungry guests will leave unhappy.")
    if not any(s.spec.kind == "drink" for s in state.stalls):
        w.append("No drinks stall. Thirsty guests will leave unhappy.")
    if not any(s.spec_id == "toilets" for s in state.stalls):
        w.append("No toilets. Guests will get uncomfortable.")
    if state.rides and not any(s.kind == "mechanic" for s in state.staff):
        w.append("No mechanic. Rides will break down and stay closed.")
    if not any(s.kind == "handyman" for s in state.staff) and state.num_guests > 5:
        w.append("No handyman. Litter will tank park rating.")
    if not open_rides:
        w.append("No open rides. Guests have nothing to do.")
    elif ride_value < 80:
        w.append("Ride value is low. Build more (or more exciting) attractions.")
    if state.cash < 50_000:
        w.append("Cash is running low. Consider a loan, higher prices, or slower building.")
    if state.weather in ("rain", "storm") and not any(s.spec_id == "umbrella_stall" for s in state.stalls):
        w.append("It is raining and there is no umbrella stall.")
    broken = [r for r in state.rides if r.downtime >= 60]
    if broken:
        w.append("Broken / high-downtime rides: " + ", ".join(f"#{r.id} {r.spec.name}" for r in broken[:6]))
    state.warnings = w


def simulate_days(state: GameState, days: int) -> None:
    if state.result != "undecided":
        return
    for _ in range(days):
        _simulate_day(state)
        if state.result != "undecided":
            return


def simulate_months(state: GameState, months: int) -> None:
    if state.result != "undecided":
        return
    for _ in range(months):
        days = DAYS_IN_MONTH[state.month_index]
        # Remaining days this month, then full months.
        remaining = days - state.day + 1
        simulate_days(state, remaining)
        if state.result != "undecided":
            return


def _simulate_day(state: GameState) -> None:
    state.ticks += 40
    _update_weather(state)
    _staff_work(state)
    _spawn_guests(state)
    _simulate_guests(state)
    _update_rides(state)
    _recalculate(state)
    _check_objective(state)
    _check_bankruptcy(state)
    if state.result != "undecided":
        return
    days = DAYS_IN_MONTH[state.month_index]
    state.day += 1
    if state.day > days:
        state.day = 1
        _end_of_month(state)


def _update_weather(state: GameState) -> None:
    roll = state.rng.randrange(100)
    month = state.month_index
    # Spring/autumn wetter.
    rain_chance = 18 if month in (0, 1, 6, 7) else 10
    if roll < 4:
        state.weather = "storm"
    elif roll < rain_chance:
        state.weather = "rain"
    elif roll < rain_chance + 35:
        state.weather = "cloudy"
    else:
        state.weather = "sunny"


def _staff_work(state: GameState) -> None:
    handymen = [s for s in state.staff if s.kind == "handyman"]
    mechanics = [s for s in state.staff if s.kind == "mechanic"]
    # Sweep litter: each handyman clears several dirty path tiles.
    dirty = [(x, y) for y, row in enumerate(state.tiles) for x, t in enumerate(row) if t.litter > 0]
    state.rng.shuffle(dirty)
    i = 0
    for _h in handymen:
        for _ in range(14):
            if i >= len(dirty):
                break
            x, y = dirty[i]
            i += 1
            t = state.tile(x, y)
            t.litter = max(0, t.litter - 2)
    # Mechanics reduce downtime / finish repairs.
    for ride in state.rides:
        if mechanics:
            ride.downtime = max(0, ride.downtime - 12 * len(mechanics))
            ride.last_inspection_day = state.months_elapsed * 31 + state.day
        else:
            # Slow self-repair only if not fully broken.
            if 0 < ride.downtime < 60:
                ride.downtime = max(0, ride.downtime - 1)
    # Entertainers bump nearby happiness (park-wide small bump).
    ents = sum(1 for s in state.staff if s.kind == "entertainer")
    if ents and state.guests:
        bump = min(8, ents * 2)
        for g in state.guests:
            g.happiness = min(255, g.happiness + bump)


def _spawn_guests(state: GameState) -> None:
    if not state.park_open:
        return
    n = state.guest_generation_probability
    extra = 1 if state.rng.randrange(100) < (n % 3) * 25 else 0
    spawn = max(0, (n * 2) // 3 + extra)
    if state.weather == "rain":
        spawn = max(0, spawn - 1)
    if state.weather == "storm":
        spawn = max(0, spawn // 2)
    reachable = path_reachable(state)
    ex, ey = state.entrance
    spawn_tile = (ex, ey - 1) if (ex, ey - 1) in reachable else (ex, ey)
    for _ in range(spawn):
        if state.entrance_fee > 0 and not state.no_money:
            # Guests refuse overpriced gates.
            if state.rng.randrange(100) < min(80, state.entrance_fee // 80):
                if state.rating < 650:
                    continue
            ok, _ = charge(state, -state.entrance_fee, why="admission")  # negative = income
            if ok:
                state.admission_income += state.entrance_fee
        g = Guest(
            id=state.next_guest_id,
            cash=max(200, state.guest_initial_cash + state.rng.randint(-1500, 2000)),
            happiness=state.rng.randint(110, 160),
            energy=state.rng.randint(160, 230),
            hunger=state.rng.randint(40, 120),
            thirst=state.rng.randint(40, 120),
            toilet=state.rng.randint(10, 80),
            x=spawn_tile[0],
            y=spawn_tile[1],
        )
        state.next_guest_id += 1
        state.guests.append(g)
        state.total_admissions += 1


def _simulate_guests(state: GameState) -> None:
    reachable = path_reachable(state)
    open_rides = [
        r
        for r in state.rides
        if r.status == "open"
        and r.downtime < 80
        and adjacent_to_reachable_path(state, r.x, r.y, r.w, r.h, reachable)
    ]
    stalls = [s for s in state.stalls if adjacent_to_reachable_path(state, s.x, s.y, s.w, s.h, reachable)]
    food = [s for s in stalls if s.spec.kind == "food"]
    drink = [s for s in stalls if s.spec.kind == "drink"]
    toilets = [s for s in stalls if s.spec_id == "toilets"]
    first_aid = [s for s in stalls if s.spec_id == "first_aid"]
    umbrellas = [s for s in stalls if s.spec_id == "umbrella_stall"]
    infos = [s for s in stalls if s.spec_id == "information_kiosk"]
    cash_machines = [s for s in stalls if s.spec_id == "cash_machine"]
    souvenirs = [s for s in stalls if s.spec.kind == "souvenir" and s.spec_id != "umbrella_stall"]

    leaving: list[Guest] = []
    for g in state.guests:
        g.days_in_park += 1
        g.hunger = min(255, g.hunger + state.rng.randint(8, 18))
        g.thirst = min(255, g.thirst + state.rng.randint(8, 18))
        g.toilet = min(255, g.toilet + state.rng.randint(6, 14))
        g.energy = max(0, g.energy - state.rng.randint(10, 20))
        g.nausea = max(0, g.nausea - 15)
        if state.weather in ("rain", "storm") and g.umbrellas <= 0:
            g.happiness = max(0, g.happiness - (12 if state.weather == "rain" else 22))

        # Needs
        if g.hunger > 160 and food:
            _use_stall(state, g, food)
        elif g.thirst > 160 and drink:
            _use_stall(state, g, drink)
        elif g.toilet > 170 and toilets:
            _use_stall(state, g, toilets, free=True)
            g.toilet = 10
            g.happiness = min(255, g.happiness + 6)
        elif g.nausea > 140 and first_aid:
            g.nausea = 20
            g.happiness = min(255, g.happiness + 8)
        elif state.weather in ("rain", "storm") and g.umbrellas <= 0 and umbrellas:
            if _use_stall(state, g, umbrellas):
                g.umbrellas = 1
        elif g.cash < 80 and cash_machines:
            g.cash += 2500
        elif not g.map_bought and infos and state.rng.random() < 0.15:
            if _use_stall(state, g, infos):
                g.map_bought = True
                g.lost = False
                g.happiness = min(255, g.happiness + 4)
        elif souvenirs and g.happiness > 160 and g.cash > 1500 and state.rng.random() < 0.08:
            _use_stall(state, g, souvenirs)

        # Unmet needs punish happiness.
        if g.hunger > 200 and not food:
            g.happiness = max(0, g.happiness - 18)
        if g.thirst > 200 and not drink:
            g.happiness = max(0, g.happiness - 16)
        if g.toilet > 210 and not toilets:
            g.happiness = max(0, g.happiness - 12)

        # Ride
        if open_rides and g.energy > 40 and g.happiness > 40 and g.rides_today < 4:
            candidates = [r for r in open_rides if r.id not in g.rides_ridden or state.rng.random() < 0.35]
            if not candidates:
                candidates = open_rides
            # Prefer rides matching intensity preference (around 4.00-6.50).
            ride = state.rng.choice(candidates)
            too_intense = ride.intensity > 650 and g.happiness < 140
            too_pricey = ride.price > 0 and g.cash < ride.price
            value_ok = ride.price <= max(50, ride.excitement * 2 + 40)
            if too_intense:
                g.happiness = max(0, g.happiness - 6)
            elif too_pricey or not value_ok:
                g.happiness = max(0, g.happiness - 4)
            else:
                if ride.price and not state.no_money:
                    g.cash -= ride.price
                    ride.income_total += ride.price
                    ride.income_month += ride.price
                    state.cash += ride.price
                    state.monthly_ride_income += ride.price
                ride.customers_total += 1
                ride.customers_month += 1
                g.rides_ridden.add(ride.id)
                g.rides_today += 1
                g.energy = max(0, g.energy - 25)
                g.nausea = min(255, g.nausea + ride.nausea // 8)
                # Happiness from a good ride.
                gain = 12 + ride.excitement // 40 - (8 if ride.intensity > 600 else 0)
                g.happiness = max(0, min(255, g.happiness + gain))
                g.x, g.y = ride.x, ride.y
                # Queue / litter by the ride.
                rx, ry = ride.x, ride.y
                if state.in_bounds(rx, ry + ride.h) and state.tile(rx, ry + ride.h).kind == "path":
                    if state.rng.random() < 0.05:
                        state.tile(rx, ry + ride.h).litter = min(3, state.tile(rx, ry + ride.h).litter + 1)

        # Lost if they cannot find anything.
        if not open_rides:
            g.happiness = max(0, g.happiness - 8)
            if g.days_in_park >= 2:
                g.lost = True

        g.rides_today = 0
        # Leave?
        stay_cap = 7 + (5 if g.happiness > 140 else 1) + min(5, len(g.rides_ridden))
        if (
            g.leaving
            or g.happiness < 35
            or g.energy < 20
            or g.cash < 40
            or g.days_in_park >= stay_cap
            or (state.weather == "storm" and g.umbrellas <= 0 and g.days_in_park >= 1)
        ):
            leaving.append(g)

    if leaving:
        leave_set = set(id(g) for g in leaving)
        state.guests = [g for g in state.guests if id(g) not in leave_set]


def _use_stall(state: GameState, g: Guest, stalls: list[StallInstance], *, free: bool = False) -> bool:
    stall = state.rng.choice(stalls)
    price = 0 if free else stall.price
    if price and g.cash < price:
        return False
    if price and not state.no_money:
        g.cash -= price
        stall.income_total += price
        stall.income_month += price
        state.cash += price
        if stall.spec.kind in ("food", "drink"):
            state.monthly_food_income += price
    stall.customers_total += 1
    stall.customers_month += 1
    if stall.spec.kind == "food":
        g.hunger = max(0, g.hunger - 140)
        g.thirst = min(255, g.thirst + 20)
        g.toilet = min(255, g.toilet + 25)
        g.happiness = min(255, g.happiness + 8)
    elif stall.spec.kind == "drink":
        g.thirst = max(0, g.thirst - 150)
        g.happiness = min(255, g.happiness + 6)
        g.toilet = min(255, g.toilet + 20)
    g.x, g.y = stall.x, stall.y
    return True


def _update_rides(state: GameState) -> None:
    for ride in state.rides:
        if ride.status == "testing":
            ride.tested = True
            ride.status = "open"
            _push_news(
                state,
                f"{ride.spec.name} #{ride.id} test complete: "
                f"E {rating_str(ride.excitement)} / I {rating_str(ride.intensity)} / N {rating_str(ride.nausea)}.",
            )
        if ride.status != "open":
            continue
        # Breakdown chance from reliability.
        chance = max(1, 8 - ride.spec.reliability // 20)
        if state.rng.randrange(100) < chance:
            ride.downtime = min(100, ride.downtime + state.rng.randint(8, 22))
            ride.breakdowns += 1
            if ride.downtime >= 70:
                _push_news(state, f"{ride.spec.name} #{ride.id} has broken down.")
        # Tiny rating jitter after open, still deterministic.
        jitter = state.rng.randint(-4, 4)
        ride.excitement = max(40, ride.spec.excitement + jitter)
        ride.intensity = max(10, ride.spec.intensity + state.rng.randint(-3, 3))
        ride.nausea = max(5, ride.spec.nausea + state.rng.randint(-3, 3))


def _end_of_month(state: GameState) -> None:
    # Wages + running costs + interest + research.
    wages = sum(STAFF_WAGE_MONTH[s.kind] for s in state.staff)
    running = sum(r.spec.running_cost_month for r in state.rides if r.status != "closed")
    running += sum(s.spec.running_cost_month for s in state.stalls)
    research = RESEARCH_FUNDING.get(state.research_funding, 0)
    interest = (state.loan * state.interest_rate) // (100 * MONTH_COUNT) if state.loan else 0
    total = wages + running + research + interest
    if not state.no_money:
        state.cash -= total
    state.weekly_profit = (state.cash - state.month_start_cash)
    state.month_start_cash = state.cash

    _advance_research(state)
    for c in state.campaigns:
        c.weeks_left -= 4
    state.campaigns = [c for c in state.campaigns if c.weeks_left > 0]

    state.last_month_ride_income = state.monthly_ride_income
    state.last_month_food_income = state.monthly_food_income
    state.monthly_ride_income = 0
    state.monthly_food_income = 0
    for r in state.rides:
        r.customers_month = 0
        r.income_month = 0
    for s in state.stalls:
        s.customers_month = 0
        s.income_month = 0

    state.months_elapsed += 1
    _recalculate(state)
    _push_news(
        state,
        f"End of {MONTHS[(state.months_elapsed - 1) % MONTH_COUNT]} Year {((state.months_elapsed - 1) // MONTH_COUNT) + 1}: "
        f"cash {money_str(state.cash)}, guests {state.num_guests}, rating {state.rating}, "
        f"costs {money_str(total)} (wages {money_str(wages)}, running {money_str(running)}, "
        f"research {money_str(research)}, interest {money_str(interest)}).",
    )
    _check_objective(state)
    _check_bankruptcy(state)


def _advance_research(state: GameState) -> None:
    pts = RESEARCH_PROGRESS.get(state.research_funding, 0)
    if pts <= 0 or not state.research_next:
        return
    state.research_progress += pts
    if state.research_progress >= 100:
        unlocked = state.research_next
        state.invented.add(unlocked)
        state.research_progress = 0
        if state.research_queue and state.research_queue[0] == unlocked:
            state.research_queue.pop(0)
        elif unlocked in state.research_queue:
            state.research_queue.remove(unlocked)
        state.research_next = state.research_queue[0] if state.research_queue else None
        name = RIDES[unlocked].name if unlocked in RIDES else STALLS.get(unlocked, type("T", (), {"name": unlocked})).name
        _push_news(state, f"Research complete: {name} is now available to build.")


def _check_objective(state: GameState) -> None:
    if state.result != "undecided":
        return
    obj = state.objective
    typ = obj["type"]
    deadline = obj.get("month_deadline", obj["year"] * MONTH_COUNT)
    hit_deadline = state.months_elapsed >= deadline

    def succeed(reason: str) -> None:
        state.result = "success"
        state.result_reason = reason
        _push_news(state, "SCENARIO COMPLETE: " + reason)

    def fail(reason: str) -> None:
        state.result = "failure"
        state.result_reason = reason
        _push_news(state, "SCENARIO FAILED: " + reason)

    if typ == "guests_by":
        if state.rating >= obj["min_rating"] and state.num_guests >= obj["num_guests"]:
            succeed(
                f"{state.num_guests} guests with rating {state.rating} "
                f"(needed {obj['num_guests']} guests and rating {obj['min_rating']})."
            )
            return
        if hit_deadline:
            fail(
                f"Time up. Guests {state.num_guests}/{obj['num_guests']}, rating {state.rating}/{obj['min_rating']}."
            )
    elif typ == "park_value_by":
        if state.park_value >= obj["currency"]:
            succeed(f"Park value {money_str(state.park_value)} reached target {money_str(obj['currency'])}.")
            return
        if hit_deadline:
            fail(f"Time up. Park value {money_str(state.park_value)} / {money_str(obj['currency'])}.")
    elif typ == "guests_and_rating":
        if state.rating >= 700 and state.num_guests >= obj["num_guests"]:
            succeed(f"{state.num_guests} guests with rating {state.rating}.")
            return
        if hit_deadline:
            fail("Could not keep guests and rating high enough.")
    elif typ == "repay_loan_and_park_value":
        if state.loan <= 0 and state.park_value >= obj["currency"]:
            succeed(f"Loan repaid and park value {money_str(state.park_value)}.")
            return
        if hit_deadline:
            fail(f"Loan {money_str(state.loan)}, park value {money_str(state.park_value)}.")
    elif typ == "have_fun":
        if hit_deadline:
            succeed("You had fun for the full sandbox duration.")


def _check_bankruptcy(state: GameState) -> None:
    if state.result != "undecided" or state.no_money:
        return
    if state.cash < -400_000:
        state.result = "failure"
        state.result_reason = f"Bankrupt (cash {money_str(state.cash)})."
        _push_news(state, "SCENARIO FAILED: The bank has foreclosed on the park.")
