"""
LivePilot - Track domain handlers (17 commands).
"""

from .router import register
from .utils import get_track


@register("get_track_info")
def get_track_info(song, params):
    """Return detailed info for a single track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)

    # Clip slots
    clips = []
    for i, slot in enumerate(track.clip_slots):
        clip_info = {
            "index": i,
            "has_clip": slot.has_clip,
        }
        if slot.has_clip and slot.clip:
            clip = slot.clip
            clip_info.update({
                "name": clip.name,
                "color_index": clip.color_index,
                "length": clip.length,
                "is_playing": clip.is_playing,
                "is_recording": clip.is_recording,
                "looping": clip.looping,
                "loop_start": clip.loop_start,
                "loop_end": clip.loop_end,
                "start_marker": clip.start_marker,
                "end_marker": clip.end_marker,
            })
        clips.append(clip_info)

    # Devices
    devices = []
    for i, device in enumerate(track.devices):
        dev_info = {
            "index": i,
            "name": device.name,
            "class_name": device.class_name,
            "is_active": device.is_active,
        }
        dev_params = []
        for j, param in enumerate(device.parameters):
            dev_params.append({
                "index": j,
                "name": param.name,
                "value": param.value,
                "min": param.min,
                "max": param.max,
                "is_quantized": param.is_quantized,
            })
        dev_info["parameters"] = dev_params
        devices.append(dev_info)

    # Mixer info
    mixer = {
        "volume": track.mixer_device.volume.value,
        "panning": track.mixer_device.panning.value,
    }

    # Sends
    sends = []
    for i, send in enumerate(track.mixer_device.sends):
        sends.append({
            "index": i,
            "name": send.name,
            "value": send.value,
            "min": send.min,
            "max": send.max,
        })

    result = {
        "index": track_index,
        "name": track.name,
        "color_index": track.color_index,
        "mute": track.mute,
        "solo": track.solo,
        "is_foldable": track.is_foldable,
        "is_grouped": track.is_grouped,
        "clip_slots": clips,
        "devices": devices,
        "mixer": mixer,
        "sends": sends,
    }

    if track.is_foldable:
        result["fold_state"] = bool(track.fold_state)

    # Regular tracks have arm and input type; return tracks get null values
    if track_index >= 0:
        result["arm"] = track.arm
        result["has_midi_input"] = track.has_midi_input
        result["has_audio_input"] = track.has_audio_input
        result["current_monitoring_state"] = track.current_monitoring_state
    else:
        result["arm"] = None
        result["has_midi_input"] = None
        result["has_audio_input"] = None
        result["is_return_track"] = track_index != -1000
        result["is_master_track"] = track_index == -1000

    return result


@register("create_midi_track")
def create_midi_track(song, params):
    """Create a new MIDI track at the given index."""
    index = int(params.get("index", -1))
    song.create_midi_track(index)
    # The new track is at the requested index (or end if -1)
    if index == -1:
        new_index = len(list(song.tracks)) - 1
    else:
        new_index = index
    track = list(song.tracks)[new_index]
    if "name" in params:
        track.name = str(params["name"])
    if "color_index" in params:
        track.color_index = int(params["color_index"])
    # Ableton auto-arms newly created tracks — disarm to avoid surprises
    if track.arm and not params.get("arm", False):
        track.arm = False
    return {"index": new_index, "name": track.name}


@register("create_audio_track")
def create_audio_track(song, params):
    """Create a new audio track at the given index."""
    index = int(params.get("index", -1))
    song.create_audio_track(index)
    if index == -1:
        new_index = len(list(song.tracks)) - 1
    else:
        new_index = index
    track = list(song.tracks)[new_index]
    if "name" in params:
        track.name = str(params["name"])
    if "color_index" in params:
        track.color_index = int(params["color_index"])
    # Ableton auto-arms newly created tracks — disarm to avoid surprises
    if track.arm and not params.get("arm", False):
        track.arm = False
    return {"index": new_index, "name": track.name}


@register("create_return_track")
def create_return_track(song, params):
    """Create a new return track."""
    song.create_return_track()
    return_tracks = list(song.return_tracks)
    new_index = len(return_tracks) - 1
    return {"index": new_index, "name": return_tracks[new_index].name}


@register("delete_track")
def delete_track(song, params):
    """Delete a track by index."""
    track_index = int(params["track_index"])
    tracks = list(song.tracks)
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(
            "Track index %d out of range (0..%d)"
            % (track_index, len(tracks) - 1)
        )
    song.delete_track(track_index)
    return {"deleted": track_index}


@register("duplicate_track")
def duplicate_track(song, params):
    """Duplicate a track by index."""
    track_index = int(params["track_index"])
    tracks = list(song.tracks)
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError(
            "Track index %d out of range (0..%d)"
            % (track_index, len(tracks) - 1)
        )
    count_before = len(tracks)
    song.duplicate_track(track_index)
    all_tracks = list(song.tracks)
    # For group tracks, Ableton duplicates the group + all children.
    # The duplicate block starts right after the original group's last child.
    added = len(all_tracks) - count_before
    new_index = track_index + added
    return {"index": new_index, "name": all_tracks[new_index].name}


@register("set_track_name")
def set_track_name(song, params):
    """Rename a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    track.name = str(params["name"])
    return {"index": track_index, "name": track.name}


@register("set_track_color")
def set_track_color(song, params):
    """Set a track's color."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    track.color_index = int(params["color_index"])
    return {"index": track_index, "color_index": track.color_index}


@register("set_track_mute")
def set_track_mute(song, params):
    """Mute or unmute a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    track.mute = bool(params["mute"])
    return {"index": track_index, "mute": track.mute}


@register("set_track_solo")
def set_track_solo(song, params):
    """Solo or unsolo a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    track.solo = bool(params["solo"])
    return {"index": track_index, "solo": track.solo}


@register("set_track_arm")
def set_track_arm(song, params):
    """Arm or disarm a track for recording."""
    track_index = int(params["track_index"])
    if track_index < 0:
        raise ValueError("Cannot arm a return track")
    track = get_track(song, track_index)
    track.arm = bool(params["arm"])
    return {"index": track_index, "arm": track.arm}


@register("stop_track_clips")
def stop_track_clips(song, params):
    """Stop all clips on a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    track.stop_all_clips()
    return {"index": track_index, "stopped": True}


@register("set_group_fold")
def set_group_fold(song, params):
    """Fold or unfold a group track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    if not track.is_foldable:
        raise ValueError("Track %d is not a group track" % track_index)
    track.fold_state = int(bool(params["folded"]))
    return {
        "index": track_index,
        "folded": bool(track.fold_state),
    }


@register("set_track_input_monitoring")
def set_track_input_monitoring(song, params):
    """Set input monitoring state for a track (0=In, 1=Auto, 2=Off)."""
    track_index = int(params["track_index"])
    if track_index < 0:
        raise ValueError("Cannot set input monitoring on a return track")
    track = get_track(song, track_index)
    state = int(params["state"])
    if state not in (0, 1, 2):
        raise ValueError(
            "Invalid monitoring state %d. Valid: 0=In, 1=Auto, 2=Off" % state
        )
    track.current_monitoring_state = state
    return {
        "index": track_index,
        "monitoring_state": track.current_monitoring_state,
    }


# ── Freeze / Flatten ────────────────────────────────────────────────────


@register("get_freeze_status")
def get_freeze_status(song, params):
    """Return freeze state for a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    return {
        "track_index": track_index,
        "is_frozen": track.is_frozen,
    }


@register("freeze_track")
def freeze_track(song, params):
    """Freeze a track — render all devices to audio for CPU savings.

    Freeze is async in Ableton — this call initiates it and returns
    immediately. Use get_freeze_status to poll for completion.
    """
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    if track.is_frozen:
        return {
            "track_index": track_index,
            "is_frozen": True,
            "note": "Track is already frozen",
        }
    # Try track.freeze() first (available in some Live versions),
    # then fall back to song-level freeze API
    frozen = False
    try:
        track.freeze()
        frozen = True
    except AttributeError:
        pass

    if not frozen:
        # Song-level API: freeze by track index
        try:
            song.freeze_track(track_index)
            frozen = True
        except AttributeError:
            pass

    if not frozen:
        raise ValueError(
            "freeze() not available via ControlSurface API. "
            "Use Ableton's Freeze Track command (Cmd+F) manually, "
            "or use the M4L bridge for programmatic freeze."
        )
    return {
        "track_index": track_index,
        "freezing": True,
        "note": "Freeze initiated. Poll get_freeze_status to check completion.",
    }


@register("flatten_track")
def flatten_track(song, params):
    """Flatten a frozen track — commits rendered audio permanently.

    Destructive operation. The track must already be frozen.
    Wrapped in undo step so it can be reverted.
    """
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    if not track.is_frozen:
        raise ValueError(
            "Track %d is not frozen. Freeze it first with freeze_track."
            % track_index
        )
    song.begin_undo_step()
    try:
        flattened = False
        try:
            track.flatten()
            flattened = True
        except AttributeError:
            pass
        if not flattened:
            try:
                song.flatten_track(track_index)
                flattened = True
            except AttributeError:
                pass
        if not flattened:
            raise ValueError(
                "flatten() not available via ControlSurface API. "
                "Use Ableton's Flatten command manually."
            )
    finally:
        song.end_undo_step()
    return {
        "track_index": track_index,
        "flattened": True,
    }
