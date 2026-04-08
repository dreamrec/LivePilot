"""Gap analyzer — compute and classify gaps between project and reference.

Pure functions, zero I/O.
"""

from __future__ import annotations

import math

from .models import GapEntry, GapReport, ReferenceProfile


# ── Domain thresholds ──────────────────────────────────────────────

# Minimum delta magnitude to consider a gap meaningful
_RELEVANCE_THRESHOLDS: dict[str, float] = {
    "spectral": 0.01,
    "loudness": 1.0,     # 1 LU
    "density": 0.1,
    "width": 0.05,
    "pacing": 0.15,
    "harmonic": 0.0,     # always relevant if different
}

# When a gap exceeds this fraction of the project value, closing it
# risks flattening identity.
_IDENTITY_WARNING_THRESHOLD = 0.6


# ── Main analysis ──────────────────────────────────────────────────


def analyze_gaps(
    project_snapshot: dict,
    reference: ReferenceProfile,
) -> GapReport:
    """Compare a project snapshot against a reference profile.

    Args:
        project_snapshot: dict with keys matching ReferenceProfile fields:
            loudness (float), spectral (dict with band_balance),
            width (float), density (float or list), pacing (list),
            harmonic_character (str).
        reference: The target ReferenceProfile.

    Returns:
        GapReport with all detected gaps.
    """
    gaps: list[GapEntry] = []
    ref_id = f"{reference.source_type}"

    # 1. Loudness gap
    proj_loudness = project_snapshot.get("loudness", 0.0)
    if reference.loudness_posture != 0.0 or proj_loudness != 0.0:
        delta = proj_loudness - reference.loudness_posture
        gaps.append(GapEntry(
            domain="loudness",
            delta=round(delta, 2),
            relevant=abs(delta) >= _RELEVANCE_THRESHOLDS["loudness"],
            identity_warning=False,
            suggested_tactic=_suggest_loudness_tactic(delta),
        ))

    # 2. Spectral gaps (per-band)
    proj_spectral = project_snapshot.get("spectral", {})
    proj_bands = proj_spectral.get("band_balance", {})
    ref_bands = reference.spectral_contour.get("band_balance", {})

    all_bands = set(list(proj_bands.keys()) + list(ref_bands.keys()))
    for band in sorted(all_bands):
        proj_val = proj_bands.get(band, 0.0)
        ref_val = ref_bands.get(band, 0.0)
        delta = proj_val - ref_val
        if abs(delta) >= _RELEVANCE_THRESHOLDS["spectral"]:
            gaps.append(GapEntry(
                domain="spectral",
                delta=round(delta, 6),
                relevant=True,
                identity_warning=_is_identity_risk(proj_val, delta),
                suggested_tactic=_suggest_spectral_tactic(band, delta),
            ))

    # 3. Width gap
    proj_width = project_snapshot.get("width", 0.0)
    ref_width = reference.width_depth.get("stereo_width", 0.0)
    if proj_width != 0.0 or ref_width != 0.0:
        delta = proj_width - ref_width
        gaps.append(GapEntry(
            domain="width",
            delta=round(delta, 4),
            relevant=abs(delta) >= _RELEVANCE_THRESHOLDS["width"],
            identity_warning=_is_identity_risk(proj_width, delta),
            suggested_tactic=_suggest_width_tactic(delta),
        ))

    # 4. Density gap
    proj_density = project_snapshot.get("density", 0.0)
    if isinstance(proj_density, list):
        proj_density = sum(proj_density) / max(len(proj_density), 1)
    ref_density = (
        sum(reference.density_arc) / max(len(reference.density_arc), 1)
        if reference.density_arc
        else 0.0
    )
    if proj_density != 0.0 or ref_density != 0.0:
        delta = proj_density - ref_density
        gaps.append(GapEntry(
            domain="density",
            delta=round(delta, 3),
            relevant=abs(delta) >= _RELEVANCE_THRESHOLDS["density"],
            identity_warning=_is_identity_risk(proj_density, delta),
            suggested_tactic=_suggest_density_tactic(delta),
        ))

    # 5. Pacing gap
    proj_pacing = project_snapshot.get("pacing", [])
    ref_pacing = reference.section_pacing
    if proj_pacing or ref_pacing:
        delta = len(proj_pacing) - len(ref_pacing)
        gaps.append(GapEntry(
            domain="pacing",
            delta=float(delta),
            relevant=abs(delta) >= _RELEVANCE_THRESHOLDS["pacing"],
            identity_warning=False,
            suggested_tactic=_suggest_pacing_tactic(delta),
        ))

    # 6. Harmonic gap
    proj_harmonic = project_snapshot.get("harmonic_character", "")
    ref_harmonic = reference.harmonic_character
    if ref_harmonic and proj_harmonic != ref_harmonic:
        gaps.append(GapEntry(
            domain="harmonic",
            delta=1.0 if proj_harmonic != ref_harmonic else 0.0,
            relevant=True,
            identity_warning=True,  # harmonic identity is core
            suggested_tactic=f"Consider {ref_harmonic} voicings",
        ))

    # Compute overall distance
    overall = _compute_overall_distance(gaps)

    return GapReport(
        reference_id=ref_id,
        gaps=gaps,
        overall_distance=round(overall, 3),
    )


# ── Relevance classification ──────────────────────────────────────


def classify_gap_relevance(
    gap: GapEntry,
    goal_dimensions: list[str],
) -> bool:
    """Reclassify a gap's relevance against the user's stated goal dimensions.

    Args:
        gap: The GapEntry to classify.
        goal_dimensions: list of domain names the user cares about
            (e.g. ["spectral", "width"]).

    Returns:
        True if the gap is relevant to the goal.
    """
    if not goal_dimensions:
        return gap.relevant  # keep original classification

    return gap.domain in goal_dimensions


# ── Identity warnings ──────────────────────────────────────────────


def detect_identity_warnings(gaps: list[GapEntry]) -> list[str]:
    """Detect gaps where closing them would destroy project identity.

    Returns human-readable warning strings.
    """
    warnings: list[str] = []
    for g in gaps:
        if g.identity_warning:
            warnings.append(
                f"[{g.domain}] delta={g.delta:+.3f}: closing this gap "
                f"risks flattening your project's unique {g.domain} character"
            )
    return warnings


# ── Internal helpers ──────────────────────────────────────────────


def _is_identity_risk(project_value: float, delta: float) -> bool:
    """Check if the gap is large enough relative to project value
    that closing it would significantly alter character."""
    if abs(project_value) < 1e-9:
        return False
    return abs(delta / project_value) > _IDENTITY_WARNING_THRESHOLD


def _compute_overall_distance(gaps: list[GapEntry]) -> float:
    """Euclidean-like distance across all relevant gap deltas."""
    relevant = [g for g in gaps if g.relevant]
    if not relevant:
        return 0.0
    sum_sq = sum(g.delta ** 2 for g in relevant)
    return math.sqrt(sum_sq)


def _suggest_loudness_tactic(delta: float) -> str:
    if delta > 2.0:
        return "Reduce master gain or limiter ceiling"
    elif delta < -2.0:
        return "Increase gain staging or limiter drive"
    return "Loudness is close — fine-tune with limiter"


def _suggest_spectral_tactic(band: str, delta: float) -> str:
    direction = "cut" if delta > 0 else "boost"
    return f"EQ {direction} in {band} range"


def _suggest_width_tactic(delta: float) -> str:
    if delta > 0:
        return "Narrow stereo image — check Utility width or mono bass"
    return "Widen stereo image — try chorus, haas, or panning spread"


def _suggest_density_tactic(delta: float) -> str:
    if delta > 0:
        return "Thin arrangement — mute or remove layers"
    return "Add layers or textural elements for density"


def _suggest_pacing_tactic(delta: float) -> str:
    if delta > 0:
        return "Consolidate sections — fewer, longer sections"
    return "Add more section variety or transitions"
