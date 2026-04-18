"""FluCoMa-specific helpers (hints + pitch-name table).

Extracted from ``analyzer.py`` as part of BUG-C1. Purely about formatting
hints for the FluCoMa real-time streams — no Ableton or bridge access.
"""

from __future__ import annotations


PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _flucoma_hint(cache) -> str:
    """Return an error hint if no FluCoMa data has arrived on ``cache``.

    If ANY stream has data, FluCoMa is working and the specific stream just
    hasn't updated yet — return a 'play audio' hint. If NO streams have
    data, FluCoMa may not be installed — return an install hint.
    """
    for key in ("spectral_shape", "mel_bands", "chroma", "loudness"):
        if cache.get(key):
            return "play some audio"
    return "FluCoMa may not be installed. Install via: npx livepilot --setup-flucoma"
