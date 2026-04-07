"""Agent OS V1 MCP tools — goal compilation, world model, and evaluation.

3 tools that connect the pure-computation engine (_agent_os_engine.py) to the
live Ableton session via the existing MCP infrastructure.

These tools power the Agent OS cyclical loop:
  compile_goal_vector → build_world_model → [agent acts] → evaluate_move
"""

from __future__ import annotations

import json
from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import _agent_os_engine as engine


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _get_spectral(ctx: Context):
    return ctx.lifespan_context.get("spectral")


def _parse_json_param(value, name: str) -> dict:
    """Parse a dict, JSON string, or None parameter."""
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {name}: {exc}") from exc
    if isinstance(value, dict):
        return value
    raise ValueError(f"{name} must be a dict or JSON string")


# ── compile_goal_vector ───────────────────────────────────────────────


@mcp.tool()
def compile_goal_vector(
    ctx: Context,
    request_text: str,
    targets: dict | str,
    protect: dict | str = "{}",
    mode: str = "improve",
    aggression: float = 0.5,
    research_mode: str = "none",
) -> dict:
    """Compile a user request into a validated GoalVector.

    The agent interprets the user's natural language into quality dimensions,
    then this tool validates the schema and normalizes weights.

    targets: dict of dimension → weight (e.g., {"punch": 0.4, "weight": 0.3, "energy": 0.3}).
             Weights are normalized to sum to 1.0.
    protect: dict of dimension → minimum threshold (e.g., {"clarity": 0.8}).
             If a dimension drops below this value after a move, the move is undone.
    mode: observe | improve | explore | finish | diagnose
    aggression: 0.0 (subtle) to 1.0 (bold)
    research_mode: none | targeted | deep

    Valid dimensions: energy, punch, weight, density, brightness, warmth,
    width, depth, motion, contrast, clarity, cohesion, groove, tension,
    novelty, polish, emotion.
    """
    targets_dict = _parse_json_param(targets, "targets")
    protect_dict = _parse_json_param(protect, "protect")

    gv = engine.validate_goal_vector(
        request_text=request_text,
        targets=targets_dict,
        protect=protect_dict,
        mode=mode,
        aggression=float(aggression),
        research_mode=research_mode,
    )

    return {
        "goal_vector": gv.to_dict(),
        "measurable_dimensions": [
            d for d in gv.targets if d in engine.MEASURABLE_PROXIES
        ],
        "unmeasurable_dimensions": [
            d for d in gv.targets if d not in engine.MEASURABLE_PROXIES
        ],
    }


# ── build_world_model ─────────────────────────────────────────────────


@mcp.tool()
def build_world_model(ctx: Context) -> dict:
    """Build a WorldModel snapshot of the current Ableton session.

    Reads session info, spectral data (if analyzer available), per-track
    device health, and infers track roles from names. Degrades gracefully
    if M4L Analyzer is not loaded.

    Returns topology (tracks, devices, scenes), sonic state (spectrum, RMS, key),
    technical state (analyzer/FluCoMa availability, plugin health), and
    inferred track roles.
    """
    ableton = _get_ableton(ctx)
    spectral = _get_spectral(ctx)

    # Fetch session info (always available)
    session_info = ableton.send_command("get_session_info")

    # Fetch per-track device info for plugin health checks (I2 fix)
    track_infos = []
    for track in session_info.get("tracks", []):
        try:
            ti = ableton.send_command("get_track_info", {
                "track_index": track["index"]
            })
            track_infos.append(ti)
        except Exception:
            pass  # Skip tracks that fail — don't block world model build

    # Fetch spectral data (may be unavailable)
    spectrum = None
    rms = None
    detected_key = None
    flucoma_status = None

    if spectral and spectral.is_connected:
        spec_data = spectral.get("spectrum")
        if spec_data:
            spectrum = {"bands": spec_data["value"]}

        rms_data = spectral.get("rms")
        if rms_data:
            rms = rms_data["value"] if isinstance(rms_data["value"], dict) else {"rms": rms_data["value"]}

        key_data = spectral.get("key")
        if key_data:
            detected_key = key_data["value"] if isinstance(key_data["value"], dict) else {"key": key_data["value"]}

        flucoma_data = spectral.get("flucoma_status")
        if flucoma_data:
            flucoma_status = flucoma_data["value"] if isinstance(flucoma_data["value"], dict) else {}
    else:
        flucoma_status = {"flucoma_available": False}

    # Build model
    wm = engine.build_world_model_from_data(
        session_info=session_info,
        spectrum=spectrum,
        rms=rms,
        detected_key=detected_key,
        flucoma_status=flucoma_status,
        track_infos=track_infos,
    )

    # Run critics with all-dimensions stub goal to surface all issues.
    # The agent should filter these against its actual GoalVector.
    goal_stub = engine.GoalVector(
        request_text="world_model_build",
        targets={d: 1.0 / len(engine.QUALITY_DIMENSIONS) for d in engine.QUALITY_DIMENSIONS},
        mode="observe",
    )
    sonic_issues = engine.run_sonic_critic(wm.sonic, goal_stub, wm.track_roles)
    technical_issues = engine.run_technical_critic(wm.technical)

    result = wm.to_dict()
    result["issues"] = {
        "sonic": [i.to_dict() for i in sonic_issues],
        "technical": [i.to_dict() for i in technical_issues],
        "total_count": len(sonic_issues) + len(technical_issues),
        "note": "Issues are unfiltered — filter against your GoalVector targets before acting.",
    }
    return result


# ── evaluate_move ─────────────────────────────────────────────────────


@mcp.tool()
def evaluate_move(
    ctx: Context,
    goal_vector: dict | str,
    before_snapshot: dict | str,
    after_snapshot: dict | str,
) -> dict:
    """Evaluate whether a production move improved the mix toward the goal.

    Takes before/after sonic snapshots and the active GoalVector.
    Returns a score and keep/undo recommendation.

    Snapshots should contain: spectrum (8-band dict), rms, peak.
    Get these from get_master_spectrum + get_master_rms before and after
    making changes.

    Hard rules enforce undo when:
    - No measurable improvement (delta <= 0)
    - Protected dimension dropped below its threshold or by > 0.15
    - Total score < 0.40

    When all target dimensions are unmeasurable (e.g., groove, tension),
    the tool defers keep/undo to the agent's musical judgment.

    Returns consecutive_undo_hint=true when keep_change=false — the agent
    should track consecutive undos and switch to observe mode after 3.
    """
    gv_dict = _parse_json_param(goal_vector, "goal_vector")
    before = _parse_json_param(before_snapshot, "before_snapshot")
    after = _parse_json_param(after_snapshot, "after_snapshot")

    # I6 fix: validate the GoalVector to catch malformed input
    gv = engine.validate_goal_vector(
        request_text=gv_dict.get("request_text", "evaluate"),
        targets=gv_dict.get("targets", {}),
        protect=gv_dict.get("protect", {}),
        mode=gv_dict.get("mode", "improve"),
        aggression=float(gv_dict.get("aggression", 0.5)),
        research_mode=gv_dict.get("research_mode", "none"),
    )

    return engine.compute_evaluation_score(gv, before, after)
