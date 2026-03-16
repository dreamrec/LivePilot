"""
LivePilot - Track domain handlers (12 commands).
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
        "clip_slots": clips,
        "devices": devices,
        "mixer": mixer,
        "sends": sends,
    }

    # Only regular tracks have arm and input type
    if track_index >= 0:
        result["arm"] = track.arm
        result["has_midi_input"] = track.has_midi_input
        result["has_audio_input"] = track.has_audio_input

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
    song.duplicate_track(track_index)
    new_index = track_index + 1
    return {"index": new_index, "name": list(song.tracks)[new_index].name}


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
