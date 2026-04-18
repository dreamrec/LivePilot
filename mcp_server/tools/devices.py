"""Device MCP tools — parameters, racks, browser loading, plugin deep control.

16 tools matching the Remote Script devices domain + M4L bridge.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastmcp import Context

from ..server import mcp, _identify_port_holder
import logging

logger = logging.getLogger(__name__)



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
_PLUGIN_CLASS_NAMES = {"PluginDevice", "AuPluginDevice"}
_SAMPLE_DEPENDENT_DEVICE_NAMES = {
    "idensity": "Requires source audio loaded inside the plugin UI before MIDI can produce sound.",
    "tardigrain": "Requires source audio loaded inside the plugin UI before MIDI can produce sound.",
    "koala sampler": "Requires source audio loaded inside the plugin UI before MIDI can produce sound.",
    "burns audio granular": "Requires source audio loaded inside the plugin UI before MIDI can produce sound.",
    "audiolayer": "Requires samples loaded inside the plugin UI before MIDI can produce sound.",
    "segments": "Requires source audio loaded inside the plugin UI before MIDI can produce sound.",
    "segments (instr)": "Requires source audio loaded inside the plugin UI before MIDI can produce sound.",
}


def _sample_dependency_reason(device_name: str) -> Optional[str]:
    lowered = device_name.strip().lower()
    for candidate, reason in _SAMPLE_DEPENDENT_DEVICE_NAMES.items():
        if candidate in lowered:
            return reason
    return None


def _annotate_device_info(result: dict) -> dict:
    """Attach MCP-focused health hints to raw get_device_info results."""
    if not isinstance(result, dict):
        return result

    class_name = str(result.get("class_name") or "")
    device_name = str(result.get("name") or "")
    parameter_count = int(result.get("parameter_count") or 0)
    is_plugin = class_name in _PLUGIN_CLASS_NAMES

    plugin_host_status = "not_plugin"
    if is_plugin:
        plugin_host_status = "host_visible" if parameter_count > 1 else "opaque_or_failed"

    flags: list[str] = []
    warnings: list[str] = []

    sample_reason = _sample_dependency_reason(device_name)
    if sample_reason:
        flags.append("sample_dependent")
        warnings.append(sample_reason)

    if plugin_host_status == "opaque_or_failed":
        flags.append("opaque_or_failed_plugin")
        warnings.append(
            "Ableton only sees %d host parameter(s) for this plugin. "
            "If auditioning produces no audio, the plugin likely failed to initialize. "
            "If audio is flowing, the plugin is usable but opaque to MCP sound design."
            % parameter_count
        )

    annotated = dict(result)
    annotated["is_plugin"] = is_plugin
    annotated["plugin_host_status"] = plugin_host_status
    annotated["health_flags"] = flags
    annotated["mcp_sound_design_ready"] = len(flags) == 0
    if warnings:
        annotated["warnings"] = warnings
    return annotated


def _annotate_loaded_device_result(result: dict) -> dict:
    """Attach preflight warnings to load results based on loaded device names."""
    if not isinstance(result, dict):
        return result

    loaded_name = str(result.get("loaded") or "")
    sample_reason = _sample_dependency_reason(loaded_name)
    if not sample_reason:
        return result

    annotated = dict(result)
    annotated["health_flags"] = ["sample_dependent"]
    annotated["warnings"] = [sample_reason]
    annotated["mcp_sound_design_ready"] = False
    return annotated


def _merge_unique(base: list[str], extra: list[str]) -> list[str]:
    merged = list(base)
    for item in extra:
        if item not in merged:
            merged.append(item)
    return merged


def _postflight_loaded_device(ctx: Context, result: dict) -> dict:
    """Attach post-load health info by inspecting the newly loaded device."""
    annotated = _annotate_loaded_device_result(result)
    if not isinstance(annotated, dict):
        return annotated

    track_index = annotated.get("track_index")
    loaded_name = str(annotated.get("loaded") or "")
    if track_index is None or not loaded_name:
        return annotated

    try:
        track_info = _get_ableton(ctx).send_command("get_track_info", {
            "track_index": int(track_index),
        })
    except Exception as exc:
        logger.debug("_postflight_loaded_device failed: %s", exc)
        return annotated
    devices = track_info.get("devices", []) if isinstance(track_info, dict) else []
    if not isinstance(devices, list) or not devices:
        return annotated

    match = None
    for device in reversed(devices):
        if str(device.get("name") or "") == loaded_name:
            match = device
            break
    if match is None:
        match = devices[-1]

    # get_track_info returns device summaries without a parameters list,
    # so use the 'parameter_count' field if present, otherwise fetch
    # the actual device info for an accurate count.
    param_count = match.get("parameter_count", len(match.get("parameters", [])))
    if param_count == 0 and match.get("index") is not None:
        try:
            full_info = _get_ableton(ctx).send_command("get_device_info", {
                "track_index": int(track_index),
                "device_index": int(match["index"]),
            })
            param_count = full_info.get("parameter_count", 0)
        except Exception as exc:
            logger.debug("_postflight_loaded_device failed: %s", exc)
    device_info = _annotate_device_info({
        "name": match.get("name"),
        "class_name": match.get("class_name"),
        "is_active": match.get("is_active"),
        "parameter_count": param_count,
    })

    merged = dict(annotated)
    merged["device_index"] = match.get("index")
    merged["class_name"] = device_info.get("class_name")
    merged["parameter_count"] = device_info.get("parameter_count")
    merged["is_plugin"] = device_info.get("is_plugin")
    merged["plugin_host_status"] = device_info.get("plugin_host_status")
    merged["mcp_sound_design_ready"] = (
        merged.get("mcp_sound_design_ready", True)
        and device_info.get("mcp_sound_design_ready", True)
    )

    merged["health_flags"] = _merge_unique(
        annotated.get("health_flags", []),
        device_info.get("health_flags", []),
    )

    warnings = _merge_unique(
        annotated.get("warnings", []),
        device_info.get("warnings", []),
    )
    if warnings:
        merged["warnings"] = warnings

    return merged


def _validate_track_index(track_index: int):
    if track_index < 0 and track_index != MASTER_TRACK_INDEX:
        if not (-99 <= track_index <= -1):
            raise ValueError(
                "track_index must be >= 0 for regular tracks, "
                "-1..-99 for return tracks (-1=A, -2=B), or -1000 for master"
            )


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
    result = _get_ableton(ctx).send_command("get_device_info", {
        "track_index": track_index,
        "device_index": device_index,
    })
    return _annotate_device_info(result)


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

    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master.

    ⚠️ PARAMETER RANGES ARE NOT ALWAYS 0-1 (BUG-B4 / B9):
      Ableton devices use MIXED units depending on the parameter. Always
      read the `value_string` in the response (and the `min`/`max` from
      get_device_parameters) before assuming 0-1 semantics:

        - Auto Filter `Frequency`:      20-135 index (NOT normalized)
        - Auto Filter Legacy `LFO Amount`: 0-30 absolute (displays as %)
        - Auto Filter `Resonance`:      0-1.25 on legacy, 0-1 on AutoFilter2
        - Auto Filter `Env. Modulation`: -127..+127 on legacy
        - Compressor I, Dynamic Tube, Vocoder: pre-2010 units
        - EQ Three `Frequency Hi/Lo`:    50Hz-15kHz absolute
        - Wavetable `Osc 1 Pos`:         0-1 normalized ✓
        - Drift / Analog / Operator macros: 0-1 normalized ✓

      The `value_string` field in the response is the SOURCE OF TRUTH
      for what the user sees. Automation recipes that assume 0-1 will
      clamp on legacy devices. When in doubt, call
      get_device_parameters first to inspect min/max/is_quantized.
    """
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
    result = _get_ableton(ctx).send_command("load_device_by_uri", {
        "track_index": track_index,
        "uri": uri,
    })
    return _postflight_loaded_device(ctx, result)


@mcp.tool()
def move_device(
    ctx: Context,
    track_index: int,
    device_index: int,
    target_index: int,
    target_track_index: Optional[int] = None,
) -> dict:
    """Move a device to a new position on the same or different track.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks, -1000 for master."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    params: dict = {
        "track_index": track_index,
        "device_index": device_index,
        "target_index": target_index,
    }
    if target_track_index is not None:
        _validate_track_index(target_track_index)
        params["target_track_index"] = target_track_index
    return _get_ableton(ctx).send_command("move_device", params)


@mcp.tool()
def find_and_load_device(ctx: Context, track_index: int, device_name: str) -> dict:
    """Search the browser for a device by name and load it onto a track.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master."""
    _validate_track_index(track_index)
    if not device_name.strip():
        raise ValueError("device_name cannot be empty")

    # Guardrail: bare Drum Rack produces silence unless building programmatically (12.3+)
    if device_name.strip().lower() == "drum rack":
        raise ValueError(
            "Loading a bare 'Drum Rack' creates an empty rack that produces silence. "
            "Options: (1) search_browser(path='drums') to find a kit preset "
            "(e.g., '808 Core Kit'), then load with load_browser_item(). "
            "(2) On Live 12.3+: use insert_device('Drum Rack') + insert_rack_chain "
            "+ set_drum_chain_note to build a kit programmatically. "
            "(3) DS drum synths (DS Kick, DS Snare, DS HH) are self-contained."
        )

    result = _get_ableton(ctx).send_command("find_and_load_device", {
        "track_index": track_index,
        "device_name": device_name,
    })
    return _postflight_loaded_device(ctx, result)


@mcp.tool()
def insert_device(
    ctx: Context,
    track_index: int,
    device_name: str,
    position: int = -1,
    device_index: Optional[int] = None,
    chain_index: Optional[int] = None,
) -> dict:
    """Insert a native Live device by name — 10x faster than browser search (Live 12.3+).

    Only works for native devices (Reverb, Compressor, EQ Eight, Drift, etc.).
    For plugins, M4L devices, or presets, use find_and_load_device or load_browser_item.

    track_index:  0+ for regular tracks, -1/-2 for returns, -1000 for master
    device_name:  exact device name (e.g. 'Reverb', 'Auto Filter', 'Wavetable')
    position:     device chain position (0 = first, -1 = end of chain)
    device_index: required when inserting into a rack chain (identifies the rack)
    chain_index:  insert into this chain of a rack device (for building drum kits)

    Drum Rack construction workflow (12.3+):
    1. insert_device(track_index, 'Drum Rack')       — create empty rack
    2. insert_rack_chain(track_index, device_index)   — add chains
    3. set_drum_chain_note(chain_index, note=36)      — assign C1 (kick)
    4. insert_device(track_index, 'Simpler',          — add instrument
       device_index=rack_idx, chain_index=0)            into chain

    On Live < 12.3: returns an error suggesting find_and_load_device instead.
    """
    _validate_track_index(track_index)
    if not device_name.strip():
        raise ValueError("device_name cannot be empty")

    params = {
        "track_index": track_index,
        "device_name": device_name,
        "position": position,
    }
    if device_index is not None:
        params["device_index"] = device_index
    if chain_index is not None:
        if device_index is None:
            raise ValueError("device_index is required when chain_index is provided")
        _validate_device_index(device_index)
        _validate_chain_index(chain_index)
        params["chain_index"] = chain_index

    result = _get_ableton(ctx).send_command("insert_device", params)
    return _postflight_loaded_device(ctx, result)


@mcp.tool()
def insert_rack_chain(
    ctx: Context,
    track_index: int,
    device_index: int,
    position: int = -1,
) -> dict:
    """Insert a new chain into a Rack device — Instrument Rack, Audio Effect Rack, or Drum Rack (Live 12.3+).

    Use with insert_device + set_drum_chain_note to build Drum Racks from scratch:
    1. insert_device(track, 'Drum Rack') to create the rack
    2. insert_rack_chain(track, rack_device_index) to add chains
    3. set_drum_chain_note(chain_index=0, note=36) to assign C1 (kick)
    4. insert_device(track, 'Simpler', device_index=rack, chain_index=0) into chain

    track_index:  track containing the rack
    device_index: rack device index on the track
    position:     chain position (-1 = append to end)
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)

    return _get_ableton(ctx).send_command("insert_rack_chain", {
        "track_index": track_index,
        "device_index": device_index,
        "position": position,
    })


@mcp.tool()
def set_drum_chain_note(
    ctx: Context,
    track_index: int,
    device_index: int,
    chain_index: int,
    note: int,
) -> dict:
    """Set which MIDI note triggers a Drum Rack chain (Live 12.3+).

    Standard drum mapping:
    C1 (36) = Kick, D1 (38) = Snare, F#1 (42) = Closed HH,
    A#1 (46) = Open HH, C#2 (49) = Crash, D#2 (51) = Ride

    note: MIDI note 0-127, or -1 for 'All Notes'
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    _validate_chain_index(chain_index)
    if note < -1 or note > 127:
        raise ValueError("note must be -1 (All Notes) or 0-127")

    return _get_ableton(ctx).send_command("set_drum_chain_note", {
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
        "note": note,
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
    # Keep the active request context attached so analyzer error paths can
    # distinguish "device missing" from "bridge disconnected".
    setattr(cache, "_livepilot_ctx", ctx)
    return cache


def _require_analyzer(cache) -> None:
    if not cache.is_connected:
        ctx = getattr(cache, "_livepilot_ctx", None)
        try:
            track = (
                ctx.lifespan_context["ableton"].send_command("get_master_track")
                if ctx else {}
            )
        except Exception as exc:
            logger.debug("_require_analyzer failed: %s", exc)
            track = {}

        devices = track.get("devices", []) if isinstance(track, dict) else []
        analyzer_loaded = False
        for device in devices:
            normalized = " ".join(
                str(device.get("name") or "").replace("_", " ").replace("-", " ").lower().split()
            )
            if normalized == "livepilot analyzer":
                analyzer_loaded = True
                break

        if analyzer_loaded:
            holder = _identify_port_holder(9880)
            detail = (
                "LivePilot Analyzer is loaded on the master track, but its UDP bridge is not connected. "
            )
            if holder:
                detail += (
                    "UDP port 9880 is currently held by another LivePilot instance "
                    f"({holder}). Close the other client/server, then retry."
                )
            else:
                detail += "Reload the analyzer device or restart the MCP server."
            raise ValueError(detail)

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


# ── Rack Variations + Macro CRUD (Live 11+) ─────────────────────────────


@mcp.tool()
def get_rack_variations(ctx: Context, track_index: int, device_index: int) -> dict:
    """Get the Rack's variation count, currently selected variation index, and visible macro count (Live 11+).

    Variations are macro snapshots — store a scene of macro values, recall later.
    Returns {count, selected_index, visible_macro_count}. selected_index may be -1
    if no variation is currently selected. Errors if the device is not a Rack
    (Instrument/Audio Effect/Drum Rack).
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_rack_variations", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def store_rack_variation(ctx: Context, track_index: int, device_index: int) -> dict:
    """Store the Rack's current macro values as a new variation (Live 11+).

    Appends a new variation at the end of the list. Returns the new total
    {count, new_index} where new_index = count - 1.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("store_rack_variation", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def recall_rack_variation(
    ctx: Context,
    track_index: int,
    device_index: int,
    variation_index: int,
) -> dict:
    """Select and recall a stored Rack variation by index (Live 11+).

    Sets selected_variation_index then calls recall_selected_variation(),
    immediately pushing the stored macro values to the live Rack.
    Returns {selected_index}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if variation_index < 0:
        raise ValueError("variation_index must be >= 0")
    return _get_ableton(ctx).send_command("recall_rack_variation", {
        "track_index": track_index,
        "device_index": device_index,
        "variation_index": variation_index,
    })


@mcp.tool()
def delete_rack_variation(
    ctx: Context,
    track_index: int,
    device_index: int,
    variation_index: int,
) -> dict:
    """Delete a Rack variation by index (Live 11+).

    Selects the given index first then deletes it. Returns the new {count}
    after removal.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if variation_index < 0:
        raise ValueError("variation_index must be >= 0")
    return _get_ableton(ctx).send_command("delete_rack_variation", {
        "track_index": track_index,
        "device_index": device_index,
        "variation_index": variation_index,
    })


@mcp.tool()
def randomize_rack_macros(ctx: Context, track_index: int, device_index: int) -> dict:
    """Randomize the Rack's macro values using Live's built-in randomize dice (Live 11+).

    Does not store a variation — just scrambles the current macros. Combine
    with store_rack_variation to snapshot the random state.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("randomize_rack_macros", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def add_rack_macro(ctx: Context, track_index: int, device_index: int) -> dict:
    """Add one macro to a Rack, raising visible_macro_count by 1 (Live 11+).

    Maxes at 16 macros. Returns the new {visible_macro_count}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("add_rack_macro", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def remove_rack_macro(ctx: Context, track_index: int, device_index: int) -> dict:
    """Remove the last macro from a Rack, lowering visible_macro_count by 1 (Live 11+).

    Minimum is 1 macro. Returns the new {visible_macro_count}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("remove_rack_macro", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def set_rack_visible_macros(
    ctx: Context,
    track_index: int,
    device_index: int,
    count: int,
) -> dict:
    """Set the Rack's visible_macro_count directly (1-16, Live 11+).

    Faster than calling add_rack_macro/remove_rack_macro repeatedly to reach
    a target count. Returns the new {visible_macro_count}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if not 1 <= count <= 16:
        raise ValueError("count must be 1-16")
    return _get_ableton(ctx).send_command("set_rack_visible_macros", {
        "track_index": track_index,
        "device_index": device_index,
        "count": count,
    })
