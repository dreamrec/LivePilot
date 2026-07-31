"""Listening Engine — pure computation, zero I/O.

Extracts a perceptual feature report from raw audio samples and compares
two reports (before/after a creative move). The report carries two layers:

1. ``snapshot`` — canonical sonic-snapshot shape consumed by the existing
   evaluation stack (``normalize_sonic_snapshot`` / ``evaluate_move``):
   9 LivePilot spectrum bands, rms, peak, spectral_shape, onset, novelty,
   loudness.
2. ``extended`` — measurements the live 9-band cache cannot provide:
   stereo width, groove microtiming, transient character, per-band loudness
   movement, technical polish.

Calibration: band levels use Parseval/window-power energy calibration, so a
full-scale in-band sine reads ~1.0 in its band regardless of how its energy
leaks across bins. A tone sitting ON a band boundary genuinely splits its
energy between the two adjacent bands — physics, not a bug; per-band
readings within ~2 FFT bins of a boundary should not be interpreted as
isolating to a single band.

Canonical dimensions (brightness … novelty) are computed by the repo's real
``extract_dimension_value``, so reported values are exactly what
``evaluate_move`` scores.

Note on rms/peak semantics: these are whole-clip statistics. The live
M4L meters (``average~ 200 rms`` / ``peakamp~ 200``) are 200 ms rolling
windows sampled at call time — same 0..1 units, different integration time.
Deltas between two captures are self-consistent; do not diff a capture
statistic directly against a single live meter read.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..evaluation.feature_extractors import extract_dimension_value

# LivePilot 9-band definitions (mcp_server/tools/analyzer.py band table).
BANDS: list[tuple[str, float, float]] = [
    ("sub_low", 20.0, 60.0),
    ("sub", 60.0, 120.0),
    ("low", 120.0, 250.0),
    ("low_mid", 250.0, 500.0),
    ("mid", 500.0, 1000.0),
    ("high_mid", 1000.0, 2000.0),
    ("high", 2000.0, 4000.0),
    ("presence", 4000.0, 8000.0),
    ("air", 8000.0, 20000.0),
]

RHYTHM_SR = 22050  # librosa rhythm features operate on a mono downsample
ONSET_HOP = 128  # ~5.8 ms/frame at 22050 Hz; default 512 bakes in ~13 ms latency
MOTION_WINDOW_S = 0.4  # short-time window for per-band loudness movement
CLIP_THRESHOLD = 0.999
GRID_DIVISIONS = (3, 4, 6, 8)  # per-beat subdivisions tried for microtiming grid
LUFS_FLOOR = -70.0  # silence sentinel; pyloudnorm returns -inf on digital silence
NOVELTY_LUFS_GATE = -60.0  # below this, flux/onset ratios are numerical noise
STEREO_RATIO_CEILING = 10.0  # +20 dB side-over-mid; beyond this the ratio is a
# near-total-cancellation degeneracy (mid_rms -> ~0), not a meaningfully
# "wider" mix — saturate instead of reporting an unbounded/billions-scale value
CENTROID_FLOOR_HZ = 20.0  # BANDS[0] low edge; floors the centroid-ratio
# denominator so a silent 'before' (centroid gated to 0.0) doesn't divide by
# zero and skip the comparison entirely

CANONICAL_DIMENSIONS = (
    "brightness", "warmth", "weight", "clarity", "density",
    "energy", "punch", "motion", "novelty",
)

# Minimum deltas considered significant (measurement noise guards).
EPSILON = {
    "band": 0.005,
    "dimension": 0.02,
    "lufs": 0.3,
    "centroid_ratio": 0.03,
    "width": 0.02,
    "correlation": 0.03,
    "timing_ms": 2.0,
    "swing": 2.0,
    "cv": 0.03,
}


@dataclass
class ClipFeatures:
    """Full feature report for one clip."""

    duration_s: float
    sample_rate: int
    channels: int
    snapshot: dict = field(default_factory=dict)
    extended: dict = field(default_factory=dict)
    dimensions: dict = field(default_factory=dict)


def _mono(audio: np.ndarray) -> np.ndarray:
    return audio.mean(axis=1) if audio.ndim == 2 else audio


def _db(x: float, floor: float = -120.0) -> float:
    return float(20.0 * math.log10(x)) if x > 10 ** (floor / 20.0) else floor


def _floor_lufs(value: float) -> float:
    if not np.isfinite(value) or value < LUFS_FLOOR:
        return LUFS_FLOOR
    return float(value)


# ── spectrum ─────────────────────────────────────────────────────────────


def _band_level_series(mono: np.ndarray, sr: int) -> tuple[dict, dict]:
    """Per-band, per-frame calibrated levels + spectral shape descriptors.

    Level calibration (Parseval): band mean-square =
    2·Σ|X|² / (n_fft · Σw²); level = sqrt(2·ms) so a full-scale sine
    reads ~1.0 in its band, independent of bin leakage.
    """
    import librosa

    n_fft = 8192 if sr > 48000 else 4096
    hop = n_fft // 4
    S = np.abs(librosa.stft(mono, n_fft=n_fft, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    w = np.hanning(n_fft)
    energy_norm = 2.0 / (n_fft * float((w ** 2).sum()))

    series: dict[str, np.ndarray] = {}
    for name, lo, hi in BANDS:
        mask = (freqs >= lo) & (freqs < min(hi, sr / 2))
        if not mask.any():
            series[name] = np.zeros(S.shape[1])
            continue
        band_ms = (S[mask] ** 2).sum(axis=0) * energy_norm
        series[name] = np.sqrt(2.0 * band_ms)

    power = S ** 2
    frame_power = power.sum(axis=0) + 1e-12
    centroid = float((freqs[:, None] * power).sum(axis=0).mean() / frame_power.mean())
    spread = float(
        np.sqrt(
            (((freqs[:, None] - centroid) ** 2) * power).sum(axis=0).mean()
            / frame_power.mean()
        )
    )
    cumulative = np.cumsum(power, axis=0)
    rolloff_idx = np.argmax(cumulative >= 0.85 * cumulative[-1], axis=0)
    rolloff = float(freqs[rolloff_idx].mean())
    mag_mean = S.mean(axis=1) + 1e-12
    flatness = float(np.exp(np.log(mag_mean).mean()) / mag_mean.mean())
    crest = float(mag_mean.max() / mag_mean.mean())

    shape = {
        "centroid": centroid,
        "spread": spread,
        "rolloff": rolloff,
        "flatness": flatness,
        "crest": crest,
    }
    return series, shape


# ── loudness ─────────────────────────────────────────────────────────────


def _loudness(audio: np.ndarray, sr: int) -> dict:
    from scipy.signal import resample_poly

    mono = _mono(audio)
    rms = float(np.sqrt((mono ** 2).mean()))

    # True peak is a per-channel quantity: panned or decorrelated content
    # (the normal case for a stereo master) averages away on a mono downmix,
    # systematically understating it (or reading silence on perfectly
    # anti-phase material). Oversample every channel independently and take
    # the max across channels, not the mono sum.
    channels = audio if audio.ndim == 2 else audio[:, None]
    oversampled = resample_poly(channels, 4, 1, axis=0)
    true_peak = float(np.abs(oversampled).max())

    # pyloudnorm's gating block is 400 ms; shorter input raises ValueError
    if len(mono) < int(0.5 * sr):
        return {
            "integrated_lufs": _floor_lufs(_db(rms)),
            "true_peak_dbtp": _db(true_peak),
            "loudness_range_lu": 0.0,
            "approximate": True,
        }

    import pyloudnorm as pyln

    meter = pyln.Meter(sr)
    integrated = _floor_lufs(float(meter.integrated_loudness(audio)))

    # short-term LUFS series (3s windows, 1s hop) for range estimation
    win, hop = 3 * sr, sr
    shorts = []
    if len(mono) >= win:
        for start in range(0, len(mono) - win + 1, hop):
            seg = audio[start:start + win]
            with np.errstate(all="ignore"):
                val = meter.integrated_loudness(seg)
            shorts.append(_floor_lufs(val))
    loudness_range = float(np.ptp(shorts)) if len(shorts) >= 2 else 0.0

    return {
        "integrated_lufs": integrated,
        "true_peak_dbtp": _db(true_peak),
        "loudness_range_lu": loudness_range,
        "approximate": False,
    }


# ── transients / groove ──────────────────────────────────────────────────


def _transients(mono22: np.ndarray) -> dict:
    import librosa

    # n_fft=1024 (~46 ms) keeps adjacent fast transients (32nds at 120 BPM =
    # 62.5 ms apart) out of each other's analysis windows; the default 2048
    # (~93 ms) smears them together and biases onset times by ~20 ms.
    env = librosa.onset.onset_strength(
        y=mono22, sr=RHYTHM_SR, hop_length=ONSET_HOP, n_fft=1024, n_mels=64
    )
    onsets = librosa.onset.onset_detect(
        onset_envelope=env, sr=RHYTHM_SR, hop_length=ONSET_HOP, units="frames"
    )
    onset_times = librosa.frames_to_time(onsets, sr=RHYTHM_SR, hop_length=ONSET_HOP)

    env_std = float(env.std()) + 1e-9
    attack_slopes = [
        (env[f] - env[f - 1]) / env_std for f in onsets if f >= 1
    ]
    duration = len(mono22) / RHYTHM_SR

    return {
        "onset_count": int(len(onsets)),
        "onset_rate_hz": float(len(onsets) / duration) if duration else 0.0,
        "onset_strength_mean": float(env.mean()),
        "attack_sharpness": float(np.mean(attack_slopes)) if attack_slopes else 0.0,
        "flux_std": float(env.std()),
        "flux_slope": _envelope_slope(env),
        "_onset_times": onset_times,  # consumed by _groove, stripped later
    }


def _envelope_slope(env: np.ndarray) -> float:
    """Linear trend of the flux envelope: >0 building, <0 falling."""
    if len(env) < 4:
        return 0.0
    x = np.linspace(-1.0, 1.0, len(env))
    denom = float((x ** 2).sum()) + 1e-12
    scale = float(env.mean()) + 1e-9
    return float((x * (env - env.mean())).sum() / denom / scale)


def _groove(onset_times: np.ndarray, bpm: Optional[float], mono22: np.ndarray) -> dict:
    import librosa

    estimated = False
    if bpm is None or bpm <= 0:
        tempo, _ = librosa.beat.beat_track(y=mono22, sr=RHYTHM_SR)
        bpm = float(np.atleast_1d(tempo)[0]) or 120.0
        estimated = True

    beat = 60.0 / bpm

    if len(onset_times) < 4:
        return {
            "bpm": bpm,
            "bpm_estimated": estimated,
            "onset_count": int(len(onset_times)),
            "grid_division": None,
            "microtiming_mad_ms": None,
            "swing_percent": None,
        }

    # Try several per-beat subdivisions; a fixed 16th grid aliases against
    # finer/triplet content. Prefer the coarsest division whose residual is
    # within tolerance of the best, so dense grids don't win by default.
    mads = {}
    for div in GRID_DIVISIONS:
        step = beat / div
        dev = onset_times - np.round(onset_times / step) * step
        mads[div] = float(np.median(np.abs(dev)) * 1000.0)
    best = min(mads.values())
    division = next(d for d in GRID_DIVISIONS if mads[d] <= best * 1.25 + 1.0)

    # swing: mean phase of onsets landing between beats (50 straight, ~67 triplet)
    phases = (onset_times % beat) / beat
    offbeats = phases[(phases > 0.3) & (phases < 0.85)]
    swing = float(offbeats.mean() * 100.0) if len(offbeats) >= 3 else None

    return {
        "bpm": bpm,
        "bpm_estimated": estimated,
        "onset_count": int(len(onset_times)),
        "grid_division": division,
        "microtiming_mad_ms": mads[division],
        "swing_percent": swing,
    }


# ── stereo / motion / polish ─────────────────────────────────────────────


def _stereo(audio: np.ndarray, sr: int) -> dict:
    if audio.ndim != 2 or audio.shape[1] < 2:
        return {"is_stereo": False, "correlation": 1.0, "side_mid_ratio": 0.0,
                "low_side_ratio": 0.0}

    left, right = audio[:, 0], audio[:, 1]
    mid, side = (left + right) / 2.0, (left - right) / 2.0
    mid_rms = float(np.sqrt((mid ** 2).mean())) + 1e-12
    side_rms = float(np.sqrt((side ** 2).mean()))

    denom = float(np.sqrt((left ** 2).mean() * (right ** 2).mean())) + 1e-12
    correlation = float((left * right).mean() / denom)

    # bass-mono check: side energy below 120 Hz relative to mid
    from scipy.signal import butter, sosfilt

    sos = butter(4, 120.0, btype="lowpass", fs=sr, output="sos")
    low_mid_rms = float(np.sqrt((sosfilt(sos, mid) ** 2).mean())) + 1e-12
    low_side_rms = float(np.sqrt((sosfilt(sos, side) ** 2).mean()))

    # The +1e-12 floor only guards 0/0 on digital silence; it does not keep
    # the ratio physical once mid nearly cancels (phase-invert / anti-phase
    # content), where mid_rms can collapse to ~1e-9..1e-12 while side_rms
    # stays normal. Saturate at a documented ceiling instead of letting the
    # ratio explode into the billions and dominate compare()'s ranking.
    return {
        "is_stereo": True,
        "correlation": correlation,
        "side_mid_ratio": min(side_rms / mid_rms, STEREO_RATIO_CEILING),
        "low_side_ratio": min(low_side_rms / low_mid_rms, STEREO_RATIO_CEILING),
    }


def _motion(band_series: dict, sr: int) -> dict:
    """Per-band short-time loudness movement (coefficient of variation)."""
    n_fft = 8192 if sr > 48000 else 4096
    hop = n_fft // 4
    frames_per_window = max(int(MOTION_WINDOW_S * sr / hop), 1)

    per_band_cv: dict[str, float] = {}
    for name, series in band_series.items():
        if float(series.mean()) < 1e-4:
            continue
        n_windows = len(series) // frames_per_window
        if n_windows < 3:
            continue
        windowed = series[: n_windows * frames_per_window].reshape(
            n_windows, frames_per_window
        ).mean(axis=1)
        mean = float(windowed.mean()) + 1e-12
        per_band_cv[name] = float(windowed.std() / mean)

    overall = float(np.mean(list(per_band_cv.values()))) if per_band_cv else 0.0
    return {"per_band_cv": per_band_cv, "overall_cv": overall}


def _polish(audio: np.ndarray, loudness: dict) -> dict:
    mono = _mono(audio)
    clipped_fraction = float((np.abs(audio) >= CLIP_THRESHOLD).mean())
    dc_offset = float(np.abs(mono.mean()))
    true_peak_margin_db = -loudness["true_peak_dbtp"]

    penalties = 0.0
    if clipped_fraction > 1e-5:
        penalties += min(clipped_fraction * 2000.0, 0.5)
    if dc_offset > 0.01:
        penalties += 0.2
    if true_peak_margin_db < 0.3:
        penalties += 0.2

    return {
        "clipped_fraction": clipped_fraction,
        "dc_offset": dc_offset,
        "true_peak_margin_db": true_peak_margin_db,
        "score": max(0.0, 1.0 - penalties),
    }


def _dimensions(snapshot: dict, extended: dict) -> dict:
    """Canonical dimensions via the real evaluation-stack extractor, plus
    extended dimensions under deliberately non-canonical names (so they
    can't be mistaken for GoalVector targets)."""

    def clamp(v: float) -> float:
        return max(0.0, min(1.0, v))

    dims = {}
    for dim in CANONICAL_DIMENSIONS:
        value = extract_dimension_value(snapshot, dim)
        if value is not None:
            dims[dim] = value

    dims["width"] = clamp(extended["stereo"]["side_mid_ratio"])
    dims["polish"] = extended["polish"]["score"]
    dims["motion_cv"] = clamp(extended["motion"]["overall_cv"])
    mad = extended["groove"].get("microtiming_mad_ms")
    if mad is not None:
        dims["groove_tightness"] = clamp(1.0 - mad / 30.0)
    return dims


# ── entry points ─────────────────────────────────────────────────────────


def extract_features(
    audio: np.ndarray,
    sr: int,
    bpm: Optional[float] = None,
) -> ClipFeatures:
    """Extract the full clip report from float32 samples (n,) or (n, ch)."""
    import librosa

    if not np.all(np.isfinite(audio)):
        raise ValueError(
            "Audio buffer contains non-finite samples (NaN/Inf) — likely a "
            "misbehaving plugin, a divide-by-zero in a synth, or an "
            "interrupted capture write. Re-capture and retry."
        )

    mono = _mono(audio)
    mono22 = librosa.resample(mono, orig_sr=sr, target_sr=RHYTHM_SR) \
        if sr != RHYTHM_SR else mono

    band_series, shape = _band_level_series(mono, sr)
    bands = {name: min(float(series.mean()), 1.0)
             for name, series in band_series.items()}
    loudness = _loudness(audio, sr)
    transients = _transients(mono22)
    onset_times = transients.pop("_onset_times")
    groove = _groove(onset_times, bpm, mono22)
    stereo = _stereo(audio, sr)
    motion = _motion(band_series, sr)
    polish = _polish(audio, loudness)

    rms = float(np.sqrt((mono ** 2).mean()))
    peak = float(np.abs(audio).max())

    # onset.strength must be 0..1 per the live m4l_bridge contract; raw
    # librosa onset_strength_mean is unbounded, squash it deterministically.
    onset_01 = transients["onset_strength_mean"] / (
        transients["onset_strength_mean"] + 2.0
    )

    quiet = loudness["integrated_lufs"] <= NOVELTY_LUFS_GATE
    novelty_01 = None
    if not quiet:
        novelty_01 = min(
            transients["flux_std"]
            / (transients["onset_strength_mean"] + 1e-9) / 3.0,
            1.0,
        )

    snapshot = {
        "spectrum": bands,
        "rms": rms,
        "peak": peak,
        "spectral_shape": shape,
        "onset": {"strength": onset_01},
        "loudness": {
            "integrated_lufs": loudness["integrated_lufs"],
            "true_peak_dbtp": loudness["true_peak_dbtp"],
        },
        "source": "listening_engine_offline",
    }
    if novelty_01 is not None:
        snapshot["novelty"] = {"score": novelty_01}

    extended = {
        "loudness": loudness,
        "transients": transients,
        "groove": groove,
        "stereo": stereo,
        "motion": motion,
        "polish": polish,
    }
    report = ClipFeatures(
        duration_s=len(mono) / sr,
        sample_rate=sr,
        channels=audio.shape[1] if audio.ndim == 2 else 1,
        snapshot=snapshot,
        extended=extended,
    )
    report.dimensions = _dimensions(snapshot, extended)
    return report


def _delta(after: Optional[float], before: Optional[float]) -> Optional[float]:
    if after is None or before is None:
        return None
    return after - before


def compare(before: ClipFeatures, after: ClipFeatures) -> dict:
    """Pure comparison of two clip reports."""
    changes: list[dict] = []

    def note(area: str, metric: str, b, a, eps: float, unit: str = "") -> None:
        d = _delta(a, b)
        if d is None or abs(d) < eps:
            return
        changes.append({
            "area": area,
            "metric": metric,
            "before": round(b, 4),
            "after": round(a, 4),
            "delta": round(d, 4),
            "unit": unit,
            "magnitude": abs(d) / eps,
        })

    bl, al = before.extended["loudness"], after.extended["loudness"]
    note("loudness", "integrated_lufs", bl["integrated_lufs"],
         al["integrated_lufs"], EPSILON["lufs"], "LUFS")
    note("loudness", "true_peak_dbtp", bl["true_peak_dbtp"],
         al["true_peak_dbtp"], EPSILON["lufs"], "dBTP")

    for band in before.snapshot["spectrum"]:
        note("spectrum", band, before.snapshot["spectrum"][band],
             after.snapshot["spectrum"][band], EPSILON["band"])

    bc = before.snapshot["spectral_shape"]["centroid"]
    ac = after.snapshot["spectral_shape"]["centroid"]
    # bc == 0 means 'before' was silence (centroid gated to 0.0 upstream) —
    # the relative-ratio test would divide by zero and silently skip a
    # silence -> bright transition no matter how loud 'after' is. Floor the
    # denominator instead of guarding on bc > 0.
    centroid_denom = bc if bc > 0 else CENTROID_FLOOR_HZ
    if abs(ac - bc) / centroid_denom >= EPSILON["centroid_ratio"]:
        changes.append({
            "area": "spectral_shape", "metric": "centroid",
            "before": round(bc, 1), "after": round(ac, 1),
            "delta": round(ac - bc, 1), "unit": "Hz",
            "magnitude": abs(ac - bc) / centroid_denom / EPSILON["centroid_ratio"],
        })

    bs, as_ = before.extended["stereo"], after.extended["stereo"]
    note("stereo", "side_mid_ratio", bs["side_mid_ratio"],
         as_["side_mid_ratio"], EPSILON["width"])
    note("stereo", "correlation", bs["correlation"],
         as_["correlation"], EPSILON["correlation"])
    note("stereo", "low_side_ratio", bs["low_side_ratio"],
         as_["low_side_ratio"], EPSILON["width"])

    bg, ag = before.extended["groove"], after.extended["groove"]
    note("groove", "microtiming_mad_ms", bg.get("microtiming_mad_ms"),
         ag.get("microtiming_mad_ms"), EPSILON["timing_ms"], "ms")
    note("groove", "swing_percent", bg.get("swing_percent"),
         ag.get("swing_percent"), EPSILON["swing"], "%")

    note("motion", "overall_cv", before.extended["motion"]["overall_cv"],
         after.extended["motion"]["overall_cv"], EPSILON["cv"])
    note("transients", "attack_sharpness",
         before.extended["transients"]["attack_sharpness"],
         after.extended["transients"]["attack_sharpness"], 0.1)
    note("transients", "onset_rate_hz",
         before.extended["transients"]["onset_rate_hz"],
         after.extended["transients"]["onset_rate_hz"], 0.2, "Hz")

    note("polish", "score", before.extended["polish"]["score"],
         after.extended["polish"]["score"], 0.05)

    changes.sort(key=lambda c: c["magnitude"], reverse=True)

    dimension_deltas = {}
    for dim in sorted(set(before.dimensions) | set(after.dimensions)):
        d = _delta(after.dimensions.get(dim), before.dimensions.get(dim))
        if d is not None and abs(d) >= EPSILON["dimension"]:
            dimension_deltas[dim] = {
                "before": round(before.dimensions[dim], 3),
                "after": round(after.dimensions[dim], 3),
                "delta": round(d, 3),
            }

    return {
        "dimension_deltas": dimension_deltas,
        "significant_changes": changes,
        "unchanged": not changes,
        "before_snapshot": before.snapshot,
        "after_snapshot": after.snapshot,
    }


def format_verdict(result: dict) -> str:
    """Human-readable summary of a compare() result."""
    lines = []
    if result["unchanged"]:
        return "No significant perceptual change detected."
    dims = result["dimension_deltas"]
    if dims:
        lines.append("Dimension deltas (evaluation-stack vocabulary):")
        for dim, d in sorted(dims.items(), key=lambda kv: -abs(kv[1]["delta"])):
            arrow = "+" if d["delta"] > 0 else "-"
            lines.append(f"  {arrow} {dim}: {d['before']:.3f} -> {d['after']:.3f}"
                         f" ({d['delta']:+.3f})")
    lines.append("Top feature changes:")
    for c in result["significant_changes"][:8]:
        lines.append(f"  {c['area']}/{c['metric']}: {c['before']} -> {c['after']}"
                     f" ({c['delta']:+g}{c['unit']})")
    return "\n".join(lines)
