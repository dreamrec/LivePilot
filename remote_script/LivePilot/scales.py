"""
LivePilot — Song-level scale handlers (Live 12.0+).

Exposes Song.root_note / scale_mode / scale_name / scale_intervals
and the Song.scale_names list via the LivePilot TCP protocol.

All four props shipped in Live 12.0 when Scale Mode was introduced.
Gated behind the `song_scale_api` feature flag for defensive safety
on older versions, even though we target 12.3.6.
"""

from .router import register


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
        "available_scales": list(song.scale_names),
    }


@register("set_song_scale")
def set_song_scale(song, params):
    """Set both root_note (0-11) and scale_name atomically."""
    from .version_detect import has_feature
    if not has_feature("song_scale_api"):
        raise RuntimeError("Song scale API requires Live 12.0+.")
    root = int(params["root_note"])
    if not 0 <= root <= 11:
        raise ValueError("root_note must be 0-11 (C=0, C#=1, ... B=11)")
    name = str(params["scale_name"])
    available = list(song.scale_names)
    if name not in available:
        raise ValueError(
            "Unknown scale '%s'. Available: %s" % (name, ", ".join(available))
        )
    song.root_note = root
    song.scale_name = name
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
    """Return Live's built-in list of scale names."""
    from .version_detect import has_feature
    if not has_feature("song_scale_api"):
        raise RuntimeError("Song scale API requires Live 12.0+.")
    return {"scales": list(song.scale_names)}
