"""Arrangement MCP tools — clips, recording, cue points, navigation.

19 tools matching the Remote Script arrangement domain.
"""

from __future__ import annotations

import json
import time
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


_TRANSPORT_SETTLE_SECONDS = 0.15
_MAX_TRANSPORT_ATTEMPTS = 3
_POSITION_TOLERANCE_BEATS = 0.75
_ROLLING_POSITION_TOLERANCE_BEATS = 4.0
_SESSION_CLEAR_ATTEMPTS = 12


def _settle_transport() -> None:
    if _TRANSPORT_SETTLE_SECONDS > 0:
        time.sleep(_TRANSPORT_SETTLE_SECONDS)


def _float_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _position_delta(info: dict, target: float) -> Optional[float]:
    position = _float_or_none(info.get("current_song_time"))
    if position is None:
        return None
    return position - target


def _position_is_verified(info: dict, target: float) -> bool:
    delta = _position_delta(info, target)
    return delta is not None and abs(delta) <= _POSITION_TOLERANCE_BEATS


def _rolling_position_is_verified(info: dict, target: float) -> bool:
    delta = _position_delta(info, target)
    if delta is None:
        return False
    return (
        delta >= -_POSITION_TOLERANCE_BEATS
        and delta <= _ROLLING_POSITION_TOLERANCE_BEATS
    )


def _playing_session_clips(result: dict) -> list[dict]:
    clips = result.get("clips") or []
    return [
        clip for clip in clips
        if clip.get("is_playing") or clip.get("is_triggered")
    ]


def _arrangement_override_active(info: dict) -> bool:
    observed: list[bool] = []
    value = info.get("arrangement_override")
    if isinstance(value, bool):
        observed.append(value)
    for track in info.get("tracks") or []:
        if isinstance(track, dict):
            value = track.get("arrangement_override")
            if isinstance(value, bool):
                observed.append(value)
    return any(observed)


def _clear_session_override(send, warnings: list[str]) -> tuple[bool, int, list[dict]]:
    """Stop Session View clips and press Back to Arrangement after they settle."""
    last_clips: list[dict] = []
    for attempt in range(1, _SESSION_CLEAR_ATTEMPTS + 1):
        try:
            send("stop_all_clips")
        except Exception as exc:
            warnings.append(f"stop_all_clips failed: {exc}")

        _settle_transport()

        try:
            last_clips = _playing_session_clips(send("get_playing_clips"))
        except Exception as exc:
            warnings.append(f"get_playing_clips failed: {exc}")
            last_clips = []
            break

        if not last_clips:
            send("back_to_arranger")
            _settle_transport()
            return True, attempt, []

    send("back_to_arranger")
    _settle_transport()
    return not last_clips, _SESSION_CLEAR_ATTEMPTS, last_clips


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
def create_native_arrangement_clip(
    ctx: Context,
    track_index: int,
    start_time: float,
    length: float,
    name: str = "",
    color_index: Optional[int] = None,
) -> dict:
    """Create an empty MIDI clip directly in Arrangement View (Live 12.1.10+).

    Unlike create_arrangement_clip (which duplicates a session clip), this creates
    a native arrangement clip with full automation envelope support — volume rides,
    filter sweeps, send automation all work natively.

    Requires Live 12.1.10+. Falls back with a clear error on older versions.

    track_index: 0+ for regular MIDI tracks
    start_time:  beat position (0.0 = song start, 4.0 = bar 2 in 4/4)
    length:      clip length in beats
    name:        optional clip display name
    color_index: optional 0-69 Ableton color
    """
    _validate_track_index(track_index)
    if start_time < 0:
        raise ValueError("start_time must be >= 0")
    if length <= 0:
        raise ValueError("length must be > 0")

    params = {
        "track_index": track_index,
        "start_time": start_time,
        "length": length,
    }
    if name:
        params["name"] = name
    if color_index is not None:
        params["color_index"] = color_index

    return _get_ableton(ctx).send_command("create_native_arrangement_clip", params)


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
    """Force ALL tracks to follow the arrangement and optionally start playback.

    Sequenced and verified: stops transport/session clips, releases tracks
    from session override, sets back-to-arranger, jumps to position, checks
    the real playhead, starts transport, and re-seeks after playback starts
    if Live resumes from an old location.
    This is the reliable "play my arrangement from the top" command.

    beat_time: position to start from (default 0 = beginning)
    loop_start: loop region start in beats (default 0)
    loop_length: loop region length in beats (0 = no loop change)
    play: whether to start playback (default True)
    """
    ableton = _get_ableton(ctx)
    target = max(0.0, float(beat_time))
    warnings: list[str] = []
    latest_info: dict = {}

    def send(command: str, params: Optional[dict] = None) -> dict:
        result = ableton.send_command(command, params or {})
        return result if isinstance(result, dict) else {}

    send("stop_playback")
    _settle_transport()

    session_clear, session_clear_attempts, playing_clips = _clear_session_override(
        send, warnings
    )

    if loop_length > 0:
        send("set_session_loop", {
            "enabled": True,
            "loop_start": float(loop_start),
            "loop_length": float(loop_length),
        })
        _settle_transport()

    seek_verified = False
    seek_attempts = 0
    for seek_attempts in range(1, _MAX_TRANSPORT_ATTEMPTS + 1):
        send("jump_to_time", {"beat_time": target})
        _settle_transport()
        latest_info = send("get_session_info")
        if _position_is_verified(latest_info, target):
            seek_verified = True
            break

    if not seek_verified:
        position = latest_info.get("current_song_time")
        warnings.append(
            f"position verification failed: requested {target}, observed {position}"
        )

    play_verified = not play
    play_attempts = 0
    if play:
        for play_attempts in range(1, _MAX_TRANSPORT_ATTEMPTS + 1):
            send("back_to_arranger")
            _settle_transport()
            send("start_playback")
            _settle_transport()

            try:
                playing_clips = _playing_session_clips(send("get_playing_clips"))
                session_clear = not playing_clips
            except Exception as exc:
                warnings.append(f"get_playing_clips failed after playback start: {exc}")

            if playing_clips:
                extra_clear, extra_attempts, playing_clips = _clear_session_override(
                    send, warnings
                )
                session_clear = extra_clear
                session_clear_attempts += extra_attempts

            latest_info = send("get_session_info")
            if (
                latest_info.get("is_playing")
                and session_clear
                and not _arrangement_override_active(latest_info)
                and _rolling_position_is_verified(latest_info, target)
            ):
                play_verified = True
                break

            # Live can resume from a previous playhead despite a stopped seek.
            # Once transport is rolling, a second seek is much more reliable.
            if not _rolling_position_is_verified(latest_info, target):
                send("jump_to_time", {"beat_time": target})
                _settle_transport()
                send("back_to_arranger")
                _settle_transport()
                latest_info = send("get_session_info")
                if (
                    latest_info.get("is_playing")
                    and session_clear
                    and not _arrangement_override_active(latest_info)
                    and _rolling_position_is_verified(latest_info, target)
                ):
                    play_verified = True
                    break

        if not play_verified:
            warnings.append("playback verification failed after start_playback")

    position = _float_or_none(latest_info.get("current_song_time"))
    delta = position - target if position is not None else None

    return {
        "arrangement_active": (
            session_clear and not _arrangement_override_active(latest_info)
        ),
        "arrangement_override": latest_info.get("arrangement_override"),
        "requested_position": target,
        "position": position,
        "position_delta": delta,
        "is_playing": bool(latest_info.get("is_playing", False)),
        "loop": latest_info.get("loop"),
        "verified_position": seek_verified,
        "verified_playback": play_verified,
        "session_clear": session_clear,
        "session_clear_attempts": session_clear_attempts,
        "playing_clips": playing_clips,
        "seek_attempts": seek_attempts,
        "play_attempts": play_attempts,
        "warnings": warnings,
    }


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
