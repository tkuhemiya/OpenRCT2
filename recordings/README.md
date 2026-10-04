# Agent play recording

Gentle Glen (`gentle_intro`), seed **11**, heuristic policy.

- **Playable park:** `python3 -m openrct2_agent.cli play` → http://127.0.0.1:8765/play
- **Agent watch stills** (heuristic on Gentle Glen seed 11; camera tick 0 except `05`):
  `recordings/agent_watch/00_start.png` empty park
  → `01_first_stall.png` paths + toilets
  → `02_first_ride.png` stalls + merry-go-round
  → `03_gates_open.png` six rides, gates OPEN
  → `04_guests_arrive.png` wait:1, 121 guests, SUCCESS
  → `05_success.png` same park one animation beat later (cars and peeps moved)
- **PR screenshots:** `recordings/pr_screenshots/`
  (`01_gentle_glen_new_park.png` … `08_ride_silhouettes.png`)
- Start / end stills: `agent_play_gameplay_start.png` / `agent_play_gameplay_end.png`
- ASCII HUD (older): `agent_play.mp4` and `agent_play_transcript.txt`
- Machine replay: `replay.json`

How to regenerate: `WATCH.md`.
