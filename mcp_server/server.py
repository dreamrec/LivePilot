"""FastMCP entry point for LivePilot."""

from contextlib import asynccontextmanager
import asyncio

from fastmcp import FastMCP, Context  # noqa: F401

from .connection import AbletonConnection
from .m4l_bridge import SpectralCache, SpectralReceiver, M4LBridge


@asynccontextmanager
async def lifespan(server):
    """Create and yield the shared AbletonConnection + M4L bridge."""
    ableton = AbletonConnection()
    spectral = SpectralCache()
    receiver = SpectralReceiver(spectral)
    m4l = M4LBridge(spectral, receiver)

    # Start UDP listener for incoming M4L spectral data (port 9880)
    loop = asyncio.get_running_loop()
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: receiver,
            local_addr=('127.0.0.1', 9880),
        )
    except OSError:
        # Port in use — M4L bridge won't work but core tools still function
        transport = None

    try:
        yield {
            "ableton": ableton,
            "spectral": spectral,
            "m4l": m4l,
        }
    finally:
        if transport:
            transport.close()
        m4l.close()
        ableton.disconnect()


mcp = FastMCP("LivePilot", lifespan=lifespan)

# Import tool modules so they register with `mcp`
from .tools import transport    # noqa: F401, E402
from .tools import tracks       # noqa: F401, E402
from .tools import clips        # noqa: F401, E402
from .tools import notes        # noqa: F401, E402
from .tools import devices      # noqa: F401, E402
from .tools import scenes       # noqa: F401, E402
from .tools import mixing       # noqa: F401, E402
from .tools import browser      # noqa: F401, E402
from .tools import arrangement  # noqa: F401, E402
from .tools import memory       # noqa: F401, E402
from .tools import analyzer     # noqa: F401, E402
from .tools import automation   # noqa: F401, E402
from .tools import theory       # noqa: F401, E402
from .tools import generative   # noqa: F401, E402
from .tools import harmony      # noqa: F401, E402
from .tools import midi_io      # noqa: F401, E402
from .tools import perception   # noqa: F401, E402


# ---------------------------------------------------------------------------
# Schema coercion patch — accept strings for numeric parameters
# ---------------------------------------------------------------------------
# Some MCP clients (with deferred tools) send all parameter
# values as strings.  Their client-side Zod validators reject "0" against
# {"type": "integer"} before the request even reaches our server.
#
# Fix: widen every integer/number property in the advertised JSON Schema to
# also accept strings.  Server-side Pydantic validation (lax mode) coerces
# "5" → 5 and "0.75" → 0.75 automatically, so no tool code changes needed.
# ---------------------------------------------------------------------------

def _coerce_schema_property(prop: dict) -> None:
    """Widen a single JSON Schema property to also accept strings."""
    if prop.get("type") in ("integer", "number"):
        original_type = prop.pop("type")
        prop["anyOf"] = [{"type": original_type}, {"type": "string"}]
    elif "anyOf" in prop:
        for variant in prop["anyOf"]:
            _coerce_schema_property(variant)


def _get_all_tools():
    """Get all registered tools, compatible with FastMCP 0.x and 3.x."""
    # FastMCP 0.x: mcp._tool_manager._tools (dict of name -> Tool)
    if hasattr(mcp, "_tool_manager"):
        return list(mcp._tool_manager._tools.values())
    # FastMCP 3.x: mcp._local_provider._components (dict of key -> Tool)
    if hasattr(mcp, "_local_provider") and hasattr(mcp._local_provider, "_components"):
        return list(mcp._local_provider._components.values())
    return []


def _patch_tool_schemas() -> None:
    """Post-process all registered tool schemas for string coercion."""
    for tool in _get_all_tools():
        props = tool.parameters.get("properties", {})
        for name, prop in props.items():
            if name == "ctx":
                continue  # skip the Context parameter
            _coerce_schema_property(prop)


_patch_tool_schemas()


def main():
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
