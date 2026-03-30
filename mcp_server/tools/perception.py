"""Offline audio perception tools for LivePilot v1.8.

4 MCP tools wrapping the pure-function engine in _perception_engine.py.
These tools do NOT require an Ableton connection — they work on any local
audio file.

Tools:
  analyze_loudness         — integrated LUFS, true peak, LRA, streaming compliance
  analyze_spectrum_offline — spectral centroid, rolloff, flatness, 5-band balance
  compare_to_reference     — loudness + spectral delta between mix and reference
  read_audio_metadata      — format, sample rate, tags, artwork flag
"""

from __future__ import annotations

import os
from typing import Any, Optional

from ..server import mcp
from ._perception_engine import (
    compute_loudness,
    compute_spectral,
    compare_to_reference as _compare,
    read_audio_metadata as _read_metadata,
)


# ---------------------------------------------------------------------------
# Supported formats
# ---------------------------------------------------------------------------

_LOSSLESS_EXTS = {".wav", ".flac", ".ogg", ".aiff", ".aif"}
_LOSSY_EXTS = {".mp3", ".m4a"}
_MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB


def _validate_audio(file_path: str, allow_mp3: bool = False) -> Optional[dict]:
    """Validate that a file exists, has a supported extension, and is < 500 MB.

    Returns None if valid, or an error dict if invalid.
    """
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}", "code": "INVALID_PARAM"}

    ext = os.path.splitext(file_path)[1].lower()
    allowed = _LOSSLESS_EXTS | (_LOSSY_EXTS if allow_mp3 else set())
    if ext not in allowed:
        return {
            "error": (
                f"Unsupported format '{ext}'. "
                f"Supported: {sorted(allowed)}"
            ),
            "code": "INVALID_PARAM",
        }

    size = os.path.getsize(file_path)
    if size > _MAX_FILE_SIZE:
        mb = size / (1024 * 1024)
        return {
            "error": f"File too large ({mb:.1f} MB). Maximum is 500 MB.",
            "code": "INVALID_PARAM",
        }

    return None  # valid


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def analyze_loudness(
    file_path: str,
    detail: str = "summary",
) -> dict[str, Any]:
    """Analyze the integrated loudness of an audio file (offline — no Ableton needed).

    Computes integrated LUFS (EBU R128), true peak, RMS, crest factor,
    loudness range (LRA), and streaming platform compliance.

    Args:
        file_path: Absolute path to the audio file (.wav, .flac, .ogg, .aiff).
        detail: "summary" (default) or "full" — "full" includes the short_term_lufs
                array (up to 100 points, mean-pooled).

    Returns:
        On success: dict with integrated_lufs, true_peak_dbtp (4x oversampled),
        sample_peak_dbfs (raw sample peak, kept for backward compat), rms_dbfs,
        crest_factor_db, lra_lu, meets_streaming {spotify, apple, youtube, tidal},
        and optionally short_term_lufs.
        On error: {"error": ..., "code": ...}
    """
    err = _validate_audio(file_path, allow_mp3=False)
    if err:
        return err

    if detail not in ("summary", "full"):
        return {"error": "detail must be 'summary' or 'full'", "code": "INVALID_PARAM"}

    try:
        return compute_loudness(file_path, detail=detail)
    except FileNotFoundError as exc:
        return {"error": str(exc), "code": "INVALID_PARAM"}
    except Exception as exc:
        return {"error": f"Loudness analysis failed: {exc}", "code": "INTERNAL"}


@mcp.tool()
def analyze_spectrum_offline(
    file_path: str,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> dict[str, Any]:
    """Analyze the frequency spectrum of an audio file (offline — no Ableton needed).

    Uses scipy STFT to compute spectral centroid, rolloff, flatness, bandwidth,
    and 5-band energy balance (sub_60hz, low_250hz, mid_2khz, high_8khz, air_16khz).

    Args:
        file_path: Absolute path to the audio file (.wav, .flac, .ogg, .aiff).
        n_fft: FFT window size (default 2048).
        hop_length: Hop size in samples (default 512).

    Returns:
        On success: dict with centroid_hz, rolloff_hz, spectral_flatness,
        bandwidth_hz, band_balance.
        On error: {"error": ..., "code": ...}
    """
    err = _validate_audio(file_path, allow_mp3=False)
    if err:
        return err

    if n_fft < 64 or n_fft > 65536:
        return {"error": "n_fft must be between 64 and 65536", "code": "INVALID_PARAM"}
    if hop_length < 1 or hop_length > n_fft:
        return {"error": "hop_length must be between 1 and n_fft", "code": "INVALID_PARAM"}

    try:
        return compute_spectral(file_path, n_fft=n_fft, hop_length=hop_length)
    except FileNotFoundError as exc:
        return {"error": str(exc), "code": "INVALID_PARAM"}
    except Exception as exc:
        return {"error": f"Spectral analysis failed: {exc}", "code": "INTERNAL"}


@mcp.tool()
def compare_to_reference(
    mix_path: str,
    reference_path: str,
    normalize: bool = True,
) -> dict[str, Any]:
    """Compare a mix to a reference track (offline — no Ableton needed).

    Computes loudness delta (LUFS), spectral centroid delta, stereo width
    comparison, per-band energy deltas, and actionable mixing suggestions.

    When normalize=True (default), both files are LUFS-normalized to -14 LUFS
    before spectral comparison so frequency differences aren't skewed by volume.

    Args:
        mix_path: Absolute path to the mix file (.wav, .flac, .ogg, .aiff).
        reference_path: Absolute path to the reference file.
        normalize: LUFS-normalize before spectral comparison (default True).

    Returns:
        On success: dict with loudness_delta_lufs, mix_lufs, reference_lufs,
        centroid_delta_hz, stereo_width_mix, stereo_width_ref, band_deltas,
        suggestions.
        On error: {"error": ..., "code": ...}
    """
    err = _validate_audio(mix_path, allow_mp3=False)
    if err:
        return {"error": f"mix_path: {err['error']}", "code": err["code"]}

    err = _validate_audio(reference_path, allow_mp3=False)
    if err:
        return {"error": f"reference_path: {err['error']}", "code": err["code"]}

    try:
        return _compare(mix_path, reference_path, normalize=normalize)
    except FileNotFoundError as exc:
        return {"error": str(exc), "code": "INVALID_PARAM"}
    except Exception as exc:
        return {"error": f"Reference comparison failed: {exc}", "code": "INTERNAL"}


@mcp.tool()
def read_audio_metadata(
    file_path: str,
) -> dict[str, Any]:
    """Read metadata from an audio file (offline — no Ableton needed).

    Uses mutagen for tag reading (title, artist, album, BPM, etc.) and
    soundfile for format information. Falls back gracefully if mutagen
    cannot parse the file.

    Args:
        file_path: Absolute path to the audio file (.wav, .flac, .ogg, .aiff,
                   .mp3, .m4a).

    Returns:
        On success: dict with format, duration, sample_rate, channels,
        bitrate, tags, has_artwork, file_size.
        On error: {"error": ..., "code": ...}
    """
    err = _validate_audio(file_path, allow_mp3=True)
    if err:
        return err

    try:
        return _read_metadata(file_path)
    except FileNotFoundError as exc:
        return {"error": str(exc), "code": "INVALID_PARAM"}
    except Exception as exc:
        return {"error": f"Metadata read failed: {exc}", "code": "INTERNAL"}
