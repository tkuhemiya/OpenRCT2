# PROGRESS

## Current phase

Phase 3–4 wrapping up. Waiting on background LLM play reports, then DONE.md.

## Completed

- Phase 0: PLAN.md; cannot boot C++ OpenRCT2 without RCT2 assets; Python GameState/GameAction mirror.
- Phase 1: Full API (reset, get_state, list_legal_actions, step) + ASCII renderer. No stubs.
- Phase 2: JSONL logs under `./logs`; `agent/README.md` with HTTP/stdio/Python examples.
- Phase 3a: 30 unittest cases (unit + e2e). All passing, including heuristic wins on `gentle_intro` and `forest_frontiers`.
- Phase 3b: Brute-force 70 games after balance fixes, **0 crashes**. Heuristic 10/10 intro, 8/8 Forest Frontiers.
- Phase 3d: Bugs B1–B6 fixed and retested. B7 documented.
- Phase 4: Replay video `logs/agent_play.mp4` (also `/opt/cursor/artifacts/agent_play.mp4`) + transcript + `agent/scripts/render_replay.py`. Agent loop stays text-only; ffmpeg renders HUD/map frames for humans.
- Phase 5: Branch `themiya/agent-text-api-17ff` pushed to **fork** `tkuhemiya/OpenRCT2` (confirmed via `git remote -v`). PR: https://github.com/tkuhemiya/OpenRCT2/pull/1

## Next step

Incorporate Composer 2.5 / Grok 4.6 Medium play reports into BUGS.md, then write DONE.md and update the PR.

## Open bugs

None blocking. B7 (path-id order) is fixed; LLM play reports still incoming.


## Decisions

1. Do not compile OpenRCT2; missing RCT2 data files.
2. Prebuilt rides, not track pieces.
3. 18×16 map for text readability.
4. Money in integer pence.
5. RCT calendar: 8 months (March–October).
6. Push only to `tkuhemiya/OpenRCT2`.
7. Logs under repo-root `./logs`.
8. Cheap model = Composer 2.5 (`composer-2.5`); quality = Grok 4.6 Medium (`cursor-grok-4.6-medium`).
9. Human video is an ffmpeg capture of the text HUD, not a GUI OpenRCT2 window (no assets).

## Substitutions / failed tools

None. Requested sub-agent models were available. Screen recording of a live OpenRCT2 window is impossible here (no RCT2 files); substituted replay MP4 + transcript as specified.
