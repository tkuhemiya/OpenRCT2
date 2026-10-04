# DONE

Text-only LLM agent API for playing an RCT2-style park inside this OpenRCT2 fork.

## What was built

A Python package `agent/openrct2_agent` that mirrors OpenRCT2 internals
(`GameState_t`, `Park::ParkData`, `GameCommand` / GameActions, park rating,
March–October calendar) and exposes a crash-safe JSON/text loop.

The live C++ client is **not** booted: original RCT2 data files are required
and are not in this repo. Mapping for a future live plugin is in
`agent/OPENRCT2_HOOK.md`.

### API

| Call | What you get |
|---|---|
| `reset(seed, scenario)` | New deterministic park |
| `get_state()` | Readable ASCII HUD+map (`text`) and structured JSON (`state`) |
| `list_legal_actions()` | Grouped schemas + `actions_flat` ids |
| `step(action)` | Execute, or `{ok:false, error, code}` — never a crash |
| `apply_replay(replay)` | Reset + replay `{seed, scenario, actions}` |
| `result` / `game_over` | `undecided` / `success` / `failure` plus reason |

Interfaces: Python `ParkSession`, HTTP (`python3 -m openrct2_agent.cli serve`),
stdio JSON-lines, file-backed CLI (`logs/sessions/*.pkl`).

Logs: JSONL under `./logs` (`api.*`, `game.start`, `game.over`, `game.event`,
`game.month`, `game.wait`, `game.research`, `game.breakdown`). Replays can be exported and
applied (`apply_replay`) to reconstruct the same park.

## How to run

```bash
export PYTHONPATH=agent
cd agent && python3 -m unittest discover -s tests -v
python3 -m openrct2_agent.cli reset --seed 42 --scenario gentle_intro --session demo --text
python3 -m openrct2_agent.cli step --session demo --action hire_staff:handyman
python3 agent/scripts/play_and_record.py --seed 11 --scenario gentle_intro --out logs/replay.json
python3 agent/scripts/render_replay.py logs/replay.json --mp4 logs/agent_play.mp4
```

Full usage: `agent/README.md`.

## Tests

- **62** unittest cases (unit + e2e + expanded edge: invalid, game-over, rapid reset, long games, odd seeds, malformed HTTP, timeouts). All passing.
- Heuristic wins `gentle_intro`, `forest_frontiers`, and `dynamite_dunes`.
- Brute force round 2: **0 crashes**. Heuristic 12/12 intro, 10/10 then 6/6 Forest Frontiers, 8/8 Dynamite Dunes after B10.
- Grok 4.6 Medium g81/g82/g83: **3/3 success**, HUD clarity 4/5 then B12 text fixes.
- Edge: malformed input, game-over, rapid resets, odd seeds, isolated HTTP/CLI sessions, `wait:0`.

## LLM play

| Model | Games | Outcome |
|---|---|---|
| Composer 2.5 | gentle_intro ×3 + forest ×1 (plus failed retries) | Several wins; failed when buildings were placed far from the entrance path (B7, since fixed) |
| Grok 4.6 Medium | g61, g71, then g81/g82/g83 | **5/5 success** this campaign; g81–g83 HUD-only wins including Dynamite Dunes. Clarity 4/5 → B12 text fixes. |

No agent-loop crashes or hangs.

## Bugs

See `BUGS.md`. B1–B12 all **fixed**. No open blockers.

## Video / replay

The agent itself never sees images. Human capture:

- `logs/agent_play.mp4` — ffmpeg render of the text HUD/map (Gentle Glen seed 11, a win)
- `logs/agent_play_transcript.txt` — step-by-step text
- `logs/replay.json` — machine replay
- copies: `/opt/cursor/artifacts/agent_play.mp4`

Regenerate with the commands in `agent/README.md`. There is no live OpenRCT2
GUI in this environment (no RCT2 assets).

## PR

Opened on the **fork only** after `git remote -v` showed:

`origin  https://github.com/tkuhemiya/OpenRCT2`

https://github.com/tkuhemiya/OpenRCT2/pull/1  

Branch: `themiya/agent-text-api-17ff` → `develop`. Never pushed to `OpenRCT2/OpenRCT2`.
