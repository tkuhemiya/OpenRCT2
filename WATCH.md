# How to watch an agent play

Live OpenRCT2 GUI capture is **not possible here** (original RCT2 data files
are not in the repo). The agent loop is text-only. Human-facing capture is a
HUD/map replay rendered with a monospace font.

## Ready-made recording (Gentle Glen, seed 11, a win)

**Primary (committed, open this):** `recordings/agent_play.mp4`

| What | Path |
|---|---|
| **MP4 (~18s, 4 fps, 72 steps, 976×1598)** | `recordings/agent_play.mp4` |
| Full text transcript (clearest) | `recordings/agent_play_transcript.txt` |
| Machine replay (seed + actions + HUD frames) | `recordings/replay.json` |
| Start / end stills | `recordings/agent_play_start.png` / `recordings/agent_play_end.png` |
| How-to | `WATCH.md` (this file) |
| Render script | `agent/scripts/render_replay.py` |
| Play script | `agent/scripts/play_and_record.py` |

Working copies also land in gitignored `logs/` when you regenerate:

- `logs/agent_play.mp4`
- `logs/agent_play_transcript.txt`
- `logs/replay.json`

Cloud-agent artifacts (this environment only):

- `/opt/cursor/artifacts/agent_play.mp4`
- `/opt/cursor/artifacts/agent_play_gentle_glen_seed11.mp4`

Result: **SUCCESS** — 121 guests, rating 771 (needed 80 / 600) in 72 steps.
Heuristic policy, scenario `gentle_intro`, seed 11.

## Watch

```bash
# video
vlc recordings/agent_play.mp4
# or
mpv recordings/agent_play.mp4

# transcript (every step's ASCII HUD)
less recordings/agent_play_transcript.txt
```

A browser will also play the MP4.

## Regenerate

```bash
export PYTHONPATH=agent
python3 agent/scripts/play_and_record.py \
  --scenario gentle_intro --seed 11 --out logs/replay.json
python3 agent/scripts/render_replay.py logs/replay.json \
  --mp4 logs/agent_play.mp4 --transcript logs/agent_play_transcript.txt
```

`render_replay.py` uses Pillow + JetBrains Mono / DejaVu / Liberation if
present, otherwise a tiny bitmap font. Needs `ffmpeg` for the MP4.

The **agent never sees this video** — it only gets `get_state()["text"]`.
