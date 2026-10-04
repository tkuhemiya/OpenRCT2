# Park art

The playable camera is **programmatic isometric pixel art**
(`openrct2_agent/art.py`). Every ride, stall, tile, tree, and peep is drawn
with ImageDraw from the catalog — adding a ride type does not need a new PNG.

Sounds are likewise generated in `openrct2_agent/audio.py` (WAV, no RCT2
samples).

`sprites/` may still contain earlier packed images; the live renderer does
not require them.

Play: `python3 -m openrct2_agent.cli play` then open `/play`.
