"""
LivePilot - Clip domain handlers (11 commands).
"""

from .router import register
from .utils import get_clip, get_clip_slot


@register("get_clip_info")
def get_clip_info(song, params):
    """Return detailed info for a single clip."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)

    result = {
        "track_index": track_index,
        "clip_index": clip_index,
        "name": clip.name,
        "color_index": clip.color_index,
        "length": clip.length,
        "is_playing": clip.is_playing,
        "is_recording": clip.is_recording,
        "is_midi_clip": clip.is_midi_clip,
        "is_audio_clip": clip.is_audio_clip,
        "looping": clip.looping,
        "loop_start": clip.loop_start,
        "loop_end": clip.loop_end,
        "start_marker": clip.start_marker,
        "end_marker": clip.end_marker,
        "launch_mode": clip.launch_mode,
        "launch_quantization": clip.launch_quantization,
    }

    # Audio-clip-specific fields
    if clip.is_audio_clip:
        result["warping"] = clip.warping
        result["warp_mode"] = clip.warp_mode

    return result


@register("create_clip")
def create_clip(song, params):
    """Create an empty MIDI clip in the given clip slot."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    length = float(params["length"])
    if length <= 0:
        raise ValueError("Clip length must be > 0")

    clip_slot = get_clip_slot(song, track_index, clip_index)
    clip_slot.create_clip(length)
    clip = clip_slot.clip

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "name": clip.name,
        "length": clip.length,
    }


@register("delete_clip")
def delete_clip(song, params):
    """Delete the clip in the given clip slot."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip_slot = get_clip_slot(song, track_index, clip_index)
    clip_slot.delete_clip()
    return {"track_index": track_index, "clip_index": clip_index, "deleted": True}


@register("duplicate_clip")
def duplicate_clip(song, params):
    """Duplicate a clip from one slot to another."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    target_track = int(params["target_track"])
    target_clip = int(params["target_clip"])

    source_slot = get_clip_slot(song, track_index, clip_index)
    target_slot = get_clip_slot(song, target_track, target_clip)
    source_slot.duplicate_clip_to(target_slot)

    return {
        "source_track": track_index,
        "source_clip": clip_index,
        "target_track": target_track,
        "target_clip": target_clip,
        "duplicated": True,
    }


@register("fire_clip")
def fire_clip(song, params):
    """Launch/fire a clip slot."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip_slot = get_clip_slot(song, track_index, clip_index)
    clip_slot.fire()
    return {"track_index": track_index, "clip_index": clip_index, "fired": True}


@register("stop_clip")
def stop_clip(song, params):
    """Stop a clip slot."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip_slot = get_clip_slot(song, track_index, clip_index)
    clip_slot.stop()
    return {"track_index": track_index, "clip_index": clip_index, "stopped": True}


@register("set_clip_name")
def set_clip_name(song, params):
    """Rename a clip."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)
    clip.name = str(params["name"])
    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "name": clip.name,
    }


@register("set_clip_color")
def set_clip_color(song, params):
    """Set a clip's color."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)
    clip.color_index = int(params["color_index"])
    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "color_index": clip.color_index,
    }


@register("set_clip_loop")
def set_clip_loop(song, params):
    """Enable/disable clip looping and optionally set loop start/end."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)

    # Set end before start to avoid Live's loop_start < loop_end clamping.
    # Expanding the window first ensures the left edge can move freely.
    if "end" in params:
        clip.loop_end = float(params["end"])
    if "start" in params:
        clip.loop_start = float(params["start"])
    if "enabled" in params:
        clip.looping = bool(params["enabled"])

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "looping": clip.looping,
        "loop_start": clip.loop_start,
        "loop_end": clip.loop_end,
    }


@register("set_clip_launch")
def set_clip_launch(song, params):
    """Set clip launch mode and optional quantization."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)

    clip.launch_mode = int(params["mode"])
    if "quantization" in params:
        clip.launch_quantization = int(params["quantization"])

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "launch_mode": clip.launch_mode,
        "launch_quantization": clip.launch_quantization,
    }


@register("set_clip_warp_mode")
def set_clip_warp_mode(song, params):
    """Set warp mode for an audio clip."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)

    if clip.is_midi_clip:
        raise ValueError("Warp modes only apply to audio clips")

    mode = int(params["mode"])
    if mode not in (0, 1, 2, 3, 4, 6):
        raise ValueError(
            "Invalid warp mode %d. Valid: 0=Beats, 1=Tones, 2=Texture, "
            "3=Re-Pitch, 4=Complex, 6=Complex Pro" % mode
        )

    # Enable warping first so warp_mode assignment is accepted by Live,
    # then disable afterwards if requested.
    enable_warping = params.get("warping")
    if enable_warping is not None and bool(enable_warping):
        clip.warping = True

    clip.warp_mode = mode

    if enable_warping is not None and not bool(enable_warping):
        clip.warping = False

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "warp_mode": clip.warp_mode,
        "warping": clip.warping,
    }
