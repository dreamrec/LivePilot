"""Reference Engine MCP tools — 3 tools for reference-aware production intelligence.

Each tool fetches data from Ableton/perception via the shared connection,
then delegates to pure-computation modules.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import mcp
from ..tools._research_engine import get_style_tactics
from .profile_builder import build_audio_reference_profile, build_style_reference_profile
from .gap_analyzer import analyze_gaps, classify_gap_relevance, detect_identity_warnings
from .tactic_router import build_reference_plan


# ── Helpers ────────────────────────────────────────────────────────


def _fetch_comparison_data(ctx: Context, mix_path: str, reference_path: str) -> dict:
    """Run compare_to_reference via the perception engine."""
    from ..tools._perception_engine import compare_to_reference

    if not mix_path:
        return {"error": "No mix_path provided — bounce your project first and pass the path", "code": "INVALID_PARAM"}

    return compare_to_reference(mix_path, reference_path, normalize=True)


def _fetch_project_snapshot(ctx: Context) -> dict:
    """Build a lightweight project snapshot for gap analysis."""
    ableton = ctx.lifespan_context["ableton"]

    snapshot: dict = {
        "loudness": 0.0,
        "spectral": {},
        "width": 0.0,
        "density": 0.0,
        "pacing": [],
        "harmonic_character": "",
    }

    # Try to get master RMS / loudness
    try:
        rms_result = ableton.send_command("get_master_rms", {})
        rms = rms_result.get("rms", 0.0) if isinstance(rms_result, dict) else 0.0
        # Approximate LUFS from RMS (rough heuristic)
        if rms > 0:
            import math
            snapshot["loudness"] = round(20 * math.log10(max(rms, 1e-10)), 2)
    except Exception:
        pass

    # Try to get spectrum data
    try:
        spectrum = ableton.send_command("get_master_spectrum", {})
        if isinstance(spectrum, dict):
            snapshot["spectral"] = spectrum
    except Exception:
        pass

    # Try to get session info for pacing / density
    try:
        session_info = ableton.send_command("get_session_info", {})
        track_count = session_info.get("track_count", 0)
        scene_count = session_info.get("scene_count", 0)
        # Rough density estimate
        snapshot["density"] = min(1.0, track_count / 20.0)
        snapshot["pacing"] = [{"label": f"scene_{i}", "bars": 8} for i in range(scene_count)]
    except Exception:
        pass

    return snapshot


# ── MCP Tools ──────────────────────────────────────────────────────


@mcp.tool()
def build_reference_profile(
    ctx: Context,
    reference_path: str = "",
    mix_path: str = "",
    style: str = "",
) -> dict:
    """Build a reference profile from an audio file or style/genre name.

    Provide either reference_path (for audio comparison) or style
    (for style tactic lookup). If both are provided, audio takes priority.

    Args:
        reference_path: Absolute path to a reference audio file (.wav, .flac, .aiff).
        mix_path: Absolute path to your bounced mix file (required for audio comparison).
        style: Artist or genre name (e.g. "burial", "techno", "lo-fi").

    Returns:
        ReferenceProfile as dict with source_type, loudness_posture,
        spectral_contour, width_depth, density_arc, section_pacing,
        harmonic_character, transition_tendencies.
    """
    if reference_path:
        comparison = _fetch_comparison_data(ctx, mix_path, reference_path)
        if "error" in comparison:
            return comparison
        profile = build_audio_reference_profile(comparison)
        return profile.to_dict()

    if style:
        tactics = get_style_tactics(style)
        if not tactics:
            return {
                "error": f"No style tactics found for '{style}'",
                "code": "NOT_FOUND",
            }
        tactic_dicts = [t.to_dict() for t in tactics]
        profile = build_style_reference_profile(tactic_dicts)
        return profile.to_dict()

    return {
        "error": "Provide either reference_path or style",
        "code": "INVALID_PARAM",
    }


@mcp.tool()
def analyze_reference_gaps(
    ctx: Context,
    reference_path: str = "",
    mix_path: str = "",
    style: str = "",
    goal_dimensions: str = "",
) -> dict:
    """Analyze gaps between your project and a reference.

    Computes deltas across spectral, loudness, width, density, pacing,
    and harmonic domains. Flags which gaps are relevant and which
    would destroy your project's identity if closed.

    Args:
        reference_path: Absolute path to a reference audio file.
        mix_path: Absolute path to your bounced mix file (required for audio comparison).
        style: Artist or genre name for style-based comparison.
        goal_dimensions: Comma-separated domains to focus on
            (e.g. "spectral,width"). Empty = all domains.

    Returns:
        GapReport as dict with gaps, relevant_gaps, identity_warnings,
        and overall_distance.
    """
    # Build reference profile
    if reference_path:
        comparison = _fetch_comparison_data(ctx, mix_path, reference_path)
        if "error" in comparison:
            return comparison
        profile = build_audio_reference_profile(comparison)
    elif style:
        tactics = get_style_tactics(style)
        if not tactics:
            return {"error": f"No style tactics found for '{style}'", "code": "NOT_FOUND"}
        tactic_dicts = [t.to_dict() for t in tactics]
        profile = build_style_reference_profile(tactic_dicts)
    else:
        return {"error": "Provide either reference_path or style", "code": "INVALID_PARAM"}

    # Build project snapshot
    snapshot = _fetch_project_snapshot(ctx)

    # Analyze gaps
    gap_report = analyze_gaps(snapshot, profile)

    # Reclassify relevance if user specified goal dimensions
    if goal_dimensions:
        dims = [d.strip() for d in goal_dimensions.split(",") if d.strip()]
        for gap in gap_report.gaps:
            gap.relevant = classify_gap_relevance(gap, dims)

    return gap_report.to_dict()


@mcp.tool()
def plan_reference_moves(
    ctx: Context,
    reference_path: str = "",
    mix_path: str = "",
    style: str = "",
    goal_dimensions: str = "",
) -> dict:
    """Plan concrete moves to close reference gaps.

    Builds a reference profile, analyzes gaps, then routes each gap
    to the appropriate engine (mix_engine or composition) with
    ranked tactics and identity warnings.

    Args:
        reference_path: Absolute path to a reference audio file.
        mix_path: Absolute path to your bounced mix file (required for audio comparison).
        style: Artist or genre name for style-based comparison.
        goal_dimensions: Comma-separated domains to focus on.

    Returns:
        ReferencePlan as dict with gap_report, ranked_tactics,
        and target_engines.
    """
    # Build reference profile
    if reference_path:
        comparison = _fetch_comparison_data(ctx, mix_path, reference_path)
        if "error" in comparison:
            return comparison
        profile = build_audio_reference_profile(comparison)
    elif style:
        tactics = get_style_tactics(style)
        if not tactics:
            return {"error": f"No style tactics found for '{style}'", "code": "NOT_FOUND"}
        tactic_dicts = [t.to_dict() for t in tactics]
        profile = build_style_reference_profile(tactic_dicts)
    else:
        return {"error": "Provide either reference_path or style", "code": "INVALID_PARAM"}

    # Build project snapshot
    snapshot = _fetch_project_snapshot(ctx)

    # Analyze gaps
    gap_report = analyze_gaps(snapshot, profile)

    # Reclassify relevance if user specified goal dimensions
    if goal_dimensions:
        dims = [d.strip() for d in goal_dimensions.split(",") if d.strip()]
        for gap in gap_report.gaps:
            gap.relevant = classify_gap_relevance(gap, dims)

    # Build plan
    plan = build_reference_plan(gap_report)

    return plan.to_dict()
