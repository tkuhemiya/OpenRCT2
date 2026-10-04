# Hooking this agent API into live OpenRCT2

The Python engine is the runnable backend in environments **without RCT2
data files**. When a real OpenRCT2 process is available, the same JSON
schema can be served from the C++ `GameState_t`.

## Why a Python engine exists

`openrct2-cli` still constructs a full `Context` (`src/openrct2-cli/Cli.cpp`)
and requires original RCT2 objects, title sequences, and g2 sprites.
Those assets are commercial and are not in this repository.

## Source mapping

| Agent field | OpenRCT2 |
|---|---|
| `GameState` | `OpenRCT2::GameState_t` (`src/openrct2/GameState.h`) |
| cash, loan, rating, guests, entrance fee | `Park::ParkData` (`src/openrct2/world/ParkData.h`) |
| `calculate_park_rating` | `Park::CalculateParkRating` (`src/openrct2/world/Park.cpp`) |
| `step()` query-then-execute | `GameAction::Query` / `Execute` (`src/openrct2/actions/GameAction.hpp`) |
| action names | `enum class GameCommand` (`src/openrct2/actions/GameCommand.h`) |
| objectives | `Scenario::Objective` (`src/openrct2/scenario/ScenarioObjective.h`) |
| Mar–Oct calendar | `Date.h` `MONTH_COUNT = 8` |
| plugin actions | `context.executeAction` in `distribution/scripting/openrct2.d.ts` |

## Live adapter (when assets exist)

1. Run `openrct2-cli` headless (`gOpenRCT2Headless = true`).
2. Load a plugin that:
   - On `interval.tick` / a custom action, serialises park, rides, guests, staff
     to the JSON shape produced by `structured_state()`.
   - Accepts the same `step` payloads and calls `context.executeAction`.
3. Point `ParkSession` at that process instead of `new_game()`.

A sketch plugin:

```javascript
registerPlugin({
    name: "agent-bridge",
    version: "1.0",
    authors: ["OpenRCT2 agent API"],
    type: "local",
    licence: "GPL-3.0",
    targetApiVersion: 114,
    main: function () {
        // Dump a text snapshot the Python API already speaks.
        console.log("agent-bridge ready; use the in-game console to query park.cash, map, rides.");
    }
});
```

## Action subset

Track-piece building (`placeTrack`) is intentionally **not** in the text
API: it is a visual, high-cardinality control problem. Agents place
**complete prebuilt rides**, which corresponds to `createRide` +
`placeTrackDesign` rather than tile-by-tile track.

Paths, land, stalls, staff, prices, loans, research, marketing, and
park open/close match the GameCommand list directly.
