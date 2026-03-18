"""
LivePilot - Error formatting, validation helpers, and JSON serialization.
"""

import json


# ── Error codes ──────────────────────────────────────────────────────────────

INDEX_ERROR = "INDEX_ERROR"
NOT_FOUND = "NOT_FOUND"
INVALID_PARAM = "INVALID_PARAM"
STATE_ERROR = "STATE_ERROR"
TIMEOUT = "TIMEOUT"
INTERNAL = "INTERNAL"


# ── Response builders ────────────────────────────────────────────────────────

def success_response(request_id, result=None):
    """Build a success JSON-RPC-style response."""
    resp = {"id": request_id, "ok": True}
    if result is not None:
        resp["result"] = result
    return resp


def error_response(request_id, message, code=INTERNAL):
    """Build an error JSON-RPC-style response."""
    return {
        "id": request_id,
        "ok": False,
        "error": {
            "code": code,
            "message": str(message),
        },
    }


# ── Validation helpers ───────────────────────────────────────────────────────

MASTER_TRACK_INDEX = -1000


def get_track(song, track_index):
    """Return a track by index (0-based).  Supports negative indices for
    return tracks: -1 = first return, -2 = second return, etc.
    Use -1000 for the master track."""
    if track_index == MASTER_TRACK_INDEX:
        return song.master_track
    tracks = list(song.tracks)
    if track_index < 0:
        return_tracks = list(song.return_tracks)
        ri = abs(track_index) - 1
        if ri >= len(return_tracks):
            raise IndexError(
                "Return track index %d out of range (0..%d)"
                % (ri, len(return_tracks) - 1)
            )
        return return_tracks[ri]
    if track_index >= len(tracks):
        raise IndexError(
            "Track index %d out of range (0..%d)"
            % (track_index, len(tracks) - 1)
        )
    return tracks[track_index]


def get_clip_slot(song, track_index, clip_index):
    """Return a clip slot by track + slot index."""
    track = get_track(song, track_index)
    slots = list(track.clip_slots)
    if clip_index < 0 or clip_index >= len(slots):
        raise IndexError(
            "Clip slot index %d out of range (0..%d)"
            % (clip_index, len(slots) - 1)
        )
    return slots[clip_index]


def get_clip(song, track_index, clip_index):
    """Return a clip (must exist in the slot)."""
    slot = get_clip_slot(song, track_index, clip_index)
    clip = slot.clip
    if clip is None:
        raise ValueError(
            "No clip in track %d, slot %d" % (track_index, clip_index)
        )
    return clip


def get_device(track, device_index):
    """Return a device from a track by index."""
    devices = list(track.devices)
    if device_index < 0 or device_index >= len(devices):
        raise IndexError(
            "Device index %d out of range (0..%d)"
            % (device_index, len(devices) - 1)
        )
    return devices[device_index]


def get_scene(song, scene_index):
    """Return a scene by index."""
    scenes = list(song.scenes)
    if scene_index < 0 or scene_index >= len(scenes):
        raise IndexError(
            "Scene index %d out of range (0..%d)"
            % (scene_index, len(scenes) - 1)
        )
    return scenes[scene_index]


# ── JSON serialization ───────────────────────────────────────────────────────

def serialize_json(data):
    """Serialize *data* to a compact JSON string with a trailing newline."""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=True) + "\n"
