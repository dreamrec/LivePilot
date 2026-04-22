"""Automation MCP tools — clip envelope CRUD + intelligent curve generation.

8 tools for writing, reading, and generating automation curves on session clips.
Combines the clip automation handlers (Remote Script) with the curve generation
engine (curves.py) for musically intelligent automation.
"""

from __future__ import annotations

from typing import Any, Optional

from fastmcp import Context
from pydantic import BaseModel, Field

from ..curves import generate_curve, generate_from_recipe, list_recipes
from ..server import mcp
import logging

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
