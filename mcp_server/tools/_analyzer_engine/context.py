"""Analyzer lifespan-context accessors + health check.

These were inline in ``analyzer.py`` pre-v1.10.9. Split out as part of
BUG-C1 so the tool file contains only ``@mcp.tool()`` definitions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastmcp import Context

if TYPE_CHECKING:  # pragma: no cover — type-only imports
    from ...m4l_bridge import M4LBridge, SpectralCache

logger = logging.getLogger(__name__)


def _get_spectral(ctx: Context):
    """Get the SpectralCache from the lifespan context.

    Attaches the active FastMCP ``Context`` to the cache so the analyzer
    error path can distinguish "device missing" from "bridge disconnected"
    — needed for the actionable error messages in ``_require_analyzer``.
    """
    cache = ctx.lifespan_context.get("spectral")
    if not cache:
        raise ValueError("Spectral cache not initialized — restart the MCP server")
    setattr(cache, "_livepilot_ctx", ctx)
    return cache


def _get_m4l(ctx: Context):
    """Get the M4LBridge from the lifespan context."""
    bridge = ctx.lifespan_context.get("m4l")
    if not bridge:
        raise ValueError("M4L bridge not initialized — restart the MCP server")
    return bridge


def _require_analyzer(cache) -> None:
    """Raise a user-actionable error if the analyzer device isn't reachable.

    The error text is the most user-visible surface of the analyzer layer,
    so it spends effort distinguishing:

      * "not loaded on master" → concrete drag-and-drop instructions
      * "loaded but UDP port 9880 held by another instance" → show the
        PID/command of the holder so the user can close it
      * "loaded but bridge disconnected for some other reason" → generic
        reload/restart hint

    The ``_livepilot_ctx`` attribute attached by ``_get_spectral`` is what
    lets us probe the master-track devices here; without it, the caller
    would have to pass ``ctx`` through every ``_require_analyzer`` site.
    """
    if cache.is_connected:
        return

    # Imported lazily to avoid a circular import: server.py imports this
    # package's parent during tool registration.
    from ...server import _identify_port_holder

    ctx = getattr(cache, "_livepilot_ctx", None)
    try:
        track = (
            ctx.lifespan_context["ableton"].send_command("get_master_track")
            if ctx else {}
        )
    except Exception as exc:
        logger.debug("_require_analyzer failed: %s", exc)
        track = {}

    devices = track.get("devices", []) if isinstance(track, dict) else []
    analyzer_loaded = False
    for device in devices:
        normalized = " ".join(
            str(device.get("name") or "").replace("_", " ").replace("-", " ").lower().split()
        )
        if normalized == "livepilot analyzer":
            analyzer_loaded = True
            break

    if analyzer_loaded:
        holder = _identify_port_holder(9880)
        detail = (
            "LivePilot Analyzer is loaded on the master track, but its UDP bridge is not connected. "
        )
        if holder:
            detail += (
                "UDP port 9880 is currently held by another LivePilot instance "
                f"({holder}). Close the other client/server, then call the "
                "reconnect_bridge tool (safe no-op when already connected)."
            )
        else:
            detail += (
                "Call the reconnect_bridge tool first (the port may have been "
                "busy at server startup); if that fails, reload the analyzer "
                "device or restart the MCP server."
            )
        raise ValueError(detail)

    raise ValueError(
        "LivePilot Analyzer not detected. "
        "Drag 'LivePilot Analyzer' onto the master track from "
        "Audio Effects > Max Audio Effect."
    )


async def _require_analyzer_async(cache) -> None:
    """``async def`` form of :func:`_require_analyzer`.

    Same guard, same error text — but safe to call from an async tool handler.

    Why this exists: ``_require_analyzer``'s *diagnostic* path is expensive. To
    tell "not loaded" from "loaded but port held" it does a synchronous TCP
    round-trip (``get_master_track``) and a ``subprocess`` port-holder probe.
    Called bare from an ``async def``, both run on the event loop and freeze
    every other in-flight MCP request — and they fire exactly when the session
    is already unhealthy and the user is most likely retrying. (Found by the
    2026-07-31 review; 24 analyzer tools were affected.)

    The connected fast path returns WITHOUT a thread hop. That is the
    overwhelmingly common case, and these guards sit at the top of ~24 hot
    tools that run in tight evaluation loops, so paying a threadpool
    round-trip per call to re-check an in-memory flag would be pure waste.
    ``cache.is_connected`` is a timestamp comparison under a briefly-held
    lock — it never touches I/O.
    """
    if cache.is_connected:
        return
    await asyncio.to_thread(_require_analyzer, cache)
