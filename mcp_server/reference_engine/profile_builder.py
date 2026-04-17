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

    # BUG-B50 fix: the old code hardcoded loudness_posture=0.0 and
    # empty spectral_contour / width_depth because StyleTactic entries
    # don't carry those fields. We now derive them heuristically from
    # the device_chain (each device's params leak its intended sonic
    # shape — e.g., Auto Filter at 800Hz low-pass = darker spectrum,
    # Utility Width > 0.6 = wider stereo). Rough but non-empty values
    # are better than zeros for downstream reference-gap analysis.
    loudness_posture = _derive_loudness_posture(style_tactics)
    spectral_contour = _derive_spectral_contour(style_tactics)
    width_depth = _derive_width_depth(style_tactics)

    return ReferenceProfile(
        source_type="style",
        loudness_posture=loudness_posture,
        spectral_contour=spectral_contour,
        width_depth=width_depth,
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


# ── BUG-B50 derivations — style → loudness/spectral/width heuristics ──────


def _derive_loudness_posture(style_tactics: list[dict]) -> float:
    """Heuristic: compression / saturation / limiter devices imply a
    specific loudness posture. Glue / Ratio>3 → loud, saturator drive
    high → cranked/loud, delay/reverb-heavy → quieter mix."""
    loud_signals = 0
    quiet_signals = 0
    for tactic in style_tactics:
        for dev in tactic.get("device_chain", []):
            name = str(dev.get("name", "")).lower()
            params = dev.get("params", {}) or {}
            if "glue" in name or "limiter" in name:
                loud_signals += 2
            if name == "saturator" or "overdrive" in name:
                drive = float(params.get("Drive", 0) or 0)
                if drive >= 6:
                    loud_signals += 1
            if name == "compressor":
                ratio = float(params.get("Ratio", 0) or 0)
                if ratio >= 4:
                    loud_signals += 1
            if name == "reverb":
                # Heavy reverb tails push the mix quieter
                wet = float(params.get("Dry/Wet", 0) or 0)
                if wet >= 0.6:
                    quiet_signals += 1
    # Normalize to -1..+1 range (loud=+1, quiet=-1, neutral=0)
    if loud_signals == 0 and quiet_signals == 0:
        return 0.0
    net = (loud_signals - quiet_signals) / max(
        loud_signals + quiet_signals, 1
    )
    return round(net, 2)


def _derive_spectral_contour(style_tactics: list[dict]) -> dict:
    """Heuristic: Auto Filter frequencies + device names leak the
    target spectrum. Low-pass filters → dark, EQ Eight with no params
    → neutral, saturators → mid-forward."""
    brightness = 0.5  # neutral starting point
    mid_emphasis = 0.5
    dark_hits = 0
    bright_hits = 0
    for tactic in style_tactics:
        for dev in tactic.get("device_chain", []):
            name = str(dev.get("name", "")).lower()
            params = dev.get("params", {}) or {}
            if "auto filter" in name or name == "autofilter":
                freq = float(params.get("Frequency", 1500) or 1500)
                # Ableton Auto Filter Frequency is 20-22000; below 2k hints dark
                if freq < 2000:
                    dark_hits += 1
                elif freq > 5000:
                    bright_hits += 1
            if "saturator" in name or "overdrive" in name:
                mid_emphasis += 0.1
    if dark_hits > bright_hits:
        brightness = 0.3
    elif bright_hits > dark_hits:
        brightness = 0.75
    return {
        "band_balance": {
            "sub": 0.45,
            "low": 0.5,
            "mid": min(1.0, mid_emphasis),
            "high_mid": round(0.3 + brightness * 0.4, 2),
            "high": round(0.2 + brightness * 0.5, 2),
        },
        "brightness": round(brightness, 2),
        "centroid_hint": "dark" if brightness < 0.4
                         else "bright" if brightness > 0.65
                         else "neutral",
    }


def _derive_width_depth(style_tactics: list[dict]) -> dict:
    """Heuristic: Utility Width, Chorus-Ensemble, or heavy reverb
    implies a wider stereo field; dry chains imply narrow."""
    width_value = 0.5
    depth_value = 0.5
    for tactic in style_tactics:
        for dev in tactic.get("device_chain", []):
            name = str(dev.get("name", "")).lower()
            params = dev.get("params", {}) or {}
            if name == "utility":
                w = params.get("Width")
                if w is not None:
                    try:
                        width_value = max(width_value, float(w))
                    except (TypeError, ValueError):
                        pass
            if "reverb" in name:
                wet = float(params.get("Dry/Wet", 0) or 0)
                if wet > 0.4:
                    depth_value = max(depth_value, 0.7)
                    width_value = max(width_value, 0.65)
            if "chorus" in name or "ensemble" in name:
                width_value = max(width_value, 0.75)
            if "delay" in name:
                wet = float(params.get("Dry/Wet", 0) or 0)
                if wet > 0.2:
                    depth_value = max(depth_value, 0.6)
    return {
        "stereo_width": round(width_value, 2),
        "depth": round(depth_value, 2),
        "depth_hint": (
            "deep" if depth_value > 0.6 else
            "intimate" if depth_value < 0.4 else
            "neutral"
        ),
    }
