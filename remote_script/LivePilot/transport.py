"""
LivePilot - Transport domain handlers (10 commands).
"""

from .router import register


@register("get_session_info")
def get_session_info(song, params):
    """Return comprehensive session state."""
    tracks_info = []
    for i, track in enumerate(song.tracks):
        tracks_info.append({
            "index": i,
            "name": track.name,
            "color_index": track.color_index,
            "has_midi_input": track.has_midi_input,
            "has_audio_input": track.has_audio_input,
            "mute": track.mute,
            "solo": track.solo,
            "arm": track.arm,
        })

    return_tracks_info = []
    for i, track in enumerate(song.return_tracks):
        return_tracks_info.append({
            "index": i,
            "name": track.name,
            "color_index": track.color_index,
            "mute": track.mute,
            "solo": track.solo,
        })

    scenes_info = []
    for i, scene in enumerate(song.scenes):
        scenes_info.append({
            "index": i,
            "name": scene.name,
            "color_index": scene.color_index,
            "tempo": scene.tempo if scene.tempo > 0 else None,
        })

    return {
        "tempo": song.tempo,
        "signature_numerator": song.signature_numerator,
        "signature_denominator": song.signature_denominator,
        "is_playing": song.is_playing,
        "song_length": song.song_length,
        "current_song_time": song.current_song_time,
        "loop": song.loop,
        "loop_start": song.loop_start,
        "loop_length": song.loop_length,
        "metronome": song.metronome,
        "record_mode": song.record_mode,
        "session_record": song.session_record,
        "track_count": len(list(song.tracks)),
        "return_track_count": len(list(song.return_tracks)),
        "scene_count": len(list(song.scenes)),
        "tracks": tracks_info,
        "return_tracks": return_tracks_info,
        "scenes": scenes_info,
    }


@register("set_tempo")
def set_tempo(song, params):
    """Set the song tempo in BPM."""
    tempo = float(params["tempo"])
    if tempo < 20 or tempo > 999:
        raise ValueError("Tempo must be between 20 and 999 BPM")
    song.tempo = tempo
    return {"tempo": song.tempo}


@register("set_time_signature")
def set_time_signature(song, params):
    """Set the song time signature."""
    numerator = int(params["numerator"])
    denominator = int(params["denominator"])
    if numerator < 1 or numerator > 99:
        raise ValueError("Numerator must be between 1 and 99")
    if denominator not in (1, 2, 4, 8, 16):
        raise ValueError("Denominator must be 1, 2, 4, 8, or 16")
    song.signature_numerator = numerator
    song.signature_denominator = denominator
    return {
        "signature_numerator": song.signature_numerator,
        "signature_denominator": song.signature_denominator,
    }


@register("start_playback")
def start_playback(song, params):
    """Start playback from the beginning."""
    song.start_playing()
    return {"is_playing": True}


@register("stop_playback")
def stop_playback(song, params):
    """Stop playback."""
    song.stop_playing()
    return {"is_playing": False}


@register("continue_playback")
def continue_playback(song, params):
    """Continue playback from the current position."""
    song.continue_playing()
    return {"is_playing": True}


@register("toggle_metronome")
def toggle_metronome(song, params):
    """Enable or disable the metronome."""
    enabled = bool(params["enabled"])
    song.metronome = enabled
    return {"metronome": song.metronome}


@register("set_session_loop")
def set_session_loop(song, params):
    """Enable/disable loop and optionally set loop start/length."""
    # Set region FIRST — setting loop_start/loop_length can reset song.loop
    if "loop_start" in params:
        song.loop_start = float(params["loop_start"])
    if "loop_length" in params:
        song.loop_length = float(params["loop_length"])
    # Set enabled LAST so it sticks
    song.loop = bool(params["enabled"])
    return {
        "loop": song.loop,
        "loop_start": song.loop_start,
        "loop_length": song.loop_length,
    }


@register("undo")
def undo(song, params):
    """Undo the last action."""
    song.undo()
    return {"undone": True}


@register("redo")
def redo(song, params):
    """Redo the last undone action."""
    song.redo()
    return {"redone": True}
