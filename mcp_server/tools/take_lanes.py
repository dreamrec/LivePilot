"""Take Lanes tools (Live 12.0 UI / 12.2 API).

6 tools matching the Remote Script take_lanes domain:
- get_take_lanes / get_take_lane_clips — read-only introspection
  (works on any Live 12.x).
- create_take_lane / set_take_lane_name — mutation ops (12.2+).
- create_audio_clip_on_take_lane / create_midi_clip_on_take_lane —
  programmatic lane-scoped clip creation (12.2+).

Take lanes are alternative clip rows stacked under an arrangement
track — they let you audition or comp multiple passes of the same
part without occupying extra tracks. Live 12.0 shipped the UI;
scripting access to create/rename lanes and attach clips to them
landed in Live 12.2.
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def get_take_lanes(ctx: Context, track_index: int) -> dict:
    """List all take lanes on a track (Live 12.0+).

    Returns {lanes: [{index, name, is_frozen, clip_count}]}. Works
    on any Live 12.x — pure introspection, no version gate. Returns
    an empty list on tracks that don't expose take_lanes.
    """
    return _get_ableton(ctx).send_command("get_take_lanes", {
        "track_index": track_index,
    })


@mcp.tool()
def create_take_lane(ctx: Context, track_index: int) -> dict:
    """Create a new take lane on a track (Live 12.2+).

    Returns {lane_index, name}. Raises if the Live version predates
    12.2 or if the specific build doesn't expose Track.create_take_lane.
    """
    return _get_ableton(ctx).send_command("create_take_lane", {
        "track_index": track_index,
    })


@mcp.tool()
def set_take_lane_name(
    ctx: Context,
    track_index: int,
    lane_index: int,
    name: str,
) -> dict:
    """Rename an existing take lane (Live 12.2+).

    Returns {name} — the name after the update (Live may normalize
    whitespace or reject duplicates in some builds).
    """
    return _get_ableton(ctx).send_command("set_take_lane_name", {
        "track_index": track_index,
        "lane_index": lane_index,
        "name": name,
    })


@mcp.tool()
def create_audio_clip_on_take_lane(
    ctx: Context,
    track_index: int,
    lane_index: int,
    start_time: float,
    length: float,
) -> dict:
    """Create an arrangement audio clip on a specific take lane (Live 12.2+).

    start_time / length are in beats. length must be > 0. The track
    must be an audio track; Live raises on MIDI tracks. Returns
    {ok, track_index, lane_index, start_time, length}.
    """
    if length <= 0:
        raise ValueError("length must be > 0")
    return _get_ableton(ctx).send_command("create_audio_clip_on_take_lane", {
        "track_index": track_index,
        "lane_index": lane_index,
        "start_time": start_time,
        "length": length,
    })


@mcp.tool()
def create_midi_clip_on_take_lane(
    ctx: Context,
    track_index: int,
    lane_index: int,
    start_time: float,
    length: float,
) -> dict:
    """Create an arrangement MIDI clip on a specific take lane (Live 12.2+).

    start_time / length are in beats. length must be > 0. The track
    must be a MIDI track; Live raises on audio tracks. Returns
    {ok, track_index, lane_index, start_time, length}.
    """
    if length <= 0:
        raise ValueError("length must be > 0")
    return _get_ableton(ctx).send_command("create_midi_clip_on_take_lane", {
        "track_index": track_index,
        "lane_index": lane_index,
        "start_time": start_time,
        "length": length,
    })


@mcp.tool()
def get_take_lane_clips(
    ctx: Context,
    track_index: int,
    lane_index: int,
) -> dict:
    """List the arrangement clips on a specific take lane (Live 12.0+).

    Returns {clips: [{name, start_time, length, is_midi_clip}]}. Pure
    introspection — no version gate.
    """
    return _get_ableton(ctx).send_command("get_take_lane_clips", {
        "track_index": track_index,
        "lane_index": lane_index,
    })
