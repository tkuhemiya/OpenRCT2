"""Human park client: click-to-build mapped onto ParkSession.step."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional

from .api import AgentAPI, dumps
from .art import layout_for, pixel_to_tile
from .audio import sfx, sfx_for_action
from .catalog import RIDES, SCENARIOS, SCENERY, STAFF_HIRE_COST, STALLS
from .engine import GameState, money_str
from .players import heuristic_policy
from .visual import VisualPark, caption_for

WEB = Path(__file__).resolve().parents[1] / "web"
_VIS = VisualPark()


def _session(api: AgentAPI, sid: Optional[str]):
    return api.session(sid)


def status_payload(state: GameState, session) -> dict[str, Any]:
    news = state.news[-1].text if state.news else ""
    last = session.replay["actions"][-1] if session.replay.get("actions") else None
    return {
        "ok": True,
        "session_id": session.session_id,
        "game_over": state.result != "undecided",
        "result": state.result,
        "result_reason": state.result_reason,
        "park_name": state.park_name,
        "park_open": state.park_open,
        "cash": state.cash,
        "cash_text": money_str(state.cash),
        "guests": state.num_guests,
        "rating": state.rating,
        "rating_text": f"{state.rating // 100}.{state.rating % 100:02d}",
        "date": f"{state.day} {state.month_name} Year {state.year}",
        "weather": state.weather,
        "loan": state.loan,
        "entrance_fee": state.entrance_fee,
        "objective": state.objective,
        "warnings": list(state.warnings),
        "news": news,
        "n_actions": len(session.replay.get("actions") or []),
        "last_action": last,
        "caption": caption_for(last) if last else "New park",
        "sfx": sfx_for_action(last) if last else "click",
        "rides": [
            {
                "id": r.id,
                "spec_id": r.spec_id,
                "name": r.name or r.spec.name,
                "status": r.status,
                "x": r.x,
                "y": r.y,
                "w": r.w,
                "h": r.h,
                "price": r.price,
            }
            for r in state.rides
        ],
        "stalls": [
            {
                "id": s.id,
                "spec_id": s.spec_id,
                "name": s.name or s.spec.name,
                "x": s.x,
                "y": s.y,
            }
            for s in state.stalls
        ],
        "staff": [{"id": s.id, "kind": s.kind} for s in state.staff],
        "invented_rides": [i for i in state.invented if i in RIDES],
        "invented_stalls": [i for i in state.invented if i in STALLS],
        "map_w": state.map_w,
        "map_h": state.map_h,
        "entrance": list(state.entrance),
    }


def catalog_payload(state: Optional[GameState] = None) -> dict[str, Any]:
    invented = set(state.invented) if state is not None else None

    def ride_row(spec) -> dict[str, Any]:
        return {
            "id": spec.id,
            "name": spec.name,
            "category": spec.category,
            "cost": spec.build_cost,
            "cost_text": money_str(spec.build_cost),
            "footprint": list(spec.footprint),
            "excitement": spec.excitement,
            "invented": True if invented is None else spec.id in invented,
        }

    def stall_row(spec) -> dict[str, Any]:
        return {
            "id": spec.id,
            "name": spec.name,
            "kind": spec.kind,
            "cost": spec.build_cost,
            "cost_text": money_str(spec.build_cost),
            "footprint": list(spec.footprint),
            "invented": True if invented is None else spec.id in invented,
        }

    return {
        "ok": True,
        "scenarios": [
            {"id": s.id, "name": s.name, "details": s.details} for s in SCENARIOS.values()
        ],
        "rides": [ride_row(s) for s in RIDES.values()],
        "stalls": [stall_row(s) for s in STALLS.values()],
        "scenery": [
            {"id": s.id, "name": s.name, "cost": s.build_cost, "cost_text": money_str(s.build_cost)}
            for s in SCENERY.values()
        ],
        "staff": [
            {"id": k, "name": k.title(), "cost": v, "cost_text": money_str(v)}
            for k, v in STAFF_HIRE_COST.items()
        ],
    }


def action_from_click(
    state: GameState,
    tool: str,
    item: str,
    x: int,
    y: int,
) -> tuple[Optional[str], Optional[str]]:
    if not state.in_bounds(x, y):
        return None, "That click is off the map."
    tool = (tool or "inspect").strip()
    item = (item or "").strip()
    t = state.tile(x, y)
    if tool == "inspect":
        return f"inspect_tile:{x},{y}", None
    if tool == "path":
        return f"place_path:{x},{y}", None
    if tool == "remove_path":
        return f"remove_path:{x},{y}", None
    if tool in ("land", "buy_land"):
        return f"buy_land:{x},{y}", None
    if tool == "ride":
        if not item:
            return None, "Pick a ride from the list first."
        return f"place_ride:{item},{x},{y}", None
    if tool == "stall":
        if not item:
            return None, "Pick a stall from the list first."
        return f"place_stall:{item},{x},{y}", None
    if tool == "scenery":
        if not item:
            return None, "Pick scenery first."
        return f"place_scenery:{item},{x},{y}", None
    if tool == "demolish":
        if t.ride_id is not None:
            return f"demolish_ride:{t.ride_id}", None
        if t.stall_id is not None:
            return f"demolish_stall:{t.stall_id}", None
        if t.kind == "path":
            return f"remove_path:{x},{y}", None
        return None, "Nothing to demolish on that tile."
    if tool == "open_ride" and t.ride_id is not None:
        return f"set_ride_status:{t.ride_id},open", None
    return None, f"Unknown tool {tool!r}."


def click_park(api: AgentAPI, body: dict[str, Any]) -> dict[str, Any]:
    sid = body.get("session_id")
    session = _session(api, sid)
    if session.state is None:
        return {"ok": False, "error": "No game in progress.", "code": "no_game"}
    state = session.state
    tool = str(body.get("tool") or "inspect")
    item = str(body.get("item") or "")
    if "x" in body and "y" in body:
        try:
            x, y = int(body["x"]), int(body["y"])
        except (TypeError, ValueError):
            return {"ok": False, "error": "x and y must be integers.", "code": "bad_params"}
    elif "px" in body and "py" in body:
        try:
            px, py = float(body["px"]), float(body["py"])
        except (TypeError, ValueError):
            return {"ok": False, "error": "px and py must be numbers.", "code": "bad_params"}
        hud = bool(body.get("hud", True))
        lay = layout_for(state.map_w, state.map_h, hud=hud)
        x, y = pixel_to_tile(px, py, lay)
    else:
        return {"ok": False, "error": "Pass x,y or px,py.", "code": "bad_params"}
    action, err = action_from_click(state, tool, item, x, y)
    if err:
        return {"ok": False, "error": err, "code": "bad_click", "x": x, "y": y, "tool": tool}
    out = session.step(action)
    out["x"] = x
    out["y"] = y
    out["tool"] = tool
    out["action"] = action
    out["caption"] = caption_for(action)
    out["sfx"] = sfx_for_action(action) if out.get("ok") else "error"
    if session.state is not None:
        out["status"] = status_payload(session.state, session)
    return out


def agent_steps(api: AgentAPI, body: dict[str, Any]) -> dict[str, Any]:
    sid = body.get("session_id")
    session = _session(api, sid)
    if session.state is None:
        return {"ok": False, "error": "No game in progress.", "code": "no_game"}
    try:
        n = max(1, min(20, int(body.get("n") or 1)))
    except (TypeError, ValueError):
        n = 1
    applied: list[Any] = []
    last: dict[str, Any] = {"ok": True}
    for _ in range(n):
        action = heuristic_policy(session)
        if not action:
            break
        last = session.step(action)
        applied.append({"action": action, "ok": last.get("ok"), "message": last.get("message")})
        if not last.get("ok") or session.state is None or session.state.result != "undecided":
            break
    out = {
        "ok": True,
        "error": None,
        "applied": applied,
        "count": len(applied),
        "caption": caption_for(applied[-1]["action"]) if applied else "Idle",
        "sfx": sfx_for_action(applied[-1]["action"]) if applied else "click",
    }
    if session.state is not None:
        out["status"] = status_payload(session.state, session)
        out["game_over"] = session.state.result != "undecided"
        out["result"] = session.state.result
    return out


def render_png(api: AgentAPI, qs: dict[str, list[str]]) -> bytes:
    sid = (qs.get("session_id") or [None])[0]
    session = _session(api, sid)
    if session.state is None:
        session.reset(11, "gentle_intro")
    assert session.state is not None
    tick = int((qs.get("tick") or ["0"])[0])
    caption = (qs.get("caption") or [""])[0]
    hud = (qs.get("hud") or ["1"])[0] not in ("0", "false", "no")
    highlight = None
    if qs.get("hx"):
        highlight = (
            int(qs["hx"][0]),
            int(qs.get("hy", ["0"])[0]),
            int(qs.get("hw", ["1"])[0]),
            int(qs.get("hh", ["1"])[0]),
        )
    ghost = None
    if qs.get("ghost"):
        parts = qs["ghost"][0].split(",")
        if len(parts) >= 4:
            ghost = (parts[0], parts[1], int(parts[2]), int(parts[3]))
    img = _VIS.render(session.state, caption=caption, tick=tick, highlight=highlight, ghost=ghost, hud=hud)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def meta_payload(api: AgentAPI, sid: Optional[str]) -> dict[str, Any]:
    session = _session(api, sid)
    if session.state is None:
        session.reset(11, "gentle_intro")
    assert session.state is not None
    lay = layout_for(session.state.map_w, session.state.map_h, hud=True)
    return {
        "ok": True,
        "tw": lay.tw,
        "th": lay.th,
        "ox": lay.ox,
        "oy": lay.oy,
        "hud": lay.hud,
        "width": lay.width,
        "height": lay.height,
        "map_w": lay.map_w,
        "map_h": lay.map_h,
    }


def _html() -> bytes:
    path = WEB / "index.html"
    if path.is_file():
        return path.read_bytes()
    return b"<html><body>Missing agent/web/index.html</body></html>"


def handle_get(path: str, qs: dict[str, list[str]], api: AgentAPI) -> tuple[int, str, bytes]:
    if path in ("/play", "/play/", "/play/index.html"):
        return 200, "text/html; charset=utf-8", _html()
    if path.startswith("/play/frame"):
        return 200, "image/png", render_png(api, qs)
    if path == "/play/status":
        sid = (qs.get("session_id") or [None])[0]
        session = _session(api, sid)
        if session.state is None:
            return 200, "application/json; charset=utf-8", dumps({"ok": False, "code": "no_game"}).encode()
        return 200, "application/json; charset=utf-8", dumps(status_payload(session.state, session)).encode()
    if path == "/play/catalog":
        sid = (qs.get("session_id") or [None])[0]
        session = _session(api, sid)
        return 200, "application/json; charset=utf-8", dumps(catalog_payload(session.state)).encode()
    if path == "/play/meta":
        sid = (qs.get("session_id") or [None])[0]
        return 200, "application/json; charset=utf-8", dumps(meta_payload(api, sid)).encode()
    if path.startswith("/play/sfx/"):
        name = path.rsplit("/", 1)[-1]
        return 200, "audio/wav", sfx(name)
    return 404, "application/json; charset=utf-8", dumps({"ok": False, "error": f"Unknown GET {path}", "code": "not_found"}).encode()


def handle_post(path: str, body: dict[str, Any], api: AgentAPI) -> tuple[int, str, bytes]:
    if path in ("/play/click", "/play/act"):
        return 200, "application/json; charset=utf-8", dumps(click_park(api, body)).encode()
    if path in ("/play/agent_step", "/play/agent"):
        return 200, "application/json; charset=utf-8", dumps(agent_steps(api, body)).encode()
    if path == "/play/reset":
        sid = body.get("session_id")
        out = api.reset(body.get("seed", 1), body.get("scenario", "gentle_intro"), sid)
        return 200, "application/json; charset=utf-8", dumps(out).encode()
    return 404, "application/json; charset=utf-8", dumps({"ok": False, "error": f"Unknown POST {path}", "code": "not_found"}).encode()


