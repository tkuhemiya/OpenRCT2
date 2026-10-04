# BUGS

Bugs found while building and testing the OpenRCT2 text agent API.

| ID | Symptom | Cause | Status |
|---|---|---|---|
| B1 | Package import crash (`IndentationError` in `engine.py`) | Spawn-rate edit left leftover indent in `_spawn_guests`. | **Fixed** |
| B2 | `reset` of an unknown scenario raised `TypeError` | `log_event(..., **result)` collided with `ok=`. | **Fixed** |
| B3 | Later tests hit `FileNotFoundError` on the log path | Logger pointed at a deleted `TemporaryDirectory`. | **Fixed** (mkdir + fallback) |
| B4 | Heuristic never won `forest_frontiers` (≤130 guests vs 250) | Guest spawn/stay too low for an 18×16 park; rating crushed by litter. | **Fixed** (higher gen/stay, milder litter penalty). Re-run: 8/8 heuristic wins. |
| B5 | Park rating 0 after opening a ride / `test_open_park_with_rides_gets_guests` | (1) Rating not recalculated until time passed. (2) OpenRCT2-style litter term subtracted 600 for modest dirt. (3) Guests marked `lost` whenever no usable ride. | **Fixed** (`_recalculate` after successful `step`; litter scaled; lost only after 2 days with nothing to ride) |
| B6 | Merry-go-round downtime 100 after one month without a mechanic | Daily breakdown chance ~7% stacking +20–50 downtime. | **Fixed** (gentler breakdowns). Mechanic still important long-term. |
| B7 | Legal `place_path` list starts at the north-west of owned land, not next to the entrance | Enumerator scans y=0..h, x=0..w. Text warns to build from `E`. Heuristic sorts by distance to entrance. | **Accepted** (documented). LLM agents should read the map, not the first id. |

## Brute-force (after fixes)

Command: `PYTHONPATH=agent python3 agent/scripts/brute_force.py`

| Scenario | Games | Crashes | Heuristic wins | Random notes |
|---|---|---|---|---|
| `gentle_intro` | 50 (10 heuristic + 40 random) | **0** | **10/10** | 3 randoms hit the time limit with 0 guests (never opened a usable park). Rest still in progress at step cap. |
| `forest_frontiers` | 20 (8 heuristic + 12 random) | **0** | **8/8** | 1 random actually won; others undecided at step cap. No illegal-state exceptions. |

No hangs. Invalid actions from the random policy are returned as errors and skipped; the process never crashed.

## LLM play

Composer 2.5 and Grok 4.6 Medium sub-agents were launched against `agent_client.py` (sessions `c31`, `c32`, `c33`, `c41`, `g61`, `g71`). Reports are collected in the following commit once those runs finish.

## Confusing text (from engine warnings / legal lists)

- Flat `place_path` ids are not ordered from the entrance (B7).
- `legal` JSON can be large (hundreds of tile origins); `agent_client.py` truncates stdout and `--text` shows a sample.
- A ride reports `WARNING: no path from the entrance` after `place_ride` if paths do not touch the footprint — this is correct, not a crash.
