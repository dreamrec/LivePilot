"""
LivePilot — Groove Pool handlers (Live 11+).

Exposes ``song.groove_pool`` enumeration, per-groove parameter
tuning, per-clip groove assignment, and the master
``song.groove_amount`` dial.

Groove ids are zero-based indices into ``song.groove_pool.grooves``;
the index is stable for the lifetime of the pool but may shift if
the user adds/removes grooves in the UI. Callers should re-list
before issuing long-running sequences that depend on a specific id.
"""

from .router import register
from .utils import get_clip


def _groove_info(groove, groove_id):
    """Serialize a Groove object to a plain dict."""
    return {
        "id": int(groove_id),
        "name": str(groove.name),
        "base": int(getattr(groove, "base", 0)),
        "quantization_amount": float(groove.quantization_amount),
        "random_amount": float(groove.random_amount),
        "timing_amount": float(groove.timing_amount),
        "velocity_amount": float(groove.velocity_amount),
    }


def _get_groove(song, groove_id):
    """Resolve a groove_id to a Groove object, raising IndexError on miss."""
    grooves = list(song.groove_pool.grooves)
    idx = int(groove_id)
    if not 0 <= idx < len(grooves):
        raise IndexError(
            "groove_id %d out of range (0..%d). Groove pool has %d grooves."
            % (idx, len(grooves) - 1 if grooves else -1, len(grooves))
        )
    return grooves[idx]


@register("list_grooves")
def list_grooves(song, params):
    """List all grooves in the Groove Pool (Live 11+)."""
    from .version_detect import has_feature
    if not has_feature("groove_pool_api"):
        raise RuntimeError("Groove pool API requires Live 11+.")
    grooves = []
    for i, g in enumerate(song.groove_pool.grooves):
        grooves.append(_groove_info(g, i))
    return {"grooves": grooves}


@register("get_groove_info")
def get_groove_info(song, params):
    """Read a single groove's parameters (Live 11+)."""
    from .version_detect import has_feature
    if not has_feature("groove_pool_api"):
        raise RuntimeError("Groove pool API requires Live 11+.")
    groove = _get_groove(song, params["groove_id"])
    return _groove_info(groove, params["groove_id"])


@register("set_groove_params")
def set_groove_params(song, params):
    """Set one or more groove parameters (Live 11+).

    Any of quantization_amount, random_amount, timing_amount,
    velocity_amount may be omitted — omitted fields leave the current
    value untouched. quantization/random/timing are 0.0-1.0; velocity
    is signed -1.0 to 1.0 (negative = subtract velocity, positive = add).
    """
    from .version_detect import has_feature
    if not has_feature("groove_pool_api"):
        raise RuntimeError("Groove pool API requires Live 11+.")
    groove = _get_groove(song, params["groove_id"])

    if "quantization_amount" in params:
        v = float(params["quantization_amount"])
        if not 0.0 <= v <= 1.0:
            raise ValueError("quantization_amount must be 0.0-1.0")
        groove.quantization_amount = v
    if "random_amount" in params:
        v = float(params["random_amount"])
        if not 0.0 <= v <= 1.0:
            raise ValueError("random_amount must be 0.0-1.0")
        groove.random_amount = v
    if "timing_amount" in params:
        v = float(params["timing_amount"])
        if not 0.0 <= v <= 1.0:
            raise ValueError("timing_amount must be 0.0-1.0")
        groove.timing_amount = v
    if "velocity_amount" in params:
        v = float(params["velocity_amount"])
        if not -1.0 <= v <= 1.0:
            raise ValueError("velocity_amount must be -1.0 to 1.0")
        groove.velocity_amount = v

    return _groove_info(groove, params["groove_id"])


@register("assign_clip_groove")
def assign_clip_groove(song, params):
    """Assign (or clear) a groove on a clip (Live 11+).

    Pass ``groove_id = -1`` (or null/None) to clear the clip's groove.
    """
    from .version_detect import has_feature
    if not has_feature("groove_pool_api"):
        raise RuntimeError("Groove pool API requires Live 11+.")
    clip = get_clip(song, int(params["track_index"]), int(params["clip_index"]))

    groove_id = params.get("groove_id")
    if groove_id is None or int(groove_id) < 0:
        clip.groove = None
        return {
            "track_index": int(params["track_index"]),
            "clip_index": int(params["clip_index"]),
            "groove_id": None,
            "groove_name": None,
        }

    groove = _get_groove(song, groove_id)
    clip.groove = groove
    return {
        "track_index": int(params["track_index"]),
        "clip_index": int(params["clip_index"]),
        "groove_id": int(groove_id),
        "groove_name": str(groove.name),
    }


@register("get_clip_groove")
def get_clip_groove(song, params):
    """Read a clip's current groove assignment (Live 11+).

    Returns ``{groove_id: int, groove_name: str}`` when set, or
    ``{groove_id: None, groove_name: None}`` when unset.
    """
    from .version_detect import has_feature
    if not has_feature("groove_pool_api"):
        raise RuntimeError("Groove pool API requires Live 11+.")
    clip = get_clip(song, int(params["track_index"]), int(params["clip_index"]))

    clip_groove = getattr(clip, "groove", None)
    if clip_groove is None:
        return {"groove_id": None, "groove_name": None}

    # Resolve the groove object's id by matching against the pool. Live's
    # Python API compares Groove objects by identity, so == is fine here;
    # we fall back to a None id (but keep the name) if the clip's groove
    # somehow isn't in the current pool — shouldn't happen in practice but
    # avoids crashing on an orphan reference.
    for i, g in enumerate(song.groove_pool.grooves):
        if g == clip_groove:
            return {"groove_id": i, "groove_name": str(g.name)}
    return {"groove_id": None, "groove_name": str(clip_groove.name)}


@register("get_song_groove_amount")
def get_song_groove_amount(song, params):
    """Read the master groove amount dial (Live 11+)."""
    from .version_detect import has_feature
    if not has_feature("groove_pool_api"):
        raise RuntimeError("Groove pool API requires Live 11+.")
    return {"groove_amount": float(song.groove_amount)}


@register("set_song_groove_amount")
def set_song_groove_amount(song, params):
    """Set the master groove amount dial (Live 11+).

    Range: 0.0-1.31. Live's spec nominally goes to 1.0 but the
    exposed property clamps at roughly 1.31 internally; we accept
    the full exposed range so scripts can match UI nudges exactly.
    """
    from .version_detect import has_feature
    if not has_feature("groove_pool_api"):
        raise RuntimeError("Groove pool API requires Live 11+.")
    amount = float(params["amount"])
    if not 0.0 <= amount <= 1.31:
        raise ValueError("amount must be 0.0-1.31")
    song.groove_amount = amount
    return {"groove_amount": float(song.groove_amount)}
