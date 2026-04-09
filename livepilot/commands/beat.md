---
name: beat
description: Guided beat creation — create a beat from scratch with genre, tempo, and instrumentation choices
---

Guide the user through creating a beat from scratch. Follow these steps:

## Step 0: Session Prep (fresh projects only)

If the user asks for a **fresh start** (new track, clean slate, start from scratch):

1. **Read the session** — `get_session_info` to see what exists
2. **Delete all existing tracks** — loop through all tracks with `delete_track`, starting from the highest index down to 0 (deleting from the top prevents index shifts)
3. **Load the M4L Analyzer on master** — `find_and_load_device(track_index=-1000, device_name="LivePilot_Analyzer")`. This enables real-time spectral analysis, RMS metering, and key detection for the entire session. If it fails, try `search_browser(path="max_for_live", name_filter="LivePilot")` to find the URI and load manually.
4. **Set up master chain** — load Glue Compressor + EQ Eight + Utility on master for bus processing
5. **Verify analyzer** — wait 2 seconds, then call `get_master_spectrum`. If it returns data, the bridge is connected. If it errors with "UDP bridge not connected", call `reconnect_bridge` to rebind.

If the user is adding to an **existing project**, skip step 0 — just call `get_session_info` and work with what's there.

## Step 1: Ask about the vibe
Genre, tempo range, mood, reference tracks.

## Step 2: Set up the session
`set_tempo`, create tracks for drums/bass/harmony/melody with `create_midi_track`, name and color them.

## Step 3: Load instruments
Use `search_browser` to find devices by name, `load_browser_item` or `find_and_load_device` to load them.

## Step 4: Verify device health
After loading, run `get_device_info` on each loaded device. A `parameter_count` of 0 or 1 on AU/VST plugins means the plugin failed to initialize (dead plugin). If detected:
- Delete the dead plugin with `delete_device`
- Replace with a native Ableton alternative (e.g., Saturator instead of tape plugins, Operator instead of failed FM synths)
- Run `get_session_diagnostics` for any other issues (armed tracks, missing instruments)
- Inform the user which plugin failed and what replacement was used

## Step 5: Program drums first
Create a clip, add kick/snare/hat patterns with `add_notes`.

## Step 6: Add bass
Create clip, program a bassline that locks with the kick.

## Step 7: Add harmony
Chords or pads that set the mood.

## Step 8: Add melody
Top-line or lead element.

## Step 9: Mix + VERIFY
Balance levels with `set_track_volume` and `set_track_pan`.

**MANDATORY after every parameter change:**
- Read `value_string` in the response to confirm the actual Hz/dB/% value makes sense
- Call `get_track_meters(include_stereo=true)` and verify each track has non-zero output
- If a track's stereo output drops to 0, the effect is killing the signal — check `get_device_parameters` for `value_string`, fix, re-verify
- Parameter ranges are NOT always 0-1. Always read `value_string`.

## Step 10: Pitch & tuning audit
MANDATORY before firing. Run on every melodic track (skip drums):
- `identify_scale` on each track — verify all tracks agree on the same tonal center
- `analyze_harmony` on chordal tracks — verify chord quality
- `detect_theory_issues` with `strict=true` on each track — check for out-of-key notes, parallel fifths, voice crossing
- **Interpret results against the intended scale**, not just C major
- Report a clear tuning table to the user: which tracks are clean, which have issues
- Fix wrong notes with `modify_notes` before proceeding

## Step 11: Perception check
If the M4L Analyzer is connected:
- `get_master_spectrum` — check spectral balance (sub should be present but not >60% for most genres)
- `get_master_rms` — check levels aren't clipping
- `get_detected_key` — verify the analyzer agrees with the intended key

If not connected, use `capture_audio` + `analyze_loudness` + `analyze_spectrum_offline` for offline analysis.

## Step 12: Fire the scene
Fire to listen, iterate based on feedback.

Use the livepilot-core skill for all tool calls. Verify after each step. Keep the user informed of what you're doing and why.
