"""MCP tools for the synthesis_brain subsystem (PR5/v2).

Four user-facing wrappers that expose the Python-callable internals
through the MCP surface. Thin wrappers by design — all intelligence
lives in adapters/engine.py; these tools handle ctx plumbing, param
rehydration, and response shaping.

Tools:
  analyze_synth_patch(track_index, device_index, role_hint?)
    → SynthProfile dict for any supported native synth on the given
       track+device. Fetches parameter state via get_device_parameters
       and display_values via get_display_values.

  propose_synth_branches(track_index, device_index, target?, freshness?)
    → List of (seed_dict, compiled_plan) pairs. Feed directly to
       create_experiment(seeds=seed_dicts, compiled_plans=plans) OR
       skip the plans list to have run_experiment compile from move_id
       (not applicable here — synthesis seeds always ship with plans).

  extract_timbre_fingerprint(spectrum?, loudness?, spectral_shape?)
    → TimbralFingerprint dict. Pure transform; no I/O. Callers that
       have already captured audio analysis dicts can convert them to
       a fingerprint without going through the full render-verify path.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from .engine import analyze_synth_patch as _analyze_synth_patch
from .engine import propose_synth_branches as _propose_synth_branches
from .engine import supported_devices
from .timbre import extract_timbre_fingerprint as _extract_fp
from .models import TimbralFingerprint

import logging

logger = logging.getLogger(__name__)


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def analyze_synth_patch(
    ctx: Context,
    track_index: int,
    device_index: int,
    role_hint: str = "",
) -> dict:
    """Extract a SynthProfile for a native synth on the given track+device.

    Fetches live parameter state + display_values from Ableton, then hands
    them to the synthesis_brain adapter for that device. When the device
    isn't a supported native (Wavetable / Operator / Analog / Drift / Meld),
    returns an opaque SynthProfile — raw params survive for manual inspection
    but no strategies are proposed.

    role_hint: optional tag ("pad", "lead", "bass", "pluck", "stab",
        "drone") that gates adapter strategy selection. Leave empty when
        the role is ambiguous.

    Returns: SynthProfile dict with device_name, opacity, track_index,
    device_index, parameter_state, display_values, role_hint, modulation,
    articulation, notes.
    """
    ableton = _get_ableton(ctx)
    try:
        info = ableton.send_command(
            "get_device_info",
            {"track_index": track_index, "device_index": device_index},
        )
    except Exception as exc:
        return {"error": f"get_device_info failed: {exc}"}
    if not isinstance(info, dict) or "error" in info:
        return {"error": info.get("error") if isinstance(info, dict) else "device not found"}

    device_name = info.get("name") or info.get("class_name") or ""

    try:
        params_result = ableton.send_command(
            "get_device_parameters",
            {"track_index": track_index, "device_index": device_index},
        )
    except Exception as exc:
        return {"error": f"get_device_parameters failed: {exc}"}

    parameter_state: dict = {}
    display_values: dict = {}
    if isinstance(params_result, dict):
        for p in params_result.get("parameters", []) or []:
            name = p.get("name")
            if name is None:
                continue
            parameter_state[name] = p.get("value")
            if "value_string" in p:
                display_values[name] = p["value_string"]

    profile = _analyze_synth_patch(
        device_name=device_name,
        track_index=int(track_index),
        device_index=int(device_index),
        parameter_state=parameter_state,
        display_values=display_values,
        role_hint=role_hint,
    )
    result = profile.to_dict()
    result["supported_devices"] = supported_devices()
    return result


@mcp.tool()
def propose_synth_branches(
    ctx: Context,
    track_index: int,
    device_index: int,
    target: Optional[dict] = None,
    freshness: float = 0.5,
    role_hint: str = "",
) -> dict:
    """Propose branch seeds + pre-compiled plans for a native synth.

    Fetches the device's current parameters (via analyze_synth_patch),
    hands them to the appropriate adapter, and returns the emitted
    (seed, plan) pairs as two parallel lists suitable for
    create_experiment(seeds=..., compiled_plans=...).

    target: optional TimbralFingerprint dict ({"brightness": 0.3, ...}).
        Seeds that know about target direction (synthesis_brain adapters)
        will score their diffs against it during run_experiment with
        render_verify=True. When omitted, adapters shift based on freshness
        alone and role_hint gating.

    freshness: 0.0-1.0; threaded into kernel for adapter magnitude scaling.

    Returns:
      {
        "device_name": str,
        "branch_count": int,
        "seeds": [BranchSeed.to_dict(), ...],
        "compiled_plans": [plan_dict, ...]    (parallel to seeds),
        "warnings": list,
      }

    Each seed's producer_payload captures strategy + topology_hint so
    PR3/PR4 winner-commit and render-verify can refine behavior without
    losing provenance.
    """
    profile_dict = analyze_synth_patch(
        ctx, track_index=int(track_index), device_index=int(device_index),
        role_hint=role_hint,
    )
    if "error" in profile_dict:
        return profile_dict

    device_name = profile_dict.get("device_name", "")
    if profile_dict.get("opacity") != "native":
        return {
            "device_name": device_name,
            "branch_count": 0,
            "seeds": [],
            "compiled_plans": [],
            "warnings": [
                f"'{device_name}' is not a supported native synth — "
                f"synthesis_brain only knows about {supported_devices()}"
            ],
        }

    # Rehydrate the SynthProfile from the dict (round-trip is lossy for
    # some nested fields, so we re-analyze with the original parameter
    # state captured by analyze_synth_patch).
    from .engine import analyze_synth_patch as _refetch
    profile = _refetch(
        device_name=device_name,
        track_index=int(track_index),
        device_index=int(device_index),
        parameter_state=profile_dict.get("parameter_state") or {},
        display_values=profile_dict.get("display_values") or {},
        role_hint=role_hint or profile_dict.get("role_hint", ""),
    )

    target_fp = TimbralFingerprint(**{
        k: float(v) for k, v in (target or {}).items()
        if k in TimbralFingerprint.__dataclass_fields__ and isinstance(v, (int, float))
    })
    kernel = {"freshness": float(freshness)}

    pairs = _propose_synth_branches(profile, target=target_fp, kernel=kernel)

    seeds = [s.to_dict() for s, _ in pairs]
    plans = [p for _, p in pairs]
    return {
        "device_name": device_name,
        "branch_count": len(seeds),
        "seeds": seeds,
        "compiled_plans": plans,
        "warnings": [],
    }


@mcp.tool()
def extract_timbre_fingerprint(
    ctx: Context,
    spectrum: Optional[dict] = None,
    loudness: Optional[dict] = None,
    spectral_shape: Optional[dict] = None,
) -> dict:
    """Build a TimbralFingerprint from analysis dicts.

    Pure transform — no I/O. Useful when you already have spectrum +
    loudness + spectral_shape dicts (e.g. from analyze_spectrum_offline
    + analyze_loudness + get_spectral_shape) and want the 9-dimensional
    fingerprint without going through the full render-verify pipeline.

    Inputs are all optional; the fingerprint degrades gracefully to
    neutral (all-zero) when no signal data is present.

    Returns: TimbralFingerprint dict with brightness, warmth, bite,
    softness, instability, width, texture_density, movement, polish
    — each in [-1.0, 1.0].
    """
    fp = _extract_fp(
        spectrum=spectrum,
        loudness=loudness,
        spectral_shape=spectral_shape,
    )
    return fp.to_dict()
