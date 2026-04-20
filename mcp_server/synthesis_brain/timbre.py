"""Render-based timbre extraction.

Builds a TimbralFingerprint from captured spectrum / loudness / spectral-shape
data. The inputs come from existing perception tools (capture_audio →
analyze_spectrum_offline / analyze_loudness / get_spectral_shape when
FluCoMa is available).

This layer is intentionally pure Python — no I/O. Callers capture audio
and feed the dicts here. PR10 ships a heuristic first pass; later PRs
will add model-driven extraction on render-based features.
"""

from __future__ import annotations

from typing import Optional

from .models import TimbralFingerprint


# ── Band-based brightness / warmth mapping ──────────────────────────────
#
# The M4L analyzer returns an 8-band spectrum by default. When a full
# spectrum dict is passed, we look for these band keys in order. If the
# raw {freq: magnitude} shape is passed instead, we fall back to a coarser
# low/mid/high split.

_BANDS = ("sub", "low", "low_mid", "mid", "high_mid", "high", "very_high", "ultra")


def _band_energy(spectrum: Optional[dict], band: str) -> float:
    """Read a single band's energy from a spectrum dict. Defaults to 0."""
    if not spectrum:
        return 0.0
    val = spectrum.get(band)
    if val is None and "bands" in spectrum:
        val = spectrum["bands"].get(band)
    try:
        return float(val or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_to_range(value: float, low: float = -1.0, high: float = 1.0) -> float:
    """Clamp to [-1, 1]."""
    return max(low, min(high, value))


def extract_timbre_fingerprint(
    spectrum: Optional[dict] = None,
    loudness: Optional[dict] = None,
    spectral_shape: Optional[dict] = None,
) -> TimbralFingerprint:
    """Build a TimbralFingerprint from captured analysis data.

    Inputs are all optional — the function degrades gracefully when only
    some dimensions are measurable.

      spectrum: either {sub, low, low_mid, mid, high_mid, high, very_high, ultra}
        or {"bands": {...}} — the 8-band shape returned by get_master_spectrum /
        analyze_spectrum_offline. Missing bands default to 0.
      loudness: {"rms": float, "peak": float, "lufs": float, "lra": float} —
        output shape from analyze_loudness.
      spectral_shape: FluCoMa descriptors when available — {"centroid", "flatness",
        "rolloff", "crest"} (see get_spectral_shape).

    Heuristic dimension mapping (each dimension is clamped to [-1, 1]):
      brightness ← (high_mid + high - low_mid) / total, scaled; or centroid / 10000
      warmth     ← low_mid / total — classic low-mid richness
      bite       ← high_mid / mid — the "bite" frequency balance
      softness   ← 1.0 - crest (if present) or 1.0 - peak/rms
      instability ← flatness (if present) — noisier = less stable pitch
      width      ← not from single-channel data; left at 0 (stereo support in PR11+)
      texture_density ← flatness proxy — more noise-like = denser texture
      movement   ← not from single capture — left at 0
      polish     ← rough dynamic-range proxy: rms / peak closer to 1 = less polished
    """
    bands = {b: _band_energy(spectrum, b) for b in _BANDS}
    total = sum(bands.values())
    # Silent/empty input → neutral fingerprint. Band-derived dimensions
    # need real signal to be meaningful; falling back to 0 everywhere is
    # more honest than forcing brightness/warmth into the extremes.
    has_signal = total > 1e-6
    total_safe = total if has_signal else 1.0

    low_mid = bands["low_mid"]
    mid = bands["mid"] or 0.001
    high_mid = bands["high_mid"]
    high = bands["high"]

    # brightness ∈ [-1, 1] — bias on high-band presence relative to low-mid
    brightness = (
        _normalize_to_range((high_mid + high - low_mid) / total_safe * 2.0)
        if has_signal else 0.0
    )
    # Prefer spectral centroid when available (model-driven).
    shape = spectral_shape or {}
    centroid = shape.get("centroid")
    if centroid is not None:
        # Centroid typically in Hz — map 200Hz → -0.8, 5000Hz → +0.8.
        try:
            c = float(centroid)
            # Log-scale mapping is fairer; approximate with piecewise linear.
            if c <= 200:
                brightness = -0.8
            elif c >= 5000:
                brightness = 0.8
            else:
                # linear over log(200..5000) ≈ 2.30 .. 3.70
                import math
                t = (math.log10(c) - math.log10(200)) / (math.log10(5000) - math.log10(200))
                brightness = _normalize_to_range(-0.8 + t * 1.6)
        except (TypeError, ValueError):
            pass

    warmth = (
        _normalize_to_range(low_mid / total_safe * 4.0 - 1.0)
        if has_signal else 0.0
    )
    bite = (
        _normalize_to_range((high_mid / mid) - 1.0)
        if has_signal else 0.0
    )

    # softness via crest factor (lower crest = more sustained / softer)
    crest = shape.get("crest") if spectral_shape else None
    if crest is not None:
        try:
            softness = _normalize_to_range(1.0 - float(crest) / 10.0)
        except (TypeError, ValueError):
            softness = 0.0
    elif loudness:
        peak = float(loudness.get("peak", 0.0) or 0.0)
        rms = float(loudness.get("rms", 0.0) or 0.0)
        if peak > 0:
            softness = _normalize_to_range(rms / peak * 2.0 - 1.0)
        else:
            softness = 0.0
    else:
        softness = 0.0

    # instability + texture_density via spectral flatness
    flatness = shape.get("flatness") if spectral_shape else None
    if flatness is not None:
        try:
            f = float(flatness)
            instability = _normalize_to_range(f * 2.0 - 1.0)
            texture_density = _normalize_to_range(f * 2.0 - 1.0)
        except (TypeError, ValueError):
            instability = 0.0
            texture_density = 0.0
    else:
        instability = 0.0
        texture_density = 0.0

    # polish = inverse of crest dominance (very crest-heavy = unpolished)
    if crest is not None:
        try:
            polish = _normalize_to_range(1.0 - float(crest) / 8.0)
        except (TypeError, ValueError):
            polish = 0.0
    else:
        polish = 0.0

    return TimbralFingerprint(
        brightness=round(brightness, 3),
        warmth=round(warmth, 3),
        bite=round(bite, 3),
        softness=round(softness, 3),
        instability=round(instability, 3),
        width=0.0,  # stereo detection in later PRs
        texture_density=round(texture_density, 3),
        movement=0.0,  # single-capture — no movement signal
        polish=round(polish, 3),
    )


def diff_fingerprint(a: TimbralFingerprint, b: TimbralFingerprint) -> dict:
    """Return per-dimension delta a → b.

    Useful after a branch has been auditioned: capture audio before and
    after, extract fingerprints for each, and diff to see which dimensions
    actually moved.
    """
    return {
        "brightness": round(b.brightness - a.brightness, 3),
        "warmth": round(b.warmth - a.warmth, 3),
        "bite": round(b.bite - a.bite, 3),
        "softness": round(b.softness - a.softness, 3),
        "instability": round(b.instability - a.instability, 3),
        "width": round(b.width - a.width, 3),
        "texture_density": round(b.texture_density - a.texture_density, 3),
        "movement": round(b.movement - a.movement, 3),
        "polish": round(b.polish - a.polish, 3),
    }
