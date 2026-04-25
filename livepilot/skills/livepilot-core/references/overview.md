# LivePilot v1.23.2 — Architecture & Tool Reference

Agentic production system for Ableton Live 12. 433 tools across 53 domains. Device atlas (5264 devices, 120 enriched, 47 with aesthetic-tagged `signature_techniques`), spectral perception (M4L analyzer with 9-band FFT — sub_low / sub / low / low_mid / mid / high_mid / high / presence / air), technique memory, automation intelligence (16 curve types, 15 recipes), music theory (Krumhansl-Schmuckler, species counterpoint), generative algorithms (Euclidean rhythm, tintinnabuli, phase shift, additive process), neo-Riemannian harmony (PRL transforms, Tonnetz), MIDI file I/O, **LIVE Splice describe-a-sound + variations via captured GraphQL endpoints (v1.17)**, drum-rack pad-by-pad construction, live dead-device detection via meter sampling, role-aware Simpler defaults, session-record arrangement-automation workaround.

**Concept surface (v1.17):** `artist-vocabularies.md` and `genre-vocabularies.md` in `references/` provide structured translation from the LLM's training (producers like Villalobos, Hawtin, Basic Channel, Gas, Basinski, Hecker, Aphex, Dilla, Burial, Henke; genres like microhouse, dub_techno, ambient, idm) into LivePilot's device surface. New MCP tools `atlas_describe_chain` (free-text → chain proposal) and `atlas_techniques_for_device` (reverse-lookup: 146 technique cross-references across 58 devices).

**Creative Director (v1.18):** new `livepilot-creative-director` skill enforces divergence on creative intent — three plans across distinct `move.family` values, critics deferred until after selection, `get_anti_preferences` read before generation. Concept packets become structured YAML (`references/concepts/artists/*.yaml`, `references/concepts/genres/*.yaml` — 28 artists + 14 genres). Device affordances added (`references/affordances/devices/*.yaml` — 20 devices with `subtle / moderate / aggressive` parameter ranges, chain `pairings`, and `remeasure` queues). Evaluation vocabulary extended with Family B artistic dimensions (style_fit, distinctiveness, motif_coherence, section_contrast, restraint) and a 5-verdict taxonomy (safe_win, bold_win, interesting_failure, identity_break, generic_fallback). Zero new Python.

## Architecture

```
AI Client  ──MCP──►  FastMCP Server  ──TCP/9878──►  Remote Script (inside Ableton)
                        (validates)                    (executes on main thread)
                            │
                            ├── Device Atlas (5264 devices, 120 enriched with sonic intelligence)
                            ├── M4L Analyzer ──UDP/OSC──► LivePilot_Analyzer.amxd
                            └── Technique Memory (~/.livepilot/memory/)
```

- **MCP Server** validates inputs (ranges, types) before sending
- **Remote Script** runs inside Ableton's Python environment, executes on the main thread via `schedule_message`
- **Device Atlas** provides structured knowledge of Ableton's device library — real names, real URIs, sonic descriptions
- **M4L Analyzer** reads the master bus in real-time: 9-band spectrum (sub_low → air), RMS/peak, pitch tracking, Krumhansl-Schmuckler key detection
- **Technique Memory** persists production decisions across sessions as typed, searchable, replayable data structures
- **Protocol**: JSON over TCP, newline-delimited. Every command gets a response.
- **Thread safety**: All Live Object Model (LOM) access happens on Ableton's main thread

## The Agentic Difference

A flat tool list lets the AI press buttons. LivePilot's three layers give it context:

1. **Before loading a device** — the agent consults the atlas to find a real preset, not a hallucinated name
2. **Before writing harmonic content** — the agent reads the detected key from the analyzer
3. **Before making creative decisions** — the agent checks technique memory for the user's style preferences
4. **After every mixing move** — the agent reads the spectrum to verify the result

This turns "set EQ band 3 to -4 dB" into "cut 400 Hz by 4 dB, then read the spectrum to confirm the mud is actually reduced."

## The 433 Tools — What Each One Does

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

### Devices (15) — Instruments, effects, racks, 12.3+ device insertion

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_device_info` | Returns device name, class, active state, all parameters | `track_index`, `device_index` |
| `get_device_parameters` | Lists all parameters with values, ranges, and `display_value` (12.2+) | `track_index`, `device_index` |
| `set_device_parameter` | Sets a single parameter, returns `display_value` on 12.2+ | `track_index`, `device_index`, `parameter_index`, `value` |
| `batch_set_parameters` | Sets multiple parameters at once | `track_index`, `device_index`, `parameters` (array) |
| `toggle_device` | Enables/disables a device | `track_index`, `device_index` |
| `delete_device` | Removes a device from the chain | `track_index`, `device_index` |
| `load_device_by_uri` | Loads a device by browser URI | `track_index`, `uri` |
| `find_and_load_device` | Searches browser and loads first match (uses `insert_device` fast path on 12.3+) | `track_index`, `name` |
| `insert_device` | **12.3+** Insert native device by name — 10x faster than browser. Supports chain insertion for drum racks | `track_index`, `device_name`, `position`, `device_index`, `chain_index` |
| `insert_rack_chain` | **12.3+** Add a chain to Instrument/Audio Effect/Drum Rack | `track_index`, `device_index`, `position` |
| `set_drum_chain_note` | **12.3+** Assign MIDI note to a Drum Rack chain (C1=36 kick, D1=38 snare) | `track_index`, `device_index`, `chain_index`, `note` |
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

### Mixing (11) — Levels, panning, routing, metering

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
| `get_track_meters` | Returns real-time output levels for a track | `track_index` |
| `get_master_meters` | Returns real-time output levels for the master | — |
| `get_mix_snapshot` | Returns all levels, panning, routing, mute/solo state for entire session | — |

### Browser (4) — Finding and loading presets/devices

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_browser_tree` | Returns top-level browser categories | — |
| `get_browser_items` | Lists items in a browser path | `path` |
| `search_browser` | Searches the browser | `query` |
| `load_browser_item` | Loads a browser item onto a track — **`uri` MUST come from `search_browser` results, NEVER invented** | `track_index`, `uri` |

### Arrangement (20) — Timeline, recording, cue points, arrangement notes

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_arrangement_clips` | Lists clips in arrangement view | `track_index` |
| `create_arrangement_clip` | Duplicates session clip into arrangement at a beat position | `track_index`, `clip_slot_index`, `start_time`, `length` |
| `create_native_arrangement_clip` | **12.1.10+** Creates native arrangement clip with full automation envelope support | `track_index`, `start_time`, `length`, `name`, `color_index` |
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

### Analyzer (30) — Real-time DSP analysis (requires LivePilot Analyzer M4L device on master track)

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_master_spectrum` | 9-band spectral analysis (sub_low → air) of master output | `window_ms`, `sub_detail` |
| `get_master_rms` | True RMS and peak amplitude levels | — |
| `get_detected_key` | Detects musical key (Krumhansl-Schmuckler) | — |
| `get_hidden_parameters` | All device parameters including hidden ones | `track_index`, `device_index` |
| `get_automation_state` | Parameters with active automation | `track_index`, `device_index` |
| `walk_device_tree` | Recursive device tree (racks, drum pads, 6 levels) | `track_index`, `device_index` |
| `get_clip_file_path` | Audio file path on disk | `track_index`, `clip_index` |
| `replace_simpler_sample` | Replace sample in Simpler | `track_index`, `device_index`, `file_path` |
| `load_sample_to_simpler` | Bootstrap Simpler and load sample (full workflow) | `track_index`, `file_path` |
| `get_simpler_slices` | Slice points from Simpler | `track_index`, `device_index` |
| `crop_simpler` | Crop sample to active region | `track_index`, `device_index` |
| `reverse_simpler` | Reverse sample | `track_index`, `device_index` |
| `warp_simpler` | Warp sample to N beats | `track_index`, `device_index`, `beats` |
| `get_warp_markers` | All warp markers (beat_time + sample_time) | `track_index`, `clip_index` |
| `add_warp_marker` | Add warp marker | `track_index`, `clip_index`, `beat_time` |
| `move_warp_marker` | Move warp marker | `track_index`, `clip_index`, `old_beat`, `new_beat` |
| `remove_warp_marker` | Remove warp marker | `track_index`, `clip_index`, `beat_time` |
| `scrub_clip` | Preview audio at position | `track_index`, `clip_index`, `beat_time` |
| `stop_scrub` | Stop preview | `track_index`, `clip_index` |
| `get_display_values` | Human-readable parameter values ("440 Hz", "-6 dB") | `track_index`, `device_index` |

### Automation (8) — Clip automation CRUD + intelligent curve generation

| Tool | What it does | Key params |
|------|-------------|------------|
| `get_clip_automation` | Lists all automation envelopes on a session clip | `track_index`, `clip_index` |
| `set_clip_automation` | Writes automation points to a clip envelope | `track_index`, `clip_index`, `parameter_type`, `points` |
| `clear_clip_automation` | Clears automation envelopes (specific or all) | `track_index`, `clip_index`, `parameter_type` (optional) |
| `apply_automation_shape` | Generates and applies a curve to a clip in one call | `track_index`, `clip_index`, `parameter_type`, `curve_type`, `duration`, `density` |
| `apply_automation_recipe` | Applies a named recipe (filter_sweep_up, dub_throw, etc.) | `track_index`, `clip_index`, `parameter_type`, `recipe`, `duration` |
| `get_automation_recipes` | Lists all 15 recipes with descriptions and targets | — |
| `generate_automation_curve` | Previews curve points without writing them | `curve_type`, `duration`, `density`, curve-specific params |
| `analyze_for_automation` | Spectral analysis + device-aware automation suggestions | `track_index` |

**16 curve types:** linear, exponential, logarithmic, s_curve, sine, sawtooth, spike, square, steps, perlin, brownian, spring, bezier, easing, euclidean, stochastic

**15 recipes:** filter_sweep_up, filter_sweep_down, dub_throw, tape_stop, build_rise, sidechain_pump, fade_in, fade_out, tremolo, auto_pan, stutter, breathing, washout, vinyl_crackle, stereo_narrow

### Theory (7) — Built-in music theory analysis (zero dependencies)

| Tool | What it does | Key params |
|------|-------------|------------|
| `analyze_harmony` | Chord-by-chord Roman numeral analysis of a clip | `track_index`, `clip_index`, `key` (optional) |
| `suggest_next_chord` | Suggests theory-valid chord continuations | `track_index`, `clip_index`, `style` (common_practice/jazz/modal/pop) |
| `detect_theory_issues` | Finds parallel fifths/octaves, out-of-key notes, voice crossing | `track_index`, `clip_index`, `strict` (bool) |
| `identify_scale` | Deep scale/mode identification with confidence ranking | `track_index`, `clip_index` |
| `harmonize_melody` | Generates 2 or 4-voice SATB harmonization | `track_index`, `clip_index`, `voices` (2 or 4) |
| `generate_countermelody` | Species counterpoint against a melody | `track_index`, `clip_index`, `species` (1 or 2) |
| `transpose_smart` | Diatonic or chromatic transposition to a new key | `track_index`, `clip_index`, `target_key`, `mode` (diatonic/chromatic) |

**Built-in** — zero external dependencies, works on every LivePilot install.

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
