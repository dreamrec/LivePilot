"""Listening Engine ground-truth tests — synthetic signals with known
properties (graduated from spikes/listening/synthetic_checks.py)."""

from __future__ import annotations

import math
from dataclasses import asdict

import numpy as np
import pytest

librosa = pytest.importorskip("librosa")

from mcp_server.listening.engine import (  # noqa: E402
    LUFS_FLOOR,
    extract_features,
)

SR = 48000


def _stereo(mono: np.ndarray) -> np.ndarray:
    return np.stack([mono, mono], axis=1).astype(np.float32)


def _sine(freq: float, seconds: float = 6.0, amp: float = 1.0) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * math.pi * freq * t)).astype(np.float32)


def _clicks(bpm: float, division: int, seconds: float = 8.0,
            offset_ms: float = 0.0, amp: float = 0.9) -> np.ndarray:
    step = 60.0 / bpm / division
    out = np.zeros(int(SR * seconds), dtype=np.float32)
    i, t = 0, 0.0
    while t < seconds - 0.05:
        t_hit = t + (offset_ms / 1000.0 if i % 2 else 0.0)
        idx = int(t_hit * SR)
        out[idx:idx + 32] = amp * np.hanning(64)[:32].astype(np.float32)
        i += 1
        t += step
    return out


def _walk_finite(obj, path="") -> list[str]:
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            bad += _walk_finite(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            bad += _walk_finite(v, f"{path}[{i}]")
    elif isinstance(obj, float) and not np.isfinite(obj):
        bad.append(path)
    return bad


def test_in_band_sine_calibration():
    report = extract_features(_stereo(_sine(700.0)), SR)
    bands = report.snapshot["spectrum"]
    assert 0.9 <= bands["mid"] <= 1.05, bands["mid"]
    others = {k: v for k, v in bands.items() if k != "mid"}
    assert max(others.values()) < 0.05, others


def test_boundary_tone_conserves_energy():
    report = extract_features(_stereo(_sine(1000.0)), SR)
    b = report.snapshot["spectrum"]
    total = math.sqrt(b["mid"] ** 2 + b["high_mid"] ** 2)
    assert 0.9 <= total <= 1.1, (b["mid"], b["high_mid"])


def test_exact_grid_is_tight_and_offset_raises_mad():
    on_grid = extract_features(_stereo(_clicks(120, 4)), SR, bpm=120)
    mad = on_grid.extended["groove"]["microtiming_mad_ms"]
    assert mad is not None and mad < 5.0, mad

    offset = extract_features(_stereo(_clicks(120, 4, offset_ms=15.0)), SR, bpm=120)
    mad2 = offset.extended["groove"]["microtiming_mad_ms"]
    assert mad2 is not None and mad2 - mad > 4.0, (mad, mad2)


def test_fine_grid_auto_division():
    report = extract_features(_stereo(_clicks(120, 8)), SR, bpm=120)
    groove = report.extended["groove"]
    assert groove["microtiming_mad_ms"] is not None
    assert groove["microtiming_mad_ms"] < 5.0, groove


def test_stereo_field_ground_truth():
    rng = np.random.default_rng(7)
    uncorrelated = np.stack(
        [rng.standard_normal(SR * 4) * 0.3, rng.standard_normal(SR * 4) * 0.3],
        axis=1,
    ).astype(np.float32)
    s = extract_features(uncorrelated, SR).extended["stereo"]
    assert abs(s["correlation"]) < 0.05
    assert 0.8 <= s["side_mid_ratio"] <= 1.2

    mono_noise = (rng.standard_normal(SR * 4) * 0.3).astype(np.float32)
    s = extract_features(_stereo(mono_noise), SR).extended["stereo"]
    assert s["correlation"] > 0.99
    assert s["side_mid_ratio"] < 0.01


def test_silence_is_finite_and_floored():
    report = extract_features(np.zeros((SR * 6, 2), dtype=np.float32), SR)
    assert not _walk_finite(asdict(report))
    assert report.snapshot["loudness"]["integrated_lufs"] == LUFS_FLOOR


def test_mono_shapes_and_short_input():
    tone = _sine(440.0, seconds=2.0, amp=0.5)
    for arr in (tone, tone[:, None]):
        assert extract_features(arr, SR).channels == 1
    short = extract_features(_stereo(_sine(300.0, seconds=0.2)), SR)
    assert short.extended["loudness"]["approximate"] is True


def test_loudness_range_counts_tail_window():
    quiet = np.random.default_rng(3).standard_normal(SR * 3) * 1e-4
    loud = np.random.default_rng(4).standard_normal(SR * 1) * 0.4
    clip = np.concatenate([quiet, loud]).astype(np.float32)
    report = extract_features(_stereo(clip), SR)
    assert report.extended["loudness"]["loudness_range_lu"] > 1.0


def test_quiet_signal_gates_novelty():
    pulses = _clicks(120, 4, amp=10 ** (-80 / 20))
    report = extract_features(_stereo(pulses), SR)
    assert "novelty" not in report.snapshot


def test_canonical_dimensions_present():
    report = extract_features(_stereo(_sine(700.0, seconds=2.0, amp=0.5)), SR)
    for dim in ("brightness", "punch", "energy", "warmth", "weight"):
        assert dim in report.dimensions, report.dimensions
    for dim in ("width", "polish", "motion_cv"):
        assert dim in report.dimensions, report.dimensions
