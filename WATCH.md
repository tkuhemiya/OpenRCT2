# How to watch an agent play

Live OpenRCT2 GUI capture is **not possible here** (original RCT2 data files
are not in the repo). The agent loop is still text-only. For humans we render
a **top-down park camera** from original pixel-art sprites.

## Gameplay video (watch this)

**`recordings/agent_play_gameplay.mp4`** — ~40s, 10 fps, Gentle Glen seed 11.

This is the park being built and then filling with guests. It is **not**
a terminal or ASCII dump.

| What | Path |
|---|---|
| **Gameplay MP4** | `recordings/agent_play_gameplay.mp4` |
| Start / end stills | `recordings/agent_play_gameplay_start.png` / `_end.png` |
| Sprites | `agent/assets/sprites/` |
| Record script | `agent/scripts/record_gameplay.py` |

Result: **SUCCESS** — 121 guests, rating 771 in 72 agent steps.

Still frames from that same play (isometric camera, not the older top-down
sprites): `recordings/agent_watch/00_start.png` through `05_success.png`.
`05` is tick 18 of the winning park — cars and peeps have moved.

```bash
vlc recordings/agent_play_gameplay.mp4
```

Regenerate:

```bash
export PYTHONPATH=agent
python3 agent/scripts/record_gameplay.py \
  --scenario gentle_intro --seed 11 \
  --mp4 recordings/agent_play_gameplay.mp4
```

Needs Pillow + ffmpeg. The **agent never sees this video**.

## ASCII HUD replay (older, text dump)

| What | Path |
|---|---|
| MP4 of ASCII HUD | `recordings/agent_play.mp4` |
| Transcript | `recordings/agent_play_transcript.txt` |
| Machine replay | `recordings/replay.json` |
