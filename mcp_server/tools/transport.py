"""Transport MCP tools — playback, tempo, metronome, loop, undo/redo, action log.

11 tools matching the Remote Script transport domain.
"""

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def get_session_info(ctx: Context) -> dict:
    """Get comprehensive Ableton session state: tempo, tracks, scenes, transport."""
    return _get_ableton(ctx).send_command("get_session_info")


@mcp.tool()
def set_tempo(ctx: Context, tempo: float) -> dict:
    """Set the song tempo in BPM (20-999)."""
    if not 20 <= tempo <= 999:
        raise ValueError("Tempo must be between 20 and 999 BPM")
    return _get_ableton(ctx).send_command("set_tempo", {"tempo": tempo})


@mcp.tool()
def set_time_signature(ctx: Context, numerator: int, denominator: int) -> dict:
    """Set the time signature (e.g., 4/4, 3/4, 6/8)."""
    if numerator < 1 or numerator > 99:
        raise ValueError("Numerator must be between 1 and 99")
    if denominator not in (1, 2, 4, 8, 16):
        raise ValueError("Denominator must be 1, 2, 4, 8, or 16")
    return _get_ableton(ctx).send_command("set_time_signature", {
        "numerator": numerator,
        "denominator": denominator,
    })


@mcp.tool()
def start_playback(ctx: Context) -> dict:
    """Start playback from the beginning."""
    return _get_ableton(ctx).send_command("start_playback")


@mcp.tool()
def stop_playback(ctx: Context) -> dict:
    """Stop playback."""
    return _get_ableton(ctx).send_command("stop_playback")


@mcp.tool()
def continue_playback(ctx: Context) -> dict:
    """Continue playback from the current position."""
    return _get_ableton(ctx).send_command("continue_playback")


@mcp.tool()
def toggle_metronome(ctx: Context, enabled: bool) -> dict:
    """Enable or disable the metronome click."""
    return _get_ableton(ctx).send_command("toggle_metronome", {"enabled": enabled})


@mcp.tool()
def set_session_loop(
    ctx: Context,
    enabled: bool,
    start: float | None = None,
    length: float | None = None,
) -> dict:
    """Set loop on/off and optional loop region (start beat, length in beats)."""
    params = {"enabled": enabled}
    if start is not None:
        if start < 0:
            raise ValueError("Loop start must be >= 0")
        params["loop_start"] = start
    if length is not None:
        if length <= 0:
            raise ValueError("Loop length must be > 0")
        params["loop_length"] = length
    return _get_ableton(ctx).send_command("set_session_loop", params)


@mcp.tool()
def undo(ctx: Context) -> dict:
    """Undo the last action in Ableton."""
    return _get_ableton(ctx).send_command("undo")


@mcp.tool()
def redo(ctx: Context) -> dict:
    """Redo the last undone action in Ableton."""
    return _get_ableton(ctx).send_command("redo")


@mcp.tool()
def get_recent_actions(ctx: Context, limit: int = 20) -> dict:
    """Get a log of recent commands sent to Ableton (newest first). Useful for reviewing what was changed."""
    if limit < 1:
        limit = 1
    elif limit > 50:
        limit = 50
    entries = _get_ableton(ctx).get_recent_commands(limit)
    return {"actions": entries, "count": len(entries)}
