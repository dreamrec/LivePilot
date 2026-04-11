"""Arrangement MCP tools — clips, recording, cue points, navigation.

19 tools matching the Remote Script arrangement domain.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastmcp import Context

from ..server import mcp
from .notes import _validate_note


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_track_index(track_index: int):
    """Validate track index. Must be >= 0 for regular tracks."""
    if track_index < 0:
        raise ValueError("track_index must be >= 0")


def _validate_clip_index(clip_index: int):
    if clip_index < 0:
        raise ValueError("clip_index must be >= 0")


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


@mcp.tool()
def create_arrangement_clip(
    ctx: Context,
    track_index: int,
    clip_slot_index: int,
    start_time: float,
    length: float,
    loop_length: Optional[float] = None,
    name: str = "",
    color_index: Optional[int] = None,
) -> dict:
    """Duplicate a session clip into Arrangement View at a specific beat position.

    clip_slot_index: which session clip slot to use as the source pattern
    start_time:      beat position in arrangement (0.0 = song start, 4.0 = bar 2)
    length:          total clip length in beats on the timeline
    loop_length:     pattern length to loop within the clip (e.g. 8.0 for an
                     8-beat pattern inside a 128-beat section). Defaults to
                     the source clip's length. Must be > 0.

    When loop_length < source clip length, overlapping copies are placed
    every loop_length beats. Ableton's "later clip takes priority" rule
    ensures correct playback. Each copy's internal loop region is set to
    loop_length beats. For best results, use loop_length >= source length.

    name:            optional clip display name
    color_index:     optional 0-69 Ableton color

    Returns clip_index in the track's arrangement_clips list.
    """
    _validate_track_index(track_index)
    if clip_slot_index < 0:
        raise ValueError("clip_slot_index must be >= 0")
    if start_time < 0:
        raise ValueError("start_time must be >= 0")
    if length <= 0:
        raise ValueError("length must be > 0")
    params: dict = {
        "track_index": track_index,
        "clip_slot_index": clip_slot_index,
        "start_time": start_time,
        "length": length,
    }
    if loop_length is not None:
        if loop_length <= 0:
            raise ValueError("loop_length must be > 0")
        params["loop_length"] = loop_length
    if name:
        params["name"] = name
    if color_index is not None:
        if not 0 <= color_index <= 69:
            raise ValueError("color_index must be 0-69")
        params["color_index"] = color_index
    return _get_ableton(ctx).send_command("create_arrangement_clip", params)


@mcp.tool()
def add_arrangement_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    notes: list | str,
) -> dict:
    """Add MIDI notes to an arrangement clip.

    clip_index:  index in track.arrangement_clips (returned by create_arrangement_clip
                 or get_arrangement_clips)
    notes:       list of dicts with: pitch (0-127), start_time (beats, relative to
                 clip start), duration (beats), velocity (1-127), mute (bool)

    start_time in notes is relative to the clip start, not the song timeline.
    """
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if isinstance(notes, str):
        try:
            notes = json.loads(notes)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in notes parameter: {exc}") from exc
    for note in notes:
        _validate_note(note)
    return _get_ableton(ctx).send_command("add_arrangement_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "notes": notes,
    })


@mcp.tool()
def set_arrangement_automation(
    ctx: Context,
    track_index: int,
    clip_index: int,
    parameter_type: str,
    points: list | str,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
) -> dict:
    """Write automation envelope points into an arrangement clip.

    parameter_type: "device", "volume", "panning", or "send"
    points:         list of {time, value, duration?} dicts — time is relative
                    to clip start (0.0 = first beat of clip), value is the
                    parameter's native range (0.0-1.0 for most, check
                    get_device_parameters for exact min/max).
                    duration defaults to 0.125 beats (step automation).
                    For smooth ramps, use many closely-spaced points.

    For parameter_type="device": device_index + parameter_index required.
    For parameter_type="send": send_index required (0=A, 1=B, ...).
    """
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if parameter_type not in ("device", "volume", "panning", "send"):
        raise ValueError("parameter_type must be 'device', 'volume', 'panning', or 'send'")
    if parameter_type == "device":
        if device_index is None or parameter_index is None:
            raise ValueError("device_index and parameter_index required for parameter_type='device'")
    if parameter_type == "send" and send_index is None:
        raise ValueError("send_index required for parameter_type='send'")
    if isinstance(points, str):
        try:
            points = json.loads(points)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in points parameter: {exc}") from exc
    if not points:
        raise ValueError("points list cannot be empty")
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_type": parameter_type,
        "points": points,
    }
    if device_index is not None:
        params["device_index"] = device_index
    if parameter_index is not None:
        params["parameter_index"] = parameter_index
    if send_index is not None:
        params["send_index"] = send_index
    return _get_ableton(ctx).send_command("set_arrangement_automation", params)


@mcp.tool()
def transpose_arrangement_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    semitones: int,
    from_time: float = 0.0,
    time_span: Optional[float] = None,
) -> dict:
    """Transpose notes in an arrangement clip by semitones (positive=up, negative=down).

    clip_index:  index in track.arrangement_clips (from get_arrangement_clips)
    semitones:   number of semitones to shift (-127 to 127)
    from_time:   start of note range (beats, relative to clip start)
    time_span:   length of note range in beats (defaults to full clip)
    """
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not -127 <= semitones <= 127:
        raise ValueError("semitones must be between -127 and 127")
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
        "semitones": semitones,
        "from_time": from_time,
    }
    if time_span is not None:
        if time_span <= 0:
            raise ValueError("time_span must be > 0")
        params["time_span"] = time_span
    return _get_ableton(ctx).send_command("transpose_arrangement_notes", params)


@mcp.tool()
def set_arrangement_clip_name(
    ctx: Context,
    track_index: int,
    clip_index: int,
    name: str,
) -> dict:
    """Rename an arrangement clip by its index in the track's arrangement_clips list."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not name.strip():
        raise ValueError("name cannot be empty")
    return _get_ableton(ctx).send_command("set_arrangement_clip_name", {
        "track_index": track_index,
        "clip_index": clip_index,
        "name": name,
    })


@mcp.tool()
def back_to_arranger(ctx: Context) -> dict:
    """Switch playback from session clips back to the arrangement timeline."""
    return _get_ableton(ctx).send_command("back_to_arranger")


@mcp.tool()
def force_arrangement(
    ctx: Context,
    beat_time: float = 0,
    loop_start: float = 0,
    loop_length: float = 0,
    play: bool = True,
) -> dict:
    """Force ALL tracks to follow the arrangement and start playback.

    Atomically: stops all session clips, releases every track from
    session override, sets back-to-arranger, jumps to position, and
    starts playing. This is the "play my arrangement from the top"
    command.

    beat_time: position to start from (default 0 = beginning)
    loop_start: loop region start in beats (default 0)
    loop_length: loop region length in beats (0 = no loop change)
    play: whether to start playback (default True)
    """
    params: dict = {"beat_time": beat_time, "play": play}
    if loop_length > 0:
        params["loop_start"] = loop_start
        params["loop_length"] = loop_length
    return _get_ableton(ctx).send_command("force_arrangement", params)


@mcp.tool()
def get_arrangement_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    from_pitch: int = 0,
    pitch_span: int = 128,
    from_time: float = 0.0,
    time_span: Optional[float] = None,
) -> dict:
    """Get MIDI notes from an arrangement clip. Returns note_id, pitch, start_time,
    duration, velocity, mute, probability. Times are relative to clip start."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not 0 <= from_pitch <= 127:
        raise ValueError("from_pitch must be between 0 and 127")
    if pitch_span < 1 or pitch_span > 128:
        raise ValueError("pitch_span must be between 1 and 128")
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
        "from_pitch": from_pitch,
        "pitch_span": pitch_span,
        "from_time": from_time,
    }
    if time_span is not None:
        if time_span <= 0:
            raise ValueError("time_span must be > 0")
        params["time_span"] = time_span
    return _get_ableton(ctx).send_command("get_arrangement_notes", params)


@mcp.tool()
def remove_arrangement_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    from_pitch: int = 0,
    pitch_span: int = 128,
    from_time: float = 0.0,
    time_span: Optional[float] = None,
) -> dict:
    """Remove all MIDI notes in a pitch/time region of an arrangement clip. Defaults remove ALL notes."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
        "from_pitch": from_pitch,
        "pitch_span": pitch_span,
        "from_time": from_time,
    }
    if time_span is not None:
        if time_span <= 0:
            raise ValueError("time_span must be > 0")
        params["time_span"] = time_span
    return _get_ableton(ctx).send_command("remove_arrangement_notes", params)


@mcp.tool()
def remove_arrangement_notes_by_id(
    ctx: Context,
    track_index: int,
    clip_index: int,
    note_ids: list | str,
) -> dict:
    """Remove specific MIDI notes from an arrangement clip by their IDs."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if isinstance(note_ids, str):
        try:
            note_ids = json.loads(note_ids)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in note_ids parameter: {exc}") from exc
    if not note_ids:
        raise ValueError("note_ids list cannot be empty")
    return _get_ableton(ctx).send_command("remove_arrangement_notes_by_id", {
        "track_index": track_index,
        "clip_index": clip_index,
        "note_ids": note_ids,
    })


@mcp.tool()
def modify_arrangement_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    modifications: list | str,
) -> dict:
    """Modify existing MIDI notes in an arrangement clip by ID. modifications is a JSON array:
    [{note_id, pitch?, start_time?, duration?, velocity?, probability?}]."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if isinstance(modifications, str):
        try:
            modifications = json.loads(modifications)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in modifications parameter: {exc}") from exc
    if not modifications:
        raise ValueError("modifications list cannot be empty")
    for mod in modifications:
        if "note_id" not in mod:
            raise ValueError("Each modification must have a 'note_id' field")
        if "pitch" in mod and not 0 <= int(mod["pitch"]) <= 127:
            raise ValueError("pitch must be between 0 and 127")
        if "duration" in mod and float(mod["duration"]) <= 0:
            raise ValueError("duration must be > 0")
        if "velocity" in mod and not 0.0 <= float(mod["velocity"]) <= 127.0:
            raise ValueError("velocity must be between 0.0 and 127.0")
        if "probability" in mod and not 0.0 <= float(mod["probability"]) <= 1.0:
            raise ValueError("probability must be between 0.0 and 1.0")
    return _get_ableton(ctx).send_command("modify_arrangement_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "modifications": modifications,
    })


@mcp.tool()
def duplicate_arrangement_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    note_ids: list | str,
    time_offset: float = 0.0,
) -> dict:
    """Duplicate specific notes in an arrangement clip by ID, with optional time offset (beats)."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if isinstance(note_ids, str):
        try:
            note_ids = json.loads(note_ids)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in note_ids parameter: {exc}") from exc
    if not note_ids:
        raise ValueError("note_ids list cannot be empty")
    return _get_ableton(ctx).send_command("duplicate_arrangement_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "note_ids": note_ids,
        "time_offset": time_offset,
    })
