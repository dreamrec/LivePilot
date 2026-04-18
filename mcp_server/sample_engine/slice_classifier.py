"""Spectral classification of Simpler-slice drum break segments.

Lessons from the 2026-04-18 creative session that drove this module:

- Never assume slice 0 is a kick. Slice content depends on transient
  detection order in the source audio, not drum-rack convention.
- Snares ALWAYS have 20-35% mid-frequency energy (drum body resonance).
  Hi-hats / cymbals have <25% mid (they're thin metal discs with no
  resonant body). This mid-content threshold is the critical separator
  that tripped up the first classification pass.
- Ghosts are defined by low peak amplitude (<0.35) regardless of spectrum.

Thresholds validated against "Break Ghosts 90 bpm" (Ableton Core Library)
in the session. See ``feedback_analyze_slices_before_programming`` memory
entry for the full story and the specific slice map for that sample.

This module is pure Python (numpy only). No LivePilot / Ableton /
FastMCP dependencies — testable and runnable in isolation.
"""
from __future__ import annotations

from typing import List, Literal, Sequence, TypedDict

import numpy as np


Label = Literal["KICK", "SNARE", "HAT", "ghost"]


class SliceFeatures(TypedDict):
    """Per-slice classification result plus the features that drove the decision."""

    index: int
    label: Label
    peak: float
    rms: float
    sub_pct: float
    low_pct: float
    mid_pct: float
    high_pct: float


# ---------------------------------------------------------------------------
# Band boundaries (Hz). Tuned against the 2026-04-18 session's working set.
# ---------------------------------------------------------------------------

_SUB_MAX = 100.0    # sub-bass (kick fundamentals live here)
_LOW_MAX = 300.0    # body / low-mid (kick "thud" + bass fundamentals)
_MID_MAX = 3000.0   # presence / drum body / vocals
# Everything above _MID_MAX is "high" (sizzle / air / cymbal).


# ---------------------------------------------------------------------------
# Classification thresholds. DO NOT loosen these without re-validating on a
# real break — the 2026-04-18 session proved that relaxing the HAT mid-cap
# to 32% misclassifies loud snares as hats.
# ---------------------------------------------------------------------------

_GHOST_PEAK = 0.35        # Below this peak → ghost regardless of spectrum
_KICK_SUB_LOW_MIN = 0.45  # sub + low must be this dominant
_KICK_HIGH_MAX = 0.40     # kicks never have >40% high
_SNARE_MID_MIN = 0.25     # snares HAVE a drum body (mid content)
_SNARE_HIGH_MIN = 0.40    # + sizzle
_SNARE_PEAK_MIN = 0.60    # + loud enough to not be a ghost
_HAT_HIGH_MIN = 0.70      # hats are thin metal — overwhelmingly high
_HAT_MID_MAX = 0.25       # hats have almost no drum body


def _band_energy(segment: np.ndarray, sr: int) -> tuple[float, float, float, float]:
    """Return (sub, low, mid, high) energy fractions that sum to ~1.0.

    Uses an rFFT. If the segment is empty or silent, returns equal quarters
    so downstream logic doesn't have to handle zero-sum edge cases (the
    caller still sees silence via the peak/rms fields).
    """
    if len(segment) < 2:
        return 0.25, 0.25, 0.25, 0.25
    spec = np.abs(np.fft.rfft(segment))
    total = float(spec.sum())
    if total <= 0:
        return 0.25, 0.25, 0.25, 0.25
    freqs = np.fft.rfftfreq(len(segment), 1.0 / sr)
    sub = float(spec[freqs < _SUB_MAX].sum() / total)
    low = float(spec[(freqs >= _SUB_MAX) & (freqs < _LOW_MAX)].sum() / total)
    mid = float(spec[(freqs >= _LOW_MAX) & (freqs < _MID_MAX)].sum() / total)
    high = float(spec[freqs >= _MID_MAX].sum() / total)
    return sub, low, mid, high


def classify_segment(segment: np.ndarray, sr: int) -> Label:
    """Classify a single audio segment as KICK / SNARE / HAT / ghost.

    Returns the label string. See module docstring for the reasoning behind
    each threshold.
    """
    if len(segment) < 2:
        return "ghost"
    peak = float(np.max(np.abs(segment)))
    if peak < _GHOST_PEAK:
        return "ghost"

    sub, low, mid, high = _band_energy(segment, sr)

    # KICK: sub+low dominance with limited high content.
    if (sub + low) >= _KICK_SUB_LOW_MIN and high < _KICK_HIGH_MAX:
        return "KICK"

    # HAT: overwhelmingly high-freq, almost no drum-body mid content.
    if high >= _HAT_HIGH_MIN and mid <= _HAT_MID_MAX:
        return "HAT"

    # SNARE: broadband (mid body + high sizzle) AND loud.
    if (
        mid >= _SNARE_MID_MIN
        and high >= _SNARE_HIGH_MIN
        and peak >= _SNARE_PEAK_MIN
    ):
        return "SNARE"

    # Fallback for ambiguous mid/high dominant loud hits — usually
    # snares with unusual spectrum (e.g., rim-shots, piccolo snare).
    if peak >= _SNARE_PEAK_MIN and (mid + high) >= 0.70:
        return "SNARE"

    # If nothing else matched but there's real energy, call it a hat
    # rather than a ghost (ghost is reserved for quiet hits).
    return "HAT"


def classify_slices(
    audio: np.ndarray,
    sr: int,
    frame_boundaries: Sequence[int],
) -> List[SliceFeatures]:
    """Classify every slice defined by ``frame_boundaries``.

    ``frame_boundaries`` is a list of N+1 frame positions defining N slices.
    For a sample with slices starting at frames [0, 1000, 3000, 5000] and
    total length 10000 frames, pass [0, 1000, 3000, 5000, 10000].

    Stereo input is auto-downmixed (mean of the two channels).

    Returns a list of ``SliceFeatures`` in slice-index order.
    """
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    results: List[SliceFeatures] = []
    for i in range(len(frame_boundaries) - 1):
        start = int(frame_boundaries[i])
        end = int(frame_boundaries[i + 1])
        segment = audio[start:end]
        label = classify_segment(segment, sr)
        peak = float(np.max(np.abs(segment))) if len(segment) else 0.0
        rms = float(np.sqrt(np.mean(segment ** 2))) if len(segment) else 0.0
        sub, low, mid, high = _band_energy(segment, sr)
        results.append(
            SliceFeatures(
                index=i,
                label=label,
                peak=peak,
                rms=rms,
                sub_pct=sub,
                low_pct=low,
                mid_pct=mid,
                high_pct=high,
            )
        )
    return results
