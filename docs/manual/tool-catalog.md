# LivePilot — Full Tool Catalog

402 tools across 52 domains.

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

## Clips (13)

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
| `set_clip_pitch` | Transpose an audio clip (semitones/cents) + gain |
| `check_clip_key_consistency` | Cross-check a clip's filename-encoded key against the detected session key (Splice-style `_D#min.wav` tokens); returns the exact `set_clip_pitch` call to realign on mismatch (BUG-D1) |

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

## Devices (15)

| Tool | Description |
|------|-------------|
| `get_device_info` | Device name, class, parameters |
| `get_device_parameters` | All params with names, values, ranges (+ display_value on 12.2+) |
| `set_device_parameter` | Set param by name or index |
| `batch_set_parameters` | Set multiple params in one call |
| `toggle_device` | Enable/disable |
| `delete_device` | Remove from chain |
| `move_device` | Reorder device on track or move between tracks |
| `load_device_by_uri` | Load by browser URI |
| `find_and_load_device` | Search and load by name (uses insert_device fast path on 12.3+) |
| `insert_device` | Insert native device by name — 10x faster (12.3+), supports chain insertion |
| `insert_rack_chain` | Add chain to Instrument/Audio Effect/Drum Rack (12.3+) |
| `set_drum_chain_note` | Assign MIDI note to Drum Rack chain (12.3+) |
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

## Arrangement (20)

| Tool | Description |
|------|-------------|
| `get_arrangement_clips` | List arrangement clips |
| `create_arrangement_clip` | New clip at timeline position (duplicates session clip) |
| `create_native_arrangement_clip` | Native arrangement clip with automation envelope support (12.1.10+) |
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
| `force_arrangement` | Force ALL tracks to follow arrangement — stops session clips, releases overrides, starts playback |
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

## Analyzer (32) `[M4L]`

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
| `get_simpler_slices` | Slice point positions (includes `base_midi_pitch` + per-slice `midi_pitch`) |
| `classify_simpler_slices` | Classify each slice as KICK / SNARE / HAT / ghost via FFT |
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
| `simpler_set_warp` | Toggle Simpler sample warping + warp_mode (BUG-A2) |
| `compressor_set_sidechain` | Set Compressor sidechain input routing (BUG-A3) |

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

---

## Device Forge (3)

| Tool | Description |
|------|-------------|
| `generate_m4l_effect` | Generate a custom M4L audio effect from gen~ templates |
| `install_m4l_device` | Install generated M4L device to User Library |
| `list_genexpr_templates` | List available gen~ expression templates |

---

## Device Atlas (7)

| Tool | Description |
|------|-------------|
| `atlas_search` | Search the device atlas — name, sonic character, use case, or genre |
| `atlas_device_info` | Full atlas knowledge about a device — parameters, recipes, pairings |
| `atlas_suggest` | Suggest devices for a production intent with rationale and recipe |
| `atlas_chain_suggest` | Suggest a full device chain for a track role and genre |
| `atlas_compare` | Compare two devices — strengths, weaknesses, recommendation |
| `scan_full_library` | Scan Ableton browser and rebuild the device atlas |
| `reload_atlas` | Force re-read of device_atlas.json from disk (post-rebuild refresh) |

---

## Sample Engine (10)

| Tool | Description |
|------|-------------|
| `analyze_sample` | Analyze sample characteristics — material, spectral profile, Simpler mode recommendation |
| `evaluate_sample_fit` | 6-critic fitness battery — key, tempo, frequency, role, vibe, intent fit scores |
| `search_samples` | Search library for samples matching criteria (prefers Splice online catalog via gRPC when connected) |
| `suggest_sample_technique` | Suggest manipulation technique from the 29-technique library |
| `plan_sample_workflow` | Plan multi-step sample manipulation workflow |
| `get_sample_opportunities` | Find opportunities to add samples to the current session |
| `plan_slice_workflow` | Plan an end-to-end slice workflow — Simpler strategy, MIDI mapping, starter pattern |
| `get_splice_credits` | Query Splice subscription tier, credit balance, and download capability (v1.10.5) |
| `splice_catalog_hunt` | Search Splice's ONLINE catalog via gRPC — 19,690+ hits unblocked in v1.10.5 |
| `splice_download_sample` | Download a Splice sample by file_hash with credit-floor safety, copy into User Library (v1.10.5) |

---

## Composer (4)

| Tool | Description |
|------|-------------|
| `compose` | Create a full multi-layer composition from a text prompt — searches samples, loads devices, arranges sections |
| `augment_with_samples` | Add sample-based layers to the existing session with Splice-aware credit safety |
| `get_composition_plan` | Dry-run preview of what compose would do — no execution, no credits spent |
| `propose_composer_branches` | Emit N distinct compositional hypotheses (canonical / energy_shift / layer_contrast) for exploratory workflows — feeds create_experiment(seeds=...); winner commit rehydrates intent and runs full compose() |

---

## Synthesis Brain (3)

| Tool | Description |
|------|-------------|
| `analyze_synth_patch` | Extract a SynthProfile from a native synth (Wavetable / Operator / Analog / Drift / Meld) — parameter state, display values, modulation graph, articulation, role hint |
| `propose_synth_branches` | Emit algorithm/topology-aware branch seeds + pre-compiled plans for a native synth; strategy selection responds to profile + role_hint + target TimbralFingerprint |
| `extract_timbre_fingerprint` | Build a 9-dimension TimbralFingerprint (brightness, warmth, bite, softness, instability, width, texture_density, movement, polish) from spectrum / loudness / spectral_shape dicts — pure transform |

---

## Scales (8) — Song-level Scale Mode + microtonal tuning (Live 12.0+ / 12.1+)

| Tool | Description |
|------|-------------|
| `get_song_scale` | Read Live's current Scale Mode state (Live 12.0+) |
| `set_song_scale` | Set the Song-level Scale Mode root + scale name (Live 12.0+) |
| `set_song_scale_mode` | Enable or disable Scale Mode on the current set (Live 12.0+) |
| `list_available_scales` | Return Live's built-in scale names (Live 12.0+) |
| `get_tuning_system` | Read the current Tuning System state (Live 12.1+) |
| `set_tuning_reference_pitch` | Set the Tuning System's reference pitch in Hz (Live 12.1+) |
| `set_tuning_note` | Adjust the cent offset for a single scale degree (Live 12.1+) |
| `reset_tuning_system` | Reset all per-degree tuning offsets to 12-TET (Live 12.1+) |

---

## Clips — Scale overrides (3, Live 12.0+)

| Tool | Description |
|------|-------------|
| `get_clip_scale` | Read a clip's per-clip scale override (Live 12.0+) |
| `set_clip_scale` | Set a clip's per-clip scale override (Live 12.0+) |
| `set_clip_scale_mode` | Enable or disable Scale Mode on a single clip (Live 12.0+) |

---

## Follow Actions (8) — Clip 12.0 revamp + scene 12.2+

| Tool | Description |
|------|-------------|
| `get_clip_follow_action` | Read a clip's follow-action state (Live 12.0+) |
| `set_clip_follow_action` | Set a clip's follow action (Live 12.0+). Any omitted arg preserves |
| `clear_clip_follow_action` | Disable follow action on a clip (Live 12.0+) |
| `apply_follow_action_preset` | Apply a named follow-action preset to a clip (Live 12.0+) |
| `list_follow_action_types` | List valid follow-action names (Live 12.0+) |
| `get_scene_follow_action` | Read a scene's follow-action state (Live 12.2+) |
| `set_scene_follow_action` | Set a scene's follow action (Live 12.2+). Any omitted arg preserves |
| `clear_scene_follow_action` | Disable a scene's follow action (Live 12.2+) |

---

## Grooves (7) — Groove Pool + master dial (Live 11+)

| Tool | Description |
|------|-------------|
| `list_grooves` | List all grooves in the Groove Pool (Live 11+) |
| `get_groove_info` | Read a single groove's parameters (Live 11+) |
| `set_groove_params` | Adjust a groove's parameters (Live 11+). Omitted args preserve |
| `assign_clip_groove` | Assign a groove to a clip (Live 11+) |
| `get_clip_groove` | Read a clip's current groove assignment (Live 11+) |
| `get_song_groove_amount` | Read the master groove amount dial (Live 11+) |
| `set_song_groove_amount` | Set the master groove amount dial (Live 11+) |

---

## Take Lanes (6) — Live 12.0 read / 12.2 write

| Tool | Description |
|------|-------------|
| `get_take_lanes` | List all take lanes on a track (Live 12.0+) |
| `get_take_lane_clips` | List the arrangement clips on a specific take lane (Live 12.0+) |
| `create_take_lane` | Create a new take lane on a track (Live 12.2+) |
| `set_take_lane_name` | Rename an existing take lane (Live 12.2+) |
| `create_midi_clip_on_take_lane` | Create an arrangement MIDI clip on a specific take lane (Live 12.2+) |
| `create_audio_clip_on_take_lane` | Create an arrangement audio clip on a specific take lane (Live 12.2+) |

---

## Devices — Rack Variations + Macro CRUD (8, Live 11+)

| Tool | Description |
|------|-------------|
| `get_rack_variations` | Get the Rack's variation count, currently selected variation index, and visible macro count (Live 11+) |
| `store_rack_variation` | Store the Rack's current macro values as a new variation (Live 11+) |
| `recall_rack_variation` | Select and recall a stored Rack variation by index (Live 11+) |
| `delete_rack_variation` | Delete a Rack variation by index (Live 11+) |
| `add_rack_macro` | Add one macro to a Rack, raising visible_macro_count by 1 (Live 11+) |
| `remove_rack_macro` | Remove the last macro from a Rack, lowering visible_macro_count by 1 (Live 11+) |
| `set_rack_visible_macros` | Set the Rack's visible_macro_count directly (1-16, Live 11+) |
| `randomize_rack_macros` | Randomize the Rack's macro values using Live's built-in randomize dice (Live 11+) |

---

## Devices — Simpler Slice CRUD (6, Live 11+)

| Tool | Description |
|------|-------------|
| `insert_simpler_slice` | Insert a slice at a sample-frame position on a Simpler (Live 11+) |
| `move_simpler_slice` | Move an existing slice from one sample-frame position to another (Live 11+) |
| `remove_simpler_slice` | Remove a slice at an exact sample-frame position (Live 11+) |
| `clear_simpler_slices` | Remove all manual slices from the Simpler (Live 11+) |
| `reset_simpler_slices` | Reset the Simpler's slices to Live's default detection (Live 11+) |
| `import_slices_from_onsets` | Force Transient slicing mode, set sensitivity, and re-detect (Live 11+) |

---

## Devices — Wavetable Modulation Matrix (5, Live 11+)

| Tool | Description |
|------|-------------|
| `get_wavetable_mod_targets` | Enumerate visible modulation target parameter names on a Wavetable (Live 11+) |
| `get_wavetable_mod_matrix` | Dump all non-zero modulation routings on a Wavetable device (Live 11+) |
| `get_wavetable_mod_amount` | Read the current modulation amount for a Wavetable source→target routing (Live 11+) |
| `set_wavetable_mod_amount` | Set the modulation amount for a Wavetable source→target routing (Live 11+) |
| `add_wavetable_mod_route` | Create a modulation routing on a Wavetable device (Live 11+) |

---

## Devices — A/B Compare (3, Live 12.3+)

| Tool | Description |
|------|-------------|
| `get_device_ab_state` | Read a device's A/B compare state (Live 12.3+) |
| `toggle_device_ab` | Swap a device's A/B state (Live 12.3+) |
| `copy_device_state` | Copy one A/B state to the other (Live 12.3+) |

---

## Transport — Long-tail primitives (9)

| Tool | Description |
|------|-------------|
| `tap_tempo` | Tap the tempo (one tap). Live averages consecutive taps to set BPM |
| `nudge_tempo` | Nudge tempo up or down by Live's internal nudge delta. direction: 'up' or 'down' |
| `capture_and_insert_scene` | Capture currently-playing clips and insert them as a new scene. Distinct from capture_midi |
| `set_count_in_duration` | Set pre-record count-in duration (0-4 bars) |
| `set_exclusive_arm` | Enable/disable exclusive arm mode (only one track armed at a time) |
| `set_exclusive_solo` | Enable/disable exclusive solo mode (only one track soloed at a time) |
| `get_link_state` | Read Ableton Link + count-in state (enabled, start/stop sync, tempo follower, is_counting_in) |
| `set_link_enabled` | Enable or disable Ableton Link (network tempo synchronization) |
| `force_link_beat_time` | Force Ableton Link to a specific beat time (if supported by this Live version) |

---

## Tracks — Long-tail primitives (3)

| Tool | Description |
|------|-------------|
| `jump_in_session_clip` | Jump playhead within a running session clip, in beats from start |
| `get_track_performance_impact` | Read a track's CPU performance impact metric |
| `get_appointed_device` | Return the Blue Hand (appointed/focused) device location as (track_index, device_index, track_name, device_name) |

---

## Diagnostics (2) — ControlSurface enumeration

| Tool | Description |
|------|-------------|
| `list_control_surfaces` | List all active ControlSurface instances (Push, APC, Launchkey, etc.) |
| `get_control_surface_info` | Read detailed info about a single control surface |

---

## MIDI Tool bridge (4, Live 12.0+ MIDI Generators / Transformations)

Requires `LivePilot_MIDITool.amxd` (see `m4l_device/MIDITOOL_BUILD_GUIDE.md`).

| Tool | Description |
|------|-------------|
| `install_miditool_device` | Copy LivePilot_MIDITool.amxd into Ableton's User Library (macOS) |
| `set_miditool_target` | Configure which LivePilot generator runs on MIDI Tool requests |
| `get_miditool_context` | Read the last context (grid/selection/scale/seed/tuning) received from the bridge |
| `list_miditool_generators` | Enumerate registered generators: euclidean_rhythm, tintinnabuli, humanize |
