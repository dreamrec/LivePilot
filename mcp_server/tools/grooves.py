"""Groove Pool tools (Live 11+).

7 tools matching the Remote Script grooves domain:
- list_grooves / get_groove_info — enumerate the pool and inspect.
- set_groove_params — adjust quantization/random/timing/velocity amounts.
- assign_clip_groove / get_clip_groove — per-clip groove binding
  (pass ``groove_id = -1`` to clear).
- get/set_song_groove_amount — master groove dial (0.0-1.31).
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def list_grooves(ctx: Context) -> dict:
    """List all grooves in the Groove Pool (Live 11+).

    Returns each groove's id (index), name, base quantization grid
    (integer enum, e.g. 1/16th = 4), quantization_amount, random_amount,
    timing_amount, and velocity_amount. Use the id with
    assign_clip_groove() or set_groove_params().
    """
    return _get_ableton(ctx).send_command("list_grooves", {})


@mcp.tool()
def get_groove_info(ctx: Context, groove_id: int) -> dict:
    """Read a single groove's parameters (Live 11+).

    groove_id is the index from list_grooves(). Returns the same shape
    as one entry of list_grooves().
    """
    return _get_ableton(ctx).send_command("get_groove_info", {
        "groove_id": groove_id,
    })


@mcp.tool()
def set_groove_params(
    ctx: Context,
    groove_id: int,
    quantization_amount: Optional[float] = None,
    random_amount: Optional[float] = None,
    timing_amount: Optional[float] = None,
    velocity_amount: Optional[float] = None,
) -> dict:
    """Adjust a groove's parameters (Live 11+). Omitted args preserve.

    Ranges:
      quantization_amount, random_amount, timing_amount: 0.0-1.0
      velocity_amount: -1.0 to 1.0 (signed — negative subtracts velocity)
    Any field left unspecified keeps its current value. Returns the
    full groove_info dict after the update.
    """
    payload: dict = {"groove_id": groove_id}
    if quantization_amount is not None:
        if not 0.0 <= quantization_amount <= 1.0:
            raise ValueError("quantization_amount must be 0.0-1.0")
        payload["quantization_amount"] = quantization_amount
    if random_amount is not None:
        if not 0.0 <= random_amount <= 1.0:
            raise ValueError("random_amount must be 0.0-1.0")
        payload["random_amount"] = random_amount
    if timing_amount is not None:
        if not 0.0 <= timing_amount <= 1.0:
            raise ValueError("timing_amount must be 0.0-1.0")
        payload["timing_amount"] = timing_amount
    if velocity_amount is not None:
        if not -1.0 <= velocity_amount <= 1.0:
            raise ValueError("velocity_amount must be -1.0 to 1.0")
        payload["velocity_amount"] = velocity_amount
    return _get_ableton(ctx).send_command("set_groove_params", payload)


@mcp.tool()
def assign_clip_groove(
    ctx: Context,
    track_index: int,
    clip_index: int,
    groove_id: int = -1,
) -> dict:
    """Assign a groove to a clip (Live 11+).

    groove_id: integer index from list_grooves(), or -1 to clear the
    clip's groove (sets clip.groove = None). Returns
    {track_index, clip_index, groove_id, groove_name} — both id and
    name are None when cleared.
    """
    return _get_ableton(ctx).send_command("assign_clip_groove", {
        "track_index": track_index,
        "clip_index": clip_index,
        "groove_id": groove_id,
    })


@mcp.tool()
def get_clip_groove(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Read a clip's current groove assignment (Live 11+).

    Returns {groove_id, groove_name}. Both are null/None if the clip
    has no groove assigned.
    """
    return _get_ableton(ctx).send_command("get_clip_groove", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def get_song_groove_amount(ctx: Context) -> dict:
    """Read the master groove amount dial (Live 11+).

    Scales the effect of ALL assigned grooves on playback. 0.0 = no
    groove influence; 1.0 = nominal; up to 1.31 = exaggerated.
    """
    return _get_ableton(ctx).send_command("get_song_groove_amount", {})


@mcp.tool()
def set_song_groove_amount(ctx: Context, amount: float) -> dict:
    """Set the master groove amount dial (Live 11+).

    Scales all grooves' effect on playback. Range 0.0-1.31.
    Live's spec nominally caps at 1.0 but the exposed property
    accepts values up to ~1.31, matching the UI's maximum nudge.
    """
    if not 0.0 <= amount <= 1.31:
        raise ValueError("amount must be 0.0-1.31")
    return _get_ableton(ctx).send_command("set_song_groove_amount", {
        "amount": amount,
    })
