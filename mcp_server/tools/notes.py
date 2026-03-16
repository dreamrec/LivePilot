"""Notes MCP tools — add, get, remove, modify, duplicate, transpose, quantize.

8 tools matching the Remote Script notes domain.
"""

from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_track_index(track_index: int):
    if track_index < 0:
        raise ValueError("track_index must be >= 0")


def _validate_clip_index(clip_index: int):
    if clip_index < 0:
        raise ValueError("clip_index must be >= 0")


def _validate_note(note: dict):
    """Validate a single note specification dict."""
    pitch = note.get("pitch")
    if pitch is None:
        raise ValueError("Each note must have a 'pitch' field")
    if not 0 <= int(pitch) <= 127:
        raise ValueError("pitch must be between 0 and 127")

    if "start_time" not in note:
        raise ValueError("Each note must have a 'start_time' field")

    duration = note.get("duration")
    if duration is None:
        raise ValueError("Each note must have a 'duration' field")
    if float(duration) <= 0:
        raise ValueError("duration must be > 0")

    velocity = note.get("velocity")
    if velocity is not None:
        if not 0.0 <= float(velocity) <= 127.0:
            raise ValueError("velocity must be between 0.0 and 127.0")

    probability = note.get("probability")
    if probability is not None:
        if not 0.0 <= float(probability) <= 1.0:
            raise ValueError("probability must be between 0.0 and 1.0")

    velocity_deviation = note.get("velocity_deviation")
    if velocity_deviation is not None:
        if not -127.0 <= float(velocity_deviation) <= 127.0:
            raise ValueError("velocity_deviation must be between -127.0 and 127.0")

    release_velocity = note.get("release_velocity")
    if release_velocity is not None:
        if not 0.0 <= float(release_velocity) <= 127.0:
            raise ValueError("release_velocity must be between 0.0 and 127.0")


@mcp.tool()
def add_notes(ctx: Context, track_index: int, clip_index: int, notes: list[dict]) -> dict:
    """Add MIDI notes to a clip. Each note: {pitch, start_time, duration, velocity?, probability?, velocity_deviation?, release_velocity?}."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not notes:
        raise ValueError("notes list cannot be empty")
    for note in notes:
        _validate_note(note)
    return _get_ableton(ctx).send_command("add_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "notes": notes,
    })


@mcp.tool()
def get_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    from_pitch: int = 0,
    pitch_span: int = 128,
    from_time: float = 0.0,
    time_span: Optional[float] = None,
) -> dict:
    """Get MIDI notes from a clip region. Returns note_id, pitch, start_time, duration, velocity, mute, probability."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not 0 <= from_pitch <= 127:
        raise ValueError("from_pitch must be between 0 and 127")
    if pitch_span < 1 or pitch_span > 128:
        raise ValueError("pitch_span must be between 1 and 128")
    params = {
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
    return _get_ableton(ctx).send_command("get_notes", params)


@mcp.tool()
def remove_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    from_pitch: int = 0,
    pitch_span: int = 128,
    from_time: float = 0.0,
    time_span: Optional[float] = None,
) -> dict:
    """Remove all MIDI notes in a pitch/time region. Use undo to revert. Defaults remove ALL notes in the clip."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    params = {
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
    return _get_ableton(ctx).send_command("remove_notes", params)


@mcp.tool()
def remove_notes_by_id(ctx: Context, track_index: int, clip_index: int, note_ids: list[int]) -> dict:
    """Remove specific MIDI notes by their IDs. Use undo to revert."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not note_ids:
        raise ValueError("note_ids list cannot be empty")
    return _get_ableton(ctx).send_command("remove_notes_by_id", {
        "track_index": track_index,
        "clip_index": clip_index,
        "note_ids": note_ids,
    })


@mcp.tool()
def modify_notes(ctx: Context, track_index: int, clip_index: int, modifications: list[dict]) -> dict:
    """Modify existing MIDI notes by ID. Each mod: {note_id, pitch?, start_time?, duration?, velocity?, probability?}."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
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
    return _get_ableton(ctx).send_command("modify_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "modifications": modifications,
    })


@mcp.tool()
def duplicate_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    note_ids: list[int],
    time_offset: float = 0.0,
) -> dict:
    """Duplicate specific notes by ID, with optional time offset (in beats)."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not note_ids:
        raise ValueError("note_ids list cannot be empty")
    return _get_ableton(ctx).send_command("duplicate_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "note_ids": note_ids,
        "time_offset": time_offset,
    })


@mcp.tool()
def transpose_notes(
    ctx: Context,
    track_index: int,
    clip_index: int,
    semitones: int,
    from_time: float = 0.0,
    time_span: Optional[float] = None,
) -> dict:
    """Transpose notes in a time range by semitones (positive=up, negative=down)."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not -127 <= semitones <= 127:
        raise ValueError("semitones must be between -127 and 127")
    params = {
        "track_index": track_index,
        "clip_index": clip_index,
        "semitones": semitones,
        "from_time": from_time,
    }
    if time_span is not None:
        if time_span <= 0:
            raise ValueError("time_span must be > 0")
        params["time_span"] = time_span
    return _get_ableton(ctx).send_command("transpose_notes", params)


@mcp.tool()
def quantize_clip(
    ctx: Context,
    track_index: int,
    clip_index: int,
    grid: float,
    amount: float = 1.0,
) -> dict:
    """Quantize a clip's notes to a grid. grid=1.0 is quarter note, 0.5 is eighth, etc. amount 0.0-1.0."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if grid <= 0:
        raise ValueError("grid must be > 0")
    if not 0.0 <= amount <= 1.0:
        raise ValueError("amount must be between 0.0 and 1.0")
    return _get_ableton(ctx).send_command("quantize_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
        "grid": grid,
        "amount": amount,
    })
