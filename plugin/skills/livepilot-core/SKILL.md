---
name: livepilot-core
description: Core discipline for controlling Ableton Live 12 through LivePilot's 78 MCP tools. Use whenever working with Ableton Live through MCP tools.
---

# LivePilot Core — Ableton Live 12 AI Copilot

LivePilot gives you 78 MCP tools to control Ableton Live 12 in real-time: transport, tracks, clips, MIDI notes, devices, scenes, mixing, browser, and arrangement.

## Golden Rules

1. **Always call `get_session_info` first** — know what you're working with before changing anything
2. **Verify after every write** — re-read state to confirm your change took effect
3. **Use `undo` liberally** — it's your safety net. Mention it to users when doing destructive ops
4. **One operation at a time** — don't batch unrelated changes. Verify between steps
5. **Track indices are 0-based** — track 0 is the first track, scene 0 is the first scene
6. **Color indices 0-69** — Ableton's fixed palette. Don't guess — use the index
7. **Volume is 0.0-1.0, pan is -1.0 to 1.0** — these are normalized, not dB
8. **Tempo range 20-999 BPM** — validated before sending to Ableton
9. **Always name your tracks and clips** — organization is part of the creative process

## Tool Domains (78 total)

### Transport (12)
`get_session_info` · `set_tempo` · `set_time_signature` · `start_playback` · `stop_playback` · `continue_playback` · `toggle_metronome` · `set_session_loop` · `undo` · `redo` · `get_recent_actions` · `get_session_diagnostics`

### Tracks (12)
`get_track_info` · `create_midi_track` · `create_audio_track` · `create_return_track` · `delete_track` · `duplicate_track` · `set_track_name` · `set_track_color` · `set_track_mute` · `set_track_solo` · `set_track_arm` · `stop_track_clips`

### Clips (10)
`get_clip_info` · `create_clip` · `delete_clip` · `duplicate_clip` · `fire_clip` · `stop_clip` · `set_clip_name` · `set_clip_color` · `set_clip_loop` · `set_clip_launch`

### Notes (8)
`add_notes` · `get_notes` · `remove_notes` · `remove_notes_by_id` · `modify_notes` · `duplicate_notes` · `transpose_notes` · `quantize_clip`

### Devices (10)
`get_device_info` · `get_device_parameters` · `set_device_parameter` · `batch_set_parameters` · `toggle_device` · `delete_device` · `load_device_by_uri` · `find_and_load_device` · `get_rack_chains` · `set_chain_volume`

### Scenes (6)
`get_scenes_info` · `create_scene` · `delete_scene` · `duplicate_scene` · `fire_scene` · `set_scene_name`

### Mixing (8)
`set_track_volume` · `set_track_pan` · `set_track_send` · `get_return_tracks` · `get_master_track` · `set_master_volume` · `get_track_routing` · `set_track_routing`

### Browser (4)
`get_browser_tree` · `get_browser_items` · `search_browser` · `load_browser_item`

### Arrangement (8)
`get_arrangement_clips` · `jump_to_time` · `capture_midi` · `start_recording` · `stop_recording` · `get_cue_points` · `jump_to_cue` · `toggle_cue_point`

## Workflow: Building a Beat

1. `get_session_info` — check current state
2. `set_tempo` — set your target BPM
3. `create_midi_track` — create tracks for drums, bass, chords, melody
4. Name and color each track with `set_track_name` / `set_track_color`
5. `find_and_load_device` — load instruments (e.g., "Drum Rack", "Analog", "Wavetable")
6. `create_clip` — create clips on each track (4 beats = 1 bar at 4/4)
7. `add_notes` — program MIDI patterns. Each note needs `pitch`, `start_time`, `duration`
8. `fire_scene` or `fire_clip` — listen to your work
9. Iterate: `get_notes` → `modify_notes` / `transpose_notes` → listen again

## Workflow: Sound Design

1. Load a synth: `find_and_load_device` with name like "Wavetable" or "Analog"
2. `get_device_parameters` — see all available parameters
3. `set_device_parameter` — tweak individual params by name or index
4. `batch_set_parameters` — set multiple params at once for a preset
5. Load effects: `find_and_load_device` with "Reverb", "Delay", "Compressor", etc.
6. Chain devices: they stack in order on the track's device chain
7. Use `get_device_info` to inspect rack devices, `get_rack_chains` for racks

## Workflow: Mixing

1. `get_session_info` — see all tracks and current levels
2. `set_track_volume` / `set_track_pan` — set levels and stereo position
3. `set_track_send` — route to return tracks for shared effects
4. `get_return_tracks` — check return track setup
5. `set_master_volume` — final output level
6. `set_track_routing` — configure input/output routing

## Live 12 Note API

Notes use this format when calling `add_notes`:
```json
{
  "pitch": 60,
  "start_time": 0.0,
  "duration": 0.5,
  "velocity": 100,
  "mute": false
}
```

When reading with `get_notes`, you also get:
- `note_id` — unique ID for modify/remove operations
- `probability` — 0.0-1.0, Live 12 per-note probability
- `velocity_deviation` — -127.0 to 127.0
- `release_velocity` — 0.0-127.0

Use `modify_notes` with `note_id` to update existing notes.
Use `remove_notes_by_id` for surgical deletion.
Use `transpose_notes` for pitch shifting a region.
Use `quantize_clip` to snap notes to a grid (grid=1.0 is quarter note).

## Reference Corpus

Deep production knowledge lives in `references/`. Consult these when making creative decisions — they contain specific parameter values, recipes, and patterns. Use them as starting points, not rigid rules.

| File | What's inside | When to consult |
|------|--------------|-----------------|
| `references/overview.md` | All 76 tools mapped with params, units, ranges | Quick lookup for any tool |
| `references/midi-recipes.md` | Drum patterns by genre, chord voicings, scales, hi-hat techniques, humanization, polymetrics | Programming MIDI notes, building beats |
| `references/sound-design.md` | Stock instruments/effects, parameter recipes for bass/pad/lead/pluck, device chain patterns | Loading and configuring devices |
| `references/mixing-patterns.md` | Gain staging, parallel compression, sidechain, EQ by instrument, bus processing, stereo width | Setting volumes, panning, adding effects |
| `references/ableton-workflow-patterns.md` | Session/Arrangement workflow, song structures by genre, follow actions, clip launch modes, export | Organizing sessions, structuring songs |
| `references/m4l-devices.md` | Browser organization, MIDI effects, rack systems, device loading patterns | Finding and loading devices, using racks |
