# BUGS

Bugs found while building and testing the OpenRCT2 text agent API.

| ID | Symptom | Cause | Status |
|---|---|---|---|
| B1 | Package import crash (`IndentationError` in `engine.py`) | Spawn-rate edit left leftover indent in `_spawn_guests`. | **Fixed** |
| B2 | `reset` of an unknown scenario raised `TypeError` | `log_event(..., **result)` collided with `ok=`. | **Fixed** |
| B3 | Later tests hit `FileNotFoundError` on the log path | Logger pointed at a deleted `TemporaryDirectory`. | **Fixed** (mkdir + fallback) |
| B4 | Heuristic never won `forest_frontiers` (≤130 guests vs 250) | Guest spawn/stay too low for an 18×16 park; rating crushed by litter. | **Fixed**. Re-run: 8/8 heuristic wins. |
| B5 | Park rating 0 after opening a ride | Rating not recalculated until time passed; litter term too harsh; guests marked `lost` too eagerly. | **Fixed** |
| B6 | Merry-go-round downtime 100 after one month without a mechanic | Daily breakdown chance too high. | **Fixed** |
| B7 | Legal `place_path` list started at the NW corner, not the entrance | Enumerator scanned y=0..h, x=0..w. | **Fixed** (sort by distance; path-adjacent origins first) |
| B8 | `wait:0` silently advanced one month | `int(parsed.get("months") or 1)` treats 0 as missing. | **Fixed** (`_positive_int`). Edge test `test_wait_out_of_range`. |
| B9 | One-shot CLI `reset` then `step` started a fresh in-memory game | Each process constructed a new `AgentAPI()`. | **Fixed** (pickle persist under `logs/sessions/`). |
| B10 | `dynamite_dunes` unwinnable: heuristic 0/6 and Composer 2.5 peaked at ~£13k vs £25k | Park-value formula (`build/4 + E*80 + guests*700`) is full-map RCT scale; 18×16 parks never reach £25,000. | **Fixed**. Value uses construction cost + excitement×350 + £40/guest. Heuristic also builds coasters on `park_value_by`. Re-run: **8/8** heuristic wins. |
| B11 | Winning `wait:1` skipped month-end JSONL (`game.month` missing) and left `months_elapsed=0` | Objective is checked every day; a mid-month win returned before `_end_of_month`. | **Fixed**. Calendar always finishes the requested wait; `game.month` + `game.wait` log even after a mid-month result. |

## Brute-force round 2 (this e2e pass)

| Scenario | Games | Crashes | Heuristic wins | Notes |
|---|---|---|---|---|
| `gentle_intro` | 52 (12 heuristic + 40 random) | **0** | **12/12** | 5 random failures (never opened a usable park). |
| `forest_frontiers` | 26 then 14 re-run | **0** | **10/10** then **6/6** | Random mostly undecided at step cap. |
| `dynamite_dunes` | 14 then 16 re-run | **0** | **0/6** then **8/8** after B10 | First pass exposed B10. |
| `have_fun` | 10 (4 heuristic + 6 random) | **0** | **4/4** | Time-cap success. |

No hangs. Invalid random actions return errors; the process never crashed.

Logs after B11 (`logs/e2e-event-check-r3.jsonl`): `game.start`, `game.event` (start/success/month), `game.month`, `game.wait`, `game.over` all present on a winning Forest Frontiers game. `months_elapsed` is 1 after the winning `wait:1`.

## Brute-force round 1 (after B4–B6)

| Scenario | Games | Crashes | Heuristic wins | Random notes |
|---|---|---|---|---|
| `gentle_intro` | 50 (10 heuristic + 40 random) | **0** | **10/10** | 3 randoms timed out with 0 guests (never opened a usable park). |
| `forest_frontiers` | 20 (8 heuristic + 12 random) | **0** | **8/8** | 1 random won; others undecided at step cap. |

No hangs. Invalid random actions return errors; the process never crashed.

## LLM play

Sessions from Composer 2.5 (`c31`,`c32`,`c33`,`c41`) and Grok 4.6 Medium (`g61`,`g71`), recovered from `logs/sessions/*.pkl`.

| Session | Model | Scenario | Result | Guests | Rating | Notes |
|---|---|---|---|---|---|---|
| c31 | Composer 2.5 | gentle_intro | **success** | 97 | 753 | Won; some rides still disconnected (warning). |
| c32 | Composer 2.5 | gentle_intro | **success** | 90 | 748 | Won; stalls placed off the path network. |
| c32play / c32final | Composer 2.5 | gentle_intro | **failure** | 182 | 0 | Built at y=2 (old NW origin order, B7). Paths at entrance never reached buildings. Confusing: guests still entered. |
| c33 | Composer 2.5 | gentle_intro | **success** | 84 | 773 | Won. |
| c41 | Composer 2.5 | forest_frontiers | **success** | 274 | 803 | Won in year 1. |
| g61 | Grok 4.6 Medium | gentle_intro | **success** | 105 | 759 | Clean connected park; **no warnings**. Text was clear enough to play well. |
| g71 | Grok 4.6 Medium | forest_frontiers | **success** | 309 | 784 | Strong build; one leftover disconnected car ride. |
| bf-c51 | Composer 2.5 | gentle_intro seed 51 | **success** | 148 | 769 | 75 steps, 0 invalid, 0 crashes. |
| bf-c52 | Composer 2.5 | gentle_intro seed 52 | **success** | 149 | 757 | 74 steps, 0 invalid. |
| bf-c53 | Composer 2.5 | gentle_intro seed 53 | **success** | 139 | 754 | Some disconnected coasters; still won. |
| bf-c54 | Composer 2.5 | forest_frontiers seed 54 | **success** | 306 | 766 | Path warnings on later rides; guests/rating still hit. |
| bf-c55 | Composer 2.5 | forest_frontiers seed 55 | **success** | 310 | 741 | Same pattern. |
| bf-c56 | Composer 2.5 | dynamite_dunes seed 56 | **failure** | 361 | 999 | Park value £12.8k / £25k — B10, since fixed. |

Crashes: **none**. Hangs: **none**.

**Clarity:** HUD + ASCII map is enough for a stronger model (Grok) to build a connected park. Composer often trusted the first legal `place_stall`/`place_ride` id, which used to be the far north-west tile (B7). After the sort fix, those ids start next to `E` / reachable `#`. Coach text now says isolated buildings are useless.

## Confusing text (remaining, documented)

- A ride still prints `WARNING: no path from the entrance` after `place_ride` if paths do not touch it — **correct**, not a crash.
- `legal` JSON can be large; `agent_client.py` truncates stdout. Use `--text` for the summary plus a sample of ids.
- Guests can enter an open park even when no ride is reachable (they mill around). Rating then collapses unless something is connected. Documented in README.
