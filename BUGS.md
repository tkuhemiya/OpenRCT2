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

## Brute-force (after B4–B6)

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

Crashes: **none**. Hangs: **none**.

**Clarity:** HUD + ASCII map is enough for a stronger model (Grok) to build a connected park. Composer often trusted the first legal `place_stall`/`place_ride` id, which used to be the far north-west tile (B7). After the sort fix, those ids start next to `E` / reachable `#`. Coach text now says isolated buildings are useless.

## Confusing text (remaining, documented)

- A ride still prints `WARNING: no path from the entrance` after `place_ride` if paths do not touch it — **correct**, not a crash.
- `legal` JSON can be large; `agent_client.py` truncates stdout. Use `--text` for the summary plus a sample of ids.
- Guests can enter an open park even when no ride is reachable (they mill around). Rating then collapses unless something is connected. Documented in README.
