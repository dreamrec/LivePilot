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


@mcp.tool()
def get_tuning_system(ctx: Context) -> dict:
    """Read the current Tuning System state (Live 12.1+).

    Exposes Ableton's microtonal tuning: name, pseudo-octave size
    (in cents), note range, reference pitch (Hz), and per-degree
    cent offsets from 12-TET.

    Use for maqam, just intonation, or any non-12-TET workflow.
    """
    return _get_ableton(ctx).send_command("get_tuning_system", {})


@mcp.tool()
def set_tuning_reference_pitch(ctx: Context, reference_pitch: float) -> dict:
    """Set the Tuning System's reference pitch in Hz (Live 12.1+).

    Default is 440.0. Common alternatives: 432.0 (A432), 415.3 (Baroque).
    """
    if reference_pitch <= 0:
        raise ValueError("reference_pitch must be > 0 Hz")
    return _get_ableton(ctx).send_command("set_tuning_reference_pitch", {
        "reference_pitch": reference_pitch,
    })


@mcp.tool()
def set_tuning_note(ctx: Context, degree: int, cent_offset: float) -> dict:
    """Adjust the cent offset for a single scale degree (Live 12.1+).

    degree:      0-based scale-degree index (length depends on the
                 loaded tuning system — call get_tuning_system() first
                 to see the note_tunings array length).
    cent_offset: cents from 12-TET. Examples:
                   -13.686 -> pure minor third
                    +1.955 -> pure major third (third harmonic)
    """
    if degree < 0:
        raise ValueError("degree must be >= 0")
    return _get_ableton(ctx).send_command("set_tuning_note", {
        "degree": degree,
        "cent_offset": cent_offset,
    })


@mcp.tool()
def reset_tuning_system(ctx: Context) -> dict:
    """Reset all per-degree tuning offsets to 12-TET (Live 12.1+).

    Clears all per-note microtonal offsets. Doesn't change the
    tuning system's name or reference pitch — just the offsets.
    """
    return _get_ableton(ctx).send_command("reset_tuning_system", {})
