"""Diagnostic MCP tools — read-only inspection of the Live environment.

Currently exposes ControlSurface enumeration. Other session-health
diagnostics (``get_session_diagnostics``, ``get_recent_actions``) live in
``transport.py`` for historical reasons — this module is specifically for
inspection utilities that reach outside Song (into Application /
ControlSurface / Preferences / etc.).
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def list_control_surfaces(ctx: Context) -> dict:
    """List all active ControlSurface instances (Push, APC, Launchkey, etc.).

    Returns {surfaces: [{index, name, class_name}]}. Read-only diagnostic —
    mirrors Live.Application.get_application().control_surfaces. Use the
    index with get_control_surface_info() for per-surface detail.
    """
    return _get_ableton(ctx).send_command("list_control_surfaces", {})


@mcp.tool()
def get_control_surface_info(ctx: Context, index: int) -> dict:
    """Read detailed info about a single control surface.

    index: 0-based position in list_control_surfaces() results.
    Returns {index, name, class_name, component_count}. Component count
    falls back to 0 when the surface doesn't expose a .components iterable.
    """
    return _get_ableton(ctx).send_command("get_control_surface_info",
                                          {"index": index})


@mcp.tool()
def reload_handlers(ctx: Context) -> dict:
    """Reload every Remote Script handler module in Ableton — dev-loop helper.

    Client-side wrapper for the `reload_handlers` TCP command exposed by the
    Remote Script (see `remote_script/LivePilot/__init__.py`). Re-discovers
    handler submodules via pkgutil.iter_modules and reloads each one,
    re-firing @register decorators against a freshly-cleared router. Lets
    you edit a handler file → run installer → call this tool, without a
    Control Surface toggle or Ableton restart.

    Does NOT reload `router`, `server`, or `__init__.py` — Ableton's
    embedded Python handles only leaf-submodule reloads correctly.

    Returns {reloaded: True, handler_count: int} so callers can assert the
    post-reload registration surface. Raises if the Remote Script is
    pre-PR#16 (will surface as `[NOT_FOUND] Unknown command type`).
    """
    return _get_ableton(ctx).send_command("reload_handlers", {})
