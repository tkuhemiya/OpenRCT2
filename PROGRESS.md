# PROGRESS

## Current phase

Human-playable isometric park on the existing engine. Catalog objects are
**drawn in code** (`openrct2_agent/art.py`) instead of per-object PNGs.
Sounds are synthesized (`audio.py`). Open `http://127.0.0.1:8765/play`.

Tests: `python3 -m unittest discover -s agent/tests -v` → **71/71 OK**
(includes click-to-build, painter coverage, agent-step pixel change).

## Original brief

**All PLAN phases 0–5 complete.** Final verification passed. See `DONE.md`.

Verified just now:

- Tests: `python3 -m unittest discover -s agent/tests -v` → **71/71 OK**
- `BUGS.md`: B1–B12 **Fixed**; no unfixed bugs
- Recording: `recordings/agent_play_gameplay.mp4` (~40s top-down sprites) plus ASCII `recordings/agent_play.mp4`
- PR: https://github.com/tkuhemiya/OpenRCT2/pull/1 OPEN on **fork only**
- Origin is `tkuhemiya/OpenRCT2`; upstream `OpenRCT2/OpenRCT2` has no matching PR

## Next step

None for the original overnight brief. `DONE.md` is written.

## Fork PR check (`git remote -v`)

Exact remotes (token redacted):

```
origin	https://x-access-token:[REDACTED]@github.com/tkuhemiya/OpenRCT2 (fetch)
origin	https://x-access-token:[REDACTED]@github.com/tkuhemiya/OpenRCT2 (push)
```

Sanitized origin: `https://github.com/tkuhemiya/OpenRCT2`

- Only remote is `origin`. There is **no** `upstream` remote.
- Target is **`tkuhemiya/OpenRCT2`**, not `OpenRCT2/OpenRCT2`.
- Explicit check: `gh pr list --repo tkuhemiya/OpenRCT2 --head themiya/agent-text-api-17ff`
  → OPEN PR **#1** https://github.com/tkuhemiya/OpenRCT2/pull/1  
  head `tkuhemiya/OpenRCT2` / `themiya/agent-text-api-17ff` → `develop`  
  `isCrossRepository: false`
- Explicit check: `gh pr list --repo OpenRCT2/OpenRCT2 --head themiya/agent-text-api-17ff` → **[]**
- Explicit check: `gh pr list --repo OpenRCT2/OpenRCT2 --search "agent-text-api"` → **[]**

Did **not** open or push anything against `OpenRCT2/OpenRCT2`. Feature branch is already on the fork; no extra push required for this check.

## README + clean tests

README matches the live API (setup, reference, example loop, limitations).
Unused `pytest` pin removed from `agent/requirements.txt`.

**Clean checkout:** `git archive HEAD` → `/tmp/rct-clean-*` with no session
pickles. `python3 -m unittest discover -s agent/tests -v` → **62/62 OK**
(8.6s). Same from `cd agent && python3 -m unittest discover -s tests -v`.
README Python/CLI snippets ran successfully on that tree.

## Recording (this turn)

Live OpenRCT2 GUI capture is not possible (no RCT2 assets). Substitution:

**Watch this:** `recordings/agent_play.mp4`

| Artifact | Path |
|---|---|
| MP4 (~18s, 4 fps, 72 HUD frames, 976×1598 h264) | `recordings/agent_play.mp4` |
| Step-by-step ASCII transcript | `recordings/agent_play_transcript.txt` |
| Machine replay JSON | `recordings/replay.json` |
| Start / end stills | `recordings/agent_play_start.png`, `recordings/agent_play_end.png` |
| How to watch / regenerate | `WATCH.md` |
| Render script | `agent/scripts/render_replay.py` |
| Play script | `agent/scripts/play_and_record.py` |
| Cloud copies | `/opt/cursor/artifacts/agent_play.mp4` |

Playthrough: heuristic on **Gentle Glen** (`gentle_intro`) seed **11** — **SUCCESS**, 121 guests, rating 771 (needed 80 / 600) in 72 steps.

How to watch: `vlc recordings/agent_play.mp4` or `less recordings/agent_play_transcript.txt`.

`logs/agent_play.mp4` is the gitignored working copy (`logs/*.mp4` is ignored); `recordings/` is committed.

## Completed

- Phase 0–2: PLAN, engine, API, renderer, logging, README.
- Phase 3a: **62** unittest cases (unit + e2e + expanded edge). All passing.
- Phase 3b: Volume brute-force + 6 Composer 2.5 full games. **0 crashes**.
- Phase 3c: Grok 4.6 Medium g81/g82/g83 all **success**. Text judged playable (4/5); B12 fixed.
- Phase 3d: B1–B12 fixed and retested.
- Phase 4: `recordings/agent_play.mp4` + transcript + render script + `WATCH.md`.
- Phase 5: PR on fork https://github.com/tkuhemiya/OpenRCT2/pull/1

## This edge + Grok round

### Edge tests added

Invalid/stale ids, game-over legal list, mid-game reset, odd seeds (`0`, negative, `2**32`, `"1.5"`), `wait:16` bound, have_fun under 15s, `max_steps` cap, HTTP 400 bad JSON / 404 unknown path, failed apply_replay, HUD clarity assertions.

### Grok 4.6 Medium (stronger model)

| Session | Scenario | Result | Clarity |
|---|---|---|---|
| g81 | gentle_intro / 81 | success 91g / 737 | 4/5 |
| g82 | forest_frontiers / 82 | success 302g / 750 | 4/5 |
| g83 | dynamite_dunes / 83 | success £26.5k value | 4/5 |

0 crashes, 0 invalid-action storms. Text was clear enough to win all three after reading HUD + legal ids (no heuristic import).

### Fixes from their notes (B12)

Objective names the last month; map has a tens ruler; warnings no longer print `! (none)`; invented `Name [id]`; legal truncate keeps ≥1 origin per ride/stall type; north-from-E tip.

## Open bugs

None unfixed.

## Decisions

1–17 as before.
18. Stronger-model HUD complaints that did not block wins still got fixed (B12) so the next agent is less likely to place isolated buildings or miss umbrella stalls.
20. Follow-up: original pixel-art sprites in `agent/assets/sprites/` and a
    top-down gameplay MP4 at `recordings/agent_play_gameplay.mp4` (not a
    terminal dump). Still no RCT2 data files.
