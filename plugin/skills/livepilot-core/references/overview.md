# LivePilot Architecture & Tool Reference

LivePilot is an MCP server that controls Ableton Live 12 in real-time through 77 tools across 9 domains. This document maps every tool to what it actually does in Ableton, so you know exactly which tool to reach for.

## Architecture

```
Claude Code  ──MCP──►  FastMCP Server  ──TCP/9878──►  Remote Script (inside Ableton)
                        (validates)                    (executes on main thread)
```

- **MCP Server** validates inputs (ranges, types) before sending
- **Remote Script** runs inside Ableton's Python environment, executes on the main thread via `schedule_message`
- **Protocol**: JSON over TCP, newline-delimited. Every command gets a response.
- **Thread safety**: All Live Object Model (LOM) access happens on Ableton's main thread

## The 76 Tools — What Each One Does

### Transport (11) — Playback, tempo, global state

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_session_info` | Returns tempo, time sig, playing state, track count, scene count, song length | — |
| `set_tempo` | Changes BPM | `tempo` (20-999) |
| `set_time_signature` | Changes time signature | `numerator` (1-99), `denominator` (1,2,4,8,16) |
| `start_playback` | Starts from current position | — |
| `stop_playback` | Stops playback | — |
| `continue_playback` | Resumes from where it stopped | — |
| `toggle_metronome` | Toggles click on/off | — |
| `set_session_loop` | Sets loop region | `loop_start` (beats), `loop_length` (beats) |
| `undo` | Undoes last action | — |
| `redo` | Redoes last undone action | — |

### Tracks (12) — Create, delete, configure tracks

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_track_info` | Returns clips, devices, mixer state, routing for one track | `track_index` (0-based) |
| `create_midi_track` | Creates a new MIDI track | `index` (-1=end), `name`, `color` (0-69) |
| `create_audio_track` | Creates a new audio track | `index` (-1=end), `name`, `color` (0-69) |
| `create_return_track` | Creates a new return track | — |
| `delete_track` | Deletes a track | `track_index` |
| `duplicate_track` | Duplicates track with all contents | `track_index` |
| `set_track_name` | Renames a track | `track_index`, `name` |
| `set_track_color` | Sets track color | `track_index`, `color_index` (0-69) |
| `set_track_mute` | Mutes/unmutes | `track_index`, `muted` (bool) |
| `set_track_solo` | Solos/unsolos | `track_index`, `soloed` (bool) |
| `set_track_arm` | Arms/disarms for recording | `track_index`, `armed` (bool) |
| `stop_track_clips` | Stops all playing clips on track | `track_index` |

### Clips (10) — Clip lifecycle and properties

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_clip_info` | Returns clip name, length, loop settings, playing state, notes count | `track_index`, `clip_index` |
| `create_clip` | Creates empty MIDI clip | `track_index`, `clip_index`, `length` (beats) |
| `delete_clip` | Removes a clip from its slot | `track_index`, `clip_index` |
| `duplicate_clip` | Copies clip to next slot | `track_index`, `clip_index` |
| `fire_clip` | Launches a clip | `track_index`, `clip_index` |
| `stop_clip` | Stops a playing clip | `track_index`, `clip_index` |
| `set_clip_name` | Renames a clip | `track_index`, `clip_index`, `name` |
| `set_clip_color` | Sets clip color | `track_index`, `clip_index`, `color_index` (0-69) |
| `set_clip_loop` | Configures loop region | `track_index`, `clip_index`, `loop_start`, `loop_end`, `looping` |
| `set_clip_launch` | Sets launch mode and quantization | `track_index`, `clip_index`, `launch_mode`, `quantization` |

### Notes (8) — MIDI note manipulation (Live 12 API)

| Tool | What it does | Key params |
|------|-------------|------------|
| `add_notes` | Adds MIDI notes to a clip | `track_index`, `clip_index`, `notes` (array) |
| `get_notes` | Reads all notes in a region | `track_index`, `clip_index`, `start_time`, `length` |
| `remove_notes` | Removes notes in a region | `track_index`, `clip_index`, `start_time`, `pitch_start`, etc. |
| `remove_notes_by_id` | Removes specific notes by ID | `track_index`, `clip_index`, `note_ids` |
| `modify_notes` | Changes existing notes (pitch, time, velocity, probability) | `track_index`, `clip_index`, `modifications` |
| `duplicate_notes` | Copies notes in a region | `track_index`, `clip_index`, region params |
| `transpose_notes` | Shifts pitch of notes in a region | `track_index`, `clip_index`, `semitones`, region params |
| `quantize_clip` | Snaps notes to grid | `track_index`, `clip_index`, `grid` (1.0=quarter), `amount` (0-1) |

**Note format** (for `add_notes`):
```json
{"pitch": 60, "start_time": 0.0, "duration": 0.5, "velocity": 100, "mute": false}
```

**Extended note fields** (returned by `get_notes`):
- `note_id` — unique identifier for modify/remove operations
- `probability` — 0.0-1.0, per-note trigger probability (Live 12)
- `velocity_deviation` — -127.0 to 127.0
- `release_velocity` — 0.0-127.0

### Devices (10) — Instruments, effects, racks

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_device_info` | Returns device name, class, active state, all parameters | `track_index`, `device_index` |
| `get_device_parameters` | Lists all parameters with values and ranges | `track_index`, `device_index` |
| `set_device_parameter` | Sets a single parameter | `track_index`, `device_index`, `parameter_index`, `value` |
| `batch_set_parameters` | Sets multiple parameters at once | `track_index`, `device_index`, `parameters` (array) |
| `toggle_device` | Enables/disables a device | `track_index`, `device_index` |
| `delete_device` | Removes a device from the chain | `track_index`, `device_index` |
| `load_device_by_uri` | Loads a device by browser URI | `track_index`, `uri` |
| `find_and_load_device` | Searches browser and loads first match | `track_index`, `name` |
| `get_rack_chains` | Lists chains in an Instrument/Effect Rack | `track_index`, `device_index` |
| `set_chain_volume` | Sets volume of a rack chain | `track_index`, `device_index`, `chain_index`, `volume` |

### Scenes (6) — Scene management

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_scenes_info` | Lists all scenes with names and clip status | — |
| `create_scene` | Creates a new scene | `index` (-1=end) |
| `delete_scene` | Deletes a scene | `scene_index` |
| `duplicate_scene` | Duplicates a scene | `scene_index` |
| `fire_scene` | Launches all clips in a scene | `scene_index` |
| `set_scene_name` | Renames a scene | `scene_index`, `name` |

### Mixing (8) — Levels, panning, routing

| Tool | What it does | Key params |
|------|-------------|------------|
| `set_track_volume` | Sets track volume | `track_index`, `volume` (0.0-1.0, where 0.85≈0dB) |
| `set_track_pan` | Sets stereo position | `track_index`, `pan` (-1.0 left to 1.0 right) |
| `set_track_send` | Sets send level to return track | `track_index`, `send_index`, `value` (0.0-1.0) |
| `get_return_tracks` | Lists all return tracks | — |
| `get_master_track` | Returns master track info | — |
| `set_master_volume` | Sets master output level | `volume` (0.0-1.0) |
| `get_track_routing` | Returns input/output routing config | `track_index` |
| `set_track_routing` | Configures input/output routing | `track_index`, routing params |

### Browser (4) — Finding and loading presets/devices

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_browser_tree` | Returns top-level browser categories | — |
| `get_browser_items` | Lists items in a browser path | `path` |
| `search_browser` | Searches the browser | `query` |
| `load_browser_item` | Loads a browser item onto a track | `track_index`, `uri` |

### Arrangement (8) — Timeline, recording, cue points

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_arrangement_clips` | Lists clips in arrangement view | `track_index` |
| `jump_to_time` | Moves playhead to a beat position | `time` (beats) |
| `capture_midi` | Captures recently played MIDI | — |
| `start_recording` | Starts arrangement recording | — |
| `stop_recording` | Stops recording | — |
| `get_cue_points` | Lists all cue markers | — |
| `jump_to_cue` | Jumps to a cue point by index | `cue_index` |
| `toggle_cue_point` | Creates/removes cue point at current position | — |

## Units & Ranges Quick Reference

| Concept | Unit/Range | Notes |
|---------|-----------|-------|
| Tempo | 20-999 BPM | — |
| Volume | 0.0-1.0 | 0.85 ≈ 0dB, 0.0 = -inf |
| Pan | -1.0 to 1.0 | -1 = full left, 0 = center |
| Time/Position | Beats (float) | 1.0 = quarter note at any tempo |
| Clip length | Beats (float) | 4.0 = 1 bar at 4/4 |
| Pitch | 0-127 (MIDI) | 60 = C3 (middle C) |
| Velocity | 1-127 | 1 = softest, 127 = loudest |
| Probability | 0.0-1.0 | 1.0 = always triggers |
| Color index | 0-69 | Ableton's fixed palette |
| Track index | 0-based | -1 for return tracks: -1=A, -2=B |
| Grid (quantize) | Beats (float) | 1.0=quarter, 0.5=eighth, 0.25=16th |
| Time signature | num/denom | denom must be power of 2 |

## Common Patterns

**"Read before write"** — Always `get_session_info` or `get_track_info` before making changes.

**"Verify after write"** — Re-read state after mutations to confirm the change took effect.

**"Undo is your safety net"** — The `undo` tool reverts the last operation. Mention it to users.

**"One step at a time"** — Don't batch unrelated operations. Verify between steps.
