# BUGS

Bugs found while building and testing the OpenRCT2 text agent API.

| ID | Symptom | Cause | Status |
|---|---|---|---|
| B1 | Package import crash (`IndentationError` in `engine.py`) | Spawn-rate edit left leftover indent on two lines in `_spawn_guests`. | **Fixed** (re-indent). Unit tests import cleanly. |
| B2 | `reset` of an unknown scenario raised `TypeError` instead of returning an error object | `log_event(..., **result)` collided with an explicit `ok=` keyword. | **Fixed** (log only `error`/`code`). Test `test_unknown_scenario`. |
| B3 | Later tests crashed with `FileNotFoundError` on a log path | `LoggingTests` pointed the logger at a `TemporaryDirectory` that was deleted; `_path` stayed stale. | **Fixed** (mkdir + fallback reconfigure; test restores default log). |
| B4 | (watch) Heuristic might fail `forest_frontiers` (250 guests / year) | Classic objective is tighter than `gentle_intro`. Smoke test only requires a non-crash + some buildings. | **Open / accepted.** `gentle_intro` e2e must win; forest_frontiers is the hard scenario for LLM quality play. |

Brute-force and LLM play findings are appended below as they appear.

## Brute-force

_Not run yet._

## LLM play

_Not run yet._
