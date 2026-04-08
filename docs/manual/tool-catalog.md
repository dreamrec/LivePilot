# LivePilot — Full Tool Catalog

236 tools across 32 domains.

---

## Transport (12)

| Tool | Description |
|------|-------------|
| `get_session_info` | Session state: tempo, tracks, scenes, transport |
| `set_tempo` | Set tempo (20-999 BPM) |
| `set_time_signature` | Set time signature |
| `start_playback` | Start from beginning |
| `stop_playback` | Stop |
| `continue_playback` | Resume from current position |
| `toggle_metronome` | Enable/disable click |
| `set_session_loop` | Set loop start, length, on/off |
| `undo` | Undo last action |
| `redo` | Redo |
| `get_recent_actions` | Recent undo history |
| `get_session_diagnostics` | Analyze session for issues |

## Tracks (17)

| Tool | Description |
|------|-------------|
| `get_track_info` | Track details: clips, devices, mixer |
| `create_midi_track` | New MIDI track |
| `create_audio_track` | New audio track |
| `create_return_track` | New return track |
| `delete_track` | Delete a track |
| `duplicate_track` | Copy track with all content |
| `set_track_name` | Rename |
| `set_track_color` | Set color (0-69) |
| `set_track_mute` | Mute on/off |
| `set_track_solo` | Solo on/off |
| `set_track_arm` | Arm for recording |
| `stop_track_clips` | Stop all clips on track |
| `set_group_fold` | Fold/unfold group track |
| `set_track_input_monitoring` | Set monitoring mode |
| `freeze_track` | Freeze track (render devices to audio) |
| `flatten_track` | Flatten frozen track (commit audio permanently) |
| `get_freeze_status` | Check if track is frozen |

## Clips (11)

| Tool | Description |
|------|-------------|
| `get_clip_info` | Clip details: length, loop, launch |
| `create_clip` | New empty MIDI clip |
| `delete_clip` | Delete a clip |
| `duplicate_clip` | Copy to another slot |
| `fire_clip` | Launch a clip |
| `stop_clip` | Stop a clip |
| `set_clip_name` | Rename |
| `set_clip_color` | Set color |
| `set_clip_loop` | Loop start, end, on/off |
| `set_clip_launch` | Launch mode and quantization |
| `set_clip_warp_mode` | Set warp algorithm |

## Notes (8)

| Tool | Description |
|------|-------------|
| `add_notes` | Add MIDI notes with velocity, probability |
| `get_notes` | Read notes from a region |
| `remove_notes` | Remove notes in a region |
| `remove_notes_by_id` | Remove specific notes by ID |
| `modify_notes` | Change pitch, time, velocity, probability |
| `duplicate_notes` | Copy notes to new position |
| `transpose_notes` | Shift pitch by semitones |
| `quantize_clip` | Quantize to grid |

## Devices (12)

| Tool | Description |
|------|-------------|
| `get_device_info` | Device name, class, parameters |
| `get_device_parameters` | All params with names, values, ranges |
| `set_device_parameter` | Set param by name or index |
| `batch_set_parameters` | Set multiple params in one call |
| `toggle_device` | Enable/disable |
| `delete_device` | Remove from chain |
| `load_device_by_uri` | Load by browser URI |
| `find_and_load_device` | Search and load by name |
| `get_rack_chains` | Get chains in a rack |
| `set_simpler_playback_mode` | Classic/1-shot/slice |
| `set_chain_volume` | Set chain volume in rack |
| `get_device_presets` | List available presets |

## Scenes (12)

| Tool | Description |
|------|-------------|
| `get_scenes_info` | All scenes: name, tempo, color |
| `create_scene` | New scene |
| `delete_scene` | Delete a scene |
| `duplicate_scene` | Copy scene with all clips |
| `fire_scene` | Launch all clips in scene |
| `set_scene_name` | Rename |
| `set_scene_color` | Set color |
| `set_scene_tempo` | Per-scene tempo |
| `get_scene_matrix` | Full clip grid: every track x every scene |
| `fire_scene_clips` | Fire scene with optional track filter |
| `stop_all_clips` | Stop all playing clips (panic) |
| `get_playing_clips` | All currently playing/triggered clips |

## Mixing (11)

| Tool | Description |
|------|-------------|
| `set_track_volume` | Volume (0.0-1.0) |
| `set_track_pan` | Pan (-1.0 to 1.0) |
| `set_track_send` | Send level (0.0-1.0) |
| `get_return_tracks` | Return track info |
| `get_master_track` | Master track info |
| `set_master_volume` | Master volume |
| `get_track_routing` | Input/output routing |
| `set_track_routing` | Set routing by display name |
| `get_track_meters` | Live meter levels |
| `get_master_meters` | Master meter levels |
| `get_mix_snapshot` | Full mix state in one call |

## Browser (4)

| Tool | Description |
|------|-------------|
| `get_browser_tree` | Browse category tree |
| `get_browser_items` | List items in a category |
| `search_browser` | Search by name with filters |
| `load_browser_item` | Load item by URI |

## Arrangement (19)

| Tool | Description |
|------|-------------|
| `get_arrangement_clips` | List arrangement clips |
| `create_arrangement_clip` | New clip at timeline position |
| `add_arrangement_notes` | Add MIDI notes to arrangement clip |
| `get_arrangement_notes` | Read arrangement notes |
| `remove_arrangement_notes` | Remove notes in region |
| `remove_arrangement_notes_by_id` | Remove by ID |
| `modify_arrangement_notes` | Modify arrangement notes |
| `duplicate_arrangement_notes` | Copy notes |
| `transpose_arrangement_notes` | Shift pitch |
| `set_arrangement_clip_name` | Rename arrangement clip |
| `set_arrangement_automation` | Write arrangement automation |
| `back_to_arranger` | Switch to arrangement view |
| `jump_to_time` | Seek to beat position |
| `capture_midi` | Capture played MIDI |
| `start_recording` | Start recording |
| `stop_recording` | Stop recording |
| `get_cue_points` | List cue points |
| `jump_to_cue` | Jump to cue point |
| `toggle_cue_point` | Add/remove cue point |

## Automation (8)

| Tool | Description |
|------|-------------|
| `get_clip_automation` | List envelopes on a clip |
| `set_clip_automation` | Write automation points |
| `clear_clip_automation` | Clear envelopes |
| `apply_automation_shape` | Generate + write curve in one call |
| `apply_automation_recipe` | Apply named recipe |
| `get_automation_recipes` | List all 15 recipes |
| `generate_automation_curve` | Preview curve without writing |
| `analyze_for_automation` | Spectral analysis + suggestions |

## Memory (8)

| Tool | Description |
|------|-------------|
| `memory_learn` | Save a technique |
| `memory_recall` | Search by text/mood/genre |
| `memory_list` | Browse library |
| `memory_get` | Get full technique with payload |
| `memory_update` | Update a technique |
| `memory_delete` | Delete a technique |
| `memory_favorite` | Toggle favorite |
| `memory_replay` | Replay saved technique |

## Analyzer (29) `[M4L]`

| Tool | Description |
|------|-------------|
| `get_master_spectrum` | 8-band frequency analysis |
| `get_master_rms` | RMS and peak levels |
| `get_detected_key` | Krumhansl-Schmuckler key detection |
| `get_hidden_parameters` | All params including hidden ones |
| `get_automation_state` | Automation state per parameter |
| `walk_device_tree` | Recursive device chain tree (6 levels) |
| `get_display_values` | Human-readable param values |
| `get_clip_file_path` | Audio file path on disk |
| `replace_simpler_sample` | Load audio into Simpler |
| `load_sample_to_simpler` | Bootstrap Simpler + load sample |
| `get_simpler_slices` | Slice point positions |
| `crop_simpler` | Crop to active region |
| `reverse_simpler` | Reverse sample |
| `warp_simpler` | Time-stretch to N beats |
| `get_warp_markers` | Get all warp markers |
| `add_warp_marker` | Add warp marker |
| `move_warp_marker` | Move warp marker |
| `remove_warp_marker` | Remove warp marker |
| `scrub_clip` | Preview at beat position |
| `stop_scrub` | Stop preview |
| `get_spectral_shape` | 7 spectral descriptors via FluCoMa |
| `get_mel_spectrum` | 40-band mel spectrum |
| `get_chroma` | 12 pitch class energies |
| `get_onsets` | Real-time onset detection |
| `get_novelty` | Spectral novelty for section boundaries |
| `get_momentary_loudness` | EBU R128 momentary LUFS + peak |
| `check_flucoma` | Verify FluCoMa installation |
| `capture_audio` | Record master output to WAV |
| `capture_stop` | Cancel in-progress capture |

## Devices — Plugin Deep Control (3) `[M4L]`

| Tool | Description |
|------|-------------|
| `get_plugin_parameters` | All VST/AU params including unconfigured |
| `map_plugin_parameter` | Add param to Ableton's Configure list |
| `get_plugin_presets` | List plugin's internal presets/banks |

## Perception (4)

| Tool | Description |
|------|-------------|
| `analyze_loudness` | Integrated LUFS, true peak, LRA, streaming compliance |
| `analyze_spectrum_offline` | Spectral centroid, rolloff, flatness, 5-band balance |
| `compare_to_reference` | Mix vs reference: loudness + spectral delta |
| `read_audio_metadata` | Format, duration, sample rate, tags |

## Theory (7)

| Tool | Description |
|------|-------------|
| `analyze_harmony` | Chord-by-chord Roman numeral analysis |
| `suggest_next_chord` | Theory-valid continuations with style presets |
| `detect_theory_issues` | Parallel 5ths, out-of-key, voice crossing |
| `identify_scale` | Key/mode detection with confidence ranking |
| `harmonize_melody` | 2 or 4-voice SATB harmonization |
| `generate_countermelody` | Species counterpoint (1st/2nd) |
| `transpose_smart` | Diatonic or chromatic transposition |

## Generative (5)

| Tool | Description |
|------|-------------|
| `generate_euclidean_rhythm` | Bjorklund algorithm, identifies named rhythms |
| `layer_euclidean_rhythms` | Stack patterns for polyrhythmic textures |
| `generate_tintinnabuli` | Arvo Part — triad voice from melody |
| `generate_phase_shift` | Steve Reich — drifting canon |
| `generate_additive_process` | Philip Glass — expanding/contracting melody |

## Harmony (4)

| Tool | Description |
|------|-------------|
| `navigate_tonnetz` | PRL neighbors at depth N |
| `find_voice_leading_path` | Shortest path between two chords |
| `classify_progression` | Identify neo-Riemannian pattern |
| `suggest_chromatic_mediants` | All chromatic mediant relations |

## MIDI I/O (4)

| Tool | Description |
|------|-------------|
| `export_clip_midi` | Export clip to .mid file |
| `import_midi_to_clip` | Import .mid into session clip |
| `analyze_midi_file` | Offline MIDI analysis |
| `extract_piano_roll` | 2D velocity matrix extraction |
