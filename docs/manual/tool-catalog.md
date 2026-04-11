# LivePilot — Full Tool Catalog

292 tools across 39 domains.

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
| `move_device` | Reorder device on track or move between tracks |
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

## Analyzer (30) `[M4L]`

| Tool | Description |
|------|-------------|
| `get_master_spectrum` | 8-band frequency analysis |
| `get_master_rms` | RMS and peak levels |
| `get_detected_key` | Krumhansl-Schmuckler key detection |
| `reconnect_bridge` | Rebind M4L UDP bridge mid-session |
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

## Agent OS (8)

| Tool | Description |
|------|-------------|
| `compile_goal_vector` | Compile a user request into a validated GoalVector |
| `build_world_model` | Build a WorldModel snapshot of the current Ableton session |
| `evaluate_move` | Evaluate whether a production move improved the mix toward the goal |
| `analyze_outcomes` | Analyze accumulated outcome memories to identify user taste patterns |
| `get_technique_card` | Search for technique cards — structured production recipes |
| `get_taste_profile` | Get the user's production taste profile from outcome history |
| `get_turn_budget` | Get a resource budget for the current agent turn |
| `route_request` | Route a production request to the right engine(s) |

## Composition (9)

| Tool | Description |
|------|-------------|
| `analyze_composition` | Run full composition analysis on the current session |
| `get_section_graph` | Lightweight structural overview — sections and boundaries |
| `get_phrase_grid` | Get phrase boundaries for a specific section |
| `plan_gesture` | Map abstract intent to concrete automation gestures |
| `evaluate_composition_move` | Evaluate whether a composition move improved the arrangement |
| `get_harmony_field` | Analyze harmonic content — key, chords, voice-leading, tension |
| `get_transition_analysis` | Analyze transition quality between adjacent sections |
| `apply_gesture_template` | Apply a compound gesture template — coordinated automation |
| `get_section_outcomes` | Composition move success rates grouped by section type |

## Motif (2)

| Tool | Description |
|------|-------------|
| `get_motif_graph` | Detect recurring melodic and rhythmic patterns across all tracks |
| `transform_motif` | Transform a motif using classical composition techniques |

## Research (3)

| Tool | Description |
|------|-------------|
| `research_technique` | Research a production technique — search device atlas + memory |
| `get_emotional_arc` | Analyze the emotional arc of the arrangement |
| `get_style_tactics` | Get production tactics for a specific artist style or genre |

## Planner (2)

| Tool | Description |
|------|-------------|
| `plan_arrangement` | Transform the current loop/session into an arrangement blueprint |
| `transform_section` | Apply a structural transformation to the arrangement |

## Project Brain (2)

| Tool | Description |
|------|-------------|
| `build_project_brain` | Build a full Project Brain snapshot from the current session |
| `get_project_brain_summary` | Lightweight Project Brain summary — track count, sections, stale stats |

## Runtime (4)

| Tool | Description |
|------|-------------|
| `get_capability_state` | Probe the runtime and return a capability state snapshot |
| `get_action_ledger_summary` | Summary of recent semantic moves from the action ledger |
| `get_last_move` | Most recent semantic move from the action ledger |
| `check_safety` | Validate a proposed action against safety policies |

## Evaluation (1)

| Tool | Description |
|------|-------------|
| `evaluate_with_fabric` | Evaluate a move using the unified Evaluation Fabric |

## Memory Fabric (6)

| Tool | Description |
|------|-------------|
| `get_anti_preferences` | Return all recorded anti-preferences |
| `record_anti_preference` | Record a user dislike for a dimension+direction |
| `get_promotion_candidates` | Check session ledger for entries eligible for memory promotion |
| `get_session_memory` | Return recent session memory entries |
| `add_session_memory` | Add an ephemeral session memory entry |
| `get_taste_dimensions` | Return all taste dimensions — preferences inferred from outcomes |

## Mix Engine (6)

| Tool | Description |
|------|-------------|
| `analyze_mix` | Build full mix state and run all critics |
| `get_mix_issues` | Run all mix critics and return detected issues only |
| `plan_mix_move` | Get ranked move suggestions based on current mix issues |
| `evaluate_mix_move` | Score a mix change using the evaluation fabric |
| `get_masking_report` | Get detailed frequency collision report |
| `get_mix_summary` | Lightweight mix overview — track count, issue count, dynamics |

## Sound Design (4)

| Tool | Description |
|------|-------------|
| `analyze_sound_design` | Build full sound design state and run all critics for a track |
| `get_sound_design_issues` | Run all sound design critics and return detected issues |
| `plan_sound_design_move` | Get ranked move suggestions for sound design issues |
| `get_patch_model` | Get the structural patch model for a track's device chain |

## Transition Engine (3)

| Tool | Description |
|------|-------------|
| `analyze_transition` | Analyze the transition boundary between two sections |
| `plan_transition` | Plan a transition with concrete gestures |
| `score_transition` | Score the transition quality between two sections |

## Reference Engine (4)

| Tool | Description |
|------|-------------|
| `build_reference_profile` | Build a reference profile from audio file or style/genre name |
| `analyze_reference_gaps` | Analyze gaps between your project and a reference |
| `plan_reference_moves` | Plan concrete moves to close reference gaps |
| `build_session_reference` | Build a self-reference from current session identity |

## Translation Engine (2)

| Tool | Description |
|------|-------------|
| `check_translation` | Check playback robustness — mono safety, small speakers, harshness |
| `get_translation_issues` | Get just the translation issues without the full report |

## Performance Engine (3)

| Tool | Description |
|------|-------------|
| `get_performance_state` | Current live performance overview — scenes, energy, safe moves |
| `get_performance_safe_moves` | Available safe moves for live performance |
| `plan_scene_handoff` | Plan a safe transition between two scenes |

## Runtime (2)

| Tool | Description |
|------|-------------|
| `get_capability_state` | Probe runtime capabilities — analyzer, memory, session |
| `get_session_kernel` | Build unified V2 turn snapshot — session + capabilities + memory + taste |

## Semantic Moves (4)

| Tool | Description |
|------|-------------|
| `list_semantic_moves` | Discover available high-level musical intents by domain |
| `preview_semantic_move` | See what a move will do before applying — full compile plan |
| `propose_next_best_move` | AI-ranked suggestions for a natural language request |
| `apply_semantic_move` | Compile and execute a move against current session state |

## Experiments (7)

| Tool | Description |
|------|-------------|
| `create_experiment` | Set up branches from semantic moves for comparison |
| `run_experiment` | Trial each branch (apply → capture → undo) |
| `compare_experiments` | Rank branches by evaluation score |
| `commit_experiment` | Re-apply the winning branch permanently |
| `discard_experiment` | Throw away all branches |
| `render_branch_preview` | Capture audio preview of a branch's changes |
| `compare_branch_previews` | Compare rendered branch previews by phrase quality |

## Taste Graph (4)

| Tool | Description |
|------|-------------|
| `get_taste_graph` | Full taste model — dimensions, move families, device affinities |
| `explain_taste_inference` | Human-readable explanation of inferred preferences |
| `rank_moves_by_taste` | Rank semantic moves by personalized taste fit |
| `record_positive_preference` | Record that user prefers more/less of a dimension |

## Musical Intelligence (10)

| Tool | Description |
|------|-------------|
| `detect_repetition_fatigue` | Is the arrangement getting stale? |
| `detect_role_conflicts` | Are tracks fighting for the same musical role? |
| `infer_section_purposes` | What is each section trying to do musically? |
| `score_emotional_arc` | Does the song have a satisfying tension/release arc? |
| `detect_motif_salience` | Which motifs are prominent vs overused? |
| `detect_call_response_patterns` | Find alternating track dialogues |
| `analyze_phrase_arc` | Evaluate a captured audio phrase for musical quality |
| `compare_phrase_renders` | Compare multiple captures and rank by quality |
| `render_phrase_snapshot` | Capture a bounded musical phrase for evaluation |
| `score_phrase_payoff` | Score how well a phrase delivers on its promise |

---

## Song Brain (3)

| Tool | Description |
|------|-------------|
| `build_song_brain` | Build the musical identity model for the current song |
| `explain_song_identity` | Human-readable summary of the song's identity |
| `detect_identity_drift` | Detect whether recent changes damaged the song's identity |

---

## Preview Studio (5)

| Tool | Description |
|------|-------------|
| `create_preview_set` | Generate safe/strong/unexpected creative variants |
| `render_preview_variant` | Render a short preview of a variant for evaluation |
| `compare_preview_variants` | Rank variants by taste + identity + impact |
| `commit_preview_variant` | Apply the chosen variant |
| `discard_preview_set` | Throw away all variants |

---

## Hook Hunter (9)

| Tool | Description |
|------|-------------|
| `find_primary_hook` | Detect the most salient hook in the session |
| `rank_hook_candidates` | List and rank all hook candidates |
| `develop_hook` | Suggest development strategies for a hook |
| `measure_hook_salience` | Score a specific hook's salience |
| `score_phrase_impact` | Score a section's emotional impact |
| `detect_payoff_failure` | Find where the song should deliver but doesn't |
| `suggest_payoff_repair` | Generate repair strategies for payoff failures |
| `detect_hook_neglect` | Check if a strong hook is underused across sections |
| `compare_phrase_impact` | Compare emotional impact across multiple sections |

---

## Stuckness Detector (3)

| Tool | Description |
|------|-------------|
| `detect_stuckness` | Identify whether the session is losing momentum |
| `suggest_momentum_rescue` | Get strategic rescue suggestions |
| `start_rescue_workflow` | Start a structured rescue plan for a specific stuckness type |

---

## Wonder Mode (2)

| Tool | Description |
|------|-------------|
| `enter_wonder_mode` | Full pipeline: discover moves, build variants, rank by taste + identity + novelty + coherence |
| `rank_wonder_variants` | Standalone re-ranker for any variant list with score breakdowns |
| `discard_wonder_session` | Reject all Wonder variants, keep creative thread open |

---

## Session Continuity (7)

| Tool | Description |
|------|-------------|
| `get_session_story` | Narrative of the session — identity, turns, open threads |
| `resume_last_intent` | Pick up the most recent unresolved creative intent |
| `record_turn_resolution` | Log what happened in a creative turn |
| `rank_by_taste_and_identity` | Rank candidates with separated taste/identity scoring |
| `open_creative_thread` | Open a new creative thread — track unresolved goals |
| `list_open_creative_threads` | List all open non-stale creative threads |
| `explain_preference_vs_identity` | Explain taste vs identity tension for a candidate |

---

## Creative Constraints (5)

| Tool | Description |
|------|-------------|
| `apply_creative_constraint_set` | Activate creative constraints for focused suggestions |
| `distill_reference_principles` | Learn musical principles from a reference |
| `map_reference_principles_to_song` | Translate reference principles to current song |
| `generate_constrained_variants` | Generate triptych variants under active constraints |
| `generate_reference_inspired_variants` | Generate variants inspired by distilled reference principles |
