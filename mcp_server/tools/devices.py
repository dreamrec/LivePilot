"""Device MCP tools — parameters, racks, browser loading, plugin deep control.

15 tools matching the Remote Script devices domain + M4L bridge.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastmcp import Context

from ..server import mcp


def _ensure_list(value: Any) -> list:
    """Parse JSON strings into lists. MCP clients may serialize list params as strings."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in parameter: {exc}") from exc
    return value


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


MASTER_TRACK_INDEX = -1000


def _validate_track_index(track_index: int):
    if track_index < 0 and track_index != MASTER_TRACK_INDEX:
        if track_index < -100:
            raise ValueError(
                "track_index must be >= 0 for regular tracks, "
                "negative for return tracks (-1=A, -2=B), or -1000 for master"
            )
        # Negative values -1..-99 are valid return track indices


def _validate_device_index(device_index: int):
    if device_index < 0:
        raise ValueError("device_index must be >= 0")


def _validate_chain_index(chain_index: int):
    if chain_index < 0:
        raise ValueError("chain_index must be >= 0")


@mcp.tool()
def get_device_info(ctx: Context, track_index: int, device_index: int) -> dict:
    """Get info about a device: name, class, type, active state, parameter count.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_device_info", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def get_device_parameters(ctx: Context, track_index: int, device_index: int) -> dict:
    """Get all parameters for a device with names, values, and ranges.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_device_parameters", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def set_device_parameter(
    ctx: Context,
    track_index: int,
    device_index: int,
    value: float,
    parameter_name: Optional[str] = None,
    parameter_index: Optional[int] = None,
) -> dict:
    """Set a device parameter by name or index.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if parameter_name is None and parameter_index is None:
        raise ValueError("Must provide parameter_name or parameter_index")
    if parameter_index is not None and parameter_index < 0:
        raise ValueError("parameter_index must be >= 0")
    params = {
        "track_index": track_index,
        "device_index": device_index,
        "value": value,
    }
    if parameter_name is not None:
        params["parameter_name"] = parameter_name
    if parameter_index is not None:
        params["parameter_index"] = parameter_index
    return _get_ableton(ctx).send_command("set_device_parameter", params)


@mcp.tool()
def batch_set_parameters(
    ctx: Context,
    track_index: int,
    device_index: int,
    parameters: Any,
) -> dict:
    """Set multiple device parameters in one call. parameters is a JSON array of objects: [{"name_or_index": "Dry/Wet", "value": 0.5}, ...].
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    parameters = _ensure_list(parameters)
    if not parameters:
        raise ValueError("parameters list cannot be empty")
    for entry in parameters:
        if "name_or_index" not in entry or "value" not in entry:
            raise ValueError("Each parameter must have 'name_or_index' and 'value'")
    return _get_ableton(ctx).send_command("batch_set_parameters", {
        "track_index": track_index,
        "device_index": device_index,
        "parameters": parameters,
    })


@mcp.tool()
def toggle_device(ctx: Context, track_index: int, device_index: int, active: bool) -> dict:
    """Enable or disable a device.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("toggle_device", {
        "track_index": track_index,
        "device_index": device_index,
        "active": active,
    })


@mcp.tool()
def delete_device(ctx: Context, track_index: int, device_index: int) -> dict:
    """Delete a device from a track. Use undo to revert if needed.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("delete_device", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def load_device_by_uri(ctx: Context, track_index: int, uri: str) -> dict:
    """Load a device onto a track using a browser URI string.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master."""
    _validate_track_index(track_index)
    if not uri.strip():
        raise ValueError("URI cannot be empty")
    return _get_ableton(ctx).send_command("load_device_by_uri", {
        "track_index": track_index,
        "uri": uri,
    })


@mcp.tool()
def find_and_load_device(ctx: Context, track_index: int, device_name: str) -> dict:
    """Search the browser for a device by name and load it onto a track.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master."""
    _validate_track_index(track_index)
    if not device_name.strip():
        raise ValueError("device_name cannot be empty")
    return _get_ableton(ctx).send_command("find_and_load_device", {
        "track_index": track_index,
        "device_name": device_name,
    })


@mcp.tool()
def set_simpler_playback_mode(
    ctx: Context,
    track_index: int,
    device_index: int,
    playback_mode: int,
    slice_by: Optional[int] = None,
    sensitivity: Optional[float] = None,
) -> dict:
    """Set Simpler's playback mode. playback_mode: 0=Classic, 1=One-Shot, 2=Slice. slice_by (Slice only): 0=Transient, 1=Beat, 2=Region, 3=Manual. sensitivity (0.0-1.0, Transient only)."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if playback_mode not in (0, 1, 2):
        raise ValueError("playback_mode must be 0 (Classic), 1 (One-Shot), or 2 (Slice)")
    params = {
        "track_index": track_index,
        "device_index": device_index,
        "playback_mode": playback_mode,
    }
    if slice_by is not None:
        params["slice_by"] = slice_by
    if sensitivity is not None:
        params["sensitivity"] = sensitivity
    return _get_ableton(ctx).send_command("set_simpler_playback_mode", params)


@mcp.tool()
def get_rack_chains(ctx: Context, track_index: int, device_index: int) -> dict:
    """Get all chains in a rack device with volume, pan, mute, solo."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_rack_chains", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def set_chain_volume(
    ctx: Context,
    track_index: int,
    device_index: int,
    chain_index: int,
    volume: Optional[float] = None,
    pan: Optional[float] = None,
) -> dict:
    """Set volume and/or pan for a chain in a rack device."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    _validate_chain_index(chain_index)
    if volume is not None and not 0.0 <= volume <= 1.0:
        raise ValueError("volume must be between 0.0 and 1.0")
    if pan is not None and not -1.0 <= pan <= 1.0:
        raise ValueError("pan must be between -1.0 and 1.0")
    if volume is None and pan is None:
        raise ValueError("Must provide volume and/or pan")
    params = {
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
    }
    if volume is not None:
        params["volume"] = volume
    if pan is not None:
        params["pan"] = pan
    return _get_ableton(ctx).send_command("set_chain_volume", params)


@mcp.tool()
def get_device_presets(ctx: Context, device_name: str) -> dict:
    """List available presets for an Ableton device (e.g. 'Corpus', 'Drum Buss', 'Wavetable').
    Searches audio_effects, instruments, and midi_effects categories.
    Returns preset names and URIs that can be loaded with load_device_by_uri."""
    if not device_name.strip():
        raise ValueError("device_name cannot be empty")
    return _get_ableton(ctx).send_command("get_device_presets", {
        "device_name": device_name,
    })


# ── Plugin Deep Control (M4L Bridge) ────────────────────────────────────


def _get_m4l(ctx: Context):
    """Get M4LBridge from lifespan context."""
    bridge = ctx.lifespan_context.get("m4l")
    if not bridge:
        raise ValueError("M4L bridge not initialized — restart the MCP server")
    return bridge


def _get_spectral(ctx: Context):
    """Get SpectralCache from lifespan context."""
    cache = ctx.lifespan_context.get("spectral")
    if not cache:
        raise ValueError("Spectral cache not initialized — restart the MCP server")
    return cache


def _require_analyzer(cache) -> None:
    if not cache.is_connected:
        raise ValueError(
            "LivePilot Analyzer not detected. "
            "Drag 'LivePilot Analyzer' onto the master track."
        )


@mcp.tool()
async def get_plugin_parameters(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Get ALL parameters from a VST/AU plugin including unconfigured ones.

    Returns every parameter the plugin exposes — not just the 128
    that Ableton's Configure panel shows. Includes name, value, min,
    max, default, and display string for each.
    Only works on PluginDevice/AuPluginDevice types.
    Requires LivePilot Analyzer on master track.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("get_plugin_params", track_index, device_index, timeout=20.0)


@mcp.tool()
async def map_plugin_parameter(
    ctx: Context,
    track_index: int,
    device_index: int,
    parameter_index: int,
) -> dict:
    """Add a plugin parameter to Ableton's Configure list for automation.

    After mapping, the parameter becomes visible in the device's macro
    panel and can be automated with set_device_parameter or
    set_clip_automation like any native parameter.
    Requires LivePilot Analyzer on master track.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if parameter_index < 0:
        raise ValueError("parameter_index must be >= 0")
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("map_plugin_param", track_index, device_index, parameter_index, timeout=10.0)


@mcp.tool()
async def get_plugin_presets(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """List a VST/AU plugin's internal presets and banks.

    Returns preset names and the currently selected preset index.
    Only works on PluginDevice/AuPluginDevice types.
    Requires LivePilot Analyzer on master track.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    cache = _get_spectral(ctx)
    _require_analyzer(cache)
    bridge = _get_m4l(ctx)
    return await bridge.send_command("get_plugin_presets", track_index, device_index, timeout=15.0)
