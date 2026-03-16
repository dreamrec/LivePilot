"""FastMCP entry point for LivePilot."""

from contextlib import asynccontextmanager

from fastmcp import FastMCP, Context  # noqa: F401

from .connection import AbletonConnection


@asynccontextmanager
async def lifespan(server):
    """Create and yield the shared AbletonConnection for all tools."""
    ableton = AbletonConnection()
    try:
        yield {"ableton": ableton}
    finally:
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


def main():
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
