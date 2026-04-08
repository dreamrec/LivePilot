"""MCP tool wrappers for runtime capability state.

Tools:
  get_capability_state — probe session + analyzer + memory, return snapshot
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from .capability_state import build_capability_state


@mcp.tool()
def get_capability_state(ctx: Context) -> dict:
    """Probe the runtime and return a capability state snapshot.

    Checks session connectivity, analyzer freshness, memory availability,
    and reports what modes the system can operate in right now.
    """
    ableton = ctx.lifespan_context["ableton"]
    spectral = ctx.lifespan_context.get("spectral")

    # ── Probe session ───────────────────────────────────────────────
    session_ok = False
    try:
        result = ableton.send_command("get_session_info")
        session_ok = isinstance(result, dict) and "error" not in result
    except Exception:
        session_ok = False

    # ── Probe analyzer (M4L bridge) ─────────────────────────────────
    analyzer_ok = False
    analyzer_fresh = False
    if spectral is not None:
        analyzer_ok = spectral.is_connected
        if analyzer_ok:
            # Check if we have recent spectrum data
            snap = spectral.get("spectrum")
            analyzer_fresh = snap is not None

    # ── Probe memory ────────────────────────────────────────────────
    memory_ok = False
    try:
        mem_result = ableton.send_command("memory_list", {"type": "technique"})
        memory_ok = isinstance(mem_result, dict) and "error" not in mem_result
    except Exception:
        memory_ok = False

    # ── Web / FluCoMa — not probed live, default to False ───────────
    web_ok = False
    flucoma_ok = False

    state = build_capability_state(
        session_ok=session_ok,
        analyzer_ok=analyzer_ok,
        analyzer_fresh=analyzer_fresh,
        memory_ok=memory_ok,
        web_ok=web_ok,
        flucoma_ok=flucoma_ok,
    )

    return state.to_dict()
