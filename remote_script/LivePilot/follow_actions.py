"""
LivePilot — Follow Actions handlers (Live 12.0+ clip, 12.2+ scene).

Exposes the revamped clip follow-action API (Live 12.0) and the
scene-level follow-action properties added in Live 12.2.

Clip follow-actions use an integer enum internally (0..8) mapped
bidirectionally to string names via ``_FOLLOW_ACTION_NAMES``. We
accept strings from tool wrappers and convert to int for the Live
API; on read we convert back to the string form. Unknown / future
enum values (e.g. anything Live 12.4+ might add) fall through as a
plain stringified int rather than raising, so the tool remains
forward-compatible for additive enum growth.

Chance values are documented by Live as 0.0-1.0 normalized. We
accept the same range from callers and pass through unchanged.
"""

from .router import register
from .utils import get_clip, get_scene


_FOLLOW_ACTION_NAMES = [
    "stop",         # 0
    "play_again",   # 1
    "previous",     # 2
    "next",         # 3
    "first",        # 4
    "last",         # 5
    "any",          # 6
    "other",        # 7
    "jump",         # 8
]
_FOLLOW_ACTION_IDX = {name: i for i, name in enumerate(_FOLLOW_ACTION_NAMES)}

_FOLLOW_ACTION_PRESETS = {
    "loop_forever":    {"action_a": "play_again", "action_b": "stop",
                        "chance_a": 1.0, "chance_b": 0.0, "time": 1.0},
    "random_walk":     {"action_a": "next", "action_b": "previous",
                        "chance_a": 0.5, "chance_b": 0.5, "time": 1.0},
    "next_after_one":  {"action_a": "next", "action_b": "stop",
                        "chance_a": 1.0, "chance_b": 0.0, "time": 1.0},
    "stop_after_one":  {"action_a": "stop", "action_b": "stop",
                        "chance_a": 1.0, "chance_b": 0.0, "time": 1.0},
}


def _action_name(idx):
    """Map int enum → string, tolerating out-of-range (future) values."""
    try:
        return _FOLLOW_ACTION_NAMES[int(idx)]
    except (IndexError, ValueError):
        return str(idx)


def _action_idx(name_or_int):
    """Map string → int enum, passing through ints untouched."""
    if isinstance(name_or_int, int):
        return name_or_int
    key = str(name_or_int).lower()
    if key not in _FOLLOW_ACTION_IDX:
        raise ValueError(
            "Unknown follow action '%s'. Valid: %s"
            % (name_or_int, ", ".join(_FOLLOW_ACTION_NAMES))
        )
    return _FOLLOW_ACTION_IDX[key]


def _read_clip_follow_action(clip):
    """Snapshot all clip follow-action fields as a plain dict."""
    return {
        "enabled": bool(getattr(clip, "follow_action_enabled", False)),
        "action_a": _action_name(clip.follow_action_a),
        "action_b": _action_name(clip.follow_action_b),
        "chance_a": float(clip.follow_action_chance_a),
        "chance_b": float(clip.follow_action_chance_b),
        "time": float(clip.follow_action_time),
    }


@register("list_follow_action_types")
def list_follow_action_types(song, params):
    """Return the list of valid follow-action names."""
    return {"actions": list(_FOLLOW_ACTION_NAMES)}


@register("get_clip_follow_action")
def get_clip_follow_action(song, params):
    """Read a clip's follow-action state (Live 12.0+)."""
    from .version_detect import has_feature
    if not has_feature("clip_follow_action_v2"):
        raise RuntimeError("Clip follow actions require Live 12.0+.")
    clip = get_clip(song, int(params["track_index"]), int(params["clip_index"]))
    return _read_clip_follow_action(clip)


@register("set_clip_follow_action")
def set_clip_follow_action(song, params):
    """Set a clip's follow-action state (Live 12.0+).

    Any of action_a, action_b, chance_a, chance_b, time, enabled may
    be omitted — omitted fields leave the current value untouched.
    Chance values are 0.0-1.0 normalized per Live's public API.
    """
    from .version_detect import has_feature
    if not has_feature("clip_follow_action_v2"):
        raise RuntimeError("Clip follow actions require Live 12.0+.")
    clip = get_clip(song, int(params["track_index"]), int(params["clip_index"]))

    if "action_a" in params:
        clip.follow_action_a = _action_idx(params["action_a"])
    if "action_b" in params:
        clip.follow_action_b = _action_idx(params["action_b"])
    if "chance_a" in params:
        c = float(params["chance_a"])
        if not 0.0 <= c <= 1.0:
            raise ValueError("chance_a must be 0.0-1.0")
        clip.follow_action_chance_a = c
    if "chance_b" in params:
        c = float(params["chance_b"])
        if not 0.0 <= c <= 1.0:
            raise ValueError("chance_b must be 0.0-1.0")
        clip.follow_action_chance_b = c
    if "time" in params:
        t = float(params["time"])
        if t < 0.0:
            raise ValueError("time must be >= 0.0 beats")
        clip.follow_action_time = t
    if "enabled" in params:
        # Some Live versions expose this as ``follow_action_enabled``; fall
        # back silently if the attribute isn't present so the rest of the
        # set still applies on e.g. an older 12.0 point release.
        if hasattr(clip, "follow_action_enabled"):
            clip.follow_action_enabled = bool(params["enabled"])

    return _read_clip_follow_action(clip)


@register("clear_clip_follow_action")
def clear_clip_follow_action(song, params):
    """Disable a clip's follow actions (Live 12.0+)."""
    from .version_detect import has_feature
    if not has_feature("clip_follow_action_v2"):
        raise RuntimeError("Clip follow actions require Live 12.0+.")
    clip = get_clip(song, int(params["track_index"]), int(params["clip_index"]))
    if hasattr(clip, "follow_action_enabled"):
        clip.follow_action_enabled = False
    return {"enabled": False}


@register("apply_follow_action_preset")
def apply_follow_action_preset(song, params):
    """Apply a named follow-action preset to a clip (Live 12.0+)."""
    from .version_detect import has_feature
    if not has_feature("clip_follow_action_v2"):
        raise RuntimeError("Clip follow actions require Live 12.0+.")
    preset_name = str(params["preset"]).lower()
    if preset_name not in _FOLLOW_ACTION_PRESETS:
        raise ValueError(
            "Unknown preset '%s'. Valid: %s"
            % (params["preset"], ", ".join(_FOLLOW_ACTION_PRESETS))
        )
    preset = _FOLLOW_ACTION_PRESETS[preset_name]
    # Delegate to set_clip_follow_action with the preset values merged in.
    # User-supplied params take no precedence — presets are all-or-nothing.
    apply_params = dict(params)
    apply_params.update(preset)
    apply_params["enabled"] = True
    return set_clip_follow_action(song, apply_params)


# ── Scene follow actions (Live 12.2+) ────────────────────────────────────


def _read_scene_follow_action(scene):
    """Snapshot all scene follow-action fields as a plain dict."""
    return {
        "enabled": bool(scene.follow_action_enabled),
        "time": float(scene.follow_action_time),
        "linked": bool(getattr(scene, "follow_action_linked", False)),
        "multiplier": int(getattr(scene, "follow_action_multiplier", 1)),
    }


@register("get_scene_follow_action")
def get_scene_follow_action(song, params):
    """Read a scene's follow-action state (Live 12.2+)."""
    from .version_detect import has_feature
    if not has_feature("scene_follow_actions"):
        raise RuntimeError("Scene follow actions require Live 12.2+.")
    scene = get_scene(song, int(params["scene_index"]))
    return _read_scene_follow_action(scene)


@register("set_scene_follow_action")
def set_scene_follow_action(song, params):
    """Set a scene's follow-action state (Live 12.2+).

    All args except scene_index are optional; omitted ones preserve
    the current value. ``linked`` controls "Longest" mode — when True
    the scene waits for the longest clip's loop length; when False it
    uses ``time * multiplier`` as the trigger point.
    """
    from .version_detect import has_feature
    if not has_feature("scene_follow_actions"):
        raise RuntimeError("Scene follow actions require Live 12.2+.")
    scene = get_scene(song, int(params["scene_index"]))

    if "enabled" in params:
        scene.follow_action_enabled = bool(params["enabled"])
    if "time" in params:
        t = float(params["time"])
        if t < 0.0:
            raise ValueError("time must be >= 0.0 beats")
        scene.follow_action_time = t
    if "linked" in params and hasattr(scene, "follow_action_linked"):
        scene.follow_action_linked = bool(params["linked"])
    if "multiplier" in params and hasattr(scene, "follow_action_multiplier"):
        m = int(params["multiplier"])
        if not 1 <= m <= 8:
            raise ValueError("multiplier must be 1-8")
        scene.follow_action_multiplier = m

    return _read_scene_follow_action(scene)


@register("clear_scene_follow_action")
def clear_scene_follow_action(song, params):
    """Disable a scene's follow action (Live 12.2+)."""
    from .version_detect import has_feature
    if not has_feature("scene_follow_actions"):
        raise RuntimeError("Scene follow actions require Live 12.2+.")
    scene = get_scene(song, int(params["scene_index"]))
    scene.follow_action_enabled = False
    return {"enabled": False}
