"""Song-level scale tools (Live 12.0+ Scale Mode).

4 tools matching the Remote Script scales domain.
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def get_song_scale(ctx: Context) -> dict:
    """Read Live's current Scale Mode state (Live 12.0+).

    Returns:
        root_note:          0-11 (C=0, C#=1, ... B=11)
        scale_mode:         bool — is Scale Mode currently enabled
        scale_name:         e.g. "Major", "Minor Pentatonic", "Dorian"
        scale_intervals:    tuple of semitone offsets from root_note
        available_scales:   all scale names Live knows about

    Prefer this over our own `identify_scale` detector when you want
    the user's actual Live selection rather than an audio-detected key.
    """
    return _get_ableton(ctx).send_command("get_song_scale", {})


@mcp.tool()
def set_song_scale(ctx: Context, root_note: int, scale_name: str) -> dict:
    """Set the Song-level Scale Mode root + scale name (Live 12.0+).

    root_note:   0-11 (C=0, C#=1, ... B=11)
    scale_name:  must match one of Live's built-in scale names.
                 Call list_available_scales() first if unsure.
    """
    if not 0 <= root_note <= 11:
        raise ValueError("root_note must be 0-11")
    if not scale_name.strip():
        raise ValueError("scale_name cannot be empty")
    return _get_ableton(ctx).send_command("set_song_scale", {
        "root_note": root_note,
        "scale_name": scale_name,
    })


@mcp.tool()
def set_song_scale_mode(ctx: Context, enabled: bool) -> dict:
    """Enable or disable Scale Mode on the current set (Live 12.0+).

    When enabled, Live's MIDI input and some devices become scale-aware.
    """
    return _get_ableton(ctx).send_command("set_song_scale_mode", {
        "enabled": enabled,
    })


@mcp.tool()
def list_available_scales(ctx: Context) -> dict:
    """Return Live's built-in scale names (Live 12.0+).

    Use before set_song_scale() to validate names or offer the user
    a list. Returns e.g. ["Major", "Minor", "Dorian", "Mixolydian", ...].
    """
    return _get_ableton(ctx).send_command("list_available_scales", {})
