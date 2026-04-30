"""Track MCP tools — create, delete, rename, mute, solo, arm, group fold, monitor, freeze, flatten.

20 tools matching the Remote Script tracks domain.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


MASTER_TRACK_INDEX = -1000  # mirrors remote_script/LivePilot/utils.py


def _validate_track_index(track_index: int, allow_return: bool = True, allow_master: bool = True):
    """Validate track index.

    Regular tracks: >= 0. Return tracks: -1 (A), -2 (B), etc. Master: -1000.
    Set allow_return=False for operations that only work on regular tracks
    (e.g., create_scene, set_group_fold).
    Set allow_master=False for operations that don't make sense on master
    (e.g., delete_track, set_track_arm).
    """
    if track_index == MASTER_TRACK_INDEX:
        if not allow_master:
            raise ValueError("track_index=-1000 (master) is not supported for this operation")
        return
    if track_index < 0:
        if not allow_return:
            raise ValueError("track_index must be >= 0 (return tracks not supported for this operation)")
        if track_index < -99:
            raise ValueError(
                "track_index must be >= 0 for regular tracks, "
                "-1..-99 for return tracks (-1=A, -2=B), "
                "or -1000 for master"
            )


def _validate_color_index(color_index: int):
    if not 0 <= color_index <= 69:
        raise ValueError("color_index must be between 0 and 69")


@mcp.tool()
def get_track_info(ctx: Context, track_index: int) -> dict:
    """Get detailed info about a track: clips, devices, mixer state.

    BUG-2026-04-22#11 FIX: track_index=-1000 (the master-track convention
    used by set_track_volume, find_and_load_device, etc.) now dispatches
    to the get_master_track endpoint instead of rejecting. This makes
    -1000 work consistently across every track-addressing tool.
    """
    _validate_track_index(track_index)
    if track_index == MASTER_TRACK_INDEX:
        return _get_ableton(ctx).send_command("get_master_track")
    return _get_ableton(ctx).send_command("get_track_info", {"track_index": track_index})


@mcp.tool()
def verify_device_alive(
    ctx: Context,
    track_index: int,
    device_index: int,
) -> dict:
    """Check whether a loaded device is alive (BUG-2026-04-22 #19).

    Static health check based on get_device_info — no test note required.
    A device is considered DEAD when:
      - class_name contains "PluginDevice" (AU/VST) AND parameter_count <= 1
        (the shell loaded but the DSP engine crashed / wasn't activated)
      - health_flags contains "opaque_or_failed_plugin"

    Returns: {alive: bool, reason: str, parameter_count: int, class_name: str,
              health_flags: list, recommendation: str | None}

    The `recommendation` is a one-liner like "delete and load native
    alternative" when the device is dead. None when alive.
    """
    _validate_track_index(track_index)
    info = _get_ableton(ctx).send_command(
        "get_device_info", {"track_index": track_index, "device_index": device_index},
    )
    if not isinstance(info, dict):
        return {"alive": False, "reason": f"get_device_info returned non-dict: {info!r}"}

    class_name = str(info.get("class_name", ""))
    parameter_count = int(info.get("parameter_count", 0))
    health_flags = list(info.get("health_flags", []))

    if "PluginDevice" in class_name and parameter_count <= 1:
        return {
            "alive": False,
            "reason": (
                f"plugin_shell_no_dsp — class_name={class_name!r}, "
                f"parameter_count={parameter_count}. The plugin host loaded "
                f"the shell but the DSP engine did not activate (common "
                f"after a crash or unauthorized AU/VST)."
            ),
            "parameter_count": parameter_count,
            "class_name": class_name,
            "health_flags": health_flags,
            "recommendation": (
                "Delete this device and load a native Ableton alternative "
                "(Wavetable / Operator / Drift for synth, Reverb / Delay / "
                "Compressor for FX)."
            ),
        }

    if "opaque_or_failed_plugin" in health_flags:
        return {
            "alive": False,
            "reason": "health_flags reports opaque_or_failed_plugin",
            "parameter_count": parameter_count,
            "class_name": class_name,
            "health_flags": health_flags,
            "recommendation": "Delete and replace with a native alternative.",
        }

    return {
        "alive": True,
        "reason": "passes static health checks",
        "parameter_count": parameter_count,
        "class_name": class_name,
        "health_flags": health_flags,
        "recommendation": None,
    }


def _find_name_collisions(ctx: Context, name: str) -> list[int]:
    """Return track indices whose name exactly matches `name` (case-sensitive).

    BUG #5 fix (v1.20.2): downstream role-based resolvers like
    find_tracks_by_role match on track names. If create_midi_track
    creates a second "Pad" while another "Pad" already exists, mix
    moves like widen_stereo match BOTH — applying the change twice.
    This helper enables create_*_track to warn the caller so they can
    pick a unique name or explicitly accept the collision.

    Best-effort: returns [] when session_info can't be fetched —
    collision detection must never block creation.
    """
    try:
        info = _get_ableton(ctx).send_command("get_session_info")
    except Exception:
        return []
    if not isinstance(info, dict):
        return []
    tracks = info.get("tracks") or []
    matches: list[int] = []
    for t in tracks:
        if isinstance(t, dict) and t.get("name") == name:
            idx = t.get("index")
            if isinstance(idx, int):
                matches.append(idx)
    return matches


def _resolve_color_alias(
    color: Optional[int],
    color_index: Optional[int],
) -> Optional[int]:
    """BUG-2026-04-26#3: accept both `color` and `color_index` keywords.

    The track-creation tools used `color` while `set_track_color` used
    `color_index`. Callers writing parallel tool batches (create + paint
    in one shot) consistently picked the wrong name and lost a whole
    parallel batch to the validation error. This helper accepts either,
    rejects the conflict case, and returns the resolved value.
    """
    if color is not None and color_index is not None:
        if color != color_index:
            raise ValueError(
                "Pass either 'color' or 'color_index', not both with "
                f"different values (got color={color}, color_index={color_index})"
            )
        return color
    if color is not None:
        return color
    return color_index


@mcp.tool()
def create_midi_track(
    ctx: Context,
    index: int = -1,
    name: Optional[str] = None,
    color: Optional[int] = None,
    color_index: Optional[int] = None,
) -> dict:
    """Create a new MIDI track. index=-1 appends at end.

    `color` and `color_index` are accepted interchangeably (BUG-2026-04-26#3).
    Both reference Ableton's 0-69 color palette. Pass either; passing
    both with different values is rejected.

    Response (v1.20.2+): when `name` is provided, the response carries
    a ``name_collision`` bool and ``existing_tracks_with_same_name``
    list[int]. Downstream role-based resolvers (find_tracks_by_role)
    match duplicate names and apply mix changes twice — check the
    warning before proceeding with mix moves on the new track's role.
    """
    color = _resolve_color_alias(color, color_index)

    collisions: list[int] = []
    if name is not None and name.strip():
        collisions = _find_name_collisions(ctx, name)

    params = {"index": index}
    if name is not None:
        if not name.strip():
            raise ValueError("Track name cannot be empty")
        params["name"] = name
    if color is not None:
        _validate_color_index(color)
        params["color_index"] = color
    result = _get_ableton(ctx).send_command("create_midi_track", params)
    if isinstance(result, dict):
        # Always stamp both fields so callers can check unconditionally
        # (False + [] when no name provided or no collision).
        result["name_collision"] = bool(collisions)
        result["existing_tracks_with_same_name"] = collisions
    return result


@mcp.tool()
def create_audio_track(
    ctx: Context,
    index: int = -1,
    name: Optional[str] = None,
    color: Optional[int] = None,
    color_index: Optional[int] = None,
) -> dict:
    """Create a new audio track. index=-1 appends at end.

    `color` and `color_index` are accepted interchangeably (BUG-2026-04-26#3).
    See create_midi_track for full semantics.

    Response (v1.20.2+): ``name_collision`` + ``existing_tracks_with_same_name``
    same as create_midi_track — see BUG #5 rationale there.
    """
    color = _resolve_color_alias(color, color_index)

    collisions: list[int] = []
    if name is not None and name.strip():
        collisions = _find_name_collisions(ctx, name)

    params = {"index": index}
    if name is not None:
        if not name.strip():
            raise ValueError("Track name cannot be empty")
        params["name"] = name
    if color is not None:
        _validate_color_index(color)
        params["color_index"] = color
    result = _get_ableton(ctx).send_command("create_audio_track", params)
    if isinstance(result, dict):
        result["name_collision"] = bool(collisions)
        result["existing_tracks_with_same_name"] = collisions
    return result


@mcp.tool()
def create_return_track(ctx: Context) -> dict:
    """Create a new return track."""
    return _get_ableton(ctx).send_command("create_return_track")


@mcp.tool()
def delete_track(ctx: Context, track_index: int) -> dict:
    """Delete a track by index. Use undo to revert if needed.

    Ableton requires at least one track in the session. Attempting to
    delete the last remaining track raises ValueError with actionable
    guidance rather than surfacing Ableton's misleading default
    STATE_ERROR text (BUG-F3).
    """
    _validate_track_index(track_index)
    ableton = _get_ableton(ctx)
    session_info = ableton.send_command("get_session_info")
    track_count = session_info.get("track_count") if session_info else None
    if track_count is not None and track_count <= 1:
        raise ValueError(
            "Cannot delete track: Ableton requires at least one track "
            "in the session. Add another track first, or rename the "
            "current track if you want a clean slate."
        )
    return ableton.send_command("delete_track", {"track_index": track_index})


@mcp.tool()
def duplicate_track(ctx: Context, track_index: int) -> dict:
    """Duplicate a track (copies all clips, devices, and settings)."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("duplicate_track", {"track_index": track_index})


@mcp.tool()
def set_track_name(ctx: Context, track_index: int, name: str) -> dict:
    """Rename a track. The new name appears in both the Session and Arrangement views and survives session save."""
    _validate_track_index(track_index)
    if not name.strip():
        raise ValueError("Track name cannot be empty")
    return _get_ableton(ctx).send_command("set_track_name", {
        "track_index": track_index,
        "name": name,
    })


@mcp.tool()
def set_track_color(ctx: Context, track_index: int, color_index: int) -> dict:
    """Set track color (0-69, Ableton's color palette)."""
    _validate_track_index(track_index)
    _validate_color_index(color_index)
    return _get_ableton(ctx).send_command("set_track_color", {
        "track_index": track_index,
        "color_index": color_index,
    })


@mcp.tool()
def set_track_mute(ctx: Context, track_index: int, muted: bool) -> dict:
    """Mute or unmute a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_track_mute", {
        "track_index": track_index,
        "mute": muted,
    })


@mcp.tool()
def set_track_solo(ctx: Context, track_index: int, solo: bool) -> dict:
    """Solo or unsolo a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_track_solo", {
        "track_index": track_index,
        "solo": solo,
    })


@mcp.tool()
def set_track_arm(ctx: Context, track_index: int, arm: bool) -> dict:
    """Arm or disarm a track for recording."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("set_track_arm", {
        "track_index": track_index,
        "arm": arm,
    })


@mcp.tool()
def stop_track_clips(ctx: Context, track_index: int) -> dict:
    """Stop all playing clips on a track."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("stop_track_clips", {"track_index": track_index})


@mcp.tool()
def set_group_fold(ctx: Context, track_index: int, folded: bool) -> dict:
    """Fold or unfold a group track to show/hide its children."""
    _validate_track_index(track_index, allow_return=False)
    return _get_ableton(ctx).send_command("set_group_fold", {
        "track_index": track_index,
        "folded": folded,
    })


@mcp.tool()
def set_track_input_monitoring(ctx: Context, track_index: int, state: int) -> dict:
    """Set input monitoring (0=In, 1=Auto, 2=Off). Only for regular tracks, not return tracks."""
    _validate_track_index(track_index, allow_return=False)
    if state not in (0, 1, 2):
        raise ValueError("Monitoring state must be 0=In, 1=Auto, or 2=Off")
    return _get_ableton(ctx).send_command("set_track_input_monitoring", {
        "track_index": track_index,
        "state": state,
    })


# ── Freeze / Flatten ────────────────────────────────────────────────────


@mcp.tool()
def freeze_track(ctx: Context, track_index: int) -> dict:
    """Freeze a track — render all devices to audio for CPU savings.

    Freeze is async in Ableton: this initiates the render and returns
    immediately. Poll get_freeze_status to check when it's done.
    Freezing a track that's already frozen is a no-op.

    Note: freeze() is not available via ControlSurface API in all Live
    versions. If this fails, use Ableton's Freeze Track menu command
    (Cmd+F on Mac) manually instead.
    """
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("freeze_track", {
        "track_index": track_index,
    })


@mcp.tool()
def flatten_track(ctx: Context, track_index: int) -> dict:
    """Flatten a frozen track — commit rendered audio permanently.

    Destructive: replaces all devices with the rendered audio file.
    The track must already be frozen. Use undo to revert.
    """
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("flatten_track", {
        "track_index": track_index,
    })


@mcp.tool()
def get_freeze_status(ctx: Context, track_index: int) -> dict:
    """Check if a track is frozen.

    Use after freeze_track to poll for completion, or before
    flatten_track to verify the track is ready to flatten.
    """
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("get_freeze_status", {
        "track_index": track_index,
    })


# ── Track long-tail primitives ──────────────────────────────────────────


@mcp.tool()
def jump_in_session_clip(ctx: Context, track_index: int, beats: float) -> dict:
    """Jump playhead within a running session clip, in beats from start."""
    _validate_track_index(track_index, allow_return=False)
    return _get_ableton(ctx).send_command("jump_in_session_clip", {
        "track_index": track_index,
        "beats": beats,
    })


@mcp.tool()
def get_track_performance_impact(ctx: Context, track_index: int) -> dict:
    """Read a track's CPU performance impact metric."""
    _validate_track_index(track_index)
    return _get_ableton(ctx).send_command("get_track_performance_impact", {
        "track_index": track_index,
    })


@mcp.tool()
def get_appointed_device(ctx: Context) -> dict:
    """Return the Blue Hand (appointed/focused) device location as (track_index, device_index, track_name, device_name)."""
    return _get_ableton(ctx).send_command("get_appointed_device", {})
