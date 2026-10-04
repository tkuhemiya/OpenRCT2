# PLAN: Text-only LLM agent API for OpenRCT2 (RollerCoaster Tycoon 2)

## Feasibility

**Verdict: feasible for a complete, playable, text-only agent loop. Not feasible to boot the full C++ client in this environment.**

OpenRCT2 is an open-source reimplementation of RCT2. The live engine (`GameState_t`, `Park::ParkData`, `GameActions::GameAction`) is the right internal model, but:

1. **Original RCT2 data files are required** to run `openrct2` / `openrct2-cli`. They are commercial assets and are not in this repo or this VM. We cannot legally bundle them.
2. Compiling the C++ tree is a heavy, asset-dependent process (objects, title sequences, g2.dat). Headless CLI still calls `CreateContext()` and expects those files.
3. The plugin/scripting API (`distribution/scripting/openrct2.d.ts`) is an excellent live hook *when the game is running*, but it cannot start without assets.

**Decision (no wait for approval):** ship a **standalone Python simulation** that:

- Mirrors OpenRCT2 internal state (`GameState_t`, park finance, guests, staff, rides, research, objectives, weather, date calendar).
- Exposes the same *kinds* of player actions as `GameCommand` (place path, create ride, hire staff, set prices, loan, research, marketing, wait).
- Uses **prebuilt ride layouts** instead of piece-by-piece track building (track pieces are a huge, visual, multimodal action space; LLM agents get complete rides like the ride-create + track-design flow).
- Is fully deterministic given a seed.
- Can later be swapped for a live OpenRCT2 backend via the plugin/CLI adapter documented in `agent/OPENRCT2_HOOK.md`.

This is the only approach that satisfies the hard requirements (text-only, reset/state/legal/step, logging, seeds, tests, overnight autonomy) **and** is actually playable here.

## Architecture

```
LLM agent  --JSON/text-->  Agent API (HTTP or stdio)
                              |
                              v
                     openrct2_agent.ParkSession
                              |
                              v
                     Simulation engine (Python)
                       |-- Map / ownership / paths
                       |-- Rides, stalls, scenery (catalog from RCT2)
                       |-- Guests + staff (needs, happiness, wages)
                       |-- Finance, research, weather, objectives
                       |-- ASCII + structured state renderer
                              |
                              v
                     logs/*.jsonl  +  replay JSON
```

Public methods (required):

| Method | Role |
|---|---|
| `reset(seed, scenario)` | New game, deterministic |
| `get_state()` | Readable text + structured JSON |
| `list_legal_actions()` | Every currently valid action |
| `step(action)` | Execute or return a helpful error |
| `game_over` / `result` | `undecided` / `success` / `failure` plus reason |

Invalid actions **never crash**; they return `{ok: false, error, code}`.

## What the agent can actually play

RCT2 is a construction + management sim, not a turn-based puzzle. The agent loop is:

1. Build paths from the park entrance.
2. Place complete rides/stalls on owned land.
3. Hire staff, set fees, fund research, advertise.
4. `wait` to advance RCT months (Mar–Oct, 8 months/year — matching `Date.h`).
5. Hit the scenario objective before time runs out, without going bankrupt.

Scenarios included:

- `forest_frontiers` — classic “attract N guests by end of year 1, rating ≥ 600”.
- `gentle_intro` — shorter/easier, used by automated tests.
- `have_fun` — sandbox with a bankruptcy/time cap so games still terminate.

Map size is **18×16 tiles** (not 128×128). A full RCT map cannot be conveyed as text to an LLM; the smaller park is the whole playable area, with buyable extra plots.

## Hook into internal state (source mapping)

Python fields are named after OpenRCT2 types. See `agent/OPENRCT2_HOOK.md`.

| OpenRCT2 | Agent |
|---|---|
| `GameState_t` | `GameState` |
| `Park::ParkData` | `ParkData` |
| `GameCommand` / `GameAction::Query/Execute` | `step()` query-then-execute |
| `Scenario::Objective` | `Objective` |
| `CalculateParkRating` | `calculate_park_rating` (same structure: guests, happiness, uptime, excitement, litter) |
| `scenarioRand` | seeded `random.Random` |
| Plugin `context.executeAction` | future live backend |

## Risks

| Risk | Mitigation |
|---|---|
| Full engine cannot run without RCT2 files | Python sim is the product; hook doc for later |
| Action space explosion (every tile × every ride) | Grouped legal actions + flat IDs; tile origins listed in JSON |
| Balance too hard/easy for LLM | Tuned so a heuristic builder wins `gentle_intro`; `forest_frontiers` is the real challenge |
| Guest pathfinding too slow | BFS on paths once per day; guests are individual but cheap |
| Sub-agent models unavailable | Local random + heuristic brute force still runs; note substitutions in PROGRESS.md |
| Video capture of a GUI game | Agent stays text-only; we record an ASCII/HUD replay render (ffmpeg). If screen recording works, also capture that. |
| Accidental PR against OpenRCT2/OpenRCT2 | Origin is `tkuhemiya/OpenRCT2` only; never add the upstream remote; ManagePullRequest + explicit fork |

## Phases

0. This plan + `PROGRESS.md` + branch `themiya/agent-text-api-17ff`
1. Engine + API + text renderer (no stubs)
2. File logging under `./logs` + `agent/README.md`
3. Unit/e2e tests, brute-force play, stronger-model play, `BUGS.md`
4. Replay video / transcript
5. PR against **the fork only**
