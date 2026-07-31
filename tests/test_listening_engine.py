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
    STEREO_RATIO_CEILING,
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
    assert groove["grid_division"] == 8, groove


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
    assert report.channels == 2
    for dim in ("brightness", "punch", "energy", "warmth", "weight"):
        assert dim in report.dimensions, report.dimensions
    for dim in ("width", "polish", "motion_cv"):
        assert dim in report.dimensions, report.dimensions


def test_compare_detects_known_perturbation():
    """compare() must flag a real change above EPSILON and stay silent on
    an identical pair."""
    from mcp_server.listening.engine import compare, format_verdict

    rng = np.random.default_rng(11)
    base = (rng.standard_normal(SR * 5) * 0.2).astype(np.float32)
    before = extract_features(_stereo(base), SR, bpm=120)

    # identical pair: no significant changes
    same = compare(before, extract_features(_stereo(base), SR, bpm=120))
    assert same["unchanged"], same["significant_changes"]
    assert format_verdict(same) == "No significant perceptual change detected."

    # -6 dB gain drop: loudness must dominate the ranked changes
    after = extract_features(_stereo(base * 0.5), SR, bpm=120)
    result = compare(before, after)
    assert not result["unchanged"]
    lufs = [c for c in result["significant_changes"]
            if c["metric"] == "integrated_lufs"]
    assert lufs and abs(lufs[0]["delta"] + 6.0) < 0.5, lufs
    assert "energy" in result["dimension_deltas"]
    assert result["dimension_deltas"]["energy"]["delta"] < 0
    # snapshots ready for evaluate_move
    for side in ("before_snapshot", "after_snapshot"):
        assert set(result[side]["spectrum"]) == {
            "sub_low", "sub", "low", "low_mid", "mid",
            "high_mid", "high", "presence", "air",
        }
    assert "integrated_lufs" in format_verdict(result)


def test_tools_path_resolution_rejects_directories(tmp_path, monkeypatch):
    """Directories, empty names, and missing files must produce the clean
    ValueError — never a raw soundfile error (regression: review 2026-07-30)."""
    import soundfile as sf

    from mcp_server.listening import tools as listening_tools

    monkeypatch.setattr(listening_tools, "CAPTURE_DIR", str(tmp_path))
    (tmp_path / "subdir").mkdir()
    wav = tmp_path / "real.wav"
    sf.write(wav, np.zeros((SR, 2), dtype=np.float32), SR)

    resolve = listening_tools._resolve_capture_path
    assert resolve("real") == str(wav)
    assert resolve("real.wav") == str(wav)
    assert resolve(str(wav)) == str(wav)

    for bad in ("", "subdir", str(tmp_path), "nope"):
        with pytest.raises(ValueError, match="not found"):
            resolve(bad)


def test_true_peak_uses_per_channel_max_not_mono_downmix():
    """Regression (review finding [1]): true peak must be measured per
    channel and maxed, not from the L+R mono downmix — _stereo() in this
    file duplicates L into R, so this test deliberately builds L != R."""
    tone = _sine(1000.0, seconds=2.0, amp=0.95)
    panned = np.stack([tone, np.zeros_like(tone)], axis=1).astype(np.float32)
    report = extract_features(panned, SR)
    true_peak_dbtp = report.extended["loudness"]["true_peak_dbtp"]
    # ~0.95 amplitude -> ~-0.45 dBTP; the mono downmix (silent right channel)
    # halves the peak first and reads ~-6.5 dBTP instead.
    assert true_peak_dbtp > -2.0, true_peak_dbtp


def test_true_peak_anti_phase_not_reported_as_silence():
    """Regression (review finding [1]): anti-phase L/-R cancels to exact
    silence on a mono downmix, but the true peak (and the fact the clip is
    audibly loud per LUFS) must not be lost."""
    tone = _sine(1000.0, seconds=2.0, amp=0.9)
    anti_phase = np.stack([tone, -tone], axis=1).astype(np.float32)
    report = extract_features(anti_phase, SR)
    loudness = report.extended["loudness"]
    # ~0.9 amplitude -> ~-0.9 dBTP; the mono downmix is exact zero and would
    # floor to -120 dBTP while integrated_lufs correctly reads well above floor.
    assert loudness["true_peak_dbtp"] > -5.0, loudness
    assert loudness["integrated_lufs"] > LUFS_FLOOR + 5.0, loudness


def test_stereo_ratios_clamped_on_phase_cancellation():
    """Regression (review finding [5]): near-total mid cancellation must not
    blow the side/mid and low-side ratios up to physically meaningless
    values that would dominate compare()'s ranking."""
    tone = _sine(300.0, seconds=2.0, amp=0.9)
    anti_phase = np.stack([tone, -tone], axis=1).astype(np.float32)
    stereo = extract_features(anti_phase, SR).extended["stereo"]
    assert stereo["side_mid_ratio"] <= STEREO_RATIO_CEILING + 1e-9, stereo
    assert stereo["low_side_ratio"] <= STEREO_RATIO_CEILING + 1e-9, stereo


def test_compare_reports_centroid_change_from_silence():
    """Regression (review finding [6]): a silence -> bright transition must
    still surface a spectral_shape/centroid entry in significant_changes,
    even though the relative-ratio test's denominator (bc) is 0."""
    from mcp_server.listening.engine import compare

    silence = extract_features(_stereo(np.zeros(SR * 6, dtype=np.float32)), SR)
    bright = extract_features(_stereo(_sine(9000.0, seconds=6.0, amp=0.5)), SR)
    assert silence.snapshot["spectral_shape"]["centroid"] == 0.0

    result = compare(silence, bright)
    centroid_changes = [
        c for c in result["significant_changes"]
        if c["area"] == "spectral_shape" and c["metric"] == "centroid"
    ]
    assert centroid_changes, result["significant_changes"]
    assert centroid_changes[0]["after"] > 5000.0, centroid_changes


def test_extract_features_rejects_non_finite_audio():
    """Regression (review finding [7a]): NaN/Inf samples must raise a clean
    ValueError, never a raw librosa.ParameterError from deep in the stack."""
    bad = _stereo(_sine(300.0, seconds=1.0))
    bad[100, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        extract_features(bad, SR)


def test_tools_analyze_wraps_soundfile_read_errors(tmp_path, monkeypatch):
    """Regression (review finding [7b]): a 0-byte/truncated-header capture
    must raise a clean ValueError from _analyze(), never a raw
    soundfile.LibsndfileError — reachable per _relocate_capture_file's
    documented ~480ms race with a still-writing capture."""
    from mcp_server.listening import tools as listening_tools

    monkeypatch.setattr(listening_tools, "CAPTURE_DIR", str(tmp_path))
    truncated = tmp_path / "truncated.wav"
    truncated.write_bytes(b"")

    with pytest.raises(ValueError, match="Could not read audio file"):
        listening_tools._analyze(str(truncated), None, None)
