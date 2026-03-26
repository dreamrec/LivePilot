"""
LivePilot - Scene domain handlers (12 commands).
"""

from .router import register
from .utils import get_scene


@register("get_scenes_info")
def get_scenes_info(song, params):
    """Return info for all scenes."""
    scenes = []
    for i, scene in enumerate(song.scenes):
        scenes.append({
            "index": i,
            "name": scene.name,
            "tempo": scene.tempo if scene.tempo > 0 else None,
            "color_index": scene.color_index,
        })
    return {"scenes": scenes}


@register("create_scene")
def create_scene(song, params):
    """Create a new scene at the given index."""
    index = int(params.get("index", -1))
    song.create_scene(index)
    if index == -1:
        new_index = len(list(song.scenes)) - 1
    else:
        new_index = index
    scene = list(song.scenes)[new_index]
    return {
        "index": new_index,
        "name": scene.name,
        "color_index": scene.color_index,
    }


@register("delete_scene")
def delete_scene(song, params):
    """Delete a scene by index."""
    scene_index = int(params["scene_index"])
    get_scene(song, scene_index)
    song.delete_scene(scene_index)
    return {"deleted": scene_index}


@register("duplicate_scene")
def duplicate_scene(song, params):
    """Duplicate a scene by index."""
    scene_index = int(params["scene_index"])
    get_scene(song, scene_index)
    song.duplicate_scene(scene_index)
    new_index = scene_index + 1
    scene = list(song.scenes)[new_index]
    return {"index": new_index, "name": scene.name}


@register("fire_scene")
def fire_scene(song, params):
    """Fire (launch) a scene."""
    scene_index = int(params["scene_index"])
    scene = get_scene(song, scene_index)
    scene.fire()
    return {"index": scene_index, "fired": True}


@register("set_scene_name")
def set_scene_name(song, params):
    """Rename a scene."""
    scene_index = int(params["scene_index"])
    scene = get_scene(song, scene_index)
    scene.name = str(params["name"])
    return {"index": scene_index, "name": scene.name}


@register("set_scene_color")
def set_scene_color(song, params):
    """Set a scene's color."""
    scene_index = int(params["scene_index"])
    scene = get_scene(song, scene_index)
    scene.color_index = int(params["color_index"])
    return {"index": scene_index, "color_index": scene.color_index}


@register("set_scene_tempo")
def set_scene_tempo(song, params):
    """Set a scene's tempo (BPM, 20-999)."""
    scene_index = int(params["scene_index"])
    scene = get_scene(song, scene_index)
    tempo = float(params["tempo"])
    if tempo < 20 or tempo > 999:
        raise ValueError("Tempo must be between 20 and 999 BPM")
    scene.tempo = tempo
    return {
        "index": scene_index,
        "tempo": scene.tempo,
    }


# ── Scene Matrix Operations ─────────────────────────────────────────────


@register("get_scene_matrix")
def get_scene_matrix(song, params):
    """Return the full clip grid: tracks x scenes with clip states."""
    tracks = list(song.tracks)
    scenes = list(song.scenes)

    track_headers = []
    for i, t in enumerate(tracks):
        track_headers.append({"index": i, "name": t.name})

    scene_headers = []
    for i, s in enumerate(scenes):
        scene_headers.append({
            "index": i,
            "name": s.name,
            "tempo": s.tempo if s.tempo > 0 else None,
        })

    matrix = []
    for si, scene in enumerate(scenes):
        row = []
        for ti, track in enumerate(tracks):
            slots = list(track.clip_slots)
            if si >= len(slots):
                row.append({"state": "missing"})
                continue
            slot = slots[si]
            cell = {"state": "empty"}
            if slot.has_clip and slot.clip:
                clip = slot.clip
                if clip.is_recording:
                    cell["state"] = "recording"
                elif clip.is_playing:
                    cell["state"] = "playing"
                elif clip.is_triggered:
                    cell["state"] = "triggered"
                else:
                    cell["state"] = "stopped"
                cell["name"] = clip.name
                cell["color_index"] = clip.color_index
            row.append(cell)
        matrix.append(row)

    return {
        "tracks": track_headers,
        "scenes": scene_headers,
        "matrix": matrix,
    }


@register("fire_scene_clips")
def fire_scene_clips(song, params):
    """Fire a scene with optional track filter."""
    scene_index = int(params["scene_index"])
    track_indices = params.get("track_indices")

    scene = get_scene(song, scene_index)

    if track_indices is None:
        # Fire entire scene
        scene.fire()
        return {"scene_index": scene_index, "fired": "all"}

    # Fire specific tracks only
    tracks = list(song.tracks)
    fired = []
    for ti in track_indices:
        ti = int(ti)
        if ti < 0 or ti >= len(tracks):
            raise IndexError("Track index %d out of range (0..%d)" % (ti, len(tracks) - 1))
        slots = list(tracks[ti].clip_slots)
        if scene_index < len(slots):
            slots[scene_index].fire()
            fired.append(ti)

    return {"scene_index": scene_index, "fired_tracks": fired}


@register("stop_all_clips")
def stop_all_clips(song, params):
    """Stop all playing clips in the session."""
    song.stop_all_clips()
    return {"stopped": True}


@register("get_playing_clips")
def get_playing_clips(song, params):
    """Return all currently playing or triggered clips."""
    tracks = list(song.tracks)
    clips = []
    for ti, track in enumerate(tracks):
        for si, slot in enumerate(track.clip_slots):
            if slot.has_clip and slot.clip:
                clip = slot.clip
                if clip.is_playing or clip.is_triggered:
                    clips.append({
                        "track_index": ti,
                        "track_name": track.name,
                        "clip_index": si,
                        "clip_name": clip.name,
                        "is_playing": clip.is_playing,
                        "is_triggered": clip.is_triggered,
                    })
    return {"clips": clips}
