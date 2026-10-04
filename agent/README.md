# OpenRCT2 text-only LLM agent API

An LLM (or any client) can play a RollerCoaster Tycoon 2–style park **without a
multimodal model**. The agent loop is JSON + readable text: park HUD, ASCII
map, legal actions, and a step() that never crashes on bad input.

This is a **source-faithful simulation** of OpenRCT2 internals
(`GameState_t`, `Park::ParkData`, `GameCommand` / GameActions, park rating,
March–October calendar). The full C++ client is not booted here because
OpenRCT2 needs original RCT2 data files, which cannot be bundled. See
[OPENRCT2_HOOK.md](OPENRCT2_HOOK.md) for how this maps onto a live game.

## Quick start

From the repo root:

```bash
export PYTHONPATH=agent
python3 -m openrct2_agent.cli reset --seed 42 --scenario gentle_intro --text
```

Stdio JSON-lines (one JSON object per line in, one out):

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
```

HTTP:

```bash
export PYTHONPATH=agent
python3 -m openrct2_agent.cli serve --port 8765
```

```bash
curl -s http://127.0.0.1:8765/health
curl -s -X POST http://127.0.0.1:8765/reset \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42, "scenario": "gentle_intro", "session_id": "p1"}'
curl -s 'http://127.0.0.1:8765/state?session_id=p1' | python3 -m json.tool | head
curl -s 'http://127.0.0.1:8765/legal_actions?session_id=p1'
curl -s -X POST http://127.0.0.1:8765/state \
  -H 'Content-Type: application/json' -d '{"session_id": "p1"}'
curl -s -X POST http://127.0.0.1:8765/legal_actions \
  -H 'Content-Type: application/json' -d '{"session_id": "p1"}'
curl -s -X POST http://127.0.0.1:8765/step \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "p1", "action": "wait:1"}'
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

## Required API

| Call | Meaning |
|---|---|
| `reset(seed, scenario)` | New game. Deterministic for that seed. |
| `get_state()` | `text` (full readable dump) + `state` (JSON). Includes `game_over`, `result`, `result_reason`. |
| `list_legal_actions()` | Grouped schemas + `actions_flat` ids. |
| `step(action)` | Execute. Invalid actions return `{ok:false, error, code}` — no exceptions to the client. |
| `apply_replay(replay)` | Reset + replay a previously exported `{seed, scenario, actions}` log. |

`result` is `undecided` | `success` | `failure`. After game-over, only `reset` starts a new park (`inspect_tile` still works).

Action ids look like `place_path:7,8`, `place_ride:merry_go_round,6,10`, `wait:1`.
You may also pass a JSON object: `{"type":"wait","months":1}`.

## Scenarios

| id | Goal |
|---|---|
| `gentle_intro` | 80 guests, rating ≥ 600, by end of June Year 1 |
| `forest_frontiers` | 250 guests, rating ≥ 600, by end of Year 1 (classic beginner park) |
| `dynamite_dunes` | Park value £25,000 by end of Year 2 |
| `have_fun` | Sandbox until bankruptcy or 4 years |

## How to play (for agents)

1. Pave `#` paths north from the `E` entrance.
2. Place toilets (`T`), drinks (`D`), food (`F`) touching a path.
3. Place complete rides (`R`) — no track pieces; each ride is a prebuilt layout.
4. `set_ride_status:{id},open` then `set_park_open:true`.
5. Hire a `handyman` and a `mechanic`.
6. `wait:1` to simulate a month.
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

One-shot CLI commands **persist** under `logs/sessions/<session>.pkl` (default session `default`):

```bash
export PYTHONPATH=agent
python3 -m openrct2_agent.cli reset --seed 42 --scenario gentle_intro --session demo --text
python3 -m openrct2_agent.cli step --session demo --action place_path:8,14
python3 -m openrct2_agent.cli state --session demo --text
```

## Known limitations

- Original RCT2 data files are **not** bundled. This is a source-faithful Python sim, not a running `openrct2` process. See `OPENRCT2_HOOK.md`.
- Map is 18×16 so the whole park fits in text. Not a 128×128 RCT2 map.
- Rides are **complete prebuilt layouts**, not piece-by-piece track.
- Buildings must touch a `#` path connected to `E` or guests cannot use them.
- `list_legal_actions` can list hundreds of tile origins; the flat list is sorted (path-adjacent, near the entrance first). Tile ids are truncated at 800 while wait/hire/open/finance actions are always kept. Full origin grids remain in `action_types`.
- Money is integer pence. Dates use RCT’s 8-month year (March–October).

## Logging and replay

Every API call and key simulation event is appended as JSONL under `./logs/`
(repo root). Kinds include:

- `api.reset` / `api.get_state` / `api.list_legal_actions` / `api.step` / `api.apply_replay`
- `game.start` / `game.over`
- `game.event` — park news ticker (`topic`: start, month, research, breakdown, ride_test, success, failure)
- `game.month` — structured end-of-month finance snapshot (always fired at month wrap, including after a mid-month win)
- `game.wait` — each `wait` action (requested months vs `months_elapsed`)
- `game.research` / `game.breakdown` when those happen

Replays can be exported (`GET /replay` or `{cmd:"replay"}`) and applied
(`POST /replay` or `{cmd:"apply_replay","replay":...}`) to reconstruct the
same park from seed + action log.

```bash
PYTHONPATH=agent python3 agent/scripts/play_and_record.py \
  --scenario gentle_intro --seed 11 --out logs/replay.json
PYTHONPATH=agent python3 agent/scripts/render_replay.py logs/replay.json \
  --mp4 logs/agent_play.mp4 --transcript logs/agent_play_transcript.txt
```

The **agent never sees images**. The MP4 is a human-facing capture of the text
HUD/map over time (Pillow + a system monospace font, then ffmpeg). There is no
live OpenRCT2 window in this environment.

A recorded win (Gentle Glen, seed 11) is committed at
**`recordings/agent_play.mp4`**. How to watch: `WATCH.md`.

## Tests

```bash
cd agent && python3 -m unittest discover -s tests -v
PYTHONPATH=agent python3 agent/scripts/brute_force.py --games 40 --heuristic 8
```

## Layout

```
agent/openrct2_agent/   # engine, actions, renderer, HTTP, stdio
agent/tests/
agent/scripts/          # play_and_record.py, render_replay.py, …
agent/OPENRCT2_HOOK.md  # mapping onto live OpenRCT2
recordings/             # committed agent-play MP4 + transcript
WATCH.md                # how to watch the recording
```
