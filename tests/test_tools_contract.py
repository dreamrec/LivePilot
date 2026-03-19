"""Verify all 155 MCP tools are registered across 16 domains."""

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


def test_total_tool_count():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 155, f"Expected 155 tools, got {len(tools)}"


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
