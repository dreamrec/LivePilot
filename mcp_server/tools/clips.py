"""Clip MCP tools — info, create, delete, duplicate, fire, stop, properties, warp.

11 tools matching the Remote Script clips domain, plus a key-consistency
diagnostic (BUG-D1) that cross-references filename-encoded keys against
the analyzer-detected session key.
"""

from __future__ import annotations

import re
from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


# ── Key-token parsing (BUG-D1) ─────────────────────────────────────────
#
# Splice filenames encode the key as one of:
#   _D#min   _Dmin   _Dm       → minor
#   _Dmaj    _DMaj   _D        → major (trailing nothing or just "maj")
#   _Eb      _Ebmin   _Dbm     → accidentals accepted as # or b
#
# We accept any of those forms and emit a canonical (root, mode) tuple.

# Note → semitone offset from C (C=0, C#=1, D=2, ...)
_NOTE_TO_SEMI = {
    "c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "fb": 4,
    "e#": 5, "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8,
    "a": 9, "a#": 10, "bb": 10, "b": 11, "cb": 11,
}

# Match the trailing key token in a filename stem (everything before the
# extension, underscore-delimited). We anchor to the end of the stem so
# an earlier "D" in the filename (e.g. "Dabrye_...") doesn't match.
_KEY_RE = re.compile(
    r"(?P<root>[A-Ga-g][#b]?)(?P<mode>maj|min|m|Maj|Min)?$",
    flags=re.IGNORECASE,
)


def _parse_key_from_filename(filename: str) -> Optional[dict]:
    """Extract key info from a Splice-style filename.

    Returns ``{"root": "D#", "mode": "minor", "semi": 3, "token": "D#min"}``
    or ``None`` if no recognizable key token is present in the final
    underscore-segment of the filename stem.
    """
    if not filename:
        return None
    stem = filename.rsplit(".", 1)[0]
    last = stem.split("_")[-1]
    match = _KEY_RE.fullmatch(last)
    if not match:
        return None
    root_raw = match.group("root").lower()
    mode_raw = (match.group("mode") or "").lower()
    # Normalize the root to lookup form. Canonicalize B# → C, etc. (rare
    # but possible in hand-named samples).
    semi = _NOTE_TO_SEMI.get(root_raw)
    if semi is None:
        return None
    # Without an explicit mode suffix, Splice convention defaults to major.
    mode = "minor" if mode_raw in ("min", "m") else "major"
    # Canonical display: capitalize root, preserve #/b.
    root_display = root_raw[0].upper() + root_raw[1:]
    return {
        "root": root_display,
        "mode": mode,
        "semi": semi,
        "token": last,
    }


def _key_to_semi(root: str, mode: str = "major") -> Optional[int]:
    """Convert a session-reported key like ``"D"`` + ``"minor"`` to 0..11 semis."""
    if not root:
        return None
    semi = _NOTE_TO_SEMI.get(root.strip().lower())
    return semi


def _validate_track_index(track_index: int):
    """Validate track index. Must be >= 0 for regular tracks."""
    if track_index < 0:
        raise ValueError("track_index must be >= 0")


def _validate_clip_index(clip_index: int):
    if clip_index < 0:
        raise ValueError("clip_index must be >= 0")


def _validate_color_index(color_index: int):
    if not 0 <= color_index <= 69:
        raise ValueError("color_index must be between 0 and 69")


@mcp.tool()
def get_clip_info(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Get detailed info about a clip: name, length, loop, launch settings."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    return _get_ableton(ctx).send_command("get_clip_info", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def create_clip(ctx: Context, track_index: int, clip_index: int, length: float) -> dict:
    """Create an empty MIDI clip in a clip slot (length in beats)."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if length <= 0:
        raise ValueError("length must be > 0")
    return _get_ableton(ctx).send_command("create_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
        "length": length,
    })


@mcp.tool()
def delete_clip(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Delete a clip from a clip slot. This removes all notes and automation. Use undo to revert."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    return _get_ableton(ctx).send_command("delete_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def duplicate_clip(
    ctx: Context,
    track_index: int,
    clip_index: int,
    target_track: int,
    target_clip: int,
) -> dict:
    """Duplicate a clip from one slot to another."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    _validate_track_index(target_track)
    _validate_clip_index(target_clip)
    return _get_ableton(ctx).send_command("duplicate_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
        "target_track": target_track,
        "target_clip": target_clip,
    })


@mcp.tool()
def fire_clip(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Launch/fire a clip slot."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    return _get_ableton(ctx).send_command("fire_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def stop_clip(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Stop a playing clip."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    return _get_ableton(ctx).send_command("stop_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def set_clip_name(ctx: Context, track_index: int, clip_index: int, name: str) -> dict:
    """Rename a clip in the Session view. The new name appears on the clip slot and in Device Chain displays."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not name.strip():
        raise ValueError("Clip name cannot be empty")
    return _get_ableton(ctx).send_command("set_clip_name", {
        "track_index": track_index,
        "clip_index": clip_index,
        "name": name,
    })


@mcp.tool()
def set_clip_color(ctx: Context, track_index: int, clip_index: int, color_index: int) -> dict:
    """Set clip color (0-69, Ableton's color palette)."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    _validate_color_index(color_index)
    return _get_ableton(ctx).send_command("set_clip_color", {
        "track_index": track_index,
        "clip_index": clip_index,
        "color_index": color_index,
    })


@mcp.tool()
def set_clip_loop(
    ctx: Context,
    track_index: int,
    clip_index: int,
    enabled: Optional[bool] = None,
    loop_start: Optional[float] = None,
    loop_end: Optional[float] = None,
) -> dict:
    """Enable/disable clip looping and optionally set loop start/end (in beats).
    All parameters are optional but at least one must be provided."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if enabled is None and loop_start is None and loop_end is None:
        raise ValueError("At least one of enabled, loop_start, or loop_end must be provided")
    params = {
        "track_index": track_index,
        "clip_index": clip_index,
    }
    if enabled is not None:
        params["enabled"] = enabled
    if loop_start is not None:
        if loop_start < 0:
            raise ValueError("Loop start must be >= 0")
        params["start"] = loop_start
    if loop_end is not None:
        if loop_end <= 0:
            raise ValueError("Loop end must be > 0")
        params["end"] = loop_end
    if loop_start is not None and loop_end is not None and loop_start >= loop_end:
        raise ValueError("Loop start must be less than loop end")
    return _get_ableton(ctx).send_command("set_clip_loop", params)


@mcp.tool()
def set_clip_launch(
    ctx: Context,
    track_index: int,
    clip_index: int,
    mode: int,
    quantization: Optional[int] = None,
) -> dict:
    """Set clip launch mode (0=Trigger, 1=Gate, 2=Toggle, 3=Repeat) and optional quantization."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if not 0 <= mode <= 3:
        raise ValueError("Launch mode must be 0-3 (Trigger, Gate, Toggle, Repeat)")
    params = {
        "track_index": track_index,
        "clip_index": clip_index,
        "mode": mode,
    }
    if quantization is not None:
        params["quantization"] = quantization
    return _get_ableton(ctx).send_command("set_clip_launch", params)


@mcp.tool()
def set_clip_pitch(
    ctx: Context,
    track_index: int,
    clip_index: int,
    coarse: Optional[int] = None,
    fine: Optional[float] = None,
    gain: Optional[float] = None,
) -> dict:
    """Set pitch transposition and/or gain on an audio clip (BUG-A5).

    Audio clips only. Use this to correct sample pitch to match session key
    (e.g. a D#min Splice clip in a Dm session -> coarse=-1).

    coarse: semitones, -48..+48
    fine:   cents, -50..+50
    gain:   linear, 0..1 (Live's internal scale, not dB)

    At least one of coarse/fine/gain must be provided.
    """
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if coarse is None and fine is None and gain is None:
        raise ValueError(
            "Provide at least one of: coarse (semitones), fine (cents), gain (0-1)"
        )
    if coarse is not None and not -48 <= coarse <= 48:
        raise ValueError("coarse must be in -48..+48 semitones")
    if fine is not None and not -50.0 <= fine <= 50.0:
        raise ValueError("fine must be in -50..+50 cents")
    if gain is not None and not 0.0 <= gain <= 1.0:
        raise ValueError("gain must be in 0..1")
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
    }
    if coarse is not None:
        params["coarse"] = coarse
    if fine is not None:
        params["fine"] = fine
    if gain is not None:
        params["gain"] = gain
    return _get_ableton(ctx).send_command("set_clip_pitch", params)


_VALID_WARP_MODES = {0, 1, 2, 3, 4, 6}


@mcp.tool()
def set_clip_warp_mode(
    ctx: Context,
    track_index: int,
    clip_index: int,
    mode: int,
    warping: Optional[bool] = None,
) -> dict:
    """Set warp mode for an audio clip (0=Beats, 1=Tones, 2=Texture, 3=Re-Pitch, 4=Complex, 6=Complex Pro)."""
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)
    if mode not in _VALID_WARP_MODES:
        raise ValueError("Warp mode must be one of: 0=Beats, 1=Tones, 2=Texture, 3=Re-Pitch, 4=Complex, 6=Complex Pro")
    params = {
        "track_index": track_index,
        "clip_index": clip_index,
        "mode": mode,
    }
    if warping is not None:
        params["warping"] = warping
    return _get_ableton(ctx).send_command("set_clip_warp_mode", params)


@mcp.tool()
async def check_clip_key_consistency(
    ctx: Context,
    track_index: int,
    clip_index: int,
) -> dict:
    """Cross-check a clip's filename-encoded key against the session key (BUG-D1).

    Splice-style sample filenames encode the sample's key (e.g.
    ``AU_THF2_128_vocal_..._D#min.wav``). This tool parses that token,
    compares it to the analyzer-detected session key, and — when they
    disagree — computes the semitone delta needed to realign, returning
    the exact ``set_clip_pitch(coarse=...)`` call that would correct it.

    Return shape::

        {
            "track_index": 6,
            "clip_index": 0,
            "filename_key": {"root": "D#", "mode": "minor", "token": "D#min"},
            "session_key": {"root": "D", "mode": "minor"},
            "status": "mismatch" | "match" | "unknown",
            "semitone_delta": -1,          # clip needs to shift DOWN 1
            "recommended_fix": {
                "tool": "set_clip_pitch",
                "args": {"track_index": 6, "clip_index": 0, "coarse": -1}
            },
            "reason": "Clip is D#min, session is Dm — shift -1 semitone."
        }

    Returns ``status="unknown"`` (not an error) when:
      - the clip is MIDI (no audio file path)
      - the filename has no parseable key token
      - the analyzer hasn't detected a session key yet

    Requires the M4L bridge for both ``get_clip_file_path`` and
    ``get_detected_key``. Degrades gracefully without it.
    """
    _validate_track_index(track_index)
    _validate_clip_index(clip_index)

    # 1) Resolve the clip's file path. Relies on the M4L bridge.
    try:
        from .analyzer import get_clip_file_path as _get_path
        # get_clip_file_path is an @mcp.tool, but FastMCP decorators preserve
        # the underlying function — we can call it directly for composition.
        path_resp = await _get_path.fn(ctx, track_index, clip_index)
    except Exception as exc:
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "status": "unknown",
            "reason": f"Could not resolve clip file path: {exc}",
        }
    if not isinstance(path_resp, dict) or path_resp.get("error"):
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "status": "unknown",
            "reason": path_resp.get("error", "No file path available (MIDI clip?)."),
        }
    file_path = path_resp.get("path") or path_resp.get("file_path") or ""

    # 2) Parse key token from the filename.
    import os
    filename_key = _parse_key_from_filename(os.path.basename(file_path))
    if filename_key is None:
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "file_path": file_path,
            "status": "unknown",
            "reason": "Filename has no recognizable key token.",
        }

    # 3) Query the session-detected key (needs the analyzer).
    try:
        from .analyzer import get_detected_key as _get_key
        key_resp = await _get_key.fn(ctx)
    except Exception as exc:
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "file_path": file_path,
            "filename_key": filename_key,
            "status": "unknown",
            "reason": f"Analyzer unavailable: {exc}",
        }
    if not isinstance(key_resp, dict) or key_resp.get("error") or not key_resp.get("key"):
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "file_path": file_path,
            "filename_key": filename_key,
            "status": "unknown",
            "reason": key_resp.get(
                "error", "Session key not yet detected — play 4-8 bars."
            ),
        }
    session_root = str(key_resp.get("key", ""))
    session_mode = str(key_resp.get("scale", "major")).lower()
    session_semi = _key_to_semi(session_root)

    # 4) Classify + compute fix.
    file_semi = filename_key["semi"]
    if session_semi is None or file_semi is None:
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "file_path": file_path,
            "filename_key": filename_key,
            "session_key": {"root": session_root, "mode": session_mode},
            "status": "unknown",
            "reason": "Could not resolve semitone offsets for comparison.",
        }

    if filename_key["mode"] != session_mode:
        mode_note = (
            f" (clip is {filename_key['mode']}, session is {session_mode} — "
            "mode mismatch is often OK for ambient/background use)"
        )
    else:
        mode_note = ""

    if file_semi == session_semi and filename_key["mode"] == session_mode:
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "file_path": file_path,
            "filename_key": filename_key,
            "session_key": {"root": session_root, "mode": session_mode},
            "status": "match",
            "semitone_delta": 0,
            "recommended_fix": None,
            "reason": "Clip key matches session.",
        }

    # Semitone delta: how much the clip should shift to align with the
    # session root. Choose the smaller magnitude (shift up or down).
    raw_delta = (session_semi - file_semi) % 12
    if raw_delta > 6:
        raw_delta -= 12  # prefer the nearer direction (−1 over +11)
    delta = raw_delta

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "file_path": file_path,
        "filename_key": filename_key,
        "session_key": {"root": session_root, "mode": session_mode},
        "status": "mismatch",
        "semitone_delta": delta,
        "recommended_fix": {
            "tool": "set_clip_pitch",
            "args": {
                "track_index": track_index,
                "clip_index": clip_index,
                "coarse": delta,
            },
        },
        "reason": (
            f"Clip is {filename_key['root']}{filename_key['mode'][:3]}, "
            f"session is {session_root}{session_mode[:3]} — "
            f"shift {delta:+d} semitone{'' if abs(delta) == 1 else 's'}."
            f"{mode_note}"
        ),
    }


@mcp.tool()
def get_clip_scale(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Read a clip's per-clip scale override (Live 12.0+).

    Per-clip scales are independent of Song.scale_*. A clip can have
    Scale Mode enabled with a different root/name than the Song.

    Returns {root_note (0-11), scale_mode (bool), scale_name (str)}.
    Raises if the clip slot is empty.
    """
    return _get_ableton(ctx).send_command("get_clip_scale", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def set_clip_scale(
    ctx: Context,
    track_index: int,
    clip_index: int,
    root_note: int,
    scale_name: str,
) -> dict:
    """Set a clip's per-clip scale override (Live 12.0+).

    Overrides the Song-level scale for this clip only. Useful for
    key changes within a set, or for clips that live in a different
    mode than the rest of the arrangement.

    root_note:   0-11 (C=0, C#=1, ... B=11)
    scale_name:  must match one of Live's built-in scales
                 (call list_available_scales() if unsure)
    """
    if not 0 <= root_note <= 11:
        raise ValueError("root_note must be 0-11")
    if not scale_name.strip():
        raise ValueError("scale_name cannot be empty")
    return _get_ableton(ctx).send_command("set_clip_scale", {
        "track_index": track_index,
        "clip_index": clip_index,
        "root_note": root_note,
        "scale_name": scale_name,
    })


@mcp.tool()
def set_clip_scale_mode(
    ctx: Context,
    track_index: int,
    clip_index: int,
    enabled: bool,
) -> dict:
    """Enable or disable Scale Mode on a single clip (Live 12.0+).

    When enabled on a clip, its notes are constrained/highlighted
    by the clip's own root_note + scale_name (set via set_clip_scale).
    """
    return _get_ableton(ctx).send_command("set_clip_scale_mode", {
        "track_index": track_index,
        "clip_index": clip_index,
        "enabled": enabled,
    })
