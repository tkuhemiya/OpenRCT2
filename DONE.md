# DONE

Text-only LLM agent API for playing an RCT2-style park on this OpenRCT2 **fork**.

Final verification (this file): every PLAN phase is present, tests pass, BUGS.md
has no unfixed items, the recording exists, and the PR is open on
`tkuhemiya/OpenRCT2` only.

## PR

https://github.com/tkuhemiya/OpenRCT2/pull/1

- Branch: `themiya/agent-text-api-17ff` → `develop`
- Remote: **only** `origin` → `https://github.com/tkuhemiya/OpenRCT2`
- `gh pr list --repo tkuhemiya/OpenRCT2 --head themiya/agent-text-api-17ff` → OPEN #1
- `gh pr list --repo OpenRCT2/OpenRCT2 --head themiya/agent-text-api-17ff` → empty
- Never pushed to `OpenRCT2/OpenRCT2`

## Phase checklist (PLAN.md)

| Phase | What | Status |
|---|---|---|
| 0 | `PLAN.md`, `PROGRESS.md`, branch `themiya/agent-text-api-17ff` | Done |
| 1 | Engine + API + ASCII renderer, no stubs | Done (`agent/openrct2_agent/`) |
| 2 | JSONL under `./logs`, `agent/README.md` | Done |
| 3 | Unit/e2e/edge tests, brute force, stronger-model play, `BUGS.md` | Done |
| 4 | Replay video + transcript | Done (`recordings/agent_play.mp4`) |
| 5 | PR on the fork only | Done (#1) |

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
`game.month`, `game.wait`, `game.research`, `game.breakdown`).

Full usage: `agent/README.md`.

## How to run

```bash
export PYTHONPATH=agent
python3 -m unittest discover -s agent/tests -v
python3 -m openrct2_agent.cli reset --seed 42 --scenario gentle_intro --session demo --text
python3 -m openrct2_agent.cli step --session demo --action hire_staff:handyman
```

## Tests (re-run at final verification)

```
python3 -m unittest discover -s agent/tests -v
Ran 62 tests in 8.465s
OK
```

- Heuristic wins `gentle_intro`, `forest_frontiers`, and `dynamite_dunes`.
- Brute force: **0 crashes**. Heuristic 12/12 intro, 10/10 then 6/6 Forest
  Frontiers, 8/8 Dynamite Dunes after B10.
- Composer 2.5 volume play + Grok 4.6 Medium g81/g82/g83: **3/3 HUD-only
  success** (including Dynamite Dunes). Clarity 4/5 → B12 text fixes.
- Clean `git archive` tree: 62/62 OK (no leftover session pickles).

## Bugs

See `BUGS.md`. **B1–B12 all Fixed.** No open blockers. Remaining notes in
BUGS.md (disconnected-ride WARN, all rides draw as `R`, large legal JSON) are
documented behaviour, not unfixed defects.

## Video / replay

No live OpenRCT2 GUI (no RCT2 assets). Human capture is a HUD/map replay:

| Artifact | Path |
|---|---|
| **Watch this** | `recordings/agent_play.mp4` (~18s, 72 frames, h264 976×1598) |
| Transcript | `recordings/agent_play_transcript.txt` |
| Machine replay | `recordings/replay.json` |
| How to watch | `WATCH.md` |

Gentle Glen (`gentle_intro`) seed 11, heuristic: **SUCCESS**, 121 guests,
rating 771. The agent never sees this video.

## Limitations (intentional)

- Python sim, not a running `openrct2` process.
- 18×16 map; rides are prebuilt layouts.
- Park value is scaled so Dynamite Dunes £25k is reachable on that map.
- Flat legal-action list capped at 800 ids.
