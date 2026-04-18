"""
LivePilot — Take Lanes handlers (Live 12.0 UI / 12.2 API).

Take lanes are alternative clip rows stacked under an arrangement
track — they let you audition or comp multiple passes of the same
part without occupying extra tracks. Live 12.0 introduced them in
the UI; the scripting API that lets us create/rename them and
attach clips landed in Live 12.2.

Read-only introspection (``get_take_lanes`` / ``get_take_lane_clips``)
works on any Live 12.x since it's pure attribute traversal — we only
feature-gate the mutation ops behind ``take_lanes_api`` (12.2.0).

The ``track.take_lanes`` list grows through ``track.create_take_lane()``
(when exposed) and each TakeLane exposes ``name``, ``is_frozen``,
``clips``, and — in 12.2+ — ``create_audio_clip`` / ``create_midi_clip``.
"""

from .router import register
from .utils import get_track


def _get_take_lane(track, lane_index):
    """Resolve a lane_index to a TakeLane object, raising IndexError on miss."""
    lanes = list(getattr(track, "take_lanes", []))
    idx = int(lane_index)
    if not 0 <= idx < len(lanes):
        raise IndexError(
            "lane_index %d out of range (0..%d). Track has %d take lanes."
            % (idx, len(lanes) - 1 if lanes else -1, len(lanes))
        )
    return lanes[idx]


@register("get_take_lanes")
def get_take_lanes(song, params):
    """List all take lanes on a track.

    Pure introspection — works on Live 12.0+ even when the creation
    API isn't exposed. Returns an empty list if the track doesn't
    expose ``take_lanes`` at all.
    """
    track = get_track(song, int(params["track_index"]))
    lanes = getattr(track, "take_lanes", None)
    if lanes is None:
        return {"lanes": []}
    out = []
    for i, lane in enumerate(lanes):
        out.append({
            "index": i,
            "name": str(getattr(lane, "name", "")),
            "is_frozen": bool(getattr(lane, "is_frozen", False)),
            "clip_count": len(list(getattr(lane, "clips", []))),
        })
    return {"lanes": out}


@register("create_take_lane")
def create_take_lane(song, params):
    """Create a new take lane on a track (Live 12.2+).

    Returns the new lane's index and name. Raises if the Live version
    predates 12.2 or if the specific build doesn't expose
    ``Track.create_take_lane`` — some pre-release 12.2 builds shipped
    the TakeLane read surface without the create method.
    """
    from .version_detect import has_feature
    if not has_feature("take_lanes_api"):
        raise RuntimeError("Take lane creation requires Live 12.2+.")
    track = get_track(song, int(params["track_index"]))
    if not hasattr(track, "create_take_lane"):
        raise RuntimeError(
            "Track.create_take_lane is not available in this Live version."
        )
    track.create_take_lane()
    lanes = list(track.take_lanes)
    new_index = len(lanes) - 1
    lane = lanes[new_index]
    return {
        "lane_index": new_index,
        "name": str(getattr(lane, "name", "")),
    }


@register("set_take_lane_name")
def set_take_lane_name(song, params):
    """Rename an existing take lane (Live 12.2+)."""
    from .version_detect import has_feature
    if not has_feature("take_lanes_api"):
        raise RuntimeError("Take lane rename requires Live 12.2+.")
    track = get_track(song, int(params["track_index"]))
    lane = _get_take_lane(track, params["lane_index"])
    lane.name = str(params["name"])
    return {"name": str(lane.name)}


@register("create_audio_clip_on_take_lane")
def create_audio_clip_on_take_lane(song, params):
    """Create an arrangement audio clip on a specific take lane (Live 12.2+).

    start_time / length are in beats. length must be > 0. The track
    must be an audio track — Live will raise if called on a MIDI track.
    """
    from .version_detect import has_feature
    if not has_feature("take_lanes_api"):
        raise RuntimeError("Take lane clip creation requires Live 12.2+.")
    track = get_track(song, int(params["track_index"]))
    lane = _get_take_lane(track, params["lane_index"])
    if not hasattr(lane, "create_audio_clip"):
        raise RuntimeError(
            "TakeLane.create_audio_clip is not available in this Live version."
        )
    start = float(params["start_time"])
    length = float(params["length"])
    if length <= 0:
        raise ValueError("length must be > 0")
    lane.create_audio_clip(start, length)
    return {
        "ok": True,
        "track_index": int(params["track_index"]),
        "lane_index": int(params["lane_index"]),
        "start_time": start,
        "length": length,
    }


@register("create_midi_clip_on_take_lane")
def create_midi_clip_on_take_lane(song, params):
    """Create an arrangement MIDI clip on a specific take lane (Live 12.2+).

    start_time / length are in beats. length must be > 0. The track
    must be a MIDI track — Live will raise if called on an audio track.
    """
    from .version_detect import has_feature
    if not has_feature("take_lanes_api"):
        raise RuntimeError("Take lane clip creation requires Live 12.2+.")
    track = get_track(song, int(params["track_index"]))
    lane = _get_take_lane(track, params["lane_index"])
    if not hasattr(lane, "create_midi_clip"):
        raise RuntimeError(
            "TakeLane.create_midi_clip is not available in this Live version."
        )
    start = float(params["start_time"])
    length = float(params["length"])
    if length <= 0:
        raise ValueError("length must be > 0")
    lane.create_midi_clip(start, length)
    return {
        "ok": True,
        "track_index": int(params["track_index"]),
        "lane_index": int(params["lane_index"]),
        "start_time": start,
        "length": length,
    }


@register("get_take_lane_clips")
def get_take_lane_clips(song, params):
    """List the arrangement clips on a specific take lane.

    Pure introspection — no version gate. Returns ``{clips: [...]}``
    where each clip entry has name, start_time, length, and
    is_midi_clip.
    """
    track = get_track(song, int(params["track_index"]))
    lane = _get_take_lane(track, params["lane_index"])
    out = []
    for clip in getattr(lane, "clips", []):
        out.append({
            "name": str(getattr(clip, "name", "")),
            "start_time": float(getattr(clip, "start_time", 0.0)),
            "length": float(getattr(clip, "length", 0.0)),
            "is_midi_clip": bool(getattr(clip, "is_midi_clip", False)),
        })
    return {"clips": out}
