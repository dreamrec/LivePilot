"""Browser MCP tools — browse, search, and load instruments/effects.

4 tools matching the Remote Script browser domain.
"""

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_track_index(track_index: int):
    if track_index < 0:
        raise ValueError("track_index must be >= 0")


@mcp.tool()
def get_browser_tree(ctx: Context, category_type: str = "all") -> dict:
    """Get an overview of browser categories and their children."""
    return _get_ableton(ctx).send_command("get_browser_tree", {
        "category_type": category_type,
    })


@mcp.tool()
def get_browser_items(ctx: Context, path: str) -> dict:
    """List items at a browser path (e.g., 'instruments/Analog')."""
    if not path.strip():
        raise ValueError("Path cannot be empty")
    return _get_ableton(ctx).send_command("get_browser_items", {"path": path})


@mcp.tool()
def search_browser(
    ctx: Context,
    path: str,
    name_filter: str | None = None,
    loadable_only: bool = False,
) -> dict:
    """Search the browser tree under a path, optionally filtering by name."""
    if not path.strip():
        raise ValueError("Path cannot be empty")
    params = {"path": path}
    if name_filter is not None:
        params["name_filter"] = name_filter
    if loadable_only:
        params["loadable_only"] = loadable_only
    return _get_ableton(ctx).send_command("search_browser", params)


@mcp.tool()
def load_browser_item(ctx: Context, track_index: int, uri: str) -> dict:
    """Load a browser item (instrument/effect) onto a track by URI."""
    _validate_track_index(track_index)
    if not uri.strip():
        raise ValueError("URI cannot be empty")
    return _get_ableton(ctx).send_command("load_browser_item", {
        "track_index": track_index,
        "uri": uri,
    })
