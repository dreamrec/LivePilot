"""
LivePilot - Arrangement domain handlers (8 commands).
"""

from .router import register
from .utils import get_track


@register("get_arrangement_clips")
def get_arrangement_clips(song, params):
    """Return all arrangement clips on a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    clips = []
    for clip in track.arrangement_clips:
        clips.append({
            "name": clip.name,
            "start_time": clip.start_time,
            "end_time": clip.start_time + clip.length,
            "length": clip.length,
            "color_index": clip.color_index,
            "is_audio_clip": clip.is_audio_clip,
        })
    return {"track_index": track_index, "clips": clips}


@register("jump_to_time")
def jump_to_time(song, params):
    """Jump to a specific beat time in the arrangement."""
    beat_time = float(params["beat_time"])
    if beat_time < 0:
        raise ValueError("beat_time must be >= 0")
    song.current_song_time = beat_time
    return {"current_song_time": song.current_song_time}


@register("capture_midi")
def capture_midi(song, params):
    """Capture recently played MIDI notes into a clip."""
    song.capture_midi()
    return {"captured": True}


@register("start_recording")
def start_recording(song, params):
    """Start recording in session or arrangement mode."""
    arrangement = bool(params.get("arrangement", False))
    if arrangement:
        song.record_mode = True
    else:
        song.session_record = True
    return {
        "record_mode": song.record_mode,
        "session_record": song.session_record,
    }


@register("stop_recording")
def stop_recording(song, params):
    """Stop all recording."""
    song.record_mode = False
    song.session_record = False
    return {"record_mode": False, "session_record": False}


@register("get_cue_points")
def get_cue_points(song, params):
    """Return all cue points in the arrangement."""
    cue_points = list(song.cue_points)
    result = []
    for i, cue in enumerate(cue_points):
        result.append({
            "index": i,
            "name": cue.name,
            "time": cue.time,
        })
    return {"cue_points": result}


@register("jump_to_cue")
def jump_to_cue(song, params):
    """Jump to a cue point by index."""
    cue_index = int(params["cue_index"])
    cue_points = list(song.cue_points)
    if cue_index < 0 or cue_index >= len(cue_points):
        raise IndexError(
            "Cue point index %d out of range (0..%d)"
            % (cue_index, len(cue_points) - 1)
        )
    cue_points[cue_index].jump()
    return {"cue_index": cue_index, "jumped": True}


@register("toggle_cue_point")
def toggle_cue_point(song, params):
    """Set or delete a cue point at the current position."""
    song.set_or_delete_cue()
    return {"toggled": True}
