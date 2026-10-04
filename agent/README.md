# OpenRCT2 text-only LLM agent API

An LLM (or any client) can play a RollerCoaster Tycoon 2–style park **without a
multimodal model**. The agent loop is JSON + readable text: park HUD, ASCII
map, legal actions, and a `step()` that never crashes on bad input.

This is a **source-faithful Python simulation** of OpenRCT2 internals
(`GameState_t`, `Park::ParkData`, `GameCommand` / GameActions, park rating,
March–October calendar). The full C++ client is not booted here because
OpenRCT2 needs original RCT2 data files, which cannot be bundled. See
[OPENRCT2_HOOK.md](OPENRCT2_HOOK.md) for how this maps onto a live game.

## Setup

- **Python 3.10+** (stdlib only). No `pip install` for the agent loop or tests.
- Optional, human park + recordings: **Pillow** (isometric `/play` camera) and **ffmpeg** (MP4).
- `agent/requirements.txt` documents that; it does not add runtime packages.

From the **repository root**:

```bash
export PYTHONPATH=agent
python3 -m openrct2_agent.cli --help
```

`python3 -m openrct2_agent` is the same CLI. One-shot CLI commands persist
the park as `logs/sessions/<session>.pkl` (default session id `default`).

## Quick start

```bash
export PYTHONPATH=agent
python3 -m openrct2_agent.cli reset --seed 42 --scenario gentle_intro --text
```

Stdio JSON-lines (one JSON object per line in, one out). The first line is a
hello banner; then send commands:

```bash
export PYTHONPATH=agent
python3 -m openrct2_agent.cli stdio
```

```json
{"cmd": "reset", "seed": 42, "scenario": "forest_frontiers"}
{"cmd": "get_state"}
{"cmd": "list_legal_actions"}
{"cmd": "step", "action": "place_path:9,11"}
{"cmd": "step", "action": {"type": "place_ride", "ride_type": "merry_go_round", "x": 6, "y": 10}}
{"cmd": "step", "action": "wait:1"}
{"cmd": "replay"}
```

HTTP:

```bash
export PYTHONPATH=agent
python3 -m openrct2_agent.cli serve --port 8765
# GET /health  GET /help
```

```bash
curl -s http://127.0.0.1:8765/health
curl -s -X POST http://127.0.0.1:8765/reset \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42, "scenario": "gentle_intro", "session_id": "p1"}'
curl -s 'http://127.0.0.1:8765/state?session_id=p1'
curl -s 'http://127.0.0.1:8765/legal_actions?session_id=p1'
curl -s -X POST http://127.0.0.1:8765/state \
  -H 'Content-Type: application/json' -d '{"session_id": "p1"}'
curl -s -X POST http://127.0.0.1:8765/legal_actions \
  -H 'Content-Type: application/json' -d '{"session_id": "p1"}'
curl -s -X POST http://127.0.0.1:8765/step \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "p1", "action": "wait:1"}'
curl -s 'http://127.0.0.1:8765/replay?session_id=p1'
```

Python:

```python
from openrct2_agent.api import ParkSession

s = ParkSession()
print(s.reset(seed=42, scenario="gentle_intro")["text"])
print(s.list_legal_actions()["text"])
print(s.step("hire_staff:handyman")["message"])
print(s.step("set_park_open:true")["result"])
```

If `scenario` is omitted, **`forest_frontiers`** is the default.

## API reference

### Calls

| Call | Meaning |
|---|---|
| `reset(seed, scenario)` | New game. Deterministic for that seed + scenario + action sequence. |
| `get_state()` | `text` (full readable dump) + `state` (JSON). Also `game_over`, `result`, `result_reason`. |
| `list_legal_actions()` | `text` coach notes, grouped `action_types`, `actions` objects, `actions_flat` ids. |
| `step(action)` | Execute. Invalid input returns `{ok:false, error, code}` — no client-facing exception. |
| `export_replay()` / `{cmd:"replay"}` | `{seed, scenario, actions}` log. |
| `apply_replay(replay)` | Reset + replay that log. Alias: `replay_from`. |

`result` is `undecided` \| `success` \| `failure`. After game-over, only `reset`
starts a new park (`inspect_tile` still works). `step` also returns a fresh
`text` + `state` snapshot so you do not have to call `get_state` every turn.

Every successful payload includes `ok: true` and `session_id`. Failures include
`ok: false`, `error` (string), and `code` (e.g. `no_game`, `parse_error`,
`unknown_action`, `game_over`, `bad_seed`, `unknown_scenario`).

### Action ids

Pick an id from `actions_flat`, or pass a JSON object with `type` plus params.
Examples:

| Id | JSON |
|---|---|
| `place_path:7,8` | `{"type":"place_path","x":7,"y":8}` |
| `place_ride:merry_go_round,6,10` | `{"type":"place_ride","ride_type":"merry_go_round","x":6,"y":10}` |
| `place_stall:toilets,8,11` | `{"type":"place_stall","stall_type":"toilets","x":8,"y":11}` |
| `set_ride_status:0,open` | `{"type":"set_ride_status","ride_id":0,"status":"open"}` |
| `hire_staff:handyman` | `{"type":"hire_staff","staff_type":"handyman"}` |
| `set_park_open:true` | `{"type":"set_park_open","open":true}` |
| `wait:1` | `{"type":"wait","months":1}` |
| `inspect_tile:9,15` | `{"type":"inspect_tile","x":9,"y":15}` |

Other types: `remove_path`, `buy_land`, `place_scenery`, `demolish_ride`,
`demolish_stall`, `set_ride_price`, `set_ride_name`, `set_stall_price`,
`fire_staff`, `set_entrance_fee`, `set_loan`, `set_research_funding`
(`none`/`minimum`/`normal`/`maximum`), `start_marketing`, `set_park_name`,
`wait_days` (1–62), `wait_weeks` (1–16). `wait` / `wait_months` is **1–16**
months. Money fields are **integer pence** (1000 = £10.00). Staff kinds:
`handyman`, `mechanic`, `security`, `entertainer`.

`list_legal_actions` can list hundreds of tile origins. The flat list is
sorted (path-adjacent, near the entrance first) and **capped at 800 ids**.
Wait/hire/open/finance actions are always kept; tile origins fill the rest,
reserving at least one origin per invented ride/stall type. Full origin
grids remain in `action_types`.

### HTTP / stdio aliases

| Interface | Reset | State | Legal | Step | Replay |
|---|---|---|---|---|---|
| Python | `reset` | `get_state` | `list_legal_actions` | `step` | `export_replay` / `apply_replay` |
| Stdio `cmd` | `reset`, `new_game` | `get_state`, `state` | `list_legal_actions`, `legal`, `actions` | `step`, `act` | `replay` (export), `apply_replay` |
| HTTP | `POST /reset` | `GET` or `POST /state` | `GET` or `POST /legal_actions` | `POST /step` | `GET /replay` export, `POST /replay` apply |
| CLI | `reset` | `state` | `legal` | `step --action …` | `replay` / `apply_replay --action file.json` |

`POST /rpc` accepts the same `{cmd,…}` objects as stdio. `GET /help` lists
endpoints. Stdio also accepts `quit` / `exit`.

## Scenarios

| id | Park | Goal |
|---|---|---|
| `gentle_intro` | Gentle Glen | 80 guests **and** rating ≥ 600 by end of June Year 1 |
| `forest_frontiers` | Forest Frontiers | 250 guests and rating ≥ 600 by end of Year 1 (API default) |
| `dynamite_dunes` | Dynamite Dunes | Park value £25,000 by end of Year 2 |
| `have_fun` | Fun Park | Sandbox until bankruptcy or 4 years (park starts open) |

## Play it yourself (human client)

The engine is the same `ParkSession` the agent uses. The park camera is
**drawn in code** (isometric tiles, rides, stalls, peeps) so every catalog
object has a silhouette without a pile of PNGs.

```bash
export PYTHONPATH=agent
python3 -m openrct2_agent.cli play --port 8765
# open http://127.0.0.1:8765/play
```

Click the map to pave paths, pick a ride/stall and click to build, then
**Open park gates** and **Wait 1 month**. Sounds are generated in code
(`openrct2_agent.audio`). **Watch manager play** runs the heuristic on this
same session so you see the isometric park change when the agent acts.
`POST /step` from any API client updates that view too.

Pillow is required for `/play` and the isometric frames. The text agent
loop still needs only the stdlib.

## How to play (for agents)

1. Pave `#` paths **north** from the `E` entrance (smaller `y`; `x` grows east).
2. Place toilets (`T`), drinks (`D`), food (`F`) so they **touch** a `#` path
   connected to `E`. Isolated buildings do nothing.
3. Place complete rides (`R`) — no track pieces; each ride is a prebuilt layout.
4. `set_ride_status:{id},open` then `set_park_open:true`.
5. Hire a `handyman` and a `mechanic`.
6. `wait:1` to simulate a month (the calendar still finishes those months if
   you already won mid-month).
7. Expand with more rides as cash and research allow.

## Example agent loop

```python
from openrct2_agent.api import ParkSession

s = ParkSession()
s.reset(seed=42, scenario="gentle_intro")
while True:
    snap = s.get_state()
    print(snap["text"])
    if snap["game_over"]:
        print("RESULT", snap["result"], snap["result_reason"])
        break
    legal = s.list_legal_actions()
    # Pick an id from legal["actions_flat"], or a JSON object:
    action = "wait:1"  # replace with your policy
    result = s.step(action)
    if not result["ok"]:
        print("illegal:", result["error"])  # never a crash
```

One-shot CLI (persists under `logs/sessions/<session>.pkl`):

```bash
export PYTHONPATH=agent
python3 -m openrct2_agent.cli reset --seed 42 --scenario gentle_intro --session demo --text
python3 -m openrct2_agent.cli step --session demo --action place_path:8,14
python3 -m openrct2_agent.cli state --session demo --text
```

## Known limitations

- Original RCT2 data files are **not** bundled. This is a Python sim, not a
  running `openrct2` process. See `OPENRCT2_HOOK.md`.
- Map is **18×16** so the whole park fits in text. Not a 128×128 RCT2 map.
- Rides are **complete prebuilt layouts**, not piece-by-piece track.
- Buildings must touch a `#` path connected to `E` or guests cannot use them.
- Park value is scaled so an 18×16 Dynamite Dunes can still hit the classic
  £25k objective (not a 1:1 OpenRCT2 valuation).
- `list_legal_actions` caps the flat id list at 800 (see above).
- Money is integer pence. Dates use RCT’s 8-month year (March–October).
- The agent loop never sees images. MP4 capture is a human-facing HUD replay
  (`WATCH.md`); it needs Pillow + ffmpeg and is not part of `step()`.
- CLI pickle sessions are process-local files, not a multiplayer server.

## Logging and replay

Every API call and key simulation event is appended as JSONL under `./logs/`
(repo root, relative to the working directory). Kinds include:

- `api.reset` / `api.get_state` / `api.list_legal_actions` / `api.step` / `api.apply_replay`
- `game.start` / `game.over`
- `game.event` — park news ticker (`topic`: start, month, research, breakdown, ride_test, success, failure)
- `game.month` — structured end-of-month finance snapshot (always fired at month wrap, including after a mid-month win)
- `game.wait` — each `wait` action (requested months vs `months_elapsed`)
- `game.research` / `game.breakdown` when those happen

Replays can be exported (`GET /replay` or `{cmd:"replay"}`) and applied
(`POST /replay` or `{cmd:"apply_replay","replay":…}`) to reconstruct the
same park from seed + action log.

```bash
PYTHONPATH=agent python3 agent/scripts/play_and_record.py \
  --scenario gentle_intro --seed 11 --out logs/replay.json
PYTHONPATH=agent python3 agent/scripts/render_replay.py logs/replay.json \
  --mp4 logs/agent_play.mp4 --transcript logs/agent_play_transcript.txt
```

A recorded **gameplay** win (Gentle Glen, seed 11) is committed at
**`recordings/agent_play_gameplay.mp4`** (top-down sprites, not a terminal).
Sprites live in `agent/assets/sprites/`. How to watch: [`WATCH.md`](../WATCH.md).

## Tests

Stdlib `unittest` only (no pytest):

```bash
python3 -m unittest discover -s agent/tests -v
```

Or from `agent/`:

```bash
cd agent && python3 -m unittest discover -s tests -v
```

Optional extra (not required for CI of the API):

```bash
PYTHONPATH=agent python3 agent/scripts/brute_force.py --games 40 --heuristic 8
```

## Layout

```
agent/openrct2_agent/   # engine, actions, renderer, HTTP, stdio
agent/assets/sprites/   # original pixel-art tiles / rides / stalls / guests
agent/tests/            # unittest (unit + e2e + edge)
agent/scripts/          # play_and_record.py, record_gameplay.py, render_replay.py, …
agent/OPENRCT2_HOOK.md  # mapping onto live OpenRCT2
recordings/             # gameplay MP4 + ASCII HUD replay
WATCH.md                # how to watch the recording
```
