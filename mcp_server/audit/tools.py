"""audit_layer — single-tool replacement for the §5 layer-precision checklist.

Fetches once, runs 8 server-side checks, returns a structured report with
ranked fixes. Replaces the manual sequence:

    solo + get_master_spectrum
    get_notes (per clip) + sequence critique
    get_track_info (pan/width)
    get_masking_report (filter for this track)
    get_device_parameters (modulation routings)
    get_device_parameters (default-detection)
    get_simpler_slices + classify_simpler_slices
    track_info.devices (effects coverage)

…which was 8+ tool calls of LLM-driven ceremony. Now: one call.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import checks
from .state import (
    safe_call as _safe_call,
    fetch_notes_for_clips as _fetch_notes_for_clips,
    has_clip_automation as _has_clip_automation,
    count_wavetable_routings as _count_wavetable_routings,
)

logger = logging.getLogger(__name__)


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _maybe_get_timbre_fingerprint(ctx: Context, track_index: int) -> dict | None:
    """Pull a per-track timbre fingerprint via the synthesis_brain timbre helper.

    Returns None when the M4L bridge is offline or no fingerprint is available.
    Does NOT solo the track — uses cached spectral data only.
    """
    try:
        from ..synthesis_brain.timbre import extract_timbre_fingerprint  # type: ignore
    except Exception:
        return None
    try:
        result = extract_timbre_fingerprint(ctx, track_index)  # type: ignore[arg-type]
        if isinstance(result, dict) and result.get("bands"):
            return result
    except Exception as exc:
        logger.debug("audit_layer timbre fetch failed: %s", exc)
    return None


@mcp.tool()
def audit_layer(
    ctx: Context,
    track_index: int,
    role: Optional[str] = None,
    include_masking: bool = True,
    include_timbre: bool = False,
) -> dict:
    """Run the §5 layer-precision audit on a single track in one call.

    Replaces 8 manual checks (timbre, sequence, stereo, masking, modulation,
    params, samples, effects) with one server-side aggregation. Returns
    structured report with PASS/WARN/FAIL per check + ranked fixes.

    Args:
        track_index: Track to audit.
        role: Optional role override ("kick"/"snare"/"hat"/"perc"/"bass"/
            "pad"/"lead"/"atmos"/"vox"/"fx"). If omitted, inferred from
            track name + first instrument class.
        include_masking: If True (default), pulls cross-track masking report
            and filters for this track. Adds ~200-600ms.
        include_timbre: If True, pulls per-track timbre fingerprint via the
            M4L bridge. Costs an extra spectral read; default False so the
            tool stays fast on bridge-less sessions.

    Returns one structured report — no follow-up calls needed.
    """
    started = time.time()
    ableton = _get_ableton(ctx)

    track_info = _safe_call(ableton, "get_track_info", {"track_index": track_index})
    if not track_info:
        return {
            "track_index": track_index,
            "error": "get_track_info failed",
            "checks": {},
            "recommended_fixes": [],
        }

    track_name = track_info.get("name", f"track_{track_index}")
    devices = track_info.get("devices", []) or []
    clip_slots = track_info.get("clip_slots", []) or []

    # Role: caller-given or inferred
    inferred_role = role or checks.infer_role(track_name, devices)

    # Pull per-clip notes only when MIDI clips exist (audio tracks return [])
    notes_per_clip = _fetch_notes_for_clips(ableton, track_index, clip_slots)

    # Modulation signals: clip automation + wavetable mod matrix routings
    automation_present = _has_clip_automation(ableton, track_index, clip_slots)
    wt_routings = _count_wavetable_routings(ableton, track_index, devices)

    # Optional masking — note that get_masking_report is an MCP-server-side
    # tool (mix_engine.tools), NOT a Remote Script command. We import and
    # call its python function directly. Going through ableton.send_command
    # would dispatch to the LOM bridge which has no such handler and silently
    # fails (BUG-D, caught by 4-way parallel live test 2026-05-01).
    masking_report = None
    if include_masking:
        try:
            from ..mix_engine.tools import get_masking_report as _get_masking_report_impl
            masking_report = _get_masking_report_impl(ctx)  # type: ignore[arg-type]
        except Exception as exc:
            logger.debug("audit_layer: masking fetch failed: %s", exc)
    fingerprint = _maybe_get_timbre_fingerprint(ctx, track_index) if include_timbre else None

    # Slice classifications only if Simpler with slices is present
    slice_classes = None
    if any(d.get("class_name") == "Simpler" for d in devices):
        result = _safe_call(ableton, "classify_simpler_slices", {"track_index": track_index})
        if result:
            slice_classes = result.get("slices") or result.get("classifications")

    # Run the 8 checks
    check_results = {
        "timbre": checks.check_timbre(inferred_role, fingerprint),
        "sequence": checks.check_sequence(inferred_role, notes_per_clip),
        "stereo": checks.check_stereo(inferred_role, track_info),
        "masking": checks.check_masking(track_index, masking_report),
        "modulation": checks.check_modulation(
            inferred_role, devices, automation_present, wt_routings
        ),
        "params": checks.check_params(inferred_role, devices),
        "samples": checks.check_samples(inferred_role, devices, slice_classes),
        "effects": checks.check_effects(inferred_role, devices),
    }

    overall = checks.rollup_severity(check_results)
    fixes = checks.rank_fixes(check_results)

    duration_ms = int((time.time() - started) * 1000)

    return {
        "track_index": track_index,
        "track_name": track_name,
        "role": inferred_role,
        "role_inferred": role is None,
        "overall_severity": overall,
        "checks": check_results,
        "recommended_fixes": fixes,
        "metadata": {
            "duration_ms": duration_ms,
            "clip_count": len([s for s in clip_slots if s.get("has_clip")]),
            "device_count": len(devices),
            "timbre_source": "fresh" if fingerprint else "skipped" if not include_timbre else "unavailable",
            "masking_source": "fresh" if masking_report else "skipped" if not include_masking else "unavailable",
        },
    }
