"""Offline audio perception engine for LivePilot v1.8.

Pure functions for loudness, spectral, comparison, and metadata analysis.
All heavy imports are lazy (inside functions) except numpy and os.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STREAMING_TARGETS: dict[str, float] = {
    "spotify": -14.0,
    "apple": -16.0,
    "youtube": -14.0,
    "tidal": -14.0,
}

SILENCE_FLOOR = -70.0

BAND_EDGES: dict[str, tuple[float, float]] = {
    "sub_60hz":   (20.0,   60.0),
    "low_250hz":  (60.0,  250.0),
    "mid_2khz":  (250.0, 2000.0),
    "high_8khz": (2000.0, 8000.0),
    "air_16khz": (8000.0, 20000.0),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_audio(file_path: str) -> tuple[np.ndarray, int]:
    """Load an audio file as (ndarray, sample_rate). Ensures stereo output."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")
    import soundfile as sf
    data, sr = sf.read(file_path, dtype="float32", always_2d=True)
    # Ensure stereo: if mono, duplicate channel
    if data.shape[1] == 1:
        data = np.column_stack([data, data])
    return data, sr


def _normalize_to_lufs(
    file_path: str, current_lufs: float, target_lufs: float = -14.0
) -> str:
    """LUFS-normalize audio to target, write to temp file, return path."""
    import soundfile as sf

    if current_lufs <= SILENCE_FLOOR:
        return file_path
    gain_db = target_lufs - current_lufs
    gain_linear = 10 ** (gain_db / 20.0)
    data, sr = _load_audio(file_path)
    normalized = np.clip(data * gain_linear, -1.0, 1.0)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(tmp_fd)
    try:
        sf.write(tmp_path, normalized, sr)
    except Exception:
        # Clean up on failure to avoid orphan files
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return tmp_path


# ---------------------------------------------------------------------------
# compute_loudness
# ---------------------------------------------------------------------------

def compute_loudness(file_path: str, detail: str = "summary") -> dict[str, Any]:
    """Analyze integrated loudness (LUFS), true peak, RMS, LRA, and streaming compliance.

    Args:
        file_path: Absolute path to audio file (.wav, .flac, .ogg, .aiff).
        detail: "summary" (default) or "full" (includes short_term_lufs array).

    Returns:
        dict with integrated_lufs, sample_peak_dbfs, rms_dbfs, crest_factor_db,
        lra_lu, meets_streaming, and optionally short_term_lufs.
    """
    import pyloudnorm as pyln

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    data, sr = _load_audio(file_path)

    meter = pyln.Meter(sr)

    # Integrated LUFS
    # pyloudnorm expects (samples, channels)
    raw_lufs = meter.integrated_loudness(data)
    integrated_lufs = max(float(raw_lufs), SILENCE_FLOOR) if np.isfinite(raw_lufs) else SILENCE_FLOOR

    # Sample peak (max absolute value, no oversampling — not EBU R128 true peak)
    peak_linear = float(np.max(np.abs(data)))
    sample_peak_dbfs = float(20.0 * np.log10(max(peak_linear, 1e-10)))

    # RMS dBFS
    rms_linear = float(np.sqrt(np.mean(data ** 2)))
    rms_dbfs = float(20.0 * np.log10(max(rms_linear, 1e-10)))

    # Crest factor
    crest_factor_db = sample_peak_dbfs - rms_dbfs

    # Short-term LUFS (3s window, 1s hop) — also used for LRA
    window_samples = int(sr * 3.0)
    hop_samples = int(sr * 1.0)
    n_samples = data.shape[0]
    short_term_raw: list[float] = []

    pos = 0
    while pos + window_samples <= n_samples:
        window = data[pos : pos + window_samples]
        try:
            st = meter.integrated_loudness(window)
            short_term_raw.append(float(st) if np.isfinite(st) else SILENCE_FLOOR)
        except Exception:
            short_term_raw.append(SILENCE_FLOOR)
        pos += hop_samples

    # Guard: if no windows, fall back to integrated value
    if not short_term_raw:
        short_term_raw = [integrated_lufs]

    # Replace -inf values with floor
    short_term_clean = [max(v, SILENCE_FLOOR) for v in short_term_raw]

    # LRA: 95th - 10th percentile of short-term values
    st_array = np.array(short_term_clean)
    lra_lu = float(np.percentile(st_array, 95) - np.percentile(st_array, 10))

    # Cap short-term to 100 points via mean-pooling
    if len(short_term_clean) > 100:
        arr = np.array(short_term_clean, dtype=float)
        chunk_size = len(arr) / 100.0
        pooled = [
            float(np.mean(arr[int(i * chunk_size): int((i + 1) * chunk_size)]))
            for i in range(100)
        ]
        short_term_clean = pooled

    # Streaming compliance
    meets_streaming = {
        name: abs(integrated_lufs - target) <= 1.0  # ±1 LU tolerance
        for name, target in STREAMING_TARGETS.items()
    }

    result: dict[str, Any] = {
        "integrated_lufs": round(integrated_lufs, 2),
        "sample_peak_dbfs": round(sample_peak_dbfs, 2),
        "rms_dbfs": round(rms_dbfs, 2),
        "crest_factor_db": round(crest_factor_db, 2),
        "lra_lu": round(lra_lu, 2),
        "meets_streaming": meets_streaming,
    }

    if detail == "full":
        result["short_term_lufs"] = [round(v, 2) for v in short_term_clean]

    return result


# ---------------------------------------------------------------------------
# compute_spectral
# ---------------------------------------------------------------------------

def compute_spectral(
    file_path: str,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> dict[str, Any]:
    """Compute spectral features using scipy.signal.stft.

    Args:
        file_path: Absolute path to audio file.
        n_fft: FFT size.
        hop_length: Hop size in samples.

    Returns:
        dict with centroid_hz, rolloff_hz, spectral_flatness, bandwidth_hz,
        band_balance.
    """
    from scipy.signal import stft as scipy_stft

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    data, sr = _load_audio(file_path)

    # Mix to mono for spectral analysis
    mono = data.mean(axis=1).astype(np.float64)

    # STFT
    freqs, _times, Zxx = scipy_stft(
        mono,
        fs=sr,
        nperseg=n_fft,
        noverlap=n_fft - hop_length,
        window="hann",
    )

    # Power spectrum (mean over time)
    power = np.mean(np.abs(Zxx) ** 2, axis=1)  # shape: (n_fft//2+1,)

    # Guard against all-zero power
    total_power = float(np.sum(power))
    if total_power < 1e-30:
        # Return zeroed-out result for silence
        band_balance = {k: 0.0 for k in BAND_EDGES}
        return {
            "centroid_hz": 0.0,
            "rolloff_hz": 0.0,
            "spectral_flatness": 0.0,
            "bandwidth_hz": 0.0,
            "band_balance": band_balance,
        }

    # Spectral centroid (weighted mean frequency)
    centroid_hz = float(np.sum(freqs * power) / total_power)

    # Spectral rolloff (95% energy threshold)
    cumulative = np.cumsum(power)
    threshold = 0.95 * cumulative[-1]
    rolloff_idx = int(np.searchsorted(cumulative, threshold))
    rolloff_hz = float(freqs[min(rolloff_idx, len(freqs) - 1)])

    # Spectral flatness (geometric mean / arithmetic mean)
    eps = 1e-10
    log_mean = float(np.mean(np.log(power + eps)))
    arith_mean = float(np.mean(power))
    geo_mean = np.exp(log_mean)
    spectral_flatness = float(geo_mean / (arith_mean + eps))

    # Spectral bandwidth (weighted std around centroid)
    bandwidth_hz = float(
        np.sqrt(np.sum(power * (freqs - centroid_hz) ** 2) / (total_power + eps))
    )

    # 5-band energy balance
    band_balance: dict[str, float] = {}
    for band_name, (f_low, f_high) in BAND_EDGES.items():
        mask = (freqs >= f_low) & (freqs < f_high)
        band_power = float(np.sum(power[mask]))
        band_balance[band_name] = round(band_power / (total_power + eps), 6)

    return {
        "centroid_hz": round(centroid_hz, 2),
        "rolloff_hz": round(rolloff_hz, 2),
        "spectral_flatness": round(spectral_flatness, 6),
        "bandwidth_hz": round(bandwidth_hz, 2),
        "band_balance": band_balance,
    }


# ---------------------------------------------------------------------------
# compare_to_reference
# ---------------------------------------------------------------------------

def compare_to_reference(
    mix_path: str,
    reference_path: str,
    normalize: bool = True,
) -> dict[str, Any]:
    """Compare a mix to a reference track.

    Computes loudness delta, spectral centroid delta, stereo width delta,
    per-band energy deltas, and actionable suggestions.

    Args:
        mix_path: Path to the mix file.
        reference_path: Path to the reference file.
        normalize: If True, LUFS-normalize both to -14 before spectral comparison.

    Returns:
        dict with loudness_delta_lufs, centroid_delta_hz, stereo_width_mix,
        stereo_width_ref, band_deltas, suggestions.
    """
    if not os.path.exists(mix_path):
        raise FileNotFoundError(f"Mix file not found: {mix_path}")
    if not os.path.exists(reference_path):
        raise FileNotFoundError(f"Reference file not found: {reference_path}")

    mix_loudness = compute_loudness(mix_path)
    ref_loudness = compute_loudness(reference_path)

    mix_lufs = mix_loudness["integrated_lufs"]
    ref_lufs = ref_loudness["integrated_lufs"]
    loudness_delta = round(mix_lufs - ref_lufs, 2)

    # Optionally LUFS-normalize before spectral comparison
    mix_for_spectral = mix_path
    ref_for_spectral = reference_path
    tmp_files: list[str] = []

    if normalize:
        mix_for_spectral = _normalize_to_lufs(mix_path, mix_lufs, -14.0)
        ref_for_spectral = _normalize_to_lufs(reference_path, ref_lufs, -14.0)
        if mix_for_spectral != mix_path:
            tmp_files.append(mix_for_spectral)
        if ref_for_spectral != reference_path:
            tmp_files.append(ref_for_spectral)

    try:
        mix_spectral = compute_spectral(mix_for_spectral)
        ref_spectral = compute_spectral(ref_for_spectral)
    finally:
        for f in tmp_files:
            try:
                os.unlink(f)
            except OSError:
                pass

    centroid_delta = round(mix_spectral["centroid_hz"] - ref_spectral["centroid_hz"], 2)

    # Stereo width: side_energy / (mid_energy + side_energy)
    def _stereo_width(file_path: str) -> float:
        data, _sr = _load_audio(file_path)
        mid = (data[:, 0] + data[:, 1]) / 2.0
        side = (data[:, 0] - data[:, 1]) / 2.0
        mid_energy = float(np.mean(mid ** 2))
        side_energy = float(np.mean(side ** 2))
        total = mid_energy + side_energy
        if total < 1e-30:
            return 0.0
        return round(side_energy / total, 4)

    stereo_width_mix = _stereo_width(mix_path)
    stereo_width_ref = _stereo_width(reference_path)

    # Band deltas
    mix_bands = mix_spectral["band_balance"]
    ref_bands = ref_spectral["band_balance"]
    band_deltas = {
        band: round(mix_bands.get(band, 0.0) - ref_bands.get(band, 0.0), 6)
        for band in BAND_EDGES
    }

    # Build suggestions
    suggestions: list[str] = []
    if loudness_delta < -3:
        suggestions.append(
            f"Mix is {abs(loudness_delta):.1f} LUFS quieter than reference — consider raising gain."
        )
    elif loudness_delta > 3:
        suggestions.append(
            f"Mix is {loudness_delta:.1f} LUFS louder than reference — consider reducing gain."
        )

    if abs(centroid_delta) > 200:
        direction = "brighter" if centroid_delta > 0 else "darker"
        suggestions.append(
            f"Mix spectral centroid is {abs(centroid_delta):.0f} Hz {direction} than reference."
        )

    width_delta = stereo_width_mix - stereo_width_ref
    if width_delta < -0.1:
        suggestions.append("Mix is narrower than reference — consider widening the stereo image.")
    elif width_delta > 0.1:
        suggestions.append("Mix is wider than reference — check for phase issues.")

    for band, delta in band_deltas.items():
        if abs(delta) > 0.05:
            direction = "more" if delta > 0 else "less"
            suggestions.append(f"{band}: mix has {direction} energy than reference ({delta:+.3f}).")

    return {
        "loudness_delta_lufs": loudness_delta,
        "mix_lufs": mix_lufs,
        "reference_lufs": ref_lufs,
        "centroid_delta_hz": centroid_delta,
        "stereo_width_mix": stereo_width_mix,
        "stereo_width_ref": stereo_width_ref,
        "band_deltas": band_deltas,
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------------
# read_audio_metadata
# ---------------------------------------------------------------------------

def read_audio_metadata(file_path: str) -> dict[str, Any]:
    """Read audio file metadata using mutagen (tags) and soundfile (format info).

    Args:
        file_path: Absolute path to audio file.

    Returns:
        dict with format, duration, sample_rate, channels, bitrate, tags,
        has_artwork, file_size.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    import soundfile as sf

    file_size = os.path.getsize(file_path)

    # soundfile for basic info
    sf_info = sf.info(file_path)
    duration = float(sf_info.duration)
    sample_rate = int(sf_info.samplerate)
    channels = int(sf_info.channels)
    fmt = str(sf_info.subtype) if sf_info.subtype else str(sf_info.format)

    # bitrate estimate (bits/s)
    bitrate: int | None = None
    if duration > 0:
        bitrate = int((file_size * 8) / duration)

    # mutagen for tags
    tags: dict[str, Any] = {}
    has_artwork = False
    try:
        import mutagen
        audio = mutagen.File(file_path)
        if audio is not None:
            for key, value in audio.tags.items() if audio.tags else []:
                try:
                    # Skip binary/artwork tags
                    str_val = str(value)
                    if len(str_val) < 2048:
                        tags[str(key)] = str_val
                except Exception:
                    pass
            # Detect artwork (common tag names)
            artwork_keys = {"APIC", "covr", "METADATA_BLOCK_PICTURE", "artwork"}
            if audio.tags:
                for key in audio.tags.keys():
                    if any(k in str(key) for k in artwork_keys):
                        has_artwork = True
                        break
    except Exception:
        pass  # mutagen can't parse — use soundfile info only

    return {
        "format": fmt,
        "duration": round(duration, 4),
        "sample_rate": sample_rate,
        "channels": channels,
        "bitrate": bitrate,
        "tags": tags,
        "has_artwork": has_artwork,
        "file_size": file_size,
    }
