"""Verify all 76 MCP tools are registered across 9 domains."""

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
        "get_rack_chains",
        "set_chain_volume",
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


def test_total_tool_count():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 76, f"Expected 76 tools, got {len(tools)}"
