"""Registry of in-process MCP tools callable from the async execution router.

These tools live as Python async functions in the MCP server — not TCP Remote
Script handlers and not M4L bridge commands. Plans that want to invoke them
go through this registry so the async router can dispatch them in-process.

Each entry is a thin wrapper around the real MCP tool import, keeping the
module cheap to import (no heavy server wiring until a caller actually
dispatches an MCP step).

To add a new in-process tool to plans:
  1. Add the tool name to MCP_TOOLS in execution_router.py so classify_step
     returns "mcp_tool" for it.
  2. Add an _adapter function here that imports the real implementation and
     adapts its kwargs from a plan-style params dict.
  3. Register the adapter in build_mcp_dispatch_registry.
"""

from __future__ import annotations

from typing import Any, Callable


async def _load_sample_to_simpler(params: dict, ctx: Any = None) -> dict:
    """Adapter for mcp_server.tools.analyzer.load_sample_to_simpler.

    Accepts the plan-step params dict and unpacks into the real tool's kwargs.
    """
    from ..tools.analyzer import load_sample_to_simpler
    return await load_sample_to_simpler(
        ctx,
        track_index=int(params["track_index"]),
        file_path=str(params["file_path"]),
        device_index=int(params.get("device_index", 0)),
    )


def build_mcp_dispatch_registry() -> dict[str, Callable]:
    """Return the canonical registry of MCP-only tools for plan execution.

    Callers (typically the server lifespan init) should call this once and
    pass the registry to execute_plan_steps_async via the mcp_registry kwarg.
    """
    return {
        "load_sample_to_simpler": _load_sample_to_simpler,
    }
