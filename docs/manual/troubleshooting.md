# Troubleshooting

When something goes wrong, find your symptom below and follow the fix.

---

## Connection Issues

### "Connection refused" when running --status

**Likely cause:** Ableton is not running, or LivePilot is not selected as Control Surface.

**Fix:** Open Ableton > Preferences > Link, Tempo & MIDI > set Control Surface to LivePilot.

---

### "Another client is already connected"

**Likely cause:** Only one MCP client can connect at a time (single-client TCP by design).

**Fix:** Close the other client, or restart Ableton to reset the connection.

---

### "Unknown command type: xyz"

**Likely cause:** The Remote Script in Ableton is older than the MCP server.

**Fix:** Run `npx -y github:dreamrec/LivePilot --install` again, then restart Ableton.

---

### Tools work but responses are slow

**Likely cause:** This depends on the delay.

- **Under ~200ms:** Normal. Write commands have a ~100ms settle delay by design so Ableton's state can settle before the response is read back.
- **Over 2 seconds:** Heavy session. Ableton is busy processing audio or scanning plugins. Try again.
- **Timeout after 10-15 seconds:** Ableton may be unresponsive due to CPU overload or plugin scanning.

**Fix:** Wait and retry. If timeouts persist, save your session and restart Ableton.

---

## No Sound

### Track has notes but produces no sound

Check these causes in order:

1. **No instrument loaded** -- `get_track_info` shows an empty devices array. Load an instrument first.
2. **Empty Drum Rack** -- You loaded a bare "Drum Rack" instead of a kit preset. The rack has no samples. Fix: delete it, then use `search_browser` with `path="Drums"` and `name_filter="Kit"` to find an actual kit.
3. **Notes at wrong pitch** -- Drum kits map samples to specific pitches (36-51 typically). Notes placed at 60-69 may miss all pads. Check the kit mapping with `get_rack_chains`.
4. **Track volume is 0** -- Check `mixer.volume` in `get_track_info`.
5. **Track is muted** -- Check the mute state in `get_track_info`.
6. **Master volume is 0** -- Check with `get_master_track`.
7. **Clip not fired** -- The clip exists but is not playing. Use `fire_clip`.
8. **Effect with Dry/Wet at 0%** -- An effect in the device chain is silencing the signal. Check parameters with `get_device_parameters`.

---

### Drum Rack loaded but silent

**Likely cause:** The rack was loaded without any samples.

**Fix:** Run `get_rack_chains` -- if it returns empty chains, the rack has no samples. Delete the device, then use `search_browser` with `path="Drums"` and `name_filter="Kit"` to find a real kit with samples pre-loaded.

---

## MIDI Issues

### Notes don't play at expected pitch

**Likely cause:** Drum Racks use a different pitch mapping than melodic instruments. Kick is typically at pitch 36 (C1), not 60 (C3).

**Fix:** Check the kit's actual mapping with `get_rack_chains` to see which pitches have samples assigned.

---

### modify_notes fails with "note_id not found"

**Likely cause:** Note IDs are assigned by Ableton and can change whenever notes are added, removed, or modified.

**Fix:** Always call `get_notes` immediately before `modify_notes` and use the returned IDs right away. Do not cache note IDs across multiple operations.

---

### transpose_notes skips some notes

**Likely cause:** Notes that would go below 0 or above 127 after transposition are skipped (not clamped).

**Fix:** This is intentional. The response includes a `skipped_out_of_range` count so you know how many notes were affected. Adjust the transposition amount or the source notes to stay within the 0-127 range.

---

## Device Issues

### find_and_load_device loads the wrong thing

**Likely cause:** Name matching is partial. For example, searching for "Drift" can match sample files like "Synth Bass Drift Pad.wav" before the Drift synthesizer.

**Fix:** Use `search_browser` with `path="Instruments"` and `name_filter="Drift"` for more precise results. Then use `load_browser_item` with the exact URI from the search results.

---

### set_device_parameter says parameter not found

**Likely cause:** Parameter names are exact and case-sensitive.

**Fix:** Call `get_device_parameters` first to see the exact names and indices. Use those exact strings when setting values.

---

### Device loaded but no sound

**Likely cause:** Key parameters may be at zero or in a disabled state.

**Fix:** Check these common culprits:
- Volume or Gain at 0
- Filter cutoff fully closed
- Dry/Wet at 0% (for effects)
- Oscillators turned off (some synth presets start this way)

Use `get_device_parameters` to inspect parameter values.

---

## Arrangement Issues

### Arrangement clips not playing

**Likely cause:** Session clips override arrangement playback on a per-track basis.

**Fix:** Use `back_to_arranger` to return all tracks to arrangement playback. Alternatively, stop individual session clips with `stop_track_clips`.

---

### set_arrangement_automation fails with "Cannot create automation envelope"

**Likely cause:** Known Ableton API limitation -- `automation_envelope()` returns None for some arrangement clips.

**Fix:** The tool has a session-clip workaround, but it requires an empty clip slot on the track. If there is no empty slot, create one or free up a slot first.

---

### Arrangement clip indices changed

**Likely cause:** Indices are based on position in `track.arrangement_clips`, which changes when clips are added or removed.

**Fix:** Always call `get_arrangement_clips` before operating on arrangement clips to get current indices.

---

## General Issues

### "TIMEOUT" errors

**Likely cause:** The command took longer than 10-15 seconds. Ableton is busy with audio processing, plugin scanning, or a complex operation.

**Fix:** Try again. If timeouts persist, save your session and restart Ableton.

---

### Undo doesn't seem to work

**Likely cause:** There are a few quirks with undo:

- `undo` and `redo` are silent -- they do not error even if there is nothing to undo.
- Multiple rapid changes may need multiple undos to fully revert.
- Some operations (like loading devices) may require 2-3 undos to fully revert.

**Fix:** Call `undo` multiple times if a single call does not revert what you expected.

---

### Session diagnostics shows unexpected issues

The `get_session_diagnostics` tool reports potential issues as warnings, not errors. Your session still works, but you may want to address these:

- **Armed tracks:** Tracks left in record-ready state waste CPU. Disarm tracks you are not recording to.
- **Solo leftovers:** A track was soloed and forgotten, muting everything else. Unsolo it.
- **Default names:** Tracks named "1-MIDI", "2-Audio" etc. should be renamed for clarity.

---

## When to Restart

### Restart just the MCP server (your AI client)

- When new tools were added but are not appearing.
- When the connection drops and will not reconnect.

### Restart just Ableton

- When the Remote Script was updated with new handlers.
- When "Unknown command type" errors appear for tools that should exist.

### Restart both

- After updating LivePilot to a new version.
- When nothing else works.

---

## Getting Help

- **Report issues:** [github.com/dreamrec/LivePilot/issues](https://github.com/dreamrec/LivePilot/issues)
- **Run diagnostics:** `npx -y github:dreamrec/LivePilot --doctor`
- **Check version:** `npx -y github:dreamrec/LivePilot --version`

---

Back to [Manual](index.md)
