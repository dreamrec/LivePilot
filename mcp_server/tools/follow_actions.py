"""Follow Actions tools (Live 12.0+ clip, 12.2+ scene).

8 tools matching the Remote Script follow_actions domain:
- Clip follow actions (Live 12.0 revamp): get/set/clear, a preset
  wrapper, and enum-name enumeration.
- Scene follow actions (Live 12.2+): get/set/clear with "Longest"
  mode (``linked``) and the 1-8 ``multiplier`` selector.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


# ── Clip follow actions (Live 12.0+) ─────────────────────────────────────


@mcp.tool()
def get_clip_follow_action(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Read a clip's follow-action state (Live 12.0+).

    Returns:
        enabled:   bool — follow-action master switch
        action_a:  primary action name (stop, play_again, previous,
                   next, first, last, any, other, jump)
        action_b:  secondary action (used when chance_b > 0)
        chance_a:  probability of action_a firing (0.0-1.0)
        chance_b:  probability of action_b firing (0.0-1.0)
        time:      follow-action trigger time in beats
    """
    return _get_ableton(ctx).send_command("get_clip_follow_action", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def set_clip_follow_action(
    ctx: Context,
    track_index: int,
    clip_index: int,
    action_a: Optional[str] = None,
    action_b: Optional[str] = None,
    chance_a: Optional[float] = None,
    chance_b: Optional[float] = None,
    time: Optional[float] = None,
    enabled: Optional[bool] = None,
) -> dict:
    """Set a clip's follow action (Live 12.0+). Any omitted arg preserves.

    action_a/b values (string): stop, play_again, previous, next,
      first, last, any, other, jump.
    chance_a/b: probability 0.0-1.0. Live normalizes the split between
      the two actions — set chance_b=0 to always fire action_a.
    time: follow-action trigger time in beats (e.g. 1.0 = one bar in 4/4,
      4.0 = one bar in 4/4 if the clip is 4 beats long).
    enabled: master on/off for follow actions on this clip.
    """
    payload: dict = {"track_index": track_index, "clip_index": clip_index}
    if action_a is not None:
        payload["action_a"] = action_a
    if action_b is not None:
        payload["action_b"] = action_b
    if chance_a is not None:
        if not 0.0 <= chance_a <= 1.0:
            raise ValueError("chance_a must be 0.0-1.0")
        payload["chance_a"] = chance_a
    if chance_b is not None:
        if not 0.0 <= chance_b <= 1.0:
            raise ValueError("chance_b must be 0.0-1.0")
        payload["chance_b"] = chance_b
    if time is not None:
        if time < 0.0:
            raise ValueError("time must be >= 0.0")
        payload["time"] = time
    if enabled is not None:
        payload["enabled"] = enabled
    return _get_ableton(ctx).send_command("set_clip_follow_action", payload)


@mcp.tool()
def clear_clip_follow_action(ctx: Context, track_index: int, clip_index: int) -> dict:
    """Disable follow action on a clip (Live 12.0+).

    Sets follow_action_enabled=False without touching the action/chance
    values, so re-enabling keeps the previous configuration.
    """
    return _get_ableton(ctx).send_command("clear_clip_follow_action", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def list_follow_action_types(ctx: Context) -> dict:
    """List valid follow-action names (Live 12.0+).

    Returns the 9 enum values usable for action_a/action_b:
    stop, play_again, previous, next, first, last, any, other, jump.
    """
    return _get_ableton(ctx).send_command("list_follow_action_types", {})


@mcp.tool()
def apply_follow_action_preset(
    ctx: Context,
    track_index: int,
    clip_index: int,
    preset: str,
) -> dict:
    """Apply a named follow-action preset to a clip (Live 12.0+).

    Presets:
      loop_forever    — re-fires the clip each bar indefinitely
                        (action_a=play_again, chance 100%)
      random_walk     — 50/50 split between next and previous clip
      next_after_one  — play the clip once, advance to next slot
      stop_after_one  — play the clip once, then stop
    Each preset sets action_a, action_b, chance_a, chance_b, time
    and enables follow actions. Time is 1.0 beat across all presets.
    """
    valid = ["loop_forever", "random_walk", "next_after_one", "stop_after_one"]
    if preset not in valid:
        raise ValueError("preset must be one of %s" % ", ".join(valid))
    return _get_ableton(ctx).send_command("apply_follow_action_preset", {
        "track_index": track_index,
        "clip_index": clip_index,
        "preset": preset,
    })


# ── Scene follow actions (Live 12.2+) ────────────────────────────────────


@mcp.tool()
def get_scene_follow_action(ctx: Context, scene_index: int) -> dict:
    """Read a scene's follow-action state (Live 12.2+).

    Returns:
        enabled:    bool — scene follow-action master switch
        time:       trigger time in beats
        linked:     True = "Longest" mode (waits for longest clip's loop)
        multiplier: 1-8, used when not linked (time * multiplier = trigger)
    """
    return _get_ableton(ctx).send_command("get_scene_follow_action", {
        "scene_index": scene_index,
    })


@mcp.tool()
def set_scene_follow_action(
    ctx: Context,
    scene_index: int,
    enabled: Optional[bool] = None,
    time: Optional[float] = None,
    linked: Optional[bool] = None,
    multiplier: Optional[int] = None,
) -> dict:
    """Set a scene's follow action (Live 12.2+). Any omitted arg preserves.

    enabled:    on/off master switch for this scene's follow action
    time:       trigger time in beats (e.g. 4.0 = one bar in 4/4)
    linked:     True = "Longest" mode — waits for the longest clip in
                the scene to complete one loop
    multiplier: 1-8 — multiplies `time` when not linked. Used to trigger
                the follow action every N beats.
    """
    payload: dict = {"scene_index": scene_index}
    if enabled is not None:
        payload["enabled"] = enabled
    if time is not None:
        if time < 0.0:
            raise ValueError("time must be >= 0.0")
        payload["time"] = time
    if linked is not None:
        payload["linked"] = linked
    if multiplier is not None:
        if not 1 <= multiplier <= 8:
            raise ValueError("multiplier must be 1-8")
        payload["multiplier"] = multiplier
    return _get_ableton(ctx).send_command("set_scene_follow_action", payload)


@mcp.tool()
def clear_scene_follow_action(ctx: Context, scene_index: int) -> dict:
    """Disable a scene's follow action (Live 12.2+).

    Sets follow_action_enabled=False without touching time/linked/
    multiplier, so re-enabling preserves the prior configuration.
    """
    return _get_ableton(ctx).send_command("clear_scene_follow_action", {
        "scene_index": scene_index,
    })
