"""Automation MCP tools — clip envelope CRUD + intelligent curve generation.

10 tools for writing, reading, and generating automation curves on session clips
and Arrangement record passes.
Combines the clip automation handlers (Remote Script) with the curve generation
engine (curves.py) for musically intelligent automation.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from typing import Any, Optional

from fastmcp import Context
from pydantic import BaseModel, Field

from ..curves import generate_curve, generate_from_recipe, list_recipes
from ..server import mcp

logger = logging.getLogger(__name__)


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _ensure_list(v: Any) -> list:
    if isinstance(v, str):
        import json

        try:
            return json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in parameter: {exc}") from exc
    if isinstance(v, list):
        normalized = []
        for item in v:
            if isinstance(item, BaseModel):
                normalized.append(item.model_dump(exclude_none=True))
            else:
                normalized.append(item)
        return normalized
    return [v]


class AutomationPoint(BaseModel):
    time: float
    value: float
    duration: Optional[float] = Field(default=None, ge=0.0)


def _as_tool_fn(tool: Any):
    return getattr(tool, "fn", tool)


async def _call_maybe_async(fn: Any, *args: Any, **kwargs: Any) -> Any:
    result = _as_tool_fn(fn)(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _normalize_realtime_points(points: list[AutomationPoint] | str) -> list[dict]:
    points_list = _ensure_list(points)
    if not points_list:
        raise ValueError("points list cannot be empty")

    normalized: list[dict] = []
    for i, point in enumerate(points_list):
        if isinstance(point, BaseModel):
            point = point.model_dump(exclude_none=True)
        if not isinstance(point, dict):
            raise ValueError(f"points[{i}] must be an object")
        if "time" not in point or "value" not in point:
            raise ValueError(f"points[{i}] must include time and value")
        time_value = float(point["time"])
        if time_value < 0:
            raise ValueError(f"points[{i}].time must be >= 0")
        normalized.append({
            "time": time_value,
            "value": float(point["value"]),
        })
    return sorted(normalized, key=lambda p: p["time"])


def _find_automation_param(state: Optional[dict], parameter_index: int) -> Optional[dict]:
    if not isinstance(state, dict):
        return None
    for item in state.get("automated_params") or []:
        try:
            if int(item.get("index")) == int(parameter_index):
                return item
        except (TypeError, ValueError):
            continue
    return None


async def _get_ready_m4l_bridge(ctx: Context) -> tuple[Any, list[str]]:
    """Return a connected M4L bridge, loading/reconnecting analyzer if possible."""
    warnings: list[str] = []
    try:
        from .analyzer import ensure_analyzer_on_master, reconnect_bridge
        from ._analyzer_engine import _get_m4l, _get_spectral, _require_analyzer
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"M4L bridge helpers unavailable: {exc}") from exc

    try:
        ensure_result = await _call_maybe_async(ensure_analyzer_on_master, ctx)
        if isinstance(ensure_result, dict):
            status = ensure_result.get("status")
            if status not in ("already_loaded", "loaded"):
                warnings.append(f"ensure_analyzer_on_master returned {status}: {ensure_result}")
            if ensure_result.get("warning"):
                warnings.append(str(ensure_result["warning"]))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"ensure_analyzer_on_master failed: {exc}")

    cache = _get_spectral(ctx)
    if not cache.is_connected:
        try:
            reconnect_result = await _call_maybe_async(reconnect_bridge, ctx)
            if isinstance(reconnect_result, dict) and not reconnect_result.get("ok", False):
                warnings.append(f"reconnect_bridge failed: {reconnect_result}")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"reconnect_bridge failed: {exc}")

    bridge = _get_m4l(ctx)
    if cache.is_connected:
        return bridge, warnings

    try:
        ping_result = await bridge.send_command("ping", timeout=1.5)
        if isinstance(ping_result, dict) and not ping_result.get("error"):
            warnings.append(
                "analyzer spectral cache is stale, but the M4L command bridge responded"
            )
            return bridge, warnings
        warnings.append(f"M4L command bridge ping failed: {ping_result}")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"M4L command bridge ping failed: {exc}")

    _require_analyzer(cache)
    return bridge, warnings


async def _read_automation_state(
    ctx: Context,
    track_index: int,
    device_index: int,
    parameter_index: Optional[int] = None,
) -> tuple[Optional[dict], list[str]]:
    """Read device automation state via the M4L bridge.

    Returns (state, warnings). Loading/reconnect attempts are best-effort so
    the caller can decide whether missing verification is fatal.
    """
    warnings: list[str] = []
    try:
        from .analyzer import (
            ensure_analyzer_on_master,
            get_automation_state,
            reconnect_bridge,
        )
    except Exception as exc:  # noqa: BLE001
        return None, [f"automation verification unavailable: {exc}"]

    try:
        ensure_result = await _call_maybe_async(ensure_analyzer_on_master, ctx)
        if isinstance(ensure_result, dict):
            status = ensure_result.get("status")
            if status not in ("already_loaded", "loaded"):
                warnings.append(f"ensure_analyzer_on_master returned {status}: {ensure_result}")
            if ensure_result.get("warning"):
                warnings.append(str(ensure_result["warning"]))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"ensure_analyzer_on_master failed: {exc}")

    if parameter_index is not None:
        try:
            from ._analyzer_engine import _get_m4l

            bridge = _get_m4l(ctx)
            state = await bridge.send_command(
                "get_auto_state",
                track_index,
                device_index,
                int(parameter_index),
                timeout=10.0,
            )
            if isinstance(state, dict) and state.get("error"):
                warnings.append(f"targeted get_auto_state failed: {state}")
            else:
                warnings.append("read target automation state via direct M4L parameter probe")
                return state, warnings
        except Exception as target_exc:  # noqa: BLE001
            warnings.append(f"targeted get_auto_state failed: {target_exc}")

    try:
        state = await _call_maybe_async(
            get_automation_state,
            ctx,
            track_index=track_index,
            device_index=device_index,
        )
        return state, warnings
    except Exception as first_exc:  # noqa: BLE001
        warnings.append(f"get_automation_state failed: {first_exc}")

    try:
        reconnect_result = await _call_maybe_async(reconnect_bridge, ctx)
        if isinstance(reconnect_result, dict) and not reconnect_result.get("ok", False):
            warnings.append(f"reconnect_bridge failed: {reconnect_result}")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"reconnect_bridge failed: {exc}")
        return None, warnings

    try:
        state = await _call_maybe_async(
            get_automation_state,
            ctx,
            track_index=track_index,
            device_index=device_index,
        )
        return state, warnings
    except Exception as second_exc:  # noqa: BLE001
        warnings.append(f"get_automation_state retry failed: {second_exc}")

    try:
        from ._analyzer_engine import _get_m4l

        bridge = _get_m4l(ctx)
        state = await bridge.send_command(
            "get_auto_state",
            track_index,
            device_index,
            *([] if parameter_index is None else [int(parameter_index)]),
            timeout=10.0,
        )
        if isinstance(state, dict) and state.get("error"):
            warnings.append(f"direct get_auto_state failed: {state}")
            return None, warnings
        warnings.append(
            "read automation state via direct M4L command bridge after stale spectral gate"
        )
        return state, warnings
    except Exception as bridge_exc:  # noqa: BLE001
        warnings.append(f"direct get_auto_state failed: {bridge_exc}")
        return None, warnings


@mcp.tool()
def get_clip_automation(
    ctx: Context,
    track_index: int,
    clip_index: int,
) -> dict:
    """List all automation envelopes on a session clip.

    Returns which parameters have automation, including device name,
    parameter name, and type (mixer/send/device). Use this to see
    what's already automated before writing new curves.
    """
    if track_index < -99:
        raise ValueError(
            "track_index must be >= 0 for regular tracks, "
            "or -1..-99 for return tracks (-1=A, -2=B)"
        )
    if clip_index < 0:
        raise ValueError("clip_index must be >= 0")
    return _get_ableton(ctx).send_command("get_clip_automation", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def set_clip_automation(
    ctx: Context,
    track_index: int,
    clip_index: int,
    parameter_type: str,
    points: list[AutomationPoint] | str,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
) -> dict:
    """Write automation points to a session clip envelope.

    parameter_type: "device", "volume", "panning", or "send"
    points: [{time, value, duration?}] — time relative to clip start (beats)
    values: 0.0-1.0 normalized (or parameter's actual min/max range)

    For device params: provide device_index + parameter_index.
    For sends: provide send_index (0=A, 1=B, etc).

    Tip: Use apply_automation_shape to generate points from curves/recipes
    instead of calculating points manually.
    """
    if track_index < -99:
        raise ValueError(
            "track_index must be >= 0 for regular tracks, "
            "or -1..-99 for return tracks (-1=A, -2=B)"
        )
    if clip_index < 0:
        raise ValueError("clip_index must be >= 0")
    if parameter_type not in ("device", "volume", "panning", "send"):
        raise ValueError("parameter_type must be 'device', 'volume', 'panning', or 'send'")
    if parameter_type == "device":
        if device_index is None or parameter_index is None:
            raise ValueError("device_index and parameter_index required for parameter_type='device'")
    if parameter_type == "send" and send_index is None:
        raise ValueError("send_index required for parameter_type='send'")
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_type": parameter_type,
        "points": _ensure_list(points),
    }
    if device_index is not None:
        params["device_index"] = device_index
    if parameter_index is not None:
        params["parameter_index"] = parameter_index
    if send_index is not None:
        params["send_index"] = send_index
    return _get_ableton(ctx).send_command("set_clip_automation", params)


@mcp.tool()
def clear_clip_automation(
    ctx: Context,
    track_index: int,
    clip_index: int,
    parameter_type: Optional[str] = None,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
) -> dict:
    """Clear automation envelopes from a session clip.

    If parameter_type is omitted, clears ALL envelopes.
    If provided, clears only that parameter's envelope.
    """
    if track_index < -99:
        raise ValueError(
            "track_index must be >= 0 for regular tracks, "
            "or -1..-99 for return tracks (-1=A, -2=B)"
        )
    if clip_index < 0:
        raise ValueError("clip_index must be >= 0")
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
    }
    if parameter_type is not None:
        if parameter_type not in ("device", "volume", "panning", "send"):
            raise ValueError("parameter_type must be 'device', 'volume', 'panning', or 'send'")
        if parameter_type == "device":
            if device_index is None or parameter_index is None:
                raise ValueError("device_index and parameter_index required for parameter_type='device'")
        if parameter_type == "send" and send_index is None:
            raise ValueError("send_index required for parameter_type='send'")
        params["parameter_type"] = parameter_type
    if device_index is not None:
        params["device_index"] = device_index
    if parameter_index is not None:
        params["parameter_index"] = parameter_index
    if send_index is not None:
        params["send_index"] = send_index
    return _get_ableton(ctx).send_command("clear_clip_automation", params)


@mcp.tool()
def apply_automation_shape(
    ctx: Context,
    track_index: int,
    clip_index: int,
    parameter_type: str,
    curve_type: str,
    duration: float = 4.0,
    density: int = 16,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
    start: float = 0.0,
    end: float = 1.0,
    center: float = 0.5,
    amplitude: float = 0.5,
    frequency: float = 1.0,
    phase: float = 0.0,
    peak: float = 1.0,
    decay: float = 4.0,
    low: float = 0.0,
    high: float = 1.0,
    factor: float = 3.0,
    invert: bool = False,
    time_offset: float = 0.0,
    # Steps params
    values: Optional[list[float]] = None,
    # Euclidean params
    hits: int = 5,
    steps: int = 16,
    # Organic params
    seed: float = 0.0,
    drift: float = 0.0,
    volatility: float = 0.1,
    damping: float = 0.15,
    stiffness: float = 8.0,
    # Bezier params
    control1: float = 0.0,
    control2: float = 1.0,
    control1_time: float = 0.33,
    control2_time: float = 0.66,
    # Easing params
    easing_type: str = "ease_out",
    # Stochastic params
    narrowing: float = 0.5,
) -> dict:
    """Generate and apply an automation curve to a session clip.

    Combines curve generation with clip automation writing in one call.

    curve_type: linear, exponential, logarithmic, s_curve, sine,
                sawtooth, spike, square, steps, perlin, brownian,
                spring, bezier, easing, euclidean, stochastic
    duration: curve length in beats
    density: number of automation points
    time_offset: shift the entire curve forward by N beats

    Curve-specific params:
    - linear/exp/log: start, end, factor (steepness 2-6)
    - sine: center, amplitude, frequency, phase
    - sawtooth: start, end, frequency (resets per duration)
    - spike: peak, decay (higher = faster)
    - square: low, high, frequency
    - s_curve: start, end

    Musical guidance:
    - Filter sweeps: use exponential (perceptually even)
    - Volume fades: use logarithmic (matches ear's response)
    - Crossfades: use s_curve (natural acceleration/deceleration)
    - Pumping: use sawtooth with frequency matching beat divisions
    - Throws: use spike with short duration (1-2 beats)
    - Tremolo/pan: use sine with frequency in musical divisions
    """
    # Validate indices and parameter_type (same rules as set_clip_automation)
    if track_index < -99:
        raise ValueError(
            "track_index must be >= 0 for regular tracks, "
            "or -1..-99 for return tracks (-1=A, -2=B)"
        )
    if clip_index < 0:
        raise ValueError("clip_index must be >= 0")
    if parameter_type not in ("device", "volume", "panning", "send"):
        raise ValueError("parameter_type must be 'device', 'volume', 'panning', or 'send'")
    if parameter_type == "device":
        if device_index is None or parameter_index is None:
            raise ValueError("device_index and parameter_index required for parameter_type='device'")
    if parameter_type == "send" and send_index is None:
        raise ValueError("send_index required for parameter_type='send'")

    # Generate the curve
    points = generate_curve(
        curve_type=curve_type,
        duration=duration,
        density=density,
        start=start, end=end,
        center=center, amplitude=amplitude,
        frequency=frequency, phase=phase,
        peak=peak, decay=decay,
        low=low, high=high,
        factor=factor,
        invert=invert,
        values=values or [],
        hits=hits, steps=steps,
        seed=seed, drift=drift, volatility=volatility,
        damping=damping, stiffness=stiffness,
        control1=control1, control2=control2,
        control1_time=control1_time, control2_time=control2_time,
        easing_type=easing_type,
        narrowing=narrowing,
    )

    # Apply time offset
    if time_offset > 0:
        for p in points:
            p["time"] += time_offset

    # Write to clip
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

    result = _get_ableton(ctx).send_command("set_clip_automation", params)
    result["curve_type"] = curve_type
    result["curve_points"] = len(points)
    return result


@mcp.tool()
def apply_automation_recipe(
    ctx: Context,
    track_index: int,
    clip_index: int,
    parameter_type: str,
    recipe: str,
    duration: float = 4.0,
    density: int = 16,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
    time_offset: float = 0.0,
) -> dict:
    """Apply a named automation recipe to a session clip.

    Recipes are predefined curve shapes for common production techniques.
    Use get_automation_recipes to list all available recipes.

    Available recipes:
    - filter_sweep_up: LP filter opening (exponential, 8-32 bars)
    - filter_sweep_down: LP filter closing (logarithmic, 4-16 bars)
    - dub_throw: send spike for reverb/delay throw (1-2 beats)
    - tape_stop: pitch dropping to zero (0.5-2 beats)
    - build_rise: tension build on HP filter + volume (8-32 bars)
    - sidechain_pump: volume ducking per beat (sawtooth, 1 beat loop)
    - fade_in / fade_out: perceptually smooth volume fades
    - tremolo: periodic volume oscillation
    - auto_pan: stereo movement via pan sine
    - stutter: rapid on/off gating
    - breathing: subtle filter movement (acoustic instrument feel)
    - washout: reverb/delay feedback increasing
    - vinyl_crackle: slow bit reduction movement
    - stereo_narrow: collapse to mono before drop
    """
    # Validate indices and parameter_type (same rules as set_clip_automation)
    if track_index < -99:
        raise ValueError(
            "track_index must be >= 0 for regular tracks, "
            "or -1..-99 for return tracks (-1=A, -2=B)"
        )
    if clip_index < 0:
        raise ValueError("clip_index must be >= 0")
    if parameter_type not in ("device", "volume", "panning", "send"):
        raise ValueError("parameter_type must be 'device', 'volume', 'panning', or 'send'")
    if parameter_type == "device":
        if device_index is None or parameter_index is None:
            raise ValueError("device_index and parameter_index required for parameter_type='device'")
    if parameter_type == "send" and send_index is None:
        raise ValueError("send_index required for parameter_type='send'")

    points = generate_from_recipe(recipe, duration=duration, density=density)

    # Scale recipe's 0.0-1.0 curves to the parameter's actual native range.
    # Without this, a "0.3" center on a 20-135 range parameter writes 0.3
    # literally instead of scaling to the 20-135 range — killing the signal.
    if parameter_type == "device" and device_index is not None and parameter_index is not None:
        try:
            dev_info = _get_ableton(ctx).send_command("get_device_parameters", {
                "track_index": track_index,
                "device_index": device_index,
            })
            params_list = dev_info.get("parameters", [])
            if parameter_index < len(params_list):
                p_info = params_list[parameter_index]
                p_min = float(p_info.get("min", 0))
                p_max = float(p_info.get("max", 1))
                # Only scale if the range is NOT already 0-1
                if abs(p_max - p_min) > 1.5 or p_min < -0.5:
                    for pt in points:
                        pt["value"] = p_min + pt["value"] * (p_max - p_min)
        except Exception as exc:
            logger.debug("apply_automation_recipe failed: %s", exc)
            pass  # Fail open — write values as-is if we can't read the range

    # Safety clamp: auto_pan amplitude should be limited to avoid full L/R swing
    if recipe == "auto_pan" and parameter_type == "panning":
        for pt in points:
            pt["value"] = max(-0.6, min(0.6, pt["value"]))

    if time_offset > 0:
        for p in points:
            p["time"] += time_offset

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

    result = _get_ableton(ctx).send_command("set_clip_automation", params)
    result["recipe"] = recipe
    result["curve_points"] = len(points)
    return result


@mcp.tool()
def get_automation_recipes(ctx: Context) -> dict:
    """List all available automation recipes with descriptions.

    Each recipe includes: curve type, description, typical duration,
    and recommended target parameter. Use apply_automation_recipe
    to apply any recipe to a clip.
    """
    return {"recipes": list_recipes()}


@mcp.tool()
def generate_automation_curve(
    ctx: Context,
    curve_type: str,
    duration: float = 4.0,
    density: int = 16,
    start: float = 0.0,
    end: float = 1.0,
    center: float = 0.5,
    amplitude: float = 0.5,
    frequency: float = 1.0,
    phase: float = 0.0,
    peak: float = 1.0,
    decay: float = 4.0,
    low: float = 0.0,
    high: float = 1.0,
    factor: float = 3.0,
    invert: bool = False,
    # Steps params
    values: Optional[list[float]] = None,
    # Euclidean params
    hits: int = 5,
    steps: int = 16,
    # Organic params
    seed: float = 0.0,
    drift: float = 0.0,
    volatility: float = 0.1,
    damping: float = 0.15,
    stiffness: float = 8.0,
    # Bezier params
    control1: float = 0.0,
    control2: float = 1.0,
    control1_time: float = 0.33,
    control2_time: float = 0.66,
    # Easing params
    easing_type: str = "ease_out",
    # Stochastic params
    narrowing: float = 0.5,
) -> dict:
    """Generate automation curve points WITHOUT writing them.

    Returns the points array for preview/inspection. Use this to see
    what a curve looks like before committing it to a clip.
    Pass the returned points to set_clip_automation or
    set_arrangement_automation to write them.
    """
    points = generate_curve(
        curve_type=curve_type,
        duration=duration,
        density=density,
        start=start, end=end,
        center=center, amplitude=amplitude,
        frequency=frequency, phase=phase,
        peak=peak, decay=decay,
        low=low, high=high,
        factor=factor,
        invert=invert,
        values=values or [],
        hits=hits, steps=steps,
        seed=seed, drift=drift, volatility=volatility,
        damping=damping, stiffness=stiffness,
        control1=control1, control2=control2,
        control1_time=control1_time, control2_time=control2_time,
        easing_type=easing_type,
        narrowing=narrowing,
    )
    return {
        "curve_type": curve_type,
        "duration": duration,
        "point_count": len(points),
        "points": points,
        "value_range": {
            "min": min(p["value"] for p in points) if points else 0,
            "max": max(p["value"] for p in points) if points else 0,
        },
    }


@mcp.tool()
def analyze_for_automation(
    ctx: Context,
    track_index: int,
) -> dict:
    """Analyze a track's spectrum and suggest automation targets.

    Reads the track's current spectral data and device chain,
    then suggests which parameters would benefit from automation
    based on the frequency content and device types present.

    Requires LivePilot Analyzer on master track and audio playing.
    """
    ableton = _get_ableton(ctx)

    # Get track devices
    track_info = ableton.send_command("get_track_info", {
        "track_index": track_index,
    })

    # Get current spectrum
    spectral = ctx.lifespan_context.get("spectral")
    spectrum = {}
    if spectral and spectral.is_connected:
        data = spectral.get("spectrum")
        spectrum = data["value"] if data else {}

    # Get meter level
    meters = ableton.send_command("get_track_meters", {
        "track_index": track_index,
    })

    devices = track_info.get("devices", [])
    suggestions = []

    # Analyze based on device types and spectrum
    for i, dev in enumerate(devices):
        dev_name = dev.get("name", "").lower()
        dev_class = dev.get("class_name", "").lower()

        # Filter devices — suggest sweep automation
        if any(kw in dev_class for kw in ["autofilter", "eq8", "filter"]):
            suggestions.append({
                "device_index": i,
                "device_name": dev.get("name"),
                "suggestion": "filter_sweep",
                "reason": "Filter detected — automate cutoff for movement",
                "recipe": "filter_sweep_up",
            })

        # Reverb/delay — suggest send throws or washout
        if any(kw in dev_class for kw in ["reverb", "delay", "hybrid", "echo"]):
            suggestions.append({
                "device_index": i,
                "device_name": dev.get("name"),
                "suggestion": "spatial_automation",
                "reason": "Space effect — automate mix/decay for depth changes",
                "recipe": "washout",
            })

        # Distortion — suggest drive automation
        if any(kw in dev_class for kw in ["saturator", "overdrive", "pedal", "amp"]):
            suggestions.append({
                "device_index": i,
                "device_name": dev.get("name"),
                "suggestion": "drive_automation",
                "reason": "Distortion — automate drive for dynamic saturation",
                "recipe": "breathing",
            })

        # Synths — suggest wavetable/macro automation
        if any(kw in dev_class for kw in ["wavetable", "drift", "analog", "operator"]):
            suggestions.append({
                "device_index": i,
                "device_name": dev.get("name"),
                "suggestion": "timbre_evolution",
                "reason": "Synth — automate timbre params for evolving sound",
                "recipe": "breathing",
            })

    # Mixer suggestions based on spectrum
    if spectrum:
        sub = spectrum.get("sub", 0)
        if sub > 0.15:
            suggestions.append({
                "suggestion": "high_pass_automation",
                "reason": "Heavy sub content (%.2f) — HP filter sweep for builds" % sub,
                "recipe": "build_rise",
            })

    # Always suggest send automation for spatial depth
    suggestions.append({
        "suggestion": "send_throws",
        "reason": "Reverb/delay sends — automate for dub throws and spatial variation",
        "recipe": "dub_throw",
    })

    return {
        "track_index": track_index,
        "track_name": track_info.get("name", ""),
        "device_count": len(devices),
        "current_level": (meters.get("tracks") or [{}])[0].get("level", 0) if meters.get("tracks") else 0,
        "spectrum": spectrum,
        "suggestions": suggestions,
    }


# ── Real-time Arrangement automation recorder ──────────────────────────────

@mcp.tool()
async def record_parameter_automation_realtime(
    ctx: Context,
    track_index: int,
    device_index: int,
    points: list[AutomationPoint] | str,
    start_beat: float,
    duration_beats: Optional[float] = None,
    parameter_index: Optional[int] = None,
    parameter_name: Optional[str] = None,
    record_arm_track_index: Optional[int] = None,
    overwrite_existing: bool = False,
    require_verification: bool = True,
    restore_transport: bool = True,
    guard_previous_value: bool = True,
    guard_beats: float = 0.25,
    pre_roll_beats: float = 8.0,
) -> dict:
    """Record Arrangement automation by moving a device parameter in real time.

    This clean workaround does not create or fire a Session View automation
    clip. It enables Arrangement Record + Automation Arm, moves the target
    device parameter at the requested beat offsets, then lets Ableton write
    the native Arrangement automation lane.

    ``points`` are relative to ``start_beat``:
      [{"time": 0.0, "value": 0.2}, {"time": 4.0, "value": 0.8}]

    By default the tool creates a temporary MIDI track as the record trigger,
    arms only that track, deletes it afterward, restores prior arm/transport
    state, and verifies the target parameter has automation. It also records
    a short guard point before ``start_beat`` at the parameter's pre-pass value
    so the first requested value is not held backward across earlier timeline.
    """
    if track_index < 0:
        raise ValueError("track_index must be >= 0 for Arrangement track automation")
    if device_index < 0:
        raise ValueError("device_index must be >= 0")
    if parameter_index is None and not parameter_name:
        raise ValueError("parameter_index or parameter_name is required")
    if parameter_index is not None and parameter_index < 0:
        raise ValueError("parameter_index must be >= 0")
    if start_beat < 0:
        raise ValueError("start_beat must be >= 0")
    if record_arm_track_index is not None and record_arm_track_index < 0:
        raise ValueError("record_arm_track_index must be >= 0 when provided")

    normalized_points = _normalize_realtime_points(points)
    last_point_time = normalized_points[-1]["time"]
    if duration_beats is None:
        duration_beats = max(0.25, last_point_time + 0.25)
    duration_beats = float(duration_beats)
    if duration_beats <= 0:
        raise ValueError("duration_beats must be > 0")
    if duration_beats < last_point_time:
        raise ValueError("duration_beats must be >= the last point time")
    guard_beats = float(guard_beats)
    if guard_beats <= 0:
        raise ValueError("guard_beats must be > 0")
    pre_roll_beats = float(pre_roll_beats)
    if pre_roll_beats < 0:
        raise ValueError("pre_roll_beats must be >= 0")

    ableton = _get_ableton(ctx)
    warnings: list[str] = []
    cleanup: dict[str, Any] = {
        "stop_recording": None,
        "stop_playback": None,
        "deleted_temp_track": False,
        "restored_arms": [],
        "restore_transport": None,
        "warnings": [],
    }
    executed_points: list[dict] = []
    temp_track_index: Optional[int] = None
    trigger_track_index: Optional[int] = record_arm_track_index
    record_attempted = False
    record_started = False
    phase = "preflight"

    before_session = ableton.send_command("get_session_info", {}) or {}
    before_recording = ableton.send_command("get_recording_state", {}) or {}
    before_position = float(before_session.get("current_song_time") or 0.0)
    before_was_playing = bool(before_session.get("is_playing", False))
    before_arms: dict[int, bool] = {}
    for track in before_session.get("tracks") or []:
        if isinstance(track, dict) and isinstance(track.get("arm"), bool):
            before_arms[int(track["index"])] = bool(track["arm"])

    parameter_info = ableton.send_command("get_device_parameters", {
        "track_index": track_index,
        "device_index": device_index,
    }) or {}
    device_parameters = parameter_info.get("parameters") or []
    target_parameter: Optional[dict] = None

    if parameter_index is not None:
        for parameter in device_parameters:
            if int(parameter.get("index", -1)) == int(parameter_index):
                target_parameter = parameter
                break
        if target_parameter is None:
            raise ValueError(f"parameter_index {parameter_index} not found on device {device_index}")
    else:
        assert parameter_name is not None
        for parameter in device_parameters:
            if str(parameter.get("name")) == parameter_name:
                target_parameter = parameter
                break
        if target_parameter is None:
            lowered = parameter_name.lower()
            for parameter in device_parameters:
                if str(parameter.get("name")).lower() == lowered:
                    target_parameter = parameter
                    break
        if target_parameter is None:
            available = [str(p.get("name")) for p in device_parameters[:20]]
            raise ValueError(
                f"parameter_name '{parameter_name}' not found on device {device_index}. "
                f"Available (first 20): {', '.join(available)}"
            )
        parameter_index = int(target_parameter["index"])

    parameter_min = float(target_parameter.get("min", float("-inf")))
    parameter_max = float(target_parameter.get("max", float("inf")))
    target_parameter_before_value = float(target_parameter.get("value", 0.0))
    for point in normalized_points:
        value = float(point["value"])
        if value < parameter_min or value > parameter_max:
            raise ValueError(
                f"point value {value} is outside parameter range "
                f"{parameter_min}..{parameter_max}"
            )

    record_start_beat = float(start_beat)
    record_duration_beats = duration_beats
    drive_points = [dict(point) for point in normalized_points]
    guard_point: Optional[dict] = None
    if guard_previous_value and start_beat > 0:
        actual_guard_beats = min(guard_beats, float(start_beat))
        record_start_beat = float(start_beat) - actual_guard_beats
        record_duration_beats = duration_beats + actual_guard_beats
        guard_point = {
            "time": 0.0,
            "value": target_parameter_before_value,
            "guard": True,
        }
        drive_points = [guard_point] + [
            {
                **dict(point),
                "time": float(point["time"]) + actual_guard_beats,
                "requested_time": float(point["time"]),
            }
            for point in normalized_points
        ]
    transport_start_beat = max(0.0, record_start_beat - pre_roll_beats)

    pre_auto_state, pre_verify_warnings = await _read_automation_state(
        ctx,
        track_index,
        device_index,
        int(parameter_index),
    )
    warnings.extend(pre_verify_warnings)
    pre_existing = _find_automation_param(pre_auto_state, int(parameter_index))
    if pre_auto_state is None and require_verification:
        return {
            "ok": False,
            "phase": "preflight",
            "error": "automation verification unavailable before recording",
            "warnings": warnings,
            "before": {
                "session": before_session,
                "recording": before_recording,
            },
        }
    if pre_existing is not None and not overwrite_existing:
        return {
            "ok": False,
            "phase": "preflight",
            "error": "target parameter already has automation; pass overwrite_existing=True to record over it",
            "parameter": target_parameter,
            "existing_automation": pre_existing,
            "automation_state": pre_auto_state,
            "warnings": warnings,
        }

    result: dict[str, Any] = {
        "ok": False,
        "phase": phase,
        "track_index": track_index,
        "device_index": device_index,
        "parameter_index": int(parameter_index),
        "parameter_name": str(target_parameter.get("name")),
        "start_beat": float(start_beat),
        "record_start_beat": record_start_beat,
        "transport_start_beat": transport_start_beat,
        "duration_beats": duration_beats,
        "record_duration_beats": record_duration_beats,
        "points_requested": normalized_points,
        "points_driven": drive_points,
        "points_recorded": executed_points,
        "guard_previous_value": bool(guard_previous_value),
        "guard_beats": guard_beats,
        "pre_roll_beats": pre_roll_beats,
        "guard_point": guard_point,
        "target_parameter_before_value": target_parameter_before_value,
        "trigger_track_index": None,
        "temporary_trigger_track": False,
        "pre_automation_state": pre_auto_state,
        "post_automation_state": None,
        "warnings": warnings,
        "cleanup": cleanup,
    }

    try:
        phase = "setup"
        result["phase"] = phase
        if trigger_track_index is None:
            create_result = ableton.send_command("create_midi_track", {
                "index": -1,
                "name": "LP Automation Recorder",
                "color_index": 14,
            }) or {}
            trigger_track_index = int(create_result["index"])
            temp_track_index = trigger_track_index
            result["temporary_trigger_track"] = True
        result["trigger_track_index"] = trigger_track_index

        try:
            ableton.send_command("set_track_input_monitoring", {
                "track_index": trigger_track_index,
                "state": 2,
            })
        except Exception as exc:  # noqa: BLE001
            cleanup["warnings"].append(f"set_track_input_monitoring failed: {exc}")

        for armed_index, was_armed in before_arms.items():
            if armed_index != trigger_track_index and was_armed:
                ableton.send_command("set_track_arm", {
                    "track_index": armed_index,
                    "arm": False,
                })
        ableton.send_command("set_track_arm", {
            "track_index": trigger_track_index,
            "arm": True,
        })

        phase = "transport"
        result["phase"] = phase
        ableton.send_command("stop_playback", {})
        try:
            ableton.send_command("stop_all_clips", {})
        except Exception as exc:  # noqa: BLE001
            cleanup["warnings"].append(f"stop_all_clips failed: {exc}")
        ableton.send_command("back_to_arranger", {})
        ableton.send_command("jump_to_time", {"beat_time": transport_start_beat})
        result["pre_roll_playback"] = ableton.send_command("continue_playback", {}) or {}
        await asyncio.sleep(0.35)
        # Live can resume an older stopped transport position. Seek again while
        # already playing, then engage Arrangement Record during the pre-roll.
        result["pre_roll_seek"] = ableton.send_command(
            "jump_to_time",
            {"beat_time": transport_start_beat},
        ) or {}
        await asyncio.sleep(0.35)

        start_result = ableton.send_command("start_recording", {"arrangement": True}) or {}
        record_attempted = True
        result["start_recording"] = start_result
        await asyncio.sleep(0.35)

        recording_info = ableton.send_command("get_session_info", {}) or {}
        if (
            isinstance(start_result, dict)
            and start_result.get("warning")
            and recording_info.get("record_mode")
        ):
            start_result = dict(start_result)
            start_result["preliminary_warning"] = start_result.pop("warning")
            result["start_recording"] = start_result
        result["recording_info"] = recording_info
        if not recording_info.get("record_mode"):
            raise RuntimeError(f"Arrangement record did not engage: {start_result}")
        record_started = True

        tempo = float(recording_info.get("tempo") or before_session.get("tempo") or 120.0)
        if tempo <= 0:
            tempo = 120.0
        seconds_per_beat = 60.0 / tempo
        result["tempo"] = tempo
        result["seconds_per_beat"] = seconds_per_beat

        try:
            record_position = float(recording_info.get("current_song_time"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Arrangement record position unavailable: {recording_info}"
            ) from exc
        result["record_position_at_drive_start"] = record_position
        # We need record mode to engage before the first driven point. Starting
        # too late would silently move the requested automation later.
        if record_position > record_start_beat + 0.1:
            raise RuntimeError(
                "Arrangement record engaged too late for the requested pass: "
                f"current beat {record_position:.3f}, first automation beat "
                f"{record_start_beat:.3f}. Increase pre_roll_beats."
            )
        if record_position < transport_start_beat - 0.25:
            raise RuntimeError(
                "Arrangement record started outside the pre-roll window: "
                f"current beat {record_position:.3f}, expected at or after "
                f"{transport_start_beat:.3f}."
            )

        phase = "drive"
        result["phase"] = phase
        loop = asyncio.get_running_loop()
        wall_start = loop.time()
        beat_start = record_position
        for point in drive_points:
            absolute_beat = record_start_beat + float(point["time"])
            due = wall_start + (absolute_beat - beat_start) * seconds_per_beat
            wait = due - loop.time()
            if wait < -0.1:
                warnings.append(
                    "automation point at beat %.3f was %.3fs late at drive time"
                    % (absolute_beat, abs(wait))
                )
            if wait > 0:
                await asyncio.sleep(wait)
            set_result = ableton.send_command("set_device_parameter", {
                "track_index": track_index,
                "device_index": device_index,
                "parameter_index": int(parameter_index),
                "value": float(point["value"]),
            })
            executed_points.append({
                "time": float(point["time"]),
                "absolute_beat": absolute_beat,
                "value": float(point["value"]),
                "guard": bool(point.get("guard", False)),
                "requested_time": point.get("requested_time"),
                "result": set_result,
            })

        record_end_beat = record_start_beat + record_duration_beats
        remaining = (
            wall_start
            + (record_end_beat - beat_start) * seconds_per_beat
            - loop.time()
        )
        if remaining > 0:
            await asyncio.sleep(remaining)

        phase = "stop"
        result["phase"] = phase
        cleanup["stop_recording"] = ableton.send_command("stop_recording", {})
        record_attempted = False
        record_started = False
        cleanup["stop_playback"] = ableton.send_command("stop_playback", {})

        phase = "verification"
        result["phase"] = phase
        post_auto_state, post_verify_warnings = await _read_automation_state(
            ctx,
            track_index,
            device_index,
            int(parameter_index),
        )
        warnings.extend(post_verify_warnings)
        result["post_automation_state"] = post_auto_state
        post_param = _find_automation_param(post_auto_state, int(parameter_index))
        result["verified"] = post_param is not None
        result["post_parameter_automation"] = post_param
        if require_verification and post_param is None:
            result["ok"] = False
            result["error"] = "record pass completed but target parameter automation was not verified"
        else:
            result["ok"] = True
            result["phase"] = "completed"

    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["phase"] = phase
        result["error"] = str(exc)
    finally:
        if record_started or record_attempted:
            try:
                cleanup["stop_recording"] = ableton.send_command("stop_recording", {})
            except Exception as exc:  # noqa: BLE001
                cleanup["warnings"].append(f"stop_recording cleanup failed: {exc}")
        try:
            if cleanup["stop_playback"] is None:
                cleanup["stop_playback"] = ableton.send_command("stop_playback", {})
        except Exception as exc:  # noqa: BLE001
            cleanup["warnings"].append(f"stop_playback cleanup failed: {exc}")

        for armed_index, was_armed in sorted(before_arms.items()):
            if armed_index == temp_track_index:
                continue
            try:
                ableton.send_command("set_track_arm", {
                    "track_index": armed_index,
                    "arm": was_armed,
                })
                cleanup["restored_arms"].append({
                    "track_index": armed_index,
                    "arm": was_armed,
                })
            except Exception as exc:  # noqa: BLE001
                cleanup["warnings"].append(
                    f"restore arm state failed for track {armed_index}: {exc}"
                )

        if temp_track_index is not None:
            try:
                ableton.send_command("delete_track", {"track_index": temp_track_index})
                cleanup["deleted_temp_track"] = True
            except Exception as exc:  # noqa: BLE001
                cleanup["warnings"].append(f"delete temporary trigger track failed: {exc}")

        if restore_transport:
            try:
                ableton.send_command("back_to_arranger", {})
                ableton.send_command("jump_to_time", {"beat_time": before_position})
                if before_was_playing:
                    cleanup["restore_transport"] = ableton.send_command("start_playback", {})
                else:
                    cleanup["restore_transport"] = {
                        "current_song_time": before_position,
                        "is_playing": False,
                    }
            except Exception as exc:  # noqa: BLE001
                cleanup["warnings"].append(f"restore transport failed: {exc}")

    return result


@mcp.tool()
async def record_parameter_automation_m4l_curve(
    ctx: Context,
    track_index: int,
    device_index: int,
    points: list[AutomationPoint] | str,
    start_beat: float,
    duration_beats: Optional[float] = None,
    parameter_index: Optional[int] = None,
    parameter_name: Optional[str] = None,
    record_arm_track_index: Optional[int] = None,
    overwrite_existing: bool = False,
    require_verification: bool = True,
    restore_transport: bool = True,
    guard_previous_value: bool = True,
    guard_beats: float = 0.25,
    pre_roll_beats: float = 8.0,
    mode: str = "linear",
    tick_ms: int = 10,
    min_delta: float = 0.0005,
) -> dict:
    """Record fast Arrangement automation via the M4L local scheduler.

    Unlike ``record_parameter_automation_realtime``, this sends the full curve
    to the LivePilot Analyzer bridge once. Max then drives the target device
    parameter locally against Arrangement song time while this MCP tool handles
    pre-roll, Arrangement Record, cleanup, and verification.
    """
    if track_index < 0:
        raise ValueError("track_index must be >= 0 for Arrangement track automation")
    if device_index < 0:
        raise ValueError("device_index must be >= 0")
    if parameter_index is None and not parameter_name:
        raise ValueError("parameter_index or parameter_name is required")
    if parameter_index is not None and parameter_index < 0:
        raise ValueError("parameter_index must be >= 0")
    if start_beat < 0:
        raise ValueError("start_beat must be >= 0")
    if record_arm_track_index is not None and record_arm_track_index < 0:
        raise ValueError("record_arm_track_index must be >= 0 when provided")

    mode = str(mode or "linear").lower()
    if mode not in ("linear", "points", "step"):
        raise ValueError("mode must be one of: linear, points, step")
    tick_ms = int(tick_ms)
    if tick_ms < 5:
        raise ValueError("tick_ms must be >= 5")
    min_delta = float(min_delta)
    if min_delta < 0:
        raise ValueError("min_delta must be >= 0")

    normalized_points = _normalize_realtime_points(points)
    last_point_time = normalized_points[-1]["time"]
    if duration_beats is None:
        duration_beats = max(0.25, last_point_time + 0.25)
    duration_beats = float(duration_beats)
    if duration_beats <= 0:
        raise ValueError("duration_beats must be > 0")
    if duration_beats < last_point_time:
        raise ValueError("duration_beats must be >= the last point time")
    guard_beats = float(guard_beats)
    if guard_beats <= 0:
        raise ValueError("guard_beats must be > 0")
    pre_roll_beats = float(pre_roll_beats)
    if pre_roll_beats < 0:
        raise ValueError("pre_roll_beats must be >= 0")

    ableton = _get_ableton(ctx)
    warnings: list[str] = []
    cleanup: dict[str, Any] = {
        "stop_recording": None,
        "stop_playback": None,
        "deleted_temp_track": False,
        "restored_arms": [],
        "restore_transport": None,
        "warnings": [],
    }
    temp_track_index: Optional[int] = None
    trigger_track_index: Optional[int] = record_arm_track_index
    record_attempted = False
    record_started = False
    scheduler_armed = False
    scheduler_completed = False
    phase = "preflight"

    before_session = ableton.send_command("get_session_info", {}) or {}
    before_recording = ableton.send_command("get_recording_state", {}) or {}
    before_position = float(before_session.get("current_song_time") or 0.0)
    before_was_playing = bool(before_session.get("is_playing", False))
    before_arms: dict[int, bool] = {}
    for track in before_session.get("tracks") or []:
        if isinstance(track, dict) and isinstance(track.get("arm"), bool):
            before_arms[int(track["index"])] = bool(track["arm"])

    parameter_info = ableton.send_command("get_device_parameters", {
        "track_index": track_index,
        "device_index": device_index,
    }) or {}
    device_parameters = parameter_info.get("parameters") or []
    target_parameter: Optional[dict] = None

    if parameter_index is not None:
        for parameter in device_parameters:
            if int(parameter.get("index", -1)) == int(parameter_index):
                target_parameter = parameter
                break
        if target_parameter is None:
            raise ValueError(f"parameter_index {parameter_index} not found on device {device_index}")
    else:
        assert parameter_name is not None
        for parameter in device_parameters:
            if str(parameter.get("name")) == parameter_name:
                target_parameter = parameter
                break
        if target_parameter is None:
            lowered = parameter_name.lower()
            for parameter in device_parameters:
                if str(parameter.get("name")).lower() == lowered:
                    target_parameter = parameter
                    break
        if target_parameter is None:
            available = [str(p.get("name")) for p in device_parameters[:20]]
            raise ValueError(
                f"parameter_name '{parameter_name}' not found on device {device_index}. "
                f"Available (first 20): {', '.join(available)}"
            )
        parameter_index = int(target_parameter["index"])

    parameter_min = float(target_parameter.get("min", float("-inf")))
    parameter_max = float(target_parameter.get("max", float("inf")))
    target_parameter_before_value = float(target_parameter.get("value", 0.0))
    for point in normalized_points:
        value = float(point["value"])
        if value < parameter_min or value > parameter_max:
            raise ValueError(
                f"point value {value} is outside parameter range "
                f"{parameter_min}..{parameter_max}"
            )

    record_start_beat = float(start_beat)
    record_duration_beats = duration_beats
    drive_points = [dict(point) for point in normalized_points]
    guard_point: Optional[dict] = None
    if guard_previous_value and start_beat > 0:
        actual_guard_beats = min(guard_beats, float(start_beat))
        record_start_beat = float(start_beat) - actual_guard_beats
        record_duration_beats = duration_beats + actual_guard_beats
        guard_point = {
            "time": 0.0,
            "value": target_parameter_before_value,
            "guard": True,
        }
        drive_points = [guard_point] + [
            {
                **dict(point),
                "time": float(point["time"]) + actual_guard_beats,
                "requested_time": float(point["time"]),
            }
            for point in normalized_points
        ]
    transport_start_beat = max(0.0, record_start_beat - pre_roll_beats)
    record_end_beat = record_start_beat + record_duration_beats
    curve_points = [
        {
            "beat": record_start_beat + float(point["time"]),
            "value": float(point["value"]),
            "guard": bool(point.get("guard", False)),
            "requested_time": point.get("requested_time"),
        }
        for point in drive_points
    ]

    bridge, bridge_warnings = await _get_ready_m4l_bridge(ctx)
    warnings.extend(bridge_warnings)

    pre_auto_state, pre_verify_warnings = await _read_automation_state(
        ctx,
        track_index,
        device_index,
        int(parameter_index),
    )
    warnings.extend(pre_verify_warnings)
    pre_existing = _find_automation_param(pre_auto_state, int(parameter_index))
    if pre_auto_state is None and require_verification:
        return {
            "ok": False,
            "phase": "preflight",
            "error": "automation verification unavailable before recording",
            "warnings": warnings,
            "before": {
                "session": before_session,
                "recording": before_recording,
            },
        }
    if pre_existing is not None and not overwrite_existing:
        return {
            "ok": False,
            "phase": "preflight",
            "error": "target parameter already has automation; pass overwrite_existing=True to record over it",
            "parameter": target_parameter,
            "existing_automation": pre_existing,
            "automation_state": pre_auto_state,
            "warnings": warnings,
        }

    result: dict[str, Any] = {
        "ok": False,
        "phase": phase,
        "track_index": track_index,
        "device_index": device_index,
        "parameter_index": int(parameter_index),
        "parameter_name": str(target_parameter.get("name")),
        "start_beat": float(start_beat),
        "record_start_beat": record_start_beat,
        "transport_start_beat": transport_start_beat,
        "record_end_beat": record_end_beat,
        "duration_beats": duration_beats,
        "record_duration_beats": record_duration_beats,
        "points_requested": normalized_points,
        "points_driven": drive_points,
        "curve_points": curve_points,
        "guard_previous_value": bool(guard_previous_value),
        "guard_beats": guard_beats,
        "pre_roll_beats": pre_roll_beats,
        "guard_point": guard_point,
        "target_parameter_before_value": target_parameter_before_value,
        "mode": mode,
        "tick_ms": tick_ms,
        "min_delta": min_delta,
        "trigger_track_index": None,
        "temporary_trigger_track": False,
        "pre_automation_state": pre_auto_state,
        "post_automation_state": None,
        "scheduler_arm": None,
        "scheduler_status": None,
        "warnings": warnings,
        "cleanup": cleanup,
    }

    scheduler_id = "m4l_curve_" + uuid.uuid4().hex[:12]

    try:
        phase = "setup"
        result["phase"] = phase
        if trigger_track_index is None:
            create_result = ableton.send_command("create_midi_track", {
                "index": -1,
                "name": "LP M4L Automation Recorder",
                "color_index": 14,
            }) or {}
            trigger_track_index = int(create_result["index"])
            temp_track_index = trigger_track_index
            result["temporary_trigger_track"] = True
        result["trigger_track_index"] = trigger_track_index

        try:
            ableton.send_command("set_track_input_monitoring", {
                "track_index": trigger_track_index,
                "state": 2,
            })
        except Exception as exc:  # noqa: BLE001
            cleanup["warnings"].append(f"set_track_input_monitoring failed: {exc}")

        for armed_index, was_armed in before_arms.items():
            if armed_index != trigger_track_index and was_armed:
                ableton.send_command("set_track_arm", {
                    "track_index": armed_index,
                    "arm": False,
                })
        ableton.send_command("set_track_arm", {
            "track_index": trigger_track_index,
            "arm": True,
        })

        phase = "transport"
        result["phase"] = phase
        ableton.send_command("stop_playback", {})
        try:
            ableton.send_command("stop_all_clips", {})
        except Exception as exc:  # noqa: BLE001
            cleanup["warnings"].append(f"stop_all_clips failed: {exc}")
        ableton.send_command("back_to_arranger", {})
        ableton.send_command("jump_to_time", {"beat_time": transport_start_beat})
        result["pre_roll_playback"] = ableton.send_command("continue_playback", {}) or {}
        await asyncio.sleep(0.35)
        result["pre_roll_seek"] = ableton.send_command(
            "jump_to_time",
            {"beat_time": transport_start_beat},
        ) or {}
        await asyncio.sleep(0.35)

        start_result = ableton.send_command("start_recording", {"arrangement": True}) or {}
        record_attempted = True
        result["start_recording"] = start_result
        await asyncio.sleep(0.35)

        recording_info = ableton.send_command("get_session_info", {}) or {}
        if (
            isinstance(start_result, dict)
            and start_result.get("warning")
            and recording_info.get("record_mode")
        ):
            start_result = dict(start_result)
            start_result["preliminary_warning"] = start_result.pop("warning")
            result["start_recording"] = start_result
        result["recording_info"] = recording_info
        if not recording_info.get("record_mode"):
            raise RuntimeError(f"Arrangement record did not engage: {start_result}")
        record_started = True

        tempo = float(recording_info.get("tempo") or before_session.get("tempo") or 120.0)
        if tempo <= 0:
            tempo = 120.0
        seconds_per_beat = 60.0 / tempo
        result["tempo"] = tempo
        result["seconds_per_beat"] = seconds_per_beat

        try:
            record_position = float(recording_info.get("current_song_time"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Arrangement record position unavailable: {recording_info}"
            ) from exc
        result["record_position_at_drive_start"] = record_position
        if record_position > record_start_beat + 0.1:
            raise RuntimeError(
                "Arrangement record engaged too late for the requested pass: "
                f"current beat {record_position:.3f}, first automation beat "
                f"{record_start_beat:.3f}. Increase pre_roll_beats."
            )
        if record_position < transport_start_beat - 0.25:
            raise RuntimeError(
                "Arrangement record started outside the pre-roll window: "
                f"current beat {record_position:.3f}, expected at or after "
                f"{transport_start_beat:.3f}."
            )

        phase = "scheduler"
        result["phase"] = phase
        payload = {
            "id": scheduler_id,
            "track_index": track_index,
            "device_index": device_index,
            "parameter_index": int(parameter_index),
            "points": curve_points,
            "end_beat": record_end_beat,
            "mode": mode,
            "time_base": "wall_clock",
            "origin_beat": record_position,
            "seconds_per_beat": seconds_per_beat,
            "tick_ms": tick_ms,
            "min_delta": min_delta,
            "end_tolerance_beats": 0.25,
        }
        arm_result = await bridge.send_command(
            "automation_curve_arm",
            json.dumps(payload, separators=(",", ":")),
            timeout=10.0,
        )
        result["scheduler_arm"] = arm_result
        if not isinstance(arm_result, dict) or arm_result.get("error"):
            raise RuntimeError(f"M4L automation scheduler arm failed: {arm_result}")
        scheduler_armed = True

        phase = "recording"
        result["phase"] = phase
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(
            5.0,
            ((record_end_beat - record_position) * seconds_per_beat) + 8.0,
        )
        final_status: Optional[dict] = None
        while loop.time() < deadline:
            status = await bridge.send_command("automation_curve_status", timeout=5.0)
            result["scheduler_status"] = status
            final_status = status if isinstance(status, dict) else None
            if isinstance(status, dict) and status.get("status") in (
                "completed",
                "error",
                "cancelled",
            ):
                break
            await asyncio.sleep(0.1)

        if final_status is None:
            raise RuntimeError("M4L automation scheduler did not return a status")
        if final_status.get("status") != "completed":
            raise RuntimeError(f"M4L automation scheduler did not complete: {final_status}")
        if final_status.get("ok") is False:
            raise RuntimeError(f"M4L automation scheduler failed: {final_status}")
        min_sets = 1 if mode == "linear" else len(curve_points)
        if int(final_status.get("set_count") or 0) < min_sets:
            raise RuntimeError(f"M4L automation scheduler set too few values: {final_status}")
        scheduler_completed = True
        scheduler_armed = False

        phase = "stop"
        result["phase"] = phase
        cleanup["stop_recording"] = ableton.send_command("stop_recording", {})
        record_attempted = False
        record_started = False
        cleanup["stop_playback"] = ableton.send_command("stop_playback", {})

        phase = "verification"
        result["phase"] = phase
        post_auto_state, post_verify_warnings = await _read_automation_state(
            ctx,
            track_index,
            device_index,
            int(parameter_index),
        )
        warnings.extend(post_verify_warnings)
        result["post_automation_state"] = post_auto_state
        post_param = _find_automation_param(post_auto_state, int(parameter_index))
        result["verified"] = post_param is not None
        result["post_parameter_automation"] = post_param
        if require_verification and post_param is None:
            result["ok"] = False
            result["error"] = "record pass completed but target parameter automation was not verified"
        else:
            result["ok"] = True
            result["phase"] = "completed"

    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["phase"] = phase
        result["error"] = str(exc)
    finally:
        if scheduler_armed and not scheduler_completed:
            try:
                result["scheduler_cancel"] = await bridge.send_command(
                    "automation_curve_cancel",
                    timeout=5.0,
                )
            except Exception as exc:  # noqa: BLE001
                cleanup["warnings"].append(f"automation_curve_cancel failed: {exc}")
        if record_started or record_attempted:
            try:
                cleanup["stop_recording"] = ableton.send_command("stop_recording", {})
            except Exception as exc:  # noqa: BLE001
                cleanup["warnings"].append(f"stop_recording cleanup failed: {exc}")
        try:
            if cleanup["stop_playback"] is None:
                cleanup["stop_playback"] = ableton.send_command("stop_playback", {})
        except Exception as exc:  # noqa: BLE001
            cleanup["warnings"].append(f"stop_playback cleanup failed: {exc}")

        for armed_index, was_armed in sorted(before_arms.items()):
            if armed_index == temp_track_index:
                continue
            try:
                ableton.send_command("set_track_arm", {
                    "track_index": armed_index,
                    "arm": was_armed,
                })
                cleanup["restored_arms"].append({
                    "track_index": armed_index,
                    "arm": was_armed,
                })
            except Exception as exc:  # noqa: BLE001
                cleanup["warnings"].append(
                    f"restore arm state failed for track {armed_index}: {exc}"
                )

        if temp_track_index is not None:
            try:
                ableton.send_command("delete_track", {"track_index": temp_track_index})
                cleanup["deleted_temp_track"] = True
            except Exception as exc:  # noqa: BLE001
                cleanup["warnings"].append(f"delete temporary trigger track failed: {exc}")

        if restore_transport:
            try:
                ableton.send_command("back_to_arranger", {})
                ableton.send_command("jump_to_time", {"beat_time": before_position})
                if before_was_playing:
                    cleanup["restore_transport"] = ableton.send_command("start_playback", {})
                else:
                    cleanup["restore_transport"] = {
                        "current_song_time": before_position,
                        "is_playing": False,
                    }
            except Exception as exc:  # noqa: BLE001
                cleanup["warnings"].append(f"restore transport failed: {exc}")

    return result


# ── Track-level arrangement automation workaround (T5, 2026-04-22 handoff) ─
#
# The Live LOM has a well-known gap: you cannot directly write a
# TRACK-level automation envelope into arrangement between clips or
# outside any clip. You can only write CLIP-level automation (which
# lives inside a specific clip). The workaround is the classic
# session-clip + record-to-arrangement dance:
#
#   1. Build a session clip with the automation (set_clip_automation)
#   2. Arm the track
#   3. Jump to the target beat
#   4. Start arrangement recording
#   5. Fire the session clip
#   6. Wait for the clip to play through at tempo
#   7. Stop recording
#   8. Stop the session clip (return control to arrangement)
#
# The recorded arrangement clip has the automation rendered as a native
# arrangement envelope — which IS writable by Live even when the LOM
# disallows direct API access.

@mcp.tool()
async def set_arrangement_automation_via_session_record(
    ctx: Context,
    track_index: int,
    parameter_type: str,
    points: list | str,
    target_beat: float,
    duration_beats: float,
    session_clip_slot: int = 0,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
    cleanup_session_clip: bool = True,
) -> dict:
    """Write an arrangement automation envelope at a specific beat via session record.

    Workaround for the Live LOM limitation that prevents direct writing of
    track-level arrangement automation outside of an existing arrangement
    clip. Creates a temporary session clip with the automation, arms the
    track, records the clip into arrangement at target_beat, then cleans
    up. The recorded arrangement clip has the automation baked in.

    **Status: LIVE** as of 2026-04-22. Uses a two-phase protocol so Live's
    main thread never blocks: phase 1 (start) fires the session clip into
    arrangement record; this tool then asyncio.sleeps for the expected
    record duration (computed from the live tempo that phase 1 returns);
    phase 2 (complete) stops record, cleans up, and returns the new
    arrangement clip's index + start/length. Total wall time ≈
    duration_beats × 60/tempo + 0.5s handler overhead.

    parameter_type:       "device" | "volume" | "panning" | "send"
    points:               [{time, value, duration?}] — time relative to
                          the session clip's start (0.0 = first beat)
    target_beat:          where the recording should begin in the
                          arrangement timeline (beats)
    duration_beats:       how long to record (usually matches the session
                          clip's natural length, but may be longer for
                          multiple repeats)
    session_clip_slot:    which session clip slot to use (default 0 — must
                          be EMPTY or its current content will be overwritten)
    device_index,
    parameter_index:      required for parameter_type="device"
    send_index:           required for parameter_type="send" (0=A, 1=B)
    cleanup_session_clip: delete the temp session clip after recording
                          completes (default True)

    Returns a dict with the recorded arrangement clip index + verification
    info, or an error if any step failed. Because this orchestrates a
    real-time recording, any of the steps can fail at runtime (track
    not armable, session clip already running, transport not cooperating).
    Each failure is reported with the stage it happened at.
    """
    if track_index < 0:
        raise ValueError("track_index must be >= 0 (track-level automation only supports regular tracks)")
    if parameter_type not in ("device", "volume", "panning", "send"):
        raise ValueError("parameter_type must be 'device', 'volume', 'panning', or 'send'")
    if parameter_type == "device":
        if device_index is None or parameter_index is None:
            raise ValueError("device_index and parameter_index required for parameter_type='device'")
    if parameter_type == "send" and send_index is None:
        raise ValueError("send_index required for parameter_type='send'")
    points_list = _ensure_list(points)
    if not points_list:
        raise ValueError("points list cannot be empty")
    if target_beat < 0:
        raise ValueError("target_beat must be >= 0")
    if duration_beats <= 0:
        raise ValueError("duration_beats must be > 0")

    ableton = _get_ableton(ctx)

    # Two-phase protocol — the start handler can't block Live's main thread
    # for the full recording duration (audio dropouts, UI freezes). So:
    #   1. start — writes session clip, arms, seeks, fires, enables record
    #   2. MCP-side asyncio.sleep for duration + buffer
    #   3. complete — stops record, cleans up, returns arrangement clip info
    # The session-clip route is unchanged; the orchestration moved to us.
    start_params: dict = {
        "track_index": track_index,
        "parameter_type": parameter_type,
        "points": points_list,
        "target_beat": target_beat,
        "duration_beats": duration_beats,
        "session_clip_slot": session_clip_slot,
    }
    if device_index is not None:
        start_params["device_index"] = device_index
    if parameter_index is not None:
        start_params["parameter_index"] = parameter_index
    if send_index is not None:
        start_params["send_index"] = send_index

    start_result = ableton.send_command(
        "arrangement_automation_via_session_record_start",
        start_params,
    )
    if not isinstance(start_result, dict) or start_result.get("status") != "recording":
        return {
            "ok": False,
            "phase": "start",
            "error": "arrangement record failed to engage",
            "details": start_result,
        }

    # Compute sleep: duration_beats * 60/tempo seconds + 0.5s buffer for
    # Live's record-arm latency. Tempo comes back from the start handler
    # (fresh Song.tempo read) so we don't hardcode 120.
    import asyncio
    tempo = float(start_result.get("tempo") or 120.0)
    if tempo <= 0:
        tempo = 120.0
    seconds_per_beat = 60.0 / tempo
    sleep_sec = duration_beats * seconds_per_beat + 0.5
    # Safety ceiling — if something is misconfigured we shouldn't sleep
    # forever. 10 minutes is far beyond any realistic arrangement clip.
    sleep_sec = min(sleep_sec, 600.0)
    try:
        await asyncio.sleep(sleep_sec)
    except Exception as exc:
        # Even if sleep fails we try to complete so we don't leave the
        # track armed + recording.
        logger.warning("sleep interrupted: %s", exc)

    complete_params = {
        "track_index": track_index,
        "session_clip_slot": session_clip_slot,
        "target_beat": target_beat,
        "duration_beats": duration_beats,
        "cleanup_session_clip": cleanup_session_clip,
    }
    complete_result = ableton.send_command(
        "arrangement_automation_via_session_record_complete",
        complete_params,
    )
    ok = (
        isinstance(complete_result, dict)
        and complete_result.get("status") == "completed"
    )
    return {
        "ok": bool(ok),
        "tempo": tempo,
        "slept_sec": sleep_sec,
        "start": start_result,
        "complete": complete_result,
    }
