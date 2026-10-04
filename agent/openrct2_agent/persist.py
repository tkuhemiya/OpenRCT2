"""File-backed ParkSession store so CLI invocations share a game."""

from __future__ import annotations

import pickle
from pathlib import Path

from .api import ParkSession


def session_dir() -> Path:
    d = Path.cwd() / "logs" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def session_path(session_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in session_id)
    return session_dir() / f"{safe}.pkl"


def load_session(session_id: str) -> ParkSession:
    p = session_path(session_id)
    if not p.exists():
        return ParkSession(session_id)
    with p.open("rb") as f:
        return pickle.load(f)


def save_session(session: ParkSession) -> None:
    with session_path(session.session_id).open("wb") as f:
        pickle.dump(session, f)
