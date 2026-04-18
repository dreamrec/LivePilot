"""Transport MCP tools — playback, tempo, metronome, loop, undo/redo, action log, diagnostics.

21 tools matching the Remote Script transport domain.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def get_session_info(ctx: Context) -> dict:
    """Get comprehensive Ableton session state: tempo, tracks, scenes, transport."""
    return _get_ableton(ctx).send_command("get_session_info")


def _validate_tempo(tempo: float) -> None:
    """Validate tempo is within Ableton's accepted range."""
    if not 20 <= tempo <= 999:
        raise ValueError("Tempo must be between 20 and 999 BPM")


def _validate_time_signature(numerator: int, denominator: int) -> None:
    """Validate time signature components."""
    if numerator < 1 or numerator > 99:
        raise ValueError("Numerator must be between 1 and 99")
    if denominator not in (1, 2, 4, 8, 16):
        raise ValueError("Denominator must be 1, 2, 4, 8, or 16")


@mcp.tool()
def set_tempo(ctx: Context, tempo: float) -> dict:
    """Set the song tempo in BPM (20-999)."""
    _validate_tempo(tempo)
    return _get_ableton(ctx).send_command("set_tempo", {"tempo": tempo})


@mcp.tool()
def set_time_signature(ctx: Context, numerator: int, denominator: int) -> dict:
    """Set the time signature (e.g., 4/4, 3/4, 6/8)."""
    _validate_time_signature(numerator, denominator)
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
    """Stop playback — halts the session transport and the arrangement cursor returns to its last position."""
    return _get_ableton(ctx).send_command("stop_playback")


@mcp.tool()
def continue_playback(ctx: Context) -> dict:
    """Continue playback from the current position."""
    return _get_ableton(ctx).send_command("continue_playback")


@mcp.tool()
def toggle_metronome(ctx: Context, enabled: Optional[bool] = None) -> dict:
    """Enable or disable the metronome click.

    If enabled is omitted, toggles the current state (true toggle).
    If enabled is provided, sets to that value explicitly.
    """
    if enabled is None:
        # True toggle: read current state and flip it
        info = _get_ableton(ctx).send_command("get_session_info")
        enabled = not info.get("metronome", False)
    return _get_ableton(ctx).send_command("toggle_metronome", {"enabled": enabled})


@mcp.tool()
def set_session_loop(
    ctx: Context,
    enabled: bool,
    start: Optional[float] = None,
    length: Optional[float] = None,
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


@mcp.tool()
async def get_session_diagnostics(ctx: Context, check_clip_keys: bool = False) -> dict:
    """Analyze the session for potential issues: armed tracks, solo/mute leftovers, unnamed tracks, empty clips/scenes, MIDI tracks without instruments. Returns issues with severity (warning/info) and stats.

    check_clip_keys: when True, also cross-checks every audio clip's
        filename-encoded key against the detected session key (BUG-D1 scan).
        Each mismatch appears as a diagnostic entry with the exact
        set_clip_pitch call that would correct it. Requires the M4L bridge
        (uses get_clip_file_path + get_detected_key); skipped gracefully if
        the bridge is unavailable. Off by default because it round-trips
        the bridge once per audio clip and can add noticeable latency on
        large sessions.
    """
    result = _get_ableton(ctx).send_command("get_session_diagnostics")

    if not check_clip_keys:
        return result
    if not isinstance(result, dict):
        return result

    # Augment with per-clip key-consistency checks. Each mismatch is added
    # as a diagnostic with severity="warning"; "unknown" results are
    # skipped so we don't drown the user in "no key detected yet" noise.
    from .clips import check_clip_key_consistency  # local import to avoid cycles

    audio_mismatches: list[dict] = []
    session_info = _get_ableton(ctx).send_command("get_session_info")
    tracks = (session_info or {}).get("tracks", []) if isinstance(session_info, dict) else []
    for track in tracks:
        t_idx = track.get("index")
        if t_idx is None:
            continue
        # We don't know which slots hold audio clips without probing, so
        # iterate the first N scene slots conservatively. A session with
        # many scenes would benefit from a scene-count cap; 32 is a
        # reasonable upper bound for typical production sessions.
        for clip_idx in range(min(32, len(session_info.get("scenes", []) or []) or 8)):
            try:
                check = await check_clip_key_consistency.fn(ctx, t_idx, clip_idx)
            except Exception:  # noqa: BLE001 — any failure means "skip this clip"
                continue
            if not isinstance(check, dict):
                continue
            if check.get("status") == "mismatch":
                audio_mismatches.append({
                    "severity": "warning",
                    "category": "clip_key_mismatch",
                    "track_index": t_idx,
                    "clip_index": clip_idx,
                    "message": check.get("reason", ""),
                    "recommended_fix": check.get("recommended_fix"),
                })

    if audio_mismatches:
        issues = result.setdefault("issues", [])
        issues.extend(audio_mismatches)
        result["clip_key_mismatch_count"] = len(audio_mismatches)

    return result


# ── Song / Transport long-tail primitives ─────────────────────────────


@mcp.tool()
def tap_tempo(ctx: Context) -> dict:
    """Tap the tempo (one tap). Live averages consecutive taps to set BPM."""
    return _get_ableton(ctx).send_command("tap_tempo", {})


@mcp.tool()
def nudge_tempo(ctx: Context, direction: str) -> dict:
    """Nudge tempo up or down by Live's internal nudge delta. direction: 'up' or 'down'."""
    if direction not in ("up", "down"):
        raise ValueError("direction must be 'up' or 'down'")
    return _get_ableton(ctx).send_command("nudge_tempo", {"direction": direction})


@mcp.tool()
def set_exclusive_arm(ctx: Context, enabled: bool) -> dict:
    """Enable/disable exclusive arm mode (only one track armed at a time)."""
    return _get_ableton(ctx).send_command("set_exclusive_arm", {"enabled": enabled})


@mcp.tool()
def set_exclusive_solo(ctx: Context, enabled: bool) -> dict:
    """Enable/disable exclusive solo mode (only one track soloed at a time)."""
    return _get_ableton(ctx).send_command("set_exclusive_solo", {"enabled": enabled})


@mcp.tool()
def capture_and_insert_scene(ctx: Context) -> dict:
    """Capture currently-playing clips and insert them as a new scene. Distinct from capture_midi."""
    return _get_ableton(ctx).send_command("capture_and_insert_scene", {})


@mcp.tool()
def set_count_in_duration(ctx: Context, bars: int) -> dict:
    """Set pre-record count-in duration (0-4 bars)."""
    if not 0 <= bars <= 4:
        raise ValueError("bars must be 0-4")
    return _get_ableton(ctx).send_command("set_count_in_duration", {"bars": bars})


@mcp.tool()
def get_link_state(ctx: Context) -> dict:
    """Read Ableton Link + count-in state (enabled, start/stop sync, tempo follower, is_counting_in)."""
    return _get_ableton(ctx).send_command("get_link_state", {})


@mcp.tool()
def set_link_enabled(ctx: Context, enabled: bool) -> dict:
    """Enable or disable Ableton Link (network tempo synchronization)."""
    return _get_ableton(ctx).send_command("set_link_enabled", {"enabled": enabled})


@mcp.tool()
def force_link_beat_time(ctx: Context, beat_time: float) -> dict:
    """Force Ableton Link to a specific beat time (if supported by this Live version)."""
    return _get_ableton(ctx).send_command("force_link_beat_time", {"beat_time": beat_time})
