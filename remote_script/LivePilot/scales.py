"""
LivePilot — Song-level scale handlers (Live 12.0+).

Exposes Song.root_note / scale_mode / scale_name / scale_intervals via the
LivePilot TCP protocol. The scale list is resolved via a tolerant helper
that probes multiple attribute names because Live 12.4 moved/renamed
``Song.scale_names`` (see BUG-2026-04-22#2).

All props shipped in Live 12.0 when Scale Mode was introduced.
Gated behind the `song_scale_api` feature flag for defensive safety.
"""

from .router import register
from ._scale_helpers import (
    _BUILTIN_SCALES_FALLBACK,
    _coerce_root_note,
    _resolve_scale_names,
)


@register("get_song_scale")
def get_song_scale(song, params):
    """Read Live's current Scale Mode state."""
    from .version_detect import has_feature
    if not has_feature("song_scale_api"):
        raise RuntimeError("Song scale API requires Live 12.0+.")
    return {
        "root_note": int(song.root_note),
        "scale_mode": bool(song.scale_mode),
        "scale_name": str(song.scale_name),
        "scale_intervals": list(song.scale_intervals),
        "available_scales": _resolve_scale_names(song),
    }


@register("set_song_scale")
def set_song_scale(song, params):
    """Set both root_note and scale_name atomically.

    root_note accepts int 0-11 OR a note-name string like "C#", "F", "Bb".
    scale_name is case-insensitive and validated against Live's scale list
    (with a fallback to the built-in names when Live 12.4 hides scale_names).
    """
    from .version_detect import has_feature
    if not has_feature("song_scale_api"):
        raise RuntimeError("Song scale API requires Live 12.0+.")
    root = _coerce_root_note(params["root_note"])
    name = str(params["scale_name"]).strip()
    available = _resolve_scale_names(song)
    # Case-insensitive match against Live's list (or fallback).
    match = None
    for candidate in available:
        if candidate.lower() == name.lower():
            match = candidate
            break
    if match is None:
        raise ValueError(
            "Unknown scale '%s'. Available: %s" % (name, ", ".join(available))
        )
    song.root_note = root
    song.scale_name = match
    return {
        "root_note": int(song.root_note),
        "scale_name": str(song.scale_name),
        "scale_intervals": list(song.scale_intervals),
    }


@register("set_song_scale_mode")
def set_song_scale_mode(song, params):
    """Enable/disable Scale Mode on the set."""
    from .version_detect import has_feature
    if not has_feature("song_scale_api"):
        raise RuntimeError("Song scale API requires Live 12.0+.")
    song.scale_mode = bool(params["enabled"])
    return {"scale_mode": bool(song.scale_mode)}


@register("list_available_scales")
def list_available_scales(song, params):
    """Return Live's built-in scale names — tolerant of 12.4 API drop."""
    from .version_detect import has_feature
    if not has_feature("song_scale_api"):
        raise RuntimeError("Song scale API requires Live 12.0+.")
    return {"scales": _resolve_scale_names(song)}


@register("get_tuning_system")
def get_tuning_system(song, params):
    """Read the current Tuning System state (Live 12.1+).

    Returns name, pseudo-octave size, range, reference pitch,
    and the full per-degree cent offset table.
    """
    from .version_detect import has_feature
    if not has_feature("tuning_system"):
        raise RuntimeError("Tuning System requires Live 12.1+.")
    ts = song.tuning_system
    return {
        "name": str(ts.name),
        "pseudo_octave_in_cents": float(ts.pseudo_octave_in_cents),
        "lowest_note": int(ts.lowest_note),
        "highest_note": int(ts.highest_note),
        "reference_pitch": float(ts.reference_pitch),
        "note_tunings": list(ts.note_tunings),
    }


@register("set_tuning_reference_pitch")
def set_tuning_reference_pitch(song, params):
    """Set the tuning reference pitch in Hz (Live 12.1+)."""
    from .version_detect import has_feature
    if not has_feature("tuning_system"):
        raise RuntimeError("Tuning System requires Live 12.1+.")
    pitch = float(params["reference_pitch"])
    if pitch <= 0:
        raise ValueError("reference_pitch must be > 0 Hz")
    song.tuning_system.reference_pitch = pitch
    return {"reference_pitch": float(song.tuning_system.reference_pitch)}


@register("set_tuning_note")
def set_tuning_note(song, params):
    """Set the cent offset for a single scale degree (Live 12.1+).

    degree:       0-based index into note_tunings
    cent_offset:  offset in cents from 12-TET (float, any sign)
    """
    from .version_detect import has_feature
    if not has_feature("tuning_system"):
        raise RuntimeError("Tuning System requires Live 12.1+.")
    ts = song.tuning_system
    degree = int(params["degree"])
    cents = float(params["cent_offset"])
    tunings = list(ts.note_tunings)
    if not 0 <= degree < len(tunings):
        raise IndexError(
            "degree %d out of range (0..%d)" % (degree, len(tunings) - 1)
        )
    tunings[degree] = cents
    ts.note_tunings = tunings
    return {"degree": degree, "cent_offset": cents}


@register("reset_tuning_system")
def reset_tuning_system(song, params):
    """Reset all per-degree tuning offsets to 12-TET (Live 12.1+)."""
    from .version_detect import has_feature
    if not has_feature("tuning_system"):
        raise RuntimeError("Tuning System requires Live 12.1+.")
    ts = song.tuning_system
    ts.note_tunings = [0.0] * len(ts.note_tunings)
    return {"note_tunings": list(ts.note_tunings)}
