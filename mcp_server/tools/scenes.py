"""Scene MCP tools — list, create, delete, duplicate, fire, rename.

6 tools matching the Remote Script scenes domain.
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
    """Rename a scene."""
    _validate_scene_index(scene_index)
    if not name.strip():
        raise ValueError("Scene name cannot be empty")
    return _get_ableton(ctx).send_command("set_scene_name", {
        "scene_index": scene_index,
        "name": name,
    })
