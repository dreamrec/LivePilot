"""Performance Engine MCP tools — 3 tools for live performance mode.

Each tool fetches scene data from Ableton via the shared connection,
then delegates to pure-computation modules.
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from .models import EnergyWindow, SceneRole
from .planner import build_performance_state, plan_scene_transition, suggest_energy_moves
from .safety import classify_move_safety, get_blocked_moves, get_safe_moves
import logging

logger = logging.getLogger(__name__)



# ── Helpers ─────────────────────────────────────────────────────────


# BUG-E4 / E5 fix: performance_engine used to have its own _infer_role() keyword
# list and _infer_energy() static {role → number} table. Those diverged from
# _composition_engine's richer section classifier, which caused
# get_performance_state and analyze_composition to label the same scenes
# differently (Deep Flow: drop vs verse, Sun Peak: drop vs chorus) and to
# report dissimilar energies (composition derived from active-track density,
# performance looked up a hard-coded 0.2/0.4/0.7 table). Now performance
# consumes composition's section graph as the source of truth and only keeps
# a positional fallback for scenes without enough data.
_POSITIONAL_FALLBACK_ROLES = {
    "first": "intro",
    "last": "outro",
    "early": "intro",
    "middle_low": "verse",
    "middle_high": "chorus",
    "late": "outro",
    "default": "verse",
}


def _positional_fallback_role(index: int, scene_count: int) -> str:
    """Map a scene index to a role when no composition data is available.

    Kept only as a last-resort so we still produce a sensible answer for
    unnamed scenes or when build_section_graph_from_scenes returns empty.
    Callers should prefer the composition-engine result when it exists.
    """
    if scene_count <= 0:
        return _POSITIONAL_FALLBACK_ROLES["default"]
    if index == 0:
        return _POSITIONAL_FALLBACK_ROLES["first"]
    if index == scene_count - 1:
        return _POSITIONAL_FALLBACK_ROLES["last"]
    if scene_count > 4:
        quarter = scene_count / 4.0
        if index < quarter:
            return _POSITIONAL_FALLBACK_ROLES["early"]
        if index < quarter * 2:
            return _POSITIONAL_FALLBACK_ROLES["middle_low"]
        if index < quarter * 3:
            return _POSITIONAL_FALLBACK_ROLES["middle_high"]
        return _POSITIONAL_FALLBACK_ROLES["late"]
    return _POSITIONAL_FALLBACK_ROLES["default"]


def _positional_fallback_energy(role: str) -> float:
    """Static energy map used only when density is unavailable.

    Kept tiny and explicit so the fallback path is obvious — the primary
    source of energy is _composition_engine's density-based value.
    """
    return {
        "intro": 0.3,
        "verse": 0.4,
        "build": 0.6,
        "chorus": 0.7,
        "drop": 0.9,
        "breakdown": 0.3,
        "transition": 0.5,
        "outro": 0.2,
    }.get(role, 0.5)


def _fetch_scene_data(ctx: Context) -> tuple[list[SceneRole], int]:
    """Fetch scene info + composition graph from Ableton and build SceneRole list.

    BUG-E4 / E5 fix: roles + energies now flow from composition_engine's
    build_section_graph_from_scenes, which uses keyword matching + active-
    track density for energy. Unnamed scenes fall back to the positional
    heuristic. This keeps get_performance_state in sync with
    get_section_graph / analyze_composition.
    """
    from ..tools._composition_engine import (
        build_section_graph_from_scenes,
        SectionNode as CESectionNode,
    )

    ableton = ctx.lifespan_context["ableton"]

    scenes_info = ableton.send_command("get_scenes_info", {})
    scenes_list = scenes_info.get("scenes", [])
    scene_count = len(scenes_list)

    # Pull session topology + clip matrix so composition engine can compute
    # active-track density. If any of these fails we fall back to the
    # positional heuristic — preserving the old behavior as a safety net.
    track_count = 0
    clip_matrix: list[list[dict]] = []
    try:
        session_info = ableton.send_command("get_session_info", {})
        track_count = int(session_info.get("track_count", 0))
    except Exception as exc:
        logger.debug("_fetch_scene_data session_info failed: %s", exc)
    try:
        mtx = ableton.send_command("get_scene_matrix", {})
        if isinstance(mtx, dict):
            clip_matrix = mtx.get("matrix", []) or []
    except Exception as exc:
        logger.debug("_fetch_scene_data scene_matrix failed: %s", exc)

    # Build the composition section graph. Each SectionNode has
    # section_id = f"sec_{raw_enumerate_index:02d}" per BUG-E1 fix, so we
    # can index by scene position directly.
    ce_sections: list[CESectionNode] = []
    try:
        if scenes_list and clip_matrix and track_count > 0:
            ce_sections = build_section_graph_from_scenes(
                scenes_list, clip_matrix, track_count,
            )
    except Exception as exc:
        logger.debug("_fetch_scene_data section graph failed: %s", exc)

    ce_by_scene_idx: dict[int, CESectionNode] = {}
    for sec in ce_sections:
        # section_id format "sec_02" → scene index 2 (raw enumerate index)
        sid = str(sec.section_id)
        if sid.startswith("sec_"):
            try:
                ce_by_scene_idx[int(sid[4:])] = sec
            except ValueError:
                pass

    scene_roles: list[SceneRole] = []
    for i, scene_data in enumerate(scenes_list):
        name = scene_data.get("name", f"Scene {i}")
        ce_sec = ce_by_scene_idx.get(i)
        if ce_sec is not None:
            # SectionType is an enum; .value gives the string vocabulary
            stype = ce_sec.section_type
            role = stype.value if hasattr(stype, "value") else str(stype)
            energy = float(ce_sec.energy)
        else:
            # Unnamed scene or build failed — positional fallback
            role = _positional_fallback_role(i, scene_count)
            energy = _positional_fallback_energy(role)

        scene_roles.append(SceneRole(
            scene_index=i,
            name=name,
            energy_level=energy,
            role=role,
        ))

    # Determine current scene — default to 0 since session_info
    # doesn't expose a selected_scene field
    current_scene = 0
    try:
        session_info = ableton.send_command("get_session_info", {})
        session_scenes = session_info.get("scenes", [])
        for i, s in enumerate(session_scenes):
            if s.get("is_triggered", False):
                current_scene = i
                break
    except Exception as exc:
        logger.debug("_fetch_scene_data current_scene failed: %s", exc)

    return scene_roles, current_scene


# ── MCP Tools ───────────────────────────────────────────────────────


@mcp.tool()
def get_performance_state(ctx: Context) -> dict:
    """Get current live performance overview — scenes, energy, safe moves.

    Returns scene roles with energy levels, current energy window
    with steering direction, available safe moves, and blocked move types.
    Use this to understand the performance context before making changes.
    """
    scene_roles, current_scene = _fetch_scene_data(ctx)
    state = build_performance_state(scene_roles, current_scene)
    return state.to_dict()


@mcp.tool()
def get_performance_safe_moves(ctx: Context) -> dict:
    """Get available safe moves for live performance.

    Returns only performance-safe moves based on current scene
    and energy direction. All moves are reversible and low-risk.
    Also returns the full blocked move list for transparency.
    """
    scene_roles, current_scene = _fetch_scene_data(ctx)
    state = build_performance_state(scene_roles, current_scene)

    # Also get energy-specific suggestions
    current = None
    for s in scene_roles:
        if s.scene_index == current_scene:
            current = s
            break

    energy_moves: list[dict] = []
    if current is not None:
        em = suggest_energy_moves(state.energy_window, current)
        energy_moves = [m.to_dict() for m in em]

    return {
        "safe_moves": [m.to_dict() for m in state.safe_moves],
        "energy_moves": energy_moves,
        "blocked_moves": state.blocked_moves,
        "safe_move_count": len(state.safe_moves),
        "energy_move_count": len(energy_moves),
    }


@mcp.tool()
def plan_scene_handoff(
    ctx: Context,
    from_scene: int,
    to_scene: int,
) -> dict:
    """Plan a safe transition between two scenes.

    Generates an energy path and gesture sequence for smooth
    scene-to-scene handoffs during live performance.

    Args:
        from_scene: Source scene index.
        to_scene: Destination scene index.
    """
    scene_roles, _ = _fetch_scene_data(ctx)

    # Find the two scenes
    from_role = None
    to_role = None
    for s in scene_roles:
        if s.scene_index == from_scene:
            from_role = s
        if s.scene_index == to_scene:
            to_role = s

    if from_role is None:
        return {"error": f"Scene {from_scene} not found", "code": "NOT_FOUND"}
    if to_role is None:
        return {"error": f"Scene {to_scene} not found", "code": "NOT_FOUND"}

    plan = plan_scene_transition(from_role, to_role)
    return {
        "handoff_plan": plan.to_dict(),
        "from_scene": from_role.to_dict(),
        "to_scene": to_role.to_dict(),
        "energy_delta": round(to_role.energy_level - from_role.energy_level, 3),
        "gesture_count": len(plan.gestures),
        "step_count": len(plan.energy_path),
    }
