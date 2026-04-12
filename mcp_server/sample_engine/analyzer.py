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
    """Build a SampleProfile from filename metadata only (no spectral analysis).

    This is the fallback when M4L bridge is unavailable.
    """
    name = os.path.splitext(os.path.basename(file_path))[0]
    metadata = parse_filename_metadata(file_path)
    material = classify_material_from_name(name)

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
        duration_seconds=duration_seconds,
    )

    profile.suggested_mode = suggest_simpler_mode(profile)
    profile.suggested_slice_by = suggest_slice_method(profile)
    profile.suggested_warp_mode = suggest_warp_mode(profile)

    return profile
