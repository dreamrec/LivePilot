"""Clip MCP tools — info, create, delete, duplicate, fire, stop, properties, warp.

11 tools matching the Remote Script clips domain.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp


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


def _validate_color_index(color_index: int):
    if not 0 <= color_index <= 69:
        raise ValueError("color_index must be between 0 and 69")


@mcp.tool()
def get_clip_info(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Get detailed info about a clip: name, length, loop, launch settings."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    return _get_ableton(ctx).send_command("get_clip_info", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def create_clip(ctx: Context, track_index: int, clip_index: int, length: float) -> dict:
    """Create an empty MIDI clip in a clip slot (length in beats)."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if length <= 0:
        raise ValueError("length must be > 0")
    return _get_ableton(ctx).send_command("create_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
        "length": length,
    })


@mcp.tool()
def delete_clip(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Delete a clip from a clip slot. This removes all notes and automation. Use undo to revert."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    return _get_ableton(ctx).send_command("delete_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def duplicate_clip(
    ctx: Context,
    track_index: int,
    clip_index: int,
    target_track: int,
    target_clip: int,
) -> dict:
    """Duplicate a clip from one slot to another."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    _validate_track_index(target_track)
    _validate_clip_index(target_clip)
    return _get_ableton(ctx).send_command("duplicate_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
        "target_track": target_track,
        "target_clip": target_clip,
    })


@mcp.tool()
def fire_clip(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Launch/fire a clip slot."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    return _get_ableton(ctx).send_command("fire_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def stop_clip(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Stop a playing clip."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    return _get_ableton(ctx).send_command("stop_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def set_clip_name(ctx: Context, track_index: int, clip_index: int, name: str) -> dict:
    """Rename a clip."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not name.strip():
        raise ValueError("Clip name cannot be empty")
    return _get_ableton(ctx).send_command("set_clip_name", {
        "track_index": track_index,
        "clip_index": clip_index,
        "name": name,
    })


@mcp.tool()
def set_clip_color(ctx: Context, track_index: int, clip_index: int, color_index: int) -> dict:
    """Set clip color (0-69, Ableton's color palette)."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    _validate_color_index(color_index)
    return _get_ableton(ctx).send_command("set_clip_color", {
        "track_index": track_index,
        "clip_index": clip_index,
        "color_index": color_index,
    })


@mcp.tool()
def set_clip_loop(
    ctx: Context,
    track_index: int,
    clip_index: int,
    enabled: Optional[bool] = None,
    loop_start: Optional[float] = None,
    loop_end: Optional[float] = None,
) -> dict:
    """Enable/disable clip looping and optionally set loop start/end (in beats).
    All parameters are optional but at least one must be provided."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if enabled is None and loop_start is None and loop_end is None:
        raise ValueError("At least one of enabled, loop_start, or loop_end must be provided")
    params = {
        "track_index": track_index,
        "clip_index": clip_index,
    }
    if enabled is not None:
        params["enabled"] = enabled
    if loop_start is not None:
        if loop_start < 0:
            raise ValueError("Loop start must be >= 0")
        params["start"] = loop_start
    if loop_end is not None:
        if loop_end <= 0:
            raise ValueError("Loop end must be > 0")
        params["end"] = loop_end
    if loop_start is not None and loop_end is not None and loop_start >= loop_end:
        raise ValueError("Loop start must be less than loop end")
    return _get_ableton(ctx).send_command("set_clip_loop", params)


@mcp.tool()
def set_clip_launch(
    ctx: Context,
    track_index: int,
    clip_index: int,
    mode: int,
    quantization: Optional[int] = None,
) -> dict:
    """Set clip launch mode (0=Trigger, 1=Gate, 2=Toggle, 3=Repeat) and optional quantization."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not 0 <= mode <= 3:
        raise ValueError("Launch mode must be 0-3 (Trigger, Gate, Toggle, Repeat)")
    params = {
        "track_index": track_index,
        "clip_index": clip_index,
        "mode": mode,
    }
    if quantization is not None:
        params["quantization"] = quantization
    return _get_ableton(ctx).send_command("set_clip_launch", params)


@mcp.tool()
def set_clip_pitch(
    ctx: Context,
    track_index: int,
    clip_index: int,
    coarse: Optional[int] = None,
    fine: Optional[float] = None,
    gain: Optional[float] = None,
) -> dict:
    """Set pitch transposition and/or gain on an audio clip (BUG-A5).

    Audio clips only. Use this to correct sample pitch to match session key
    (e.g. a D#min Splice clip in a Dm session -> coarse=-1).

    coarse: semitones, -48..+48
    fine:   cents, -50..+50
    gain:   linear, 0..1 (Live's internal scale, not dB)

    At least one of coarse/fine/gain must be provided.
    """
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if coarse is None and fine is None and gain is None:
        raise ValueError(
            "Provide at least one of: coarse (semitones), fine (cents), gain (0-1)"
        )
    if coarse is not None and not -48 <= coarse <= 48:
        raise ValueError("coarse must be in -48..+48 semitones")
    if fine is not None and not -50.0 <= fine <= 50.0:
        raise ValueError("fine must be in -50..+50 cents")
    if gain is not None and not 0.0 <= gain <= 1.0:
        raise ValueError("gain must be in 0..1")
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
    }
    if coarse is not None:
        params["coarse"] = coarse
    if fine is not None:
        params["fine"] = fine
    if gain is not None:
        params["gain"] = gain
    return _get_ableton(ctx).send_command("set_clip_pitch", params)


_VALID_WARP_MODES = {0, 1, 2, 3, 4, 6}


@mcp.tool()
def set_clip_warp_mode(
    ctx: Context,
    track_index: int,
    clip_index: int,
    mode: int,
    warping: Optional[bool] = None,
) -> dict:
    """Set warp mode for an audio clip (0=Beats, 1=Tones, 2=Texture, 3=Re-Pitch, 4=Complex, 6=Complex Pro)."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if mode not in _VALID_WARP_MODES:
        raise ValueError("Warp mode must be one of: 0=Beats, 1=Tones, 2=Texture, 3=Re-Pitch, 4=Complex, 6=Complex Pro")
    params = {
        "track_index": track_index,
        "clip_index": clip_index,
        "mode": mode,
    }
    if warping is not None:
        params["warping"] = warping
    return _get_ableton(ctx).send_command("set_clip_warp_mode", params)
