"""Verify all 236 MCP tools are registered across 32 domains."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _get_tool_names():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


def test_transport_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_session_info",
        "set_tempo",
        "set_time_signature",
        "start_playback",
        "stop_playback",
        "continue_playback",
        "toggle_metronome",
        "set_session_loop",
        "undo",
        "redo",
        "get_recent_actions",
        "get_session_diagnostics",
    }
    missing = expected - names
    assert not missing, f"Missing transport tools: {missing}"


def test_tracks_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_track_info",
        "create_midi_track",
        "create_audio_track",
        "create_return_track",
        "delete_track",
        "duplicate_track",
        "set_track_name",
        "set_track_color",
        "set_track_mute",
        "set_track_solo",
        "set_track_arm",
        "stop_track_clips",
        "set_group_fold",
        "set_track_input_monitoring",
        # Freeze/flatten
        "freeze_track",
        "flatten_track",
        "get_freeze_status",
    }
    missing = expected - names
    assert not missing, f"Missing tracks tools: {missing}"


def test_clips_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_clip_info",
        "create_clip",
        "delete_clip",
        "duplicate_clip",
        "fire_clip",
        "stop_clip",
        "set_clip_name",
        "set_clip_color",
        "set_clip_loop",
        "set_clip_launch",
        "set_clip_warp_mode",
    }
    missing = expected - names
    assert not missing, f"Missing clips tools: {missing}"


def test_notes_tools_registered():
    names = _get_tool_names()
    expected = {
        "add_notes",
        "get_notes",
        "remove_notes",
        "remove_notes_by_id",
        "modify_notes",
        "duplicate_notes",
        "transpose_notes",
        "quantize_clip",
    }
    missing = expected - names
    assert not missing, f"Missing notes tools: {missing}"


def test_devices_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_device_info",
        "get_device_parameters",
        "set_device_parameter",
        "batch_set_parameters",
        "toggle_device",
        "delete_device",
        "load_device_by_uri",
        "find_and_load_device",
        "set_simpler_playback_mode",
        "get_rack_chains",
        "set_chain_volume",
        "get_device_presets",
        # Plugin deep control (M4L)
        "get_plugin_parameters",
        "map_plugin_parameter",
        "get_plugin_presets",
    }
    missing = expected - names
    assert not missing, f"Missing devices tools: {missing}"


def test_scenes_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_scenes_info",
        "create_scene",
        "delete_scene",
        "duplicate_scene",
        "fire_scene",
        "set_scene_name",
        "set_scene_color",
        "set_scene_tempo",
        # Scene matrix operations
        "get_scene_matrix",
        "fire_scene_clips",
        "stop_all_clips",
        "get_playing_clips",
    }
    missing = expected - names
    assert not missing, f"Missing scenes tools: {missing}"


def test_mixing_tools_registered():
    names = _get_tool_names()
    expected = {
        "set_track_volume",
        "set_track_pan",
        "set_track_send",
        "get_return_tracks",
        "get_master_track",
        "set_master_volume",
        "get_track_routing",
        "set_track_routing",
        "get_track_meters",
        "get_master_meters",
        "get_mix_snapshot",
    }
    missing = expected - names
    assert not missing, f"Missing mixing tools: {missing}"


def test_browser_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_browser_tree",
        "get_browser_items",
        "search_browser",
        "load_browser_item",
    }
    missing = expected - names
    assert not missing, f"Missing browser tools: {missing}"


def test_arrangement_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_arrangement_clips",
        "create_arrangement_clip",
        "add_arrangement_notes",
        "get_arrangement_notes",
        "remove_arrangement_notes",
        "remove_arrangement_notes_by_id",
        "modify_arrangement_notes",
        "duplicate_arrangement_notes",
        "transpose_arrangement_notes",
        "set_arrangement_clip_name",
        "set_arrangement_automation",
        "back_to_arranger",
        "jump_to_time",
        "capture_midi",
        "start_recording",
        "stop_recording",
        "get_cue_points",
        "jump_to_cue",
        "toggle_cue_point",
    }
    missing = expected - names
    assert not missing, f"Missing arrangement tools: {missing}"


def test_memory_tools_registered():
    names = _get_tool_names()
    expected = {
        "memory_learn",
        "memory_recall",
        "memory_get",
        "memory_replay",
        "memory_list",
        "memory_favorite",
        "memory_update",
        "memory_delete",
    }
    missing = expected - names
    assert not missing, f"Missing memory tools: {missing}"


def test_analyzer_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_master_spectrum",
        "get_master_rms",
        "get_detected_key",
        "get_hidden_parameters",
        "get_automation_state",
        "walk_device_tree",
        # Phase 2: Sample Operations
        "get_clip_file_path",
        "replace_simpler_sample",
        "get_simpler_slices",
        "crop_simpler",
        "reverse_simpler",
        "warp_simpler",
        # Phase 2: Warp Markers
        "get_warp_markers",
        "add_warp_marker",
        "move_warp_marker",
        "remove_warp_marker",
        # Phase 2: Clip & Display
        "scrub_clip",
        "stop_scrub",
        "get_display_values",
        # Phase 3: Capture
        "capture_audio",
        "capture_stop",
        # Phase 4: FluCoMa Real-Time
        "get_spectral_shape",
        "get_mel_spectrum",
        "get_chroma",
        "get_onsets",
        "get_novelty",
        "get_momentary_loudness",
        "check_flucoma",
        "load_sample_to_simpler",
    }
    missing = expected - names
    assert not missing, f"Missing analyzer tools: {missing}"


def test_automation_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_clip_automation",
        "set_clip_automation",
        "clear_clip_automation",
        "apply_automation_shape",
        "apply_automation_recipe",
        "get_automation_recipes",
        "generate_automation_curve",
        "analyze_for_automation",
    }
    missing = expected - names
    assert not missing, f"Missing automation tools: {missing}"


def test_theory_tools_registered():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    expected = {
        'analyze_harmony', 'suggest_next_chord', 'detect_theory_issues',
        'identify_scale', 'harmonize_melody', 'generate_countermelody',
        'transpose_smart',
    }
    missing = expected - names
    assert not missing, f"Missing theory tools: {missing}"


def test_agent_os_tools_registered():
    names = _get_tool_names()
    expected = {
        "compile_goal_vector",
        "build_world_model",
        "evaluate_move",
        "analyze_outcomes",
        "get_technique_card",
    }
    missing = expected - names
    assert not missing, f"Missing agent_os tools: {missing}"


def test_composition_tools_registered():
    names = _get_tool_names()
    expected = {
        "analyze_composition",
        "get_section_graph",
        "get_phrase_grid",
        "plan_gesture",
        "evaluate_composition_move",
        "get_harmony_field",
        "get_transition_analysis",
        "apply_gesture_template",
        "get_section_outcomes",
    }
    missing = expected - names
    assert not missing, f"Missing composition tools: {missing}"


def test_motif_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_motif_graph",
        "transform_motif",
    }
    missing = expected - names
    assert not missing, f"Missing motif tools: {missing}"


def test_research_tools_registered():
    names = _get_tool_names()
    expected = {
        "research_technique",
        "get_emotional_arc",
        "get_style_tactics",
    }
    missing = expected - names
    assert not missing, f"Missing research tools: {missing}"


def test_planner_tools_registered():
    names = _get_tool_names()
    expected = {
        "plan_arrangement",
        "transform_section",
    }
    missing = expected - names
    assert not missing, f"Missing planner tools: {missing}"


def test_project_brain_tools_registered():
    names = _get_tool_names()
    expected = {
        "build_project_brain",
        "get_project_brain_summary",
    }
    missing = expected - names
    assert not missing, f"Missing project_brain tools: {missing}"


def test_capability_state_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_capability_state",
    }
    missing = expected - names
    assert not missing, f"Missing capability_state tools: {missing}"


def test_action_ledger_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_action_ledger_summary",
        "get_last_move",
    }
    missing = expected - names
    assert not missing, f"Missing action_ledger tools: {missing}"


def test_agent_os_taste_tool_registered():
    names = _get_tool_names()
    assert "get_taste_profile" in names, "Missing get_taste_profile tool"


def test_evaluation_fabric_tools_registered():
    names = _get_tool_names()
    assert "evaluate_with_fabric" in names, "Missing evaluate_with_fabric tool"


def test_memory_fabric_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_anti_preferences",
        "record_anti_preference",
        "get_promotion_candidates",
    }
    missing = expected - names
    assert not missing, f"Missing memory_fabric tools: {missing}"


def test_mix_engine_tools_registered():
    names = _get_tool_names()
    expected = {
        "analyze_mix",
        "get_mix_issues",
        "plan_mix_move",
        "evaluate_mix_move",
        "get_masking_report",
        "get_mix_summary",
    }
    missing = expected - names
    assert not missing, f"Missing mix_engine tools: {missing}"


def test_sound_design_tools_registered():
    names = _get_tool_names()
    expected = {
        "analyze_sound_design",
        "get_sound_design_issues",
        "plan_sound_design_move",
        "get_patch_model",
    }
    missing = expected - names
    assert not missing, f"Missing sound_design tools: {missing}"


def test_transition_engine_tools_registered():
    names = _get_tool_names()
    expected = {
        "analyze_transition",
        "plan_transition",
        "score_transition",
    }
    missing = expected - names
    assert not missing, f"Missing transition_engine tools: {missing}"


def test_reference_engine_tools_registered():
    names = _get_tool_names()
    expected = {
        "build_reference_profile",
        "analyze_reference_gaps",
        "plan_reference_moves",
    }
    missing = expected - names
    assert not missing, f"Missing reference_engine tools: {missing}"


def test_translation_engine_tools_registered():
    names = _get_tool_names()
    expected = {
        "check_translation",
        "get_translation_issues",
    }
    missing = expected - names
    assert not missing, f"Missing translation_engine tools: {missing}"


def test_performance_engine_tools_registered():
    names = _get_tool_names()
    expected = {
        "get_performance_state",
        "get_performance_safe_moves",
        "plan_scene_handoff",
    }
    missing = expected - names
    assert not missing, f"Missing performance_engine tools: {missing}"


def test_safety_tools_registered():
    names = _get_tool_names()
    expected = {
        "check_safety",
    }
    missing = expected - names
    assert not missing, f"Missing safety tools: {missing}"


def test_total_tool_count():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 236, f"Expected 236 tools, got {len(tools)}"


def test_perception_tools_registered():
    names = _get_tool_names()
    expected = {
        "analyze_loudness",
        "analyze_spectrum_offline",
        "compare_to_reference",
        "read_audio_metadata",
    }
    missing = expected - names
    assert not missing, f"Missing perception tools: {missing}"


def test_generative_tools_registered():
    names = _get_tool_names()
    expected = {
        "generate_euclidean_rhythm",
        "layer_euclidean_rhythms",
        "generate_tintinnabuli",
        "generate_phase_shift",
        "generate_additive_process",
    }
    missing = expected - names
    assert not missing, f"Missing generative tools: {missing}"


def test_harmony_tools_registered():
    names = _get_tool_names()
    expected = {
        "navigate_tonnetz",
        "find_voice_leading_path",
        "classify_progression",
        "suggest_chromatic_mediants",
    }
    missing = expected - names
    assert not missing, f"Missing harmony tools: {missing}"


def test_midi_io_tools_registered():
    names = _get_tool_names()
    expected = {
        "export_clip_midi",
        "import_midi_to_clip",
        "analyze_midi_file",
        "extract_piano_roll",
    }
    missing = expected - names
    assert not missing, f"Missing MIDI I/O tools: {missing}"
