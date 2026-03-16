"""
LivePilot - Scene domain handlers (6 commands).
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
