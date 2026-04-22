"""Mixing MCP tools — volume, pan, sends, routing, master, metering.

11 tools matching the Remote Script mixing domain.
"""

from __future__ import annotations

import asyncio
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
async def get_track_meters(
    ctx: Context,
    track_index: Optional[int] = None,
    include_stereo: bool = False,
    samples: int = 1,
    sample_interval_ms: int = 50,
) -> dict:
    """Read real-time output meter levels for tracks.

    Returns peak level (0.0-1.0) for each track. Call while playing to
    check levels, detect clipping, or verify a track is producing sound.

    track_index:        specific track (omit for all tracks)
    include_stereo:     include left/right channel meters (adds GUI load)
    samples:            number of snapshots to take (default 1). When > 1,
                        returns peak-over-window for `level`/`left`/`right`
                        (BUG-2026-04-22#7 fix — single reads are unreliable
                        because Live samples `level` and `left/right` at
                        slightly different moments and they can disagree).
    sample_interval_ms: ms between snapshots when samples > 1 (default 50).

    BUG-B3 (still active): when playback is stopped, `level` reports
    peak-hold from the last loud moment while `left`/`right` report
    instantaneous channel levels (decay to 0). We tag responses with
    `is_playing`; when stopped + stereo requested, left/right → null.
    """
    params: dict = {}
    if track_index is not None:
        params["track_index"] = track_index
    if include_stereo:
        params["include_stereo"] = include_stereo
    ableton = _get_ableton(ctx)

    # Multi-sample path for BUG-2026-04-22#7 — take N snapshots and return
    # the max per track per channel. Mathematical-impossibility cases
    # (level>0 but left=right=0) are resolved by sampling over time.
    if samples and samples > 1:
        samples = min(samples, 20)  # hard cap
        interval = max(0, sample_interval_ms) / 1000.0
        snapshots: list[dict] = []
        for i in range(samples):
            snap = ableton.send_command("get_track_meters", params)
            if isinstance(snap, dict):
                snapshots.append(snap)
            if i < samples - 1 and interval > 0:
                await asyncio.sleep(interval)
        if not snapshots:
            return {"error": "No meter snapshots collected"}
        # Take the first snapshot's structure and peak-combine across all.
        result = dict(snapshots[0])
        # Merge tracks field with peak-maxing
        if "tracks" in result:
            merged = {}
            for snap in snapshots:
                for t in snap.get("tracks", []):
                    tid = t.get("index")
                    if tid is None:
                        continue
                    if tid not in merged:
                        merged[tid] = dict(t)
                    else:
                        for fld in ("level", "left", "right"):
                            cur = merged[tid].get(fld) or 0
                            new = t.get(fld) or 0
                            if new > cur:
                                merged[tid][fld] = new
            result["tracks"] = list(merged.values())
        elif include_stereo or track_index is not None:
            # Single-track response shape
            for fld in ("level", "left", "right"):
                vals = [s.get(fld) for s in snapshots if s.get(fld) is not None]
                if vals:
                    result[fld] = max(vals)
        result["samples_collected"] = len(snapshots)
        result["sample_interval_ms"] = sample_interval_ms
    else:
        result = ableton.send_command("get_track_meters", params)
        if not isinstance(result, dict):
            return result

    # Probe playback state once so we can annotate the response
    try:
        session = ableton.send_command("get_session_info", {})
        is_playing = bool(session.get("is_playing", False))
    except Exception:
        is_playing = None  # unknown — leave left/right as reported

    result["is_playing"] = is_playing
    # When stopped AND stereo was requested, mark l/r as None so they
    # don't look like a killed signal
    if include_stereo and is_playing is False:
        for t in result.get("tracks", []):
            if isinstance(t, dict):
                if t.get("left") == 0 and t.get("right") == 0:
                    t["left"] = None
                    t["right"] = None
                    t["_stereo_note"] = (
                        "left/right suppressed because playback is stopped; "
                        "`level` is peak-hold from the last audio event"
                    )
    return result


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
