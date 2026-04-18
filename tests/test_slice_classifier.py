"""Tests for mcp_server/sample_engine/slice_classifier.py.

Synthesizes drum hits directly (no WAV fixtures committed to the repo)
and verifies the classifier labels them correctly. Thresholds were
validated on the real "Break Ghosts 90 bpm" sample in the 2026-04-18
creative session — see feedback_analyze_slices_before_programming.
"""
from __future__ import annotations

import numpy as np
import pytest

from mcp_server.sample_engine.slice_classifier import (
    classify_segment,
    classify_slices,
)


SR = 44100


# ---------------------------------------------------------------------------
# Synthetic drum hit fixtures — deterministic (seeded) where noise is used.
# ---------------------------------------------------------------------------


def _synth_kick(duration_s: float = 0.3, sr: int = SR) -> np.ndarray:
    """Low-frequency sine with a fast pitch drop. Classic kick."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    freq = 120 * np.exp(-t * 25) + 55
    env = np.exp(-t * 8)
    return (np.sin(2 * np.pi * freq * t) * env).astype(np.float32) * 0.95


def _synth_snare(duration_s: float = 0.2, sr: int = SR) -> np.ndarray:
    """Mid body + bandpassed sizzle — matches real snare spectrum.

    Real snare wires sit in the 1-5kHz region. Raw white noise would
    dominate the high band by bin count (Nyquist = 22kHz), which would
    misclassify as HAT. We bandpass the sizzle via FFT masking so the
    synthetic snare has realistic 20-35% mid content.
    """
    rng = np.random.default_rng(42)
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)

    # Mid body: 220Hz fundamental + 440Hz overtone, quick decay
    body = (
        np.sin(2 * np.pi * 220 * t) + 0.5 * np.sin(2 * np.pi * 440 * t)
    ) * np.exp(-t * 16)

    # Snare-wire sizzle: bandpassed noise centered on 1-5kHz
    noise = rng.standard_normal(len(t))
    spec = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(len(noise), 1.0 / sr)
    mask = np.ones_like(spec, dtype=float)
    mask[freqs < 500] = 0.05   # Kill sub-lows
    mask[freqs > 6000] = 0.15  # Roll off extreme highs
    sizzle = np.real(np.fft.irfft(spec * mask, len(noise))) * np.exp(-t * 10)
    sizzle /= np.max(np.abs(sizzle)) + 1e-9

    mix = 0.65 * body + 0.40 * sizzle
    return mix.astype(np.float32) * 0.9


def _synth_hat(duration_s: float = 0.06, sr: int = SR) -> np.ndarray:
    """High-frequency shimmer with tight decay — thin metal disc.

    We synthesize by filtering noise aggressively high-pass so the
    signal is overwhelmingly >3kHz content.
    """
    rng = np.random.default_rng(42)
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    noise = rng.standard_normal(len(t))
    # High-pass via repeated differencing. Each diff attenuates lows.
    hi = noise
    for _ in range(5):
        hi = np.diff(hi, prepend=0)
    hi = hi / (np.max(np.abs(hi)) + 1e-9)
    env = np.exp(-t * 55)
    return (hi * env).astype(np.float32) * 0.75


def _synth_ghost(duration_s: float = 0.08, sr: int = SR) -> np.ndarray:
    """Very quiet sub-threshold signal — anything below 0.35 peak."""
    rng = np.random.default_rng(123)
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (rng.standard_normal(len(t)) * np.exp(-t * 30)).astype(np.float32) * 0.12


# ---------------------------------------------------------------------------
# classify_segment: single-segment label tests.
# ---------------------------------------------------------------------------


def test_classify_kick_segment():
    segment = _synth_kick()
    label = classify_segment(segment, SR)
    assert label == "KICK", f"Expected KICK, got {label}"


def test_classify_snare_segment():
    segment = _synth_snare()
    label = classify_segment(segment, SR)
    assert label == "SNARE", f"Expected SNARE, got {label}"


def test_classify_hat_segment():
    segment = _synth_hat()
    label = classify_segment(segment, SR)
    assert label == "HAT", f"Expected HAT, got {label}"


def test_classify_ghost_segment():
    segment = _synth_ghost()
    label = classify_segment(segment, SR)
    assert label == "ghost", f"Expected ghost, got {label}"


def test_classify_empty_segment_is_ghost():
    """Zero-length segments return ghost, not a crash."""
    assert classify_segment(np.zeros(0), SR) == "ghost"
    assert classify_segment(np.zeros(1), SR) == "ghost"


def test_classify_silence_is_ghost():
    """Peak below ghost threshold → ghost."""
    assert classify_segment(np.zeros(1000), SR) == "ghost"


# ---------------------------------------------------------------------------
# classify_slices: end-to-end over a stitched waveform.
# ---------------------------------------------------------------------------


def test_classify_slices_full_break():
    """Build a synthetic break with 4 slices (kick, hat, snare, ghost) and classify."""
    segments = [_synth_kick(), _synth_hat(), _synth_snare(), _synth_ghost()]
    audio = np.concatenate(segments)
    frame_boundaries = [0]
    for s in segments:
        frame_boundaries.append(frame_boundaries[-1] + len(s))

    result = classify_slices(audio, SR, frame_boundaries)
    assert len(result) == 4
    labels = [r["label"] for r in result]
    assert labels == ["KICK", "HAT", "SNARE", "ghost"]


def test_classify_slices_includes_features():
    """Each slice result includes the feature breakdown used for the decision."""
    audio = _synth_kick()
    result = classify_slices(audio, SR, [0, len(audio)])
    assert len(result) == 1
    entry = result[0]
    assert entry["label"] == "KICK"
    assert 0 <= entry["peak"] <= 1
    assert 0 <= entry["rms"] <= 1
    # Band fractions should sum to 1
    total = entry["sub_pct"] + entry["low_pct"] + entry["mid_pct"] + entry["high_pct"]
    assert total == pytest.approx(1.0, abs=0.01)


def test_classify_slices_handles_empty_boundaries():
    """Zero-length slices (end == start) don't crash — return ghost."""
    audio = np.zeros(1000)
    result = classify_slices(audio, SR, [500, 500, 1000])
    assert result[0]["label"] == "ghost"
    assert result[1]["label"] == "ghost"


def test_classify_slices_preserves_index_order():
    """Result list is in slice-index order."""
    segments = [_synth_kick(), _synth_snare(), _synth_kick()]
    audio = np.concatenate(segments)
    boundaries = [0]
    for s in segments:
        boundaries.append(boundaries[-1] + len(s))
    result = classify_slices(audio, SR, boundaries)
    assert [r["index"] for r in result] == [0, 1, 2]
    assert result[0]["label"] == "KICK"
    assert result[1]["label"] == "SNARE"
    assert result[2]["label"] == "KICK"


def test_classify_slices_handles_stereo():
    """Stereo input is auto-downmixed to mono for analysis."""
    mono = _synth_kick()
    stereo = np.column_stack([mono, mono])
    result = classify_slices(stereo, SR, [0, len(mono)])
    assert result[0]["label"] == "KICK"
