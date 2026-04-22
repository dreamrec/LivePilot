# LivePilot — Full Tool Catalog (Generated)

426 tools across 52 domains.

> Auto-generated from `mcp.list_tools()`. Do not hand-edit.
> Regenerate: `python3 scripts/generate_tool_catalog.py`

---

## Agent Os (8)

| Tool | Description |
|------|-------------|
| `analyze_outcomes` | Analyze accumulated outcome memories to identify user taste patterns. |
| `build_world_model` | Build a WorldModel snapshot of the current Ableton session. |
| `compile_goal_vector` | Compile a user request into a validated GoalVector. |
| `evaluate_move` | Evaluate whether a production move improved the mix toward the goal. |
| `get_taste_profile` | Get the user's production taste profile from outcome history. |
| `get_technique_card` | Search for technique cards — structured production recipes. |
| `get_turn_budget` | Get a resource budget for the current agent turn. |
| `route_request` | Route a production request to the right engine(s). |

## Analyzer (37)

| Tool | Description |
|------|-------------|
| `add_drum_rack_pad` | Add a new pad (chain) to a Drum Rack and load a sample into it. |
| `add_warp_marker` | Add a warp marker to an audio clip at the specified beat position. |
| `analyze_loudness_live` | Analyze the currently-playing master output's loudness over a window. |
| `capture_audio` | Capture audio from Ableton Live to a WAV file on disk. |
| `capture_stop` | Stop an in-progress audio capture early. |
| `check_flucoma` | Check if FluCoMa is installed and sending data. |
| `classify_simpler_slices` | Classify each Simpler slice as KICK / SNARE / HAT / ghost via FFT analysis. |
| `compressor_set_sidechain` | Configure a Compressor's sidechain INPUT ROUTING (BUG-A3). |
| `crop_simpler` | Crop a Simpler's sample to the currently active region. |
| `get_automation_state` | Get automation state for all parameters on a device. |
| `get_chroma` | Get 12 pitch class energies from FluCoMa for real-time chord detection. |
| `get_clip_file_path` | Get the audio file path of a clip on disk. |
| `get_detected_key` | Get the detected musical key and scale of the current session. |
| `get_display_values` | Get human-readable display values for all device parameters. |
| `get_hidden_parameters` | Get ALL parameters for a device, including hidden ones not accessible |
| `get_master_rms` | Get real-time RMS and peak levels from the master bus. |
| `get_master_spectrum` | Get 8-band frequency analysis of the master bus. |
| `get_mel_spectrum` | Get 40-band mel spectrum from FluCoMa (5x resolution of get_master_spectrum). |
| `get_momentary_loudness` | Get EBU R128 momentary LUFS + true peak from FluCoMa. |
| `get_novelty` | Get real-time spectral novelty for section boundary detection from FluCoMa. |
| `get_onsets` | Get real-time onset/transient detection from FluCoMa. |
| `get_simpler_slices` | Get slice point positions from a Simpler device. |
| `get_spectral_shape` | Get 7 real-time spectral descriptors from FluCoMa. |
| `get_warp_markers` | Get all warp markers from an audio clip. |
| `load_sample_to_simpler` | Load an audio file into a NEW Simpler device on a track. |
| `move_warp_marker` | Move a warp marker from one beat position to another. |
| `reconnect_bridge` | Attempt to reconnect the M4L UDP bridge (port 9880). |
| `remove_warp_marker` | Remove a warp marker from an audio clip at the specified beat. |
| `replace_simpler_sample` | Load an audio file into a Simpler device by absolute file path. |
| `reverse_simpler` | Reverse the sample loaded in a Simpler device. |
| `scrub_clip` | Scrub/preview a clip at a specific beat position. |
| `simpler_set_warp` | Toggle a Simpler's sample warping + set the warp algorithm (BUG-A2). |
| `stop_scrub` | Stop scrubbing a clip. Call after scrub_clip to stop preview. |
| `verify_all_devices_health` | Run verify_device_health across every eligible track in one call. |
| `verify_device_health` | Fire a test MIDI note at a track's instrument and check for output. |
| `walk_device_tree` | Walk the full device chain tree including nested racks, drum pads, |
| `warp_simpler` | Warp a Simpler's sample to fit the specified number of beats. |

## Arrangement (21)

| Tool | Description |
|------|-------------|
| `add_arrangement_notes` | Add MIDI notes to an arrangement clip. |
| `back_to_arranger` | Switch playback from session clips back to the arrangement timeline. |
| `capture_midi` | Capture recently played MIDI notes into a new clip. |
| `create_arrangement_clip` | Duplicate a session clip into Arrangement View at a specific beat position. |
| `create_native_arrangement_clip` | Create an empty MIDI clip directly in Arrangement View (Live 12.1.10+). |
| `duplicate_arrangement_notes` | Duplicate specific notes in an arrangement clip by ID, with optional time offset (beats). |
| `force_arrangement` | Force ALL tracks to follow the arrangement and start playback. |
| `get_arrangement_clips` | Get all arrangement clips on a track. |
| `get_arrangement_notes` | Get MIDI notes from an arrangement clip. Returns note_id, pitch, start_time, |
| `get_cue_points` | Get all cue points in the arrangement. |
| `jump_to_cue` | Jump to a cue point by index. |
| `jump_to_time` | Jump to a specific beat time in the arrangement. |
| `modify_arrangement_notes` | Modify existing MIDI notes in an arrangement clip by ID. modifications is a JSON array: |
| `remove_arrangement_notes` | Remove all MIDI notes in a pitch/time region of an arrangement clip. Defaults remove ALL notes. |
| `remove_arrangement_notes_by_id` | Remove specific MIDI notes from an arrangement clip by their IDs. |
| `set_arrangement_automation` | Write automation envelope points into an arrangement clip. |
| `set_arrangement_clip_name` | Rename an arrangement clip by its index in the track's arrangement_clips list. |
| `start_recording` | Start recording. arrangement=True for arrangement, False for session. |
| `stop_recording` | Stop all recording (both session and arrangement). |
| `toggle_cue_point` | Set or delete a cue point at the current playback position. |
| `transpose_arrangement_notes` | Transpose notes in an arrangement clip by semitones (positive=up, negative=down). |

## Atlas (10)

| Tool | Description |
|------|-------------|
| `atlas_chain_suggest` | Suggest a full device chain for a track role. |
| `atlas_compare` | Compare two devices — strengths, weaknesses, and recommendation for a role. |
| `atlas_describe_chain` | Free-text describe-a-chain: "a granular pad that sounds like Tim Hecker" |
| `atlas_device_info` | Get complete atlas knowledge about a device — parameters, recipes, pairings, gotchas. |
| `atlas_pack_info` | Inspect a single Ableton pack — device list + enrichment coverage. |
| `atlas_search` | Search the device atlas for instruments, effects, kits, or plugins. |
| `atlas_suggest` | Suggest devices for a production intent. |
| `atlas_techniques_for_device` | Reverse-lookup: what techniques / principles reference this device? |
| `reload_atlas` | Force the atlas to re-read device_atlas.json from disk. |
| `scan_full_library` | Scan the full Ableton browser and rebuild the device atlas. |

## Automation (9)

| Tool | Description |
|------|-------------|
| `analyze_for_automation` | Analyze a track's spectrum and suggest automation targets. |
| `apply_automation_recipe` | Apply a named automation recipe to a session clip. |
| `apply_automation_shape` | Generate and apply an automation curve to a session clip. |
| `clear_clip_automation` | Clear automation envelopes from a session clip. |
| `generate_automation_curve` | Generate automation curve points WITHOUT writing them. |
| `get_automation_recipes` | List all available automation recipes with descriptions. |
| `get_clip_automation` | List all automation envelopes on a session clip. |
| `set_arrangement_automation_via_session_record` | Write an arrangement automation envelope at a specific beat via session record. |
| `set_clip_automation` | Write automation points to a session clip envelope. |

## Browser (4)

| Tool | Description |
|------|-------------|
| `get_browser_items` | List items at a browser path (e.g., 'instruments/Analog'). |
| `get_browser_tree` | Get an overview of browser categories and their children. |
| `load_browser_item` | Load a browser item (instrument/effect/sample) onto a track by URI. |
| `search_browser` | Search the browser tree under a path, optionally filtering by name. |

## Clips (16)

| Tool | Description |
|------|-------------|
| `check_clip_key_consistency` | Cross-check a clip's filename-encoded key against the session key (BUG-D1). |
| `create_clip` | Create an empty MIDI clip in a clip slot (length in beats). |
| `delete_clip` | Delete a clip from a clip slot. This removes all notes and automation. Use undo to revert. |
| `duplicate_clip` | Duplicate a clip from one slot to another. |
| `fire_clip` | Launch/fire a clip slot. |
| `get_clip_info` | Get detailed info about a clip: name, length, loop, launch settings. |
| `get_clip_scale` | Read a clip's per-clip scale override (Live 12.0+). |
| `set_clip_color` | Set clip color (0-69, Ableton's color palette). |
| `set_clip_launch` | Set clip launch mode (0=Trigger, 1=Gate, 2=Toggle, 3=Repeat) and optional quantization. |
| `set_clip_loop` | Enable/disable clip looping and optionally set loop start/end (in beats). |
| `set_clip_name` | Rename a clip in the Session view. The new name appears on the clip slot and in Device Chain displays. |
| `set_clip_pitch` | Set pitch transposition and/or gain on an audio clip (BUG-A5). |
| `set_clip_scale` | Set a clip's per-clip scale override (Live 12.0+). |
| `set_clip_scale_mode` | Enable or disable Scale Mode on a single clip (Live 12.0+). |
| `set_clip_warp_mode` | Set warp mode for an audio clip (0=Beats, 1=Tones, 2=Texture, 3=Re-Pitch, 4=Complex, 6=Complex Pro). |
| `stop_clip` | Stop a playing clip. |

## Composer (4)

| Tool | Description |
|------|-------------|
| `augment_with_samples` | Plan sample-based layers to add to the existing session. |
| `compose` | Plan a full multi-layer composition from a text prompt. |
| `get_composition_plan` | Preview what compose would do without executing or spending credits. |
| `propose_composer_branches` | Emit N distinct compositional hypotheses for a single prompt (PR5/v2). |

## Composition (9)

| Tool | Description |
|------|-------------|
| `analyze_composition` | Run full composition analysis on the current Ableton session. |
| `apply_gesture_template` | Apply a compound gesture template — multiple coordinated automation gestures. |
| `evaluate_composition_move` | Evaluate whether a composition move improved the arrangement. |
| `get_harmony_field` | Analyze the harmonic content of a section — key, chords, voice-leading, tension. |
| `get_phrase_grid` | Get phrase boundaries for a specific section. |
| `get_section_graph` | Get just the section graph — lightweight structural overview. |
| `get_section_outcomes` | Get composition move success rates grouped by section type. |
| `get_transition_analysis` | Analyze transition quality between all adjacent sections. |
| `plan_gesture` | Plan a musical gesture — map abstract intent to concrete automation. |

## Creative Constraints (5)

| Tool | Description |
|------|-------------|
| `apply_creative_constraint_set` | Apply creative constraints to focus suggestions. |
| `distill_reference_principles` | Learn musical principles from a reference — not surface traits. |
| `generate_constrained_variants` | Generate creative variants under active constraints. |
| `generate_reference_inspired_variants` | Generate creative variants inspired by a distilled reference. |
| `map_reference_principles_to_song` | Map distilled reference principles to the current song. |

## Device Forge (3)

| Tool | Description |
|------|-------------|
| `generate_m4l_effect` | Generate a Max for Live device from gen~ codebox code. |
| `install_m4l_device` | Copy a .amxd file to Ableton's User Library. |
| `list_genexpr_templates` | List available gen~ DSP building block templates. |

## Devices (42)

| Tool | Description |
|------|-------------|
| `add_rack_macro` | Add one macro to a Rack, raising visible_macro_count by 1 (Live 11+). |
| `add_wavetable_mod_route` | Create a modulation routing on a Wavetable device (Live 11+). |
| `batch_set_parameters` | Set multiple device parameters in one call. |
| `clear_simpler_slices` | Remove all manual slices from the Simpler (Live 11+). |
| `copy_device_state` | Copy one A/B state to the other (Live 12.3+). |
| `delete_device` | Delete a device from a track. Use undo to revert if needed. |
| `delete_rack_variation` | Delete a Rack variation by index (Live 11+). |
| `find_and_load_device` | Search the browser for a device by name and load it onto a track. |
| `get_device_ab_state` | Read a device's A/B compare state (Live 12.3+). |
| `get_device_info` | Get info about a device: name, class, type, active state, parameter count. |
| `get_device_parameters` | Get all parameters for a device with names, values, and ranges. |
| `get_device_presets` | List available presets for an Ableton device (e.g. 'Corpus', 'Drum Buss', 'Wavetable'). |
| `get_plugin_parameters` | Get ALL parameters from a VST/AU plugin including unconfigured ones. |
| `get_plugin_presets` | List a VST/AU plugin's internal presets and banks. |
| `get_rack_chains` | Get all chains in a rack device with volume, pan, mute, solo. |
| `get_rack_variations` | Get the Rack's variation count, currently selected variation index, and visible macro count (Live 11+). |
| `get_wavetable_mod_amount` | Read the current modulation amount for a Wavetable source→target routing (Live 11+). |
| `get_wavetable_mod_matrix` | Dump all non-zero modulation routings on a Wavetable device (Live 11+). |
| `get_wavetable_mod_targets` | Enumerate visible modulation target parameter names on a Wavetable (Live 11+). |
| `import_slices_from_onsets` | Force Transient slicing mode, set sensitivity, and re-detect (Live 11+). |
| `insert_device` | Insert a native Live device by name — 10x faster than browser search (Live 12.3+). |
| `insert_rack_chain` | Insert a new chain into a Rack device — Instrument Rack, Audio Effect Rack, or Drum Rack (Live 12.3+). |
| `insert_simpler_slice` | Insert a slice at a sample-frame position on a Simpler (Live 11+). |
| `load_device_by_uri` | Load a device onto a track using a browser URI string. |
| `map_plugin_parameter` | Add a plugin parameter to Ableton's Configure list for automation. |
| `move_device` | Move a device to a new position on the same or different track. |
| `move_simpler_slice` | Move an existing slice from one sample-frame position to another (Live 11+). |
| `randomize_rack_macros` | Randomize the Rack's macro values using Live's built-in randomize dice (Live 11+). |
| `recall_rack_variation` | Select and recall a stored Rack variation by index (Live 11+). |
| `remove_rack_macro` | Remove the last macro from a Rack, lowering visible_macro_count by 1 (Live 11+). |
| `remove_simpler_slice` | Remove a slice at an exact sample-frame position (Live 11+). |
| `rename_chain` | Rename a chain inside any Rack device — Instrument, Audio Effect, or Drum (Live 12.3+). |
| `reset_simpler_slices` | Reset the Simpler's slices to Live's default detection (Live 11+). |
| `set_chain_volume` | Set volume and/or pan for a chain in a rack device. |
| `set_device_parameter` | Set a device parameter by name or index. |
| `set_drum_chain_note` | Set which MIDI note triggers a Drum Rack chain (Live 12.3+). |
| `set_rack_visible_macros` | Set the Rack's visible_macro_count directly (1-16, Live 11+). |
| `set_simpler_playback_mode` | Set Simpler's playback mode. playback_mode: 0=Classic, 1=One-Shot, 2=Slice. slice_by (Slice only): 0=Transient, 1=Beat, |
| `set_wavetable_mod_amount` | Set the modulation amount for a Wavetable source→target routing (Live 11+). |
| `store_rack_variation` | Store the Rack's current macro values as a new variation (Live 11+). |
| `toggle_device` | Enable or disable a device. |
| `toggle_device_ab` | Swap a device's A/B state (Live 12.3+). |

## Diagnostics (3)

| Tool | Description |
|------|-------------|
| `get_control_surface_info` | Read detailed info about a single control surface. |
| `list_control_surfaces` | List all active ControlSurface instances (Push, APC, Launchkey, etc.). |
| `reload_handlers` | Reload every Remote Script handler module in Ableton — dev-loop helper. |

## Evaluation (1)

| Tool | Description |
|------|-------------|
| `evaluate_with_fabric` | Evaluate a move using the unified Evaluation Fabric. |

## Experiment (5)

| Tool | Description |
|------|-------------|
| `commit_experiment` | Commit the winning branch — re-apply its moves permanently. |
| `compare_experiments` | Compare and rank all evaluated branches in an experiment. |
| `create_experiment` | Create an experiment set to compare multiple approaches. |
| `discard_experiment` | Discard an entire experiment — no changes are kept. |
| `run_experiment` | Run all pending branches in an experiment. |

## Follow Actions (8)

| Tool | Description |
|------|-------------|
| `apply_follow_action_preset` | Apply a named follow-action preset to a clip (Live 12.0+). |
| `clear_clip_follow_action` | Disable follow action on a clip (Live 12.0+). |
| `clear_scene_follow_action` | Disable a scene's follow action (Live 12.2+). |
| `get_clip_follow_action` | Read a clip's follow-action state (Live 12.0+). |
| `get_scene_follow_action` | Read a scene's follow-action state (Live 12.2+). |
| `list_follow_action_types` | List valid follow-action names (Live 12.0+). |
| `set_clip_follow_action` | Set a clip's follow action (Live 12.0+). Any omitted arg preserves. |
| `set_scene_follow_action` | Set a scene's follow action (Live 12.2+). Any omitted arg preserves. |

## Generative (5)

| Tool | Description |
|------|-------------|
| `generate_additive_process` | Generate an additive process (Philip Glass technique). |
| `generate_euclidean_rhythm` | Generate a Euclidean rhythm using the Bjorklund algorithm. |
| `generate_phase_shift` | Generate a phase-shifted canon (Steve Reich technique). |
| `generate_tintinnabuli` | Generate a tintinnabuli voice (Arvo Pärt technique). |
| `layer_euclidean_rhythms` | Stack multiple Euclidean rhythms for polyrhythmic textures. |

## Grooves (7)

| Tool | Description |
|------|-------------|
| `assign_clip_groove` | Assign a groove to a clip (Live 11+). |
| `get_clip_groove` | Read a clip's current groove assignment (Live 11+). |
| `get_groove_info` | Read a single groove's parameters (Live 11+). |
| `get_song_groove_amount` | Read the master groove amount dial (Live 11+). |
| `list_grooves` | List all grooves in the Groove Pool (Live 11+). |
| `set_groove_params` | Adjust a groove's parameters (Live 11+). Omitted args preserve. |
| `set_song_groove_amount` | Set the master groove amount dial (Live 11+). |

## Harmony (4)

| Tool | Description |
|------|-------------|
| `classify_progression` | Classify a chord progression by its neo-Riemannian transform pattern. |
| `find_voice_leading_path` | Find the shortest neo-Riemannian path between two chords. |
| `navigate_tonnetz` | Show neo-Riemannian neighbors of a chord on the Tonnetz. |
| `suggest_chromatic_mediants` | Suggest all chromatic mediant relations for a chord. |

## Hook Hunter (9)

| Tool | Description |
|------|-------------|
| `compare_phrase_impact` | Compare phrase-level emotional impact across multiple sections. |
| `detect_hook_neglect` | Detect if a strong hook exists but is underused across sections. |
| `detect_payoff_failure` | Detect where the song should deliver a payoff but doesn't. |
| `develop_hook` | Suggest development strategies for a hook. |
| `find_primary_hook` | Find the most salient hook in the current session. |
| `measure_hook_salience` | Measure the salience of a specific hook or the primary hook. |
| `rank_hook_candidates` | List and rank all hook candidates in the session. |
| `score_phrase_impact` | Score a section's emotional impact as a musical phrase. |
| `suggest_payoff_repair` | Generate repair strategies for detected payoff failures. |

## Memory (18)

| Tool | Description |
|------|-------------|
| `add_session_memory` | Add an ephemeral session memory entry (observation, hypothesis, decision, issue). |
| `explain_taste_inference` | Explain why the system thinks the user prefers certain approaches. |
| `get_anti_preferences` | Return all recorded anti-preferences — dimensions the user has repeatedly disliked. |
| `get_promotion_candidates` | Check the session ledger for entries eligible for memory promotion. |
| `get_session_memory` | Return recent session memory entries — ephemeral observations, hypotheses, decisions. |
| `get_taste_dimensions` | Return all taste dimensions — user preferences inferred from kept/undone outcomes. |
| `get_taste_graph` | Get the full TasteGraph — extended preferences including move families, |
| `memory_delete` | Delete a technique from the library (creates backup first). |
| `memory_favorite` | Star and/or rate a technique (rating 0-5). |
| `memory_get` | Fetch a full technique by ID, including payload for replay. |
| `memory_learn` | Save a new technique to the memory library with stylistic qualities. type must be one of: beat_pattern, device_chain, mi |
| `memory_list` | Browse the technique library with optional filtering. |
| `memory_recall` | Search the technique library by text query and/or filters. Returns summaries (no payload). |
| `memory_replay` | Retrieve a technique with a replay plan for the agent to execute. adapt=false: returns step-by-step replay plan for exac |
| `memory_update` | Update name, tags, or qualities on an existing technique. Qualities are merged (lists replace). |
| `rank_moves_by_taste` | Rank semantic moves by taste fit for the current user. |
| `record_anti_preference` | Record a user dislike for a dimension+direction. direction must be 'increase' or 'decrease'. |
| `record_positive_preference` | Record a user preference for more/less of a dimension. |

## Midi Io (4)

| Tool | Description |
|------|-------------|
| `analyze_midi_file` | Analyze a .mid file — works offline, no Ableton needed. |
| `export_clip_midi` | Export a session clip's notes to a .mid file. |
| `extract_piano_roll` | Extract a 2D piano roll matrix from a .mid file. Offline-capable. |
| `import_midi_to_clip` | Load a .mid file into a session clip. |

## Miditool (4)

| Tool | Description |
|------|-------------|
| `get_miditool_context` | Return the most recent MIDI Tool context received from the bridge. |
| `install_miditool_device` | Install LivePilot MIDI Tool .amxd files into Ableton's User Library. |
| `list_miditool_generators` | Enumerate the generators available for MIDI Tool targets. |
| `set_miditool_target` | Configure which LivePilot generator handles MIDI Tool requests. |

## Mix Engine (6)

| Tool | Description |
|------|-------------|
| `analyze_mix` | Build full mix state and run all critics. |
| `evaluate_mix_move` | Score a mix change using the evaluation fabric. |
| `get_masking_report` | Get detailed frequency collision report. |
| `get_mix_issues` | Run all mix critics and return detected issues only. |
| `get_mix_summary` | Lightweight mix overview — track count, issue count, dynamics state. |
| `plan_mix_move` | Get ranked move suggestions based on current mix issues. |

## Mixing (11)

| Tool | Description |
|------|-------------|
| `get_master_meters` | Read real-time output meter levels for the master track (left, right, peak). |
| `get_master_track` | Get master track info: volume, panning, devices. |
| `get_mix_snapshot` | Get a complete mix snapshot: all track meters, volumes, pans, mute/solo, |
| `get_return_tracks` | Get info about all return tracks: name, volume, panning. |
| `get_track_meters` | Read real-time output meter levels for tracks. |
| `get_track_routing` | Get input/output routing info for a track. Use negative track_index for return tracks (-1=A, -2=B). |
| `set_master_volume` | Set the master track volume (0.0-1.0). |
| `set_track_pan` | Set a track's panning (-1.0 left to 1.0 right). Use negative track_index for return tracks (-1=A, -2=B). |
| `set_track_routing` | Set input/output routing for a track by display name. Use negative track_index for return tracks (-1=A, -2=B). |
| `set_track_send` | Set a send level on a track (0.0-1.0). |
| `set_track_volume` | Set a track's volume (0.0-1.0). Use negative track_index for return tracks (-1=A, -2=B). |

## Motif (2)

| Tool | Description |
|------|-------------|
| `get_motif_graph` | Detect recurring melodic and rhythmic patterns across all tracks. |
| `transform_motif` | Transform a musical motif using classical composition techniques. |

## Musical Intelligence (6)

| Tool | Description |
|------|-------------|
| `analyze_phrase_arc` | Analyze a captured audio phrase for musical quality. |
| `compare_phrase_renders` | Compare multiple audio captures and rank by musical quality. |
| `detect_repetition_fatigue` | Detect repetition fatigue — are patterns overused? |
| `detect_role_conflicts` | Detect role conflicts — are tracks fighting for the same musical space? |
| `infer_section_purposes` | Infer what each section/scene is trying to do musically. |
| `score_emotional_arc` | Score the emotional arc of the arrangement. |

## Notes (8)

| Tool | Description |
|------|-------------|
| `add_notes` | Add MIDI notes to a clip. notes is a JSON array: [{pitch, start_time, duration, velocity?, probability?, velocity_deviat |
| `duplicate_notes` | Duplicate specific notes by ID (JSON array of ints), with optional time offset (in beats). |
| `get_notes` | Get MIDI notes from a clip region. Returns note_id, pitch, start_time, duration, velocity, mute, probability. |
| `modify_notes` | Modify existing MIDI notes by ID. modifications is a JSON array: [{note_id, pitch?, start_time?, duration?, velocity?, p |
| `quantize_clip` | Quantize a clip's notes to a grid. grid is a RecordQuantization enum: 0=None, 1=1/4, 2=1/8, 3=1/8T, 4=1/8+T, 5=1/16, 6=1 |
| `remove_notes` | Remove all MIDI notes in a pitch/time region. Use undo to revert. Defaults remove ALL notes in the clip. |
| `remove_notes_by_id` | Remove specific MIDI notes by their IDs (JSON array of ints). Use undo to revert. |
| `transpose_notes` | Transpose notes in a time range by semitones (positive=up, negative=down). |

## Perception (4)

| Tool | Description |
|------|-------------|
| `analyze_loudness` | Analyze the integrated loudness of an audio file (offline — no Ableton needed). |
| `analyze_spectrum_offline` | Analyze the frequency spectrum of an audio file (offline — no Ableton needed). |
| `compare_to_reference` | Compare a mix to a reference track (offline — no Ableton needed). |
| `read_audio_metadata` | Read metadata from an audio file (offline — no Ableton needed). |

## Performance Engine (3)

| Tool | Description |
|------|-------------|
| `get_performance_safe_moves` | Get available safe moves for live performance. |
| `get_performance_state` | Get current live performance overview — scenes, energy, safe moves. |
| `plan_scene_handoff` | Plan a safe transition between two scenes. |

## Planner (2)

| Tool | Description |
|------|-------------|
| `plan_arrangement` | Transform the current loop/session into a full arrangement blueprint. |
| `transform_section` | Apply a structural transformation to the arrangement. |

## Preview Studio (5)

| Tool | Description |
|------|-------------|
| `commit_preview_variant` | Commit the chosen variant from a preview set — APPLIES the plan. |
| `compare_preview_variants` | Compare and rank variants in a preview set. |
| `create_preview_set` | Create a preview set with multiple creative options. |
| `discard_preview_set` | Discard an entire preview set and all its variants. |
| `render_preview_variant` | Render a short preview of a specific variant for evaluation. |

## Project Brain (2)

| Tool | Description |
|------|-------------|
| `build_project_brain` | Build a full Project Brain snapshot from the current Ableton session. |
| `get_project_brain_summary` | Get a lightweight Project Brain summary — track count, section count, stale status. |

## Reference Engine (3)

| Tool | Description |
|------|-------------|
| `analyze_reference_gaps` | Analyze gaps between your project and a reference. |
| `build_reference_profile` | Build a reference profile from an audio file or style/genre name. |
| `plan_reference_moves` | Plan concrete moves to close reference gaps. |

## Research (3)

| Tool | Description |
|------|-------------|
| `get_emotional_arc` | Analyze the emotional arc of the arrangement — tension, climax, resolution. |
| `get_style_tactics` | Get production tactics for a specific artist style or genre. |
| `research_technique` | Research a production technique — search device atlas + memory for answers. |

## Runtime (5)

| Tool | Description |
|------|-------------|
| `check_safety` | Validate a proposed action against safety policies before executing. |
| `get_action_ledger_summary` | Return a summary of recent semantic moves from the action ledger. |
| `get_capability_state` | Probe the runtime and return a capability state snapshot. |
| `get_last_move` | Return the most recent semantic move from the action ledger. |
| `get_session_kernel` | Build the unified turn snapshot for V2 orchestration. |

## Sample Engine (23)

| Tool | Description |
|------|-------------|
| `analyze_sample` | Analyze a sample and build a complete SampleProfile. |
| `evaluate_sample_fit` | Run the 6-critic battery to evaluate how well a sample fits the current song. |
| `get_sample_opportunities` | Analyze current song and identify where samples could improve it. |
| `get_splice_credits` | Get the user's current Splice plan, credits, and daily sample quota. |
| `plan_sample_workflow` | Full end-to-end sample workflow: analyze, critique, select technique, compile plan. |
| `plan_slice_workflow` | Plan an end-to-end slice workflow for a sample. |
| `search_samples` | Search for samples across Splice library, Ableton browser, and local filesystem. |
| `splice_add_to_collection` | Add one or more samples to a user Collection. |
| `splice_catalog_hunt` | Search Splice's ONLINE catalog via gRPC. |
| `splice_create_collection` | Create a new user Collection. Returns the new UUID on success. |
| `splice_describe_sound` | Natural-language sample search — the Sounds Plugin's "Describe a Sound". |
| `splice_download_preset` | Trigger a preset download (uses Splice.com credits, not the sample quota). |
| `splice_download_sample` | Download a Splice sample by file_hash — plan-aware gating. |
| `splice_generate_variation` | Find catalog samples similar to a given Splice sample — the "Variations" feature. |
| `splice_http_diagnose` | Diagnose the Splice HTTPS bridge configuration and readiness. |
| `splice_list_collections` | List the user's Splice Collections (Likes, custom folders, Daily Picks…). |
| `splice_list_presets` | List presets the user has purchased from Splice. |
| `splice_pack_info` | Fetch full metadata for a Splice sample pack by UUID. |
| `splice_preset_info` | Fetch metadata for a single preset (uuid, file_hash, or plugin_name). |
| `splice_preview_sample` | Fetch a Splice sample's preview audio — ZERO credits, ZERO quota cost. |
| `splice_remove_from_collection` | Remove one or more samples from a user Collection (server-side). |
| `splice_search_in_collection` | List samples inside a Splice Collection by UUID. |
| `suggest_sample_technique` | Suggest sample manipulation techniques from the technique library. |

## Scales (8)

| Tool | Description |
|------|-------------|
| `get_song_scale` | Read Live's current Scale Mode state (Live 12.0+). |
| `get_tuning_system` | Read the current Tuning System state (Live 12.1+). |
| `list_available_scales` | Return Live's built-in scale names (Live 12.0+). |
| `reset_tuning_system` | Reset all per-degree tuning offsets to 12-TET (Live 12.1+). |
| `set_song_scale` | Set the Song-level Scale Mode root + scale name (Live 12.0+, Live 12.4 compat). |
| `set_song_scale_mode` | Enable or disable Scale Mode on the current set (Live 12.0+). |
| `set_tuning_note` | Adjust the cent offset for a single scale degree (Live 12.1+). |
| `set_tuning_reference_pitch` | Set the Tuning System's reference pitch in Hz (Live 12.1+). |

## Scenes (12)

| Tool | Description |
|------|-------------|
| `create_scene` | Create a new scene. index=-1 appends at end. |
| `delete_scene` | Delete a scene by index. Use undo to revert if needed. |
| `duplicate_scene` | Duplicate a scene (copies all clip slots). |
| `fire_scene` | Fire (launch) a scene, triggering all its clips. |
| `fire_scene_clips` | Fire a scene, optionally filtering to specific tracks. |
| `get_playing_clips` | Get all currently playing or triggered clips. |
| `get_scene_matrix` | Get the full session clip grid: every track x every scene. |
| `get_scenes_info` | Get info for all scenes: name, tempo, color. |
| `set_scene_color` | Set scene color (0-69, Ableton's color palette). |
| `set_scene_name` | Rename a scene. Pass empty string to clear the name. |
| `set_scene_tempo` | Set scene tempo in BPM (20-999). Fires when the scene launches. |
| `stop_all_clips` | Stop all playing clips in the session. Panic button. |

## Semantic Moves (4)

| Tool | Description |
|------|-------------|
| `apply_semantic_move` | Compile and optionally execute a semantic move against the current session. |
| `list_semantic_moves` | List available semantic moves — high-level musical intents. |
| `preview_semantic_move` | Preview what a semantic move will do before applying it. |
| `propose_next_best_move` | Propose the best semantic moves for a natural language request, ranked |

## Session Continuity (7)

| Tool | Description |
|------|-------------|
| `explain_preference_vs_identity` | Explain how taste preference and song identity score a candidate. |
| `get_session_story` | Get the narrative of the current session. |
| `list_open_creative_threads` | List all open (non-stale) creative threads in the session. |
| `open_creative_thread` | Open a new creative thread — an unresolved creative goal. |
| `rank_by_taste_and_identity` | Rank candidates with separated taste and identity scoring. |
| `record_turn_resolution` | Record what happened in a creative turn. |
| `resume_last_intent` | Resume the most recent unresolved creative intent. |

## Song Brain (3)

| Tool | Description |
|------|-------------|
| `build_song_brain` | Build the musical identity model for the current song. |
| `detect_identity_drift` | Detect whether recent changes have damaged the song's identity. |
| `explain_song_identity` | Explain the current song's identity in human musical language. |

## Sound Design (4)

| Tool | Description |
|------|-------------|
| `analyze_sound_design` | Build full sound design state and run all critics for a track. |
| `get_patch_model` | Get the structural patch model for a track's device chain. |
| `get_sound_design_issues` | Run all sound design critics and return detected issues only. |
| `plan_sound_design_move` | Get ranked move suggestions based on current sound design issues. |

## Stuckness Detector (3)

| Tool | Description |
|------|-------------|
| `detect_stuckness` | Detect whether the session is losing momentum. |
| `start_rescue_workflow` | Start a structured rescue workflow for a specific stuckness type. |
| `suggest_momentum_rescue` | Suggest strategic moves to restore session momentum. |

## Synthesis Brain (3)

| Tool | Description |
|------|-------------|
| `analyze_synth_patch` | Extract a SynthProfile for a native synth on the given track+device. |
| `extract_timbre_fingerprint` | Build a TimbralFingerprint from analysis dicts. |
| `propose_synth_branches` | Propose branch seeds + pre-compiled plans for a native synth. |

## Take Lanes (6)

| Tool | Description |
|------|-------------|
| `create_audio_clip_on_take_lane` | Create an arrangement audio clip on a specific take lane (Live 12.2+). |
| `create_midi_clip_on_take_lane` | Create an arrangement MIDI clip on a specific take lane (Live 12.2+). |
| `create_take_lane` | Create a new take lane on a track (Live 12.2+). |
| `get_take_lane_clips` | List the arrangement clips on a specific take lane (Live 12.0+). |
| `get_take_lanes` | List all take lanes on a track (Live 12.0+). |
| `set_take_lane_name` | Rename an existing take lane (Live 12.2+). |

## Theory (7)

| Tool | Description |
|------|-------------|
| `analyze_harmony` | Analyze harmony of a MIDI clip: chords, Roman numerals, progression. |
| `detect_theory_issues` | Detect music theory issues: parallel fifths/octaves, out-of-key notes, |
| `generate_countermelody` | Generate a countermelody using species counterpoint rules. |
| `harmonize_melody` | Generate a multi-voice harmonization of a melody from a MIDI clip. |
| `identify_scale` | Identify the scale/mode of a MIDI clip beyond basic major/minor. |
| `suggest_next_chord` | Suggest the next chord based on the current progression. |
| `transpose_smart` | Transpose a MIDI clip to a new key with musical intelligence. |

## Tracks (21)

| Tool | Description |
|------|-------------|
| `create_audio_track` | Create a new audio track. index=-1 appends at end. |
| `create_midi_track` | Create a new MIDI track. index=-1 appends at end. |
| `create_return_track` | Create a new return track. |
| `delete_track` | Delete a track by index. Use undo to revert if needed. |
| `duplicate_track` | Duplicate a track (copies all clips, devices, and settings). |
| `flatten_track` | Flatten a frozen track — commit rendered audio permanently. |
| `freeze_track` | Freeze a track — render all devices to audio for CPU savings. |
| `get_appointed_device` | Return the Blue Hand (appointed/focused) device location as (track_index, device_index, track_name, device_name). |
| `get_freeze_status` | Check if a track is frozen. |
| `get_track_info` | Get detailed info about a track: clips, devices, mixer state. |
| `get_track_performance_impact` | Read a track's CPU performance impact metric. |
| `jump_in_session_clip` | Jump playhead within a running session clip, in beats from start. |
| `set_group_fold` | Fold or unfold a group track to show/hide its children. |
| `set_track_arm` | Arm or disarm a track for recording. |
| `set_track_color` | Set track color (0-69, Ableton's color palette). |
| `set_track_input_monitoring` | Set input monitoring (0=In, 1=Auto, 2=Off). Only for regular tracks, not return tracks. |
| `set_track_mute` | Mute or unmute a track. |
| `set_track_name` | Rename a track. The new name appears in both the Session and Arrangement views and survives session save. |
| `set_track_solo` | Solo or unsolo a track. |
| `stop_track_clips` | Stop all playing clips on a track. |
| `verify_device_alive` | Check whether a loaded device is alive (BUG-2026-04-22 #19). |

## Transition Engine (3)

| Tool | Description |
|------|-------------|
| `analyze_transition` | Analyze the transition boundary between two sections. |
| `plan_transition` | Plan a transition between two sections with concrete gestures. |
| `score_transition` | Score the transition quality between two sections. |

## Translation Engine (2)

| Tool | Description |
|------|-------------|
| `check_translation` | Check playback robustness — mono safety, small speakers, harshness. |
| `get_translation_issues` | Get just the translation issues without the full report. |

## Transport (21)

| Tool | Description |
|------|-------------|
| `capture_and_insert_scene` | Capture currently-playing clips and insert them as a new scene. Distinct from capture_midi. |
| `continue_playback` | Continue playback from the current position. |
| `force_link_beat_time` | Force Ableton Link to a specific beat time (if supported by this Live version). |
| `get_link_state` | Read Ableton Link + count-in state (enabled, start/stop sync, tempo follower, is_counting_in). |
| `get_recent_actions` | Get a log of recent commands sent to Ableton (newest first). Useful for reviewing what was changed. |
| `get_session_diagnostics` | Analyze the session for potential issues: armed tracks, solo/mute leftovers, unnamed tracks, empty clips/scenes, MIDI tr |
| `get_session_info` | Get comprehensive Ableton session state: tempo, tracks, scenes, transport. |
| `nudge_tempo` | Nudge tempo up or down by Live's internal nudge delta. direction: 'up' or 'down'. |
| `redo` | Redo the last undone action in Ableton. |
| `set_count_in_duration` | Set pre-record count-in duration (0-4 bars). |
| `set_exclusive_arm` | Enable/disable exclusive arm mode (only one track armed at a time). |
| `set_exclusive_solo` | Enable/disable exclusive solo mode (only one track soloed at a time). |
| `set_link_enabled` | Enable or disable Ableton Link (network tempo synchronization). |
| `set_session_loop` | Set loop on/off and optional loop region (start beat, length in beats). |
| `set_tempo` | Set the song tempo in BPM (20-999). |
| `set_time_signature` | Set the time signature (e.g., 4/4, 3/4, 6/8). |
| `start_playback` | Start playback from the beginning. |
| `stop_playback` | Stop playback — halts the session transport and the arrangement cursor returns to its last position. |
| `tap_tempo` | Tap the tempo (one tap). Live averages consecutive taps to set BPM. |
| `toggle_metronome` | Enable or disable the metronome click. |
| `undo` | Undo the last action in Ableton. |

## Wonder Mode (3)

| Tool | Description |
|------|-------------|
| `discard_wonder_session` | Reject all Wonder variants and close the session. |
| `enter_wonder_mode` | Activate Wonder Mode — stuck-rescue workflow with real diagnosis. |
| `rank_wonder_variants` | Rank wonder-mode variants by taste + identity + novelty + coherence. |

---
*Generated from 426 registered tools.*
