# PROGRESS

## Current phase

Phase 1 — implement API + renderer (running tests next)

## Completed

- Inspected repo: OpenRCT2, origin `tkuhemiya/OpenRCT2`.
- PLAN.md: Python sim mirroring GameState_t / GameActions; cannot boot C++ without RCT2 assets.
- Branch `themiya/agent-text-api-17ff`.
- Engine, actions, legal-action enumerator, ASCII renderer, HTTP + stdio API, logging, heuristic/random players, unit + e2e tests, brute-force and replay scripts.

## Next step

Run unit tests, fix failures, then logging README polish (Phase 2 is largely done), then brute-force + LLM play.

## Open bugs

None confirmed yet — about to run the test suite.

## Decisions

1. Do not compile OpenRCT2; missing RCT2 data files.
2. Prebuilt rides, not track pieces.
3. 18×16 map for text readability.
4. Money in integer pence.
5. RCT calendar: 8 months (March–October).
6. Push only to `tkuhemiya/OpenRCT2`.
7. Logs under repo-root `./logs`.
8. Cheap model = Composer 2.5; quality = Grok 4.6 Medium.

## Substitutions / failed tools

None yet.
