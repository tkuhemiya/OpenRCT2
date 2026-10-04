"""Public agent API: reset, get_state, list_legal_actions, step, plus sessions."""

from __future__ import annotations

import copy
import json
import time
import uuid
from typing import Any, Optional

from . import logging_util
from .actions import execute
from .catalog import SCENARIOS
from .engine import GameState, new_game
from .legal import list_legal_actions as _list_legal
from .renderer import render_text, structured_state


class ParkSession:
    """One in-memory park. Deterministic for a given seed+scenario+action sequence."""

    def __init__(self, session_id: Optional[str] = None) -> None:
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.state: Optional[GameState] = None
        self.replay: dict[str, Any] = {"session_id": self.session_id, "seed": None, "scenario": None, "actions": []}
        self.created = time.time()
        self.api_calls = 0

    def reset(self, seed: int = 1, scenario: str = "forest_frontiers") -> dict[str, Any]:
        if scenario not in SCENARIOS:
            known = ", ".join(sorted(SCENARIOS))
            result = {
                "ok": False,
                "error": f"Unknown scenario {scenario!r}. Known: {known}.",
                "code": "unknown_scenario",
                "session_id": self.session_id,
            }
            logging_util.log_event("api.reset", session=self.session_id, ok=False, error=result.get("error"), code=result.get("code"))
            return result
        try:
            seed_i = int(seed)
        except (TypeError, ValueError):
            return {
                "ok": False,
                "error": f"seed must be an integer, got {seed!r}.",
                "code": "bad_seed",
                "session_id": self.session_id,
            }
        self.state = new_game(seed_i, SCENARIOS[scenario])
        self.replay = {
            "session_id": self.session_id,
            "seed": seed_i,
            "scenario": scenario,
            "actions": [],
        }
        self.api_calls += 1
        payload = self.get_state()
        payload["ok"] = True
        payload["error"] = None
        payload["message"] = f"New park '{SCENARIOS[scenario].name}' seed={seed_i}."
        logging_util.log_event(
            "api.reset",
            session=self.session_id,
            seed=seed_i,
            scenario=scenario,
            ok=True,
        )
        logging_util.log_event(
            "game.start",
            session=self.session_id,
            seed=seed_i,
            scenario=scenario,
            cash=self.state.cash,
            objective=self.state.objective,
        )
        return payload

    def _need_state(self) -> Optional[dict[str, Any]]:
        if self.state is None:
            return {
                "ok": False,
                "error": "No game in progress. Call reset(seed, scenario) first.",
                "code": "no_game",
                "session_id": self.session_id,
            }
        return None

    def get_state(self) -> dict[str, Any]:
        missing = self._need_state()
        if missing:
            logging_util.log_event("api.get_state", session=self.session_id, ok=False, code="no_game")
            return missing
        assert self.state is not None
        self.api_calls += 1
        data = structured_state(self.state)
        text = render_text(self.state)
        out = {
            "ok": True,
            "error": None,
            "session_id": self.session_id,
            "text": text,
            "state": data,
            "game_over": data["game_over"],
            "result": data["result"],
            "result_reason": data["result_reason"],
        }
        logging_util.log_event(
            "api.get_state",
            session=self.session_id,
            result=data["result"],
            guests=data["guests"]["in_park"],
            cash=data["finance"]["cash"],
            rating=data["rating"],
            month=data["date"]["months_elapsed"],
        )
        return out

    def list_legal_actions(self) -> dict[str, Any]:
        missing = self._need_state()
        if missing:
            logging_util.log_event("api.list_legal_actions", session=self.session_id, ok=False, code="no_game")
            return missing
        assert self.state is not None
        self.api_calls += 1
        legal = _list_legal(self.state)
        legal["ok"] = True
        legal["error"] = None
        legal["session_id"] = self.session_id
        logging_util.log_event(
            "api.list_legal_actions",
            session=self.session_id,
            count=legal.get("count", 0),
            game_over=legal.get("game_over", False),
        )
        return legal

    def step(self, action: Any) -> dict[str, Any]:
        missing = self._need_state()
        if missing:
            logging_util.log_event("api.step", session=self.session_id, ok=False, code="no_game")
            return missing
        assert self.state is not None
        self.api_calls += 1
        result = execute(self.state, action)
        result["session_id"] = self.session_id
        result["game_over"] = self.state.result != "undecided"
        result["result"] = self.state.result
        result["result_reason"] = self.state.result_reason
        if result.get("ok"):
            self.replay["actions"].append(copy.deepcopy(action) if not isinstance(action, str) else action)
        logging_util.log_event(
            "api.step",
            session=self.session_id,
            action=action,
            ok=result.get("ok"),
            code=result.get("code"),
            error=result.get("error"),
            message=result.get("message"),
            game_result=self.state.result,
            guests=self.state.num_guests,
            cash=self.state.cash,
            rating=self.state.rating,
        )
        if self.state.result != "undecided":
            logging_util.log_event(
                "game.over",
                session=self.session_id,
                result=self.state.result,
                reason=self.state.result_reason,
                guests=self.state.num_guests,
                cash=self.state.cash,
                rating=self.state.rating,
                months=self.state.months_elapsed,
            )
        # Include a compact post-step snapshot so agents need not always re-fetch.
        result["text"] = render_text(self.state)
        result["state"] = structured_state(self.state)
        return result

    def export_replay(self) -> dict[str, Any]:
        return dict(self.replay)


class AgentAPI:
    """Multi-session facade used by HTTP/CLI. Default session is 'default'."""

    def __init__(self) -> None:
        self.sessions: dict[str, ParkSession] = {}

    def session(self, session_id: Optional[str] = None) -> ParkSession:
        sid = session_id or "default"
        if sid not in self.sessions:
            self.sessions[sid] = ParkSession(sid)
        return self.sessions[sid]

    def reset(self, seed: int = 1, scenario: str = "forest_frontiers", session_id: Optional[str] = None) -> dict[str, Any]:
        return self.session(session_id).reset(seed, scenario)

    def get_state(self, session_id: Optional[str] = None) -> dict[str, Any]:
        return self.session(session_id).get_state()

    def list_legal_actions(self, session_id: Optional[str] = None) -> dict[str, Any]:
        return self.session(session_id).list_legal_actions()

    def step(self, action: Any, session_id: Optional[str] = None) -> dict[str, Any]:
        return self.session(session_id).step(action)

    def dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        """JSON-RPC-ish: {cmd, ...params, session_id?}."""
        if not isinstance(payload, dict):
            return {"ok": False, "error": "Payload must be a JSON object.", "code": "bad_payload"}
        cmd = payload.get("cmd") or payload.get("method") or payload.get("op")
        sid = payload.get("session_id")
        try:
            if cmd in ("reset", "new_game"):
                return self.reset(payload.get("seed", 1), payload.get("scenario", "forest_frontiers"), sid)
            if cmd in ("get_state", "state"):
                return self.get_state(sid)
            if cmd in ("list_legal_actions", "legal", "actions"):
                return self.list_legal_actions(sid)
            if cmd in ("step", "act"):
                return self.step(payload.get("action"), sid)
            if cmd in ("replay", "export_replay"):
                return {"ok": True, "replay": self.session(sid).export_replay()}
            if cmd in ("help",):
                return {
                    "ok": True,
                    "commands": ["reset", "get_state", "list_legal_actions", "step", "replay"],
                    "scenarios": sorted(SCENARIOS),
                    "example": {
                        "cmd": "reset",
                        "seed": 42,
                        "scenario": "gentle_intro",
                    },
                }
            return {
                "ok": False,
                "error": f"Unknown cmd {cmd!r}. Try help, reset, get_state, list_legal_actions, step.",
                "code": "unknown_cmd",
            }
        except Exception as exc:  # noqa: BLE001
            logging_util.log_event("api.dispatch_error", cmd=cmd, error=str(exc))
            return {"ok": False, "error": f"Internal error: {exc}", "code": "internal_error"}


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
