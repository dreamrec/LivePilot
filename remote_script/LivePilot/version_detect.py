"""
LivePilot - Ableton Live version detection and feature flags.

Detects the running Live version and provides feature availability checks.
Used by handlers to conditionally use new APIs (12.1.10+, 12.2+, 12.3+).
"""

import Live

# ── Feature version requirements ────────────────────────────────────────

FEATURES = {
    "song_scale_api": (12, 0, 0),
    "clip_follow_action_v2": (12, 0, 0),
    "create_midi_clip_arrangement": (12, 1, 10),
    "looper_export": (12, 1, 0),
    "tuning_system": (12, 1, 0),
    "display_value": (12, 2, 0),
    "clip_start_time_observable": (12, 2, 0),
    "take_lanes_api": (12, 2, 0),
    "scene_follow_actions": (12, 2, 0),
    "insert_device": (12, 3, 0),
    "insert_chain": (12, 3, 0),
    "drum_chain_in_note": (12, 3, 0),
    "stem_separation": (12, 3, 0),
    "replace_sample_native": (12, 4, 0),
}


# ── Cached version ──────────────────────────────────────────────────────

_cached_version = None


def get_live_version():
    """Return (major, minor, patch) of the running Live instance.

    Uses Live.Application.get_application() to read version info.
    Returns a conservative (12, 0, 0) fallback on detection failure BUT
    does NOT cache the fallback — earlier versions cached any failure,
    which pinned the whole session to the oldest capability tier even
    after Live finished initializing. Only successful reads are cached.
    """
    global _cached_version
    if _cached_version is not None:
        return _cached_version

    try:
        app = Live.Application.get_application()
        major = app.get_major_version()
        minor = app.get_minor_version()
        # get_bugfix_version() was added later; fall back to 0
        try:
            patch = app.get_bugfix_version()
        except AttributeError:
            patch = 0
        _cached_version = (int(major), int(minor), int(patch))
        return _cached_version
    except Exception:
        # Don't cache failures — next call may succeed once Live is fully up.
        return (12, 0, 0)


def has_feature(feature_name):
    """Check if a feature is available in the running Live version.

    Returns True if the detected version >= the feature's required version.
    Returns False for unknown feature names (safe default).
    """
    required = FEATURES.get(feature_name)
    if required is None:
        return False
    return get_live_version() >= required


def get_api_features():
    """Return a dict of all feature flags for the current version."""
    return {name: has_feature(name) for name in FEATURES}


def version_string():
    """Return version as a dot-separated string, e.g. '12.3.6'."""
    v = get_live_version()
    return "%d.%d.%d" % v
