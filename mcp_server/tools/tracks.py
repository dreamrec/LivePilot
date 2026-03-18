"""Track MCP tools — create, delete, rename, mute, solo, arm, group fold, monitor.

14 tools matching the Remote Script tracks domain.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_track_index(track_index: int):
    if track_index < 0:
        raise ValueError("track_index must be >= 0")


def _validate_color_index(color_index: int):
    if not 0 <= color_index <= 69:
        raise ValueError("color_index must be between 0 and 69")


@mcp.tool()
def get_track_info(ctx: Context, track_index: int) -> dict:
    """Get detailed info about a track: clips, devices, mixer state."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("get_track_info", {"track_index": track_index})


@mcp.tool()
def create_midi_track(
    ctx: Context,
    index: int = -1,
    name: Optional[str] = None,
    color: Optional[int] = None,
) -> dict:
    """Create a new MIDI track. index=-1 appends at end."""
    params = {"index": index}
    if name is not None:
        if not name.strip():
            raise ValueError("Track name cannot be empty")
        params["name"] = name
    if color is not None:
        _validate_color_index(color)
        params["color_index"] = color
    return _get_ableton(ctx).send_command("create_midi_track", params)


@mcp.tool()
def create_audio_track(
    ctx: Context,
    index: int = -1,
    name: Optional[str] = None,
    color: Optional[int] = None,
) -> dict:
    """Create a new audio track. index=-1 appends at end."""
    params = {"index": index}
    if name is not None:
        if not name.strip():
            raise ValueError("Track name cannot be empty")
        params["name"] = name
    if color is not None:
        _validate_color_index(color)
        params["color_index"] = color
    return _get_ableton(ctx).send_command("create_audio_track", params)


@mcp.tool()
def create_return_track(ctx: Context) -> dict:
    """Create a new return track."""
    return _get_ableton(ctx).send_command("create_return_track")


@mcp.tool()
def delete_track(ctx: Context, track_index: int) -> dict:
    """Delete a track by index. Use undo to revert if needed."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("delete_track", {"track_index": track_index})


@mcp.tool()
def duplicate_track(ctx: Context, track_index: int) -> dict:
    """Duplicate a track (copies all clips, devices, and settings)."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("duplicate_track", {"track_index": track_index})


@mcp.tool()
def set_track_name(ctx: Context, track_index: int, name: str) -> dict:
    """Rename a track."""
    _validate_track_index(track_index)
    if not name.strip():
        raise ValueError("Track name cannot be empty")
    return _get_ableton(ctx).send_command("set_track_name", {
        "track_index": track_index,
        "name": name,
    })


@mcp.tool()
def set_track_color(ctx: Context, track_index: int, color_index: int) -> dict:
    """Set track color (0-69, Ableton's color palette)."""
    _validate_track_index(track_index)
    _validate_color_index(color_index)
    return _get_ableton(ctx).send_command("set_track_color", {
        "track_index": track_index,
        "color_index": color_index,
    })


@mcp.tool()
def set_track_mute(ctx: Context, track_index: int, muted: bool) -> dict:
    """Mute or unmute a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_track_mute", {
        "track_index": track_index,
        "mute": muted,
    })


@mcp.tool()
def set_track_solo(ctx: Context, track_index: int, soloed: bool) -> dict:
    """Solo or unsolo a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_track_solo", {
        "track_index": track_index,
        "solo": soloed,
    })


@mcp.tool()
def set_track_arm(ctx: Context, track_index: int, armed: bool) -> dict:
    """Arm or disarm a track for recording."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_track_arm", {
        "track_index": track_index,
        "arm": armed,
    })


@mcp.tool()
def stop_track_clips(ctx: Context, track_index: int) -> dict:
    """Stop all playing clips on a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("stop_track_clips", {"track_index": track_index})


@mcp.tool()
def set_group_fold(ctx: Context, track_index: int, folded: bool) -> dict:
    """Fold or unfold a group track to show/hide its children."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_group_fold", {
        "track_index": track_index,
        "folded": folded,
    })


@mcp.tool()
def set_track_input_monitoring(ctx: Context, track_index: int, state: int) -> dict:
    """Set input monitoring (0=In, 1=Auto, 2=Off). Only for regular tracks, not return tracks."""
    _validate_track_index(track_index)
    if state not in (0, 1, 2):
        raise ValueError("Monitoring state must be 0=In, 1=Auto, or 2=Off")
    return _get_ableton(ctx).send_command("set_track_input_monitoring", {
        "track_index": track_index,
        "state": state,
    })
