---
name: beat
description: Guided beat creation — create a beat from scratch with genre, tempo, and instrumentation choices
---

Guide the user through creating a beat from scratch. Follow these steps:

1. **Ask about the vibe** — genre, tempo range, mood, reference tracks
2. **Set up the session** — `set_tempo`, create tracks for drums/bass/harmony/melody with `create_midi_track`, name and color them
3. **Load instruments** — use `find_and_load_device` for appropriate instruments per track
4. **Program drums first** — create a clip, add kick/snare/hat patterns with `add_notes`
5. **Add bass** — create clip, program a bassline that locks with the kick
6. **Add harmony** — chords or pads that set the mood
7. **Add melody** — top-line or lead element
8. **Mix** — balance levels with `set_track_volume` and `set_track_pan`
9. **Fire the scene** to listen, iterate based on feedback

Use the livepilot-core skill for all tool calls. Verify after each step. Keep the user informed of what you're doing and why.
