# PROGRESS

## Current phase

Completeness audit (post Phase 5). Hard-requirement gaps closed; tests extended.

## Completed

- Phase 0–2: PLAN, engine, API, renderer, logging, README.
- Phase 3a: 47 unittest cases (unit + e2e + edge). All passing.
- Phase 3b: Brute-force 70 games, 0 crashes. Heuristic 10/10 intro, 8/8 Forest Frontiers.
- Phase 3c: Composer 2.5 and Grok 4.6 Medium play recovered from session pickles. Grok parks were connected and clean; Composer hit B7 (now fixed).
- Phase 3d: B1–B9 fixed and retested.
- Phase 4: `logs/agent_play.mp4` + transcript + render script. Also `/opt/cursor/artifacts/agent_play.mp4`.
- Phase 5: PR on fork https://github.com/tkuhemiya/OpenRCT2/pull/1
- Audit: internal sim events now write JSONL (`game.event`, `game.month`, `game.research`, `game.breakdown`); `apply_replay` / `replay_from` reconstructs a park from seed+actions; HTTP POST `/state` and `/legal_actions`; `max_tile_actions` actually trims tile ids (management actions always kept).

## Next step

Queued follow-ups (more e2e, edge/stronger-model, video, README, PR, DONE, synopsis) can run against this finished API.

## Open bugs

None unfixed.

## Decisions

1–9 as before.
10. Collect LLM results from `logs/sessions/*.pkl` rather than waiting on still-RUNNING cloud sub-agents (g71 pickle already has a finished success).
11. Persist one-shot CLI via pickle so README sequential commands actually work (B9).
12. `wait:0` is an error, not a synonym for `wait:1` (B8).
13. Completeness audit: in-game news (`_push_news`) is the source of `game.event` JSONL so month-end, research, breakdowns, and scenario result all hit `./logs`, not only the API wrappers.
14. Replay apply lives on `ParkSession.apply_replay` (alias `replay_from`), RPC `apply_replay`, HTTP `POST /replay`. Export remains `GET /replay`.
15. `list_legal_actions(max_tile_actions=)` keeps every non-tile action and truncates place/remove/buy origins so the LLM list stays bounded.

## Substitutions / failed tools

- Live OpenRCT2 window recording: no RCT2 assets. Substituted ffmpeg HUD replay.
- One Grok forest cloud sub-agent still marked RUNNING; used the completed `g71.pkl` session instead of blocking.
