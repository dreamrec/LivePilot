"""Canonical set of all valid Remote Script commands.

Every command here has a @register handler in remote_script/LivePilot/.
This is the source of truth for what can be called via
ableton.send_command(). If a command is not in this set, sending it
through TCP will return NOT_FOUND from the Remote Script.

Maintained manually — the Remote Script uses Ableton's Python and
cannot be imported in CI. Update this when adding new handlers.
"""

REMOTE_COMMANDS: frozenset[str] = frozenset({
    # transport (10)
    "get_session_info", "set_tempo", "set_time_signature",
    "start_playback", "stop_playback", "continue_playback",
    "toggle_metronome", "set_session_loop", "undo", "redo",
    # tracks (17)
    "get_track_info", "create_midi_track", "create_audio_track",
    "create_return_track", "delete_track", "duplicate_track",
    "set_track_name", "set_track_color", "set_track_mute",
    "set_track_solo", "set_track_arm", "stop_track_clips",
    "set_group_fold", "set_track_input_monitoring",
    "get_freeze_status", "freeze_track", "flatten_track",
    # clips (12)
    "get_clip_info", "create_clip", "delete_clip", "duplicate_clip",
    "fire_clip", "stop_clip", "set_clip_name", "set_clip_color",
    "set_clip_loop", "set_clip_launch", "set_clip_warp_mode",
    "set_clip_pitch",
    # notes (8)
    "add_notes", "get_notes", "remove_notes", "remove_notes_by_id",
    "modify_notes", "duplicate_notes", "transpose_notes", "quantize_clip",
    # mixing (12)
    "set_track_volume", "set_track_pan", "set_track_send",
    "get_return_tracks", "get_master_track", "set_master_volume",
    "get_track_routing", "get_track_meters", "get_master_meters",
    "get_mix_snapshot", "set_track_routing",
    "set_compressor_sidechain",  # BUG-A3 — Python LOM path (was M4L bridge)
    # scenes (12)
    "get_scenes_info", "create_scene", "delete_scene", "duplicate_scene",
    "fire_scene", "set_scene_name", "set_scene_color", "set_scene_tempo",
    "get_scene_matrix", "fire_scene_clips", "stop_all_clips",
    "get_playing_clips",
    # devices (15)
    "get_device_info", "get_device_parameters", "set_device_parameter",
    "batch_set_parameters", "toggle_device", "delete_device",
    "move_device", "load_device_by_uri", "find_and_load_device",
    "set_simpler_playback_mode", "get_rack_chains", "set_chain_volume",
    "insert_device",           # 12.3+ native device insertion
    "insert_rack_chain",       # 12.3+ rack chain insertion
    "set_drum_chain_note",     # 12.3+ drum chain note assignment
    # clip_automation (3)
    "get_clip_automation", "set_clip_automation", "clear_clip_automation",
    # browser (6)
    "get_browser_tree", "get_browser_items", "search_browser",
    "load_browser_item", "get_device_presets",
    "scan_browser_deep",       # Atlas deep scan — returns full category tree
    # arrangement (21)
    "get_arrangement_clips", "create_arrangement_clip",
    "create_native_arrangement_clip",
    "add_arrangement_notes", "get_arrangement_notes",
    "remove_arrangement_notes", "remove_arrangement_notes_by_id",
    "modify_arrangement_notes", "duplicate_arrangement_notes",
    "set_arrangement_automation", "transpose_arrangement_notes",
    "set_arrangement_clip_name", "jump_to_time",
    "capture_midi", "start_recording", "stop_recording",
    "get_cue_points", "jump_to_cue", "toggle_cue_point",
    "back_to_arranger", "force_arrangement",
    # diagnostics (1)
    "get_session_diagnostics",
    # ping (built-in)
    "ping",
})

# M4L bridge commands — routed through TCP but handled by livepilot_bridge.js
# These require the M4L Analyzer device on the master track.
BRIDGE_COMMANDS: frozenset[str] = frozenset({
    "get_params", "get_hidden_params", "get_auto_state", "walk_rack",
    "get_chains_deep", "get_track_cpu", "get_selected", "get_key",
    "get_clip_file_path", "replace_simpler_sample", "get_simpler_slices",
    "crop_simpler", "reverse_simpler", "warp_simpler",
    "get_warp_markers", "add_warp_marker", "move_warp_marker",
    "remove_warp_marker", "capture_audio", "capture_stop",
    "check_flucoma", "scrub_clip", "stop_scrub", "get_display_values",
    "get_plugin_params", "map_plugin_param", "get_plugin_presets",
    # NOTE: load_sample_to_simpler used to live here, but it's actually an
    # async Python MCP tool in mcp_server/tools/analyzer.py, not a bridge
    # command. It has no case in livepilot_bridge.js and no @register handler
    # in remote_script. See mcp_server/runtime/execution_router.MCP_TOOLS.
})

# Combined: all valid send_command targets
ALL_VALID_COMMANDS: frozenset[str] = REMOTE_COMMANDS | BRIDGE_COMMANDS
