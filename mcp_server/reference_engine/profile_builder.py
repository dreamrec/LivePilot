"""Reference profile builders — construct ReferenceProfile from various sources.

Pure functions, zero I/O.
"""

from __future__ import annotations

from .models import ReferenceProfile


# ── Audio Reference ────────────────────────────────────────────────


def build_audio_reference_profile(comparison_data: dict) -> ReferenceProfile:
    """Build a ReferenceProfile from compare_to_reference output.

    Args:
        comparison_data: dict returned by perception engine's
            compare_to_reference (keys: reference_lufs, centroid_delta_hz,
            stereo_width_ref, band_deltas, suggestions, etc.)

    Returns:
        ReferenceProfile with source_type="audio".
    """
    band_deltas = comparison_data.get("band_deltas", {})

    # Reconstruct approximate reference spectral contour from band deltas.
    # The deltas are (mix - ref), so ref bands are conceptually the baseline.
    spectral_contour: dict = {
        "band_balance": band_deltas,
        "centroid_delta_hz": comparison_data.get("centroid_delta_hz", 0.0),
    }

    width_depth: dict = {
        "stereo_width": comparison_data.get("stereo_width_ref", 0.0),
    }

    # Extract loudness posture
    loudness = comparison_data.get("reference_lufs", comparison_data.get("ref_lufs", 0.0))

    return ReferenceProfile(
        source_type="audio",
        loudness_posture=float(loudness),
        spectral_contour=spectral_contour,
        width_depth=width_depth,
        density_arc=[],  # audio comparison doesn't provide density
        section_pacing=[],  # not available from offline comparison
        harmonic_character="",  # would need chroma analysis
        transition_tendencies=[],
    )


# ── Style Reference ───────────────────────────────────────────────


def build_style_reference_profile(style_tactics: list[dict]) -> ReferenceProfile:
    """Build a ReferenceProfile from style tactic data.

    Args:
        style_tactics: list of StyleTactic.to_dict() entries from the
            research engine's get_style_tactics.

    Returns:
        ReferenceProfile with source_type="style".
    """
    if not style_tactics:
        return ReferenceProfile(source_type="style")

    # Aggregate arrangement patterns into section_pacing
    section_pacing: list[dict] = []
    transition_tendencies: list[str] = []
    device_names: list[str] = []

    for tactic in style_tactics:
        # Arrangement patterns -> section pacing
        for pattern in tactic.get("arrangement_patterns", []):
            section_pacing.append({
                "label": pattern,
                "source": tactic.get("artist_or_genre", "unknown"),
            })

        # Automation gestures -> transition tendencies
        for gesture in tactic.get("automation_gestures", []):
            if gesture not in transition_tendencies:
                transition_tendencies.append(gesture)

        # Collect device names for harmonic character hints
        for dev in tactic.get("device_chain", []):
            name = dev.get("name", "")
            if name and name not in device_names:
                device_names.append(name)

    # Infer harmonic character from device chain
    harmonic_character = _infer_harmonic_character(device_names)

    # Estimate density from arrangement pattern count
    density_arc = _estimate_density_from_patterns(style_tactics)

    return ReferenceProfile(
        source_type="style",
        loudness_posture=0.0,  # style doesn't specify loudness
        spectral_contour={},  # style doesn't specify spectrum
        width_depth={},
        density_arc=density_arc,
        section_pacing=section_pacing,
        harmonic_character=harmonic_character,
        transition_tendencies=transition_tendencies,
    )


# ── Internal helpers ──────────────────────────────────────────────


def _infer_harmonic_character(device_names: list[str]) -> str:
    """Heuristic: infer harmonic character from common device names."""
    lower_names = [d.lower() for d in device_names]

    if any("reverb" in n for n in lower_names):
        if any("filter" in n for n in lower_names):
            return "atmospheric_filtered"
        return "spacious"
    if any("saturator" in n or "overdrive" in n or "amp" in n for n in lower_names):
        return "warm_harmonic"
    if any("operator" in n or "wavetable" in n for n in lower_names):
        return "synthetic"
    return "neutral"


def _estimate_density_from_patterns(style_tactics: list[dict]) -> list[float]:
    """Heuristic: estimate a density arc from arrangement patterns.

    More patterns / longer structures suggest higher density.
    """
    if not style_tactics:
        return []

    densities: list[float] = []
    for tactic in style_tactics:
        patterns = tactic.get("arrangement_patterns", [])
        # Simple heuristic: 1-2 patterns = sparse, 3+ = dense
        n = len(patterns)
        if n == 0:
            densities.append(0.2)
        elif n <= 2:
            densities.append(0.4)
        else:
            densities.append(min(0.9, 0.3 + n * 0.15))

    return densities
