"""Scene MCP tools — list, create, delete, duplicate, fire, rename, color, tempo.

8 tools matching the Remote Script scenes domain.
"""

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_scene_index(scene_index: int):
    if scene_index < 0:
        raise ValueError("scene_index must be >= 0")


@mcp.tool()
def get_scenes_info(ctx: Context) -> dict:
    """Get info for all scenes: name, tempo, color."""
    return _get_ableton(ctx).send_command("get_scenes_info")


@mcp.tool()
def create_scene(ctx: Context, index: int = -1) -> dict:
    """Create a new scene. index=-1 appends at end."""
    return _get_ableton(ctx).send_command("create_scene", {"index": index})


@mcp.tool()
def delete_scene(ctx: Context, scene_index: int) -> dict:
    """Delete a scene by index. Use undo to revert if needed."""
    _validate_scene_index(scene_index)
    return _get_ableton(ctx).send_command("delete_scene", {"scene_index": scene_index})


@mcp.tool()
def duplicate_scene(ctx: Context, scene_index: int) -> dict:
    """Duplicate a scene (copies all clip slots)."""
    _validate_scene_index(scene_index)
    return _get_ableton(ctx).send_command("duplicate_scene", {"scene_index": scene_index})


@mcp.tool()
def fire_scene(ctx: Context, scene_index: int) -> dict:
    """Fire (launch) a scene, triggering all its clips."""
    _validate_scene_index(scene_index)
    return _get_ableton(ctx).send_command("fire_scene", {"scene_index": scene_index})


@mcp.tool()
def set_scene_name(ctx: Context, scene_index: int, name: str) -> dict:
    """Rename a scene. Pass empty string to clear the name."""
    _validate_scene_index(scene_index)
    return _get_ableton(ctx).send_command("set_scene_name", {
        "scene_index": scene_index,
        "name": name,
    })


def _validate_color_index(color_index: int):
    if not 0 <= color_index <= 69:
        raise ValueError("color_index must be between 0 and 69")


@mcp.tool()
def set_scene_color(ctx: Context, scene_index: int, color_index: int) -> dict:
    """Set scene color (0-69, Ableton's color palette)."""
    _validate_scene_index(scene_index)
    _validate_color_index(color_index)
    return _get_ableton(ctx).send_command("set_scene_color", {
        "scene_index": scene_index,
        "color_index": color_index,
    })


@mcp.tool()
def set_scene_tempo(ctx: Context, scene_index: int, tempo: float) -> dict:
    """Set scene tempo in BPM (20-999). Fires when the scene launches."""
    _validate_scene_index(scene_index)
    if tempo < 20 or tempo > 999:
        raise ValueError("Tempo must be between 20.0 and 999.0 BPM")
    return _get_ableton(ctx).send_command("set_scene_tempo", {
        "scene_index": scene_index,
        "tempo": tempo,
    })
