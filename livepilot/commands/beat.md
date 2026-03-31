---
name: beat
description: Guided beat creation — create a beat from scratch with genre, tempo, and instrumentation choices
---

Guide the user through creating a beat from scratch. Follow these steps:

1. **Ask about the vibe** — genre, tempo range, mood, reference tracks
2. **Set up the session** — `set_tempo`, create tracks for drums/bass/harmony/melody with `create_midi_track`, name and color them
3. **Load instruments** — use `find_and_load_device` for appropriate instruments per track
4. **Verify device health** — after loading, run `get_device_info` on each loaded device. A `parameter_count` of 0 or 1 on AU/VST plugins means the plugin failed to initialize (dead plugin). If detected:
   - Delete the dead plugin with `delete_device`
   - Replace with a native Ableton alternative (e.g., Saturator instead of tape plugins, Operator instead of failed FM synths)
   - Run `get_session_diagnostics` for any other issues (armed tracks, missing instruments)
   - Inform the user which plugin failed and what replacement was used
5. **Program drums first** — create a clip, add kick/snare/hat patterns with `add_notes`
6. **Add bass** — create clip, program a bassline that locks with the kick
7. **Add harmony** — chords or pads that set the mood
8. **Add melody** — top-line or lead element
9. **Mix** — balance levels with `set_track_volume` and `set_track_pan`
10. **Pitch & tuning audit** — MANDATORY before firing. Run on every melodic track (skip drums):
    - `identify_scale` on each track — verify all tracks agree on the same tonal center
    - `analyze_harmony` on chordal tracks (pads, keys) — verify chord quality (no accidental augmented/diminished chords unless intentional)
    - `detect_theory_issues` with `strict=true` on each track — check for out-of-key notes, parallel fifths, voice crossing
    - **Interpret results against the intended scale**, not just C major. The analyzer only knows 7 standard modes — exotic scales (Hijaz, Hungarian minor, whole tone, etc.) will produce false "out of key" warnings. Cross-reference flagged notes against the intended scale manually.
    - Report a clear tuning table to the user: which tracks are clean, which have issues, what the issues are
    - Fix wrong notes with `modify_notes` before proceeding
11. **Fire the scene** to listen, iterate based on feedback

Use the livepilot-core skill for all tool calls. Verify after each step. Keep the user informed of what you're doing and why.
