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


# ── Helpers ─────────────────────────────────────────────────────────


def _infer_role(name: str, index: int, scene_count: int) -> str:
    """Infer a scene's role from its name or position."""
    lower = name.lower()
    for role in ("intro", "verse", "chorus", "build", "drop", "breakdown", "outro", "transition"):
        if role in lower:
            return role
    # Positional fallback
    if index == 0:
        return "intro"
    if index == scene_count - 1:
        return "outro"
    if scene_count > 4:
        quarter = scene_count / 4
        if index < quarter:
            return "intro"
        elif index < quarter * 2:
            return "verse"
        elif index < quarter * 3:
            return "chorus"
        else:
            return "outro"
    return "verse"


def _infer_energy(role: str) -> float:
    """Infer energy level from scene role."""
    energy_map = {
        "intro": 0.2,
        "verse": 0.4,
        "build": 0.6,
        "chorus": 0.7,
        "drop": 0.9,
        "breakdown": 0.3,
        "transition": 0.5,
        "outro": 0.2,
    }
    return energy_map.get(role, 0.5)


def _fetch_scene_data(ctx: Context) -> tuple[list[SceneRole], int]:
    """Fetch scene info from Ableton and build SceneRole list."""
    ableton = ctx.lifespan_context["ableton"]

    scenes_info = ableton.send_command("get_scenes_info", {})
    scenes_list = scenes_info.get("scenes", [])
    scene_count = len(scenes_list)

    scene_roles: list[SceneRole] = []
    for i, scene_data in enumerate(scenes_list):
        name = scene_data.get("name", f"Scene {i}")
        role = _infer_role(name, i, scene_count)
        energy = _infer_energy(role)
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
        # Check if any scene is marked as triggered/playing
        session_scenes = session_info.get("scenes", [])
        for i, s in enumerate(session_scenes):
            if s.get("is_triggered", False):
                current_scene = i
                break
    except Exception:
        pass

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
