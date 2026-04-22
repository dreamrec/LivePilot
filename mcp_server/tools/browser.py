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
    """Validate track index.

    0+ for regular tracks, -1/-2/... for return tracks (A/B/...),
    -1000 for master track.
    """
    if track_index < 0 and track_index != -1000 and track_index < -20:
        raise ValueError(
            "track_index must be >= 0 for regular tracks, "
            "-1/-2/... for return tracks, or -1000 for master"
        )


@mcp.tool()
def get_browser_tree(ctx: Context, category_type: str = "all") -> dict:
    """Get an overview of browser categories and their children."""
    return _get_ableton(ctx).send_command("get_browser_tree", {
        "category_type": category_type,
    })


@mcp.tool()
def get_browser_items(
    ctx: Context,
    path: str,
    limit: int = 500,
    offset: int = 0,
    filter_pattern: Optional[str] = None,
) -> dict:
    """List items at a browser path (e.g., 'instruments/Analog').

    BUG-2026-04-22#5 fix — the /drums folder returned 68KB+ of JSON on
    single calls, blowing past tool token caps. These params give agents
    a way to page and filter natively without dumping to temp files.

    path:            browser path (e.g., 'drums', 'samples/Packs/Foo')
    limit:           maximum items returned (default 500, max 5000)
    offset:          number of items to skip (default 0)
    filter_pattern:  case-insensitive substring to filter item names by
                     (applied server-side when possible, client-side fallback)
    """
    if not path.strip():
        raise ValueError("Path cannot be empty")
    if limit < 1:
        raise ValueError("limit must be >= 1")
    limit = min(limit, 5000)
    if offset < 0:
        raise ValueError("offset must be >= 0")
    params: dict = {
        "path": path,
        "limit": limit,
        "offset": offset,
    }
    if filter_pattern:
        params["filter_pattern"] = filter_pattern
    result = _get_ableton(ctx).send_command("get_browser_items", params)

    # Client-side fallback: if the remote script's handler doesn't know about
    # limit/offset/filter_pattern yet (older remote-script build), apply the
    # paging + filter here so the MCP contract still works. Returned payload
    # keeps `truncated`/`total_before_filter` for observability.
    if isinstance(result, dict) and "items" in result:
        items = result.get("items") or []
        total_before = len(items)
        if filter_pattern:
            needle = filter_pattern.lower()
            items = [i for i in items if needle in str(i.get("name", "")).lower()]
        total_filtered = len(items)
        paged = items[offset : offset + limit]
        result["items"] = paged
        result["total_before_filter"] = total_before
        result["total_after_filter"] = total_filtered
        result["returned"] = len(paged)
        result["offset"] = offset
        result["limit"] = limit
        result["truncated"] = (offset + limit) < total_filtered
    return result


@mcp.tool()
def search_browser(
    ctx: Context,
    path: str,
    name_filter: Optional[str] = None,
    loadable_only: bool = False,
    max_depth: int = 8,
    max_results: int = 100,
    query: Optional[str] = None,
) -> dict:
    """Search the browser tree under a path, optionally filtering by name.

    BUG-2026-04-22#4 fix — `query` is now accepted as an alias for
    `name_filter`, aligning this tool's schema with `search_samples`.
    Callers passing either keyword work.

    path:         top-level category to search under. Valid categories:
                  instruments, audio_effects, midi_effects, sounds, drums,
                  samples, packs, user_library, plugins, max_for_live, clips
    name_filter:  case-insensitive substring filter on item name
    query:        alias for name_filter (accepts either)
    max_depth:    how deep to recurse into subfolders (default 8)
    max_results:  maximum number of results to return (default 100)
    """
    if not path.strip():
        raise ValueError("Path cannot be empty")
    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    if max_results < 1:
        raise ValueError("max_results must be >= 1")
    effective_filter = name_filter if name_filter is not None else query
    params: dict = {"path": path}
    if effective_filter is not None:
        params["name_filter"] = effective_filter
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
