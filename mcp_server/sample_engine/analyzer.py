"""SampleAnalyzer — filename parsing, material classification, mode recommendation.

Pure computation for the offline parts. Spectral analysis requires M4L bridge
and is handled in tools.py which calls these functions + bridge data.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from .models import SampleProfile


# ── Filename Metadata Parsing ───────────────────────────────────────

# Key patterns: C, Cm, C#, C#m, Cb, Cbm, Csharp, Csharpmin, etc.
_KEY_PATTERN = re.compile(
    r'\b([A-G])([b#]|sharp|flat)?(m|min|minor|maj|major)?\b',
    re.IGNORECASE,
)

# BPM patterns: 120bpm, 120_bpm, 120 BPM, or standalone 60-300 range
_BPM_PATTERN = re.compile(
    r'\b(\d{2,3})\s*(?:bpm)\b', re.IGNORECASE,
)
_BPM_STANDALONE = re.compile(
    r'(?:^|[_\-\s])(\d{2,3})(?:[_\-\s]|$)',
)

_KEY_NORMALIZE = {
    "sharp": "#", "flat": "b",
    "min": "m", "minor": "m", "maj": "", "major": "",
}


def parse_filename_metadata(filename: str) -> dict:
    """Extract key and BPM from a filename string.

    Returns dict with 'key' (str|None) and 'bpm' (float|None).
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    # Replace common separators with spaces for easier matching
    normalized = stem.replace("-", " ").replace("_", " ")

    key = _extract_key(normalized)
    bpm = _extract_bpm(normalized)

    return {"key": key, "bpm": bpm}


def _extract_key(text: str) -> Optional[str]:
    """Extract musical key from text."""
    matches = list(_KEY_PATTERN.finditer(text))
    for match in matches:
        root = match.group(1).upper()
        accidental = match.group(2) or ""
        quality = match.group(3) or ""

        # Normalize accidentals
        accidental = _KEY_NORMALIZE.get(accidental.lower(), accidental)
        quality = _KEY_NORMALIZE.get(quality.lower(), quality) if quality else ""

        # Avoid false positives: single letters that are common words
        full = root + accidental + quality
        if len(full) == 1 and root in ("A", "B", "C", "D", "E", "F", "G"):
            # Single letter — only accept if it looks like it's in a key context
            # Check surrounding chars
            start = match.start()
            end = match.end()
            before = text[start - 1] if start > 0 else " "
            after = text[end] if end < len(text) else " "
            if before.isalpha() or after.isalpha():
                continue  # Part of a word, not a key
        return full
    return None


def _extract_bpm(text: str) -> Optional[float]:
    """Extract BPM from text."""
    # Try explicit bpm markers first
    match = _BPM_PATTERN.search(text)
    if match:
        bpm = float(match.group(1))
        if 40 <= bpm <= 300:
            return bpm

    # Try standalone numbers in valid range
    for match in _BPM_STANDALONE.finditer(text):
        bpm = float(match.group(1))
        if 60 <= bpm <= 250:
            return bpm
    return None


# ── Material Classification ─────────────────────────────────────────

_MATERIAL_KEYWORDS: dict[str, list[str]] = {
    "vocal": ["vocal", "vox", "voice", "singer", "acapella", "spoken"],
    "drum_loop": ["drum", "beat", "break", "breakbeat", "loop", "groove",
                  "hihat", "hat", "ride", "cymbal", "perc", "percussion",
                  "shaker", "tamb", "conga", "bongo", "top"],
    "one_shot": ["kick", "snare", "clap", "snap", "tom", "rim", "hit",
                 "oneshot", "one shot", "stab", "shot", "impact"],
    "instrument_loop": ["guitar", "piano", "keys", "bass", "synth",
                        "strings", "brass", "horn", "organ", "riff",
                        "chord", "arp", "pluck"],
    "texture": ["ambient", "pad", "drone", "atmosphere", "noise",
                "texture", "wash", "evolving", "soundscape"],
    "foley": ["foley", "field", "recording", "room", "nature",
              "water", "metal", "wood", "glass", "paper"],
    "fx": ["fx", "effect", "riser", "sweep", "whoosh", "boom",
           "transition", "downlifter", "uplifter"],
}


def classify_material_from_name(name: str) -> str:
    """Classify sample material type from filename/name keywords."""
    lower = name.lower().replace("-", " ").replace("_", " ")

    # Score each type by keyword matches
    scores: dict[str, int] = {}
    for material_type, keywords in _MATERIAL_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[material_type] = score

    if not scores:
        return "unknown"

    return max(scores, key=scores.get)


# ── Simpler Mode Recommendation ────────────────────────────────────


def suggest_simpler_mode(profile: SampleProfile) -> str:
    """Recommend Simpler playback mode based on material analysis.

    Returns: "classic", "one_shot", or "slice"
    """
    if profile.duration_seconds < 0.5 or profile.material_type == "one_shot":
        return "classic"
    if profile.material_type == "fx":
        return "classic"
    if profile.material_type in ("texture", "foley"):
        return "classic"
    if profile.material_type in ("drum_loop", "instrument_loop",
                                  "vocal", "full_mix"):
        return "slice"
    # Unknown material with decent length — slice is more useful
    if profile.duration_seconds > 2.0:
        return "slice"
    return "classic"


def suggest_slice_method(profile: SampleProfile) -> str:
    """Recommend slice-by method for Simpler's Slice mode."""
    if profile.material_type == "drum_loop":
        return "transient"
    if profile.material_type == "instrument_loop":
        return "beat"
    if profile.material_type == "vocal":
        return "region"
    if profile.material_type == "full_mix":
        return "beat"
    return "transient"


def suggest_warp_mode(profile: SampleProfile) -> str:
    """Recommend Ableton warp mode for the sample material."""
    mode_map = {
        "drum_loop": "beats",
        "one_shot": "complex",
        "instrument_loop": "complex_pro",
        "vocal": "complex_pro",
        "texture": "texture",
        "foley": "texture",
        "fx": "complex",
        "full_mix": "complex_pro",
    }
    return mode_map.get(profile.material_type, "complex")


def build_profile_from_filename(
    file_path: str,
    source: str = "filesystem",
    duration_seconds: float = 0.0,
) -> SampleProfile:
    """Build a SampleProfile from filename metadata + offline spectral
    analysis (BUG-B49 fix).

    Filename still supplies key / bpm / material-type hints when
    present, but we now ALSO open the audio file via soundfile and
    compute:
        - duration_seconds (exact)
        - frequency_center / frequency_spread (FFT-based centroid)
        - brightness (high-band energy ratio)
        - transient_density (RMS-gradient peak count)
        - has_clear_downbeat (peak-interval consistency)
    These used to be zeros regardless of file contents — downstream
    critics had no real data.

    If soundfile isn't available or the file can't be decoded, we
    gracefully fall back to the filename-only path (legacy behavior).
    """
    name = os.path.splitext(os.path.basename(file_path))[0]
    metadata = parse_filename_metadata(file_path)
    material = classify_material_from_name(name)

    # Offline spectral analysis — best-effort, never raises.
    spectral = _analyze_audio_file(file_path)

    profile = SampleProfile(
        source=source,
        file_path=file_path,
        name=name,
        key=metadata.get("key"),
        key_confidence=0.5 if metadata.get("key") else 0.0,
        bpm=metadata.get("bpm"),
        bpm_confidence=0.5 if metadata.get("bpm") else 0.0,
        material_type=material,
        material_confidence=0.4,  # filename-only is low confidence
        duration_seconds=(
            spectral.get("duration_seconds") or duration_seconds
        ),
        frequency_center=spectral.get("frequency_center", 0.0),
        frequency_spread=spectral.get("frequency_spread", 0.0),
        brightness=spectral.get("brightness", 0.0),
        transient_density=spectral.get("transient_density", 0.0),
        has_clear_downbeat=spectral.get("has_clear_downbeat", False),
    )

    profile.suggested_mode = suggest_simpler_mode(profile)
    profile.suggested_slice_by = suggest_slice_method(profile)
    profile.suggested_warp_mode = suggest_warp_mode(profile)

    return profile


def _analyze_audio_file(file_path: str) -> dict:
    """Read an audio file and compute lightweight spectral/temporal
    features via numpy. Returns {} if the file can't be decoded.

    Uses soundfile (already a dependency) + numpy FFT — no librosa
    required. Falls back cleanly so file-not-found / unsupported
    format doesn't break the analyzer.
    """
    try:
        import soundfile as sf
        import numpy as np
    except ImportError:
        return {}

    if not file_path or not os.path.exists(file_path):
        return {}

    try:
        data, samplerate = sf.read(file_path, dtype="float32")
    except Exception:
        return {}

    # Downmix to mono
    if data.ndim > 1:
        data = data.mean(axis=1)
    if data.size == 0 or samplerate <= 0:
        return {}

    duration = float(data.size) / float(samplerate)

    # Spectral centroid via magnitude-weighted frequency average.
    # Use a Welch-style average over ~50ms windows to stabilize.
    win_len = max(1024, int(samplerate * 0.05))
    hop = win_len // 2
    centroids: list[float] = []
    spreads: list[float] = []
    frames = range(0, max(len(data) - win_len, 1), hop)
    for start in frames:
        frame = data[start:start + win_len]
        if len(frame) < 32:
            continue
        # Hann-window + FFT
        mags = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
        total = mags.sum()
        if total <= 0:
            continue
        freqs = np.linspace(0, samplerate / 2, len(mags))
        c = float((mags * freqs).sum() / total)
        centroids.append(c)
        # Spectral spread = sqrt(sum(mags * (freqs - c)**2) / total)
        s = float(np.sqrt(((mags * (freqs - c) ** 2).sum()) / total))
        spreads.append(s)

    if not centroids:
        return {"duration_seconds": duration}

    frequency_center = float(np.mean(centroids))
    frequency_spread = float(np.mean(spreads))
    # Brightness: fraction of energy above 4kHz
    # Use a single FFT on the whole signal for this (cheap)
    full_mags = np.abs(np.fft.rfft(data * np.hanning(len(data))))
    full_freqs = np.linspace(0, samplerate / 2, len(full_mags))
    total_energy = full_mags.sum() or 1.0
    high_energy = full_mags[full_freqs >= 4000].sum()
    brightness = float(high_energy / total_energy)

    # Transient density: peak count in rectified-RMS gradient
    # Coarse envelope over ~20ms windows
    env_win = max(256, int(samplerate * 0.02))
    envelope = np.array([
        float(np.sqrt(np.mean(data[i:i + env_win] ** 2)))
        for i in range(0, len(data), env_win)
    ])
    if envelope.size > 1:
        diffs = np.diff(envelope)
        # Count upward transitions above a dynamic threshold
        thresh = max(envelope.std() * 1.5, 1e-4)
        peaks = int(np.sum(diffs > thresh))
        transient_density = float(peaks / max(duration, 0.001))
    else:
        transient_density = 0.0

    # Clear downbeat: peaks evenly spaced
    has_clear_downbeat = False
    if envelope.size > 4:
        # Find top-N peaks and check interval stddev
        peak_positions = np.argsort(envelope)[-8:]
        peak_positions.sort()
        if len(peak_positions) >= 3:
            intervals = np.diff(peak_positions)
            if intervals.size > 0 and float(np.mean(intervals)) > 0:
                cv = float(np.std(intervals)) / float(np.mean(intervals))
                has_clear_downbeat = cv < 0.5  # low variation → steady

    return {
        "duration_seconds": duration,
        "frequency_center": frequency_center,
        "frequency_spread": frequency_spread,
        "brightness": brightness,
        "transient_density": transient_density,
        "has_clear_downbeat": has_clear_downbeat,
    }
