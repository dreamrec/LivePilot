"""
LivePilot - Transport domain handlers (19 commands).
"""

from .router import register
from .version_detect import version_string, get_api_features


@register("get_session_info")
def get_session_info(song, params):
        """Return comprehensive session state."""
        tracks_info = []
        for i, track in enumerate(song.tracks):
                    track_data = {
                                    "index": i,
                                    "name": track.name,
                                    "color_index": track.color_index,
                                    "mute": track.mute,
                                    "solo": track.solo,
                    }
                    try:
                                    track_data["arm"] = track.arm
                                    track_data["has_midi_input"] = track.has_midi_input
                                    track_data["has_audio_input"] = track.has_audio_input
except Exception:
            track_data["arm"] = None
            track_data["has_midi_input"] = None
            track_data["has_audio_input"] = None
        tracks_info.append(track_data)

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
                "track_count": len(tracks_info),
                "return_track_count": len(return_tracks_info),
                "scene_count": len(scenes_info),
                "tracks": tracks_info,
                "return_tracks": return_tracks_info,
                "scenes": scenes_info,
                "live_version": version_string(),
                "api_features": get_api_features(),
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
                    enabled = bool(params["enabled"])
    song.loop = enabled
    # Echo requested value — song.loop getter may return stale state
    return {
                "loop": enabled,
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


# ── Song / Transport long-tail primitives ─────────────────────────────────────


@register("tap_tempo")
def tap_tempo(song, params):
        """Tap the tempo (one tap); Live averages consecutive taps."""
        song.tap_tempo()
        return {"tempo": float(song.tempo)}


@register("nudge_tempo")
def nudge_tempo(song, params):
        """Nudge tempo up or down by Live's internal nudge delta."""
        direction = str(params["direction"]).lower()
        if direction == "up":
                    song.nudge_up()
elif direction == "down":
        song.nudge_down()
else:
        raise ValueError("direction must be 'up' or 'down'")
        return {"tempo": float(song.tempo)}


@register("set_exclusive_arm")
def set_exclusive_arm(song, params):
        """Enable/disable exclusive arm (only one track armed at a time)."""
        song.exclusive_arm = bool(params["enabled"])
        return {"exclusive_arm": bool(song.exclusive_arm)}


@register("set_exclusive_solo")
def set_exclusive_solo(song, params):
        """Enable/disable exclusive solo mode."""
        song.exclusive_solo = bool(params["enabled"])
        return {"exclusive_solo": bool(song.exclusive_solo)}


@register("capture_and_insert_scene")
def capture_and_insert_scene(song, params):
        """Capture currently-playing clips and insert them as a new scene."""
        before_count = len(list(song.scenes))
        song.capture_and_insert_scene()
        scenes = list(song.scenes)
        new_idx = len(scenes) - 1
        # capture_and_insert_scene inserts at a specific position — find the new one.
        # Safest: if count grew by 1, the new scene is at the end; otherwise return -1.
    if len(scenes) > before_count:
                return {"scene_index": new_idx, "scene_name": str(scenes[new_idx].name)}
            return {"scene_index": -1, "scene_name": ""}


@register("set_count_in_duration")
def set_count_in_duration(song, params):
        """Set pre-record count-in (0-4 bars)."""
        bars = int(params["bars"])
        if not 0 <= bars <= 4:
                    raise ValueError("bars must be 0-4")
                song.count_in_duration = bars
    return {"count_in_duration": int(song.count_in_duration)}


@register("get_link_state")
def get_link_state(song, params):
        """Read Ableton Link + count-in state."""
    return {
                "enabled": bool(getattr(song, "is_ableton_link_enabled", False)),
                "start_stop_sync": bool(getattr(song, "is_ableton_link_start_stop_sync_enabled", False)),
                "tempo_follower": bool(getattr(song, "tempo_follower_enabled", False)),
                "is_counting_in": bool(getattr(song, "is_counting_in", False)),
    }


@register("set_link_enabled")
def set_link_enabled(song, params):
        """Enable or disable Ableton Link."""
    song.is_ableton_link_enabled = bool(params["enabled"])
    return {"enabled": bool(song.is_ableton_link_enabled)}


@register("force_link_beat_time")
def force_link_beat_time(song, params):
        """Force Link to a specific beat time (if supported)."""
    if not hasattr(song, "force_link_beat_time"):
                raise RuntimeError("force_link_beat_time is not exposed in this Live version.")
            beat_time = float(params["beat_time"])
    song.force_link_beat_time(beat_time)
    return {"ok": True, "beat_time": beat_time}
