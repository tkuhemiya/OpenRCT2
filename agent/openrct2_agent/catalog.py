"""RCT2-style catalogs: rides, stalls, scenery, research groups.

Costs and ratings are approximate RCT2 values (pence; ratings in hundredths,
so 600 == 6.00 excitement). Footprints are complete prebuilt layouts so a
text agent never has to place individual track pieces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


RideCategory = Literal["transport", "gentle", "rollercoaster", "thrill", "water", "shop"]
StallKind = Literal["food", "drink", "souvenir", "facility"]


@dataclass(frozen=True)
class RideSpec:
    id: str
    name: str
    category: RideCategory
    footprint: tuple[int, int]  # width, height (rotation 90 swaps)
    build_cost: int  # pence
    running_cost_month: int
    excitement: int  # hundredths
    intensity: int
    nausea: int
    capacity: int  # guests per day at 100% uptime, one unit
    reliability: int  # 0-100, higher = fewer breakdowns
    default_price: int  # pence
    research_group: RideCategory
    start_invented: bool = False
    is_coaster: bool = False
    track_length: int = 0  # metres, for coaster-length objectives


@dataclass(frozen=True)
class StallSpec:
    id: str
    name: str
    kind: StallKind
    footprint: tuple[int, int]
    build_cost: int
    running_cost_month: int
    default_price: int
    start_invented: bool = True
    symbol: str = "$"


@dataclass(frozen=True)
class ScenerySpec:
    id: str
    name: str
    build_cost: int
    symbol: str
    kind: str  # tree, garden, bench, lamp, bin


RIDES: dict[str, RideSpec] = {
    spec.id: spec
    for spec in [
        RideSpec("merry_go_round", "Merry-Go-Round", "gentle", (2, 2), 31200, 4000, 120, 60, 50, 28, 92, 100, "gentle", True),
        RideSpec("ferris_wheel", "Ferris Wheel", "gentle", (2, 2), 45500, 5200, 152, 70, 55, 24, 90, 120, "gentle", True),
        RideSpec("observation_tower", "Observation Tower", "gentle", (1, 1), 49200, 4800, 185, 48, 40, 18, 88, 150, "gentle", True),
        RideSpec("haunted_house", "Haunted House", "gentle", (3, 3), 42000, 4500, 248, 82, 62, 32, 94, 150, "gentle", True),
        RideSpec("circus", "Circus", "gentle", (3, 3), 51000, 6200, 138, 40, 30, 36, 96, 150, "gentle", False),
        RideSpec("crooked_house", "Crooked House", "gentle", (2, 2), 36000, 3200, 128, 38, 24, 20, 95, 90, "gentle", False),
        RideSpec("maze", "Hedge Maze", "gentle", (4, 4), 56000, 2800, 176, 58, 18, 40, 98, 80, "gentle", False),
        RideSpec("dodgems", "Dodgems", "gentle", (4, 4), 72000, 7000, 218, 92, 48, 36, 86, 150, "gentle", False),
        RideSpec("ghost_train", "Ghost Train", "gentle", (4, 3), 84000, 7600, 318, 148, 122, 34, 84, 180, "gentle", False),
        RideSpec("car_ride", "Car Ride", "gentle", (4, 3), 68000, 5400, 198, 42, 22, 30, 90, 120, "gentle", True),
        RideSpec("spiral_slide", "Spiral Slide", "gentle", (2, 2), 27500, 1800, 108, 78, 38, 22, 96, 70, "gentle", True),
        RideSpec("miniature_railway", "Miniature Railway", "transport", (5, 3), 82000, 6000, 220, 32, 18, 40, 93, 100, "transport", True),
        RideSpec("monorail", "Monorail", "transport", (5, 3), 118000, 8200, 248, 38, 20, 42, 91, 120, "transport", False),
        RideSpec("chairlift", "Chairlift", "transport", (5, 2), 74000, 5800, 205, 52, 28, 28, 87, 90, "transport", False),
        RideSpec("twist", "Twist", "thrill", (2, 2), 48500, 5600, 278, 348, 318, 26, 82, 180, "thrill", False),
        RideSpec("scrambler", "Scrambler", "thrill", (3, 3), 54000, 6000, 252, 302, 278, 28, 84, 160, "thrill", False),
        RideSpec("motion_simulator", "Motion Simulator", "thrill", (2, 2), 56000, 7200, 288, 322, 298, 24, 88, 200, "thrill", False),
        RideSpec("cinema_3d", "3D Cinema", "thrill", (3, 3), 62000, 7800, 242, 178, 152, 40, 94, 180, "thrill", False),
        RideSpec("go_karts", "Go-Karts", "thrill", (4, 4), 98000, 9000, 382, 248, 118, 22, 80, 220, "thrill", False),
        RideSpec("swinging_ship", "Swinging Ship", "thrill", (5, 2), 64000, 6800, 268, 338, 308, 30, 83, 180, "thrill", False),
        RideSpec("gravitron", "Gravitron", "thrill", (3, 3), 72000, 8200, 352, 682, 618, 24, 78, 250, "thrill", False),
        RideSpec("top_spin", "Top Spin", "thrill", (3, 3), 76000, 8600, 322, 598, 572, 22, 76, 240, "thrill", False),
        RideSpec("enterprise", "Enterprise", "thrill", (3, 3), 92000, 9800, 378, 748, 682, 20, 74, 260, "thrill", False),
        RideSpec("boat_hire", "Boat Hire", "water", (4, 4), 42000, 3600, 148, 28, 18, 26, 95, 80, "water", False),
        RideSpec("dinghy_slide", "Dinghy Slide", "water", (4, 3), 92000, 7200, 348, 238, 178, 28, 85, 200, "water", False),
        RideSpec("log_flume", "Log Flume", "water", (5, 4), 148000, 9800, 422, 278, 218, 32, 82, 240, "water", False),
        RideSpec("river_rapids", "River Rapids", "water", (5, 5), 186000, 12000, 478, 318, 248, 30, 80, 260, "water", False),
        RideSpec(
            "junior_coaster",
            "Junior Roller Coaster",
            "rollercoaster",
            (5, 4),
            168000,
            11000,
            452,
            278,
            168,
            36,
            86,
            250,
            "rollercoaster",
            False,
            True,
            280,
        ),
        RideSpec(
            "wooden_wild_mouse",
            "Wooden Wild Mouse",
            "rollercoaster",
            (5, 5),
            182000,
            12500,
            486,
            382,
            298,
            28,
            78,
            280,
            "rollercoaster",
            False,
            True,
            320,
        ),
        RideSpec(
            "side_friction",
            "Side-Friction Coaster",
            "rollercoaster",
            (6, 4),
            142000,
            9000,
            378,
            218,
            158,
            32,
            84,
            220,
            "rollercoaster",
            True,
            True,
            240,
        ),
        RideSpec(
            "mini_steel",
            "Mini Steel Coaster",
            "rollercoaster",
            (5, 5),
            228000,
            14000,
            524,
            448,
            322,
            34,
            82,
            300,
            "rollercoaster",
            False,
            True,
            360,
        ),
        RideSpec(
            "wooden_coaster",
            "Wooden Roller Coaster",
            "rollercoaster",
            (6, 6),
            328000,
            18000,
            642,
            518,
            398,
            40,
            80,
            350,
            "rollercoaster",
            False,
            True,
            520,
        ),
        RideSpec(
            "looping_coaster",
            "Looping Roller Coaster",
            "rollercoaster",
            (6, 6),
            362000,
            20000,
            682,
            648,
            478,
            38,
            76,
            400,
            "rollercoaster",
            False,
            True,
            540,
        ),
        RideSpec(
            "corkscrew",
            "Corkscrew Coaster",
            "rollercoaster",
            (6, 6),
            388000,
            21000,
            694,
            638,
            488,
            36,
            75,
            400,
            "rollercoaster",
            False,
            True,
            560,
        ),
        RideSpec(
            "suspended_swinging",
            "Suspended Swinging Coaster",
            "rollercoaster",
            (6, 5),
            305000,
            19000,
            618,
            578,
            448,
            32,
            74,
            380,
            "rollercoaster",
            False,
            True,
            480,
        ),
        RideSpec(
            "inverted_coaster",
            "Inverted Coaster",
            "rollercoaster",
            (6, 6),
            412000,
            23000,
            724,
            682,
            502,
            34,
            72,
            420,
            "rollercoaster",
            False,
            True,
            580,
        ),
        RideSpec(
            "virginia_reel",
            "Virginia Reel",
            "rollercoaster",
            (4, 4),
            152000,
            10500,
            402,
            298,
            348,
            26,
            80,
            240,
            "rollercoaster",
            False,
            True,
            260,
        ),
        RideSpec(
            "mine_train",
            "Mine Train Coaster",
            "rollercoaster",
            (6, 5),
            286000,
            17000,
            582,
            418,
            338,
            36,
            81,
            320,
            "rollercoaster",
            False,
            True,
            500,
        ),
    ]
}


STALLS: dict[str, StallSpec] = {
    spec.id: spec
    for spec in [
        StallSpec("toilets", "Toilets", "facility", (1, 1), 20000, 1200, 0, True, "T"),
        StallSpec("first_aid", "First Aid Room", "facility", (1, 1), 25000, 1800, 0, True, "+"),
        StallSpec("information_kiosk", "Information Kiosk", "facility", (1, 1), 21000, 1500, 50, True, "I"),
        StallSpec("cash_machine", "Cash Machine", "facility", (1, 1), 18000, 800, 0, False, "£"),
        StallSpec("burger_bar", "Burger Bar", "food", (1, 1), 25000, 2200, 120, True, "F"),
        StallSpec("drinks_stall", "Drinks Stall", "drink", (1, 1), 22000, 1800, 100, True, "D"),
        StallSpec("ice_cream", "Ice Cream Stall", "food", (1, 1), 23000, 1600, 90, True, "F"),
        StallSpec("fries_stall", "Fries Stall", "food", (1, 1), 24000, 1700, 100, False, "F"),
        StallSpec("pizza_stall", "Pizza Stall", "food", (1, 1), 28000, 2400, 140, False, "F"),
        StallSpec("balloon_stall", "Balloon Stall", "souvenir", (1, 1), 20000, 900, 80, True, "B"),
        StallSpec("souvenir_stall", "Souvenir Stall", "souvenir", (1, 1), 26000, 1100, 150, False, "B"),
        StallSpec("umbrella_stall", "Umbrella Stall", "souvenir", (1, 1), 21000, 1000, 120, True, "U"),
    ]
}


SCENERY: dict[str, ScenerySpec] = {
    spec.id: spec
    for spec in [
        ScenerySpec("tree", "Tree", 800, "^", "tree"),
        ScenerySpec("garden", "Garden", 1200, "*", "garden"),
        ScenerySpec("bench", "Bench", 500, "h", "bench"),
        ScenerySpec("lamp", "Lamp", 600, "!", "lamp"),
        ScenerySpec("bin", "Litter Bin", 400, "o", "bin"),
    ]
}


PATH_COST = 1000  # £10.00 per tile, close to RCT2
PATH_REMOVE_COST = 400
LAND_PRICE_DEFAULT = 9000  # £90.00
CONSTRUCTION_RIGHTS_PRICE = 4000
STAFF_HIRE_COST = {
    "handyman": 5000,
    "mechanic": 6000,
    "security": 5500,
    "entertainer": 5000,
}
STAFF_WAGE_MONTH = {
    "handyman": 5000,
    "mechanic": 6500,
    "security": 5500,
    "entertainer": 5000,
}

RESEARCH_FUNDING = {
    "none": 0,
    "minimum": 8000,
    "normal": 16000,
    "maximum": 32000,
}

# Progress points per month toward the next invention.
RESEARCH_PROGRESS = {
    "none": 0,
    "minimum": 30,
    "normal": 55,
    "maximum": 90,
}

MARKETING_CAMPAIGNS = {
    "park_tickets": {"name": "Free park entry vouchers", "cost": 50000, "weeks": 6, "guest_bonus": 8},
    "ride_free": {"name": "Free ride vouchers", "cost": 40000, "weeks": 6, "guest_bonus": 6},
    "park_ads": {"name": "Park advertising", "cost": 35000, "weeks": 4, "guest_bonus": 5},
    "ride_ads": {"name": "Ride advertising", "cost": 35000, "weeks": 4, "guest_bonus": 5},
}

MONTHS = ["March", "April", "May", "June", "July", "August", "September", "October"]
DAYS_IN_MONTH = [31, 30, 31, 30, 31, 31, 30, 31]  # close enough; OpenRCT2 uses GetDaysInMonth
MONTH_COUNT = 8


@dataclass
class ScenarioSpec:
    id: str
    name: str
    details: str
    objective_type: str  # guests_by | park_value_by | have_fun | guests_and_rating | repay_loan_and_park_value
    year: int  # deadline in years (8 months each)
    num_guests: int = 0
    currency: int = 0  # pence, for value/income objectives
    starting_cash: int = 1_000_000
    starting_loan: int = 1_000_000
    max_loan: int = 2_000_000
    interest_rate: int = 10  # percent per year, charged monthly as rate/12
    entrance_fee: int = 1000
    park_open: bool = False
    map_w: int = 18
    map_h: int = 16
    owned_margin: int = 2
    start_invented_extra: list[str] = field(default_factory=list)
    forbid_tree_removal: bool = False
    no_money: bool = False
    suggested_guest_max: int = 400
    guest_initial_cash: int = 5000
    land_price: int = LAND_PRICE_DEFAULT


SCENARIOS: dict[str, ScenarioSpec] = {
    "gentle_intro": ScenarioSpec(
        id="gentle_intro",
        name="Gentle Glen",
        details="A small wooded valley. Attract 80 guests with a park rating of at least 600 before the end of June, Year 1.",
        objective_type="guests_by",
        year=0,  # special: 4 months (March–June) handled via year=0 + month cap in engine
        num_guests=80,
        starting_cash=1_200_000,
        starting_loan=800_000,
        max_loan=1_500_000,
        suggested_guest_max=200,
    ),
    "forest_frontiers": ScenarioSpec(
        id="forest_frontiers",
        name="Forest Frontiers",
        details="A classic beginner park. Attract 250 guests with a park rating of at least 600 by the end of Year 1.",
        objective_type="guests_by",
        year=1,
        num_guests=250,
        starting_cash=1_000_000,
        starting_loan=1_000_000,
        max_loan=2_000_000,
        start_invented_extra=["twist"],
        suggested_guest_max=500,
    ),
    "dynamite_dunes": ScenarioSpec(
        id="dynamite_dunes",
        name="Dynamite Dunes",
        details="Desert park. Raise park value to £25,000.00 by the end of Year 2.",
        objective_type="park_value_by",
        year=2,
        currency=2_500_000,
        starting_cash=800_000,
        starting_loan=1_200_000,
        max_loan=2_500_000,
        start_invented_extra=["twist", "junior_coaster", "boat_hire"],
        suggested_guest_max=700,
    ),
    "have_fun": ScenarioSpec(
        id="have_fun",
        name="Fun Park",
        details="Sandbox. Stay solvent and keep the park entertaining. Game ends on bankruptcy or after 4 years.",
        objective_type="have_fun",
        year=4,
        starting_cash=2_000_000,
        starting_loan=0,
        max_loan=3_000_000,
        park_open=True,
        suggested_guest_max=1000,
    ),
}


def invented_at_start(scenario: ScenarioSpec) -> set[str]:
    invented = {rid for rid, spec in RIDES.items() if spec.start_invented}
    invented |= {sid for sid, spec in STALLS.items() if spec.start_invented}
    invented |= set(scenario.start_invented_extra)
    return invented


def research_queue(invented: set[str]) -> list[str]:
    """Uninvented ride/stall ids in a stable RCT-like category order."""
    order_cats: list[RideCategory] = ["gentle", "thrill", "water", "rollercoaster", "transport", "shop"]
    queue: list[str] = []
    for cat in order_cats:
        for rid, spec in RIDES.items():
            if spec.research_group == cat and rid not in invented:
                queue.append(rid)
        if cat == "shop":
            for sid, spec in STALLS.items():
                if sid not in invented:
                    queue.append(sid)
    return queue
