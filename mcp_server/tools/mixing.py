"""Mixing MCP tools — volume, pan, sends, routing, master, metering.

11 tools matching the Remote Script mixing domain.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_track_index(track_index: int):
    if track_index < -100:
        raise ValueError(
            "track_index must be >= 0 for regular tracks, "
            "or negative for return tracks (-1=A, -2=B)"
        )
    # Negative values -1..-99 are valid return track indices


@mcp.tool()
def set_track_volume(ctx: Context, track_index: int, volume: float) -> dict:
    """Set a track's volume (0.0-1.0). Use negative track_index for return tracks (-1=A, -2=B)."""
    _validate_track_index(track_index)
    if not 0.0 <= volume <= 1.0:
        raise ValueError("Volume must be between 0.0 and 1.0")
    return _get_ableton(ctx).send_command("set_track_volume", {
        "track_index": track_index,
        "volume": volume,
    })


@mcp.tool()
def set_track_pan(ctx: Context, track_index: int, pan: float) -> dict:
    """Set a track's panning (-1.0 left to 1.0 right). Use negative track_index for return tracks (-1=A, -2=B)."""
    _validate_track_index(track_index)
    if not -1.0 <= pan <= 1.0:
        raise ValueError("Pan must be between -1.0 and 1.0")
    return _get_ableton(ctx).send_command("set_track_pan", {
        "track_index": track_index,
        "pan": pan,
    })


@mcp.tool()
def set_track_send(
    ctx: Context, track_index: int, send_index: int, value: float
) -> dict:
    """Set a send level on a track (0.0-1.0)."""
    _validate_track_index(track_index)
    if send_index < 0:
        raise ValueError("send_index must be >= 0")
    if not 0.0 <= value <= 1.0:
        raise ValueError("Send value must be between 0.0 and 1.0")
    return _get_ableton(ctx).send_command("set_track_send", {
        "track_index": track_index,
        "send_index": send_index,
        "value": value,
    })


@mcp.tool()
def get_return_tracks(ctx: Context) -> dict:
    """Get info about all return tracks: name, volume, panning."""
    return _get_ableton(ctx).send_command("get_return_tracks")


@mcp.tool()
def get_master_track(ctx: Context) -> dict:
    """Get master track info: volume, panning, devices."""
    return _get_ableton(ctx).send_command("get_master_track")


@mcp.tool()
def set_master_volume(ctx: Context, volume: float) -> dict:
    """Set the master track volume (0.0-1.0)."""
    if not 0.0 <= volume <= 1.0:
        raise ValueError("Volume must be between 0.0 and 1.0")
    return _get_ableton(ctx).send_command("set_master_volume", {"volume": volume})


@mcp.tool()
def get_track_meters(
    ctx: Context,
    track_index: Optional[int] = None,
    include_stereo: bool = False,
) -> dict:
    """Read real-time output meter levels for tracks.

    Returns peak level (0.0-1.0) for each track. Call while playing to
    check levels, detect clipping, or verify a track is producing sound.

    track_index:    specific track (omit for all tracks)
    include_stereo: include left/right channel meters (adds GUI load)
    """
    params: dict = {}
    if track_index is not None:
        params["track_index"] = track_index
    if include_stereo:
        params["include_stereo"] = include_stereo
    return _get_ableton(ctx).send_command("get_track_meters", params)


@mcp.tool()
def get_master_meters(ctx: Context) -> dict:
    """Read real-time output meter levels for the master track (left, right, peak)."""
    return _get_ableton(ctx).send_command("get_master_meters")


@mcp.tool()
def get_mix_snapshot(ctx: Context) -> dict:
    """Get a complete mix snapshot: all track meters, volumes, pans, mute/solo,
    return tracks, and master levels. One call to assess the full mix state.
    Call while playing for meaningful meter readings."""
    return _get_ableton(ctx).send_command("get_mix_snapshot")


@mcp.tool()
def get_track_routing(ctx: Context, track_index: int) -> dict:
    """Get input/output routing info for a track. Use negative track_index for return tracks (-1=A, -2=B)."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("get_track_routing", {
        "track_index": track_index,
    })


@mcp.tool()
def set_track_routing(
    ctx: Context,
    track_index: int,
    input_routing_type: Optional[str] = None,
    input_routing_channel: Optional[str] = None,
    output_routing_type: Optional[str] = None,
    output_routing_channel: Optional[str] = None,
) -> dict:
    """Set input/output routing for a track by display name. Use negative track_index for return tracks (-1=A, -2=B)."""
    _validate_track_index(track_index)
    params = {"track_index": track_index}
    if input_routing_type is not None:
        params["input_type"] = input_routing_type
    if input_routing_channel is not None:
        params["input_channel"] = input_routing_channel
    if output_routing_type is not None:
        params["output_type"] = output_routing_type
    if output_routing_channel is not None:
        params["output_channel"] = output_routing_channel
    if len(params) == 1:
        raise ValueError("At least one routing parameter must be provided")
    return _get_ableton(ctx).send_command("set_track_routing", params)
