"""Mix Engine MCP tools — 6 tools for mix analysis and move planning.

Each tool fetches data from Ableton via the shared connection,
then delegates to pure-computation modules.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import mcp
from ..tools._evaluation_contracts import EvaluationRequest
from ..tools._snapshot_normalizer import normalize_sonic_snapshot
from ..evaluation.fabric import evaluate_sonic_move
from .state_builder import build_mix_state
from .critics import run_all_mix_critics
from .planner import plan_mix_moves


# ── Helpers ─────────────────────────────────────────────────────────


def _fetch_mix_data(ctx: Context) -> dict:
    """Fetch all data needed to build a MixState from Ableton."""
    ableton = ctx.lifespan_context["ableton"]

    session_info = ableton.send_command("get_session_info", {})
    track_count = len(session_info.get("tracks", []))

    track_infos: list[dict] = []
    for i in range(track_count):
        try:
            info = ableton.send_command("get_track_info", {"track_index": i})
            track_infos.append(info)
        except Exception:
            continue

    # Get spectrum and RMS data directly from SpectralCache (not TCP)
    spectrum = None
    rms_data = None
    try:
        spectral = ctx.lifespan_context.get("spectral")
        if spectral and spectral.is_connected:
            spec_data = spectral.get("spectrum")
            if spec_data:
                spectrum = {"bands": spec_data["value"]}
                key_data = spectral.get("key")
                if key_data:
                    spectrum["detected_key"] = key_data["value"]

            rms_snap = spectral.get("rms")
            if rms_snap:
                rms_data = rms_snap["value"] if isinstance(rms_snap["value"], dict) else rms_snap["value"]
    except Exception:
        pass

    return {
        "session_info": session_info,
        "track_infos": track_infos,
        "spectrum": spectrum,
        "rms_data": rms_data,
    }


# ── MCP Tools ───────────────────────────────────────────────────────


@mcp.tool()
def analyze_mix(ctx: Context) -> dict:
    """Build full mix state and run all critics.

    Returns the complete mix analysis including all sub-states
    (balance, masking, dynamics, stereo, depth) and all detected issues.
    """
    data = _fetch_mix_data(ctx)
    mix_state = build_mix_state(
        session_info=data["session_info"],
        track_infos=data["track_infos"],
        spectrum=data["spectrum"],
        rms_data=data["rms_data"],
    )
    issues = run_all_mix_critics(mix_state)
    moves = plan_mix_moves(issues, mix_state)

    return {
        "mix_state": mix_state.to_dict(),
        "issues": [i.to_dict() for i in issues],
        "suggested_moves": [m.to_dict() for m in moves],
        "issue_count": len(issues),
        "move_count": len(moves),
    }


@mcp.tool()
def get_mix_issues(ctx: Context) -> dict:
    """Run all mix critics and return detected issues only.

    Lighter than analyze_mix — skips move planning.
    """
    data = _fetch_mix_data(ctx)
    mix_state = build_mix_state(
        session_info=data["session_info"],
        track_infos=data["track_infos"],
        spectrum=data["spectrum"],
        rms_data=data["rms_data"],
    )
    issues = run_all_mix_critics(mix_state)

    return {
        "issues": [i.to_dict() for i in issues],
        "issue_count": len(issues),
    }


@mcp.tool()
def plan_mix_move(ctx: Context) -> dict:
    """Get ranked move suggestions based on current mix issues.

    Runs critics and planner, returns sorted moves with
    estimated impact and risk scores.
    """
    data = _fetch_mix_data(ctx)
    mix_state = build_mix_state(
        session_info=data["session_info"],
        track_infos=data["track_infos"],
        spectrum=data["spectrum"],
        rms_data=data["rms_data"],
    )
    issues = run_all_mix_critics(mix_state)
    moves = plan_mix_moves(issues, mix_state)

    return {
        "moves": [m.to_dict() for m in moves],
        "move_count": len(moves),
        "issue_count": len(issues),
    }


@mcp.tool()
def evaluate_mix_move(
    ctx: Context,
    before_snapshot: dict,
    after_snapshot: dict,
    targets: dict | None = None,
    protect: dict | None = None,
) -> dict:
    """Score a mix change using the evaluation fabric.

    Compare before/after spectral snapshots and evaluate whether
    the mix move improved the targeted dimensions without harming
    protected ones.

    Args:
        before_snapshot: Spectral snapshot before the move.
        after_snapshot: Spectral snapshot after the move.
        targets: Goal targets {dimension: weight} (e.g. {"clarity": 0.5}).
        protect: Protected dimensions {dimension: threshold}.
    """
    targets = targets or {}
    protect = protect or {}

    request = EvaluationRequest(
        engine="mix_engine",
        goal={"targets": targets},
        before=before_snapshot,
        after=after_snapshot,
        protect=protect,
    )
    result = evaluate_sonic_move(request)
    return result.to_dict()


@mcp.tool()
def get_masking_report(ctx: Context) -> dict:
    """Get detailed frequency collision report.

    Shows all detected masking pairs, severity, and the
    worst collision pair.
    """
    data = _fetch_mix_data(ctx)
    mix_state = build_mix_state(
        session_info=data["session_info"],
        track_infos=data["track_infos"],
        spectrum=data["spectrum"],
        rms_data=data["rms_data"],
    )
    masking = mix_state.masking

    return {
        "masking": masking.to_dict(),
        "collision_count": len(masking.entries),
        "worst_pair": list(masking.worst_pair) if masking.worst_pair else None,
    }


@mcp.tool()
def get_mix_summary(ctx: Context) -> dict:
    """Lightweight mix overview — track count, issue count, dynamics state.

    Faster than full analysis for quick status checks.
    """
    data = _fetch_mix_data(ctx)
    mix_state = build_mix_state(
        session_info=data["session_info"],
        track_infos=data["track_infos"],
        spectrum=data["spectrum"],
        rms_data=data["rms_data"],
    )
    issues = run_all_mix_critics(mix_state)

    return {
        "track_count": len(mix_state.balance.track_states),
        "issue_count": len(issues),
        "dynamics": mix_state.dynamics.to_dict(),
        "stereo": mix_state.stereo.to_dict(),
        "depth": mix_state.depth.to_dict(),
        "anchor_tracks": mix_state.balance.anchor_tracks,
        "loudest_track": mix_state.balance.loudest_track,
        "quietest_track": mix_state.balance.quietest_track,
    }
