"""Pure-Python helpers for scale handling — importable outside Ableton.

These helpers are extracted so tests can import them without pulling in
Live's `_Framework` package (which only exists inside the Ableton
runtime). The main scales.py module re-imports them.

Nothing here talks to Live's LOM. The `_resolve_scale_names` helper
takes a `song` argument but only calls `getattr` on it, so duck-typing
is enough — tests pass a plain object with the right attrs.
"""

from __future__ import annotations


# Live's built-in scale names — stable since 12.0. Used as a final fallback
# when both `Song.scale_names` and the alternative attribute names are absent
# (e.g. Live 12.4.0 where `scale_names` attribute was dropped from Python LOM).
# Source: Live 12 Manual — "Scale Mode" chapter; order matches Live's picker.
_BUILTIN_SCALES_FALLBACK = [
    "Major", "Minor", "Dorian", "Mixolydian", "Lydian", "Phrygian",
    "Locrian", "Whole Tone", "Half-whole Dim.", "Whole-half Dim.",
    "Minor Blues", "Minor Pentatonic", "Major Pentatonic",
    "Harmonic Minor", "Harmonic Major", "Dorian #4", "Phrygian Dominant",
    "Melodic Minor", "Lydian Augmented", "Lydian Dominant",
    "Super Locrian", "8-Tone Spanish",
]


def _resolve_scale_names(song):
    """Get Live's available scale names, resilient to 12.4 API changes.

    Probes: song.scale_names, song.available_scale_names, song.get_scale_names()
    in that order. Falls back to _BUILTIN_SCALES_FALLBACK so callers always
    get a usable list rather than an AttributeError.
    """
    for attr in ("scale_names", "available_scale_names"):
        try:
            value = getattr(song, attr, None)
            if value is not None:
                return list(value)
        except Exception:
            continue
    for attr in ("get_scale_names", "get_available_scale_names"):
        try:
            fn = getattr(song, attr, None)
            if callable(fn):
                value = fn()
                if value is not None:
                    return list(value)
        except Exception:
            continue
    return list(_BUILTIN_SCALES_FALLBACK)


def _coerce_root_note(value):
    """Accept int 0-11 OR note-name string ('C', 'C#', 'Db', 'F#', etc.)."""
    if isinstance(value, bool):
        # bool is a subclass of int in Python — reject explicitly.
        raise ValueError("root_note cannot be a boolean")
    if isinstance(value, int):
        root = value
    elif isinstance(value, str):
        s = value.strip()
        try:
            root = int(s)
        except ValueError:
            name_map = {
                "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
                "E": 4, "Fb": 4, "E#": 5, "F": 5, "F#": 6, "Gb": 6,
                "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10,
                "B": 11, "Cb": 11,
            }
            if not s:
                raise ValueError("root_note string cannot be empty")
            norm = s[0].upper() + s[1:]
            if norm not in name_map:
                raise ValueError(
                    "Unknown note name '%s'. Use C, C#, Db, D, ..., B." % value
                )
            root = name_map[norm]
    else:
        raise ValueError(
            "root_note must be int (0-11) or note name string ('C#', 'F', ...)"
        )
    if not 0 <= root <= 11:
        raise ValueError("root_note must be 0-11 (C=0, C#=1, ... B=11)")
    return root
