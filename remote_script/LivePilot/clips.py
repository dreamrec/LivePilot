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
        # BUG-A4: expose pitch/gain so callers can reason about sample
        # transposition vs session key. Pitch is in semitones (int, -48..+48),
        # pitch_fine in cents (-50..+50), gain linear (normalized 0..1 in Live).
        # Some Live builds expose these as None on freshly-recorded clips
        # before a warp pass; wrap in try/except for safety.
        for attr in ("pitch_coarse", "pitch_fine", "gain"):
            try:
                result[attr] = getattr(clip, attr)
            except AttributeError:
                pass

    return result


@register("create_clip")
def create_clip(song, params):
    """Create an empty MIDI clip in the given clip slot.

    BUG-2026-04-22#1c FIX: Live's `clip_slot.create_clip(length)` sets
    the clip's *length* but defaults `loop_end` to length/2 in some
    configurations (depends on time signature). Without enforcing
    `loop_end == length`, downstream `add_notes` calls silently drop
    notes that fall beyond the implicit half-length loop. This handler
    now applies the invariant via `_apply_clip_length_invariants` (a
    pure-Python helper that's also unit-tested).
    """
    from ._clip_helpers import _apply_clip_length_invariants

    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    length = float(params["length"])
    if length <= 0:
        raise ValueError("Clip length must be > 0")

    clip_slot = get_clip_slot(song, track_index, clip_index)
    if clip_slot.has_clip:
        raise ValueError(
            "Clip slot %d on track %d already has a clip. "
            "Delete it first with delete_clip." % (clip_index, track_index)
        )
    clip_slot.create_clip(length)
    clip = clip_slot.clip

    invariants = _apply_clip_length_invariants(clip, length)

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "name": clip.name,
        "length": clip.length,
        "loop_end": invariants["loop_end"],
        "end_marker": invariants["end_marker"],
    }


@register("delete_clip")
def delete_clip(song, params):
    """Delete the clip in the given clip slot."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip_slot = get_clip_slot(song, track_index, clip_index)
    if not clip_slot.has_clip:
        raise ValueError("No clip in slot %d on track %d" % (clip_index, track_index))
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

    # Conditional ordering to avoid Live's loop_start < loop_end clamping.
    # When expanding the window, set the expanding edge first.
    # When shrinking, set the contracting edge first.
    new_end = float(params["end"]) if "end" in params else None
    new_start = float(params["start"]) if "start" in params else None

    if new_end is not None and new_end > clip.loop_end:
        # Expanding right — set end first so start can move freely
        clip.loop_end = new_end
        if new_start is not None:
            clip.loop_start = new_start
    else:
        # Shrinking or only changing start — set start first
        if new_start is not None:
            clip.loop_start = new_start
        if new_end is not None:
            clip.loop_end = new_end
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


@register("set_clip_pitch")
def set_clip_pitch(song, params):
    """Set pitch/gain on an audio clip (BUG-A5).

    Audio clips only — MIDI clips raise ValueError.

    Parameters
    ----------
    track_index, clip_index : int
    coarse : int, optional        -- semitones, -48..+48
    fine   : float, optional      -- cents, -50.0..+50.0
    gain   : float, optional      -- linear normalized (0..1 in Live)

    At least one of (coarse, fine, gain) must be provided.
    """
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    clip = get_clip(song, track_index, clip_index)

    if clip.is_midi_clip:
        raise ValueError("set_clip_pitch only works on audio clips")

    coarse = params.get("coarse")
    fine = params.get("fine")
    gain = params.get("gain")

    if coarse is None and fine is None and gain is None:
        raise ValueError(
            "Provide at least one of: coarse (semitones), fine (cents), gain (0-1)"
        )

    if coarse is not None:
        c = int(coarse)
        if c < -48 or c > 48:
            raise ValueError("coarse must be in -48..+48 semitones")
        clip.pitch_coarse = c
    if fine is not None:
        f = float(fine)
        if f < -50.0 or f > 50.0:
            raise ValueError("fine must be in -50..+50 cents")
        clip.pitch_fine = f
    if gain is not None:
        g = float(gain)
        if g < 0.0 or g > 1.0:
            raise ValueError("gain must be in 0..1")
        clip.gain = g

    result = {
        "track_index": track_index,
        "clip_index": clip_index,
    }
    for attr in ("pitch_coarse", "pitch_fine", "gain"):
        try:
            result[attr] = getattr(clip, attr)
        except AttributeError:
            pass
    return result


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


@register("get_clip_scale")
def get_clip_scale(song, params):
    """Read a clip's per-clip scale override (Live 12.0+).

    Per-clip scale is independent of Song.scale_* and lets each clip
    carry its own key/mode.
    """
    from .version_detect import has_feature
    if not has_feature("song_scale_api"):
        raise RuntimeError("Per-clip scale requires Live 12.0+.")
    clip_slot = get_clip_slot(song, int(params["track_index"]), int(params["clip_index"]))
    if not clip_slot.has_clip:
        raise ValueError("Clip slot is empty")
    clip = clip_slot.clip
    return {
        "root_note": int(clip.root_note),
        "scale_mode": bool(clip.scale_mode),
        "scale_name": str(clip.scale_name),
    }


@register("set_clip_scale")
def set_clip_scale(song, params):
    """Set a clip's per-clip scale override (Live 12.0+)."""
    from .version_detect import has_feature
    if not has_feature("song_scale_api"):
        raise RuntimeError("Per-clip scale requires Live 12.0+.")
    clip_slot = get_clip_slot(song, int(params["track_index"]), int(params["clip_index"]))
    if not clip_slot.has_clip:
        raise ValueError("Clip slot is empty")
    clip = clip_slot.clip
    root = int(params["root_note"])
    if not 0 <= root <= 11:
        raise ValueError("root_note must be 0-11 (C=0, C#=1, ... B=11)")
    scale_name = str(params["scale_name"])
    # scale_name validation against Song.scale_names — clip uses the same list
    available = list(song.scale_names)
    if scale_name not in available:
        raise ValueError(
            "Unknown scale '%s'. Available: %s" % (scale_name, ", ".join(available))
        )
    clip.root_note = root
    clip.scale_name = scale_name
    return {
        "root_note": int(clip.root_note),
        "scale_name": str(clip.scale_name),
    }


@register("set_clip_scale_mode")
def set_clip_scale_mode(song, params):
    """Enable/disable Scale Mode on a single clip (Live 12.0+)."""
    from .version_detect import has_feature
    if not has_feature("song_scale_api"):
        raise RuntimeError("Per-clip scale requires Live 12.0+.")
    clip_slot = get_clip_slot(song, int(params["track_index"]), int(params["clip_index"]))
    if not clip_slot.has_clip:
        raise ValueError("Clip slot is empty")
    clip_slot.clip.scale_mode = bool(params["enabled"])
    return {"scale_mode": bool(clip_slot.clip.scale_mode)}
