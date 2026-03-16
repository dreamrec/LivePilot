"""Arrangement MCP tools — clips, recording, cue points, navigation.

8 tools matching the Remote Script arrangement domain.
"""

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_track_index(track_index: int):
    if track_index < 0:
        raise ValueError("track_index must be >= 0")


@mcp.tool()
def get_arrangement_clips(ctx: Context, track_index: int) -> dict:
    """Get all arrangement clips on a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("get_arrangement_clips", {
        "track_index": track_index,
    })


@mcp.tool()
def jump_to_time(ctx: Context, beat_time: float) -> dict:
    """Jump to a specific beat time in the arrangement."""
    if beat_time < 0:
        raise ValueError("beat_time must be >= 0")
    return _get_ableton(ctx).send_command("jump_to_time", {"beat_time": beat_time})


@mcp.tool()
def capture_midi(ctx: Context) -> dict:
    """Capture recently played MIDI notes into a new clip."""
    return _get_ableton(ctx).send_command("capture_midi")


@mcp.tool()
def start_recording(ctx: Context, arrangement: bool = False) -> dict:
    """Start recording. arrangement=True for arrangement, False for session."""
    return _get_ableton(ctx).send_command("start_recording", {
        "arrangement": arrangement,
    })


@mcp.tool()
def stop_recording(ctx: Context) -> dict:
    """Stop all recording (both session and arrangement)."""
    return _get_ableton(ctx).send_command("stop_recording")


@mcp.tool()
def get_cue_points(ctx: Context) -> dict:
    """Get all cue points in the arrangement."""
    return _get_ableton(ctx).send_command("get_cue_points")


@mcp.tool()
def jump_to_cue(ctx: Context, cue_index: int) -> dict:
    """Jump to a cue point by index."""
    if cue_index < 0:
        raise ValueError("cue_index must be >= 0")
    return _get_ableton(ctx).send_command("jump_to_cue", {"cue_index": cue_index})


@mcp.tool()
def toggle_cue_point(ctx: Context) -> dict:
    """Set or delete a cue point at the current playback position."""
    return _get_ableton(ctx).send_command("toggle_cue_point")
