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


def _normalize_batch_entry(entry: dict) -> dict:
    """Accept legacy 'name_or_index', aligned 'parameter_index'/'parameter_name',
    or the 'index'/'name' keys that `get_device_parameters` returns natively.

    BUG-F4 + BUG-2026-04-22#3: the sibling tools had inconsistent schemas.
    Callers writing code against set_device_parameter hit validation errors
    switching to batch_set_parameters. The 2026-04-22 bug report flagged
    that `get_device_parameters` returns entries with `"index": N` but
    `batch_set_parameters` rejected that key — forcing callers to rename
    it. We now accept every shape and normalize to the Remote Script's
    expected `{name_or_index, value}` so `get_device_parameters`'s output
    can be fed straight back in.
    """
    if "value" not in entry:
        raise ValueError("Each parameter entry must include 'value'")

    has_legacy = "name_or_index" in entry
    has_index = "parameter_index" in entry
    has_name = "parameter_name" in entry
    # BUG-2026-04-22#3 aliases
    has_short_index = "index" in entry
    has_short_name = "name" in entry

    specified = sum([
        has_legacy, has_index, has_name, has_short_index, has_short_name,
    ])
    if specified == 0:
        raise ValueError(
            "Each parameter entry must include exactly one of: "
            "parameter_name, parameter_index, name, index, or name_or_index"
        )
    if specified > 1:
        raise ValueError(
            "Each parameter entry must include exactly one of "
            "parameter_name, parameter_index, name, index, or name_or_index "
            "— not multiple"
        )

    if has_legacy:
        key = entry["name_or_index"]
    elif has_index:
        key = entry["parameter_index"]
    elif has_name:
        key = entry["parameter_name"]
    elif has_short_index:
        key = entry["index"]
    else:
        key = entry["name"]

    # BUG-audit-H3: match set_device_parameter's validation so negative
    # indices are rejected at the MCP layer rather than leaking through to
    # the Remote Script as unstructured IndexError.
    if isinstance(key, int) and key < 0:
        raise ValueError(
            "parameter_index must be >= 0 (got {})".format(key)
        )

    return {"name_or_index": key, "value": entry["value"]}


_SNAP_EPSILON = 1e-5


def _detect_snapped_params(
    requested: list[dict], response: dict,
) -> list[dict]:
    """Compare requested parameter values against Ableton's returned
    values; surface any that were silently snapped.

    BUG #4 fix (v1.20.2): quantized-enum params (e.g., Beat Repeat's
    "Gate" at 0/1/2/... integer enum) silently snap a caller's float
    request to the nearest step. Pre-fix, the response gave no signal —
    callers saw success with the snapped value hidden in `value_string`.

    Returns a list of {name, requested, actual, display_value} entries
    for params whose actual (returned) value differs from the requested
    value by more than _SNAP_EPSILON. String params are compared
    exactly. Integer params use int equality.

    Empty list when nothing snapped — callers can check
    ``result.get("snapped_params") == []`` as a go/no-go signal.
    """
    result_params = response.get("parameters") or []
    if not isinstance(result_params, list):
        return []

    # Build {key → requested_value} from the original caller input.
    # Accept any of the same schemas _normalize_batch_entry accepts.
    by_key: dict = {}
    for entry in requested:
        if not isinstance(entry, dict):
            continue
        for key_name in ("parameter_name", "name", "parameter_index",
                         "index", "name_or_index"):
            if key_name in entry:
                by_key[entry[key_name]] = entry.get("value")
                break

    snapped: list[dict] = []
    for rp in result_params:
        if not isinstance(rp, dict):
            continue
        name = rp.get("name")
        # Match by name first (most common), fall back to index
        requested_val = by_key.get(name)
        if requested_val is None and "index" in rp:
            requested_val = by_key.get(rp["index"])
        if requested_val is None:
            continue
        actual_val = rp.get("value")
        if actual_val is None:
            continue

        # Compare with type-appropriate tolerance. Numeric → epsilon;
        # other types → strict equality.
        try:
            req_f = float(requested_val)
            act_f = float(actual_val)
            did_snap = abs(req_f - act_f) > _SNAP_EPSILON
        except (TypeError, ValueError):
            did_snap = requested_val != actual_val

        if did_snap:
            snapped.append({
                "name": name,
                "requested": requested_val,
                "actual": actual_val,
                "display_value": rp.get("display_value"),
                "value_string": rp.get("value_string"),
            })

    return snapped


@mcp.tool()
def batch_set_parameters(
    ctx: Context,
    track_index: int,
    device_index: int,
    parameters: Any,
) -> dict:
    """Set multiple device parameters in one call.

    parameters: JSON array of objects. Each entry uses exactly one of:
      - {"parameter_index": N, "value": V}        (preferred, aligned with set_device_parameter)
      - {"parameter_name": "Dry/Wet", "value": V} (preferred)
      - {"name_or_index": X, "value": V}          (legacy, still accepted)

    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master.

    Response (v1.20.2+): the dict now includes a ``snapped_params`` list
    when quantized-enum parameters were silently snapped by Ableton
    (requested 0.3, received 0). Empty list means every requested value
    round-tripped within 1e-5 tolerance. Callers using this tool to
    drive deterministic state should inspect ``snapped_params`` before
    assuming success — see BUG #4 in the v1.20 live-test campaign for
    the motivating case (Beat Repeat Gate).
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    parameters_list = _ensure_list(parameters)
    if not parameters_list:
        raise ValueError("parameters list cannot be empty")
    normalized = [_normalize_batch_entry(e) for e in parameters_list]
    response = _get_ableton(ctx).send_command("batch_set_parameters", {
        "track_index": track_index,
        "device_index": device_index,
        "parameters": normalized,
    })
    if isinstance(response, dict):
        response["snapped_params"] = _detect_snapped_params(parameters_list, response)
    return response


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
def find_and_load_device(
    ctx: Context,
    track_index: int,
    device_name: str,
    allow_duplicate: bool = False,
) -> dict:
    """Search the browser for a device by name and load it onto a track.
    track_index: 0+ for regular tracks, -1/-2/... for return tracks (A/B/...), -1000 for master.

    allow_duplicate (default False): if a device with the same name is
    already on the track's chain, the default behavior is to NO-OP and
    return the existing device's location with `already_present: True`.
    Pass allow_duplicate=True to force a second instance (e.g., parallel
    processing chains where you genuinely want two of the same device)."""
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
        "allow_duplicate": allow_duplicate,
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
def rename_chain(
    ctx: Context,
    track_index: int,
    device_index: int,
    chain_index: int,
    name: str,
) -> dict:
    """Rename a chain inside any Rack device — Instrument, Audio Effect, or Drum (Live 12.3+).

    Works with Drum Racks (the primary use case — naming pads "Kick", "Snare",
    "Clap", etc.) as well as Instrument/Audio Effect Racks.

    track_index:  track containing the rack
    device_index: rack device index on the track
    chain_index:  0-based chain to rename
    name:         new chain name (non-empty; Live may truncate)
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    _validate_chain_index(chain_index)
    if not name or not name.strip():
        raise ValueError("name cannot be empty")
    return _get_ableton(ctx).send_command("set_chain_name", {
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
        "name": name.strip(),
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


# ── Simpler Slice CRUD (Live 11+) ───────────────────────────────────────


@mcp.tool()
def insert_simpler_slice(
    ctx: Context,
    track_index: int,
    device_index: int,
    time_samples: int,
) -> dict:
    """Insert a slice at a sample-frame position on a Simpler (Live 11+).

    time_samples is in raw sample frames (NOT beats, NOT seconds). Call
    get_simpler_slices first to see existing slice positions. The Simpler
    must be in Slice playback mode for slices to matter musically, but this
    tool does not force that — errors only if the device is not a Simpler
    or has no sample loaded.

    Returns {slice_count} after insertion.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if time_samples < 0:
        raise ValueError("time_samples must be >= 0")
    return _get_ableton(ctx).send_command("insert_simpler_slice", {
        "track_index": track_index,
        "device_index": device_index,
        "time_samples": time_samples,
    })


@mcp.tool()
def move_simpler_slice(
    ctx: Context,
    track_index: int,
    device_index: int,
    old_time_samples: int,
    new_time_samples: int,
) -> dict:
    """Move an existing slice from one sample-frame position to another (Live 11+).

    Both values are in raw sample frames. old_time_samples must match an
    existing slice exactly — use get_simpler_slices to read current
    positions. Returns {ok, old_time_samples, new_time_samples}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if old_time_samples < 0 or new_time_samples < 0:
        raise ValueError("time values must be >= 0")
    return _get_ableton(ctx).send_command("move_simpler_slice", {
        "track_index": track_index,
        "device_index": device_index,
        "old_time_samples": old_time_samples,
        "new_time_samples": new_time_samples,
    })


@mcp.tool()
def remove_simpler_slice(
    ctx: Context,
    track_index: int,
    device_index: int,
    time_samples: int,
) -> dict:
    """Remove a slice at an exact sample-frame position (Live 11+).

    time_samples must EXACTLY match an existing slice position. Read current
    positions with get_simpler_slices first. Returns {slice_count} after
    removal.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if time_samples < 0:
        raise ValueError("time_samples must be >= 0")
    return _get_ableton(ctx).send_command("remove_simpler_slice", {
        "track_index": track_index,
        "device_index": device_index,
        "time_samples": time_samples,
    })


@mcp.tool()
def clear_simpler_slices(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Remove all manual slices from the Simpler (Live 11+).

    Clears the slice list outright. Combine with reset_simpler_slices or
    import_slices_from_onsets to regenerate. Returns {slice_count: 0}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("clear_simpler_slices", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def reset_simpler_slices(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Reset the Simpler's slices to Live's default detection (Live 11+).

    Re-runs detection under the CURRENT slicing_style and sensitivity. Use
    import_slices_from_onsets instead if you want to force Transient mode
    AND set sensitivity in one call. Returns the resulting {slice_count}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("reset_simpler_slices", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def import_slices_from_onsets(
    ctx: Context,
    track_index: int,
    device_index: int,
    sensitivity: float = 0.5,
) -> dict:
    """Force Transient slicing mode, set sensitivity, and re-detect (Live 11+).

    Writes slicing_style=Transient and slicing_sensitivity, then calls
    reset_slices(). sensitivity must be 0.0-1.0; 0.5 is moderate, higher
    produces more slices. Returns {slice_count, sensitivity}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if not 0.0 <= sensitivity <= 1.0:
        raise ValueError("sensitivity must be 0.0-1.0")
    return _get_ableton(ctx).send_command("import_slices_from_onsets", {
        "track_index": track_index,
        "device_index": device_index,
        "sensitivity": sensitivity,
    })


# ── Wavetable modulation matrix (Live 11+) ──────────────────────────────


@mcp.tool()
def get_wavetable_mod_targets(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Enumerate visible modulation target parameter names on a Wavetable (Live 11+).

    Returns {targets: [...]} — the list depends on the current patch
    configuration (e.g. which oscillators are active). Feed these strings
    into add_wavetable_mod_route / set_wavetable_mod_amount as the target
    argument.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_wavetable_mod_targets", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def add_wavetable_mod_route(
    ctx: Context,
    track_index: int,
    device_index: int,
    source: str,
    target: str,
) -> dict:
    """Create a modulation routing on a Wavetable device (Live 11+).

    source must be one of: "Env 2", "Env 3", "LFO 1", "LFO 2",
    "MIDI Key", "MIDI Velocity", "MIDI Aftertouch", "MIDI Pitchbend",
    "Macro 1".."Macro 8". target must be a name from
    get_wavetable_mod_targets — valid targets depend on the current patch.
    Returns {source, target, actual_target} where actual_target is the
    parameter name Live resolved the routing to.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("add_wavetable_mod_route", {
        "track_index": track_index,
        "device_index": device_index,
        "source": source,
        "target": target,
    })


@mcp.tool()
def set_wavetable_mod_amount(
    ctx: Context,
    track_index: int,
    device_index: int,
    source: str,
    target: str,
    amount: float,
) -> dict:
    """Set the modulation amount for a Wavetable source→target routing (Live 11+).

    amount is bipolar: -1.0 to 1.0. 0.0 effectively disables the routing.
    source and target use the same names documented on
    add_wavetable_mod_route. Returns {source, target, amount}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if not -1.0 <= amount <= 1.0:
        raise ValueError("amount must be -1.0 to 1.0")
    return _get_ableton(ctx).send_command("set_wavetable_mod_amount", {
        "track_index": track_index,
        "device_index": device_index,
        "source": source,
        "target": target,
        "amount": amount,
    })


@mcp.tool()
def get_wavetable_mod_amount(
    ctx: Context,
    track_index: int,
    device_index: int,
    source: str,
    target: str,
) -> dict:
    """Read the current modulation amount for a Wavetable source→target routing (Live 11+).

    Returns {source, target, amount, actual_target}. amount is -1.0 to 1.0.
    actual_target is the parameter name Live resolved the routing to — use
    it to confirm the routing went where you expected.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_wavetable_mod_amount", {
        "track_index": track_index,
        "device_index": device_index,
        "source": source,
        "target": target,
    })


@mcp.tool()
def get_wavetable_mod_matrix(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Dump all non-zero modulation routings on a Wavetable device (Live 11+).

    Iterates every source × visible target and returns any routing with a
    non-zero amount. O(sources × targets) but safe — useful to audit a
    patch or snapshot its modulation state. Returns
    {routings: [{source, target, amount}, ...]}.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_wavetable_mod_matrix", {
        "track_index": track_index,
        "device_index": device_index,
    })


# ── Device A/B compare (Live 12.3+) ─────────────────────────────────────


@mcp.tool()
def get_device_ab_state(ctx: Context, track_index: int, device_index: int) -> dict:
    """Read a device's A/B compare state (Live 12.3+).

    Returns current_state ('A'|'B'|'unknown') and has_b (bool).
    If the LOM doesn't expose A/B attributes, returns 'unknown' with
    a 'note' field explaining the limitation.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_device_ab_state",
        {"track_index": track_index, "device_index": device_index})


@mcp.tool()
def toggle_device_ab(ctx: Context, track_index: int, device_index: int) -> dict:
    """Swap a device's A/B state (Live 12.3+)."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("toggle_device_ab",
        {"track_index": track_index, "device_index": device_index})


@mcp.tool()
def copy_device_state(
    ctx: Context,
    track_index: int,
    device_index: int,
    direction: str,
) -> dict:
    """Copy one A/B state to the other (Live 12.3+).

    direction: 'a_to_b' or 'b_to_a'.
    """
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if direction not in ("a_to_b", "b_to_a"):
        raise ValueError("direction must be 'a_to_b' or 'b_to_a'")
    return _get_ableton(ctx).send_command("copy_device_state",
        {"track_index": track_index, "device_index": device_index,
         "direction": direction})
