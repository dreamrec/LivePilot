"""Browser MCP tools — browse, search, and load instruments/effects.

4 tools matching the Remote Script browser domain.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_track_index(track_index: int):
    """Validate track index. Supports 0+ for regular tracks,
    negative for return tracks (-1=A, -2=B), -1000 for master."""
    pass  # Remote script's get_track() handles all validation


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
    name_filter: Optional[str] = None,
    loadable_only: bool = False,
    max_depth: int = 8,
    max_results: int = 100,
) -> dict:
    """Search the browser tree under a path, optionally filtering by name.

    path:        top-level category to search under. Valid categories:
                 instruments, audio_effects, midi_effects, sounds, drums,
                 samples, packs, user_library, plugins, max_for_live, clips
    max_depth:   how deep to recurse into subfolders (default 8)
    max_results: maximum number of results to return (default 100)
    """
    if not path.strip():
        raise ValueError("Path cannot be empty")
    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    if max_results < 1:
        raise ValueError("max_results must be >= 1")
    params: dict = {"path": path}
    if name_filter is not None:
        params["name_filter"] = name_filter
    if loadable_only:
        params["loadable_only"] = loadable_only
    if max_depth != 8:
        params["max_depth"] = max_depth
    if max_results != 100:
        params["max_results"] = max_results
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
