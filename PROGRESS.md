# PROGRESS

## Current phase

Phase 3b e2e brute-force round complete (post-audit). B10–B11 found, fixed, retested.

## Completed

- Phase 0–2: PLAN, engine, API, renderer, logging, README.
- Phase 3a: 49 unittest cases (unit + e2e + edge). All passing.
- Phase 3b: Volume brute-force + 6 Composer 2.5 full games. **0 crashes**.
- Phase 3c: Composer 2.5 and Grok 4.6 Medium play recovered from session pickles. Grok parks were connected and clean; Composer hit B7 (now fixed).
- Phase 3d: B1–B11 fixed and retested.
- Phase 4: `logs/agent_play.mp4` + transcript + render script. Also `/opt/cursor/artifacts/agent_play.mp4`.
- Phase 5: PR on fork https://github.com/tkuhemiya/OpenRCT2/pull/1
- Audit: internal sim events now write JSONL (`game.event`, `game.month`, `game.wait`, `game.research`, `game.breakdown`); `apply_replay` / `replay_from`; HTTP POST `/state` and `/legal_actions`; tile-id cap.

## This e2e round

### Local volume (heuristic + random)

- `gentle_intro`: 12/12 heuristic wins, 40 random, 0 crashes.
- `forest_frontiers`: 10/10 then 6/6 heuristic wins after calendar fix, 0 crashes.
- `dynamite_dunes`: 0/6 then **8/8** after B10, 0 crashes.
- `have_fun`: 4/4 heuristic time-cap wins, 0 crashes.

### Cheap-model sub-agents (Composer 2.5)

| Session | Scenario | Result |
|---|---|---|
| bf-c51 | gentle_intro / 51 | success 148g / 769 |
| bf-c52 | gentle_intro / 52 | success 149g / 757 |
| bf-c53 | gentle_intro / 53 | success 139g / 754 |
| bf-c54 | forest_frontiers / 54 | success 306g / 766 |
| bf-c55 | forest_frontiers / 55 | success 310g / 741 |
| bf-c56 | dynamite_dunes / 56 | failure £12.8k value (B10, fixed after) |

0 invalid-action storms, 0 process crashes.

### Logs

Confirmed on a winning Forest Frontiers run (`logs/e2e-event-check-r3.jsonl`): `game.start`, `game.event` (start/month/success), `game.month`, `game.wait`, `game.over`. `months_elapsed` is 1 after `wait:1`.

## Next step

Queued follow-ups: edge + stronger-model play, video, README polish, PR, DONE, synopsis.

## Open bugs

None unfixed.

## Decisions

1–15 as before.
16. Dynamite Dunes £25,000 stays the classic target; park-value formula is scaled to the 18×16 map so a built park can actually hit it (B10).
17. `wait:N` always finishes N months of calendar even if the objective completes mid-month, so JSONL month events and `months_elapsed` stay honest (B11).
