# LivePilot Tool Reference

127 MCP tools across 11 domains. Tools marked with [M4L] require the LivePilot Analyzer device on the master track.

## Transport (12 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_session_info` | Get session state: tempo, tracks, scenes, transport | (none) |
| `set_tempo` | Set song tempo (20-999 BPM) | `tempo` |
| `set_time_signature` | Set time signature (e.g., 4/4, 6/8) | `numerator`, `denominator` |
| `start_playback` | Start from beginning | (none) |
| `stop_playback` | Stop playback | (none) |
| `continue_playback` | Continue from current position | (none) |
| `toggle_metronome` | Enable/disable metronome | `enabled` |
| `set_session_loop` | Set loop on/off with optional region | `enabled` |
| `undo` | Undo last action | (none) |
| `redo` | Redo last undone action | (none) |
| `get_recent_actions` | Log of recent commands (newest first) | (none) |
| `get_session_diagnostics` | Analyze session for issues (armed tracks, solos, empty clips) | (none) |

## Tracks (14 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_track_info` | Track details: clips, devices, mixer state | `track_index` |
| `create_midi_track` | Create MIDI track (-1 = append) | (none) |
| `create_audio_track` | Create audio track (-1 = append) | (none) |
| `create_return_track` | Create return track | (none) |
| `delete_track` | Delete track by index | `track_index` |
| `duplicate_track` | Duplicate track with all contents | `track_index` |
| `set_track_name` | Rename a track | `track_index`, `name` |
| `set_track_color` | Set track color (0-69) | `track_index`, `color_index` |
| `set_track_mute` | Mute/unmute track | `track_index`, `muted` |
| `set_track_solo` | Solo/unsolo track | `track_index`, `solo` |
| `set_track_arm` | Arm/disarm for recording | `track_index`, `armed` |
| `stop_track_clips` | Stop all playing clips on track | `track_index` |
| `set_group_fold` | Fold/unfold group track | `track_index`, `folded` |
| `set_track_input_monitoring` | Set monitoring (0=In, 1=Auto, 2=Off) | `track_index`, `state` |

## Clips (11 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_clip_info` | Clip details: name, length, loop, launch | `track_index`, `clip_index` |
| `create_clip` | Create empty MIDI clip (length in beats) | `track_index`, `clip_index`, `length` |
| `delete_clip` | Delete clip from slot | `track_index`, `clip_index` |
| `duplicate_clip` | Duplicate clip to another slot | `track_index`, `clip_index`, `target_track`, `target_clip` |
| `fire_clip` | Launch/fire a clip | `track_index`, `clip_index` |
| `stop_clip` | Stop a playing clip | `track_index`, `clip_index` |
| `set_clip_name` | Rename a clip | `track_index`, `clip_index`, `name` |
| `set_clip_color` | Set clip color (0-69) | `track_index`, `clip_index`, `color_index` |
| `set_clip_loop` | Set loop on/off and region | `track_index`, `clip_index` |
| `set_clip_launch` | Set launch mode (Trigger/Gate/Toggle/Repeat) | `track_index`, `clip_index`, `mode` |
| `set_clip_warp_mode` | Set warp mode (Beats/Tones/Texture/Re-Pitch/Complex/Complex Pro) | `track_index`, `clip_index`, `mode` |

## Notes (8 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `add_notes` | Add MIDI notes to a clip | `track_index`, `clip_index`, `notes` |
| `get_notes` | Get MIDI notes from a clip region | `track_index`, `clip_index` |
| `remove_notes` | Remove notes in a pitch/time region | `track_index`, `clip_index` |
| `remove_notes_by_id` | Remove specific notes by ID | `track_index`, `clip_index`, `note_ids` |
| `modify_notes` | Modify existing notes by ID | `track_index`, `clip_index`, `modifications` |
| `duplicate_notes` | Duplicate notes by ID with time offset | `track_index`, `clip_index`, `note_ids` |
| `transpose_notes` | Transpose notes by semitones | `track_index`, `clip_index`, `semitones` |
| `quantize_clip` | Quantize notes to grid | `track_index`, `clip_index`, `grid` |

## Devices (12 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_device_info` | Device details: name, class, type, active | `track_index`, `device_index` |
| `get_device_parameters` | All parameters with names, values, ranges | `track_index`, `device_index` |
| `set_device_parameter` | Set parameter by name or index | `track_index`, `device_index`, `value` |
| `batch_set_parameters` | Set multiple parameters in one call | `track_index`, `device_index`, `parameters` |
| `toggle_device` | Enable/disable device | `track_index`, `device_index`, `active` |
| `delete_device` | Delete device from track | `track_index`, `device_index` |
| `load_device_by_uri` | Load device by browser URI | `track_index`, `uri` |
| `find_and_load_device` | Search and load device by name | `track_index`, `device_name` |
| `set_simpler_playback_mode` | Set Simpler mode (Classic/One-Shot/Slice) | `track_index`, `device_index`, `playback_mode` |
| `get_rack_chains` | Get chains in rack device | `track_index`, `device_index` |
| `set_chain_volume` | Set chain volume/pan in rack | `track_index`, `device_index`, `chain_index` |
| `get_device_presets` | List available presets for a device | `device_name` |

## Scenes (8 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_scenes_info` | Info for all scenes: name, tempo, color | (none) |
| `create_scene` | Create scene (-1 = append) | (none) |
| `delete_scene` | Delete scene by index | `scene_index` |
| `duplicate_scene` | Duplicate scene | `scene_index` |
| `fire_scene` | Fire/launch scene | `scene_index` |
| `set_scene_name` | Rename scene | `scene_index`, `name` |
| `set_scene_color` | Set scene color (0-69) | `scene_index`, `color_index` |
| `set_scene_tempo` | Set scene tempo (20-999 BPM) | `scene_index`, `tempo` |

## Mixing (11 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `set_track_volume` | Set track volume (0.0-1.0) | `track_index`, `volume` |
| `set_track_pan` | Set panning (-1.0 to 1.0) | `track_index`, `pan` |
| `set_track_send` | Set send level (0.0-1.0) | `track_index`, `send_index`, `value` |
| `get_return_tracks` | Info on all return tracks | (none) |
| `get_master_track` | Master track info | (none) |
| `set_master_volume` | Set master volume (0.0-1.0) | `volume` |
| `get_track_meters` | Real-time output meter levels | (none) |
| `get_master_meters` | Master track meter levels | (none) |
| `get_mix_snapshot` | Full mix state: all meters, volumes, pans, sends | (none) |
| `get_track_routing` | Input/output routing info | `track_index` |
| `set_track_routing` | Set input/output routing by display name | `track_index` |

## Browser (4 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_browser_tree` | Overview of browser categories | (none) |
| `get_browser_items` | List items at browser path | `path` |
| `search_browser` | Search browser tree with filters | `path` |
| `load_browser_item` | Load instrument/effect by URI | `track_index`, `uri` |

## Arrangement (19 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_arrangement_clips` | All arrangement clips on a track | `track_index` |
| `jump_to_time` | Jump to beat position | `beat_time` |
| `capture_midi` | Capture recently played MIDI | (none) |
| `start_recording` | Start session or arrangement recording | (none) |
| `stop_recording` | Stop all recording | (none) |
| `get_cue_points` | Get all cue points | (none) |
| `jump_to_cue` | Jump to cue point by index | `cue_index` |
| `toggle_cue_point` | Set/delete cue point at playback position | (none) |
| `create_arrangement_clip` | Duplicate session clip into arrangement | `track_index`, `clip_slot_index`, `start_time`, `length` |
| `add_arrangement_notes` | Add MIDI notes to arrangement clip | `track_index`, `clip_index`, `notes` |
| `set_arrangement_automation` | Write automation envelope points | `track_index`, `clip_index`, `parameter_type`, `points` |
| `transpose_arrangement_notes` | Transpose arrangement notes by semitones | `track_index`, `clip_index`, `semitones` |
| `set_arrangement_clip_name` | Rename arrangement clip | `track_index`, `clip_index`, `name` |
| `back_to_arranger` | Switch from session to arrangement playback | (none) |
| `get_arrangement_notes` | Get notes from arrangement clip | `track_index`, `clip_index` |
| `remove_arrangement_notes` | Remove notes in pitch/time region | `track_index`, `clip_index` |
| `remove_arrangement_notes_by_id` | Remove specific notes by ID | `track_index`, `clip_index`, `note_ids` |
| `modify_arrangement_notes` | Modify notes by ID | `track_index`, `clip_index`, `modifications` |
| `duplicate_arrangement_notes` | Duplicate notes by ID | `track_index`, `clip_index`, `note_ids` |

## Memory (8 tools)

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `memory_learn` | Save technique with qualities | `name`, `type`, `qualities`, `payload` |
| `memory_recall` | Search techniques by query/filters | (none) |
| `memory_get` | Fetch full technique by ID | `technique_id` |
| `memory_replay` | Get replay plan for technique | `technique_id` |
| `memory_list` | Browse technique library | (none) |
| `memory_favorite` | Star/rate a technique | `technique_id` |
| `memory_update` | Update technique metadata | `technique_id` |
| `memory_delete` | Delete technique (creates backup) | `technique_id` |

## Analyzer (20 tools) [M4L]

All tools in this domain require the LivePilot Analyzer M4L device on the master track.

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_master_spectrum` | 8-band frequency analysis of master bus | (none) |
| `get_master_rms` | Real-time RMS, peak, and pitch | (none) |
| `get_detected_key` | Detected musical key (Krumhansl-Schmuckler) | (none) |
| `get_hidden_parameters` | All parameters including hidden ones | `track_index`, `device_index` |
| `get_automation_state` | Automation state (active/overridden) | `track_index`, `device_index` |
| `walk_device_tree` | Recursive rack/drum pad tree walk | `track_index` |
| `get_display_values` | Human-readable parameter values | `track_index`, `device_index` |
| `get_clip_file_path` | Audio file path on disk | `track_index`, `clip_index` |
| `replace_simpler_sample` | Load audio file into Simpler | `track_index`, `device_index`, `file_path` |
| `load_sample_to_simpler` | Bootstrap + load sample into new Simpler | `track_index`, `file_path` |
| `get_simpler_slices` | Slice positions from Simpler | `track_index` |
| `crop_simpler` | Crop sample to active region | `track_index` |
| `reverse_simpler` | Reverse sample in Simpler | `track_index` |
| `warp_simpler` | Warp sample to N beats | `track_index` |
| `get_warp_markers` | All warp markers from audio clip | `track_index`, `clip_index` |
| `add_warp_marker` | Add warp marker at beat position | `track_index`, `clip_index`, `beat_time` |
| `move_warp_marker` | Move warp marker | `track_index`, `clip_index`, `old_beat_time`, `new_beat_time` |
| `remove_warp_marker` | Remove warp marker | `track_index`, `clip_index`, `beat_time` |
| `scrub_clip` | Preview clip at beat position | `track_index`, `clip_index`, `beat_time` |
| `stop_scrub` | Stop clip preview | `track_index`, `clip_index` |

## Track Index Convention

All tools that accept `track_index` use these conventions:
- **0+** — regular tracks (MIDI, audio, group)
- **-1, -2, ...** — return tracks (A, B, ...)
- **-1000** — master track

Not all tools support negative indices. Check individual tool docs for support.
