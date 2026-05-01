"""Verifies develop-mode MCP tool registration."""

import pytest
from unittest.mock import MagicMock


def test_analyze_loop_for_extension_is_registered():
    """The new tool must be importable from composer.tools."""
    from mcp_server.composer import tools
    assert hasattr(tools, "analyze_loop_for_extension"), (
        "analyze_loop_for_extension not registered as @mcp.tool"
    )


def test_develop_apply_is_registered():
    from mcp_server.composer import tools
    assert hasattr(tools, "develop_apply"), (
        "develop_apply not registered as @mcp.tool"
    )


def test_compose_accepts_develop_mode():
    """compose() must accept mode='develop' without raising."""
    import inspect
    from mcp_server.composer import tools
    sig = inspect.signature(tools.compose)
    # mode parameter should still exist
    assert "mode" in sig.parameters
    # New seed_scene_index parameter for develop mode
    assert "seed_scene_index" in sig.parameters or "scene_index" in sig.parameters


@pytest.mark.asyncio
async def test_compose_develop_mode_returns_brief():
    """compose(mode='develop') should call introspect_seed + build_develop_brief
    and return the brief dict."""
    from mcp_server.composer import tools

    # Build a mock ctx for a 5-track session
    ableton = MagicMock()
    def send_command(cmd, args):
        if cmd == "get_session_info":
            return {
                "tempo": 122.0, "signature_numerator": 4, "signature_denominator": 4,
                "track_count": 1, "scene_count": 8,
                "tracks": [{"index": 0, "name": "Bass", "mute": False}],
            }
        if cmd == "get_clip_info":
            return {"length": 4.0, "is_midi_clip": True, "is_audio_clip": False}
        if cmd == "get_notes":
            return {"notes": [
                {"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100},
                {"pitch": 48, "start_time": 1, "duration": 1, "velocity": 100},
            ]}
        if cmd == "get_song_scale":
            return {"root_note": "Am", "scale_name": "minor"}
        return {}
    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    # compose tool may be sync OR async — handle both
    result = tools.compose(
        ctx=ctx,
        prompt="",
        mode="develop",
        seed_scene_index=0,
    )
    if hasattr(result, "__await__"):
        result = await result

    # Brief should carry seed_state with the right shape
    assert "seed_state" in result
    assert "design_targets" in result
    assert result["seed_state"]["tempo"] == 122.0


@pytest.mark.asyncio
async def test_develop_apply_dispatches_to_apply_develop_plan():
    """develop_apply MCP tool delegates to apply_develop_plan."""
    from mcp_server.composer import tools

    ableton = MagicMock()
    def send_command(cmd, args):
        if cmd == "get_session_info":
            return {"tempo": 122.0, "track_count": 5, "scene_count": 8}
        if cmd == "create_clip":
            return {"track_index": args["track_index"], "clip_index": args["clip_index"]}
        if cmd == "add_notes":
            return {"notes_added": len(args.get("notes", []))}
        if cmd == "set_clip_name":
            return {"name": args["name"]}
        return {"ok": True}
    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    plan = {
        "scope": "develop", "clip_length_beats": 4.0,
        "variants": [{"track_index": 0, "scene_index": 1, "name": "v",
                      "notes": [{"pitch": 60, "start_time": 0, "duration": 1, "velocity": 100}]}],
    }
    result = tools.develop_apply(ctx=ctx, plan=plan)
    if hasattr(result, "__await__"):
        result = await result

    assert "status" in result
    assert result["clips_created"] == 1


@pytest.mark.asyncio
async def test_analyze_loop_for_extension_returns_seed_state():
    from mcp_server.composer import tools

    ableton = MagicMock()
    def send_command(cmd, args):
        if cmd == "get_session_info":
            return {
                "tempo": 122.0, "signature_numerator": 4, "signature_denominator": 4,
                "track_count": 1, "scene_count": 8,
                "tracks": [{"index": 0, "name": "Drums", "mute": False}],
            }
        if cmd == "get_clip_info":
            return {"length": 4.0, "is_midi_clip": True, "is_audio_clip": False}
        if cmd == "get_notes":
            return {"notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 100}]}
        return {}
    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    result = tools.analyze_loop_for_extension(ctx=ctx, scene_index=0)
    if hasattr(result, "__await__"):
        result = await result

    assert "tracks" in result
    assert result["tempo"] == 122.0
    assert result["tracks"][0]["classification"] == "sample_trigger"
