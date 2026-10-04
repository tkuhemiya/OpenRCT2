"""Structured JSONL logging of API calls and key simulation events."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_lock = threading.Lock()
_path: Optional[Path] = None


def default_log_dir() -> Path:
    # Prefer ./logs relative to CWD (hard requirement); fall back next to the package.
    cwd = Path.cwd() / "logs"
    try:
        cwd.mkdir(parents=True, exist_ok=True)
        return cwd
    except OSError:
        alt = Path(__file__).resolve().parents[2] / "logs"
        alt.mkdir(parents=True, exist_ok=True)
        return alt


def configure(path: Optional[str] = None) -> Path:
    global _path
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        _path = p
        return p
    log_dir = default_log_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _path = log_dir / f"agent-{os.getpid()}-{ts}.jsonl"
    return _path


def log_path() -> Path:
    global _path
    if _path is None:
        configure()
    assert _path is not None
    return _path


def log_event(kind: str, **fields: Any) -> None:
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        **fields,
    }
    line = json.dumps(rec, default=str, ensure_ascii=False)
    p = log_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with p.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        # Temp dirs from tests can vanish; fall back to ./logs.
        global _path
        _path = None
        p = log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with p.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
