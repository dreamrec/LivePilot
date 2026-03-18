# LivePilot Architecture & Tool Reference

LivePilot is an MCP server that controls Ableton Live 12 in real-time through 104 tools across 10 domains. This document maps every tool to what it actually does in Ableton, so you know exactly which tool to reach for.

## Architecture

```
Claude Code  ──MCP──►  FastMCP Server  ──TCP/9878──►  Remote Script (inside Ableton)
                        (validates)                    (executes on main thread)
```

- **MCP Server** validates inputs (ranges, types) before sending
- **Remote Script** runs inside Ableton's Python environment, executes on the main thread via `schedule_message`
- **Protocol**: JSON over TCP, newline-delimited. Every command gets a response.
- **Thread safety**: All Live Object Model (LOM) access happens on Ableton's main thread

## The 104 Tools — What Each One Does

### Transport (12) — Playback, tempo, global state, diagnostics

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
| `get_recent_actions` | Returns log of recent commands sent to Ableton (newest first) | `limit` (1-50, default 20) |
| `get_session_diagnostics` | Analyzes session for issues: armed tracks, solo leftovers, unnamed tracks, empty clips | — |

### Tracks (14) — Create, delete, configure, group tracks

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_track_info` | Returns clips, devices, mixer state, group/fold info for one track | `track_index` (0-based) |
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
| `set_group_fold` | Folds/unfolds a group track | `track_index`, `folded` (bool) |
| `set_track_input_monitoring` | Sets input monitoring state | `track_index`, `state` (0=In, 1=Auto, 2=Off) |

### Clips (11) — Clip lifecycle, properties, warp

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_clip_info` | Returns clip name, length, loop settings, playing state, is_midi/is_audio, warp info | `track_index`, `clip_index` |
| `create_clip` | Creates empty MIDI clip | `track_index`, `clip_index`, `length` (beats) |
| `delete_clip` | Removes a clip from its slot | `track_index`, `clip_index` |
| `duplicate_clip` | Copies clip to next slot | `track_index`, `clip_index` |
| `fire_clip` | Launches a clip | `track_index`, `clip_index` |
| `stop_clip` | Stops a playing clip | `track_index`, `clip_index` |
| `set_clip_name` | Renames a clip | `track_index`, `clip_index`, `name` |
| `set_clip_color` | Sets clip color | `track_index`, `clip_index`, `color_index` (0-69) |
| `set_clip_loop` | Configures loop region | `track_index`, `clip_index`, `loop_start`, `loop_end`, `looping` |
| `set_clip_launch` | Sets launch mode and quantization | `track_index`, `clip_index`, `launch_mode`, `quantization` |
| `set_clip_warp_mode` | Sets warp mode for audio clips | `track_index`, `clip_index`, `mode` (0=Beats,1=Tones,2=Texture,3=Re-Pitch,4=Complex,6=Complex Pro) |

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
| `quantize_clip` | Snaps notes to grid | `track_index`, `clip_index`, `grid` (int 0-8: 0=None,1=1/4,2=1/8,5=1/16,8=1/32), `amount` (0-1) |

**Note format** (for `add_notes`):
```json
{"pitch": 60, "start_time": 0.0, "duration": 0.5, "velocity": 100, "mute": false}
```

**Extended note fields** (returned by `get_notes`):
- `note_id` — unique identifier for modify/remove operations
- `probability` — 0.0-1.0, per-note trigger probability (Live 12)
- `velocity_deviation` — -127.0 to 127.0
- `release_velocity` — 0.0-127.0

### Devices (12) — Instruments, effects, racks

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
| `set_simpler_playback_mode` | Switches Simpler mode (Classic/One-Shot/Slice) | `track_index`, `device_index`, `playback_mode` (0/1/2), `slice_by`, `sensitivity` |
| `set_chain_volume` | Sets volume of a rack chain | `track_index`, `device_index`, `chain_index`, `volume` |
| `get_device_presets` | Lists presets for a device (audio effects, instruments, MIDI effects) | `device_name` |

### Scenes (8) — Scene management

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_scenes_info` | Lists all scenes with names, tempo, and color | — |
| `create_scene` | Creates a new scene | `index` (-1=end) |
| `delete_scene` | Deletes a scene | `scene_index` |
| `duplicate_scene` | Duplicates a scene | `scene_index` |
| `fire_scene` | Launches all clips in a scene | `scene_index` |
| `set_scene_name` | Renames a scene | `scene_index`, `name` |
| `set_scene_color` | Sets scene color | `scene_index`, `color_index` (0-69) |
| `set_scene_tempo` | Sets tempo that triggers when scene fires | `scene_index`, `tempo` (20-999 BPM) |

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
| `load_browser_item` | Loads a browser item onto a track — **`uri` MUST come from `search_browser` results, NEVER invented** | `track_index`, `uri` |

### Arrangement (19) — Timeline, recording, cue points, arrangement notes

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_arrangement_clips` | Lists clips in arrangement view | `track_index` |
| `create_arrangement_clip` | Duplicates session clip into arrangement at a beat position | `track_index`, `clip_slot_index`, `start_time`, `length` |
| `add_arrangement_notes` | Adds MIDI notes to an arrangement clip | `track_index`, `clip_index`, `notes` |
| `get_arrangement_notes` | Reads notes from an arrangement clip | `track_index`, `clip_index`, region params |
| `remove_arrangement_notes` | Removes notes in a region of an arrangement clip | `track_index`, `clip_index`, region params |
| `remove_arrangement_notes_by_id` | Removes specific notes by ID | `track_index`, `clip_index`, `note_ids` |
| `modify_arrangement_notes` | Modifies notes by ID (pitch, time, velocity, probability) | `track_index`, `clip_index`, `modifications` |
| `duplicate_arrangement_notes` | Copies notes by ID with optional time offset | `track_index`, `clip_index`, `note_ids`, `time_offset` |
| `transpose_arrangement_notes` | Transposes notes in an arrangement clip | `track_index`, `clip_index`, `semitones`, region params |
| `set_arrangement_clip_name` | Renames an arrangement clip | `track_index`, `clip_index`, `name` |
| `set_arrangement_automation` | Writes automation envelope to an arrangement clip | `track_index`, `clip_index`, `parameter_type`, `points` |
| `back_to_arranger` | Switches playback from session back to arrangement | — |
| `jump_to_time` | Moves playhead to a beat position | `beat_time` (beats) |
| `capture_midi` | Captures recently played MIDI | — |
| `start_recording` | Starts recording (session or arrangement) | `arrangement` (bool) |
| `stop_recording` | Stops all recording | — |
| `get_cue_points` | Lists all cue markers | — |
| `jump_to_cue` | Jumps to a cue point by index | `cue_index` |
| `toggle_cue_point` | Creates/removes cue point at current position | — |

### Memory (8) — Technique library persistence

| Tool | What it does | Key params |
|------|-------------|------------|
| `memory_learn` | Saves a technique with stylistic qualities | `name`, `type`, `qualities`, `payload`, `tags` |
| `memory_recall` | Searches library by text and filters | `query`, `type`, `tags`, `limit` |
| `memory_get` | Fetches full technique including payload | `technique_id` |
| `memory_replay` | Returns technique with replay plan for agent | `technique_id`, `adapt` (bool) |
| `memory_list` | Browses library with filtering/sorting | `type`, `tags`, `sort_by`, `limit` |
| `memory_favorite` | Stars and/or rates a technique | `technique_id`, `favorite`, `rating` (0-5) |
| `memory_update` | Updates name, tags, or qualities | `technique_id`, `name`, `tags`, `qualities` |
| `memory_delete` | Removes technique (backs up first) | `technique_id` |

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
| Track index | 0-based | Negative for return tracks (-1=A, -2=B), -1000 for master |
| Grid (quantize) | Integer enum (0-8) | 0=None, 1=1/4, 2=1/8, 3=1/8T, 4=1/8+T, 5=1/16, 6=1/16T, 7=1/16+T, 8=1/32 |
| Time signature | num/denom | denom must be power of 2 |

## Common Patterns

**"Read before write"** — Always `get_session_info` or `get_track_info` before making changes.

**"Verify after write"** — Re-read state after mutations to confirm the change took effect.

**"Undo is your safety net"** — The `undo` tool reverts the last operation. Mention it to users.

**"One step at a time"** — Don't batch unrelated operations. Verify between steps.
