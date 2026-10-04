"""Programmatic park sound effects. No sampled RCT2 audio."""

from __future__ import annotations

import io
import math
import struct
import wave
from typing import Callable

SR = 22050


def _env(i: int, n: int, attack: int = 80, release: int = 400) -> float:
    a = min(1.0, i / max(1, attack))
    r = min(1.0, (n - i) / max(1, release))
    return a * r


def _tone(freq: float, ms: int, vol: float = 0.35, wave_fn: Callable[[float], float] | None = None) -> list[int]:
    n = int(SR * ms / 1000)
    fn = wave_fn or math.sin
    out: list[int] = []
    for i in range(n):
        t = i / SR
        sample = vol * _env(i, n) * fn(2 * math.pi * freq * t)
        out.append(int(max(-1, min(1, sample)) * 32767))
    return out


def _square(x: float) -> float:
    return 1.0 if math.sin(x) >= 0 else -1.0


def _noise(ms: int, vol: float = 0.2) -> list[int]:
    n = int(SR * ms / 1000)
    out: list[int] = []
    seed = 1234567
    for i in range(n):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        sample = vol * _env(i, n, 20, 200) * ((seed / 0x7FFFFFFF) * 2 - 1)
        out.append(int(sample * 32767))
    return out


def _join(*parts: list[int]) -> list[int]:
    acc: list[int] = []
    for p in parts:
        acc.extend(p)
    return acc


def _silence(ms: int) -> list[int]:
    return [0] * int(SR * ms / 1000)


def wav_bytes(samples: list[int]) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    return buf.getvalue()


def _scream(seed: int) -> list[int]:
    freq = 420 + (seed * 37) % 380
    return _join(_tone(freq, 90, 0.22), _tone(freq * 0.7, 140, 0.18))


def _lift(freq: float) -> list[int]:
    return _join(_tone(freq, 80, 0.2, _square), _tone(freq * 1.25, 120, 0.16))


def sfx(name: str) -> bytes:
    """Named UI/game cue. Covers RCT2 SoundId names plus the /play aliases."""
    key = name.lower().replace(".wav", "").replace("-", "_")
    if key in ("place", "path", "build", "place_item"):
        samples = _join(_tone(220, 40, 0.25, _square), _tone(330, 80, 0.3, _square))
    elif key in ("click_1", "click_2", "click_3", "click", "ui"):
        samples = _tone(900 + 80 * (int(key[-1]) if key[-1].isdigit() else 4), 35, 0.22, _square)
    elif key in ("cash", "buy", "purchase"):
        samples = _join(_tone(880, 70, 0.28), _silence(20), _tone(1320, 110, 0.32))
    elif key in ("open", "fanfare", "gates", "door_open", "window_open"):
        samples = _join(_tone(523, 90, 0.28), _tone(659, 90, 0.28), _tone(784, 90, 0.3), _tone(1046, 180, 0.34))
    elif key in ("door_close", "portcullis", "block_brake_close"):
        samples = _join(_tone(180, 80, 0.3, _square), _noise(60, 0.12))
    elif key in ("wait", "month"):
        samples = _join(_tone(196, 120, 0.22), _tone(247, 160, 0.2))
    elif key in ("error", "deny"):
        samples = _join(_tone(140, 160, 0.35, _square), _tone(110, 180, 0.3, _square))
    elif key in ("cheer", "success", "applause"):
        samples = _join(_noise(80, 0.12), _tone(784, 80, 0.25), _tone(1046, 160, 0.3))
    elif key in ("hire",):
        samples = _join(_tone(660, 60, 0.25), _tone(880, 90, 0.28))
    elif key in ("demolish", "remove", "crash"):
        samples = _join(_noise(140, 0.28), _tone(90, 80, 0.2, _square))
    elif key in ("music", "loop"):
        melody = [262, 330, 392, 330, 349, 440, 523, 440, 392, 494, 587, 494, 523, 659, 784, 523]
        samples = []
        for i, f in enumerate(melody):
            samples.extend(_tone(f, 140, 0.12 + 0.04 * (i % 2), _square))
    elif key.startswith("scream"):
        samples = _scream(sum(ord(c) for c in key))
    elif key.startswith("laugh"):
        samples = _join(_tone(520, 50, 0.2), _tone(640, 70, 0.18), _tone(480, 80, 0.16))
    elif key.startswith("cough"):
        samples = _noise(90, 0.18)
    elif key == "rain":
        samples = _noise(400, 0.12)
    elif key in ("thunder_1", "thunder_2", "thunder"):
        samples = _join(_noise(80, 0.3), _tone(60, 220, 0.28, _square))
    elif "water" in key or key == "laying_out_water":
        samples = _join(_noise(70, 0.1), _tone(280, 90, 0.16))
    elif "lift" in key:
        samples = _lift(180 if "wood" in key else 220)
    elif "friction" in key or "track" in key:
        samples = _noise(160, 0.14)
    elif key in ("train_whistle", "tram"):
        samples = _join(_tone(620, 120, 0.22), _tone(520, 160, 0.2))
    elif key == "train_departing":
        samples = _join(_tone(140, 80, 0.2, _square), _tone(110, 200, 0.16, _square))
    elif key == "go_kart_engine":
        samples = _join(_tone(90, 80, 0.22, _square), _tone(120, 160, 0.2, _square))
    elif key in ("ride_launch_1", "ride_launch_2", "brake_release", "block_brake_release"):
        samples = _join(_noise(40, 0.16), _tone(300, 120, 0.22))
    elif key == "balloon_pop":
        samples = _join(_noise(30, 0.25), _tone(900, 40, 0.2))
    elif key == "mechanic_fix":
        samples = _join(_tone(240, 40, 0.2, _square), _tone(180, 50, 0.18, _square), _tone(300, 70, 0.2))
    elif key == "toilet_flush":
        samples = _join(_noise(80, 0.12), _tone(200, 180, 0.14))
    elif key == "quack":
        samples = _join(_tone(320, 70, 0.22), _tone(240, 90, 0.18))
    elif key == "news_item":
        samples = _join(_tone(784, 60, 0.22), _tone(988, 80, 0.2))
    elif "haunted" in key:
        samples = _scream(99)
    else:
        samples = _tone(1000, 40, 0.2, _square)
    return wav_bytes(samples)


def sfx_for_action(action: str) -> str:
    a = str(action)
    if a.startswith("place_path") or a.startswith("place_scenery"):
        return "place_item"
    if a.startswith("place_ride:go_karts"):
        return "go_kart_engine"
    if a.startswith("place_ride:haunted"):
        return "haunted_house_scare"
    if a.startswith("place_ride:") and any(
        tag in a for tag in ("log_flume", "river", "splash", "boat", "dinghy", "submarine", "water")
    ):
        return "water_splash"
    if a.startswith("place_ride:") and "coaster" in a:
        return "scream_1"
    if a.startswith("place_ride") or a.startswith("place_stall"):
        return "build"
    if a.startswith("buy_land") or a.startswith("set_loan"):
        return "purchase"
    if a.startswith("set_park_open"):
        return "door_open"
    if a.startswith("wait"):
        return "wait"
    if a.startswith("hire"):
        return "hire"
    if a.startswith("demolish") or a.startswith("remove"):
        return "crash"
    if a.startswith("start_marketing"):
        return "applause"
    return "click_1"
